"""readonly.atz: read-only and sealed-after-init wrappers over any runtime type.

`readonly.type(T)` is `T` whose values cannot be assigned: `set` on a read-only value is a compile error, everything
else (fields, calls, operators, conversions to `T`) behaves as `T`. It is shallow, like Java's `final`: a field read
yields the plain field value. Bindings of a read-only value keep it read-only when loaded.

`readonly.sealed(T)` is `T` that may be assigned until it is sealed: loading a sealed binding yields a reference that
acts as `T`; `set` through it assigns until `.seal()` is called on it, after which `set` is a compile error. Sealing
is a compile-time state of the binding, so a binding sealed in some branches but not others is a compile error.

Both have the runtime representation of `T` (retagged values).
"""

from ..core import values
from ..eco_mb import p
from ..target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    body,
    bool_t,
    cast_to_panic,
    cast_value,
    code_none,
    code_t,
    cv_no,
    cv_of,
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
    has,
    has_b,
    hf_rec,
    in_,
    is_equal,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    must_v,
    ok_cve,
    or_b,
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
    type_can_cast_from,
    unwrap_m,
    xx,
)

FILE = "readonly.atz"

TARGET = "readonly"


def _binding_t(e):
    return e.mb.eval_binding()


def _setter_t(e):
    return e.mb.builtin("eval", "binding_setter")


def _rec_xl(e, *fields):
    return e.rec(p("xx", xx(e)), p("loc", loc(e)), *fields)


def _retag(e, cv, type_):
    return hf_rec(e, "h_retag", p("xx", xx(e)), p("loc", loc(e)), p("cv", cv), p("type", type_))


def _retag_v(e, cv, type_):
    return must_v(e, TARGET, try_er(e, _retag(e, cv, type_), cve_t(e)), "retag binding value")


def _retag_m(e, cv, type_, ret_inner):
    return unwrap_m(e, try_er(e, _retag(e, cv, type_), cve_t(e)), ret_inner)


def _setter_set(e, setter, binding, drop_modified):
    return bim(e, _setter_t(e), "set", setter, _rec_xl(e, p("new_binding", binding), p("drop_modified", drop_modified)))


def _binding_use(e, binding, setter, code):
    return bim(e, _binding_t(e), "use", binding, _rec_xl(e, p("setter", setter), p("code", code)))


def _dispatch(e, own_ids, fallback):
    branches = []
    for id_ in own_ids:
        branches.append((e.eq(a(e, "key"), id_), e.opt_some(e.mb.types_aspect(), outer(e))))
    return e.mb.if_of(branches, fallback)


def _const_str(e, cv):
    return bim(
        e,
        e.mb.eval_aspect_string_const(),
        "get",
        lookup_v(e, xx(e), cve_type(e, cv), e.mb.eval_aspect_string_const()),
        cve_value(e, cv),
    )


def _host_fns(e, x):
    fn_def(
        e,
        x,
        TARGET,
        "h_retag",
        e.rec(p("xx", e.types_expr_context()), p("loc", e.types_loc()), p("cv", cve_t(e)), p("type", ty(e))),
        cve_t(e),
    )
    fn_throws(e, "h_retag", errs_t(e))
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
                        e.call(
                            e.mb.eval_codevalue(),
                            e.rec(
                                p("code", e.fld(a(e, "cv"), "code")),
                                p(
                                    "value",
                                    e.call(
                                        e.eval_builtin("value_dynamic"),
                                        e.rec(p("source", e.fld(e.v("__d"), "source")), p("type", a(e, "type"))),
                                    ),
                                ),
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
                        e.call(
                            e.mb.eval_codevalue(),
                            e.rec(
                                p("code", e.fld(a(e, "cv"), "code")),
                                p(
                                    "value",
                                    bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), a(e, "type")),
                                ),
                            ),
                        ),
                    ),
                ),
                p("errs", throw_err(e, loc(e), "readonly: only runtime values can be wrapped")),
            ),
        ),
    )


# ---- shared pieces for a wrapper type over `under()` -------------------------------------------------------------


