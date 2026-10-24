"""option-test-wasm.atz / option-test.atz: apps exercising option.atz over the targets' tuple values: options made
by `some`, `none` and `of`, read with `match` (with and without a fallback), passed to and returned from a function,
assigned through their binding and returned through a labeled block; an option over a tuple element (its `none`
holds the tuple's zero); an option over an option (`none`, `some(none)` and `some(some(v))` are distinct); and an
option over an owned block (destructor.atz, a destroy counting into a cell): a consumed temporary's payload is
destroyed with the case binding, a bound option destroys its payload at its scope's end, `.move()` consumes, an
unmatched option destroys its payload when dropped or assigned over, a match without `.move()` reads the payload in
place. The wasm app exits with the number of failed
checks; the llvm app prints `pass` or `fail` per check."""

from .. import target_mb as tm
from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
CHECKS = 24


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
        # An option over a pair: `none` carries the pair's zero; `some` the pair.
        e.let("p0", e.call(lo("none2"), e.tup())),
        check(e.eq(e.match_of(e.v("p0"), "v", i32(-5), e.p("some", e.mb.field(e.v("v"), e.n(1)))), e.n(-5))),
        e.let("p1", e.call(lo("some2"), e.tup(i32(3), i32(4)))),
        check(e.eq(e.match_of(e.v("p1"), "v", i32(-5), e.p("some", e.mb.field(e.v("v"), e.n(1)))), e.n(4))),
        # An option over an option: none, some(none) and some(some(v)) are three distinct values.
        e.let("q0", e.call(lo("none3"), e.tup())),
        check(e.eq(e.match_of(e.v("q0"), "v", i32(-7), e.p("some", value_or(e.v("v"), -8))), e.n(-7))),
        e.let("q1", e.call(lo("some3"), none)),
        check(e.eq(e.match_of(e.v("q1"), "v", i32(-7), e.p("some", value_or(e.v("v"), -8))), e.n(-8))),
        e.let("q2", e.call(lo("some3"), some(e.n(5)))),
        check(e.eq(e.match_of(e.v("q2"), "v", i32(-7), e.p("some", value_or(e.v("v"), -8))), e.n(5))),
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


def _owned_checks(e, lo, check, malloc):
    """The checks over `ob`, the option type of owned blocks (`osome`, `onone`), counting destroys in the cell."""

    def i32(n):
        return e.mb.as_(e.n(n), lo("t_i32"))

    def cell():
        return e.mb.field(tm.conv(e, lo("ptr_cast"), e.call(fn_of(e, lo("count")), e.tup()), lo("t_pi32")), e.n(0))

    def block():
        return e.mb.as_(malloc(), lo("blk_own"))

    def osome(v):
        return e.call(lo("osome"), v)

    def onone():
        return e.call(lo("onone"), e.tup())

    def tag_of(o):
        return e.match_of(o, "x", None, e.p("some", i32(1)), e.p("none", i32(0)))

    return [
        e.mb.set(cell(), e.n(0)),
        # a consumed temporary: the payload moves into the case binding and is destroyed with it
        check(e.eq(tag_of(osome(block())), e.n(1))),
        check(e.eq(cell(), e.n(1))),
        # a bound option destroys its payload at the end of its scope
        e.seq(e.let("o", osome(block())), check(e.eq(cell(), e.n(1)))),
        check(e.eq(cell(), e.n(2))),
        # `.move()` consumes the binding: destroyed once, in the match
        e.seq(
            e.let("o2", osome(block())),
            check(e.eq(tag_of(e.call(e.fld(e.v("o2"), "move"), e.tup())), e.n(1))),
            check(e.eq(cell(), e.n(3))),
        ),
        check(e.eq(cell(), e.n(3))),
        # unmatched temporaries: none holds nothing, some destroys its payload
        onone(),
        osome(block()),
        check(e.eq(cell(), e.n(4))),
        check(e.eq(tag_of(onone()), e.n(0))),
        # assigning over a bound option destroys what it held
        e.seq(e.let("o3", osome(block())), e.mb.set(e.v("o3"), onone()), check(e.eq(cell(), e.n(5)))),
        check(e.eq(cell(), e.n(5))),
        # read in place (no `.move()`): the payload is handed out as the raw block and stays the option's, destroyed
        # at the scope's end
        e.seq(
            e.let("o4", osome(block())),
            check(e.eq(tag_of(e.v("o4")), e.n(1))),
            check(e.eq(cell(), e.n(5))),
        ),
        check(e.eq(cell(), e.n(6))),
    ]


OPTION_NAMES = ["opt_t", "some", "none", "of", "opt2_t", "some2", "none2", "opt3_t", "some3", "none3"]
OWNED_NAMES = ["t_pv", "t_pi32", "ptr_cast", "count", "blk_type", "blk_own"]


