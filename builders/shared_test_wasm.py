"""shared-test-wasm.atz: a WASI app sharing heap blocks through shared-wasm.atz; its exit status is the number of destroy
calls, expected 3: one block shared four ways (one clone dropped early), one block owned once, one block moved."""

from .wat import bind_types

EXPECTED_DESTROYS = 3


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.call_m(e.fld(e.v("wasi"), "fn_types"), "get", e.s("proc_exit"))))
    for name, params, ret in [
        ("start_fn_t", [], "t_void"),
        ("destroy_fn_t", ["t_pv"], "t_void"),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "fn"),
                    e.rec(
                        e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])),
                        e.p("ret", e.v(ret)),
                    ),
                ),
            )
        )
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    # The destroy function is a dependency (shared's release function, itself a dependency, calls it), counting into
    # a zeroed block.
    setup.append(
        e.let(
            "expected",
            e.call(
                e.fld(e.v("wasm"), "data_dep"),
                e.rec(
                    e.p("name", e.s("expected")),
                    e.p("elem", e.v("t_i32")),
                    e.p("values", e.list_new(e.mb.types_int(), e.int_of(3))),
                ),
            ),
        )
    )
    setup.append(
        e.let(
            "count",
            e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(e.p("name", e.s("destroy_count")), e.p("size", e.int_of(4)))),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def cell():
        return e.mb.field(e.mb.as_(e.call(lo("count"), e.tup()), lo("t_pi32")), e.n(0))

    setup.append(
        e.let(
            "destroy",
            e.call(
                e.fld(e.v("wasm"), "func_dep"),
                e.rec(
                    e.p("name", e.s("destroy")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("p"))),
                    e.p("ty", e.v("destroy_fn_t")),
                    e.p("body", e.stage(e.mb.set(cell(), e.mb.operator_add(cell(), e.n(1))))),
                ),
            ),
        )
    )
    exported = [
        "count",
        "destroy",
        "expected",
        "m",
        "proc_exit_fn_t",
        "start_fn_t",
        "destroy_fn_t",
        "t_i32",
        "t_u32",
        "t_pv",
        "t_pi32",
    ]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    top.append(e.let("shared", e.import_local("shared", "shared-wasm.atz")))
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
    top.append(
        e.let(
            "sp",
            e.call(
                e.fld(e.v("shared"), "type"),
                e.rec(e.p("under", e.v("t_pv")), e.p("destroy", e.v("destroy"))),
            ),
        )
    )
    for f in ["type", "adopt", "clone"]:
        top.append(e.let("sp_" + f, e.fld(e.v("sp"), f)))

    def malloc(n):
        return e.call(e.fld(lo("heap"), "malloc"), e.n(n))

    def owned(v):
        return e.call(lo("sp_type"), v)

    def adopt(v):
        return e.call(lo("sp_adopt"), v)

    def clone(v):
        return e.call(lo("sp_clone"), v)

    body = e.seq(
        e.seq(
            e.let("a", owned(adopt(malloc(16)))),
            e.let("b", owned(clone(e.v("a")))),
            e.let("c", owned(clone(e.v("b")))),
            e.seq(e.let("d", owned(clone(e.v("c"))))),
            e.let("e2", owned(adopt(malloc(16)))),
            e.let("f", owned(adopt(malloc(16)))),
            e.let("g", e.call(e.fld(e.v("f"), "move"), e.tup())),
        ),
        e.if_else(
            e.eq(cell(), e.mb.field(e.call(lo("expected"), e.tup()), e.n(0))),
            e.call(lo("proc_exit"), e.call(lo("t_u32"), cell())),
            e.call(lo("proc_exit"), e.call(lo("t_u32"), e.n(100))),
        ),
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