def _wrapper_casts(e, under):
    """can_cast_from / cast_from / can_cast_to / cast_to for a wrapper that reads as `under`."""
    return [
        # An `under` value casts to the wrapper (wrapping it); a wrapped value is its own type.
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    type_can_cast_from(e, xx(e), loc(e), under(), a(e, "source_type")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(e.not_(cve_has(e, a(e, "cv"))), ret_m(e, err_cve(e, loc(e), "cast source has no value"))),
            e.let("v", unwrap_m(e, cast_value(e, xx(e), loc(e), under(), a(e, "cv")), cve_t(e))),
            e.ret(ok_cve(e, _retag_m(e, e.v("v"), outer(e), cve_t(e)))),
        ),
        # A wrapped value converts to `under` itself (unwrapping it: the wrapper's identity is its own, so the under
        # type does not take the wrapped value for its own) and to whatever `under` converts to.
        e.if_else(
            or_b(
                e,
                is_equal(e, xx(e), outer(e), a(e, "dest_type")),
                is_equal(e, xx(e), under(), a(e, "dest_type")),
            ),
            e.mb.as_(e.b(True), bool_t(e)),
            bim(e, e.mb.eval_type(), "can_cast_to", under(), _rec_xl(e, p("dest_type", a(e, "dest_type")))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), a(e, "dest_type")), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let("v", _retag_m(e, a(e, "cv"), under(), cve_t(e))),
            e.if_only(is_equal(e, xx(e), under(), a(e, "dest_type")), ret_m(e, ok_cve(e, e.v("v")))),
            e.ret(
                bim(
                    e,
                    e.mb.eval_type(),
                    "cast_to",
                    under(),
                    _rec_xl(e, p("cv", e.v("v")), p("dest_type", a(e, "dest_type"))),
                )
            ),
        ),
    ]


def _under_drop(e, x, obj):
    """Dropping a wrapped value outside a binding drops the `under` value."""
    x.append(
        e.impl_interface(
            e.v(obj),
            e.mb.eval_aspect_drop_dynamic(),
            p(
                "drop",
                body(
                    e,
                    e.let("v", _retag_m(e, a(e, "cv"), in_(e, "under"), code_t(e))),
                    e.ret(e.call(e.mb.eval_drop_value(), _rec_xl(e, p("cv", e.v("v"))))),
                ),
            ),
        )
    )


def _bind_wrapping(e, x, obj, label, make_binding):
    """`bind` and `initial_bind`: the under type's binding, wrapped by `make_binding(inner_binding_expr)`."""
    br_t = e.mb.types_bind_result()
    x.append(
        e.impl_interface(
            e.v(obj),
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
                                e.cat(e.s(label + ": "), ty_desc(e, in_(e, "under")), e.s(" cannot be bound")),
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
                                    p("binding", make_binding(e.fld(e.v("r"), "binding"))),
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
            e.v(obj),
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
                                e.cat(e.s(label + ": "), ty_desc(e, in_(e, "under")), e.s(" cannot be a parameter")),
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
                    e.ret(e.eresult_ok(_binding_t(e), make_binding(e.v("r")))),
                ),
            ),
        )
    )


def _ref_field(e, x, obj, under, under_x, extra=None):
    """Field access on a wrapper value: the `under` type's field aspect over the retagged value; `extra` may answer
    a key first (host statements ending the method with a return)."""
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    *(extra or []),
                    e.let("uf", lookup(e, xx(e), under(), asp_iface(e, "field"))),
                    e.if_only(
                        e.not_(e.fld(e.v("uf"), "is_some")),
                        ret_m(e, err_cve(e, loc(e), "the value has no fields")),
                    ),
                    e.let("v", _retag_m(e, a(e, "value"), under(), cve_t(e))),
                    e.ret(
                        bim(
                            e,
                            asp_iface(e, "field"),
                            "field",
                            e.fld(e.v("uf"), "value"),
                            _rec_xl(e, p("value", e.v("v")), p("key", a(e, "key"))),
                        )
                    ),
                ),
            ),
            p(
                "type_opt",
                body(
                    e,
                    e.let("uf", lookup(e, xx(e), under(), asp_iface(e, "field"))),
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
                    e.let("uf", lookup(e, e.v("arg"), under_x(e.v("arg")), asp_iface(e, "field"))),
                    e.if_only(e.not_(e.fld(e.v("uf"), "is_some")), ret_m(e, e.list_new(e.mb.types_constkey()))),
                    e.ret(bim(e, asp_iface(e, "field"), "keys", e.fld(e.v("uf"), "value"), e.v("arg"))),
                ),
            ),
        )
    )


