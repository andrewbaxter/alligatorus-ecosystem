"""option-wasm.atz / option-llvm.atz: a value that is either `some(v)` or `none`, one module per target from this
builder.

`option.type(elem)` yields `{type, own, raw, some, none, of}` for a constant element type `elem` with a zero
(values.atz's `zero_i`); `option.types({xx, loc, elem})` is the host-function face of the same (for a library making
options in its own host body, as webidl-wasm.atz does for nullable results), yielding the types `{type, own, raw,
some_t, none_t, of_t}` (`types_t`). An option is the target's tuple `(i32, elem)` (the tag, zero for none, and the
payload, `elem`'s zero when none) viewed as its own type (`raw`): it binds, is assigned, passed and returned exactly
like that tuple, but exposes no components. `some(v)`, `none(())` and `of((tag, v))` are function values, the empty
values of constructor types (returned too, as `some_t`, `none_t` and `of_t`, for types that carry them); modules hold
them in lowered setup blocks and bodies lower them. An option is read with `match`: the type implements
`eval.aspect_union` (variants `some` with the payload and `none` with the target's unit), whose `test` compares the tag
and whose `extract` yields the payload for the case to bind.

An element type with a destructor (destructor.atz) is stored as its under type, and `type` is then an owned type
over the view (`own` its adopting type; for a plain element `type` and `own` are the view itself): the constructors
take ownership of the payload (`some(v.move())`, `some(new() as own)`) and yield owned temporaries, dropping an
unmatched option destroys its payload when it holds one, and `match` moves the payload out of an option it consumes
(a temporary, or a binding's `.move()`); matched in place (a bound owned option, or one held in a record or a
container), it hands the payload out as its under value (the raw form an owned type's borrow converts to), leaving
the option as it is.
"""

from ..core import values
from ..memory import destructor
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
    bim0,
    asp_iface,
    bool_t,
    cast_to_panic,
    cast_value,
    code_none,
    code_seq,
    const_eval_in,
    count_loop,
    count_let,
    const_fn,
    cv_of,
    cve_code,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    errs_t,
    fn_def,
    fn_impl,
    fn_throws,
    loc_t,
    throw_err,
    xx_t,
    def_obj,
    err_cve,
    graft,
    has,
    has_b,
    ident_of,
    in_,
    is_equal,
    loc,
    lookup,
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
# What an option type carries: the element type, the type the payload is stored as (`elem`'s under when it has a
# destructor), i32 (the tag), the target's unit (the payload type of `none`), the pair tuple type `(i32, estore)`
# the option is a view of, and whether the element has a destructor.
BASE_TYPES = ["elem", "estore", "i32", "unit", "pt"]
BASE = BASE_TYPES + ["drops"]
# A constructor also carries the type its results have: the owned option type, or the view for a plain element.
CTOR_FIELDS = ["kind"] + BASE + ["rt"]
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
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(expr)))


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
    """Staged in the caller's context: the option type (`type`: the owned type for an owned element, else the view),
    its adopting type (`own`), the view (`raw`) and the constructor types for `elem` (made in the host body,
    constants here), and the constructors' function values."""
    out = []
    out.append(e.let("type", e.lower(e.v("rt"))))
    out.append(e.let("own", e.lower(e.v("oown"))))
    out.append(e.let("raw", e.lower(e.v("view_t"))))
    for kind in KINDS:
        out.append(e.let(kind + "_t", e.mb.as_(e.lower(e.v(kind + "_i")), e.mb.eval_type())))
        out.append(e.let(kind, fn_of(e, e.lower(e.v(kind + "_i")))))
    out.append(
        e.ret(
            e.rec(
                p("type", e.v("type")),
                p("own", e.v("own")),
                p("raw", e.v("raw")),
                *[p(k, e.v(k)) for k in KINDS],
                *[p(k + "_t", e.v(k + "_t")) for k in KINDS],
            )
        )
    )
    return e.mb.seq(out)


