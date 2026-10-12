"""destructor.atz: owned values whose destroy function runs when the binding holding them is dropped.

`destructor.type({under, destroy})` makes a type over `under` (a runtime type of any target); `destroy` is the
function value to call with the `under` value. Calling the made type converts an
`under` value into an owned value. Binding an owned value tracks a moved flag on the binding: loading the binding
yields a reference that acts as `under` everywhere, except that `.move()` yields the owned value again and marks the
binding moved, and assigning an owned value to it destroys the previous one first. When the binding is dropped
unmoved, `destroy(value)` is emitted. A binding moved in some branches but not others is a compile error.
"""

from . import values
from .eco_mb import p
from .target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    body,
    bool_t,
    cast_from_self,
    cast_to_panic,
    cast_value,
    const_fn,
    code_none,
    code_t,
    const_eval_in,
    cv_no,
    cv_of,
    cve_code,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    errs_t,
    fn_def,
    fn_impl,
    fn_throws,
    graft,
    has,
    has_b,
    hf_rec,
    in_,
    is_equal,
    is_target_code,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    must_v,
    ok_cve,
    outer,
    reinterpret,
    ret_m,
    self_type,
    t,
    throw_err,
    try_er,
    ty,
    ty_desc,
    type_aspect,
    unwrap_cve_m,
    unwrap_m,
    voc_t,
    xx,
)

FILE = "destructor.atz"

TARGET = "destructor"


def _binding_t(e):
    return e.mb.eval_binding()


def _setter_t(e):
    return e.mb.builtin("eval", "binding_setter")


def _must(e, res):
    """Unwraps an eresult inside a host function, rethrowing its errors."""
    return e.match_of(res, "__r", None, p("ok", e.v("__r")), p("errs", e.mb.throw_(e.v("__r"))))


def _rec_xl(e, *fields):
    return e.rec(p("xx", xx(e)), p("loc", loc(e)), *fields)


def _retag(e, cv, type_):
    return hf_rec(e, "h_retag", p("xx", xx(e)), p("loc", loc(e)), p("cv", cv), p("type", type_))


def _retag_v(e, cv, type_):
    """Retags where no error channel exists (binding use); a failure here is a bug upstream of the binding."""
    return must_v(e, TARGET, try_er(e, _retag(e, cv, type_), cve_t(e)), "retag binding value")


def _retag_m(e, cv, type_, ret_inner):
    return unwrap_m(e, try_er(e, _retag(e, cv, type_), cve_t(e)), ret_inner)


def _destroy_m(e, owned, cv, ret_inner):
    return unwrap_m(
        e,
        try_er(e, hf_rec(e, "h_destroy", p("xx", xx(e)), p("loc", loc(e)), p("owned", owned), p("cv", cv)), code_t(e)),
        ret_inner,
    )


def _cat_m(e, first, second, ret_inner):
    return unwrap_m(
        e,
        try_er(
            e,
            hf_rec(e, "h_cat", p("xx", xx(e)), p("loc", loc(e)), p("first", first), p("second", second)),
            code_t(e),
        ),
        ret_inner,
    )


def _under_of(e, owned):
    return acc(e, xx(e), owned, "owned_m", "under")


def _under_x(e, xx_, owned):
    return acc(e, xx_, owned, "owned_m", "under")


def _ref_under(e):
    return _under_of(e, in_(e, "owned"))


def _obinding(e, inner, owned, moved):
    return mk(e, "obinding", p("inner", inner), p("owned", owned), p("moved", moved))


def _setter_set(e, setter, binding, drop_modified):
    return bim(e, _setter_t(e), "set", setter, _rec_xl(e, p("new_binding", binding), p("drop_modified", drop_modified)))


def _binding_use(e, binding, setter, code):
    return bim(e, _binding_t(e), "use", binding, _rec_xl(e, p("setter", setter), p("code", code)))


def _consumed(e):
    return e.call(e.mb.eval_binding_setter_consumed(), e.tup())


def _drop_value(e, cv):
    return e.call(e.mb.eval_drop_value(), _rec_xl(e, p("cv", cv)))


