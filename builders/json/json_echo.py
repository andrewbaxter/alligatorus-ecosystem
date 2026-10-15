"""json-echo-wasi.atz / json-echo-libc.atz: apps reading a json document from stdin and writing it back out
compactly, one per target from this builder.

Each app is a reader of stdin and a sink to stdout as target functions (wasi: buffered over fd_read and fd_write;
libc: getchar and putchar), a parser and a writer of json-<target>.atz over them, and a loop matching each event
of the document into the writer. A malformed document prints `json error <code>` and exits with status 1.
"""

from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "json-echo-wasi.atz", LLVM: "json-echo-libc.atz"}

ERROR_TEXT = "json error "

# wasi: the stdin and stdout buffers and the cells of their state
BUF = 4096
CELL_IN_POS = 0
CELL_IN_LEN = 1
CELL_OUT_LEN = 2
CELLS = 3


def _lo(e, name):
    return e.lower(e.v(name))


def _fn_t(e, lib, params, ret):
    return e.call(
        e.fld(e.v(lib), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))),
    )


def _dep(e, lib, name, params, fn_t, body_):
    return e.let(
        name,
        e.call(
            e.fld(e.v(lib), "func_dep"),
            e.rec(
                e.p("name", e.s(name)),
                e.p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                e.p("ty", e.v(fn_t)),
                e.p("body", e.stage(body_)),
            ),
        ),
    )


def _json_lets(e, top, lib_file, read, write):
    """The parser over `read` and the writer over `write`, as top-level values the body lowers."""
    top.append(e.let("json", e.import_local("json", lib_file)))
    top.append(e.let("jp", e.call(e.fld(e.v("json"), "parser"), e.rec(e.p("name", e.s(read)), e.p("read", e.v(read))))))
    for f in ["type", "new"]:
        top.append(e.let("jp_" + f, e.fld(e.v("jp"), f)))
    top.append(
        e.let("jw", e.call(e.fld(e.v("json"), "writer"), e.rec(e.p("name", e.s(write)), e.p("write", e.v(write)))))
    )
    for f in ["type", "new"]:
        top.append(e.let("jw_" + f, e.fld(e.v("jw"), f)))


def _echo(e, null, on_error, write_byte):
    """The parse loop: every event of the document into the writer; `on_error(code)` reports and exits."""

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def piece(name, *args):
        return e.p(name, method("w", name, *args) if args else method("w", name, e.tup()))

    return e.seq(
        e.let("p", e.mb.as_(e.call(_lo(e, "jp_new"), null), _lo(e, "jp_type"))),
        e.let("w", e.mb.as_(e.call(_lo(e, "jw_new"), null), _lo(e, "jw_type"))),
        e.mb.labeled(
            "doc",
            e.mb.loop(
                e.match_of(
                    method("p", "next", e.tup()),
                    "ev",
                    None,
                    e.p("end", e.mb.return_label("doc")),
                    e.p("error", on_error(e.v("ev"))),
                    piece("null"),
                    piece("bool", e.v("ev")),
                    piece("number", e.v("ev")),
                    piece("string", e.v("ev")),
                    piece("key", e.v("ev")),
                    piece("object_begin"),
                    piece("object_end"),
                    piece("array_begin"),
                    piece("array_end"),
                )
            ),
        ),
        write_byte(e.n(ord("\n"))),
    )


def _error_report(e, null, write_byte, code):
    """`json error <code>` on its own line, through a fresh writer for the digits."""
    return e.seq(
        *[write_byte(e.n(ord(ch))) for ch in ERROR_TEXT],
        e.seq(
            e.let("w2", e.mb.as_(e.call(_lo(e, "jw_new"), null), _lo(e, "jw_type"))),
            e.call(e.fld(e.v("w2"), "int"), code),
        ),
        write_byte(e.n(ord("\n"))),
    )


