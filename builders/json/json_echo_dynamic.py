"""json-echo-dynamic.atz: json-echo-dynamic.json parsed and rewritten compactly on the dynamic target.

The document is read and echoed on the host at compile time, through json-dynamic.atz's parser and writer; the
result then becomes the message of a hello-wasi style wasm app, only so `at run` has something to print: the
json work is all done by the time that app is built. A malformed document makes the message `json error <code>`
and the app exit with status 1.
"""

from ..wasm.wat import bind_types
from . import json_dynamic

DOC = "json-echo-dynamic.json"


def _host(e):
    """The compile-time block: parses the document and yields the compact text as `message` with a `status`."""
    out = []
    out.append(e.let("jd", e.import_local("jd", json_dynamic.FILE)))
    out.append(e.let("f", e.import_local("doc", DOC)))
    out.append(
        e.let(
            "bytes",
            e.mb.as_(
                e.call_m(e.v("f"), "read", e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v("f"), "len")))),
                e.list_type(e.mb.builtin("types", "ubyte")),
            ),
        )
    )
    out.append(
        e.let(
            "r",
            e.call(e.fld(e.fld(e.v("jd"), "reader"), "new"), e.rec(e.p("bytes", e.v("bytes")), e.p("pos", e.int_of(0)))),
        )
    )
    out.append(e.let("p", e.call(e.fld(e.fld(e.v("jd"), "parser"), "new"), e.v("r"))))
    out.append(e.let("w", e.call(e.fld(e.fld(e.v("jd"), "writer"), "new"), e.tup())))
    out.append(e.let("status", e.int_of(0)))
    out.append(e.let("err", e.int_of(0)))

    def method(v, name, *args):
        return e.call_m(e.v(v), name, args[0] if len(args) == 1 else e.tup(*args))

    def piece(name, *args):
        return e.p(name, method("w", name, *args) if args else method("w", name, e.tup()))

    out.append(
        e.mb.labeled(
            "doc",
            e.mb.loop(
                e.match_of(
                    method("p", "next", e.tup()),
                    "ev",
                    None,
                    e.p("end", e.mb.return_label("doc")),
                    e.p("error", e.seq(e.mb.set(e.v("status"), e.int_of(1)), e.mb.set(e.v("err"), e.v("ev")), e.mb.return_label("doc"))),
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
        )
    )
    out.append(
        e.let(
            "message",
            e.if_else(
                e.eq(e.v("status"), e.int_of(0)),
                e.cat(method("w", "text", e.tup()), e.s("\n")),
                e.cat(e.s("json error "), e.to_str(e.v("err")), e.s("\n")),
            ),
        )
    )
    out.append(
        e.ret(
            e.rec(
                e.p("message", e.v("message")),
                e.p("len", e.fld(e.call(e.mb.eval_str_utf8(), e.v("message")), "len")),
                e.p("status", e.v("status")),
            )
        )
    )
    return out


def module(e):
    # The wasm app printing the message, as hello-wasi does.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    for name in ["fd_write", "proc_exit"]:
        setup.append(e.let(name + "_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s(name))))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    exported = ["m", "fd_write_fn_t", "proc_exit_fn_t", "start_fn_t", "t_u32"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("h", e.lower(e.mb.seq(_host(e)))))
    top.append(e.let("message", e.fld(e.v("h"), "message")))
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name in ["fd_write", "proc_exit"]:
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
    top.append(e.let("text", e.call_m(e.v("m"), "cstr", e.v("message"))))
    for name, values in [("iov", e.tup(e.v("text"), e.fld(e.v("h"), "len"))), ("nwritten", e.tup(e.n(0)))]:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "data_fn"),
                    e.rec(e.p("mod", e.v("m")), e.p("name", e.s(name)), e.p("elem", e.v("t_u32")), e.p("values", values)),
                ),
            )
        )
    body = e.seq(
        e.call(e.lower(e.v("fd_write")), e.tup(e.n(1), e.lower(e.v("iov")), e.n(1), e.lower(e.v("nwritten")))),
        e.call(e.lower(e.v("proc_exit")), e.call(e.lower(e.v("t_u32")), e.lower(e.fld(e.v("h"), "status")))),
    )
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
