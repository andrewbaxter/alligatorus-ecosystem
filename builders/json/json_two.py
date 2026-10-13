"""json-two-wasi.atz / json-two-libc.atz: apps parsing two documents at once through one parser definition, one
per target from this builder.

Two parsers read two embedded documents through json-<target>.atz's slice reader, their `next` calls
interleaved, and two writers collect compact json into two byte vecs through its vec sink; the app then prints
the vecs, one document per line. The module holds one `next` for the reader and one of each writer piece for the
sink, shared by both parsers and both writers.
"""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "json-two-wasi.atz", LLVM: "json-two-libc.atz"}

DOCS = ['{"a": [1, 2, 3], "b": "x"}', '[true, null, {"k": "v"}, -5.5e1]']
EXPECTED = '{"a":[1,2,3],"b":"x"}\n[true,null,{"k":"v"},-5.5e1]\n'


def _lo(e, name):
    return e.lower(e.v(name))


def _fn_t(e, lib, params, ret):
    return e.call(
        e.fld(e.v(lib), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))),
    )


def _json_lets(e, top, lib_file, vec_file, t_u8):
    """The parser over the slice reader, the writer over the vec sink, and the byte vec type."""
    top.append(e.let("json", e.import_local("json", lib_file)))
    top.append(e.let("vec", e.import_local("vec", vec_file)))
    top.append(e.let("bytes", e.call(e.fld(e.v("vec"), "type"), e.v(t_u8))))
    for f in ["type", "new"]:
        top.append(e.let("bytes_" + f, e.fld(e.v("bytes"), f)))
    top.append(e.let("sr", e.fld(e.v("json"), "slice_reader")))
    for f in ["read", "new", "free"]:
        top.append(e.let("sr_" + f, e.fld(e.v("sr"), f)))
    top.append(e.let("vw_write", e.fld(e.fld(e.v("json"), "vec_writer"), "write")))
    top.append(
        e.let("jp", e.call(e.fld(e.v("json"), "parser"), e.rec(e.p("name", e.s("slice")), e.p("read", e.v("sr_read")))))
    )
    for f in ["type", "new"]:
        top.append(e.let("jp_" + f, e.fld(e.v("jp"), f)))
    top.append(
        e.let("jw", e.call(e.fld(e.v("json"), "writer"), e.rec(e.p("name", e.s("vec")), e.p("write", e.v("vw_write")))))
    )
    for f in ["type", "new"]:
        top.append(e.let("jw_" + f, e.fld(e.v("jw"), f)))


