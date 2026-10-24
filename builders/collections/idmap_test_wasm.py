"""idmap-test-wasm.atz: a WASI app exercising idmap-wasm.atz with i32 values and with owned values (vec(i32)); its
exit status is the number of failed checks."""

from ..wasm.wat import bind_types


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
    # the owned value type, a constant for the idmap over it
    setup.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    setup.append(e.let("ints", e.call(e.fld(e.v("vec"), "type"), e.v("t_i32"))))
    setup.append(e.let("ints_t", e.fld(e.v("ints"), "type")))
    setup.append(e.let("ints_new", e.fld(e.v("ints"), "new")))
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "ints_t", "ints_new"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("idmap", e.import_local("idmap", "idmap-wasm.atz")))
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
    top.append(e.let("im", e.call(e.fld(e.v("idmap"), "type"), e.v("t_i32"))))
    top.append(e.let("im_new", e.fld(e.v("im"), "new")))
    top.append(e.let("vm", e.call(e.fld(e.v("idmap"), "type"), e.v("ints_t"))))
    top.append(e.let("vm_new", e.fld(e.v("vm"), "new")))

    def lo(name):
        return e.lower(e.v(name))

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    def got(v, id_):
        return e.match_of(
            method(v, "get", e.n(id_)),
            "p",
            None,
            e.p("some", e.mb.field(e.v("p"), e.n(0))),
            e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
        )

    def got_len(v, id_):
        return e.match_of(
            method(v, "get", e.n(id_)),
            "p",
            None,
            e.p("some", e.mb.as_(e.fld(e.mb.field(e.v("p"), e.n(0)), "len"), lo("t_i32"))),
            e.p("none", e.mb.as_(e.n(-1), lo("t_i32"))),
        )

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.seq(
            e.let("a", e.call(lo("im_new"), e.tup())),
            check(e.eq(e.fld(e.v("a"), "len"), e.n(0))),
            check(e.eq(method("a", "index_of", e.n(5)), e.n(-1))),
            method("a", "put", e.n(30), e.n(300)),
            method("a", "put", e.n(10), e.n(100)),
            method("a", "put", e.n(20), e.n(200)),
            check(e.eq(e.fld(e.v("a"), "len"), e.n(3))),
            check(e.eq(method("a", "id_at", e.n(0)), e.n(10))),
            check(e.eq(method("a", "id_at", e.n(1)), e.n(20))),
            check(e.eq(method("a", "id_at", e.n(2)), e.n(30))),
            check(e.eq(method("a", "index_of", e.n(20)), e.n(1))),
            check(e.eq(method("a", "index_of", e.n(25)), e.n(-3))),
            check(e.eq(method("a", "index_of", e.n(5)), e.n(-1))),
            check(e.eq(got("a", 20), e.n(200))),
            check(e.eq(got("a", 25), e.n(-1))),
            # an overwrite keeps one id
            method("a", "put", e.n(20), e.n(201)),
            check(e.eq(e.fld(e.v("a"), "len"), e.n(3))),
            check(e.eq(got("a", 20), e.n(201))),
            check(e.eq(method("a", "remove", e.n(20)), e.n(1))),
            check(e.eq(method("a", "remove", e.n(20)), e.n(0))),
            check(e.eq(e.fld(e.v("a"), "len"), e.n(2))),
            check(e.eq(method("a", "id_at", e.n(1)), e.n(30))),
            check(e.eq(got("a", 20), e.n(-1))),
            # owned values: taken by put, borrowed by get, dropped with the map
            e.let("b", e.call(lo("vm_new"), e.tup())),
            e.let("x", e.call(lo("ints_new"), e.tup())),
            method("x", "push", e.n(1)),
            method("x", "push", e.n(2)),
            method("b", "put", e.n(7), e.call(e.fld(e.v("x"), "move"), e.tup())),
            method("b", "put", e.n(3), e.call(lo("ints_new"), e.tup())),
            check(e.eq(e.fld(e.v("b"), "len"), e.n(2))),
            check(e.eq(method("b", "id_at", e.n(0)), e.n(3))),
            check(e.eq(got_len("b", 7), e.n(2))),
            check(e.eq(got_len("b", 3), e.n(0))),
            check(e.eq(method("b", "remove", e.n(3)), e.n(1))),
            check(e.eq(e.fld(e.v("b"), "len"), e.n(1))),
        ),
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(
        e.call(
            e.fld(e.v("wasm"), "export_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("_start")),
                e.p("params", e.tup()),
                e.p("ty", e.v("start_fn_t")),
                e.p("body", e.stage(body)),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
