"""values.atz: interfaces every target's runtime value object implements, plus the value aspects target TYPES
implement so generic libraries (collections) can work with any element type.

Interfaces on values: `retag(type) -> value`, the same runtime value (same place or register) viewed as `type`;
`retag_slot(type) -> binding_slot`, a target's parameter slot viewed as a slot of `type`.

Aspects on types (looked up through the type's aspect dispatch):
- `size_i`: `size(()) -> int`, the byte size of a stored value of the type.
- `hash_i`: `hash({xx, loc, cv}) -> eresult(cve)`, stages a 32-bit integer hash of the value `cv`.
- `eq_i`: `eq({xx, loc, a, b}) -> eresult(cve)`, stages the target's native comparison of two values (usable as an
  `if` condition).

Callables for use in target code: `hash(v)`, `eq((a, b))`, and `size(type)` (a host integer); each errors when the
type lacks the aspect. The aspect ids (`size_id`, `hash_id`, `eq_id`) are exported for type dispatch tables.
"""

from ..eco_mb import p
from ..target_mb import (
    a,
    asp_iface,
    bim,
    bim0,
    body,
    const_fn,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    err_cve,
    const_eval_in,
    int_t,
    is_runtime,
    loc,
    loc_t,
    lookup,
    or_b,
    ret_m,
    ty_desc,
    unwrap_cve_m,
    xx,
    xx_t,
)

FILE = "values.atz"


def _eres_cve_t(e):
    return e.call(e.mb.types_eresult(), cve_t(e))


def _iface(e, out, name, method, arg_type, ret_type):
    out.append(e.let(name, e.call_m0(e.v("d"), "interface")))
    out.append(e.interface_impl(e.v(name), True))
    out.append(e.let(name + "d", e.call_m0(e.v(name), "aspect_id")))
    out.append(
        e.call_m(
            e.v(name),
            "func",
            e.rec(p("name", e.s(method)), p("arg", arg_type), p("ret", e.option_type_some(ret_type))),
        )
    )


def _arg_cve(e, label):
    return [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), label + ": argument has no value"))),
    ]


def _need(e, label, typ, iface, what):
    """Checks `typ` implements the aspect `iface` (the lookup is left in `ik`), else errors out of the const
    function."""
    return [
        e.let("ik", lookup(e, xx(e), typ, e.lower(e.fld(e.v(iface), "type")))),
        e.if_only(
            e.not_(e.fld(e.v("ik"), "is_some")),
            ret_m(e, err_cve(e, loc(e), e.cat(e.s(label + ": type "), ty_desc(e, typ), e.s(" has no " + what)))),
        ),
    ]


def _impl(e):
    """The implementation `_need` found (an interface value cannot be bound, so it is read where it is used)."""
    return e.fld(e.v("ik"), "value")