def _body(e, docs, write_byte, t_i32):
    """The interleaved parse of the two documents into two vecs, then the vecs to stdout."""

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def step(i):
        """One event of document `i` into its writer; `done<i>` set at the end (an error is reported there too)."""
        w = f"w{i}"

        def piece(name, *args):
            return e.p(name, method(w, name, *args) if args else method(w, name, e.tup()))

        return e.match_of(
            method(f"p{i}", "next", e.tup()),
            "ev",
            None,
            e.p("end", e.mb.set(e.v(f"done{i}"), e.n(1))),
            e.p("error", e.seq(method(w, "int", e.mb.operator_sub(e.n(0), e.v("ev"))), e.mb.set(e.v(f"done{i}"), e.n(1)))),
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

    def print_vec(i):
        return e.seq(
            e.let("n", e.fld(e.v(f"v{i}"), "len")),
            e.let("j", e.mb.as_(e.n(0), _lo(e, t_i32))),
            e.mb.labeled(
                "out",
                e.mb.loop(
                    e.seq(
                        e.if_only(e.mb.operator_ge(e.v("j"), e.v("n")), e.mb.return_label("out")),
                        write_byte(e.call(_lo(e, t_i32), method(f"v{i}", "at", e.v("j")))),
                        e.mb.set(e.v("j"), e.mb.operator_add(e.v("j"), e.n(1))),
                    )
                ),
            ),
            write_byte(e.n(ord("\n"))),
        )

    parts = []
    for i, (doc_ptr, doc_len) in enumerate(docs):
        parts.append(e.let(f"r{i}", e.call(_lo(e, "sr_new"), e.tup(doc_ptr, e.n(doc_len)))))
        parts.append(e.let(f"p{i}", e.call(_lo(e, "jp_type"), e.call(_lo(e, "jp_new"), e.v(f"r{i}")))))
        parts.append(e.let(f"v{i}p", e.call(_lo(e, "bytes_new"), e.tup())))
        parts.append(e.let(f"v{i}", e.call(_lo(e, "bytes_type"), e.v(f"v{i}p"))))
        parts.append(e.let(f"w{i}", e.call(_lo(e, "jw_type"), e.call(_lo(e, "jw_new"), e.v(f"v{i}p")))))
        parts.append(e.let(f"done{i}", e.mb.as_(e.n(0), _lo(e, t_i32))))
    parts.append(
        e.mb.labeled(
            "both",
            e.mb.loop(
                e.seq(
                    e.if_only(
                        e.mb.operator_ge(e.mb.operator_add(e.v("done0"), e.v("done1")), e.n(2)),
                        e.mb.return_label("both"),
                    ),
                    step(0),
                    step(1),
                )
            ),
        )
    )
    parts.append(print_vec(0))
    parts.append(print_vec(1))
    for i in range(len(docs)):
        parts.append(e.call(_lo(e, "sr_free"), e.v(f"r{i}")))
    return e.seq(*parts)


def _llvm(e, mode):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    for prim in ["i32", "u8", "void"]:
        setup.append(e.let("t_" + prim, e.fld(e.v("llvm"), prim)))
    setup.append(e.let("main_fn_t", _fn_t(e, "llvm", [], "t_i32")))
    exported = ["llvm", "ll", "c", "t_i32", "t_u8", "main_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for i, doc in enumerate(DOCS):
        top.append(e.let(f"doc{i}", e.call_m(e.v("ll"), "cstr", e.s(doc))))
    _json_lets(e, top, "json-llvm.atz", "vec-llvm.atz", "t_u8")

    def write_byte(b):
        return e.seq(e.call(e.lower(e.fld(e.v("c"), "putchar")), b), e.seq())

    docs = [(_lo(e, f"doc{i}"), len(doc.encode())) for i, doc in enumerate(DOCS)]
    body = e.seq(_body(e, docs, write_byte, "t_i32"), e.ret(e.n(0)))
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
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("start_fn_t", _fn_t(e, "wasm", [], "t_void")))
    setup.append(e.let("fd_write_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s("fd_write"))))
    for name, size in [("ch", 4), ("iov", 8), ("nwritten", 4)]:
        setup.append(
            e.let(
                name,
                e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(e.p("name", e.s("out_" + name)), e.p("size", e.int_of(size)))),
            )
        )
    for i, doc in enumerate(DOCS):
        setup.append(
            e.let(
                f"doc{i}", e.call(e.fld(e.v("wasm"), "cstr_dep"), e.rec(e.p("name", e.s(f"doc{i}")), e.p("text", e.s(doc))))
            )
        )
    exported = ["m", "t_i32", "t_u8", "t_u32", "t_void", "t_pv", "t_pu8", "t_pu32", "start_fn_t", "fd_write_fn_t"]
    exported += ["ch", "iov", "nwritten"] + [f"doc{i}" for i in range(len(DOCS))]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(
        e.let(
            "fd_write",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    e.p("module", e.fld(e.v("wasi"), "module")),
                    e.p("name", e.s("fd_write")),
                    e.p("ty", e.v("fd_write_fn_t")),
                ),
            ),
        )
    )
    _json_lets(e, top, "json-wasm.atz", "vec-wasm.atz", "t_u8")

    def block(name, ptr_type):
        return e.mb.as_(e.call(_lo(e, name), e.tup()), _lo(e, ptr_type))

    def write_byte(b):
        """One byte to stdout through fd_write (unbuffered: this app prints little)."""
        return e.seq(
            e.mb.set(e.mb.field(block("ch", "t_pu8"), e.n(0)), e.call(_lo(e, "t_u8"), b)),
            e.mb.set(e.mb.field(block("iov", "t_pu32"), e.n(0)), e.mb.as_(block("ch", "t_pv"), _lo(e, "t_u32"))),
            e.mb.set(e.mb.field(block("iov", "t_pu32"), e.n(1)), e.call(_lo(e, "t_u32"), e.n(1))),
            e.call(_lo(e, "fd_write"), e.tup(e.n(1), block("iov", "t_pv"), e.n(1), block("nwritten", "t_pv"))),
        )

    docs = [(e.call(_lo(e, f"doc{i}"), e.tup()), len(doc.encode())) for i, doc in enumerate(DOCS)]
    body = _body(e, docs, write_byte, "t_i32")
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