def _plain_binding(e, x, obj, setter_obj, wrap_type, make):
    """A binding wrapping the under binding whose loads are retagged to `wrap_type()`; `make(inner)` rebuilds it."""
    x.append(
        e.impl_interface(
            e.v(obj),
            _binding_t(e),
            p(
                "use",
                _retag_v(
                    e,
                    _binding_use(
                        e,
                        in_(e, "inner"),
                        mk(e, setter_obj, p("setter", a(e, "setter")), p("ty", wrap_type())),
                        a(e, "code"),
                    ),
                    wrap_type(),
                ),
            ),
            p("drop", bim(e, _binding_t(e), "drop", in_(e, "inner"), _rec_xl(e))),
            p("fork", make(bim0(e, _binding_t(e), "fork", in_(e, "inner")))),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.push(e.v("inners"), e.call_m(reinterpret(e, e.v("o"), obj), "inner", e.tup())),
                    ),
                    e.let(
                        "m",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "inner"), _rec_xl(e, p("others", e.v("inners")))),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(e.eresult_ok(_binding_t(e), make(e.v("m")))),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v(setter_obj),
            _setter_t(e),
            p(
                "set",
                _setter_set(
                    e,
                    in_(e, "setter"),
                    mk(e, obj, p("inner", a(e, "new_binding")), p("ty", in_(e, "ty"))),
                    a(e, "drop_modified"),
                ),
            ),
        )
    )


# ---- read-only ---------------------------------------------------------------------------------------------------


def _ro(e, x):
    def under():
        return in_(e, "under")

    x.append(e.impl_interface(e.v("ro"), t(e, "ro_m"), p("under", under())))
    self_type(
        e,
        x,
        "ro",
        e.cat(e.s("read-only "), ty_desc(e, under())),
        _dispatch(
            e,
            [
                asp_id(e, "set"),
                asp_id(e, "field"),
                asp_id(e, "bind"),
                asp_id(e, "initial_bind"),
                e.mb.eval_aspect_drop_dynamic_id(),
                lv(e, "ro_m_id"),
            ],
            type_aspect(e, xx(e), under(), a(e, "key")),
        ),
        *_wrapper_casts(e, under),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ro_m"),
                    is_equal(e, xx(e), under(), acc(e, xx(e), a(e, "other"), "ro_m", "under")),
                )
            ),
        ),
    )
    x.append(
        e.impl_interface(
            e.v("ro"),
            e.mb.eval_aspect_set(),
            p("set", err_cve(e, loc(e), e.cat(e.s("read-only "), ty_desc(e, under()), e.s(" cannot be assigned")))),
        )
    )
    _ref_field(e, x, "ro", under, lambda xx_: in_(e, "under"))
    _under_drop(e, x, "ro")
    _bind_wrapping(e, x, "ro", "readonly", lambda inner: mk(e, "rob", p("inner", inner), p("ty", outer(e))))
    _plain_binding(
        e,
        x,
        "rob",
        "robsetter",
        lambda: in_(e, "ty"),
        lambda inner: mk(e, "rob", p("inner", inner), p("ty", in_(e, "ty"))),
    )


# ---- sealed ------------------------------------------------------------------------------------------------------


def _sb(e, inner, sealed, done):
    return mk(e, "sb", p("inner", inner), p("sealed", sealed), p("done", done))


