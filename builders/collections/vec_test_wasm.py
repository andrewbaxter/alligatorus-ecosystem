"""vec-test-wasm.atz: a WASI app exercising vec-wasm.atz. It prints `ok` through a byte vec and exits with the
number of failed checks on an i32 vec (push 100, sum, slice checks as in vec-test.atz, pop, length, capacity)."""

from ..wasm.wat import bind_types

COUNT = 100
MESSAGE = b"ok\n"


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s("proc_exit"))))
    setup.append(e.let("fd_write_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s("fd_write"))))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))
            ),
        )
    )
    exported = ["m", "proc_exit_fn_t", "fd_write_fn_t", "start_fn_t", "t_i32", "t_u32", "t_u8", "t_pv"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    for name, ty in [("proc_exit", "proc_exit_fn_t"), ("fd_write", "fd_write_fn_t")]:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(e.p("module", e.fld(e.v("wasi"), "module")), e.p("name", e.s(name)), e.p("ty", e.v(ty))),
                ),
            )
        )
    for vname, elem in [("ints", "t_i32"), ("bytes", "t_u8")]:
        top.append(e.let(vname, e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
        for f in ["type", "new"]:
            top.append(e.let(vname + "_" + f, e.fld(e.v(vname), f)))
    top.append(
        e.let(
            "iov",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("iov")),
                    e.p("elem", e.v("t_u32")),
                    e.p("values", e.tup(e.n(0), e.n(0), e.n(0))),
                ),
            ),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def counted_loop(label, limit, body):
        return e.seq(
            e.let("i", e.mb.as_(e.n(0), lo("t_i32"))),
            e.mb.labeled(
                label,
                e.foreach(
                    e.lower(e.call(e.fld(e.v("wasm"), "loop_fn"), e.rec())),
                    "_",
                    e.seq(
                        e.if_only(e.eq(e.v("i"), e.n(limit)), e.mb.return_label(label)),
                        body,
                        e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.n(1))),
                    ),
                ),
            ),
        )

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(
            e.let("v", e.call(lo("ints_type"), e.call(lo("ints_new"), e.tup()))),
            counted_loop("fill", COUNT, method("v", "push", e.v("i"))),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(COUNT))),
            check(e.mb.operator_ge(e.fld(e.v("v"), "cap"), e.n(COUNT))),
            e.let("sum", e.mb.as_(e.n(0), lo("t_i32"))),
            counted_loop(
                "sum", COUNT, e.mb.set(e.v("sum"), e.mb.operator_add(e.v("sum"), method("v", "at", e.v("i"))))
            ),
            check(e.eq(e.v("sum"), e.n(COUNT * (COUNT - 1) // 2))),
            e.let("s", method("v", "slice", e.tup())),
            check(e.eq(e.fld(e.v("s"), "len"), e.n(COUNT))),
            e.let("sum2", e.mb.as_(e.n(0), lo("t_i32"))),
            counted_loop(
                "sum2",
                COUNT,
                e.mb.set(e.v("sum2"), e.mb.operator_add(e.v("sum2"), e.call(e.fld(e.v("s"), "at"), e.v("i")))),
            ),
            check(e.eq(e.v("sum2"), e.n(COUNT * (COUNT - 1) // 2))),
            e.let("s2", e.call(e.fld(e.v("s"), "sub"), e.tup(e.n(10), e.n(20)))),
            check(e.eq(e.fld(e.v("s2"), "len"), e.n(10))),
            check(e.eq(e.call(e.fld(e.v("s2"), "at"), e.n(0)), e.n(10))),
            e.mb.set(e.call(e.fld(e.v("s2"), "at"), e.n(1)), e.n(777)),
            check(e.eq(method("v", "at", e.n(11)), e.n(777))),
            check(
                e.eq(
                    e.match_of(
                        method("v", "pop", e.tup()),
                        "p",
                        None,
                        e.p("some", e.v("p")),
                        e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
                    ),
                    e.n(COUNT - 1),
                )
            ),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(COUNT - 1))),
            e.mb.set(method("v", "at", e.n(3)), e.n(1000)),
            check(e.eq(method("v", "at", e.n(3)), e.n(1000))),
            method("v", "clear", e.tup()),
            check(e.eq(e.fld(e.v("v"), "len"), e.n(0))),
            check(
                e.eq(
                    e.match_of(
                        method("v", "pop", e.tup()),
                        "p",
                        None,
                        e.p("some", e.v("p")),
                        e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
                    ),
                    e.n(-1),
                )
            ),
            e.let("s", e.call(lo("bytes_type"), e.call(lo("bytes_new"), e.tup()))),
            *[method("s", "push", e.n(b)) for b in MESSAGE],
            e.mb.set(e.mb.field(lo("iov"), e.n(0)), e.mb.as_(e.fld(e.v("s"), "data"), lo("t_u32"))),
            e.mb.set(e.mb.field(lo("iov"), e.n(1)), e.call(lo("t_u32"), e.fld(e.v("s"), "len"))),
            e.call(
                lo("fd_write"),
                e.tup(
                    e.n(1),
                    e.mb.as_(lo("iov"), lo("t_u32")),
                    e.n(1),
                    e.mb.as_(e.mb.field(lo("iov"), e.n(2)), lo("t_u32")),
                ),
            ),
        ),
        e.call(lo("proc_exit"), e.call(lo("t_u32"), e.v("fails"))),
    )
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
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
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
