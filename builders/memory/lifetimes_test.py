"""lifetimes-test.atz / lifetimes-test-err.atz: llvm apps exercising lifetimes.atz. The app binds two owners, gives the
earlier one level 0 and the later one level 1 (so drops happen in descending level order) and prints `ok`; the err
module assigns the levels the other way round, so the level-0 owner is dropped while the level-1 owner is alive,
which must fail to compile."""

from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of

ERR = "err"


def _lo(e, name):
    return e.lower(e.v(name))


def module(e, mode):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("lifetimes", e.import_local("lifetimes", "lifetimes.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(e.let("t_pv", e.call(e.fld(e.v("llvm"), "ptr"), e.fld(e.v("llvm"), "void"))))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))
            ),
        )
    )
    setup.append(
        e.let(
            "void_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.fld(e.v("llvm"), "void"))),
            ),
        )
    )
    setup.append(
        e.let("lt", e.call(e.fld(e.v("lifetimes"), "set"), e.rec(e.p("name", e.s("t")), e.p("count", e.int_of(2)))))
    )
    setup.append(e.let("own", e.call_m(e.v("lt"), "own", e.v("t_pv"))))
    for i in range(2):
        setup.append(
            e.let("L%d" % i, e.call_m(e.v("lt"), "at", e.rec(e.p("index", e.int_of(i)), e.p("under", e.v("t_pv")))))
        )
    exported = ["llvm", "ll", "c", "t_i32", "t_pv", "main_fn_t", "void_fn_t", "own", "L0", "L1"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("s_ok", e.call_m(e.v("ll"), "cstr", e.s("ok"))))
    # A function taking an L1 reference: the parameter is live at level 1 inside it and released when it returns.
    top.append(
        e.let(
            "use_ref",
            e.call(
                e.fld(e.v("llvm"), "func_dep"),
                e.rec(
                    e.p("name", e.s("use_ref")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("r"))),
                    e.p(
                        "ty",
                        e.call(
                            e.fld(e.v("llvm"), "fn"),
                            e.rec(
                                e.p("params", e.list_new(e.mb.eval_type(), e.v("L1"))),
                                e.p("ret", e.fld(e.v("llvm"), "void")),
                            ),
                        ),
                    ),
                    e.p("body", e.stage(e.seq(e.let("p", e.mb.as_(e.v("r"), _lo(e, "t_pv")))))),
                ),
            ),
        )
    )

    def malloc(n):
        return e.call(e.lower(e.fld(e.v("c"), "malloc")), e.mb.as_(e.n(n), e.lower(e.fld(e.v("llvm"), "u64"))))

    def owners():
        return [e.let("a", e.mb.as_(malloc(16), _lo(e, "own"))), e.let("b", e.mb.as_(malloc(16), _lo(e, "own")))]

    if mode == APP:
        # a (declared first, dropped last) is the longer-lived level 0; b is level 1.
        flag = e.v("flag")
        body = e.seq(
            e.let("flag", e.mb.as_(e.n(0), _lo(e, "t_i32"))),
            *owners(),
            e.let("r0", e.mb.as_(e.v("a"), _lo(e, "L0"))),
            e.let("r1", e.mb.as_(e.v("b"), _lo(e, "L1"))),
            # an early exit: its cleanup chain drops forked bindings speculatively, which must not disturb the check
            e.if_only(e.not_(e.eq(flag, e.n(0))), e.ret(e.mb.as_(e.n(2), _lo(e, "t_i32")))),
            # a branch binding another reference to b, dropped at the branch's end
            e.if_else(
                e.eq(flag, e.n(0)),
                e.seq(
                    e.let("r1b", e.mb.as_(e.v("b"), _lo(e, "L1"))),
                    e.let("p1b", e.mb.as_(e.v("r1b"), _lo(e, "t_pv"))),
                    e.mb.set(flag, e.mb.as_(e.n(0), _lo(e, "t_i32"))),
                ),
                e.seq(e.mb.set(flag, e.mb.as_(e.n(3), _lo(e, "t_i32")))),
            ),
            e.call(fn_of(e, _lo(e, "use_ref")), e.mb.as_(e.v("b"), _lo(e, "L1"))),
            # references act as their underlying type
            e.call(e.lower(e.fld(e.v("c"), "free")), e.mb.as_(e.v("r1"), _lo(e, "t_pv"))),
            e.call(e.lower(e.fld(e.v("c"), "puts")), _lo(e, "s_ok")),
            e.ret(e.mb.as_(e.n(0), _lo(e, "t_i32"))),
        )
        top.append(
            e.let(
                "main",
                e.call(
                    e.fld(e.v("llvm"), "func_fn"),
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
    elif mode == ERR:
        # b (dropped first) is given the longer level 0 while a keeps level 1: dropping b violates the order.
        body = e.seq(
            *owners(), e.let("r0", e.mb.as_(e.v("b"), _lo(e, "L0"))), e.let("r1", e.mb.as_(e.v("a"), _lo(e, "L1")))
        )
        top.append(
            e.let(
                "bad",
                e.call(
                    e.fld(e.v("llvm"), "func_fn"),
                    e.rec(
                        e.p("mod", e.v("ll")),
                        e.p("name", e.s("bad")),
                        e.p("params", e.tup()),
                        e.p("ty", e.v("void_fn_t")),
                        e.p("body", e.stage(body)),
                    ),
                ),
            )
        )
        top.append(e.call(e.mb.log(), e.fld(e.call_m0(e.v("ll"), "render"), "ir")))
    else:
        raise AssertionError(mode)
    return top
