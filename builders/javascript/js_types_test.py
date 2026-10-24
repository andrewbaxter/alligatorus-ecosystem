"""js-types-test.atz: a js app dir pinning the typed js target's semantics (harness/verify-js-types.sh runs it under
node and compares its lines): `number` and `bigint` with js's operators (float division, int32 bitwise ops, unbounded
BigInts), their conversions, bool and string operators, a typed function, a valued `if`."""


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def _utf8(e, text):
    return e.call(e.mb.eval_str_utf8(), text)


def _js(e, name):
    return e.lower(e.fld(e.v("js"), name))


def _n(e, kind, v):
    """The constant `v` as a js `kind` number."""
    return e.mb.as_(e.n(v), _js(e, kind))


def _s(e, text):
    return e.mb.as_(e.s(text), _js(e, "string"))


def _str(e, kind, v):
    """`String(v)` for a `kind` value (`String` is declared once per parameter type)."""
    return e.call(e.lower(e.v("str_" + kind)), v)


def _log(e, label, text):
    return e.call(e.lower(e.v("log")), e.mb.operator_add(_s(e, label + " "), text))


def _fn(e, params, ret):
    return e.call(e.fld(e.v("js"), "fn"), e.rec(e.p("params", e.tup(*params)), e.p("ret", ret)))


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("m", e.call(e.fld(e.v("js"), "new"), e.tup())))

    def jt(name):
        return e.fld(e.v("js"), name)

    top.append(
        e.let(
            "log",
            e.call(
                e.fld(e.v("js"), "global_fn"),
                e.rec(e.p("name", e.s("console.log")), e.p("ty", _fn(e, [jt("string")], jt("void")))),
            ),
        )
    )
    for kind in ["number", "bigint", "bool"]:
        top.append(
            e.let(
                "str_" + kind,
                e.call(
                    e.fld(e.v("js"), "global_fn"),
                    e.rec(e.p("name", e.s("String")), e.p("ty", _fn(e, [jt(kind)], jt("string")))),
                ),
            )
        )
    # `clamp(a, lo, hi)`: a typed function with two early returns.
    top.append(
        e.let(
            "clamp",
            e.call(
                e.fld(e.v("js"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("clamp")),
                    e.p("params", e.tup(e.s("a"), e.s("lo"), e.s("hi"))),
                    e.p("ty", _fn(e, [jt("number"), jt("number"), jt("number")], jt("number"))),
                    e.p(
                        "body",
                        e.stage(
                            e.mb.labeled(
                                "f",
                                e.seq(
                                    e.if_only(e.mb.operator_lt(e.v("a"), e.v("lo")), e.mb.return_to("f", e.v("lo"))),
                                    e.if_only(e.mb.operator_gt(e.v("a"), e.v("hi")), e.mb.return_to("f", e.v("hi"))),
                                    e.mb.return_to("f", e.v("a")),
                                ),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    add = e.mb.operator_add
    mb = e.mb
    staged = e.seq(
        e.let("n7", _n(e, "number", 7)),
        _log(e, "number div", _str(e, "number", mb.operator_div(e.v("n7"), e.n(2)))),
        _log(e, "number mod", _str(e, "number", mb.operator_mod(mb.operator_neg(e.v("n7")), e.n(2)))),
        _log(e, "number big", _str(e, "number", add(_n(e, "number", 2147483647), e.n(1)))),
        _log(e, "number ushr", _str(e, "number", mb.operator_ushr(_n(e, "number", -1), e.n(28)))),
        _log(e, "number shl", _str(e, "number", mb.operator_shl(_n(e, "number", 1), e.n(31)))),
        _log(e, "number and", _str(e, "number", mb.operator_and(e.v("n7"), e.n(3)))),
        e.let("b32", _n(e, "bigint", 4294967296)),
        _log(e, "bigint mul", _str(e, "bigint", mb.operator_mul(e.v("b32"), e.v("b32")))),
        _log(e, "bigint div", _str(e, "bigint", mb.operator_div(_n(e, "bigint", 7), e.n(2)))),
        _log(e, "bigint mod", _str(e, "bigint", mb.operator_mod(_n(e, "bigint", -7), e.n(2)))),
        _log(
            e,
            "to_bigint",
            _str(e, "bigint", mb.operator_mul(e.call(e.fld(e.v("n7"), "to_bigint"), e.tup()), e.n(3))),
        ),
        _log(
            e,
            "to_number",
            _str(e, "number", mb.operator_div(e.call(e.fld(_n(e, "bigint", 5), "to_number"), e.tup()), e.n(2))),
        ),
        _log(
            e,
            "bool",
            _str(
                e,
                "bool",
                mb.operator_and(
                    mb.operator_lt(_n(e, "number", 1), e.n(2)), e.not_(mb.operator_eq(_n(e, "number", 3), e.n(4)))
                ),
            ),
        ),
        _log(e, "string lt", _str(e, "bool", mb.operator_lt(_s(e, "ab"), _s(e, "b")))),
        _log(e, "string add", add(_s(e, "a"), _s(e, "b"))),
        _log(e, "clamp", _str(e, "number", e.call(e.lower(e.v("clamp")), e.tup(e.n(12), e.n(0), e.n(10))))),
        e.let("lo", mb.if_of([(mb.operator_lt(e.v("n7"), e.n(3)), e.v("n7"))], _n(e, "number", 3))),
        _log(e, "if", _str(e, "number", e.v("lo"))),
    )
    top.append(e.call_m(e.v("m"), "run", e.stage(staged)))
    top.append(e.let("out", e.call_m(e.v("m"), "render", e.rec(e.p("frames", e.s("frames.json"))))))
    top.append(
        e.ret(
            e.call(
                e.mb.builtin("dir"),
                e.map_new(
                    e.mb.types_string(),
                    _bytes_t(e),
                    e.p("main.js", _utf8(e, e.cat(e.fld(e.v("out"), "js"), e.s("//# sourceMappingURL=main.js.map\n")))),
                    e.p("main.js.map", _utf8(e, e.fld(e.v("out"), "map"))),
                    e.p("frames.json", _utf8(e, e.fld(e.v("out"), "frames"))),
                ),
            )
        )
    )
    return top
