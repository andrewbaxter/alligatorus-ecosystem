"""owned-test.atz (llvm) / owned-test-wasm.atz (wasi): a vec and a map holding values with a destructor
(destructor.atz owned blocks over `ptr(void)`); the exit status is the number of destroy calls, expected 12:
vec: pop (1, the popped binding drops), assigning through `at(0)` (1, the old element), clear (2), the owned vec's
drop (2); map: an overwriting put (1), remove (1), clear (2), the owned map's drop (1); a labeled block yielding an
owned binding's value by `move()` (1: the moved binding does not drop, the block's value does)."""

from ..root_mode import APP, root_mode_finish
from .. import target_mb as tm
from ..target_mb import fn_of
from ..wasm.wat import bind_types

LLVM = "llvm"
WASM = "wasm"
FILES = {LLVM: "owned-test.atz", WASM: "owned-test-wasm.atz"}  # plus owned-test-ir.atz: the llvm IR logged
EXPECTED_DESTROYS = 12


def _lo(e, name):
    return e.lower(e.v(name))


def module(e, kind, mode=APP):
    setup = []
    if kind == LLVM:
        setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
        setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
        setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
        lib = e.v("llvm")
        for t in ["i32", "void"]:
            setup.append(e.let("t_" + t, e.fld(lib, t)))
        setup.append(e.let("t_pv", e.call(e.fld(lib, "ptr"), e.v("t_void"))))
        setup.append(
            e.let(
                "main_fn_t",
                e.call(e.fld(lib, "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))),
            )
        )
        count_arg = e.p("ty", e.v("t_i32"))
        exported = ["llvm", "ll", "c", "t_i32", "t_pv", "main_fn_t"]
    else:
        setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
        setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
        lib = e.v("wasm")
        bind_types(e, setup)
        setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
        setup.append(
            e.let(
                "start_fn_t",
                e.call(e.fld(lib, "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))),
            )
        )
        count_arg = e.p("size", e.int_of(4))
        exported = ["m", "t_i32", "t_u32", "t_pv", "proc_exit_fn_t", "start_fn_t"]
    setup.append(e.let("t_pi32", e.call(e.fld(lib, "ptr"), e.v("t_i32"))))
    setup.append(e.let("ptr_cast", e.fld(lib, "ptr_cast")))
    setup.append(
        e.let(
            "destroy_fn_t",
            e.call(
                e.fld(lib, "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("t_pv"))), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.let("count", e.call(e.fld(lib, "alloc_dep"), e.rec(e.p("name", e.s("destroy_count")), count_arg))))

    def cell():
        return e.mb.field(
            tm.conv(e, _lo(e, "ptr_cast"), e.call(fn_of(e, _lo(e, "count")), e.tup()), _lo(e, "t_pi32")), e.n(0)
        )

    # The destroy function (a dependency) counts into the zeroed block.
    setup.append(
        e.let(
            "destroy",
            e.call(
                e.fld(lib, "func_dep"),
                e.rec(
                    e.p("name", e.s("destroy")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("p"))),
                    e.p("ty", e.v("destroy_fn_t")),
                    e.p("body", e.stage(e.mb.set(cell(), e.mb.operator_add(cell(), e.n(1))))),
                ),
            ),
        )
    )
    exported += ["t_pi32", "ptr_cast", "count", "destroy"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    # The owned block type, one lifting level above the setup: a const function's result is a value of the context
    # it ran in, so `destructor.type` takes the lifted destroy dependency, and the collections (below) take the
    # lifted owned type as their constant element type.
    setup2 = []
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    setup2.append(e.let("destructor", e.import_local("destructor", "destructor.atz")))
    setup2.append(
        e.let(
            "blk",
            e.call(
                e.fld(e.v("destructor"), "type"),
                e.rec(e.p("under", e.v("t_pv")), e.p("destroy", e.v("destroy"))),
            ),
        )
    )
    for f in ["type", "own"]:
        setup2.append(e.let("blk_" + f, e.fld(e.v("blk"), f)))
    exported += ["blk_type", "blk_own"]
    setup2.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    if kind == WASM:
        top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    if kind == WASM:
        top.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    top.append(e.let("vec", e.import_local("vec", "vec-" + kind + ".atz")))
    top.append(e.let("map", e.import_local("map", "map-" + kind + ".atz")))
    top.append(e.let("blks", e.call(e.fld(e.v("vec"), "type"), e.v("blk_type"))))
    for f in ["own", "new"]:
        top.append(e.let("blks_" + f, e.fld(e.v("blks"), f)))
    top.append(e.let("bmap", e.call(e.fld(e.v("map"), "type"), e.tup(e.v("t_i32"), e.v("blk_type")))))
    for f in ["own", "new"]:
        top.append(e.let("bmap_" + f, e.fld(e.v("bmap"), f)))

    def malloc():
        if kind == WASM:
            return e.call(e.fld(_lo(e, "heap"), "malloc"), e.n(16))
        return e.call(e.fld(_lo(e, "c"), "malloc"), e.n(16))

    def block():
        """A fresh owned block (an owned temporary)."""
        return e.mb.as_(malloc(), _lo(e, "blk_own"))

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    body = e.seq(
        e.seq(
            e.let("v", e.call(_lo(e, "blks_new"), e.tup())),
            method("v", "push", block()),
            method("v", "push", block()),
            method("v", "push", block()),
            e.seq(e.let("p", method("v", "pop", e.tup()))),
            e.mb.set(method("v", "at", e.n(0)), block()),
            e.let("r", e.mb.as_(method("v", "at", e.n(1)), _lo(e, "t_pv"))),
            method("v", "clear", e.tup()),
            method("v", "push", block()),
            method("v", "push", block()),
            e.let("m", e.call(_lo(e, "bmap_new"), e.tup())),
            method("m", "put", e.n(1), block()),
            method("m", "put", e.n(1), block()),
            e.let("removed", method("m", "remove", e.n(1))),
            method("m", "put", e.n(2), block()),
            method("m", "put", e.n(3), block()),
            method("m", "clear", e.tup()),
            method("m", "put", e.n(4), block()),
            e.let(
                "w",
                e.mb.labeled("lb", e.seq(e.let("t", block()), e.mb.return_to("lb", method("t", "move", e.tup())))),
            ),
        ),
    )
    if kind == LLVM:
        top.append(
            e.let(
                "main",
                e.call(
                    e.fld(e.v("llvm"), "export_fn"),
                    e.rec(
                        e.p("mod", e.v("ll")),
                        e.p("name", e.s("main")),
                        e.p("params", e.tup()),
                        e.p("ty", e.v("main_fn_t")),
                        e.p("body", e.stage(e.seq(body, e.ret(cell())))),
                    ),
                ),
            )
        )
        top.append(root_mode_finish(mode, e, e.v("llvm"), e.v("ll")))
        return top
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
            "start",
            e.call(
                e.fld(e.v("wasm"), "export_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("_start")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("start_fn_t")),
                    e.p(
                        "body",
                        e.stage(
                            e.seq(body, e.call(_lo(e, "proc_exit"), e.call(e.fld(cell(), "wrap"), _lo(e, "t_u32"))))
                        ),
                    ),
                ),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
