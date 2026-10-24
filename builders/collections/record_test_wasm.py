"""record-test-wasm.atz: a WASI app exercising record-wasm.atz: a record of an i32, an f64, an owned block
(destroyed with the record, counted into a cell), an (i32, i32) pair and an (f64, i32) tuple, read and assigned
through its field places, an empty record; its exit status has a bit per failed check.
"""

from ..eco_mb import p
from ..memory import destructor
from ..target_mb import conv, fn_of
from ..wasm.wat import bind_types
from . import record_wasm

TYPES = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "t_void", "t_f64", "t_pv", "t_pi32", "pair_t", "q_t"]
CELLS = ["counter_cell", "b_cell"]
DEPS = ["blk_destroy"]
DECLARED = ["blk_t", "blk_own"]
MADE = ["r_own", "r_new", "empty_own", "empty_new"]


def module(e):
    # Level one: the types, the cells, the destroy function and the owned block type.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(e.let("ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    setup.append(
        e.let("pair_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_i32"), e.v("t_i32"))))
    )
    setup.append(
        e.let("q_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), e.v("t_f64"), e.v("t_i32"))))
    )

    def fn_t(params, ret):
        return e.call(
            e.fld(e.v("wasm"), "fn"),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(n) for n in params])), p("ret", e.v(ret))),
        )

    setup.append(e.let("start_fn_t", fn_t([], "t_void")))
    setup.append(e.let("unary_t", fn_t(["t_pv"], "t_void")))
    for name in CELLS:
        setup.append(
            e.let(name, e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s(name)), p("size", e.int_of(4)))))
        )

    def cell(ptr):
        return e.mb.field(conv(e, e.lower(e.v("ptr_cast")), ptr, e.lower(e.v("t_pi32"))), e.n(0))

    def block(name):
        return e.mb.as_(e.call(fn_of(e, e.lower(e.v(name))), e.tup()), e.lower(e.v("t_pv")))

    counter = cell(block("counter_cell"))
    setup.append(
        e.let(
            "blk_destroy",
            e.call(
                e.fld(e.v("wasm"), "func_dep"),
                e.rec(
                    p("name", e.s("blk_destroy")),
                    p("params", e.list_new(e.mb.types_string(), e.s("v"))),
                    p("ty", e.v("unary_t")),
                    p("body", e.stage(e.seq(e.mb.set(counter, e.mb.operator_add(counter, e.n(1)))))),
                ),
            ),
        )
    )
    setup.append(
        e.let(
            "blk_r",
            e.call(
                e.fld(e.v("destructor"), "type"),
                e.rec(p("under", e.v("t_pv")), p("destroy", e.v("blk_destroy"))),
            ),
        )
    )
    setup.append(e.let("blk_t", e.fld(e.v("blk_r"), "type")))
    setup.append(e.let("blk_own", e.fld(e.v("blk_r"), "own")))
    setup.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED])))

    # Level two: the record types.
    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in TYPES + CELLS + DEPS + DECLARED:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    setup2.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    setup2.append(
        e.let(
            "r",
            e.call(
                e.fld(e.v("record"), "type"),
                e.rec(
                    p(
                        "fields",
                        e.rec(
                            p("n", e.v("t_i32")),
                            p("x", e.v("t_f64")),
                            p("b", e.v("blk_t")),
                            p("p", e.v("pair_t")),
                            p("q", e.v("q_t")),
                        ),
                    )
                ),
            ),
        )
    )
    setup2.append(e.let("r_own", e.fld(e.v("r"), "own")))
    setup2.append(e.let("r_new", e.fld(e.v("r"), "new")))
    setup2.append(e.let("empty", e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec())))))
    setup2.append(e.let("empty_own", e.fld(e.v("empty"), "own")))
    setup2.append(e.let("empty_new", e.fld(e.v("empty"), "new")))
    setup2.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED + MADE])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in TYPES + CELLS + DEPS + DECLARED + MADE:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))
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

    def lo(name):
        return e.lower(e.v(name))

    bits = [1]

    def check(cond):
        bit = bits[0]
        bits[0] *= 2
        return e.if_only(e.not_(cond), e.mb.set(e.v("fails"), e.mb.operator_add(e.v("fails"), e.n(bit))))

    def bcell(name):
        return e.mb.field(conv(e, lo("ptr_cast"), e.call(fn_of(e, lo(name)), e.tup()), lo("t_pi32")), e.n(0))

    def fld(v, name):
        return e.fld(e.v(v), name)

    def pair(a, b):
        return e.mb.as_(e.tup(e.n(a), e.n(b)), lo("pair_t"))

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.mb.set(bcell("counter_cell"), e.n(0)),
        e.mb.set(bcell("b_cell"), e.n(7)),
        e.seq(
            e.let("b", e.mb.as_(e.mb.as_(e.call(fn_of(e, lo("b_cell")), e.tup()), lo("t_pv")), lo("blk_own"))),
            e.let(
                "r",
                e.call(
                    lo("r_new"),
                    e.rec(
                        p("n", e.n(3)),
                        p("x", e.mb.as_(e.n(2.5), lo("t_f64"))),
                        p("b", e.call(e.fld(e.v("b"), "move"), e.tup())),
                        p("p", pair(1, 2)),
                        p("q", e.mb.as_(e.tup(e.mb.as_(e.n(0.5), lo("t_f64")), e.n(9)), lo("q_t"))),
                    ),
                ),
            ),
            check(e.eq(fld("r", "n"), e.n(3))),
            check(e.eq(fld("r", "x"), e.n(2.5))),
            # the owned field reads as its under: the block's cell
            check(e.eq(e.mb.field(conv(e, lo("ptr_cast"), fld("r", "b"), lo("t_pi32")), e.n(0)), e.n(7))),
            e.mb.set(fld("r", "n"), e.mb.operator_add(fld("r", "n"), e.n(4))),
            e.mb.set(fld("r", "x"), e.mb.operator_mul(fld("r", "x"), e.n(2))),
            check(e.eq(fld("r", "n"), e.n(7))),
            check(e.eq(fld("r", "x"), e.n(5))),
            # tuple fields: read by component, assigned whole, without disturbing their neighbours
            check(e.eq(e.mb.field(fld("r", "p"), e.n(0)), e.n(1))),
            check(e.eq(e.mb.field(fld("r", "p"), e.n(1)), e.n(2))),
            check(e.eq(e.mb.field(fld("r", "q"), e.n(0)), e.n(0.5))),
            check(e.eq(e.mb.field(fld("r", "q"), e.n(1)), e.n(9))),
            e.mb.set(fld("r", "p"), pair(5, 6)),
            check(e.eq(e.mb.field(fld("r", "p"), e.n(0)), e.n(5))),
            check(e.eq(e.mb.field(fld("r", "p"), e.n(1)), e.n(6))),
            check(e.eq(fld("r", "n"), e.n(7))),
            check(e.eq(fld("r", "x"), e.n(5))),
            check(e.eq(e.mb.field(fld("r", "q"), e.n(1)), e.n(9))),
            e.let("z", e.call(lo("empty_new"), e.rec())),
            # nothing destroyed while r lives
            check(e.eq(bcell("counter_cell"), e.n(0))),
        ),
        # r dropped: the block's destroy counted once
        check(e.eq(bcell("counter_cell"), e.n(1))),
        e.call(lo("proc_exit"), e.call(e.fld(e.v("fails"), "wrap"), lo("t_u32"))),
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