def _sealed(e, x):
    def under():
        return in_(e, "under")

    x.append(e.impl_interface(e.v("sealed"), t(e, "sealed_m"), p("under", under())))
    self_type(
        e,
        x,
        "sealed",
        e.cat(e.s("sealed "), ty_desc(e, under())),
        _dispatch(
            e,
            [
                asp_id(e, "bind"),
                asp_id(e, "initial_bind"),
                e.mb.eval_aspect_drop_dynamic_id(),
                lv(e, "sealed_m_id"),
            ],
            type_aspect(e, xx(e), under(), a(e, "key")),
        ),
        *_wrapper_casts(e, under),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "sealed_m"),
                    is_equal(e, xx(e), under(), acc(e, xx(e), a(e, "other"), "sealed_m", "under")),
                )
            ),
        ),
    )
    _under_drop(e, x, "sealed")
    _bind_wrapping(e, x, "sealed", "sealed", lambda inner: _sb(e, inner, outer(e), e.b(False)))
    # the binding: loads yield a reference that knows whether the binding is sealed
    x.append(
        e.impl_interface(
            e.v("sb"),
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
                            "sbsetter",
                            p("setter", a(e, "setter")),
                            p("sealed", in_(e, "sealed")),
                            p("done", in_(e, "done")),
                        ),
                        a(e, "code"),
                    ),
                    mk(
                        e,
                        "sref",
                        p("sealed", in_(e, "sealed")),
                        p("inner", in_(e, "inner")),
                        p("setter", a(e, "setter")),
                        p("done", in_(e, "done")),
                    ),
                ),
            ),
            p("drop", bim(e, _binding_t(e), "drop", in_(e, "inner"), _rec_xl(e))),
            p("fork", _sb(e, bim0(e, _binding_t(e), "fork", in_(e, "inner")), in_(e, "sealed"), in_(e, "done"))),
            p(
                "merge",
                body(
                    e,
                    e.let("inners", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.seq(
                            e.let("ob", reinterpret(e, e.v("o"), "sb")),
                            e.if_only(
                                e.not_(e.eq(e.call_m(e.v("ob"), "done", e.tup()), in_(e, "done"))),
                                ret_m(
                                    e,
                                    e.eresult_err(
                                        _binding_t(e), loc(e), e.s("value sealed in some branches but not others")
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
                    e.ret(e.eresult_ok(_binding_t(e), _sb(e, e.v("m"), in_(e, "sealed"), in_(e, "done")))),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("sbsetter"),
            _setter_t(e),
            p(
                "set",
                _setter_set(
                    e,
                    in_(e, "setter"),
                    _sb(e, a(e, "new_binding"), in_(e, "sealed"), in_(e, "done")),
                    a(e, "drop_modified"),
                ),
            ),
        )
    )

    # the reference: acts as `under`; `set` assigns until sealed; `.seal()` seals the binding
    def runder():
        return acc(e, xx(e), in_(e, "sealed"), "sealed_m", "under")

    x.append(
        e.impl_interface(
            e.v("sref"),
            t(e, "sref_m"),
            p("sealed", in_(e, "sealed")),
            p("inner", in_(e, "inner")),
            p("setter", in_(e, "setter")),
            p("done", in_(e, "done")),
        )
    )
    self_type(
        e,
        x,
        "sref",
        e.cat(e.s("reference to "), ty_desc(e, in_(e, "sealed"))),
        _dispatch(
            e,
            [
                asp_id(e, "set"),
                asp_id(e, "field"),
                e.mb.eval_aspect_drop_dynamic_id(),
                asp_id(e, "bind"),
                lv(e, "sref_m_id"),
            ],
            type_aspect(e, xx(e), runder(), a(e, "key")),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        bim(e, e.mb.eval_type(), "can_cast_to", runder(), _rec_xl(e, p("dest_type", a(e, "dest_type")))),
        body(
            e,
            e.let("v", _retag_m(e, a(e, "cv"), runder(), cve_t(e))),
            e.ret(
                bim(
                    e,
                    e.mb.eval_type(),
                    "cast_to",
                    runder(),
                    _rec_xl(e, p("cv", e.v("v")), p("dest_type", a(e, "dest_type"))),
                )
            ),
        ),
        is_equal(e, xx(e), runder(), a(e, "other")),
    )
    _ref_field(
        e,
        x,
        "sref",
        runder,
        lambda xx_: acc(e, xx_, in_(e, "sealed"), "sealed_m", "under"),
        extra=[
            e.if_only(
                and_b(
                    e,
                    has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                    e.eq(_const_str(e, a(e, "key")), e.s("seal")),
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
                                    p("type", mk(e, "sseal", p("ref", outer(e)), p("self", a(e, "value")))),
                                    p("data", e.tup()),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        ],
    )
    x.append(
        e.impl_interface(
            e.v("sref"),
            e.mb.eval_aspect_set(),
            p(
                "set",
                body(
                    e,
                    e.if_only(
                        in_(e, "done"),
                        ret_m(
                            e,
                            err_cve(e, loc(e), e.cat(e.s("sealed "), ty_desc(e, runder()), e.s(" cannot be assigned"))),
                        ),
                    ),
                    e.if_only(
                        e.not_(cve_has(e, a(e, "value"))),
                        ret_m(e, err_cve(e, loc(e), "assigned expression has no value")),
                    ),
                    e.let("us", lookup(e, xx(e), runder(), e.mb.eval_aspect_set())),
                    e.if_only(
                        e.not_(e.fld(e.v("us"), "is_some")), ret_m(e, err_cve(e, loc(e), "the value is not assignable"))
                    ),
                    e.let("nv", unwrap_m(e, cast_value(e, xx(e), loc(e), runder(), a(e, "value")), cve_t(e))),
                    e.let("sv", _retag_m(e, a(e, "target"), runder(), cve_t(e))),
                    e.ret(
                        bim(
                            e,
                            e.mb.eval_aspect_set(),
                            "set",
                            e.fld(e.v("us"), "value"),
                            _rec_xl(e, p("target", e.v("sv")), p("value", e.v("nv"))),
                        )
                    ),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("sref"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                e.eresult_err(
                    e.mb.types_bind_result(),
                    loc(e),
                    e.s("a reference to a sealed binding cannot be bound; convert it to its type"),
                ),
            ),
        )
    )
    x.append(
        e.impl_interface(
            e.v("sref"), e.mb.eval_aspect_drop_dynamic(), p("drop", e.eresult_ok(code_t(e), code_none(e, loc(e))))
        )
    )
    # `.seal()`: marks the binding sealed; yields no value.
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        "sseal",
        e.s("seal"),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )
    x.append(
        e.impl_interface(
            e.v("sseal"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    e.let("r", in_(e, "ref")),
                    e.let(
                        "__s",
                        _setter_set(
                            e,
                            acc(e, xx(e), e.v("r"), "sref_m", "setter"),
                            _sb(
                                e,
                                acc(e, xx(e), e.v("r"), "sref_m", "inner"),
                                acc(e, xx(e), e.v("r"), "sref_m", "sealed"),
                                e.b(True),
                            ),
                            e.b(True),
                        ),
                    ),
                    e.ret(ok_cve(e, cv_no(e, code_none(e, loc(e))))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def module(e):
    x = []
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    def_iface(e, x, "ro_m", p("under", ty(e)))
    def_iface(e, x, "sealed_m", p("under", ty(e)))
    def_iface(
        e, x, "sref_m", p("sealed", ty(e)), p("inner", _binding_t(e)), p("setter", _setter_t(e)), p("done", bool_t(e))
    )
    def_obj(e, x, "ro", "read-only type", e.rec(p("under", ty(e))))
    def_obj(e, x, "rob", "read-only binding", e.rec(p("inner", _binding_t(e)), p("ty", ty(e))))
    def_obj(e, x, "robsetter", "read-only binding setter", e.rec(p("setter", _setter_t(e)), p("ty", ty(e))))
    def_obj(e, x, "sealed", "sealed type", e.rec(p("under", ty(e))))
    def_obj(e, x, "sb", "sealed binding", e.rec(p("inner", _binding_t(e)), p("sealed", ty(e)), p("done", bool_t(e))))
    def_obj(
        e,
        x,
        "sbsetter",
        "sealed binding setter",
        e.rec(p("setter", _setter_t(e)), p("sealed", ty(e)), p("done", bool_t(e))),
    )
    def_obj(
        e,
        x,
        "sref",
        "sealed reference type",
        e.rec(p("sealed", ty(e)), p("inner", _binding_t(e)), p("setter", _setter_t(e)), p("done", bool_t(e))),
    )
    def_obj(e, x, "sseal", "seal", e.rec(p("ref", ty(e)), p("self", cve_t(e))))
    x.append(e.method_impl(e.v("rob"), "inner", e.tup(), e.option_type_some(_binding_t(e)), e.stage(in_(e, "inner"))))
    for f, ft in [("inner", _binding_t(e)), ("done", bool_t(e))]:
        x.append(e.method_impl(e.v("sb"), f, e.tup(), e.option_type_some(ft), e.stage(in_(e, f))))
    _host_fns(e, x)
    _ro(e, x)
    _sealed(e, x)
    fn_def(e, x, TARGET, "c_ro", ty(e), ty(e))
    fn_impl(e, x, "c_ro", body(e, e.ret(e.mb.as_(mk(e, "ro", p("under", e.v("arg"))), ty(e)))))
    fn_def(e, x, TARGET, "c_sealed", ty(e), ty(e))
    fn_impl(e, x, "c_sealed", body(e, e.ret(e.mb.as_(mk(e, "sealed", p("under", e.v("arg"))), ty(e)))))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("c_ro_b"), "func")), p("sealed", e.fld(e.v("c_sealed_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")), p("sealed", e.fld(e.v("k"), "sealed")))))
    return top
