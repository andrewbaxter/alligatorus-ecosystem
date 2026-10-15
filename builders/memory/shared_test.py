"""shared-test.atz: an llvm app sharing heap blocks through shared-llvm.atz. It prints `end`, then one `destroy`
per block whose count reached zero (through a constant-string dependency), and exits with that count, expected 3: a
block shared four ways (one clone dropped early), a block owned once, a block moved."""

from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of

EXPECTED = "end\ndestroy\ndestroy\ndestroy\n"
EXPECTED_STATUS = 3


def _lo(e, name):
    return e.lower(e.v(name))


def module(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_pv", e.call(e.fld(e.v("llvm"), "ptr"), e.fld(e.v("llvm"), "void"))))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    for name, params, ret in [
        ("main_fn_t", [], e.fld(e.v("llvm"), "i32")),
        ("destroy_fn_t", ["t_pv"], e.fld(e.v("llvm"), "void")),
    ]:
        setup.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("llvm"), "fn"),
                    e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", ret)),
                ),
            )
        )
    # The destroy function is a dependency (shared's release function, itself a dependency, calls it), counting into
    # a zeroed global; main returns the count after the owned values drop.
    setup.append(
        e.let(
            "s_destroy",
            e.call(e.fld(e.v("llvm"), "cstr_dep"), e.rec(e.p("name", e.s("s_destroy")), e.p("text", e.s("destroy")))),
        )
    )
    setup.append(
        e.let(
            "count",
            e.call(e.fld(e.v("llvm"), "alloc_dep"), e.rec(e.p("name", e.s("destroy_count")), e.p("ty", e.v("t_i32")))),
        )
    )

    def cell():
        return e.mb.field(e.call(fn_of(e, _lo(e, "count")), e.tup()), e.n(0))

    setup.append(
        e.let(
            "destroy",
            e.call(
                e.fld(e.v("llvm"), "func_dep"),
                e.rec(
                    e.p("name", e.s("destroy")),
                    e.p("params", e.list_new(e.mb.types_string(), e.s("p"))),
                    e.p("ty", e.v("destroy_fn_t")),
                    e.p(
                        "body",
                        e.stage(
                            e.seq(
                                e.call(
                                    e.lower(e.fld(e.v("c"), "puts")), e.call(fn_of(e, _lo(e, "s_destroy")), e.tup())
                                ),
                                e.mb.set(cell(), e.mb.operator_add(cell(), e.n(1))),
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    exported = ["count", "destroy", "s_destroy", "llvm", "ll", "c", "t_pv", "t_i32", "main_fn_t", "destroy_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("shared", e.import_local("shared", "shared-llvm.atz")))
    for name, text in [("s_end", "end")]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    puts = e.lower(e.fld(e.v("c"), "puts"))
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
        return e.call(e.lower(e.fld(e.v("c"), "malloc")), e.n(n))

    def owned(v):
        return e.mb.as_(v, _lo(e, "sp_type"))

    body = e.seq(
        e.seq(
            e.let("a", owned(e.call(_lo(e, "sp_adopt"), malloc(16)))),
            e.let("b", owned(e.call(_lo(e, "sp_clone"), e.v("a")))),
            e.let("c2", owned(e.call(_lo(e, "sp_clone"), e.v("b")))),
            e.seq(e.let("d", owned(e.call(_lo(e, "sp_clone"), e.v("c2"))))),
            e.let("e2", owned(e.call(_lo(e, "sp_adopt"), malloc(16)))),
            e.let("f", owned(e.call(_lo(e, "sp_adopt"), malloc(16)))),
            e.let("g", e.call(e.fld(e.v("f"), "move"), e.tup())),
            e.call(puts, _lo(e, "s_end")),
        ),
        e.ret(cell()),
    )
    top.append(
        e.let(
            "main",
            e.call(
                e.fld(e.v("llvm"), "func_fn"),
                e.rec(
                    e.p("mod", e.v("ll")),
                    e.p("name", e.s("main")),
                    e.p("params", e.tup()),
                    e.p("ty", e.v("main_fn_t")),
                    e.p("body", e.stage(body)),
                ),
            ),
        )
    )
    top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    return top
