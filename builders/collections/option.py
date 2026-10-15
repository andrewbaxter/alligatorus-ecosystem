"""option-wasm.atz / option-llvm.atz: a value that is either `some(v)` or `none`, one module per target from this
builder.

`option.type(elem)` yields `{type, some, none, of}` for a constant element type `elem` without a destructor. An
option is the target's tuple `(i32, elem)` (the tag, zero for none, and the payload, a zero of `elem` when none)
viewed as its own type: it binds, is assigned, passed and returned exactly like that tuple, but exposes no
components. `some(v)`, `none(())` and `of((tag, v))` are function values, the empty values of constructor types (returned too,
as `some_t`, `none_t` and `of_t`, for types that carry them); modules hold them in lowered setup blocks and bodies
lower them. An option is read with `match`: the type implements `eval.aspect_union` (variants
`some` with the payload and `none` with the target's unit), whose `test` compares the tag and whose `extract` yields
the payload for the case to bind.
"""

from ..core import values
from ..eco_mb import p
from ..target_mb import (
    cast_from_empty,
    can_cast_from_unit,
    fn_of,
    a,
    acc,
    and_b,
    asp_id,
    bim,
    body,
    cast_to_panic,
    cast_value,
    code_none,
    code_seq,
    const_eval_in,
    const_fn,
    cv_of,
    cve_code,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    graft,
    has,
    has_b,
    in_,
    is_equal,
    loc,
    lv,
    mk,
    no_cast_to,
    ok_cve,
    or_b,
    outer,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    str_,
    t,
    ty,
    ty_desc,
    type_aspect,
    unwrap_cve_m,
    unwrap_m,
    xx,
)
from .vec import const_type_arg

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "option-wasm.atz", LLVM: "option-llvm.atz"}

KINDS = ["some", "none", "of"]
# What an option type carries: the element type, i32 (the tag), the target's unit (the payload type of `none`) and
# the pair tuple type `(i32, elem)` the option is a view of.
BASE = ["elem", "i32", "unit", "pt"]
SOME = 0


class _Target:
    """What differs between the wasm and llvm modules: the import."""

    def __init__(self, kind):
        self.kind = kind

    def imports(self, e, out):
        if self.kind == WASM:
            out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
        else:
            out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))


def _staged(e, expr):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(expr)))


def _codes(e, *codes):
    """The target's sequence of the host code values `codes`; errors return an eresult(cve)."""
    return unwrap_m(e, code_seq(e, *codes), e.mb.types_cve())


def _retag(e, cv, typ):
    """The runtime value of `cv` (a variable reference: it is spliced twice) viewed as `typ` (values.atz), with the
    code of `cv`."""
    retag = e.lower(e.fld(e.v("values"), "retag"))
    return cv_of(
        e,
        cve_code(e, cv),
        bim(e, retag, "retag", e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), retag)), typ),
    )


def _as_pair(e, cv):
    """The option value `cv` viewed as its pair tuple."""
    return _retag(e, cv, in_(e, "pt"))


def _variant(e, key, type_):
    return e.call(
        e.eval_builtin("aspect_union_variant"),
        e.rec(p("key", e.mb.as_(e.s(key), e.mb.types_constkey())), p("type", type_)),
    )


def _setup(e):
    """Staged in the caller's context: the option type and the constructor types for `elem` (made in the host body,
    constants here), and the constructors' function values."""
    out = []
    out.append(e.let("type", e.mb.as_(e.lower(e.v("ot_i")), e.mb.eval_type())))
    for kind in KINDS:
        out.append(e.let(kind + "_t", e.mb.as_(e.lower(e.v(kind + "_i")), e.mb.eval_type())))
        out.append(e.let(kind, fn_of(e, e.lower(e.v(kind + "_i")))))
    out.append(
        e.ret(
            e.rec(
                p("type", e.v("type")),
                *[p(k, e.v(k)) for k in KINDS],
                *[p(k + "_t", e.v(k + "_t")) for k in KINDS],
            )
        )
    )
    return e.mb.seq(out)


