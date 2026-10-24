"""Shared shape of the editor project's WASI test apps: `_start` runs the checks the builder gives; when one fails it
prints the 1-based index of the first that did (a line on stdout) and exits with 1, else with 0
(tests/cases/editor); editor-types.atz's `str` and `bytes` are bound for the checks."""

from . import editor_types
from ..wasm.kit import Kit


def module(e, imports, checks):
    """`imports`: (binding, file) pairs; `checks(k)`: the list of statements, using `check(cond)` from the kit
    (`k.check`)."""
    k = Kit(e)
    setup = []
    k.bind(setup)
    setup.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    setup.append(e.let("proc_exit_t", e.fld(e.v("wasi"), "proc_exit_t")))
    setup.append(e.let("fd_write_t", e.fld(e.v("wasi"), "fd_write_t")))
    setup.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.fld(e.v("wasm"), "void"))))
    setup.append(e.let("start_t", k.fn_t([], "t_void")))
    exported = [
        "m",
        "proc_exit_t",
        "fd_write_t",
        "t_pv",
        "start_t",
        "t_i32",
        "t_u32",
        "t_f64",
        "t_pi32",
        "t_pf64",
        "t_pu8",
        "t_pu32",
        "t_u8",
        "t_void",
    ]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))
    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    for name, file in imports:
        top.append(e.let(name, e.import_local(name, file)))
    top.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n != "t_pu8":
            top.append(e.let(n, e.fld(e.v("types"), n)))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(
        e.let(
            "proc_exit",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    e.p("module", e.fld(e.v("wasi"), "module")),
                    e.p("name", e.s("proc_exit")),
                    e.p("ty", e.v("proc_exit_t")),
                ),
            ),
        )
    )

    top.append(
        e.let(
            "fd_write",
            e.call(
                e.fld(e.v("wasm"), "import_fn"),
                e.rec(
                    e.p("module", e.fld(e.v("wasi"), "module")),
                    e.p("name", e.s("fd_write")),
                    e.p("ty", e.v("fd_write_t")),
                ),
            ),
        )
    )
    # The report block: an iovec (pointer, length) at 0, the count written at 8, the digits and newline at 16..32.
    k.block(top, "report", 32)
    count = [0]

    def check(cond):
        count[0] += 1
        return e.if_only(
            e.not_(cond), e.if_only(e.mb.operator_eq(e.v("fail"), e.n(0)), e.mb.set(e.v("fail"), e.n(count[0])))
        )

    k.check = check
    v = e.v

    def byte_at(addr):
        return k.at(addr, 0, "t_pu8")

    # `print_i32(n)`: prints `n` in decimal and a newline on stdout (`k.print(expr)` in the checks, for looking at
    # values while a test is being written).
    k.dep(
        top,
        "print_i32",
        ["n"],
        ["t_i32"],
        "t_void",
        e.seq(
            e.let("buf", k.block_addr("report")),
            e.let("neg", k.lt(v("n"), e.n(0))),
            e.let("m", k.ifelse(v("neg"), k.neg(v("n")), v("n"))),
            e.let("i", k.i32(31)),
            k.set(byte_at(k.add(v("buf"), v("i"))), k.m(k.i32(10), "wrap", k.lo("t_u8"))),
            k.loop(
                "digits",
                e.mb.set(v("i"), k.sub(v("i"), e.n(1))),
                k.set(
                    byte_at(k.add(v("buf"), v("i"))),
                    k.m(k.add(k.rem(v("m"), e.n(10)), e.n(ord("0"))), "wrap", k.lo("t_u8")),
                ),
                e.mb.set(v("m"), k.div(v("m"), e.n(10))),
                k.if_(k.eq(v("m"), e.n(0)), k.brk("digits")),
            ),
            k.if_(
                v("neg"),
                e.mb.set(v("i"), k.sub(v("i"), e.n(1))),
                k.set(byte_at(k.add(v("buf"), v("i"))), k.m(k.i32(ord("-")), "wrap", k.lo("t_u8"))),
            ),
            k.set(k.at(v("buf"), 0, "t_pi32"), k.add(v("buf"), v("i"))),
            k.set(k.at(v("buf"), 1, "t_pi32"), k.sub(e.n(32), v("i"))),
            e.seq(
                e.let(
                    "werr",
                    e.call(
                        k.lo("fd_write"),
                        e.tup(e.n(1), k.ptr_of(v("buf"), "t_pv"), e.n(1), k.ptr_of(k.add(v("buf"), e.n(8)), "t_pu32")),
                    ),
                )
            ),
        ),
    )

    def print_(value):
        return k.dcall("print_i32", e.mb.as_(value, k.lo("t_i32")))

    k.print = print_

    body = e.seq(
        e.let("fail", k.i32(0)),
        *checks(k),
        k.if_(k.ne(v("fail"), e.n(0)), print_(v("fail"))),
        e.call(k.lo("proc_exit"), k.m(k.ifelse(k.ne(v("fail"), e.n(0)), k.i32(1), k.i32(0)), "wrap", k.lo("t_u32"))),
    )
    top.append(
        e.call(
            e.fld(e.v("wasm"), "export_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("_start")),
                e.p("params", e.tup()),
                e.p("ty", e.v("start_t")),
                e.p("body", e.stage(body)),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("wasm"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
