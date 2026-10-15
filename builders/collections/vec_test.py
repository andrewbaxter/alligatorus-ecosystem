"""vec-test.atz: an llvm app exercising vec-llvm.atz. It prints `hi` through a byte vec, then `pass` or `fail` for
each check on an i32 vec (push 100, sum, slice length, sum through the slice, sub-slice length and element, write
through a sub-slice element, pop, length, capacity, write through `at`, clear, pop of the empty vec)."""

from ..root_mode import APP, root_mode_finish

COUNT = 100
MESSAGE = b"hi"
EXPECTED = "hi\n" + "pass\n" * 13


def _lo(e, name):
    return e.lower(e.v(name))


def module(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(e.let("t_u8", e.fld(e.v("llvm"), "u8")))
    setup.append(e.let("t_pu8", e.call(e.fld(e.v("llvm"), "ptr"), e.v("t_u8"))))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))
            ),
        )
    )
    exported = ["llvm", "ll", "c", "t_i32", "t_u8", "t_pu8", "main_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("vec", e.import_local("vec", "vec-llvm.atz")))
    for vname, elem in [("ints", "t_i32"), ("bytes", "t_u8")]:
        top.append(e.let(vname, e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
        for f in ["type", "own", "new"]:
            top.append(e.let(vname + "_" + f, e.fld(e.v(vname), f)))
    top.append(
        e.let(
            "loop",
            e.call(e.fld(e.v("llvm"), "ref_fn"), e.rec(e.p("ref", e.s("loop")), e.p("ty", e.fld(e.v("llvm"), "loop")))),
        )
    )
    for name, text in [("s_pass", "pass"), ("s_fail", "fail")]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    puts = e.lower(e.fld(e.v("c"), "puts"))

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

    body = e.seq(
        e.seq(
            e.let("s", e.mb.as_(e.call(_lo(e, "bytes_new"), e.tup()), _lo(e, "bytes_own"))),
            *[method("s", "push", e.n(b)) for b in MESSAGE + b"\0"],
            e.call(puts, e.fld(e.v("s"), "data")),
            e.let("v", e.mb.as_(e.call(_lo(e, "ints_new"), e.tup()), _lo(e, "ints_own"))),
            counted_loop("fill", COUNT, method("v", "push", e.v("i"))),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(COUNT))),
            check(e.mb.operator_ge(e.fld(e.v("v"), "cap"), e.n(COUNT))),
            e.let("sum", e.mb.as_(e.n(0), _lo(e, "t_i32"))),
            counted_loop(
                "sum", COUNT, e.mb.set(e.v("sum"), e.mb.operator_add(e.v("sum"), method("v", "at", e.v("i"))))
            ),
            check(e.eq(e.v("sum"), e.n(COUNT * (COUNT - 1) // 2))),
            e.let("s", method("v", "slice", e.tup())),
            check(e.eq(e.fld(e.v("s"), "len"), e.n(COUNT))),
            e.let("sum2", e.mb.as_(e.n(0), _lo(e, "t_i32"))),
            counted_loop(
                "sum2",
                COUNT,
                e.mb.set(e.v("sum2"), e.mb.operator_add(e.v("sum2"), e.call(e.fld(e.v("s"), "at"), e.v("i")))),
            ),
            check(e.eq(e.v("sum2"), e.n(COUNT * (COUNT - 1) // 2))),
            e.let("s2", e.call(e.fld(e.v("s"), "sub"), e.tup(e.n(10), e.n(20)))),
            check(e.eq(e.fld(e.v("s2"), "len"), e.n(10))),
            check(e.eq(e.call(e.fld(e.v("s2"), "at"), e.n(0)), e.n(10))),
            e.mb.set(e.call(e.fld(e.v("s2"), "at"), e.n(1)), e.n(777)),
            check(e.eq(method("v", "at", e.n(11)), e.n(777))),
            check(
                e.eq(
                    e.match_of(
                        method("v", "pop", e.tup()),
                        "p",
                        None,
                        e.p("some", e.v("p")),
                        e.p("none", e.mb.as_(e.n(-1), _lo(e, "t_i32"))),
                    ),
                    e.n(COUNT - 1),
                )
            ),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(COUNT - 1))),
            e.mb.set(method("v", "at", e.n(3)), e.n(1000)),
            check(e.eq(method("v", "at", e.n(3)), e.n(1000))),
            method("v", "clear", e.tup()),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(0))),
            check(
                e.eq(
                    e.match_of(
                        method("v", "pop", e.tup()),
                        "p",
                        None,
                        e.p("some", e.v("p")),
                        e.p("none", e.mb.as_(e.n(-1), _lo(e, "t_i32"))),
                    ),
                    e.n(-1),
                )
            ),
        ),
        e.ret(e.n(0)),
    )
    top.append(
        e.let(
            "main",
            e.call(
                e.fld(e.v("llvm"), "export_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s("main")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("main_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top
