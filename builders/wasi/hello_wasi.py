"""hello-wasi.atz / hello-wasi-wat.atz: wasm module printing a message via WASI fd_write."""

from ..target_mb import conv
from ..wasm.wat import bind_types

MESSAGE = "hello wasi!\n"

# Modes: APP builds the wasm binary, WAT logs the rendered wat text.
APP = "app"
WAT = "wat"


def module(e, mode):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(e.let("fd_write_fn_t", e.fld(e.v("wasi"), "fd_write_t")))
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.fld(e.v("wasm"), "void"))))
    exported = ["m", "fd_write_fn_t", "start_fn_t", "t_u32", "t_pv"]
    exported_fields = []
    for n in exported:
        exported_fields.append(e.p(n, e.v(n)))
    setup.append(e.ret(e.rec(*exported_fields)))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(
        e.let(
            "fd_write",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    e.p("module", e.fld(e.v("wasi"), "module")),
                    e.p("name", e.s("fd_write")),
                    e.p("ty", e.v("fd_write_fn_t")),
                ),
            ),
        )
    )
    top.append(e.let("hello", e.call_m(e.v("m"), "cstr", e.s(MESSAGE))))
    top.append(
        e.let(
            "iov",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("iov")),
                    e.p("elem", e.v("t_u32")),
                    e.p("values", e.tup(e.v("hello"), e.n(len(MESSAGE.encode())))),
                ),
            ),
        )
    )
    top.append(
        e.let(
            "nwritten",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("nwritten")),
                    e.p("elem", e.v("t_u32")),
                    e.p("values", e.tup(e.n(0))),
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
                            e.seq(
                                e.call(
                                    e.lower(e.v("fd_write")),
                                    e.tup(
                                        e.n(1),
                                        conv(
                                            e,
                                            e.lower(e.fld(e.v("wasm"), "ptr_cast")),
                                            e.lower(e.v("iov")),
                                            e.lower(e.v("t_pv")),
                                        ),
                                        e.n(1),
                                        e.lower(e.v("nwritten")),
                                    ),
                                )
                            )
                        ),
                    ),
                ),
            ),
        )
    )
    if mode == APP:
        top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    elif mode == WAT:
        top.append(e.call(e.mb.log(), e.fld(e.call_m0(e.v("m"), "render"), "wat")))
    else:
        raise AssertionError(mode)
    return top
