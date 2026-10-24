"""record-wasm.atz: heap records with typed fields on the wasm target.

`record.type({fields: {name: type, ...}})` yields `{type, own, raw, new}` for constant field types (each with
values.atz's `size` aspect): `raw` is the record handle type (a `ptr(void)` by representation), `type` its owned
form (destructor.atz) and `own` the adopting type. `new({name: value, ...})` (a constant callable: `fn_of(new)`)
allocates the record (wasm-alloc.atz) and stores every field; `new(...) as own` owns it. On a record value `r`,
`r.name` is the field's place: it reads and assigns. A field of an owned type (destructor.atz) is stored as its
under value: `new` takes that value (`v.forget()`: the record owns it from then on), `r.name` reads it as a borrow
(destructor.borrow: assigning an owned value through it destroys the old one), and the record's destroy destroys it.
Dropping an owned record destroys its owned fields, then frees the record.

The fields are laid out by alignment (8, 4, 2, 1 bytes: values.atz's `align_i`), so each sits at a multiple of its
own alignment and takes its size (`size_i`, padded to the alignment: a tuple field works), and the size is
rounded up to 8; a record without fields has no storage (a null pointer, which `free` ignores).

The Python functions here also define the record machinery inside closure-wasm.atz (a closure's captures are such a
record): `fields_parts`, `ctor`, `destroy_dep` are the host statements a const function uses to lay a record out,
make its constructor and its destroy dependency.
"""

from ..eco_mb import p
from ..core import values
from ..memory import destructor
from ..target_mb import (
    up,
    a,
    acc,
    accessor,
    alloc_or_trap,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    body,
    bool_t,
    call_result,
    can_cast_from_unit,
    cast_from_empty,
    cast_to_panic,
    cast_value,
    code_t,
    const_eval_in,
    const_fn,
    const_type_arg,
    conv,
    cv_no,
    cve_code,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    fn_of,
    fresh_unique,
    graft,
    handle_type,
    has,
    has_b,
    in_,
    is_equal,
    key_str,
    loc,
    lookup,
    to_str,
    or_b,
    lookup_v,
    lt,
    mk,
    no_cast_to,
    ok_cve,
    ret_m,
    retag_values,
    self_type,
    staged_in,
    str_,
    t,
    ty,
    unique_t,
    unwrap_cve_m,
    unwrap_m,
    xx,
)
from .vec import align_of, size_of

FILE = "record-wasm.atz"

# Stage depths: a dependency body made in a const function's host body, or a `staged_in` in a module-level method
# body, is two stages below the module and one below the enclosing body's locals.
BODY_MOD = 2
BODY_HOST = 1

ALIGNS = [8, 4, 2, 1]
# The constructor kinds: `new` allocates and stores (through `store`, over the record argument), `drop` destroys the
# owned fields.
CTOR_TYPES = ["rt", "pv", "pi32", "i32"]


def _field_access(e, c, name):
    return e.call_m(c, name, e.tup())


def place(e, ptr_expr, c, pfield="pty"):
    """The field `c`'s place in the record at `ptr_expr` (a `ptr(void)` expression in staged code of a module
    method body): the record's address plus the field's byte offset, through its pointer type `pfield` (`pty` the
    stored type's, `pref` the read type's)."""
    addr = e.mb.operator_add(
        conv(e, up(e, e.v("ptr_to_int"), BODY_MOD), ptr_expr, up(e, e.v("i32"), BODY_MOD)),
        e.lower(_field_access(e, c, "off")),
    )
    return e.mb.field(conv(e, up(e, e.v("int_to_ptr"), BODY_MOD), addr, e.lower(_field_access(e, c, pfield))), e.n(0))


def rfield(e, x):
    """A field: its name, stored type (`ty`, an owned type's under), read type (`ref`, a borrow of an owned type),
    adopting type (`own`), the declared type (`owned`: the owned type when the field drops, else `ty`), pointer
    types over the stored type (`pty`) and over the read type (`pref`: a borrow's place) and its byte offset in the
    record."""
    fields = [
        ("name", str_(e)),
        ("ty", ty(e)),
        ("ref", ty(e)),
        ("own", ty(e)),
        ("drops", bool_t(e)),
        ("owned", ty(e)),
        ("pty", ty(e)),
        ("pref", ty(e)),
        ("off", e.mb.types_int()),
    ]
    def_obj(e, x, "rfield", "record field", e.rec(*[p(f, ft) for f, ft in fields]))
    for f, ft in fields:
        accessor(e, x, "rfield", f, ft)


