"""hello-web.atz: wasm web app appending an <h1> to the document via the WebIDL hooks. Its handles (window, document,
the h1, the body read from the out cell and wrapped) are owned and released when `_start` returns."""

from ..wasm.wat import bind_types

TAG = "h1"
MESSAGE = "Hello world"


def _len(e, s):
    return e.n(len(s.encode()))


def _hook(e, kind, iface, member):
    return e.call(e.fld(e.v("webidl"), kind), e.rec(e.p("iface", e.s(iface)), e.p("member", e.s(member))))


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.ret(e.rec(e.p("m", e.v("m")), e.p("start_fn_t", e.v("start_fn_t")), e.p("t_i32", e.v("t_i32")))))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    top.append(e.let("web", e.import_local("web", "web-wasm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    top.append(e.let("m", e.fld(e.v("k"), "m")))
    top.append(e.let("tag", e.call_m(e.v("m"), "cstr", e.s(TAG))))
    top.append(e.let("text", e.call_m(e.v("m"), "cstr", e.s(MESSAGE))))
    top.append(
        e.let(
            "cell",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("cell")),
                    e.p("elem", e.fld(e.v("k"), "t_i32")),
                    e.p("values", e.tup(e.n(0), e.n(0))),
                ),
            ),
        )
    )
    top.append(e.let("document", _hook(e, "get", "Window", "document")))
    top.append(e.let("create", _hook(e, "op", "Document", "createElement")))
    top.append(e.let("set_text", _hook(e, "set", "Node", "textContent")))
    top.append(e.let("body", _hook(e, "get", "Document", "body")))
    top.append(e.let("append", _hook(e, "op", "Node", "appendChild")))
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("_start")),
                    e.p("params", e.tup()),
                    e.p("ty", e.fld(e.v("k"), "start_fn_t")),
                    e.p(
                        "body",
                        e.stage(
                            e.seq(
                                e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
                                e.let("doc", e.call(e.lower(e.v("document")), e.v("win"))),
                                e.let(
                                    "h1",
                                    e.call(
                                        e.lower(e.v("create")),
                                        e.tup(e.v("doc"), e.lower(e.v("tag")), _len(e, TAG), e.n(0), e.n(0), e.n(0)),
                                    ),
                                ),
                                e.call(
                                    e.lower(e.v("set_text")),
                                    e.tup(e.v("h1"), e.n(1), e.lower(e.v("text")), _len(e, MESSAGE)),
                                ),
                                e.call(e.lower(e.v("body")), e.tup(e.v("doc"), e.lower(e.v("cell")))),
                                e.let(
                                    "b",
                                    e.call(
                                        e.lower(e.fld(e.v("webidl"), "handle")),
                                        e.mb.field(e.lower(e.v("cell")), e.n(1)),
                                    ),
                                ),
                                e.call(e.lower(e.v("append")), e.tup(e.v("b"), e.v("h1"))),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.ret(e.call(e.fld(e.v("web"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