def _destroy_lets(e, setup, lib, count_arg):
    """Setup statements: the destroy-count cell (a zeroed block) and the counting destroy dependency over `t_pv`."""
    setup.append(e.let("t_pi32", e.call(e.fld(lib, "ptr"), e.v("t_i32"))))
    setup.append(e.let("ptr_cast", e.fld(lib, "ptr_cast")))
    setup.append(
        e.let(
            "destroy_fn_t",
            e.call(
                e.fld(lib, "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("t_pv"))), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.let("count", e.call(e.fld(lib, "alloc_dep"), e.rec(e.p("name", e.s("destroy_count")), count_arg))))

    def cell():
        return e.mb.field(
            tm.conv(
                e, e.lower(e.v("ptr_cast")), e.call(fn_of(e, e.lower(e.v("count"))), e.tup()), e.lower(e.v("t_pi32"))
            ),
            e.n(0),
        )

    setup.append(
        e.let(
            "destroy",
            e.call(
                e.fld(lib, "func_dep"),
                e.rec(
                    e.p("name", e.s("destroy")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("p"))),
                    e.p("ty", e.v("destroy_fn_t")),
                    e.p("body", e.stage(e.mb.set(cell(), e.mb.operator_add(cell(), e.n(1))))),
                ),
            ),
        )
    )


def _block_type_lets(e, setup2):
    """Statements one level above the setup: the owned block type over the lifted destroy dependency."""
    setup2.append(e.let("destructor", e.import_local("destructor", "destructor.atz")))
    setup2.append(
        e.let(
            "blk",
            e.call(
                e.fld(e.v("destructor"), "type"),
                e.rec(e.p("under", e.v("t_pv")), e.p("destroy", e.v("destroy"))),
            ),
        )
    )
    for f in ["type", "own"]:
        setup2.append(e.let("blk_" + f, e.fld(e.v("blk"), f)))


def _owned_option_lets(e, top):
    """Top-level statements: the option type of owned blocks (from the lowered block type) and its constructors."""
    top.append(e.let("ob", e.call(e.fld(e.v("option"), "type"), e.v("blk_type"))))
    top.append(e.let("ob_t", e.fld(e.v("ob"), "type")))
    top.append(e.let("osome", e.fld(e.v("ob"), "some")))
    top.append(e.let("onone", e.fld(e.v("ob"), "none")))


def _option_lets(e, setup, lib_file):
    """Binds the option type and constructors for i32 (`opt_t`, `some`, `none`, `of`) and for the pair (i32, i32)
    (`opt2_t`, `some2`, `none2`) in the setup block. The pair type is made one level lower (a block importing the
    target module `lib_file` itself): a type made in the setup block would be code there, and option.type needs a
    constant."""
    setup.append(e.let("o", e.call(e.fld(e.v("option"), "type"), e.v("t_i32"))))
    setup.append(e.let("opt_t", e.fld(e.v("o"), "type")))
    for k in ["some", "none", "of"]:
        setup.append(e.let(k, e.fld(e.v("o"), k)))
    setup.append(
        e.let(
            "pair_t",
            e.lower(
                e.mb.seq(
                    [
                        e.let("lib", e.import_local("lib", lib_file)),
                        e.ret(
                            e.call(
                                e.fld(e.v("lib"), "tuple"),
                                e.list_new(e.mb.eval_type(), e.fld(e.v("lib"), "i32"), e.fld(e.v("lib"), "i32")),
                            )
                        ),
                    ]
                )
            ),
        )
    )
    setup.append(e.let("o2", e.call(e.fld(e.v("option"), "type"), e.v("pair_t"))))
    setup.append(e.let("opt2_t", e.fld(e.v("o2"), "type")))
    for k in ["some", "none"]:
        setup.append(e.let(k + "2", e.fld(e.v("o2"), k)))
    setup.append(e.let("o3", e.call(e.fld(e.v("option"), "type"), e.v("opt_t"))))
    setup.append(e.let("opt3_t", e.fld(e.v("o3"), "type")))
    for k in ["some", "none"]:
        setup.append(e.let(k + "3", e.fld(e.v("o3"), k)))


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("option", e.import_local("option", "option-wasm.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    _option_lets(e, setup, "wat-2.0.atz")
    _destroy_lets(e, setup, e.v("wasm"), e.p("size", e.int_of(4)))
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
    exported = ["m", "proc_exit_fn_t", "dec_fn_t", "start_fn_t", "t_i32", "t_u32", "destroy"] + OPTION_NAMES
    exported += [n for n in OWNED_NAMES if n not in ["blk_type", "blk_own"]]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    _block_type_lets(e, setup2)
    exported += ["blk_type", "blk_own"]
    setup2.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("option", e.import_local("option", "option-wasm.atz")))
    top.append(e.let("heap", e.import_local("heap", "wasm-alloc.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    _owned_option_lets(e, top)
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

    def malloc():
        return e.call(e.fld(lo("heap"), "malloc"), e.n(16))

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(*_checks(e, lo, check, lo("dec"))),
        e.seq(*_owned_checks(e, lo, check, malloc)),
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
    setup.append(e.let("t_void", e.fld(e.v("llvm"), "void")))
    setup.append(e.let("t_pv", e.call(e.fld(e.v("llvm"), "ptr"), e.v("t_void"))))
    _option_lets(e, setup, "llvm-ir-22.atz")
    _destroy_lets(e, setup, e.v("llvm"), e.p("ty", e.v("t_i32")))
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
    exported = ["llvm", "ll", "c", "t_i32", "main_fn_t", "dec_fn_t", "destroy"] + OPTION_NAMES
    exported += [n for n in OWNED_NAMES if n not in ["blk_type", "blk_own"]]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    _block_type_lets(e, setup2)
    exported += ["blk_type", "blk_own"]
    setup2.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("option", e.import_local("option", "option-llvm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    _owned_option_lets(e, top)
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

    def malloc():
        return e.call(e.fld(lo("c"), "malloc"), e.n(16))

    body = e.seq(e.seq(*_checks(e, lo, check, lo("dec"))), e.seq(*_owned_checks(e, lo, check, malloc)), e.ret(e.n(0)))
    top.append(func("main", [], "main_fn_t", body, "export_fn"))
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top


def module(e, kind):
    if kind == WASM:
        return _wasm(e)
    if kind == LLVM:
        return _llvm(e)
    raise AssertionError(kind)
