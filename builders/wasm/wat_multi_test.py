"""wat-multi-test.atz: a WASI app checking wat-2.0.atz's multi-value (tuple) results where the values are consumed
straight off the stack: a call's pair result as the argument of another call (alone and beside another argument),
bound first, chosen by an if/else, and returned through a labeled block; its exit status is the number of failed
checks."""

from .wat import bind_types


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(
        e.let("pair_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_i32"), e.v("t_i32"))))
    )
    for name, params, ret in [
        ("start_fn_t", [], "t_void"),
        ("pair_fn_t", ["t_i32"], "pair_t"),
        ("diff_fn_t", ["pair_t"], "t_i32"),
        ("diff2_fn_t", ["t_i32", "pair_t"], "t_i32"),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "fn"),
                    e.rec(
                        e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))
                    ),
                ),
            )
        )
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "pair_fn_t", "diff_fn_t", "diff2_fn_t", "t_i32", "t_u32", "pair_t"]
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

    def func(name, params, fn_t, body, kind="func_fn"):
        return e.let(
            name,
            e.call(
                e.fld(e.v("wasm"), kind),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s(name)),
                    e.p("params", e.tup(*[e.s(pn) for pn in params])),
                    e.p("ty", e.v(fn_t)),
                    e.p("body", e.stage(body)),
                ),
            ),
        )

    def i32(n):
        return e.mb.as_(e.n(n), lo("t_i32"))

    def returning(value):
        """A function body yielding `value` (a return leaves the innermost block: the body is one labeled block)."""
        return e.mb.labeled("fn", e.seq(e.mb.return_to("fn", value)))

    # pair(n) = (n, n + 2); diff(p) = p.1 - p.0; diff2(a, p) = a * 100 + p.1 - p.0.
    top.append(
        func(
            "pair",
            ["n"],
            "pair_fn_t",
            returning(e.mb.as_(e.tup(e.v("n"), e.mb.operator_add(e.v("n"), e.n(2))), lo("pair_t"))),
        )
    )
    top.append(
        func(
            "diff",
            ["p"],
            "diff_fn_t",
            returning(e.mb.operator_sub(e.mb.field(e.v("p"), e.n(1)), e.mb.field(e.v("p"), e.n(0)))),
        )
    )
    top.append(
        func(
            "diff2",
            ["a", "p"],
            "diff2_fn_t",
            returning(
                e.mb.operator_add(
                    e.mb.operator_mul(e.v("a"), e.n(100)),
                    e.mb.operator_sub(e.mb.field(e.v("p"), e.n(1)), e.mb.field(e.v("p"), e.n(0))),
                )
            ),
        )
    )

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    def pair(n):
        return e.call(lo("pair"), i32(n))

    body = e.seq(
        e.let("fails", i32(0)),
        # The result straight into another call.
        check(e.eq(e.call(lo("diff"), pair(7)), e.n(2))),
        check(e.eq(e.call(lo("diff2"), e.tup(i32(3), pair(7))), e.n(302))),
        # Bound first.
        e.let("q", pair(10)),
        check(e.eq(e.call(lo("diff"), e.v("q")), e.n(2))),
        check(e.eq(e.mb.field(e.v("q"), e.n(0)), e.n(10))),
        check(e.eq(e.mb.field(e.v("q"), e.n(1)), e.n(12))),
        # Chosen by an if/else, consumed directly and bound.
        e.let("c", i32(1)),
        check(e.eq(e.mb.field(e.if_else(e.eq(e.v("c"), e.n(1)), pair(20), pair(30)), e.n(0)), e.n(20))),
        e.let("r", e.if_else(e.eq(e.v("c"), e.n(1)), pair(20), pair(30))),
        check(e.eq(e.mb.field(e.v("r"), e.n(1)), e.n(22))),
        check(e.eq(e.call(lo("diff"), e.if_else(e.eq(e.v("c"), e.n(0)), pair(20), pair(30))), e.n(2))),
        # Through a labeled block.
        e.let("w", e.mb.labeled("w", e.seq(e.mb.return_to("w", pair(40))))),
        check(e.eq(e.mb.field(e.v("w"), e.n(0)), e.n(40))),
        check(e.eq(e.call(lo("diff"), e.mb.labeled("w2", e.seq(e.mb.return_to("w2", pair(50))))), e.n(2))),
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(func("_start", [], "start_fn_t", body, "export_fn"))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
