"""vec-trap.atz / vec-trap-wasm.atz: apps that index an empty vec, which must trap (the process ends with a non-zero
status). The wasm app first writes `before` to stdout (fd_write is unbuffered, so it survives the trap); the llvm app
prints nothing, since buffered stdout is lost in the trap."""

from ..root_mode import APP, root_mode_finish
from ..wasm.wat import bind_types

WASM = "wasm"
LLVM = "llvm"
MESSAGE = b"before\n"


def _llvm(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))
            ),
        )
    )
    exported = ["llvm", "ll", "c", "t_i32", "main_fn_t"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("vec", e.import_local("vec", "vec-llvm.atz")))
    top.append(e.let("ints", e.call(e.fld(e.v("vec"), "type"), e.v("t_i32"))))
    for f in ["type", "new"]:
        top.append(e.let("ints_" + f, e.fld(e.v("ints"), f)))
    body = e.seq(
        e.let("v", e.mb.as_(e.call(e.lower(e.v("ints_new")), e.tup()), e.lower(e.v("ints_type")))),
        e.let("x", e.call(e.fld(e.v("v"), "at"), e.n(0))),
        e.ret(e.v("x")),
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


def _wasm(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("proc_exit_fn_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(e.let("fd_write_fn_t", e.fld(e.v("wasi"), "fd_write_t")))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void")))
            ),
        )
    )
    exported = ["m", "proc_exit_fn_t", "fd_write_fn_t", "start_fn_t", "t_i32", "t_u32", "t_u8"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    for name, ty in [("proc_exit", "proc_exit_fn_t"), ("fd_write", "fd_write_fn_t")]:
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "import_fn"),
                    e.rec(e.p("module", e.fld(e.v("wasi"), "module")), e.p("name", e.s(name)), e.p("ty", e.v(ty))),
                ),
            )
        )
    for vname, elem in [("ints", "t_i32"), ("bytes", "t_u8")]:
        top.append(e.let(vname, e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
        for f in ["type", "new"]:
            top.append(e.let(vname + "_" + f, e.fld(e.v(vname), f)))
    top.append(
        e.let(
            "iov",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("iov")),
                    e.p("elem", e.v("t_u32")),
                    e.p("values", e.tup(e.n(0), e.n(0), e.n(0))),
                ),
            ),
        )
    )

    def lo(name):
        return e.lower(e.v(name))

    def method(v, name, *args):
        return e.call(e.fld(e.v(v), name), args[0] if len(args) == 1 else e.tup(*args))

    body = e.seq(
        e.let("s", e.mb.as_(e.call(lo("bytes_new"), e.tup()), lo("bytes_type"))),
        *[method("s", "push", e.n(b)) for b in MESSAGE],
        e.mb.set(e.mb.field(lo("iov"), e.n(0)), e.mb.as_(e.fld(e.v("s"), "data"), lo("t_u32"))),
        e.mb.set(e.mb.field(lo("iov"), e.n(1)), e.mb.as_(e.fld(e.v("s"), "len"), lo("t_u32"))),
        e.call(
            lo("fd_write"),
            e.tup(
                e.n(1), e.mb.as_(lo("iov"), lo("t_u32")), e.n(1), e.mb.as_(e.mb.field(lo("iov"), e.n(2)), lo("t_u32"))
            ),
        ),
        e.let("v", e.mb.as_(e.call(lo("ints_new"), e.tup()), lo("ints_type"))),
        e.let("x", method("v", "at", e.n(0))),
        e.call(lo("proc_exit"), e.mb.as_(e.v("x"), lo("t_u32"))),
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


def module(e, kind):
    if kind == LLVM:
        return _llvm(e)
    if kind == WASM:
        return _wasm(e)
    raise AssertionError(kind)
