"""webgl-uniforms.atz: std140 uniform blocks laid out in wasm memory and declared in glsl."""

from .. import target_mb as tm
from ..target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bool_t,
    body,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_t,
    const_eval_in,
    count_let,
    count_loop,
    cv_no,
    cve_code,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    err_cve,
    errs_t,
    fn_impl,
    fn_throws,
    graft,
    has,
    has_b,
    hf_rec,
    in_,
    int_t,
    is_const,
    is_runtime,
    loc,
    loc_t,
    lookup,
    lookup_v,
    lt,
    lv,
    mk,
    no_cast_to,
    num,
    ok_cve,
    or_b,
    push,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    str_,
    t,
    tag_value,
    throw_err,
    to_str,
    try_er,
    ty,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    xx,
    xx_t,
)

TARGET = "uniforms"

UGFN_KINDS = ["wasm_fn", "glsl_fn"]


def _ugfn_kind(kind):
    return UGFN_KINDS.index(kind)


def _staged(e, expr):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(expr)))


def _field(e, key):
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(key)))


def _fn_def(e, out, name, arg_type, ret):
    return tm.fn_def(e, out, TARGET, name, arg_type, ret)


def _const_str(e, cv):
    return bim(
        e,
        e.mb.eval_aspect_string_const(),
        "get",
        lookup_v(e, xx(e), cve_type(e, cv), e.mb.eval_aspect_string_const()),
        cve_value(e, cv),
    )


def _int_cve(e, value):
    return _staged(e, e.lower(e.mb.as_(value, int_t(e))))


def _elem_type(e, kind):
    return e.call_m(
        e.map_new(
            str_(e),
            ty(e),
            e.p("float", e.lower_v("t_f32")),
            e.p("uint", e.lower_v("t_u32")),
            e.p("int", e.lower_v("t_i32")),
            e.p("bool", e.lower_v("t_i32")),
        ),
        "get",
        kind,
    )


def _place(e, self_cv, kind, byte_offset):
    return e.seq(
        e.let("__et", _elem_type(e, kind)),
        e.let("__pt", e.call(e.lower_v("c_ptr"), e.v("__et"))),
        # The block's pointer as the field's element pointer: the named conversion, staged over the tagged value.
        e.let("__gv", unwrap_cve_m(e, tag_value(e, self_cv, e.lower_v("t_gpv")))),
        e.let("__pc", e.lower_v("c_ptr_cast")),
        e.let(
            "__pv",
            unwrap_cve_m(
                e,
                const_eval_in(
                    e,
                    xx(e),
                    loc(e),
                    e.stage(tm.conv(e, e.lower(e.v("__pc")), graft(e, e.v("__gv")), e.lower(e.v("__pt")))),
                ),
            ),
        ),
        e.ret(
            unwrap_cve_m(
                e,
                bim(
                    e,
                    asp_iface(e, "field"),
                    "field",
                    lookup_v(e, xx(e), e.v("__pt"), asp_iface(e, "field")),
                    e.rec(
                        e.p("xx", xx(e)),
                        e.p("loc", loc(e)),
                        e.p("value", e.v("__pv")),
                        e.p("key", _int_cve(e, e.mb.operator_div(byte_offset, e.int_of(4)))),
                    ),
                ),
            )
        ),
    )


