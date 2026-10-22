"""wat-2.0.atz: WebAssembly text target.

Conversions: `as` only converts losslessly and never between pointer types or between pointers and integers; a
pointer type casts from itself and from constant literals. The unsafe conversions are named constant functions
taking `{value, to}`: `ptr_cast` (pointer to another pointer type), `ptr_to_int` (pointer to i32) and `int_to_ptr`
(i32 to a pointer type). Internal symbols are minted per module from a hint; only exports and imports carry user
names. Dependencies (`func_dep`, `alloc_dep`, `data_dep`, `cstr_dep`) are identified by the instance, never by
name: two apps or libraries naming a dependency alike define two items. The module's SipHash key block is reached
through `mod.siphash_key()`."""

from ..core import meta, srcmap, values
from .. import target_mb as tm
from ..target_mb import (
    panic_errs,
    a,
    acc,
    accessor,
    and_b,
    asp,
    asp_id,
    asp_iface,
    bim,
    bim0,
    binding_drop_body,
    body,
    bool_t,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_none,
    code_t,
    const_eval_in,
    count_let,
    count_loop,
    cv_bits,
    cv_no,
    cv_of,
    cve_code,
    cve_ended,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    dfalse,
    err_cve,
    errs_t,
    fn_impl,
    fn_throws,
    graft,
    has,
    hf,
    hf_rec,
    im0,
    in_,
    int_t,
    is_const,
    is_equal,
    is_runtime,
    is_target_code,
    key_str,
    loc,
    loc_t,
    lookup,
    lookup_v,
    lt,
    lv,
    marker_type,
    method,
    mk,
    mk_arg,
    no_cast_to,
    num,
    ok_cve,
    op,
    op_id,
    op_iface,
    or_b,
    outer,
    push,
    recv_of,
    reinterpret,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    src_bits,
    src_type,
    str_,
    structural_exits,
    t,
    tag_value,
    target_drop_body,
    throw_err,
    to_str,
    try_er,
    ty,
    ty_desc,
    type_aspect,
    type_can_cast_from,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    voc_t,
    xx,
    xx_t,
)

TARGET = "wasm"


def _fn_def(e, out, name, arg_type, ret):
    return tm.fn_def(e, out, TARGET, name, arg_type, ret)


def _must_v(e, res, what):
    return tm.must_v(e, TARGET, res, what)


def _wval_t(e):
    return t(e, "wval")


def _wmod_t(e):
    return t(e, "wmod")


META_EXPORTS = ["meta_t", "meta_other", "meta_new"]


def _render_t(e, meta_t):
    return e.rec(e.p("wat", str_(e)), e.p("meta", e.list_type(meta_t)), e.p("frames", str_(e)))


def _insts_t(e):
    return e.list_type(t(e, "winst"))


class IntSpec:
    def __init__(self, name, bits, signed, min_, max_):
        self.name = name
        self.bits = bits
        self.signed = signed
        self.min = min_
        self.max = max_


INT_SPECS = [
    IntSpec("i1", 1, False, 0, 1),
    IntSpec("i8", 8, True, -128, 127),
    IntSpec("i16", 16, True, -32768, 32767),
    IntSpec("i32", 32, True, -2147483648.0, 2147483647.0),
    IntSpec("i64", 64, True, -9223372036854775808.0, 9223372036854775807.0),
    IntSpec("u8", 8, False, 0, 255),
    IntSpec("u16", 16, False, 0, 65535),
    IntSpec("u32", 32, False, 0, 4294967295.0),
    IntSpec("u64", 64, False, 0, 18446744073709551615.0),
]


def _int_ty(e, name):
    for spec in INT_SPECS:
        if spec.name == name:
            return mk(
                e,
                "wt_int",
                e.p("bits", num(e, spec.bits)),
                e.p("signed", e.b(spec.signed)),
                e.p("min", e.n(spec.min)),
                e.p("max", e.n(spec.max)),
            )
    raise ValueError("no int type " + name)


def _initial_bind_impl(e, x, obj):
    """`initial_bind`: a parameter slot of this target (one local for a scalar) becomes this target's binding, typed
    as the parameter (a type delegating its aspects here keeps its own identity)."""
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_initial_bind(),
            e.p(
                "initial_bind",
                body(
                    e,
                    e.let("ps", e.call(e.mb.must_reinterpret(), e.tup(a(e, "slot"), lt(e, "wparam")))),
                    e.let("pty", e.call_m(e.v("ps"), "ty", e.tup())),
                    e.foreach(
                        e.call_m(e.v("ps"), "slots", e.tup()),
                        "s0",
                        ret_m(
                            e,
                            e.eresult_ok(
                                e.mb.eval_binding(),
                                mk(
                                    e,
                                    "wbinding",
                                    e.p("ty", e.v("pty")),
                                    e.p("slot", _wval_slot(e, e.v("pty"), e.v("s0"))),
                                ),
                            ),
                        ),
                    ),
                    e.mb.panic(e.s("wasm: parameter without a slot")),
                ),
            ),
        )
    )


def _conv_methods(e, x):
    """Lossy numeric conversions as methods on int and float values (`as` only converts losslessly): `wrap(T)` wraps an
    integer into the integer type `T` (two's complement: narrowing, extension by the source's signedness, or a
    reinterpretation at the same width); `trunc(T)` truncates a float toward zero into the integer type `T` (trapping
    when out of range); `to_float(T)` rounds an integer or a float to the float type `T`."""
    tm.method_type(e, x, "wconv", "wasm conversion")
    to = e.v("to")
    v = e.v("v")
    st = e.v("st")

    def when(cond, result):
        return e.if_only(cond, ret_m(e, result))

    def conv_via(op_, signed):
        return hf_rec(
            e,
            "h_conv",
            e.p("loc", loc(e)),
            e.p("mod", _xmod(e)),
            e.p("op", _conv_name(e, to, op_, st, signed)),
            e.p("a", v),
            e.p("to", to),
        )

    x.append(
        e.impl_interface(
            e.v("wconv"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    *tm.const_type_arg(e, "wasm conversion", a(e, "argument"), "to"),
                    e.let(
                        "v",
                        unwrap_cve_m(
                            e,
                            try_er(
                                e,
                                _ssa(
                                    e,
                                    xx(e),
                                    loc(e),
                                    _xmod(e),
                                    cv_of(e, cve_code(e, a(e, "function")), cve_value(e, recv_of(e))),
                                ),
                                cve_t(e),
                            ),
                        ),
                    ),
                    e.let("st", cve_type(e, v)),
                    when(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("wrap")),
                            and_b(e, has(e, xx(e), st, "wint"), has(e, xx(e), to, "wint")),
                        ),
                        e.if_else(
                            e.eq(_wide(e, xx(e), st), _wide(e, xx(e), to)),
                            e.if_else(
                                e.mb.operator_lt(acc(e, xx(e), to, "wint", "bits"), cv_bits(e, st, "wint")),
                                _narrow(e, v, to),
                                _retag(e, v, to),
                            ),
                            e.if_else(
                                _wide(e, xx(e), st),
                                _narrow(e, conv_via("wrap", None), to),
                                _conv(e, _conv_name(e, to, "extend", st, acc(e, xx(e), st, "wint", "signed")), v, to),
                            ),
                        ),
                    ),
                    when(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("trunc")),
                            and_b(e, has(e, xx(e), st, "wfloat"), has(e, xx(e), to, "wint")),
                        ),
                        _narrow(e, conv_via("trunc", acc(e, xx(e), to, "wint", "signed")), to),
                    ),
                    when(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("to_float")),
                            and_b(e, has(e, xx(e), st, "wint"), has(e, xx(e), to, "wfloat")),
                        ),
                        _conv(e, _conv_name(e, to, "convert", st, acc(e, xx(e), st, "wint", "signed")), v, to),
                    ),
                    e.if_only(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("to_float")),
                            and_b(e, has(e, xx(e), st, "wfloat"), has(e, xx(e), to, "wfloat")),
                        ),
                        e.seq(
                            e.let("sb", cv_bits(e, st, "wfloat")),
                            e.let("tb", acc(e, xx(e), to, "wfloat", "bits")),
                            when(e.eq(e.v("sb"), e.v("tb")), _retag(e, v, to)),
                            when(
                                e.mb.operator_gt(e.v("sb"), e.v("tb")),
                                _conv(e, _conv_name(e, to, "demote", st, None), v, to),
                            ),
                            ret_m(e, _conv(e, _conv_name(e, to, "promote", st, None), v, to)),
                        ),
                    ),
                    e.ret(
                        err_cve(
                            e,
                            loc(e),
                            e.cat(
                                e.s("wasm: no conversion "),
                                in_(e, "op"),
                                e.s(" from "),
                                ty_desc(e, st),
                                e.s(" to "),
                                ty_desc(e, to),
                            ),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    tm.method_fields(e, x, "wt_int", "wconv", ["wrap", "to_float"])
    tm.method_fields(e, x, "wt_float", "wconv", ["trunc", "to_float"])


def _value_aspects(e, x, obj, size_expr, hash_stage):
    """Implements values.atz's `size_i`, `eq_i` and (when `hash_stage` is given) `hash_i` for a type object: eq
    stages the type's own `==`; hash stages a 32-bit hash of the value `cv`."""
    x.append(e.impl_interface(e.v(obj), e.fld(e.v("values"), "size_i"), e.p("size", size_expr)))
    x.append(
        e.impl_interface(
            e.v(obj),
            e.fld(e.v("values"), "eq_i"),
            e.p(
                "eq", const_eval_in(e, a(e, "xx"), a(e, "loc"), e.stage(e.eq(graft(e, a(e, "a")), graft(e, a(e, "b")))))
            ),
        )
    )
    if hash_stage is not None:
        x.append(e.impl_interface(e.v(obj), e.fld(e.v("values"), "hash_i"), e.p("hash", hash_stage)))


def _int_hash_body(e):
    """values.hash for ints: widened (or kept, at 64 bits) to i64 and SipHashed."""
    return e.seq(
        e.let("sh_i64", e.mb.as_(_int_ty(e, "i64"), e.mb.eval_type())),
        e.let("sh_i32", e.mb.as_(_int_ty(e, "i32"), e.mb.eval_type())),
        e.let("pi64", mk(e, "wt_ptr", e.p("pointee", e.v("sh_i64")))),
        e.if_else(
            e.eq(in_(e, "bits"), num(e, 64)),
            e.ret(_sip_hash(e, lambda x: x, e.p("size", e.int_of(16)))),
            e.ret(_sip_hash(e, lambda x: e.call(e.fld(x, "wrap"), e.lower(e.v("sh_i64"))), e.p("size", e.int_of(16)))),
        ),
    )


def _ptr_hash_body(e):
    """values.hash for pointers: the address as i64, SipHashed."""
    return e.seq(
        e.let("sh_i64", e.mb.as_(_int_ty(e, "i64"), e.mb.eval_type())),
        e.let("sh_i32", e.mb.as_(_int_ty(e, "i32"), e.mb.eval_type())),
        e.let("pi64", mk(e, "wt_ptr", e.p("pointee", e.v("sh_i64")))),
        e.ret(
            _sip_hash(
                e,
                lambda x: e.call(e.fld(e.mb.as_(x, e.lower(e.v("sh_i32"))), "wrap"), e.lower(e.v("sh_i64"))),
                e.p("size", e.int_of(16)),
            )
        ),
    )


# SipHash-1-3 (the hash aspect of ints and pointers): one 64-bit word under a 128-bit key. The key lives in the
# module's zeroed `siphash_key` block (an `alloc_dep`), so an app may seed it at startup; the function itself is the
# `siphash13_u64` dependency, defined once per module (the body is staged in the hash method, where types exist).
SIP_C = [(0x736F6D65, 0x70736575), (0x646F7261, 0x6E646F6D), (0x6C796765, 0x6E657261), (0x74656462, 0x79746573)]


def _sip_i64(e, v):
    return e.mb.as_(e.n(v), e.lower(e.v("sh_i64")))


def _sip_k(e, hi, lo):
    """A 64-bit constant from two 32-bit halves (host numbers are doubles)."""
    return e.mb.operator_or(e.mb.operator_shl(_sip_i64(e, hi), e.n(32)), _sip_i64(e, lo))


def _sip_rotl(e, x, n):
    return e.mb.operator_or(e.mb.operator_shl(x, e.n(n)), e.mb.operator_ushr(x, e.n(64 - n)))


def _sip_round(e):
    v = [e.v("v0"), e.v("v1"), e.v("v2"), e.v("v3")]
    add, xor = e.mb.operator_add, e.mb.operator_xor

    def s(i, expr):
        return e.mb.set(v[i], expr)

    return [
        s(0, add(v[0], v[1])),
        s(1, _sip_rotl(e, v[1], 13)),
        s(1, xor(v[1], v[0])),
        s(0, _sip_rotl(e, v[0], 32)),
        s(2, add(v[2], v[3])),
        s(3, _sip_rotl(e, v[3], 16)),
        s(3, xor(v[3], v[2])),
        s(0, add(v[0], v[3])),
        s(3, _sip_rotl(e, v[3], 21)),
        s(3, xor(v[3], v[0])),
        s(2, add(v[2], v[1])),
        s(1, _sip_rotl(e, v[1], 17)),
        s(1, xor(v[1], v[2])),
        s(2, _sip_rotl(e, v[2], 32)),
    ]


def _siphash_body(e):
    """siphash13_u64(m, k0, k1) -> i32: SipHash-1-3 of the 8-byte message `m`, low 32 bits of the 64-bit result."""
    xor = e.mb.operator_xor
    return e.mb.labeled(
        "fn",
        e.seq(
            e.let("v0", xor(e.v("k0"), _sip_k(e, *SIP_C[0]))),
            e.let("v1", xor(e.v("k1"), _sip_k(e, *SIP_C[1]))),
            e.let("v2", xor(e.v("k0"), _sip_k(e, *SIP_C[2]))),
            e.let("v3", xor(e.v("k1"), _sip_k(e, *SIP_C[3]))),
            e.mb.set(e.v("v3"), xor(e.v("v3"), e.v("m"))),
            *_sip_round(e),
            e.mb.set(e.v("v0"), xor(e.v("v0"), e.v("m"))),
            e.let("b", _sip_k(e, 0x08000000, 0)),
            e.mb.set(e.v("v3"), xor(e.v("v3"), e.v("b"))),
            *_sip_round(e),
            e.mb.set(e.v("v0"), xor(e.v("v0"), e.v("b"))),
            e.mb.set(e.v("v2"), xor(e.v("v2"), _sip_i64(e, 255))),
            *_sip_round(e),
            *_sip_round(e),
            *_sip_round(e),
            e.mb.return_to(
                "fn",
                e.call(
                    e.fld(xor(xor(e.v("v0"), e.v("v1")), xor(e.v("v2"), e.v("v3"))), "wrap"), e.lower(e.v("sh_i32"))
                ),
            ),
        ),
    )


def _sip_hash(e, to_i64, key_arg):
    """In a values.hash impl (host code): the argument `cv`, converted to i64 by `to_i64(x)`, hashed by the SipHash
    dependency under the module's key block; `key_arg` is the `alloc_dep` size/type field for that block."""

    def key(i):
        return e.mb.field(graft(e, e.v("keypc")), e.n(i))

    return try_er(
        e,
        e.mb.labeled(
            "h",
            e.seq(
                e.let("sipmod", _xmod_must(e)),
                e.let(
                    "siphash_t",
                    mk(
                        e,
                        "wt_fn",
                        e.p("params", e.list_new(ty(e), e.v("sh_i64"), e.v("sh_i64"), e.v("sh_i64"))),
                        e.p("ret", e.v("sh_i32")),
                    ),
                ),
                e.let(
                    "keyp",
                    hf_rec(
                        e,
                        "h_allocdep_call",
                        e.p("xx", a(e, "xx")),
                        e.p("loc", a(e, "loc")),
                        e.p("id", e.call_m(e.v("sipmod"), "sip_key_id", e.tup())),
                        e.p("name", e.s("siphash_key")),
                        key_arg,
                    ),
                ),
                # The key block's pointer as the cell type (a retag: the block is the module's).
                e.let(
                    "keyv",
                    unwrap_cve_t(
                        e,
                        try_er(
                            e,
                            _operand(
                                e,
                                a(e, "xx"),
                                a(e, "loc"),
                                _xmod_must(e),
                                mk(e, "wt_ptr", e.p("pointee", mk_arg(e, "wt_void", e.tup()))),
                                e.v("keyp"),
                            ),
                            cve_t(e),
                        ),
                    ),
                ),
                e.let(
                    "keypc",
                    hf_rec(
                        e,
                        "h_retag",
                        e.p("loc", a(e, "loc")),
                        e.p("mod", _xmod_must(e)),
                        e.p("cv", e.v("keyv")),
                        e.p("ty", e.v("pi64")),
                    ),
                ),
                e.let(
                    "args",
                    unwrap_cve_t(
                        e,
                        const_eval_in(
                            e, a(e, "xx"), a(e, "loc"), e.stage(e.tup(to_i64(graft(e, a(e, "cv"))), key(0), key(1)))
                        ),
                    ),
                ),
                e.mb.return_to(
                    "h",
                    hf_rec(
                        e,
                        "h_funcdep_call",
                        e.p("xx", a(e, "xx")),
                        e.p("loc", a(e, "loc")),
                        e.p("id", e.call_m(e.v("sipmod"), "sip_fn_id", e.tup())),
                        e.p("name", e.s("siphash13_u64")),
                        e.p("params", e.list_new(e.mb.types_string(), e.s("m"), e.s("k0"), e.s("k1"))),
                        e.p("ty", e.v("siphash_t")),
                        e.p("body", e.stage(_siphash_body(e))),
                        e.p("argument", e.v("args")),
                    ),
                ),
            ),
        ),
        cve_t(e),
    )


def _lty(e, obj, arg):
    return e.mb.as_(e.call(e.fld(e.v("k"), obj + "_new"), arg), ty(e))


def _wval_of(e, cve_tp):
    return reinterpret(e, cve_value(e, cve_tp), "wval")


def _wval_new(e, ty_, source_tag, ref):
    return mk(e, "wval", e.p("ty", ty_), e.p("source", e.call(e.lower_v("ws_" + source_tag), ref)))


def _wval_local(e, ty_, name):
    return _wval_new(e, ty_, "local", name)


def _wval_konst(e, ty_, text):
    return _wval_new(e, ty_, "konst", text)


def _wval_slot(e, ty_, name):
    return _wval_new(e, ty_, "slot", name)


def _wval_multi(e, ty_, parts):
    """A tuple value: its components, in order, as one value (wasm multi-value)."""
    return _wval_new(e, ty_, "multi", parts)


def _wv_flat(e, wval_tp):
    return e.call_m(wval_tp, "flat", e.tup())


def _fresh_val(e, mod, ty_):
    return hf_rec(e, "h_fresh_val", e.p("mod", mod), e.p("ty", ty_))


def _slot_val(e, mod, ty_):
    return hf_rec(e, "h_slot_val", e.p("mod", mod), e.p("ty", ty_))


def _store_to(e, loc_, out, val, target):
    return hf_rec(e, "h_store_to", e.p("loc", loc_), e.p("out", out), e.p("val", val), e.p("target", target))


def _setl_val(e, loc_, out, target):
    return hf_rec(e, "h_setl_val", e.p("loc", loc_), e.p("out", out), e.p("target", target))


def _names_of(e, val):
    return hf(e, "h_names", val)


def _zip(e, la, lb, va, vb, elem_t, *body_):
    """Iterates `la` and `lb` (of `elem_t` elements) in step: `va` and `vb` are the elements at the same index (lists
    have no index access, so the second list is keyed by position first)."""
    return e.seq(
        e.let("zm", e.map_new(str_(e), elem_t)),
        e.let("zi", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            lb,
            "zb",
            e.seq(
                e.call_m(e.v("zm"), "put", e.tup(to_str(e, e.fld(e.v("zi"), "v")), e.v("zb"))),
                e.incr(e.fld(e.v("zi"), "v")),
            ),
        ),
        e.let("zj", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            la,
            va,
            e.seq(
                e.let(vb, e.call_m(e.v("zm"), "get", to_str(e, e.fld(e.v("zj"), "v")))),
                *body_,
                e.incr(e.fld(e.v("zj"), "v")),
            ),
        ),
    )


def _reversed_names(e, names, var, *body_):
    """Runs `body_` with `var` bound to each of `names` (list<str>), last first."""
    return e.seq(
        e.let("rm", e.map_new(str_(e), str_(e))),
        count_let(e, "rn"),
        e.foreach(
            names,
            "rx",
            e.seq(
                e.call_m(e.v("rm"), "put", e.tup(to_str(e, e.fld(e.v("rn"), "v")), e.v("rx"))),
                e.incr(e.fld(e.v("rn"), "v")),
            ),
        ),
        e.let("ri", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            names,
            "_",
            e.seq(
                e.let(
                    var,
                    e.call_m(
                        e.v("rm"),
                        "get",
                        to_str(
                            e,
                            e.mb.operator_sub(
                                e.mb.operator_sub(e.fld(e.v("rn"), "v"), e.int_of(1)), e.fld(e.v("ri"), "v")
                            ),
                        ),
                    ),
                ),
                *body_,
                e.incr(e.fld(e.v("ri"), "v")),
            ),
        ),
    )


def _wv_mem(e, wval_tp):
    return e.call_m(wval_tp, "mem", e.tup())


def _wv_is_mem(e, wval_tp):
    return e.eq(e.call_m(wval_tp, "is_mem", e.tup()), num(e, 1))


def _wv_is_addr(e, wval_tp):
    return e.eq(e.call_m(wval_tp, "is_addr", e.tup()), num(e, 1))


def _wv_ty(e, wval_tp):
    return e.call_m(wval_tp, "ty", e.tup())


def _operand(e, xx_, loc_, mod, ty_, cv):
    return hf_rec(e, "h_operand", e.p("xx", xx_), e.p("loc", loc_), e.p("mod", mod), e.p("ty", ty_), e.p("cv", cv))


def _insts_new(e):
    return e.list_new(lt(e, "winst"))


def _loc_opt_t(e):
    return e.call(e.mb.types_option(), loc_t(e))


def _inst(e, loc_, variant, *fields):
    """An instruction at `loc_`, the expression it computes: its `;;@` annotation names that location's frame."""
    return _inst_at(e, e.opt_some(loc_t(e), loc_), variant, e.rec(*fields))


def _inst0(e, loc_, variant):
    return _inst_at(e, e.opt_some(loc_t(e), loc_), variant, e.tup())


def _inst_bare(e, variant, *fields):
    """A structural instruction (label, branch, block delimiter, dependency) with no location of its own."""
    return _inst_at(e, e.opt_none(loc_t(e)), variant, e.rec(*fields))


def _inst0_bare(e, variant):
    return _inst_at(e, e.opt_none(loc_t(e)), variant, e.tup())


def _inst_at(e, loc_opt, variant, arg):
    return mk(e, "winst", e.p("k", e.call(e.lower_v("wi_" + variant), arg)), e.p("loc", loc_opt))


def _append_code(e, out, code_tp):
    return hf_rec(e, "h_append", e.p("out", out), e.p("code", code_tp))


def _code_of(e, insts):
    return hf(e, "h_code", insts)


def _ssa(e, xx_, loc_, mod, cv):
    return hf_rec(e, "h_ssa", e.p("xx", xx_), e.p("loc", loc_), e.p("mod", mod), e.p("cv", cv))


def _is_wasm(e, xx_, cv):
    return hf_rec(e, "h_is_wasm", e.p("xx", xx_), e.p("cv", cv))


def _mod(e):
    return in_(e, "mod")


def _xmod(e, ret_inner=None):
    if ret_inner is None:
        ret_inner = e.mb.types_cve()
    return e.call_m(
        unwrap_m(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "wtarget"))), ret_inner),
        "mod",
        e.tup(),
    )


def _xmod_must(e):
    """The current wasm module from `arg.xx`, in a host function that throws its errors."""
    return e.call_m(
        _must(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "wtarget")))), "mod", e.tup()
    )


def _must(e, res):
    return e.match_of(res, "__r", None, e.p("ok", e.v("__r")), e.p("errs", e.mb.throw_(e.v("__r"))))


def _fresh(e, mod, ty_):
    return e.call_m(mod, "fresh", ty_)


def _store_inst(e, loc_, val, name):
    return _inst(e, loc_, "store", e.p("val", val), e.p("name", name))


def _load_inst(e, loc_, res, ty_, name):
    return _inst(e, loc_, "load", e.p("res", res), e.p("ty", ty_), e.p("name", name))


def _br_inst(e, name):
    return _inst_bare(e, "br", e.p("name", name))


def _ir_of(e, ty_):
    return e.call_m(outer(e), "ir", ty_)


def _p(e, key):
    return e.fld(e.v("p"), key)


def _ir_arg_xx(e):
    return e.call_m(e.v("arg"), "xx", e.tup())


def _ir_fn(e, xx_, ty_):
    return hf_rec(e, "h_ir", e.p("xx", xx_), e.p("ty", ty_))


def _binop_body(e, op_):
    return hf_rec(
        e,
        "h_binop",
        e.p("xx", xx(e)),
        e.p("loc", loc(e)),
        e.p("mod", _xmod(e)),
        e.p("ty", outer(e)),
        e.p("op", op_),
        e.p("a", a(e, "base")),
        e.p("b", a(e, "reference")),
        e.p("res", outer(e)),
    )


def _cmp_body(e, op_):
    return hf_rec(
        e,
        "h_cmp",
        e.p("xx", xx(e)),
        e.p("loc", loc(e)),
        e.p("mod", _xmod(e)),
        e.p("ty", outer(e)),
        e.p("op", op_),
        e.p("a", a(e, "base")),
        e.p("b", a(e, "reference")),
    )


def _signed_op(e, signed, unsigned):
    return e.if_else(in_(e, "signed"), e.dstr(signed), e.dstr(unsigned))


def _conv(e, op_, from_, to):
    return ok_cve(
        e, hf_rec(e, "h_conv", e.p("loc", loc(e)), e.p("mod", _xmod(e)), e.p("op", op_), e.p("a", from_), e.p("to", to))
    )


def _retag(e, cv, ty_):
    return ok_cve(e, hf_rec(e, "h_retag", e.p("loc", loc(e)), e.p("mod", _xmod(e)), e.p("cv", cv), e.p("ty", ty_)))


def _narrow(e, cv, ty_):
    return ok_cve(
        e,
        hf_rec(
            e, "h_narrow", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("mod", _xmod(e)), e.p("cv", cv), e.p("to", ty_)
        ),
    )


def _literal(e, ty_, text):
    return hf_rec(e, "h_literal", e.p("loc", loc(e)), e.p("ty", ty_), e.p("text", text))


def _conv_name(e, to, op_, from_, signed):
    """`signed`: expr or None."""
    parts = []
    parts.append(e.call_m(_xmod(e), "ir", to))
    parts.append(e.s("." + op_ + "_"))
    parts.append(e.call_m(_xmod(e), "ir", from_))
    if signed is not None:
        parts.append(e.if_else(signed, e.dstr("_s"), e.dstr("_u")))
    return e.cat(*parts)


def _set_impl(e, x, obj):
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_set",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", outer(e)),
                                e.p("self", a(e, "target")),
                                e.p("value", a(e, "value")),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )


def _bind_impl(e, x, obj):
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_bind(),
            e.p(
                "bind",
                body(
                    e,
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_store_new",
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p("mod", _xmod(e, br_t)),
                                    e.p("cv", a(e, "cv")),
                                ),
                                cve_t(e),
                            ),
                            br_t,
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    e.p("code", cve_code(e, e.v("r"))),
                                    e.p(
                                        "binding",
                                        mk(
                                            e,
                                            "wbinding",
                                            e.p("ty", _wv_ty(e, _wval_of(e, e.v("r")))),
                                            e.p("slot", _wval_of(e, e.v("r"))),
                                        ),
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def _binding_impl(e, x, obj, use_body, drop_body):
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_binding(),
            e.p("use", use_body),
            e.p("drop", drop_body),
            e.p("fork", outer(e)),
            e.p("merge", e.eresult_ok(e.mb.eval_binding(), outer(e))),
        )
    )


def _wide(e, xx_, typ):
    return e.eq(acc(e, xx_, typ, "wint", "bits"), num(e, 64))


def _if_branch_stmts(e, cv_var):
    valued = and_b(e, cve_has(e, e.v(cv_var)), _is_wasm(e, xx(e), e.v(cv_var)))
    return e.seq(
        e.if_only(
            and_b(
                e,
                cve_has(e, e.v(cv_var)),
                and_b(
                    e,
                    e.not_(_is_wasm(e, xx(e), e.v(cv_var))),
                    e.not_(hf_rec(e, "h_is_unit", e.p("xx", xx(e)), e.p("cv", e.v(cv_var)))),
                ),
            ),
            ret_m(e, err_cve(e, loc(e), "if branches must yield wasm values")),
        ),
        e.if_only(
            valued,
            e.seq(
                e.let("bv", unwrap_cve_m(e, try_er(e, _ssa(e, xx(e), loc(e), e.v("mod"), e.v(cv_var)), cve_t(e)))),
                e.if_only(
                    e.eq(e.fld(e.v("st"), "has"), num(e, 0)),
                    e.seq(
                        e.mb.set(e.fld(e.v("st"), "ty"), e.option_type_lowered_some(cve_type(e, e.v("bv")))),
                        e.mb.set(e.fld(e.v("st"), "has"), num(e, 1)),
                    ),
                ),
                _append_code(e, e.v("bo"), cve_code(e, e.v("bv"))),
                push(e, e.v("bo"), _inst(e, loc(e), "push", e.p("val", _wval_of(e, e.v("bv"))))),
            ),
        ),
        e.if_only(
            e.not_(valued),
            e.seq(
                _append_code(e, e.v("bo"), cve_code(e, e.v(cv_var))),
                e.if_only(e.not_(cve_ended(e, e.v(cv_var))), e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1))),
            ),
        ),
        e.if_only(e.not_(cve_ended(e, e.v(cv_var))), e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0))),
    )