def rt(e, x, desc):
    """The record handle type `rt`: a `ptr(void)` whose fields are the record's field places."""
    fields = [p("id", unique_t(e)), p("caps", e.list_type(t(e, "rfield"))), p("size", e.mb.types_int()), p("pv", ty(e))]

    def place_():
        return place(e, e.mb.as_(graft(e, a(e, "value")), up(e, e.v("pv"), BODY_MOD)), e.v("c"), "pref")

    field_body = body(
        e,
        e.if_only(
            e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
            ret_m(e, err_cve(e, loc(e), desc + ": field must be a constant string")),
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
        e.foreach(
            in_(e, "caps"),
            "c",
            e.if_only(
                e.eq(_field_access(e, e.v("c"), "name"), e.v("key")), ret_m(e, ok_cve(e, staged_in(e, place_())))
            ),
        ),
        e.ret(err_cve(e, loc(e), e.cat(e.s(desc + " has no field "), e.v("key")))),
    )
    keys = e.seq(
        e.let("ks", e.list_new(e.mb.types_constkey())),
        e.foreach(
            in_(e, "caps"), "c", e.push(e.v("ks"), e.mb.as_(_field_access(e, e.v("c"), "name"), e.mb.types_constkey()))
        ),
        e.ret(e.v("ks")),
    )
    handle_type(
        e,
        x,
        "rt",
        "rt_m",
        desc,
        fields,
        {},
        [],
        under="pv",
        from_under=True,
        desc_expr=e.s(desc),
        identity="id",
        identity_eq=lambda e_, xx_, mine, theirs: e_.eq(mine, theirs),
        field=(field_body, keys),
    )


def codes_seq(e, codes):
    """The target's sequence of the host code values in the list `codes`; errors return an eresult(cve)."""
    return unwrap_m(
        e,
        bim(e, e.mb.eval_target(), "seq", e.fld(xx(e), "target"), e.rec(p("loc", loc(e)), p("entries", codes))),
        e.mb.types_cve(),
    )


def _elements(e, cv):
    return bim(
        e,
        asp_iface(e, "tuple"),
        "take_elements",
        lookup_v(e, xx(e), cve_type(e, cv), asp_iface(e, "tuple")),
        e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, cv))),
    )


def record_fields_of(e, cv):
    """The fields (a map of name to code-value) of the record `cv`, which is known to be one."""
    return bim(
        e,
        asp_iface(e, "record"),
        "take_fields",
        lookup_v(e, xx(e), cve_type(e, cv), asp_iface(e, "record")),
        e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, cv))),
    )


def alloc(e, size_expr):
    """Staged (in a module method body): the record's pointer, null for a record without storage."""
    return e.if_else(
        e.eq(size_expr, e.n(0)),
        e.mb.as_(e.n(0), e.lower(in_(e, "pv"))),
        alloc_or_trap(
            e,
            e.call(up(e, e.fld(e.v("heap"), "malloc"), BODY_MOD), size_expr),
            up(e, e.v("ptr_to_int"), BODY_MOD),
            e.lower(in_(e, "i32")),
            e.call(fn_of(e, up(e, e.fld(e.v("lib"), "trap"), BODY_MOD)), e.tup()),
        ),
    )