def module(e):
    x = []
    x.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("glsl", e.import_local("glsl", "glsl-es-3.00.atz")))
    for t_ in ["f32", "i32", "u32", "void"]:
        x.append(e.let("t_" + t_, e.fld(e.v("wasm"), t_)))
    x.append(e.let("c_ptr", e.fld(e.v("wasm"), "ptr")))
    x.append(e.let("c_ptr_cast", e.fld(e.v("wasm"), "ptr_cast")))
    x.append(e.let("t_gpv", e.call(e.fld(e.v("wasm"), "global_t"), e.call(e.v("c_ptr"), e.v("t_void")))))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    tm.def_iface(e, x, "ufield_m")
    tm.def_iface(e, x, "ublock_m", e.p("name", str_(e)))
    tm.def_iface(
        e, x, "uvec_m", e.p("offset", int_t(e)), e.p("kind", str_(e)), e.p("n", int_t(e)), e.p("mat", bool_t(e))
    )
    tm.def_iface(e, x, "ugfn_m", e.p("kind", int_t(e)))
    tm.def_obj(
        e,
        x,
        "ufield",
        "std140 field",
        e.rec(
            e.p("name", str_(e)),
            e.p("ty", ty(e)),
            e.p("offset", int_t(e)),
            e.p("kind", str_(e)),
            e.p("n", int_t(e)),
            e.p("mat", bool_t(e)),
        ),
    )
    for f in ["name", "kind"]:
        tm.accessor(e, x, "ufield", f, str_(e))
    for f in ["offset", "n"]:
        tm.accessor(e, x, "ufield", f, int_t(e))
    tm.accessor(e, x, "ufield", "ty", ty(e))
    tm.accessor(e, x, "ufield", "mat", bool_t(e))
    tm.marker_type(e, x, "ufield", "ufield", "ufield_m", e.aspect_dispatch(lv(e, "ufield_m_id")))
    x.append(e.impl_interface(e.v("ufield"), t(e, "ufield_m")))
    tm.def_obj(
        e,
        x,
        "ut_block",
        "std140 block in wasm memory",
        e.rec(e.p("name", str_(e)), e.p("size", int_t(e)), e.p("fields", e.list_type(t(e, "ufield")))),
    )
    tm.def_obj(
        e,
        x,
        "ut_vec",
        "std140 vector or matrix field",
        e.rec(e.p("offset", int_t(e)), e.p("kind", str_(e)), e.p("n", int_t(e)), e.p("mat", bool_t(e))),
    )
    tm.def_obj(e, x, "ugfn_t", "uniforms definition function", e.rec(e.p("kind", int_t(e))))

    _fn_def(
        e,
        x,
        "h_layout",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))),
        e.rec(e.p("size", int_t(e)), e.p("fields", e.list_type(t(e, "ufield")))),
    )
    fn_throws(e, "h_layout", errs_t(e))
    _fn_def(
        e,
        x,
        "h_elements",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))),
        e.list_type(cve_t(e)),
    )
    fn_throws(e, "h_elements", errs_t(e))
    _fn_def(e, x, "h_align", e.rec(e.p("v", int_t(e)), e.p("a", int_t(e))), int_t(e))
    fn_impl(
        e,
        x,
        "h_align",
        body(
            e,
            e.ret(
                e.mb.operator_mul(
                    e.mb.operator_div(
                        e.mb.operator_add(a(e, "v"), e.mb.operator_sub(a(e, "a"), e.int_of(1))),
                        a(e, "a"),
                    ),
                    a(e, "a"),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_elements",
        body(
            e,
            e.let("els", e.list_new(e.mb.types_cve())),
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "argument has no value")),
            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "tuple"))),
            e.if_only(
                e.not_(e.fld(e.v("tk"), "is_some")),
                throw_err(e, loc(e), "uniforms: fields must be a tuple of (name, type) tuples"),
            ),
            e.foreach(
                bim(
                    e,
                    asp_iface(e, "tuple"),
                    "take_elements",
                    e.fld(e.v("tk"), "value"),
                    e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, a(e, "cv")))),
                ),
                "er",
                push(e, e.v("els"), unwrap_cve_t(e, e.v("er"))),
            ),
            e.ret(e.v("els")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_layout",
        body(
            e,
            e.let("fields", e.list_new(lt(e, "ufield"))),
            e.let("cur", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(
                hf_rec(e, "h_elements", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", a(e, "cv"))),
                "pc",
                e.seq(
                    e.let("pair", hf_rec(e, "h_elements", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", e.v("pc")))),
                    count_let(e, "n2"),
                    count_loop(e, "n2", e.v("pair")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("n2"), "v"), num(e, 2))),
                        throw_err(e, loc(e), "uniforms: a field is a (name, type) tuple"),
                    ),
                    e.let("i", e.rec(e.p("v", e.int_of(0)))),
                    e.let("fname", e.rec(e.p("v", e.dstr("")))),
                    e.foreach(
                        e.v("pair"),
                        "pe",
                        e.seq(
                            e.if_only(
                                e.eq(e.fld(e.v("i"), "v"), num(e, 0)),
                                e.seq(
                                    e.if_only(
                                        e.not_(
                                            has_b(e, xx(e), cve_type(e, e.v("pe")), e.mb.eval_aspect_string_const()),
                                        ),
                                        throw_err(e, loc(e), "uniforms: field name must be a constant string"),
                                    ),
                                    e.mb.set(e.fld(e.v("fname"), "v"), _const_str(e, e.v("pe"))),
                                ),
                            ),
                            e.if_only(
                                e.eq(e.fld(e.v("i"), "v"), num(e, 1)),
                                e.seq(
                                    e.let("tk", lookup(e, xx(e), cve_type(e, e.v("pe")), asp_iface(e, "type"))),
                                    e.if_only(
                                        or_b(e, is_runtime(e, e.v("pe")), e.not_(e.fld(e.v("tk"), "is_some"))),
                                        throw_err(e, loc(e), "uniforms: field type must be a constant glsl type"),
                                    ),
                                    e.let(
                                        "fty",
                                        bim(
                                            e,
                                            asp_iface(e, "type"),
                                            "type",
                                            e.fld(e.v("tk"), "value"),
                                            cve_value(e, e.v("pe")),
                                        ),
                                    ),
                                    e.let(
                                        "d",
                                        e.call(
                                            e.lower(e.fld(e.v("glsl"), "desc")),
                                            e.rec(e.p("xx", xx(e)), e.p("ty", e.v("fty"))),
                                        ),
                                    ),
                                    e.let("n", e.fld(e.v("d"), "n")),
                                    e.let(
                                        "align",
                                        e.if_else(
                                            or_b(e, e.fld(e.v("d"), "mat"), e.mb.operator_ge(e.v("n"), num(e, 3))),
                                            e.int_of(16),
                                            e.if_else(e.eq(e.v("n"), num(e, 2)), e.int_of(8), e.int_of(4)),
                                        ),
                                    ),
                                    e.let(
                                        "size",
                                        e.if_else(
                                            e.fld(e.v("d"), "mat"),
                                            e.mb.operator_mul(e.v("n"), e.int_of(16)),
                                            e.mb.operator_mul(e.v("n"), e.int_of(4)),
                                        ),
                                    ),
                                    e.let(
                                        "offset",
                                        hf_rec(e, "h_align", e.p("v", e.fld(e.v("cur"), "v")), e.p("a", e.v("align"))),
                                    ),
                                    e.mb.set(e.fld(e.v("cur"), "v"), e.mb.operator_add(e.v("offset"), e.v("size"))),
                                    push(
                                        e,
                                        e.v("fields"),
                                        mk(
                                            e,
                                            "ufield",
                                            e.p("name", e.fld(e.v("fname"), "v")),
                                            e.p("ty", e.v("fty")),
                                            e.p("offset", e.v("offset")),
                                            e.p("kind", e.fld(e.v("d"), "kind")),
                                            e.p("n", e.v("n")),
                                            e.p("mat", e.fld(e.v("d"), "mat")),
                                        ),
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                ),
            ),
            e.ret(
                e.rec(
                    e.p("size", hf_rec(e, "h_align", e.p("v", e.fld(e.v("cur"), "v")), e.p("a", e.int_of(16)))),
                    e.p("fields", e.v("fields")),
                )
            ),
        ),
    )

    self_type(
        e,
        x,
        "ut_block",
        e.cat(e.s("std140 block "), in_(e, "name")),
        rt_dispatch(e, str_(e), e.aspect_dispatch(lv(e, "ublock_m_id"), asp_id(e, "field"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ublock_m"),
                    e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), "ublock_m", "name")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("ut_block"), t(e, "ublock_m"), e.p("name", in_(e, "name"))))
    rt_lift_impl(e, x, "ut_block")
    rt_bind_impl(e, x, "ut_block", str_(e))
    rt_use_impl(e, x, "ut_block")
    x.append(
        e.impl_interface(
            e.v("ut_block"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "uniforms: field must be a constant string")),
                    ),
                    e.let("key", _const_str(e, a(e, "key"))),
                    e.if_only(e.eq(e.v("key"), e.s("ptr")), ret_m(e, tag_value(e, a(e, "value"), e.lower_v("t_gpv")))),
                    e.if_only(e.eq(e.v("key"), e.s("size")), ret_m(e, ok_cve(e, _int_cve(e, in_(e, "size"))))),
                    e.foreach(
                        in_(e, "fields"),
                        "f",
                        e.if_only(
                            e.eq(e.call_m(e.v("f"), "name", e.tup()), e.v("key")),
                            e.seq(
                                e.if_only(
                                    and_b(
                                        e,
                                        e.eq(e.call_m(e.v("f"), "n", e.tup()), num(e, 1)),
                                        e.not_(e.call_m(e.v("f"), "mat", e.tup())),
                                    ),
                                    ret_m(
                                        e,
                                        ok_cve(
                                            e,
                                            _place(
                                                e,
                                                a(e, "value"),
                                                e.call_m(e.v("f"), "kind", e.tup()),
                                                e.call_m(e.v("f"), "offset", e.tup()),
                                            ),
                                        ),
                                    ),
                                ),
                                ret_m(
                                    e,
                                    tag_value(
                                        e,
                                        a(e, "value"),
                                        mk(
                                            e,
                                            "ut_vec",
                                            e.p("offset", e.call_m(e.v("f"), "offset", e.tup())),
                                            e.p("kind", e.call_m(e.v("f"), "kind", e.tup())),
                                            e.p("n", e.call_m(e.v("f"), "n", e.tup())),
                                            e.p("mat", e.call_m(e.v("f"), "mat", e.tup())),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.ret(
                        err_cve(
                            e,
                            loc(e),
                            e.cat(e.s("uniforms: block "), in_(e, "name"), e.s(" has no field "), e.v("key")),
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
        "ut_vec",
        e.cat(e.s("std140 "), in_(e, "kind"), e.s(" field at "), to_str(e, in_(e, "offset"))),
        rt_dispatch(e, str_(e), e.aspect_dispatch(lv(e, "uvec_m_id"), asp_id(e, "field"), asp_id(e, "set"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "uvec_m"),
                    e.eq(in_(e, "offset"), acc(e, xx(e), a(e, "other"), "uvec_m", "offset")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("ut_vec"),
            t(e, "uvec_m"),
            e.p("offset", in_(e, "offset")),
            e.p("kind", in_(e, "kind")),
            e.p("n", in_(e, "n")),
            e.p("mat", in_(e, "mat")),
        )
    )
    rt_lift_impl(e, x, "ut_vec")
    rt_bind_impl(e, x, "ut_vec", str_(e))
    rt_use_impl(e, x, "ut_vec")
    elem_offset = e.if_else(
        in_(e, "mat"),
        e.mb.operator_add(
            in_(e, "offset"),
            e.mb.operator_add(
                e.mb.operator_mul(e.mb.operator_div(e.v("idx"), in_(e, "n")), e.int_of(16)),
                e.mb.operator_mul(e.mb.operator_mod(e.v("idx"), in_(e, "n")), e.int_of(4)),
            ),
        ),
        e.mb.operator_add(in_(e, "offset"), e.mb.operator_mul(e.v("idx"), e.int_of(4))),
    )
    count = e.if_else(in_(e, "mat"), e.mb.operator_mul(in_(e, "n"), in_(e, "n")), in_(e, "n"))
    x.append(
        e.impl_interface(
            e.v("ut_vec"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(is_const(e, xx(e), cve_type(e, a(e, "key")))),
                        ret_m(e, err_cve(e, loc(e), "uniforms: component index must be a constant integer")),
                    ),
                    e.let(
                        "idx",
                        e.mb.as_(
                            e.call(
                                e.eval_builtin("const_numeric_to_double"),
                                e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "key")))),
                            ),
                            int_t(e),
                        ),
                    ),
                    e.if_only(
                        or_b(e, e.mb.operator_lt(e.v("idx"), num(e, 0)), e.mb.operator_ge(e.v("idx"), count)),
                        ret_m(e, err_cve(e, loc(e), "uniforms: component index out of range")),
                    ),
                    e.ret(ok_cve(e, _place(e, a(e, "value"), in_(e, "kind"), elem_offset))),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    x.append(
        e.impl_interface(
            e.v("ut_vec"),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.let(
                        "elems",
                        unwrap_m(
                            e,
                            try_er(
                                e,
                                hf_rec(e, "h_elements", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", a(e, "value"))),
                                e.list_type(cve_t(e)),
                            ),
                            cve_t(e),
                        ),
                    ),
                    count_let(e, "ne"),
                    count_loop(e, "ne", e.v("elems")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("ne"), "v"), count)),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("uniforms: field takes a tuple of "), to_str(e, count), e.s(" components")),
                            ),
                        ),
                    ),
                    e.let("out", e.list_new(cve_t(e))),
                    e.let("idxc", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("elems"),
                        "ec",
                        e.seq(
                            e.let("idx", e.fld(e.v("idxc"), "v")),
                            e.let("pl", _place(e, a(e, "target"), in_(e, "kind"), elem_offset)),
                            e.let("et", _elem_type(e, in_(e, "kind"))),
                            push(
                                e,
                                e.v("out"),
                                unwrap_cve_m(
                                    e,
                                    bim(
                                        e,
                                        e.mb.eval_aspect_set(),
                                        "set",
                                        lookup_v(e, xx(e), e.v("et"), e.mb.eval_aspect_set()),
                                        e.rec(
                                            e.p("xx", xx(e)),
                                            e.p("loc", loc(e)),
                                            e.p("target", e.v("pl")),
                                            e.p("value", e.v("ec")),
                                        ),
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("idxc"), "v")),
                        ),
                    ),
                    e.let("codes", e.list_new(code_t(e))),
                    e.foreach(e.v("out"), "c", push(e, e.v("codes"), cve_code(e, e.v("c")))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_no(
                                e,
                                unwrap_m(
                                    e,
                                    bim(
                                        e,
                                        e.mb.eval_target(),
                                        "seq",
                                        e.fld(xx(e), "target"),
                                        e.rec(e.p("loc", loc(e)), e.p("entries", e.v("codes"))),
                                    ),
                                    cve_t(e),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    self_type(
        e,
        x,
        "ugfn_t",
        e.cat(e.s("uniforms definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, str_(e), e.aspect_dispatch(lv(e, "ugfn_m_id"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ugfn_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "ugfn_m", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "ugfn_t")
    rt_bind_impl(e, x, "ugfn_t", str_(e))
    rt_use_impl(e, x, "ugfn_t")
    x.append(e.impl_interface(e.v("ugfn_t"), t(e, "ugfn_m"), e.p("kind", in_(e, "kind"))))
    tm.method(
        e,
        x,
        "ugfn_t",
        "call",
        e.rec(e.p("xx", e.types_expr_context()), e.p("loc", loc_t(e)), e.p("argument", cve_t(e))),
        e.mb.call(e.mb.types_eresult(), cve_t(e)),
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))),
                ret_m(e, err_cve(e, loc(e), "uniforms definition argument has no value")),
            ),
            e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "uniforms definition argument must be {mod, name, fields}")),
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
            e.let("modcv", _field(e, "mod")),
            e.let("namecv", _staged(e, graft(e, _field(e, "name")))),
            e.if_only(
                is_runtime(e, e.v("namecv")),
                ret_m(e, err_cve(e, loc(e), "uniforms block name must be constant")),
            ),
            e.let("fieldscv", _field(e, "fields")),
            e.let("block_fn", e.lower(e.fld(e.v("glsl"), "uniform_block_fn"))),
            e.let("alloc_fn", e.lower(e.fld(e.v("wasm"), "alloc_fn"))),
            e.if_only(
                e.eq(in_(e, "kind"), num(e, _ugfn_kind("glsl_fn"))),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        _staged(
                            e,
                            e.call(
                                e.lower(e.v("block_fn")),
                                e.rec(
                                    e.p("mod", graft(e, e.v("modcv"))),
                                    e.p("name", graft(e, e.v("namecv"))),
                                    e.p("layout", e.s("std140")),
                                    e.p("fields", graft(e, e.v("fieldscv"))),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            e.let(
                "layout",
                unwrap_m(
                    e,
                    try_er(
                        e,
                        hf_rec(e, "h_layout", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", e.v("fieldscv"))),
                        e.rec(e.p("size", int_t(e)), e.p("fields", e.list_type(lt(e, "ufield")))),
                    ),
                    cve_t(e),
                ),
            ),
            e.let(
                "refcv",
                _staged(
                    e,
                    e.call(
                        e.lower(e.v("alloc_fn")),
                        e.rec(
                            e.p("mod", graft(e, e.v("modcv"))),
                            e.p("name", graft(e, e.v("namecv"))),
                            e.p("size", e.lower(e.fld(e.v("layout"), "size"))),
                        ),
                    ),
                ),
            ),
            e.ret(
                tag_value(
                    e,
                    e.v("refcv"),
                    mk(
                        e,
                        "ut_block",
                        e.p("name", _const_str(e, e.v("namecv"))),
                        e.p("size", e.fld(e.v("layout"), "size")),
                        e.p("fields", e.fld(e.v("layout"), "fields")),
                    ),
                )
            ),
        ),
    )
    x.append(e.finish(e.v("d")))
    defs = []
    defs.append(e.p("ugfn_t_new", e.fld(e.v("ugfn_t"), "new")))
    x.append(e.ret(e.rec(*defs)))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.let("d", e.define()))
    exports = []
    for kind in UGFN_KINDS:
        top.append(
            e.let(kind + "_o", e.call(e.fld(e.v("k"), "ugfn_t_new"), e.rec(e.p("kind", e.int_of(_ugfn_kind(kind))))))
        )
        tm.const_fn(
            e,
            top,
            kind + "_b",
            TARGET + "." + kind,
            e.call_m(
                e.lower(e.v(kind + "_o")),
                "call",
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("argument", a(e, "argument"))),
            ),
        )
        top.append(e.let(kind, e.fld(e.v(kind + "_b"), "func")))
        exports.append(e.p(kind, e.v(kind)))
    top.append(e.finish(e.v("d")))
    top.append(e.ret(e.rec(*exports)))
    return top
