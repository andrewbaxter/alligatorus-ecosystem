"""closure-test-wasm.atz: a WASI app exercising closure-wasm.atz: one `callable(i32) -> i32` signature; an
accumulator closure whose captures are read and written across calls, a closure over an owned capture (destroyed
with the closure, counted into a cell), and `closure.of` a plain function; its exit status has a bit per failed
check."""

from ..eco_mb import p
from ..memory import destructor
from ..target_mb import conv, fn_of
from ..wasm.wat import bind_types
from . import closure_wasm

TYPES = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "t_void", "t_pv", "t_pi32"]
CELLS = ["counter_cell", "b_cell"]
DEPS = ["blk_destroy", "dbl"]
DECLARED = ["blk_t", "blk_own", "callable_t", "callable_own"]
MADE = ["acc_make", "over_make", "dbl_make"]


def module(e):
    # Level one: the types, the cells, the functions, the owned block type and the callable signature.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    setup.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(e.let("ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))
    setup.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))

    def fn_t(params, ret):
        return e.call(
            e.fld(e.v("wasm"), "fn"),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(n) for n in params])), p("ret", e.v(ret))),
        )

    setup.append(e.let("start_fn_t", fn_t([], "t_void")))
    setup.append(e.let("unary_t", fn_t(["t_pv"], "t_void")))
    setup.append(e.let("dbl_t", fn_t(["t_pv", "t_i32"], "t_i32")))
    for name in CELLS:
        setup.append(
            e.let(name, e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s(name)), p("size", e.int_of(4)))))
        )

    def cell(ptr):
        return e.mb.field(conv(e, e.lower(e.v("ptr_cast")), ptr, e.lower(e.v("t_pi32"))), e.n(0))

    def block(name):
        return e.mb.as_(e.call(fn_of(e, e.lower(e.v(name))), e.tup()), e.lower(e.v("t_pv")))

    def dep(name, params, ty_, body_):
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "func_dep"),
                    e.rec(
                        p("name", e.s(name)),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.v(ty_)),
                        p("body", e.stage(e.seq(*body_))),
                    ),
                ),
            )
        )

    counter = cell(block("counter_cell"))
    dep("blk_destroy", ["v"], "unary_t", [e.mb.set(counter, e.mb.operator_add(counter, e.n(1)))])
    dep("dbl", ["v", "n"], "dbl_t", [e.ret(e.mb.operator_mul(e.v("n"), e.n(2)))])
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
    setup.append(
        e.let(
            "callable_r",
            e.call(e.fld(e.v("closure"), "callable"), e.rec(p("arg", e.v("t_i32")), p("ret", e.v("t_i32")))),
        )
    )
    setup.append(e.let("callable_t", e.fld(e.v("callable_r"), "type")))
    setup.append(e.let("callable_own", e.fld(e.v("callable_r"), "own")))
    setup.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED])))

    # Level two: the closures over level one's constants.
    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in TYPES + CELLS + DEPS + DECLARED:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    setup2.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup2.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    setup2.append(e.let("ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))

    def self_cap(name):
        return e.fld(e.v("self"), name)

    # acc: total += step * arg, yielding total (two i32 captures, read and written)
    acc_body = e.seq(
        e.mb.set(
            self_cap("total"), e.mb.operator_add(self_cap("total"), e.mb.operator_mul(self_cap("step"), e.v("arg")))
        ),
        e.ret(self_cap("total")),
    )
    # over: the owned block's cell plus arg (an owned capture, read as a borrow)
    over_body = e.seq(e.ret(e.mb.operator_add(cell(self_cap("b")), e.v("arg"))))
    for name, caps, body_ in [
        ("acc", [("total", "t_i32"), ("step", "t_i32")], acc_body),
        ("over", [("b", "blk_t")], over_body),
    ]:
        setup2.append(
            e.let(
                name + "_make",
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("callable_t")),
                            p("capture", e.rec(*[p(cn, e.v(ct)) for cn, ct in caps])),
                            p("body", e.stage(body_)),
                        ),
                    ),
                    "make",
                ),
            )
        )
    setup2.append(
        e.let(
            "dbl_make",
            e.fld(
                e.call(
                    e.fld(e.v("closure"), "of"),
                    e.rec(p("callable", e.v("callable_t")), p("fn", e.v("dbl"))),
                ),
                "make",
            ),
        )
    )
    setup2.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED + MADE])))

    # The module.
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

    def call(v, arg):
        return e.call(e.fld(e.v(v), "call"), arg)

    def method(v, name):
        return e.call(e.fld(e.v(v), name), e.tup())

    def made(name, arg):
        return e.call(fn_of(e, lo(name)), arg)

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.mb.set(bcell("counter_cell"), e.n(0)),
        e.mb.set(bcell("b_cell"), e.n(100)),
        e.seq(
            e.let("f", made("acc_make", e.rec(p("total", e.n(10)), p("step", e.n(2))))),
            check(e.eq(call("f", e.n(1)), e.n(12))),
            check(e.eq(call("f", e.n(3)), e.n(18))),
            e.let("g", made("dbl_make", e.tup())),
            check(e.eq(call("g", e.n(21)), e.n(42))),
            e.let("b", e.mb.as_(e.mb.as_(e.call(fn_of(e, lo("b_cell")), e.tup()), lo("t_pv")), lo("blk_own"))),
            e.let("h", made("over_make", e.rec(p("b", e.call(e.fld(e.v("b"), "move"), e.tup()))))),
            check(e.eq(call("h", e.n(5)), e.n(105))),
            # two closures of one signature are values of one type: rebinding drops f's closure, pick then owns h's
            e.let("pick", method("f", "move")),
            e.mb.set(e.v("pick"), method("h", "move")),
            check(e.eq(call("pick", e.n(7)), e.n(107))),
            # nothing destroyed while the closures live
            check(e.eq(bcell("counter_cell"), e.n(0))),
        ),
        # h dropped: the block's destroy counted once
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
