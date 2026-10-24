"""enum-wasm.atz / enum-llvm.atz: an enumeration, a value that is one of a fixed set of named variants without
payloads, one module per target from this builder.

`enum.type(("red", "green", ...))` yields `{type, red, green, ...}` for constant variant names (a tuple of
strings): the type and one constructor per variant, `red(())` the constant of that variant (a function value, as
option.atz's `none`: a target constant exists only in target code, so the result record, built as a record
expression over the names and evaluated in the caller's context, holds callables). An enumeration is the target's
i32 (the variant's index) viewed as its own type: it binds, is assigned, compares with `==`, passes to and returns
from functions and is stored (values.atz `size`, `zero`: the first variant) exactly like an i32, but nothing
converts into it except a constant integer in range (how the constructors make the constants). It is read with
`match`: the type implements `eval.aspect_union` (one variant per name, each with the target's unit as its payload),
whose `test` compares the index and whose `extract` yields the unit, so a match over an enumeration is checked for
exhaustiveness.
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
    body,
    cast_to_panic,
    code_none,
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
    fresh_unique,
    graft,
    has,
    has_b,
    in_,
    int_t,
    count_loop,
    count_let,
    unwrap_m,
    ty_desc,
    rt_use_impl,
    rt_lift_impl,
    rt_dispatch,
    rt_bind_impl,
    fn_of,
    code_seq,
    cast_from_empty,
    can_cast_from_unit,
    cast_value,
    is_const,
    or_b,
    is_equal,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    no_cast_to,
    ok_cve,
    outer,
    ret_m,
    self_type,
    str_,
    t,
    ty,
    type_aspect,
    unique_t,
    unwrap_cve_m,
    xx,
)

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "enum-wasm.atz", LLVM: "enum-llvm.atz"}

# What an enumeration type carries: its identity, the variant names, i32 (its representation) and the target's unit
# (every variant's payload type).
FIELDS = [("id", unique_t), ("names", lambda e: e.list_type(str_(e))), ("i32", ty), ("unit", ty)]


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


def _retag(e, cv, typ):
    """The runtime value of `cv` (a variable reference: it is spliced twice) viewed as `typ` (values.atz), with the
    code of `cv`."""
    retag = e.lower(e.fld(e.v("values"), "retag"))
    return cv_of(
        e,
        cve_code(e, cv),
        bim(e, retag, "retag", e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), retag)), typ),
    )


def _as_i32(e, cv):
    """The enumeration value `cv` viewed as its i32."""
    return _retag(e, cv, in_(e, "i32"))


def _index_const(e, index_expr):
    """The i32 constant `index_expr` (a host int) in target code."""
    return _staged(e, e.mb.as_(e.lower(index_expr), e.lower(in_(e, "i32"))))


def _unit_value(e):
    return cv_of(
        e,
        code_none(e, loc(e)),
        e.call(e.eval_builtin("value_object_const"), e.rec(p("type", in_(e, "unit")), p("data", e.tup()))),
    )


def _ctor(e, x):
    """`ec{index, et}`: a variant's constructor, the callable whose call `red(())` yields the variant's constant."""
    fields = [p("index", e.mb.types_int()), p("et", ty(e))]
    def_iface(e, x, "ec_m", *fields)
    def_obj(e, x, "ec", "enumeration constant", e.rec(*fields))
    x.append(e.impl_interface(e.v("ec"), t(e, "ec_m"), p("index", in_(e, "index")), p("et", in_(e, "et"))))
    self_type(
        e,
        x,
        "ec",
        e.cat(ty_desc(e, in_(e, "et")), e.s(".constant")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_unit(e),
        cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ec_m"),
                    and_b(
                        e,
                        e.eq(in_(e, "index"), acc(e, xx(e), a(e, "other"), "ec_m", "index")),
                        is_equal(e, xx(e), in_(e, "et"), acc(e, xx(e), a(e, "other"), "ec_m", "et")),
                    ),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "ec")
    rt_bind_impl(e, x, "ec", e.mb.types_string())
    rt_use_impl(e, x, "ec")
    x.append(
        e.impl_interface(
            e.v("ec"),
            e.eval_builtin("aspect_function"),
            p(
                "call",
                body(
                    e,
                    e.let(
                        "c", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "et"), _host_int(e, in_(e, "index"))))
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                unwrap_m(
                                    e,
                                    code_seq(e, cve_code(e, a(e, "function")), cve_code(e, e.v("c"))),
                                    e.mb.types_cve(),
                                ),
                                cve_value(e, e.v("c")),
                            ),
                        )
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def _host_int(e, n):
    """The host integer `n` as a code value (a constant: it casts to the enumeration in the caller's context)."""
    return unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(e.lower(n))))


