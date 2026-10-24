"""llvm-ir-22.atz: the LLVM IR target (types, values, module rendering, global data factories).

Conversions: `as` only converts losslessly and never between pointer types or between pointers and integers; a
pointer type casts from itself only. The unsafe conversions are named constant functions taking `{value, to}`:
`ptr_cast` (pointer to another pointer type, a retag; an in-memory global to a pointer type: its address),
`fn_to_ptr` (a function reference under a pointer type),
`ptr_to_int` (`ptrtoint` to a 64-bit integer), `int_to_ptr` (`inttoptr` from one) and `num_cast` (the C numeric
conversion: integers wrap, floats truncate into integers, anything rounds into a float; a constant must convert
losslessly). The lossy numeric conversions are also methods on values (`wrap`, `trunc`, `to_float`), each naming
one rule. A null of a given pointer type
is `ref_fn({ref: "null", ty: global_t({ty, mem: false})})`; a global's address is `ptr_cast({value: g, to:
ptr(elem)})` in target code (its symbol is minted, so a reference is never spelled from the hint). Internal symbols
are minted per module from a hint; only
externs and exported functions carry user names. Dependencies (`func_dep`, `alloc_dep`, `data_dep`, `cstr_dep`) are
identified by the instance, never by name: two libraries naming a dependency alike define two items. The module's
SipHash key block is reached through `mod.siphash_key()`."""

from collections import namedtuple

from ..core import meta, srcmap, values
from .. import target_mb
from .. import target_mb as tm
from ..target_mb import (
    lty,
    panic_errs,
    a,
    aggregate_layout_impls,
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
    has_b,
    hf,
    hf_rec,
    host_cve,
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
    retag_values,
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
    p_,
    push,
    recv_of,
    reinterpret,
    ret_m,
    retag_runtime,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    short_circuit_body,
    src_bits,
    src_type,
    str_,
    str_cve,
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
    type_can_convert,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    voc_t,
    xx,
    xx_t,
)


def _fn_def(e, out, name, arg_type, ret):
    return target_mb.fn_def(e, out, "llvm", name, arg_type, ret)


def _must_v(e, res, what):
    return target_mb.must_v(e, "llvm", res, what)


def _lval_t(e):
    return t(e, "lval")


# The fixed debug metadata nodes !0..!5 of every module: line tables only, over the one "file" frames.json whose
# line numbers are frame indices plus one (line 0 is "no location" in DWARF).
DBG_HEADER = [
    'distinct !DICompileUnit(language: DW_LANG_C, file: !3, producer: "alligatorus", isOptimized: false, '
    "runtimeVersion: 0, emissionKind: LineTablesOnly)",
    '!{i32 7, !"Dwarf Version", i32 5}',
    '!{i32 2, !"Debug Info Version", i32 3}',
    '!DIFile(filename: "frames.json", directory: "")',
    "!DISubroutineType(types: !5)",
    "!{null}",
]


def _lmod_t(e):
    return t(e, "lmod")


def _ltail_opt_t(e):
    return e.call(e.mb.types_option(), t(e, "ltail"))


def _lmod_opt_t(e):
    return e.call(e.mb.types_option(), t(e, "lmod"))


META_EXPORTS = ["meta_t", "meta_other", "meta_new"]


def _render_t(e, meta_t):
    return e.rec(
        e.p("ir", str_(e)),
        e.p("libs", e.list_type(str_(e))),
        e.p("meta", e.list_type(meta_t)),
        e.p("frames", str_(e)),
    )


def _init_fn(e, ty_, cv):
    return hf_rec(e, "h_init", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("ty", ty_), e.p("cv", cv))


HostInt = namedtuple("HostInt", ["name", "min", "max"])

HOST_INTS = [
    HostInt("byte", -128, 127),
    HostInt("ubyte", 0, 255),
    HostInt("short", -32768, 32767),
    HostInt("ushort", 0, 65535),
    HostInt("int", -2147483648.0, 2147483647.0),
    HostInt("uint", 0, 4294967295.0),
    HostInt("long", -9223372036854775808.0, 9223372036854775807.0),
    HostInt("ulong", 0, 18446744073709551615.0),
]

DATA_FACTORIES = ["const_list", "global_list", "const_def", "global_def"]

LlvmPrim = namedtuple("LlvmPrim", ["llvm", "ir", "host", "bits", "signed", "is_float"])

LLVM_PRIMS = [
    LlvmPrim("i8", "i8", "byte", 8, True, False),
    LlvmPrim("u8", "i8", "ubyte", 8, False, False),
    LlvmPrim("i16", "i16", "short", 16, True, False),
    LlvmPrim("u16", "i16", "ushort", 16, False, False),
    LlvmPrim("i32", "i32", "int", 32, True, False),
    LlvmPrim("u32", "i32", "uint", 32, False, False),
    LlvmPrim("i64", "i64", "long", 64, True, False),
    LlvmPrim("u64", "i64", "ulong", 64, False, False),
    LlvmPrim("f32", "float", "float", 32, False, True),
    LlvmPrim("f64", "double", "double", 64, False, True),
]


def _is_prim(e, xx_, ty_, prim):
    return (
        and_b(e, has(e, xx_, ty_, "lfloat"), e.eq(acc(e, xx_, ty_, "lfloat", "bits"), num(e, prim.bits)))
        if prim.is_float
        else and_b(
            e,
            has(e, xx_, ty_, "lint"),
            and_b(
                e,
                e.eq(acc(e, xx_, ty_, "lint", "bits"), num(e, prim.bits)),
                acc(e, xx_, ty_, "lint", "signed") if prim.signed else e.not_(acc(e, xx_, ty_, "lint", "signed")),
            ),
        )
    )


def _global_def(e, konst, init):
    return [
        e.let("gname", e.cat(e.s("@"), e.call_m(outer(e), "mint", a(e, "name")))),
        push(
            e,
            in_(e, "constants" if konst else "globals"),
            mk(e, "lglobal", e.p("name", e.v("gname")), e.p("ty", e.v("gty")), e.p("init", init)),
        ),
        e.ret(
            mk(
                e,
                "lgref",
                e.p("ref", e.v("gname")),
                e.p("mod", outer(e)),
                e.p(
                    "ty",
                    (
                        mk(
                            e,
                            "lt_global",
                            e.p("base", mk(e, "lt_ptr", e.p("pointee", e.v("gty")))),
                            e.p("mem", e.b(False)),
                        )
                        if konst
                        else mk(e, "lt_global", e.p("base", e.v("gty")), e.p("mem", e.b(True)))
                    ),
                ),
            )
        ),
    ]


def _ptr_pointee_let(e):
    return e.let("pointee", e.call_m(e.v("desc"), "pointee", e.tup()))


def _ptr_obj_let(e):
    return e.let("gref_obj", e.fld(e.lower_v("k"), "gref_obj_t"))


def _grefs_fill(e, grefs):
    return e.foreach(
        grefs, "g", push(e, e.v("refs"), e.call(e.mb.must_reinterpret(), e.tup(e.v("g"), e.lower(e.v("gref_obj")))))
    )


def _grefs_new(e):
    return e.let("refs", e.list_new(e.lower(e.v("gref_obj"))))


def _specialize(e, name, arg_type, impl_body):
    return e.seq(
        e.let("sp_d", e.define()),
        e.let("sp", e.call_m(e.v("sp_d"), "func", e.s(name))),
        e.call_m(
            e.v("sp"),
            "impl",
            e.rec(
                e.p("arg", arg_type),
                e.p("ret", e.option_type_lowered_some(e.lower_v("gref_t"))),
                e.p("impl_body", e.stage(impl_body)),
                e.p("exception_type", e.option_type_lowered_none()),
                e.p("description", e.opt_none(str_(e))),
            ),
        ),
        e.finish(e.v("sp_d")),
        ret_m(
            e,
            ok_cve(
                e,
                cv_of(
                    e,
                    code_none(e, loc(e)),
                    e.call(e.eval_builtin("value_empty"), e.call_m0(e.v("sp"), "func_type")),
                ),
            ),
        ),
    )


def _init_mismatch(e, st):
    return throw_err(
        e, loc(e), e.cat(e.s("cannot initialize llvm "), ty_desc(e, a(e, "ty")), e.s(" from "), ty_desc(e, st))
    )


def _fold_join(e, parts, open_, close):
    return e.mb.labeled(
        "fold",
        e.seq(
            e.let("accs", e.map_new(str_(e), cve_t(e))),
            e.call_m(e.v("accs"), "put", e.tup(e.s("0"), host_cve(e, e.stage(e.s(open_))))),
            e.let("fi", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                parts,
                "p",
                e.seq(
                    e.let("k0", to_str(e, e.fld(e.v("fi"), "i"))),
                    e.incr(e.fld(e.v("fi"), "i")),
                    e.call_m(
                        e.v("accs"),
                        "put",
                        e.tup(
                            to_str(e, e.fld(e.v("fi"), "i")),
                            host_cve(
                                e,
                                e.stage(
                                    e.cat(
                                        graft(e, e.call_m(e.v("accs"), "get", e.v("k0"))),
                                        e.lower(
                                            e.if_else(e.eq(e.fld(e.v("fi"), "i"), num(e, 1)), e.dstr(""), e.dstr(", "))
                                        ),
                                        graft(e, e.v("p")),
                                    )
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.mb.return_to(
                "fold",
                host_cve(
                    e,
                    e.stage(
                        e.cat(graft(e, e.call_m(e.v("accs"), "get", to_str(e, e.fld(e.v("fi"), "i")))), e.s(close))
                    ),
                ),
            ),
        ),
    )


def _ir_arg_xx(e):
    return e.call_m(e.v("arg"), "xx", e.tup())


def _ir_arg_mod(e):
    return e.call_m(e.v("arg"), "mod", e.tup())


def _ir_fn(e, xx_, mod_, ty_):
    return hf_rec(e, "h_ir", e.p("xx", xx_), e.p("mod", mod_), e.p("ty", ty_))


def _insts_t(e):
    return e.list_type(t(e, "linst"))


def _mod(e):
    return in_(e, "mod")


def _xmod(e):
    return _xmod_in(e, e.mb.types_cve())


def _xmod_must(e):
    """The current llvm module from `arg.xx`, in a host function that throws its errors."""
    return e.call_m(
        _must(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "ltarget")))), "mod", e.tup()
    )


def _must(e, res):
    return e.match_of(res, "__r", None, e.p("ok", e.v("__r")), e.p("errs", e.mb.throw_(e.v("__r"))))


def _xmod_in(e, ret_inner):
    return e.call_m(
        unwrap_m(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "ltarget"))), ret_inner),
        "mod",
        e.tup(),
    )


IntSpec = namedtuple("IntSpec", ["name", "bits", "signed", "min", "max"])

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
                "lt_int",
                e.p("bits", num(e, spec.bits)),
                e.p("signed", e.b(spec.signed)),
                e.p("min", e.n(spec.min)),
                e.p("max", e.n(spec.max)),
            )
    raise ValueError("no int type " + name)


def _initial_bind_impl(e, x, obj):
    """`initial_bind`: a parameter slot of this target becomes this target's binding, typed as the parameter (a type
    delegating its aspects here keeps its own identity)."""
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_initial_bind(),
            e.p(
                "initial_bind",
                e.seq(
                    e.let("ps", e.call(e.mb.must_reinterpret(), e.tup(a(e, "slot"), lt(e, "lparam")))),
                    e.ret(
                        e.eresult_ok(
                            e.mb.eval_binding(),
                            mk(
                                e,
                                "lbinding",
                                e.p("ty", e.call_m(e.v("ps"), "ty", e.tup())),
                                e.p("ptr", e.call_m(e.v("ps"), "ptr", e.tup())),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def _conv_methods(e, x):
    """Lossy numeric conversions as methods on int and float values (`as` only converts losslessly): `wrap(T)` wraps an
    integer into the integer type `T` (two's complement: truncation, extension by the source's signedness, or a
    reinterpretation at the same width); `trunc(T)` truncates a float toward zero into the integer type `T`;
    `to_float(T)` rounds an integer or a float to the float type `T`."""
    target_mb.method_type(e, x, "lconv", "llvm conversion")
    to = e.v("to")
    v = e.v("v")
    st = e.v("st")

    def when(cond, result):
        return e.if_only(cond, ret_m(e, result))

    x.append(
        e.impl_interface(
            e.v("lconv"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    *target_mb.const_type_arg(e, "llvm conversion", a(e, "argument"), "to"),
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
                    e.if_only(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("wrap")),
                            and_b(e, has(e, xx(e), st, "lint"), has(e, xx(e), to, "lint")),
                        ),
                        e.seq(
                            e.let("sb", cv_bits(e, st, "lint")),
                            e.let("tb", acc(e, xx(e), to, "lint", "bits")),
                            when(e.eq(e.v("sb"), e.v("tb")), _retag(e, v, to)),
                            when(e.mb.operator_gt(e.v("sb"), e.v("tb")), _conv(e, e.s("trunc"), v, to)),
                            ret_m(
                                e,
                                _conv(
                                    e,
                                    e.if_else(acc(e, xx(e), st, "lint", "signed"), e.dstr("sext"), e.dstr("zext")),
                                    v,
                                    to,
                                ),
                            ),
                        ),
                    ),
                    when(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("trunc")),
                            and_b(e, has(e, xx(e), st, "lfloat"), has(e, xx(e), to, "lint")),
                        ),
                        _conv(
                            e, e.if_else(acc(e, xx(e), to, "lint", "signed"), e.dstr("fptosi"), e.dstr("fptoui")), v, to
                        ),
                    ),
                    when(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("to_float")),
                            and_b(e, has(e, xx(e), st, "lint"), has(e, xx(e), to, "lfloat")),
                        ),
                        _conv(
                            e, e.if_else(acc(e, xx(e), st, "lint", "signed"), e.dstr("sitofp"), e.dstr("uitofp")), v, to
                        ),
                    ),
                    e.if_only(
                        and_b(
                            e,
                            e.eq(in_(e, "op"), e.s("to_float")),
                            and_b(e, has(e, xx(e), st, "lfloat"), has(e, xx(e), to, "lfloat")),
                        ),
                        e.seq(
                            e.let("sb", cv_bits(e, st, "lfloat")),
                            e.let("tb", acc(e, xx(e), to, "lfloat", "bits")),
                            when(e.eq(e.v("sb"), e.v("tb")), _retag(e, v, to)),
                            when(e.mb.operator_gt(e.v("sb"), e.v("tb")), _conv(e, e.s("fptrunc"), v, to)),
                            ret_m(e, _conv(e, e.s("fpext"), v, to)),
                        ),
                    ),
                    e.ret(
                        err_cve(
                            e,
                            loc(e),
                            e.cat(
                                e.s("llvm: no conversion "),
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
    target_mb.method_fields(e, x, "lt_int", [("lconv", ["wrap", "to_float"])])
    target_mb.method_fields(e, x, "lt_float", [("lconv", ["trunc", "to_float"])])


def _value_aspects(e, x, obj, size_expr, hash_stage, zero_text):
    """Implements values.atz's `size_i`, `eq_i`, `zero_i` (the constant `zero_text`) and (when `hash_stage` is
    given) `hash_i` for a type object: eq stages the type's own `==`; hash stages a 32-bit hash of the value `cv`."""
    x.append(e.impl_interface(e.v(obj), e.fld(e.v("values"), "size_i"), e.p("size", size_expr)))
    x.append(e.impl_interface(e.v(obj), e.fld(e.v("values"), "align_i"), e.p("align", size_expr)))
    x.append(
        e.impl_interface(
            e.v(obj),
            e.fld(e.v("values"), "zero_i"),
            e.p("zero", ok_cve(e, cv_of(e, code_none(e, a(e, "loc")), _lval_new(e, outer(e), e.s(zero_text))))),
        )
    )
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
        e.let("pi64", mk(e, "lt_ptr", e.p("pointee", e.v("sh_i64")))),
        e.if_else(
            e.eq(in_(e, "bits"), num(e, 64)),
            e.ret(
                _sip_hash(
                    e, lambda x: x, e.p("ty", mk(e, "lt_arr", e.p("elem", e.v("sh_i64")), e.p("count", e.int_of(2))))
                )
            ),
            e.ret(
                _sip_hash(
                    e,
                    lambda x: e.call(e.fld(x, "wrap"), e.lower(e.v("sh_i64"))),
                    e.p("ty", mk(e, "lt_arr", e.p("elem", e.v("sh_i64")), e.p("count", e.int_of(2)))),
                )
            ),
        ),
    )


def _ptr_hash_body(e):
    """values.hash for pointers: the address as i64, SipHashed."""
    return e.seq(
        e.let("sh_i64", e.mb.as_(_int_ty(e, "i64"), e.mb.eval_type())),
        e.let("sh_i32", e.mb.as_(_int_ty(e, "i32"), e.mb.eval_type())),
        e.let("pi64", mk(e, "lt_ptr", e.p("pointee", e.v("sh_i64")))),
        e.ret(
            _sip_hash(
                e,
                lambda x: e.call(e.fld(x, "wrap"), e.lower(e.v("sh_i64"))),
                e.p("ty", mk(e, "lt_arr", e.p("elem", e.v("sh_i64")), e.p("count", e.int_of(2)))),
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
                        "lt_fn",
                        e.p("params", e.list_new(ty(e), e.v("sh_i64"), e.v("sh_i64"), e.v("sh_i64"))),
                        e.p("ret", e.v("sh_i32")),
                        e.p("varargs", e.b(False)),
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
                    "keypc",
                    hf_rec(
                        e,
                        "h_retag",
                        e.p("loc", a(e, "loc")),
                        e.p("mod", _xmod_must(e)),
                        e.p("cv", e.v("keyp")),
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


def _lval_of(e, cve_tp):
    return reinterpret(e, cve_value(e, cve_tp), "lval")


def _lval_new(e, ty_, ref):
    return mk(e, "lval", e.p("ty", ty_), e.p("source", e.call(e.lower_v("ls_ssa"), ref)))


def _lval_mem(e, ty_, ptr):
    return mk(e, "lval", e.p("ty", ty_), e.p("source", e.call(e.lower_v("ls_mem"), ptr)))


def _lv_mem(e, lval_tp):
    return e.call_m(lval_tp, "mem", e.tup())


def _lv_is_mem(e, lval_tp):
    return e.eq(e.call_m(lval_tp, "is_mem", e.tup()), num(e, 1))


def _operand(e, xx_, loc_, mod_, ty_, cv):
    return hf_rec(e, "h_operand", e.p("xx", xx_), e.p("loc", loc_), e.p("mod", mod_), e.p("ty", ty_), e.p("cv", cv))


def _insts_new(e):
    return e.list_new(lt(e, "linst"))


def _loc_opt_t(e):
    return e.call(e.mb.types_option(), loc_t(e))


def _inst(e, loc_, variant, *fields):
    """An instruction at `loc_`, the expression it computes: its `!dbg` names that location's frame."""
    return _inst_at(e, e.opt_some(loc_t(e), loc_), variant, *fields)


def _inst_bare(e, variant, *fields):
    """A structural instruction (label, branch, dependency) with no location of its own."""
    return _inst_at(e, e.opt_none(loc_t(e)), variant, *fields)


def _inst_at(e, loc_opt, variant, *fields):
    return mk(e, "linst", e.p("k", e.call(e.lower_v("li_" + variant), e.rec(*fields))), e.p("loc", loc_opt))


def _dep_inst(e, variant, *fields):
    dep = mk(e, "ldep", e.p("k", e.call(e.lower_v(variant), e.rec(*fields))))
    meta_ = mk(e, "lmeta", e.p("k", e.call(e.lower_v("lm_dep"), e.rec(e.p("dep", dep)))))
    return _inst_bare(e, "meta", e.p("meta", meta_))


def _append_code(e, out, code_tp):
    return hf_rec(e, "h_append", e.p("out", out), e.p("code", code_tp))


def _code_of(e, insts):
    return hf(e, "h_code", insts)


def _ssa(e, xx_, loc_, mod_, cv):
    return hf_rec(e, "h_ssa", e.p("xx", xx_), e.p("loc", loc_), e.p("mod", mod_), e.p("cv", cv))


def _is_llvm(e, xx_, cv):
    return hf_rec(e, "h_is_llvm", e.p("xx", xx_), e.p("cv", cv))


def _def_variant(e, out, tag, type_ref):
    out.append(
        e.let("li_" + tag, e.call_m(e.v("linst_u"), "variant", e.rec(e.p("tag", e.s(tag)), e.p("type_ref", type_ref))))
    )


def _fresh(e, mod_):
    return e.call_m(mod_, "fresh", e.tup())


def _fresh_label(e, mod_):
    return e.call_m(mod_, "fresh_label", e.tup())


def _lv_ref(e, lval_tp):
    return e.call_m(lval_tp, "ref", e.tup())


def _lv_ty(e, lval_tp):
    return e.call_m(lval_tp, "ty", e.tup())


def _store_inst(e, loc_, val, ptr):
    return _inst(e, loc_, "store", e.p("val", val), e.p("ptr", ptr))


def _label_inst(e, name):
    return _inst_bare(e, "label", e.p("name", name))


def _br_inst(e, name):
    return _inst_bare(e, "br", e.p("name", name))


def _inst_binop_i64(e, loc_, res, op_, a_, b):
    return push(
        e,
        e.v("out"),
        _inst(
            e,
            loc_,
            "binop",
            e.p("res", e.v(res)),
            e.p("op", e.s(op_)),
            e.p("a", _lval_new(e, e.v("i64"), a_)),
            e.p("b", _lval_new(e, e.v("i64"), b)),
        ),
    )


def _load_inst(e, loc_, res, ty_, ptr):
    return _inst(e, loc_, "load", e.p("res", res), e.p("ty", ty_), e.p("ptr", ptr))


def _dbg(e):
    """The `, !dbg !N` suffix of the instruction `i0` being rendered (empty for a structural one)."""
    return e.call_m(outer(e), "dbg_of", e.call_m(e.v("i0"), "loc", e.tup()))


def _render_arm(e, *line_parts):
    return e.seq(push(e, e.v("out"), e.cat(*line_parts, _dbg(e))), e.mb.set(e.fld(e.v("st"), "open"), num(e, 1)))


def _count_ref(e, name):
    return e.call_m(
        e.v("refs"),
        "put",
        e.tup(name, e.mb.operator_add(e.mb.as_(e.call_m(e.v("refs"), "get", name), e.mb.types_int()), num(e, 1))),
    )


def _flush_pend(e):
    return e.seq(
        e.if_only(
            e.not_(e.eq(e.fld(e.v("st"), "pend"), e.s(""))),
            push(e, e.v("out"), e.cat(e.s("  br label %"), e.fld(e.v("st"), "pend"))),
        ),
        e.mb.set(e.fld(e.v("st"), "pend"), e.s("")),
    )


def _render_terminator(e, *line_parts):
    return e.seq(push(e, e.v("out"), e.cat(*line_parts, _dbg(e))), e.mb.set(e.fld(e.v("st"), "open"), num(e, 0)))


def _ir_of(e, ty_):
    return e.call_m(outer(e), "ir", ty_)


def _typed_of(e, lval_tp):
    return e.call_m(outer(e), "typed", lval_tp)


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


def _literal(e, ty_, ref):
    return hf_rec(e, "h_literal", e.p("loc", loc(e)), e.p("ty", ty_), e.p("ref", ref))


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
                                    e.p("mod", _xmod_in(e, br_t)),
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
                                            "lbinding",
                                            e.p("ty", _lv_ty(e, _lval_of(e, e.v("r")))),
                                            e.p("ptr", _lv_mem(e, _lval_of(e, e.v("r")))),
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


def _when_st(e, marker, result):
    return e.if_only(has(e, xx(e), e.v("st"), marker), ret_m(e, result))


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


def _if_branch_stmts(e, cv_var):
    valued = and_b(e, cve_has(e, e.v(cv_var)), _is_llvm(e, xx(e), e.v(cv_var)))
    return e.seq(
        e.if_only(
            and_b(
                e,
                cve_has(e, e.v(cv_var)),
                and_b(
                    e,
                    e.not_(_is_llvm(e, xx(e), e.v(cv_var))),
                    e.not_(hf_rec(e, "h_is_unit", e.p("xx", xx(e)), e.p("cv", e.v(cv_var)))),
                ),
            ),
            ret_m(e, err_cve(e, loc(e), "if branches must yield llvm values")),
        ),
        e.if_only(
            valued,
            e.seq(
                e.let("bv", unwrap_cve_m(e, try_er(e, _ssa(e, xx(e), loc(e), e.v("mod"), e.v(cv_var)), cve_t(e)))),
                e.if_only(
                    e.eq(e.fld(e.v("st"), "has"), num(e, 0)),
                    e.seq(
                        e.mb.set(e.fld(e.v("st"), "slot"), e.call_m(e.v("mod"), "slot", cve_type(e, e.v("bv")))),
                        e.mb.set(e.fld(e.v("st"), "ty"), e.option_type_lowered_some(cve_type(e, e.v("bv")))),
                        e.mb.set(e.fld(e.v("st"), "has"), num(e, 1)),
                    ),
                ),
                _append_code(e, e.v("out"), cve_code(e, e.v("bv"))),
                push(e, e.v("out"), _store_inst(e, loc(e), _lval_of(e, e.v("bv")), e.fld(e.v("st"), "slot"))),
            ),
        ),
        e.if_only(
            e.not_(valued),
            e.seq(
                _append_code(e, e.v("out"), cve_code(e, e.v(cv_var))),
                e.if_only(e.not_(cve_ended(e, e.v(cv_var))), e.mb.set(e.fld(e.v("st"), "novalue"), num(e, 1))),
            ),
        ),
        e.if_only(
            e.not_(cve_ended(e, e.v(cv_var))),
            e.seq(push(e, e.v("out"), _br_inst(e, e.v("end"))), e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0))),
        ),
    )


def _arms_body(e, pre, branches, skip_last, prelude, else_is_some, else_prelude):
    """The target's `if` and `match`: a conditional branch per arm into its own block, every arm joining at `end`;
    a value, when the arms yield one, goes through a slot loaded at `end`. `pre` runs once `out` exists;
    `prelude(br)` binds `c0` (the condition code value) and `b` (the body code value) of branch `br`; `else_prelude`
    binds `b` for the else arm, present when `else_is_some`; when `skip_last`, the last branch is not emitted (the
    else arm stands for it)."""
    return body(
        e,
        e.let("mod", _mod(e)),
        e.let("out", _insts_new(e)),
        e.let("i1", _int_ty(e, "i1")),
        e.let("end", _fresh_label(e, e.v("mod"))),
        e.let(
            "st",
            e.rec(
                e.p("ended", e.int_of(1)),
                e.p("has", e.int_of(0)),
                e.p("novalue", e.int_of(0)),
                e.p("slot", e.dstr("")),
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
                    e.not_(and_b(e, skip_last, e.eq(e.fld(e.v("bi"), "v"), e.fld(e.v("nc"), "v")))),
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
                        e.let("thn", _fresh_label(e, e.v("mod"))),
                        e.let("nxt", _fresh_label(e, e.v("mod"))),
                        push(
                            e,
                            e.v("out"),
                            _inst(
                                e,
                                loc(e),
                                "condbr",
                                e.p("cond", _lval_of(e, e.v("c"))),
                                e.p("t", e.v("thn")),
                                e.p("f", e.v("nxt")),
                            ),
                        ),
                        push(e, e.v("out"), _label_inst(e, e.v("thn"))),
                        _if_branch_stmts(e, "b"),
                        push(e, e.v("out"), _label_inst(e, e.v("nxt"))),
                    ),
                ),
            ),
        ),
        e.if_only(else_is_some, e.seq(*else_prelude(), _if_branch_stmts(e, "b"))),
        e.if_only(e.not_(else_is_some), e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "ended"), num(e, 1)),
            ret_m(e, ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
        ),
        push(e, e.v("out"), _label_inst(e, e.v("end"))),
        e.if_only(e.eq(e.fld(e.v("st"), "has"), num(e, 0)), ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out")))))),
        e.if_only(
            e.eq(e.fld(e.v("st"), "novalue"), num(e, 1)),
            ret_m(e, err_cve(e, loc(e), "if: some branches yield a value and some do not")),
        ),
        e.let("r", _fresh(e, e.v("mod"))),
        push(e, e.v("out"), _load_inst(e, loc(e), e.v("r"), e.fld(e.v("st"), "ty", "value"), e.fld(e.v("st"), "slot"))),
        e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_new(e, e.fld(e.v("st"), "ty", "value"), e.v("r"))))),
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


def _tuple_type(e, x):
    """`lt_tuple{elems}`: a first-class aggregate `{ T0, T1, … }`. A host tuple of castable values casts to it through
    an `insertvalue` chain; `.0`, `.1`, … are `extractvalue`s of a register value and places (GEPs) of a value in
    memory; it binds to one slot, is passed and returned whole, and dropping it drops its components."""
    no = no_cast_to(e)
    i32 = _int_ty(e, "i32")

    def elems_of(typ):
        return acc(e, xx(e), typ, "ltuple", "elems")

    def same_elems(other):
        return body(
            e,
            e.if_only(e.not_(has(e, xx(e), other, "ltuple")), ret_m(e, dfalse(e))),
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

    def component(self_cv, idx, elem_t):
        """The component `idx` (a host int) of the tuple value `self_cv`: a place for a value in memory, else an
        `extractvalue` register."""
        return e.seq(
            e.let("sl", _lval_of(e, self_cv)),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, self_cv)),
            e.let("r", _fresh(e, _xmod(e))),
            e.if_only(
                _lv_is_mem(e, e.v("sl")),
                e.seq(
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "gep",
                            e.p("res", e.v("r")),
                            e.p("base", outer(e)),
                            e.p("ptr", _lv_mem(e, e.v("sl"))),
                            e.p(
                                "idx",
                                e.list_new(
                                    lt(e, "lval"), _lval_new(e, i32, e.dstr("0")), _lval_new(e, i32, to_str(e, idx))
                                ),
                            ),
                        ),
                    ),
                    ret_m(e, ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_mem(e, elem_t, e.v("r"))))),
                ),
            ),
            push(e, e.v("out"), _inst(e, loc(e), "extv", e.p("res", e.v("r")), e.p("agg", e.v("sl")), e.p("idx", idx))),
            ret_m(e, ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_new(e, elem_t, e.v("r"))))),
        )

    def _any_elem_drops(e_):
        """Whether a component type of the tuple has the drop aspect (in the type's own aspect dispatch)."""
        return e_.mb.labeled(
            "d",
            e_.seq(
                e_.foreach(
                    in_(e_, "elems"),
                    "et",
                    e_.if_only(
                        e_.fld(
                            lookup(e_, e_.fld(e_.v("arg"), "xx"), e_.v("et"), e_.mb.eval_aspect_drop_dynamic()),
                            "is_some",
                        ),
                        e_.mb.return_to("d", e_.mb.as_(e_.b(True), bool_t(e_))),
                    ),
                ),
                e_.mb.return_to("d", e_.mb.as_(e_.b(False), bool_t(e_))),
            ),
        )

    self_type(
        e,
        x,
        "lt_tuple",
        body(
            e,
            e.let("ds", e.list_new(str_(e))),
            e.foreach(in_(e, "elems"), "et", push(e, e.v("ds"), bim0(e, ty(e), "desc", e.v("et")))),
            e.ret(e.cat(e.s("("), e.join(e.v("ds"), ", "), e.s(")"))),
        ),
        # A tuple drops (its components) only when a component does.
        e.mb.if_of(
            [
                (
                    e.eq(a(e, "key"), e.mb.eval_aspect_drop_dynamic_id()),
                    e.if_else(
                        _any_elem_drops(e),
                        e.opt_some(e.mb.types_aspect(), outer(e)),
                        e.opt_none(e.mb.types_aspect()),
                    ),
                )
            ],
            e.aspect_dispatch(
                lv(e, "ltype_id"),
                lv(e, "ltuple_id"),
                lv(e, "zero_id"),
                lv(e, "size_id"),
                lv(e, "align_id"),
                asp_id(e, "initial_bind"),
                asp_id(e, "bind"),
                asp_id(e, "set"),
                asp_id(e, "field"),
            ),
        ),
        body(
            e,
            e.if_only(has(e, xx(e), src_type(e), "ltuple"), ret_m(e, same_elems(src_type(e)))),
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
                e.if_only(e.not_(type_can_convert(e, xx(e), loc(e), e.v("eb"), e.v("ea"))), ret_m(e, dfalse(e))),
            ),
            e.ret(e.not_(dfalse(e))),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(has(e, xx(e), e.v("st"), "ltuple"), ret_m(e, _retag(e, a(e, "cv"), outer(e)))),
            # A host tuple: each element becomes an operand of its component type, inserted in turn.
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
            e.let("agg", e.list_new(lt(e, "lval"))),
            e.let("ai", e.rec(e.p("v", e.int_of(0)))),
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
                e.let("r", _fresh(e, _xmod(e))),
                e.let("prev", e.opt_none(lt(e, "lval"))),
                e.foreach(e.v("agg"), "pa", e.mb.set(e.v("prev"), e.opt_some(lt(e, "lval"), e.v("pa")))),
                push(
                    e,
                    e.v("out"),
                    _inst(
                        e,
                        loc(e),
                        "insv",
                        e.p("res", e.v("r")),
                        e.p("ty", outer(e)),
                        e.p("agg", e.v("prev")),
                        e.p("val", _lval_of(e, e.v("v"))),
                        e.p("idx", e.fld(e.v("ai"), "v")),
                    ),
                ),
                e.mb.set(e.v("agg"), e.list_new(lt(e, "lval"), _lval_new(e, outer(e), e.v("r")))),
                e.incr(e.fld(e.v("ai"), "v")),
            ),
            e.foreach(e.v("agg"), "fa", ret_m(e, ok_cve(e, cv_of(e, _code_of(e, e.v("out")), e.v("fa"))))),
            e.ret(err_cve(e, loc(e), "an empty tuple has no llvm value")),
        ),
        no,
        cast_to_panic(e),
        same_elems(a(e, "other")),
    )
    x.append(
        e.impl_interface(
            e.v("lt_tuple"),
            t(e, "ltype"),
            e.p(
                "ir",
                e.seq(
                    e.let("irs", e.list_new(str_(e))),
                    e.foreach(
                        in_(e, "elems"), "et", push(e, e.v("irs"), _ir_fn(e, _ir_arg_xx(e), _ir_arg_mod(e), e.v("et")))
                    ),
                    e.ret(e.cat(e.s("{ "), e.join(e.v("irs"), ", "), e.s(" }"))),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("lt_tuple"), t(e, "ltuple"), e.p("elems", in_(e, "elems"))))
    aggregate_layout_impls(e, x, "lt_tuple", in_(e, "elems"))
    # The zero tuple: llvm's aggregate constant.
    x.append(
        e.impl_interface(
            e.v("lt_tuple"),
            e.fld(e.v("values"), "zero_i"),
            e.p(
                "zero",
                ok_cve(e, cv_of(e, code_none(e, a(e, "loc")), _lval_new(e, outer(e), e.s("zeroinitializer")))),
            ),
        )
    )
    _initial_bind_impl(e, x, "lt_tuple")
    _bind_impl(e, x, "lt_tuple")
    _set_impl(e, x, "lt_tuple")
    x.append(
        e.impl_interface(
            e.v("lt_tuple"),
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
                        in_(e, "elems"),
                        "et",
                        e.seq(
                            e.if_only(
                                e.eq(e.fld(e.v("ki"), "v"), e.v("k")), component(a(e, "value"), e.v("k"), e.v("et"))
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
    x.append(
        e.impl_interface(
            e.v("lt_tuple"),
            e.mb.eval_aspect_drop_dynamic(),
            e.p(
                "drop",
                body(
                    e,
                    e.let("codes", e.list_new(code_t(e))),
                    e.let("v", cv_of(e, code_none(e, loc(e)), cve_value(e, a(e, "cv")))),
                    e.let("ki", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        in_(e, "elems"),
                        "et",
                        e.seq(
                            e.let(
                                "c",
                                unwrap_m(
                                    e,
                                    e.mb.labeled("m", e.seq(component(e.v("v"), e.fld(e.v("ki"), "v"), e.v("et")))),
                                    code_t(e),
                                ),
                            ),
                            push(
                                e,
                                e.v("codes"),
                                unwrap_m(
                                    e,
                                    e.call(
                                        e.mb.eval_drop_value(),
                                        e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", e.v("c"))),
                                    ),
                                    code_t(e),
                                ),
                            ),
                            e.incr(e.fld(e.v("ki"), "v")),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            code_t(e),
                            unwrap_m(
                                e,
                                bim(
                                    e,
                                    e.mb.eval_target(),
                                    "seq",
                                    e.fld(xx(e), "target"),
                                    e.rec(e.p("loc", loc(e)), e.p("entries", e.v("codes"))),
                                ),
                                code_t(e),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def _gval(e, cv):
    return hf_rec(e, "h_gval", e.p("cv", cv), e.p("base", in_(e, "base")), e.p("mem", in_(e, "mem")))


# The named unsafe conversions (const functions `{value, to}`), exported beside the type factories.
CONV_NAMES = ["ptr_cast", "fn_to_ptr", "ptr_to_int", "int_to_ptr", "num_cast"]

LGFN_KINDS = [
    "global_fn",
    "global_const_fn",
    "constant_fn",
    "extern_fn",
    "func_fn",
    "export_fn",
    "ref_fn",
    "cstr_fn",
    "global_zero_fn",
]


def _lgfn_kind(kind):
    for i, known in enumerate(LGFN_KINDS):
        if known == kind:
            return i
    raise ValueError("no llvm global definition kind " + kind)


def _lgfn_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _lgfn_kind(kind)))


def _lgfn_staged(e, staged):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(staged)))


def _lgfn_global_t(e, base, mem):
    return mk(e, "lt_global", e.p("base", base), e.p("mem", e.b(mem)))


def _lgfn_field(e, key):
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(key)))


def _def_extern_type(e, x):
    self_type(
        e,
        x,
        "lt_extern",
        e.cat(e.s("extern("), in_(e, "name"), e.s(": "), bim0(e, ty(e), "desc", in_(e, "base")), e.s(")")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "lextern_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "dest_type")))),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(err_cve(e, loc(e), "llvm extern cannot be cast")),
        ),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "lextern_m")), ret_m(e, dfalse(e))),
            e.ret(
                and_b(
                    e,
                    e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), "lextern_m", "name")),
                    is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "lextern_m", "base")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(e.v("lt_extern"), t(e, "lextern_m"), e.p("name", in_(e, "name")), e.p("base", in_(e, "base")))
    )
    rt_lift_impl(e, x, "lt_extern")
    rt_bind_impl(e, x, "lt_extern", e.mb.types_string())
    rt_use_impl(e, x, "lt_extern")
    x.append(
        e.impl_interface(
            e.v("lt_extern"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(
                        e,
                        e.v("out"),
                        _dep_inst(e, "ld_extern", e.p("name", in_(e, "name")), e.p("ty", in_(e, "base"))),
                    ),
                    e.foreach(in_(e, "libs"), "l", push(e, e.v("out"), _dep_inst(e, "ld_lib", e.p("name", e.v("l"))))),
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
                                            e.p("cv", a(e, "function")),
                                            e.p("base", in_(e, "base")),
                                            e.p("mem", e.b(False)),
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


def _lmod_meta_method(e):
    return e.method_impl(
        e.v("lmod"),
        "meta",
        t(e, "lmeta"),
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
                                    "extern",
                                    e.cat(
                                        e.s("extern "),
                                        p_(e, "name"),
                                        e.s(" "),
                                        _ir_of(
                                            e, im0(e, "lfn", "ret", asp(e, in_(e, "xx", "value"), p_(e, "ty"), "lfn"))
                                        ),
                                        e.s("("),
                                        e.call_m(outer(e), "params_ir", p_(e, "ty")),
                                        e.s(")"),
                                    ),
                                ),
                                e.p("lib", e.cat(e.s("lib "), p_(e, "name"))),
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


def _lmod_render(e, x):
    method(
        e,
        x,
        "lmod",
        "render",
        e.tup(),
        _render_t(e, t(e, "lmeta")),
        e.seq(
            e.let("out", e.list_new(str_(e))),
            e.let("libs", e.list_new(str_(e))),
            push(e, e.v("out"), e.s("declare void @llvm.trap()")),
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
                                "extern",
                                push(
                                    e,
                                    e.v("out"),
                                    e.cat(
                                        e.s("declare "),
                                        _ir_of(
                                            e, im0(e, "lfn", "ret", asp(e, in_(e, "xx", "value"), p_(e, "ty"), "lfn"))
                                        ),
                                        e.s(" @"),
                                        p_(e, "name"),
                                        e.s("("),
                                        e.call_m(outer(e), "params_ir", p_(e, "ty")),
                                        e.s(")"),
                                    ),
                                ),
                            ),
                            e.p("lib", push(e, e.v("libs"), p_(e, "name"))),
                        ),
                    ),
                    e.p("other", e.seq()),
                ),
            ),
            e.foreach(
                in_(e, "globals"),
                "g0",
                push(
                    e,
                    e.v("out"),
                    e.cat(
                        e.call_m(e.v("g0"), "name", e.tup()),
                        e.s(" = internal global "),
                        _ir_of(e, e.call_m(e.v("g0"), "ty", e.tup())),
                        e.s(" "),
                        e.call_m(e.v("g0"), "init", e.tup()),
                    ),
                ),
            ),
            e.foreach(
                in_(e, "constants"),
                "g0",
                push(
                    e,
                    e.v("out"),
                    e.cat(
                        e.call_m(e.v("g0"), "name", e.tup()),
                        e.s(" = private unnamed_addr constant "),
                        _ir_of(e, e.call_m(e.v("g0"), "ty", e.tup())),
                        e.s(" "),
                        e.call_m(e.v("g0"), "init", e.tup()),
                    ),
                ),
            ),
            e.foreach(in_(e, "funcs"), "f", push(e, e.v("out"), e.v("f"))),
            push(e, e.v("out"), e.s("!llvm.dbg.cu = !{!0}")),
            push(e, e.v("out"), e.s("!llvm.module.flags = !{!1, !2}")),
            e.let("di", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                in_(e, "dbg"),
                "d",
                e.seq(
                    push(e, e.v("out"), e.cat(e.s("!"), to_str(e, e.fld(e.v("di"), "v")), e.s(" = "), e.v("d"))),
                    e.incr(e.fld(e.v("di"), "v")),
                ),
            ),
            e.let("all", e.list_new(str_(e))),
            e.foreach(in_(e, "struct_lines"), "l", push(e, e.v("all"), e.v("l"))),
            e.foreach(e.v("out"), "l", push(e, e.v("all"), e.v("l"))),
            e.ret(
                e.rec(
                    e.p("ir", e.cat(e.join(e.v("all"), "\n"), e.s("\n"))),
                    e.p("libs", e.v("libs")),
                    e.p("meta", in_(e, "meta")),
                    e.p("frames", e.call_m(in_(e, "frames"), "render", e.tup())),
                )
            ),
        ),
    )