def _llvm(e, mode):
    # One lowered block: the module, the reader and sink dependencies (typed by the library's contract) and the
    # entry point's type, computed so the parser and `func_fn` take them as constants.
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("json", e.import_local("json", "json-llvm.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(e.let("main_fn_t", _fn_t(e, "llvm", [], "t_i32")))
    setup.append(e.let("null", e.call_m(e.v("ll"), "null", e.tup())))
    setup.append(e.let("read_t", e.fld(e.v("json"), "read_t")))
    setup.append(e.let("write_t", e.fld(e.v("json"), "write_t")))
    setup.append(
        _dep(
            e,
            "llvm",
            "stdin_read",
            ["ctx"],
            "read_t",
            e.seq(e.ret(e.call(e.lower(e.fld(e.v("c"), "getchar")), e.tup()))),
        )
    )
    setup.append(
        _dep(
            e,
            "llvm",
            "stdout_write",
            ["ctx", "b"],
            "write_t",
            e.seq(e.call(e.lower(e.fld(e.v("c"), "putchar")), e.v("b")), e.seq()),
        )
    )
    exported = ["llvm", "ll", "c", "main_fn_t", "null", "stdin_read", "stdout_write"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    _json_lets(e, top, "json-llvm.atz", "stdin_read", "stdout_write")

    def write_byte(b):
        return e.seq(e.call(e.lower(e.fld(e.v("c"), "putchar")), b), e.seq())

    def on_error(code):
        return e.seq(
            _error_report(e, _lo(e, "null"), write_byte, code), e.call(e.lower(e.fld(e.v("c"), "exit")), e.n(1))
        )

    body = e.seq(_echo(e, _lo(e, "null"), on_error, write_byte), e.ret(e.n(0)))
    top.append(
        e.let(
            "main",
            e.call(
                e.fld(e.v("llvm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s("main")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("main_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(root_mode_finish(mode, e, e.v("llvm"), e.v("ll")))
    return top


def _wasm(e):
    # One lowered block: the module, the wasi imports (typed by wasi's exports), the stdio blocks, the reader,
    # sink and flush dependencies (typed by the library's contract) and the entry point's type.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("json", e.import_local("json", "json-wasm.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    setup.append(e.let("start_fn_t", _fn_t(e, "wasm", [], "t_void")))
    setup.append(e.let("flush_fn_t", _fn_t(e, "wasm", [], "t_void")))
    setup.append(e.let("read_t", e.fld(e.v("json"), "read_t")))
    setup.append(e.let("write_t", e.fld(e.v("json"), "write_t")))
    for name in ["fd_read", "fd_write", "proc_exit"]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(
                        e.p("module", e.fld(e.v("wasi"), "module")),
                        e.p("name", e.s(name)),
                        e.p("ty", e.fld(e.v("wasi"), name + "_t")),
                    ),
                ),
            )
        )
    for name, size in [
        ("cells", 4 * CELLS),
        ("inbuf", BUF),
        ("outbuf", BUF),
        ("in_iov", 8),
        ("out_iov", 8),
        ("nread", 4),
        ("nwritten", 4),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "alloc_dep"),
                    e.rec(e.p("name", e.s("stdio_" + name)), e.p("size", e.int_of(size))),
                ),
            )
        )

    def block(name, ptr_type):
        """A static block as a typed pointer (in a body)."""
        return e.mb.as_(e.call(fn_of(e, _lo(e, name)), e.tup()), _lo(e, ptr_type))

    def cell(index):
        return e.mb.field(block("cells", "t_pi32"), e.n(index))

    def byte_at(buf, index):
        return e.mb.field(block(buf, "t_pu8"), index)

    def conv(type_name, v):
        return e.mb.as_(v, _lo(e, type_name))

    def addr(name):
        """A static block's address as u32 (for an iovec)."""
        return e.mb.as_(block(name, "t_pv"), _lo(e, "t_u32"))

    def count(name):
        """The i32 a wasi call stored in the block."""
        return e.mb.field(block(name, "t_pi32"), e.n(0))

    # stdin_read(ctx): the next byte of stdin, or -1 once it ends (or fails).
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
    # stdout_flush(): writes out what is buffered.
    flush_body = e.if_only(
        e.mb.operator_gt(cell(CELL_OUT_LEN), e.n(0)),
        e.seq(
            e.mb.set(e.mb.field(block("out_iov", "t_pu32"), e.n(0)), addr("outbuf")),
            e.mb.set(
                e.mb.field(block("out_iov", "t_pu32"), e.n(1)),
                e.call(e.fld(cell(CELL_OUT_LEN), "wrap"), _lo(e, "t_u32")),
            ),
            e.call(_lo(e, "fd_write"), e.tup(e.n(1), block("out_iov", "t_pv"), e.n(1), block("nwritten", "t_pv"))),
            e.mb.set(cell(CELL_OUT_LEN), e.n(0)),
        ),
    )
    # stdout_write(ctx, b): buffers a byte of stdout.
    write_body = e.seq(
        e.if_only(e.mb.operator_ge(cell(CELL_OUT_LEN), e.n(BUF)), e.call(fn_of(e, _lo(e, "stdout_flush")), e.tup())),
        e.mb.set(byte_at("outbuf", cell(CELL_OUT_LEN)), e.call(e.fld(e.v("b"), "wrap"), _lo(e, "t_u8"))),
        e.mb.set(cell(CELL_OUT_LEN), e.mb.operator_add(cell(CELL_OUT_LEN), e.n(1))),
    )
    setup.append(_dep(e, "wasm", "stdin_read", ["ctx"], "read_t", read_body))
    setup.append(_dep(e, "wasm", "stdout_flush", [], "flush_fn_t", flush_body))
    setup.append(_dep(e, "wasm", "stdout_write", ["ctx", "b"], "write_t", write_body))
    exported = [
        "m",
        "t_i32",
        "t_u32",
        "t_void",
        "t_pv",
        "start_fn_t",
        "proc_exit",
        "stdin_read",
        "stdout_flush",
        "stdout_write",
    ]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    _json_lets(e, top, "json-wasm.atz", "stdin_read", "stdout_write")

    def null():
        return e.mb.as_(e.n(0), _lo(e, "t_pv"))

    def write_byte(b):
        return e.call(fn_of(e, _lo(e, "stdout_write")), e.tup(null(), b))

    def on_error(code):
        return e.seq(
            _error_report(e, null(), write_byte, code),
            e.call(fn_of(e, _lo(e, "stdout_flush")), e.tup()),
            e.call(_lo(e, "proc_exit"), conv("t_u32", e.n(1))),
        )

    body = e.seq(_echo(e, null(), on_error, write_byte), e.call(fn_of(e, _lo(e, "stdout_flush")), e.tup()))
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("_start")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("start_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top


def module(e, kind, mode=APP):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e, mode)
    raise AssertionError(kind)
