"""iface-test-wasm.atz: a WASI app exercising iface-wasm.atz: a `counter` interface (`inc(n)`, `get()`) implemented
by two owned types over a cell (one adds, one multiplies, with destroys counting 1 and 10 into a cell), both used
through owned interface values whose drops run the right destroys; its exit status has a bit per failed check.
"""

from ..eco_mb import p
from ..memory import destructor
from ..target_mb import conv, fn_of
from ..wasm.wat import bind_types
from . import iface_wasm

TYPES = ["m", "proc_exit_fn_t", "start_fn_t", "t_i32", "t_u32", "t_void", "t_pv", "t_pi32"]
CELLS = ["counter_cell", "a_cell", "b_cell"]
DEPS = ["a_destroy", "b_destroy", "a_inc", "b_inc", "a_get"]
DECLARED = ["a_t", "a_own", "b_t", "b_own", "counter_t", "counter_own"]
IMPLS = ["a_up", "b_up"]


def module(e):
    # The setup, evaluated before the module: the types, the cells and the dependencies.
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
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
    setup.append(e.let("binary_t", fn_t(["t_pv", "t_i32"], "t_void")))
    setup.append(e.let("getter_t", fn_t(["t_pv"], "t_i32")))
    for name in CELLS:
        setup.append(
            e.let(name, e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s(name)), p("size", e.int_of(4)))))
        )

    # The dependencies' bodies lower the setup's values.
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
    dep("a_destroy", ["v"], "unary_t", [e.mb.set(counter, e.mb.operator_add(counter, e.n(1)))])
    dep("b_destroy", ["v"], "unary_t", [e.mb.set(counter, e.mb.operator_add(counter, e.n(10)))])
    dep("a_inc", ["v", "n"], "binary_t", [e.mb.set(cell(e.v("v")), e.mb.operator_add(cell(e.v("v")), e.v("n")))])
    dep("b_inc", ["v", "n"], "binary_t", [e.mb.set(cell(e.v("v")), e.mb.operator_mul(cell(e.v("v")), e.v("n")))])
    dep("a_get", ["v"], "getter_t", [e.ret(cell(e.v("v")))])
    # The owned types and the interface, declared in the setup too (a const function's result is code at the
    # level it is called from; it is a constant one stage in, so each composition step is a level of its own).
    setup.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    setup.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
    for name, destroy in [("a", "a_destroy"), ("b", "b_destroy")]:
        setup.append(
            e.let(
                name + "_r",
                e.call(
                    e.fld(e.v("destructor"), "type"),
                    e.rec(p("under", e.v("t_pv")), p("destroy", e.v(destroy))),
                ),
            )
        )
        setup.append(e.let(name + "_t", e.fld(e.v(name + "_r"), "type")))
        setup.append(e.let(name + "_own", e.fld(e.v(name + "_r"), "own")))
    setup.append(
        e.let(
            "counter",
            e.call(
                e.fld(e.v("iface"), "declare"),
                e.rec(
                    p(
                        "methods",
                        e.rec(
                            p("inc", e.rec(p("arg", e.v("t_i32")), p("ret", e.v("t_void")))),
                            p("get", e.rec(p("arg", e.v("t_void")), p("ret", e.v("t_i32")))),
                        ),
                    )
                ),
            ),
        )
    )
    setup.append(e.let("counter_t", e.fld(e.v("counter"), "type")))
    setup.append(e.let("counter_own", e.fld(e.v("counter"), "own")))
    setup.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED])))

    # The implementations, one level in: over the declaration's constants.
    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in TYPES + CELLS + DEPS + DECLARED:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    setup2.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
    for name, inc in [("a", "a_inc"), ("b", "b_inc")]:
        setup2.append(
            e.let(
                name + "_up",
                e.fld(
                    e.call(
                        e.fld(e.v("iface"), "impl"),
                        e.rec(
                            p("iface", e.v("counter_t")),
                            p("self", e.v(name + "_t")),
                            p("methods", e.rec(p("inc", e.v(inc)), p("get", e.v("a_get")))),
                        ),
                    ),
                    "upcast",
                ),
            )
        )
    setup2.append(e.ret(e.rec(*[p(n, e.v(n)) for n in TYPES + CELLS + DEPS + DECLARED + IMPLS])))

    # The module.
    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in TYPES + CELLS + DEPS + DECLARED + IMPLS:
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

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    body = e.seq(
        e.let("fails", e.mb.as_(e.n(0), lo("t_i32"))),
        e.mb.set(bcell("counter_cell"), e.n(0)),
        e.mb.set(bcell("a_cell"), e.n(0)),
        e.mb.set(bcell("b_cell"), e.n(1)),
        e.seq(
            e.let("a", e.mb.as_(e.mb.as_(e.call(fn_of(e, lo("a_cell")), e.tup()), lo("t_pv")), lo("a_own"))),
            e.let("b", e.mb.as_(e.mb.as_(e.call(fn_of(e, lo("b_cell")), e.tup()), lo("t_pv")), lo("b_own"))),
            e.let("x", e.mb.as_(e.call(fn_of(e, lo("a_up")), method("a", "forget")), lo("counter_own"))),
            e.let("y", e.mb.as_(e.call(fn_of(e, lo("b_up")), method("b", "forget")), lo("counter_own"))),
            method("x", "inc", e.n(5)),
            method("y", "inc", e.n(5)),
            method("y", "inc", e.n(3)),
            check(e.eq(method("x", "get", e.tup()), e.n(5))),
            check(e.eq(method("y", "get", e.tup()), e.n(15))),
            # nothing destroyed while x and y live
            check(e.eq(bcell("counter_cell"), e.n(0))),
        ),
        # both dropped: a's destroy counted 1, b's 10
        check(e.eq(bcell("counter_cell"), e.n(11))),
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
