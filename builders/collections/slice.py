"""slice-wasm.atz / slice-llvm.atz: bounds-checked views over a run of elements, one module per target from this
builder.

`slice.type(elem)` yields `{of}` for a constant element type `elem` (which must have values.atz's `size` aspect):
`of((ptr, len))` is the slice of `len` elements starting at `ptr` (a `ptr(elem)`); `of` is a callable type (not a
value), so modules may hold it in lowered setup blocks and bodies lower it. A slice is a compile-time pair of
two runtime values, the data pointer and the i32 length, so it binds and loads like any value and is dropped with its
parts; it has no single machine representation, so it cannot be a function parameter or return value. On a slice
value: `len` and `data` are its parts; `at(i)` is the element place; `sub((from, to))` is the sub-slice. Both trap
(wasm `unreachable`, llvm `llvm.trap`) when the index or range is out of bounds, through the `slice_idx` and
`slice_range` dependencies (`func_dep`), which a module gets when its code first uses them. A slice never owns its
elements.
"""

from ..core import values
from ..eco_mb import p
from ..target_mb import (
    a,
    acc,
    accessor,
    and_b,
    asp_id,
    asp_iface,
    bim,
    bim0,
    body,
    bool_t,
    call_result,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_none,
    code_seq,
    code_t,
    const_eval_in,
    const_fn,
    cv_of,
    cve_code,
    cve_has,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    graft,
    has,
    has_b,
    in_,
    int_t,
    is_equal,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    mk_arg,
    must_v,
    no_cast_to,
    ok_cve,
    outer,
    reinterpret,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    str_,
    t,
    to_str,
    ty,
    ty_desc,
    unwrap_cve_m,
    unwrap_m,
    xx,
)
from .vec import const_type_arg, size_of

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "slice-wasm.atz", LLVM: "slice-llvm.atz"}

PARTS = ["len", "data"]
METHODS = ["at", "sub"]
# What a slice type carries besides its two parts: the element and pointer types, i32, the two checking dependencies
# (callable types) and the element size.
BASE = ["elem", "pelem", "i32", "idx", "range", "elem_size"]

# Stage depths, as in vec.py: dependency bodies are staged in the const function's host body, two below the module;
# the setup staged in the caller's context also sits two below the module.
BODY_MOD = 2
SETUP_MOD = 2


def _up(e, expr, depth):
    for _ in range(depth):
        expr = e.lower(expr)
    return expr


class _Target:
    """What differs between the wasm and llvm modules: the import, the trap, pointer arithmetic."""

    def __init__(self, kind):
        self.kind = kind

    def imports(self, e, out):
        if self.kind == WASM:
            out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
        else:
            out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))

    def trap(self, e, depth):
        """A trap statement in target code; the wasm intrinsic is instantiated in the body (only its type is
        lowered)."""
        if self.kind == WASM:
            return e.call(e.call(_up(e, e.fld(e.v("lib"), "trap_fn"), depth), e.rec()), e.tup())
        return e.call(_up(e, e.fld(e.v("lib"), "trap"), depth), e.tup())

    def elem_ptr(self, e, base, idx, size, ptr_type):
        """The address of element `idx` of the array at `base`, as `ptr_type`; `i32` is a host local."""
        if self.kind == WASM:
            addr = e.mb.operator_add(e.mb.as_(base, e.lower(e.v("i32"))), e.mb.operator_mul(idx, size))
            return e.mb.as_(addr, ptr_type)
        return e.mb.operator_add(e.mb.as_(base, ptr_type), idx)


def _binding_t(e):
    return e.mb.eval_binding()


def _setter_t(e):
    return e.mb.builtin("eval", "binding_setter")


def _rec_xl(e, *fields):
    return e.rec(p("xx", xx(e)), p("loc", loc(e)), *fields)


def _staged(e, expr):
    return const_eval_in(e, xx(e), e.stage(expr))


def _codes(e, ret_t, *codes):
    """The target's sequence of the host code values `codes`; errors return `ret_t`."""
    return unwrap_m(e, code_seq(e, *codes), ret_t)


