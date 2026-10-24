"""js-loop-test.atz: a js app dir exercising `loop` and block returns on the js target: a loop left by a return to its
enclosing block, a valued return out of a loop, two returns of one block sharing its slot, a nested loop leaving
the outer block, and a function returning from inside a loop (harness/verify-js-loop.sh runs it under node). The
loops count in the module variables `cnt` and `o`."""


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def _utf8(e, text):
    return e.call(e.mb.eval_str_utf8(), text)


def _js(e, name):
    return e.lower(e.fld(e.v("js"), name))


def _fn(e, params, ret):
    return e.call(e.fld(e.v("js"), "fn"), e.rec(e.p("params", e.tup(*params)), e.p("ret", ret)))


def _log(e, label, n):
    """Logs `label n` (`n` a number)."""
    return e.call(
        e.lower(e.v("log")),
        e.mb.operator_add(e.mb.as_(e.s(label + " "), _js(e, "string")), e.call(e.lower(e.v("str")), n)),
    )


def _incr(e, var):
    return e.mb.set(e.lower(e.v(var)), e.mb.operator_add(e.lower(e.v(var)), e.n(1)))


def _is(e, var, n):
    return e.mb.operator_eq(e.lower(e.v(var)), e.n(n))


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("m", e.call(e.fld(e.v("js"), "new"), e.tup())))
    number = e.fld(e.v("js"), "number")
    string = e.fld(e.v("js"), "string")
    for name, js_name, ty_ in [
        ("log", "console.log", _fn(e, [string], e.fld(e.v("js"), "void"))),
        ("str", "String", _fn(e, [number], string)),
    ]:
        top.append(e.let(name, e.call(e.fld(e.v("js"), "global_fn"), e.rec(e.p("name", e.s(js_name)), e.p("ty", ty_)))))
    for var in ["cnt", "o"]:
        top.append(
            e.let(
                var,
                e.call(
                    e.fld(e.v("js"), "var_fn"),
                    e.rec(e.p("mod", e.v("m")), e.p("name", e.s(var)), e.p("ty", number)),
                ),
            )
        )
    # `drain(limit)` counts `cnt` up to `limit`, returning from the function inside its loop.
    top.append(
        e.let(
            "drain",
            e.call(
                e.fld(e.v("js"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("drain")),
                    e.p("params", e.tup(e.s("limit"))),
                    e.p("ty", _fn(e, [number], number)),
                    e.p(
                        "body",
                        e.stage(
                            e.mb.labeled(
                                "drain",
                                e.mb.loop(
                                    e.seq(
                                        e.if_only(
                                            e.mb.operator_eq(e.lower(e.v("cnt")), e.v("limit")),
                                            e.mb.return_to("drain", e.lower(e.v("cnt"))),
                                        ),
                                        _incr(e, "cnt"),
                                    )
                                ),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    string_s = e.lower(string)
    top.append(
        e.call_m(
            e.v("m"),
            "run",
            e.stage(
                e.seq(
                    e.mb.set(e.lower(e.v("cnt")), e.n(0)),
                    e.mb.labeled(
                        "count",
                        e.mb.loop(e.seq(_incr(e, "cnt"), e.if_only(_is(e, "cnt", 3), e.mb.return_label("count")))),
                    ),
                    _log(e, "count", e.lower(e.v("cnt"))),
                    e.let(
                        "found",
                        e.mb.labeled(
                            "found",
                            e.mb.loop(
                                e.seq(
                                    _incr(e, "cnt"),
                                    e.if_only(_is(e, "cnt", 5), e.mb.return_to("found", e.lower(e.v("cnt")))),
                                )
                            ),
                        ),
                    ),
                    _log(e, "found", e.v("found")),
                    e.let(
                        "pick",
                        e.mb.labeled(
                            "pick",
                            e.seq(
                                e.if_only(_is(e, "cnt", 4), e.mb.return_to("pick", e.mb.as_(e.s("four"), string_s))),
                                e.mb.return_to("pick", e.mb.as_(e.s("five"), string_s)),
                            ),
                        ),
                    ),
                    e.call(e.lower(e.v("log")), e.mb.operator_add(e.mb.as_(e.s("pick "), string_s), e.v("pick"))),
                    e.mb.set(e.lower(e.v("o")), e.n(0)),
                    e.mb.labeled(
                        "outer",
                        e.mb.loop(
                            e.seq(
                                _incr(e, "o"),
                                e.mb.labeled(
                                    "inner",
                                    e.mb.loop(
                                        e.seq(
                                            _incr(e, "cnt"),
                                            e.if_only(_is(e, "cnt", 7), e.mb.return_label("inner")),
                                            e.if_only(_is(e, "cnt", 9), e.mb.return_label("outer")),
                                        )
                                    ),
                                ),
                            )
                        ),
                    ),
                    _log(
                        e,
                        "nested",
                        e.mb.operator_add(e.mb.operator_mul(e.lower(e.v("o")), e.n(10)), e.lower(e.v("cnt"))),
                    ),
                    _log(e, "drain", e.call(e.lower(e.v("drain")), e.n(12))),
                )
            ),
        )
    )
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