def store_parts(e, label):
    """The `store` constructor's call: `(p, {name: value, ...})`, each field's value cast to its declared type (an
    owned field takes the owned value: a temporary or a binding's `move()`, which the record owns from then on,
    stored as its under) into its place."""
    return [
        e.let("els", _elements(e, a(e, "argument"))),
        e.let("pcv", unwrap_cve_m(e, e.call_m(e.v("els"), "get", e.int_of(0)))),
        e.let("rcv", unwrap_cve_m(e, e.call_m(e.v("els"), "get", e.int_of(1)))),
        e.if_only(
            e.not_(has_b(e, xx(e), cve_type(e, e.v("rcv")), asp_iface(e, "record"))),
            ret_m(e, err_cve(e, loc(e), label + ": new takes a record of the fields")),
        ),
        e.let("fields", record_fields_of(e, e.v("rcv"))),
        e.let("codes", e.list_new(code_t(e))),
        e.push(e.v("codes"), cve_code(e, e.v("pcv"))),
        e.foreach(
            acc(e, xx(e), in_(e, "rt"), "rt_m", "caps"),
            "c",
            e.seq(
                e.let("fcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", _field_access(e, e.v("c"), "name")))),
                e.let(
                    "ocv",
                    unwrap_cve_m(e, cast_value(e, xx(e), loc(e), _field_access(e, e.v("c"), "owned"), e.v("fcv"))),
                ),
                e.let(
                    "vcv",
                    e.if_else(
                        _field_access(e, e.v("c"), "drops"),
                        retag_values(e, e.v("ocv"), _field_access(e, e.v("c"), "ty")),
                        e.v("ocv"),
                    ),
                ),
                e.let(
                    "scv",
                    staged_in(
                        e,
                        e.mb.set(
                            place(e, e.mb.as_(graft(e, e.v("pcv")), up(e, e.v("pv"), BODY_MOD)), e.v("c")),
                            graft(e, e.v("vcv")),
                        ),
                    ),
                ),
                e.push(e.v("codes"), cve_code(e, e.v("scv"))),
            ),
        ),
        ret_m(e, ok_cve(e, cv_no(e, codes_seq(e, e.v("codes"))))),
    ]


def drop_parts(e):
    """The `drop` constructor's call: `(self)`, each owned field adopted into a binding whose drop destroys it."""
    return [
        e.let("codes", e.list_new(code_t(e))),
        e.push(e.v("codes"), cve_code(e, a(e, "argument"))),
        e.foreach(
            acc(e, xx(e), in_(e, "rt"), "rt_m", "caps"),
            "c",
            e.if_only(
                _field_access(e, e.v("c"), "drops"),
                e.push(
                    e.v("codes"),
                    cve_code(
                        e,
                        staged_in(
                            e,
                            e.seq(
                                e.let(
                                    "__o",
                                    e.mb.as_(
                                        place(
                                            e,
                                            e.mb.as_(graft(e, a(e, "argument")), up(e, e.v("pv"), BODY_MOD)),
                                            e.v("c"),
                                        ),
                                        e.lower(_field_access(e, e.v("c"), "own")),
                                    ),
                                )
                            ),
                        ),
                    ),
                ),
            ),
        ),
        ret_m(e, ok_cve(e, cv_no(e, codes_seq(e, e.v("codes"))))),
    ]


def ctor_type(e, x, obj, desc, kinds, extra_fields):
    """A constructor type `obj`: a constant callable (its function value is the unit cast to it) whose call emits
    the code of its kind (`kinds`: name → the host statements of its call) over the record's types and
    `extra_fields`; two are equal when their kinds and record types are."""
    spec = [("kind", str_(e)), ("size", e.mb.types_int())] + [(f, ty(e)) for f in CTOR_TYPES] + extra_fields
    fields = [p(f, ft) for f, ft in spec]
    def_iface(e, x, obj + "_m", *fields)
    def_obj(e, x, obj, desc, e.rec(*fields))
    x.append(e.impl_interface(e.v(obj), t(e, obj + "_m"), *[p(f, in_(e, f)) for f, _ in spec]))
    self_type(
        e,
        x,
        obj,
        e.cat(e.s(desc + " "), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        can_cast_from_unit(e),
        cast_from_empty(e),
        no_cast_to(e),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), obj + "_m"),
                    and_b(
                        e,
                        e.eq(in_(e, "kind"), acc(e, xx(e), a(e, "other"), obj + "_m", "kind")),
                        is_equal(e, xx(e), in_(e, "rt"), acc(e, xx(e), a(e, "other"), obj + "_m", "rt")),
                    ),
                )
            ),
        ),
    )
    dispatch = [e.if_only(e.eq(in_(e, "kind"), e.s(k)), e.seq(*kinds[k])) for k in kinds]
    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "function"),
            p("call", body(e, *dispatch, e.mb.panic(e.cat(e.s(desc + ": unknown kind "), in_(e, "kind"))))),
            p("exception_type", e.option_type_lowered_none()),
        )
    )
    return spec