def _objs(e, x):
    _ctor(e, x)
    fields = [p(f, ft(e)) for f, ft in FIELDS]
    def_iface(e, x, "et_m", *fields)
    def_obj(e, x, "et", "enumeration type", e.rec(*fields))
    x.append(e.impl_interface(e.v("et"), t(e, "et_m"), *[p(f, in_(e, f)) for f, _ in FIELDS]))
    # ---- the type: an i32's aspects, except that it is read with `match`, its constants are its fields and
    # nothing but itself converts into it ----
    self_type(
        e,
        x,
        "et",
        e.cat(e.s("enum("), e.join(in_(e, "names"), "|"), e.s(")")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "union")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "et_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, "i32"), a(e, "key")),
        ),
        body(
            e,
            e.ret(or_b(e, is_equal(e, xx(e), outer(e), a(e, "source_type")), is_const(e, xx(e), a(e, "source_type")))),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.let(
                "index",
                e.call(
                    e.eval_builtin("const_numeric_to_double"),
                    e.rec(p("xx", xx(e)), p("value", cve_value(e, a(e, "cv")))),
                ),
            ),
            e.let("ii", e.mb.as_(e.v("index"), int_t(e))),
            count_let(e, "n"),
            count_loop(e, "n", in_(e, "names")),
            e.if_only(
                or_b(
                    e,
                    e.not_(e.eq(e.mb.as_(e.v("ii"), e.types_double()), e.v("index"))),
                    or_b(
                        e,
                        e.mb.operator_lt(e.v("ii"), e.int_of(0)),
                        e.not_(e.mb.operator_lt(e.v("ii"), e.fld(e.v("n"), "v"))),
                    ),
                ),
                ret_m(e, err_cve(e, loc(e), "enum: the index is out of the enumeration's range")),
            ),
            e.let("iv", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "i32"), a(e, "cv")))),
            e.ret(ok_cve(e, _retag(e, e.v("iv"), outer(e)))),
        ),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "et_m"),
                    e.eq(in_(e, "id"), acc(e, xx(e), a(e, "other"), "et_m", "id")),
                )
            ),
        ),
    )
    # `match`: variant `i` holds when the index is `i`; every payload is the unit.
    x.append(
        e.impl_interface(
            e.v("et"),
            e.eval_builtin("aspect_union"),
            p(
                "variants",
                e.seq(
                    e.let("vs", e.list_new(e.mb.builtin("types", "aspect_union_variant"))),
                    e.foreach(
                        in_(e, "names"),
                        "n",
                        e.push(
                            e.v("vs"),
                            e.call(
                                e.eval_builtin("aspect_union_variant"),
                                e.rec(
                                    p("key", e.mb.as_(e.v("n"), e.mb.types_constkey())),
                                    p("type", in_(e, "unit")),
                                ),
                            ),
                        ),
                    ),
                    e.ret(e.v("vs")),
                ),
            ),
            p(
                "test",
                body(
                    e,
                    e.let("v", _as_i32(e, a(e, "base"))),
                    e.ret(
                        e.eresult_ok(
                            cve_t(e),
                            _staged(
                                e,
                                e.eq(
                                    graft(e, e.v("v")),
                                    e.mb.as_(e.lower(a(e, "variant_index")), e.lower(in_(e, "i32"))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
            p("extract", body(e, e.ret(e.eresult_ok(cve_t(e), _unit_value(e))))),
        )
    )
    # The constants: `color.red` is the index of `red` as the enumeration.
    x.append(
        e.impl_interface(
            e.v("et"),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "enum: a variant is named by a constant string")),
                    ),
                    e.let(
                        "key",
                        bim(
                            e,
                            e.mb.eval_aspect_string_const(),
                            "get",
                            lookup_v(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                            cve_value(e, a(e, "key")),
                        ),
                    ),
                    e.let("i", e.rec(p("v", e.int_of(0)))),
                    e.foreach(
                        in_(e, "names"),
                        "n",
                        e.seq(
                            e.if_only(
                                e.eq(e.v("n"), e.v("key")),
                                ret_m(e, ok_cve(e, _retag(e, _index_const(e, e.fld(e.v("i"), "v")), outer(e)))),
                            ),
                            e.incr(e.fld(e.v("i"), "v")),
                        ),
                    ),
                    e.ret(err_cve(e, loc(e), e.cat(e.s("enum: no variant "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.seq(
                    e.let("ks", e.list_new(e.mb.types_constkey())),
                    e.foreach(in_(e, "names"), "n", e.push(e.v("ks"), e.mb.as_(e.v("n"), e.mb.types_constkey()))),
                    e.ret(e.v("ks")),
                ),
            ),
        )
    )


def _entry(e, key, value):
    return e.call(e.eval_builtin("expr_record_entry"), e.rec(p("key", key), p("value", value)))


def _result(e):
    """Host statements: the result record `{type, <name>: constant, ...}` as a record expression over the names
    (the type and the constants are made in the host body, lowered into the entries), evaluated in the caller's
    context."""
    return [
        e.let("entries", e.list_new(e.mb.builtin("types", "expr_record_entry"))),
        e.push(e.v("entries"), _entry(e, e.stage(e.s("type")), e.stage(e.lower(e.v("et_i"))))),
        e.let("i", e.rec(p("v", e.int_of(0)))),
        e.foreach(
            e.v("names"),
            "n",
            e.seq(
                e.let(
                    "ci",
                    mk(e, "ec", p("index", e.fld(e.v("i"), "v")), p("et", e.mb.as_(e.v("et_i"), e.mb.eval_type()))),
                ),
                e.push(
                    e.v("entries"),
                    _entry(e, e.stage(e.lower(e.v("n"))), e.stage(fn_of(e, e.lower(e.v("ci"))))),
                ),
                e.incr(e.fld(e.v("i"), "v")),
            ),
        ),
        e.ret(
            e.call(
                e.eval_builtin("const_eval"),
                e.rec(
                    p("xx", xx(e)),
                    p("loc", loc(e)),
                    p(
                        "staged",
                        e.call(e.eval_builtin("expr_record"), e.rec(p("loc", loc(e)), p("entries", e.v("entries")))),
                    ),
                ),
            )
        ),
    ]


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
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "enum.type: argument has no value"))),
        e.let("tk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "tuple"))),
        e.if_only(
            e.not_(e.fld(e.v("tk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "enum.type: the argument must be a tuple of the variant names")),
        ),
        e.let("names", e.list_new(str_(e))),
        e.foreach(
            bim(
                e,
                asp_iface(e, "tuple"),
                "take_elements",
                e.fld(e.v("tk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, e.v("argv")))),
            ),
            "er",
            e.seq(
                e.let("ncv", unwrap_cve_m(e, e.v("er"))),
                e.if_only(
                    e.not_(has_b(e, xx(e), cve_type(e, e.v("ncv")), e.mb.eval_aspect_string_const())),
                    ret_m(e, err_cve(e, loc(e), "enum.type: a variant name must be a constant string")),
                ),
                e.push(
                    e.v("names"),
                    bim(
                        e,
                        e.mb.eval_aspect_string_const(),
                        "get",
                        lookup_v(e, xx(e), cve_type(e, e.v("ncv")), e.mb.eval_aspect_string_const()),
                        cve_value(e, e.v("ncv")),
                    ),
                ),
            ),
        ),
        e.let(
            "et_i",
            mk(
                e,
                "et",
                p("id", fresh_unique(e)),
                p("names", e.v("names")),
                p("i32", e.lower(e.v("i32"))),
                p("unit", e.lower(e.v("unit"))),
            ),
        ),
        *_result(e),
    ]
    const_fn(e, x, "enum_b", "enum.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("enum_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
