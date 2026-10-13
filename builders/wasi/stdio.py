"""stdio-wasi.atz: stdin and stdout as byte functions of a wasm module, buffered over wasi's fd_read and fd_write.

Exports, all dependencies (`func_dep`) a module gets when its code first uses them, over static buffers of
their own:

    read (ctx) -> i32         the next byte of stdin, or -1 at its end (or on failure); `ctx` is ignored
    write (ctx, b)            buffers a byte of stdout
    flush ()                  writes the buffered bytes out
    exit (code)               proc_exit
    pv                        the pointer type, for a null `ctx`
"""

from ..wasm.wat import bind_types

FILE = "stdio-wasi.atz"

BUF = 4096
CELL_IN_POS = 0
CELL_IN_LEN = 1
CELL_OUT_LEN = 2
CELLS = 3


def _lo(e, name):
    return e.lower(e.v(name))


def _fn_t(e, params, ret):
    return e.call(
        e.fld(e.v("wasm"), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))),
    )


def _dep(e, name, params, fn_t, body_):
    return e.let(
        name,
        e.call(
            e.fld(e.v("wasm"), "func_dep"),
            e.rec(
                e.p("name", e.s("stdio_" + name)),
                e.p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                e.p("ty", e.v(fn_t)),
                e.p("body", e.stage(body_)),
            ),
        ),
    )


def module(e):
    # The types and blocks, computed one level down so the imports and dependencies take them as constants.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    bind_types(e, setup)
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    setup.append(e.let("read_fn_t", _fn_t(e, ["t_pv"], "t_i32")))
    setup.append(e.let("write_fn_t", _fn_t(e, ["t_pv", "t_i32"], "t_void")))
    setup.append(e.let("flush_fn_t", _fn_t(e, [], "t_void")))
    setup.append(e.let("exit_fn_t", _fn_t(e, ["t_i32"], "t_void")))
    for name in ["fd_read", "fd_write", "proc_exit"]:
        setup.append(e.let(name + "_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s(name))))
    blocks = [("cells", 4 * CELLS), ("inbuf", BUF), ("outbuf", BUF), ("in_iov", 8), ("out_iov", 8), ("nread", 4), ("nwritten", 4)]
    for name, size in blocks:
        setup.append(
            e.let(
                name,
                e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(e.p("name", e.s("stdio_" + name)), e.p("size", e.int_of(size)))),
            )
        )
    exported = ["t_i32", "t_u8", "t_u32", "t_void", "t_pv", "t_pu8", "t_pu32", "t_pi32"]
    exported += ["read_fn_t", "write_fn_t", "flush_fn_t", "exit_fn_t", "fd_read_fn_t", "fd_write_fn_t", "proc_exit_fn_t"]
    exported += [name for name, _ in blocks]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name in ["fd_read", "fd_write", "proc_exit"]:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(
                        e.p("module", e.fld(e.v("wasi"), "module")),
                        e.p("name", e.s(name)),
                        e.p("ty", e.v(name + "_fn_t")),
                    ),
                ),
            )
        )

    def block(name, ptr_type):
        """A static block as a typed pointer (in a body)."""
        return e.mb.as_(e.call(_lo(e, name), e.tup()), _lo(e, ptr_type))

    def cell(index):
        return e.mb.field(block("cells", "t_pi32"), e.n(index))

    def byte_at(buf, index):
        return e.mb.field(block(buf, "t_pu8"), index)

    def conv(type_name, v):
        return e.call(_lo(e, type_name), v)

    def addr(name):
        """A static block's address as u32 (for an iovec)."""
        return e.mb.as_(block(name, "t_pv"), _lo(e, "t_u32"))

    def count(name):
        """The i32 a wasi call stored in the block."""
        return e.mb.field(block(name, "t_pi32"), e.n(0))

    read_body = e.seq(
        e.let("r", conv("t_i32", e.n(-1))),
        e.if_only(
            e.mb.operator_ge(cell(CELL_IN_POS), cell(CELL_IN_LEN)),
            e.seq(
                e.mb.set(e.mb.field(block("in_iov", "t_pu32"), e.n(0)), addr("inbuf")),
                e.mb.set(e.mb.field(block("in_iov", "t_pu32"), e.n(1)), conv("t_u32", e.n(BUF))),
                e.let(
                    "errno",
                    e.call(_lo(e, "fd_read"), e.tup(e.n(0), block("in_iov", "t_pv"), e.n(1), block("nread", "t_pv"))),
                ),
                e.if_only(
                    e.eq(e.v("errno"), e.n(0)),
                    e.seq(
                        e.let("got", count("nread")),
                        e.if_only(
                            e.mb.operator_gt(e.v("got"), e.n(0)),
                            e.seq(e.mb.set(cell(CELL_IN_LEN), e.v("got")), e.mb.set(cell(CELL_IN_POS), e.n(0))),
                        ),
                    ),
                ),
            ),
        ),
        e.if_only(
            e.mb.operator_lt(cell(CELL_IN_POS), cell(CELL_IN_LEN)),
            e.seq(
                e.mb.set(e.v("r"), conv("t_i32", byte_at("inbuf", cell(CELL_IN_POS)))),
                e.mb.set(cell(CELL_IN_POS), e.mb.operator_add(cell(CELL_IN_POS), e.n(1))),
            ),
        ),
        e.ret(e.v("r")),
    )
    flush_body = e.if_only(
        e.mb.operator_gt(cell(CELL_OUT_LEN), e.n(0)),
        e.seq(
            e.mb.set(e.mb.field(block("out_iov", "t_pu32"), e.n(0)), addr("outbuf")),
            e.mb.set(e.mb.field(block("out_iov", "t_pu32"), e.n(1)), conv("t_u32", cell(CELL_OUT_LEN))),
            e.call(_lo(e, "fd_write"), e.tup(e.n(1), block("out_iov", "t_pv"), e.n(1), block("nwritten", "t_pv"))),
            e.mb.set(cell(CELL_OUT_LEN), e.n(0)),
        ),
    )
    write_body = e.seq(
        e.if_only(e.mb.operator_ge(cell(CELL_OUT_LEN), e.n(BUF)), e.call(_lo(e, "flush"), e.tup())),
        e.mb.set(byte_at("outbuf", cell(CELL_OUT_LEN)), conv("t_u8", e.v("b"))),
        e.mb.set(cell(CELL_OUT_LEN), e.mb.operator_add(cell(CELL_OUT_LEN), e.n(1))),
    )
    exit_body = e.call(_lo(e, "proc_exit"), conv("t_u32", e.v("code")))
    top.append(_dep(e, "read", ["ctx"], "read_fn_t", read_body))
    top.append(_dep(e, "flush", [], "flush_fn_t", flush_body))
    top.append(_dep(e, "write", ["ctx", "b"], "write_fn_t", write_body))
    top.append(_dep(e, "exit", ["code"], "exit_fn_t", exit_body))
    top.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in ["read", "write", "flush", "exit"]], e.p("pv", e.v("t_pv")))))
    return top
