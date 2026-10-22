"""js-decls-test.atz (`decls`) and js-decls-app-test.atz: a declarations module exporting a js object type that refers
to itself (`Node.parent: Node | null`), and an app importing it (harness/verify-js-decls.sh runs it under node), so a
cyclic declaration crosses a module boundary."""


def _jsf(e, name):
    return e.fld(e.v("js"), name)


def _def(e, kind, *fields):
    return e.call(_jsf(e, kind), e.rec(*fields))


def _fn(e, params, ret):
    return _def(e, "fn", e.p("params", e.tup(*params)), e.p("ret", ret))


def module(e, part):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    if part == "decls":
        top.append(e.let("node", _def(e, "object", e.p("name", e.s("Node")))))
        top.append(e.let("parent_t", _def(e, "union", e.p("node", e.v("node")), e.p("none", _jsf(e, "null")))))
        top.append(
            _def(
                e,
                "members",
                e.p("object", e.v("node")),
                e.p("fields", e.rec(e.p("name", _jsf(e, "string")), e.p("parent", e.v("parent_t")))),
                e.p("methods", e.rec()),
            )
        )
        top.append(e.ret(e.rec(e.p("node", e.v("node")))))
        return top
    top.append(e.let("decls", e.import_local("decls", "js-decls-test.atz")))
    top.append(e.let("m", e.call(_jsf(e, "new"), e.tup())))
    string = _jsf(e, "string")
    top.append(
        e.let(
            "log",
            _def(e, "global_fn", e.p("name", e.s("console.log")), e.p("ty", _fn(e, [string], _jsf(e, "void")))),
        )
    )
    node = e.lower(e.fld(e.v("decls"), "node"))

    def parent_of(n):
        return e.match_of(
            e.fld(n, "parent"),
            "p",
            None,
            (
                "node",
                e.call(
                    e.lower(e.v("log")),
                    e.mb.operator_add(e.mb.as_(e.s("parent "), e.lower(string)), e.fld(e.v("p"), "name")),
                ),
            ),
            ("none", e.call(e.lower(e.v("log")), e.mb.as_(e.s("root"), e.lower(string)))),
        )

    staged = e.seq(
        e.let("a", e.mb.as_(e.rec(e.p("name", e.s("a")), e.p("parent", e.tup())), node)),
        e.let("b", e.mb.as_(e.rec(e.p("name", e.s("b")), e.p("parent", e.v("a"))), node)),
        parent_of(e.v("b")),
        parent_of(e.v("a")),
    )
    top.append(e.call_m(e.v("m"), "run", e.stage(staged)))
    top.append(e.let("out", e.call_m(e.v("m"), "render", e.rec(e.p("frames", e.s("frames.json"))))))
    top.append(
        e.ret(
            e.call(
                e.mb.builtin("dir"),
                e.map_new(
                    e.mb.types_string(),
                    e.call(e.mb.types_array(), e.mb.types_byte()),
                    e.p("main.js", e.call(e.mb.eval_str_utf8(), e.fld(e.v("out"), "js"))),
                ),
            )
        )
    )
    return top
