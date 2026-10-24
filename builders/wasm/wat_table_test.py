"""wat-table-test.atz: a WASI app exercising wat-2.0.atz's function table: `fn_ref` of a function dependency, of an
exported function and of an import, calls through the references (`call_indirect`, a multi-value result included), a
reference stored in memory as an i32 and read back (`fnref_to_int`, `int_to_fnref`), reference equality, and a
`fnref_dep` segment of references read and called; its exit status is the number of failed checks.
"""

from ..eco_mb import p
from ..target_mb import fn_of
from .wat import bind_types

CONVS = ["fn_ref", "fnref_dep", "ptr_cast", "fnref_to_int", "int_to_fnref"]


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))

    def fn_t(params, ret):
        return e.call(
            e.fld(e.v("wasm"), "fn"),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(n) for n in params])), p("ret", ret)),
        )

    setup.append(e.let("start_fn_t", fn_t([], e.v("t_void"))))
    setup.append(e.let("bin_fn_t", fn_t(["t_i32", "t_i32"], e.v("t_i32"))))
    setup.append(
        e.let("pair_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_i32"), e.v("t_i32"))))
    )
    setup.append(e.let("split_fn_t", fn_t(["t_i32"], e.v("pair_t"))))
    setup.append(e.let("bin_ref_t", e.call(e.fld(e.v("wasm"), "fnref"), e.v("bin_fn_t"))))
    setup.append(e.let("split_ref_t", e.call(e.fld(e.v("wasm"), "fnref"), e.v("split_fn_t"))))
    setup.append(e.let("exit_ref_t", e.call(e.fld(e.v("wasm"), "fnref"), e.v("proc_exit_fn_t"))))
    # the dependencies: add and mul (binary), split (a pair of the halves)
    for name, body_ in [
        ("add", e.seq(e.ret(e.mb.operator_add(e.v("a"), e.v("b"))))),
        ("mul", e.seq(e.ret(e.mb.operator_mul(e.v("a"), e.v("b"))))),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "func_dep"),
                    e.rec(
                        p("name", e.s(name)),
                        p("params", e.list_new(e.mb.types_string(), e.s("a"), e.s("b"))),
                        p("ty", e.v("bin_fn_t")),
                        p("body", e.stage(body_)),
                    ),
                ),
            )
        )
    setup.append(
        e.let(
            "split",
            e.call(
                e.fld(e.v("wasm"), "func_dep"),
                e.rec(
                    p("name", e.s("split")),
                    p("params", e.list_new(e.mb.types_string(), e.s("n"))),
                    p("ty", e.v("split_fn_t")),
                    p(
                        "body",
                        e.stage(
                            e.seq(
                                e.ret(
                                    e.mb.as_(
                                        e.tup(
                                            e.mb.operator_div(e.v("n"), e.n(2)),
                                            e.mb.operator_sub(e.v("n"), e.mb.operator_div(e.v("n"), e.n(2))),
                                        ),
                                        e.lower(e.v("pair_t")),
                                    )
                                )
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    # a cell holding a reference as an i32
    setup.append(
        e.let("cell", e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s("cell")), p("size", e.int_of(4)))))
    )
    exported = [
        "m",
        "proc_exit_fn_t",
        "start_fn_t",
        "bin_fn_t",
        "pair_t",
        "bin_ref_t",
        "split_ref_t",
        "exit_ref_t",
        "add",
        "mul",
        "split",
        "cell",
        "t_i32",
        "t_u32",
        "t_pi32",
    ]
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    for name in CONVS:
        setup.append(e.let(name, e.fld(e.v("wasm"), name)))
    setup.append(e.ret(e.rec(*[p(n, e.v(n)) for n in exported + CONVS])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported + CONVS:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(
        e.let(
            "proc_exit",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    p("module", e.fld(e.v("wasi"), "module")),
                    p("name", e.s("proc_exit")),
                    p("ty", e.v("proc_exit_fn_t")),
                ),
            ),
        )
    )
    # sub: an exported function, referenced like a dependency
    top.append(
        e.let(
            "sub",
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    p("mod", e.v("m")),
                    p("name", e.s("sub")),
                    p("params", e.tup(e.s("a"), e.s("b"))),
                    p("ty", e.v("bin_fn_t")),
                    p("body", e.stage(e.seq(e.ret(e.mb.operator_sub(e.v("a"), e.v("b")))))),
                ),
            ),
        )
    )

    # the segment: the dependencies (an export or import bound at module level reads as a runtime string there,
    # so those are referenced from staged code, where they are constants: `fn_ref` above)
    top.append(
        e.let(
            "vt",
            e.call(
                e.fld(e.v("wasm"), "fnref_dep"), e.rec(p("name", e.s("vt")), p("fns", e.tup(e.v("add"), e.v("mul"))))
            ),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def ref(name):
        return e.call(lo("fn_ref"), lo(name))

    def conv(fn, value, to):
        return e.call(lo(fn), e.rec(p("value", value), p("to", to)))

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.let("r_add", ref("add")),
        e.let("r_mul", ref("mul")),
        e.let("r_sub", ref("sub")),
        e.let("r_split", ref("split")),
        # calls through references
        check(e.eq(e.call(e.v("r_add"), e.tup(e.n(3), e.n(4))), e.n(7))),
        check(e.eq(e.call(e.v("r_mul"), e.tup(e.n(3), e.n(4))), e.n(12))),
        check(e.eq(e.call(e.v("r_sub"), e.tup(e.n(3), e.n(4))), e.n(-1))),
        e.let("halves", e.call(e.v("r_split"), e.n(7))),
        check(e.eq(e.mb.field(e.v("halves"), e.n(0)), e.n(3))),
        check(e.eq(e.mb.field(e.v("halves"), e.n(1)), e.n(4))),
        # a reference is a value: rebinding picks the function at runtime
        e.let("pick", e.if_else(e.eq(e.call(e.v("r_add"), e.tup(e.n(1), e.n(1))), e.n(2)), e.v("r_mul"), e.v("r_add"))),
        check(e.eq(e.call(e.v("pick"), e.tup(e.n(5), e.n(6))), e.n(30))),
        # equality: the same function gives the same reference; different functions differ
        check(e.eq(e.v("r_add"), ref("add"))),
        check(e.not_(e.eq(e.v("r_add"), e.v("r_mul")))),
        # stored as an i32 and read back
        e.let("slot", conv("ptr_cast", e.call(fn_of(e, lo("cell")), e.tup()), lo("t_pi32"))),
        e.mb.set(e.mb.field(e.v("slot"), e.n(0)), conv("fnref_to_int", e.v("r_mul"), lo("t_i32"))),
        e.let("back", conv("int_to_fnref", e.mb.field(e.v("slot"), e.n(0)), lo("bin_ref_t"))),
        check(e.eq(e.call(e.v("back"), e.tup(e.n(6), e.n(7))), e.n(42))),
        # a segment of references: the second is mul
        e.let("vtp", e.call(fn_of(e, lo("vt")), e.tup())),
        e.let("second", conv("int_to_fnref", e.mb.field(e.v("vtp"), e.n(1)), lo("bin_ref_t"))),
        check(e.eq(e.call(e.v("second"), e.tup(e.n(10), e.n(4))), e.n(40))),
        check(e.eq(e.mb.field(e.v("vtp"), e.n(0)), conv("fnref_to_int", e.v("r_add"), lo("t_i32")))),
        # an import through a reference: exits with the count
        e.let("r_exit", ref("proc_exit")),
        e.call(e.v("r_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
    )
    top.append(
        e.let(
            "start",
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    p("mod", e.v("m")),
                    p("name", e.s("_start")),
                    p("params", e.tup()),
                    p("ty", e.v("start_fn_t")),
                    p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
