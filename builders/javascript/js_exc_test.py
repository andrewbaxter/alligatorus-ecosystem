"""js-exc-test.atz: a js app dir exercising exceptions on the js target (harness/verify-js-exc.sh runs it under node
and compares its lines and exit): a language `throw` out of a function declared to throw, caught by its caller; a
`finally` on the normal and the exceptional path; a declared throwing host function (`JSON.parse` throws a
`SyntaxError`); an owned value (destructor.atz) dropped while the exception unwinds; a valued `try`; and a `panic`,
which no catch takes."""


def _jsf(e, name):
    return e.fld(e.v("js"), name)


def _def(e, kind, *fields):
    return e.call(_jsf(e, kind), e.rec(*fields))


def _fn(e, params, ret, throws=None):
    fields = [e.p("params", e.tup(*params)), e.p("ret", ret)]
    if throws is not None:
        fields.append(e.p("throws", throws))
    return _def(e, "fn", *fields)


def _s(e, text):
    return e.mb.as_(e.s(text), e.lower(_jsf(e, "string")))


def _log(e, text):
    return e.call(e.lower(e.v("log")), text)


def _num(e, n):
    return e.call(e.lower(e.v("str")), n)


def _try(e, body, name, exc_t, catch_body, finally_=None):
    return e.mb.try_catch_finally(body, (name, exc_t, catch_body), finally_)


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("destructor", e.import_local("destructor", "destructor.atz")))
    top.append(e.let("m", e.call(_jsf(e, "new"), e.tup())))
    number, string, void = _jsf(e, "number"), _jsf(e, "string"), _jsf(e, "void")
    top.append(e.let("syntax_t", _def(e, "object", e.p("name", e.s("SyntaxError")))))
    top.append(
        _def(
            e,
            "members",
            e.p("object", e.v("syntax_t")),
            e.p("fields", e.rec(e.p("name", string))),
            e.p("methods", e.rec()),
        )
    )
    top.append(e.let("parsed_t", _def(e, "object", e.p("name", e.s("Parsed")))))
    for name, js_name, ty_ in [
        ("log", "console.log", _fn(e, [string], void)),
        ("str", "String", _fn(e, [number], string)),
        ("parse", "JSON.parse", _fn(e, [string], e.v("parsed_t"), e.v("syntax_t"))),
    ]:
        top.append(e.let(name, _def(e, "global_fn", e.p("name", e.s(js_name)), e.p("ty", ty_))))
    # `drop(n)` logs the owned number it destroys.
    top.append(
        e.let(
            "drop",
            _def(
                e,
                "func_fn",
                e.p("mod", e.v("m")),
                e.p("name", e.s("drop")),
                e.p("params", e.tup(e.s("n"))),
                e.p("ty", _fn(e, [number], void)),
                e.p(
                    "body",
                    e.stage(
                        e.call(
                            e.lower(e.v("log")),
                            e.mb.operator_add(
                                e.mb.as_(e.s("drop "), e.lower(string)), e.call(e.lower(e.v("str")), e.v("n"))
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    top.append(
        e.let(
            "owned_r",
            e.call(e.fld(e.v("destructor"), "type"), e.rec(e.p("under", number), e.p("destroy", e.v("drop")))),
        )
    )
    top.append(e.let("own_n", e.fld(e.v("owned_r"), "own")))
    # `check(n)` returns `n`, or throws `big <n>` when `n` is over 2.
    top.append(
        e.let(
            "check",
            _def(
                e,
                "func_fn",
                e.p("mod", e.v("m")),
                e.p("name", e.s("check")),
                e.p("params", e.tup(e.s("n"))),
                e.p("ty", _fn(e, [number], number, string)),
                e.p(
                    "body",
                    e.stage(
                        e.mb.labeled(
                            "f",
                            e.seq(
                                e.if_only(
                                    e.mb.operator_gt(e.v("n"), e.n(2)),
                                    e.call(
                                        e.mb.as_(e.tup(), e.lower(_jsf(e, "throw"))),
                                        e.mb.operator_add(_s(e, "big "), e.call(e.lower(e.v("str")), e.v("n"))),
                                    ),
                                ),
                                e.mb.return_to("f", e.v("n")),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    string_s = e.lower(string)
    check = e.lower(e.v("check"))
    staged = e.seq(
        _try(
            e,
            e.seq(
                _log(e, e.mb.operator_add(_s(e, "ok "), _num(e, e.call(check, e.n(1))))),
                _log(e, _num(e, e.call(check, e.n(5)))),
            ),
            "err",
            string_s,
            _log(e, e.mb.operator_add(_s(e, "caught "), e.v("err"))),
            _log(e, _s(e, "finally")),
        ),
        _try(
            e,
            e.seq(e.call(e.lower(e.v("parse")), _s(e, "{bad")), e.seq()),
            "err",
            e.lower(e.v("syntax_t")),
            _log(e, e.mb.operator_add(_s(e, "parse "), e.fld(e.v("err"), "name"))),
        ),
        _try(
            e,
            e.seq(
                e.let("o", e.mb.as_(e.mb.as_(e.n(7), e.lower(number)), e.lower(e.v("own_n")))),
                _log(e, _num(e, e.call(check, e.n(9)))),
            ),
            "err",
            string_s,
            _log(e, e.mb.operator_add(_s(e, "caught "), e.v("err"))),
        ),
        e.let(
            "v",
            _try(e, e.call(check, e.n(1)), "err", string_s, e.mb.as_(e.n(0), e.lower(number))),
        ),
        _log(e, e.mb.operator_add(_s(e, "v "), _num(e, e.v("v")))),
        _try(
            e,
            e.call(e.mb.as_(e.tup(), e.lower(_jsf(e, "panic"))), _s(e, "boom")),
            "err",
            string_s,
            _log(e, e.mb.operator_add(_s(e, "caught "), e.v("err"))),
        ),
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