def _objs(e, x):
    base_fields = [p(f, ty(e)) for f in BASE_TYPES] + [p("drops", bool_t(e))]
    oct_fields = [p("kind", str_(e))] + base_fields + [p("rt", ty(e))]
    def_iface(e, x, "oct_m", *oct_fields)
    def_obj(e, x, "oct", "option constructor", e.rec(*oct_fields))
    def_iface(e, x, "ot_m", *base_fields)
    def_obj(e, x, "ot", "option type", e.rec(*base_fields))
    no = no_cast_to(e)

    # ---- the constructors `some(v)`, `none(())`, `of((tag, v))`: constant callables that modules bind and export ----
    x.append(e.impl_interface(e.v("oct"), t(e, "oct_m"), *[p(f, in_(e, f)) for f in CTOR_FIELDS]))
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
            e.let("o", _retag(e, e.v("pr"), in_(e, "rt"))),
            ret_m(
                e,
                ok_cve(
                    e,
                    cv_of(e, _codes(e, cve_code(e, a(e, "function")), cve_code(e, e.v("o"))), cve_value(e, e.v("o"))),
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
                            # an owned payload is stored as its under value (the option owns it now)
                            e.let("cs", e.if_else(in_(e, "drops"), _retag(e, e.v("c"), in_(e, "estore")), e.v("c"))),
                            result(_staged(e, e.mb.as_(e.tup(e.n(1), graft(e, e.v("cs"))), e.lower(in_(e, "pt"))))),
                        ),
                    ),
                    e.if_only(
                        e.eq(in_(e, "kind"), e.s("none")),
                        e.seq(
                            e.let(
                                "ez",
                                _retag(
                                    e,
                                    unwrap_cve_m(
                                        e,
                                        bim(
                                            e,
                                            e.lower(e.fld(e.v("values"), "zero_i")),
                                            "zero",
                                            e.fld(
                                                lookup(
                                                    e, xx(e), in_(e, "estore"), e.lower(e.fld(e.v("values"), "zero_i"))
                                                ),
                                                "value",
                                            ),
                                            e.rec(p("xx", xx(e)), p("loc", loc(e))),
                                        ),
                                    ),
                                    in_(e, "estore"),
                                ),
                            ),
                            e.let(
                                "z",
                                _staged(e, e.mb.as_(e.tup(e.n(0), graft(e, e.v("ez"))), e.lower(in_(e, "pt")))),
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
                    e.if_only(
                        in_(e, "drops"),
                        e.seq(
                            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "argument")), asp_iface(e, "tuple"))),
                            e.if_only(
                                e.not_(e.fld(e.v("tk"), "is_some")),
                                ret_m(e, err_cve(e, loc(e), "option.of: the argument must be a (tag, value) tuple")),
                            ),
                            e.let("els", e.list_new(e.mb.types_cve())),
                            e.foreach(
                                bim(
                                    e,
                                    asp_iface(e, "tuple"),
                                    "take_elements",
                                    e.fld(e.v("tk"), "value"),
                                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, a(e, "argument")))),
                                ),
                                "er",
                                e.push(e.v("els"), unwrap_cve_m(e, e.v("er"))),
                            ),
                            count_let(e, "nels"),
                            count_loop(e, "nels", e.v("els")),
                            e.if_only(
                                e.not_(e.eq(e.fld(e.v("nels"), "v"), e.int_of(2))),
                                ret_m(e, err_cve(e, loc(e), "option.of: the argument must be a (tag, value) tuple")),
                            ),
                            e.let(
                                "tag",
                                unwrap_cve_m(
                                    e,
                                    cast_value(
                                        e, xx(e), loc(e), in_(e, "i32"), e.call_m(e.v("els"), "get", e.int_of(0))
                                    ),
                                ),
                            ),
                            e.let(
                                "ov",
                                unwrap_cve_m(
                                    e,
                                    cast_value(
                                        e, xx(e), loc(e), in_(e, "elem"), e.call_m(e.v("els"), "get", e.int_of(1))
                                    ),
                                ),
                            ),
                            e.let("vs", _retag(e, e.v("ov"), in_(e, "estore"))),
                            result(
                                _staged(
                                    e, e.mb.as_(e.tup(graft(e, e.v("tag")), graft(e, e.v("vs"))), e.lower(in_(e, "pt")))
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
                        e.seq(
                            e.let("payload", _staged(e, e.mb.field(graft(e, e.v("pair")), e.n(1)))),
                            # An owned payload moves out of the option the match consumes: an owned temporary or
                            # the view itself; a bound owned option is matched through its `.move()`.
                            e.let(
                                "consuming",
                                or_b(
                                    e,
                                    has_b(
                                        e,
                                        xx(e),
                                        cve_type(e, a(e, "base")),
                                        e.lower(e.fld(e.v("destructor"), "owned_m")),
                                    ),
                                    is_equal(e, xx(e), outer(e), cve_type(e, a(e, "base"))),
                                ),
                            ),
                            # Read in place (a bound owned option, or one held in a record or container), the
                            # payload is handed out as its under value (the raw, untracked form an owned type's
                            # borrow converts to), left in the option.
                            e.if_only(
                                and_b(e, in_(e, "drops"), e.not_(e.v("consuming"))),
                                ret_m(e, e.eresult_ok(cve_t(e), _retag(e, e.v("payload"), in_(e, "estore")))),
                            ),
                            ret_m(e, e.eresult_ok(cve_t(e), _retag(e, e.v("payload"), in_(e, "elem")))),
                        ),
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


def _type_parts(e, fail):
    """Host statements over `elem` (a constant element type) binding the option's types and constructors: `rt`
    (`type`), `oown` (`own`), `view_t` (`raw`) and `<kind>_i`; `fail(msg)` leaves with the error `msg`."""
    return [
        e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))),
        e.let("drops", has_b(e, xx(e), e.v("elem"), e.v("owned_m"))),
        e.if_only(
            and_b(e, e.not_(e.v("drops")), has_b(e, xx(e), e.v("elem"), e.mb.eval_aspect_drop_dynamic())),
            fail(
                e.cat(
                    e.s("option.type: element type "), ty_desc(e, e.v("elem")), e.s(" drops but is not an owned type")
                )
            ),
        ),
        # An owned element is stored as its under value, read through a borrow and given back as the owned value.
        e.let(
            "estore",
            e.if_else(
                e.v("drops"),
                bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("elem"), e.v("owned_m")), "value")),
                e.v("elem"),
            ),
        ),
        e.let(
            "eown",
            e.if_else(e.v("drops"), e.call(e.lower(e.fld(e.v("destructor"), "adopt")), e.v("elem")), e.v("elem")),
        ),
        e.if_only(
            e.not_(has_b(e, xx(e), e.v("estore"), e.lower(e.fld(e.v("values"), "zero_i")))),
            fail(
                e.cat(e.s("option.type: element type "), ty_desc(e, e.v("elem")), e.s(" has no zero (values.zero_i)"))
            ),
        ),
        e.let("i32", e.lower(e.v("i32"))),
        e.let("unit", e.lower(e.v("unit"))),
        # The pair tuple type `(i32, estore)` the option is a view of.
        e.let(
            "pt",
            e.call(e.lower(e.fld(e.v("lib"), "tuple")), e.list_new(e.mb.eval_type(), e.v("i32"), e.v("estore"))),
        ),
        # The owned option type's destroy (a dependency of the caller's module; a plain element's goes unused): it
        # destroys the payload when the tag is set, by adopting it into an owned binding that drops at once.
        e.let(
            "odestroy",
            e.call(
                e.lower(e.fld(e.v("lib"), "func_dep")),
                e.rec(
                    p("name", e.cat(e.s("option_destroy_"), ident_of(e, ty_desc(e, e.v("elem"))))),
                    p("params", e.list_new(e.mb.types_string(), e.s("o"))),
                    p(
                        "ty",
                        e.call(
                            e.lower(e.fld(e.v("lib"), "fn")),
                            e.rec(p("params", e.list_new(e.mb.eval_type(), e.v("pt"))), p("ret", e.lower(e.v("void")))),
                        ),
                    ),
                    p(
                        "body",
                        e.stage(
                            e.if_only(
                                e.not_(e.eq(e.mb.field(e.v("o"), e.n(0)), e.n(0))),
                                e.seq(e.let("__p", e.mb.as_(e.mb.field(e.v("o"), e.n(1)), e.lower(e.v("eown"))))),
                            )
                        ),
                    ),
                ),
            ),
        ),
        e.let("ot_i", mk(e, "ot", *[p(f, e.v(f)) for f in BASE])),
        e.let("view_t", e.mb.as_(e.v("ot_i"), e.mb.eval_type())),
        # The owned option type over the view (destructor.owned_of: made here, so the constructors, lowered into the
        # setup as constants, carry it); a plain element's option is the view itself.
        e.let(
            "oo",
            e.if_else(
                e.v("drops"),
                e.call(
                    e.lower(e.fld(e.v("destructor"), "owned_of")),
                    e.rec(p("under", e.v("view_t")), p("destroy", e.v("odestroy"))),
                ),
                e.rec(p("type", e.v("view_t")), p("own", e.v("view_t"))),
            ),
        ),
        e.let("rt", e.fld(e.v("oo"), "type")),
        e.let("oown", e.fld(e.v("oo"), "own")),
        *[
            e.let(kind + "_i", mk(e, "oct", p("kind", e.s(kind)), *[p(f, e.v(f)) for f in BASE], p("rt", e.v("rt"))))
            for kind in KINDS
        ],
    ]


