"""wasm-alloc-test.atz: a WASI app exercising wasm-alloc.atz; its exit status is the number of failed checks."""

from .wat import bind_types
from .. import target_mb as tm

BIG = 200000


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    for name in ["ptr_cast", "ptr_to_int"]:
        setup.append(e.let(name, e.fld(e.v("wasm"), name)))
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "t_pv", "t_pi32", "ptr_cast", "ptr_to_int"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    top.append(e.let("malloc", e.fld(e.v("heap"), "malloc")))
    top.append(e.let("free", e.fld(e.v("heap"), "free")))
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

    def malloc(n):
        return e.call(lo("malloc"), e.n(n))

    def i32(v):
        """A constant as i32, or a pointer's address."""
        if tm.is_const_expr(v):
            return e.mb.as_(v, lo("t_i32"))
        return tm.conv(e, lo("ptr_to_int"), v, lo("t_i32"))

    def cell(p, i):
        return e.mb.field(tm.conv(e, lo("ptr_cast"), p, lo("t_pi32")), e.n(i))

    def check(cond):
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(1))))

    body = e.seq(
        e.let("fails", i32(e.n(0))),
        e.let("a", malloc(24)),
        e.let("b", malloc(100)),
        e.let("c", malloc(8)),
        check(e.not_(e.eq(i32(e.v("a")), e.n(0)))),
        check(e.eq(e.mb.operator_mod(i32(e.v("a")), e.n(8)), e.n(0))),
        check(e.mb.operator_gt(i32(e.v("b")), i32(e.v("a")))),
        check(e.mb.operator_gt(i32(e.v("c")), i32(e.v("b")))),
        check(e.mb.operator_ge(e.mb.operator_sub(i32(e.v("b")), i32(e.v("a"))), e.n(32))),
        e.mb.set(cell(e.v("a"), 0), e.n(42)),
        e.mb.set(cell(e.v("a"), 5), e.n(7)),
        e.mb.set(cell(e.v("b"), 24), e.n(9)),
        check(e.eq(cell(e.v("a"), 0), e.n(42))),
        check(e.eq(cell(e.v("a"), 5), e.n(7))),
        check(e.eq(cell(e.v("b"), 24), e.n(9))),
        e.call(lo("free"), e.v("b")),
        e.let("d", malloc(50)),
        check(e.eq(i32(e.v("d")), i32(e.v("b")))),
        e.call(lo("free"), e.v("a")),
        e.call(lo("free"), e.v("c")),
        e.let("e2", malloc(24)),
        check(e.eq(i32(e.v("e2")), i32(e.v("a")))),
        e.let("big", malloc(BIG)),
        check(e.not_(e.eq(i32(e.v("big")), e.n(0)))),
        e.mb.set(cell(e.v("big"), BIG // 4 - 1), e.n(3)),
        check(e.eq(cell(e.v("big"), BIG // 4 - 1), e.n(3))),
        # coalescing: two freed neighbours form one block that a larger request reuses in place
        e.let("x1", malloc(40)),
        e.let("x2", malloc(40)),
        e.let("x3", malloc(40)),
        e.call(lo("free"), e.v("x1")),
        e.call(lo("free"), e.v("x2")),
        e.let("y", malloc(80)),
        check(e.eq(i32(e.v("y")), i32(e.v("x1")))),
        # a freed chunk next to the top merges into it and is carved again at the same address
        e.call(lo("free"), e.v("x3")),
        e.let("z", malloc(40)),
        check(e.eq(i32(e.v("z")), i32(e.v("x3")))),
        # splitting: a small request takes the front of a large free chunk, the rest stays allocatable
        e.call(lo("free"), e.v("y")),
        e.let("s1", malloc(8)),
        check(e.eq(i32(e.v("s1")), i32(e.v("x1")))),
        e.let("s2", malloc(8)),
        check(e.mb.operator_lt(i32(e.v("s2")), i32(e.v("z")))),
        e.call(lo("free"), e.mb.as_(e.n(0), lo("t_pv"))),
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
