"""js-srcmap-test.atz: a js app dir whose statements come through a const function's expansion, so its frame sidecar
must chain each expanded statement to the call that produced it (harness/verify-js-srcmap.sh checks the map)."""

from ..target_mb import body, const_eval_in, const_fn, loc, xx


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def _utf8(e, text):
    return e.call(e.mb.eval_str_utf8(), text)


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    # `twice(())` expands to two calls of the caller's `f`: both statements' frames have the call as their parent.
    const_fn(
        e,
        top,
        "twice_b",
        "twice",
        body(
            e,
            e.ret(
                const_eval_in(
                    e,
                    xx(e),
                    loc(e),
                    e.stage(e.seq(e.call(e.v("f"), e.s("a")), e.call(e.v("f"), e.s("b")))),
                )
            ),
        ),
    )
    top.append(e.finish(e.v("d")))
    top.append(e.let("twice", e.fld(e.v("twice_b"), "func")))
    top.append(e.let("m", e.call(e.fld(e.v("js"), "new"), e.tup())))
    top.append(
        e.call_m(
            e.v("m"),
            "run",
            e.stage(
                e.seq(
                    e.let(
                        "f",
                        e.call(
                            e.lower(e.fld(e.v("js"), "global_fn")),
                            e.rec(
                                e.p("name", e.s("f")),
                                e.p(
                                    "ty",
                                    e.call(
                                        e.lower(e.fld(e.v("js"), "fn")),
                                        e.rec(
                                            e.p("params", e.tup(e.lower(e.fld(e.v("js"), "string")))),
                                            e.p("ret", e.lower(e.fld(e.v("js"), "void"))),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.call(e.v("f"), e.s("direct")),
                    e.call(e.lower(e.v("twice")), e.tup()),
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
