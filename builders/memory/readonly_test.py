"""readonly-test.atz / readonly-test-err-ro.atz / readonly-test-err-sealed.atz: llvm apps exercising readonly.atz.
The app reads a read-only value and a sealed value (assigned, then sealed) and prints `ok`; the err modules assign a
read-only value, and a sealed value after sealing, which must fail to compile."""

from ..root_mode import APP, root_mode_finish

ERR_RO = "err_ro"
ERR_SEALED = "err_sealed"


def _lo(e, name):
    return e.lower(e.v(name))


def module(e, mode):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("readonly", e.import_local("readonly", "readonly.atz")))
    setup.append(e.let("t_i32", e.fld(e.v("llvm"), "i32")))
    setup.append(
        e.let(
            "main_fn_t",
            e.call(
                e.fld(e.v("llvm"), "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))
            ),
        )
    )
    setup.append(e.let("ro_i32", e.call(e.fld(e.v("readonly"), "type"), e.v("t_i32"))))
    setup.append(e.let("sealed_i32", e.call(e.fld(e.v("readonly"), "sealed"), e.v("t_i32"))))
    exported = ["llvm", "ll", "c", "t_i32", "main_fn_t", "ro_i32", "sealed_i32"]
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    for name, text in [("s_ok", "ok"), ("s_bad", "bad")]:
        top.append(e.let(name, e.call_m(e.v("ll"), "cstr", e.s(text))))
    puts = e.lower(e.fld(e.v("c"), "puts"))

    def i32(v):
        return e.mb.as_(e.n(v), _lo(e, "t_i32"))

    common = [
        e.let("r", e.mb.as_(i32(5), _lo(e, "ro_i32"))),
        e.let("s", e.mb.as_(i32(1), _lo(e, "sealed_i32"))),
        e.mb.set(e.v("s"), i32(7)),
        e.call(e.fld(e.v("s"), "seal"), e.tup()),
    ]
    if mode == APP:
        body = e.seq(
            *common,
            # both read as i32 (a read-only field is plain `final`: reads are the inner value)
            e.if_else(
                e.eq(
                    e.mb.operator_add(e.mb.as_(e.v("r"), _lo(e, "t_i32")), e.mb.as_(e.v("s"), _lo(e, "t_i32"))), e.n(12)
                ),
                e.call(puts, _lo(e, "s_ok")),
                e.call(puts, _lo(e, "s_bad")),
            ),
            e.ret(i32(0)),
        )
    elif mode == ERR_RO:
        body = e.seq(*common, e.mb.set(e.v("r"), i32(6)), e.ret(i32(0)))
    elif mode == ERR_SEALED:
        body = e.seq(*common, e.mb.set(e.v("s"), i32(8)), e.ret(i32(0)))
    else:
        raise AssertionError(mode)
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
    if mode == APP:
        top.append(root_mode_finish(APP, e, e.v("llvm"), e.v("ll")))
    else:
        top.append(e.call(e.mb.log(), e.fld(e.call_m0(e.v("ll"), "render"), "ir")))
    return top
