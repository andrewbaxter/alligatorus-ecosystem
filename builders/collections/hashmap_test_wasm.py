"""hashmap-test-wasm.atz: a WASI app exercising map-wasm.atz and set-wasm.atz with i32 keys; its exit status is the
number of failed checks."""

from ..wasm.wat import bind_types

COUNT = 200


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    for name, params, ret in [
        ("start_fn_t", [], "t_void"),
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
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("map", e.import_local("map", "map-wasm.atz")))
    top.append(e.let("set", e.import_local("set", "set-wasm.atz")))
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

    top.append(e.let("imap", e.call(e.fld(e.v("map"), "type"), e.tup(e.v("t_i32"), e.v("t_i32")))))
    top.append(e.let("iset", e.call(e.fld(e.v("set"), "type"), e.v("t_i32"))))
    for tname in ["imap", "iset"]:
        for f in ["type", "own", "new"]:
            top.append(e.let(tname + "_" + f, e.fld(e.v(tname), f)))

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

    def truthy(x):
        return e.not_(e.eq(x, e.n(0)))

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(
            e.let("mp", e.mb.as_(e.call(lo("imap_new"), e.tup()), lo("imap_own"))),
            counted_loop("fill", COUNT, method("mp", "put", e.v("i"), e.mb.operator_mul(e.v("i"), e.n(3)))),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT))),
            check(truthy(method("mp", "has", e.n(150)))),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(7)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
                    ),
                    e.n(21),
                )
            ),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(500)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
                    ),
                    e.n(-1),
                )
            ),
            check(e.not_(truthy(method("mp", "has", e.n(500))))),
            check(truthy(method("mp", "remove", e.n(100)))),
            check(e.not_(truthy(method("mp", "has", e.n(100))))),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT - 1))),
            method("mp", "put", e.n(100), e.n(5)),
            check(
                e.eq(
                    e.match_of(
                        method("mp", "get", e.n(100)),
                        "p",
                        None,
                        e.p("some", e.mb.field(e.v("p"), e.n(0))),
                        e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
                    ),
                    e.n(5),
                )
            ),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(COUNT))),
            check(e.not_(truthy(method("mp", "remove", e.n(999))))),
            method("mp", "clear", e.tup()),
            check(e.eq(e.fld(e.v("mp"), "len"), e.n(0))),
            check(e.not_(truthy(method("mp", "has", e.n(7))))),
            e.let("st", e.mb.as_(e.call(lo("iset_new"), e.tup()), lo("iset_own"))),
            counted_loop("fills", 50, method("st", "add", e.v("i"))),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(50))),
            check(truthy(method("st", "has", e.n(25)))),
            check(truthy(method("st", "remove", e.n(25)))),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(49))),
            check(e.not_(truthy(method("st", "has", e.n(25))))),
            method("st", "add", e.n(25)),
            method("st", "add", e.n(25)),
            check(e.eq(e.fld(e.v("st"), "len"), e.n(50))),
        ),
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(func("_start", [], "start_fn_t", body, "export_fn"))
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