def _const_str(e, cv):
    return bim(
        e,
        e.mb.eval_aspect_string_const(),
        "get",
        lookup_v(e, xx(e), cve_type(e, cv), e.mb.eval_aspect_string_const()),
        cve_value(e, cv),
    )


def _dispatch(e, own_ids, fallback):
    branches = []
    for id_ in own_ids:
        branches.append((e.eq(a(e, "key"), id_), e.opt_some(e.mb.types_aspect(), outer(e))))
    return e.mb.if_of(branches, fallback)


def _host_fns(e, x):
    def xl():
        return [p("xx", e.types_expr_context()), p("loc", e.types_loc())]

    fn_def(e, x, TARGET, "h_retag", e.rec(*xl(), p("cv", cve_t(e)), p("type", ty(e))), cve_t(e))
    fn_def(e, x, TARGET, "h_destroy", e.rec(*xl(), p("owned", ty(e)), p("cv", cve_t(e))), code_t(e))
    fn_def(e, x, TARGET, "h_cat", e.rec(*xl(), p("first", code_t(e)), p("second", code_t(e))), code_t(e))
    for name in ["h_retag", "h_destroy", "h_cat"]:
        fn_throws(e, name, errs_t(e))
    fn_impl(
        e,
        x,
        "h_retag",
        body(
            e,
            e.let("v", cve_value(e, a(e, "cv"))),
            e.match_of(
                e.call(e.mb.reinterpret(), e.tup(loc(e), e.v("v"), e.mb.builtin("types", "value_dynamic"))),
                "__d",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        cv_of(
                            e,
                            cve_code(e, a(e, "cv")),
                            e.call(
                                e.eval_builtin("value_dynamic"),
                                e.rec(p("source", e.fld(e.v("__d"), "source")), p("type", a(e, "type"))),
                            ),
                        ),
                    ),
                ),
                p("errs", e.seq()),
            ),
            e.match_of(
                e.call(e.mb.reinterpret(), e.tup(loc(e), e.v("v"), e.lower(e.fld(e.v("values"), "retag")))),
                "__t",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        cv_of(
                            e,
                            cve_code(e, a(e, "cv")),
                            bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), a(e, "type")),
                        ),
                    ),
                ),
                p("errs", throw_err(e, loc(e), "destructor: only runtime values can be owned")),
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_destroy",
        body(
            e,
            e.let("under", _under_of(e, a(e, "owned"))),
            e.let(
                "destroy",
                cv_of(
                    e,
                    code_none(e, loc(e)),
                    e.mb.as_(acc(e, xx(e), a(e, "owned"), "owned_m", "destroy"), e.mb.eval_value()),
                ),
            ),
            e.let("fk", lookup(e, xx(e), cve_type(e, e.v("destroy")), asp_iface(e, "function"))),
            e.if_only(e.not_(e.fld(e.v("fk"), "is_some")), throw_err(e, loc(e), "destructor: destroy is not callable")),
            e.let("v", _retag(e, a(e, "cv"), e.v("under"))),
            e.let(
                "r",
                _must(
                    e,
                    bim(
                        e,
                        asp_iface(e, "function"),
                        "call",
                        e.fld(e.v("fk"), "value"),
                        _rec_xl(e, p("self", e.v("destroy")), p("argument", e.v("v"))),
                    ),
                ),
            ),
            e.if_only(e.not_(cve_has(e, e.v("r"))), ret_m(e, cve_code(e, e.v("r")))),
            e.ret(
                hf_rec(
                    e,
                    "h_cat",
                    p("xx", xx(e)),
                    p("loc", loc(e)),
                    p("first", cve_code(e, e.v("r"))),
                    p("second", _must(e, _drop_value(e, e.v("r")))),
                )
            ),
        ),
    )
    fn_impl(
        e,
        x,
        "h_cat",
        body(
            e,
            e.if_only(e.not_(is_target_code(e, a(e, "first"))), ret_m(e, a(e, "second"))),
            e.if_only(e.not_(is_target_code(e, a(e, "second"))), ret_m(e, a(e, "first"))),
            e.ret(
                _must(
                    e,
                    bim(
                        e,
                        e.mb.eval_target(),
                        "seq",
                        e.fld(xx(e), "target"),
                        e.rec(p("loc", loc(e)), p("entries", e.list_new(code_t(e), a(e, "first"), a(e, "second")))),
                    ),
                )
            ),
        ),
    )