def rctor(e, x):
    """The record constructor type `rctor`: `new` (allocate, store the fields, yield the raw record), `store`,
    `drop`."""

    def new_parts():
        return [
            e.let(
                "store",
                e.mb.as_(
                    mk(e, "rctor", p("kind", e.s("store")), *[p(f, in_(e, f)) for f in ["size"] + CTOR_TYPES]), ty(e)
                ),
            ),
            *call_result(
                e,
                staged_in(
                    e,
                    e.mb.labeled(
                        "m",
                        e.seq(
                            e.let("__p", alloc(e, e.lower(in_(e, "size")))),
                            e.call(fn_of(e, e.lower(e.v("store"))), e.tup(e.v("__p"), graft(e, a(e, "argument")))),
                            e.mb.return_to("m", e.mb.as_(e.v("__p"), e.lower(in_(e, "rt")))),
                        ),
                    ),
                ),
            ),
        ]

    ctor_type(
        e,
        x,
        "rctor",
        "record constructor",
        {"new": new_parts(), "store": store_parts(e, "record"), "drop": drop_parts(e)},
        [],
    )


def fields_parts(e, label, fields_cv):
    """Host statements laying out the fields of the record `fields_cv` (a record of types): bind `caps` (the
    `rfield` list), `size`, and `rtt` (the record handle type, a type value)."""
    parts = []
    parts.append(e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))))
    parts.append(e.let("cfields_rk", lookup(e, xx(e), cve_type(e, fields_cv), asp_iface(e, "record"))))
    parts.append(
        e.if_only(
            e.not_(e.fld(e.v("cfields_rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), label + ": fields must be a record of types")),
        )
    )
    parts.append(
        e.let(
            "cfields",
            bim(
                e,
                asp_iface(e, "record"),
                "take_fields",
                e.fld(e.v("cfields_rk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, fields_cv))),
            ),
        )
    )
    for name, elem_t in [
        ("names", str_(e)),
        ("tys", ty(e)),
        ("ctys", ty(e)),
        ("refs", ty(e)),
        ("owns", ty(e)),
        ("drops", bool_t(e)),
        ("sizes", e.mb.types_int()),
        ("aligns", e.mb.types_int()),
    ]:
        parts.append(e.let(name, e.list_new(elem_t)))
    parts.append(
        e.foreach(
            e.v("cfields"),
            "cent",
            e.seq(
                e.let("cname", key_str(e, e.fld(e.v("cent"), "key"))),
                *const_type_arg(e, label, unwrap_cve_m(e, e.fld(e.v("cent"), "value")), "cty"),
                e.let("cdrops", has_b(e, xx(e), e.v("cty"), e.mb.eval_aspect_drop_dynamic())),
                e.if_only(
                    and_b(e, e.v("cdrops"), e.not_(has_b(e, xx(e), e.v("cty"), e.v("owned_m")))),
                    ret_m(
                        e,
                        err_cve(
                            e,
                            loc(e),
                            e.cat(e.s(label + ": field "), e.v("cname"), e.s(" drops but is not an owned type")),
                        ),
                    ),
                ),
                e.let(
                    "craw",
                    e.if_else(
                        e.v("cdrops"),
                        bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("cty"), e.v("owned_m")), "value")),
                        e.v("cty"),
                    ),
                ),
                *size_of(e, label, e.v("craw"), "csize"),
                *align_of(e, label, e.v("craw"), "calign"),
                e.push(e.v("names"), e.v("cname")),
                e.push(e.v("tys"), e.v("craw")),
                e.push(e.v("ctys"), e.v("cty")),
                e.push(
                    e.v("refs"),
                    e.if_else(
                        e.v("cdrops"), e.call(e.lower(e.fld(e.v("destructor"), "borrow")), e.v("cty")), e.v("cty")
                    ),
                ),
                e.push(
                    e.v("owns"),
                    e.if_else(
                        e.v("cdrops"), e.call(e.lower(e.fld(e.v("destructor"), "adopt")), e.v("cty")), e.v("cty")
                    ),
                ),
                e.push(e.v("drops"), e.v("cdrops")),
                e.push(e.v("sizes"), e.v("csize")),
                e.push(e.v("aligns"), e.v("calign")),
                e.if_only(
                    e.not_(
                        or_b(
                            e,
                            e.eq(e.v("calign"), e.int_of(8)),
                            or_b(
                                e,
                                e.eq(e.v("calign"), e.int_of(4)),
                                or_b(e, e.eq(e.v("calign"), e.int_of(2)), e.eq(e.v("calign"), e.int_of(1))),
                            ),
                        )
                    ),
                    ret_m(
                        e,
                        err_cve(
                            e,
                            loc(e),
                            e.cat(
                                e.s(label + ": field "),
                                e.v("cname"),
                                e.s(" has the unsupported alignment "),
                                to_str(e, e.v("calign")),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    # The layout: by alignment, each field at a multiple of its own alignment, taking its size.
    parts.append(e.let("caps", e.list_new(lt(e, "rfield"))))
    parts.append(e.let("off", e.rec(p("v", e.int_of(0)))))
    for al in ALIGNS:
        parts.append(e.let("i", e.rec(p("v", e.int_of(0)))))
        parts.append(
            e.foreach(
                e.v("names"),
                "cname",
                e.seq(
                    e.let("k", e.fld(e.v("i"), "v")),
                    e.if_only(
                        e.eq(e.call_m(e.v("aligns"), "get", e.v("k")), e.int_of(al)),
                        e.seq(
                            e.let("craw", e.call_m(e.v("tys"), "get", e.v("k"))),
                            e.push(
                                e.v("caps"),
                                mk(
                                    e,
                                    "rfield",
                                    p("name", e.v("cname")),
                                    p("ty", e.v("craw")),
                                    p("ref", e.call_m(e.v("refs"), "get", e.v("k"))),
                                    p("own", e.call_m(e.v("owns"), "get", e.v("k"))),
                                    p("drops", e.call_m(e.v("drops"), "get", e.v("k"))),
                                    p("owned", e.call_m(e.v("ctys"), "get", e.v("k"))),
                                    p("pty", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("craw"))),
                                    p(
                                        "pref",
                                        e.call(
                                            e.lower(e.fld(e.v("lib"), "ptr")), e.call_m(e.v("refs"), "get", e.v("k"))
                                        ),
                                    ),
                                    p("off", e.fld(e.v("off"), "v")),
                                ),
                            ),
                            e.mb.set(
                                e.fld(e.v("off"), "v"),
                                e.mb.operator_add(e.fld(e.v("off"), "v"), e.call_m(e.v("sizes"), "get", e.v("k"))),
                            ),
                        ),
                    ),
                    e.incr(e.fld(e.v("i"), "v")),
                ),
            )
        )
    parts.append(
        e.let(
            "size",
            e.mb.operator_mul(
                e.mb.operator_div(e.mb.operator_add(e.fld(e.v("off"), "v"), e.int_of(7)), e.int_of(8)), e.int_of(8)
            ),
        )
    )
    parts.append(
        e.let(
            "rtt",
            e.mb.as_(
                mk(
                    e,
                    "rt",
                    p("id", fresh_unique(e)),
                    p("caps", e.v("caps")),
                    p("size", e.v("size")),
                    p("pv", e.v("pv")),
                ),
                ty(e),
            ),
        )
    )
    return parts


def ctor(e, obj, kind, extra):
    """A constructor type value (host) of `obj` and `kind` over the host's `rtt`, `size` and target types, plus the
    `extra` fields (pairs)."""
    return e.mb.as_(
        mk(
            e,
            obj,
            p("kind", e.s(kind)),
            p("size", e.v("size")),
            p("rt", e.v("rtt")),
            *[p(f, e.v(f)) for f in ["pv", "pi32", "i32"]],
            *extra,
        ),
        ty(e),
    )


def destroy_dep(e, name, dropt_expr):
    """Host: the destroy dependency type of the record `rtt`: the owned fields (the `drop` constructor `dropt_expr`,
    a host type value), then `free`."""
    steps = [
        e.call(fn_of(e, up(e, dropt_expr, BODY_HOST)), e.v("self")),
        e.call(up(e, e.fld(e.v("heap"), "free"), BODY_MOD), e.mb.as_(e.v("self"), up(e, e.v("pv"), BODY_HOST))),
    ]
    return e.call(
        e.lower(e.fld(e.v("lib"), "func_dep")),
        e.rec(
            p("name", e.s(name)),
            p("params", e.list_new(e.mb.types_string(), e.s("self"))),
            p(
                "ty",
                e.call(
                    e.lower(e.fld(e.v("lib"), "fn")),
                    e.rec(p("params", e.list_new(e.mb.eval_type(), e.v("rtt"))), p("ret", e.lower(e.v("void")))),
                ),
            ),
            p("body", e.stage(e.seq(*steps))),
        ),
    )


def module_lets(e, x):
    """The module-level imports and types the record machinery lowers (for closure-wasm.atz too)."""
    x.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("heap", e.import_local("heap", "wasm-alloc.atz")))
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.v("i32"))))
    x.append(e.let("ptr_cast", e.fld(e.v("lib"), "ptr_cast")))
    x.append(e.let("ptr_to_int", e.fld(e.v("lib"), "ptr_to_int")))
    x.append(e.let("int_to_ptr", e.fld(e.v("lib"), "int_to_ptr")))


def host_lets(e):
    """Host statements binding the target types the constructors take."""
    return [e.let(n, e.lower(e.v(n))) for n in ["pv", "pi32", "i32"]]


def record_fields(e, label, cv, bind):
    """Binds `bind` to the fields (a map of name to code-value) of the record `cv`, else errors out."""
    return [
        e.let(bind + "_rk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "record"))),
        e.if_only(
            e.not_(e.fld(e.v(bind + "_rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), label + ": " + bind + " must be a record")),
        ),
        e.let(
            bind,
            bim(
                e,
                asp_iface(e, "record"),
                "take_fields",
                e.fld(e.v(bind + "_rk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, cv))),
            ),
        ),
    ]


def argument(e, label, bind):
    """Binds `bind` to the const function's argument record's fields."""
    return [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), label + ": argument has no value"))),
        *record_fields(e, label, e.v("argv"), bind),
    ]


def field(e, fields, name):
    """The field `name` (a Python string, or a string expression) of the record fields `fields`."""
    return unwrap_cve_m(e, e.call_m(fields, "get", e.s(name) if isinstance(name, str) else name))


def cve_has(e, cv):
    return e.fld(e.call(e.fld(cv, "value"), e.tup()), "is_some")


def _type(e, x):
    """`record.type`: the layout, the destroy dependency, the owned type (in the staged result) and `new`."""
    parts = []
    parts += argument(e, "record.type", "fields")
    parts += host_lets(e)
    parts += fields_parts(e, "record.type", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("fields"))))
    parts.append(e.let("dropt", ctor(e, "rctor", "drop", [])))
    parts.append(e.let("newt", ctor(e, "rctor", "new", [])))
    parts.append(e.let("destroy", destroy_dep(e, "record_destroy", e.v("dropt"))))
    parts.append(
        e.ret(
            const_eval_in(
                e,
                xx(e),
                loc(e),
                e.stage(
                    e.mb.labeled(
                        "__r",
                        e.seq(
                            e.let(
                                "__owned",
                                e.call(
                                    e.fld(up(e, e.v("destructor"), BODY_MOD), "owning"),
                                    e.rec(
                                        p("under", e.lower(e.v("rtt"))),
                                        p("destroy", fn_of(e, e.lower(e.v("destroy")))),
                                        p("new", e.lower(e.v("newt"))),
                                    ),
                                ),
                            ),
                            e.mb.return_to(
                                "__r",
                                e.rec(
                                    p("type", e.fld(e.v("__owned"), "type")),
                                    p("own", e.fld(e.v("__owned"), "own")),
                                    p("raw", e.lower(e.v("rtt"))),
                                    p("new", e.fld(e.v("__owned"), "new")),
                                ),
                            ),
                        ),
                    )
                ),
            )
        )
    )
    const_fn(e, x, "type_b", "record.type", body(e, *parts))


def module(e):
    x = []
    module_lets(e, x)
    rfield(e, x)
    rt(e, x, "record")
    rctor(e, x)
    _type(e, x)
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("type_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