def _codes_v(e, *codes):
    """`_codes` where the method cannot return errors (binding use)."""
    return must_v(e, "slice", code_seq(e, *codes), "sequencing codes")


def _val_only(e, cv):
    return cv_of(e, code_none(e, loc(e)), cve_value(e, cv))


def _sl_new(e, slt, data_cv, len_cv):
    """A slice type like `slt` (an `sl`) with the parts `data_cv` and `len_cv` (value-only code values)."""
    return mk(e, "sl", *[p(f, acc(e, xx(e), slt, "sl_m", f)) for f in BASE], p("data", data_cv), p("len", len_cv))


def _slice_value(e, code, slt):
    """The slice value of type `slt`, carrying `code` (what computes its parts)."""
    return cv_of(e, code, e.call(e.eval_builtin("value_object_const"), e.rec(p("type", slt), p("data", e.tup()))))


def _tuple_args(e, label, cv, count):
    """Splits the tuple code-value `cv` into `args` ("0", "1", ...), requiring exactly `count` elements."""
    msg = label + ": argument must be a tuple of " + str(count) + " values"
    return [
        e.let("tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "tuple"))),
        e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, err_cve(e, loc(e), msg))),
        e.let("args", e.map_new(str_(e), e.mb.types_cve())),
        e.let("an", e.rec(p("i", e.int_of(0)))),
        e.foreach(
            bim(
                e,
                asp_iface(e, "tuple"),
                "take_elements",
                e.fld(e.v("tk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, cv))),
            ),
            "er",
            e.seq(
                e.call_m(e.v("args"), "put", e.tup(to_str(e, e.fld(e.v("an"), "i")), unwrap_cve_m(e, e.v("er")))),
                e.incr(e.fld(e.v("an"), "i")),
            ),
        ),
        e.if_only(e.not_(e.eq(e.fld(e.v("an"), "i"), e.int_of(count))), ret_m(e, err_cve(e, loc(e), msg))),
    ]


def _arg(e, i):
    return e.call_m(e.v("args"), "get", e.s(str(i)))


def _idx_body(e, tg):
    """slice_idx(i, len) -> i32: `i` when 0 <= i < len, else a trap."""
    d = BODY_MOD
    return e.seq(
        e.if_only(e.mb.operator_lt(e.v("i"), e.n(0)), tg.trap(e, d)),
        e.if_only(e.mb.operator_ge(e.v("i"), e.v("len")), tg.trap(e, d)),
        e.ret(e.v("i")),
    )


def _range_body(e, tg):
    """slice_range(from, to, len) -> i32: `to - from` when 0 <= from <= to <= len, else a trap."""
    d = BODY_MOD
    return e.seq(
        e.if_only(e.mb.operator_lt(e.v("from"), e.n(0)), tg.trap(e, d)),
        e.if_only(e.mb.operator_lt(e.v("to"), e.v("from")), tg.trap(e, d)),
        e.if_only(e.mb.operator_gt(e.v("to"), e.v("len")), tg.trap(e, d)),
        e.ret(e.mb.operator_sub(e.v("to"), e.v("from"))),
    )


def _deps(e, tg, out):
    """In the const function's host body: the checking dependencies (constants from here on)."""
    for fn, fn_t, params, fbody in [
        ("idx", "idx_t", ("i", "len"), _idx_body(e, tg)),
        ("range", "range_t", ("from", "to", "len"), _range_body(e, tg)),
    ]:
        out.append(
            e.let(
                fn,
                e.call(
                    e.lower(e.fld(e.v("lib"), "func_dep")),
                    e.rec(
                        p("name", e.s("slice_" + fn)),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.lower(e.v(fn_t))),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )


def _setup(e):
    """Staged in the caller's context: the `of` callable for `elem` over the lowered dependencies."""
    out = []
    for name in ["elem", "idx", "range", "elem_size"]:
        out.append(e.let(name, e.lower(e.v(name))))
    out.append(e.let("i32", _up(e, e.v("i32"), SETUP_MOD)))
    out.append(e.let("pelem", e.call(_up(e, e.fld(e.v("lib"), "ptr"), SETUP_MOD), e.v("elem"))))
    out.append(
        e.let(
            "of",
            e.mb.as_(
                e.call(_up(e, e.fld(e.v("slof"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in BASE])),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(e.ret(e.rec(p("of", e.v("of")))))
    return e.mb.seq(out)


def _objs(e, x, tg):
    base_fields = [p(f, int_t(e) if f == "elem_size" else ty(e)) for f in BASE]
    sl_fields = base_fields + [p("data", e.mb.types_cve()), p("len", e.mb.types_cve())]
    def_iface(e, x, "slof_m", *base_fields)
    def_obj(e, x, "slof", "slice constructor", e.rec(*base_fields))
    def_iface(e, x, "sl_m", *sl_fields)
    def_obj(e, x, "sl", "slice type", e.rec(*sl_fields))
    def_obj(e, x, "slmeth", "slice method", e.rec(p("kind", str_(e)), p("sl", ty(e))))
    slb_fields = [p("sl", ty(e)), p("bdata", _binding_t(e)), p("blen", _binding_t(e))]
    def_obj(e, x, "slb", "slice binding", e.rec(*slb_fields))
    for name, typ in slb_fields:
        accessor(e, x, "slb", name, typ)
    def_obj(e, x, "slsetter", "slice part setter", e.tup())
    no = no_cast_to(e)

    # ---- the constructor `of((ptr, len))`: a constant callable that modules bind and export ----
    x.append(e.impl_interface(e.v("slof"), t(e, "slof_m"), *[p(f, in_(e, f)) for f in BASE]))
    self_type(
        e,
        x,
        "slof",
        e.cat(e.s("slice.of("), ty_desc(e, in_(e, "elem")), e.s(")")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no,
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "slof_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "slof_m", "elem")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "slof")
    rt_bind_impl(e, x, "slof", e.mb.types_string())
    rt_use_impl(e, x, "slof")
    x.append(
        e.impl_interface(
            e.v("slof"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    *_tuple_args(e, "slice.of", a(e, "argument"), 2),
                    e.let("c0", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "pelem"), _arg(e, 0)))),
                    e.let("c1", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "i32"), _arg(e, 1)))),
                    e.let(
                        "code",
                        _codes(
                            e,
                            e.mb.types_cve(),
                            cve_code(e, a(e, "self")),
                            cve_code(e, e.v("c0")),
                            cve_code(e, e.v("c1")),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            _slice_value(
                                e,
                                e.v("code"),
                                mk(
                                    e,
                                    "sl",
                                    *[p(f, in_(e, f)) for f in BASE],
                                    p("data", _val_only(e, e.v("c0"))),
                                    p("len", _val_only(e, e.v("c1"))),
                                ),
                            ),
                        )
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )

    # ---- the slice type ----
    x.append(e.impl_interface(e.v("sl"), t(e, "sl_m"), *[p(f, in_(e, f)) for f in BASE + PARTS]))
    self_type(
        e,
        x,
        "sl",
        e.cat(e.s("slice("), ty_desc(e, in_(e, "elem")), e.s(")")),
        e.aspect_dispatch(asp_id(e, "field"), e.mb.eval_aspect_drop_dynamic_id(), asp_id(e, "bind"), lv(e, "sl_m_id")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "sl_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "sl_m", "elem")),
                )
            ),
        ),
    )
    # The parts are a pointer and an i32: nothing to drop.
    x.append(
        e.impl_interface(
            e.v("sl"), e.mb.eval_aspect_drop_dynamic(), p("drop", e.eresult_ok(code_t(e), code_none(e, loc(e))))
        )
    )
    br_t = e.mb.types_bind_result()

    def bind_part(bind, part_type, cv):
        return e.let(
            bind,
            unwrap_m(
                e,
                bim(
                    e,
                    e.mb.eval_aspect_bind(),
                    "bind",
                    lookup_v(e, xx(e), part_type, e.mb.eval_aspect_bind()),
                    _rec_xl(e, p("cv", cv)),
                ),
                br_t,
            ),
        )

    x.append(
        e.impl_interface(
            e.v("sl"),
            e.mb.eval_aspect_bind(),
            p(
                "bind",
                body(
                    e,
                    # The slice's carried code computes both parts; it goes before the data part's store.
                    bind_part("rd", in_(e, "pelem"), cv_of(e, cve_code(e, a(e, "cv")), cve_value(e, in_(e, "data")))),
                    bind_part("rl", in_(e, "i32"), _val_only(e, in_(e, "len"))),
                    e.let("code", _codes(e, br_t, e.fld(e.v("rd"), "code"), e.fld(e.v("rl"), "code"))),
                    e.ret(
                        e.eresult_ok(
                            br_t,
                            e.call(
                                e.mb.eval_bind_result(),
                                e.rec(
                                    p("code", e.v("code")),
                                    p(
                                        "binding",
                                        mk(
                                            e,
                                            "slb",
                                            p("sl", outer(e)),
                                            p("bdata", e.fld(e.v("rd"), "binding")),
                                            p("blen", e.fld(e.v("rl"), "binding")),
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
    x.append(
        e.impl_interface(
            e.v("sl"),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "slice: field must be a constant string")),
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
                    *[
                        e.if_only(
                            e.eq(e.v("key"), e.s(part)),
                            ret_m(e, ok_cve(e, cv_of(e, cve_code(e, a(e, "self")), cve_value(e, in_(e, part))))),
                        )
                        for part in PARTS
                    ],
                    *[
                        e.if_only(
                            e.eq(e.v("key"), e.s(m)),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        cve_code(e, a(e, "self")),
                                        e.call(
                                            e.eval_builtin("value_object_const"),
                                            e.rec(
                                                p("type", mk(e, "slmeth", p("kind", e.s(m)), p("sl", outer(e)))),
                                                p("data", e.tup()),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                        for m in METHODS
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("slice has no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.list_new(e.mb.types_constkey(), *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in PARTS + METHODS]),
            ),
        )
    )

    # ---- methods: a callable whose type carries the slice type (and so its parts) ----
    self_type(
        e,
        x,
        "slmeth",
        e.cat(e.s("slice."), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )

    def staged(expr):
        return unwrap_cve_m(e, _staged(e, expr))

    def sl_field(name):
        return acc(e, xx(e), in_(e, "sl"), "sl_m", name)

    x.append(
        e.impl_interface(
            e.v("slmeth"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    *[e.let(f, sl_field(f)) for f in ["pelem", "i32", "idx", "range", "elem_size", "data", "len"]],
                    e.if_only(
                        e.eq(in_(e, "kind"), e.s("at")),
                        e.seq(
                            *call_result(
                                e,
                                staged(
                                    e.mb.field(
                                        graft(e, e.v("data")),
                                        e.call(
                                            e.lower(e.v("idx")),
                                            e.tup(graft(e, a(e, "argument")), graft(e, e.v("len"))),
                                        ),
                                    )
                                ),
                            )
                        ),
                    ),
                    # sub((from, to)): the arguments' codes run once; their values feed the range check and the
                    # pointer arithmetic.
                    *_tuple_args(e, "slice.sub", a(e, "argument"), 2),
                    e.let("v0", _val_only(e, _arg(e, 0))),
                    e.let("v1", _val_only(e, _arg(e, 1))),
                    e.let(
                        "lcv",
                        staged(
                            e.call(
                                e.lower(e.v("range")),
                                e.tup(graft(e, e.v("v0")), graft(e, e.v("v1")), graft(e, e.v("len"))),
                            )
                        ),
                    ),
                    e.let(
                        "dcv",
                        staged(
                            tg.elem_ptr(
                                e,
                                graft(e, e.v("data")),
                                graft(e, e.v("v0")),
                                e.lower(e.v("elem_size")),
                                e.lower(e.v("pelem")),
                            )
                        ),
                    ),
                    e.let(
                        "code",
                        _codes(
                            e,
                            e.mb.types_cve(),
                            cve_code(e, a(e, "self")),
                            cve_code(e, _arg(e, 0)),
                            cve_code(e, _arg(e, 1)),
                            cve_code(e, e.v("lcv")),
                            cve_code(e, e.v("dcv")),
                        ),
                    ),
                    e.ret(
                        ok_cve(
                            e,
                            _slice_value(
                                e,
                                e.v("code"),
                                _sl_new(e, in_(e, "sl"), _val_only(e, e.v("dcv")), _val_only(e, e.v("lcv"))),
                            ),
                        )
                    ),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )

    # ---- the binding: the two parts' bindings ----

    def part_use(binding, code):
        return bim(
            e, _binding_t(e), "use", binding, _rec_xl(e, p("setter", mk_arg(e, "slsetter", e.tup())), p("code", code))
        )

    def slb_new(bdata, blen):
        return mk(e, "slb", p("sl", in_(e, "sl")), p("bdata", bdata), p("blen", blen))

    x.append(
        e.impl_interface(
            e.v("slb"),
            _binding_t(e),
            p(
                "use",
                body(
                    e,
                    e.let("ud", part_use(in_(e, "bdata"), a(e, "code"))),
                    e.let("ul", part_use(in_(e, "blen"), code_none(e, loc(e)))),
                    e.ret(
                        _slice_value(
                            e,
                            _codes_v(e, cve_code(e, e.v("ud")), cve_code(e, e.v("ul"))),
                            _sl_new(e, in_(e, "sl"), _val_only(e, e.v("ud")), _val_only(e, e.v("ul"))),
                        )
                    ),
                ),
            ),
            p(
                "drop",
                body(
                    e,
                    e.let("dl", unwrap_m(e, bim(e, _binding_t(e), "drop", in_(e, "blen"), _rec_xl(e)), code_t(e))),
                    e.let("dd", unwrap_m(e, bim(e, _binding_t(e), "drop", in_(e, "bdata"), _rec_xl(e)), code_t(e))),
                    e.ret(e.eresult_ok(code_t(e), _codes(e, code_t(e), e.v("dl"), e.v("dd")))),
                ),
            ),
            p(
                "fork",
                slb_new(
                    bim0(e, _binding_t(e), "fork", in_(e, "bdata")), bim0(e, _binding_t(e), "fork", in_(e, "blen"))
                ),
            ),
            p(
                "merge",
                body(
                    e,
                    e.let("ds", e.list_new(_binding_t(e))),
                    e.let("ls", e.list_new(_binding_t(e))),
                    e.foreach(
                        a(e, "others"),
                        "o",
                        e.seq(
                            e.let("ob", reinterpret(e, e.v("o"), "slb")),
                            e.push(e.v("ds"), e.call_m(e.v("ob"), "bdata", e.tup())),
                            e.push(e.v("ls"), e.call_m(e.v("ob"), "blen", e.tup())),
                        ),
                    ),
                    e.let(
                        "md",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "bdata"), _rec_xl(e, p("others", e.v("ds")))),
                            _binding_t(e),
                        ),
                    ),
                    e.let(
                        "ml",
                        unwrap_m(
                            e,
                            bim(e, _binding_t(e), "merge", in_(e, "blen"), _rec_xl(e, p("others", e.v("ls")))),
                            _binding_t(e),
                        ),
                    ),
                    e.ret(e.eresult_ok(_binding_t(e), slb_new(e.v("md"), e.v("ml")))),
                ),
            ),
        )
    )
    # A slice's parts cannot be assigned through it.
    x.append(e.impl_interface(e.v("slsetter"), _setter_t(e), p("set", e.mb.as_(e.b(False), bool_t(e)))))


def module(e, kind):
    tg = _Target(kind)
    x = []
    tg.imports(e, x)
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    for name, count in [("idx_t", 2), ("range_t", 3)]:
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("lib"), "fn"),
                    e.rec(
                        p("params", e.list_new(e.mb.eval_type(), *[e.v("i32") for _ in range(count)])),
                        p("ret", e.v("i32")),
                    ),
                ),
            )
        )
    _objs(e, x, tg)
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "slice.type: argument has no value"))),
        *const_type_arg(e, "slice.type", e.v("argv"), "elem"),
        *size_of(e, "slice.type", e.v("elem"), "elem_size"),
    ]
    _deps(e, tg, parts)
    parts.append(e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))))
    const_fn(e, x, "slice_b", "slice.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("slice_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
