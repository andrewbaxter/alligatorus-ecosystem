"""glsl-es-3.00.atz: GLSL ES 3.00 shader target."""

from .. import target_mb as tm
from ..core import values
from ..target_mb import (
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
    must_v,
    no_cast_to,
    num,
    ok_cve,
    op,
    op_id,
    op_iface,
    or_b,
    outer,
    panic_errs,
    push,
    reinterpret,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
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
    type_can_cast_from,
    unwrap_cve_m,
    unwrap_cve_t,
    unwrap_m,
    voc_t,
    xx,
    xx_t,
)

TARGET = "glsl"

KINDS = ["float", "int", "uint", "bool"]

GGFN_KINDS = ["func_fn", "in_fn", "out_fn", "uniform_block_fn", "gl_fn"]

GL_VARS = [
    ["gl_Position", "float", "4"],
    ["gl_PointSize", "float", "1"],
    ["gl_VertexID", "int", "1"],
    ["gl_InstanceID", "int", "1"],
    ["gl_FragCoord", "float", "4"],
    ["gl_FrontFacing", "bool", "1"],
    ["gl_PointCoord", "float", "2"],
    ["gl_FragDepth", "float", "1"],
]

BUILTINS = [
    ["radians", "G G"],
    ["degrees", "G G"],
    ["sin", "G G"],
    ["cos", "G G"],
    ["tan", "G G"],
    ["asin", "G G"],
    ["acos", "G G"],
    ["atan", "G G G", "G G"],
    ["sinh", "G G"],
    ["cosh", "G G"],
    ["tanh", "G G"],
    ["asinh", "G G"],
    ["acosh", "G G"],
    ["atanh", "G G"],
    ["pow", "G G G"],
    ["exp", "G G"],
    ["log", "G G"],
    ["exp2", "G G"],
    ["log2", "G G"],
    ["sqrt", "G G"],
    ["inversesqrt", "G G"],
    ["abs", "G G", "GI GI"],
    ["sign", "G G", "GI GI"],
    ["floor", "G G"],
    ["trunc", "G G"],
    ["round", "G G"],
    ["roundEven", "G G"],
    ["ceil", "G G"],
    ["fract", "G G"],
    ["mod", "G G G", "G G F"],
    ["min", "G G G", "G G F", "GI GI GI", "GI GI I", "GU GU GU", "GU GU U"],
    ["max", "G G G", "G G F", "GI GI GI", "GI GI I", "GU GU GU", "GU GU U"],
    ["clamp", "G G G G", "G G F F", "GI GI GI GI", "GI GI I I", "GU GU GU GU", "GU GU U U"],
    ["mix", "G G G G", "G G G F", "G G G GB"],
    ["step", "G G G", "G F G"],
    ["smoothstep", "G G G G", "G F F G"],
    ["isnan", "GB G"],
    ["isinf", "GB G"],
    ["floatBitsToInt", "GI G"],
    ["floatBitsToUint", "GU G"],
    ["intBitsToFloat", "G GI"],
    ["uintBitsToFloat", "G GU"],
    ["packSnorm2x16", "U F2"],
    ["packUnorm2x16", "U F2"],
    ["packHalf2x16", "U F2"],
    ["unpackSnorm2x16", "F2 U"],
    ["unpackUnorm2x16", "F2 U"],
    ["unpackHalf2x16", "F2 U"],
    ["length", "F G"],
    ["distance", "F G G"],
    ["dot", "F G G"],
    ["cross", "F3 F3 F3"],
    ["normalize", "G G"],
    ["faceforward", "G G G G"],
    ["reflect", "G G G"],
    ["refract", "G G G F"],
    ["matrixCompMult", "M M M"],
    ["outerProduct", "M V V"],
    ["transpose", "M M"],
    ["determinant", "F M"],
    ["inverse", "M M"],
    ["lessThan", "BV V V", "BV IV IV", "BV UV UV"],
    ["lessThanEqual", "BV V V", "BV IV IV", "BV UV UV"],
    ["greaterThan", "BV V V", "BV IV IV", "BV UV UV"],
    ["greaterThanEqual", "BV V V", "BV IV IV", "BV UV UV"],
    ["equal", "BV V V", "BV IV IV", "BV UV UV", "BV BV BV"],
    ["notEqual", "BV V V", "BV IV IV", "BV UV UV", "BV BV BV"],
    ["any", "B BV"],
    ["all", "B BV"],
    ["not", "BV BV"],
    ["dFdx", "G G"],
    ["dFdy", "G G"],
    ["fwidth", "G G"],
]


def _fn_def(e, out, name, arg_type, ret):
    return tm.fn_def(e, out, TARGET, name, arg_type, ret)


def _gmod_t(e):
    return t(e, "gmod")


def _render_t(e):
    return e.rec(e.p("glsl", str_(e)))


def _desc_t(e):
    return e.rec(e.p("kind", str_(e)), e.p("n", int_t(e)), e.p("mat", bool_t(e)))


def _insts_t(e):
    return e.list_type(t(e, "ginst"))


def _insts_new(e):
    return e.list_new(lt(e, "ginst"))


def _inst(e, text):
    return mk(e, "ginst", e.p("text", text))


def _gval_new(e, ty_, expr):
    return mk(e, "gval", e.p("ty", ty_), e.p("expr", expr))


def _gv_expr(e, cve_tp):
    return e.call_m(reinterpret(e, cve_value(e, cve_tp), "gval"), "expr", e.tup())


def _append_code(e, out, code_tp):
    return hf_rec(e, "h_append", e.p("out", out), e.p("code", code_tp))


def _code_of(e, insts):
    return hf(e, "h_code", insts)


def _fresh(e, mod):
    return e.call_m(mod, "fresh", e.tup())


def _xmod(e, ret_inner=None):
    if ret_inner is None:
        ret_inner = e.mb.types_cve()
    return e.call_m(
        unwrap_m(e, e.call(e.mb.reinterpret(), e.tup(loc(e), e.fld(xx(e), "target"), lt(e, "gtarget"))), ret_inner),
        "mod",
        e.tup(),
    )


def _operand(e, xx_, loc_, ty_, cv):
    return hf_rec(e, "h_operand", e.p("xx", xx_), e.p("loc", loc_), e.p("ty", ty_), e.p("cv", cv))


def _operand_m(e, ty_, cv):
    return unwrap_cve_m(e, try_er(e, _operand(e, xx(e), loc(e), ty_, cv), cve_t(e)))


def _is_glsl(e, xx_, cv):
    return hf_rec(e, "h_is_glsl", e.p("xx", xx_), e.p("cv", cv))


def _ir_of(e, xx_, ty_):
    return hf_rec(e, "h_ir", e.p("xx", xx_), e.p("ty", ty_))


def _desc_of(e, xx_, ty_):
    return hf_rec(e, "h_desc", e.p("xx", xx_), e.p("ty", ty_))


def _type_of(e, desc):
    return hf(e, "h_type_of", desc)


def _scalar_t(e, kind):
    """`kind`: expr or plain string."""
    if isinstance(kind, str):
        kind = e.s(kind)
    return mk(e, "gt_scalar", e.p("kind", kind))


def _vec_t(e, kind, n):
    return mk(e, "gt_vec", e.p("kind", kind), e.p("n", n))


def _arith(e, op_):
    return try_er(
        e,
        hf_rec(
            e,
            "h_arith",
            e.p("xx", xx(e)),
            e.p("loc", loc(e)),
            e.p("mod", _xmod(e)),
            e.p("op", e.s(op_)),
            e.p("self", outer(e)),
            e.p("a", a(e, "base")),
            e.p("b", a(e, "reference")),
        ),
        cve_t(e),
    )


def _cmp(e, op_):
    return try_er(
        e,
        hf_rec(
            e,
            "h_cmp",
            e.p("xx", xx(e)),
            e.p("loc", loc(e)),
            e.p("mod", _xmod(e)),
            e.p("op", e.s(op_)),
            e.p("self", outer(e)),
            e.p("a", a(e, "base")),
            e.p("b", a(e, "reference")),
        ),
        cve_t(e),
    )


def _unary(e, op_):
    return try_er(
        e,
        hf_rec(
            e,
            "h_unop",
            e.p("xx", xx(e)),
            e.p("loc", loc(e)),
            e.p("mod", _xmod(e)),
            e.p("op", e.s(op_)),
            e.p("ty", outer(e)),
            e.p("a", a(e, "base")),
        ),
        cve_t(e),
    )


def _ggfn_is(e, kind):
    return e.eq(in_(e, "kind"), num(e, _ggfn_kind(kind)))


def _ggfn_kind(kind):
    return GGFN_KINDS.index(kind)


def _ggfn_staged(e, staged):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(staged)))


def _ggfn_field(e, key):
    return unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(key)))


def _ggfn_mod(e):
    return e.call_m(graft(e, e.v("modcv")), "m", e.tup())


def _global_t(e, base):
    return mk(e, "gt_global", e.p("base", base))


def _const_str(e, cv):
    return hf_rec(e, "h_const_str", e.p("xx", xx(e)), e.p("cv", cv))


def _elements(e, argv):
    return hf_rec(e, "h_elements", e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("cv", argv))


def _elements_m(e, argv):
    return unwrap_m(e, try_er(e, _elements(e, argv), e.list_type(e.mb.types_cve())), cve_t(e))