def _arms_body(e, pre, branches, skip_last, prelude, else_is_some, else_prelude):
    """The target's `if` and `match`: one wasm `if … else … end` per branch, nested in the preceding branch's
    `else`; a value, when the arms yield one, is left in a fresh local. `pre` runs once `out` exists; `prelude(br)`
    binds `c0` (the condition code value) and `b` (the body code value) of branch `br`; `else_prelude` binds `b` for
    the else arm, present when `else_is_some`; when `skip_last`, the last branch is not emitted (the else arm stands
    for it)."""

    def not_skipped(counter):
        return e.not_(and_b(e, skip_last, e.eq(e.fld(e.v(counter), "v"), e.fld(e.v("nc"), "v"))))

    return body(
        e,
        e.let("mod", _mod(e)),
        e.let("out", _insts_new(e)),
        e.let("i1", _int_ty(e, "i1")),
        e.let(
            "st",
            e.rec(
                e.p("ended", e.int_of(1)),
                e.p("has", e.int_of(0)),
                e.p("novalue", e.int_of(0)),
                e.p("ty", e.option_type_lowered_none()),
            ),
        ),
        *pre,
        count_let(e, "nc"),
        count_loop(e, "nc", branches),
        e.let("bi", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            branches,
            "br",
            e.seq(
                e.incr(e.fld(e.v("bi"), "v")),
                e.if_only(
                    not_skipped("bi"),
                    e.seq(
                        *prelude("br"),
                        e.let(
                            "c",
                            unwrap_cve_m(
                                e,
                                try_er(e, _operand(e, xx(e), loc(e), e.v("mod"), e.v("i1"), e.v("c0")), cve_t(e)),
                            ),
                        ),
                        _append_code(e, e.v("out"), cve_code(e, e.v("c"))),
                        e.let("bo", _insts_new(e)),
                        _if_branch_stmts(e, "b"),
                        push(
                            e,
                            e.v("out"),
                            _inst(
                                e, loc(e), "if", e.p("cond", _wval_of(e, e.v("c"))), e.p("ty", e.fld(e.v("st"), "ty"))
                            ),
                        ),
                        e.foreach(e.v("bo"), "i", push(e, e.v("out"), e.v("i"))),
                        e.if_only(
                            or_b(e, e.mb.operator_lt(e.fld(e.v("bi"), "v"), e.fld(e.v("nc"), "v")), else_is_some),
                            push(e, e.v("out"), _inst0_bare(e, "else")),
                        ),
                    ),
                ),
            ),
        ),
        e.if_only(
            else_is_some,
            e.seq(
                e.let("bo", _insts_new(e)),
                *else_prelude(),
                _if_branch_stmts(e, "b"),
                e.foreach(e.v("bo"), "i", push(e, e.v("out"), e.v("i"))),
            ),
        ),
        e.if_only(
            e.not_(else_is_some),
            e.seq(
                e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0)),
                e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 1)), e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1))),
            ),
        ),
        e.let("ei", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            branches,
            "_",
            e.seq(
                e.incr(e.fld(e.v("ei"), "v")), e.if_only(not_skipped("ei"), push(e, e.v("out"), _inst0_bare(e, "end")))
            ),
        ),
        e.if_only(
            e.eq(e.fld(e.v("st"), "ended"), num(e, 1)),
            ret_m(e, ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
        ),
        e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 0)), ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out")))))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "novalue"), num(e, 1)),
            ret_m(e, err_cve(e, loc(e), "if: some branches yield a value and some do not")),
        ),
        e.let("rv", _fresh_val(e, e.v("mod"), e.fld(e.v("st"), "ty", "value"))),
        _setl_val(e, loc(e), e.v("out"), e.v("rv")),
        e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), e.v("rv")))),
    )


def _if_hook(e):
    return _arms_body(
        e,
        [],
        a(e, "conditions"),
        dfalse(e),
        lambda br: [e.let("c0", e.fld(e.v(br), "condition")), e.let("b", e.fld(e.v(br), "body"))],
        e.fld(a(e, "else"), "is_some"),
        lambda: [e.let("b", e.fld(a(e, "else"), "value"))],
    )


def _match_hook(e):
    """`match`: the base value's code runs once, then each case's test (an i1 code value from the type's
    `eval.aspect_union`) guards its body, which already binds the payload. The else arm is the fallback or, without
    one, the last case (the match is exhaustive, so it needs no test)."""
    base = e.v("base")
    fb_some = e.fld(a(e, "fallback"), "is_some")
    pre = [
        e.let("base", a(e, "base")),
        e.if_only(e.not_(cve_has(e, base)), ret_m(e, err_cve(e, loc(e), "match: the value has no value"))),
        _append_code(e, e.v("out"), cve_code(e, base)),
        # The else arm's body: the fallback's, or the last case's.
        e.let("elseb", e.map_new(str_(e), e.mb.types_cve())),
        count_let(e, "nn"),
        count_loop(e, "nn", a(e, "cases")),
        e.let("ai", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            a(e, "cases"),
            "cs",
            e.seq(
                e.incr(e.fld(e.v("ai"), "v")),
                e.if_only(
                    and_b(e, e.not_(fb_some), e.eq(e.fld(e.v("ai"), "v"), e.fld(e.v("nn"), "v"))),
                    e.call_m(e.v("elseb"), "put", e.tup(e.s("else"), e.fld(e.v("cs"), "body"))),
                ),
            ),
        ),
        e.if_only(fb_some, e.call_m(e.v("elseb"), "put", e.tup(e.s("else"), e.fld(a(e, "fallback"), "value")))),
    ]
    return _arms_body(
        e,
        pre,
        a(e, "cases"),
        e.not_(fb_some),
        lambda br: [e.let("c0", e.fld(e.v(br), "test")), e.let("b", e.fld(e.v(br), "body"))],
        e.not_(dfalse(e)),
        lambda: [e.let("b", e.call_m(e.v("elseb"), "get", e.s("else")))],
    )


