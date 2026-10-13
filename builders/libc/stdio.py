"""stdio-libc.atz: stdin and stdout as byte functions of an llvm module, over libc's getchar and putchar.

Exports: `read (ctx) -> i32` (the next byte of stdin, or -1 at its end; `ctx` is ignored) and `write (ctx, b)`,
dependencies (`func_dep`) a module gets when its code first uses them; `exit`, libc's; `null`, the null pointer;
and `pv`, the pointer type.
"""

FILE = "stdio-libc.atz"


def _fn_t(e, params, ret):
    return e.call(
        e.fld(e.v("llvm"), "fn"),
        e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), e.p("ret", e.v(ret))),
    )


def _dep(e, name, params, fn_t, body_):
    return e.let(
        name,
        e.call(
            e.fld(e.v("llvm"), "func_dep"),
            e.rec(
                e.p("name", e.s("stdio_" + name)),
                e.p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                e.p("ty", e.v(fn_t)),
                e.p("body", e.stage(body_)),
            ),
        ),
    )


def module(e):
    # The types, computed one level down so the dependencies take them as constants.
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    for prim in ["i32", "void"]:
        setup.append(e.let("t_" + prim, e.fld(e.v("llvm"), prim)))
    setup.append(e.let("t_pv", e.call(e.fld(e.v("llvm"), "ptr"), e.v("t_void"))))
    setup.append(e.let("read_fn_t", _fn_t(e, ["t_pv"], "t_i32")))
    setup.append(e.let("write_fn_t", _fn_t(e, ["t_pv", "t_i32"], "t_void")))
    setup.append(
        e.let("pv_gt", e.call(e.fld(e.v("llvm"), "global_t"), e.rec(e.p("ty", e.v("t_pv")), e.p("mem", e.b(False)))))
    )
    exported = ["t_i32", "t_void", "t_pv", "read_fn_t", "write_fn_t", "pv_gt"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    top.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(_dep(e, "read", ["ctx"], "read_fn_t", e.seq(e.ret(e.call(e.lower(e.fld(e.v("c"), "getchar")), e.tup())))))
    top.append(
        _dep(e, "write", ["ctx", "b"], "write_fn_t", e.seq(e.call(e.lower(e.fld(e.v("c"), "putchar")), e.v("b")), e.seq()))
    )
    top.append(
        e.let("null", e.call(e.fld(e.v("llvm"), "ref_fn"), e.rec(e.p("ref", e.s("null")), e.p("ty", e.v("pv_gt")))))
    )
    top.append(
        e.ret(
            e.rec(
                e.p("read", e.v("read")),
                e.p("write", e.v("write")),
                e.p("exit", e.fld(e.v("c"), "exit")),
                e.p("null", e.v("null")),
                e.p("pv", e.v("t_pv")),
            )
        )
    )
    return top
