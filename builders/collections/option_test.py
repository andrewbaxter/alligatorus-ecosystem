"""option-test-wasm.atz / option-test.atz: apps exercising option.atz over the targets' tuple values: options made
by `some`, `none` and `of`, read with `match` (with and without a fallback), passed to and returned from a function,
assigned through their binding and returned through a labeled block. The wasm app exits with the number of failed
checks; the llvm app prints `pass` or `fail` per check."""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
CHECKS = 8


def _checks(e, lo, check, dec):
    """The checks over `dec`, the function mapping `some(v)` to `some(v - 1)` and `none` to `none`."""

    def i32(n):
        return e.mb.as_(e.n(n), lo("t_i32"))

    def value_of(opt):
        """The payload of `opt`, or -1 for none (an exhaustive match)."""
        return e.match_of(opt, "v", None, e.p("some", e.v("v")), e.p("none", i32(-1)))

    def value_or(opt, dflt):
        """The payload of `opt`, or `dflt` from the fallback arm."""
        return e.match_of(opt, "v", i32(dflt), e.p("some", e.v("v")))

    def some(v):
        return e.call(lo("some"), v)

    none = e.call(lo("none"), e.tup())
    return [
        e.let("a", some(e.n(10))),
        check(e.eq(value_of(e.v("a")), e.n(10))),
        e.let("b", none),
        check(e.eq(value_of(e.v("b")), e.n(-1))),
        check(e.eq(value_or(e.v("b"), -2), e.n(-2))),
        e.let("c", e.call(dec, e.v("a"))),
        check(e.eq(value_of(e.v("c")), e.n(9))),
        check(e.eq(value_or(e.call(dec, e.v("b")), -3), e.n(-3))),
        e.mb.set(e.v("a"), some(e.n(7))),
        check(e.eq(value_of(e.v("a")), e.n(7))),
        check(e.eq(value_of(e.call(lo("of"), e.tup(i32(1), i32(3)))), e.n(3))),
        e.let("w", e.mb.labeled("w", e.seq(e.mb.return_to("w", e.call(dec, some(e.n(20))))))),
        check(e.eq(value_of(e.v("w")), e.n(19))),
    ]


def _dec_body(e, lo):
    """dec(p) -> some(v - 1) for some(v), none for none."""
    return e.match_of(
        e.v("p"),
        "v",
        None,
        e.p("some", e.call(lo("some"), e.mb.operator_sub(e.v("v"), e.n(1)))),
        e.p("none", e.call(lo("none"), e.tup())),
    )


OPTION_NAMES = ["opt_t", "some", "none", "of"]


def _option_lets(e, setup):
    """Binds the option type and constructors for i32 in the setup block."""
    setup.append(e.let("o", e.call(e.fld(e.v("option"), "type"), e.v("t_i32"))))
    setup.append(e.let("opt_t", e.fld(e.v("o"), "type")))
    for k in ["some", "none", "of"]:
        setup.append(e.let(k, e.fld(e.v("o"), k)))


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("option", e.import_local("option", "option-wasm.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    _option_lets(e, setup)
    setup.append(
        e.let(
            "dec_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("opt_t"))), e.p("ret", e.v("opt_t"))),
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
    exported = ["m", "proc_exit_fn_t", "dec_fn_t", "start_fn_t", "t_i32", "t_u32"] + OPTION_NAMES
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

    top.append(func("dec", ["p"], "dec_fn_t", _dec_body(e, lo)))
    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(*_checks(e, lo, check, lo("dec"))),
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
    setup.append(e.let("option", e.import_local("option", "option-llvm.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    _option_lets(e, setup)
    for name, params, ret in [("main_fn_t", [], "t_i32"), ("dec_fn_t", ["opt_t"], "opt_t")]:
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
    exported = ["llvm", "ll", "c", "t_i32", "main_fn_t", "dec_fn_t"] + OPTION_NAMES
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

    top.append(func("dec", ["p"], "dec_fn_t", _dec_body(e, lo)))
    body = e.seq(e.seq(*_checks(e, lo, check, lo("dec"))), e.ret(e.n(0)))
    top.append(func("main", [], "main_fn_t", body, "export_fn"))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top


def module(e, kind):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e)
    raise AssertionError(kind)