def module(e):
    top = []
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    top.append(e.let("retag", e.call_m0(e.v("d"), "interface")))
    top.append(e.interface_impl(e.v("retag"), False))
    top.append(
        e.call_m(
            e.v("retag"),
            "func",
            e.rec(
                e.p("name", e.s("retag")),
                e.p("arg", e.mb.eval_type()),
                e.p("ret", e.option_type_some(e.mb.eval_value())),
            ),
        )
    )
    # The slot analog: a parameter slot of a target viewed as a slot of `type`, for a type that wraps another's
    # parameter binding.
    top.append(e.let("retag_slot", e.call_m0(e.v("d"), "interface")))
    top.append(e.interface_impl(e.v("retag_slot"), False))
    top.append(
        e.call_m(
            e.v("retag_slot"),
            "func",
            e.rec(
                e.p("name", e.s("retag_slot")),
                e.p("arg", e.mb.eval_type()),
                e.p("ret", e.option_type_some(e.mb.eval_binding_slot())),
            ),
        )
    )
    _iface(e, top, "size_i", "size", e.tup(), int_t(e))
    _iface(e, top, "hash_i", "hash", e.rec(p("xx", xx_t(e)), p("loc", loc_t(e)), p("cv", cve_t(e))), _eres_cve_t(e))
    _iface(
        e,
        top,
        "eq_i",
        "eq",
        e.rec(p("xx", xx_t(e)), p("loc", loc_t(e)), p("a", cve_t(e)), p("b", cve_t(e))),
        _eres_cve_t(e),
    )
    const_fn(
        e,
        top,
        "hash_b",
        "values.hash",
        body(
            e,
            *_arg_cve(e, "values.hash"),
            *_need(e, "values.hash", cve_type(e, e.v("argv")), "hash_i", "hash"),
            e.ret(
                bim(
                    e,
                    e.lower(e.fld(e.v("hash_i"), "type")),
                    "hash",
                    _impl(e),
                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("cv", e.v("argv"))),
                )
            ),
        ),
    )
    const_fn(
        e,
        top,
        "eq_b",
        "values.eq",
        body(
            e,
            *_arg_cve(e, "values.eq"),
            e.let("tk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "tuple"))),
            e.if_only(
                e.not_(e.fld(e.v("tk"), "is_some")),
                ret_m(e, err_cve(e, loc(e), "values.eq: argument must be a tuple (a, b)")),
            ),
            e.let("parts", e.map_new(e.mb.types_string(), cve_t(e))),
            e.let("ni", e.rec(p("i", e.int_of(0)))),
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
                    e.call_m(e.v("parts"), "put", e.tup(e.to_str(e.fld(e.v("ni"), "i")), unwrap_cve_m(e, e.v("er")))),
                    e.incr(e.fld(e.v("ni"), "i")),
                ),
            ),
            e.if_only(
                e.not_(e.eq(e.fld(e.v("ni"), "i"), e.int_of(2))),
                ret_m(e, err_cve(e, loc(e), "values.eq: argument must be a tuple of two values")),
            ),
            e.let("av", e.call_m(e.v("parts"), "get", e.s("0"))),
            e.let("bv", e.call_m(e.v("parts"), "get", e.s("1"))),
            *_need(e, "values.eq", cve_type(e, e.v("av")), "eq_i", "eq"),
            e.ret(
                bim(
                    e,
                    e.lower(e.fld(e.v("eq_i"), "type")),
                    "eq",
                    _impl(e),
                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("a", e.v("av")), p("b", e.v("bv"))),
                )
            ),
        ),
    )
    const_fn(
        e,
        top,
        "size_b",
        "values.size",
        body(
            e,
            *_arg_cve(e, "values.size"),
            e.let("tyk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "type"))),
            e.if_only(
                or_b(e, is_runtime(e, e.v("argv")), e.not_(e.fld(e.v("tyk"), "is_some"))),
                ret_m(e, err_cve(e, loc(e), "values.size: argument must be a constant type")),
            ),
            e.let("st", bim(e, asp_iface(e, "type"), "type", e.fld(e.v("tyk"), "value"), cve_value(e, e.v("argv")))),
            *_need(e, "values.size", e.v("st"), "size_i", "size"),
            e.let("n", bim0(e, e.lower(e.fld(e.v("size_i"), "type")), "size", _impl(e))),
            e.ret(const_eval_in(e, xx(e), e.stage(e.lower(e.v("n"))))),
        ),
    )
    top.append(e.finish(e.v("d")))
    exported = [
        p("retag", e.fld(e.v("retag"), "type")),
        p("retag_slot", e.fld(e.v("retag_slot"), "type")),
        p("size_i", e.fld(e.v("size_i"), "type")),
        p("hash_i", e.fld(e.v("hash_i"), "type")),
        p("eq_i", e.fld(e.v("eq_i"), "type")),
        p("size_id", e.v("size_id")),
        p("hash_id", e.v("hash_id")),
        p("eq_id", e.v("eq_id")),
        p("size", e.fld(e.v("size_b"), "func")),
        p("hash", e.fld(e.v("hash_b"), "func")),
        p("eq", e.fld(e.v("eq_b"), "func")),
    ]
    top.append(e.ret(e.rec(*exported)))
    return top
