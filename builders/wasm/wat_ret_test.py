"""wat-ret-err.atz: a module that must fail to build: a function declared to yield an f64 whose every path returns an
(i32, i32) tuple (a returned value is cast to the declared result type like a body's last value)."""

from .wat import bind_types


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(
        e.let(
            "f_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("t_i32"))), e.p("ret", e.v("t_f64"))),
            ),
        )
    )
    exported = ["m", "f_t", "t_i32", "t_f64"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    body = e.seq(e.if_only(e.eq(e.v("x"), e.n(0)), e.ret(e.tup(e.v("x"), e.v("x")))), e.ret(e.tup(e.v("x"), e.n(1))))
    top.append(
        e.call(
            e.fld(e.v("wasm"), "export_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("f")),
                e.p("params", e.tup(e.s("x"))),
                e.p("ty", e.v("f_t")),
                e.p("body", e.stage(body)),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