def _def_arith(e, x):
    fn_impl(
        e,
        x,
        "h_arith",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("av", _operand(e, xx(e), loc(e), a(e, "self"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("av"))),
            e.let("ad", _desc_of(e, xx(e), a(e, "self"))),
            e.if_only(e.not_(cve_has(e, a(e, "b"))), throw_err(e, loc(e), "operand has no value")),
            e.let("bt0", cve_type(e, a(e, "b"))),
            e.let(
                "bt",
                e.if_else(
                    has(e, xx(e), e.v("bt0"), "gtype"),
                    e.if_else(
                        has(e, xx(e), e.v("bt0"), "ggtype_m"),
                        acc(e, xx(e), e.v("bt0"), "ggtype_m", "base"),
                        e.v("bt0"),
                    ),
                    e.mb.as_(_scalar_t(e, e.fld(e.v("ad"), "kind")), ty(e)),
                ),
            ),
            e.let("bv", _operand(e, xx(e), loc(e), e.v("bt"), a(e, "b"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("bv"))),
            e.let("bd", _desc_of(e, xx(e), e.v("bt"))),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("ad"), "kind"), e.fld(e.v("bd"), "kind"))),
                throw_err(
                    e,
                    loc(e),
                    e.cat(
                        e.s("glsl: operands of "),
                        a(e, "op"),
                        e.s(" have different component types: "),
                        ty_desc(e, a(e, "self")),
                        e.s(" and "),
                        ty_desc(e, e.v("bt")),
                    ),
                ),
            ),
            e.let("an", e.fld(e.v("ad"), "n")),
            e.let("bn", e.fld(e.v("bd"), "n")),
            e.let("am", e.fld(e.v("ad"), "mat")),
            e.let("bm", e.fld(e.v("bd"), "mat")),
            e.let("rc", e.rec(e.p("v", e.option_type_lowered_none()))),
            e.if_only(
                or_b(
                    e,
                    is_equal(e, xx(e), a(e, "self"), e.v("bt")),
                    or_b(
                        e,
                        e.eq(e.v("bn"), num(e, 1)),
                        and_b(
                            e,
                            e.eq(a(e, "op"), e.s("*")),
                            and_b(e, e.eq(e.v("an"), e.v("bn")), and_b(e, e.v("am"), e.not_(e.v("bm")))),
                        ),
                    ),
                ),
                e.mb.set(e.fld(e.v("rc"), "v"), e.option_type_lowered_some(a(e, "self"))),
            ),
            e.if_only(
                and_b(
                    e,
                    e.not_(e.fld(e.v("rc"), "v", "is_some")),
                    or_b(
                        e,
                        e.eq(e.v("an"), num(e, 1)),
                        and_b(
                            e,
                            e.eq(a(e, "op"), e.s("*")),
                            and_b(e, e.eq(e.v("an"), e.v("bn")), and_b(e, e.v("bm"), e.not_(e.v("am")))),
                        ),
                    ),
                ),
                e.mb.set(e.fld(e.v("rc"), "v"), e.option_type_lowered_some(e.v("bt"))),
            ),
            e.if_only(
                e.not_(e.fld(e.v("rc"), "v", "is_some")),
                throw_err(
                    e,
                    loc(e),
                    e.cat(
                        e.s("glsl: cannot apply "),
                        a(e, "op"),
                        e.s(" to "),
                        ty_desc(e, a(e, "self")),
                        e.s(" and "),
                        ty_desc(e, e.v("bt")),
                    ),
                ),
            ),
            e.let("res", e.fld(e.v("rc"), "v", "value")),
            e.ret(
                hf_rec(
                    e,
                    "h_stmt",
                    e.p("mod", a(e, "mod")),
                    e.p("out", e.v("out")),
                    e.p("ty", e.v("res")),
                    e.p("expr", e.cat(_gv_expr(e, e.v("av")), e.s(" "), a(e, "op"), e.s(" "), _gv_expr(e, e.v("bv")))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_cmp",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("av", _operand(e, xx(e), loc(e), a(e, "self"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("av"))),
            e.let("bv", _operand(e, xx(e), loc(e), a(e, "self"), a(e, "b"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("bv"))),
            e.ret(
                hf_rec(
                    e,
                    "h_stmt",
                    e.p("mod", a(e, "mod")),
                    e.p("out", e.v("out")),
                    e.p("ty", e.mb.as_(_scalar_t(e, "bool"), ty(e))),
                    e.p("expr", e.cat(_gv_expr(e, e.v("av")), e.s(" "), a(e, "op"), e.s(" "), _gv_expr(e, e.v("bv")))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_unop",
        body(
            e,
            e.let("out", _insts_new(e)),
            e.let("av", _operand(e, xx(e), loc(e), a(e, "ty"), a(e, "a"))),
            _append_code(e, e.v("out"), cve_code(e, e.v("av"))),
            e.ret(
                hf_rec(
                    e,
                    "h_stmt",
                    e.p("mod", a(e, "mod")),
                    e.p("out", e.v("out")),
                    e.p("ty", a(e, "ty")),
                    e.p("expr", e.cat(a(e, "op"), _gv_expr(e, e.v("av")))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_construct",
        body(
            e,
            e.let("mod", a(e, "mod")),
            e.let("td", _desc_of(e, xx(e), a(e, "ty"))),
            e.let("elems", _elements(e, a(e, "argument"))),
            e.let("out", _insts_new(e)),
            e.let("exprs", e.list_new(str_(e))),
            e.let("st", e.rec(e.p("n", e.int_of(0)), e.p("comps", e.int_of(0)), e.p("mat", e.int_of(0)))),
            e.foreach(
                e.v("elems"),
                "ec",
                e.seq(
                    e.if_only(e.not_(cve_has(e, e.v("ec"))), throw_err(e, loc(e), "argument has no value")),
                    e.let("et0", cve_type(e, e.v("ec"))),
                    e.let(
                        "et",
                        e.if_else(
                            has(e, xx(e), e.v("et0"), "gtype"),
                            e.if_else(
                                has(e, xx(e), e.v("et0"), "ggtype_m"),
                                acc(e, xx(e), e.v("et0"), "ggtype_m", "base"),
                                e.v("et0"),
                            ),
                            e.mb.as_(_scalar_t(e, e.fld(e.v("td"), "kind")), ty(e)),
                        ),
                    ),
                    e.let("ev", _operand(e, xx(e), loc(e), e.v("et"), e.v("ec"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("ev"))),
                    push(e, e.v("exprs"), _gv_expr(e, e.v("ev"))),
                    e.let("ed", _desc_of(e, xx(e), e.v("et"))),
                    e.if_only(e.fld(e.v("ed"), "mat"), e.mb.set(e.fld(e.v("st"), "mat"), e.int_of(1))),
                    e.mb.set(
                        e.fld(e.v("st"), "comps"),
                        e.mb.operator_add(
                            e.fld(e.v("st"), "comps"),
                            hf_rec(e, "h_components", e.p("xx", xx(e)), e.p("ty", e.v("et"))),
                        ),
                    ),
                    e.incr(e.fld(e.v("st"), "n")),
                ),
            ),
            e.let("want", hf_rec(e, "h_components", e.p("xx", xx(e)), e.p("ty", a(e, "ty")))),
            e.let("n", e.fld(e.v("st"), "n")),
            e.let("comps", e.fld(e.v("st"), "comps")),
            e.let(
                "ok",
                e.if_else(
                    e.eq(e.v("n"), num(e, 1)),
                    or_b(
                        e,
                        e.eq(e.v("comps"), num(e, 1)),
                        or_b(e, e.mb.operator_ge(e.v("comps"), e.v("want")), e.eq(e.fld(e.v("st"), "mat"), num(e, 1))),
                    ),
                    and_b(e, e.eq(e.v("comps"), e.v("want")), e.eq(e.fld(e.v("st"), "mat"), num(e, 0))),
                ),
            ),
            e.if_only(
                e.not_(e.v("ok")),
                throw_err(
                    e,
                    loc(e),
                    e.cat(
                        e.s("glsl: "),
                        ty_desc(e, a(e, "ty")),
                        e.s(" constructor needs "),
                        to_str(e, e.v("want")),
                        e.s(" components but got "),
                        to_str(e, e.v("comps")),
                    ),
                ),
            ),
            e.ret(
                hf_rec(
                    e,
                    "h_stmt",
                    e.p("mod", e.v("mod")),
                    e.p("out", e.v("out")),
                    e.p("ty", a(e, "ty")),
                    e.p(
                        "expr",
                        e.cat(_ir_of(e, xx(e), a(e, "ty")), e.s("("), e.join(e.v("exprs"), ", "), e.s(")")),
                    ),
                )
            ),
        ),
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
                        "v",
                        unwrap_m(e, try_er(e, _operand(e, xx(e), loc(e), outer(e), a(e, "cv")), cve_t(e)), br_t),
                    ),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    e.let("r", _fresh(e, _xmod(e, br_t))),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.cat(
                                _ir_of(e, xx(e), outer(e)),
                                e.s(" "),
                                e.v("r"),
                                e.s(" = "),
                                _gv_expr(e, e.v("v")),
                                e.s(";"),
                            ),
                        ),
                    ),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    e.p("code", _code_of(e, e.v("out"))),
                                    e.p("binding", mk(e, "gbinding", e.p("ty", outer(e)), e.p("name", e.v("r")))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def _set_impl(e, x, obj):
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.let("t", _operand_m(e, outer(e), a(e, "self"))),
                    e.let("v", _operand_m(e, outer(e), a(e, "value"))),
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), cve_code(e, e.v("t"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                    push(
                        e,
                        e.v("out"),
                        _inst(e, e.cat(_gv_expr(e, e.v("t")), e.s(" = "), _gv_expr(e, e.v("v")), e.s(";"))),
                    ),
                    e.ret(ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                ),
            ),
        )
    )


def _construct_impl(e, x, obj):
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.ret(
                        try_er(
                            e,
                            hf_rec(
                                e,
                                "h_construct",
                                e.p("xx", xx(e)),
                                e.p("loc", loc(e)),
                                e.p("mod", _xmod(e)),
                                e.p("ty", outer(e)),
                                e.p("argument", a(e, "argument")),
                            ),
                            cve_t(e),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )


def _vec_ir(e, kind, n):
    return e.cat(
        e.if_else(
            e.eq(kind, e.s("float")),
            e.dstr(""),
            e.if_else(
                e.eq(kind, e.s("int")),
                e.dstr("i"),
                e.if_else(e.eq(kind, e.s("uint")), e.dstr("u"), e.dstr("b")),
            ),
        ),
        e.s("vec"),
        to_str(e, n),
    )


def _def_types(e, x):
    num_ops = [["add", "+"], ["sub", "-"], ["mul", "*"], ["div", "/"]]
    int_ops = [["mod", "%"], ["and", "&"], ["or", "|"], ["xor", "^"], ["shl", "<<"], ["shr", ">>"]]
    cmp_ops = [["lt", "<"], ["le", "<="], ["gt", ">"], ["ge", ">="]]
    eq_ops = [["eq", "=="], ["ne", "!="]]
    bool_ops = [["and", "&&"], ["or", "||"]]

    ids = []
    ids.append(lv(e, "gtype_id"))
    ids.append(lv(e, "gscalar_id"))
    for op_ in num_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in int_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in cmp_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in eq_ops:
        ids.append(op_id(e, op_[0]))
    ids.append(op_id(e, "neg"))
    ids.append(op_id(e, "bit_not"))
    ids.append(asp_id(e, "bind"))
    ids.append(asp_id(e, "set"))
    ids.append(asp_id(e, "function"))
    self_type(
        e,
        x,
        "gt_scalar",
        in_(e, "kind"),
        e.aspect_dispatch(*ids),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), src_type(e)),
                    e.if_else(
                        e.eq(in_(e, "kind"), e.s("bool")),
                        has_b(e, xx(e), src_type(e), e.eval_builtin("aspect_bool_const")),
                        is_const(e, xx(e), src_type(e)),
                    ),
                )
            ),
        ),
        body(
            e,
            e.let("st", cve_type(e, a(e, "cv"))),
            e.if_only(is_equal(e, xx(e), outer(e), e.v("st")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.seq(
                e.if_only(
                    e.eq(in_(e, "kind"), e.s("bool")),
                    e.seq(
                        e.if_only(
                            e.not_(has_b(e, xx(e), e.v("st"), e.eval_builtin("aspect_bool_const"))),
                            ret_m(e, err_cve(e, loc(e), "glsl: expected a boolean")),
                        ),
                        ret_m(
                            e,
                            ok_cve(
                                e,
                                cv_of(
                                    e,
                                    cve_code(e, a(e, "cv")),
                                    _gval_new(
                                        e,
                                        outer(e),
                                        e.if_else(
                                            bim(
                                                e,
                                                e.eval_builtin("aspect_bool_const"),
                                                "get",
                                                lookup_v(e, xx(e), e.v("st"), e.eval_builtin("aspect_bool_const")),
                                                cve_value(e, a(e, "cv")),
                                            ),
                                            e.dstr("true"),
                                            e.dstr("false"),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                e.if_only(
                    e.not_(is_const(e, xx(e), e.v("st"))),
                    ret_m(
                        e,
                        err_cve(
                            e,
                            loc(e),
                            e.cat(
                                e.s("glsl: "),
                                ty_desc(e, e.v("st")),
                                e.s(" cannot convert to "),
                                ty_desc(e, outer(e)),
                            ),
                        ),
                    ),
                ),
                e.let(
                    "d",
                    e.call(
                        e.eval_builtin("const_numeric_to_double"),
                        e.rec(e.p("xx", xx(e)), e.p("value", cve_value(e, a(e, "cv")))),
                    ),
                ),
                e.if_only(
                    e.eq(in_(e, "kind"), e.s("float")),
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(e, cve_code(e, a(e, "cv")), _gval_new(e, outer(e), hf(e, "h_float_lit", e.v("d")))),
                        ),
                    ),
                ),
                e.let("l", e.mb.as_(e.v("d"), e.mb.types_long())),
                e.if_only(
                    e.not_(e.eq(e.mb.as_(e.v("l"), e.types_double()), e.v("d"))),
                    ret_m(e, err_cve(e, loc(e), "glsl: integer literal is not integral")),
                ),
                e.if_only(
                    and_b(e, e.eq(in_(e, "kind"), e.s("uint")), e.mb.operator_lt(e.v("d"), num(e, 0))),
                    ret_m(e, err_cve(e, loc(e), "glsl: uint literal is negative")),
                ),
                ret_m(
                    e,
                    ok_cve(
                        e,
                        cv_of(
                            e,
                            cve_code(e, a(e, "cv")),
                            _gval_new(
                                e,
                                outer(e),
                                e.cat(
                                    to_str(e, e.v("l")),
                                    e.if_else(e.eq(in_(e, "kind"), e.s("uint")), e.dstr("u"), e.dstr("")),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "gscalar"),
                    e.eq(acc(e, xx(e), a(e, "other"), "gscalar", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("gt_scalar"), t(e, "gtype"), e.p("ir", in_(e, "kind"))))
    x.append(e.impl_interface(e.v("gt_scalar"), t(e, "gscalar"), e.p("kind", in_(e, "kind"))))
    for op_ in num_ops:
        op(
            e,
            x,
            "gt_scalar",
            op_[0],
            e.if_else(
                e.eq(in_(e, "kind"), e.s("bool")), err_cve(e, loc(e), "glsl: arithmetic on bool"), _arith(e, op_[1])
            ),
        )
    for op_ in int_ops:
        text = op_[1]
        on_bool = err_cve(e, loc(e), "glsl: " + text + " on bool")
        for bop in bool_ops:
            if bop[0] == op_[0]:
                on_bool = _arith(e, bop[1])
        op(
            e,
            x,
            "gt_scalar",
            op_[0],
            e.if_else(
                e.eq(in_(e, "kind"), e.s("bool")),
                on_bool,
                e.if_else(
                    e.eq(in_(e, "kind"), e.s("float")),
                    err_cve(e, loc(e), "glsl: " + text + " on float"),
                    _arith(e, text),
                ),
            ),
        )
    for op_ in cmp_ops:
        op(
            e,
            x,
            "gt_scalar",
            op_[0],
            e.if_else(
                e.eq(in_(e, "kind"), e.s("bool")),
                err_cve(e, loc(e), "glsl: ordering comparison on bool"),
                _cmp(e, op_[1]),
            ),
        )
    for op_ in eq_ops:
        op(e, x, "gt_scalar", op_[0], _cmp(e, op_[1]))
    op(
        e,
        x,
        "gt_scalar",
        "neg",
        e.if_else(e.eq(in_(e, "kind"), e.s("bool")), err_cve(e, loc(e), "glsl: negating a bool"), _unary(e, "-")),
    )
    op(
        e,
        x,
        "gt_scalar",
        "bit_not",
        e.if_else(
            e.eq(in_(e, "kind"), e.s("bool")),
            _unary(e, "!"),
            e.if_else(
                e.eq(in_(e, "kind"), e.s("float")), err_cve(e, loc(e), "glsl: bitwise not on float"), _unary(e, "~")
            ),
        ),
    )
    _bind_impl(e, x, "gt_scalar")
    _set_impl(e, x, "gt_scalar")
    _construct_impl(e, x, "gt_scalar")

    ids = []
    ids.append(lv(e, "gtype_id"))
    ids.append(lv(e, "gvec_id"))
    for op_ in num_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in int_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in eq_ops:
        ids.append(op_id(e, op_[0]))
    ids.append(op_id(e, "neg"))
    ids.append(op_id(e, "bit_not"))
    ids.append(asp_id(e, "bind"))
    ids.append(asp_id(e, "set"))
    ids.append(asp_id(e, "function"))
    ids.append(asp_id(e, "field"))
    self_type(
        e,
        x,
        "gt_vec",
        _vec_ir(e, in_(e, "kind"), in_(e, "n")),
        e.aspect_dispatch(*ids),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "gvec"),
                    and_b(
                        e,
                        e.eq(acc(e, xx(e), a(e, "other"), "gvec", "kind"), in_(e, "kind")),
                        e.eq(acc(e, xx(e), a(e, "other"), "gvec", "n"), in_(e, "n")),
                    ),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("gt_vec"), t(e, "gtype"), e.p("ir", _vec_ir(e, in_(e, "kind"), in_(e, "n")))))
    x.append(e.impl_interface(e.v("gt_vec"), t(e, "gvec"), e.p("kind", in_(e, "kind")), e.p("n", in_(e, "n"))))
    for op_ in num_ops:
        op(
            e,
            x,
            "gt_vec",
            op_[0],
            e.if_else(
                e.eq(in_(e, "kind"), e.s("bool")), err_cve(e, loc(e), "glsl: arithmetic on bvec"), _arith(e, op_[1])
            ),
        )
    for op_ in int_ops:
        op(
            e,
            x,
            "gt_vec",
            op_[0],
            e.if_else(
                or_b(e, e.eq(in_(e, "kind"), e.s("bool")), e.eq(in_(e, "kind"), e.s("float"))),
                err_cve(e, loc(e), "glsl: " + op_[1] + " on a non-integer vector"),
                _arith(e, op_[1]),
            ),
        )
    for op_ in eq_ops:
        op(e, x, "gt_vec", op_[0], _cmp(e, op_[1]))
    op(
        e,
        x,
        "gt_vec",
        "neg",
        e.if_else(e.eq(in_(e, "kind"), e.s("bool")), err_cve(e, loc(e), "glsl: negating a bvec"), _unary(e, "-")),
    )
    op(
        e,
        x,
        "gt_vec",
        "bit_not",
        e.if_else(
            e.eq(in_(e, "kind"), e.s("bool")),
            err_cve(e, loc(e), "glsl: use not() on a bvec"),
            e.if_else(
                e.eq(in_(e, "kind"), e.s("float")),
                err_cve(e, loc(e), "glsl: bitwise not on a float vector"),
                _unary(e, "~"),
            ),
        ),
    )
    _bind_impl(e, x, "gt_vec")
    _set_impl(e, x, "gt_vec")
    _construct_impl(e, x, "gt_vec")
    x.append(
        e.impl_interface(
            e.v("gt_vec"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.let("s", _operand_m(e, outer(e), a(e, "self"))),
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "glsl: swizzle must be a constant string")),
                    ),
                    e.let("sw", _const_str(e, a(e, "key"))),
                    e.let("sets", e.list_new(str_(e), e.s("xyzw"), e.s("rgba"), e.s("stpq"))),
                    e.let("st", e.rec(e.p("len", e.int_of(0)), e.p("bad", e.int_of(0)))),
                    e.foreach(
                        e.call(e.mb.eval_str_utf8(), e.v("sw")),
                        "b",
                        e.seq(
                            e.incr(e.fld(e.v("st"), "len")),
                            e.let("hit", e.rec(e.p("v", e.int_of(0)))),
                            e.foreach(
                                e.v("sets"),
                                "set",
                                e.seq(
                                    e.let("i", e.rec(e.p("v", e.int_of(0)))),
                                    e.foreach(
                                        e.call(e.mb.eval_str_utf8(), e.v("set")),
                                        "c",
                                        e.seq(
                                            e.if_only(
                                                and_b(
                                                    e,
                                                    e.eq(e.v("c"), e.v("b")),
                                                    e.mb.operator_lt(e.fld(e.v("i"), "v"), in_(e, "n")),
                                                ),
                                                e.mb.set(e.fld(e.v("hit"), "v"), num(e, 1)),
                                            ),
                                            e.incr(e.fld(e.v("i"), "v")),
                                        ),
                                    ),
                                ),
                            ),
                            e.if_only(
                                e.eq(e.fld(e.v("hit"), "v"), num(e, 0)), e.mb.set(e.fld(e.v("st"), "bad"), e.int_of(1))
                            ),
                        ),
                    ),
                    e.if_only(
                        or_b(
                            e,
                            e.eq(e.fld(e.v("st"), "bad"), num(e, 1)),
                            or_b(
                                e,
                                e.eq(e.fld(e.v("st"), "len"), num(e, 0)),
                                e.mb.operator_gt(e.fld(e.v("st"), "len"), num(e, 4)),
                            ),
                        ),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("glsl: invalid swizzle ."), e.v("sw"), e.s(" on "), ty_desc(e, outer(e))),
                            ),
                        ),
                    ),
                    e.let(
                        "rty",
                        e.if_else(
                            e.eq(e.fld(e.v("st"), "len"), num(e, 1)),
                            e.mb.as_(_scalar_t(e, in_(e, "kind")), ty(e)),
                            e.mb.as_(_vec_t(e, in_(e, "kind"), e.fld(e.v("st"), "len")), ty(e)),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, e.v("s")),
                                _gval_new(e, e.v("rty"), e.cat(_gv_expr(e, e.v("s")), e.s("."), e.v("sw"))),
                            ),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )

    ids = []
    ids.append(lv(e, "gtype_id"))
    ids.append(lv(e, "gmat_id"))
    for op_ in num_ops:
        ids.append(op_id(e, op_[0]))
    for op_ in eq_ops:
        ids.append(op_id(e, op_[0]))
    ids.append(op_id(e, "neg"))
    ids.append(asp_id(e, "bind"))
    ids.append(asp_id(e, "set"))
    ids.append(asp_id(e, "function"))
    self_type(
        e,
        x,
        "gt_mat",
        e.cat(e.s("mat"), to_str(e, in_(e, "n"))),
        e.aspect_dispatch(*ids),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "gmat"),
                    e.eq(acc(e, xx(e), a(e, "other"), "gmat", "n"), in_(e, "n")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("gt_mat"), t(e, "gtype"), e.p("ir", e.cat(e.s("mat"), to_str(e, in_(e, "n"))))))
    x.append(e.impl_interface(e.v("gt_mat"), t(e, "gmat"), e.p("n", in_(e, "n"))))
    for op_ in num_ops:
        op(e, x, "gt_mat", op_[0], _arith(e, op_[1]))
    for op_ in eq_ops:
        op(e, x, "gt_mat", op_[0], _cmp(e, op_[1]))
    op(e, x, "gt_mat", "neg", _unary(e, "-"))
    _bind_impl(e, x, "gt_mat")
    _set_impl(e, x, "gt_mat")
    _construct_impl(e, x, "gt_mat")

    self_type(
        e,
        x,
        "gt_void",
        e.s("void"),
        e.aspect_dispatch(lv(e, "gtype_id"), lv(e, "gvoid_id")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "gvoid"))),
    )
    x.append(e.impl_interface(e.v("gt_void"), t(e, "gtype"), e.p("ir", e.s("void"))))
    x.append(e.impl_interface(e.v("gt_void"), t(e, "gvoid")))


def _def_refs(e, x):
    self_type(
        e,
        x,
        "gt_fn",
        e.s("fn"),
        e.aspect_dispatch(lv(e, "gtype_id"), lv(e, "gfn_id"), asp_id(e, "function")),
        body(e, e.ret(is_equal(e, xx(e), outer(e), src_type(e)))),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.if_only(e.not_(has(e, xx(e), a(e, "other"), "gfn")), ret_m(e, dfalse(e))),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "ret"), im0(e, "gfn", "ret", asp(e, xx(e), a(e, "other"), "gfn")))),
                ret_m(e, dfalse(e)),
            ),
            e.let("om", e.map_new(str_(e), ty(e))),
            count_let(e, "on"),
            e.foreach(
                im0(e, "gfn", "params", asp(e, xx(e), a(e, "other"), "gfn")),
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
                                    e,
                                    xx(e),
                                    e.v("p"),
                                    e.call_m(e.v("om"), "get", to_str(e, e.fld(e.v("st"), "i"))),
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
        e.impl_interface(e.v("gt_fn"), t(e, "gtype"), e.p("ir", e.mb.panic(e.s("glsl: function type has no name")))),
    )
    x.append(e.impl_interface(e.v("gt_fn"), t(e, "gfn"), e.p("params", in_(e, "params")), e.p("ret", in_(e, "ret"))))
    x.append(
        e.impl_interface(
            e.v("gt_fn"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    e.let("f", _operand_m(e, outer(e), a(e, "self"))),
                    _append_code(e, e.v("out"), cve_code(e, e.v("f"))),
                    e.let("elems", _elements_m(e, a(e, "argument"))),
                    count_let(e, "ne"),
                    count_loop(e, "ne", e.v("elems")),
                    count_let(e, "np"),
                    count_loop(e, "np", in_(e, "params")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("ne"), "v"), e.fld(e.v("np"), "v"))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("glsl: call has "),
                                    to_str(e, e.fld(e.v("ne"), "v")),
                                    e.s(" arguments but the function takes "),
                                    to_str(e, e.fld(e.v("np"), "v")),
                                ),
                            ),
                        ),
                    ),
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
                    e.let("exprs", e.list_new(str_(e))),
                    e.let("i", e.rec(e.p("v", e.int_of(0)))),
                    e.foreach(
                        e.v("elems"),
                        "ec",
                        e.seq(
                            e.let(
                                "v",
                                _operand_m(e, e.call_m(e.v("pmap"), "get", to_str(e, e.fld(e.v("i"), "v"))), e.v("ec")),
                            ),
                            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
                            push(e, e.v("exprs"), _gv_expr(e, e.v("v"))),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                    e.let("call", e.cat(_gv_expr(e, e.v("f")), e.s("("), e.join(e.v("exprs"), ", "), e.s(")"))),
                    e.if_only(
                        has(e, xx(e), in_(e, "ret"), "gvoid"),
                        e.seq(
                            push(e, e.v("out"), _inst(e, e.cat(e.v("call"), e.s(";")))),
                            ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out"))))),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            hf_rec(
                                e,
                                "h_stmt",
                                e.p("mod", _xmod(e)),
                                e.p("out", e.v("out")),
                                e.p("ty", in_(e, "ret")),
                                e.p("expr", e.v("call")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )

    bin_ops = ["add", "sub", "mul", "div", "mod", "and", "or", "xor", "shl", "shr", "eq", "ne", "lt", "le", "gt", "ge"]
    un_ops = ["neg", "bit_not"]
    ids = []
    ids.append(lv(e, "ggtype_m_id"))
    ids.append(asp_id(e, "function"))
    ids.append(asp_id(e, "field"))
    ids.append(asp_id(e, "set"))
    for op_ in bin_ops:
        ids.append(op_id(e, op_))
    for op_ in un_ops:
        ids.append(op_id(e, op_))
    self_type(
        e,
        x,
        "gt_global",
        e.cat(e.s("global("), ty_desc(e, in_(e, "base")), e.s(")")),
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
                    hf_rec(e, "h_gval", e.p("cv", a(e, "cv")), e.p("base", in_(e, "base"))),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ggtype_m"),
                    is_equal(e, xx(e), in_(e, "base"), acc(e, xx(e), a(e, "other"), "ggtype_m", "base")),
                )
            ),
        ),
    )
    x.append(e.impl_interface(e.v("gt_global"), t(e, "ggtype_m"), e.p("base", in_(e, "base"))))
    rt_lift_impl(e, x, "gt_global")
    rt_bind_impl(e, x, "gt_global", e.mb.types_string())
    rt_use_impl(e, x, "gt_global")
    self_arg = hf_rec(e, "h_gval", e.p("cv", a(e, "self")), e.p("base", in_(e, "base")))
    base_arg = hf_rec(e, "h_gval", e.p("cv", a(e, "base")), e.p("base", in_(e, "base")))
    for op_ in bin_ops:
        x.append(
            e.impl_interface(
                e.v("gt_global"),
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
                                    e.p("base", base_arg),
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
                e.v("gt_global"),
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
                                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("base", base_arg)),
                            )
                        ),
                    ),
                ),
            )
        )
    x.append(
        e.impl_interface(
            e.v("gt_global"),
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
                                e.p("self", self_arg),
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
            e.v("gt_global"),
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
                            e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("self", self_arg), e.p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )
    x.append(
        e.impl_interface(
            e.v("gt_global"),
            e.mb.eval_aspect_set(),
            e.p(
                "set",
                body(
                    e,
                    e.ret(
                        bim(
                            e,
                            e.mb.eval_aspect_set(),
                            "set",
                            lookup_v(e, xx(e), in_(e, "base"), e.mb.eval_aspect_set()),
                            e.rec(
                                e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("self", self_arg), e.p("value", a(e, "value"))
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
        "gt_block",
        e.cat(e.s("uniform block "), in_(e, "name")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(lv(e, "gblock_m_id"), asp_id(e, "field"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "gblock_m"),
                    e.eq(in_(e, "name"), acc(e, xx(e), a(e, "other"), "gblock_m", "name")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("gt_block"),
            t(e, "gblock_m"),
            e.p("fields", in_(e, "fields")),
            e.p("name", in_(e, "name")),
        )
    )
    rt_lift_impl(e, x, "gt_block")
    rt_bind_impl(e, x, "gt_block", e.mb.types_string())
    rt_use_impl(e, x, "gt_block")
    x.append(
        e.impl_interface(
            e.v("gt_block"),
            asp_iface(e, "field"),
            e.p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "glsl: block field must be a constant string")),
                    ),
                    e.let("key", _const_str(e, a(e, "key"))),
                    e.let(
                        "inst",
                        e.call(
                            e.mb.must_reinterpret(),
                            e.tup(
                                e.fld(
                                    e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, a(e, "self")), voc_t(e))),
                                    "data",
                                ),
                                str_(e),
                            ),
                        ),
                    ),
                    e.foreach(
                        in_(e, "fields"),
                        "f",
                        e.if_only(
                            e.eq(e.call_m(e.v("f"), "name", e.tup()), e.v("key")),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        cve_code(e, a(e, "self")),
                                        _gval_new(
                                            e,
                                            e.call_m(e.v("f"), "ty", e.tup()),
                                            e.cat(
                                                e.v("inst"),
                                                e.s("."),
                                                e.v("key"),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.ret(
                        err_cve(
                            e, loc(e), e.cat(e.s("glsl: block "), in_(e, "name"), e.s(" has no field "), e.v("key"))
                        )
                    ),
                ),
            ),
            e.p("type_opt", e.option_type_lowered_none()),
            e.p("keys", e.list_new(e.mb.types_constkey())),
        )
    )


def _def_module(e, x):
    method(e, x, "gmod", "xx", e.tup(), e.types_expr_context(), in_(e, "xx", "value"))
    x.append(
        e.method_impl(
            e.v("gmod"),
            "set_xx",
            e.types_expr_context(),
            e.option_type_none(),
            e.stage(e.mb.set(in_(e, "xx"), e.opt_some(e.types_expr_context(), e.v("arg")))),
        )
    )
    method(
        e,
        x,
        "gmod",
        "fresh",
        e.tup(),
        str_(e),
        e.seq(e.let("n", in_(e, "n")), e.incr(in_(e, "n")), e.ret(e.cat(e.s("t"), to_str(e, e.v("n"))))),
    )
    x.append(
        e.method_impl(
            e.v("gmod"),
            "decl",
            str_(e),
            e.option_type_none(),
            e.stage(push(e, in_(e, "decls"), e.v("arg"))),
        ),
    )
    method(
        e,
        x,
        "gmod",
        "declare",
        e.rec(e.p("text", str_(e)), e.p("name", str_(e))),
        str_(e),
        e.seq(push(e, in_(e, "decls"), a(e, "text")), e.ret(a(e, "name"))),
    )
    method(
        e,
        x,
        "gmod",
        "block",
        e.rec(e.p("name", str_(e)), e.p("layout", str_(e)), e.p("fields", e.list_type(t(e, "gfield")))),
        str_(e),
        e.seq(
            e.let("all", e.list_new(str_(e))),
            push(
                e,
                e.v("all"),
                e.cat(e.s("layout("), a(e, "layout"), e.s(") uniform "), a(e, "name"), e.s("_block {")),
            ),
            e.foreach(
                a(e, "fields"),
                "f",
                push(
                    e,
                    e.v("all"),
                    e.cat(
                        e.s("  "),
                        _ir_of(e, in_(e, "xx", "value"), e.call_m(e.v("f"), "ty", e.tup())),
                        e.s(" "),
                        e.call_m(e.v("f"), "name", e.tup()),
                        e.s(";"),
                    ),
                ),
            ),
            push(e, e.v("all"), e.cat(e.s("} "), a(e, "name"), e.s(";"))),
            push(e, in_(e, "decls"), e.join(e.v("all"), "\n")),
            e.ret(a(e, "name")),
        ),
    )
    method(
        e,
        x,
        "gmod",
        "func",
        e.rec(
            e.p("name", str_(e)),
            e.p("params", e.list_type(str_(e))),
            e.p("ty", ty(e)),
            e.p("body", e.mb.types_expr()),
        ),
        str_(e),
        body(
            e,
            e.let("loc", e.call(e.eval_builtin("expr_loc"), a(e, "body"))),
            e.let("ptypes", acc(e, in_(e, "xx", "value"), a(e, "ty"), "gfn", "params")),
            e.let("fret", acc(e, in_(e, "xx", "value"), a(e, "ty"), "gfn", "ret")),
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
            e.let("entries", e.map_new(e.mb.types_constkey(), e.mb.eval_binding())),
            e.let("pi", e.rec(e.p("i", e.int_of(0)))),
            e.let("sig", e.list_new(str_(e))),
            e.foreach(
                e.v("ptypes"),
                "pty",
                e.seq(
                    e.let("an", e.cat(e.s("a"), to_str(e, e.fld(e.v("pi"), "i")))),
                    push(e, e.v("sig"), e.cat(_ir_of(e, in_(e, "xx", "value"), e.v("pty")), e.s(" "), e.v("an"))),
                    e.call_m(
                        e.v("entries"),
                        "put",
                        e.tup(
                            e.call_m(e.v("pnames"), "get", to_str(e, e.fld(e.v("pi"), "i"))),
                            mk(e, "gbinding", e.p("ty", e.v("pty")), e.p("name", e.v("an"))),
                        ),
                    ),
                    e.incr(e.fld(e.v("pi"), "i")),
                ),
            ),
            e.let("is_void", has(e, in_(e, "xx", "value"), e.v("fret"), "gvoid")),
            e.let("vx", e.call(e.eval_builtin("eval_context"), e.tup())),
            e.let("sc", e.call(e.eval_builtin("scope"), e.rec(e.p("vx", e.v("vx")), e.p("entries", e.v("entries"))))),
            e.let("tgt", mk(e, "gtarget", e.p("mod", outer(e)))),
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
                must_v(
                    e,
                    TARGET,
                    e.call(e.mb.eval_const_eval(), e.rec(e.p("xx", e.v("ctx")), e.p("staged", a(e, "body")))),
                    "compile failed",
                ),
            ),
            e.let("ended", cve_ended(e, e.v("r"))),
            e.let("out", _insts_new(e)),
            e.if_only(
                and_b(e, e.not_(e.v("ended")), and_b(e, e.v("is_void"), _is_glsl(e, e.v("ctx"), e.v("r")))),
                e.match_of(
                    e.eresult_err(e.mb.eval_value(), e.v("loc"), e.s("void function body yields a value")),
                    "__x",
                    None,
                    e.p("ok", e.mb.panic(e.s("unreachable"))),
                    e.p("errs", panic_errs(e, TARGET, "compile failed", e.v("__x"))),
                ),
            ),
            e.let("need_cast", and_b(e, e.not_(e.v("ended")), e.not_(e.v("is_void")))),
            e.let(
                "v",
                must_v(
                    e,
                    TARGET,
                    e.if_else(
                        e.v("need_cast"),
                        try_er(e, _operand(e, e.v("ctx"), e.v("loc"), e.v("fret"), e.v("r")), cve_t(e)),
                        ok_cve(e, e.v("r")),
                    ),
                    "compile failed",
                ),
            ),
            _append_code(e, e.v("out"), cve_code(e, e.v("v"))),
            e.if_only(
                e.v("need_cast"), push(e, e.v("out"), _inst(e, e.cat(e.s("return "), _gv_expr(e, e.v("v")), e.s(";"))))
            ),
            e.let("all", e.list_new(str_(e))),
            push(
                e,
                e.v("all"),
                e.cat(
                    _ir_of(e, in_(e, "xx", "value"), e.v("fret")),
                    e.s(" "),
                    a(e, "name"),
                    e.s("("),
                    e.join(e.v("sig"), ", "),
                    e.s(") {"),
                ),
            ),
            e.foreach(e.v("out"), "i0", push(e, e.v("all"), e.cat(e.s("  "), e.call_m(e.v("i0"), "text", e.tup())))),
            push(e, e.v("all"), e.s("}")),
            push(e, in_(e, "funcs"), e.join(e.v("all"), "\n")),
            e.ret(a(e, "name")),
        ),
    )
    method(
        e,
        x,
        "gmod",
        "render",
        e.tup(),
        _render_t(e),
        e.seq(
            e.let("all", e.list_new(str_(e))),
            push(e, e.v("all"), e.s("#version 300 es")),
            push(e, e.v("all"), e.s("precision highp float;")),
            e.foreach(in_(e, "decls"), "d", push(e, e.v("all"), e.v("d"))),
            e.foreach(in_(e, "funcs"), "f", push(e, e.v("all"), e.v("f"))),
            e.ret(e.rec(e.p("glsl", e.cat(e.join(e.v("all"), "\n"), e.s("\n"))))),
        ),
    )


def _if_branch_stmts(e, cv_var):
    valued = and_b(e, cve_has(e, e.v(cv_var)), _is_glsl(e, xx(e), e.v(cv_var)))
    return e.seq(
        e.if_only(
            and_b(e, cve_has(e, e.v(cv_var)), e.not_(_is_glsl(e, xx(e), e.v(cv_var)))),
            ret_m(e, err_cve(e, loc(e), "if branches must yield glsl values")),
        ),
        e.if_only(e.not_(valued), _append_code(e, e.v("bo"), cve_code(e, e.v(cv_var)))),
        e.if_only(
            valued,
            e.seq(
                e.if_only(
                    e.eq(e.fld(e.v("st"), "has"), num(e, 0)),
                    e.seq(
                        e.mb.set(e.fld(e.v("st"), "ty"), e.option_type_lowered_some(cve_type(e, e.v(cv_var)))),
                        e.mb.set(e.fld(e.v("st"), "has"), num(e, 1)),
                    ),
                ),
                e.let("bv", _operand_m(e, e.fld(e.v("st"), "ty", "value"), e.v(cv_var))),
                _append_code(e, e.v("bo"), cve_code(e, e.v("bv"))),
                push(
                    e,
                    e.v("bo"),
                    _inst(e, e.cat(e.fld(e.v("st"), "res"), e.s(" = "), _gv_expr(e, e.v("bv")), e.s(";"))),
                ),
            ),
        ),
        e.if_only(
            and_b(e, e.not_(valued), e.not_(cve_ended(e, e.v(cv_var)))),
            e.mb.set(
                e.fld(e.v("st"), "novalue"),
                num(e, 1),
            ),
        ),
        e.if_only(e.not_(cve_ended(e, e.v(cv_var))), e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0))),
    )


def _indent(e, depth):
    return e.seq(
        e.let("__pre", e.rec(e.p("v", e.dstr("")))),
        e.let("__k", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(
            a(e, "conditions"),
            "_",
            e.seq(
                e.if_only(
                    e.mb.operator_lt(e.fld(e.v("__k"), "v"), depth),
                    e.mb.set(e.fld(e.v("__pre"), "v"), e.cat(e.fld(e.v("__pre"), "v"), e.s("  "))),
                ),
                e.incr(e.fld(e.v("__k"), "v")),
            ),
        ),
        e.ret(e.fld(e.v("__pre"), "v")),
    )


def _push_indented(e, insts, pre, extra):
    return e.foreach(
        insts, "i0", push(e, e.v("out"), _inst(e, e.cat(pre, e.s(extra), e.call_m(e.v("i0"), "text", e.tup()))))
    )


def _def_target(e, x):
    x.append(
        e.impl_interface(
            e.v("gtarget"),
            e.mb.eval_target(),
            e.p("cast_exception", e.mb.panic(e.s("glsl target: exceptions are not supported"))),
            e.p(
                "initial_bind",
                e.eresult_err(
                    e.mb.eval_binding(),
                    loc(e),
                    e.s("glsl target: match and catch payloads are not supported"),
                ),
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
            e.p("jump", e.eresult_err(code_t(e), loc(e), e.s("glsl target: jumps are not supported"))),
            e.p("land", e.eresult_ok(cve_t(e), cv_no(e, code_none(e, loc(e))))),
            e.p("value_is_runtime", e.mb.bool(False)),
            structural_exits(e)[0],
            structural_exits(e)[1],
            e.p("exit", e.eresult_err(code_t(e), loc(e), e.s("glsl target: labeled exits are not supported"))),
            e.p("guarded", e.mb.panic(e.s("glsl target: exceptions are not supported"))),
            e.p("exc_cleanup", e.mb.panic(e.s("glsl target: exceptions are not supported"))),
            e.p("exit_trampoline", e.mb.panic(e.s("glsl target: cleanup blocks are not supported"))),
            e.p("drop", target_drop_body(e)),
            e.p(
                "return",
                body(
                    e,
                    e.let("out", _insts_new(e)),
                    _append_code(e, e.v("out"), a(e, "cv", "code")),
                    push(
                        e,
                        e.v("out"),
                        _inst(
                            e,
                            e.if_else(
                                _is_glsl(e, xx(e), a(e, "cv")),
                                e.cat(e.s("return "), _gv_expr(e, a(e, "cv")), e.s(";")),
                                e.dstr("return;"),
                            ),
                        ),
                    ),
                    e.ret(e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out")))),
                ),
            ),
            e.p("stage", err_cve(e, loc(e), "glsl target: nested staging is not supported")),
            e.p(
                "if",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("out", _insts_new(e)),
                    e.let(
                        "st",
                        e.rec(
                            e.p("ended", e.int_of(1)),
                            e.p("has", e.int_of(0)),
                            e.p("novalue", e.int_of(0)),
                            e.p("ty", e.option_type_lowered_none()),
                            e.p("res", _fresh(e, e.v("mod"))),
                        ),
                    ),
                    count_let(e, "nc"),
                    count_loop(e, "nc", a(e, "conditions")),
                    e.let("ci", e.rec(e.p("v", e.int_of(0)))),
                    e.let("boolt", e.mb.as_(_scalar_t(e, "bool"), ty(e))),
                    e.foreach(
                        a(e, "conditions"),
                        "br",
                        e.seq(
                            e.let("c", _operand_m(e, e.v("boolt"), e.fld(e.v("br"), "condition"))),
                            e.let("pre", _indent(e, e.fld(e.v("ci"), "v"))),
                            e.let("cl", _insts_new(e)),
                            _append_code(e, e.v("cl"), cve_code(e, e.v("c"))),
                            _push_indented(e, e.v("cl"), e.v("pre"), ""),
                            push(
                                e,
                                e.v("out"),
                                _inst(e, e.cat(e.v("pre"), e.s("if ("), _gv_expr(e, e.v("c")), e.s(") {"))),
                            ),
                            e.let("bo", _insts_new(e)),
                            e.let("b", e.fld(e.v("br"), "body")),
                            _if_branch_stmts(e, "b"),
                            _push_indented(e, e.v("bo"), e.v("pre"), "  "),
                            e.incr(e.fld(e.v("ci"), "v")),
                            e.if_else(
                                or_b(
                                    e,
                                    e.mb.operator_lt(e.fld(e.v("ci"), "v"), e.fld(e.v("nc"), "v")),
                                    e.fld(a(e, "else"), "is_some"),
                                ),
                                push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("} else {")))),
                                push(e, e.v("out"), _inst(e, e.cat(e.v("pre"), e.s("}")))),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.fld(a(e, "else"), "is_some"),
                        e.seq(
                            e.let("pre", _indent(e, e.fld(e.v("nc"), "v"))),
                            e.let("bo", _insts_new(e)),
                            e.let("b", e.fld(a(e, "else"), "value")),
                            _if_branch_stmts(e, "b"),
                            _push_indented(e, e.v("bo"), e.v("pre"), ""),
                            push(
                                e,
                                e.v("out"),
                                _inst(
                                    e,
                                    e.cat(_indent(e, e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 1))), e.s("}")),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.fld(a(e, "else"), "is_some")),
                        e.seq(
                            e.mb.set(e.fld(e.v("st"), "ended"), num(e, 0)),
                            e.if_only(
                                e.eq(e.fld(e.v("st"), "has"), num(e, 1)),
                                e.mb.set(
                                    e.fld(e.v("st"), "novalue"),
                                    num(e, 1),
                                ),
                            ),
                        ),
                    ),
                    e.let("depth", e.rec(e.p("v", e.mb.operator_sub(e.fld(e.v("nc"), "v"), num(e, 2))))),
                    e.foreach(
                        a(e, "conditions"),
                        "_",
                        e.if_only(
                            e.mb.operator_ge(e.fld(e.v("depth"), "v"), num(e, 0)),
                            e.seq(
                                push(e, e.v("out"), _inst(e, e.cat(_indent(e, e.fld(e.v("depth"), "v")), e.s("}")))),
                                e.mb.set(
                                    e.fld(e.v("depth"), "v"),
                                    e.mb.operator_sub(e.fld(e.v("depth"), "v"), num(e, 1)),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.eq(e.fld(e.v("st"), "ended"), num(e, 1)),
                        ret_m(e, ok_cve(e, e.call(e.eval_builtin("codevalue_control_ended"), _code_of(e, e.v("out"))))),
                    ),
                    e.if_only(
                        e.eq(e.fld(e.v("st"), "has"), num(e, 0)), ret_m(e, ok_cve(e, cv_no(e, _code_of(e, e.v("out")))))
                    ),
                    e.if_only(
                        e.eq(e.fld(e.v("st"), "novalue"), num(e, 1)),
                        ret_m(e, err_cve(e, loc(e), "if: some branches yield a value and some do not")),
                    ),
                    e.let("all", _insts_new(e)),
                    push(
                        e,
                        e.v("all"),
                        _inst(
                            e,
                            e.cat(
                                _ir_of(e, xx(e), e.fld(e.v("st"), "ty", "value")),
                                e.s(" "),
                                e.fld(e.v("st"), "res"),
                                e.s(";"),
                            ),
                        ),
                    ),
                    e.foreach(e.v("out"), "i0", push(e, e.v("all"), e.v("i0"))),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                _code_of(e, e.v("all")),
                                _gval_new(e, e.fld(e.v("st"), "ty", "value"), e.fld(e.v("st"), "res")),
                            ),
                        )
                    ),
                ),
            ),
            e.p("loop", err_cve(e, loc(e), "glsl target: loops are not supported")),
            e.p("try_catch_finally", err_cve(e, loc(e), "glsl target: try is not supported")),
            e.p("match", err_cve(e, loc(e), "glsl target: match is not supported")),
        )
    )


def _want_list(e, *keys):
    items = []
    for k in keys:
        items.append(e.s(k))
    return e.list_new(str_(e), *items)


def _def_hooks(e, x):
    _fn_def(e, x, "h_var_code", str_(e), str_(e))
    _fn_def(
        e,
        x,
        "h_fields",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))),
        e.list_type(t(e, "gfield")),
    )
    fn_throws(e, "h_fields", errs_t(e))
    fn_impl(
        e,
        x,
        "h_var_code",
        body(
            e,
            e.let("st", e.rec(e.p("kind", e.list_new(e.mb.types_byte())), e.p("n", e.dstr("")))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.if_else(
                    and_b(
                        e,
                        e.mb.operator_ge(e.mb.as_(e.v("b"), int_t(e)), num(e, ord("0"))),
                        e.mb.operator_le(e.mb.as_(e.v("b"), int_t(e)), num(e, ord("9"))),
                    ),
                    e.mb.set(e.fld(e.v("st"), "n"), hf(e, "h_utf8", e.list_new(e.mb.types_byte(), e.v("b")))),
                    push(e, e.fld(e.v("st"), "kind"), e.v("b")),
                ),
            ),
            e.let("kind", hf(e, "h_utf8", e.fld(e.v("st"), "kind"))),
            e.ret(
                e.cat(
                    e.if_else(
                        e.eq(e.v("kind"), e.s("float")),
                        e.dstr("f"),
                        e.if_else(
                            e.eq(e.v("kind"), e.s("int")),
                            e.dstr("i"),
                            e.if_else(e.eq(e.v("kind"), e.s("uint")), e.dstr("u"), e.dstr("b")),
                        ),
                    ),
                    e.fld(e.v("st"), "n"),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_fields",
        body(
            e,
            e.let("fields", e.list_new(lt(e, "gfield"))),
            e.let("pairs", _elements(e, a(e, "cv"))),
            e.foreach(
                e.v("pairs"),
                "pc",
                e.seq(
                    e.let("pair", _elements(e, e.v("pc"))),
                    count_let(e, "n2"),
                    count_loop(e, "n2", e.v("pair")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("n2"), "v"), num(e, 2))),
                        throw_err(e, loc(e), "glsl: a block field is a (name, type) tuple"),
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
                                        throw_err(e, loc(e), "glsl: block field name must be a constant string"),
                                    ),
                                    e.mb.set(e.fld(e.v("fname"), "v"), _const_str(e, e.v("pe"))),
                                ),
                            ),
                            e.if_only(
                                e.eq(e.fld(e.v("i"), "v"), num(e, 1)),
                                e.seq(
                                    e.let("ptycv", e.v("pe")),
                                    e.let("tk", lookup(e, xx(e), cve_type(e, e.v("ptycv")), asp_iface(e, "type"))),
                                    e.if_only(
                                        or_b(e, is_runtime(e, e.v("ptycv")), e.not_(e.fld(e.v("tk"), "is_some"))),
                                        throw_err(e, loc(e), "glsl: block field type must be a constant type"),
                                    ),
                                    e.let(
                                        "fty",
                                        bim(
                                            e,
                                            asp_iface(e, "type"),
                                            "type",
                                            e.fld(e.v("tk"), "value"),
                                            cve_value(e, e.v("ptycv")),
                                        ),
                                    ),
                                    e.if_only(
                                        e.not_(
                                            or_b(
                                                e,
                                                has(e, xx(e), e.v("fty"), "gscalar"),
                                                or_b(
                                                    e,
                                                    has(e, xx(e), e.v("fty"), "gvec"),
                                                    has(e, xx(e), e.v("fty"), "gmat"),
                                                ),
                                            )
                                        ),
                                        throw_err(
                                            e,
                                            loc(e),
                                            e.cat(e.s("glsl: a block field cannot have type "), ty_desc(e, e.v("fty"))),
                                        ),
                                    ),
                                    push(
                                        e,
                                        e.v("fields"),
                                        mk(e, "gfield", e.p("name", e.fld(e.v("fname"), "v")), e.p("ty", e.v("fty"))),
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                ),
            ),
            e.ret(e.v("fields")),
        ),
    )
    self_type(
        e,
        x,
        "ggfn_t",
        e.cat(e.s("glsl definition function "), to_str(e, in_(e, "kind"))),
        rt_dispatch(e, lt(e, "gmod"), e.aspect_dispatch(lv(e, "ggfn_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ggfn_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "ggfn_m", "kind"), in_(e, "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "ggfn_t")
    rt_bind_impl(e, x, "ggfn_t", lt(e, "gmod"))
    rt_use_impl(e, x, "ggfn_t")
    x.append(e.impl_interface(e.v("ggfn_t"), t(e, "ggfn_m"), e.p("kind", in_(e, "kind"))))
    gl_vars = []
    for gv in GL_VARS:
        gl_vars.append(e.p(gv[0], e.s(gv[1] + gv[2])))
    x.append(
        e.impl_interface(
            e.v("ggfn_t"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("argv", a(e, "argument")),
                    e.if_only(
                        e.not_(cve_has(e, e.v("argv"))),
                        ret_m(e, err_cve(e, loc(e), "glsl definition argument has no value")),
                    ),
                    e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
                    e.if_only(
                        e.not_(e.fld(e.v("rk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "glsl definition argument must be a record")),
                    ),
                    e.let(
                        "want",
                        e.if_else(
                            _ggfn_is(e, "func_fn"),
                            _want_list(e, "mod", "name", "params", "ty", "body"),
                            e.if_else(
                                _ggfn_is(e, "uniform_block_fn"),
                                _want_list(e, "mod", "name", "layout", "fields"),
                                e.if_else(
                                    _ggfn_is(e, "gl_fn"), _want_list(e, "name"), _want_list(e, "mod", "name", "ty")
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
                            e.if_only(
                                e.eq(e.fld(e.v("hit"), "v"), num(e, 0)),
                                e.mb.set(e.fld(e.v("kc"), "bad"), e.v("ks")),
                            ),
                        ),
                    ),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("kc"), "bad"), e.s(""))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("glsl definition has no argument "), e.fld(e.v("kc"), "bad")),
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
                                e.cat(e.s("glsl definition requires arguments "), e.join(e.v("want"), ", ")),
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
                    e.let("namecv", _ggfn_staged(e, graft(e, _ggfn_field(e, "name")))),
                    e.if_only(
                        is_runtime(e, e.v("namecv")),
                        ret_m(e, err_cve(e, loc(e), "glsl definition name must be constant")),
                    ),
                    e.let("name", _const_str(e, e.v("namecv"))),
                    e.if_only(
                        _ggfn_is(e, "gl_fn"),
                        e.seq(
                            e.let("vars", e.map_new(str_(e), str_(e), *gl_vars)),
                            e.if_only(
                                e.not_(e.call_m(e.v("vars"), "has", e.v("name"))),
                                ret_m(e, err_cve(e, loc(e), e.cat(e.s("glsl: no builtin variable "), e.v("name")))),
                            ),
                            e.let(
                                "vty",
                                _type_of(
                                    e,
                                    hf(
                                        e,
                                        "h_parse_desc",
                                        hf(e, "h_var_code", e.call_m(e.v("vars"), "get", e.v("name"))),
                                    ),
                                ),
                            ),
                            ret_m(e, tag_value(e, e.v("namecv"), _global_t(e, e.v("vty")))),
                        ),
                    ),
                    e.let("modcv", _ggfn_field(e, "mod")),
                    e.if_only(
                        _ggfn_is(e, "uniform_block_fn"),
                        e.seq(
                            e.let("layoutcv", _ggfn_staged(e, graft(e, _ggfn_field(e, "layout")))),
                            e.if_only(
                                is_runtime(e, e.v("layoutcv")),
                                ret_m(e, err_cve(e, loc(e), "glsl block layout must be constant")),
                            ),
                            e.let(
                                "fieldsv",
                                unwrap_m(
                                    e,
                                    try_er(
                                        e,
                                        hf_rec(
                                            e,
                                            "h_fields",
                                            e.p("xx", xx(e)),
                                            e.p("loc", loc(e)),
                                            e.p("cv", _ggfn_field(e, "fields")),
                                        ),
                                        e.list_type(lt(e, "gfield")),
                                    ),
                                    cve_t(e),
                                ),
                            ),
                            e.let(
                                "refcv",
                                _ggfn_staged(
                                    e,
                                    e.call_m(
                                        _ggfn_mod(e),
                                        "block",
                                        e.rec(
                                            e.p("name", graft(e, e.v("namecv"))),
                                            e.p("layout", graft(e, e.v("layoutcv"))),
                                            e.p("fields", e.lower(e.v("fieldsv"))),
                                        ),
                                    ),
                                ),
                            ),
                            ret_m(
                                e,
                                tag_value(
                                    e,
                                    e.v("refcv"),
                                    mk(e, "gt_block", e.p("name", e.v("name")), e.p("fields", e.v("fieldsv"))),
                                ),
                            ),
                        ),
                    ),
                    e.let("tycv", _ggfn_field(e, "ty")),
                    e.let(
                        "tyv",
                        e.seq(
                            e.let("tk", lookup(e, xx(e), cve_type(e, e.v("tycv")), asp_iface(e, "type"))),
                            e.if_only(
                                or_b(e, is_runtime(e, e.v("tycv")), e.not_(e.fld(e.v("tk"), "is_some"))),
                                ret_m(e, err_cve(e, loc(e), "glsl ty must be a constant type")),
                            ),
                            e.ret(
                                bim(
                                    e,
                                    asp_iface(e, "type"),
                                    "type",
                                    e.fld(e.v("tk"), "value"),
                                    cve_value(e, e.v("tycv")),
                                ),
                            ),
                        ),
                    ),
                    e.if_only(
                        or_b(e, _ggfn_is(e, "in_fn"), _ggfn_is(e, "out_fn")),
                        e.seq(
                            e.if_only(
                                e.not_(
                                    or_b(
                                        e,
                                        has(e, xx(e), e.v("tyv"), "gscalar"),
                                        or_b(e, has(e, xx(e), e.v("tyv"), "gvec"), has(e, xx(e), e.v("tyv"), "gmat")),
                                    )
                                ),
                                ret_m(
                                    e,
                                    err_cve(
                                        e,
                                        loc(e),
                                        e.cat(
                                            e.s("glsl: a variable cannot have type "),
                                            ty_desc(e, e.v("tyv")),
                                        ),
                                    ),
                                ),
                            ),
                            e.let(
                                "decl",
                                e.cat(
                                    e.if_else(_ggfn_is(e, "in_fn"), e.dstr("in "), e.dstr("out ")),
                                    _ir_of(e, xx(e), e.v("tyv")),
                                    e.s(" "),
                                    e.v("name"),
                                    e.s(";"),
                                ),
                            ),
                            e.let(
                                "refcv",
                                _ggfn_staged(
                                    e,
                                    e.call_m(
                                        _ggfn_mod(e),
                                        "declare",
                                        e.rec(e.p("text", e.lower(e.v("decl"))), e.p("name", graft(e, e.v("namecv")))),
                                    ),
                                ),
                            ),
                            ret_m(e, tag_value(e, e.v("refcv"), _global_t(e, e.v("tyv")))),
                        ),
                    ),
                    e.if_only(
                        e.not_(has(e, xx(e), e.v("tyv"), "gfn")),
                        ret_m(
                            e,
                            err_cve(
                                e, loc(e), e.cat(e.s("glsl ty must be a function type, not "), ty_desc(e, e.v("tyv")))
                            ),
                        ),
                    ),
                    e.let("pcv", _ggfn_field(e, "params")),
                    e.let("ptk", lookup(e, xx(e), cve_type(e, e.v("pcv")), asp_iface(e, "tuple"))),
                    e.if_only(
                        e.not_(e.fld(e.v("ptk"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "glsl function params must be a tuple of parameter names")),
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
                            e.if_only(
                                e.not_(has_b(e, xx(e), cve_type(e, e.v("ncv")), e.mb.eval_aspect_string_const())),
                                ret_m(e, err_cve(e, loc(e), "glsl function parameter names must be constant strings")),
                            ),
                            push(e, e.v("names"), _const_str(e, e.v("ncv"))),
                        ),
                    ),
                    count_let(e, "pn"),
                    count_loop(e, "pn", e.v("names")),
                    count_let(e, "tn"),
                    count_loop(e, "tn", acc(e, xx(e), e.v("tyv"), "gfn", "params")),
                    e.if_only(
                        e.not_(e.eq(e.fld(e.v("pn"), "v"), e.fld(e.v("tn"), "v"))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("glsl function has "),
                                    to_str(e, e.fld(e.v("pn"), "v")),
                                    e.s(" parameter names but its type has "),
                                    to_str(e, e.fld(e.v("tn"), "v")),
                                    e.s(" parameters"),
                                ),
                            ),
                        ),
                    ),
                    e.let("bodycv", _ggfn_field(e, "body")),
                    e.let(
                        "refcv",
                        _ggfn_staged(
                            e,
                            e.call_m(
                                _ggfn_mod(e),
                                "func",
                                e.rec(
                                    e.p("name", graft(e, e.v("namecv"))),
                                    e.p("params", e.lower(e.v("names"))),
                                    e.p("ty", e.lower(e.v("tyv"))),
                                    e.p("body", graft(e, e.v("bodycv"))),
                                ),
                            ),
                        ),
                    ),
                    e.ret(tag_value(e, e.v("refcv"), _global_t(e, e.v("tyv")))),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )


def _family_part(tok, k):
    if tok in ("G", "V"):
        return "f" + str(k + 1)
    if tok in ("GI", "IV"):
        return "i" + str(k + 1)
    if tok in ("GU", "UV"):
        return "u" + str(k + 1)
    if tok in ("GB", "BV"):
        return "b" + str(k + 1)
    if tok == "M":
        return "m" + str(k + 1)
    if tok == "F":
        return "f1"
    if tok == "I":
        return "i1"
    if tok == "U":
        return "u1"
    if tok == "B":
        return "b1"
    if tok == "F2":
        return "f2"
    if tok == "F3":
        return "f3"
    raise ValueError("unknown glsl family token " + tok)


def _def_builtins(e, x):
    entries = []
    for row in BUILTINS:
        sigs = []
        for i in range(1, len(row)):
            toks = row[i].split(" ")
            any_g = False
            any_v = False
            for tok in toks:
                if tok in ("G", "GI", "GU", "GB"):
                    any_g = True
                elif tok in ("V", "IV", "UV", "BV", "M"):
                    any_v = True
            lo = 0 if any_g else 1
            hi = 3 if any_g or any_v else 1
            for k in range(lo, hi + 1):
                parts = []
                for tok in toks:
                    parts.append(_family_part(tok, k))
                sigs.append(e.s(" ".join(parts)))
        entries.append(e.p(row[0], e.list_new(str_(e), *sigs)))
    x.append(e.let("gsigs", e.map_new(str_(e), e.list_type(str_(e)), *entries)))
    _fn_def(e, x, "h_desc_match", e.rec(e.p("want", str_(e)), e.p("have", str_(e))), bool_t(e))
    fn_impl(
        e,
        x,
        "h_desc_match",
        body(
            e,
            e.if_only(e.eq(a(e, "want"), a(e, "have")), ret_m(e, e.mb.as_(e.b(True), bool_t(e)))),
            e.if_only(e.not_(e.eq(a(e, "have"), e.s("?1"))), ret_m(e, dfalse(e))),
            e.let("wd", hf(e, "h_parse_desc", a(e, "want"))),
            e.ret(
                and_b(
                    e,
                    e.eq(e.fld(e.v("wd"), "n"), num(e, 1)),
                    and_b(e, e.not_(e.fld(e.v("wd"), "mat")), e.not_(e.eq(e.fld(e.v("wd"), "kind"), e.s("bool")))),
                )
            ),
        ),
    )
    self_type(
        e,
        x,
        "gbuiltin_t",
        e.cat(e.s("glsl builtin "), in_(e, "name")),
        rt_dispatch(e, lt(e, "gmod"), e.aspect_dispatch(lv(e, "gbuiltin_m_id"), asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "gbuiltin_m"),
                    e.eq(acc(e, xx(e), a(e, "other"), "gbuiltin_m", "name"), in_(e, "name")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "gbuiltin_t")
    rt_bind_impl(e, x, "gbuiltin_t", lt(e, "gmod"))
    rt_use_impl(e, x, "gbuiltin_t")
    x.append(e.impl_interface(e.v("gbuiltin_t"), t(e, "gbuiltin_m"), e.p("name", in_(e, "name"))))
    x.append(
        e.impl_interface(
            e.v("gbuiltin_t"),
            asp_iface(e, "function"),
            e.p(
                "call",
                body(
                    e,
                    e.let("mod", _xmod(e)),
                    e.let("elems", _elements_m(e, a(e, "argument"))),
                    e.let("descs", e.list_new(str_(e))),
                    e.foreach(
                        e.v("elems"),
                        "ec",
                        e.seq(
                            e.if_only(
                                e.not_(cve_has(e, e.v("ec"))),
                                ret_m(e, err_cve(e, loc(e), "argument has no value")),
                            ),
                            e.let("et0", cve_type(e, e.v("ec"))),
                            e.if_else(
                                has(e, xx(e), e.v("et0"), "gtype"),
                                e.seq(
                                    e.let(
                                        "et",
                                        e.if_else(
                                            has(e, xx(e), e.v("et0"), "ggtype_m"),
                                            acc(e, xx(e), e.v("et0"), "ggtype_m", "base"),
                                            e.v("et0"),
                                        ),
                                    ),
                                    e.let("d", _desc_of(e, xx(e), e.v("et"))),
                                    push(
                                        e,
                                        e.v("descs"),
                                        e.cat(
                                            e.if_else(
                                                e.fld(e.v("d"), "mat"),
                                                e.dstr("m"),
                                                hf(e, "h_var_code", e.fld(e.v("d"), "kind")),
                                            ),
                                            to_str(e, e.fld(e.v("d"), "n")),
                                        ),
                                    ),
                                ),
                                e.if_else(
                                    has_b(e, xx(e), e.v("et0"), e.eval_builtin("aspect_bool_const")),
                                    push(e, e.v("descs"), e.dstr("b1")),
                                    e.if_else(
                                        is_const(e, xx(e), e.v("et0")),
                                        push(e, e.v("descs"), e.dstr("?1")),
                                        ret_m(
                                            e,
                                            err_cve(
                                                e,
                                                loc(e),
                                                e.cat(
                                                    e.s("glsl: "),
                                                    ty_desc(e, e.v("et0")),
                                                    e.s(" is not a glsl value"),
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let("sigs", e.call_m(e.lower_v("gsigs"), "get", in_(e, "name"))),
                    count_let(e, "nd"),
                    count_loop(e, "nd", e.v("descs")),
                    e.let("hit", e.list_new(str_(e))),
                    e.foreach(
                        e.v("sigs"),
                        "sig",
                        e.seq(
                            e.let("parts", hf(e, "h_split", e.v("sig"))),
                            count_let(e, "np"),
                            count_loop(e, "np", e.v("parts")),
                            e.if_only(
                                e.eq(e.fld(e.v("np"), "v"), e.mb.operator_add(e.fld(e.v("nd"), "v"), num(e, 1))),
                                e.seq(
                                    e.let("ok", e.rec(e.p("v", e.int_of(1)))),
                                    e.let("i", e.rec(e.p("v", e.int_of(0)))),
                                    e.foreach(
                                        e.v("parts"),
                                        "pd",
                                        e.seq(
                                            e.if_only(
                                                e.mb.operator_gt(e.fld(e.v("i"), "v"), num(e, 0)),
                                                e.seq(
                                                    e.let("j", e.rec(e.p("v", e.int_of(1)))),
                                                    e.foreach(
                                                        e.v("descs"),
                                                        "ad",
                                                        e.seq(
                                                            e.if_only(
                                                                and_b(
                                                                    e,
                                                                    e.eq(e.fld(e.v("j"), "v"), e.fld(e.v("i"), "v")),
                                                                    e.not_(
                                                                        hf_rec(
                                                                            e,
                                                                            "h_desc_match",
                                                                            e.p("want", e.v("pd")),
                                                                            e.p("have", e.v("ad")),
                                                                        )
                                                                    ),
                                                                ),
                                                                e.mb.set(e.fld(e.v("ok"), "v"), num(e, 0)),
                                                            ),
                                                            e.incr(e.fld(e.v("j"), "v")),
                                                        ),
                                                    ),
                                                ),
                                            ),
                                            e.incr(e.fld(e.v("i"), "v")),
                                        ),
                                    ),
                                    e.if_only(e.eq(e.fld(e.v("ok"), "v"), num(e, 1)), push(e, e.v("hit"), e.v("sig"))),
                                ),
                            ),
                        ),
                    ),
                    count_let(e, "nh"),
                    count_loop(e, "nh", e.v("hit")),
                    e.if_only(
                        e.eq(e.fld(e.v("nh"), "v"), num(e, 0)),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(
                                    e.s("glsl: no overload of "),
                                    in_(e, "name"),
                                    e.s(" takes ("),
                                    e.join(e.v("descs"), ", "),
                                    e.s(")"),
                                ),
                            ),
                        ),
                    ),
                    e.let("chosen", e.rec(e.p("v", e.dstr("")))),
                    e.foreach(
                        e.v("hit"),
                        "h",
                        e.if_only(
                            e.eq(e.fld(e.v("chosen"), "v"), e.s("")),
                            e.mb.set(e.fld(e.v("chosen"), "v"), e.v("h")),
                        ),
                    ),
                    e.let("parts", hf(e, "h_split", e.fld(e.v("chosen"), "v"))),
                    e.let("out", _insts_new(e)),
                    e.let("exprs", e.list_new(str_(e))),
                    e.let("i", e.rec(e.p("v", e.int_of(0)))),
                    e.let("rty", e.rec(e.p("v", e.option_type_lowered_none()))),
                    e.foreach(
                        e.v("parts"),
                        "pd",
                        e.seq(
                            e.let("pty", _type_of(e, hf(e, "h_parse_desc", e.v("pd")))),
                            e.if_only(
                                e.eq(e.fld(e.v("i"), "v"), num(e, 0)),
                                e.mb.set(e.fld(e.v("rty"), "v"), e.option_type_lowered_some(e.v("pty"))),
                            ),
                            e.if_only(
                                e.mb.operator_gt(e.fld(e.v("i"), "v"), num(e, 0)),
                                e.seq(
                                    e.let("j", e.rec(e.p("v", e.int_of(1)))),
                                    e.foreach(
                                        e.v("elems"),
                                        "ec",
                                        e.seq(
                                            e.if_only(
                                                e.eq(e.fld(e.v("j"), "v"), e.fld(e.v("i"), "v")),
                                                e.seq(
                                                    e.let("ev", _operand_m(e, e.v("pty"), e.v("ec"))),
                                                    _append_code(e, e.v("out"), cve_code(e, e.v("ev"))),
                                                    push(e, e.v("exprs"), _gv_expr(e, e.v("ev"))),
                                                ),
                                            ),
                                            e.incr(e.fld(e.v("j"), "v")),
                                        ),
                                    ),
                                ),
                            ),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            hf_rec(
                                e,
                                "h_stmt",
                                e.p("mod", e.v("mod")),
                                e.p("out", e.v("out")),
                                e.p("ty", e.fld(e.v("rty"), "v", "value")),
                                e.p("expr", e.cat(in_(e, "name"), e.s("("), e.join(e.v("exprs"), ", "), e.s(")"))),
                            ),
                        )
                    ),
                ),
            ),
            e.p("exception_type", e.option_type_lowered_none()),
        )
    )


def module(e):
    x = []
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    _def_data(e, x)
    _def_helpers(e, x)
    _def_arith(e, x)
    _def_types(e, x)
    _def_refs(e, x)
    _def_module(e, x)
    _def_target(e, x)
    _def_hooks(e, x)
    _def_builtins(e, x)
    _fn_def(e, x, "c_fn", e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e))), ty(e))
    fn_impl(e, x, "c_fn", body(e, e.ret(mk(e, "gt_fn", e.p("params", a(e, "params")), e.p("ret", a(e, "ret"))))))
    _fn_def(e, x, "c_desc", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), _desc_t(e))
    fn_impl(e, x, "c_desc", body(e, e.ret(_desc_of(e, xx(e), a(e, "ty")))))
    x.append(e.let("glsl_b", e.def_func(e.v("d"), "glsl")))
    x.append(
        e.func_impl(
            e.v("glsl_b"),
            e.tup(),
            e.option_type_some(t(e, "gmod")),
            e.mb.opt_none_type(),
            e.stage(
                e.seq(
                    e.let(
                        "m",
                        mk(
                            e,
                            "gmod",
                            e.p("n", num(e, 0)),
                            e.p("xx", e.opt_none(e.types_expr_context())),
                            e.p("decls", e.list_new(str_(e))),
                            e.p("funcs", e.list_new(str_(e))),
                        ),
                    ),
                    e.let("tgt", mk(e, "gtarget", e.p("mod", e.v("m")))),
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
    x.append(e.finish(e.v("d")))
    defs = []
    defs.append(e.p("new", e.fld(e.v("glsl_b"), "func")))
    defs.append(e.p("mod_t", t(e, "gmod")))
    defs.append(e.p("fn", e.v("c_fn")))
    defs.append(e.p("desc", e.v("c_desc")))
    defs.append(e.p("field_t", t(e, "gfield")))
    defs.append(e.p("field_new", e.fld(e.v("gfield"), "new")))
    for obj in ["gt_scalar", "gt_vec", "gt_mat", "gt_void", "ggfn_t", "gbuiltin_t"]:
        defs.append(e.p(obj + "_new", e.fld(e.v(obj), "new")))
    x.append(e.ret(e.rec(*defs)))

    y = []
    y.append(e.let("k", e.lower(e.mb.seq(x))))
    exported = []
    for kind in KINDS:
        exported.append(kind)
        y.append(e.let(kind, _lty(e, "gt_scalar", e.rec(e.p("kind", e.s(kind))))))
        for n in range(2, 5):
            name = ("" if kind == "float" else kind[0]) + "vec" + str(n)
            exported.append(name)
            y.append(e.let(name, _lty(e, "gt_vec", e.rec(e.p("kind", e.s(kind)), e.p("n", e.int_of(n))))))
    for n in range(2, 5):
        exported.append("mat" + str(n))
        y.append(e.let("mat" + str(n), _lty(e, "gt_mat", e.rec(e.p("n", e.int_of(n))))))
    exported.append("void")
    y.append(e.let("void", _lty(e, "gt_void", e.tup())))
    for kind in GGFN_KINDS:
        exported.append(kind)
        y.append(e.let(kind, _lty(e, "ggfn_t", e.rec(e.p("kind", e.int_of(_ggfn_kind(kind)))))))
    builtins = []
    for row in BUILTINS:
        builtins.append(e.p(row[0], _lty(e, "gbuiltin_t", e.rec(e.p("name", e.s(row[0]))))))
    y.append(e.let("gbuiltins", e.rec(*builtins)))
    y.append(e.let("d", e.define()))
    y.append(e.option_type_let())
    y.append(e.let("mod_o", e.def_object(e.v("d"), "glsl module")))
    y.append(e.object_impl(e.v("mod_o"), e.rec(e.p("m", e.fld(e.v("k"), "mod_t")))))
    y.append(
        e.method_impl(
            e.v("mod_o"),
            "render",
            e.tup(),
            e.option_type_some(_render_t(e)),
            e.stage(e.call_m(in_(e, "m"), "render", e.tup())),
        )
    )
    y.append(
        e.method_impl(e.v("mod_o"), "m", e.tup(), e.option_type_some(e.fld(e.v("k"), "mod_t")), e.stage(in_(e, "m"))),
    )
    y.append(
        e.method_impl(
            e.v("mod_o"), "decl", str_(e), e.option_type_none(), e.stage(e.call_m(in_(e, "m"), "decl", e.v("arg")))
        )
    )
    y.append(e.let("glsl_b", e.def_func(e.v("d"), "glsl")))
    y.append(
        e.func_impl(
            e.v("glsl_b"),
            e.tup(),
            e.option_type_some(e.fld(e.v("mod_o"), "type")),
            e.mb.opt_none_type(),
            e.stage(mk_arg(e, "mod_o", e.rec(e.p("m", e.call(e.fld(e.lower_v("k"), "new"), e.tup()))))),
        )
    )
    y.append(e.finish(e.v("d")))
    ydefs = []
    ydefs.append(e.p("new", e.fld(e.v("glsl_b"), "func")))
    ydefs.append(e.p("mod_t", e.fld(e.v("mod_o"), "type")))
    for name in ["fn", "desc", "field_t", "field_new"]:
        ydefs.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        ydefs.append(e.p(name, e.v(name)))
    ydefs.append(e.p("builtins", e.v("gbuiltins")))
    y.append(e.ret(e.rec(*ydefs)))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(y))))
    exports = []
    for name in ["new", "mod_t", "fn", "desc", "field_t", "field_new", "builtins"]:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    for name in exported:
        exports.append(e.p(name, e.fld(e.v("k"), name)))
    top.append(e.ret(e.rec(*exports)))
    return top


def _lty(e, obj, arg):
    return e.mb.as_(e.call(e.fld(e.v("k"), obj + "_new"), arg), ty(e))


def _def_data(e, x):
    def_iface(e, x, "gfield_m")
    def_obj(e, x, "gfield", "glsl block field", e.rec(e.p("name", str_(e)), e.p("ty", ty(e))))
    accessor(e, x, "gfield", "name", str_(e))
    accessor(e, x, "gfield", "ty", ty(e))
    def_iface(e, x, "gtype", e.p("ir", str_(e)))
    def_iface(e, x, "gscalar", e.p("kind", str_(e)))
    def_iface(e, x, "gvec", e.p("kind", str_(e)), e.p("n", int_t(e)))
    def_iface(e, x, "gmat", e.p("n", int_t(e)))
    def_iface(e, x, "gvoid")
    def_iface(e, x, "gfn", e.p("params", e.list_type(ty(e))), e.p("ret", ty(e)))
    def_iface(e, x, "ggtype_m", e.p("base", ty(e)))
    def_iface(e, x, "gblock_m", e.p("fields", e.list_type(t(e, "gfield"))), e.p("name", str_(e)))
    def_iface(e, x, "ggfn_m", e.p("kind", int_t(e)))
    def_iface(e, x, "gbuiltin_m", e.p("name", str_(e)))
    for vo in ["ginst", "gmod"]:
        def_iface(e, x, vo + "_m")
    def_obj(e, x, "ginst", "glsl statement", e.rec(e.p("text", str_(e))))
    accessor(e, x, "ginst", "text", str_(e))
    def_obj(e, x, "gcode", "glsl code", e.rec(e.p("insts", _insts_t(e))))
    x.append(e.impl_interface(e.v("gcode"), e.mb.builtin("eval", "code_dyn")))
    method(e, x, "gcode", "insts", e.tup(), _insts_t(e), in_(e, "insts"))
    def_obj(e, x, "gval", "glsl value", e.rec(e.p("ty", ty(e)), e.p("expr", str_(e))))
    x.append(
        e.impl_interface(
            e.v("gval"),
            e.fld(e.v("values"), "retag"),
            e.p("retag", mk(e, "gval", e.p("ty", e.v("arg")), e.p("expr", in_(e, "expr")))),
        )
    )
    accessor(e, x, "gval", "expr", str_(e))
    accessor(e, x, "gval", "ty", ty(e))
    x.append(
        e.impl_interface(
            e.v("gval"),
            e.mb.eval_value(),
            e.p("type", in_(e, "ty")),
            e.p(
                "exporter",
                e.eresult_ok(
                    e.mb.builtin("eval", "artifact_exporter"),
                    e.call(e.eval_builtin("source_object_exporter"), e.lower(e.fld(e.v("gval"), "type"))),
                ),
            ),
        )
    )
    def_obj(
        e,
        x,
        "gmod",
        "glsl module",
        e.rec(
            e.p("n", int_t(e)),
            e.p("xx", e.call(e.mb.types_option(), e.types_expr_context())),
            e.p("decls", e.list_type(str_(e))),
            e.p("funcs", e.list_type(str_(e))),
        ),
    )
    def_obj(e, x, "gtarget", "glsl target", e.rec(e.p("mod", _gmod_t(e))))
    accessor(e, x, "gtarget", "mod", _gmod_t(e))
    def_obj(e, x, "gbinding", "glsl binding", e.rec(e.p("ty", ty(e)), e.p("name", str_(e))))
    x.append(
        e.impl_interface(
            e.v("gbinding"),
            e.mb.eval_binding(),
            e.p("use", cv_of(e, a(e, "code"), _gval_new(e, in_(e, "ty"), in_(e, "name")))),
            e.p("drop", binding_drop_body(e)),
            e.p("fork", outer(e)),
            e.p("merge", e.eresult_ok(e.mb.eval_binding(), outer(e))),
        )
    )
    def_obj(e, x, "gt_scalar", "glsl scalar type", e.rec(e.p("kind", str_(e))))
    def_obj(e, x, "gt_vec", "glsl vector type", e.rec(e.p("kind", str_(e)), e.p("n", int_t(e))))
    def_obj(e, x, "gt_mat", "glsl matrix type", e.rec(e.p("n", int_t(e))))
    def_obj(e, x, "gt_void", "glsl void type", e.tup())
    def_obj(e, x, "gt_fn", "glsl function type", e.rec(e.p("params", e.list_type(ty(e))), e.p("ret", ty(e))))
    def_obj(e, x, "gt_global", "glsl global type", e.rec(e.p("base", ty(e))))
    def_obj(
        e,
        x,
        "gt_block",
        "glsl uniform block type",
        e.rec(e.p("name", str_(e)), e.p("fields", e.list_type(t(e, "gfield")))),
    )
    def_obj(e, x, "ggfn_t", "glsl definition function", e.rec(e.p("kind", int_t(e))))
    def_obj(e, x, "gbuiltin_t", "glsl builtin function", e.rec(e.p("name", str_(e))))
    for vo in ["ginst", "gmod", "gfield"]:
        marker_type(e, x, vo, vo, vo + "_m", e.aspect_dispatch(lv(e, vo + "_m_id")))
        x.append(e.impl_interface(e.v(vo), t(e, vo + "_m")))


def _def_helpers(e, x):
    _fn_def(e, x, "h_utf8", e.list_type(e.mb.types_byte()), str_(e))
    _fn_def(e, x, "h_insts", code_t(e), _insts_t(e))
    _fn_def(e, x, "h_code", _insts_t(e), code_t(e))
    x.append(e.let("h_append_b", e.def_func(e.v("d"), "glsl.h_append")))
    x.append(e.let("h_append", e.fld(e.v("h_append_b"), "func")))
    e.fn_sigs["h_append"] = [
        e.rec(e.p("out", _insts_t(e)), e.p("code", code_t(e))),
        e.option_type_none(),
        e.option_type_none(),
    ]
    _fn_def(e, x, "h_is_glsl", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), bool_t(e))
    _fn_def(e, x, "h_ir", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), str_(e))
    _fn_def(e, x, "h_desc", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), _desc_t(e))
    _fn_def(e, x, "h_type_of", _desc_t(e), ty(e))
    _fn_def(e, x, "h_parse_desc", str_(e), _desc_t(e))
    _fn_def(e, x, "h_split", str_(e), e.list_type(str_(e)))
    _fn_def(e, x, "h_float_lit", e.types_double(), str_(e))
    _fn_def(
        e,
        x,
        "h_operand",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("ty", ty(e)), e.p("cv", cve_t(e))),
        cve_t(e),
    )
    fn_throws(e, "h_operand", errs_t(e))
    _fn_def(e, x, "h_const_str", e.rec(e.p("xx", xx_t(e)), e.p("cv", cve_t(e))), str_(e))
    _fn_def(
        e,
        x,
        "h_stmt",
        e.rec(e.p("mod", _gmod_t(e)), e.p("out", _insts_t(e)), e.p("ty", ty(e)), e.p("expr", str_(e))),
        cve_t(e),
    )
    _fn_def(
        e,
        x,
        "h_arith",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _gmod_t(e)),
            e.p("op", str_(e)),
            e.p("self", ty(e)),
            e.p("a", cve_t(e)),
            e.p("b", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_arith", errs_t(e))
    _fn_def(
        e,
        x,
        "h_cmp",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _gmod_t(e)),
            e.p("op", str_(e)),
            e.p("self", ty(e)),
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
            e.p("mod", _gmod_t(e)),
            e.p("op", str_(e)),
            e.p("ty", ty(e)),
            e.p("a", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_unop", errs_t(e))
    _fn_def(e, x, "h_gval", e.rec(e.p("cv", cve_t(e)), e.p("base", ty(e))), cve_t(e))
    _fn_def(
        e,
        x,
        "h_construct",
        e.rec(
            e.p("xx", xx_t(e)),
            e.p("loc", loc_t(e)),
            e.p("mod", _gmod_t(e)),
            e.p("ty", ty(e)),
            e.p("argument", cve_t(e)),
        ),
        cve_t(e),
    )
    fn_throws(e, "h_construct", errs_t(e))
    _fn_def(e, x, "h_components", e.rec(e.p("xx", xx_t(e)), e.p("ty", ty(e))), int_t(e))
    _fn_def(
        e,
        x,
        "h_elements",
        e.rec(e.p("xx", xx_t(e)), e.p("loc", loc_t(e)), e.p("cv", cve_t(e))),
        e.list_type(e.mb.types_cve()),
    )
    fn_throws(e, "h_elements", errs_t(e))
    fn_impl(
        e,
        x,
        "h_elements",
        body(
            e,
            e.let("els", e.list_new(e.mb.types_cve())),
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "argument has no value")),
            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "cv")), asp_iface(e, "tuple"))),
            e.if_else(
                e.fld(e.v("tk"), "is_some"),
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
                push(e, e.v("els"), a(e, "cv")),
            ),
            e.ret(e.v("els")),
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
                            e.call_m(e.v("c"), "cast", lt(e, "gcode")),
                            "r",
                            None,
                            e.p("ok", e.call_m(e.v("r"), "insts", e.tup())),
                            e.p("errs", e.mb.panic(e.s("glsl: code belongs to another target"))),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(e, x, "h_code", body(e, e.ret(e.mb.as_(mk_arg(e, "gcode", e.rec(e.p("insts", e.v("arg")))), code_t(e)))))
    fn_impl(e, x, "h_append", body(e, e.foreach(hf(e, "h_insts", a(e, "code")), "i", push(e, a(e, "out"), e.v("i")))))
    fn_impl(
        e,
        x,
        "h_is_glsl",
        body(e, e.ret(e.if_else(cve_has(e, a(e, "cv")), has(e, xx(e), cve_type(e, a(e, "cv")), "gtype"), e.b(False)))),
    )
    fn_impl(
        e,
        x,
        "h_ir",
        body(
            e,
            e.let("lk", lookup(e, xx(e), a(e, "ty"), lt(e, "gtype"))),
            e.if_only(
                e.not_(e.fld(e.v("lk"), "is_some")),
                e.mb.panic(e.cat(e.s("glsl: not a glsl type: "), ty_desc(e, a(e, "ty")))),
            ),
            e.ret(bim0(e, lt(e, "gtype"), "ir", e.fld(e.v("lk"), "value"))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_desc",
        body(
            e,
            e.if_only(
                has(e, xx(e), a(e, "ty"), "gscalar"),
                ret_m(
                    e,
                    e.rec(
                        e.p("kind", acc(e, xx(e), a(e, "ty"), "gscalar", "kind")),
                        e.p("n", e.int_of(1)),
                        e.p("mat", dfalse(e)),
                    ),
                ),
            ),
            e.if_only(
                has(e, xx(e), a(e, "ty"), "gvec"),
                ret_m(
                    e,
                    e.rec(
                        e.p("kind", acc(e, xx(e), a(e, "ty"), "gvec", "kind")),
                        e.p("n", acc(e, xx(e), a(e, "ty"), "gvec", "n")),
                        e.p("mat", dfalse(e)),
                    ),
                ),
            ),
            e.if_only(
                has(e, xx(e), a(e, "ty"), "gmat"),
                ret_m(
                    e,
                    e.rec(
                        e.p("kind", e.dstr("float")),
                        e.p("n", acc(e, xx(e), a(e, "ty"), "gmat", "n")),
                        e.p("mat", e.mb.as_(e.b(True), bool_t(e))),
                    ),
                ),
            ),
            e.mb.panic(e.cat(e.s("glsl: type has no components: "), ty_desc(e, a(e, "ty")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_type_of",
        body(
            e,
            e.if_only(a(e, "mat"), ret_m(e, e.mb.as_(mk(e, "gt_mat", e.p("n", a(e, "n"))), ty(e)))),
            e.if_only(e.eq(a(e, "n"), num(e, 1)), ret_m(e, e.mb.as_(_scalar_t(e, a(e, "kind")), ty(e)))),
            e.ret(e.mb.as_(_vec_t(e, a(e, "kind"), a(e, "n")), ty(e))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_parse_desc",
        body(
            e,
            e.let("st", e.rec(e.p("kind", e.dstr("")), e.p("n", e.int_of(0)), e.p("i", e.int_of(0)))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.seq(
                    e.let("c", e.mb.as_(e.v("b"), int_t(e))),
                    e.if_else(
                        e.eq(e.fld(e.v("st"), "i"), num(e, 0)),
                        e.mb.set(
                            e.fld(e.v("st"), "kind"),
                            e.if_else(
                                e.eq(e.v("c"), num(e, ord("f"))),
                                e.dstr("float"),
                                e.if_else(
                                    e.eq(e.v("c"), num(e, ord("i"))),
                                    e.dstr("int"),
                                    e.if_else(
                                        e.eq(e.v("c"), num(e, ord("u"))),
                                        e.dstr("uint"),
                                        e.if_else(e.eq(e.v("c"), num(e, ord("b"))), e.dstr("bool"), e.dstr("mat")),
                                    ),
                                ),
                            ),
                        ),
                        e.mb.set(e.fld(e.v("st"), "n"), e.mb.operator_sub(e.v("c"), e.int_of(ord("0")))),
                    ),
                    e.incr(e.fld(e.v("st"), "i")),
                ),
            ),
            e.if_only(
                e.eq(e.fld(e.v("st"), "kind"), e.s("mat")),
                ret_m(
                    e,
                    e.rec(
                        e.p("kind", e.dstr("float")),
                        e.p("n", e.fld(e.v("st"), "n")),
                        e.p("mat", e.mb.as_(e.b(True), bool_t(e))),
                    ),
                ),
            ),
            e.ret(e.rec(e.p("kind", e.fld(e.v("st"), "kind")), e.p("n", e.fld(e.v("st"), "n")), e.p("mat", dfalse(e)))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_split",
        body(
            e,
            e.let("out", e.list_new(str_(e))),
            e.let("cur", e.rec(e.p("b", e.list_new(e.mb.types_byte())))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("arg")),
                "b",
                e.if_else(
                    e.eq(e.mb.as_(e.v("b"), int_t(e)), num(e, ord(" "))),
                    e.seq(
                        push(e, e.v("out"), hf(e, "h_utf8", e.fld(e.v("cur"), "b"))),
                        e.mb.set(e.fld(e.v("cur"), "b"), e.list_new(e.mb.types_byte())),
                    ),
                    push(e, e.fld(e.v("cur"), "b"), e.v("b")),
                ),
            ),
            push(e, e.v("out"), hf(e, "h_utf8", e.fld(e.v("cur"), "b"))),
            e.ret(e.v("out")),
        ),
    )
    fn_impl(
        e,
        x,
        "h_float_lit",
        body(
            e,
            e.let("s", to_str(e, e.v("arg"))),
            e.let("st", e.rec(e.p("frac", e.int_of(0)))),
            e.foreach(
                e.call(e.mb.eval_str_utf8(), e.v("s")),
                "b",
                e.seq(
                    e.let("c", e.mb.as_(e.v("b"), int_t(e))),
                    e.if_only(
                        or_b(
                            e,
                            e.eq(e.v("c"), num(e, ord("."))),
                            or_b(
                                e,
                                e.eq(e.v("c"), num(e, ord("e"))),
                                or_b(e, e.eq(e.v("c"), num(e, ord("E"))), e.eq(e.v("c"), num(e, ord("n")))),
                            ),
                        ),
                        e.mb.set(e.fld(e.v("st"), "frac"), e.int_of(1)),
                    ),
                ),
            ),
            e.ret(e.if_else(e.eq(e.fld(e.v("st"), "frac"), num(e, 1)), e.v("s"), e.cat(e.v("s"), e.s(".0")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_operand",
        body(
            e,
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), throw_err(e, loc(e), "operand has no value")),
            e.ret(unwrap_cve_t(e, cast_value(e, xx(e), loc(e), a(e, "ty"), a(e, "cv")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_const_str",
        body(
            e,
            e.let("sk", lookup(e, xx(e), cve_type(e, a(e, "cv")), e.mb.eval_aspect_string_const())),
            e.if_only(e.not_(e.fld(e.v("sk"), "is_some")), e.mb.panic(e.s("glsl: expected a constant string"))),
            e.ret(bim(e, e.mb.eval_aspect_string_const(), "get", e.fld(e.v("sk"), "value"), cve_value(e, a(e, "cv")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_stmt",
        body(
            e,
            e.let("r", _fresh(e, a(e, "mod"))),
            push(
                e,
                a(e, "out"),
                _inst(
                    e,
                    e.cat(
                        _ir_of(e, e.call_m(a(e, "mod"), "xx", e.tup()), a(e, "ty")),
                        e.s(" "),
                        e.v("r"),
                        e.s(" = "),
                        a(e, "expr"),
                        e.s(";"),
                    ),
                ),
            ),
            e.ret(cv_of(e, _code_of(e, a(e, "out")), _gval_new(e, a(e, "ty"), e.v("r")))),
        ),
    )
    fn_impl(
        e,
        x,
        "h_gval",
        body(
            e,
            e.ret(
                cv_of(
                    e,
                    cve_code(e, a(e, "cv")),
                    _gval_new(
                        e,
                        a(e, "base"),
                        e.call(
                            e.mb.must_reinterpret(),
                            e.tup(
                                e.fld(
                                    e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, a(e, "cv")), voc_t(e))),
                                    "data",
                                ),
                                str_(e),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_components",
        body(
            e,
            e.let("d", _desc_of(e, xx(e), a(e, "ty"))),
            e.ret(
                e.if_else(
                    e.fld(e.v("d"), "mat"),
                    e.mb.operator_mul(e.fld(e.v("d"), "n"), e.fld(e.v("d"), "n")),
                    e.fld(e.v("d"), "n"),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_utf8",
        body(
            e,
            e.ret(
                e.match_of(
                    e.call(e.eval_builtin("str_from_utf8"), e.v("arg")),
                    "__s",
                    None,
                    e.p("some", e.v("__s")),
                    e.p("none", e.mb.panic(e.s("glsl: text is not valid UTF-8"))),
                )
            ),
        ),
    )
