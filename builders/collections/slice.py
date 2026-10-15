"""slice-wasm.atz / slice-llvm.atz: bounds-checked views over a run of elements, one module per target from this
builder.

`slice.type(elem)` yields `{type, idx}` for a constant element type `elem` (which must have values.atz's `size` aspect).
A slice is the target's tuple `(ptr(elem), i32)` (the data pointer and the length) viewed as its own type, so it
binds, is assigned, passed and returned exactly like that tuple; `(ptr, len) as type` makes one. On a slice value:
`len` and `data` are its parts (places); `at(i)` is the element place; `sub((from, to))` is the sub-slice. Both trap
(wasm `unreachable`, llvm `llvm.trap`) when the index or range is out of bounds, through the `slice_idx` and
`slice_range` dependencies (`func_dep`), which a module gets when its code first uses them; `idx` is the
`slice_idx` dependency's callable type, for other bounds-checked element access (vec's `at`). A slice never owns its
elements.
"""

from ..core import values
from ..eco_mb import p
from ..target_mb import (
    a,
    asp_iface,
    bim,
    body,
    const_eval_in,
    const_fn,
    const_type_arg,
    cve_has,
    cve_type,
    cve_value,
    err_cve,
    fn_of,
    graft,
    handle_methods,
    handle_type,
    in_,
    int_t,
    lookup,
    loc,
    ret_m,
    retag_values,
    str_,
    to_str,
    ty,
    ty_desc,
    unwrap_cve_m,
    xx,
)
from .vec import size_of

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "slice-wasm.atz", LLVM: "slice-llvm.atz"}

METHODS = ["at", "sub"]
# What a slice type carries: the element, pointer, i32 and tuple types, the two checking dependencies (callable
# types) and the element size.
BASE = ["elem", "pelem", "i32", "pt", "idx", "range", "elem_size"]

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
        """A trap statement in target code: the target's trap, a callable type, called through its function value."""
        return e.call(fn_of(e, _up(e, e.fld(e.v("lib"), "trap"), depth)), e.tup())

    def elem_ptr(self, e, base, idx, size, ptr_type):
        """The address of element `idx` of the array at `base`, as `ptr_type`; `i32` is a host local."""
        if self.kind == WASM:
            addr = e.mb.operator_add(e.mb.as_(base, e.lower(e.v("i32"))), e.mb.operator_mul(idx, size))
            return e.mb.as_(addr, ptr_type)
        return e.mb.operator_add(e.mb.as_(base, ptr_type), idx)


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
    """Staged in the caller's context: the slice type for `elem` over the lowered dependencies and types."""
    out = []
    for name in BASE:
        out.append(e.let(name, e.lower(e.v(name))))
    out.append(e.let("type", e.call(_up(e, e.fld(e.v("sl"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in BASE]))))
    out.append(e.ret(e.rec(p("type", e.v("type")), p("idx", e.v("idx")))))
    return e.mb.seq(out)


def _objs(e, x, tg):
    fields = [p(f, int_t(e) if f == "elem_size" else ty(e)) for f in BASE]

    # The parts: places over the receiver cast to the tuple (a handle casts to its representation).
    places = {
        "data": lambda self_as: e.mb.field(self_as("pt"), e.n(0)),
        "len": lambda self_as: e.mb.field(self_as("pt"), e.n(1)),
    }
    meth = handle_type(
        e,
        x,
        "sl",
        "sl_m",
        "slice",
        fields,
        places,
        METHODS,
        under="pt",
        construct=True,
        desc_expr=e.cat(e.s("slice("), ty_desc(e, in_(e, "elem")), e.s(")")),
        identity="elem",
    )

    def tv():
        return graft(e, e.v("tv"))

    def data():
        return e.mb.as_(e.mb.field(tv(), e.n(0)), e.lower(e.v("pelem")))

    def length():
        return e.mb.field(tv(), e.n(1))

    def method_body(kind):
        if kind == "at":
            return e.mb.field(
                data(), e.call(fn_of(e, e.lower(e.v("idx"))), e.tup(graft(e, a(e, "argument")), length()))
            )
        if kind == "sub":
            # sub((from, to)): the arguments run once each; the range check traps before the pointer moves.
            return e.mb.labeled(
                "sub",
                e.seq(
                    e.let("from", graft(e, _arg(e, 0))),
                    e.let("to", graft(e, _arg(e, 1))),
                    e.let("n", e.call(fn_of(e, e.lower(e.v("range"))), e.tup(e.v("from"), e.v("to"), length()))),
                    e.mb.return_to(
                        "sub",
                        e.mb.as_(
                            e.tup(
                                tg.elem_ptr(e, data(), e.v("from"), e.lower(e.v("elem_size")), e.lower(e.v("pelem"))),
                                e.v("n"),
                            ),
                            e.lower(e.v("slt")),
                        ),
                    ),
                ),
            )
        raise AssertionError(kind)

    handle_methods(
        e,
        x,
        meth,
        "sl_m",
        fields,
        METHODS,
        method_body,
        prelude=[e.let("tv", retag_values(e, e.v("recv"), e.v("pt"))), e.let("slt", in_(e, "ht"))],
        kind_prelude={"sub": _tuple_args(e, "slice.sub", a(e, "argument"), 2)},
    )


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
    parts.append(e.let("i32", e.lower(e.v("i32"))))
    parts.append(e.let("pelem", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("elem"))))
    parts.append(
        e.let(
            "pt",
            e.call(e.lower(e.fld(e.v("lib"), "tuple")), e.list_new(e.mb.eval_type(), e.v("pelem"), e.v("i32"))),
        )
    )
    parts.append(e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))))
    const_fn(e, x, "slice_b", "slice.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("slice_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