def _objs(e, x):
    base_fields = [p(f, ty(e)) for f in BASE]
    oct_fields = [p("kind", str_(e))] + base_fields
    def_iface(e, x, "oct_m", *oct_fields)
    def_obj(e, x, "oct", "option constructor", e.rec(*oct_fields))
    def_iface(e, x, "ot_m", *base_fields)
    def_obj(e, x, "ot", "option type", e.rec(*base_fields))
    no = no_cast_to(e)

    # ---- the constructors `some(v)`, `none(())`, `of((tag, v))`: constant callables that modules bind and export ----
    x.append(e.impl_interface(e.v("oct"), t(e, "oct_m"), *[p(f, in_(e, f)) for f, _ in oct_fields]))
    self_type(
        e,
        x,
        "oct",
        e.cat(e.s("option."), in_(e, "kind"), e.s("("), ty_desc(e, in_(e, "elem")), e.s(")")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_unit(e),
        cast_from_empty(e),
        no,
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "oct_m"),
                    and_b(
                        e,
                        e.eq(in_(e, "kind"), acc(e, xx(e), a(e, "other"), "oct_m", "kind")),
                        is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "oct_m", "elem")),
                    ),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "oct")
    rt_bind_impl(e, x, "oct", e.mb.types_string())
    rt_use_impl(e, x, "oct")

    def result(pair_cv):
        """Ends a constructor call: the pair `pair_cv` viewed as the option type, after the callee's own code."""
        return e.seq(
            e.let("pr", pair_cv),
            e.let("o", _retag(e, e.v("pr"), mk(e, "ot", *[p(f, in_(e, f)) for f in BASE]))),
            ret_m(
                e,
                ok_cve(
                    e,
                    cv_of(e, _codes(e, cve_code(e, a(e, "self")), cve_code(e, e.v("o"))), cve_value(e, e.v("o"))),
                ),
            ),
        )

    x.append(
        e.impl_interface(
            e.v("oct"),
            e.eval_builtin("aspect_function"),
            p(
                "call",
                body(
                    e,
                    e.if_only(
                        e.eq(in_(e, "kind"), e.s("some")),
                        e.seq(
                            e.let("c", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "elem"), a(e, "argument")))),
                            result(_staged(e, e.mb.as_(e.tup(e.n(1), graft(e, e.v("c"))), e.lower(in_(e, "pt"))))),
                        ),
                    ),
                    e.if_only(
                        e.eq(in_(e, "kind"), e.s("none")),
                        e.seq(
                            e.let(
                                "z",
                                _staged(
                                    e,
                                    e.mb.as_(
                                        e.tup(e.n(0), e.mb.as_(e.n(0), e.lower(in_(e, "elem")))),
                                        e.lower(in_(e, "pt")),
                                    ),
                                ),
                            ),
                            result(
                                cv_of(
                                    e,
                                    _codes(e, cve_code(e, a(e, "argument")), cve_code(e, e.v("z"))),
                                    cve_value(e, e.v("z")),
                                )
                            ),
                        ),
                    ),
                    result(unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "pt"), a(e, "argument")))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )

    # ---- the option type: the pair tuple's aspects, except that it has no components and matches as a union ----
    x.append(e.impl_interface(e.v("ot"), t(e, "ot_m"), *[p(f, in_(e, f)) for f in BASE]))
    self_type(
        e,
        x,
        "ot",
        e.cat(e.s("option("), ty_desc(e, in_(e, "elem")), e.s(")")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "union")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "ot_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_none(e.mb.types_aspect())),
            ],
            type_aspect(e, xx(e), in_(e, "pt"), a(e, "key")),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    is_equal(e, xx(e), in_(e, "pt"), a(e, "source_type")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "pt"), cve_type(e, a(e, "cv")))),
                ret_m(e, err_cve(e, loc(e), "option: only the option's pair tuple can become an option")),
            ),
            e.ret(ok_cve(e, _retag(e, a(e, "cv"), outer(e)))),
        ),
        no,
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ot_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "ot_m", "elem")),
                )
            ),
        ),
    )
    # `match` reads the pair: variant `some` holds when the tag is not zero; the `none` payload is the unit.
    x.append(
        e.impl_interface(
            e.v("ot"),
            e.eval_builtin("aspect_union"),
            p(
                "variants",
                e.list_new(
                    e.mb.builtin("types", "aspect_union_variant"),
                    _variant(e, "some", in_(e, "elem")),
                    _variant(e, "none", in_(e, "unit")),
                ),
            ),
            p(
                "test",
                body(
                    e,
                    e.let("pair", _as_pair(e, a(e, "base"))),
                    e.if_only(
                        e.eq(a(e, "variant_index"), e.int_of(SOME)),
                        ret_m(
                            e,
                            e.eresult_ok(
                                cve_t(e),
                                _staged(e, e.not_(e.eq(e.mb.field(graft(e, e.v("pair")), e.n(0)), e.n(0)))),
                            ),
                        ),
                    ),
                    e.ret(e.eresult_ok(cve_t(e), _staged(e, e.eq(e.mb.field(graft(e, e.v("pair")), e.n(0)), e.n(0))))),
                ),
            ),
            p(
                "extract",
                body(
                    e,
                    e.let("pair", _as_pair(e, a(e, "base"))),
                    e.if_only(
                        e.eq(a(e, "variant_index"), e.int_of(SOME)),
                        ret_m(e, e.eresult_ok(cve_t(e), _staged(e, e.mb.field(graft(e, e.v("pair")), e.n(1))))),
                    ),
                    e.ret(
                        e.eresult_ok(
                            cve_t(e),
                            cv_of(
                                e,
                                code_none(e, loc(e)),
                                e.call(
                                    e.eval_builtin("value_object_const"),
                                    e.rec(p("type", in_(e, "unit")), p("data", e.tup())),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )


def module(e, kind):
    tg = _Target(kind)
    x = []
    tg.imports(e, x)
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("unit", e.fld(e.v("lib"), "unit")))
    _objs(e, x)
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "option.type: argument has no value"))),
        *const_type_arg(e, "option.type", e.v("argv"), "elem"),
        e.if_only(
            has_b(e, xx(e), e.v("elem"), e.mb.eval_aspect_drop_dynamic()),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(
                        e.s("option.type: element type "),
                        ty_desc(e, e.v("elem")),
                        e.s(" has a destructor; options hold plain values"),
                    ),
                ),
            ),
        ),
        e.let("i32", e.lower(e.v("i32"))),
        e.let("unit", e.lower(e.v("unit"))),
        # The pair tuple type `(i32, elem)` the option is a view of.
        e.let(
            "pt",
            e.call(e.lower(e.fld(e.v("lib"), "tuple")), e.list_new(e.mb.eval_type(), e.v("i32"), e.v("elem"))),
        ),
        e.let("ot_i", mk(e, "ot", *[p(f, e.v(f)) for f in BASE])),
        *[e.let(kind + "_i", mk(e, "oct", p("kind", e.s(kind)), *[p(f, e.v(f)) for f in BASE])) for kind in KINDS],
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))),
    ]
    const_fn(e, x, "option_b", "option.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("option_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
