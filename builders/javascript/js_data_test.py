"""js-data-test.atz: a js app dir exercising the typed js target's data types (harness/verify-js-data.sh runs it under
node and compares its lines): an array from a tuple literal (`push`, `length`, `foreach`, elements read and set), a
declared object type referring to itself through a `Point | null` union field, record literals as objects,
`match` on unions, and js's `Map` declared as an object type with a constructor and methods (`get` gives
`number | undefined`)."""


def _bytes_t(e):
    return e.call(e.mb.types_array(), e.mb.types_byte())


def _utf8(e, text):
    return e.call(e.mb.eval_str_utf8(), text)


def _jsf(e, name):
    return e.fld(e.v("js"), name)


def _def(e, kind, *fields):
    return e.call(_jsf(e, kind), e.rec(*fields))


def _fn(e, params, ret):
    return _def(e, "fn", e.p("params", e.tup(*params)), e.p("ret", ret))


def _log(e, label, text):
    return e.call(e.lower(e.v("log")), e.mb.operator_add(e.mb.as_(e.s(label + " "), e.lower(_jsf(e, "string"))), text))


def _num(e, n):
    return e.call(e.lower(e.v("str")), n)


def module(e):
    top = []
    top.append(e.let("js", e.import_local("js", "js-es2020.atz")))
    top.append(e.let("m", e.call(_jsf(e, "new"), e.tup())))
    number, string = _jsf(e, "number"), _jsf(e, "string")
    top.append(e.let("nums", _def(e, "array", e.p("elem", number))))
    top.append(e.let("point", _def(e, "object", e.p("name", e.s("Point")))))
    top.append(e.let("next_t", _def(e, "union", e.p("p", e.v("point")), e.p("none", _jsf(e, "null")))))
    top.append(
        _def(
            e,
            "members",
            e.p("object", e.v("point")),
            e.p("fields", e.rec(e.p("x", number), e.p("y", number), e.p("next", e.v("next_t")))),
            e.p("methods", e.rec()),
        )
    )
    top.append(e.let("map_t", _def(e, "object", e.p("name", e.s("Map")))))
    top.append(e.let("got_t", _def(e, "union", e.p("n", number), e.p("missing", _jsf(e, "undefined")))))
    top.append(
        _def(
            e,
            "members",
            e.p("object", e.v("map_t")),
            e.p("fields", e.rec(e.p("size", number))),
            e.p(
                "methods",
                e.rec(
                    e.p("set", _fn(e, [string, number], e.v("map_t"))),
                    e.p("get", _fn(e, [string], e.v("got_t"))),
                ),
            ),
        )
    )
    for name, js_name, ty_ in [
        ("log", "console.log", _fn(e, [string], _jsf(e, "void"))),
        ("str", "String", _fn(e, [number], string)),
        ("json", "JSON.stringify", _fn(e, [e.v("point")], string)),
        ("map_new", "Map", _def(e, "ctor", e.p("params", e.tup()), e.p("ret", e.v("map_t")))),
    ]:
        top.append(e.let(name, _def(e, "global_fn", e.p("name", e.s(js_name)), e.p("ty", ty_))))
    top.append(e.let("total", _def(e, "var_fn", e.p("mod", e.v("m")), e.p("name", e.s("total")), e.p("ty", number))))
    mb = e.mb
    total = e.lower(e.v("total"))

    def next_of(p_, label):
        return e.match_of(
            e.fld(p_, "next"),
            "n",
            None,
            ("p", _log(e, label, _num(e, e.fld(e.v("n"), "x")))),
            ("none", e.call(e.lower(e.v("log")), mb.as_(e.s(label + " none"), e.lower(string)))),
        )

    def got(key):
        return e.match_of(
            e.call(e.fld(e.v("mp"), "get"), e.s(key)),
            "g",
            None,
            ("n", _log(e, "map " + key, _num(e, e.v("g")))),
            ("missing", e.call(e.lower(e.v("log")), mb.as_(e.s("map " + key + " missing"), e.lower(string)))),
        )

    staged = e.seq(
        e.let("a", mb.as_(e.tup(e.n(1), e.n(2), e.n(3)), e.lower(e.v("nums")))),
        e.call(e.fld(e.v("a"), "push"), e.n(4)),
        _log(e, "len", _num(e, e.fld(e.v("a"), "length"))),
        mb.set(total, e.n(0)),
        e.foreach(e.v("a"), "el", mb.set(total, mb.operator_add(total, e.v("el")))),
        _log(e, "sum", _num(e, total)),
        _log(e, "elem", _num(e, mb.field(e.v("a"), e.mb.as_(e.n(1), e.lower(number))))),
        mb.set(mb.field(e.v("a"), mb.as_(e.n(0), e.lower(number))), e.n(9)),
        _log(e, "set", _num(e, mb.field(e.v("a"), mb.as_(e.n(0), e.lower(number))))),
        e.let("p", mb.as_(e.rec(e.p("x", e.n(1)), e.p("y", e.n(2)), e.p("next", e.tup())), e.lower(e.v("point")))),
        e.let("q", mb.as_(e.rec(e.p("x", e.n(3)), e.p("y", e.n(4)), e.p("next", e.v("p"))), e.lower(e.v("point")))),
        _log(e, "point", _num(e, mb.operator_add(e.fld(e.v("p"), "x"), e.fld(e.v("p"), "y")))),
        _log(e, "json", e.call(e.lower(e.v("json")), e.v("p"))),
        next_of(e.v("q"), "q.next"),
        next_of(e.v("p"), "p.next"),
        e.let("mp", e.call(e.lower(e.v("map_new")), e.tup())),
        e.call(e.fld(e.v("mp"), "set"), e.tup(e.s("a"), e.n(5))),
        got("a"),
        got("zz"),
        _log(e, "size", _num(e, e.fld(e.v("mp"), "size"))),
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
