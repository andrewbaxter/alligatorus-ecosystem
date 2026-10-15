"""destructor-test-wasm.atz: a WASI app owning heap blocks through destructor.atz; its exit status is the number
of destroy calls, expected 3 (a reassignment, the moved-into binding, the reassigned binding; the moved-from binding
is not destroyed)."""

from .. import target_mb as tm
from ..wasm.wat import bind_types

EXPECTED_DESTROYS = 3


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    for name, params, ret in [("start_fn_t", [], "t_void"), ("release_fn_t", ["t_pv"], "t_void")]:
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
    exported = ["m", "proc_exit_fn_t", "start_fn_t", "release_fn_t", "t_i32", "t_u32", "t_pv"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    top.append(e.let("destructor", e.import_local("destructor", "destructor.atz")))
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
            "cells",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("cells")),
                    e.p("elem", e.v("t_i32")),
                    e.p("values", e.tup(e.n(0))),
                ),
            ),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def cell():
        return e.mb.field(lo("cells"), e.n(0))

    release_body = e.seq(
        e.mb.set(cell(), e.mb.operator_add(cell(), e.n(1))),
        e.call(e.fld(lo("heap"), "free"), e.v("p")),
    )
    top.append(
        e.let(
            "release",
            e.call(
                e.fld(e.v("wasm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("release")),
                    e.p("params", e.tup(e.s("p"))),
                    e.p("ty", e.v("release_fn_t")),
                    e.p("body", e.stage(release_body)),
                ),
            ),
        )
    )
    top.append(
        e.let(
            "owned_r",
            e.call(e.fld(e.v("destructor"), "type"), e.rec(e.p("under", e.v("t_pv")), e.p("destroy", e.v("release")))),
        )
    )
    top.append(e.let("owned_blk", e.fld(e.v("owned_r"), "type")))
    top.append(e.let("own_blk", e.fld(e.v("owned_r"), "own")))

    def malloc(n):
        return e.call(e.fld(lo("heap"), "malloc"), e.n(n))

    def owned(v):
        return e.mb.as_(v, lo("own_blk"))

    body = e.seq(
        e.seq(
            e.let("a", owned(malloc(16))),
            e.let("b", owned(malloc(16))),
            e.let("c", e.call(e.fld(e.v("b"), "move"), e.tup())),
            e.mb.set(e.v("a"), owned(malloc(16))),
            e.mb.set(
                e.mb.field(tm.conv(e, lo("ptr_cast"), e.mb.as_(e.v("c"), lo("t_pv")), lo("t_pi32")), e.n(0)), e.n(5)
            ),
        ),
        e.call(lo("proc_exit"), e.call(e.fld(cell(), "wrap"), lo("t_u32"))),
    )
    top.append(e.let("t_pi32", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_i32"))))
    top.append(e.let("ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))
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
