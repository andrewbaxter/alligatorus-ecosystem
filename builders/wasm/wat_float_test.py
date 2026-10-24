"""wat-float-test.atz: a WASI app exercising wat-2.0.atz's float math methods (`sqrt`, `abs`, `floor`, `ceil`,
`nearest`, `min`, `max`, `copysign`) on f64 and f32; its exit status is the number of failed checks.
"""

from .wat import bind_types


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))
            ),
        )
    )
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "t_f32", "t_f64"]
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

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    def un(v, op_):
        return e.call(e.fld(v, op_), e.tup())

    def bin_(v, op_, o):
        return e.call(e.fld(v, op_), o)

    checks = []
    for t, name in [("t_f64", "d"), ("t_f32", "f")]:
        x = e.v(name + "x")
        y = e.v(name + "y")
        checks += [
            e.let(name + "x", e.mb.as_(e.n(-2.5), lo(t))),
            e.let(name + "y", e.mb.as_(e.n(6.25), lo(t))),
            check(e.eq(un(y, "sqrt"), e.n(2.5))),
            check(e.eq(un(x, "abs"), e.n(2.5))),
            check(e.eq(un(x, "floor"), e.n(-3))),
            check(e.eq(un(x, "ceil"), e.n(-2))),
            check(e.eq(un(x, "nearest"), e.n(-2))),
            check(e.eq(un(y, "nearest"), e.n(6))),
            check(e.eq(bin_(x, "min", y), e.n(-2.5))),
            check(e.eq(bin_(x, "max", y), e.n(6.25))),
            check(e.eq(bin_(x, "max", e.n(1)), e.n(1))),
            check(e.eq(bin_(y, "copysign", x), e.n(-6.25))),
        ]
    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        *checks,
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("_start")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("start_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