def _owned(e, x):
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v("owned"),
            t(e, "owned_m"),
            p("under", in_(e, "under")),
            p("destroy", in_(e, "destroy")),
        )
    )
    self_type(
        e,
        x,
        "owned",
        e.cat(e.s("owned "), ty_desc(e, in_(e, "under"))),
        _dispatch(
            e,
            [
                asp_id(e, "bind"),
                asp_id(e, "initial_bind"),
                e.mb.eval_aspect_drop_dynamic_id(),
                asp_id(e, "function"),
                lv(e, "owned_m_id"),
            ],
            type_aspect(e, xx(e), in_(e, "under"), a(e, "key")),
        ),
        body(e, e.ret(is_equal(e, xx(e), outer(e), a(e, "source_type")))),
        cast_from_self(e),
        e.mb.as_(e.b(True), bool_t(e)),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.ret(
                err_cve(
                    e,
                    loc(e),
                    e.cat(
                        e.s("owned value used as "),
                        ty_desc(e, a(e, "dest_type")),
                        e.s(": borrow it through a binding or move() it into an owned parameter"),
                    ),
                )
            ),
        ),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "owned_m"),
                    is_equal(e, xx(e), in_(e, "under"), _under_of(e, a(e, "other"))),
                )
            ),
        ),
    )
    # Calling the type converts an `under` value into an owned value.
    x.append(
        e.impl_interface(
            e.v("owned"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.if_only(
                        e.not_(cve_has(e, a(e, "argument"))),
                        ret_m(e, err_cve(e, loc(e), "owned: argument has no value")),
                    ),
                    e.let("v", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "under"), a(e, "argument")))),
                    e.ret(ok_cve(e, _retag_m(e, e.v("v"), outer(e), cve_t(e)))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    x.append(
        e.impl_interface(
            e.v("owned"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                body(
                    e,
                    e.let("ub", lookup(e, xx(e), in_(e, "under"), e.mb.eval_aspect_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ub"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                br_t,
                                loc(e),
                                e.cat(e.s("owned: "), ty_desc(e, in_(e, "under")), e.s(" cannot be bound")),
                            ),
                        ),
                    ),
                    e.let("v", _retag_m(e, a(e, "cv"), in_(e, "under"), br_t)),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_bind(),
                                "bind",
                                e.fld(e.v("ub"), "value"),
                                _rec_xl(e, p("cv", e.v("v"))),
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
                                    p("code", e.fld(e.v("r"), "code")),
                                    p("binding", _obinding(e, e.fld(e.v("r"), "binding"), outer(e), e.b(False))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )
    # A parameter slot: the under type's binding over it, tracked like a bound owned value.
    x.append(
        e.impl_interface(
            e.v("owned"),
            e.mb.eval_aspect_initial_bind(),
            p(
                "initial_bind",
                body(
                    e,
                    e.let("ui", lookup(e, xx(e), in_(e, "under"), e.mb.eval_aspect_initial_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ui"), "is_some")),
                        ret_m(
                            e,
                            e.eresult_err(
                                _binding_t(e),
                                loc(e),
                                e.cat(e.s("owned: "), ty_desc(e, in_(e, "under")), e.s(" cannot be a parameter")),
                            ),
                        ),
                    ),
                    e.let(
                        "r",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_initial_bind(),
                                "initial_bind",
                                e.fld(e.v("ui"), "value"),
                                _rec_xl(e, p("slot", a(e, "slot"))),
                            ),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(e.eresult_ok(_binding_t(e), _obinding(e, e.v("r"), outer(e), e.b(False)))),
                ),
            ),
        )
    )
    # Dropping an owned value held outside a binding (a temporary) destroys it.
    x.append(
        e.impl_interface(
            e.v("owned"),
            e.mb.eval_aspect_drop_dynamic(),
            p(
                "drop",
                body(
                    e,
                    e.let("c1", _destroy_m(e, outer(e), a(e, "cv"), code_t(e))),
                    e.let("v", _retag_m(e, a(e, "cv"), in_(e, "under"), code_t(e))),
                    e.let("c2", unwrap_m(e, _drop_value(e, e.v("v")), code_t(e))),
                    e.ret(e.eresult_ok(code_t(e), _cat_m(e, e.v("c1"), e.v("c2"), code_t(e)))),
                ),
            ),
        )
    )


def _obinding_impl(e, x):
    x.append(
        e.impl_interface(
            e.v("obinding"),
            _binding_t(e),
            p(
                "use",
                _retag_v(
                    e,
                    _binding_use(
                        e,
                        in_(e, "inner"),
                        mk(
                            e,
                            "osetter",
                            p("setter", a(e, "setter")),
                            p("owned", in_(e, "owned")),
                            p("moved", in_(e, "moved")),
                        ),
                        a(e, "code"),
                    ),
                    mk(
                        e,
                        "oref",
                        p("owned", in_(e, "owned")),
                        p("inner", in_(e, "inner")),
                        p("setter", a(e, "setter")),
                        p("moved", in_(e, "moved")),
                    ),
                ),
            ),
            p(
                "drop",
                body(
                    e,
                    e.if_only(in_(e, "moved"), ret_m(e, e.eresult_ok(code_t(e), code_none(e, loc(e))))),
                    e.let("cv", _binding_use(e, in_(e, "inner"), _consumed(e), code_none(e, loc(e)))),
                    e.let("c1", _destroy_m(e, in_(e, "owned"), e.v("cv"), code_t(e))),
                    e.let("c2", unwrap_m(e, bim(e, _binding_t(e), "drop", in_(e, "inner"), _rec_xl(e)), code_t(e))),
                    e.ret(e.eresult_ok(code_t(e), _cat_m(e, e.v("c1"), e.v("c2"), code_t(e)))),
                ),
            ),
            p("fork", _obinding(e, bim0(e, _binding_t(e), "fork", in_(e, "inner")), in_(e, "owned"), in_(e, "moved"))),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.seq(
                            e.let("ob", reinterpret(e, e.v("o"), "obinding")),
                            e.if_only(
                                e.not_(e.eq(e.call_m(e.v("ob"), "moved", e.tup()), in_(e, "moved"))),
                                ret_m(
                                    e,
                                    e.eresult_err(
                                        _binding_t(e), loc(e), e.s("owned value moved in some branches but not others")
                                    ),
                                ),
                            ),
                            e.push(e.v("inners"), e.call_m(e.v("ob"), "inner", e.tup())),
                        ),
                    ),
                    e.let(
                        "m",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "inner"), _rec_xl(e, p("others", e.v("inners")))),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(e.eresult_ok(_binding_t(e), _obinding(e, e.v("m"), in_(e, "owned"), in_(e, "moved")))),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("osetter"),
            _setter_t(e),
            p(
                "set",
                _setter_set(
                    e,
                    in_(e, "setter"),
                    _obinding(e, a(e, "new_binding"), in_(e, "owned"), in_(e, "moved")),
                    a(e, "drop_modified"),
                ),
            ),
        )
    )


def _oref(e, x):
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v("oref"),
            t(e, "oref_m"),
            p("owned", in_(e, "owned")),
            p("inner", in_(e, "inner")),
            p("setter", in_(e, "setter")),
            p("moved", in_(e, "moved")),
        )
    )
    self_type(
        e,
        x,
        "oref",
        e.cat(e.s("reference to "), ty_desc(e, in_(e, "owned"))),
        _dispatch(
            e,
            [
                asp_id(e, "field"),
                asp_id(e, "set"),
                e.mb.eval_aspect_drop_dynamic_id(),
                asp_id(e, "bind"),
                lv(e, "oref_m_id"),
            ],
            e.if_else(
                in_(e, "moved"), e.opt_none(e.mb.types_aspect()), type_aspect(e, xx(e), _ref_under(e), a(e, "key"))
            ),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        e.if_else(
            in_(e, "moved"),
            e.mb.as_(e.b(True), bool_t(e)),
            bim(e, e.mb.eval_type(), "can_cast_to", _ref_under(e), _rec_xl(e, p("dest_type", a(e, "dest_type")))),
        ),
        body(
            e,
            e.if_only(in_(e, "moved"), ret_m(e, err_cve(e, loc(e), "use of a moved owned value"))),
            e.let("v", _retag_m(e, a(e, "cv"), _ref_under(e), cve_t(e))),
            e.ret(
                bim(
                    e,
                    e.mb.eval_type(),
                    "cast_to",
                    _ref_under(e),
                    _rec_xl(e, p("cv", e.v("v")), p("dest_type", a(e, "dest_type"))),
                )
            ),
        ),
        e.if_else(in_(e, "moved"), e.mb.as_(e.b(False), bool_t(e)), is_equal(e, xx(e), _ref_under(e), a(e, "other"))),
    )
    x.append(
        e.impl_interface(
            e.v("oref"),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(in_(e, "moved"), ret_m(e, err_cve(e, loc(e), "use of a moved owned value"))),
                    e.if_only(
                        and_b(
                            e,
                            has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                            e.eq(_const_str(e, a(e, "key")), e.s("move")),
                        ),
                        ret_m(
                            e,
                            ok_cve(
                                e,
                                cv_of(
                                    e,
                                    code_none(e, loc(e)),
                                    e.call(
                                        e.eval_builtin("value_object_const"),
                                        e.rec(
                                            p("type", mk(e, "omove", p("ref", outer(e)), p("self", a(e, "self")))),
                                            p("data", e.tup()),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    e.let("uf", lookup(e, xx(e), _ref_under(e), asp_iface(e, "field"))),
                    e.if_only(
                        e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, err_cve(e, loc(e), "owned value has no fields"))
                    ),
                    e.let("v", _retag_m(e, a(e, "self"), _ref_under(e), cve_t(e))),
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "field",
                            e.fld(e.v("uf"), "value"),
                            _rec_xl(e, p("self", e.v("v")), p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            p(
                "type_opt",
                body(
                    e,
                    e.let("uf", lookup(e, xx(e), _ref_under(e), asp_iface(e, "field"))),
                    e.if_only(e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, e.option_type_lowered_none())),
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "type_opt",
                            e.fld(e.v("uf"), "value"),
                            e.rec(p("xx", xx(e)), p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            # keys takes the context alone, so here `arg` is the context.
            p(
                "keys",
                body(
                    e,
                    e.let("uf", lookup(e, e.v("arg"), _under_x(e, e.v("arg"), in_(e, "owned")), asp_iface(e, "field"))),
                    e.if_only(e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, e.list_new(e.mb.types_constkey()))),
                    e.ret(bim(e, asp_iface(e, "field"), "keys", e.fld(e.v("uf"), "value"), e.v("arg"))),
                ),
            ),
        )
    )
    # Assigning an owned value: evaluate it, destroy the current value (unless moved), store, and mark live.
    x.append(
        e.impl_interface(
            e.v("oref"),
            e.mb.eval_aspect_set(),
            p(
                "set",
                body(
                    e,
                    e.if_only(
                        e.not_(cve_has(e, a(e, "value"))),
                        ret_m(e, err_cve(e, loc(e), "assigned expression has no value")),
                    ),
                    e.if_only(
                        e.not_(is_equal(e, xx(e), in_(e, "owned"), cve_type(e, a(e, "value")))),
                        ret_m(
                            e,
                            err_cve(
                                e,
                                loc(e),
                                e.cat(e.s("only an "), ty_desc(e, in_(e, "owned")), e.s(" value can be assigned here")),
                            ),
                        ),
                    ),
                    e.let("ub", lookup(e, xx(e), _ref_under(e), e.mb.eval_aspect_bind())),
                    e.if_only(
                        e.not_(e.fld(e.v("ub"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "owned value cannot be stored")),
                    ),
                    e.let("us", lookup(e, xx(e), _ref_under(e), e.mb.eval_aspect_set())),
                    e.if_only(
                        e.not_(e.fld(e.v("us"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "owned value is not assignable")),
                    ),
                    e.let("nv", _retag_m(e, a(e, "value"), _ref_under(e), cve_t(e))),
                    e.let(
                        "br",
                        unwrap_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_bind(),
                                "bind",
                                e.fld(e.v("ub"), "value"),
                                _rec_xl(e, p("cv", e.v("nv"))),
                            ),
                            cve_t(e),
                        ),
                    ),
                    e.let("tmp", _binding_use(e, e.fld(e.v("br"), "binding"), _consumed(e), code_none(e, loc(e)))),
                    e.let(
                        "c2",
                        e.if_else(
                            in_(e, "moved"),
                            code_none(e, loc(e)),
                            _destroy_m(e, in_(e, "owned"), a(e, "self"), cve_t(e)),
                        ),
                    ),
                    e.let("sv", _retag_m(e, a(e, "self"), _ref_under(e), cve_t(e))),
                    e.let(
                        "r",
                        unwrap_cve_m(
                            e,
                            bim(
                                e,
                                e.mb.eval_aspect_set(),
                                "set",
                                e.fld(e.v("us"), "value"),
                                _rec_xl(e, p("self", e.v("sv")), p("value", e.v("tmp"))),
                            ),
                        ),
                    ),
                    e.if_only(
                        in_(e, "moved"),
                        e.seq(
                            e.let(
                                "__live",
                                _setter_set(
                                    e,
                                    in_(e, "setter"),
                                    _obinding(e, in_(e, "inner"), in_(e, "owned"), e.b(False)),
                                    e.b(True),
                                ),
                            )
                        ),
                    ),
                    e.let("c12", _cat_m(e, e.fld(e.v("br"), "code"), e.v("c2"), cve_t(e))),
                    e.ret(ok_cve(e, cv_no(e, _cat_m(e, e.v("c12"), cve_code(e, e.v("r")), cve_t(e))))),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("oref"),
            e.mb.eval_aspect_bind(),
            p("bind", e.eresult_err(br_t, loc(e), e.s("a reference to an owned value cannot be bound; move() it"))),
        )
    )
    x.append(
        e.impl_interface(
            e.v("oref"), e.mb.eval_aspect_drop_dynamic(), p("drop", e.eresult_ok(code_t(e), code_none(e, loc(e))))
        )
    )
    # `.move()`: a callable whose type carries the reference; calling it yields the owned value and marks the
    # binding moved.
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        "omove",
        e.s("owned move"),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )
    x.append(
        e.impl_interface(
            e.v("omove"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("r", in_(e, "ref")),
                    e.if_only(
                        acc(e, xx(e), e.v("r"), "oref_m", "moved"),
                        ret_m(e, err_cve(e, loc(e), "owned value already moved")),
                    ),
                    e.let("owned", acc(e, xx(e), e.v("r"), "oref_m", "owned")),
                    e.let(
                        "__moved",
                        _setter_set(
                            e,
                            acc(e, xx(e), e.v("r"), "oref_m", "setter"),
                            _obinding(e, acc(e, xx(e), e.v("r"), "oref_m", "inner"), e.v("owned"), e.b(True)),
                            e.b(True),
                        ),
                    ),
                    e.ret(ok_cve(e, _retag_m(e, in_(e, "self"), e.v("owned"), cve_t(e)))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def _octor(e, x):
    """`destructor.type`: a const function taking `{under, destroy}` as its call argument (so `destroy` may be any
    target function value) and yielding the owned type."""
    const_fn(
        e,
        x,
        "octor_b",
        "destructor.type",
        body(
            e,
            e.let("argv", a(e, "argument")),
            e.if_only(
                e.not_(cve_has(e, e.v("argv"))),
                ret_m(e, err_cve(e, loc(e), "destructor.type: argument has no value")),
            ),
            e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
            e.if_only(
                e.not_(e.fld(e.v("rk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "destructor.type: argument must be {under, destroy}")),
            ),
            e.let(
                "fields",
                bim(
                    e,
                    asp_iface(e, "record"),
                    "take_fields",
                    e.fld(e.v("rk"), "value"),
                    _rec_xl(e, p("value", cve_value(e, e.v("argv")))),
                ),
            ),
            e.let("undercv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("under")))),
            e.let("destroy", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("destroy")))),
            e.if_only(
                e.not_(cve_has(e, e.v("undercv"))),
                ret_m(e, err_cve(e, loc(e), "destructor.type: under has no value")),
            ),
            e.if_only(
                e.not_(cve_has(e, e.v("destroy"))),
                ret_m(e, err_cve(e, loc(e), "destructor.type: destroy has no value")),
            ),
            # The owned type is made where the caller runs (its destroy function may be a value of the
            # caller's runtime), so the construction is staged with the inputs grafted in.
            e.let("owned_new", e.lower(e.fld(e.v("owned"), "new"))),
            e.let("dt", cve_type(e, e.v("destroy"))),
            e.ret(
                e.eresult_ok(
                    cve_t(e),
                    unwrap_cve_m(
                        e,
                        const_eval_in(
                            e,
                            xx(e),
                            e.stage(
                                e.mb.as_(
                                    e.call(
                                        e.lower(e.v("owned_new")),
                                        e.rec(
                                            p("under", graft(e, e.v("undercv"))),
                                            # The lifted form of the runtime function value: its type over
                                            # the target's host object.
                                            p(
                                                "destroy",
                                                e.call(
                                                    e.eval_builtin("value_object_const"),
                                                    e.rec(
                                                        p("type", e.lower(e.v("dt"))),
                                                        p(
                                                            "data",
                                                            e.call(
                                                                e.mb.must_reinterpret(),
                                                                e.tup(
                                                                    graft(e, e.v("destroy")),
                                                                    e.mb.builtin("types", "object"),
                                                                ),
                                                            ),
                                                        ),
                                                    ),
                                                ),
                                            ),
                                        ),
                                    ),
                                    e.mb.eval_type(),
                                )
                            ),
                        ),
                    ),
                )
            ),
        ),
    )


def module(e):
    x = []
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(e, x, "owned_m", p("under", ty(e)), p("destroy", voc_t(e)))
    def_iface(
        e,
        x,
        "oref_m",
        p("owned", ty(e)),
        p("inner", _binding_t(e)),
        p("setter", _setter_t(e)),
        p("moved", bool_t(e)),
    )
    def_obj(e, x, "owned", "owned type", e.rec(p("under", ty(e)), p("destroy", voc_t(e))))
    def_obj(
        e, x, "obinding", "owned binding", e.rec(p("inner", _binding_t(e)), p("owned", ty(e)), p("moved", bool_t(e)))
    )
    def_obj(
        e,
        x,
        "osetter",
        "owned binding setter",
        e.rec(p("setter", _setter_t(e)), p("owned", ty(e)), p("moved", bool_t(e))),
    )
    def_obj(
        e,
        x,
        "oref",
        "owned reference type",
        e.rec(p("owned", ty(e)), p("inner", _binding_t(e)), p("setter", _setter_t(e)), p("moved", bool_t(e))),
    )
    def_obj(e, x, "omove", "owned move", e.rec(p("ref", ty(e)), p("self", cve_t(e))))
    for f, ft in [("inner", _binding_t(e)), ("moved", bool_t(e))]:
        x.append(e.method_impl(e.v("obinding"), f, e.tup(), e.option_type_some(ft), e.stage(in_(e, f))))
    _host_fns(e, x)
    _owned(e, x)
    _obinding_impl(e, x)
    _oref(e, x)
    _octor(e, x)
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("octor_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
