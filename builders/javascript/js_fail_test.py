"""js-fail-<case>.atz: js apps that must fail to build with a static error (harness/verify-js-fails.sh checks the
message): an undeclared member, a wrong argument type, a union whose members share a runtime tag, a non-bool
condition, an undeclared global's type, a `throw` in a function declaring no exception type."""


def _jsf(e, name):
    return e.fld(e.v("js"), name)


def _def(e, kind, *fields):
    return e.call(_jsf(e, kind), e.rec(*fields))


def _fn(e, params, ret):
    return _def(e, "fn", e.p("params", e.tup(*params)), e.p("ret", ret))


def module(e, case):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("m", e.call(_jsf(e, "new"), e.tup())))
    number, string = _jsf(e, "number"), _jsf(e, "string")
    top.append(
        e.let(
            "log",
            _def(e, "global_fn", e.p("name", e.s("console.log")), e.p("ty", _fn(e, [string], _jsf(e, "void")))),
        )
    )
    top.append(e.let("point", _def(e, "object", e.p("name", e.s("Point")))))
    top.append(
        _def(
            e,
            "members",
            e.p("object", e.v("point")),
            e.p("fields", e.rec(e.p("x", number))),
            e.p("methods", e.rec()),
        )
    )
    num = e.mb.as_(e.n(1), e.lower(number))
    if case == "member":
        staged = e.seq(
            e.let("p", e.mb.as_(e.rec(e.p("x", e.n(1))), e.lower(e.v("point")))),
            e.call(e.lower(e.v("log")), e.fld(e.v("p"), "z")),
        )
    elif case == "arg":
        staged = e.call(e.lower(e.v("log")), num)
    elif case == "union":
        top.append(e.let("u", _def(e, "union", e.p("a", number), e.p("b", number))))
        staged = e.seq()
    elif case == "cond":
        staged = e.if_only(num, e.call(e.lower(e.v("log")), e.s("x")))
    elif case == "untyped":
        top.append(e.let("g", _def(e, "global_fn", e.p("name", e.s("g")))))
        staged = e.seq()
    else:
        staged = e.call(e.mb.as_(e.tup(), e.lower(_jsf(e, "throw"))), e.mb.as_(e.s("x"), e.lower(string)))
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
