"""destructor-test.atz / destructor-test-err.atz: llvm apps exercising destructor.atz.

APP prints, via puts as the destroy function: A (reassignment destroys the old value), C (an owned parameter: the
callee destroys it when it returns), D (an owned value returned by a function and passed on as a temporary), A2 (a
borrow), end, D2 (the binding of a returned owned value drops), B (the moved-into binding drops), A2 (the reassigned
binding drops). ERR moves an owned binding in one branch only, which must fail to compile.
 ERR_LOAN returns a borrow of a local owned binding from a function, which must fail to compile."""

from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of

ERR = "err"
ERR_LOAN = "err_loan"


def _lo(e, name):
    return e.lower(e.v(name))


def module(e, mode):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_pu8", e.call(e.fld(e.v("llvm"), "ptr"), e.fld(e.v("llvm"), "u8"))))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.fld(e.v("llvm"), "i32"))),
            ),
        )
    )
    setup.append(
        e.let(
            "cond_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"),
                e.rec(
                    e.p("params", e.list_new(e.mb.eval_type(), e.fld(e.v("llvm"), "i32"))),
                    e.p("ret", e.fld(e.v("llvm"), "void")),
                ),
            ),
        )
    )
    setup.append(
        e.let(
            "leak_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_pu8"))),
            ),
        )
    )
    exported = ["llvm", "ll", "c", "t_pu8", "main_fn_t", "cond_fn_t", "leak_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("destructor", e.import_local("destructor", "destructor.atz")))
    top.append(
        e.let(
            "owned_r",
            e.call(
                e.fld(e.v("destructor"), "type"),
                e.rec(e.p("under", e.v("t_pu8")), e.p("destroy", e.fld(e.v("c"), "puts"))),
            ),
        )
    )
    top.append(e.let("owned_str", e.fld(e.v("owned_r"), "type")))
    top.append(e.let("own_str", e.fld(e.v("owned_r"), "own")))
    for name, text in [
        ("s_a", "A"),
        ("s_a2", "A2"),
        ("s_b", "B"),
        ("s_c", "C"),
        ("s_d", "D"),
        ("s_d2", "D2"),
        ("s_end", "end"),
    ]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    # A function taking an owned parameter: the callee owns it and destroys it when it returns (a dependency, so
    # its type, made here from the owned type, needs no lowering boundary).
    top.append(
        e.let(
            "consume",
            e.call(
                e.fld(e.v("llvm"), "func_dep"),
                e.rec(
                    e.p("name", e.s("consume")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("o"))),
                    e.p(
                        "ty",
                        e.call(
                            e.fld(e.v("llvm"), "fn"),
                            e.rec(
                                e.p("params", e.list_new(e.mb.eval_type(), e.v("owned_str"))),
                                e.p("ret", e.fld(e.v("llvm"), "void")),
                            ),
                        ),
                    ),
                    e.p("body", e.stage(e.seq())),
                ),
            ),
        )
    )
    # A function returning an owned value: a dependency whose return type is the owned type; its body yields an
    # owned temporary (the constant `D` or `D2`, by the argument), which the caller owns.
    top.append(
        e.let(
            "make",
            e.call(
                e.fld(e.v("llvm"), "func_dep"),
                e.rec(
                    e.p("name", e.s("make")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("second"))),
                    e.p(
                        "ty",
                        e.call(
                            e.fld(e.v("llvm"), "fn"),
                            e.rec(
                                e.p("params", e.list_new(e.mb.eval_type(), e.fld(e.v("llvm"), "i32"))),
                                e.p("ret", e.v("owned_str")),
                            ),
                        ),
                    ),
                    e.p(
                        "body",
                        e.stage(
                            e.seq(
                                e.ret(
                                    e.if_else(
                                        e.eq(e.v("second"), e.n(0)),
                                        e.mb.as_(_lo(e, "s_d"), _lo(e, "own_str")),
                                        e.mb.as_(_lo(e, "s_d2"), _lo(e, "own_str")),
                                    )
                                )
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    puts = e.lower(e.fld(e.v("c"), "puts"))
    if mode == APP:
        body = e.seq(
            e.let("a", e.mb.as_(_lo(e, "s_a"), _lo(e, "own_str"))),
            e.let("b", e.mb.as_(_lo(e, "s_b"), _lo(e, "own_str"))),
            e.let("c2", e.call(e.fld(e.v("b"), "move"), e.tup())),
            e.mb.set(e.v("a"), e.mb.as_(_lo(e, "s_a2"), _lo(e, "own_str"))),
            e.let("c3", e.mb.as_(_lo(e, "s_c"), _lo(e, "own_str"))),
            e.call(fn_of(e, _lo(e, "consume")), e.call(e.fld(e.v("c3"), "move"), e.tup())),
            e.call(fn_of(e, _lo(e, "consume")), e.call(fn_of(e, _lo(e, "make")), e.n(0))),
            e.let("d", e.call(fn_of(e, _lo(e, "make")), e.n(1))),
            e.call(puts, e.v("a")),
            e.call(puts, _lo(e, "s_end")),
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
    elif mode == ERR:
        body = e.seq(
            e.let("a", e.mb.as_(_lo(e, "s_a"), _lo(e, "own_str"))),
            e.if_only(e.mb.operator_gt(e.v("x"), e.n(0)), e.seq(e.let("m", e.call(e.fld(e.v("a"), "move"), e.tup())))),
        )
        top.append(
            e.let(
                "cond",
                e.call(
                    e.fld(e.v("llvm"), "func_fn"),
                    e.rec(
                        e.p("mod", e.v("ll")),
                        e.p("name", e.s("cond")),
                        e.p("params", e.tup(e.s("x"))),
                        e.p("ty", e.v("cond_fn_t")),
                        e.p("body", e.stage(body)),
                    ),
                ),
            )
        )
        top.append(e.call(e.mb.log(), e.fld(e.call_m0(e.v("ll"), "render"), "ir")))
    elif mode == ERR_LOAN:
        # A function returning a borrow of its own owned binding (dangling once the binding drops) must not compile.
        body = e.seq(e.let("a", e.mb.as_(_lo(e, "s_a"), _lo(e, "own_str"))), e.ret(e.v("a")))
        top.append(
            e.let(
                "leak",
                e.call(
                    e.fld(e.v("llvm"), "func_fn"),
                    e.rec(
                        e.p("mod", e.v("ll")),
                        e.p("name", e.s("leak")),
                        e.p("params", e.tup()),
                        e.p("ty", e.v("leak_fn_t")),
                        e.p("body", e.stage(body)),
                    ),
                ),
            )
        )
        top.append(e.call(e.mb.log(), e.fld(e.call_m0(e.v("ll"), "render"), "ir")))
    else:
        raise AssertionError(mode)
    return top
