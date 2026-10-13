"""tuple-test-wasm.atz / tuple-test.atz: apps exercising the targets' tuple values (wasm multi-value, llvm first-class
aggregates): a tuple built from a host tuple, bound, read by component, passed to and returned from a function,
yielded by an `if`, assigned through its binding and returned through a labeled block. The wasm app exits with the
number of failed checks; the llvm app prints `pass` or `fail` per check."""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
CHECKS = 8


def _checks(e, lo, check, pair, swap):
    """The checks over a pair type `pair(a, b)` (a host pair cast to the target tuple) and `swap`, the function
    swapping a pair's components."""

    def at(v, i):
        return e.mb.field(e.v(v), e.n(i))

    return [
        e.let("t", pair(3, 4)),
        check(e.eq(at("t", 0), e.n(3))),
        check(e.eq(at("t", 1), e.n(4))),
        e.let("r", e.call(swap, e.v("t"))),
        check(e.eq(at("r", 0), e.n(4))),
        check(e.eq(at("r", 1), e.n(3))),
        e.let("u", e.if_else(e.eq(at("r", 0), e.n(4)), pair(1, 2), pair(5, 6))),
        check(e.eq(at("u", 0), e.n(1))),
        check(e.eq(at("u", 1), e.n(2))),
        e.mb.set(e.v("t"), pair(7, 8)),
        check(e.eq(e.mb.operator_add(at("t", 0), at("t", 1)), e.n(15))),
        e.let("w", e.mb.labeled("w", e.seq(e.mb.return_to("w", e.call(swap, pair(9, 10)))))),
        check(e.eq(e.mb.operator_sub(at("w", 0), at("w", 1)), e.n(1))),
    ]


def _swap_body(e, pair_t):
    """swap(p) -> (p.1, p.0)."""
    return e.mb.as_(e.tup(e.mb.field(e.v("p"), e.n(1)), e.mb.field(e.v("p"), e.n(0))), pair_t)


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(
        e.let("pair_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_i32"), e.v("t_i32"))))
    )
    setup.append(
        e.let(
            "swap_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("pair_t"))), e.p("ret", e.v("pair_t"))),
            ),
        )
    )
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))
            ),
        )
    )
    exported = ["m", "proc_exit_fn_t", "swap_fn_t", "start_fn_t", "t_i32", "t_u32", "pair_t"]
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

    def func(name, params, fn_t, body_):
        return e.let(
            name,
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body_)),
                ),
            ),
        )

    def pair(a, b):
        return e.mb.as_(e.tup(e.n(a), e.n(b)), lo("pair_t"))

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    top.append(func("swap", ["p"], "swap_fn_t", _swap_body(e, lo("pair_t"))))
    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(*_checks(e, lo, check, pair, lo("swap"))),
        e.call(lo("proc_exit"), e.call(lo("t_u32"), e.v("fails"))),
    )
    top.append(func("_start", [], "start_fn_t", body))
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top


def _llvm(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(
        e.let("pair_t", e.call(e.fld(e.v("llvm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_i32"), e.v("t_i32"))))
    )
    for name, params, ret in [("main_fn_t", [], "t_i32"), ("swap_fn_t", ["pair_t"], "pair_t")]:
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
    exported = ["llvm", "ll", "c", "t_i32", "pair_t", "main_fn_t", "swap_fn_t"]
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

    def func(name, params, fn_t, body_):
        return e.let(
            name,
            e.call(
                e.fld(e.v("llvm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body_)),
                ),
            ),
        )

    def pair(a, b):
        return e.mb.as_(e.tup(e.n(a), e.n(b)), lo("pair_t"))

    def check(cond):
        return e.if_else(cond, e.call(puts, lo("s_pass")), e.call(puts, lo("s_fail")))

    top.append(func("swap", ["p"], "swap_fn_t", _swap_body(e, lo("pair_t"))))
    body = e.seq(e.seq(*_checks(e, lo, check, pair, lo("swap"))), e.ret(e.n(0)))
    top.append(func("main", [], "main_fn_t", body))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top


def module(e, kind):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e)
    raise AssertionError(kind)
