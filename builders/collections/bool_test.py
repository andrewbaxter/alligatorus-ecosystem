"""bool-test-wasm.atz / bool-test.atz: apps exercising the targets' boolean (the 1-bit integer comparisons yield
and `if` reads): `and` and `or` short-circuit (the right operand, a call counting into a cell, runs only when the
left one does not decide), `not`, and a boolean bound, assigned and returned from a function. The wasm app exits
with the number of failed checks; the llvm app prints `pass` or `fail` per check."""

from .. import target_mb as tm
from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
CHECKS = 10


def _checks(e, lo, check, bump):
    """The checks: `bump()` adds one to the cell and yields 1 (so `bump() == 1` is a true boolean with an effect)."""

    def cell():
        return e.mb.field(tm.conv(e, lo("ptr_cast"), e.call(fn_of(e, lo("count")), e.tup()), lo("t_pi32")), e.n(0))

    def bumped():
        return e.eq(e.call(bump, e.tup()), e.n(1))

    return [
        e.mb.set(cell(), e.n(0)),
        e.let("one", e.mb.as_(e.n(1), lo("t_i32"))),
        e.let("t", e.eq(e.v("one"), e.n(1))),
        e.let("f", e.eq(e.v("one"), e.n(2))),
        # the left operand decides: the right one does not run
        check(e.not_(e.mb.operator_and(e.v("f"), bumped()))),
        check(e.eq(cell(), e.n(0))),
        check(e.mb.operator_or(e.v("t"), bumped())),
        check(e.eq(cell(), e.n(0))),
        # the left operand does not decide: the right one runs and decides
        check(e.mb.operator_and(e.v("t"), bumped())),
        check(e.eq(cell(), e.n(1))),
        check(e.mb.operator_or(e.v("f"), bumped())),
        check(e.eq(cell(), e.n(2))),
        check(e.not_(e.not_(e.v("t")))),
        e.mb.set(e.v("f"), e.v("t")),
        check(e.v("f")),
    ]


def _bump_body(e, cell):
    return e.seq(e.mb.set(cell, e.mb.operator_add(cell, e.n(1))), e.ret(e.mb.as_(e.n(1), e.lower(e.v("t_i32")))))


def _count_lets(e, setup, lib, count_arg):
    setup.append(e.let("t_pi32", e.call(e.fld(lib, "ptr"), e.v("t_i32"))))
    setup.append(e.let("ptr_cast", e.fld(lib, "ptr_cast")))
    setup.append(e.let("count", e.call(e.fld(lib, "alloc_dep"), e.rec(e.p("name", e.s("bump_count")), count_arg))))
    setup.append(
        e.let(
            "bump_fn_t",
            e.call(e.fld(lib, "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))),
        )
    )


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    _count_lets(e, setup, e.v("wasm"), e.p("size", e.int_of(4)))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))
            ),
        )
    )
    exported = ["m", "proc_exit_fn_t", "bump_fn_t", "start_fn_t", "t_i32", "t_u32", "t_pi32", "ptr_cast", "count"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(
        e.let(
            "proc_exit",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    e.p("module", e.fld(e.v("wasi"), "module")),
                    e.p("name", e.s("proc_exit")),
                    e.p("ty", e.v("proc_exit_fn_t")),
                ),
            ),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def func(name, params, fn_t, body_, kind="func_fn"):
        return e.let(
            name,
            e.call(
                e.fld(e.v("wasm"), kind),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body_)),
                ),
            ),
        )

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    cell = e.mb.field(tm.conv(e, lo("ptr_cast"), e.call(fn_of(e, lo("count")), e.tup()), lo("t_pi32")), e.n(0))
    top.append(func("bump", [], "bump_fn_t", _bump_body(e, cell)))
    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(*_checks(e, lo, check, lo("bump"))),
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(func("_start", [], "start_fn_t", body, "export_fn"))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top


def _llvm(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    _count_lets(e, setup, e.v("llvm"), e.p("ty", e.v("t_i32")))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))
            ),
        )
    )
    exported = ["llvm", "ll", "c", "t_i32", "t_pi32", "ptr_cast", "count", "bump_fn_t", "main_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name, text in [("s_pass", "pass"), ("s_fail", "fail")]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    puts = e.lower(e.fld(e.v("c"), "puts"))

    def lo(name):
        return e.lower(e.v(name))

    def func(name, params, fn_t, body_, kind="func_fn"):
        return e.let(
            name,
            e.call(
                e.fld(e.v("llvm"), kind),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body_)),
                ),
            ),
        )

    def check(cond):
        return e.if_else(cond, e.call(puts, lo("s_pass")), e.call(puts, lo("s_fail")))

    cell = e.mb.field(tm.conv(e, lo("ptr_cast"), e.call(fn_of(e, lo("count")), e.tup()), lo("t_pi32")), e.n(0))
    top.append(func("bump", [], "bump_fn_t", _bump_body(e, cell)))
    body = e.seq(e.seq(*_checks(e, lo, check, lo("bump"))), e.ret(e.n(0)))
    top.append(func("main", [], "main_fn_t", body, "export_fn"))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top


def module(e, kind):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e)
    raise AssertionError(kind)