def _tuple_type(e, x):
    """`wt_tuple{elems}`: wasm multi-value. A value is its components in order (`ws_multi`), so it is pushed as
    several operands, bound to one local per component, passed as several parameters and returned as several
    results. A host tuple of castable values casts to it; `.0`, `.1`, … are the components; dropping drops them."""
    no = no_cast_to(e)

    def elems_of(typ):
        return acc(e, xx(e), typ, "wtuple", "elems")

    def same_elems(other):
        return body(
            e,
            e.if_only(e.not_(has(e, xx(e), other, "wtuple")), ret_m(e, dfalse(e))),
            count_let(e, "n1"),
            count_loop(e, "n1", in_(e, "elems")),
            count_let(e, "n2"),
            count_loop(e, "n2", elems_of(other)),
            e.if_only(e.not_(e.eq(e.fld(e.v("n1"), "v"), e.fld(e.v("n2"), "v"))), ret_m(e, dfalse(e))),
            _zip(
                e,
                in_(e, "elems"),
                elems_of(other),
                "ea",
                "eb",
                ty(e),
                e.if_only(e.not_(is_equal(e, xx(e), e.v("ea"), e.v("eb"))), ret_m(e, dfalse(e))),
            ),
            e.ret(e.not_(dfalse(e))),
        )

    self_type(
        e,
        x,
        "wt_tuple",
        body(
            e,
            e.let("ds", e.list_new(str_(e))),
            e.foreach(in_(e, "elems"), "et", push(e, e.v("ds"), bim0(e, ty(e), "desc", e.v("et")))),
            e.ret(e.cat(e.s("("), e.join(e.v("ds"), ", "), e.s(")"))),
        ),
        e.aspect_dispatch(
            lv(e, "wtype_id"),
            asp_id(e, "initial_bind"),
            asp_id(e, "bind"),
            asp_id(e, "set"),
            asp_id(e, "field"),
            e.mb.eval_aspect_drop_dynamic_id(),
            lv(e, "wtuple_id"),
        ),
        body(
            e,
            e.if_only(has(e, xx(e), src_type(e), "wtuple"), ret_m(e, same_elems(src_type(e)))),
            e.let("tk", lookup(e, xx(e), src_type(e), asp_iface(e, "tuple"))),
            e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, dfalse(e))),
            e.let("ets", bim0(e, asp_iface(e, "tuple"), "element_types", e.fld(e.v("tk"), "value"))),
            count_let(e, "n1"),
            count_loop(e, "n1", in_(e, "elems")),
            count_let(e, "n2"),
            count_loop(e, "n2", e.v("ets")),
            e.if_only(e.not_(e.eq(e.fld(e.v("n1"), "v"), e.fld(e.v("n2"), "v"))), ret_m(e, dfalse(e))),
            _zip(
                e,
                in_(e, "elems"),
                e.v("ets"),
                "ea",
                "eb",
                ty(e),
                e.if_only(e.not_(type_can_cast_from(e, xx(e), loc(e), e.v("ea"), e.v("eb"))), ret_m(e, dfalse(e))),
            ),
            e.ret(e.not_(dfalse(e))),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(has(e, xx(e), e.v("st"), "wtuple"), ret_m(e, _retag(e, a(e, "cv"), outer(e)))),
            # A host tuple: each element is an operand of its component type; the components form the value.
            e.let("tk", lookup(e, xx(e), e.v("st"), asp_iface(e, "tuple"))),
            e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, err_cve(e, loc(e), "cannot convert to a tuple"))),
            e.let("ecs", e.list_new(e.mb.types_cve())),
            e.foreach(
                bim(
                    e,
                    asp_iface(e, "tuple"),
                    "take_elements",
                    e.fld(e.v("tk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
                "er",
                push(e, e.v("ecs"), unwrap_cve_m(e, e.v("er"))),
            ),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            e.let("parts", e.list_new(lt(e, "wval"))),
            _zip(
                e,
                e.v("ecs"),
                in_(e, "elems"),
                "ec",
                "et",
                ty(e),
                e.let(
                    "v",
                    unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), e.v("et"), e.v("ec")), cve_t(e))),
                ),
                _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                push(e, e.v("parts"), _wval_of(e, e.v("v"))),
            ),
            e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _wval_multi(e, outer(e), e.v("parts"))))),
        ),
        no,
        cast_to_panic(e),
        same_elems(a(e, "other")),
    )
    x.append(
        e.impl_interface(
            e.v("wt_tuple"),
            t(e, "wtype"),
            e.p(
                "ir",
                e.seq(
                    e.let("irs", e.list_new(str_(e))),
                    e.foreach(in_(e, "elems"), "et", push(e, e.v("irs"), _ir_fn(e, _ir_arg_xx(e), e.v("et")))),
                    e.ret(e.join(e.v("irs"), " ")),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("wt_tuple"), t(e, "wtuple"), e.p("elems", in_(e, "elems"))))
    # A parameter: the flat slots, shaped by the parameter's type.
    x.append(
        e.impl_interface(
            e.v("wt_tuple"),
            e.mb.eval_aspect_initial_bind(),
            e.p(
                "initial_bind",
                e.seq(
                    e.let("ps", e.call(e.mb.must_reinterpret(), e.tup(a(e, "slot"), lt(e, "wparam")))),
                    e.let("pty", e.call_m(e.v("ps"), "ty", e.tup())),
                    e.ret(
                        e.eresult_ok(
                            e.mb.eval_binding(),
                            mk(
                                e,
                                "wbinding",
                                e.p("ty", e.v("pty")),
                                e.p(
                                    "slot",
                                    hf_rec(
                                        e,
                                        "h_slots_val",
                                        e.p("xx", xx(e)),
                                        e.p("ty", e.v("pty")),
                                        e.p("slots", e.call_m(e.v("ps"), "slots", e.tup())),
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    _bind_impl(e, x, "wt_tuple")
    _set_impl(e, x, "wt_tuple")
    x.append(
        e.impl_interface(
            e.v("wt_tuple"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let("ik", lookup(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_int())),
                    e.if_only(
                        e.not_(e.fld(e.v("ik"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "tuple: the component index must be a constant integer")),
                    ),
                    e.let(
                        "k", bim(e, e.mb.eval_aspect_int(), "get", e.fld(e.v("ik"), "value"), cve_value(e, a(e, "key")))
                    ),
                    e.let("ki", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.match_of(
                            e.call_m(_wval_of(e, a(e, "value")), "source", e.tup()),
                            "s",
                            e.list_new(lt(e, "wval")),
                            e.p("multi", e.v("s")),
                        ),
                        "q",
                        e.seq(
                            e.if_only(
                                e.eq(e.fld(e.v("ki"), "v"), e.v("k")),
                                ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "value")), e.v("q")))),
                            ),
                            e.incr(e.fld(e.v("ki"), "v")),
                        ),
                    ),
                    e.ret(err_cve(e, loc(e), e.cat(e.s("tuple has no component "), to_str(e, e.v("k"))))),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p(
                "keys",
                e.seq(
                    e.let("ks", e.list_new(e.mb.types_constkey())),
                    e.let("ki", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        in_(e, "elems"),
                        "_",
                        e.seq(
                            push(e, e.v("ks"), e.mb.as_(to_str(e, e.fld(e.v("ki"), "v")), e.mb.types_constkey())),
                            e.incr(e.fld(e.v("ki"), "v")),
                        ),
                    ),
                    e.ret(e.v("ks")),
                ),
            ),
        )
    )
    # Dropping a tuple drops its components.
    x.append(
        e.impl_interface(
            e.v("wt_tuple"),
            e.mb.eval_aspect_drop_dynamic(),
            e.p(
                "drop",
                body(
                    e,
                    e.let("codes", e.list_new(code_t(e))),
                    e.foreach(
                        e.match_of(
                            e.call_m(_wval_of(e, a(e, "cv")), "source", e.tup()),
                            "s",
                            e.list_new(lt(e, "wval")),
                            e.p("multi", e.v("s")),
                        ),
                        "q",
                        push(
                            e,
                            e.v("codes"),
                            unwrap_m(
                                e,
                                e.call(
                                    e.mb.eval_drop_value(),
                                    e.rec(
                                        e.p("xx", xx(e)),
                                        e.p("loc", loc(e)),
                                        e.p("cv", cv_of(e, code_none(e, loc(e)), e.v("q"))),
                                    ),
                                ),
                                code_t(e),
                            ),
                        ),
                    ),
                    e.ret(e.eresult_ok(code_t(e), unwrap_m(e, _codes_seq(e, e.v("codes")), code_t(e)))),
                ),
            ),
        )
    )


def _codes_seq(e, codes_list):
    """The target's sequence of a host list of codes (an eresult(code))."""
    return bim(
        e,
        e.mb.eval_target(),
        "seq",
        e.fld(xx(e), "target"),
        e.rec(e.p("loc", loc(e)), e.p("entries", codes_list)),
    )


def _val_shape_impls(e, x):
    """The multi-value helpers: fresh locals or slots shaped like a type (a tuple gets one per component, nested),
    the flattened component types of a type, the flattened local names of a value, and stores into a shaped target
    (component-wise, `setl` last first since the components sit on the stack in order)."""
    for name, kind, make in [("h_fresh_val", "fresh", _wval_local), ("h_slot_val", "slot", _wval_slot)]:
        fn_impl(
            e,
            x,
            name,
            body(
                e,
                e.let("xq", e.call_m(a(e, "mod"), "xx", e.tup())),
                e.if_only(
                    has(e, e.v("xq"), a(e, "ty"), "wtuple"),
                    e.seq(
                        e.let("parts", e.list_new(lt(e, "wval"))),
                        e.foreach(
                            acc(e, e.v("xq"), a(e, "ty"), "wtuple", "elems"),
                            "et",
                            push(e, e.v("parts"), hf_rec(e, name, e.p("mod", a(e, "mod")), e.p("ty", e.v("et")))),
                        ),
                        ret_m(e, _wval_multi(e, a(e, "ty"), e.v("parts"))),
                    ),
                ),
                e.ret(make(e, a(e, "ty"), e.call_m(a(e, "mod"), kind, a(e, "ty")))),
            ),
        )
    fn_impl(
        e,
        x,
        "h_flat_types",
        body(
            e,
            e.let("fl", e.list_new(ty(e))),
            e.if_only(
                has(e, a(e, "xx"), a(e, "ty"), "wtuple"),
                e.seq(
                    e.foreach(
                        acc(e, a(e, "xx"), a(e, "ty"), "wtuple", "elems"),
                        "et",
                        e.foreach(
                            hf_rec(e, "h_flat_types", e.p("xx", a(e, "xx")), e.p("ty", e.v("et"))),
                            "ft",
                            push(e, e.v("fl"), e.v("ft")),
                        ),
                    ),
                    ret_m(e, e.v("fl")),
                ),
            ),
            push(e, e.v("fl"), a(e, "ty")),
            e.ret(e.v("fl")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_names",
        body(
            e,
            e.let("ns", e.list_new(str_(e))),
            e.foreach(
                _wv_flat(e, e.v("arg")),
                "q",
                push(
                    e,
                    e.v("ns"),
                    e.match_of(
                        e.call_m(e.v("q"), "source", e.tup()),
                        "s",
                        e.mb.panic(e.s("wasm: value without a local name")),
                        e.p("local", e.v("s")),
                        e.p("slot", e.v("s")),
                    ),
                ),
            ),
            e.ret(e.v("ns")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_slots_val",
        body(
            e,
            # The flat slot names are consumed in order; a tuple component takes as many as its flattened types.
            e.let("sm", e.map_new(str_(e), str_(e))),
            count_let(e, "sn"),
            e.foreach(
                a(e, "slots"),
                "sx",
                e.seq(
                    e.call_m(e.v("sm"), "put", e.tup(to_str(e, e.fld(e.v("sn"), "v")), e.v("sx"))),
                    e.incr(e.fld(e.v("sn"), "v")),
                ),
            ),
            e.if_only(
                has(e, a(e, "xx"), a(e, "ty"), "wtuple"),
                e.seq(
                    e.let("parts", e.list_new(lt(e, "wval"))),
                    e.let("si", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        acc(e, a(e, "xx"), a(e, "ty"), "wtuple", "elems"),
                        "et",
                        e.seq(
                            e.let("sub", e.list_new(str_(e))),
                            e.foreach(
                                hf_rec(e, "h_flat_types", e.p("xx", a(e, "xx")), e.p("ty", e.v("et"))),
                                "_",
                                e.seq(
                                    push(e, e.v("sub"), e.call_m(e.v("sm"), "get", to_str(e, e.fld(e.v("si"), "v")))),
                                    e.incr(e.fld(e.v("si"), "v")),
                                ),
                            ),
                            push(
                                e,
                                e.v("parts"),
                                hf_rec(
                                    e,
                                    "h_slots_val",
                                    e.p("xx", a(e, "xx")),
                                    e.p("ty", e.v("et")),
                                    e.p("slots", e.v("sub")),
                                ),
                            ),
                        ),
                    ),
                    ret_m(e, _wval_multi(e, a(e, "ty"), e.v("parts"))),
                ),
            ),
            e.foreach(a(e, "slots"), "s0", ret_m(e, _wval_slot(e, a(e, "ty"), e.v("s0")))),
            e.mb.panic(e.s("wasm: no slot for a value")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_store_to",
        _zip(
            e,
            _wv_flat(e, a(e, "val")),
            _wv_flat(e, a(e, "target")),
            "vq",
            "tq",
            lt(e, "wval"),
            push(e, a(e, "out"), _store_inst(e, loc(e), e.v("vq"), _wv_mem(e, e.v("tq")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_setl_val",
        _reversed_names(
            e,
            _names_of(e, a(e, "target")),
            "sn",
            push(e, a(e, "out"), _inst(e, loc(e), "setl", e.p("name", e.v("sn")))),
        ),
    )


# The named unsafe conversions (const functions `{value, to}`), exported beside the type factories.
CONV_NAMES = ["ptr_cast", "ptr_to_int", "int_to_ptr"]

WGFN_KINDS = [
    "import_fn",
    "func_fn",
    "export_fn",
    "data_fn",
    "cstr_fn",
    "alloc_fn",
    "loop_fn",
    "memory_grow_fn",
    "memory_copy_fn",
    "memory_size_fn",
    "memory_fill_fn",
]


def _wgfn_kind(kind):
    return WGFN_KINDS.index(kind)


def _wgfn_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _wgfn_kind(kind)))


def _wgfn_staged(e, staged):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(staged)))


def _wgfn_global_t(e, base):
    return mk(e, "wt_global", e.p("base", base))


def _wgfn_field(e, key):
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(key)))


def _wgfn_mod(e):
    return e.call_m(graft(e, e.v("modcv")), "m", e.tup())


def _data_fn_body(e):
    return e.seq(
        e.let("elemcv", _wgfn_field(e, "elem")),
        e.let("elem", _const_type_of(e, "elemcv", "wasm data elem")),
        e.let("is_ptr", has(e, xx(e), e.v("elem"), "wptr")),
        e.if_only(
            e.not_(or_b(e, e.v("is_ptr"), has(e, xx(e), e.v("elem"), "wint"))),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(e.s("wasm data elem must be an integer or pointer type, not "), ty_desc(e, e.v("elem"))),
                ),
            ),
        ),
        e.let(
            "width",
            e.if_else(
                e.v("is_ptr"),
                e.int_of(4),
                e.mb.operator_div(
                    e.mb.operator_add(acc(e, xx(e), e.v("elem"), "wint", "bits"), e.int_of(7)), e.int_of(8)
                ),
            ),
        ),
        e.let(
            "min",
            e.if_else(e.v("is_ptr"), e.mb.as_(e.n(0), e.types_double()), acc(e, xx(e), e.v("elem"), "wint", "min")),
        ),
        e.let(
            "max",
            e.if_else(
                e.v("is_ptr"), e.mb.as_(e.n(4294967295.0), e.types_double()), acc(e, xx(e), e.v("elem"), "wint", "max")
            ),
        ),
        e.let("valuescv", _wgfn_field(e, "values")),
        e.let("vtk", lookup(e, xx(e), cve_type(e, e.v("valuescv")), asp_iface(e, "tuple"))),
        e.if_only(
            e.not_(e.fld(e.v("vtk"), "is_some")), ret_m(e, err_cve(e, loc(e), "wasm data values must be a tuple"))
        ),
        e.let("accs", e.map_new(str_(e), cve_t(e))),
        e.call_m(e.v("accs"), "put", e.tup(e.s("0"), _wgfn_staged(e, e.list_new(int_t(e))))),
        e.let("fi", e.rec(e.p("i", e.int_of(0)))),
        e.foreach(
            bim(
                e,
                asp_iface(e, "tuple"),
                "take_elements",
                e.fld(e.v("vtk"), "value"),
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("valuescv")))),
            ),
            "er",
            e.seq(
                e.let("ecv", unwrap_cve_m(e, e.v("er"))),
                e.let("ety", cve_type(e, e.v("ecv"))),
                e.let("is_ref", has(e, xx(e), e.v("ety"), "wgtype_m")),
                e.if_only(
                    and_b(
                        e, e.v("is_ref"), e.not_(has(e, xx(e), acc(e, xx(e), e.v("ety"), "wgtype_m", "base"), "wptr"))
                    ),
                    ret_m(e, err_cve(e, loc(e), "wasm data values may only reference data pointers")),
                ),
                e.if_only(
                    and_b(e, e.v("is_ref"), e.not_(e.eq(e.v("width"), num(e, 4)))),
                    ret_m(e, err_cve(e, loc(e), "wasm data pointer values need a 32 bit elem")),
                ),
                e.if_only(
                    and_b(e, e.not_(e.v("is_ref")), e.not_(is_const(e, xx(e), e.v("ety")))),
                    ret_m(e, err_cve(e, loc(e), "wasm data values must be integers or data pointers")),
                ),
                e.let(
                    "valuecv",
                    e.if_else(
                        e.v("is_ref"),
                        _wgfn_staged(
                            e,
                            e.mb.as_(
                                e.call_m(
                                    _wgfn_mod(e),
                                    "addr",
                                    e.call(e.mb.must_reinterpret(), e.tup(graft(e, e.v("ecv")), str_(e))),
                                ),
                                e.types_double(),
                            ),
                        ),
                        _wgfn_staged(e, e.mb.as_(graft(e, e.v("ecv")), e.types_double())),
                    ),
                ),
                e.let("k0", to_str(e, e.fld(e.v("fi"), "i"))),
                e.incr(e.fld(e.v("fi"), "i")),
                e.call_m(
                    e.v("accs"),
                    "put",
                    e.tup(
                        to_str(e, e.fld(e.v("fi"), "i")),
                        _wgfn_staged(
                            e,
                            e.call_m(
                                _wgfn_mod(e),
                                "data_push",
                                e.rec(
                                    e.p("bytes", graft(e, e.call_m(e.v("accs"), "get", e.v("k0")))),
                                    e.p("width", e.lower(e.v("width"))),
                                    e.p("min", e.lower(e.v("min"))),
                                    e.p("max", e.lower(e.v("max"))),
                                    e.p("value", graft(e, e.v("valuecv"))),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        e.let("namecv", _wgfn_field(e, "name")),
        e.let(
            "refcv",
            _wgfn_staged(
                e,
                e.call_m(
                    _wgfn_mod(e),
                    "data",
                    e.rec(
                        e.p("name", graft(e, e.v("namecv"))),
                        e.p("bytes", graft(e, e.call_m(e.v("accs"), "get", to_str(e, e.fld(e.v("fi"), "i"))))),
                    ),
                ),
            ),
        ),
        ret_m(e, tag_value(e, e.v("refcv"), _wgfn_global_t(e, mk(e, "wt_ptr", e.p("pointee", e.v("elem")))))),
    )


def _alloc_fn_body(e):
    return e.seq(
        e.let("sizecv", _wgfn_staged(e, graft(e, _wgfn_field(e, "size")))),
        e.if_only(
            or_b(e, is_runtime(e, e.v("sizecv")), e.not_(is_const(e, xx(e), cve_type(e, e.v("sizecv"))))),
            ret_m(e, err_cve(e, loc(e), "wasm alloc size must be a constant integer")),
        ),
        e.let(
            "size",
            e.call(
                e.eval_builtin("const_numeric_to_double"),
                e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, e.v("sizecv")))),
            ),
        ),
        e.if_only(
            or_b(
                e,
                e.not_(e.eq(e.mb.as_(e.mb.as_(e.v("size"), int_t(e)), e.types_double()), e.v("size"))),
                e.mb.operator_lt(e.v("size"), num(e, 0)),
            ),
            ret_m(e, err_cve(e, loc(e), "wasm alloc size must be a non-negative integer")),
        ),
        e.let("namecv", _wgfn_field(e, "name")),
        e.let(
            "refcv",
            _wgfn_staged(
                e,
                e.call_m(
                    _wgfn_mod(e),
                    "alloc",
                    e.rec(e.p("name", graft(e, e.v("namecv"))), e.p("size", e.lower(e.mb.as_(e.v("size"), int_t(e))))),
                ),
            ),
        ),
        ret_m(
            e,
            tag_value(
                e, e.v("refcv"), _wgfn_global_t(e, mk(e, "wt_ptr", e.p("pointee", mk_arg(e, "wt_void", e.tup()))))
            ),
        ),
    )


def _const_type_of(e, cv_var, what):
    return e.seq(
        e.let("tk", lookup(e, xx(e), cve_type(e, e.v(cv_var)), asp_iface(e, "type"))),
        e.if_only(
            or_b(e, is_runtime(e, e.v(cv_var)), e.not_(e.fld(e.v("tk"), "is_some"))),
            ret_m(e, err_cve(e, loc(e), what + " must be a constant type")),
        ),
        e.ret(bim(e, asp_iface(e, "type"), "type", e.fld(e.v("tk"), "value"), cve_value(e, e.v(cv_var)))),
    )


def _rs(e, method_, arg):
    return e.call_m(e.v("r"), method_, arg)


def _annotation(e, frame):
    """binaryen's source location annotation for `frame`: line = frame + 1 (the map's zero-based line is the frame)."""
    return e.cat(e.s(";;@ frames.json:"), to_str(e, e.mb.operator_add(frame, e.int_of(1))), e.s(":0"))


def _rs0(e, method_):
    return e.call_m(e.v("r"), method_, e.tup())


def _rs_line(e, delta, *parts):
    return _rs(e, "line", e.rec(e.p("delta", e.int_of(delta)), e.p("text", e.cat(*parts))))


def _rs_ops(e, *ops):
    return _rs(e, "ops", e.list_new(lt(e, "wval"), *ops))


def _vmethod(e, x, obj, name, arg_type, body_):
    x.append(e.method_impl(e.v(obj), name, arg_type, e.option_type_none(), e.stage(body_)))


def _pend_active(e, pend_tp):
    return e.eq(e.call_m(pend_tp, "active", e.tup()), num(e, 1))


def _pend_pos(e, pend_tp):
    return e.call_m(pend_tp, "pos", e.tup())


def _region_of(e, depth):
    return e.call_m(outer(e), "region_of", depth)


def _def_render_state(e, x):
    def_obj(e, x, "wuse", "wasm local use count", e.rec(e.p("name", str_(e)), e.p("n", int_t(e))))
    def_obj(
        e,
        x,
        "wpend",
        "wasm deferred local.set",
        e.rec(e.p("name", str_(e)), e.p("pos", int_t(e)), e.p("at", int_t(e)), e.p("active", int_t(e))),
    )
    def_obj(
        e,
        x,
        "wregion",
        "wasm structured region",
        e.rec(e.p("depth", int_t(e)), e.p("start", int_t(e)), e.p("valued", bool_t(e)), e.p("closed", int_t(e))),
    )
    def_obj(
        e,
        x,
        "wrs",
        "wasm render state",
        e.rec(
            e.p("mod", _wmod_t(e)),
            e.p("out", e.list_type(str_(e))),
            e.p("used", e.list_type(str_(e))),
            e.p("uses", e.list_type(t(e, "wuse"))),
            e.p("pn", e.list_type(t(e, "wpend"))),
            e.p("sets", e.list_type(t(e, "wblock"))),
            e.p("blocks", e.list_type(t(e, "wblock"))),
            e.p("regions", e.list_type(t(e, "wregion"))),
            e.p("n", int_t(e)),
            e.p("h", int_t(e)),
            e.p("depth", int_t(e)),
            # The location of the instruction being rendered: every line it emits is annotated with its frame.
            e.p("cur", _loc_opt_t(e)),
        ),
    )
    for vo in ["wuse", "wpend", "wregion", "wrs"]:
        def_iface(e, x, vo + "_m")
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))
    accessor(e, x, "wuse", "name", str_(e))
    accessor(e, x, "wuse", "n", int_t(e))
    _vmethod(e, x, "wuse", "inc", e.tup(), e.incr(in_(e, "n")))
    _vmethod(e, x, "wrs", "at", _loc_opt_t(e), e.mb.set(in_(e, "cur"), e.v("arg")))
    accessor(e, x, "wpend", "name", str_(e))
    accessor(e, x, "wpend", "pos", int_t(e))
    accessor(e, x, "wpend", "at", int_t(e))
    accessor(e, x, "wpend", "active", int_t(e))
    _vmethod(e, x, "wpend", "set_pos", int_t(e), e.mb.set(in_(e, "pos"), e.v("arg")))
    _vmethod(e, x, "wpend", "set_active", int_t(e), e.mb.set(in_(e, "active"), e.v("arg")))
    accessor(e, x, "wregion", "depth", int_t(e))
    accessor(e, x, "wregion", "start", int_t(e))
    accessor(e, x, "wregion", "valued", bool_t(e))
    accessor(e, x, "wregion", "closed", int_t(e))
    _vmethod(e, x, "wregion", "set_start", int_t(e), e.mb.set(in_(e, "start"), e.v("arg")))
    _vmethod(e, x, "wregion", "set_closed", e.tup(), e.mb.set(in_(e, "closed"), e.int_of(1)))
    _vmethod(
        e,
        x,
        "wrs",
        "add_use",
        str_(e),
        push(e, in_(e, "uses"), mk(e, "wuse", e.p("name", e.v("arg")), e.p("n", e.int_of(0)))),
    )
    for find in [["use_of", "uses", "wuse", "name"]]:
        method(
            e,
            x,
            "wrs",
            find[0],
            str_(e),
            t(e, find[2]),
            e.seq(
                e.let("hit", e.list_new(lt(e, find[2]))),
                e.foreach(
                    in_(e, find[1]),
                    "q",
                    e.if_only(e.eq(e.call_m(e.v("q"), find[3], e.tup()), e.v("arg")), push(e, e.v("hit"), e.v("q"))),
                ),
                e.foreach(e.v("hit"), "q", e.ret(e.v("q"))),
                e.mb.panic(e.cat(e.s("wasm: no " + find[2] + " entry for "), e.v("arg"))),
            ),
        )
    method(
        e,
        x,
        "wrs",
        "region_of",
        int_t(e),
        t(e, "wregion"),
        e.seq(
            e.let("hit", e.list_new(lt(e, "wregion"))),
            e.foreach(
                in_(e, "regions"),
                "q",
                e.if_only(
                    and_b(
                        e,
                        e.eq(e.call_m(e.v("q"), "depth", e.tup()), e.v("arg")),
                        e.eq(e.call_m(e.v("q"), "closed", e.tup()), num(e, 0)),
                    ),
                    push(e, e.v("hit"), e.v("q")),
                ),
            ),
            e.foreach(e.v("hit"), "q", e.ret(e.v("q"))),
            e.mb.panic(e.cat(e.s("wasm: no open region at depth "), to_str(e, e.v("arg")))),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "line",
        e.rec(e.p("delta", int_t(e)), e.p("text", str_(e))),
        e.seq(
            # The annotation is a line of its own (binaryen reads `;;@ file:line:col` before an instruction), so it
            # counts in `n`, the index the pending local.sets are placed by.
            e.if_only(
                e.fld(in_(e, "cur"), "is_some"),
                e.seq(
                    push(
                        e,
                        in_(e, "out"),
                        _annotation(e, e.call_m(in_(e, "mod"), "frame", e.fld(in_(e, "cur"), "value"))),
                    ),
                    e.incr(in_(e, "n")),
                ),
            ),
            push(e, in_(e, "out"), a(e, "text")),
            e.incr(in_(e, "n")),
            e.mb.set(in_(e, "h"), e.mb.operator_add(in_(e, "h"), a(e, "delta"))),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "flush_one",
        t(e, "wpend"),
        e.seq(
            e.let("fpos", _pend_pos(e, e.v("arg"))),
            push(
                e,
                in_(e, "sets"),
                mk(
                    e,
                    "wblock",
                    e.p("at", e.call_m(e.v("arg"), "at", e.tup())),
                    e.p("name", e.cat(e.s("local.set "), e.call_m(e.v("arg"), "name", e.tup()))),
                ),
            ),
            push(e, in_(e, "used"), e.call_m(e.v("arg"), "name", e.tup())),
            e.call_m(e.v("arg"), "set_active", e.int_of(0)),
            e.foreach(
                in_(e, "pn"),
                "q",
                e.if_only(
                    and_b(e, _pend_active(e, e.v("q")), e.mb.operator_gt(_pend_pos(e, e.v("q")), e.v("fpos"))),
                    e.call_m(e.v("q"), "set_pos", e.mb.operator_sub(_pend_pos(e, e.v("q")), num(e, 1))),
                ),
            ),
            e.mb.set(in_(e, "h"), e.mb.operator_sub(in_(e, "h"), num(e, 1))),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "flush_all",
        e.tup(),
        e.foreach(
            in_(e, "pn"), "q0", e.if_only(_pend_active(e, e.v("q0")), e.call_m(outer(e), "flush_one", e.v("q0")))
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "control",
        e.rec(e.p("delta", int_t(e)), e.p("text", str_(e))),
        e.seq(e.call_m(outer(e), "flush_all", e.tup()), e.call_m(outer(e), "line", e.v("arg"))),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "flush_named",
        str_(e),
        e.foreach(
            in_(e, "pn"),
            "q",
            e.if_only(
                and_b(e, _pend_active(e, e.v("q")), e.eq(e.call_m(e.v("q"), "name", e.tup()), e.v("arg"))),
                e.call_m(outer(e), "flush_one", e.v("q")),
            ),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "set_local",
        str_(e),
        e.seq(
            e.let("nuses", e.call_m(e.call_m(outer(e), "use_of", e.v("arg")), "n", e.tup())),
            e.call_m(outer(e), "flush_named", e.v("arg")),
            e.if_only(
                e.eq(e.v("nuses"), num(e, 0)),
                e.call_m(outer(e), "line", e.rec(e.p("delta", e.int_of(-1)), e.p("text", e.s("drop")))),
            ),
            e.if_only(
                e.eq(e.v("nuses"), num(e, 1)),
                push(
                    e,
                    in_(e, "pn"),
                    mk(
                        e,
                        "wpend",
                        e.p("name", e.v("arg")),
                        e.p("pos", e.mb.operator_sub(in_(e, "h"), num(e, 1))),
                        e.p("at", in_(e, "n")),
                        e.p("active", e.int_of(1)),
                    ),
                ),
            ),
            e.if_only(
                e.mb.operator_gt(e.v("nuses"), num(e, 1)),
                e.seq(
                    e.call_m(
                        outer(e),
                        "line",
                        e.rec(e.p("delta", e.int_of(-1)), e.p("text", e.cat(e.s("local.set "), e.v("arg")))),
                    ),
                    push(e, in_(e, "used"), e.v("arg")),
                ),
            ),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "get_local",
        str_(e),
        e.seq(
            e.call_m(outer(e), "flush_named", e.v("arg")),
            e.call_m(
                outer(e), "line", e.rec(e.p("delta", e.int_of(1)), e.p("text", e.cat(e.s("local.get "), e.v("arg"))))
            ),
            push(e, in_(e, "used"), e.v("arg")),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "ops",
        e.list_type(t(e, "wval")),
        e.seq(
            e.let("flat", e.list_new(lt(e, "wval"))),
            e.foreach(e.v("arg"), "o0", e.foreach(_wv_flat(e, e.v("o0")), "o1", push(e, e.v("flat"), e.v("o1")))),
            e.let("onames", e.list_new(str_(e))),
            count_let(e, "no"),
            e.foreach(
                e.v("flat"),
                "o",
                e.seq(
                    push(
                        e,
                        e.v("onames"),
                        e.match_of(e.call_m(e.v("o"), "source", e.tup()), "s", e.dstr(""), e.p("local", e.v("s"))),
                    ),
                    e.incr(e.fld(e.v("no"), "v")),
                ),
            ),
            e.let("act", e.list_new(lt(e, "wpend"))),
            count_let(e, "na"),
            e.foreach(
                in_(e, "pn"),
                "q",
                e.if_only(
                    _pend_active(e, e.v("q")), e.seq(push(e, e.v("act"), e.v("q")), e.incr(e.fld(e.v("na"), "v")))
                ),
            ),
            e.let("jj", e.rec(e.p("v", e.int_of(0)))),
            e.let(
                "j",
                e.rec(
                    e.p(
                        "v",
                        e.if_else(
                            e.mb.operator_lt(e.fld(e.v("no"), "v"), e.fld(e.v("na"), "v")),
                            e.fld(e.v("no"), "v"),
                            e.fld(e.v("na"), "v"),
                        ),
                    )
                ),
            ),
            e.foreach(
                e.v("flat"),
                "_",
                e.if_only(
                    and_b(
                        e,
                        e.eq(e.fld(e.v("jj"), "v"), num(e, 0)),
                        e.mb.operator_gt(e.fld(e.v("j"), "v"), num(e, 0)),
                    ),
                    e.seq(
                        e.let("base", e.mb.operator_sub(e.fld(e.v("na"), "v"), e.fld(e.v("j"), "v"))),
                        e.let("ok", e.rec(e.p("v", e.int_of(1)))),
                        e.let("ai", e.rec(e.p("v", e.int_of(0)))),
                        e.foreach(
                            e.v("act"),
                            "q",
                            e.seq(
                                e.if_only(
                                    e.mb.operator_ge(e.fld(e.v("ai"), "v"), e.v("base")),
                                    e.seq(
                                        e.let("oi", e.mb.operator_sub(e.fld(e.v("ai"), "v"), e.v("base"))),
                                        e.if_only(
                                            and_b(
                                                e,
                                                e.eq(e.v("oi"), num(e, 0)),
                                                e.not_(
                                                    e.eq(
                                                        in_(e, "h"),
                                                        e.mb.operator_add(_pend_pos(e, e.v("q")), e.fld(e.v("j"), "v")),
                                                    )
                                                ),
                                            ),
                                            e.mb.set(e.fld(e.v("ok"), "v"), num(e, 0)),
                                        ),
                                        e.let("k", e.rec(e.p("v", e.int_of(0)))),
                                        e.foreach(
                                            e.v("onames"),
                                            "on",
                                            e.seq(
                                                e.if_only(
                                                    and_b(
                                                        e,
                                                        e.eq(e.fld(e.v("k"), "v"), e.v("oi")),
                                                        e.not_(e.eq(e.v("on"), e.call_m(e.v("q"), "name", e.tup()))),
                                                    ),
                                                    e.mb.set(e.fld(e.v("ok"), "v"), num(e, 0)),
                                                ),
                                                e.incr(e.fld(e.v("k"), "v")),
                                            ),
                                        ),
                                    ),
                                ),
                                e.incr(e.fld(e.v("ai"), "v")),
                            ),
                        ),
                        e.if_only(
                            e.eq(e.fld(e.v("ok"), "v"), num(e, 1)),
                            e.mb.set(e.fld(e.v("jj"), "v"), e.fld(e.v("j"), "v")),
                        ),
                        e.mb.set(e.fld(e.v("j"), "v"), e.mb.operator_sub(e.fld(e.v("j"), "v"), num(e, 1))),
                    ),
                ),
            ),
            e.let("base", e.mb.operator_sub(e.fld(e.v("na"), "v"), e.fld(e.v("jj"), "v"))),
            e.let("ai", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                e.v("act"),
                "q",
                e.seq(
                    e.if_only(
                        e.mb.operator_ge(e.fld(e.v("ai"), "v"), e.v("base")),
                        e.call_m(e.v("q"), "set_active", e.int_of(0)),
                    ),
                    e.incr(e.fld(e.v("ai"), "v")),
                ),
            ),
            e.let("k", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                e.v("flat"),
                "o",
                e.seq(
                    e.if_only(
                        e.mb.operator_ge(e.fld(e.v("k"), "v"), e.fld(e.v("jj"), "v")),
                        e.match_of(
                            e.call_m(e.v("o"), "source", e.tup()),
                            "s",
                            None,
                            e.p("local", e.call_m(outer(e), "get_local", e.v("s"))),
                            e.p(
                                "konst",
                                e.call_m(
                                    outer(e),
                                    "line",
                                    e.rec(
                                        e.p("delta", e.int_of(1)),
                                        e.p(
                                            "text",
                                            e.cat(
                                                e.call_m(in_(e, "mod"), "ir", _wv_ty(e, e.v("o"))),
                                                e.s(".const "),
                                                e.v("s"),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                            e.p("slot", e.mb.panic(e.s("wasm: slot pushed without a load"))),
                            e.p("mem", e.mb.panic(e.s("wasm: memory place pushed without a load"))),
                            e.p("func", e.mb.panic(e.s("wasm: function pushed as a value"))),
                            e.p("multi", e.mb.panic(e.s("wasm: tuple not flattened"))),
                        ),
                    ),
                    e.incr(e.fld(e.v("k"), "v")),
                ),
            ),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "region_start",
        e.tup(),
        e.seq(e.call_m(_region_of(e, in_(e, "depth")), "set_start", in_(e, "n")), e.mb.set(in_(e, "h"), e.int_of(0))),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "label",
        str_(e),
        e.seq(
            e.call_m(outer(e), "flush_all", e.tup()),
            push(
                e,
                in_(e, "blocks"),
                mk(
                    e,
                    "wblock",
                    e.p("at", e.call_m(_region_of(e, in_(e, "depth")), "start", e.tup())),
                    e.p("name", e.cat(e.s("block "), e.v("arg"))),
                ),
            ),
            e.call_m(outer(e), "line", e.rec(e.p("delta", e.int_of(0)), e.p("text", e.s("end")))),
            e.mb.set(in_(e, "h"), e.int_of(0)),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "open_if",
        e.rec(e.p("text", str_(e)), e.p("valued", bool_t(e))),
        e.seq(
            e.call_m(outer(e), "control", e.rec(e.p("delta", e.int_of(-1)), e.p("text", a(e, "text")))),
            e.incr(in_(e, "depth")),
            push(
                e,
                in_(e, "regions"),
                mk(
                    e,
                    "wregion",
                    e.p("depth", in_(e, "depth")),
                    e.p("start", in_(e, "n")),
                    e.p("valued", a(e, "valued")),
                    e.p("closed", e.int_of(0)),
                ),
            ),
            e.mb.set(in_(e, "h"), e.int_of(0)),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "open_loop",
        str_(e),
        e.seq(
            e.call_m(
                outer(e), "control", e.rec(e.p("delta", e.int_of(0)), e.p("text", e.cat(e.s("loop "), e.v("arg"))))
            ),
            e.incr(in_(e, "depth")),
            push(
                e,
                in_(e, "regions"),
                mk(
                    e,
                    "wregion",
                    e.p("depth", in_(e, "depth")),
                    e.p("start", in_(e, "n")),
                    e.p("valued", e.b(False)),
                    e.p("closed", e.int_of(0)),
                ),
            ),
            e.mb.set(in_(e, "h"), e.int_of(0)),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "else_",
        e.tup(),
        e.seq(
            e.call_m(outer(e), "control", e.rec(e.p("delta", e.int_of(0)), e.p("text", e.s("else")))),
            e.call_m(outer(e), "region_start", e.tup()),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "end_if",
        e.tup(),
        e.seq(
            e.call_m(outer(e), "control", e.rec(e.p("delta", e.int_of(0)), e.p("text", e.s("end")))),
            e.let("reg", _region_of(e, in_(e, "depth"))),
            e.call_m(e.v("reg"), "set_closed", e.tup()),
            e.mb.set(in_(e, "h"), e.if_else(e.call_m(e.v("reg"), "valued", e.tup()), e.int_of(1), e.int_of(0))),
            e.mb.set(in_(e, "depth"), e.mb.operator_sub(in_(e, "depth"), num(e, 1))),
        ),
    )
    _vmethod(
        e,
        x,
        "wrs",
        "call",
        e.rec(e.p("fn", str_(e)), e.p("nargs", int_t(e)), e.p("res", e.list_type(str_(e)))),
        e.seq(
            e.call_m(
                outer(e),
                "line",
                e.rec(
                    e.p("delta", e.mb.operator_sub(e.int_of(0), a(e, "nargs"))),
                    e.p("text", e.cat(e.s("call "), a(e, "fn"))),
                ),
            ),
            # The results are on the stack in order: they are set last first.
            e.foreach(a(e, "res"), "_", e.incr(in_(e, "h"))),
            _reversed_names(e, a(e, "res"), "rname", e.call_m(outer(e), "set_local", e.v("rname"))),
        ),
    )
    method(
        e,
        x,
        "wrs",
        "finish",
        e.tup(),
        e.rec(e.p("lines", e.list_type(str_(e))), e.p("used", e.list_type(str_(e)))),
        e.seq(
            e.call_m(outer(e), "flush_all", e.tup()),
            e.if_only(
                e.not_(e.eq(in_(e, "depth"), num(e, 0))), e.mb.panic(e.s("wasm: unbalanced structured instructions"))
            ),
            e.let("lines", e.list_new(str_(e))),
            e.let("k", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                in_(e, "out"),
                "line",
                e.seq(
                    e.foreach(
                        in_(e, "sets"),
                        "sx",
                        e.if_only(
                            e.eq(e.call_m(e.v("sx"), "at", e.tup()), e.fld(e.v("k"), "i")),
                            push(e, e.v("lines"), e.call_m(e.v("sx"), "name", e.tup())),
                        ),
                    ),
                    e.let("opens", e.list_new(str_(e))),
                    e.foreach(
                        in_(e, "blocks"),
                        "b",
                        e.if_only(
                            e.eq(e.call_m(e.v("b"), "at", e.tup()), e.fld(e.v("k"), "i")),
                            push(e, e.v("opens"), e.call_m(e.v("b"), "name", e.tup())),
                        ),
                    ),
                    e.let("rev", e.list_new(str_(e))),
                    e.let("on", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(e.v("opens"), "_", e.incr(e.fld(e.v("on"), "v"))),
                    e.foreach(
                        e.v("opens"),
                        "_",
                        e.seq(
                            e.let("want", e.mb.operator_sub(e.fld(e.v("on"), "v"), num(e, 1))),
                            e.let("j", e.rec(e.p("v", e.int_of(0)))),
                            e.foreach(
                                e.v("opens"),
                                "o",
                                e.seq(
                                    e.if_only(e.eq(e.fld(e.v("j"), "v"), e.v("want")), push(e, e.v("rev"), e.v("o"))),
                                    e.incr(e.fld(e.v("j"), "v")),
                                ),
                            ),
                            e.mb.set(e.fld(e.v("on"), "v"), e.v("want")),
                        ),
                    ),
                    e.foreach(e.v("rev"), "o", push(e, e.v("lines"), e.v("o"))),
                    push(e, e.v("lines"), e.v("line")),
                    e.incr(e.fld(e.v("k"), "i")),
                ),
            ),
            e.foreach(
                in_(e, "sets"),
                "sx",
                e.if_only(
                    e.eq(e.call_m(e.v("sx"), "at", e.tup()), e.fld(e.v("k"), "i")),
                    push(e, e.v("lines"), e.call_m(e.v("sx"), "name", e.tup())),
                ),
            ),
            e.ret(e.rec(e.p("lines", e.v("lines")), e.p("used", in_(e, "used")))),
        ),
    )


def _count_use(e, wval_tp):
    return e.foreach(
        _wv_flat(e, wval_tp),
        "pw",
        e.match_of(e.call_m(e.v("pw"), "source", e.tup()), "s", e.seq(), e.p("local", _count_name(e, e.v("s")))),
    )


def _count_name(e, name):
    return e.call_m(e.call_m(e.v("r"), "use_of", name), "inc", e.tup())


def bind_types(e, out):
    for prim in ["i8", "i32", "i64", "u8", "u32", "u64", "f32", "f64", "void"]:
        out.append(e.let("t_" + prim, e.fld(e.v("wasm"), prim)))
    for prim in ["void", "u8", "u32", "u64"]:
        out.append(
            e.let("t_p" + ("v" if prim == "void" else prim), e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_" + prim)))
        )


def module(e):
    entries = []
    for b in range(256):
        text = chr(b) if 32 <= b < 127 and b != ord('"') and b != ord("\\") else "\\%02x" % b
        entries.append(e.p(str(b), e.s(text)))
    printable_bytes_map = e.map_new(str_(e), str_(e), *entries)
    x = []
    x.append(e.let("meta", e.import_local("meta", meta.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("srcmap", e.import_local("srcmap", srcmap.FILE)))
    for vid in ["size_id", "hash_id", "eq_id"]:
        x.append(e.let(vid, e.fld(e.v("values"), vid)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(
        e,
        x,
        "wint",
        e.p("bits", int_t(e)),
        e.p("signed", bool_t(e)),
        e.p("min", e.types_double()),
        e.p("max", e.types_double()),
    )
    def_iface(e, x, "wfloat", e.p("bits", int_t(e)))
    def_iface(e, x, "wptr", e.p("pointee", ty(e)))
    def_iface(e, x, "wvoid")
    def_iface(e, x, "wunit_m")
    def_iface(e, x, "wloop_m")
    def_iface(e, x, "wmem_grow_m")
    def_iface(e, x, "wmem_copy_m")
    def_iface(e, x, "wmem_size_m")
    def_iface(e, x, "wmem_fill_m")
    def_iface(e, x, "wtrap_m")
    def_iface(e, x, "wgtype_m", e.p("base", ty(e)))
    def_iface(e, x, "wgfn_m", e.p("kind", int_t(e)))
    def_iface(e, x, "wfn", e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)))
    def_iface(e, x, "wtuple", e.p("elems", e.list_type(ty(e))))

    x.append(e.let("wsrc_u", e.call_m0(e.v("d"), "union")))
    for tag in ["local", "slot", "konst", "func"]:
        x.append(
            e.let(
                "ws_" + tag,
                e.call_m(e.v("wsrc_u"), "variant", e.rec(e.p("tag", e.s(tag)), e.p("type_ref", str_(e)))),
            )
        )
    x.append(
        e.let(
            "ws_mem",
            e.call_m(
                e.v("wsrc_u"),
                "variant",
                e.rec(e.p("tag", e.s("mem")), e.p("type_ref", e.rec(e.p("addr", str_(e)), e.p("offset", int_t(e))))),
            ),
        )
    )
    def_obj(e, x, "wval", "wasm value", e.rec(e.p("ty", ty(e)), e.p("source", t(e, "wsrc_u"))))
    # A tuple value is its components in order (wasm multi-value); each component is itself a value.
    x.append(
        e.let(
            "ws_multi",
            e.call_m(
                e.v("wsrc_u"),
                "variant",
                e.rec(e.p("tag", e.s("multi")), e.p("type_ref", e.list_type(t(e, "wval")))),
            ),
        )
    )
    def_iface(e, x, "wslot", e.p("base", ty(e)), e.p("slot", _wval_t(e)))
    x.append(
        e.impl_interface(
            e.v("wval"),
            e.fld(e.v("values"), "retag"),
            e.p("retag", mk(e, "wval", e.p("ty", e.v("arg")), e.p("source", in_(e, "source")))),
        )
    )
    def_obj(
        e,
        x,
        "wdata",
        "wasm data segment",
        e.rec(e.p("name", str_(e)), e.p("addr", int_t(e)), e.p("bytes", e.list_type(int_t(e)))),
    )
    def_obj(
        e,
        x,
        "wlocal",
        "wasm function local",
        e.rec(e.p("name", str_(e)), e.p("ty", ty(e)), e.p("param", bool_t(e))),
    )
    def_obj(e, x, "wlabel", "wasm label", e.rec(e.p("key", e.types_jump_key()), e.p("name", str_(e))))
    def_obj(e, x, "wblock", "wasm block opening", e.rec(e.p("at", int_t(e)), e.p("name", str_(e))))

    x.append(e.let("wdep_u", e.call_m0(e.v("d"), "union")))
    x.append(
        e.let(
            "wd_import",
            e.call_m(
                e.v("wdep_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("import")),
                    e.p("type_ref", e.rec(e.p("module", str_(e)), e.p("name", str_(e)), e.p("ty", ty(e)))),
                ),
            ),
        )
    )
    def_obj(e, x, "wdep", "wasm dependency", e.rec(e.p("k", t(e, "wdep_u"))))
    x.append(e.let("wmeta_u", e.call_m0(e.v("d"), "union")))
    x.append(
        e.let(
            "wm_dep",
            e.call_m(
                e.v("wmeta_u"),
                "variant",
                e.rec(e.p("tag", e.s("dep")), e.p("type_ref", e.rec(e.p("dep", t(e, "wdep"))))),
            ),
        )
    )
    x.append(
        e.let(
            "wm_other",
            e.call_m(
                e.v("wmeta_u"),
                "variant",
                e.rec(e.p("tag", e.s("other")), e.p("type_ref", e.fld(e.v("meta"), "other_t"))),
            ),
        )
    )
    def_obj(e, x, "wmeta", "wasm metadata", e.rec(e.p("k", t(e, "wmeta_u"))))

    x.append(e.let("winst_u", e.call_m0(e.v("d"), "union")))
    for v in [["label", "name"], ["br", "name"], ["loop", "name"]]:
        x.append(
            e.let(
                "wi_" + v[0],
                e.call_m(
                    e.v("winst_u"),
                    "variant",
                    e.rec(e.p("tag", e.s(v[0])), e.p("type_ref", e.rec(e.p(v[1], str_(e))))),
                ),
            )
        )
    x.append(
        e.let(
            "wi_if",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("if")),
                    e.p("type_ref", e.rec(e.p("cond", _wval_t(e)), e.p("ty", e.call(e.mb.types_option(), ty(e))))),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_push",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(e.p("tag", e.s("push")), e.p("type_ref", e.rec(e.p("val", _wval_t(e))))),
            ),
        )
    )
    x.append(
        e.let(
            "wi_setl",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(e.p("tag", e.s("setl")), e.p("type_ref", e.rec(e.p("name", str_(e))))),
            ),
        )
    )
    x.append(
        e.let(
            "wi_meta",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(e.p("tag", e.s("meta")), e.p("type_ref", e.rec(e.p("meta", t(e, "wmeta"))))),
            ),
        )
    )
    for tag in ["else", "end", "trap"]:
        x.append(
            e.let(
                "wi_" + tag,
                e.call_m(e.v("winst_u"), "variant", e.rec(e.p("tag", e.s(tag)), e.p("type_ref", e.tup()))),
            )
        )
    for tag in ["binop", "cmp"]:
        x.append(
            e.let(
                "wi_" + tag,
                e.call_m(
                    e.v("winst_u"),
                    "variant",
                    e.rec(
                        e.p("tag", e.s(tag)),
                        e.p(
                            "type_ref",
                            e.rec(
                                e.p("res", str_(e)),
                                e.p("op", str_(e)),
                                e.p("a", _wval_t(e)),
                                e.p("b", _wval_t(e)),
                            ),
                        ),
                    ),
                ),
            )
        )
    for tag in ["unop", "conv"]:
        x.append(
            e.let(
                "wi_" + tag,
                e.call_m(
                    e.v("winst_u"),
                    "variant",
                    e.rec(
                        e.p("tag", e.s(tag)),
                        e.p("type_ref", e.rec(e.p("res", str_(e)), e.p("op", str_(e)), e.p("a", _wval_t(e)))),
                    ),
                ),
            )
        )
    x.append(
        e.let(
            "wi_mgrow",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(e.p("tag", e.s("mgrow")), e.p("type_ref", e.rec(e.p("res", str_(e)), e.p("a", _wval_t(e))))),
            ),
        )
    )
    x.append(
        e.let(
            "wi_msize",
            e.call_m(
                e.v("winst_u"), "variant", e.rec(e.p("tag", e.s("msize")), e.p("type_ref", e.rec(e.p("res", str_(e)))))
            ),
        )
    )
    x.append(
        e.let(
            "wi_mcopy",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("mcopy")),
                    e.p("type_ref", e.rec(e.p("dst", _wval_t(e)), e.p("src", _wval_t(e)), e.p("n", _wval_t(e)))),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_mfill",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("mfill")),
                    e.p("type_ref", e.rec(e.p("dst", _wval_t(e)), e.p("val", _wval_t(e)), e.p("n", _wval_t(e)))),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_load",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("load")),
                    e.p("type_ref", e.rec(e.p("res", str_(e)), e.p("ty", ty(e)), e.p("name", str_(e)))),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_mload",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("mload")),
                    e.p(
                        "type_ref",
                        e.rec(
                            e.p("res", str_(e)),
                            e.p("ty", ty(e)),
                            e.p("addr", _wval_t(e)),
                            e.p("offset", int_t(e)),
                        ),
                    ),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_store",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(e.p("tag", e.s("store")), e.p("type_ref", e.rec(e.p("val", _wval_t(e)), e.p("name", str_(e))))),
            ),
        )
    )
    x.append(
        e.let(
            "wi_mstore",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("mstore")),
                    e.p(
                        "type_ref",
                        e.rec(
                            e.p("val", _wval_t(e)),
                            e.p("ty", ty(e)),
                            e.p("addr", str_(e)),
                            e.p("offset", int_t(e)),
                        ),
                    ),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_call",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("call")),
                    e.p(
                        "type_ref",
                        e.rec(
                            e.p("res", e.list_type(str_(e))),
                            e.p("fn", _wval_t(e)),
                            e.p("args", e.list_type(_wval_t(e))),
                        ),
                    ),
                ),
            ),
        )
    )
    x.append(
        e.let(
            "wi_ret",
            e.call_m(
                e.v("winst_u"),
                "variant",
                e.rec(
                    e.p("tag", e.s("ret")),
                    e.p("type_ref", e.rec(e.p("val", e.call(e.mb.types_option(), _wval_t(e))))),
                ),
            ),
        )
    )

    def_obj(e, x, "winst", "wasm instruction", e.rec(e.p("k", t(e, "winst_u")), e.p("loc", _loc_opt_t(e))))
    def_iface(e, x, "winst_m")
    def_iface(e, x, "wmod_m")
    def_iface(e, x, "wlabel_m")
    def_iface(e, x, "wlocal_m")
    def_iface(e, x, "wdata_m")
    def_iface(e, x, "wblock_m")
    def_obj(e, x, "wcode", "wasm code", e.rec(e.p("insts", _insts_t(e))))
    x.append(e.impl_interface(e.v("wcode"), e.mb.builtin("eval", "code_dyn")))
    method(e, x, "wcode", "insts", e.tup(), _insts_t(e), in_(e, "insts"))

    tm.module_defs(e, x, "wdef", "wasm definition")
    def_obj(
        e,
        x,
        "wmod",
        "wasm module",
        e.rec(
            e.p("n", int_t(e)),
            e.p("xx", e.call(e.mb.types_option(), e.types_expr_context())),
            e.p("meta", e.list_type(t(e, "wmeta"))),
            e.p("dep_keys", e.list_type(str_(e))),
            e.p("data", e.list_type(t(e, "wdata"))),
            e.p("data_end", int_t(e)),
            e.p("funcs", e.list_type(str_(e))),
            e.p("defs", e.list_type(t(e, "wdef"))),
            # The SipHash key block and function are one dependency each per module: their identities are minted
            # with the module, so every hash in it shares them.
            e.p("sip_key_id", tm.unique_t(e)),
            e.p("sip_fn_id", tm.unique_t(e)),
            e.p("exports", e.list_type(str_(e))),
            e.p("labels", e.list_type(t(e, "wlabel"))),
            e.p("locals", e.list_type(t(e, "wlocal"))),
            # The frame table behind the `;;@ frames.json:<frame + 1>:0` annotations of the rendered text.
            e.p("frames", e.fld(e.v("srcmap"), "table_t")),
        ),
    )
    def_obj(e, x, "wtarget", "wasm target", e.rec(e.p("mod", _wmod_t(e))))
    def_obj(e, x, "wirctx", "wasm type rendering context", e.rec(e.p("xx", xx_t(e))))
    x.append(e.let("wtype", e.call_m0(e.v("d"), "interface")))
    x.append(e.interface_impl(e.v("wtype"), True))
    x.append(e.let("wtype_id", e.call_m0(e.v("wtype"), "aspect_id")))
    x.append(
        e.call_m(
            e.v("wtype"),
            "func",
            e.rec(e.p("name", e.s("ir")), e.p("arg", t(e, "wirctx")), e.p("ret", e.option_type_some(str_(e)))),
        )
    )
    x.append(
        e.call_m(
            e.v("wtype"),
            "func",
            e.rec(e.p("name", e.s("ssa")), e.p("arg", e.tup()), e.p("ret", e.option_type_some(ty(e)))),
        )
    )
    def_obj(e, x, "wbinding", "wasm binding", e.rec(e.p("ty", ty(e)), e.p("slot", _wval_t(e))))
    # A parameter's slot, handed to the parameter type's `initial_bind` to make the binding over it.
    def_obj(e, x, "wparam", "wasm slot", e.rec(e.p("ty", ty(e)), e.p("slots", e.list_type(str_(e)))))
    x.append(
        e.impl_interface(
            e.v("wparam"),
            e.fld(e.v("values"), "retag_slot"),
            e.p("retag_slot", mk(e, "wparam", e.p("ty", e.v("arg")), e.p("slots", in_(e, "slots")))),
        )
    )
    x.append(e.impl_interface(e.v("wparam"), e.mb.eval_binding_slot()))
    def_obj(e, x, "wbinding_none", "wasm empty binding", e.tup())
    def_obj(e, x, "wunit", "wasm unit", e.tup())
    def_obj(e, x, "wloop_t", "wasm loop", e.tup())
    def_obj(e, x, "wmem_grow", "wasm memory.grow", e.tup())
    def_obj(e, x, "wmem_copy", "wasm memory.copy", e.tup())
    def_obj(e, x, "wmem_size", "wasm memory.size", e.tup())
    def_obj(e, x, "wmem_fill", "wasm memory.fill", e.tup())
    def_obj(e, x, "wtrap", "wasm unreachable", e.tup())
    def_obj(
        e,
        x,
        "wt_int",
        "wasm int type",
        e.rec(
            e.p("bits", int_t(e)),
            e.p("signed", bool_t(e)),
            e.p("min", e.types_double()),
            e.p("max", e.types_double()),
        ),
    )
    def_obj(e, x, "wt_float", "wasm float type", e.rec(e.p("bits", int_t(e))))
    def_obj(e, x, "wt_ptr", "wasm pointer type", e.rec(e.p("pointee", ty(e))))
    def_obj(e, x, "wt_fn", "wasm function type", e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e))))
    def_obj(e, x, "wt_void", "wasm void type", e.tup())
    def_obj(e, x, "wt_tuple", "wasm tuple type", e.rec(e.p("elems", e.list_type(ty(e)))))
    def_obj(e, x, "wt_slot", "wasm slot type", e.rec(e.p("base", ty(e)), e.p("slot", _wval_t(e))))
    def_obj(e, x, "wgfn_t", "wasm global definition function", e.rec(e.p("kind", int_t(e))))
    def_obj(e, x, "wt_global", "wasm global type", e.rec(e.p("base", ty(e))))
    def_obj(
        e,
        x,
        "wt_import",
        "wasm import type",
        e.rec(e.p("module", str_(e)), e.p("name", str_(e)), e.p("base", ty(e))),
    )
    def_iface(e, x, "wimport_m", e.p("module", str_(e)), e.p("name", str_(e)), e.p("base", ty(e)))

    _fn_def(e, x, "h_ir", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), str_(e))
    fn_impl(
        e,
        x,
        "h_ir",
        body(
            e,
            e.let("lk", lookup(e, xx(e), a(e, "ty"), lt(e, "wtype"))),
            e.if_only(
                e.not_(e.fld(e.v("lk"), "is_some")),
                e.mb.panic(e.cat(e.s("wasm: not a wasm type: "), bim0(e, e.mb.eval_type(), "desc", a(e, "ty")))),
            ),
            e.ret(bim(e, lt(e, "wtype"), "ir", e.fld(e.v("lk"), "value"), mk(e, "wirctx", e.p("xx", xx(e))))),
        ),
    )
    _fn_def(e, x, "h_insts", code_t(e), _insts_t(e))
    _fn_def(e, x, "h_code", _insts_t(e), code_t(e))
    x.append(e.let("h_append_b", e.def_func(e.v("d"), "wasm.h_append")))
    x.append(e.let("h_append", e.fld(e.v("h_append_b"), "func")))
    e.fn_sigs["h_append"] = [
        e.rec(e.p("out", _insts_t(e)), e.p("code", code_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(e, x, "h_is_wasm", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(
        e,
        x,
        "h_ssa",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_ssa", errs_t(e))
    _fn_def(e, x, "h_mat", e.rec(e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e))), cve_t(e))
    _fn_def(
        e,
        x,
        "h_operand",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _wmod_t(e)),
            e.p("ty", ty(e)),
            e.p("cv", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_operand", errs_t(e))
    _fn_def(e, x, "h_is_unit", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(
        e,
        x,
        "h_set",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _wmod_t(e)),
            e.p("ty", ty(e)),
            e.p("self", cve_t(e)),
            e.p("value", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_set", errs_t(e))
    _fn_def(
        e,
        x,
        "h_binop",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _wmod_t(e)),
            e.p("ty", ty(e)),
            e.p("op", str_(e)),
            e.p("a", cve_t(e)),
            e.p("b", cve_t(e)),
            e.p("res", ty(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_binop", errs_t(e))
    _fn_def(
        e,
        x,
        "h_cmp",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _wmod_t(e)),
            e.p("ty", ty(e)),
            e.p("op", str_(e)),
            e.p("a", cve_t(e)),
            e.p("b", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_cmp", errs_t(e))
    _fn_def(
        e,
        x,
        "h_unop",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _wmod_t(e)),
            e.p("ty", ty(e)),
            e.p("op", str_(e)),
            e.p("a", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_unop", errs_t(e))
    _fn_def(
        e,
        x,
        "h_store_new",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_store_new", errs_t(e))
    _fn_def(e, x, "h_fresh_val", e.rec(e.p("mod", _wmod_t(e)), e.p("ty", ty(e))), _wval_t(e))
    _fn_def(e, x, "h_slot_val", e.rec(e.p("mod", _wmod_t(e)), e.p("ty", ty(e))), _wval_t(e))
    _fn_def(e, x, "h_flat_types", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), e.list_type(ty(e)))
    _fn_def(e, x, "h_names", _wval_t(e), e.list_type(str_(e)))
    _fn_def(
        e,
        x,
        "h_slots_val",
        e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e)), e.p("slots", e.list_type(str_(e)))),
        _wval_t(e),
    )
    x.append(e.let("h_store_to_b", e.def_func(e.v("d"), "wasm.h_store_to")))
    x.append(e.let("h_store_to", e.fld(e.v("h_store_to_b"), "func")))
    e.fn_sigs["h_store_to"] = [
        e.rec(e.p("loc", loc_t(e)), e.p("out", _insts_t(e)), e.p("val", _wval_t(e)), e.p("target", _wval_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    x.append(e.let("h_setl_val_b", e.def_func(e.v("d"), "wasm.h_setl_val")))
    x.append(e.let("h_setl_val", e.fld(e.v("h_setl_val_b"), "func")))
    e.fn_sigs["h_setl_val"] = [
        e.rec(e.p("loc", loc_t(e)), e.p("out", _insts_t(e)), e.p("target", _wval_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(
        e,
        x,
        "h_conv",
        e.rec(e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("op", str_(e)), e.p("a", cve_t(e)), e.p("to", ty(e))),
        cve_t(e),
    )
    _fn_def(
        e,
        x,
        "h_retag",
        e.rec(e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e)), e.p("ty", ty(e))),
        cve_t(e),
    )
    _fn_def(
        e,
        x,
        "h_narrow",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e)), e.p("to", ty(e))),
        cve_t(e),
    )
    _fn_def(e, x, "h_literal", e.rec(e.p("loc", loc_t(e)), e.p("ty", ty(e)), e.p("text", str_(e))), cve_t(e))
    _fn_def(e, x, "h_gref", cve_t(e), str_(e))
    _fn_def(e, x, "h_gval", e.rec(e.p("mod", _wmod_t(e)), e.p("cv", cve_t(e)), e.p("base", ty(e))), cve_t(e))
    fn_impl(
        e,
        x,
        "h_gref",
        body(
            e,
            e.ret(
                e.call(
                    e.mb.must_reinterpret(),
                    e.tup(
                        e.fld(e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, e.v("arg")), voc_t(e))), "data"),
                        str_(e),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gval",
        body(
            e,
            e.let("r", hf(e, "h_gref", a(e, "cv"))),
            e.ret(
                cv_of(
                    e,
                    cve_code(e, a(e, "cv")),
                    e.if_else(
                        has(e, e.call_m(a(e, "mod"), "xx", e.tup()), a(e, "base"), "wfn"),
                        _wval_new(e, a(e, "base"), "func", e.v("r")),
                        _wval_konst(e, a(e, "base"), to_str(e, e.call_m(a(e, "mod"), "addr", e.v("r")))),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_insts",
        body(
            e,
            e.ret(
                e.match_of(
                    e.v("arg"),
                    "c",
                    None,
                    e.p("none", _insts_new(e)),
                    e.p(
                        "target",
                        e.match_of(
                            e.call_m(e.v("c"), "cast", lt(e, "wcode")),
                            "r",
                            None,
                            e.p("ok", e.call_m(e.v("r"), "insts", e.tup())),
                            e.p("errs", e.mb.panic(e.s("wasm: code belongs to another target"))),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(e, x, "h_code", body(e, e.ret(e.mb.as_(mk_arg(e, "wcode", e.rec(e.p("insts", e.v("arg")))), code_t(e)))))
    fn_impl(e, x, "h_append", body(e, e.foreach(hf(e, "h_insts", a(e, "code")), "i", push(e, a(e, "out"), e.v("i")))))
    fn_impl(
        e,
        x,
        "h_is_wasm",
        body(
            e,
            e.ret(e.if_else(cve_has(e, a(e, "cv")), has(e, xx(e), cve_type(e, a(e, "cv")), "wtype"), e.b(False))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_ssa",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "expression has no value")),
            e.if_only(
                has(e, xx(e), cve_type(e, a(e, "cv")), "wgtype_m"),
                ret_m(
                    e,
                    hf_rec(
                        e,
                        "h_ssa",
                        e.p("xx", xx(e)),
                        e.p("loc", loc(e)),
                        e.p("mod", a(e, "mod")),
                        e.p(
                            "cv",
                            unwrap_cve_t(
                                e,
                                cast_value(
                                    e,
                                    xx(e),
                                    loc(e),
                                    acc(e, xx(e), cve_type(e, a(e, "cv")), "wgtype_m", "base"),
                                    a(e, "cv"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("lk", lookup(e, xx(e), cve_type(e, a(e, "cv")), lt(e, "wtype"))),
            e.if_only(e.not_(e.fld(e.v("lk"), "is_some")), throw_err(e, loc(e), "not a wasm value")),
            e.let("st", im0(e, "wtype", "ssa", e.fld(e.v("lk"), "value"))),
            e.let("c", unwrap_cve_t(e, cast_value(e, xx(e), loc(e), e.v("st"), a(e, "cv")))),
            e.ret(hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", e.v("c")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_is_unit",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), ret_m(e, dfalse(e))),
            e.if_only(has(e, xx(e), cve_type(e, a(e, "cv")), "wunit_m"), ret_m(e, e.not_(dfalse(e)))),
            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "tuple"))),
            e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, dfalse(e))),
            e.let("n", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                bim0(e, asp_iface(e, "tuple"), "element_types", e.fld(e.v("tk"), "value")),
                "_",
                e.incr(e.fld(e.v("n"), "v")),
            ),
            e.ret(e.eq(e.fld(e.v("n"), "v"), num(e, 0))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_mat",
        body(
            e,
            e.let("lv", _wval_of(e, a(e, "cv"))),
            # A tuple is materialized component by component.
            e.match_of(
                e.call_m(e.v("lv"), "source", e.tup()),
                "s",
                e.seq(),
                e.p(
                    "multi",
                    e.seq(
                        e.let("out", _insts_new(e)),
                        _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
                        e.let("parts", e.list_new(lt(e, "wval"))),
                        e.foreach(
                            e.v("s"),
                            "q",
                            e.seq(
                                e.let(
                                    "qm",
                                    hf_rec(
                                        e,
                                        "h_mat",
                                        e.p("loc", loc(e)),
                                        e.p("mod", a(e, "mod")),
                                        e.p("cv", cv_of(e, _code_of(e, _insts_new(e)), e.v("q"))),
                                    ),
                                ),
                                _append_code(e, e.v("out"), cve_code(e, e.v("qm"))),
                                push(e, e.v("parts"), _wval_of(e, e.v("qm"))),
                            ),
                        ),
                        ret_m(e, cv_of(e, _code_of(e, e.v("out")), _wval_multi(e, _wv_ty(e, e.v("lv")), e.v("parts")))),
                    ),
                ),
            ),
            e.if_only(
                _wv_is_addr(e, e.v("lv")),
                e.seq(
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
                    e.let("r", _fresh(e, a(e, "mod"), _wv_ty(e, e.v("lv")))),
                    e.let("place", e.call_m(e.v("lv"), "addr", e.tup())),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "mload",
                            e.p("res", e.v("r")),
                            e.p("ty", _wv_ty(e, e.v("lv"))),
                            e.p("addr", _wval_local(e, _int_ty(e, "i32"), e.fld(e.v("place"), "addr"))),
                            e.p("offset", e.fld(e.v("place"), "offset")),
                        ),
                    ),
                    ret_m(e, cv_of(e, _code_of(e, e.v("out")), _wval_local(e, _wv_ty(e, e.v("lv")), e.v("r")))),
                ),
            ),
            e.if_only(e.not_(_wv_is_mem(e, e.v("lv"))), ret_m(e, a(e, "cv"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            e.let("r", _fresh(e, a(e, "mod"), _wv_ty(e, e.v("lv")))),
            push(e, e.v("out"), _load_inst(e, loc(e), e.v("r"), _wv_ty(e, e.v("lv")), _wv_mem(e, e.v("lv")))),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, _wv_ty(e, e.v("lv")), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_operand",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "operand has no value")),
            e.let("c", unwrap_cve_t(e, cast_value(e, xx(e), loc(e), a(e, "ty"), a(e, "cv")))),
            e.ret(hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", e.v("c")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_set",
        body(
            e,
            e.let("sl", _wval_of(e, a(e, "self"))),
            e.if_only(
                _wv_is_addr(e, e.v("sl")),
                e.seq(
                    e.let("v", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "value"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "self"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    e.let("place", e.call_m(e.v("sl"), "addr", e.tup())),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "mstore",
                            e.p("val", _wval_of(e, e.v("v"))),
                            e.p("ty", _wv_ty(e, e.v("sl"))),
                            e.p("addr", e.fld(e.v("place"), "addr")),
                            e.p("offset", e.fld(e.v("place"), "offset")),
                        ),
                    ),
                    ret_m(e, cv_no(e, _code_of(e, e.v("out")))),
                ),
            ),
            e.match_of(
                e.call_m(e.v("sl"), "source", e.tup()),
                "s",
                e.seq(),
                e.p(
                    "multi",
                    e.seq(
                        e.let("v", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "value"))),
                        e.let("out", _insts_new(e)),
                        _append_code(e, e.v("out"), cve_code(e, a(e, "self"))),
                        _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                        _store_to(e, loc(e), e.v("out"), _wval_of(e, e.v("v")), e.v("sl")),
                        ret_m(e, cv_no(e, _code_of(e, e.v("out")))),
                    ),
                ),
            ),
            e.if_only(e.not_(_wv_is_mem(e, e.v("sl"))), throw_err(e, loc(e), "value is not assignable")),
            e.let("v", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "value"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "self"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            push(e, e.v("out"), _store_inst(e, loc(e), _wval_of(e, e.v("v")), _wv_mem(e, e.v("sl")))),
            e.ret(cv_no(e, _code_of(e, e.v("out")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_binop",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("a2", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("a2"))),
            e.let("b2", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "b"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("b2"))),
            e.let("r", _fresh(e, a(e, "mod"), a(e, "res"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "binop",
                    e.p("res", e.v("r")),
                    e.p("op", a(e, "op")),
                    e.p("a", _wval_of(e, e.v("a2"))),
                    e.p("b", _wval_of(e, e.v("b2"))),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, a(e, "res"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_cmp",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("a2", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("a2"))),
            e.let("b2", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "b"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("b2"))),
            e.let("i1", _int_ty(e, "i1")),
            e.let("r", _fresh(e, a(e, "mod"), e.v("i1"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "cmp",
                    e.p("res", e.v("r")),
                    e.p("op", a(e, "op")),
                    e.p("a", _wval_of(e, e.v("a2"))),
                    e.p("b", _wval_of(e, e.v("b2"))),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, e.v("i1"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_unop",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("a2", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("a2"))),
            e.let("r", _fresh(e, a(e, "mod"), a(e, "ty"))),
            push(
                e,
                e.v("out"),
                _inst(e, loc(e), "unop", e.p("res", e.v("r")), e.p("op", a(e, "op")), e.p("a", _wval_of(e, e.v("a2")))),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, a(e, "ty"), e.v("r")))),
        ),
    )
    _val_shape_impls(e, x)
    fn_impl(
        e,
        x,
        "h_store_new",
        body(
            e,
            e.let("v", _ssa(e, xx(e), loc(e), a(e, "mod"), a(e, "cv"))),
            e.let("ty", cve_type(e, e.v("v"))),
            e.let("sv", _slot_val(e, a(e, "mod"), e.v("ty"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            _store_to(e, loc(e), e.v("out"), _wval_of(e, e.v("v")), e.v("sv")),
            e.ret(cv_of(e, _code_of(e, e.v("out")), e.v("sv"))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_conv",
        body(
            e,
            e.let("a0", hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", a(e, "a")))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("a0"))),
            e.let("r", _fresh(e, a(e, "mod"), a(e, "to"))),
            push(
                e,
                e.v("out"),
                _inst(e, loc(e), "conv", e.p("res", e.v("r")), e.p("op", a(e, "op")), e.p("a", _wval_of(e, e.v("a0")))),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, a(e, "to"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_retag",
        body(
            e,
            e.let("m", hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", a(e, "cv")))),
            e.ret(
                cv_of(
                    e,
                    cve_code(e, e.v("m")),
                    mk(
                        e,
                        "wval",
                        e.p("ty", a(e, "ty")),
                        e.p("source", e.call_m(_wval_of(e, e.v("m")), "source", e.tup())),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_narrow",
        body(
            e,
            e.let("bits", acc(e, xx(e), a(e, "to"), "wint", "bits")),
            e.if_only(
                e.mb.operator_ge(e.v("bits"), num(e, 32)),
                ret_m(
                    e,
                    hf_rec(
                        e,
                        "h_retag",
                        e.p("loc", loc(e)),
                        e.p("mod", a(e, "mod")),
                        e.p("cv", a(e, "cv")),
                        e.p("ty", a(e, "to")),
                    ),
                ),
            ),
            e.let("m", hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", a(e, "cv")))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("m"))),
            e.let("r", _fresh(e, a(e, "mod"), a(e, "to"))),
            e.let("signed", acc(e, xx(e), a(e, "to"), "wint", "signed")),
            e.if_only(
                and_b(e, e.v("signed"), e.mb.operator_gt(e.v("bits"), num(e, 1))),
                push(
                    e,
                    e.v("out"),
                    _inst(
                        e,
                        loc(e),
                        "unop",
                        e.p("res", e.v("r")),
                        e.p("op", e.cat(e.s("extend"), to_str(e, e.v("bits")), e.s("_s"))),
                        e.p("a", _wval_of(e, e.v("m"))),
                    ),
                ),
            ),
            e.if_only(
                e.not_(and_b(e, e.v("signed"), e.mb.operator_gt(e.v("bits"), num(e, 1)))),
                push(
                    e,
                    e.v("out"),
                    _inst(
                        e,
                        loc(e),
                        "binop",
                        e.p("res", e.v("r")),
                        e.p("op", e.s("and")),
                        e.p("a", _wval_of(e, e.v("m"))),
                        e.p(
                            "b",
                            _wval_konst(
                                e,
                                _wv_ty(e, _wval_of(e, e.v("m"))),
                                e.if_else(
                                    e.eq(e.v("bits"), num(e, 1)),
                                    e.dstr("1"),
                                    e.if_else(e.eq(e.v("bits"), num(e, 8)), e.dstr("255"), e.dstr("65535")),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _wval_local(e, a(e, "to"), e.v("r")))),
        ),
    )
    fn_impl(e, x, "h_literal", body(e, e.ret(cv_of(e, code_none(e, loc(e)), _wval_konst(e, a(e, "ty"), a(e, "text"))))))
    _fn_def(e, x, "c_ptr", ty(e), ty(e))
    fn_impl(e, x, "c_ptr", body(e, e.ret(mk(e, "wt_ptr", e.p("pointee", e.v("arg"))))))
    _fn_def(e, x, "c_tuple", e.list_type(ty(e)), ty(e))
    fn_impl(e, x, "c_tuple", body(e, e.ret(mk(e, "wt_tuple", e.p("elems", e.v("arg"))))))
    _fn_def(e, x, "c_fn", e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e))), ty(e))
    fn_impl(e, x, "c_fn", body(e, e.ret(mk(e, "wt_fn", e.p("params", a(e, "params")), e.p("ret", a(e, "ret"))))))
    # Dependencies: a function or a zeroed block that a module gets only when code uses it. `func_dep` and
    # `alloc_dep` make callable const functions; a call defines the item in the current module on first use (by
    # name), then calls the function or yields the block's pointer. The definition travels in the const function.
    _fn_def(
        e,
        x,
        "h_funcdep_call",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("id", tm.unique_t(e)),
            e.p("name", str_(e)),
            e.p("params", e.list_type(str_(e))),
            e.p("ty", ty(e)),
            e.p("body", e.mb.types_expr()),
            e.p("argument", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_funcdep_call", errs_t(e))
    fn_impl(
        e,
        x,
        "h_funcdep_call",
        body(
            e,
            e.let("mod", _xmod_must(e)),
            e.let(
                "fref",
                tm.def_once(
                    e,
                    e.v("mod"),
                    a(e, "id"),
                    e.call_m(
                        e.v("mod"),
                        "func",
                        e.rec(
                            e.p("name", a(e, "name")),
                            e.p("params", a(e, "params")),
                            e.p("ty", a(e, "ty")),
                            e.p("body", a(e, "body")),
                            e.p("public", e.b(False)),
                        ),
                    ),
                ),
            ),
            e.let("ref", cv_of(e, code_none(e, loc(e)), _wval_new(e, a(e, "ty"), "func", e.v("fref")))),
            e.ret(
                _must(
                    e,
                    bim(
                        e,
                        asp_iface(e, "function"),
                        "call",
                        lookup_v(e, xx(e), a(e, "ty"), asp_iface(e, "function")),
                        e.rec(
                            e.p("xx", xx(e)),
                            e.p("loc", loc(e)),
                            e.p("function", e.v("ref")),
                            e.p("argument", a(e, "argument")),
                        ),
                    ),
                )
            ),
        ),
    )
    _fn_def(
        e,
        x,
        "h_allocdep_call",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("id", tm.unique_t(e)),
            e.p("name", str_(e)),
            e.p("size", int_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_allocdep_call", errs_t(e))
    fn_impl(
        e,
        x,
        "h_allocdep_call",
        body(
            e,
            e.let("mod", _xmod_must(e)),
            e.let(
                "ref",
                e.call_m(
                    e.v("mod"),
                    "alloc_once",
                    e.rec(e.p("id", a(e, "id")), e.p("name", a(e, "name")), e.p("size", a(e, "size"))),
                ),
            ),
            e.ret(
                cv_of(
                    e,
                    code_none(e, loc(e)),
                    e.call(
                        e.eval_builtin("value_object_const"),
                        e.rec(
                            e.p(
                                "type",
                                _wgfn_global_t(e, mk(e, "wt_ptr", e.p("pointee", mk_arg(e, "wt_void", e.tup())))),
                            ),
                            e.p(
                                "data",
                                e.call(e.mb.must_reinterpret(), e.tup(e.v("ref"), e.mb.builtin("types", "object"))),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    # Constant data as a dependency: `data_dep({name, elem, values})` (little-endian integers of the element type) and
    # `cstr_dep({name, text})` (NUL-terminated UTF-8) define a data segment on first use and yield its pointer.
    _fn_def(
        e,
        x,
        "h_datadep_call",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("id", tm.unique_t(e)),
            e.p("name", str_(e)),
            e.p("elem", ty(e)),
            e.p("values", e.list_type(int_t(e))),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_datadep_call", errs_t(e))
    fn_impl(
        e,
        x,
        "h_datadep_call",
        body(
            e,
            e.let("mod", _xmod_must(e)),
            e.if_only(
                e.not_(has(e, xx(e), a(e, "elem"), "wint")),
                throw_err(
                    e, loc(e), e.cat(e.s("wasm data_dep elem must be an integer type, not "), ty_desc(e, a(e, "elem")))
                ),
            ),
            e.let("bits", acc(e, xx(e), a(e, "elem"), "wint", "bits")),
            e.let("width", e.mb.operator_div(e.mb.operator_add(e.v("bits"), e.int_of(7)), e.int_of(8))),
            e.let("min", acc(e, xx(e), a(e, "elem"), "wint", "min")),
            e.let("max", acc(e, xx(e), a(e, "elem"), "wint", "max")),
            e.let("bytes", e.list_new(int_t(e))),
            e.foreach(
                a(e, "values"),
                "v",
                e.seq(
                    e.if_only(
                        or_b(
                            e,
                            e.mb.operator_lt(e.mb.as_(e.v("v"), e.types_double()), e.v("min")),
                            e.mb.operator_gt(e.mb.as_(e.v("v"), e.types_double()), e.v("max")),
                        ),
                        throw_err(
                            e,
                            loc(e),
                            e.cat(
                                e.s("wasm data_dep value "),
                                to_str(e, e.v("v")),
                                e.s(" is out of range for "),
                                ty_desc(e, a(e, "elem")),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.eq(e.v("width"), e.int_of(1)),
                        e.seq(
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(0)), e.int_of(255)),
                            )
                        ),
                    ),
                    e.if_only(
                        e.eq(e.v("width"), e.int_of(2)),
                        e.seq(
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(0)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(8)), e.int_of(255)),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.eq(e.v("width"), e.int_of(4)),
                        e.seq(
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(0)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(8)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(16)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(24)), e.int_of(255)),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.eq(e.v("width"), e.int_of(8)),
                        e.seq(
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(0)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(8)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(16)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(24)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(32)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(40)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(48)), e.int_of(255)),
                            ),
                            push(
                                e,
                                e.v("bytes"),
                                e.mb.operator_and(e.mb.operator_shr(e.v("v"), e.int_of(56)), e.int_of(255)),
                            ),
                        ),
                    ),
                ),
            ),
            e.let(
                "ref",
                e.call_m(
                    e.v("mod"),
                    "data_once",
                    e.rec(e.p("id", a(e, "id")), e.p("name", a(e, "name")), e.p("bytes", e.v("bytes"))),
                ),
            ),
            e.ret(
                cv_of(
                    e,
                    code_none(e, loc(e)),
                    e.call(
                        e.eval_builtin("value_object_const"),
                        e.rec(
                            e.p("type", _wgfn_global_t(e, mk(e, "wt_ptr", e.p("pointee", a(e, "elem"))))),
                            e.p(
                                "data",
                                e.call(e.mb.must_reinterpret(), e.tup(e.v("ref"), e.mb.builtin("types", "object"))),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    # The dependencies as callable types: their function values define them in the module on first use.
    tm.def_empty_binding(e, x, "webinding", "wasm empty value binding")
    tm.dep_type(
        e,
        x,
        "wfdep",
        "wasm function dependency",
        [("name", str_(e)), ("params", e.list_type(str_(e))), ("ty", ty(e)), ("body", e.mb.types_expr())],
        "h_funcdep_call",
        True,
        "webinding",
    )
    tm.dep_type(
        e,
        x,
        "wadep",
        "wasm allocation dependency",
        [("name", str_(e)), ("size", int_t(e))],
        "h_allocdep_call",
        False,
        "webinding",
    )
    tm.dep_type(
        e,
        x,
        "wddep",
        "wasm data dependency",
        [("name", str_(e)), ("elem", ty(e)), ("values", e.list_type(int_t(e)))],
        "h_datadep_call",
        False,
        "webinding",
    )
    _fn_def(
        e,
        x,
        "c_func_dep",
        e.rec(
            e.p("name", str_(e)), e.p("params", e.list_type(str_(e))), e.p("ty", ty(e)), e.p("body", e.mb.types_expr())
        ),
        ty(e),
    )
    fn_impl(
        e,
        x,
        "c_func_dep",
        body(
            e,
            e.ret(
                e.mb.as_(
                    mk(
                        e,
                        "wfdep",
                        e.p("id", tm.fresh_unique(e)),
                        e.p("name", a(e, "name")),
                        e.p("params", a(e, "params")),
                        e.p("ty", a(e, "ty")),
                        e.p("body", a(e, "body")),
                    ),
                    ty(e),
                )
            ),
        ),
    )
    _fn_def(
        e,
        x,
        "c_data_dep",
        e.rec(e.p("name", str_(e)), e.p("elem", ty(e)), e.p("values", e.list_type(int_t(e)))),
        ty(e),
    )
    fn_impl(
        e,
        x,
        "c_data_dep",
        body(
            e,
            e.ret(
                e.mb.as_(
                    mk(
                        e,
                        "wddep",
                        e.p("id", tm.fresh_unique(e)),
                        e.p("name", a(e, "name")),
                        e.p("elem", a(e, "elem")),
                        e.p("values", a(e, "values")),
                    ),
                    ty(e),
                )
            ),
        ),
    )
    _fn_def(e, x, "c_cstr_dep", e.rec(e.p("name", str_(e)), e.p("text", str_(e))), ty(e))
    fn_impl(
        e,
        x,
        "c_cstr_dep",
        body(
            e,
            e.let("values", e.list_new(int_t(e))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), a(e, "text")),
                "b",
                push(e, e.v("values"), e.mb.operator_and(e.mb.as_(e.v("b"), int_t(e)), e.int_of(255))),
            ),
            push(e, e.v("values"), e.int_of(0)),
            e.ret(
                hf_rec(
                    e,
                    "c_data_dep",
                    e.p("name", a(e, "name")),
                    e.p("elem", _int_ty(e, "u8")),
                    e.p("values", e.v("values")),
                )
            ),
        ),
    )
    _fn_def(e, x, "c_alloc_dep", e.rec(e.p("name", str_(e)), e.p("size", int_t(e))), ty(e))
    fn_impl(
        e,
        x,
        "c_alloc_dep",
        body(
            e,
            e.ret(
                e.mb.as_(
                    mk(
                        e,
                        "wadep",
                        e.p("id", tm.fresh_unique(e)),
                        e.p("name", a(e, "name")),
                        e.p("size", a(e, "size")),
                    ),
                    ty(e),
                )
            ),
        ),
    )
    _fn_def(e, x, "c_global_t", ty(e), ty(e))
    fn_impl(e, x, "c_global_t", body(e, e.ret(mk(e, "wt_global", e.p("base", e.v("arg"))))))
    _fn_def(e, x, "c_import_t", e.rec(e.p("module", str_(e)), e.p("name", str_(e)), e.p("ty", ty(e))), ty(e))
    fn_impl(
        e,
        x,
        "c_import_t",
        body(
            e,
            e.ret(
                mk(e, "wt_import", e.p("module", a(e, "module")), e.p("name", a(e, "name")), e.p("base", a(e, "ty")))
            ),
        ),
    )

    accessor(e, x, "wval", "ty", ty(e))
    accessor(e, x, "wval", "source", t(e, "wsrc_u"))
    method(
        e,
        x,
        "wval",
        "ref",
        e.tup(),
        str_(e),
        e.match_of(
            in_(e, "source"),
            "s",
            None,
            e.p("local", e.v("s")),
            e.p("konst", e.v("s")),
            e.p("func", e.v("s")),
            e.p("slot", e.mb.panic(e.s("wasm: value in a slot used as an operand"))),
            e.p("mem", e.mb.panic(e.s("wasm: memory place used as an operand"))),
            e.p("multi", e.mb.panic(e.s("wasm: tuple used as a single operand"))),
        ),
    )
    method(
        e,
        x,
        "wval",
        "flat",
        e.tup(),
        e.list_type(t(e, "wval")),
        e.seq(
            e.let("fl", e.list_new(lt(e, "wval"))),
            e.match_of(
                in_(e, "source"),
                "s",
                push(e, e.v("fl"), outer(e)),
                e.p(
                    "multi",
                    e.foreach(
                        e.v("s"),
                        "q",
                        e.foreach(e.call_m(e.v("q"), "flat", e.tup()), "q1", push(e, e.v("fl"), e.v("q1"))),
                    ),
                ),
            ),
            e.ret(e.v("fl")),
        ),
    )
    method(
        e,
        x,
        "wval",
        "mem",
        e.tup(),
        str_(e),
        e.match_of(
            in_(e, "source"),
            "s",
            None,
            e.p("slot", e.v("s")),
            e.p("local", e.mb.panic(e.s("wasm: temporary has no slot"))),
            e.p("konst", e.mb.panic(e.s("wasm: constant has no slot"))),
            e.p("func", e.mb.panic(e.s("wasm: function has no slot"))),
            e.p("mem", e.mb.panic(e.s("wasm: memory place has no slot"))),
            e.p("multi", e.mb.panic(e.s("wasm: tuple has no single slot"))),
        ),
    )
    method(
        e,
        x,
        "wval",
        "is_mem",
        e.tup(),
        e.mb.types_int(),
        e.match_of(in_(e, "source"), "s", e.int_of(0), e.p("slot", e.int_of(1))),
    )
    method(
        e,
        x,
        "wval",
        "is_addr",
        e.tup(),
        e.mb.types_int(),
        e.match_of(in_(e, "source"), "s", e.int_of(0), e.p("mem", e.int_of(1))),
    )
    method(
        e,
        x,
        "wval",
        "addr",
        e.tup(),
        e.rec(e.p("addr", str_(e)), e.p("offset", int_t(e))),
        e.match_of(
            in_(e, "source"),
            "s",
            e.mb.panic(e.s("wasm: value is not a memory place")),
            e.p("mem", e.rec(e.p("addr", e.fld(e.v("s"), "addr")), e.p("offset", e.fld(e.v("s"), "offset")))),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("wval"),
            e.mb.eval_value(),
            e.p("type", in_(e, "ty")),
            e.p("artifact_exporter", tm.artifact_exporter_impl(e, "wval")),
        )
    )
    accessor(e, x, "wtarget", "mod", _wmod_t(e))
    accessor(e, x, "wirctx", "xx", xx_t(e))
    accessor(e, x, "winst", "k", t(e, "winst_u"))
    accessor(e, x, "winst", "loc", _loc_opt_t(e))
    accessor(e, x, "wdep", "k", t(e, "wdep_u"))
    accessor(e, x, "wmeta", "k", t(e, "wmeta_u"))
    accessor(e, x, "wmod", "sip_key_id", tm.unique_t(e))
    accessor(e, x, "wmod", "sip_fn_id", tm.unique_t(e))
    for vo in ["wlocal", "wlabel", "winst", "wmod", "wdata", "wblock"]:
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))
    accessor(e, x, "wlocal", "name", str_(e))
    accessor(e, x, "wlocal", "ty", ty(e))
    accessor(e, x, "wlocal", "param", bool_t(e))
    accessor(e, x, "wlabel", "key", e.types_jump_key())
    accessor(e, x, "wlabel", "name", str_(e))
    accessor(e, x, "wdata", "name", str_(e))
    accessor(e, x, "wdata", "addr", int_t(e))
    accessor(e, x, "wdata", "bytes", e.list_type(int_t(e)))
    accessor(e, x, "wblock", "at", int_t(e))
    accessor(e, x, "wblock", "name", str_(e))

    method(e, x, "wmod", "xx", e.tup(), e.types_expr_context(), in_(e, "xx", "value"))
    x.append(
        e.method_impl(
            e.v("wmod"),
            "set_xx",
            e.types_expr_context(),
            e.option_type_none(),
            e.stage(e.mb.set(in_(e, "xx"), e.opt_some(e.types_expr_context(), e.v("arg")))),
        )
    )
    method(
        e,
        x,
        "wmod",
        "fresh_n",
        e.tup(),
        e.mb.types_int(),
        e.seq(e.let("n", in_(e, "n")), e.incr(in_(e, "n")), e.ret(e.v("n"))),
    )
    for kind in [["fresh", "$t"], ["slot", "$s"]]:
        method(
            e,
            x,
            "wmod",
            kind[0],
            ty(e),
            str_(e),
            e.seq(
                e.let("name", e.cat(e.s(kind[1]), to_str(e, e.call_m(outer(e), "fresh_n", e.tup())))),
                push(
                    e,
                    in_(e, "locals"),
                    mk(e, "wlocal", e.p("name", e.v("name")), e.p("ty", e.v("arg")), e.p("param", e.b(False))),
                ),
                e.ret(e.v("name")),
            ),
        )
    method(
        e,
        x,
        "wmod",
        "fresh_label",
        e.tup(),
        str_(e),
        e.cat(e.s("$L"), to_str(e, e.call_m(outer(e), "fresh_n", e.tup()))),
    )
    method(
        e,
        x,
        "wmod",
        "label_of",
        e.types_jump_key(),
        str_(e),
        e.seq(
            e.let("st", e.rec(e.p("name", e.dstr("")), e.p("hit", e.int_of(0)))),
            e.foreach(
                in_(e, "labels"),
                "l0",
                e.seq(
                    e.let("l", e.v("l0")),
                    e.if_only(
                        e.eq(e.call_m(e.v("l"), "key", e.tup()), e.v("arg")),
                        e.seq(
                            e.mb.set(e.fld(e.v("st"), "name"), e.call_m(e.v("l"), "name", e.tup())),
                            e.mb.set(e.fld(e.v("st"), "hit"), num(e, 1)),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "hit"), num(e, 0)),
                e.seq(
                    e.mb.set(e.fld(e.v("st"), "name"), e.call_m(outer(e), "fresh_label", e.tup())),
                    push(
                        e,
                        in_(e, "labels"),
                        mk(e, "wlabel", e.p("key", e.v("arg")), e.p("name", e.fld(e.v("st"), "name"))),
                    ),
                ),
            ),
            e.ret(e.fld(e.v("st"), "name")),
        ),
    )
    method(e, x, "wmod", "ir", ty(e), str_(e), _ir_fn(e, in_(e, "xx", "value"), e.v("arg")))
    method(
        e,
        x,
        "wmod",
        "width",
        ty(e),
        int_t(e),
        e.seq(
            e.if_only(
                has(e, in_(e, "xx", "value"), e.v("arg"), "wint"),
                e.ret(
                    e.mb.operator_div(
                        e.mb.operator_add(acc(e, in_(e, "xx", "value"), e.v("arg"), "wint", "bits"), e.int_of(7)),
                        e.int_of(8),
                    )
                ),
            ),
            e.if_only(has(e, in_(e, "xx", "value"), e.v("arg"), "wptr"), e.ret(e.int_of(4))),
            e.if_only(
                has(e, in_(e, "xx", "value"), e.v("arg"), "wfloat"),
                e.ret(e.mb.operator_div(acc(e, in_(e, "xx", "value"), e.v("arg"), "wfloat", "bits"), e.int_of(8))),
            ),
            e.mb.panic(e.cat(e.s("wasm: no memory width for "), ty_desc(e, e.v("arg")))),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "load_op",
        ty(e),
        str_(e),
        e.seq(
            e.if_only(has(e, in_(e, "xx", "value"), e.v("arg"), "wptr"), e.ret(e.dstr("i32.load"))),
            e.if_only(
                has(e, in_(e, "xx", "value"), e.v("arg"), "wfloat"),
                e.ret(
                    e.if_else(
                        e.eq(acc(e, in_(e, "xx", "value"), e.v("arg"), "wfloat", "bits"), num(e, 32)),
                        e.dstr("f32.load"),
                        e.dstr("f64.load"),
                    )
                ),
            ),
            e.if_only(
                e.not_(has(e, in_(e, "xx", "value"), e.v("arg"), "wint")),
                e.mb.panic(e.cat(e.s("wasm: no memory load for "), ty_desc(e, e.v("arg")))),
            ),
            e.let("bits", acc(e, in_(e, "xx", "value"), e.v("arg"), "wint", "bits")),
            e.let(
                "sx",
                e.if_else(acc(e, in_(e, "xx", "value"), e.v("arg"), "wint", "signed"), e.dstr("_s"), e.dstr("_u")),
            ),
            e.if_only(e.eq(e.v("bits"), num(e, 64)), e.ret(e.dstr("i64.load"))),
            e.if_only(e.eq(e.v("bits"), num(e, 32)), e.ret(e.dstr("i32.load"))),
            e.if_only(e.eq(e.v("bits"), num(e, 16)), e.ret(e.cat(e.s("i32.load16"), e.v("sx")))),
            e.ret(e.cat(e.s("i32.load8"), e.v("sx"))),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "store_op",
        ty(e),
        str_(e),
        e.seq(
            e.if_only(has(e, in_(e, "xx", "value"), e.v("arg"), "wptr"), e.ret(e.dstr("i32.store"))),
            e.if_only(
                has(e, in_(e, "xx", "value"), e.v("arg"), "wfloat"),
                e.ret(
                    e.if_else(
                        e.eq(acc(e, in_(e, "xx", "value"), e.v("arg"), "wfloat", "bits"), num(e, 32)),
                        e.dstr("f32.store"),
                        e.dstr("f64.store"),
                    )
                ),
            ),
            e.if_only(
                e.not_(has(e, in_(e, "xx", "value"), e.v("arg"), "wint")),
                e.mb.panic(e.cat(e.s("wasm: no memory store for "), ty_desc(e, e.v("arg")))),
            ),
            e.let("bits", acc(e, in_(e, "xx", "value"), e.v("arg"), "wint", "bits")),
            e.if_only(e.eq(e.v("bits"), num(e, 64)), e.ret(e.dstr("i64.store"))),
            e.if_only(e.eq(e.v("bits"), num(e, 32)), e.ret(e.dstr("i32.store"))),
            e.if_only(e.eq(e.v("bits"), num(e, 16)), e.ret(e.dstr("i32.store16"))),
            e.ret(e.dstr("i32.store8")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "alloc",
        e.rec(e.p("name", str_(e)), e.p("size", int_t(e))),
        str_(e),
        e.seq(
            e.let("dname", e.call_m(outer(e), "mint", a(e, "name"))),
            e.let(
                "addr",
                e.mb.operator_mul(
                    e.mb.operator_div(e.mb.operator_add(in_(e, "data_end"), e.int_of(15)), e.int_of(16)), e.int_of(16)
                ),
            ),
            push(
                e,
                in_(e, "data"),
                mk(e, "wdata", e.p("name", e.v("dname")), e.p("addr", e.v("addr")), e.p("bytes", e.list_new(int_t(e)))),
            ),
            e.mb.set(in_(e, "data_end"), e.mb.operator_add(e.v("addr"), a(e, "size"))),
            e.ret(e.v("dname")),
        ),
    )
    tm.module_defs_methods(e, x, "wmod", "wdef")
    # A zeroed block defined on first use (dependencies ask for it from every use site).
    # A data segment defined on first use (dependencies ask for it from every use site).
    method(
        e,
        x,
        "wmod",
        "data_once",
        e.rec(e.p("id", tm.unique_t(e)), e.p("name", str_(e)), e.p("bytes", e.list_type(int_t(e)))),
        str_(e),
        tm.def_once(
            e,
            outer(e),
            a(e, "id"),
            e.call_m(outer(e), "data", e.rec(e.p("name", a(e, "name")), e.p("bytes", a(e, "bytes")))),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "alloc_once",
        e.rec(e.p("id", tm.unique_t(e)), e.p("name", str_(e)), e.p("size", int_t(e))),
        str_(e),
        tm.def_once(
            e,
            outer(e),
            a(e, "id"),
            e.call_m(outer(e), "alloc", e.rec(e.p("name", a(e, "name")), e.p("size", a(e, "size")))),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "sig_ir",
        ty(e),
        str_(e),
        e.seq(
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                im0(e, "wfn", "params", asp(e, in_(e, "xx", "value"), e.v("arg"), "wfn")),
                "p",
                push(e, e.v("parts"), e.cat(e.s(" (param "), _ir_of(e, e.v("p")), e.s(")"))),
            ),
            e.let("ret", im0(e, "wfn", "ret", asp(e, in_(e, "xx", "value"), e.v("arg"), "wfn"))),
            e.if_only(
                e.not_(has(e, in_(e, "xx", "value"), e.v("ret"), "wvoid")),
                push(e, e.v("parts"), e.cat(e.s(" (result "), _ir_of(e, e.v("ret")), e.s(")"))),
            ),
            e.ret(e.join(e.v("parts"), "")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "addr",
        str_(e),
        int_t(e),
        e.seq(
            e.let("st", e.rec(e.p("addr", e.int_of(-1)))),
            e.foreach(
                in_(e, "data"),
                "d0",
                e.if_only(
                    e.eq(e.call_m(e.v("d0"), "name", e.tup()), e.v("arg")),
                    e.mb.set(e.fld(e.v("st"), "addr"), e.call_m(e.v("d0"), "addr", e.tup())),
                ),
            ),
            e.if_only(
                e.mb.operator_lt(e.fld(e.v("st"), "addr"), num(e, 0)),
                e.mb.panic(e.cat(e.s("wasm: no data segment named "), e.v("arg"))),
            ),
            e.ret(e.fld(e.v("st"), "addr")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "data",
        e.rec(e.p("name", str_(e)), e.p("bytes", e.list_type(int_t(e)))),
        str_(e),
        e.seq(
            e.let("dname", e.call_m(outer(e), "mint", a(e, "name"))),
            e.let(
                "addr",
                e.mb.operator_mul(
                    e.mb.operator_div(e.mb.operator_add(in_(e, "data_end"), e.int_of(3)), e.int_of(4)), e.int_of(4)
                ),
            ),
            push(
                e,
                in_(e, "data"),
                mk(e, "wdata", e.p("name", e.v("dname")), e.p("addr", e.v("addr")), e.p("bytes", a(e, "bytes"))),
            ),
            count_let(e, "n"),
            count_loop(e, "n", a(e, "bytes")),
            e.mb.set(in_(e, "data_end"), e.mb.operator_add(e.v("addr"), e.fld(e.v("n"), "v"))),
            e.ret(e.v("dname")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "data_push",
        e.rec(
            e.p("bytes", e.list_type(int_t(e))),
            e.p("width", int_t(e)),
            e.p("min", e.types_double()),
            e.p("max", e.types_double()),
            e.p("value", e.types_double()),
        ),
        e.list_type(int_t(e)),
        e.seq(
            e.let("d", a(e, "value")),
            e.if_only(
                e.not_(e.eq(e.mb.as_(e.mb.as_(e.v("d"), e.mb.types_long()), e.types_double()), e.v("d"))),
                e.mb.panic(e.cat(e.s("wasm: data element "), to_str(e, e.v("d")), e.s(" is not integral"))),
            ),
            e.if_only(
                or_b(e, e.mb.operator_lt(e.v("d"), a(e, "min")), e.mb.operator_gt(e.v("d"), a(e, "max"))),
                e.mb.panic(e.cat(e.s("wasm: data element "), to_str(e, e.v("d")), e.s(" is out of range"))),
            ),
            e.let("lv", e.rec(e.p("v", e.mb.as_(e.v("d"), e.mb.types_long())))),
            e.let("k", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                e.list_new(
                    int_t(e),
                    e.int_of(0),
                    e.int_of(1),
                    e.int_of(2),
                    e.int_of(3),
                    e.int_of(4),
                    e.int_of(5),
                    e.int_of(6),
                    e.int_of(7),
                ),
                "_",
                e.if_only(
                    e.mb.operator_lt(e.fld(e.v("k"), "i"), a(e, "width")),
                    e.seq(
                        push(
                            e,
                            a(e, "bytes"),
                            e.mb.as_(
                                e.mb.operator_and(e.fld(e.v("lv"), "v"), e.mb.as_(num(e, 255), e.mb.types_long())),
                                int_t(e),
                            ),
                        ),
                        e.mb.set(
                            e.fld(e.v("lv"), "v"),
                            e.mb.operator_ushr(e.fld(e.v("lv"), "v"), e.mb.as_(num(e, 8), int_t(e))),
                        ),
                        e.incr(e.fld(e.v("k"), "i")),
                    ),
                ),
            ),
            e.ret(a(e, "bytes")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "cstr",
        str_(e),
        str_(e),
        e.seq(
            e.let("bytes", e.list_new(int_t(e))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                push(e, e.v("bytes"), e.mb.operator_and(e.mb.as_(e.v("b"), e.mb.types_int()), num(e, 255))),
            ),
            push(e, e.v("bytes"), e.int_of(0)),
            e.ret(
                e.call_m(
                    outer(e),
                    "data",
                    e.rec(
                        e.p("name", e.s("str")),
                        e.p("bytes", e.v("bytes")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.method_impl(
            e.v("wmod"),
            "meta",
            t(e, "wmeta"),
            e.option_type_none(),
            e.stage(
                e.match_of(
                    e.call_m(e.v("arg"), "k", e.tup()),
                    "m",
                    None,
                    e.p(
                        "dep",
                        e.seq(
                            e.let(
                                "key",
                                e.match_of(
                                    e.call_m(e.fld(e.v("m"), "dep"), "k", e.tup()),
                                    "p",
                                    None,
                                    e.p(
                                        "import",
                                        e.cat(
                                            e.s("import "),
                                            _p(e, "module"),
                                            e.s(" "),
                                            _p(e, "name"),
                                            e.call_m(outer(e), "sig_ir", _p(e, "ty")),
                                        ),
                                    ),
                                ),
                            ),
                            e.let("dup", e.rec(e.p("v", e.int_of(0)))),
                            e.foreach(
                                in_(e, "dep_keys"),
                                "k0",
                                e.if_only(e.eq(e.v("k0"), e.v("key")), e.mb.set(e.fld(e.v("dup"), "v"), num(e, 1))),
                            ),
                            e.if_only(
                                e.eq(e.fld(e.v("dup"), "v"), num(e, 0)),
                                e.seq(push(e, in_(e, "dep_keys"), e.v("key")), push(e, in_(e, "meta"), e.v("arg"))),
                            ),
                        ),
                    ),
                    e.p("other", push(e, in_(e, "meta"), e.v("arg"))),
                )
            ),
        )
    )
    _def_render_state(e, x)
    method(e, x, "wmod", "frame", loc_t(e), int_t(e), e.call_m(in_(e, "frames"), "index", e.v("arg")))
    method(
        e,
        x,
        "wmod",
        "render_insts",
        e.rec(e.p("insts", _insts_t(e)), e.p("lstart", int_t(e))),
        e.rec(e.p("lines", e.list_type(str_(e))), e.p("used", e.list_type(str_(e)))),
        e.seq(
            e.let(
                "r",
                mk(
                    e,
                    "wrs",
                    e.p("mod", outer(e)),
                    e.p("out", e.list_new(str_(e))),
                    e.p("used", e.list_new(str_(e))),
                    e.p("uses", e.list_new(lt(e, "wuse"))),
                    e.p("pn", e.list_new(lt(e, "wpend"))),
                    e.p("sets", e.list_new(lt(e, "wblock"))),
                    e.p("blocks", e.list_new(lt(e, "wblock"))),
                    e.p(
                        "regions",
                        e.list_new(
                            lt(e, "wregion"),
                            mk(
                                e,
                                "wregion",
                                e.p("depth", e.int_of(0)),
                                e.p("start", e.int_of(0)),
                                e.p("valued", e.b(False)),
                                e.p("closed", e.int_of(0)),
                            ),
                        ),
                    ),
                    e.p("n", e.int_of(0)),
                    e.p("h", e.int_of(0)),
                    e.p("depth", e.int_of(0)),
                    e.p("cur", e.opt_none(loc_t(e))),
                ),
            ),
            e.let("li", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                in_(e, "locals"),
                "l",
                e.seq(
                    e.if_only(
                        e.mb.operator_ge(e.fld(e.v("li"), "i"), a(e, "lstart")),
                        _rs(e, "add_use", e.call_m(e.v("l"), "name", e.tup())),
                    ),
                    e.incr(e.fld(e.v("li"), "i")),
                ),
            ),
            e.foreach(
                a(e, "insts"),
                "c0",
                e.match_of(
                    e.call_m(e.v("c0"), "k", e.tup()),
                    "p",
                    e.seq(),
                    e.p("if", _count_use(e, _p(e, "cond"))),
                    e.p("binop", e.seq(_count_use(e, _p(e, "a")), _count_use(e, _p(e, "b")))),
                    e.p("cmp", e.seq(_count_use(e, _p(e, "a")), _count_use(e, _p(e, "b")))),
                    e.p("unop", _count_use(e, _p(e, "a"))),
                    e.p("conv", _count_use(e, _p(e, "a"))),
                    e.p("load", _count_name(e, _p(e, "name"))),
                    e.p("mload", _count_use(e, _p(e, "addr"))),
                    e.p("store", _count_use(e, _p(e, "val"))),
                    e.p("mstore", e.seq(_count_name(e, _p(e, "addr")), _count_use(e, _p(e, "val")))),
                    e.p("mgrow", _count_use(e, _p(e, "a"))),
                    e.p("msize", e.seq()),
                    e.p("trap", e.seq()),
                    e.p(
                        "mcopy",
                        e.seq(_count_use(e, _p(e, "dst")), _count_use(e, _p(e, "src")), _count_use(e, _p(e, "n"))),
                    ),
                    e.p(
                        "mfill",
                        e.seq(_count_use(e, _p(e, "dst")), _count_use(e, _p(e, "val")), _count_use(e, _p(e, "n"))),
                    ),
                    e.p("push", _count_use(e, _p(e, "val"))),
                    e.p("call", e.foreach(_p(e, "args"), "ax", _count_use(e, e.v("ax")))),
                    e.p("ret", e.if_only(e.fld(_p(e, "val"), "is_some"), _count_use(e, e.fld(_p(e, "val"), "value")))),
                ),
            ),
            e.foreach(
                a(e, "insts"),
                "i0",
                e.seq(
                    _rs(e, "at", e.call_m(e.v("i0"), "loc", e.tup())),
                    e.match_of(
                        e.call_m(e.v("i0"), "k", e.tup()),
                        "p",
                        None,
                        e.p("label", _rs(e, "label", _p(e, "name"))),
                        e.p(
                            "br",
                            _rs(
                                e,
                                "control",
                                e.rec(e.p("delta", e.int_of(0)), e.p("text", e.cat(e.s("br "), _p(e, "name")))),
                            ),
                        ),
                        e.p(
                            "if",
                            e.seq(
                                _rs_ops(e, _p(e, "cond")),
                                _rs(
                                    e,
                                    "open_if",
                                    e.rec(
                                        e.p(
                                            "text",
                                            e.if_else(
                                                e.fld(_p(e, "ty"), "is_some"),
                                                e.cat(
                                                    e.s("if (result "), _ir_of(e, e.fld(_p(e, "ty"), "value")), e.s(")")
                                                ),
                                                e.dstr("if"),
                                            ),
                                        ),
                                        e.p("valued", e.fld(_p(e, "ty"), "is_some")),
                                    ),
                                ),
                            ),
                        ),
                        e.p("loop", _rs(e, "open_loop", _p(e, "name"))),
                        e.p("else", _rs0(e, "else_")),
                        e.p("end", _rs0(e, "end_if")),
                        e.p(
                            "mgrow",
                            e.seq(
                                _rs_ops(e, _p(e, "a")),
                                _rs_line(e, 0, e.s("memory.grow")),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p("msize", e.seq(_rs_line(e, 1, e.s("memory.size")), _rs(e, "set_local", _p(e, "res")))),
                        e.p("trap", _rs_line(e, 0, e.s("unreachable"))),
                        e.p(
                            "mfill",
                            e.seq(
                                _rs_ops(e, _p(e, "dst"), _p(e, "val"), _p(e, "n")), _rs_line(e, -3, e.s("memory.fill"))
                            ),
                        ),
                        e.p(
                            "mcopy",
                            e.seq(
                                _rs_ops(e, _p(e, "dst"), _p(e, "src"), _p(e, "n")), _rs_line(e, -3, e.s("memory.copy"))
                            ),
                        ),
                        e.p(
                            "binop",
                            e.seq(
                                _rs_ops(e, _p(e, "a"), _p(e, "b")),
                                _rs_line(e, -1, _ir_of(e, _wv_ty(e, _p(e, "a"))), e.s("."), _p(e, "op")),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p(
                            "cmp",
                            e.seq(
                                _rs_ops(e, _p(e, "a"), _p(e, "b")),
                                _rs_line(e, -1, _ir_of(e, _wv_ty(e, _p(e, "a"))), e.s("."), _p(e, "op")),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p(
                            "unop",
                            e.seq(
                                _rs_ops(e, _p(e, "a")),
                                _rs_line(e, 0, _ir_of(e, _wv_ty(e, _p(e, "a"))), e.s("."), _p(e, "op")),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p(
                            "conv",
                            e.seq(
                                _rs_ops(e, _p(e, "a")), _rs_line(e, 0, _p(e, "op")), _rs(e, "set_local", _p(e, "res"))
                            ),
                        ),
                        e.p(
                            "load",
                            e.seq(
                                _rs_ops(e, _wval_local(e, _p(e, "ty"), _p(e, "name"))),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p(
                            "mload",
                            e.seq(
                                _rs_ops(e, _p(e, "addr")),
                                _rs_line(
                                    e,
                                    0,
                                    e.call_m(outer(e), "load_op", _p(e, "ty")),
                                    e.s(" offset="),
                                    to_str(e, _p(e, "offset")),
                                ),
                                _rs(e, "set_local", _p(e, "res")),
                            ),
                        ),
                        e.p("store", e.seq(_rs_ops(e, _p(e, "val")), _rs(e, "set_local", _p(e, "name")))),
                        e.p(
                            "mstore",
                            e.seq(
                                _rs_ops(e, _wval_local(e, _int_ty(e, "i32"), _p(e, "addr")), _p(e, "val")),
                                _rs_line(
                                    e,
                                    -2,
                                    e.call_m(outer(e), "store_op", _p(e, "ty")),
                                    e.s(" offset="),
                                    to_str(e, _p(e, "offset")),
                                ),
                            ),
                        ),
                        e.p("push", _rs_ops(e, _p(e, "val"))),
                        e.p("setl", _rs(e, "set_local", _p(e, "name"))),
                        e.p("meta", e.seq()),
                        e.p(
                            "call",
                            e.seq(
                                count_let(e, "na"),
                                e.foreach(
                                    _p(e, "args"),
                                    "ax",
                                    e.foreach(_wv_flat(e, e.v("ax")), "_", e.incr(e.fld(e.v("na"), "v"))),
                                ),
                                _rs(e, "ops", _p(e, "args")),
                                _rs(
                                    e,
                                    "call",
                                    e.rec(
                                        e.p("fn", e.call_m(_p(e, "fn"), "ref", e.tup())),
                                        e.p("nargs", e.fld(e.v("na"), "v")),
                                        e.p("res", _p(e, "res")),
                                    ),
                                ),
                            ),
                        ),
                        e.p(
                            "ret",
                            e.seq(
                                e.if_only(e.fld(_p(e, "val"), "is_some"), _rs_ops(e, e.fld(_p(e, "val"), "value"))),
                                _rs(e, "control", e.rec(e.p("delta", e.int_of(0)), e.p("text", e.s("return")))),
                            ),
                        ),
                    ),
                ),
            ),
            e.ret(_rs0(e, "finish")),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "render",
        e.tup(),
        _render_t(e, t(e, "wmeta")),
        e.seq(
            e.let("out", e.list_new(str_(e))),
            push(e, e.v("out"), e.s("(module")),
            e.foreach(
                in_(e, "meta"),
                "m0",
                e.match_of(
                    e.call_m(e.v("m0"), "k", e.tup()),
                    "m",
                    None,
                    e.p(
                        "dep",
                        e.match_of(
                            e.call_m(e.fld(e.v("m"), "dep"), "k", e.tup()),
                            "p",
                            None,
                            e.p(
                                "import",
                                push(
                                    e,
                                    e.v("out"),
                                    e.cat(
                                        e.s('  (import "'),
                                        _p(e, "module"),
                                        e.s('" "'),
                                        _p(e, "name"),
                                        e.s('" (func $'),
                                        _p(e, "name"),
                                        e.call_m(outer(e), "sig_ir", _p(e, "ty")),
                                        e.s("))"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.p("other", e.seq()),
                ),
            ),
            push(
                e,
                e.v("out"),
                e.cat(
                    e.s('  (memory (export "memory") '),
                    to_str(e, e.mb.operator_add(e.mb.operator_div(in_(e, "data_end"), e.int_of(65536)), e.int_of(1))),
                    e.s(")"),
                ),
            ),
            e.let("printable", printable_bytes_map),
            e.foreach(
                in_(e, "data"),
                "d0",
                e.seq(
                    e.let("parts", e.list_new(str_(e))),
                    e.foreach(
                        e.call_m(e.v("d0"), "bytes", e.tup()),
                        "b",
                        push(e, e.v("parts"), e.call_m(e.v("printable"), "get", to_str(e, e.v("b")))),
                    ),
                    count_let(e, "nb"),
                    count_loop(e, "nb", e.v("parts")),
                    e.if_only(
                        e.mb.operator_gt(e.fld(e.v("nb"), "v"), num(e, 0)),
                        push(
                            e,
                            e.v("out"),
                            e.cat(
                                e.s("  (data (i32.const "),
                                to_str(e, e.call_m(e.v("d0"), "addr", e.tup())),
                                e.s(') "'),
                                e.join(e.v("parts"), ""),
                                e.s('")'),
                            ),
                        ),
                    ),
                ),
            ),
            e.foreach(in_(e, "funcs"), "f", push(e, e.v("out"), e.v("f"))),
            e.foreach(in_(e, "exports"), "l", push(e, e.v("out"), e.cat(e.s("  "), e.v("l")))),
            push(e, e.v("out"), e.s(")")),
            e.ret(
                e.rec(
                    e.p("wat", e.cat(e.join(e.v("out"), "\n"), e.s("\n"))),
                    e.p("meta", in_(e, "meta")),
                    e.p("frames", e.call_m(in_(e, "frames"), "render", e.tup())),
                )
            ),
        ),
    )
    method(
        e,
        x,
        "wmod",
        "func",
        e.rec(
            e.p("name", str_(e)),
            e.p("params", e.list_type(str_(e))),
            e.p("ty", ty(e)),
            e.p("body", e.mb.types_expr()),
            e.p("public", bool_t(e)),
        ),
        str_(e),
        body(
            e,
            # A public function keeps its name and is exported under it (the name is its interface); any other
            # function's name is a hint, minted into a module-unique symbol.
            e.let("fname", e.if_else(a(e, "public"), a(e, "name"), e.call_m(outer(e), "mint", a(e, "name")))),
            e.if_only(
                a(e, "public"),
                push(
                    e,
                    in_(e, "exports"),
                    e.cat(e.s('(export "'), a(e, "name"), e.s('" (func $'), e.v("fname"), e.s("))")),
                ),
            ),
            e.let("loc", e.call(e.eval_builtin("expr_loc"), a(e, "body"))),
            e.let("ptypes", acc(e, in_(e, "xx", "value"), a(e, "ty"), "wfn", "params")),
            e.let("fret", acc(e, in_(e, "xx", "value"), a(e, "ty"), "wfn", "ret")),
            count_let(e, "lstart"),
            count_loop(e, "lstart", in_(e, "locals")),
            e.let("pnames", e.map_new(str_(e), str_(e))),
            e.let("ni", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                a(e, "params"),
                "pn",
                e.seq(
                    e.call_m(e.v("pnames"), "put", e.tup(to_str(e, e.fld(e.v("ni"), "i")), e.v("pn"))),
                    e.incr(e.fld(e.v("ni"), "i")),
                ),
            ),
            e.let("out", _insts_new(e)),
            e.let("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
            e.let("pi", e.rec(e.p("i", e.int_of(0)))),
            e.let("sig", e.list_new(str_(e))),
            e.let("ak", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                e.v("ptypes"),
                "pty",
                e.seq(
                    # A tuple parameter is one wasm parameter per flattened component.
                    e.let("slots", e.list_new(str_(e))),
                    e.foreach(
                        hf_rec(e, "h_flat_types", e.p("xx", in_(e, "xx", "value")), e.p("ty", e.v("pty"))),
                        "fty",
                        e.seq(
                            e.let("an", e.cat(e.s("$a"), to_str(e, e.fld(e.v("ak"), "i")))),
                            e.incr(e.fld(e.v("ak"), "i")),
                            push(e, e.v("slots"), e.v("an")),
                            push(
                                e,
                                e.v("sig"),
                                e.cat(e.s(" (param "), e.v("an"), e.s(" "), _ir_of(e, e.v("fty")), e.s(")")),
                            ),
                            push(
                                e,
                                in_(e, "locals"),
                                mk(e, "wlocal", e.p("name", e.v("an")), e.p("ty", e.v("fty")), e.p("param", e.b(True))),
                            ),
                        ),
                    ),
                    e.call_m(
                        e.v("entries"),
                        "put",
                        e.tup(
                            e.call_m(e.v("pnames"), "get", to_str(e, e.fld(e.v("pi"), "i"))),
                            _must_v(
                                e,
                                bim(
                                    e,
                                    e.mb.eval_aspect_initial_bind(),
                                    "initial_bind",
                                    lookup_v(e, in_(e, "xx", "value"), e.v("pty"), e.mb.eval_aspect_initial_bind()),
                                    e.rec(
                                        e.p("xx", in_(e, "xx", "value")),
                                        e.p("loc", e.v("loc")),
                                        e.p("slot", mk(e, "wparam", e.p("ty", e.v("pty")), e.p("slots", e.v("slots")))),
                                    ),
                                ),
                                "parameter binding",
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("pi"), "i")),
                ),
            ),
            e.let("is_void", has(e, in_(e, "xx", "value"), e.v("fret"), "wvoid")),
            e.if_only(
                e.not_(e.v("is_void")),
                push(e, e.v("sig"), e.cat(e.s(" (result "), _ir_of(e, e.v("fret")), e.s(")"))),
            ),
            e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
            e.let("sc", e.call(e.eval_builtin("scope"), e.rec(e.p("vx", e.v("vx")), e.p("entries", e.v("entries"))))),
            e.let("tgt", mk(e, "wtarget", e.p("mod", outer(e)))),
            e.let(
                "ctx",
                e.call(
                    e.eval_builtin("expr_context"),
                    e.rec(
                        e.p("scope", e.v("sc")),
                        e.p("target", e.mb.as_(e.v("tgt"), e.mb.eval_target())),
                        e.p("vx", e.v("vx")),
                        e.p("exception_type", str_(e)),
                    ),
                ),
            ),
            e.let(
                "r",
                _must_v(
                    e,
                    e.call(e.mb.eval_const_eval_function(), e.rec(e.p("xx", e.v("ctx")), e.p("staged", a(e, "body")))),
                    "compile failed",
                ),
            ),
            e.let("ended", cve_ended(e, e.v("r"))),
            e.if_only(
                and_b(e, e.not_(e.v("ended")), and_b(e, e.v("is_void"), _is_wasm(e, e.v("ctx"), e.v("r")))),
                e.match_of(
                    e.eresult_err(e.mb.eval_value(), e.v("loc"), e.s("void function body yields a value")),
                    "__x",
                    None,
                    e.p("ok", e.mb.panic(e.s("unreachable"))),
                    e.p("errs", tm.panic_errs(e, TARGET, "compile failed", e.v("__x"))),
                ),
            ),
            e.let("need_cast", and_b(e, e.not_(e.v("ended")), e.not_(e.v("is_void")))),
            e.let(
                "v",
                _must_v(
                    e,
                    e.if_else(
                        e.v("need_cast"),
                        try_er(e, _operand(e, e.v("ctx"), e.v("loc"), outer(e), e.v("fret"), e.v("r")), cve_t(e)),
                        ok_cve(e, e.v("r")),
                    ),
                    "compile failed",
                ),
            ),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            # The callee owns its parameters: when the body falls through, drop them, last first (an exit inside the
            # body dropped them through its cleanup chain). The drops are collected by position and emitted in reverse.
            e.if_only(
                e.not_(e.v("ended")),
                e.seq(
                    e.let("drops", e.map_new(str_(e), code_t(e))),
                    count_let(e, "pn"),
                    count_loop(e, "pn", e.v("entries")),
                    # The bindings as they stand after the body (a parameter's setter may have replaced its
                    # binding: an owned parameter moved out is dropped as moved), read off the scope's levels by
                    # the parameters' names.
                    e.let("cur", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
                    e.foreach(
                        e.fld(e.v("sc"), "levels"),
                        "lv",
                        e.match_of(
                            e.v("lv"),
                            "l",
                            e.seq(),
                            e.p(
                                "entry",
                                e.if_only(
                                    e.fld(e.fld(e.v("l"), "name"), "is_some"),
                                    e.call_m(
                                        e.v("cur"),
                                        "put",
                                        e.tup(e.fld(e.fld(e.v("l"), "name"), "value"), e.fld(e.v("l"), "binding")),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let("di", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("entries"),
                        "en",
                        e.seq(
                            e.call_m(
                                e.v("drops"),
                                "put",
                                e.tup(
                                    to_str(e, e.fld(e.v("di"), "v")),
                                    _must_v(
                                        e,
                                        bim(
                                            e,
                                            e.mb.eval_binding(),
                                            "drop",
                                            e.call_m(e.v("cur"), "get", e.fld(e.v("en"), "key")),
                                            e.rec(e.p("xx", e.v("ctx")), e.p("loc", e.v("loc"))),
                                        ),
                                        "parameter drop",
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("di"), "v")),
                        ),
                    ),
                    e.let("dj", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("entries"),
                        "_",
                        e.seq(
                            _append_code(
                                e,
                                e.v("out"),
                                e.call_m(
                                    e.v("drops"),
                                    "get",
                                    to_str(
                                        e,
                                        e.mb.operator_sub(
                                            e.mb.operator_sub(e.fld(e.v("pn"), "v"), e.int_of(1)), e.fld(e.v("dj"), "v")
                                        ),
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("dj"), "v")),
                        ),
                    ),
                ),
            ),
            e.if_only(
                e.v("need_cast"),
                push(
                    e,
                    e.v("out"),
                    _inst(e, e.v("loc"), "ret", e.p("val", e.opt_some(lt(e, "wval"), _wval_of(e, e.v("v"))))),
                ),
            ),
            e.foreach(
                e.v("out"),
                "d0",
                e.match_of(
                    e.call_m(e.v("d0"), "k", e.tup()),
                    "p",
                    e.seq(),
                    e.p("meta", e.call_m(outer(e), "meta", _p(e, "meta"))),
                ),
            ),
            e.let(
                "rendered",
                e.call_m(
                    outer(e),
                    "render_insts",
                    e.rec(e.p("insts", e.v("out")), e.p("lstart", e.fld(e.v("lstart"), "v"))),
                ),
            ),
            e.let("all", e.list_new(str_(e))),
            e.let("li", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                in_(e, "locals"),
                "l",
                e.seq(
                    e.if_only(
                        and_b(
                            e,
                            e.mb.operator_ge(e.fld(e.v("li"), "i"), e.fld(e.v("lstart"), "v")),
                            e.not_(e.call_m(e.v("l"), "param", e.tup())),
                        ),
                        e.seq(
                            e.let("hit", e.rec(e.p("v", e.int_of(0)))),
                            e.foreach(
                                e.fld(e.v("rendered"), "used"),
                                "u",
                                e.if_only(
                                    e.eq(e.v("u"), e.call_m(e.v("l"), "name", e.tup())),
                                    e.mb.set(e.fld(e.v("hit"), "v"), num(e, 1)),
                                ),
                            ),
                            e.if_only(
                                e.eq(e.fld(e.v("hit"), "v"), num(e, 1)),
                                push(
                                    e,
                                    e.v("all"),
                                    e.cat(
                                        e.s("    (local "),
                                        e.call_m(e.v("l"), "name", e.tup()),
                                        e.s(" "),
                                        _ir_of(e, e.call_m(e.v("l"), "ty", e.tup())),
                                        e.s(")"),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("li"), "i")),
                ),
            ),
            e.foreach(e.fld(e.v("rendered"), "lines"), "l", push(e, e.v("all"), e.cat(e.s("    "), e.v("l")))),
            push(
                e,
                in_(e, "funcs"),
                e.cat(
                    e.s("  "),
                    _annotation(e, e.call_m(outer(e), "frame", e.v("loc"))),
                    e.s("\n  (func $"),
                    e.v("fname"),
                    e.join(e.v("sig"), ""),
                    e.s("\n"),
                    e.join(e.v("all"), "\n"),
                    e.s("\n  )"),
                ),
            ),
            e.ret(e.cat(e.s("$"), e.v("fname"))),
        ),
    )

    _value_aspects(e, x, "wt_int", e.mb.operator_div(in_(e, "bits"), num(e, 8)), _int_hash_body(e))
    _value_aspects(e, x, "wt_float", e.mb.operator_div(in_(e, "bits"), num(e, 8)), None)
    _value_aspects(e, x, "wt_ptr", num(e, 4), _ptr_hash_body(e))
    self_type(
        e,
        x,
        "wt_int",
        e.cat(e.if_else(in_(e, "signed"), e.dstr("i"), e.dstr("u")), to_str(e, in_(e, "bits"))),
        e.aspect_dispatch(
            lv(e, "wtype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "wint_id"),
            lv(e, "size_id"),
            lv(e, "hash_id"),
            lv(e, "eq_id"),
            op_id(e, "add"),
            op_id(e, "sub"),
            op_id(e, "mul"),
            op_id(e, "div"),
            op_id(e, "mod"),
            op_id(e, "and"),
            op_id(e, "or"),
            op_id(e, "xor"),
            op_id(e, "shl"),
            op_id(e, "shr"),
            op_id(e, "ushr"),
            op_id(e, "eq"),
            op_id(e, "ne"),
            op_id(e, "lt"),
            op_id(e, "le"),
            op_id(e, "gt"),
            op_id(e, "ge"),
            op_id(e, "neg"),
            op_id(e, "bit_not"),
            asp_id(e, "bind"),
            asp_id(e, "set"),
            asp_id(e, "field"),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    or_b(
                        e,
                        is_const(e, xx(e), src_type(e)),
                        and_b(
                            e,
                            has(e, xx(e), src_type(e), "wint"),
                            and_b(
                                e,
                                e.mb.operator_ge(acc(e, xx(e), src_type(e), "wint", "min"), in_(e, "min")),
                                e.mb.operator_le(acc(e, xx(e), src_type(e), "wint", "max"), in_(e, "max")),
                            ),
                        ),
                    ),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(
                is_const(e, xx(e), e.v("st")),
                e.seq(
                    e.let(
                        "d",
                        e.call(
                            e.eval_builtin("const_numeric_to_double"),
                            e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                    ),
                    e.let("l", e.mb.as_(e.v("d"), e.mb.types_long())),
                    e.if_only(
                        e.not_(e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d"))),
                        ret_m(e, err_cve(e, loc(e), "integer literal is not integral")),
                    ),
                    e.if_only(
                        or_b(e, e.mb.operator_lt(e.v("d"), in_(e, "min")), e.mb.operator_gt(e.v("d"), in_(e, "max"))),
                        ret_m(e, err_cve(e, loc(e), "integer literal out of range")),
                    ),
                    ret_m(
                        e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _wval_konst(e, outer(e), to_str(e, e.v("l")))))
                    ),
                ),
            ),
            e.if_only(
                e.eq(_wide(e, xx(e), e.v("st")), _wide(e, xx(e), outer(e))), ret_m(e, _retag(e, a(e, "cv"), outer(e)))
            ),
            e.ret(
                _conv(
                    e,
                    _conv_name(
                        e,
                        outer(e),
                        "extend",
                        e.v("st"),
                        e.if_else(
                            e.eq(cv_bits(e, e.v("st"), "wint"), num(e, 1)),
                            dfalse(e),
                            acc(e, xx(e), e.v("st"), "wint", "signed"),
                        ),
                    ),
                    a(e, "cv"),
                    outer(e),
                )
            ),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wint"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "wint", "bits"), in_(e, "bits")),
                        e.eq(acc(e, xx(e), a(e, "other"), "wint", "signed"), in_(e, "signed")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("wt_int"),
            t(e, "wtype"),
            e.p("ir", e.if_else(e.eq(in_(e, "bits"), num(e, 64)), e.dstr("i64"), e.dstr("i32"))),
            e.p("ssa", outer(e)),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wt_int"),
            t(e, "wint"),
            e.p("bits", in_(e, "bits")),
            e.p("signed", in_(e, "signed")),
            e.p("min", in_(e, "min")),
            e.p("max", in_(e, "max")),
        )
    )
    op(e, x, "wt_int", "add", try_er(e, _binop_body(e, e.s("add")), cve_t(e)))
    op(e, x, "wt_int", "sub", try_er(e, _binop_body(e, e.s("sub")), cve_t(e)))
    op(e, x, "wt_int", "mul", try_er(e, _binop_body(e, e.s("mul")), cve_t(e)))
    op(e, x, "wt_int", "div", try_er(e, _binop_body(e, _signed_op(e, "div_s", "div_u")), cve_t(e)))
    op(e, x, "wt_int", "mod", try_er(e, _binop_body(e, _signed_op(e, "rem_s", "rem_u")), cve_t(e)))
    op(e, x, "wt_int", "and", try_er(e, _binop_body(e, e.s("and")), cve_t(e)))
    op(e, x, "wt_int", "or", try_er(e, _binop_body(e, e.s("or")), cve_t(e)))
    op(e, x, "wt_int", "xor", try_er(e, _binop_body(e, e.s("xor")), cve_t(e)))
    op(e, x, "wt_int", "shl", try_er(e, _binop_body(e, e.s("shl")), cve_t(e)))
    op(e, x, "wt_int", "shr", try_er(e, _binop_body(e, _signed_op(e, "shr_s", "shr_u")), cve_t(e)))
    op(e, x, "wt_int", "ushr", try_er(e, _binop_body(e, e.s("shr_u")), cve_t(e)))
    op(e, x, "wt_int", "eq", try_er(e, _cmp_body(e, e.s("eq")), cve_t(e)))
    op(e, x, "wt_int", "ne", try_er(e, _cmp_body(e, e.s("ne")), cve_t(e)))
    op(e, x, "wt_int", "lt", try_er(e, _cmp_body(e, _signed_op(e, "lt_s", "lt_u")), cve_t(e)))
    op(e, x, "wt_int", "le", try_er(e, _cmp_body(e, _signed_op(e, "le_s", "le_u")), cve_t(e)))
    op(e, x, "wt_int", "gt", try_er(e, _cmp_body(e, _signed_op(e, "gt_s", "gt_u")), cve_t(e)))
    op(e, x, "wt_int", "ge", try_er(e, _cmp_body(e, _signed_op(e, "ge_s", "ge_u")), cve_t(e)))
    x.append(
        e.impl_interface(
            e.v("wt_int"),
            op_iface(e, "neg"),
            e.p(
                "neg",
                body(
                    e,
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_binop",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", outer(e)),
                                e.p("op", e.s("sub")),
                                e.p("a", _literal(e, outer(e), e.s("0"))),
                                e.p("b", a(e, "base")),
                                e.p("res", outer(e)),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wt_int"),
            op_iface(e, "bit_not"),
            e.p(
                "bit_not",
                body(
                    e,
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_binop",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", outer(e)),
                                e.p("op", e.s("xor")),
                                e.p("a", a(e, "base")),
                                e.p(
                                    "b",
                                    _literal(
                                        e,
                                        outer(e),
                                        e.if_else(e.eq(in_(e, "bits"), num(e, 1)), e.dstr("1"), e.dstr("-1")),
                                    ),
                                ),
                                e.p("res", outer(e)),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )
    _bind_impl(e, x, "wt_int")
    _set_impl(e, x, "wt_int")

    self_type(
        e,
        x,
        "wt_float",
        e.cat(e.s("f"), to_str(e, in_(e, "bits"))),
        e.aspect_dispatch(
            lv(e, "wtype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "wfloat_id"),
            lv(e, "size_id"),
            lv(e, "eq_id"),
            op_id(e, "add"),
            op_id(e, "sub"),
            op_id(e, "mul"),
            op_id(e, "div"),
            op_id(e, "eq"),
            op_id(e, "ne"),
            op_id(e, "lt"),
            op_id(e, "le"),
            op_id(e, "gt"),
            op_id(e, "ge"),
            op_id(e, "neg"),
            asp_id(e, "bind"),
            asp_id(e, "set"),
            asp_id(e, "field"),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    or_b(
                        e,
                        is_const(e, xx(e), src_type(e)),
                        or_b(
                            e,
                            and_b(
                                e,
                                has(e, xx(e), src_type(e), "wfloat"),
                                e.mb.operator_lt(src_bits(e, "wfloat"), in_(e, "bits")),
                            ),
                            and_b(
                                e,
                                has(e, xx(e), src_type(e), "wint"),
                                and_b(
                                    e,
                                    e.mb.operator_ge(
                                        acc(e, xx(e), src_type(e), "wint", "min"),
                                        e.if_else(
                                            e.eq(in_(e, "bits"), num(e, 64)),
                                            e.mb.as_(num(e, -9007199254740992.0), e.types_double()),
                                            e.mb.as_(num(e, -16777216.0), e.types_double()),
                                        ),
                                    ),
                                    e.mb.operator_le(
                                        acc(e, xx(e), src_type(e), "wint", "max"),
                                        e.if_else(
                                            e.eq(in_(e, "bits"), num(e, 64)),
                                            e.mb.as_(num(e, 9007199254740992.0), e.types_double()),
                                            e.mb.as_(num(e, 16777216.0), e.types_double()),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(
                is_const(e, xx(e), e.v("st")),
                e.seq(
                    e.let(
                        "d",
                        e.call(
                            e.eval_builtin("const_numeric_to_double"),
                            e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                    ),
                    e.let(
                        "s",
                        e.if_else(
                            e.eq(in_(e, "bits"), num(e, 64)),
                            to_str(e, e.v("d")),
                            to_str(e, e.mb.as_(e.mb.as_(e.v("d"), e.types_float()), e.types_double())),
                        ),
                    ),
                    ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _wval_konst(e, outer(e), e.v("s"))))),
                ),
            ),
            e.if_only(
                has(e, xx(e), e.v("st"), "wint"),
                ret_m(
                    e,
                    _conv(
                        e,
                        _conv_name(e, outer(e), "convert", e.v("st"), acc(e, xx(e), e.v("st"), "wint", "signed")),
                        a(e, "cv"),
                        outer(e),
                    ),
                ),
            ),
            e.ret(_conv(e, _conv_name(e, outer(e), "promote", e.v("st"), None), a(e, "cv"), outer(e))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wfloat"),
                    e.eq(acc(e, xx(e), a(e, "other"), "wfloat", "bits"), in_(e, "bits")),
                )
            ),
        ),
    )
    _conv_methods(e, x)
    x.append(
        e.impl_interface(
            e.v("wt_float"),
            t(e, "wtype"),
            e.p("ir", e.if_else(e.eq(in_(e, "bits"), num(e, 32)), e.dstr("f32"), e.dstr("f64"))),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("wt_float"), t(e, "wfloat"), e.p("bits", in_(e, "bits"))))
    op(e, x, "wt_float", "add", try_er(e, _binop_body(e, e.s("add")), cve_t(e)))
    op(e, x, "wt_float", "sub", try_er(e, _binop_body(e, e.s("sub")), cve_t(e)))
    op(e, x, "wt_float", "mul", try_er(e, _binop_body(e, e.s("mul")), cve_t(e)))
    op(e, x, "wt_float", "div", try_er(e, _binop_body(e, e.s("div")), cve_t(e)))
    op(e, x, "wt_float", "eq", try_er(e, _cmp_body(e, e.s("eq")), cve_t(e)))
    op(e, x, "wt_float", "ne", try_er(e, _cmp_body(e, e.s("ne")), cve_t(e)))
    op(e, x, "wt_float", "lt", try_er(e, _cmp_body(e, e.s("lt")), cve_t(e)))
    op(e, x, "wt_float", "le", try_er(e, _cmp_body(e, e.s("le")), cve_t(e)))
    op(e, x, "wt_float", "gt", try_er(e, _cmp_body(e, e.s("gt")), cve_t(e)))
    op(e, x, "wt_float", "ge", try_er(e, _cmp_body(e, e.s("ge")), cve_t(e)))
    x.append(
        e.impl_interface(
            e.v("wt_float"),
            op_iface(e, "neg"),
            e.p(
                "neg",
                body(
                    e,
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_unop",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", outer(e)),
                                e.p("op", e.s("neg")),
                                e.p("a", a(e, "base")),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )
    _bind_impl(e, x, "wt_float")
    _set_impl(e, x, "wt_float")

    self_type(
        e,
        x,
        "wt_ptr",
        e.cat(e.s("ptr("), bim0(e, ty(e), "desc", in_(e, "pointee")), e.s(")")),
        e.aspect_dispatch(
            lv(e, "wtype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "wptr_id"),
            lv(e, "size_id"),
            lv(e, "hash_id"),
            lv(e, "eq_id"),
            op_id(e, "eq"),
            op_id(e, "ne"),
            op_id(e, "lt"),
            op_id(e, "le"),
            op_id(e, "gt"),
            op_id(e, "ge"),
            asp_id(e, "bind"),
            asp_id(e, "set"),
            asp_id(e, "field"),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    # A pointer literal (a constant address); any other pointer or an integer only through the
                    # named conversions `ptr_cast`, `ptr_to_int` and `int_to_ptr`.
                    is_const(e, xx(e), src_type(e)),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(
                is_const(e, xx(e), e.v("st")),
                e.seq(
                    e.let(
                        "d",
                        e.call(
                            e.eval_builtin("const_numeric_to_double"),
                            e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                    ),
                    e.let("l", e.mb.as_(e.v("d"), e.mb.types_long())),
                    e.if_only(
                        or_b(
                            e,
                            e.not_(e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d"))),
                            or_b(
                                e,
                                e.mb.operator_lt(e.v("d"), num(e, 0)),
                                e.mb.operator_gt(e.v("d"), num(e, 4294967295.0)),
                            ),
                        ),
                        ret_m(e, err_cve(e, loc(e), "pointer literal is not a 32 bit address")),
                    ),
                    ret_m(
                        e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _wval_konst(e, outer(e), to_str(e, e.v("l")))))
                    ),
                ),
            ),
            e.ret(err_cve(e, loc(e), e.cat(e.s("wasm: no cast to a pointer from "), ty_desc(e, e.v("st"))))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wptr"),
                    is_equal(e, xx(e), in_(e, "pointee"), acc(e, xx(e), a(e, "other"), "wptr", "pointee")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("wt_ptr"), t(e, "wtype"), e.p("ir", e.s("i32")), e.p("ssa", outer(e))))
    x.append(e.impl_interface(e.v("wt_ptr"), t(e, "wptr"), e.p("pointee", in_(e, "pointee"))))
    op(e, x, "wt_ptr", "eq", try_er(e, _cmp_body(e, e.s("eq")), cve_t(e)))
    op(e, x, "wt_ptr", "ne", try_er(e, _cmp_body(e, e.s("ne")), cve_t(e)))
    op(e, x, "wt_ptr", "lt", try_er(e, _cmp_body(e, e.s("lt_u")), cve_t(e)))
    op(e, x, "wt_ptr", "le", try_er(e, _cmp_body(e, e.s("le_u")), cve_t(e)))
    op(e, x, "wt_ptr", "gt", try_er(e, _cmp_body(e, e.s("gt_u")), cve_t(e)))
    op(e, x, "wt_ptr", "ge", try_er(e, _cmp_body(e, e.s("ge_u")), cve_t(e)))
    _bind_impl(e, x, "wt_ptr")
    _set_impl(e, x, "wt_ptr")
    x.append(
        e.impl_interface(
            e.v("wt_ptr"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let(
                        "pv",
                        unwrap_cve_m(
                            e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), outer(e), a(e, "value")), cve_t(e))
                        ),
                    ),
                    e.let("i32", _int_ty(e, "i32")),
                    e.let("w", e.call_m(_xmod(e), "width", in_(e, "pointee"))),
                    # A constant index folds into the access's `offset=`: the place is the pointer itself.
                    e.if_only(
                        and_b(
                            e,
                            e.not_(is_runtime(e, a(e, "key"))),
                            is_const(e, xx(e), cve_type(e, a(e, "key"))),
                        ),
                        e.seq(
                            e.let(
                                "ki",
                                e.call(
                                    e.eval_builtin("const_numeric_to_double"),
                                    e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "key")))),
                                ),
                            ),
                            e.if_only(
                                or_b(
                                    e,
                                    e.not_(e.eq(e.mb.as_(e.mb.as_(e.v("ki"), int_t(e)), e.types_double()), e.v("ki"))),
                                    e.mb.operator_lt(e.v("ki"), num(e, 0)),
                                ),
                                ret_m(e, err_cve(e, loc(e), "pointer index must be a non-negative integer")),
                            ),
                            e.let("pi", unwrap_cve_m(e, _retag(e, e.v("pv"), e.v("i32")))),
                            # A place's address is a local: the pointer is set into a fresh one (folded back onto
                            # the stack when used once).
                            e.let("out", _insts_new(e)),
                            _append_code(e, e.v("out"), cve_code(e, e.v("pi"))),
                            e.let("r", _fresh(e, _xmod(e), e.v("i32"))),
                            push(e, e.v("out"), _store_inst(e, loc(e), _wval_of(e, e.v("pi")), e.v("r"))),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        _code_of(e, e.v("out")),
                                        mk(
                                            e,
                                            "wval",
                                            e.p("ty", in_(e, "pointee")),
                                            e.p(
                                                "source",
                                                e.call(
                                                    e.lower_v("ws_mem"),
                                                    e.rec(
                                                        e.p("addr", e.v("r")),
                                                        e.p(
                                                            "offset",
                                                            e.mb.as_(e.mb.operator_mul(e.v("ki"), e.v("w")), int_t(e)),
                                                        ),
                                                    ),
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let(
                        "iv",
                        unwrap_cve_m(
                            e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), e.v("i32"), a(e, "key")), cve_t(e))
                        ),
                    ),
                    e.let(
                        "scaled",
                        unwrap_cve_m(
                            e,
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_binop",
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p("mod", _xmod(e)),
                                    e.p("ty", e.v("i32")),
                                    e.p("op", e.s("mul")),
                                    e.p("a", e.v("iv")),
                                    e.p(
                                        "b",
                                        cv_of(e, code_none(e, loc(e)), _wval_konst(e, e.v("i32"), to_str(e, e.v("w")))),
                                    ),
                                    e.p("res", e.v("i32")),
                                ),
                                cve_t(e),
                            ),
                        ),
                    ),
                    e.let(
                        "addr",
                        unwrap_cve_m(
                            e,
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_binop",
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p("mod", _xmod(e)),
                                    e.p("ty", e.v("i32")),
                                    e.p("op", e.s("add")),
                                    e.p("a", unwrap_cve_m(e, _retag(e, e.v("pv"), e.v("i32")))),
                                    e.p("b", e.v("scaled")),
                                    e.p("res", e.v("i32")),
                                ),
                                cve_t(e),
                            ),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("addr")),
                                mk(
                                    e,
                                    "wval",
                                    e.p("ty", in_(e, "pointee")),
                                    e.p(
                                        "source",
                                        e.call(
                                            e.lower_v("ws_mem"),
                                            e.rec(
                                                e.p("addr", e.call_m(_wval_of(e, e.v("addr")), "ref", e.tup())),
                                                e.p("offset", e.int_of(0)),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )

    self_type(
        e,
        x,
        "wt_fn",
        e.s("fn"),
        e.aspect_dispatch(lv(e, "wtype_id"), lv(e, "wfn_id"), asp_id(e, "function")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "wfn")), ret_m(e, dfalse(e))),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "ret"), im0(e, "wfn", "ret", asp(e, xx(e), a(e, "other"), "wfn")))),
                ret_m(e, dfalse(e)),
            ),
            e.let("om", e.map_new(str_(e), ty(e))),
            e.let("on", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                im0(e, "wfn", "params", asp(e, xx(e), a(e, "other"), "wfn")),
                "p",
                e.seq(
                    e.call_m(e.v("om"), "put", e.tup(to_str(e, e.fld(e.v("on"), "v")), e.v("p"))),
                    e.incr(e.fld(e.v("on"), "v")),
                ),
            ),
            e.let("st", e.rec(e.p("i", e.int_of(0)), e.p("same", e.int_of(1)))),
            e.foreach(
                in_(e, "params"),
                "p",
                e.seq(
                    e.if_only(
                        e.mb.operator_lt(e.fld(e.v("st"), "i"), e.fld(e.v("on"), "v")),
                        e.if_only(
                            e.not_(
                                is_equal(
                                    e, xx(e), e.v("p"), e.call_m(e.v("om"), "get", to_str(e, e.fld(e.v("st"), "i")))
                                )
                            ),
                            e.mb.set(e.fld(e.v("st"), "same"), num(e, 0)),
                        ),
                    ),
                    e.incr(e.fld(e.v("st"), "i")),
                ),
            ),
            e.ret(
                and_b(
                    e,
                    e.eq(e.fld(e.v("st"), "i"), e.fld(e.v("on"), "v")),
                    e.eq(e.fld(e.v("st"), "same"), num(e, 1)),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("wt_fn"),
            t(e, "wtype"),
            e.p(
                "ir",
                e.seq(
                    e.let("parts", e.list_new(str_(e))),
                    e.foreach(
                        in_(e, "params"),
                        "p",
                        push(e, e.v("parts"), e.cat(e.s(" (param "), _ir_fn(e, _ir_arg_xx(e), e.v("p")), e.s(")"))),
                    ),
                    e.if_only(
                        e.not_(has(e, _ir_arg_xx(e), in_(e, "ret"), "wvoid")),
                        push(
                            e,
                            e.v("parts"),
                            e.cat(e.s(" (result "), _ir_fn(e, _ir_arg_xx(e), in_(e, "ret")), e.s(")")),
                        ),
                    ),
                    e.ret(e.cat(e.s("(func"), e.join(e.v("parts"), ""), e.s(")"))),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("wt_fn"), t(e, "wfn"), e.p("params", in_(e, "params")), e.p("ret", in_(e, "ret"))))
    x.append(
        e.impl_interface(
            e.v("wt_fn"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "function"))),
                    e.let("fnv", _wval_of(e, a(e, "function"))),
                    e.let("args", e.list_new(lt(e, "wval"))),
                    e.let("pmap", e.map_new(str_(e), ty(e))),
                    e.let("pn", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        in_(e, "params"),
                        "p",
                        e.seq(
                            e.call_m(e.v("pmap"), "put", e.tup(to_str(e, e.fld(e.v("pn"), "v")), e.v("p"))),
                            e.incr(e.fld(e.v("pn"), "v")),
                        ),
                    ),
                    e.let("elems", e.list_new(e.mb.types_cve())),
                    e.let("argv", a(e, "argument")),
                    e.let("single", e.eq(e.fld(e.v("pn"), "v"), num(e, 1))),
                    e.if_only(e.v("single"), push(e, e.v("elems"), e.v("argv"))),
                    e.if_only(
                        e.not_(e.v("single")),
                        e.seq(
                            e.if_only(
                                e.not_(cve_has(e, e.v("argv"))),
                                ret_m(e, err_cve(e, loc(e), "call argument has no value")),
                            ),
                            e.let("tk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "tuple"))),
                            e.if_only(
                                e.not_(e.fld(e.v("tk"), "is_some")),
                                ret_m(e, err_cve(e, loc(e), "call arguments must be a tuple")),
                            ),
                            e.foreach(
                                bim(
                                    e,
                                    asp_iface(e, "tuple"),
                                    "take_elements",
                                    e.fld(e.v("tk"), "value"),
                                    e.rec(
                                        e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("argv")))
                                    ),
                                ),
                                "er",
                                e.seq(e.let("ec0", unwrap_cve_m(e, e.v("er"))), push(e, e.v("elems"), e.v("ec0"))),
                            ),
                        ),
                    ),
                    e.let("st", e.rec(e.p("i", e.int_of(0)))),
                    e.foreach(
                        e.v("elems"),
                        "ec",
                        e.seq(
                            e.if_only(
                                e.mb.operator_ge(e.fld(e.v("st"), "i"), e.fld(e.v("pn"), "v")),
                                ret_m(e, err_cve(e, loc(e), "too many call arguments")),
                            ),
                            e.let(
                                "v",
                                unwrap_cve_m(
                                    e,
                                    try_er(
                                        e,
                                        _operand(
                                            e,
                                            xx(e),
                                            loc(e),
                                            _xmod(e),
                                            e.call_m(e.v("pmap"), "get", to_str(e, e.fld(e.v("st"), "i"))),
                                            e.v("ec"),
                                        ),
                                        cve_t(e),
                                    ),
                                ),
                            ),
                            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                            push(e, e.v("args"), _wval_of(e, e.v("v"))),
                            e.incr(e.fld(e.v("st"), "i")),
                        ),
                    ),
                    e.if_only(
                        e.mb.operator_lt(e.fld(e.v("st"), "i"), e.fld(e.v("pn"), "v")),
                        ret_m(e, err_cve(e, loc(e), "too few call arguments")),
                    ),
                    e.if_only(
                        has(e, xx(e), in_(e, "ret"), "wvoid"),
                        e.seq(
                            push(
                                e,
                                e.v("out"),
                                _inst(
                                    e,
                                    loc(e),
                                    "call",
                                    e.p("res", e.list_new(str_(e))),
                                    e.p("fn", e.v("fnv")),
                                    e.p("args", e.v("args")),
                                ),
                            ),
                            ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                        ),
                    ),
                    e.let("rv", _fresh_val(e, _xmod(e), in_(e, "ret"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "call",
                            e.p("res", _names_of(e, e.v("rv"))),
                            e.p("fn", e.v("fnv")),
                            e.p("args", e.v("args")),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), e.v("rv")))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

    _tuple_type(e, x)
    self_type(
        e,
        x,
        "wt_void",
        e.s("void"),
        e.aspect_dispatch(lv(e, "wtype_id"), lv(e, "wvoid_id")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "wvoid"))),
    )
    x.append(
        e.impl_interface(
            e.v("wt_void"),
            t(e, "wtype"),
            e.p("ir", e.mb.panic(e.s("wasm: void has no value type"))),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("wt_void"), t(e, "wvoid")))

    self_type(
        e,
        x,
        "wt_slot",
        e.cat(bim0(e, ty(e), "desc", in_(e, "base")), e.s("@"), e.join(_names_of(e, in_(e, "slot")), " ")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), lv(e, "wslot_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "wtype_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, "base"), a(e, "key")),
        ),
        body(e, e.ret(type_can_cast_from(e, xx(e), loc(e), in_(e, "base"), src_type(e)))),
        body(
            e,
            e.let(
                "v",
                unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), in_(e, "base"), a(e, "cv")), cve_t(e))),
            ),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            _store_to(e, loc(e), e.v("out"), _wval_of(e, e.v("v")), in_(e, "slot")),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e,
                        _code_of(e, e.v("out")),
                        bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", in_(e, "slot"), outer(e)),
                    ),
                )
            ),
        ),
        body(e, e.ret(type_can_cast_from(e, xx(e), loc(e), a(e, "dest_type"), in_(e, "base")))),
        body(
            e,
            e.let(
                "loaded",
                hf_rec(
                    e,
                    "h_mat",
                    e.p("loc", loc(e)),
                    e.p("mod", _xmod(e)),
                    e.p(
                        "cv",
                        cv_of(
                            e,
                            cve_code(e, a(e, "cv")),
                            bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", in_(e, "slot"), in_(e, "base")),
                        ),
                    ),
                ),
            ),
            e.ret(cast_value(e, xx(e), loc(e), a(e, "dest_type"), e.v("loaded"))),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wslot"),
                    and_b(
                        e,
                        e.eq(
                            e.join(_names_of(e, acc(e, xx(e), a(e, "other"), "wslot", "slot")), " "),
                            e.join(_names_of(e, in_(e, "slot")), " "),
                        ),
                        is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "wslot", "base")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("wt_slot"),
            t(e, "wtype"),
            e.p("ir", _ir_fn(e, _ir_arg_xx(e), in_(e, "base"))),
            e.p("ssa", in_(e, "base")),
        )
    )
    x.append(e.impl_interface(e.v("wt_slot"), t(e, "wslot"), e.p("base", in_(e, "base")), e.p("slot", in_(e, "slot"))))
    bin_ops = [
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "and",
        "or",
        "xor",
        "shl",
        "shr",
        "ushr",
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
    ]
    un_ops = ["neg", "bit_not"]
    ids = []
    ids.append(lv(e, "wgtype_m_id"))
    ids.append(asp_id(e, "function"))
    ids.append(asp_id(e, "field"))
    for op_ in bin_ops:
        ids.append(op_id(e, op_))
    for op_ in un_ops:
        ids.append(op_id(e, op_))
    self_type(
        e,
        x,
        "wt_global",
        e.cat(e.s("global("), bim0(e, ty(e), "desc", in_(e, "base")), e.s(")")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(*ids)),
        can_cast_from_self(e),
        cast_from_self(e),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "dest_type")),
                    or_b(
                        e,
                        is_equal(e, xx(e), in_(e, "base"), a(e, "dest_type")),
                        type_can_cast_from(e, xx(e), loc(e), a(e, "dest_type"), in_(e, "base")),
                    ),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                cast_value(
                    e,
                    xx(e),
                    loc(e),
                    a(e, "dest_type"),
                    hf_rec(e, "h_gval", e.p("mod", _xmod(e)), e.p("cv", a(e, "cv")), e.p("base", in_(e, "base"))),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wgtype_m"),
                    is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "wgtype_m", "base")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("wt_global"), t(e, "wgtype_m"), e.p("base", in_(e, "base"))))
    rt_lift_impl(e, x, "wt_global")
    rt_bind_impl(e, x, "wt_global", e.mb.types_string())
    rt_use_impl(e, x, "wt_global")
    for op_ in bin_ops:
        x.append(
            e.impl_interface(
                e.v("wt_global"),
                op_iface(e, op_),
                e.p(
                    op_,
                    body(
                        e,
                        e.ret(
                            bim(
                                e,
                                op_iface(e, op_),
                                op_,
                                lookup_v(e, xx(e), in_(e, "base"), op_iface(e, op_)),
                                e.rec(
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p(
                                        "base",
                                        hf_rec(
                                            e,
                                            "h_gval",
                                            e.p("mod", _xmod(e)),
                                            e.p("cv", a(e, "base")),
                                            e.p("base", in_(e, "base")),
                                        ),
                                    ),
                                    e.p("reference", a(e, "reference")),
                                ),
                            )
                        ),
                    ),
                ),
            )
        )
    for op_ in un_ops:
        x.append(
            e.impl_interface(
                e.v("wt_global"),
                op_iface(e, op_),
                e.p(
                    op_,
                    body(
                        e,
                        e.ret(
                            bim(
                                e,
                                op_iface(e, op_),
                                op_,
                                lookup_v(e, xx(e), in_(e, "base"), op_iface(e, op_)),
                                e.rec(
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p(
                                        "base",
                                        hf_rec(
                                            e,
                                            "h_gval",
                                            e.p("mod", _xmod(e)),
                                            e.p("cv", a(e, "base")),
                                            e.p("base", in_(e, "base")),
                                        ),
                                    ),
                                ),
                            )
                        ),
                    ),
                ),
            )
        )
    x.append(
        e.impl_interface(
            e.v("wt_global"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "function"),
                            "call",
                            lookup_v(e, xx(e), in_(e, "base"), asp_iface(e, "function")),
                            e.rec(
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p(
                                    "function",
                                    hf_rec(
                                        e,
                                        "h_gval",
                                        e.p("mod", _xmod(e)),
                                        e.p("cv", a(e, "function")),
                                        e.p("base", in_(e, "base")),
                                    ),
                                ),
                                e.p("argument", a(e, "argument")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wt_global"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "field",
                            lookup_v(e, xx(e), in_(e, "base"), asp_iface(e, "field")),
                            e.rec(
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p(
                                    "value",
                                    hf_rec(
                                        e,
                                        "h_gval",
                                        e.p("mod", _xmod(e)),
                                        e.p("cv", a(e, "value")),
                                        e.p("base", in_(e, "base")),
                                    ),
                                ),
                                e.p("key", a(e, "key")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    self_type(
        e,
        x,
        "wt_import",
        e.cat(
            e.s("import("),
            in_(e, "module"),
            e.s("."),
            in_(e, "name"),
            e.s(": "),
            bim0(e, ty(e), "desc", in_(e, "base")),
            e.s(")"),
        ),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "wimport_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "dest_type")))),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(err_cve(e, loc(e), "wasm import cannot be cast")),
        ),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "wimport_m")), ret_m(e, dfalse(e))),
            e.ret(
                and_b(
                    e,
                    e.eq(in_(e, "module"), acc(e, xx(e), a(e, "other"), "wimport_m", "module")),
                    and_b(
                        e,
                        e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), "wimport_m", "name")),
                        is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "wimport_m", "base")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("wt_import"),
            t(e, "wimport_m"),
            e.p("module", in_(e, "module")),
            e.p("name", in_(e, "name")),
            e.p("base", in_(e, "base")),
        )
    )
    rt_lift_impl(e, x, "wt_import")
    rt_bind_impl(e, x, "wt_import", e.mb.types_string())
    rt_use_impl(e, x, "wt_import")
    import_dep = mk(
        e,
        "wdep",
        e.p(
            "k",
            e.call(
                e.lower_v("wd_import"),
                e.rec(e.p("module", in_(e, "module")), e.p("name", in_(e, "name")), e.p("ty", in_(e, "base"))),
            ),
        ),
    )
    import_meta = _inst_bare(
        e, "meta", e.p("meta", mk(e, "wmeta", e.p("k", e.call(e.lower_v("wm_dep"), e.rec(e.p("dep", import_dep))))))
    )
    x.append(
        e.impl_interface(
            e.v("wt_import"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(e, e.v("out"), import_meta),
                    e.let(
                        "rv",
                        unwrap_cve_m(
                            e,
                            bim(
                                e,
                                asp_iface(e, "function"),
                                "call",
                                lookup_v(e, xx(e), in_(e, "base"), asp_iface(e, "function")),
                                e.rec(
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p(
                                        "function",
                                        hf_rec(
                                            e,
                                            "h_gval",
                                            e.p("mod", _xmod(e)),
                                            e.p("cv", a(e, "function")),
                                            e.p("base", in_(e, "base")),
                                        ),
                                    ),
                                    e.p("argument", a(e, "argument")),
                                ),
                            ),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("rv"))),
                    e.if_only(
                        cve_has(e, e.v("rv")),
                        ret_m(e, ok_cve(e, cv_of(e, _code_of(e, e.v("out")), cve_value(e, e.v("rv"))))),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

    accessor(e, x, "wbinding", "ty", ty(e))
    accessor(e, x, "wbinding", "slot", _wval_t(e))
    _binding_impl(e, x, "wbinding", cv_of(e, a(e, "code"), in_(e, "slot")), binding_drop_body(e))
    _binding_impl(
        e,
        x,
        "wbinding_none",
        e.mb.panic(e.s("wasm: unit binding has no value")),
        e.eresult_ok(e.mb.types_code(), code_none(e, loc(e))),
    )

    marker_type(e, x, "wunit", "unit", "wunit_m", e.aspect_dispatch(lv(e, "wunit_m_id"), asp_id(e, "bind")))
    x.append(e.impl_interface(e.v("wunit"), t(e, "wunit_m")))
    x.append(
        e.impl_interface(
            e.v("wunit"),
            e.mb.eval_aspect_bind(),
            e.p(
                "bind",
                e.eresult_ok(
                    e.mb.types_bind_result(),
                    e.call(
                        e.mb.eval_bind_result(),
                        e.rec(e.p("code", code_none(e, loc(e))), e.p("binding", mk_arg(e, "wbinding_none", e.tup()))),
                    ),
                ),
            ),
        )
    )

    # `loop`: iterated with foreach, it runs its body until a `return` to an enclosing label leaves it,
    # as the llvm target's loop does.
    self_type(
        e,
        x,
        "wloop_t",
        e.s("loop"),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "wloop_m_id"), asp_id(e, "iterable"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "wloop_m"))),
    )
    rt_lift_impl(e, x, "wloop_t")
    rt_bind_impl(e, x, "wloop_t", lt(e, "wloop_t"))
    rt_use_impl(e, x, "wloop_t")
    x.append(e.impl_interface(e.v("wloop_t"), t(e, "wloop_m")))
    x.append(
        e.impl_interface(
            e.v("wloop_t"),
            asp_iface(e, "iterable"),
            e.p("element_type", mk_arg(e, "wunit", e.tup())),
            e.p("loop_binding", mk_arg(e, "wbinding_none", e.tup())),
            e.p(
                "element_access",
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        e.call(
                            e.eval_builtin("value_object_const"),
                            e.rec(e.p("type", mk_arg(e, "wunit", e.tup())), e.p("data", e.tup())),
                        ),
                    ),
                ),
            ),
            e.p(
                "foreach",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "base"))),
                    e.let("head", e.call_m(e.v("mod"), "fresh_label", e.tup())),
                    push(e, e.v("out"), _inst_bare(e, "loop", e.p("name", e.v("head")))),
                    _append_code(e, e.v("out"), a(e, "element_bind")),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "body"))),
                    e.if_only(e.not_(cve_ended(e, a(e, "body"))), push(e, e.v("out"), _br_inst(e, e.v("head")))),
                    push(e, e.v("out"), _inst0_bare(e, "end")),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )

    # `memory_grow(pages) -> i32` and `memory_copy((dst, src, n))`: the bulk memory instructions as callables.
    # Their operands are retagged to i32, so pointers pass as they are.
    for obj, marker in [
        ["wmem_grow", "wmem_grow_m"],
        ["wmem_copy", "wmem_copy_m"],
        ["wmem_size", "wmem_size_m"],
        ["wmem_fill", "wmem_fill_m"],
    ]:
        self_type(
            e,
            x,
            obj,
            e.s(obj),
            rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, marker + "_id"), asp_id(e, "function"))),
            can_cast_from_self(e),
            cast_from_self(e),
            no_cast_to(e),
            cast_to_panic(e),
            body(e, e.ret(has(e, xx(e), a(e, "other"), marker))),
        )
        rt_lift_impl(e, x, obj)
        rt_bind_impl(e, x, obj, lt(e, obj))
        rt_use_impl(e, x, obj)
        x.append(e.impl_interface(e.v(obj), t(e, marker)))

    # The trap as a callable type: its function value (the unit cast to it) emits `unreachable`.
    self_type(
        e,
        x,
        "wtrap",
        e.s("trap"),
        e.aspect_dispatch(lv(e, "wtrap_m_id"), asp_id(e, "function"), asp_id(e, "bind")),
        tm.can_cast_from_unit(e),
        tm.cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "wtrap_m"))),
    )
    x.append(e.impl_interface(e.v("wtrap"), t(e, "wtrap_m")))
    x.append(e.impl_interface(e.v("wtrap"), e.mb.eval_aspect_bind(), e.p("bind", tm.bind_empty(e, "webinding"))))

    def _i32_operand(cv):
        return e.seq(
            e.let("cty", cve_type(e, cv)),
            e.let(
                "oty",
                e.if_else(
                    is_const(e, xx(e), e.v("cty")),
                    e.mb.as_(_int_ty(e, "i32"), ty(e)),
                    e.if_else(
                        has(e, xx(e), e.v("cty"), "wgtype_m"),
                        acc(e, xx(e), e.v("cty"), "wgtype_m", "base"),
                        e.v("cty"),
                    ),
                ),
            ),
            e.let(
                "v",
                unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), e.v("mod"), e.v("oty"), cv), cve_t(e))),
            ),
            e.let("w", unwrap_cve_m(e, _retag(e, e.v("v"), _int_ty(e, "i32")))),
            _append_code(e, e.v("out"), cve_code(e, e.v("w"))),
            e.ret(_wval_of(e, e.v("w"))),
        )

    x.append(
        e.impl_interface(
            e.v("wmem_grow"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("pages", _i32_operand(a(e, "argument"))),
                    e.let("r", _fresh(e, e.v("mod"), _int_ty(e, "i32"))),
                    push(e, e.v("out"), _inst(e, loc(e), "mgrow", e.p("res", e.v("r")), e.p("a", e.v("pages")))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _wval_local(e, _int_ty(e, "i32"), e.v("r"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wmem_size"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("r", _fresh(e, e.v("mod"), _int_ty(e, "i32"))),
                    push(e, e.v("out"), _inst(e, loc(e), "msize", e.p("res", e.v("r")))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _wval_local(e, _int_ty(e, "i32"), e.v("r"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wtrap"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(e, e.v("out"), _inst0(e, loc(e), "trap")),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("wmem_copy"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("argv", a(e, "argument")),
                    e.if_only(
                        e.not_(cve_has(e, e.v("argv"))),
                        ret_m(e, err_cve(e, loc(e), "memory.copy arguments have no value")),
                    ),
                    e.let("tk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("tk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "memory.copy takes a tuple of destination, source and length")),
                    ),
                    e.let("st", e.rec(e.p("i", e.int_of(0)))),
                    e.let("ops", e.map_new(str_(e), lt(e, "wval"))),
                    e.foreach(
                        bim(
                            e,
                            asp_iface(e, "tuple"),
                            "take_elements",
                            e.fld(e.v("tk"), "value"),
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("argv")))),
                        ),
                        "er",
                        e.seq(
                            e.let("ec", unwrap_cve_m(e, e.v("er"))),
                            e.call_m(
                                e.v("ops"), "put", e.tup(to_str(e, e.fld(e.v("st"), "i")), _i32_operand(e.v("ec")))
                            ),
                            e.incr(e.fld(e.v("st"), "i")),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("st"), "i"), num(e, 3))),
                        ret_m(e, err_cve(e, loc(e), "memory.copy takes a tuple of destination, source and length")),
                    ),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "mcopy",
                            e.p("dst", e.call_m(e.v("ops"), "get", e.s("0"))),
                            e.p("src", e.call_m(e.v("ops"), "get", e.s("1"))),
                            e.p("n", e.call_m(e.v("ops"), "get", e.s("2"))),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

    self_type(
        e,
        x,
        "wgfn_t",
        e.cat(e.s("wasm global definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, lt(e, "wmod"), e.aspect_dispatch(lv(e, "wgfn_m_id"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wgfn_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "wgfn_m", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "wgfn_t")
    rt_bind_impl(e, x, "wgfn_t", lt(e, "wmod"))
    rt_use_impl(e, x, "wgfn_t")
    x.append(
        e.impl_interface(
            e.v("wmem_fill"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("argv", a(e, "argument")),
                    e.if_only(
                        e.not_(cve_has(e, e.v("argv"))),
                        ret_m(e, err_cve(e, loc(e), "memory.copy arguments have no value")),
                    ),
                    e.let("tk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("tk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "memory.copy takes a tuple of destination, source and length")),
                    ),
                    e.let("st", e.rec(e.p("i", e.int_of(0)))),
                    e.let("ops", e.map_new(str_(e), lt(e, "wval"))),
                    e.foreach(
                        bim(
                            e,
                            asp_iface(e, "tuple"),
                            "take_elements",
                            e.fld(e.v("tk"), "value"),
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("argv")))),
                        ),
                        "er",
                        e.seq(
                            e.let("ec", unwrap_cve_m(e, e.v("er"))),
                            e.call_m(
                                e.v("ops"), "put", e.tup(to_str(e, e.fld(e.v("st"), "i")), _i32_operand(e.v("ec")))
                            ),
                            e.incr(e.fld(e.v("st"), "i")),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("st"), "i"), num(e, 3))),
                        ret_m(e, err_cve(e, loc(e), "memory.copy takes a tuple of destination, source and length")),
                    ),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "mfill",
                            e.p("dst", e.call_m(e.v("ops"), "get", e.s("0"))),
                            e.p("val", e.call_m(e.v("ops"), "get", e.s("1"))),
                            e.p("n", e.call_m(e.v("ops"), "get", e.s("2"))),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

    self_type(
        e,
        x,
        "wgfn_t",
        e.cat(e.s("wasm global definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, lt(e, "wmod"), e.aspect_dispatch(lv(e, "wgfn_m_id"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "wgfn_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "wgfn_m", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "wgfn_t")
    rt_bind_impl(e, x, "wgfn_t", lt(e, "wmod"))
    rt_use_impl(e, x, "wgfn_t")
    x.append(e.impl_interface(e.v("wgfn_t"), t(e, "wgfn_m"), e.p("kind", in_(e, "kind"))))
    tm.method(
        e,
        x,
        "wgfn_t",
        "call",
        e.rec(e.p("xx", e.types_expr_context()), e.p("loc", loc_t(e)), e.p("argument", cve_t(e))),
        e.mb.call(e.mb.types_eresult(), cve_t(e)),
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))),
                ret_m(e, err_cve(e, loc(e), "wasm global definition argument has no value")),
            ),
            e.let("st", cve_type(e, e.v("argv"))),
            e.let("rk", lookup(e, xx(e), e.v("st"), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "wasm global definition argument must be a record")),
            ),
            e.let(
                "want",
                e.if_else(
                    _wgfn_is(e, "cstr_fn"),
                    e.list_new(str_(e), e.s("mod"), e.s("value")),
                    e.if_else(
                        _wgfn_is(e, "import_fn"),
                        e.list_new(str_(e), e.s("module"), e.s("name"), e.s("ty")),
                        e.if_else(
                            or_b(e, _wgfn_is(e, "func_fn"), _wgfn_is(e, "export_fn")),
                            e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("params"), e.s("ty"), e.s("body")),
                            e.if_else(
                                _wgfn_is(e, "alloc_fn"),
                                e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("size")),
                                e.if_else(
                                    or_b(
                                        e,
                                        _wgfn_is(e, "loop_fn"),
                                        or_b(
                                            e,
                                            _wgfn_is(e, "memory_grow_fn"),
                                            or_b(
                                                e,
                                                _wgfn_is(e, "memory_copy_fn"),
                                                or_b(
                                                    e,
                                                    _wgfn_is(e, "memory_size_fn"),
                                                    _wgfn_is(e, "memory_fill_fn"),
                                                ),
                                            ),
                                        ),
                                    ),
                                    e.list_new(str_(e)),
                                    e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("elem"), e.s("values")),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("kc", e.rec(e.p("n", e.int_of(0)), e.p("bad", e.dstr("")))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en",
                e.seq(
                    e.incr(e.fld(e.v("kc"), "n")),
                    e.let("ks", key_str(e, e.fld(e.v("en"), "key"))),
                    e.let("hit", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("want"),
                        "w",
                        e.if_only(e.eq(e.v("w"), e.v("ks")), e.mb.set(e.fld(e.v("hit"), "v"), num(e, 1))),
                    ),
                    e.if_only(e.eq(e.fld(e.v("hit"), "v"), num(e, 0)), e.mb.set(e.fld(e.v("kc"), "bad"), e.v("ks"))),
                ),
            ),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("kc"), "bad"), e.s(""))),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(e.s("wasm global definition has no argument "), e.fld(e.v("kc"), "bad")),
                    ),
                ),
            ),
            count_let(e, "wn"),
            count_loop(e, "wn", e.v("want")),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("kc"), "n"), e.fld(e.v("wn"), "v"))),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(e.s("wasm global definition requires arguments "), e.join(e.v("want"), ", ")),
                    ),
                ),
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("argv")))),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "import_fn"),
                e.seq(
                    e.let("itycv", _wgfn_field(e, "ty")),
                    e.let("ityv", _const_type_of(e, "itycv", "wasm import ty")),
                    e.if_only(
                        e.not_(has(e, xx(e), e.v("ityv"), "wfn")),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("wasm import ty must be a function type, not "), ty_desc(e, e.v("ityv"))),
                            ),
                        ),
                    ),
                    e.let("modulecv", _wgfn_staged(e, graft(e, _wgfn_field(e, "module")))),
                    e.let("namecv2", _wgfn_staged(e, graft(e, _wgfn_field(e, "name")))),
                    e.if_only(
                        or_b(e, is_runtime(e, e.v("modulecv")), is_runtime(e, e.v("namecv2"))),
                        ret_m(e, err_cve(e, loc(e), "wasm import module and name must be constant")),
                    ),
                    e.let("module", hf(e, "h_gref", e.v("modulecv"))),
                    e.let("name", hf(e, "h_gref", e.v("namecv2"))),
                    e.let("refcv", _wgfn_staged(e, e.cat(e.s("$"), e.lower(e.v("name"))))),
                    ret_m(
                        e,
                        tag_value(
                            e,
                            e.v("refcv"),
                            mk(
                                e,
                                "wt_import",
                                e.p("module", e.v("module")),
                                e.p("name", e.v("name")),
                                e.p("base", e.v("ityv")),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "loop_fn"),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(e.p("type", mk_arg(e, "wloop_t", e.tup())), e.p("data", e.tup())),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "memory_grow_fn"),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(e.p("type", mk_arg(e, "wmem_grow", e.tup())), e.p("data", e.tup())),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "memory_fill_fn"),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(e.p("type", mk_arg(e, "wmem_fill", e.tup())), e.p("data", e.tup())),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "memory_size_fn"),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(e.p("type", mk_arg(e, "wmem_size", e.tup())), e.p("data", e.tup())),
                            ),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _wgfn_is(e, "memory_copy_fn"),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            code_none(e, loc(e)),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(e.p("type", mk_arg(e, "wmem_copy", e.tup())), e.p("data", e.tup())),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("modcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("mod")))),
            e.if_only(
                _wgfn_is(e, "cstr_fn"),
                e.seq(
                    e.let("valuecv", _wgfn_field(e, "value")),
                    e.let("refcv", _wgfn_staged(e, e.call_m(_wgfn_mod(e), "cstr", graft(e, e.v("valuecv"))))),
                    ret_m(
                        e,
                        tag_value(
                            e,
                            e.v("refcv"),
                            _wgfn_global_t(e, mk(e, "wt_ptr", e.p("pointee", _int_ty(e, "u8")))),
                        ),
                    ),
                ),
            ),
            e.if_only(_wgfn_is(e, "data_fn"), _data_fn_body(e)),
            e.if_only(_wgfn_is(e, "alloc_fn"), _alloc_fn_body(e)),
            e.let("tycv", _wgfn_field(e, "ty")),
            e.let("tyv", _const_type_of(e, "tycv", "wasm ty")),
            e.if_only(
                e.not_(has(e, xx(e), e.v("tyv"), "wfn")),
                ret_m(
                    e,
                    err_cve(e, loc(e), e.cat(e.s("wasm ty must be a function type, not "), ty_desc(e, e.v("tyv")))),
                ),
            ),
            e.let("namecv", _wgfn_field(e, "name")),
            e.let("pcv", _wgfn_field(e, "params")),
            e.let("ptk", lookup(e, xx(e), cve_type(e, e.v("pcv")), asp_iface(e, "tuple"))),
            e.if_only(
                e.not_(e.fld(e.v("ptk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "wasm function params must be a tuple of parameter names")),
            ),
            e.let("names", e.list_new(str_(e))),
            e.foreach(
                bim(
                    e,
                    asp_iface(e, "tuple"),
                    "take_elements",
                    e.fld(e.v("ptk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("pcv")))),
                ),
                "er",
                e.seq(
                    e.let("ncv", unwrap_cve_m(e, e.v("er"))),
                    e.let("nsk", lookup(e, xx(e), cve_type(e, e.v("ncv")), e.mb.eval_aspect_string_const())),
                    e.if_only(
                        e.not_(e.fld(e.v("nsk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "wasm function parameter names must be constant strings")),
                    ),
                    push(
                        e,
                        e.v("names"),
                        bim(
                            e,
                            e.mb.eval_aspect_string_const(),
                            "get",
                            e.fld(e.v("nsk"), "value"),
                            cve_value(e, e.v("ncv")),
                        ),
                    ),
                ),
            ),
            count_let(e, "pn"),
            count_loop(e, "pn", e.v("names")),
            count_let(e, "tn"),
            count_loop(e, "tn", acc(e, xx(e), e.v("tyv"), "wfn", "params")),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("pn"), "v"), e.fld(e.v("tn"), "v"))),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(
                            e.s("wasm function has "),
                            to_str(e, e.fld(e.v("pn"), "v")),
                            e.s(" parameter names but its type has "),
                            to_str(e, e.fld(e.v("tn"), "v")),
                            e.s(" parameters"),
                        ),
                    ),
                ),
            ),
            e.let("bodycv", _wgfn_field(e, "body")),
            e.let("public", _wgfn_is(e, "export_fn")),
            e.let(
                "refcv",
                _wgfn_staged(
                    e,
                    e.call_m(
                        _wgfn_mod(e),
                        "func",
                        e.rec(
                            e.p("name", graft(e, e.v("namecv"))),
                            e.p("params", e.lower(e.v("names"))),
                            e.p("ty", e.lower(e.v("tyv"))),
                            e.p("body", graft(e, e.v("bodycv"))),
                            e.p("public", e.lower(e.v("public"))),
                        ),
                    ),
                ),
            ),
            e.ret(tag_value(e, e.v("refcv"), _wgfn_global_t(e, e.v("tyv")))),
        ),
    )

    x.append(
        e.impl_interface(
            e.v("wtarget"),
            e.mb.eval_target(),
            e.p("cast_exception", e.mb.panic(e.s("wasm target: exceptions are not supported"))),
            e.p(
                "initial_bind",
                e.eresult_err(e.mb.eval_binding(), loc(e), e.s("wasm target: exceptions are not supported")),
            ),
            e.p(
                "seq",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    e.let("st", e.rec(e.p("any", e.int_of(0)))),
                    e.foreach(
                        a(e, "entries"),
                        "en",
                        e.seq(
                            _append_code(e, e.v("out"), e.v("en")),
                            e.if_only(is_target_code(e, e.v("en")), e.mb.set(e.fld(e.v("st"), "any"), num(e, 1))),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            code_t(e),
                            e.if_else(
                                e.eq(e.fld(e.v("st"), "any"), num(e, 1)), _code_of(e, e.v("out")), code_none(e, loc(e))
                            ),
                        )
                    ),
                ),
            ),
            e.p(
                "jump",
                e.eresult_ok(
                    code_t(e),
                    _code_of(e, e.list_new(lt(e, "winst"), _br_inst(e, e.call_m(_mod(e), "label_of", a(e, "dest"))))),
                ),
            ),
            e.p(
                "land",
                e.eresult_ok(
                    cve_t(e),
                    cv_no(
                        e,
                        _code_of(
                            e,
                            e.list_new(
                                lt(e, "winst"),
                                _inst_bare(e, "label", e.p("name", e.call_m(_mod(e), "label_of", a(e, "dest")))),
                            ),
                        ),
                    ),
                ),
            ),
            e.p("value_is_runtime", e.mb.bool(False)),
            structural_exits(e)[0],
            structural_exits(e)[1],
            e.p(
                "exit",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), a(e, "value", "code")),
                    _append_code(
                        e,
                        e.v("out"),
                        _code_of(
                            e, e.list_new(lt(e, "winst"), _br_inst(e, e.call_m(_mod(e), "label_of", a(e, "dest"))))
                        ),
                    ),
                    e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("guarded", e.mb.panic(e.s("wasm target: exceptions are not supported"))),
            e.p("exc_cleanup", e.mb.panic(e.s("wasm target: exceptions are not supported"))),
            # A cleanup block: land, run the cleanup, continue to the next block; the carried value already sits in
            # the slot its return stored it in.
            e.p(
                "exit_trampoline",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(
                        e, e.v("out"), _inst_bare(e, "label", e.p("name", e.call_m(_mod(e), "label_of", a(e, "key"))))
                    ),
                    _append_code(e, e.v("out"), a(e, "cleanup")),
                    push(e, e.v("out"), _br_inst(e, e.call_m(_mod(e), "label_of", a(e, "next")))),
                    e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("drop", target_drop_body(e)),
            e.p(
                "return",
                body(
                    e,
                    e.if_only(e.not_(_is_wasm(e, xx(e), a(e, "cv"))), ret_m(e, a(e, "cv"))),
                    e.let(
                        "r",
                        e.match_of(
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_store_new",
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p("mod", _mod(e)),
                                    e.p("cv", a(e, "cv")),
                                ),
                                cve_t(e),
                            ),
                            "__r",
                            None,
                            e.p("ok", e.v("__r")),
                            e.p("errs", panic_errs(e, "wasm target", "return value store", e.v("__r"))),
                        ),
                    ),
                    e.let("lv", _wval_of(e, e.v("r"))),
                    # The slot keeps the value's declared type (a type over a wasm value stays that type).
                    e.let("t0", cve_type(e, a(e, "cv"))),
                    e.let(
                        "base",
                        e.if_else(
                            has(e, xx(e), e.v("t0"), "wgtype_m"),
                            acc(e, xx(e), e.v("t0"), "wgtype_m", "base"),
                            e.v("t0"),
                        ),
                    ),
                    e.ret(
                        cv_of(
                            e,
                            cve_code(e, e.v("r")),
                            bim(
                                e,
                                e.lower(e.fld(e.v("values"), "retag")),
                                "retag",
                                e.v("lv"),
                                mk(e, "wt_slot", e.p("base", e.v("base")), e.p("slot", e.v("lv"))),
                            ),
                        )
                    ),
                ),
            ),
            e.p("stage", err_cve(e, loc(e), "wasm target: nested staging is not supported")),
            e.p("if", _if_hook(e)),
            e.p(
                "loop",
                body(
                    e,
                    e.let("mod", _mod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("head", e.call_m(e.v("mod"), "fresh_label", e.tup())),
                    push(e, e.v("out"), _inst_bare(e, "loop", e.p("name", e.v("head")))),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "body"))),
                    e.if_only(e.not_(cve_ended(e, a(e, "body"))), push(e, e.v("out"), _br_inst(e, e.v("head")))),
                    push(e, e.v("out"), _inst0_bare(e, "end")),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("try_catch_finally", err_cve(e, loc(e), "wasm target: try/catch/finally is not supported")),
            e.p("match", _match_hook(e)),
        )
    )
    x.append(e.let("wasm_b", e.def_func(e.v("d"), "wasm")))
    x.append(
        e.func_impl(
            e.v("wasm_b"),
            e.tup(),
            e.option_type_some(t(e, "wmod")),
            e.mb.opt_none_type(),
            e.stage(
                e.seq(
                    e.let(
                        "m",
                        mk(
                            e,
                            "wmod",
                            e.p("n", num(e, 0)),
                            e.p("xx", e.opt_none(e.types_expr_context())),
                            e.p("meta", e.list_new(lt(e, "wmeta"))),
                            e.p("dep_keys", e.list_new(str_(e))),
                            e.p("data", e.list_new(lt(e, "wdata"))),
                            e.p("data_end", e.int_of(8)),
                            e.p("funcs", e.list_new(str_(e))),
                            e.p("defs", e.list_new(lt(e, "wdef"))),
                            e.p("sip_key_id", tm.fresh_unique(e)),
                            e.p("sip_fn_id", tm.fresh_unique(e)),
                            e.p("exports", e.list_new(str_(e))),
                            e.p("labels", e.list_new(lt(e, "wlabel"))),
                            e.p("locals", e.list_new(lt(e, "wlocal"))),
                            e.p("frames", e.call(e.lower(e.fld(e.v("srcmap"), "new")), e.tup())),
                        ),
                    ),
                    e.let("tgt", mk(e, "wtarget", e.p("mod", e.v("m")))),
                    e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
                    e.let(
                        "sc",
                        e.call(
                            e.eval_builtin("scope"),
                            e.rec(
                                e.p("vx", e.v("vx")),
                                e.p("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
                            ),
                        ),
                    ),
                    e.let(
                        "ctx",
                        e.call(
                            e.eval_builtin("expr_context"),
                            e.rec(
                                e.p("scope", e.v("sc")),
                                e.p("target", e.mb.as_(e.v("tgt"), e.mb.eval_target())),
                                e.p("vx", e.v("vx")),
                                e.p("exception_type", str_(e)),
                            ),
                        ),
                    ),
                    e.call_m(e.v("m"), "set_xx", e.v("ctx")),
                    e.ret(e.v("m")),
                )
            ),
        )
    )
    accessor(e, x, "wparam", "ty", ty(e))
    accessor(e, x, "wparam", "slots", e.list_type(str_(e)))
    _initial_bind_impl(e, x, "wt_int")
    _initial_bind_impl(e, x, "wt_float")
    _initial_bind_impl(e, x, "wt_ptr")
    _initial_bind_impl(e, x, "wt_fn")
    _initial_bind_impl(e, x, "wt_void")

    # The unsafe conversions, named: a pointer to another pointer type, a pointer to a 32-bit integer, a 32-bit
    # integer to a pointer. All are retags (every pointer is an i32).
    def base_of(ty_):
        return e.if_else(has(e, xx(e), ty_, "wgtype_m"), acc(e, xx(e), ty_, "wgtype_m", "base"), ty_)

    def wptr(ty_):
        return has(e, xx(e), base_of(ty_), "wptr")

    def wint32(ty_):
        return and_b(
            e,
            has(e, xx(e), base_of(ty_), "wint"),
            e.eq(acc(e, xx(e), base_of(ty_), "wint", "bits"), num(e, 32)),
        )

    def loaded_retag(cv, to):
        # The value as its base type (a global cast to its base, which loads its address), retagged.
        return e.mb.labeled(
            "c",
            e.seq(
                e.let("__pty", base_of(cve_type(e, cv))),
                e.let("__pv", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), e.v("__pty"), cv))),
                e.mb.return_to("c", _retag(e, e.v("__pv"), to)),
            ),
        )

    tm.named_conv(e, x, "ptr_cast_b", "wasm.ptr_cast", wptr, wptr, loaded_retag)
    tm.named_conv(e, x, "ptr_to_int_b", "wasm.ptr_to_int", wptr, wint32, loaded_retag)
    tm.named_conv(e, x, "int_to_ptr_b", "wasm.int_to_ptr", wint32, wptr, loaded_retag)
    x.append(e.finish(e.v("d")))
    passthrough = ["ptr", "fn", "tuple", "global_t", "import_t", "func_dep", "alloc_dep", "data_dep", "cstr_dep"]
    defs = []
    defs.append(e.p("new", e.fld(e.v("wasm_b"), "func")))
    defs.append(e.p("mod_t", t(e, "wmod")))
    defs.append(e.p("meta_t", t(e, "wmeta")))
    defs.append(e.p("meta_other", e.v("wm_other")))
    defs.append(e.p("meta_new", e.fld(e.v("wmeta"), "new")))
    for name in passthrough:
        defs.append(e.p(name, e.v("c_" + name)))
    for name in CONV_NAMES:
        defs.append(e.p(name, e.fld(e.v(name + "_b"), "func")))
    for obj in [
        "wt_int",
        "wt_float",
        "wt_void",
        "wgfn_t",
        "wt_ptr",
        "wt_global",
        "wloop_t",
        "wmem_grow",
        "wmem_copy",
        "wmem_size",
        "wmem_fill",
        "wtrap",
        "wunit",
        "wt_tuple",
        "wadep",
    ]:
        defs.append(e.p(obj + "_new", e.fld(e.v(obj), "new")))
    x.append(e.ret(e.rec(*defs)))

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    exported = []
    for spec in INT_SPECS:
        exported.append(spec.name)
        y.append(
            e.let(
                spec.name,
                _lty(
                    e,
                    "wt_int",
                    e.rec(
                        e.p("bits", e.int_of(spec.bits)),
                        e.p("signed", e.b(spec.signed)),
                        e.p("min", e.n(spec.min)),
                        e.p("max", e.n(spec.max)),
                    ),
                ),
            )
        )
    for bits in [32, 64]:
        exported.append("f" + str(bits))
        y.append(e.let("f" + str(bits), _lty(e, "wt_float", e.rec(e.p("bits", e.int_of(bits))))))
    exported.append("void")
    y.append(e.let("void", _lty(e, "wt_void", e.tup())))
    exported.append("unit")
    y.append(e.let("unit", _lty(e, "wunit", e.tup())))
    exported.append("trap")
    y.append(e.let("trap", _lty(e, "wtrap", e.tup())))
    y.append(
        e.let("cstr_t", _lty(e, "wt_global", e.rec(e.p("base", _lty(e, "wt_ptr", e.rec(e.p("pointee", e.v("u8"))))))))
    )
    for kind in WGFN_KINDS:
        if kind != "cstr_fn":
            exported.append(kind)
        y.append(
            e.let(kind + "_o", e.call(e.fld(e.v("k"), "wgfn_t_new"), e.rec(e.p("kind", e.int_of(_wgfn_kind(kind))))))
        )
    # `loop_fn {}`, `memory_grow_fn {}` and `memory_copy_fn {}` give values whose type is the
    # instance, as the llvm target's `ref_fn` does for its loop, so a staged body can iterate the
    # loop and call the intrinsics.
    y.append(e.let("d", e.define()))
    y.append(e.let("gfn_d", e.define()))
    for kind in WGFN_KINDS:
        tm.const_fn(
            e,
            y,
            kind + "_b",
            "wasm." + kind,
            e.call_m(
                e.lower(e.v(kind + "_o")),
                "call",
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("argument", a(e, "argument"))),
            ),
            d="gfn_d",
        )
        y.append(e.let(kind, e.fld(e.v(kind + "_b"), "func")))
    y.append(e.finish(e.v("gfn_d")))
    y.append(e.option_type_let())
    y.append(e.let("mod_o", e.def_object(e.v("d"), "wasm module")))
    y.append(e.object_impl(e.v("mod_o"), e.rec(e.p("m", e.fld(e.v("k"), "mod_t")))))
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "render",
            e.tup(),
            e.option_type_some(_render_t(e, e.fld(e.v("k"), "meta_t"))),
            e.stage(e.call_m(in_(e, "m"), "render", e.tup())),
        )
    )
    y.append(
        e.method_impl(e.v("mod_o"), "m", e.tup(), e.option_type_some(e.fld(e.v("k"), "mod_t")), e.stage(in_(e, "m")))
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "meta",
            e.fld(e.v("k"), "meta_t"),
            e.option_type_none(),
            e.stage(e.call_m(in_(e, "m"), "meta", e.v("arg"))),
        )
    )
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "cstr",
            str_(e),
            e.option_type_some(e.v("cstr_t")),
            e.stage(e.call(e.lower_v("cstr_fn"), e.rec(e.p("mod", outer(e)), e.p("value", e.v("arg"))))),
        )
    )
    # The module's SipHash key block (16 zeroed bytes `values.hash` reads) as the alloc dependency defining it, so
    # an app seeds the same block: dependencies are identified by id, never by name.
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "siphash_key",
            e.tup(),
            e.option_type_some(e.mb.eval_type()),
            e.stage(
                e.mb.as_(
                    e.call(
                        e.fld(e.lower_v("k"), "wadep_new"),
                        e.rec(
                            e.p("id", e.call_m(in_(e, "m"), "sip_key_id", e.tup())),
                            e.p("name", e.s("siphash_key")),
                            e.p("size", e.int_of(16)),
                        ),
                    ),
                    e.mb.eval_type(),
                )
            ),
        )
    )
    y.append(e.let("wasm_b", e.def_func(e.v("d"), "wasm")))
    y.append(
        e.func_impl(
            e.v("wasm_b"),
            e.tup(),
            e.option_type_some(e.fld(e.v("mod_o"), "type")),
            e.mb.opt_none_type(),
            e.stage(mk_arg(e, "mod_o", e.rec(e.p("m", e.call(e.fld(e.lower_v("k"), "new"), e.tup()))))),
        )
    )
    y.append(e.let("build_b", e.def_func(e.v("d"), "build")))
    y.append(
        e.func_impl(
            e.v("build_b"),
            _render_t(e, e.fld(e.v("k"), "meta_t")),
            e.option_type_some(e.mb.builtin("types", "app")),
            e.mb.opt_none_type(),
            e.stage(
                e.call(
                    e.mb.builtin("app"),
                    e.rec(
                        e.p("executor", e.opt_some(str_(e), e.s("wasmtime"))),
                        e.p("bytes", e.call(e.mb.eval_str_utf8(), a(e, "wat"))),
                    ),
                )
            ),
        )
    )
    y.append(e.finish(e.v("d")))
    ydefs = []
    ydefs.append(e.p("new", e.fld(e.v("wasm_b"), "func")))
    ydefs.append(e.p("build", e.fld(e.v("build_b"), "func")))
    ydefs.append(e.p("mod_t", e.fld(e.v("mod_o"), "type")))
    for name in META_EXPORTS:
        ydefs.append(e.p(name, e.fld(e.v("k"), name)))
    for name in passthrough + CONV_NAMES:
        ydefs.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        ydefs.append(e.p(name, e.v(name)))
    y.append(e.ret(e.rec(*ydefs)))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(y))))
    exports = []
    for name in ["new", "build", "mod_t"]:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in META_EXPORTS:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in passthrough + CONV_NAMES:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    top.append(e.ret(e.rec(*exports)))
    return top
