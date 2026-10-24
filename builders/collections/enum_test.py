"""enum-test-wasm.atz / enum-test.atz: apps exercising enum.atz: an enumeration's constants (`red(())`), read with
`match` (with and without a fallback), compared with `==`, bound and assigned, passed to and returned from a
function, and stored in a vec. The wasm app exits with the number of failed checks; the llvm app prints `pass` or
`fail` per check.

enum-test-err.atz (mode `err`) must fail to build: a match over an enumeration missing a variant and without a
fallback."""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
ERR = "err"
NAMES = ("red", "green", "blue")
CHECKS = 8


def _checks(e, lo, check, next_):
    """The checks over the enumeration `color` (lowered as `color_t`) and `next_`, the function mapping each
    variant to the following one (blue to red)."""

    def color(name):
        return e.call(lo("color_" + name), e.tup())

    def i32(n):
        return e.mb.as_(e.n(n), lo("t_i32"))

    def index_of(v):
        """The variant's index by an exhaustive match."""
        return e.match_of(v, "_", None, *[e.p(n, i32(i)) for i, n in enumerate(NAMES)])

    return [
        e.let("c", color("green")),
        check(e.eq(index_of(e.v("c")), e.n(1))),
        check(e.eq(e.v("c"), color("green"))),
        check(e.not_(e.eq(e.v("c"), color("red")))),
        e.mb.set(e.v("c"), color("blue")),
        check(e.eq(index_of(e.v("c")), e.n(2))),
        check(e.eq(e.match_of(e.v("c"), "_", i32(9), e.p("red", i32(0))), e.n(9))),
        check(e.eq(index_of(e.call(next_, color("red"))), e.n(1))),
        check(e.eq(index_of(e.call(next_, color("blue"))), e.n(0))),
        e.let("v", e.call(lo("colors_new"), e.tup())),
        e.call(e.fld(e.v("v"), "push"), color("green")),
        check(e.eq(index_of(e.call(e.fld(e.v("v"), "at"), e.n(0))), e.n(1))),
    ]


def _next_body(e, lo):
    """next(c): the following variant, wrapping."""
    return e.match_of(
        e.v("c"),
        "_",
        None,
        *[e.p(n, e.call(lo("color_" + NAMES[(i + 1) % len(NAMES)]), e.tup())) for i, n in enumerate(NAMES)],
    )


def _err_body(e, lo):
    """A non-exhaustive match without a fallback: a compile error."""
    return e.match_of(e.call(lo("color_red"), e.tup()), "_", None, e.p("red", e.n(0)))


def _enum_lets(e, setup, enum_file):
    setup.append(e.let("enum", e.import_local("enum", enum_file)))
    setup.append(e.let("color", e.call(e.fld(e.v("enum"), "type"), e.tup(*[e.s(n) for n in NAMES]))))
    setup.append(e.let("color_t", e.fld(e.v("color"), "type")))
    for n in NAMES:
        setup.append(e.let("color_" + n, e.fld(e.v("color"), n)))


def _wasm(e, mode):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    _enum_lets(e, setup, "enum-wasm.atz")
    setup.append(
        e.let(
            "next_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("color_t"))), e.p("ret", e.v("color_t"))),
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
    exported = ["m", "proc_exit_fn_t", "next_fn_t", "start_fn_t", "t_i32", "t_u32", "color_t"]
    exported += ["color_" + n for n in NAMES]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("colors", e.call(e.fld(e.v("vec"), "type"), e.v("color_t"))))
    for f in ["own", "new"]:
        top.append(e.let("colors_" + f, e.fld(e.v("colors"), f)))
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

    top.append(func("next", ["c"], "next_fn_t", _next_body(e, lo)))
    if mode == ERR:
        body = e.seq(_err_body(e, lo), e.call(lo("proc_exit"), e.mb.as_(e.n(0), lo("t_u32"))))
    else:
        body = e.seq(
            e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
            e.seq(*_checks(e, lo, check, lo("next"))),
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
    _enum_lets(e, setup, "enum-llvm.atz")
    for name, params, ret in [("main_fn_t", [], "t_i32"), ("next_fn_t", ["color_t"], "color_t")]:
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
    exported = ["llvm", "ll", "c", "t_i32", "color_t", "main_fn_t", "next_fn_t"] + ["color_" + n for n in NAMES]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("vec", e.import_local("vec", "vec-llvm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("colors", e.call(e.fld(e.v("vec"), "type"), e.v("color_t"))))
    for f in ["own", "new"]:
        top.append(e.let("colors_" + f, e.fld(e.v("colors"), f)))
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

    top.append(func("next", ["c"], "next_fn_t", _next_body(e, lo)))
    body = e.seq(e.seq(*_checks(e, lo, check, lo("next"))), e.ret(e.n(0)))
    top.append(func("main", [], "main_fn_t", body, "export_fn"))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top


def module(e, kind):
    if kind == WASM:
        return _wasm(e, WASM)
    if kind == ERR:
        return _wasm(e, ERR)
    if kind == LLVM:
        return _llvm(e)
    raise AssertionError(kind)
