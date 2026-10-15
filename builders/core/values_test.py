"""values-test.atz (llvm) / values-test-wasm.atz (wasi): `values.hash` checked, in the program itself, against the
published SipHash-1-3 test vector (Rust's library/coretests/tests/hash/sip.rs: key 00..0f, message 00..07 ->
0x369095118d299a8e). The app seeds the module's `siphash_key` block with that key, hashes the message as an i64 and
exits with 0 when the hash equals the vector's low 32 bits, else 1."""

from ..root_mode import APP, root_mode_finish
from ..target_mb import fn_of
from ..wasm.wat import bind_types

LLVM = "llvm"
WASM = "wasm"
FILES = {LLVM: "values-test.atz", WASM: "values-test-wasm.atz"}

KEY = [(0x07060504, 0x03020100), (0x0F0E0D0C, 0x0B0A0908)]
MESSAGE = (0x07060504, 0x03020100)
EXPECTED = 0x8D299A8E - (1 << 32)  # the vector's low 32 bits as a signed i32


def _lo(e, name):
    return e.lower(e.v(name))


def _check(e, hash_expr):
    """1 when the hash misses the vector, else 0 (an i32)."""
    return e.if_else(
        e.eq(hash_expr, e.n(EXPECTED)), e.mb.as_(e.n(0), _lo(e, "t_i32")), e.mb.as_(e.n(1), _lo(e, "t_i32"))
    )


def _i64(e, hi, lo):
    """A 64-bit constant from two 32-bit halves (host numbers are doubles)."""
    return e.mb.operator_or(
        e.mb.operator_shl(e.mb.as_(e.n(hi), _lo(e, "t_i64")), e.n(32)), e.mb.as_(e.n(lo), _lo(e, "t_i64"))
    )


def _seed_and_hash(e, hash_fn):
    def key_cell(i):
        return e.mb.field(e.mb.as_(e.call(fn_of(e, _lo(e, "key")), e.tup()), _lo(e, "t_pi64")), e.n(i))

    return [
        e.mb.set(key_cell(0), _i64(e, *KEY[0])),
        e.mb.set(key_cell(1), _i64(e, *KEY[1])),
        e.let("status", _check(e, e.call(hash_fn, _i64(e, *MESSAGE)))),
    ]


def module(e, kind):
    setup = []
    if kind == LLVM:
        setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
        setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
        lib = e.v("llvm")
        for t in ["i32", "i64"]:
            setup.append(e.let("t_" + t, e.fld(lib, t)))
        setup.append(
            e.let(
                "main_fn_t",
                e.call(e.fld(lib, "fn"), e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_i32")))),
            )
        )
        key_ty = e.p("ty", e.call(e.fld(lib, "array"), e.rec(e.p("elem", e.v("t_i64")), e.p("count", e.int_of(2)))))
        exported = ["llvm", "ll", "t_i32", "t_i64", "t_pi64", "key", "main_fn_t"]
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
        key_ty = e.p("size", e.int_of(16))
        exported = ["m", "t_i32", "t_i64", "t_u32", "t_pi64", "key", "proc_exit_fn_t", "start_fn_t"]
    setup.append(e.let("values", e.import_local("values", "values.atz")))
    setup.append(e.let("t_pi64", e.call(e.fld(lib, "ptr"), e.v("t_i64"))))
    setup.append(e.let("key", e.call(e.fld(lib, "alloc_dep"), e.rec(e.p("name", e.s("siphash_key")), key_ty))))
    exported.append("values")
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in exported])))

    top = []
    if kind == WASM:
        top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        top.append(e.let("wasi", e.import_local("wasi", "wasi-0.1.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in exported:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    hash_fn = e.lower(e.fld(e.v("values"), "hash"))
    if kind == LLVM:
        body = e.seq(*_seed_and_hash(e, hash_fn), e.ret(e.v("status")))
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
    body = e.seq(*_seed_and_hash(e, hash_fn), e.call(_lo(e, "proc_exit"), e.call(e.fld(e.v("status"), "wrap"), _lo(e, "t_u32"))))
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