def _lmod_dbg(e, x):
    """The module's debug metadata: `dbg_sub` adds a function's subprogram node, `dbg_of` the `!dbg` suffix of an
    instruction at a location (one DILocation node per frame and subprogram)."""
    method(
        e,
        x,
        "lmod",
        "dbg_sub",
        e.rec(e.p("name", str_(e)), e.p("loc", loc_t(e))),
        int_t(e),
        e.seq(
            e.let("f", e.call_m(in_(e, "frames"), "index", a(e, "loc"))),
            e.let("id", e.fld(in_(e, "dbg"), "len")),
            push(
                e,
                in_(e, "dbg"),
                e.cat(
                    e.s('distinct !DISubprogram(name: "'),
                    a(e, "name"),
                    e.s('", scope: !3, file: !3, line: '),
                    to_str(e, e.mb.operator_add(e.v("f"), e.int_of(1))),
                    e.s(", type: !4, spFlags: DISPFlagDefinition, unit: !0)"),
                ),
            ),
            e.ret(e.v("id")),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "dbg_of",
        _loc_opt_t(e),
        str_(e),
        e.seq(
            e.if_only(e.not_(e.fld(e.v("arg"), "is_some")), e.ret(e.dstr(""))),
            e.let("f", e.call_m(in_(e, "frames"), "index", e.fld(e.v("arg"), "value"))),
            e.let("key", e.cat(to_str(e, e.v("f")), e.s(":"), to_str(e, in_(e, "sp")))),
            e.if_only(
                e.not_(e.call_m(in_(e, "dbg_keys"), "has", e.v("key"))),
                e.seq(
                    e.call_m(in_(e, "dbg_keys"), "put", e.tup(e.v("key"), e.fld(in_(e, "dbg"), "len"))),
                    push(
                        e,
                        in_(e, "dbg"),
                        e.cat(
                            e.s("!DILocation(line: "),
                            to_str(e, e.mb.operator_add(e.v("f"), e.int_of(1))),
                            e.s(", column: 0, scope: !"),
                            to_str(e, in_(e, "sp")),
                            e.s(")"),
                        ),
                    ),
                ),
            ),
            e.ret(
                e.cat(
                    e.s(", !dbg !"),
                    to_str(e, e.mb.as_(e.call_m(in_(e, "dbg_keys"), "get", e.v("key")), e.mb.types_int())),
                )
            ),
        ),
    )


def _extern_fn_body(e):
    return e.seq(
        e.if_only(
            e.not_(has(e, xx(e), e.v("tyv"), "lfn")),
            ret_m(
                e,
                err_cve(e, loc(e), e.cat(e.s("llvm extern ty must be a function type, not "), ty_desc(e, e.v("tyv")))),
            ),
        ),
        e.let("namecv", _lgfn_staged(e, graft(e, _lgfn_field(e, "name")))),
        e.if_only(is_runtime(e, e.v("namecv")), ret_m(e, err_cve(e, loc(e), "llvm extern name must be constant"))),
        e.let("name", hf(e, "h_gref", e.v("namecv"))),
        e.let("libscv", _lgfn_field(e, "libs")),
        e.let("ltk", lookup(e, xx(e), cve_type(e, e.v("libscv")), asp_iface(e, "tuple"))),
        e.if_only(
            e.not_(e.fld(e.v("ltk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "llvm extern libs must be a tuple of library names")),
        ),
        e.let("libs", e.list_new(str_(e))),
        e.foreach(
            bim(
                e,
                asp_iface(e, "tuple"),
                "take_elements",
                e.fld(e.v("ltk"), "value"),
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, e.v("libscv")))),
            ),
            "el",
            e.seq(
                e.let("lcv", _lgfn_staged(e, graft(e, unwrap_cve_m(e, e.v("el"))))),
                e.if_only(is_runtime(e, e.v("lcv")), ret_m(e, err_cve(e, loc(e), "llvm extern libs must be constant"))),
                push(e, e.v("libs"), hf(e, "h_gref", e.v("lcv"))),
            ),
        ),
        e.let("refcv", _lgfn_staged(e, e.cat(e.s("@"), e.lower(e.v("name"))))),
        ret_m(
            e,
            tag_value(
                e,
                e.v("refcv"),
                mk(e, "lt_extern", e.p("name", e.v("name")), e.p("base", e.v("tyv")), e.p("libs", e.v("libs"))),
            ),
        ),
    )


def module(e):
    x = []
    x.append(e.let("meta", e.import_local("meta", meta.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("srcmap", e.import_local("srcmap", srcmap.FILE)))
    for vid in ["size_id", "align_id", "hash_id", "eq_id", "zero_id"]:
        x.append(e.let(vid, e.fld(e.v("values"), vid)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(
        e,
        x,
        "lint",
        e.p("bits", int_t(e)),
        e.p("signed", bool_t(e)),
        e.p("min", e.types_double()),
        e.p("max", e.types_double()),
    )
    def_iface(e, x, "lfloat", e.p("bits", int_t(e)))
    def_iface(e, x, "lptr", e.p("pointee", ty(e)))
    def_iface(e, x, "larr", e.p("elem", ty(e)), e.p("count", int_t(e)))
    def_iface(e, x, "lvoid")
    def_iface(e, x, "lslot", e.p("base", ty(e)), e.p("ptr", str_(e)))
    def_iface(e, x, "lunit_m")
    def_iface(e, x, "lrange_m", e.p("elem", ty(e)))
    def_iface(e, x, "lloop_m")
    def_iface(e, x, "ltrap_m")
    def_iface(e, x, "lgtype_m", e.p("base", ty(e)), e.p("mem", bool_t(e)))
    def_iface(e, x, "lgfn_m", e.p("kind", int_t(e)))
    def_iface(e, x, "ltuple", e.p("elems", e.list_type(ty(e))))
    x.append(e.let("lsrc_u", e.call_m0(e.v("d"), "union")))
    for tag in ["ssa", "mem"]:
        x.append(
            e.let(
                "ls_" + tag, e.call_m(e.v("lsrc_u"), "variant", e.rec(e.p("tag", e.s(tag)), e.p("type_ref", str_(e))))
            )
        )
    def_obj(e, x, "lval", "llvm value", e.rec(e.p("ty", ty(e)), e.p("source", t(e, "lsrc_u"))))
    x.append(
        e.impl_interface(
            e.v("lval"),
            e.fld(e.v("values"), "retag"),
            e.p("retag", mk(e, "lval", e.p("ty", e.v("arg")), e.p("source", in_(e, "source")))),
        )
    )
    def_obj(e, x, "lfield", "llvm field", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))))
    def_obj(
        e,
        x,
        "ltail",
        "llvm struct tail",
        e.rec(
            e.p("views", e.list_type(t(e, "lfield"))),
            e.p("after", str_(e)),
            e.p("len", e.list_type(str_(e))),
            e.p("align", int_t(e)),
        ),
    )
    def_iface(
        e, x, "lstruct", e.p("name", str_(e)), e.p("fields", e.list_type(t(e, "lfield"))), e.p("tail", _ltail_opt_t(e))
    )
    def_iface(e, x, "lfn", e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)), e.p("varargs", bool_t(e)))
    def_obj(e, x, "lglobal", "llvm global", e.rec(e.p("name", str_(e)), e.p("ty", ty(e)), e.p("init", str_(e))))
    def_obj(e, x, "lalloca", "llvm function slot", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))))
    def_obj(e, x, "llabel", "llvm label", e.rec(e.p("key", e.types_jump_key()), e.p("name", str_(e))))
    x.append(e.let("linst_u", e.call_m0(e.v("d"), "union")))
    _def_variant(e, x, "label", e.rec(e.p("name", str_(e))))
    _def_variant(e, x, "br", e.rec(e.p("name", str_(e))))
    _def_variant(e, x, "condbr", e.rec(e.p("cond", _lval_t(e)), e.p("t", str_(e)), e.p("f", str_(e))))
    _def_variant(
        e, x, "binop", e.rec(e.p("res", str_(e)), e.p("op", str_(e)), e.p("a", _lval_t(e)), e.p("b", _lval_t(e)))
    )
    _def_variant(
        e, x, "cmp", e.rec(e.p("res", str_(e)), e.p("op", str_(e)), e.p("a", _lval_t(e)), e.p("b", _lval_t(e)))
    )
    _def_variant(e, x, "unop", e.rec(e.p("res", str_(e)), e.p("op", str_(e)), e.p("a", _lval_t(e))))
    _def_variant(e, x, "conv", e.rec(e.p("res", str_(e)), e.p("op", str_(e)), e.p("a", _lval_t(e)), e.p("to", ty(e))))
    _def_variant(e, x, "load", e.rec(e.p("res", str_(e)), e.p("ty", ty(e)), e.p("ptr", str_(e))))
    _def_variant(e, x, "store", e.rec(e.p("val", _lval_t(e)), e.p("ptr", str_(e))))
    _def_variant(
        e,
        x,
        "gep",
        e.rec(e.p("res", str_(e)), e.p("base", ty(e)), e.p("ptr", str_(e)), e.p("idx", e.list_type(t(e, "lval")))),
    )
    _def_variant(
        e,
        x,
        "insv",
        e.rec(
            e.p("res", str_(e)),
            e.p("ty", ty(e)),
            e.p("agg", e.call(e.mb.types_option(), t(e, "lval"))),
            e.p("val", _lval_t(e)),
            e.p("idx", int_t(e)),
        ),
    )
    _def_variant(e, x, "extv", e.rec(e.p("res", str_(e)), e.p("agg", _lval_t(e)), e.p("idx", int_t(e))))
    _def_variant(
        e,
        x,
        "call",
        e.rec(
            e.p("res", e.call(e.mb.types_option(), str_(e))),
            e.p("fn", _lval_t(e)),
            e.p("args", e.list_type(t(e, "lval"))),
        ),
    )
    _def_variant(e, x, "ret", e.rec(e.p("val", e.call(e.mb.types_option(), t(e, "lval")))))
    _def_variant(e, x, "trap", e.tup())
    x.append(e.let("ldep_u", e.call_m0(e.v("d"), "union")))
    x.append(
        e.let(
            "ld_extern",
            e.call_m(
                e.v("ldep_u"),
                "variant",
                e.rec(e.p("tag", e.s("extern")), e.p("type_ref", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))))),
            ),
        )
    )
    x.append(
        e.let(
            "ld_lib",
            e.call_m(
                e.v("ldep_u"), "variant", e.rec(e.p("tag", e.s("lib")), e.p("type_ref", e.rec(e.p("name", str_(e)))))
            ),
        )
    )
    def_obj(e, x, "ldep", "llvm dependency", e.rec(e.p("k", t(e, "ldep_u"))))
    accessor(e, x, "ldep", "k", t(e, "ldep_u"))
    x.append(e.let("lmeta_u", e.call_m0(e.v("d"), "union")))
    x.append(
        e.let(
            "lm_dep",
            e.call_m(
                e.v("lmeta_u"),
                "variant",
                e.rec(e.p("tag", e.s("dep")), e.p("type_ref", e.rec(e.p("dep", t(e, "ldep"))))),
            ),
        )
    )
    x.append(
        e.let(
            "lm_other",
            e.call_m(
                e.v("lmeta_u"),
                "variant",
                e.rec(e.p("tag", e.s("other")), e.p("type_ref", e.fld(e.v("meta"), "other_t"))),
            ),
        )
    )
    def_obj(e, x, "lmeta", "llvm metadata", e.rec(e.p("k", t(e, "lmeta_u"))))
    accessor(e, x, "lmeta", "k", t(e, "lmeta_u"))
    _def_variant(e, x, "meta", e.rec(e.p("meta", t(e, "lmeta"))))
    def_obj(e, x, "linst", "llvm instruction", e.rec(e.p("k", t(e, "linst_u")), e.p("loc", _loc_opt_t(e))))
    def_iface(e, x, "linst_m")
    def_iface(e, x, "lglobal_m")
    def_iface(e, x, "lalloca_m")
    def_iface(e, x, "lmod_m")
    def_iface(e, x, "llabel_m")
    def_iface(e, x, "lfield_m")
    def_obj(e, x, "lcode", "llvm code", e.rec(e.p("insts", e.list_type(t(e, "linst")))))
    x.append(e.impl_interface(e.v("lcode"), e.mb.builtin("eval", "code_dyn")))
    method(e, x, "lcode", "insts", e.tup(), e.list_type(t(e, "linst")), in_(e, "insts"))
    target_mb.module_defs(e, x, "ldef", "llvm definition")
    def_obj(
        e,
        x,
        "lmod",
        "llvm module",
        e.rec(
            e.p("n", int_t(e)),
            e.p("xx", e.call(e.mb.types_option(), e.types_expr_context())),
            e.p("structs", e.list_type(ty(e))),
            e.p("struct_lines", e.list_type(str_(e))),
            e.p("meta", e.list_type(t(e, "lmeta"))),
            e.p("dep_keys", e.list_type(str_(e))),
            e.p("globals", e.list_type(t(e, "lglobal"))),
            e.p("constants", e.list_type(t(e, "lglobal"))),
            e.p("slots", e.list_type(t(e, "lalloca"))),
            e.p("funcs", e.list_type(str_(e))),
            e.p("defs", e.list_type(t(e, "ldef"))),
            # The SipHash key global and function are one dependency each per module: their identities are minted
            # with the module, so every hash in it shares them.
            e.p("sip_key_id", target_mb.unique_t(e)),
            e.p("sip_fn_id", target_mb.unique_t(e)),
            e.p("labels", e.list_type(t(e, "llabel"))),
            # Debug info: the frame table, the metadata nodes (`!<index> = <node>`; the first six are the compile
            # unit, flags, file and subroutine type), the DILocation node of each (frame, subprogram) pair, and the
            # subprogram node of the function whose body is being rendered.
            e.p("frames", e.fld(e.v("srcmap"), "table_t")),
            e.p("dbg", e.list_type(str_(e))),
            e.p("dbg_keys", e.map_type(str_(e), e.mb.types_int_box())),
            e.p("sp", int_t(e)),
        ),
    )
    def_obj(e, x, "ltarget", "llvm target", e.rec(e.p("mod", _lmod_t(e))))
    def_obj(e, x, "lirctx", "llvm ir rendering context", e.rec(e.p("xx", xx_t(e)), e.p("mod", _lmod_opt_t(e))))
    x.append(e.let("ltype", e.call_m0(e.v("d"), "interface")))
    x.append(e.interface_impl(e.v("ltype"), True))
    x.append(e.let("ltype_id", e.call_m0(e.v("ltype"), "aspect_id")))
    x.append(
        e.call_m(
            e.v("ltype"),
            "func",
            e.rec(e.p("name", e.s("ir")), e.p("arg", t(e, "lirctx")), e.p("ret", e.option_type_some(str_(e)))),
        )
    )
    x.append(
        e.call_m(
            e.v("ltype"),
            "func",
            e.rec(e.p("name", e.s("ssa")), e.p("arg", e.tup()), e.p("ret", e.option_type_some(ty(e)))),
        )
    )
    def_obj(e, x, "lbinding", "llvm binding", e.rec(e.p("ty", ty(e)), e.p("ptr", str_(e))))
    # A parameter's slot, handed to the parameter type's `initial_bind` to make the binding over it.
    def_obj(e, x, "lparam", "llvm slot", e.rec(e.p("ty", ty(e)), e.p("ptr", str_(e))))
    x.append(e.impl_interface(e.v("lparam"), e.mb.eval_binding_slot()))
    x.append(
        e.impl_interface(
            e.v("lparam"),
            e.fld(e.v("values"), "retag_slot"),
            e.p("retag_slot", mk(e, "lparam", e.p("ty", e.v("arg")), e.p("ptr", in_(e, "ptr")))),
        )
    )
    def_obj(e, x, "lbinding_none", "llvm empty binding", e.tup())
    def_obj(e, x, "lunit", "llvm unit", e.tup())
    def_obj(
        e,
        x,
        "lt_int",
        "llvm int type",
        e.rec(
            e.p("bits", int_t(e)), e.p("signed", bool_t(e)), e.p("min", e.types_double()), e.p("max", e.types_double())
        ),
    )
    def_obj(e, x, "lt_float", "llvm float type", e.rec(e.p("bits", int_t(e))))
    def_obj(e, x, "lt_ptr", "llvm pointer type", e.rec(e.p("pointee", ty(e))))
    def_obj(e, x, "lt_arr", "llvm array type", e.rec(e.p("elem", ty(e)), e.p("count", int_t(e))))
    def_obj(
        e,
        x,
        "lt_struct",
        "llvm struct type",
        e.rec(e.p("name", str_(e)), e.p("fields", e.list_type(t(e, "lfield"))), e.p("tail", _ltail_opt_t(e))),
    )
    def_obj(
        e,
        x,
        "lt_fn",
        "llvm function type",
        e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)), e.p("varargs", bool_t(e))),
    )
    def_obj(e, x, "lt_void", "llvm void type", e.tup())
    def_obj(e, x, "lt_tuple", "llvm tuple type", e.rec(e.p("elems", e.list_type(ty(e)))))
    def_obj(e, x, "lt_slot", "llvm slot type", e.rec(e.p("base", ty(e)), e.p("ptr", str_(e))))
    def_obj(e, x, "lrange_t", "llvm range type", e.rec(e.p("elem", ty(e))))
    def_obj(e, x, "lrange", "llvm range", e.rec(e.p("t", ty(e)), e.p("code", e.mb.types_code()), e.p("n", _lval_t(e))))
    def_obj(e, x, "lloop_t", "llvm loop type", e.tup())
    def_obj(e, x, "ltrap_t", "llvm trap", e.tup())
    def_obj(e, x, "lgfn_t", "llvm global definition function", e.rec(e.p("kind", int_t(e))))
    def_obj(e, x, "lt_global", "llvm global type", e.rec(e.p("base", ty(e)), e.p("mem", bool_t(e))))
    def_obj(
        e,
        x,
        "lt_extern",
        "llvm extern function type",
        e.rec(e.p("name", str_(e)), e.p("base", ty(e)), e.p("libs", e.list_type(str_(e)))),
    )
    def_iface(e, x, "lextern_m", e.p("name", str_(e)), e.p("base", ty(e)))
    def_iface(e, x, "lgref_m")
    def_obj(
        e, x, "lgref", "llvm global reference", e.rec(e.p("ref", str_(e)), e.p("ty", ty(e)), e.p("mod", _lmod_t(e)))
    )
    accessor(e, x, "lgref", "ref", str_(e))
    accessor(e, x, "lgref", "ty", ty(e))
    def_obj(e, x, "lt_gref", "llvm global reference type", e.tup())
    _fn_def(e, x, "h_ir", e.rec(e.p("xx", xx_t(e)), e.p("mod", _lmod_opt_t(e)), e.p("ty", ty(e))), str_(e))
    _fn_def(e, x, "h_params_ir", e.rec(e.p("xx", xx_t(e)), e.p("mod", _lmod_opt_t(e)), e.p("ty", ty(e))), str_(e))
    fn_impl(
        e,
        x,
        "h_ir",
        body(
            e,
            e.let("lk", lookup(e, xx(e), a(e, "ty"), lt(e, "ltype"))),
            e.if_only(
                e.not_(e.fld(e.v("lk"), "is_some")),
                e.mb.panic(e.cat(e.s("llvm: not an llvm type: "), bim0(e, e.mb.eval_type(), "desc", a(e, "ty")))),
            ),
            e.ret(
                bim(
                    e,
                    lt(e, "ltype"),
                    "ir",
                    e.fld(e.v("lk"), "value"),
                    mk(e, "lirctx", e.p("xx", xx(e)), e.p("mod", a(e, "mod"))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_params_ir",
        body(
            e,
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                im0(e, "lfn", "params", asp(e, xx(e), a(e, "ty"), "lfn")),
                "p",
                push(e, e.v("parts"), _ir_fn(e, xx(e), a(e, "mod"), e.v("p"))),
            ),
            e.if_only(im0(e, "lfn", "varargs", asp(e, xx(e), a(e, "ty"), "lfn")), push(e, e.v("parts"), e.s("..."))),
            e.ret(e.join(e.v("parts"), ", ")),
        ),
    )
    _fn_def(e, x, "h_insts", code_t(e), _insts_t(e))
    _fn_def(e, x, "h_code", _insts_t(e), code_t(e))
    x.append(e.let("h_append_b", e.def_func(e.v("d"), "llvm.h_append")))
    x.append(e.let("h_append", e.fld(e.v("h_append_b"), "func")))
    e.fn_sigs["h_append"] = [
        e.rec(e.p("out", _insts_t(e)), e.p("code", code_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(e, x, "h_is_llvm", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(
        e,
        x,
        "h_ssa",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_ssa", errs_t(e))
    _fn_def(e, x, "h_mat", e.rec(e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("cv", cve_t(e))), cve_t(e))
    _fn_def(
        e,
        x,
        "h_operand",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("ty", ty(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_operand", errs_t(e))
    _fn_def(e, x, "h_is_unit", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), e.mb.types_bool())
    _fn_def(e, x, "h_ssa_type", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), ty(e))
    _fn_def(
        e,
        x,
        "h_set",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _lmod_t(e)),
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
            e.p("mod", _lmod_t(e)),
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
            e.p("mod", _lmod_t(e)),
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
            e.p("mod", _lmod_t(e)),
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
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_store_new", errs_t(e))
    _fn_def(
        e,
        x,
        "h_conv",
        e.rec(e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("op", str_(e)), e.p("a", cve_t(e)), e.p("to", ty(e))),
        cve_t(e),
    )
    _fn_def(
        e,
        x,
        "h_gep",
        e.rec(
            e.p("loc", loc_t(e)),
            e.p("mod", _lmod_t(e)),
            e.p("base", ty(e)),
            e.p("ptr", str_(e)),
            e.p("idx", e.list_type(t(e, "lval"))),
        ),
        cve_t(e),
    )
    _fn_def(e, x, "h_key_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(
        e,
        x,
        "h_retag",
        e.rec(e.p("loc", loc_t(e)), e.p("mod", _lmod_t(e)), e.p("cv", cve_t(e)), e.p("ty", ty(e))),
        cve_t(e),
    )
    _fn_def(e, x, "h_literal", e.rec(e.p("loc", loc_t(e)), e.p("ty", ty(e)), e.p("ref", str_(e))), cve_t(e))
    _fn_def(
        e,
        x,
        "h_gep_field",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _lmod_t(e)),
            e.p("st", ty(e)),
            e.p("ptr", str_(e)),
            e.p("name", str_(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_gep_field", errs_t(e))
    _fn_def(
        e, x, "h_tail_view", e.rec(e.p("tail", t(e, "ltail")), e.p("name", str_(e))), e.call(e.mb.types_option(), ty(e))
    )
    _fn_def(
        e,
        x,
        "h_gep_tail",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _lmod_t(e)),
            e.p("st", ty(e)),
            e.p("ptr", str_(e)),
            e.p("name", str_(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_gep_tail", errs_t(e))
    _fn_def(
        e,
        x,
        "h_gep_index",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _lmod_t(e)),
            e.p("base", ty(e)),
            e.p("ptr", str_(e)),
            e.p("key", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_gep_index", errs_t(e))
    _fn_def(e, x, "h_gref", cve_t(e), str_(e))
    _fn_def(e, x, "h_gval", e.rec(e.p("cv", cve_t(e)), e.p("base", ty(e)), e.p("mem", bool_t(e))), cve_t(e))
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
                    e.if_else(a(e, "mem"), _lval_mem(e, a(e, "base"), e.v("r")), _lval_new(e, a(e, "base"), e.v("r"))),
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
                            e.call_m(e.v("c"), "cast", lt(e, "lcode")),
                            "r",
                            None,
                            e.p("ok", e.call_m(e.v("r"), "insts", e.tup())),
                            e.p("errs", e.mb.panic(e.s("llvm: codeT(e) belongs to another target"))),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(e, x, "h_code", body(e, e.ret(e.mb.as_(mk_arg(e, "lcode", e.rec(e.p("insts", e.v("arg")))), code_t(e)))))
    fn_impl(e, x, "h_append", body(e, e.foreach(hf(e, "h_insts", a(e, "code")), "i", push(e, a(e, "out"), e.v("i")))))
    fn_impl(
        e,
        x,
        "h_is_llvm",
        body(e, e.ret(e.if_else(cve_has(e, a(e, "cv")), has(e, xx(e), cve_type(e, a(e, "cv")), "ltype"), e.b(False)))),
    )
    fn_impl(
        e,
        x,
        "h_ssa",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "expression has no value")),
            e.if_only(
                has(e, xx(e), cve_type(e, a(e, "cv")), "lgtype_m"),
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
                                    acc(e, xx(e), cve_type(e, a(e, "cv")), "lgtype_m", "base"),
                                    a(e, "cv"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let("lk", lookup(e, xx(e), cve_type(e, a(e, "cv")), lt(e, "ltype"))),
            e.if_only(e.not_(e.fld(e.v("lk"), "is_some")), throw_err(e, loc(e), "not an llvm value")),
            e.let("st", im0(e, "ltype", "ssa", e.fld(e.v("lk"), "value"))),
            # The value viewed as its ssa type: the target's own view, not a conversion (an owned value refuses to be
            # cast to its pointer, and keeps its ownership here: it comes back typed as itself).
            e.let("c", retag_values(e, a(e, "cv"), e.v("st"))),
            # The materialized value keeps the value's own type (a handle over the ssa type comes back a handle),
            # less the slot wrappers of the bindings it was read through.
            e.let("mv", hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", e.v("c")))),
            e.ret(
                hf_rec(
                    e,
                    "h_retag",
                    e.p("loc", loc(e)),
                    e.p("mod", a(e, "mod")),
                    e.p("cv", e.v("mv")),
                    e.p("ty", hf_rec(e, "h_ssa_type", e.p("xx", xx(e)), e.p("ty", cve_type(e, a(e, "cv"))))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_ssa_type",
        body(
            e,
            # The type an ssa value of `ty` keeps: `ty` without the parameter slots it was read through.
            e.if_only(
                has(e, a(e, "xx"), a(e, "ty"), "lslot"),
                ret_m(
                    e,
                    hf_rec(
                        e,
                        "h_ssa_type",
                        e.p("xx", a(e, "xx")),
                        e.p("ty", acc(e, a(e, "xx"), a(e, "ty"), "lslot", "base")),
                    ),
                ),
            ),
            e.ret(a(e, "ty")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_is_unit",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), ret_m(e, dfalse(e))),
            e.if_only(has(e, xx(e), cve_type(e, a(e, "cv")), "lunit_m"), ret_m(e, e.not_(dfalse(e)))),
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
            e.let("lv", _lval_of(e, a(e, "cv"))),
            e.if_only(e.not_(_lv_is_mem(e, e.v("lv"))), ret_m(e, a(e, "cv"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            e.let("r", _fresh(e, a(e, "mod"))),
            push(e, e.v("out"), _load_inst(e, loc(e), e.v("r"), _lv_ty(e, e.v("lv")), _lv_mem(e, e.v("lv")))),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_new(e, _lv_ty(e, e.v("lv")), e.v("r")))),
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
            e.let("sl", _lval_of(e, a(e, "self"))),
            e.if_only(e.not_(_lv_is_mem(e, e.v("sl"))), throw_err(e, loc(e), "value is not assignable")),
            e.let("v", _operand(e, xx(e), loc(e), a(e, "mod"), a(e, "ty"), a(e, "value"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "self"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            push(e, e.v("out"), _store_inst(e, loc(e), _lval_of(e, e.v("v")), _lv_mem(e, e.v("sl")))),
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
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "binop",
                    e.p("res", e.v("r")),
                    e.p("op", a(e, "op")),
                    e.p("a", _lval_of(e, e.v("a2"))),
                    e.p("b", _lval_of(e, e.v("b2"))),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_new(e, a(e, "res"), e.v("r")))),
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
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "cmp",
                    e.p("res", e.v("r")),
                    e.p("op", a(e, "op")),
                    e.p("a", _lval_of(e, e.v("a2"))),
                    e.p("b", _lval_of(e, e.v("b2"))),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_new(e, _int_ty(e, "i1"), e.v("r")))),
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
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(e, loc(e), "unop", e.p("res", e.v("r")), e.p("op", a(e, "op")), e.p("a", _lval_of(e, e.v("a2")))),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_new(e, a(e, "ty"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_store_new",
        body(
            e,
            e.let("v", _ssa(e, xx(e), loc(e), a(e, "mod"), a(e, "cv"))),
            e.let("ty", cve_type(e, e.v("v"))),
            e.let("s", e.call_m(a(e, "mod"), "slot", e.v("ty"))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            push(e, e.v("out"), _store_inst(e, loc(e), _lval_of(e, e.v("v")), e.v("s"))),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_mem(e, e.v("ty"), e.v("s")))),
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
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "conv",
                    e.p("res", e.v("r")),
                    e.p("op", a(e, "op")),
                    e.p("a", _lval_of(e, e.v("a0"))),
                    e.p("to", a(e, "to")),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_new(e, a(e, "to"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gep",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "gep",
                    e.p("res", e.v("r")),
                    e.p("base", a(e, "base")),
                    e.p("ptr", a(e, "ptr")),
                    e.p("idx", a(e, "idx")),
                ),
            ),
            e.ret(
                cv_of(e, _code_of(e, e.v("out")), _lval_new(e, mk(e, "lt_ptr", e.p("pointee", a(e, "base"))), e.v("r")))
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_key_str",
        body(
            e,
            e.ret(
                e.call(
                    e.eval_builtin("constkey_to_str"),
                    e.call(
                        e.eval_builtin("extract_constkey"),
                        e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_retag",
        body(
            e,
            e.let("m", hf_rec(e, "h_mat", e.p("loc", loc(e)), e.p("mod", a(e, "mod")), e.p("cv", a(e, "cv")))),
            e.ret(cv_of(e, cve_code(e, e.v("m")), _lval_new(e, a(e, "ty"), _lv_ref(e, _lval_of(e, e.v("m")))))),
        ),
    )
    fn_impl(e, x, "h_literal", body(e, e.ret(cv_of(e, code_none(e, loc(e)), _lval_new(e, a(e, "ty"), a(e, "ref"))))))
    fn_impl(
        e,
        x,
        "h_gep_field",
        body(
            e,
            e.let("fields", acc(e, xx(e), a(e, "st"), "lstruct", "fields")),
            e.let(
                "st", e.rec(e.p("i", e.int_of(0)), e.p("idx", e.int_of(-1)), e.p("fty", e.option_type_lowered_none()))
            ),
            e.foreach(
                e.v("fields"),
                "f0",
                e.seq(
                    e.let("f", e.v("f0")),
                    e.if_only(
                        e.eq(e.call_m(e.v("f"), "name", e.tup()), a(e, "name")),
                        e.seq(
                            e.mb.set(e.fld(e.v("st"), "idx"), e.fld(e.v("st"), "i")),
                            e.mb.set(
                                e.fld(e.v("st"), "fty"), e.option_type_lowered_some(e.call_m(e.v("f"), "ty", e.tup()))
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("st"), "i")),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "idx"), num(e, -1)),
                ret_m(
                    e,
                    hf_rec(
                        e,
                        "h_gep_tail",
                        e.p("xx", xx(e)),
                        e.p("loc", loc(e)),
                        e.p("mod", a(e, "mod")),
                        e.p("st", a(e, "st")),
                        e.p("ptr", a(e, "ptr")),
                        e.p("name", a(e, "name")),
                    ),
                ),
            ),
            e.let("tailo", acc(e, xx(e), a(e, "st"), "lstruct", "tail")),
            e.if_only(
                and_b(
                    e,
                    e.fld(e.v("tailo"), "is_some"),
                    or_b(
                        e,
                        e.eq(a(e, "name"), e.s("next")),
                        e.fld(
                            hf_rec(
                                e, "h_tail_view", e.p("tail", e.fld(e.v("tailo"), "value")), e.p("name", a(e, "name"))
                            ),
                            "is_some",
                        ),
                    ),
                ),
                throw_err(
                    e, loc(e), e.cat(e.s("struct field "), a(e, "name"), e.s(" is ambiguous with the struct tail"))
                ),
            ),
            e.let("i32", _int_ty(e, "i32")),
            e.let(
                "g",
                hf_rec(
                    e,
                    "h_gep",
                    e.p("loc", loc(e)),
                    e.p("mod", a(e, "mod")),
                    e.p("base", a(e, "st")),
                    e.p("ptr", a(e, "ptr")),
                    e.p(
                        "idx",
                        e.list_new(
                            lt(e, "lval"),
                            _lval_new(e, e.v("i32"), e.s("0")),
                            _lval_new(e, e.v("i32"), to_str(e, e.fld(e.v("st"), "idx"))),
                        ),
                    ),
                ),
            ),
            e.let("r", _lv_ref(e, _lval_of(e, e.v("g")))),
            e.ret(cv_of(e, cve_code(e, e.v("g")), _lval_mem(e, e.fld(e.v("st"), "fty", "value"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gep_index",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let(
                "k",
                e.if_else(
                    _is_llvm(e, xx(e), a(e, "key")),
                    _ssa(e, xx(e), loc(e), a(e, "mod"), a(e, "key")),
                    unwrap_cve_t(e, cast_value(e, xx(e), loc(e), _int_ty(e, "i32"), a(e, "key"))),
                ),
            ),
            e.if_only(
                e.not_(has(e, xx(e), cve_type(e, e.v("k")), "lint")), throw_err(e, loc(e), "index must be an integer")
            ),
            _append_code(e, e.v("out"), cve_code(e, e.v("k"))),
            e.let(
                "g",
                hf_rec(
                    e,
                    "h_gep",
                    e.p("loc", loc(e)),
                    e.p("mod", a(e, "mod")),
                    e.p("base", a(e, "base")),
                    e.p("ptr", a(e, "ptr")),
                    e.p("idx", e.list_new(lt(e, "lval"), _lval_of(e, e.v("k")))),
                ),
            ),
            _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
            e.let("r", _lv_ref(e, _lval_of(e, e.v("g")))),
            e.ret(cv_of(e, _code_of(e, e.v("out")), _lval_mem(e, a(e, "base"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_tail_view",
        body(
            e,
            e.foreach(
                e.call_m(a(e, "tail"), "views", e.tup()),
                "v0",
                e.seq(
                    e.let("v", e.v("v0")),
                    e.if_only(
                        e.eq(e.call_m(e.v("v"), "name", e.tup()), a(e, "name")),
                        ret_m(e, e.option_type_lowered_some(e.call_m(e.v("v"), "ty", e.tup()))),
                    ),
                ),
            ),
            e.ret(e.option_type_lowered_none()),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gep_tail",
        body(
            e,
            e.let("tailo", acc(e, xx(e), a(e, "st"), "lstruct", "tail")),
            e.if_only(
                e.not_(e.fld(e.v("tailo"), "is_some")),
                throw_err(e, loc(e), e.cat(e.s("no struct field named "), a(e, "name"))),
            ),
            e.let("tl", e.fld(e.v("tailo"), "value")),
            e.let("out", _insts_new(e)),
            e.let("i64", _int_ty(e, "i64")),
            e.if_only(
                e.not_(e.eq(a(e, "name"), e.s("next"))),
                e.seq(
                    e.let("vo", hf_rec(e, "h_tail_view", e.p("tail", e.v("tl")), e.p("name", a(e, "name")))),
                    e.if_only(
                        e.not_(e.fld(e.v("vo"), "is_some")),
                        throw_err(e, loc(e), e.cat(e.s("no struct field or tail view named "), a(e, "name"))),
                    ),
                    e.let("rv", _fresh(e, a(e, "mod"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "gep",
                            e.p("res", e.v("rv")),
                            e.p("base", a(e, "st")),
                            e.p("ptr", a(e, "ptr")),
                            e.p("idx", e.list_new(lt(e, "lval"), _lval_new(e, e.v("i64"), e.s("1")))),
                        ),
                    ),
                    ret_m(
                        e,
                        cv_of(
                            e,
                            _code_of(e, e.v("out")),
                            _lval_new(e, mk(e, "lt_ptr", e.p("pointee", e.fld(e.v("vo"), "value"))), e.v("rv")),
                        ),
                    ),
                ),
            ),
            e.let("fields", acc(e, xx(e), a(e, "st"), "lstruct", "fields")),
            e.let("after", e.call_m(e.v("tl"), "after", e.tup())),
            e.let(
                "fi", e.rec(e.p("i", e.int_of(0)), e.p("idx", e.int_of(-1)), e.p("fty", e.option_type_lowered_none()))
            ),
            e.foreach(
                e.v("fields"),
                "f0",
                e.seq(
                    e.let("f", e.v("f0")),
                    e.if_only(
                        e.eq(e.call_m(e.v("f"), "name", e.tup()), e.v("after")),
                        e.seq(
                            e.mb.set(e.fld(e.v("fi"), "idx"), e.fld(e.v("fi"), "i")),
                            e.mb.set(
                                e.fld(e.v("fi"), "fty"), e.option_type_lowered_some(e.call_m(e.v("f"), "ty", e.tup()))
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("fi"), "i")),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("fi"), "idx"), num(e, -1)),
                throw_err(e, loc(e), e.cat(e.s("struct tail: no field named "), e.v("after"))),
            ),
            e.let("aty", e.fld(e.v("fi"), "fty", "value")),
            e.let("i32", _int_ty(e, "i32")),
            e.let("ra", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "gep",
                    e.p("res", e.v("ra")),
                    e.p("base", a(e, "st")),
                    e.p("ptr", a(e, "ptr")),
                    e.p(
                        "idx",
                        e.list_new(
                            lt(e, "lval"),
                            _lval_new(e, e.v("i32"), e.s("0")),
                            _lval_new(e, e.v("i32"), to_str(e, e.fld(e.v("fi"), "idx"))),
                        ),
                    ),
                ),
            ),
            e.let("re", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "gep",
                    e.p("res", e.v("re")),
                    e.p("base", e.v("aty")),
                    e.p("ptr", e.v("ra")),
                    e.p("idx", e.list_new(lt(e, "lval"), _lval_new(e, e.v("i64"), e.s("1")))),
                ),
            ),
            e.let("cur", e.rec(e.p("ty", e.option_type_lowered_some(a(e, "st"))), e.p("ptr", a(e, "ptr")))),
            e.foreach(
                e.call_m(e.v("tl"), "len", e.tup()),
                "seg0",
                e.seq(
                    e.let("seg", e.v("seg0")),
                    e.if_only(
                        e.not_(has(e, xx(e), e.fld(e.v("cur"), "ty", "value"), "lstruct")),
                        throw_err(e, loc(e), e.cat(e.s("struct tail length path: not a struct at "), e.v("seg"))),
                    ),
                    e.let(
                        "g",
                        hf_rec(
                            e,
                            "h_gep_field",
                            e.p("xx", xx(e)),
                            e.p("loc", loc(e)),
                            e.p("mod", a(e, "mod")),
                            e.p("st", e.fld(e.v("cur"), "ty", "value")),
                            e.p("ptr", e.fld(e.v("cur"), "ptr")),
                            e.p("name", e.v("seg")),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
                    e.let("gl", _lval_of(e, e.v("g"))),
                    e.mb.set(e.fld(e.v("cur"), "ty"), e.option_type_lowered_some(_lv_ty(e, e.v("gl")))),
                    e.mb.set(e.fld(e.v("cur"), "ptr"), _lv_mem(e, e.v("gl"))),
                ),
            ),
            e.let("lty", e.fld(e.v("cur"), "ty", "value")),
            e.if_only(
                e.not_(has(e, xx(e), e.v("lty"), "lint")),
                throw_err(e, loc(e), "struct tail length must be an integer field"),
            ),
            e.let("rl", _fresh(e, a(e, "mod"))),
            push(e, e.v("out"), _load_inst(e, loc(e), e.v("rl"), e.v("lty"), e.fld(e.v("cur"), "ptr"))),
            e.let("len", e.rec(e.p("ref", e.v("rl")))),
            e.if_only(
                e.mb.operator_lt(acc(e, xx(e), e.v("lty"), "lint", "bits"), num(e, 64)),
                e.seq(
                    e.let("rz", _fresh(e, a(e, "mod"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "conv",
                            e.p("res", e.v("rz")),
                            e.p("op", e.s("zext")),
                            e.p("a", _lval_new(e, e.v("lty"), e.v("rl"))),
                            e.p("to", e.v("i64")),
                        ),
                    ),
                    e.mb.set(e.fld(e.v("len"), "ref"), e.v("rz")),
                ),
            ),
            e.let("pi", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "conv",
                    e.p("res", e.v("pi")),
                    e.p("op", e.s("ptrtoint")),
                    e.p("a", _lval_new(e, mk(e, "lt_ptr", e.p("pointee", a(e, "st"))), a(e, "ptr"))),
                    e.p("to", e.v("i64")),
                ),
            ),
            e.let("ei", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "conv",
                    e.p("res", e.v("ei")),
                    e.p("op", e.s("ptrtoint")),
                    e.p("a", _lval_new(e, mk(e, "lt_ptr", e.p("pointee", e.v("aty"))), e.v("re"))),
                    e.p("to", e.v("i64")),
                ),
            ),
            e.let("align", e.call_m(e.v("tl"), "align", e.tup())),
            e.let("off", _fresh(e, a(e, "mod"))),
            _inst_binop_i64(e, loc(e), "off", "sub", e.v("ei"), e.v("pi")),
            e.let("tot", _fresh(e, a(e, "mod"))),
            _inst_binop_i64(e, loc(e), "tot", "add", e.v("off"), e.fld(e.v("len"), "ref")),
            e.let("up", _fresh(e, a(e, "mod"))),
            _inst_binop_i64(
                e, loc(e), "up", "add", e.v("tot"), to_str(e, e.mb.operator_sub(e.v("align"), e.int_of(1)))
            ),
            e.let("al", _fresh(e, a(e, "mod"))),
            _inst_binop_i64(e, loc(e), "al", "and", e.v("up"), to_str(e, e.mb.operator_sub(e.int_of(0), e.v("align")))),
            e.let("nx", _fresh(e, a(e, "mod"))),
            push(
                e,
                e.v("out"),
                _inst(
                    e,
                    loc(e),
                    "gep",
                    e.p("res", e.v("nx")),
                    e.p("base", _int_ty(e, "i8")),
                    e.p("ptr", a(e, "ptr")),
                    e.p("idx", e.list_new(lt(e, "lval"), _lval_new(e, e.v("i64"), e.v("al")))),
                ),
            ),
            e.ret(
                cv_of(e, _code_of(e, e.v("out")), _lval_new(e, mk(e, "lt_ptr", e.p("pointee", a(e, "st"))), e.v("nx")))
            ),
        ),
    )
    _fn_def(e, x, "c_ptr", ty(e), ty(e))
    fn_impl(e, x, "c_ptr", body(e, e.ret(mk(e, "lt_ptr", e.p("pointee", e.v("arg"))))))
    _fn_def(e, x, "c_array", e.rec(e.p("elem", ty(e)), e.p("count", int_t(e))), ty(e))
    fn_impl(e, x, "c_array", body(e, e.ret(mk(e, "lt_arr", e.p("elem", a(e, "elem")), e.p("count", a(e, "count"))))))
    _fn_def(e, x, "c_field", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))), t(e, "lfield"))
    fn_impl(e, x, "c_field", body(e, e.ret(mk(e, "lfield", e.p("name", a(e, "name")), e.p("ty", a(e, "ty"))))))
    _fn_def(e, x, "c_tuple", e.list_type(ty(e)), ty(e))
    fn_impl(e, x, "c_tuple", body(e, e.ret(mk(e, "lt_tuple", e.p("elems", e.v("arg"))))))
    _fn_def(e, x, "c_struct", e.rec(e.p("name", str_(e)), e.p("fields", e.list_type(t(e, "lfield")))), ty(e))
    fn_impl(
        e,
        x,
        "c_struct",
        body(
            e,
            e.ret(
                mk(
                    e,
                    "lt_struct",
                    e.p("name", a(e, "name")),
                    e.p("fields", a(e, "fields")),
                    e.p("tail", e.opt_none(lt(e, "ltail"))),
                )
            ),
        ),
    )
    _fn_def(
        e,
        x,
        "c_tail",
        e.rec(
            e.p("views", e.list_type(t(e, "lfield"))),
            e.p("after", str_(e)),
            e.p("len", e.list_type(str_(e))),
            e.p("align", int_t(e)),
        ),
        t(e, "ltail"),
    )
    fn_impl(
        e,
        x,
        "c_tail",
        body(
            e,
            e.ret(
                mk(
                    e,
                    "ltail",
                    e.p("views", a(e, "views")),
                    e.p("after", a(e, "after")),
                    e.p("len", a(e, "len")),
                    e.p("align", a(e, "align")),
                )
            ),
        ),
    )
    _fn_def(
        e,
        x,
        "c_struct_tail",
        e.rec(e.p("name", str_(e)), e.p("fields", e.list_type(t(e, "lfield"))), e.p("tail", t(e, "ltail"))),
        ty(e),
    )
    fn_impl(
        e,
        x,
        "c_struct_tail",
        body(
            e,
            e.ret(
                mk(
                    e,
                    "lt_struct",
                    e.p("name", a(e, "name")),
                    e.p("fields", a(e, "fields")),
                    e.p("tail", e.opt_some(lt(e, "ltail"), a(e, "tail"))),
                )
            ),
        ),
    )
    for varargs in [False, True]:
        name = "c_fn_varargs" if varargs else "c_fn"
        _fn_def(e, x, name, e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e))), ty(e))
        fn_impl(
            e,
            x,
            name,
            body(
                e,
                e.ret(
                    mk(e, "lt_fn", e.p("params", a(e, "params")), e.p("ret", a(e, "ret")), e.p("varargs", e.b(varargs)))
                ),
            ),
        )
    _fn_def(e, x, "c_range", ty(e), ty(e))
    _fn_def(
        e,
        x,
        "h_range_call",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("elem", ty(e)), e.p("cv", cve_t(e))),
        e.call(e.mb.types_eresult(), cve_t(e)),
    )
    fn_impl(
        e,
        x,
        "h_range_call",
        body(
            e,
            e.let(
                "a2",
                unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), a(e, "elem"), a(e, "cv")), cve_t(e))),
            ),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        mk(
                            e,
                            "lrange",
                            e.p("t", mk(e, "lrange_t", e.p("elem", a(e, "elem")))),
                            e.p("code", cve_code(e, e.v("a2"))),
                            e.p("n", _lval_of(e, e.v("a2"))),
                        ),
                    ),
                )
            ),
        ),
    )
    # Dependencies: a function or a zeroed global that a module gets only when code uses it. `func_dep` and
    # `alloc_dep` make callable const functions; a call defines the item in the current module on first use (by
    # name), then calls the function or yields the global's pointer. The definition travels in the const function.
    _fn_def(
        e,
        x,
        "h_funcdep_call",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("id", target_mb.unique_t(e)),
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
                target_mb.def_once(
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
            e.let("ref", cv_of(e, code_none(e, loc(e)), _lval_new(e, a(e, "ty"), e.v("fref")))),
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
            e.p("id", target_mb.unique_t(e)),
            e.p("name", str_(e)),
            e.p("ty", ty(e)),
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
                    e.rec(e.p("id", a(e, "id")), e.p("name", a(e, "name")), e.p("ty", a(e, "ty"))),
                ),
            ),
            e.let("pty", mk(e, "lt_ptr", e.p("pointee", a(e, "ty")))),
            e.ret(cv_of(e, code_none(e, loc(e)), _lval_new(e, e.v("pty"), e.v("ref")))),
        ),
    )
    # Constant data as a dependency: `data_dep({name, elem, values})` (an array of integers of the element type) and
    # `cstr_dep({name, text})` (NUL-terminated UTF-8) define a constant global on first use and yield its pointer.
    _fn_def(
        e,
        x,
        "h_datadep_call",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("id", target_mb.unique_t(e)),
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
                e.not_(has(e, xx(e), a(e, "elem"), "lint")),
                throw_err(
                    e, loc(e), e.cat(e.s("llvm data_dep elem must be an integer type, not "), ty_desc(e, a(e, "elem")))
                ),
            ),
            e.let("min", acc(e, xx(e), a(e, "elem"), "lint", "min")),
            e.let("max", acc(e, xx(e), a(e, "elem"), "lint", "max")),
            e.let("eir", e.call_m(e.v("mod"), "ir", a(e, "elem"))),
            e.let("parts", e.list_new(str_(e))),
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
                                e.s("llvm data_dep value "),
                                to_str(e, e.v("v")),
                                e.s(" is out of range for "),
                                ty_desc(e, a(e, "elem")),
                            ),
                        ),
                    ),
                    push(e, e.v("parts"), e.cat(e.v("eir"), e.s(" "), to_str(e, e.v("v")))),
                ),
            ),
            count_let(e, "n"),
            count_loop(e, "n", a(e, "values")),
            e.let(
                "ref",
                e.call_m(
                    e.v("mod"),
                    "const_once",
                    e.rec(
                        e.p("id", a(e, "id")),
                        e.p("name", a(e, "name")),
                        e.p("ty", mk(e, "lt_arr", e.p("elem", a(e, "elem")), e.p("count", e.fld(e.v("n"), "v")))),
                        e.p("init", e.cat(e.s("["), e.join(e.v("parts"), ", "), e.s("]"))),
                    ),
                ),
            ),
            e.ret(
                cv_of(e, code_none(e, loc(e)), _lval_new(e, mk(e, "lt_ptr", e.p("pointee", a(e, "elem"))), e.v("ref")))
            ),
        ),
    )
    # The dependencies as callable types: their function values define them in the module on first use.
    target_mb.def_empty_binding(e, x, "lebinding", "llvm empty value binding")
    target_mb.dep_type(
        e,
        x,
        "lfdep",
        "llvm function dependency",
        [("name", str_(e)), ("params", e.list_type(str_(e))), ("ty", ty(e)), ("body", e.mb.types_expr())],
        "h_funcdep_call",
        True,
        "lebinding",
    )
    target_mb.dep_type(
        e,
        x,
        "ladep",
        "llvm allocation dependency",
        [("name", str_(e)), ("ty", ty(e))],
        "h_allocdep_call",
        False,
        "lebinding",
    )
    target_mb.dep_type(
        e,
        x,
        "lddep",
        "llvm data dependency",
        [("name", str_(e)), ("elem", ty(e)), ("values", e.list_type(int_t(e)))],
        "h_datadep_call",
        False,
        "lebinding",
    )
    # The range constructor as a callable type: its function value makes the range of its argument.
    def_iface(e, x, "lrng_m", e.p("elem", ty(e)))
    def_obj(e, x, "lrng", "llvm range constructor", e.rec(e.p("elem", ty(e))))
    x.append(e.impl_interface(e.v("lrng"), t(e, "lrng_m"), e.p("elem", in_(e, "elem"))))
    self_type(
        e,
        x,
        "lrng",
        e.cat(e.s("range("), bim0(e, ty(e), "desc", in_(e, "elem")), e.s(") constructor")),
        e.aspect_dispatch(asp_id(e, "function"), asp_id(e, "bind")),
        target_mb.can_cast_from_unit(e),
        target_mb.cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lrng_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "lrng_m", "elem")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lrng"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.ret(
                        hf_rec(
                            e,
                            "h_range_call",
                            e.p("xx", xx(e)),
                            e.p("loc", loc(e)),
                            e.p("elem", in_(e, "elem")),
                            e.p("cv", a(e, "argument")),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(e.impl_interface(e.v("lrng"), e.mb.eval_aspect_bind(), e.p("bind", target_mb.bind_empty(e, "lebinding"))))
    fn_impl(e, x, "c_range", body(e, e.ret(e.mb.as_(mk(e, "lrng", e.p("elem", e.v("arg"))), ty(e)))))
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
                        "lfdep",
                        e.p("id", target_mb.fresh_unique(e)),
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
                        "lddep",
                        e.p("id", target_mb.fresh_unique(e)),
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
    _fn_def(e, x, "c_alloc_dep", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))), ty(e))
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
                        "ladep",
                        e.p("id", target_mb.fresh_unique(e)),
                        e.p("name", a(e, "name")),
                        e.p("ty", a(e, "ty")),
                    ),
                    ty(e),
                )
            ),
        ),
    )
    _fn_def(e, x, "c_global_t", e.rec(e.p("ty", ty(e)), e.p("mem", bool_t(e))), ty(e))
    fn_impl(e, x, "c_global_t", body(e, e.ret(mk(e, "lt_global", e.p("base", a(e, "ty")), e.p("mem", a(e, "mem"))))))
    _fn_def(e, x, "c_extern_t", e.rec(e.p("name", str_(e)), e.p("ty", ty(e)), e.p("libs", e.list_type(str_(e)))), ty(e))
    fn_impl(
        e,
        x,
        "c_extern_t",
        body(
            e, e.ret(mk(e, "lt_extern", e.p("name", a(e, "name")), e.p("base", a(e, "ty")), e.p("libs", a(e, "libs"))))
        ),
    )
    for name in ["h_init", "h_init_int", "h_init_float", "h_init_ptr", "h_init_arr", "h_init_struct"]:
        _fn_def(
            e, x, name, e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("ty", ty(e)), e.p("cv", cve_t(e))), cve_t(e)
        )
        fn_throws(e, name, errs_t(e))
    fn_impl(
        e,
        x,
        "h_init",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "initializer has no value")),
            e.if_only(has(e, xx(e), a(e, "ty"), "lint"), ret_m(e, hf(e, "h_init_int", e.v("arg")))),
            e.if_only(has(e, xx(e), a(e, "ty"), "lfloat"), ret_m(e, hf(e, "h_init_float", e.v("arg")))),
            e.if_only(has(e, xx(e), a(e, "ty"), "lptr"), ret_m(e, hf(e, "h_init_ptr", e.v("arg")))),
            e.if_only(has(e, xx(e), a(e, "ty"), "larr"), ret_m(e, hf(e, "h_init_arr", e.v("arg")))),
            e.if_only(
                e.not_(has(e, xx(e), a(e, "ty"), "lstruct")),
                throw_err(e, loc(e), e.cat(e.s("llvm "), ty_desc(e, a(e, "ty")), e.s(" cannot be initialized"))),
            ),
            e.ret(hf(e, "h_init_struct", e.v("arg"))),
        ),
    )
    any_host_int = dfalse(e)
    host_int_fits = []
    for host in HOST_INTS:
        is_host = is_equal(e, xx(e), e.mb.builtin("types", host.name), e.v("st"))
        any_host_int = or_b(e, is_host, any_host_int)
        host_int_fits.append(
            e.if_only(
                and_b(
                    e,
                    is_host,
                    or_b(
                        e,
                        e.mb.operator_lt(e.n(host.min), acc(e, xx(e), a(e, "ty"), "lint", "min")),
                        e.mb.operator_gt(e.n(host.max), acc(e, xx(e), a(e, "ty"), "lint", "max")),
                    ),
                ),
                throw_err(
                    e, loc(e), e.cat(e.s(("host " + host.name) + " values do not fit llvm "), ty_desc(e, a(e, "ty")))
                ),
            )
        )
    fn_impl(
        e,
        x,
        "h_init_int",
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
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
                        throw_err(e, loc(e), "integer initializer is not integral"),
                    ),
                    e.if_only(
                        or_b(
                            e,
                            e.mb.operator_lt(e.v("d"), acc(e, xx(e), a(e, "ty"), "lint", "min")),
                            e.mb.operator_gt(e.v("d"), acc(e, xx(e), a(e, "ty"), "lint", "max")),
                        ),
                        throw_err(e, loc(e), "integer initializer out of range"),
                    ),
                    e.let("s", to_str(e, e.v("l"))),
                    ret_m(e, str_cve(e, e.v("s"))),
                ),
            ),
            e.if_only(e.not_(any_host_int), _init_mismatch(e, e.v("st"))),
            e.if_only(
                and_b(
                    e,
                    is_equal(e, xx(e), e.mb.builtin("types", "byte"), e.v("st")),
                    e.eq(acc(e, xx(e), a(e, "ty"), "lint", "bits"), num(e, 8)),
                ),
                ret_m(
                    e,
                    host_cve(
                        e,
                        e.stage(
                            to_str(e, e.mb.operator_and(e.mb.as_(graft(e, a(e, "cv")), e.mb.types_int()), num(e, 255)))
                        ),
                    ),
                ),
            ),
            e.seq(*host_int_fits),
            e.ret(host_cve(e, e.stage(to_str(e, graft(e, a(e, "cv")))))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_init_float",
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.let("bits", acc(e, xx(e), a(e, "ty"), "lfloat", "bits")),
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
                            e.eq(e.v("bits"), num(e, 64)),
                            to_str(e, e.v("d")),
                            to_str(e, e.mb.as_(e.mb.as_(e.v("d"), e.types_float()), e.types_double())),
                        ),
                    ),
                    ret_m(e, str_cve(e, e.v("s"))),
                ),
            ),
            e.if_only(e.not_(is_equal(e, xx(e), e.types_double(), e.v("st"))), _init_mismatch(e, e.v("st"))),
            e.if_only(e.eq(e.v("bits"), num(e, 64)), ret_m(e, host_cve(e, e.stage(to_str(e, graft(e, a(e, "cv"))))))),
            e.ret(
                host_cve(
                    e, e.stage(to_str(e, e.mb.as_(e.mb.as_(graft(e, a(e, "cv")), e.types_float()), e.types_double())))
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_init_ptr",
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(
                has(e, xx(e), e.v("st"), "lgtype_m"),
                e.seq(
                    e.if_only(
                        e.not_(is_runtime(e, a(e, "cv"))),
                        e.seq(e.let("s", hf(e, "h_gref", a(e, "cv"))), ret_m(e, str_cve(e, e.v("s")))),
                    ),
                    ret_m(e, retag_runtime(e, a(e, "cv"), str_(e))),
                ),
            ),
            e.if_only(
                has(e, xx(e), e.v("st"), "lgref_m"),
                e.seq(
                    e.let("lgref_ty", lt(e, "lgref")),
                    e.let("pointee", acc(e, xx(e), a(e, "ty"), "lptr", "pointee")),
                    ret_m(
                        e,
                        host_cve(
                            e,
                            e.stage(
                                e.call_m(
                                    e.call(
                                        e.mb.must_reinterpret(), e.tup(graft(e, a(e, "cv")), e.lower(e.v("lgref_ty")))
                                    ),
                                    "ptr_ref",
                                    e.lower(e.v("pointee")),
                                )
                            ),
                        ),
                    ),
                ),
            ),
            _init_mismatch(e, e.v("st")),
        ),
    )
    host_list_inits = []
    def_obj(e, x, "llist", "llvm list initializer", e.rec(e.p("ir", str_(e)), e.p("count", int_t(e))))
    accessor(e, x, "llist", "ir", str_(e))
    accessor(e, x, "llist", "count", int_t(e))
    for prim in LLVM_PRIMS:
        fmt = "h_fmt_list_" + prim.llvm
        fn = "h_init_list_" + prim.llvm
        host_t = e.mb.builtin("types", prim.host)
        _fn_def(e, x, fmt, e.list_type(host_t), t(e, "llist"))
        fn_impl(
            e,
            x,
            fmt,
            body(
                e,
                e.let("parts", e.list_new(str_(e))),
                count_let(e, "n"),
                e.foreach(
                    e.v("arg"),
                    "v",
                    e.seq(
                        push(
                            e,
                            e.v("parts"),
                            e.cat(
                                e.s(prim.ir + " "),
                                to_str(e, e.mb.as_(e.v("v"), e.types_double()) if prim.host == "float" else e.v("v")),
                            ),
                        ),
                        e.incr(e.fld(e.v("n"), "v")),
                    ),
                ),
                e.ret(
                    mk(
                        e,
                        "llist",
                        e.p("ir", e.cat(e.s("["), e.join(e.v("parts"), ", "), e.s("]"))),
                        e.p("count", e.fld(e.v("n"), "v")),
                    )
                ),
            ),
        )
        _fn_def(e, x, fn, e.rec(e.p("count", int_t(e)), e.p("values", e.list_type(host_t))), str_(e))
        fn_impl(
            e,
            x,
            fn,
            body(
                e,
                e.let("list", hf(e, fmt, a(e, "values"))),
                e.if_only(
                    e.not_(e.eq(e.call_m(e.v("list"), "count", e.tup()), a(e, "count"))),
                    e.mb.panic(
                        e.cat(
                            e.s("llvm: array initializer has "),
                            to_str(e, e.call_m(e.v("list"), "count", e.tup())),
                            e.s(" elements, expected "),
                            to_str(e, a(e, "count")),
                        )
                    ),
                ),
                e.ret(e.call_m(e.v("list"), "ir", e.tup())),
            ),
        )
        is_elem = _is_prim(e, xx(e), e.v("elem"), prim)
        host_list_inits.append(
            e.if_only(
                is_elem,
                e.seq(
                    e.let("values", unwrap_cve_t(e, cast_value(e, xx(e), loc(e), e.list_type(host_t), a(e, "cv")))),
                    e.let("init_list", e.lower_v(fn)),
                    ret_m(
                        e,
                        host_cve(
                            e,
                            e.stage(
                                e.call(
                                    e.lower(e.v("init_list")),
                                    e.rec(e.p("count", e.lower(e.v("count"))), e.p("values", graft(e, e.v("values")))),
                                )
                            ),
                        ),
                    ),
                ),
            )
        )
    fn_impl(
        e,
        x,
        "h_init_arr",
        body(
            e,
            e.let("elem", acc(e, xx(e), a(e, "ty"), "larr", "elem")),
            e.let("count", acc(e, xx(e), a(e, "ty"), "larr", "count")),
            e.let("eir", _ir_fn(e, xx(e), e.opt_none(lt(e, "lmod")), e.v("elem"))),
            e.let("st", cve_type(e, a(e, "cv"))),
            e.seq(*host_list_inits),
            e.let("tk", lookup(e, xx(e), e.v("st"), asp_iface(e, "tuple"))),
            e.if_only(
                e.fld(e.v("tk"), "is_some"),
                e.seq(
                    e.let("parts", e.list_new(cve_t(e))),
                    e.foreach(
                        bim(
                            e,
                            asp_iface(e, "tuple"),
                            "take_elements",
                            e.fld(e.v("tk"), "value"),
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                        ),
                        "er",
                        e.seq(
                            e.let("v", _init_fn(e, e.v("elem"), unwrap_cve_t(e, e.v("er")))),
                            push(
                                e,
                                e.v("parts"),
                                host_cve(e, e.stage(e.cat(e.lower(e.v("eir")), e.s(" "), graft(e, e.v("v"))))),
                            ),
                        ),
                    ),
                    count_let(e, "n"),
                    count_loop(e, "n", e.v("parts")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("n"), "v"), e.v("count"))),
                        throw_err(
                            e,
                            loc(e),
                            e.cat(
                                e.s("array initializer has "),
                                to_str(e, e.fld(e.v("n"), "v")),
                                e.s(" elements, expected "),
                                to_str(e, e.v("count")),
                            ),
                        ),
                    ),
                    ret_m(e, _fold_join(e, e.v("parts"), "[", "]")),
                ),
            ),
            _init_mismatch(e, e.v("st")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_init_struct",
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.let("rk", lookup(e, xx(e), e.v("st"), asp_iface(e, "record"))),
            e.if_only(e.not_(e.fld(e.v("rk"), "is_some")), _init_mismatch(e, e.v("st"))),
            e.let("sfields", acc(e, xx(e), a(e, "ty"), "lstruct", "fields")),
            e.let("kc", e.rec(e.p("n", e.int_of(0)), e.p("bad", e.dstr("")))),
            e.foreach(
                bim0(e, asp_iface(e, "record"), "field_types", e.fld(e.v("rk"), "value")),
                "en",
                e.seq(
                    e.incr(e.fld(e.v("kc"), "n")),
                    e.let("ks", key_str(e, e.fld(e.v("en"), "key"))),
                    e.let("hit", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("sfields"),
                        "f0",
                        e.if_only(
                            e.eq(e.call_m(e.v("f0"), "name", e.tup()), e.v("ks")),
                            e.mb.set(e.fld(e.v("hit"), "v"), num(e, 1)),
                        ),
                    ),
                    e.if_only(e.eq(e.fld(e.v("hit"), "v"), num(e, 0)), e.mb.set(e.fld(e.v("kc"), "bad"), e.v("ks"))),
                ),
            ),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("kc"), "bad"), e.s(""))),
                throw_err(
                    e,
                    loc(e),
                    e.cat(e.s("llvm "), ty_desc(e, a(e, "ty")), e.s(" has no field "), e.fld(e.v("kc"), "bad")),
                ),
            ),
            count_let(e, "sn"),
            count_loop(e, "sn", e.v("sfields")),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("kc"), "n"), e.fld(e.v("sn"), "v"))),
                throw_err(
                    e, loc(e), e.cat(e.s("initializer for llvm "), ty_desc(e, a(e, "ty")), e.s(" is missing fields"))
                ),
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("parts", e.list_new(cve_t(e))),
            e.foreach(
                e.v("sfields"),
                "f0",
                e.seq(
                    e.let("f", e.v("f0")),
                    e.let("fty", e.call_m(e.v("f"), "ty", e.tup())),
                    e.let("fir", _ir_fn(e, xx(e), e.opt_none(lt(e, "lmod")), e.v("fty"))),
                    e.let(
                        "v",
                        _init_fn(
                            e,
                            e.v("fty"),
                            unwrap_cve_t(e, e.call_m(e.v("fields"), "get", e.call_m(e.v("f"), "name", e.tup()))),
                        ),
                    ),
                    push(
                        e, e.v("parts"), host_cve(e, e.stage(e.cat(e.lower(e.v("fir")), e.s(" "), graft(e, e.v("v")))))
                    ),
                ),
            ),
            e.ret(_fold_join(e, e.v("parts"), "{ ", " }")),
        ),
    )
    accessor(e, x, "lval", "ty", ty(e))
    method(
        e,
        x,
        "lval",
        "ref",
        e.tup(),
        str_(e),
        e.match_of(
            in_(e, "source"),
            "s",
            None,
            e.p("ssa", e.v("s")),
            e.p("mem", e.mb.panic(e.s("llvm: value in memory used as an operand"))),
        ),
    )
    method(
        e,
        x,
        "lval",
        "mem",
        e.tup(),
        str_(e),
        e.match_of(
            in_(e, "source"),
            "s",
            None,
            e.p("mem", e.v("s")),
            e.p("ssa", e.mb.panic(e.s("llvm: register value has no address"))),
        ),
    )
    method(
        e,
        x,
        "lval",
        "is_mem",
        e.tup(),
        e.mb.types_int(),
        e.match_of(in_(e, "source"), "s", None, e.p("mem", e.int_of(1)), e.p("ssa", e.int_of(0))),
    )
    x.append(
        e.impl_interface(
            e.v("lval"),
            e.mb.eval_value(),
            e.p("type", in_(e, "ty")),
            e.p("artifact_exporter", tm.artifact_exporter_impl(e, "lval")),
        )
    )
    accessor(e, x, "lfield", "name", str_(e))
    accessor(e, x, "lfield", "ty", ty(e))
    accessor(e, x, "ltail", "views", e.list_type(t(e, "lfield")))
    accessor(e, x, "ltail", "after", str_(e))
    accessor(e, x, "ltail", "len", e.list_type(str_(e)))
    accessor(e, x, "ltail", "align", int_t(e))
    accessor(e, x, "ltarget", "mod", _lmod_t(e))
    accessor(e, x, "lirctx", "xx", xx_t(e))
    accessor(e, x, "lirctx", "mod", _lmod_opt_t(e))
    accessor(e, x, "linst", "k", t(e, "linst_u"))
    accessor(e, x, "linst", "loc", _loc_opt_t(e))
    accessor(e, x, "lmod", "sip_key_id", target_mb.unique_t(e))
    accessor(e, x, "lmod", "sip_fn_id", target_mb.unique_t(e))
    for vo in ["lfield", "lglobal", "lalloca", "llabel", "linst", "lmod"]:
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))
    accessor(e, x, "lglobal", "name", str_(e))
    accessor(e, x, "lglobal", "ty", ty(e))
    accessor(e, x, "lglobal", "init", str_(e))
    accessor(e, x, "lalloca", "name", str_(e))
    accessor(e, x, "lalloca", "ty", ty(e))
    accessor(e, x, "llabel", "key", e.types_jump_key())
    accessor(e, x, "llabel", "name", str_(e))
    method(e, x, "lmod", "xx", e.tup(), e.types_expr_context(), in_(e, "xx", "value"))
    x.append(
        e.method_impl(
            e.v("lmod"),
            "set_xx",
            e.types_expr_context(),
            e.option_type_none(),
            e.stage(e.mb.set(in_(e, "xx"), e.opt_some(e.types_expr_context(), e.v("arg")))),
        )
    )
    method(
        e,
        x,
        "lmod",
        "fresh_n",
        e.tup(),
        e.mb.types_int(),
        e.seq(e.let("n", in_(e, "n")), e.incr(in_(e, "n")), e.ret(e.v("n"))),
    )
    method(e, x, "lmod", "fresh", e.tup(), str_(e), e.cat(e.s("%t"), to_str(e, e.call_m(outer(e), "fresh_n", e.tup()))))
    method(
        e,
        x,
        "lmod",
        "fresh_label",
        e.tup(),
        str_(e),
        e.cat(e.s("L"), to_str(e, e.call_m(outer(e), "fresh_n", e.tup()))),
    )
    method(
        e,
        x,
        "lmod",
        "slot",
        ty(e),
        str_(e),
        e.seq(
            e.let("name", e.cat(e.s("%s"), to_str(e, e.call_m(outer(e), "fresh_n", e.tup())))),
            push(e, in_(e, "slots"), mk(e, "lalloca", e.p("name", e.v("name")), e.p("ty", e.v("arg")))),
            e.ret(e.v("name")),
        ),
    )
    method(
        e,
        x,
        "lmod",
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
                        mk(e, "llabel", e.p("key", e.v("arg")), e.p("name", e.fld(e.v("st"), "name"))),
                    ),
                ),
            ),
            e.ret(e.fld(e.v("st"), "name")),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "ir",
        ty(e),
        str_(e),
        _ir_fn(e, in_(e, "xx", "value"), e.opt_some(lt(e, "lmod"), outer(e)), e.v("arg")),
    )
    method(
        e,
        x,
        "lmod",
        "use_struct",
        ty(e),
        str_(e),
        e.seq(
            e.let("name", acc(e, in_(e, "xx", "value"), e.v("arg"), "lstruct", "name")),
            e.let("st", e.rec(e.p("hit", e.int_of(0)))),
            e.foreach(
                in_(e, "structs"),
                "s",
                e.if_only(
                    e.eq(acc(e, in_(e, "xx", "value"), e.v("s"), "lstruct", "name"), e.v("name")),
                    e.mb.set(e.fld(e.v("st"), "hit"), num(e, 1)),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "hit"), num(e, 0)),
                e.seq(
                    push(e, in_(e, "structs"), e.v("arg")),
                    e.let("parts", e.list_new(str_(e))),
                    e.foreach(
                        acc(e, in_(e, "xx", "value"), e.v("arg"), "lstruct", "fields"),
                        "f0",
                        push(e, e.v("parts"), _ir_of(e, e.call_m(e.v("f0"), "ty", e.tup()))),
                    ),
                    push(
                        e,
                        in_(e, "struct_lines"),
                        e.cat(e.s("%"), e.v("name"), e.s(" = type { "), e.join(e.v("parts"), ", "), e.s(" }")),
                    ),
                ),
            ),
            e.ret(e.cat(e.s("%"), e.v("name"))),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "typed",
        _lval_t(e),
        str_(e),
        e.cat(_ir_of(e, _lv_ty(e, e.v("arg"))), e.s(" "), _lv_ref(e, e.v("arg"))),
    )
    method(
        e,
        x,
        "lmod",
        "params_ir",
        ty(e),
        str_(e),
        hf_rec(
            e,
            "h_params_ir",
            e.p("xx", in_(e, "xx", "value")),
            e.p("mod", e.opt_some(lt(e, "lmod"), outer(e))),
            e.p("ty", e.v("arg")),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "callsig",
        ty(e),
        str_(e),
        e.seq(
            e.ret(
                e.if_else(
                    im0(e, "lfn", "varargs", asp(e, in_(e, "xx", "value"), e.v("arg"), "lfn")),
                    _ir_of(e, e.v("arg")),
                    _ir_of(e, im0(e, "lfn", "ret", asp(e, in_(e, "xx", "value"), e.v("arg"), "lfn"))),
                )
            )
        ),
    )
    method(
        e,
        x,
        "lmod",
        "render_insts",
        e.list_type(t(e, "linst")),
        e.list_type(str_(e)),
        e.seq(
            e.let("out", e.list_new(str_(e))),
            e.let("st", e.rec(e.p("open", e.int_of(1)), e.p("pend", e.dstr("")))),
            e.let("refs", e.map_new(str_(e), e.mb.types_int_box())),
            e.foreach(
                e.v("arg"),
                "r0",
                e.match_of(
                    e.call_m(e.v("r0"), "k", e.tup()),
                    "p",
                    e.seq(),
                    e.p("label", e.call_m(e.v("refs"), "put", e.tup(p_(e, "name"), num(e, 0)))),
                ),
            ),
            e.foreach(
                e.v("arg"),
                "r1",
                e.match_of(
                    e.call_m(e.v("r1"), "k", e.tup()),
                    "p",
                    e.seq(),
                    e.p("br", _count_ref(e, p_(e, "name"))),
                    e.p("condbr", e.seq(_count_ref(e, p_(e, "t")), _count_ref(e, p_(e, "f")))),
                ),
            ),
            e.foreach(
                e.v("arg"),
                "i0",
                e.seq(
                    e.let("k", e.call_m(e.v("i0"), "k", e.tup())),
                    e.if_only(
                        e.eq(e.match_of(e.v("k"), "q", e.int_of(0), e.p("label", e.int_of(1))), num(e, 0)),
                        _flush_pend(e),
                    ),
                    e.match_of(
                        e.v("k"),
                        "p",
                        None,
                        e.p("meta", e.seq()),
                        e.p(
                            "label",
                            e.seq(
                                e.if_only(
                                    e.eq(e.fld(e.v("st"), "open"), num(e, 1)),
                                    push(e, e.v("out"), e.cat(e.s("  br label %"), p_(e, "name"))),
                                ),
                                e.if_else(
                                    and_b(
                                        e,
                                        e.eq(e.fld(e.v("st"), "pend"), p_(e, "name")),
                                        e.eq(
                                            e.mb.as_(e.call_m(e.v("refs"), "get", p_(e, "name")), e.mb.types_int()),
                                            num(e, 1),
                                        ),
                                    ),
                                    e.mb.set(e.fld(e.v("st"), "pend"), e.s("")),
                                    e.seq(_flush_pend(e), push(e, e.v("out"), e.cat(p_(e, "name"), e.s(":")))),
                                ),
                                e.mb.set(e.fld(e.v("st"), "open"), num(e, 1)),
                            ),
                        ),
                        e.p(
                            "br",
                            e.seq(
                                e.mb.set(e.fld(e.v("st"), "pend"), p_(e, "name")),
                                e.mb.set(e.fld(e.v("st"), "open"), num(e, 0)),
                            ),
                        ),
                        e.p(
                            "condbr",
                            _render_terminator(
                                e,
                                e.s("  br i1 "),
                                _lv_ref(e, p_(e, "cond")),
                                e.s(", label %"),
                                p_(e, "t"),
                                e.s(", label %"),
                                p_(e, "f"),
                            ),
                        ),
                        e.p(
                            "binop",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = "),
                                p_(e, "op"),
                                e.s(" "),
                                _ir_of(e, _lv_ty(e, p_(e, "a"))),
                                e.s(" "),
                                _lv_ref(e, p_(e, "a")),
                                e.s(", "),
                                _lv_ref(e, p_(e, "b")),
                            ),
                        ),
                        e.p(
                            "cmp",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = "),
                                p_(e, "op"),
                                e.s(" "),
                                _ir_of(e, _lv_ty(e, p_(e, "a"))),
                                e.s(" "),
                                _lv_ref(e, p_(e, "a")),
                                e.s(", "),
                                _lv_ref(e, p_(e, "b")),
                            ),
                        ),
                        e.p(
                            "unop",
                            _render_arm(
                                e, e.s("  "), p_(e, "res"), e.s(" = "), p_(e, "op"), e.s(" "), _typed_of(e, p_(e, "a"))
                            ),
                        ),
                        e.p(
                            "conv",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = "),
                                p_(e, "op"),
                                e.s(" "),
                                _typed_of(e, p_(e, "a")),
                                e.s(" to "),
                                _ir_of(e, p_(e, "to")),
                            ),
                        ),
                        e.p(
                            "load",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = load "),
                                _ir_of(e, p_(e, "ty")),
                                e.s(", ptr "),
                                p_(e, "ptr"),
                            ),
                        ),
                        e.p(
                            "store",
                            _render_arm(e, e.s("  store "), _typed_of(e, p_(e, "val")), e.s(", ptr "), p_(e, "ptr")),
                        ),
                        e.p(
                            "gep",
                            e.seq(
                                e.let("parts", e.list_new(str_(e))),
                                e.foreach(p_(e, "idx"), "ix", push(e, e.v("parts"), _typed_of(e, e.v("ix")))),
                                push(
                                    e,
                                    e.v("out"),
                                    e.cat(
                                        e.s("  "),
                                        p_(e, "res"),
                                        e.s(" = getelementptr inbounds "),
                                        _ir_of(e, p_(e, "base")),
                                        e.s(", ptr "),
                                        p_(e, "ptr"),
                                        e.s(", "),
                                        e.join(e.v("parts"), ", "),
                                    ),
                                ),
                                e.mb.set(e.fld(e.v("st"), "open"), num(e, 1)),
                            ),
                        ),
                        e.p(
                            "insv",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = insertvalue "),
                                e.if_else(
                                    e.fld(p_(e, "agg"), "is_some"),
                                    _typed_of(e, e.fld(p_(e, "agg"), "value")),
                                    e.cat(_ir_of(e, p_(e, "ty")), e.s(" undef")),
                                ),
                                e.s(", "),
                                _typed_of(e, p_(e, "val")),
                                e.s(", "),
                                to_str(e, p_(e, "idx")),
                            ),
                        ),
                        e.p(
                            "extv",
                            _render_arm(
                                e,
                                e.s("  "),
                                p_(e, "res"),
                                e.s(" = extractvalue "),
                                _typed_of(e, p_(e, "agg")),
                                e.s(", "),
                                to_str(e, p_(e, "idx")),
                            ),
                        ),
                        e.p(
                            "call",
                            e.seq(
                                e.let("parts", e.list_new(str_(e))),
                                e.foreach(p_(e, "args"), "ax", push(e, e.v("parts"), _typed_of(e, e.v("ax")))),
                                push(
                                    e,
                                    e.v("out"),
                                    e.cat(
                                        e.s("  "),
                                        e.if_else(
                                            e.fld(p_(e, "res"), "is_some"),
                                            e.cat(e.fld(p_(e, "res"), "value"), e.s(" = ")),
                                            e.dstr(""),
                                        ),
                                        e.s("call "),
                                        e.call_m(outer(e), "callsig", _lv_ty(e, p_(e, "fn"))),
                                        e.s(" "),
                                        _lv_ref(e, p_(e, "fn")),
                                        e.s("("),
                                        e.join(e.v("parts"), ", "),
                                        e.s(")"),
                                        _dbg(e),
                                    ),
                                ),
                                e.mb.set(e.fld(e.v("st"), "open"), num(e, 1)),
                            ),
                        ),
                        e.p(
                            "ret",
                            _render_terminator(
                                e,
                                e.s("  ret "),
                                e.if_else(
                                    e.fld(p_(e, "val"), "is_some"),
                                    _typed_of(e, e.fld(p_(e, "val"), "value")),
                                    e.dstr("void"),
                                ),
                            ),
                        ),
                        e.p(
                            "trap",
                            e.seq(
                                push(e, e.v("out"), e.cat(e.s("  call void @llvm.trap()"), _dbg(e))),
                                _render_terminator(e, e.s("  unreachable")),
                            ),
                        ),
                    ),
                ),
            ),
            _flush_pend(e),
            e.if_only(
                e.eq(e.fld(e.v("st"), "open"), num(e, 1)),
                e.mb.panic(e.s("llvm: function body does not end in a terminator")),
            ),
            e.ret(e.v("out")),
        ),
    )
    _lmod_render(e, x)
    _lmod_dbg(e, x)
    x.append(_lmod_meta_method(e))
    target_mb.module_defs_methods(e, x, "lmod", "ldef")
    # A zeroed global defined on first use (dependencies ask for it from every use site).
    method(
        e,
        x,
        "lmod",
        "alloc_once",
        e.rec(e.p("id", target_mb.unique_t(e)), e.p("name", str_(e)), e.p("ty", ty(e))),
        str_(e),
        target_mb.def_once(
            e,
            outer(e),
            a(e, "id"),
            e.call_m(
                outer(e),
                "add_global",
                e.rec(
                    e.p("konst", e.b(False)),
                    e.p("name", a(e, "name")),
                    e.p("ty", a(e, "ty")),
                    e.p("init", e.s("zeroinitializer")),
                ),
            ),
        ),
    )
    # A constant global defined on first use (dependencies ask for it from every use site).
    method(
        e,
        x,
        "lmod",
        "const_once",
        e.rec(e.p("id", target_mb.unique_t(e)), e.p("name", str_(e)), e.p("ty", ty(e)), e.p("init", str_(e))),
        str_(e),
        target_mb.def_once(
            e,
            outer(e),
            a(e, "id"),
            e.call_m(
                outer(e),
                "add_global",
                e.rec(
                    e.p("konst", e.b(True)),
                    e.p("name", a(e, "name")),
                    e.p("ty", a(e, "ty")),
                    e.p("init", a(e, "init")),
                ),
            ),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "add_global",
        e.rec(e.p("konst", bool_t(e)), e.p("name", str_(e)), e.p("ty", ty(e)), e.p("init", str_(e))),
        str_(e),
        e.seq(
            e.let("gname", e.cat(e.s("@"), e.call_m(outer(e), "mint", a(e, "name")))),
            e.let("g", mk(e, "lglobal", e.p("name", e.v("gname")), e.p("ty", a(e, "ty")), e.p("init", a(e, "init")))),
            e.if_only(a(e, "konst"), push(e, in_(e, "constants"), e.v("g"))),
            e.if_only(e.not_(a(e, "konst")), push(e, in_(e, "globals"), e.v("g"))),
            e.ret(e.v("gname")),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "add_cstr",
        str_(e),
        str_(e),
        e.seq(
            e.let("bytes", e.call(e.mb.eval_str_utf8(), e.v("arg"))),
            e.let("parts", e.list_new(str_(e))),
            e.foreach(
                e.v("bytes"),
                "b",
                push(
                    e,
                    e.v("parts"),
                    e.cat(e.s("i8 "), to_str(e, e.mb.operator_and(e.mb.as_(e.v("b"), e.mb.types_int()), num(e, 255)))),
                ),
            ),
            push(e, e.v("parts"), e.s("i8 0")),
            e.let("gname", e.cat(e.s("@str"), to_str(e, e.call_m(outer(e), "fresh_n", e.tup())))),
            push(
                e,
                in_(e, "constants"),
                mk(
                    e,
                    "lglobal",
                    e.p("name", e.v("gname")),
                    e.p(
                        "ty",
                        mk(
                            e,
                            "lt_arr",
                            e.p("elem", _int_ty(e, "u8")),
                            e.p("count", e.mb.operator_add(e.fld(e.v("bytes"), "len"), num(e, 1))),
                        ),
                    ),
                    e.p("init", e.cat(e.s("["), e.join(e.v("parts"), ", "), e.s("]"))),
                ),
            ),
            e.ret(e.v("gname")),
        ),
    )
    method(
        e,
        x,
        "lmod",
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
            # A public function keeps its name, the symbol other objects link against; any other function's name
            # is a hint, minted into a module-unique symbol.
            e.let("fname", e.if_else(a(e, "public"), a(e, "name"), e.call_m(outer(e), "mint", a(e, "name")))),
            e.let("loc", e.call(e.eval_builtin("expr_loc"), a(e, "body"))),
            e.let("ptypes", acc(e, in_(e, "xx", "value"), a(e, "ty"), "lfn", "params")),
            e.let("fret", acc(e, in_(e, "xx", "value"), a(e, "ty"), "lfn", "ret")),
            count_let(e, "sstart"),
            count_loop(e, "sstart", in_(e, "slots")),
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
            e.foreach(
                e.v("ptypes"),
                "pty",
                e.seq(
                    e.let("an", e.cat(e.s("%a"), to_str(e, e.fld(e.v("pi"), "i")))),
                    push(e, e.v("sig"), e.cat(_ir_of(e, e.v("pty")), e.s(" "), e.v("an"))),
                    e.let("s", e.call_m(outer(e), "slot", e.v("pty"))),
                    push(e, e.v("out"), _store_inst(e, e.v("loc"), _lval_new(e, e.v("pty"), e.v("an")), e.v("s"))),
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
                                        e.p("slot", mk(e, "lparam", e.p("ty", e.v("pty")), e.p("ptr", e.v("s")))),
                                    ),
                                ),
                                "parameter binding",
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("pi"), "i")),
                ),
            ),
            e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
            e.let("sc", e.call(e.eval_builtin("scope"), e.rec(e.p("vx", e.v("vx")), e.p("entries", e.v("entries"))))),
            e.let("tgt", mk(e, "ltarget", e.p("mod", outer(e)))),
            e.let(
                "ctx",
                e.call(
                    e.eval_builtin("expr_context"),
                    e.rec(
                        e.p("scope", e.v("sc")),
                        e.p("target", e.mb.as_(e.v("tgt"), e.mb.eval_target())),
                        e.p("vx", e.v("vx")),
                        e.p("exception_type", e.mb.opt_none_type()),
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
            target_mb.loan_return_check(e, e.v("ctx"), e.v("loc"), e.v("r"), "llvm"),
            e.let("is_void", has(e, e.v("ctx"), e.v("fret"), "lvoid")),
            # The body's result (its last value, or what its returns yielded) is cast to the declared result type.
            e.if_only(
                and_b(e, e.v("is_void"), _is_llvm(e, e.v("ctx"), e.v("r"))),
                e.match_of(
                    e.eresult_err(e.mb.eval_value(), e.v("loc"), e.s("void function body yields a value")),
                    "__x",
                    None,
                    e.p("ok", e.mb.panic(e.s("unreachable"))),
                    e.p("errs", target_mb.panic_errs(e, "llvm", "compile failed", e.v("__x"))),
                ),
            ),
            e.let("need_cast", e.not_(e.v("is_void"))),
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
                and_b(e, e.not_(e.v("ended")), e.v("is_void")),
                push(e, e.v("out"), _inst(e, e.v("loc"), "ret", e.p("val", e.opt_none(lt(e, "lval"))))),
            ),
            e.if_only(
                e.v("need_cast"),
                push(
                    e,
                    e.v("out"),
                    _inst(e, e.v("loc"), "ret", e.p("val", e.opt_some(lt(e, "lval"), _lval_of(e, e.v("v"))))),
                ),
            ),
            e.foreach(
                e.v("out"),
                "d0",
                e.match_of(
                    e.call_m(e.v("d0"), "k", e.tup()),
                    "p",
                    e.seq(),
                    e.p("meta", e.call_m(outer(e), "meta", p_(e, "meta"))),
                ),
            ),
            e.let("lines", e.list_new(str_(e))),
            e.let("si", e.rec(e.p("i", e.int_of(0)))),
            e.foreach(
                in_(e, "slots"),
                "s0",
                e.seq(
                    e.if_only(
                        e.mb.operator_ge(e.fld(e.v("si"), "i"), e.fld(e.v("sstart"), "v")),
                        push(
                            e,
                            e.v("lines"),
                            e.cat(
                                e.s("  "),
                                e.call_m(e.v("s0"), "name", e.tup()),
                                e.s(" = alloca "),
                                _ir_of(e, e.call_m(e.v("s0"), "ty", e.tup())),
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("si"), "i")),
                ),
            ),
            e.let("fsp", e.call_m(outer(e), "dbg_sub", e.rec(e.p("name", e.v("fname")), e.p("loc", e.v("loc"))))),
            e.mb.set(in_(e, "sp"), e.v("fsp")),
            e.foreach(e.call_m(outer(e), "render_insts", e.v("out")), "l0", push(e, e.v("lines"), e.v("l0"))),
            push(
                e,
                in_(e, "funcs"),
                e.cat(
                    # Only public functions are linkable symbols; nothing here unwinds.
                    e.if_else(a(e, "public"), e.dstr("define "), e.dstr("define internal ")),
                    _ir_of(e, e.v("fret")),
                    e.s(" @"),
                    e.v("fname"),
                    e.s("("),
                    e.join(e.v("sig"), ", "),
                    e.s(") nounwind !dbg !"),
                    to_str(e, e.v("fsp")),
                    e.s(" {\n"),
                    e.join(e.v("lines"), "\n"),
                    e.s("\n}"),
                ),
            ),
            e.ret(e.cat(e.s("@"), e.v("fname"))),
        ),
    )
    _value_aspects(e, x, "lt_int", e.mb.operator_div(in_(e, "bits"), num(e, 8)), _int_hash_body(e), "0")
    _value_aspects(e, x, "lt_float", e.mb.operator_div(in_(e, "bits"), num(e, 8)), None, "0.0")
    _value_aspects(e, x, "lt_ptr", num(e, 8), _ptr_hash_body(e), "null")
    self_type(
        e,
        x,
        "lt_int",
        e.cat(e.if_else(in_(e, "signed"), e.dstr("i"), e.dstr("u")), to_str(e, in_(e, "bits"))),
        e.aspect_dispatch(
            lv(e, "ltype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "lint_id"),
            lv(e, "size_id"),
            lv(e, "align_id"),
            lv(e, "zero_id"),
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
                            has(e, xx(e), src_type(e), "lint"),
                            and_b(
                                e,
                                e.mb.operator_ge(acc(e, xx(e), src_type(e), "lint", "min"), in_(e, "min")),
                                e.mb.operator_le(acc(e, xx(e), src_type(e), "lint", "max"), in_(e, "max")),
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
                    ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _lval_new(e, outer(e), to_str(e, e.v("l")))))),
                ),
            ),
            e.let("sb", cv_bits(e, e.v("st"), "lint")),
            # A source of this width (a type reading as this integer) is the same representation: retagged.
            e.if_only(e.eq(e.v("sb"), in_(e, "bits")), ret_m(e, _retag(e, a(e, "cv"), outer(e)))),
            e.let(
                "op",
                e.if_else(
                    e.eq(e.v("sb"), num(e, 1)),
                    e.dstr("zext"),
                    e.if_else(acc(e, xx(e), e.v("st"), "lint", "signed"), e.dstr("sext"), e.dstr("zext")),
                ),
            ),
            e.ret(_conv(e, e.v("op"), a(e, "cv"), outer(e))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lint"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "lint", "bits"), in_(e, "bits")),
                        e.eq(acc(e, xx(e), a(e, "other"), "lint", "signed"), in_(e, "signed")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lt_int"), t(e, "ltype"), e.p("ir", e.cat(e.s("i"), to_str(e, in_(e, "bits")))), e.p("ssa", outer(e))
        )
    )
    x.append(
        e.impl_interface(
            e.v("lt_int"),
            t(e, "lint"),
            e.p("bits", in_(e, "bits")),
            e.p("signed", in_(e, "signed")),
            e.p("min", in_(e, "min")),
            e.p("max", in_(e, "max")),
        )
    )
    op(e, x, "lt_int", "add", try_er(e, _binop_body(e, e.s("add")), cve_t(e)))
    op(e, x, "lt_int", "sub", try_er(e, _binop_body(e, e.s("sub")), cve_t(e)))
    op(e, x, "lt_int", "mul", try_er(e, _binop_body(e, e.s("mul")), cve_t(e)))
    op(e, x, "lt_int", "div", try_er(e, _binop_body(e, _signed_op(e, "sdiv", "udiv")), cve_t(e)))
    op(e, x, "lt_int", "mod", try_er(e, _binop_body(e, _signed_op(e, "srem", "urem")), cve_t(e)))
    op(e, x, "lt_int", "and", short_circuit_body(e, "and", try_er(e, _binop_body(e, e.s("and")), cve_t(e))))
    op(e, x, "lt_int", "or", short_circuit_body(e, "or", try_er(e, _binop_body(e, e.s("or")), cve_t(e))))
    op(e, x, "lt_int", "xor", try_er(e, _binop_body(e, e.s("xor")), cve_t(e)))
    op(e, x, "lt_int", "shl", try_er(e, _binop_body(e, e.s("shl")), cve_t(e)))
    op(e, x, "lt_int", "shr", try_er(e, _binop_body(e, _signed_op(e, "ashr", "lshr")), cve_t(e)))
    op(e, x, "lt_int", "ushr", try_er(e, _binop_body(e, e.s("lshr")), cve_t(e)))
    op(e, x, "lt_int", "eq", try_er(e, _cmp_body(e, e.s("icmp eq")), cve_t(e)))
    op(e, x, "lt_int", "ne", try_er(e, _cmp_body(e, e.s("icmp ne")), cve_t(e)))
    op(e, x, "lt_int", "lt", try_er(e, _cmp_body(e, _signed_op(e, "icmp slt", "icmp ult")), cve_t(e)))
    op(e, x, "lt_int", "le", try_er(e, _cmp_body(e, _signed_op(e, "icmp sle", "icmp ule")), cve_t(e)))
    op(e, x, "lt_int", "gt", try_er(e, _cmp_body(e, _signed_op(e, "icmp sgt", "icmp ugt")), cve_t(e)))
    op(e, x, "lt_int", "ge", try_er(e, _cmp_body(e, _signed_op(e, "icmp sge", "icmp uge")), cve_t(e)))
    x.append(
        e.impl_interface(
            e.v("lt_int"),
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
            e.v("lt_int"),
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
                                        e.if_else(e.eq(in_(e, "bits"), num(e, 1)), e.dstr("true"), e.dstr("-1")),
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
    _bind_impl(e, x, "lt_int")
    _set_impl(e, x, "lt_int")
    self_type(
        e,
        x,
        "lt_float",
        e.cat(e.s("f"), to_str(e, in_(e, "bits"))),
        e.aspect_dispatch(
            lv(e, "ltype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "lfloat_id"),
            lv(e, "size_id"),
            lv(e, "align_id"),
            lv(e, "zero_id"),
            lv(e, "eq_id"),
            op_id(e, "add"),
            op_id(e, "sub"),
            op_id(e, "mul"),
            op_id(e, "div"),
            op_id(e, "mod"),
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
                                has(e, xx(e), src_type(e), "lfloat"),
                                e.mb.operator_lt(src_bits(e, "lfloat"), in_(e, "bits")),
                            ),
                            and_b(
                                e,
                                has(e, xx(e), src_type(e), "lint"),
                                and_b(
                                    e,
                                    e.mb.operator_ge(
                                        acc(e, xx(e), src_type(e), "lint", "min"),
                                        e.if_else(
                                            e.eq(in_(e, "bits"), num(e, 64)),
                                            e.mb.as_(num(e, -9007199254740992.0), e.types_double()),
                                            e.mb.as_(num(e, -16777216.0), e.types_double()),
                                        ),
                                    ),
                                    e.mb.operator_le(
                                        acc(e, xx(e), src_type(e), "lint", "max"),
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
                    ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "cv")), _lval_new(e, outer(e), e.v("s"))))),
                ),
            ),
            e.if_only(
                has(e, xx(e), e.v("st"), "lint"),
                ret_m(
                    e,
                    _conv(
                        e,
                        e.if_else(acc(e, xx(e), e.v("st"), "lint", "signed"), e.dstr("sitofp"), e.dstr("uitofp")),
                        a(e, "cv"),
                        outer(e),
                    ),
                ),
            ),
            e.ret(_conv(e, e.s("fpext"), a(e, "cv"), outer(e))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lfloat"),
                    e.eq(acc(e, xx(e), a(e, "other"), "lfloat", "bits"), in_(e, "bits")),
                )
            ),
        ),
    )
    _conv_methods(e, x)
    x.append(
        e.impl_interface(
            e.v("lt_float"),
            t(e, "ltype"),
            e.p("ir", e.if_else(e.eq(in_(e, "bits"), num(e, 32)), e.dstr("float"), e.dstr("double"))),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("lt_float"), t(e, "lfloat"), e.p("bits", in_(e, "bits"))))
    op(e, x, "lt_float", "add", try_er(e, _binop_body(e, e.s("fadd")), cve_t(e)))
    op(e, x, "lt_float", "sub", try_er(e, _binop_body(e, e.s("fsub")), cve_t(e)))
    op(e, x, "lt_float", "mul", try_er(e, _binop_body(e, e.s("fmul")), cve_t(e)))
    op(e, x, "lt_float", "div", try_er(e, _binop_body(e, e.s("fdiv")), cve_t(e)))
    op(e, x, "lt_float", "mod", try_er(e, _binop_body(e, e.s("frem")), cve_t(e)))
    op(e, x, "lt_float", "eq", try_er(e, _cmp_body(e, e.s("fcmp oeq")), cve_t(e)))
    op(e, x, "lt_float", "ne", try_er(e, _cmp_body(e, e.s("fcmp une")), cve_t(e)))
    op(e, x, "lt_float", "lt", try_er(e, _cmp_body(e, e.s("fcmp olt")), cve_t(e)))
    op(e, x, "lt_float", "le", try_er(e, _cmp_body(e, e.s("fcmp ole")), cve_t(e)))
    op(e, x, "lt_float", "gt", try_er(e, _cmp_body(e, e.s("fcmp ogt")), cve_t(e)))
    op(e, x, "lt_float", "ge", try_er(e, _cmp_body(e, e.s("fcmp oge")), cve_t(e)))
    x.append(
        e.impl_interface(
            e.v("lt_float"),
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
                                e.p("op", e.s("fneg")),
                                e.p("a", a(e, "base")),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )
    _bind_impl(e, x, "lt_float")
    _set_impl(e, x, "lt_float")
    self_type(
        e,
        x,
        "lt_ptr",
        e.cat(e.s("ptr("), bim0(e, ty(e), "desc", in_(e, "pointee")), e.s(")")),
        e.aspect_dispatch(
            lv(e, "ltype_id"),
            asp_id(e, "initial_bind"),
            lv(e, "lptr_id"),
            lv(e, "size_id"),
            lv(e, "align_id"),
            lv(e, "zero_id"),
            lv(e, "hash_id"),
            lv(e, "eq_id"),
            op_id(e, "eq"),
            op_id(e, "ne"),
            op_id(e, "lt"),
            op_id(e, "le"),
            op_id(e, "gt"),
            op_id(e, "ge"),
            op_id(e, "add"),
            asp_id(e, "bind"),
            asp_id(e, "set"),
            asp_id(e, "field"),
        ),
        body(
            e,
            e.ret(
                # Only itself: any other pointer, a function or an integer becomes this pointer type only through
                # the named conversions `ptr_cast`, `fn_to_ptr`, `ptr_to_int` and `int_to_ptr`.
                is_equal(e, xx(e), outer(e), src_type(e))
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(err_cve(e, loc(e), e.cat(e.s("llvm: no cast to a pointer from "), ty_desc(e, e.v("st"))))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lptr"),
                    is_equal(e, xx(e), in_(e, "pointee"), acc(e, xx(e), a(e, "other"), "lptr", "pointee")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("lt_ptr"), t(e, "ltype"), e.p("ir", e.s("ptr")), e.p("ssa", outer(e))))
    x.append(e.impl_interface(e.v("lt_ptr"), t(e, "lptr"), e.p("pointee", in_(e, "pointee"))))
    op(e, x, "lt_ptr", "eq", try_er(e, _cmp_body(e, e.s("icmp eq")), cve_t(e)))
    op(e, x, "lt_ptr", "ne", try_er(e, _cmp_body(e, e.s("icmp ne")), cve_t(e)))
    op(e, x, "lt_ptr", "lt", try_er(e, _cmp_body(e, e.s("icmp ult")), cve_t(e)))
    op(e, x, "lt_ptr", "le", try_er(e, _cmp_body(e, e.s("icmp ule")), cve_t(e)))
    op(e, x, "lt_ptr", "gt", try_er(e, _cmp_body(e, e.s("icmp ugt")), cve_t(e)))
    op(e, x, "lt_ptr", "ge", try_er(e, _cmp_body(e, e.s("icmp uge")), cve_t(e)))
    x.append(
        e.impl_interface(
            e.v("lt_ptr"),
            op_iface(e, "add"),
            e.p(
                "add",
                body(
                    e,
                    e.let("p", unwrap_cve_m(e, try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), a(e, "base")), cve_t(e)))),
                    e.let(
                        "i",
                        unwrap_cve_m(
                            e,
                            e.if_else(
                                _is_llvm(e, xx(e), a(e, "reference")),
                                try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), a(e, "reference")), cve_t(e)),
                                cast_value(e, xx(e), loc(e), _int_ty(e, "i64"), a(e, "reference")),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(has(e, xx(e), cve_type(e, e.v("i")), "lint")),
                        ret_m(e, err_cve(e, loc(e), "pointer offset must be an integer")),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("p"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("i"))),
                    e.let(
                        "g",
                        hf_rec(
                            e,
                            "h_gep",
                            e.p("loc", loc(e)),
                            e.p("mod", _xmod(e)),
                            e.p("base", in_(e, "pointee")),
                            e.p("ptr", _lv_ref(e, _lval_of(e, e.v("p")))),
                            e.p("idx", e.list_new(lt(e, "lval"), _lval_of(e, e.v("i")))),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e, _code_of(e, e.v("out")), _lval_new(e, outer(e), _lv_ref(e, _lval_of(e, e.v("g"))))
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    _bind_impl(e, x, "lt_ptr")
    _set_impl(e, x, "lt_ptr")
    x.append(
        e.impl_interface(
            e.v("lt_ptr"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.if_only(
                        has(e, xx(e), in_(e, "pointee"), "lvoid"),
                        ret_m(e, err_cve(e, loc(e), "cannot index a void pointer")),
                    ),
                    e.let("s", unwrap_cve_m(e, try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), a(e, "value")), cve_t(e)))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("s"))),
                    e.let("p", _lv_ref(e, _lval_of(e, e.v("s")))),
                    e.let(
                        "g",
                        unwrap_cve_m(
                            e,
                            e.if_else(
                                has(e, xx(e), in_(e, "pointee"), "lstruct"),
                                try_er(
                                    e,
                                    hf_rec(
                                        e,
                                        "h_gep_field",
                                        e.p("xx", xx(e)),
                                        e.p("loc", loc(e)),
                                        e.p("mod", _xmod(e)),
                                        e.p("st", in_(e, "pointee")),
                                        e.p("ptr", e.v("p")),
                                        e.p("name", hf_rec(e, "h_key_str", e.p("xx", xx(e)), e.p("cv", a(e, "key")))),
                                    ),
                                    cve_t(e),
                                ),
                                try_er(
                                    e,
                                    hf_rec(
                                        e,
                                        "h_gep_index",
                                        e.p("xx", xx(e)),
                                        e.p("loc", loc(e)),
                                        e.p("mod", _xmod(e)),
                                        e.p("base", in_(e, "pointee")),
                                        e.p("ptr", e.v("p")),
                                        e.p("key", a(e, "key")),
                                    ),
                                    cve_t(e),
                                ),
                            ),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_of(e, e.v("g"))))),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    self_type(
        e,
        x,
        "lt_arr",
        e.cat(e.s("array("), bim0(e, ty(e), "desc", in_(e, "elem")), e.s(", "), to_str(e, in_(e, "count")), e.s(")")),
        e.aspect_dispatch(lv(e, "ltype_id"), lv(e, "larr_id"), asp_id(e, "field"), asp_id(e, "bind"), asp_id(e, "set")),
        body(
            e,
            e.ret(
                or_b(e, is_equal(e, xx(e), outer(e), src_type(e)), has_b(e, xx(e), src_type(e), asp_iface(e, "tuple")))
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("tk", lookup(e, xx(e), e.v("st"), asp_iface(e, "tuple"))),
            e.if_only(
                e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, err_cve(e, loc(e), "array initializer must be a tuple"))
            ),
            e.let(
                "elems",
                bim(
                    e,
                    asp_iface(e, "tuple"),
                    "take_elements",
                    e.fld(e.v("tk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("parts", e.list_new(str_(e))),
            e.let("st2", e.rec(e.p("n", e.int_of(0)), e.p("bad", e.int_of(0)))),
            e.foreach(
                e.v("elems"),
                "er",
                e.seq(
                    e.let("ec", unwrap_cve_m(e, e.v("er"))),
                    e.let(
                        "v",
                        unwrap_cve_m(
                            e, try_er(e, _operand(e, xx(e), loc(e), _xmod(e), in_(e, "elem"), e.v("ec")), cve_t(e))
                        ),
                    ),
                    e.if_only(is_target_code(e, cve_code(e, e.v("v"))), e.mb.set(e.fld(e.v("st2"), "bad"), num(e, 1))),
                    push(e, e.v("parts"), e.call_m(_xmod(e), "typed", _lval_of(e, e.v("v")))),
                    e.incr(e.fld(e.v("st2"), "n")),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st2"), "bad"), num(e, 1)),
                ret_m(e, err_cve(e, loc(e), "array initializer element is not a constant")),
            ),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("st2"), "n"), in_(e, "count"))),
                ret_m(e, err_cve(e, loc(e), "array initializer has the wrong element count")),
            ),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        _lval_new(e, outer(e), e.cat(e.s("["), e.join(e.v("parts"), ", "), e.s("]"))),
                    ),
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
                    has(e, xx(e), a(e, "other"), "larr"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "larr", "count"), in_(e, "count")),
                        is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "larr", "elem")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lt_arr"),
            t(e, "ltype"),
            e.p(
                "ir",
                e.cat(
                    e.s("["),
                    to_str(e, in_(e, "count")),
                    e.s(" x "),
                    _ir_fn(e, _ir_arg_xx(e), _ir_arg_mod(e), in_(e, "elem")),
                    e.s("]"),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(e.impl_interface(e.v("lt_arr"), t(e, "larr"), e.p("elem", in_(e, "elem")), e.p("count", in_(e, "count"))))
    _bind_impl(e, x, "lt_arr")
    _set_impl(e, x, "lt_arr")
    x.append(
        e.impl_interface(
            e.v("lt_arr"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let("sl", _lval_of(e, a(e, "value"))),
                    e.if_only(
                        e.not_(_lv_is_mem(e, e.v("sl"))), ret_m(e, err_cve(e, loc(e), "array value is not addressable"))
                    ),
                    e.let("p", _lv_mem(e, e.v("sl"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "value"))),
                    e.let("i32", _int_ty(e, "i32")),
                    e.let(
                        "k",
                        unwrap_cve_m(
                            e,
                            e.if_else(
                                _is_llvm(e, xx(e), a(e, "key")),
                                try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), a(e, "key")), cve_t(e)),
                                cast_value(e, xx(e), loc(e), e.v("i32"), a(e, "key")),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(has(e, xx(e), cve_type(e, e.v("k")), "lint")),
                        ret_m(e, err_cve(e, loc(e), "index must be an integer")),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("k"))),
                    e.let(
                        "g",
                        hf_rec(
                            e,
                            "h_gep",
                            e.p("loc", loc(e)),
                            e.p("mod", _xmod(e)),
                            e.p("base", outer(e)),
                            e.p("ptr", e.v("p")),
                            e.p(
                                "idx",
                                e.list_new(lt(e, "lval"), _lval_new(e, e.v("i32"), e.s("0")), _lval_of(e, e.v("k"))),
                            ),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
                    e.let("r", _lv_ref(e, _lval_of(e, e.v("g")))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_mem(e, in_(e, "elem"), e.v("r"))))),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    self_type(
        e,
        x,
        "lt_struct",
        e.cat(e.s("struct "), in_(e, "name")),
        e.aspect_dispatch(
            lv(e, "ltype_id"), lv(e, "lstruct_id"), asp_id(e, "field"), asp_id(e, "bind"), asp_id(e, "set")
        ),
        body(
            e,
            e.ret(
                or_b(e, is_equal(e, xx(e), outer(e), src_type(e)), has_b(e, xx(e), src_type(e), asp_iface(e, "record")))
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("rk", lookup(e, xx(e), e.v("st"), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")), ret_m(e, err_cve(e, loc(e), "struct initializer must be a record"))
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("parts", e.list_new(str_(e))),
            e.let("bad", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                in_(e, "fields"),
                "f0",
                e.seq(
                    e.let("f", e.v("f0")),
                    e.let("ec", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.call_m(e.v("f"), "name", e.tup())))),
                    e.let(
                        "v",
                        unwrap_cve_m(
                            e,
                            try_er(
                                e,
                                _operand(e, xx(e), loc(e), _xmod(e), e.call_m(e.v("f"), "ty", e.tup()), e.v("ec")),
                                cve_t(e),
                            ),
                        ),
                    ),
                    e.if_only(is_target_code(e, cve_code(e, e.v("v"))), e.mb.set(e.fld(e.v("bad"), "v"), num(e, 1))),
                    push(e, e.v("parts"), e.call_m(_xmod(e), "typed", _lval_of(e, e.v("v")))),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("bad"), "v"), num(e, 1)),
                ret_m(e, err_cve(e, loc(e), "struct initializer field is not a constant")),
            ),
            e.ret(
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        _lval_new(e, outer(e), e.cat(e.s("{ "), e.join(e.v("parts"), ", "), e.s(" }"))),
                    ),
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
                    has(e, xx(e), a(e, "other"), "lstruct"),
                    e.eq(acc(e, xx(e), a(e, "other"), "lstruct", "name"), in_(e, "name")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lt_struct"),
            t(e, "ltype"),
            e.p(
                "ir",
                e.if_else(
                    e.fld(_ir_arg_mod(e), "is_some"),
                    e.call_m(e.fld(_ir_arg_mod(e), "value"), "use_struct", outer(e)),
                    e.cat(e.s("%"), in_(e, "name")),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lt_struct"),
            t(e, "lstruct"),
            e.p("name", in_(e, "name")),
            e.p("fields", in_(e, "fields")),
            e.p("tail", in_(e, "tail")),
        )
    )
    _bind_impl(e, x, "lt_struct")
    _set_impl(e, x, "lt_struct")
    x.append(
        e.impl_interface(
            e.v("lt_struct"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let("sl", _lval_of(e, a(e, "value"))),
                    e.if_only(
                        e.not_(_lv_is_mem(e, e.v("sl"))),
                        ret_m(e, err_cve(e, loc(e), "struct value is not addressable")),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "value"))),
                    e.let(
                        "g",
                        unwrap_cve_m(
                            e,
                            try_er(
                                e,
                                hf_rec(
                                    e,
                                    "h_gep_field",
                                    e.p("xx", xx(e)),
                                    e.p("loc", loc(e)),
                                    e.p("mod", _xmod(e)),
                                    e.p("st", outer(e)),
                                    e.p("ptr", _lv_mem(e, e.v("sl"))),
                                    e.p("name", hf_rec(e, "h_key_str", e.p("xx", xx(e)), e.p("cv", a(e, "key")))),
                                ),
                                cve_t(e),
                            ),
                        ),
                    ),
                    _append_code(e, e.v("out"), cve_code(e, e.v("g"))),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_of(e, e.v("g"))))),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    _tuple_type(e, x)
    self_type(
        e,
        x,
        "lt_fn",
        e.s("fn"),
        e.aspect_dispatch(lv(e, "ltype_id"), lv(e, "lfn_id"), asp_id(e, "function")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "lfn")), ret_m(e, dfalse(e))),
            e.if_only(
                e.not_(e.eq(im0(e, "lfn", "varargs", asp(e, xx(e), a(e, "other"), "lfn")), in_(e, "varargs"))),
                ret_m(e, dfalse(e)),
            ),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "ret"), im0(e, "lfn", "ret", asp(e, xx(e), a(e, "other"), "lfn")))),
                ret_m(e, dfalse(e)),
            ),
            e.let("om", e.map_new(str_(e), ty(e))),
            e.let("on", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                im0(e, "lfn", "params", asp(e, xx(e), a(e, "other"), "lfn")),
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
                and_b(e, e.eq(e.fld(e.v("st"), "i"), e.fld(e.v("on"), "v")), e.eq(e.fld(e.v("st"), "same"), num(e, 1)))
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lt_fn"),
            t(e, "ltype"),
            e.p(
                "ir",
                e.cat(
                    _ir_fn(e, _ir_arg_xx(e), _ir_arg_mod(e), in_(e, "ret")),
                    e.s(" ("),
                    hf_rec(e, "h_params_ir", e.p("xx", _ir_arg_xx(e)), e.p("mod", _ir_arg_mod(e)), e.p("ty", outer(e))),
                    e.s(")"),
                ),
            ),
            e.p("ssa", outer(e)),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lt_fn"),
            t(e, "lfn"),
            e.p("params", in_(e, "params")),
            e.p("ret", in_(e, "ret")),
            e.p("varargs", in_(e, "varargs")),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lt_fn"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "function"))),
                    e.let("fnv", _lval_of(e, a(e, "function"))),
                    e.let("args", e.list_new(lt(e, "lval"))),
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
                    e.let("single", and_b(e, e.eq(e.fld(e.v("pn"), "v"), num(e, 1)), e.not_(in_(e, "varargs")))),
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
                                e.mb.operator_lt(e.fld(e.v("st"), "i"), e.fld(e.v("pn"), "v")),
                                e.seq(
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
                                    push(e, e.v("args"), _lval_of(e, e.v("v"))),
                                ),
                            ),
                            e.if_only(
                                e.mb.operator_ge(e.fld(e.v("st"), "i"), e.fld(e.v("pn"), "v")),
                                e.seq(
                                    e.if_only(
                                        e.not_(in_(e, "varargs")),
                                        ret_m(e, err_cve(e, loc(e), "too many call arguments")),
                                    ),
                                    e.let(
                                        "v",
                                        unwrap_cve_m(
                                            e, try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), e.v("ec")), cve_t(e))
                                        ),
                                    ),
                                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                                    push(e, e.v("args"), _lval_of(e, e.v("v"))),
                                ),
                            ),
                            e.incr(e.fld(e.v("st"), "i")),
                        ),
                    ),
                    e.if_only(
                        e.mb.operator_lt(e.fld(e.v("st"), "i"), e.fld(e.v("pn"), "v")),
                        ret_m(e, err_cve(e, loc(e), "too few call arguments")),
                    ),
                    e.if_only(
                        has(e, xx(e), in_(e, "ret"), "lvoid"),
                        e.seq(
                            push(
                                e,
                                e.v("out"),
                                _inst(
                                    e,
                                    loc(e),
                                    "call",
                                    e.p("res", e.opt_none(str_(e))),
                                    e.p("fn", e.v("fnv")),
                                    e.p("args", e.v("args")),
                                ),
                            ),
                            ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                        ),
                    ),
                    e.let("r", _fresh(e, _xmod(e))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "call",
                            e.p("res", e.opt_some(str_(e), e.v("r"))),
                            e.p("fn", e.v("fnv")),
                            e.p("args", e.v("args")),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_new(e, in_(e, "ret"), e.v("r"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    self_type(
        e,
        x,
        "lt_void",
        e.s("void"),
        e.aspect_dispatch(lv(e, "ltype_id"), lv(e, "lvoid_id")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "lvoid"))),
    )
    x.append(e.impl_interface(e.v("lt_void"), t(e, "ltype"), e.p("ir", e.s("void")), e.p("ssa", outer(e))))
    x.append(e.impl_interface(e.v("lt_void"), t(e, "lvoid")))
    self_type(
        e,
        x,
        "lt_slot",
        e.cat(bim0(e, ty(e), "desc", in_(e, "base")), e.s("@"), in_(e, "ptr")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), lv(e, "lslot_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "ltype_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
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
            push(e, e.v("out"), _store_inst(e, loc(e), _lval_of(e, e.v("v")), in_(e, "ptr"))),
            e.ret(ok_cve(e, cv_of(e, _code_of(e, e.v("out")), _lval_mem(e, outer(e), in_(e, "ptr"))))),
        ),
        body(e, e.ret(type_can_convert(e, xx(e), loc(e), in_(e, "base"), a(e, "dest_type")))),
        body(
            e,
            e.let("r", _fresh(e, _xmod(e))),
            e.let("out", _insts_new(e)),
            _append_code(e, e.v("out"), cve_code(e, a(e, "cv"))),
            push(e, e.v("out"), _load_inst(e, loc(e), e.v("r"), in_(e, "base"), in_(e, "ptr"))),
            e.let("loaded", cv_of(e, _code_of(e, e.v("out")), _lval_new(e, in_(e, "base"), e.v("r")))),
            e.ret(cast_value(e, xx(e), loc(e), a(e, "dest_type"), e.v("loaded"))),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lslot"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "lslot", "ptr"), in_(e, "ptr")),
                        is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "lslot", "base")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("lt_slot"),
            t(e, "ltype"),
            e.p("ir", _ir_fn(e, _ir_arg_xx(e), _ir_arg_mod(e), in_(e, "base"))),
            e.p("ssa", in_(e, "base")),
        )
    )
    x.append(e.impl_interface(e.v("lt_slot"), t(e, "lslot"), e.p("base", in_(e, "base")), e.p("ptr", in_(e, "ptr"))))
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
    ids.append(lv(e, "lgtype_m_id"))
    ids.append(asp_id(e, "set"))
    ids.append(asp_id(e, "function"))
    ids.append(asp_id(e, "field"))
    for op_ in bin_ops:
        ids.append(op_id(e, op_))
    for op_ in un_ops:
        ids.append(op_id(e, op_))
    self_type(
        e,
        x,
        "lt_global",
        e.cat(
            e.if_else(in_(e, "mem"), e.dstr("global("), e.s("const(")), bim0(e, ty(e), "desc", in_(e, "base")), e.s(")")
        ),
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
            e.ret(cast_value(e, xx(e), loc(e), a(e, "dest_type"), _gval(e, a(e, "cv")))),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lgtype_m"),
                    and_b(
                        e,
                        e.eq(in_(e, "mem"), acc(e, xx(e), a(e, "other"), "lgtype_m", "mem")),
                        is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "lgtype_m", "base")),
                    ),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(e.v("lt_global"), t(e, "lgtype_m"), e.p("base", in_(e, "base")), e.p("mem", in_(e, "mem")))
    )
    rt_lift_impl(e, x, "lt_global")
    rt_bind_impl(e, x, "lt_global", e.mb.types_string())
    rt_use_impl(e, x, "lt_global")
    x.append(
        e.impl_interface(
            e.v("lt_global"),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.if_only(
                        e.not_(in_(e, "mem")), ret_m(e, err_cve(e, loc(e), "cannot assign to a constant global"))
                    ),
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_set",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", in_(e, "base")),
                                e.p("self", _gval(e, a(e, "target"))),
                                e.p("value", a(e, "value")),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
        )
    )
    for op_ in bin_ops:
        x.append(
            e.impl_interface(
                e.v("lt_global"),
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
                                    e.p("base", _gval(e, a(e, "base"))),
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
                e.v("lt_global"),
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
                                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("base", _gval(e, a(e, "base")))),
                            )
                        ),
                    ),
                ),
            )
        )
    x.append(
        e.impl_interface(
            e.v("lt_global"),
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
                                e.p("function", _gval(e, a(e, "function"))),
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
            e.v("lt_global"),
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
                                e.p("value", _gval(e, a(e, "value"))),
                                e.p("key", a(e, "key")),
                            ),
                        )
                    ),
                ),
            ),
            e.p(
                "type_opt",
                bim(
                    e,
                    asp_iface(e, "field"),
                    "type_opt",
                    lookup_v(e, xx(e), in_(e, "base"), asp_iface(e, "field")),
                    e.v("arg"),
                ),
            ),
            e.p(
                "keys",
                bim(
                    e,
                    asp_iface(e, "field"),
                    "keys",
                    lookup_v(e, e.v("arg"), in_(e, "base"), asp_iface(e, "field")),
                    e.v("arg"),
                ),
            ),
        )
    )
    _def_extern_type(e, x)
    accessor(e, x, "lbinding", "ty", ty(e))
    accessor(e, x, "lbinding", "ptr", str_(e))
    method(e, x, "lbinding", "val", e.tup(), _lval_t(e), _lval_mem(e, in_(e, "ty"), in_(e, "ptr")))
    _binding_impl(
        e, x, "lbinding", cv_of(e, a(e, "code"), _lval_mem(e, in_(e, "ty"), in_(e, "ptr"))), binding_drop_body(e)
    )
    _binding_impl(
        e,
        x,
        "lbinding_none",
        e.mb.panic(e.s("llvm: unit binding has no value")),
        e.eresult_ok(e.mb.types_code(), code_none(e, loc(e))),
    )
    marker_type(e, x, "lunit", "unit", "lunit_m", e.aspect_dispatch(lv(e, "lunit_m_id"), asp_id(e, "bind")))
    x.append(e.impl_interface(e.v("lunit"), t(e, "lunit_m")))
    x.append(
        e.impl_interface(
            e.v("lunit"),
            e.mb.eval_aspect_bind(),
            e.p(
                "bind",
                e.eresult_ok(
                    e.mb.types_bind_result(),
                    e.call(
                        e.mb.eval_bind_result(),
                        e.rec(e.p("code", code_none(e, loc(e))), e.p("binding", mk_arg(e, "lbinding_none", e.tup()))),
                    ),
                ),
            ),
        )
    )
    accessor(e, x, "lrange", "code", code_t(e))
    accessor(e, x, "lrange", "n", _lval_t(e))
    x.append(
        e.impl_interface(
            e.v("lrange"),
            e.mb.eval_value(),
            e.p("type", in_(e, "t")),
            e.p("artifact_exporter", tm.artifact_exporter_impl(e, "lrange")),
        )
    )
    self_type(
        e,
        x,
        "lrange_t",
        e.cat(e.s("range("), bim0(e, ty(e), "desc", in_(e, "elem")), e.s(")")),
        e.aspect_dispatch(lv(e, "lrange_m_id"), asp_id(e, "iterable")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        body(e, e.ret(ok_cve(e, a(e, "cv")))),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lrange_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "lrange_m", "elem")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("lrange_t"), t(e, "lrange_m"), e.p("elem", in_(e, "elem"))))
    x.append(
        e.impl_interface(
            e.v("lrange_t"),
            asp_iface(e, "iterable"),
            e.p("element_type", in_(e, "elem")),
            e.p(
                "loop_binding",
                body(
                    e,
                    e.let(
                        "s",
                        e.call_m(
                            e.call_m(reinterpret(e, e.fld(e.v("arg"), "target"), "ltarget"), "mod", e.tup()),
                            "slot",
                            in_(e, "elem"),
                        ),
                    ),
                    e.ret(mk(e, "lbinding", e.p("ty", in_(e, "elem")), e.p("ptr", e.v("s")))),
                ),
            ),
            e.p(
                "element_access",
                ok_cve(
                    e,
                    cv_of(e, code_none(e, loc(e)), e.call_m(reinterpret(e, a(e, "loop"), "lbinding"), "val", e.tup())),
                ),
            ),
            e.p(
                "foreach",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("elem", in_(e, "elem")),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "base"))),
                    e.let("rv", reinterpret(e, cve_value(e, a(e, "base")), "lrange")),
                    _append_code(e, e.v("out"), e.call_m(e.v("rv"), "code", e.tup())),
                    e.let("ns", e.call_m(e.v("mod"), "slot", e.v("elem"))),
                    push(e, e.v("out"), _store_inst(e, loc(e), e.call_m(e.v("rv"), "n", e.tup()), e.v("ns"))),
                    e.let("lb", reinterpret(e, a(e, "loop"), "lbinding")),
                    e.let("cs", e.call_m(e.v("lb"), "ptr", e.tup())),
                    push(e, e.v("out"), _store_inst(e, loc(e), _lval_new(e, e.v("elem"), e.s("0")), e.v("cs"))),
                    e.let("head", _fresh_label(e, e.v("mod"))),
                    e.let("bodyl", _fresh_label(e, e.v("mod"))),
                    e.let("end", _fresh_label(e, e.v("mod"))),
                    push(e, e.v("out"), _br_inst(e, e.v("head"))),
                    push(e, e.v("out"), _label_inst(e, e.v("head"))),
                    e.let("i", _fresh(e, e.v("mod"))),
                    push(e, e.v("out"), _load_inst(e, loc(e), e.v("i"), e.v("elem"), e.v("cs"))),
                    e.let("nn", _fresh(e, e.v("mod"))),
                    push(e, e.v("out"), _load_inst(e, loc(e), e.v("nn"), e.v("elem"), e.v("ns"))),
                    e.let("c", _fresh(e, e.v("mod"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "cmp",
                            e.p("res", e.v("c")),
                            e.p(
                                "op",
                                e.if_else(
                                    acc(e, xx(e), e.v("elem"), "lint", "signed"), e.dstr("icmp slt"), e.dstr("icmp ult")
                                ),
                            ),
                            e.p("a", _lval_new(e, e.v("elem"), e.v("i"))),
                            e.p("b", _lval_new(e, e.v("elem"), e.v("nn"))),
                        ),
                    ),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            loc(e),
                            "condbr",
                            e.p("cond", _lval_new(e, _int_ty(e, "i1"), e.v("c"))),
                            e.p("t", e.v("bodyl")),
                            e.p("f", e.v("end")),
                        ),
                    ),
                    push(e, e.v("out"), _label_inst(e, e.v("bodyl"))),
                    _append_code(e, e.v("out"), a(e, "element_bind")),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "body"))),
                    e.if_only(
                        e.not_(cve_ended(e, a(e, "body"))),
                        e.seq(
                            e.let("i2", _fresh(e, e.v("mod"))),
                            push(e, e.v("out"), _load_inst(e, loc(e), e.v("i2"), e.v("elem"), e.v("cs"))),
                            e.let("i3", _fresh(e, e.v("mod"))),
                            push(
                                e,
                                e.v("out"),
                                _inst(
                                    e,
                                    loc(e),
                                    "binop",
                                    e.p("res", e.v("i3")),
                                    e.p("op", e.s("add")),
                                    e.p("a", _lval_new(e, e.v("elem"), e.v("i2"))),
                                    e.p("b", _lval_new(e, e.v("elem"), e.s("1"))),
                                ),
                            ),
                            push(
                                e, e.v("out"), _store_inst(e, loc(e), _lval_new(e, e.v("elem"), e.v("i3")), e.v("cs"))
                            ),
                            push(e, e.v("out"), _br_inst(e, e.v("head"))),
                        ),
                    ),
                    push(e, e.v("out"), _label_inst(e, e.v("end"))),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )
    self_type(
        e,
        x,
        "lloop_t",
        e.s("loop"),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "lloop_m_id"), asp_id(e, "iterable"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "lloop_m"))),
    )
    rt_lift_impl(e, x, "lloop_t")
    rt_bind_impl(e, x, "lloop_t", e.mb.types_string())
    rt_use_impl(e, x, "lloop_t")
    x.append(e.impl_interface(e.v("lloop_t"), t(e, "lloop_m")))
    self_type(
        e,
        x,
        "ltrap_t",
        e.s("trap"),
        e.aspect_dispatch(lv(e, "ltrap_m_id"), asp_id(e, "function"), asp_id(e, "bind")),
        target_mb.can_cast_from_unit(e),
        target_mb.cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "ltrap_m"))),
    )
    x.append(e.impl_interface(e.v("ltrap_t"), t(e, "ltrap_m")))
    x.append(
        e.impl_interface(e.v("ltrap_t"), e.mb.eval_aspect_bind(), e.p("bind", target_mb.bind_empty(e, "lebinding")))
    )
    x.append(
        e.impl_interface(
            e.v("ltrap_t"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(
                        e,
                        e.v("out"),
                        mk(
                            e,
                            "linst",
                            e.p("k", e.call(e.lower_v("li_trap"), e.tup())),
                            e.p("loc", e.opt_some(loc_t(e), loc(e))),
                        ),
                    ),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("lloop_t"),
            asp_iface(e, "iterable"),
            e.p("element_type", mk_arg(e, "lunit", e.tup())),
            e.p("loop_binding", mk_arg(e, "lbinding_none", e.tup())),
            e.p(
                "element_access",
                ok_cve(
                    e,
                    cv_of(
                        e,
                        code_none(e, loc(e)),
                        e.call(
                            e.eval_builtin("value_object_const"),
                            e.rec(e.p("type", mk_arg(e, "lunit", e.tup())), e.p("data", e.tup())),
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
                    e.let("head", _fresh_label(e, e.v("mod"))),
                    push(e, e.v("out"), _label_inst(e, e.v("head"))),
                    _append_code(e, e.v("out"), a(e, "element_bind")),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "body"))),
                    e.if_only(e.not_(cve_ended(e, a(e, "body"))), push(e, e.v("out"), _br_inst(e, e.v("head")))),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )
    self_type(
        e,
        x,
        "lgfn_t",
        e.cat(e.s("llvm global definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, lt(e, "lmod"), e.aspect_dispatch(lv(e, "lgfn_m_id"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "lgfn_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "lgfn_m", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "lgfn_t")
    rt_bind_impl(e, x, "lgfn_t", lt(e, "lmod"))
    rt_use_impl(e, x, "lgfn_t")
    x.append(e.impl_interface(e.v("lgfn_t"), t(e, "lgfn_m"), e.p("kind", in_(e, "kind"))))
    target_mb.method(
        e,
        x,
        "lgfn_t",
        "call",
        e.rec(e.p("xx", e.types_expr_context()), e.p("loc", loc_t(e)), e.p("argument", cve_t(e))),
        e.mb.call(e.mb.types_eresult(), cve_t(e)),
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))),
                ret_m(e, err_cve(e, loc(e), "llvm global definition argument has no value")),
            ),
            e.let("st", cve_type(e, e.v("argv"))),
            e.let("rk", lookup(e, xx(e), e.v("st"), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "llvm global definition argument must be a record")),
            ),
            e.let(
                "want",
                e.if_else(
                    _lgfn_is(e, "cstr_fn"),
                    e.list_new(str_(e), e.s("mod"), e.s("value")),
                    e.if_else(
                        _lgfn_is(e, "constant_fn"),
                        e.list_new(str_(e), e.s("ty"), e.s("value")),
                        e.if_else(
                            _lgfn_is(e, "ref_fn"),
                            e.list_new(str_(e), e.s("ref"), e.s("ty")),
                            e.if_else(
                                _lgfn_is(e, "extern_fn"),
                                e.list_new(str_(e), e.s("name"), e.s("ty"), e.s("libs")),
                                e.if_else(
                                    or_b(e, _lgfn_is(e, "func_fn"), _lgfn_is(e, "export_fn")),
                                    e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("params"), e.s("ty"), e.s("body")),
                                    e.if_else(
                                        _lgfn_is(e, "global_zero_fn"),
                                        e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("ty")),
                                        e.list_new(str_(e), e.s("mod"), e.s("name"), e.s("ty"), e.s("init")),
                                    ),
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
                        e.cat(e.s("llvm global definition has no argument "), e.fld(e.v("kc"), "bad")),
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
                        e.cat(e.s("llvm global definition requires arguments "), e.join(e.v("want"), ", ")),
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
                _lgfn_is(e, "cstr_fn"),
                e.seq(
                    e.let("modcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("mod")))),
                    e.let("valuecv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("value")))),
                    e.let(
                        "refcv",
                        _lgfn_staged(
                            e,
                            e.call_m(
                                e.call_m(graft(e, e.v("modcv")), "m", e.tup()),
                                "add_cstr",
                                graft(e, e.v("valuecv")),
                            ),
                        ),
                    ),
                    ret_m(
                        e,
                        tag_value(
                            e,
                            e.v("refcv"),
                            _lgfn_global_t(e, mk(e, "lt_ptr", e.p("pointee", _int_ty(e, "u8"))), False),
                        ),
                    ),
                ),
            ),
            e.let("tycv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("ty")))),
            e.let("tk", lookup(e, xx(e), cve_type(e, e.v("tycv")), asp_iface(e, "type"))),
            e.if_only(
                or_b(e, is_runtime(e, e.v("tycv")), e.not_(e.fld(e.v("tk"), "is_some"))),
                ret_m(e, err_cve(e, loc(e), "llvm ty must be a constant type")),
            ),
            e.let(
                "tyv",
                bim(e, asp_iface(e, "type"), "type", e.fld(e.v("tk"), "value"), cve_value(e, e.v("tycv"))),
            ),
            e.if_only(
                _lgfn_is(e, "ref_fn"),
                e.seq(
                    e.if_only(
                        e.not_(or_b(e, has(e, xx(e), e.v("tyv"), "lgtype_m"), has(e, xx(e), e.v("tyv"), "lloop_m"))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("llvm reference ty is not a reference type: "), ty_desc(e, e.v("tyv"))),
                            ),
                        ),
                    ),
                    e.let("rcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("ref")))),
                    ret_m(e, tag_value(e, e.v("rcv"), e.v("tyv"))),
                ),
            ),
            e.if_only(
                e.not_(has(e, xx(e), e.v("tyv"), "ltype")),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(e.s("llvm global definition ty is not an llvm type: "), ty_desc(e, e.v("tyv"))),
                    ),
                ),
            ),
            e.if_only(_lgfn_is(e, "extern_fn"), _extern_fn_body(e)),
            e.if_only(
                or_b(e, _lgfn_is(e, "func_fn"), _lgfn_is(e, "export_fn")),
                e.seq(
                    e.let("modcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("mod")))),
                    e.if_only(
                        e.not_(has(e, xx(e), e.v("tyv"), "lfn")),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("llvm function ty must be a function type, not "),
                                    ty_desc(e, e.v("tyv")),
                                ),
                            ),
                        ),
                    ),
                    e.let("pcv", _lgfn_field(e, "params")),
                    e.let("ptk", lookup(e, xx(e), cve_type(e, e.v("pcv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("ptk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "llvm function params must be a tuple of parameter names")),
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
                            e.let(
                                "nsk",
                                lookup(e, xx(e), cve_type(e, e.v("ncv")), e.mb.eval_aspect_string_const()),
                            ),
                            e.if_only(
                                e.not_(e.fld(e.v("nsk"), "is_some")),
                                ret_m(
                                    e,
                                    err_cve(e, loc(e), "llvm function parameter names must be constant" + " strings"),
                                ),
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
                    count_loop(e, "tn", acc(e, xx(e), e.v("tyv"), "lfn", "params")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("pn"), "v"), e.fld(e.v("tn"), "v"))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("llvm function has "),
                                    to_str(e, e.fld(e.v("pn"), "v")),
                                    e.s(" parameter names but its type has "),
                                    to_str(e, e.fld(e.v("tn"), "v")),
                                    e.s(" parameters"),
                                ),
                            ),
                        ),
                    ),
                    e.let("namecv", _lgfn_field(e, "name")),
                    e.let("bodycv", _lgfn_field(e, "body")),
                    e.seq(
                        e.let(
                            "refcv",
                            _lgfn_staged(
                                e,
                                e.call_m(
                                    e.call_m(graft(e, e.v("modcv")), "m", e.tup()),
                                    "func",
                                    e.rec(
                                        e.p("name", graft(e, e.v("namecv"))),
                                        e.p("params", e.lower(e.v("names"))),
                                        e.p("ty", e.lower(e.v("tyv"))),
                                        e.p("body", graft(e, e.v("bodycv"))),
                                        e.p("public", e.lower(_lgfn_is(e, "export_fn"))),
                                    ),
                                ),
                            ),
                        ),
                        ret_m(e, tag_value(e, e.v("refcv"), _lgfn_global_t(e, e.v("tyv"), False))),
                    ),
                ),
            ),
            e.let(
                "ir",
                e.if_else(
                    _lgfn_is(e, "global_zero_fn"),
                    unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(e.s("zeroinitializer")))),
                    unwrap_cve_m(
                        e,
                        try_er(
                            e,
                            _init_fn(
                                e,
                                e.v("tyv"),
                                unwrap_cve_m(
                                    e,
                                    e.call_m(
                                        e.v("fields"),
                                        "get",
                                        e.if_else(_lgfn_is(e, "constant_fn"), e.dstr("value"), e.dstr("init")),
                                    ),
                                ),
                            ),
                            cve_t(e),
                        ),
                    ),
                ),
            ),
            e.if_only(
                _lgfn_is(e, "constant_fn"),
                e.seq(ret_m(e, tag_value(e, e.v("ir"), _lgfn_global_t(e, e.v("tyv"), False)))),
            ),
            e.let("modcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("mod")))),
            e.let("namecv", _lgfn_field(e, "name")),
            e.seq(
                e.let(
                    "refcv",
                    _lgfn_staged(
                        e,
                        e.call_m(
                            e.call_m(graft(e, e.v("modcv")), "m", e.tup()),
                            "add_global",
                            e.rec(
                                e.p("konst", e.lower(_lgfn_is(e, "global_const_fn"))),
                                e.p("name", graft(e, e.v("namecv"))),
                                e.p("ty", e.lower(e.v("tyv"))),
                                e.p("init", graft(e, e.v("ir"))),
                            ),
                        ),
                    ),
                ),
                ret_m(
                    e,
                    tag_value(
                        e,
                        e.v("refcv"),
                        e.if_else(
                            _lgfn_is(e, "global_const_fn"),
                            _lgfn_global_t(e, mk(e, "lt_ptr", e.p("pointee", e.v("tyv"))), False),
                            _lgfn_global_t(e, e.v("tyv"), True),
                        ),
                    ),
                ),
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("ltarget"),
            e.mb.eval_target(),
            e.p("cast_exception", e.mb.panic(e.s("llvm target: exceptions are not supported"))),
            e.p(
                "initial_bind",
                e.eresult_err(e.mb.eval_binding(), loc(e), e.s("llvm target: exceptions are not supported")),
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
                    _code_of(e, e.list_new(lt(e, "linst"), _br_inst(e, e.call_m(_mod(e), "label_of", a(e, "dest"))))),
                ),
            ),
            e.p(
                "land",
                e.eresult_ok(
                    cve_t(e),
                    cv_no(
                        e,
                        _code_of(
                            e, e.list_new(lt(e, "linst"), _label_inst(e, e.call_m(_mod(e), "label_of", a(e, "dest"))))
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
                            e, e.list_new(lt(e, "linst"), _br_inst(e, e.call_m(_mod(e), "label_of", a(e, "dest"))))
                        ),
                    ),
                    e.ret(e.eresult_ok(code_t(e), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("guarded", e.mb.panic(e.s("llvm target: exceptions are not supported"))),
            e.p("exc_cleanup", e.mb.panic(e.s("llvm target: exceptions are not supported"))),
            # A cleanup block: land, run the cleanup, continue to the next block; the carried value already sits in
            # the slot its return stored it in.
            e.p(
                "exit_trampoline",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    push(e, e.v("out"), _label_inst(e, e.call_m(_mod(e), "label_of", a(e, "key")))),
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
                    e.if_only(e.not_(_is_llvm(e, xx(e), a(e, "cv"))), ret_m(e, a(e, "cv"))),
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
                            e.p("errs", panic_errs(e, "llvm target", "return value store", e.v("__r"))),
                        ),
                    ),
                    e.let("lv", _lval_of(e, e.v("r"))),
                    # The slot keeps the value's declared type (a type over an llvm value stays that type).
                    e.let("t0", cve_type(e, a(e, "cv"))),
                    e.let(
                        "base",
                        e.if_else(
                            has(e, xx(e), e.v("t0"), "lgtype_m"),
                            acc(e, xx(e), e.v("t0"), "lgtype_m", "base"),
                            e.v("t0"),
                        ),
                    ),
                    e.ret(
                        cv_of(
                            e,
                            cve_code(e, e.v("r")),
                            _lval_mem(
                                e,
                                mk(e, "lt_slot", e.p("base", e.v("base")), e.p("ptr", _lv_mem(e, e.v("lv")))),
                                _lv_mem(e, e.v("lv")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("stage", err_cve(e, loc(e), "llvm target: nested staging is not supported")),
            e.p("if", _if_hook(e)),
            e.p(
                "loop",
                body(
                    e,
                    e.let("mod", _mod(e)),
                    e.let("out", _insts_new(e)),
                    e.let("head", _fresh_label(e, e.v("mod"))),
                    push(e, e.v("out"), _br_inst(e, e.v("head"))),
                    push(e, e.v("out"), _label_inst(e, e.v("head"))),
                    _append_code(e, e.v("out"), cve_code(e, a(e, "body"))),
                    e.if_only(e.not_(cve_ended(e, a(e, "body"))), push(e, e.v("out"), _br_inst(e, e.v("head")))),
                    e.ret(ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                ),
            ),
            e.p("try_catch_finally", err_cve(e, loc(e), "llvm target: try/catch/finally is not supported")),
            e.p("match", _match_hook(e)),
        )
    )
    x.append(e.let("llvm_b", e.def_func(e.v("d"), "llvm")))
    x.append(
        e.func_impl(
            e.v("llvm_b"),
            e.tup(),
            e.option_type_some(t(e, "lmod")),
            e.mb.opt_none_type(),
            e.stage(
                e.seq(
                    e.let(
                        "m",
                        mk(
                            e,
                            "lmod",
                            e.p("n", num(e, 0)),
                            e.p("xx", e.opt_none(e.types_expr_context())),
                            e.p("structs", e.list_new(ty(e))),
                            e.p("struct_lines", e.list_new(str_(e))),
                            e.p("meta", e.list_new(lt(e, "lmeta"))),
                            e.p("dep_keys", e.list_new(str_(e))),
                            e.p("globals", e.list_new(lt(e, "lglobal"))),
                            e.p("constants", e.list_new(lt(e, "lglobal"))),
                            e.p("slots", e.list_new(lt(e, "lalloca"))),
                            e.p("funcs", e.list_new(str_(e))),
                            e.p("defs", e.list_new(lt(e, "ldef"))),
                            e.p("sip_key_id", target_mb.fresh_unique(e)),
                            e.p("sip_fn_id", target_mb.fresh_unique(e)),
                            e.p("labels", e.list_new(lt(e, "llabel"))),
                            e.p("frames", e.call(e.lower(e.fld(e.v("srcmap"), "new")), e.tup())),
                            e.p("dbg", e.list_new(str_(e), *[e.s(node) for node in DBG_HEADER])),
                            e.p("dbg_keys", e.map_new(str_(e), e.mb.types_int_box())),
                            e.p("sp", e.int_of(0)),
                        ),
                    ),
                    e.let("tgt", mk(e, "ltarget", e.p("mod", e.v("m")))),
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
                                e.p("exception_type", e.mb.opt_none_type()),
                            ),
                        ),
                    ),
                    e.call_m(e.v("m"), "set_xx", e.v("ctx")),
                    e.ret(e.v("m")),
                )
            ),
        )
    )
    self_type(
        e,
        x,
        "lt_gref",
        e.s("llvm global reference"),
        rt_dispatch(e, lt(e, "lgref"), e.aspect_dispatch(lv(e, "lgref_m_id"))),
        body(
            e,
            e.ret(or_b(e, is_equal(e, xx(e), outer(e), src_type(e)), is_equal(e, xx(e), lt(e, "lgref"), src_type(e)))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(ok_cve(e, retag_runtime(e, a(e, "cv"), outer(e)))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "lgref_m"))),
    )
    x.append(e.impl_interface(e.v("lt_gref"), t(e, "lgref_m")))
    x.append(
        e.impl_interface(
            e.v("lt_gref"),
            e.mb.eval_aspect_lift(),
            e.p(
                "lift",
                body(
                    e,
                    e.let("host", reinterpret(e, a(e, "external_host_value"), "lgref")),
                    e.ret(
                        e.eresult_ok(
                            e.mb.eval_value(),
                            e.call(
                                e.eval_builtin("value_object_const"),
                                e.rec(
                                    e.p("type", e.call_m(e.v("host"), "ty", e.tup())),
                                    e.p(
                                        "data",
                                        e.call(
                                            e.mb.must_reinterpret(),
                                            e.tup(
                                                e.call_m(e.v("host"), "ref", e.tup()), e.mb.builtin("types", "object")
                                            ),
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
    rt_bind_impl(e, x, "lt_gref", lt(e, "lgref"))
    rt_use_impl(e, x, "lt_gref")
    for prim in LLVM_PRIMS:
        elem_t = mk(e, "lt_float", e.p("bits", num(e, prim.bits))) if prim.is_float else _int_ty(e, prim.llvm)
        host_t = e.mb.builtin("types", prim.host)
        for konst in [True, False]:
            kind = "const" if konst else "global"
            list_ = []
            list_.append(e.let("list", hf(e, "h_fmt_list_" + prim.llvm, a(e, "values"))))
            list_.append(
                e.let(
                    "gty", mk(e, "lt_arr", e.p("elem", elem_t), e.p("count", e.call_m(e.v("list"), "count", e.tup())))
                )
            )
            list_.extend(_global_def(e, konst, e.call_m(e.v("list"), "ir", e.tup())))
            method(
                e,
                x,
                "lmod",
                (kind + "_list_") + prim.llvm,
                e.rec(e.p("name", str_(e)), e.p("values", e.list_type(host_t))),
                t(e, "lgref"),
                e.seq(*list_),
            )
            scalar = []
            scalar.append(e.let("gty", elem_t))
            scalar.extend(
                _global_def(
                    e,
                    konst,
                    e.if_else(
                        e.fld(a(e, "init"), "is_some"),
                        to_str(
                            e,
                            (
                                e.mb.as_(e.fld(a(e, "init"), "value"), e.types_double())
                                if prim.host == "float"
                                else e.fld(a(e, "init"), "value")
                            ),
                        ),
                        e.dstr("zeroinitializer"),
                    ),
                )
            )
            method(
                e,
                x,
                "lmod",
                (kind + "_") + prim.llvm,
                e.rec(e.p("name", str_(e)), e.p("init", e.call(e.mb.types_option(), host_t))),
                t(e, "lgref"),
                e.seq(*scalar),
            )
            array = []
            array.append(e.let("gty", mk(e, "lt_arr", e.p("elem", elem_t), e.p("count", a(e, "count")))))
            array.extend(
                _global_def(
                    e,
                    konst,
                    e.if_else(
                        e.fld(a(e, "init"), "is_some"),
                        hf_rec(
                            e,
                            "h_init_list_" + prim.llvm,
                            e.p("count", a(e, "count")),
                            e.p("values", e.fld(a(e, "init"), "value")),
                        ),
                        e.dstr("zeroinitializer"),
                    ),
                )
            )
            method(
                e,
                x,
                "lmod",
                (kind + "_array_") + prim.llvm,
                e.rec(
                    e.p("name", str_(e)),
                    e.p("count", int_t(e)),
                    e.p("init", e.call(e.mb.types_option(), e.list_type(host_t))),
                ),
                t(e, "lgref"),
                e.seq(*array),
            )
    method(
        e,
        x,
        "lgref",
        "ptr_ref",
        ty(e),
        str_(e),
        e.seq(
            e.let("cx", e.call_m(in_(e, "mod"), "xx", e.tup())),
            e.let("gt", in_(e, "ty")),
            e.let("base", acc(e, e.v("cx"), e.v("gt"), "lgtype_m", "base")),
            e.let(
                "target",
                e.if_else(
                    acc(e, e.v("cx"), e.v("gt"), "lgtype_m", "mem"),
                    e.v("base"),
                    acc(e, e.v("cx"), e.v("base"), "lptr", "pointee"),
                ),
            ),
            e.if_only(
                e.not_(
                    or_b(
                        e,
                        has(e, e.v("cx"), e.v("arg"), "lvoid"),
                        or_b(
                            e,
                            is_equal(e, e.v("cx"), e.v("target"), e.v("arg")),
                            and_b(
                                e,
                                has(e, e.v("cx"), e.v("target"), "larr"),
                                is_equal(e, e.v("cx"), acc(e, e.v("cx"), e.v("target"), "larr", "elem"), e.v("arg")),
                            ),
                        ),
                    )
                ),
                e.mb.panic(
                    e.cat(
                        e.s("llvm: pointer initializer "),
                        in_(e, "ref"),
                        e.s(" points to "),
                        ty_desc(e, e.v("target")),
                        e.s(", expected "),
                        ty_desc(e, e.v("arg")),
                    )
                ),
            ),
            e.ret(in_(e, "ref")),
        ),
    )
    method(
        e,
        x,
        "lmod",
        "h_fmt_list_ptr",
        e.rec(e.p("pointee", ty(e)), e.p("values", e.list_type(t(e, "lgref")))),
        t(e, "llist"),
        e.seq(
            e.let("parts", e.list_new(str_(e))),
            count_let(e, "n"),
            e.foreach(
                a(e, "values"),
                "g",
                e.seq(
                    push(e, e.v("parts"), e.cat(e.s("ptr "), e.call_m(e.v("g"), "ptr_ref", a(e, "pointee")))),
                    e.incr(e.fld(e.v("n"), "v")),
                ),
            ),
            e.ret(
                mk(
                    e,
                    "llist",
                    e.p("ir", e.cat(e.s("["), e.join(e.v("parts"), ", "), e.s("]"))),
                    e.p("count", e.fld(e.v("n"), "v")),
                )
            ),
        ),
    )
    for konst in [True, False]:
        kind = "const" if konst else "global"
        ptr_elem = mk(e, "lt_ptr", e.p("pointee", a(e, "pointee")))
        ptrs = []
        ptrs.append(
            e.let(
                "list",
                e.call_m(
                    outer(e), "h_fmt_list_ptr", e.rec(e.p("pointee", a(e, "pointee")), e.p("values", a(e, "values")))
                ),
            )
        )
        ptrs.append(
            e.let("gty", mk(e, "lt_arr", e.p("elem", ptr_elem), e.p("count", e.call_m(e.v("list"), "count", e.tup()))))
        )
        ptrs.extend(_global_def(e, konst, e.call_m(e.v("list"), "ir", e.tup())))
        method(
            e,
            x,
            "lmod",
            kind + "_list_ptr",
            e.rec(e.p("name", str_(e)), e.p("pointee", ty(e)), e.p("values", e.list_type(t(e, "lgref")))),
            t(e, "lgref"),
            e.seq(*ptrs),
        )
        scalar = []
        scalar.append(e.let("gty", ptr_elem))
        scalar.extend(
            _global_def(
                e,
                konst,
                e.if_else(
                    e.fld(a(e, "init"), "is_some"),
                    e.call_m(e.fld(a(e, "init"), "value"), "ptr_ref", a(e, "pointee")),
                    e.dstr("null"),
                ),
            )
        )
        method(
            e,
            x,
            "lmod",
            kind + "_ptr",
            e.rec(e.p("name", str_(e)), e.p("pointee", ty(e)), e.p("init", e.call(e.mb.types_option(), t(e, "lgref")))),
            t(e, "lgref"),
            e.seq(*scalar),
        )
        array = []
        array.append(e.let("gty", mk(e, "lt_arr", e.p("elem", ptr_elem), e.p("count", a(e, "count")))))
        array.extend(
            _global_def(
                e,
                konst,
                e.if_else(
                    e.fld(a(e, "init"), "is_some"),
                    e.seq(
                        e.let(
                            "list",
                            e.call_m(
                                outer(e),
                                "h_fmt_list_ptr",
                                e.rec(e.p("pointee", a(e, "pointee")), e.p("values", e.fld(a(e, "init"), "value"))),
                            ),
                        ),
                        e.if_only(
                            e.not_(e.eq(e.call_m(e.v("list"), "count", e.tup()), a(e, "count"))),
                            e.mb.panic(
                                e.cat(
                                    e.s("llvm: array initializer has "),
                                    to_str(e, e.call_m(e.v("list"), "count", e.tup())),
                                    e.s(" elements, expected "),
                                    to_str(e, a(e, "count")),
                                )
                            ),
                        ),
                        e.ret(e.call_m(e.v("list"), "ir", e.tup())),
                    ),
                    e.dstr("zeroinitializer"),
                ),
            )
        )
        method(
            e,
            x,
            "lmod",
            kind + "_array_ptr",
            e.rec(
                e.p("name", str_(e)),
                e.p("pointee", ty(e)),
                e.p("count", int_t(e)),
                e.p("init", e.call(e.mb.types_option(), e.list_type(t(e, "lgref")))),
            ),
            t(e, "lgref"),
            e.seq(*array),
        )
    def_obj(
        e,
        x,
        "ldesc",
        "llvm data type description",
        e.rec(e.p("prim", str_(e)), e.p("count", int_t(e)), e.p("pointee", ty(e))),
    )
    accessor(e, x, "ldesc", "pointee", ty(e))
    accessor(e, x, "ldesc", "prim", str_(e))
    accessor(e, x, "ldesc", "count", int_t(e))
    _fn_def(e, x, "c_describe", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), t(e, "ldesc"))
    describe = []
    describe.append(e.let("cx", xx(e)))
    describe.append(e.let("dty", a(e, "ty")))
    describe.append(e.let("r", e.rec(e.p("prim", e.dstr("")), e.p("count", e.int_of(-1)))))
    describe.append(
        e.let(
            "elem",
            e.if_else(has(e, e.v("cx"), e.v("dty"), "larr"), acc(e, e.v("cx"), e.v("dty"), "larr", "elem"), e.v("dty")),
        )
    )
    describe.append(
        e.if_only(
            has(e, e.v("cx"), e.v("dty"), "larr"),
            e.mb.set(e.fld(e.v("r"), "count"), acc(e, e.v("cx"), e.v("dty"), "larr", "count")),
        )
    )
    for prim in LLVM_PRIMS:
        describe.append(
            e.if_only(_is_prim(e, e.v("cx"), e.v("elem"), prim), e.mb.set(e.fld(e.v("r"), "prim"), e.s(prim.llvm)))
        )
    describe.append(e.if_only(has(e, e.v("cx"), e.v("elem"), "lptr"), e.mb.set(e.fld(e.v("r"), "prim"), e.s("ptr"))))
    describe.append(
        e.ret(
            mk(
                e,
                "ldesc",
                e.p("prim", e.fld(e.v("r"), "prim")),
                e.p("count", e.fld(e.v("r"), "count")),
                e.p(
                    "pointee",
                    e.if_else(
                        has(e, e.v("cx"), e.v("elem"), "lptr"),
                        acc(e, e.v("cx"), e.v("elem"), "lptr", "pointee"),
                        e.v("elem"),
                    ),
                ),
            )
        )
    )
    fn_impl(e, x, "c_describe", body(e, *describe))
    accessor(e, x, "lparam", "ty", ty(e))
    accessor(e, x, "lparam", "ptr", str_(e))
    _initial_bind_impl(e, x, "lt_int")
    _initial_bind_impl(e, x, "lt_float")
    _initial_bind_impl(e, x, "lt_ptr")
    _initial_bind_impl(e, x, "lt_arr")
    _initial_bind_impl(e, x, "lt_struct")
    _initial_bind_impl(e, x, "lt_fn")
    _initial_bind_impl(e, x, "lt_void")

    # The unsafe conversions, named: a pointer to another pointer type and a function to a pointer (retags, every
    # pointer being `ptr`), a pointer to a 64-bit integer (`ptrtoint`), a 64-bit integer to a pointer (`inttoptr`).
    def base_of(ty_):
        return e.if_else(has(e, xx(e), ty_, "lgtype_m"), acc(e, xx(e), ty_, "lgtype_m", "base"), ty_)

    def lptr(ty_):
        return has(e, xx(e), base_of(ty_), "lptr")

    def in_memory(ty_):
        # An in-memory global (`global(T)`): its reference is a pointer to its storage.
        return and_b(e, has(e, xx(e), ty_, "lgtype_m"), acc(e, xx(e), ty_, "lgtype_m", "mem"))

    def ptr_src(ty_):
        return or_b(e, lptr(ty_), in_memory(ty_))

    def lfn(ty_):
        return has(e, xx(e), base_of(ty_), "lfn")

    def lint64(ty_):
        return and_b(
            e,
            has(e, xx(e), base_of(ty_), "lint"),
            e.eq(acc(e, xx(e), base_of(ty_), "lint", "bits"), num(e, 64)),
        )

    def fn_ref(cv, to):
        # A function is a reference (as in a global initializer, where there is no module to emit into): the same
        # reference under the pointer type.
        return ok_cve(e, cv_of(e, cve_code(e, cv), _lval_new(e, to, _lv_ref(e, _lval_of(e, cv)))))

    def loaded(cv, make):
        # The value as its base type (a global or constant reference cast to its base: a load, or the reference as
        # a plain value), then converted.
        return e.mb.labeled(
            "c",
            e.seq(
                e.let("__pty", base_of(cve_type(e, cv))),
                e.let("__pv", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), e.v("__pty"), cv))),
                e.mb.return_to("c", make(e.v("__pv"))),
            ),
        )

    def ptr_cast(cv, to):
        # An in-memory global's address is its reference under the pointer type (no load); anything else is the
        # pointer value retagged.
        return e.if_else(
            in_memory(cve_type(e, cv)),
            ok_cve(e, cv_of(e, cve_code(e, cv), _lval_new(e, to, hf(e, "h_gref", cv)))),
            loaded(cv, lambda v: _retag(e, v, to)),
        )

    target_mb.named_conv(e, x, "ptr_cast_b", "llvm.ptr_cast", ptr_src, lptr, ptr_cast)
    target_mb.named_conv(e, x, "fn_to_ptr_b", "llvm.fn_to_ptr", lfn, lptr, fn_ref)

    # `num_cast`: the C conversion between numeric types, named once at the site instead of per rule: integers wrap
    # (truncate, or extend by the source's signedness), floats truncate toward zero into integers, integers and
    # floats round into floats; a constant converts losslessly or not at all.
    def numeric(ty_):
        return or_b(e, has(e, xx(e), ty_, "lint"), has(e, xx(e), ty_, "lfloat"))

    def num_src(ty_):
        return or_b(e, is_const(e, xx(e), ty_), numeric(base_of(ty_)))

    def num_cast(cv, to):
        v = e.v("__nv")
        st = e.v("__st")

        def when(cond, result):
            return e.if_only(cond, e.mb.return_to("n", result))

        return e.mb.labeled(
            "n",
            e.seq(
                e.if_only(
                    is_const(e, xx(e), cve_type(e, cv)),
                    e.mb.return_to("n", cast_value(e, xx(e), loc(e), to, cv)),
                ),
                e.let("__pty", base_of(cve_type(e, cv))),
                e.let("__bv", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), e.v("__pty"), cv))),
                # The operand as an SSA value (a place is loaded).
                e.let(
                    "__nv",
                    unwrap_cve_m(e, try_er(e, _ssa(e, xx(e), loc(e), _xmod(e), e.v("__bv")), cve_t(e))),
                ),
                e.let("__st", cve_type(e, v)),
                e.if_only(
                    and_b(e, has(e, xx(e), st, "lint"), has(e, xx(e), to, "lint")),
                    e.seq(
                        e.let("__sb", cv_bits(e, st, "lint")),
                        e.let("__tb", acc(e, xx(e), to, "lint", "bits")),
                        when(e.eq(e.v("__sb"), e.v("__tb")), _retag(e, v, to)),
                        when(e.mb.operator_gt(e.v("__sb"), e.v("__tb")), _conv(e, e.s("trunc"), v, to)),
                        e.mb.return_to(
                            "n",
                            _conv(
                                e,
                                e.if_else(acc(e, xx(e), st, "lint", "signed"), e.dstr("sext"), e.dstr("zext")),
                                v,
                                to,
                            ),
                        ),
                    ),
                ),
                when(
                    and_b(e, has(e, xx(e), st, "lfloat"), has(e, xx(e), to, "lint")),
                    _conv(e, e.if_else(acc(e, xx(e), to, "lint", "signed"), e.dstr("fptosi"), e.dstr("fptoui")), v, to),
                ),
                when(
                    and_b(e, has(e, xx(e), st, "lint"), has(e, xx(e), to, "lfloat")),
                    _conv(e, e.if_else(acc(e, xx(e), st, "lint", "signed"), e.dstr("sitofp"), e.dstr("uitofp")), v, to),
                ),
                e.let("__fb", cv_bits(e, st, "lfloat")),
                e.let("__ftb", acc(e, xx(e), to, "lfloat", "bits")),
                when(e.eq(e.v("__fb"), e.v("__ftb")), _retag(e, v, to)),
                when(e.mb.operator_gt(e.v("__fb"), e.v("__ftb")), _conv(e, e.s("fptrunc"), v, to)),
                e.mb.return_to("n", _conv(e, e.s("fpext"), v, to)),
            ),
        )

    target_mb.named_conv(e, x, "num_cast_b", "llvm.num_cast", num_src, numeric, num_cast)
    target_mb.named_conv(
        e,
        x,
        "ptr_to_int_b",
        "llvm.ptr_to_int",
        lptr,
        lint64,
        lambda cv, to: loaded(cv, lambda v: _conv(e, e.s("ptrtoint"), v, to)),
    )
    target_mb.named_conv(
        e, x, "int_to_ptr_b", "llvm.int_to_ptr", lint64, lptr, lambda cv, to: _conv(e, e.s("inttoptr"), cv, to)
    )
    x.append(e.finish(e.v("d")))
    passthrough = [
        "field_t",
        "ptr",
        "array",
        "field",
        "struct",
        "struct_tail",
        "tail",
        "fn",
        "fn_varargs",
        "tuple",
        "range",
        "global_t",
        "extern_t",
        "func_dep",
        "alloc_dep",
        "data_dep",
        "cstr_dep",
    ]
    defs = []
    defs.append(e.p("new", e.fld(e.v("llvm_b"), "func")))
    defs.append(e.p("mod_t", t(e, "lmod")))
    defs.append(e.p("meta_t", t(e, "lmeta")))
    defs.append(e.p("meta_other", e.v("lm_other")))
    defs.append(e.p("meta_new", e.fld(e.v("lmeta"), "new")))
    defs.append(e.p("field_t", t(e, "lfield")))
    defs.append(e.p("describe", e.v("c_describe")))
    defs.append(e.p("gref_obj_t", t(e, "lgref")))
    for name in passthrough[1:]:
        defs.append(e.p(name, e.v("c_" + name)))
    for name in CONV_NAMES:
        defs.append(e.p(name, e.fld(e.v(name + "_b"), "func")))
    for obj in [
        "lt_int",
        "lt_float",
        "lt_void",
        "lloop_t",
        "ltrap_t",
        "lgfn_t",
        "lt_ptr",
        "lt_global",
        "lt_gref",
        "lunit",
        "lt_tuple",
        "ladep",
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
                lty(
                    e,
                    "lt_int",
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
        y.append(e.let("f" + str(bits), lty(e, "lt_float", e.rec(e.p("bits", e.int_of(bits))))))
    exported.append("void")
    y.append(e.let("void", lty(e, "lt_void", e.tup())))
    exported.append("unit")
    y.append(e.let("unit", lty(e, "lunit", e.tup())))
    exported.append("loop")
    y.append(e.let("loop", lty(e, "lloop_t", e.tup())))
    exported.append("trap")
    y.append(e.let("trap", lty(e, "ltrap_t", e.tup())))
    y.append(
        e.let(
            "null_t",
            lty(
                e,
                "lt_global",
                e.rec(e.p("base", lty(e, "lt_ptr", e.rec(e.p("pointee", e.v("void"))))), e.p("mem", e.b(False))),
            ),
        )
    )
    y.append(
        e.let(
            "cstr_t",
            lty(
                e,
                "lt_global",
                e.rec(e.p("base", lty(e, "lt_ptr", e.rec(e.p("pointee", e.v("u8"))))), e.p("mem", e.b(False))),
            ),
        )
    )
    for kind in LGFN_KINDS:
        if kind != "cstr_fn":
            exported.append(kind)
        y.append(
            e.let(kind + "_o", e.call(e.fld(e.v("k"), "lgfn_t_new"), e.rec(e.p("kind", e.int_of(_lgfn_kind(kind))))))
        )
    exported.append("gref_t")
    y.append(e.let("gref_t", lty(e, "lt_gref", e.tup())))
    y.append(e.let("d", e.define()))
    y.append(e.let("gfn_d", e.define()))
    for kind in LGFN_KINDS:
        target_mb.const_fn(
            e,
            y,
            kind + "_b",
            "llvm." + kind,
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
    y.append(e.let("mod_o", e.def_object(e.v("d"), "llvm module")))
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
            "null",
            e.tup(),
            e.option_type_some(e.v("null_t")),
            e.stage(e.call(e.lower_v("ref_fn"), e.rec(e.p("ref", e.s("null")), e.p("ty", e.lower_v("null_t"))))),
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
    # The module's SipHash key block (two zeroed i64 `values.hash` reads) as the alloc dependency defining it, so
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
                        e.fld(e.lower_v("k"), "ladep_new"),
                        e.rec(
                            e.p("id", e.call_m(in_(e, "m"), "sip_key_id", e.tup())),
                            e.p("name", e.s("siphash_key")),
                            e.p(
                                "ty",
                                e.call(
                                    e.fld(e.lower_v("k"), "array"),
                                    e.rec(e.p("elem", e.lower_v("i64")), e.p("count", e.int_of(2))),
                                ),
                            ),
                        ),
                    ),
                    e.mb.eval_type(),
                )
            ),
        )
    )
    for factory in DATA_FACTORIES:
        kind = "const" if factory.startswith("const") else "global"
        fb = []
        fb.append(e.let("tycv", a(e, "argument")))
        fb.append(e.let("tk", lookup(e, xx(e), cve_type(e, e.v("tycv")), asp_iface(e, "type"))))
        fb.append(
            e.if_only(
                or_b(e, is_runtime(e, e.v("tycv")), e.not_(e.fld(e.v("tk"), "is_some"))),
                ret_m(e, err_cve(e, loc(e), ("llvm." + factory) + ": argument must be a constant type")),
            )
        )
        fb.append(
            e.let(
                "desc",
                e.call(
                    e.fld(e.lower_v("k"), "describe"),
                    e.rec(
                        e.p("xx", xx(e)),
                        e.p(
                            "ty",
                            bim(e, asp_iface(e, "type"), "type", e.fld(e.v("tk"), "value"), cve_value(e, e.v("tycv"))),
                        ),
                    ),
                ),
            )
        )
        fb.append(e.let("prim", e.call_m(e.v("desc"), "prim", e.tup())))
        fb.append(e.let("count", e.call_m(e.v("desc"), "count", e.tup())))
        fb.append(e.let("scalar", e.mb.operator_lt(e.v("count"), num(e, 0))))
        fb.append(e.let("mod_t", e.lower(e.fld(e.v("mod_o"), "type"))))
        is_ptr = e.eq(e.v("prim"), e.s("ptr"))
        ptr_lmod = e.call_m(e.fld(e.v("arg"), "mod"), "m", e.tup())
        if factory.endswith("_list"):
            fb.append(
                e.if_only(
                    and_b(e, is_ptr, e.v("scalar")),
                    e.seq(
                        _ptr_pointee_let(e),
                        _ptr_obj_let(e),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(
                                e.p("mod", e.v("mod_t")),
                                e.p("name", str_(e)),
                                e.p("values", e.list_type(e.lower_v("gref_t"))),
                            ),
                            e.seq(
                                _grefs_new(e),
                                _grefs_fill(e, e.fld(e.v("arg"), "values")),
                                e.ret(
                                    e.call_m(
                                        ptr_lmod,
                                        kind + "_list_ptr",
                                        e.rec(
                                            e.p("name", e.fld(e.v("arg"), "name")),
                                            e.p("pointee", e.lower(e.v("pointee"))),
                                            e.p("values", e.v("refs")),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                )
            )
        else:
            fb.append(
                e.if_only(
                    and_b(e, is_ptr, e.v("scalar")),
                    e.seq(
                        _ptr_pointee_let(e),
                        _ptr_obj_let(e),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(
                                e.p("mod", e.v("mod_t")),
                                e.p("name", str_(e)),
                                e.p("init", e.call(e.mb.types_option(), e.lower_v("gref_t"))),
                            ),
                            e.seq(
                                e.let("init", e.fld(e.v("arg"), "init")),
                                e.let(
                                    "ref",
                                    e.if_else(
                                        e.fld(e.v("init"), "is_some"),
                                        e.opt_some(
                                            e.lower(e.v("gref_obj")),
                                            e.call(
                                                e.mb.must_reinterpret(),
                                                e.tup(e.fld(e.v("init"), "value"), e.lower(e.v("gref_obj"))),
                                            ),
                                        ),
                                        e.opt_none(e.lower(e.v("gref_obj"))),
                                    ),
                                ),
                                e.ret(
                                    e.call_m(
                                        ptr_lmod,
                                        kind + "_ptr",
                                        e.rec(
                                            e.p("name", e.fld(e.v("arg"), "name")),
                                            e.p("pointee", e.lower(e.v("pointee"))),
                                            e.p("init", e.v("ref")),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                )
            )
            fb.append(
                e.if_only(
                    and_b(e, is_ptr, e.not_(e.v("scalar"))),
                    e.seq(
                        _ptr_pointee_let(e),
                        _ptr_obj_let(e),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(
                                e.p("mod", e.v("mod_t")),
                                e.p("name", str_(e)),
                                e.p("init", e.call(e.mb.types_option(), e.list_type(e.lower_v("gref_t")))),
                            ),
                            e.seq(
                                e.let("init", e.fld(e.v("arg"), "init")),
                                e.let(
                                    "ref",
                                    e.if_else(
                                        e.fld(e.v("init"), "is_some"),
                                        e.seq(
                                            _grefs_new(e),
                                            _grefs_fill(e, e.fld(e.v("init"), "value")),
                                            e.ret(e.opt_some(e.list_type(e.lower(e.v("gref_obj"))), e.v("refs"))),
                                        ),
                                        e.opt_none(e.list_type(e.lower(e.v("gref_obj")))),
                                    ),
                                ),
                                e.ret(
                                    e.call_m(
                                        ptr_lmod,
                                        kind + "_array_ptr",
                                        e.rec(
                                            e.p("name", e.fld(e.v("arg"), "name")),
                                            e.p("pointee", e.lower(e.v("pointee"))),
                                            e.p("count", e.lower(e.v("count"))),
                                            e.p("init", e.v("ref")),
                                        ),
                                    )
                                ),
                            ),
                        ),
                    ),
                )
            )
        for prim in LLVM_PRIMS:
            host_t = e.mb.builtin("types", prim.host)
            lmod = e.call_m(e.fld(e.v("arg"), "mod"), "m", e.tup())
            is_prim = e.eq(e.v("prim"), e.s(prim.llvm))
            if factory.endswith("_list"):
                fb.append(
                    e.if_only(
                        and_b(e, is_prim, e.v("scalar")),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(e.p("mod", e.v("mod_t")), e.p("name", str_(e)), e.p("values", e.list_type(host_t))),
                            e.call_m(
                                lmod,
                                (kind + "_list_") + prim.llvm,
                                e.rec(
                                    e.p("name", e.fld(e.v("arg"), "name")), e.p("values", e.fld(e.v("arg"), "values"))
                                ),
                            ),
                        ),
                    )
                )
            else:
                fb.append(
                    e.if_only(
                        and_b(e, is_prim, e.v("scalar")),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(
                                e.p("mod", e.v("mod_t")),
                                e.p("name", str_(e)),
                                e.p("init", e.call(e.mb.types_option(), host_t)),
                            ),
                            e.call_m(
                                lmod,
                                (kind + "_") + prim.llvm,
                                e.rec(e.p("name", e.fld(e.v("arg"), "name")), e.p("init", e.fld(e.v("arg"), "init"))),
                            ),
                        ),
                    )
                )
                fb.append(
                    e.if_only(
                        and_b(e, is_prim, e.not_(e.v("scalar"))),
                        _specialize(
                            e,
                            "llvm." + factory,
                            e.rec(
                                e.p("mod", e.v("mod_t")),
                                e.p("name", str_(e)),
                                e.p("init", e.call(e.mb.types_option(), e.list_type(host_t))),
                            ),
                            e.call_m(
                                lmod,
                                (kind + "_array_") + prim.llvm,
                                e.rec(
                                    e.p("name", e.fld(e.v("arg"), "name")),
                                    e.p("count", e.lower(e.v("count"))),
                                    e.p("init", e.fld(e.v("arg"), "init")),
                                ),
                            ),
                        ),
                    )
                )
        fb.append(e.ret(err_cve(e, loc(e), ("llvm." + factory) + ": unsupported type")))
        y.append(e.let(factory + "_b", e.call_m(e.v("d"), "const_func", e.s("llvm." + factory))))
        y.append(
            e.call_m(
                e.v(factory + "_b"),
                "impl",
                e.rec(
                    e.p("impl_body", e.stage(body(e, *fb))),
                    e.p("exception_type", e.mb.opt_none_type()),
                    e.p("description", e.opt_none(str_(e))),
                ),
            )
        )
    y.append(e.let("llvm_b", e.def_func(e.v("d"), "llvm")))
    y.append(
        e.func_impl(
            e.v("llvm_b"),
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
                e.seq(
                    e.let("args", e.str_list(e.s("-O2"), e.s("app.ll"), e.s("-o"), e.s("app"))),
                    e.foreach(a(e, "libs"), "l", push(e, e.v("args"), e.cat(e.s("-l"), e.v("l")))),
                    e.let(
                        "r",
                        e.call(
                            e.mb.builtin("exec"),
                            e.rec(
                                e.p("command", e.s("clang")),
                                e.p("args", e.v("args")),
                                e.p("env", e.map_new(str_(e), str_(e))),
                                e.p(
                                    "files",
                                    e.map_new(
                                        str_(e),
                                        e.call(e.mb.types_array(), e.mb.types_byte()),
                                        e.p("app.ll", e.call(e.mb.eval_str_utf8(), a(e, "ir"))),
                                    ),
                                ),
                                e.p("success_codes", e.opt_none(e.list_type(int_t(e)))),
                            ),
                        ),
                    ),
                    e.let("f", e.call_m(e.call_m0(e.v("r"), "dir"), "open", e.s("app"))),
                    e.ret(
                        e.call(
                            e.mb.builtin("app"),
                            e.rec(
                                e.p("executor", e.mb.opt_none_string()),
                                e.p(
                                    "bytes",
                                    e.call_m(
                                        e.v("f"),
                                        "read",
                                        e.rec(e.p("offset", e.int_of(0)), e.p("len", e.fld(e.v("f"), "len"))),
                                    ),
                                ),
                            ),
                        )
                    ),
                )
            ),
        )
    )
    y.append(e.finish(e.v("d")))
    ydefs = []
    ydefs.append(e.p("new", e.fld(e.v("llvm_b"), "func")))
    ydefs.append(e.p("build", e.fld(e.v("build_b"), "func")))
    for factory in DATA_FACTORIES:
        ydefs.append(e.p(factory, e.fld(e.v(factory + "_b"), "func")))
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
    for factory in DATA_FACTORIES:
        exports.append(e.p(factory, e.fld(e.v("k"), factory)))
    for name in passthrough + CONV_NAMES:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    top.append(e.ret(e.rec(*exports)))
    return top