def _types_t(e):
    """The record of types `option.types` yields."""
    return e.rec(p("type", ty(e)), p("own", ty(e)), p("raw", ty(e)), *[p(kind + "_t", ty(e)) for kind in KINDS])


def module(e, kind):
    tg = _Target(kind)
    x = []
    tg.imports(e, x)
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("unit", e.fld(e.v("lib"), "unit")))
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    _objs(e, x)
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "option.type: argument has no value"))),
        *const_type_arg(e, "option.type", e.v("argv"), "elem"),
        *_type_parts(e, lambda msg: ret_m(e, err_cve(e, loc(e), msg))),
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(_setup(e)))))),
    ]
    const_fn(e, x, "option_b", "option.type", body(e, *parts))
    # `option.types({xx, loc, elem})`: a host function (callable from another module's host code, like
    # destructor.owned_of) yielding the same types as plain types: `{type, own, raw, some_t, none_t, of_t}`.
    fn_def(e, x, "option", "c_types", e.rec(p("xx", xx_t(e)), p("loc", loc_t(e)), p("elem", ty(e))), _types_t(e))
    fn_throws(e, "c_types", errs_t(e))
    fn_impl(
        e,
        x,
        "c_types",
        body(
            e,
            e.let("elem", a(e, "elem")),
            *_type_parts(e, lambda msg: throw_err(e, loc(e), msg)),
            e.ret(
                e.rec(
                    p("type", e.v("rt")),
                    p("own", e.v("oown")),
                    p("raw", e.v("view_t")),
                    *[p(kind + "_t", e.mb.as_(e.v(kind + "_i"), e.mb.eval_type())) for kind in KINDS],
                )
            ),
        ),
    )
    x.append(e.finish(e.v("d")))
    x.append(
        e.ret(e.rec(p("type", e.fld(e.v("option_b"), "func")), p("types", e.v("c_types")), p("types_t", _types_t(e))))
    )

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(*[p(n, e.fld(e.v("k"), n)) for n in ["type", "types", "types_t"]])))
    return top
