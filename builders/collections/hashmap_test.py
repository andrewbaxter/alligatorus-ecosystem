"""hashmap-test.atz: an llvm app exercising map-llvm.atz and set-llvm.atz with i32 keys; prints `pass` or `fail`
per check."""

from ..root_mode import APP, root_mode_finish

COUNT = 200
CHECKS = 19
EXPECTED = "pass\n" * CHECKS


def _lo(e, name):
    return e.lower(e.v(name))


def module(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    for name, params, ret in [
        ("main_fn_t", [], "t_i32"),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("llvm"), "fn"),
                    e.rec(
                        e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))
                    ),
                ),
            )
        )
    exported = ["llvm", "ll", "c", "t_i32", "main_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("map", e.import_local("map", "map-llvm.atz")))
    top.append(e.let("set", e.import_local("set", "set-llvm.atz")))
    top.append(
        e.let(
            "loop",
            e.call(e.fld(e.v("llvm"), "ref_fn"), e.rec(e.p("ref", e.s("loop")), e.p("ty", e.fld(e.v("llvm"), "loop")))),
        )
    )
    for name, text in [("s_pass", "pass"), ("s_fail", "fail")]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    puts = e.lower(e.fld(e.v("c"), "puts"))

    def func(name, params, fn_t, body):
        return e.let(
            name,
            e.call(
                e.fld(e.v("llvm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body)),
                ),
            ),
        )

    top.append(e.let("imap", e.call(e.fld(e.v("map"), "type"), e.tup(e.v("t_i32"), e.v("t_i32")))))
    top.append(e.let("iset", e.call(e.fld(e.v("set"), "type"), e.v("t_i32"))))
    for tname in ["imap", "iset"]:
        for f in ["type", "new"]:
            top.append(e.let(tname + "_" + f, e.fld(e.v(tname), f)))

    def check(cond):
        return e.if_else(cond, e.call(puts, _lo(e, "s_pass")), e.call(puts, _lo(e, "s_fail")))

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def counted_loop(label, limit, body):
        return e.seq(
            e.let("i", e.mb.as_(e.n(0), _lo(e, "t_i32"))),
            e.mb.labeled(
                label,
                e.foreach(
                    _lo(e, "loop"),
                    "_",
                    e.seq(
                        e.if_only(e.eq(e.v("i"), e.n(limit)), e.mb.return_label(label)),
                        body,
                        e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.n(1))),
                    ),
                ),
            ),
        )

    def truthy(x):
        return e.not_(e.eq(x, e.n(0)))

    body = e.seq(
        e.seq(
            e.let("mp", e.mb.as_(e.call(_lo(e, "imap_new"), e.tup()), _lo(e, "imap_type"))),
            counted_loop("fill", COUNT, method("mp", "put", e.v("i"), e.mb.operator_mul(e.v("i"), e.n(3)))),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT))),
            check(truthy(method("mp", "has", e.n(150)))),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(7)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), _lo(e, "t_i32"))),
                    ),
                    e.n(21),
                )
            ),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(500)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), _lo(e, "t_i32"))),
                    ),
                    e.n(-1),
                )
            ),
            check(e.not_(truthy(method("mp", "has", e.n(500))))),
            check(truthy(method("mp", "remove", e.n(100)))),
            check(e.not_(truthy(method("mp", "has", e.n(100))))),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT - 1))),
            method("mp", "put", e.n(100), e.n(5)),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(100)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), _lo(e, "t_i32"))),
                    ),
                    e.n(5),
                )
            ),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT))),
            check(e.not_(truthy(method("mp", "remove", e.n(999))))),
            method("mp", "clear", e.tup()),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(0))),
            check(e.not_(truthy(method("mp", "has", e.n(7))))),
            e.let("st", e.mb.as_(e.call(_lo(e, "iset_new"), e.tup()), _lo(e, "iset_type"))),
            counted_loop("fills", 50, method("st", "add", e.v("i"))),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(50))),
            check(truthy(method("st", "has", e.n(25)))),
            check(truthy(method("st", "remove", e.n(25)))),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(49))),
            check(e.not_(truthy(method("st", "has", e.n(25))))),
            method("st", "add", e.n(25)),
            method("st", "add", e.n(25)),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(50))),
        ),
        e.ret(e.n(0)),
    )
    top.append(func("main", [], "main_fn_t", body))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top
