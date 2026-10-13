"""vec-wasm.atz / vec-llvm.atz: growable arrays on a heap, one module per target from this builder.

`vec.type(elem)` yields `{type, raw, new}` for a constant element type `elem` (which must have values.atz's `size`
aspect):
- a vec is a pointer to a 16-byte header: data pointer at 0, length (i32) at 8, capacity (i32) at 12;
- `new()` yields an empty vec; `type(new())` makes it an owned value (destructor.atz) whose drop frees the data and
  the header; `raw` is the unowned handle type (what `type` wraps);
- on a vec value: `len`, `cap`, `data` (ptr(elem)) are places; `at(i)` is the element place; `push(x)`, `clear()`
  are methods; `pop()` is `some` of the last element taken off the vec, or `none` when the vec is empty
  (option.atz); `slice()` is the slice (slice.atz) of the current elements. These are staged inline where used. `at`
  is bounds-checked through the slice: an index out of range traps.
The helper functions `vec_<elem>_grow`, `_free` and `_new` are dependencies (`func_dep`): a module gets them when
its code first uses them. Memory comes from wasm-alloc.atz (wasm) or libc (llvm). A byte vec plus the target's string
conversion stands in for a growable string.
"""

from ..memory import destructor
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
    call_result,
    cast_to_panic,
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
    ident_of,
    in_,
    is_equal,
    is_runtime,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    ok_cve,
    or_b,
    outer,
    ret_m,
    self_type,
    str_,
    t,
    ty,
    ty_desc,
    type_aspect,
    unwrap_cve_m,
    xx,
)

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "vec-wasm.atz", LLVM: "vec-llvm.atz"}

HEADER = 16
LEN_CELL = 2
CAP_CELL = 3
MIN_CAP = 4

METHODS = ["at", "push", "pop", "clear", "slice"]
PLACES = ["len", "cap", "data"]

# Stage depths. The dependencies are made in the const function's host body (so they are constants wherever they are
# lowered); their bodies are staged there, so a body sees the host locals one lower up and module-level values two
# up. The setup staged in the caller's context also sits one below the host body.
BODY_MOD = 2
BODY_HOST = 1
SETUP_MOD = 2


def _up(e, expr, depth):
    for _ in range(depth):
        expr = e.lower(expr)
    return expr


class _Target:
    """What differs between the wasm and llvm modules: imports, the allocator, sizes, null, the byte copy."""

    def __init__(self, kind):
        self.kind = kind

    def imports(self, e, out):
        if self.kind == WASM:
            out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
            out.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
        else:
            out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))
            out.append(e.let("heap", e.import_local("libc", "libc-2.42.atz")))
        out.append(e.let("slice", e.import_local("slice", "slice-" + self.kind + ".atz")))
        out.append(e.let("option", e.import_local("option", "option-" + self.kind + ".atz")))

    def module_lets(self, e, out):
        """Module-level types the bodies and host code lower."""
        if self.kind == LLVM:
            out.append(
                e.let(
                    "pv_gt",
                    e.call(e.fld(e.v("lib"), "global_t"), e.rec(p("ty", e.v("pv")), p("mem", e.b(False)))),
                )
            )

    def host_lets(self, e, out):
        """In the const function's host body: llvm's null pointer reference (its type must be a constant there)."""
        if self.kind == LLVM:
            out.append(
                e.let(
                    "null_v",
                    e.call(
                        e.lower(e.fld(e.v("lib"), "ref_fn")),
                        e.rec(p("ref", e.s("null")), p("ty", e.lower(e.v("pv_gt")))),
                    ),
                )
            )

    def null(self, e, depth):
        """The null pointer (in target code)."""
        if self.kind == WASM:
            return e.mb.as_(e.n(0), _up(e, e.v("pv"), depth))
        return _up(e, e.v("null_v"), BODY_HOST)

    def size(self, e, n, depth):
        """`n` (i32) as the allocator's size argument."""
        if self.kind == WASM:
            return n
        return e.call(_up(e, e.fld(e.v("lib"), "u64"), depth), n)

    def malloc(self, e, n, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "malloc"), depth), self.size(e, n, depth))

    def free(self, e, ptr, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "free"), depth), ptr)

    def copy(self, e, dst, src, n, depth):
        """Copies `n` bytes; a statement. The wasm intrinsic is instantiated in the body (only its type is lowered)."""
        if self.kind == WASM:
            return e.call(e.call(_up(e, e.fld(e.v("lib"), "memory_copy_fn"), depth), e.rec()), e.tup(dst, src, n))
        return e.call(_up(e, e.fld(e.v("heap"), "memcpy"), depth), e.tup(dst, src, self.size(e, n, depth)))


def _cell(e, h, index, depth):
    """Header cell `index` (i32) of the vec whose header is `h`."""
    return e.mb.field(e.mb.as_(h, _up(e, e.v("pi32"), depth)), e.n(index))


def _data_cell(e, h, depth):
    return e.mb.field(e.mb.as_(h, _up(e, e.v("ppv"), depth)), e.n(0))


def _grow_body(e, tg):
    """grow(v, min_cap): reallocate the data to hold at least min_cap elements (doubling)."""
    d = BODY_MOD
    size = _up(e, e.v("elem_size"), BODY_HOST)
    return e.seq(
        e.let("old_cap", _cell(e, e.v("v"), CAP_CELL, d)),
        e.let("doubled", e.mb.operator_mul(e.v("old_cap"), e.n(2))),
        e.let(
            "cap1",
            e.if_else(e.mb.operator_gt(e.v("doubled"), e.v("min_cap")), e.v("doubled"), e.v("min_cap")),
        ),
        e.let("cap", e.if_else(e.mb.operator_gt(e.v("cap1"), e.n(MIN_CAP)), e.v("cap1"), e.n(MIN_CAP))),
        e.let("fresh", tg.malloc(e, e.mb.operator_mul(e.v("cap"), size), d)),
        e.let("old", _data_cell(e, e.v("v"), d)),
        e.if_only(
            e.not_(e.eq(e.v("old"), tg.null(e, d))),
            e.seq(
                tg.copy(e, e.v("fresh"), e.v("old"), e.mb.operator_mul(_cell(e, e.v("v"), LEN_CELL, d), size), d),
                tg.free(e, e.v("old"), d),
            ),
        ),
        e.mb.set(_data_cell(e, e.v("v"), d), e.v("fresh")),
        e.mb.set(_cell(e, e.v("v"), CAP_CELL, d), e.v("cap")),
    )


def _free_body(e, tg):
    d = BODY_MOD
    return e.seq(
        e.let("old", _data_cell(e, e.v("v"), d)),
        e.if_only(e.not_(e.eq(e.v("old"), tg.null(e, d))), tg.free(e, e.v("old"), d)),
        tg.free(e, e.v("v"), d),
    )


def _new_body(e, tg):
    d = BODY_MOD
    return e.seq(
        e.let("h", tg.malloc(e, e.n(HEADER), d)),
        e.mb.set(_data_cell(e, e.v("h"), d), tg.null(e, d)),
        e.mb.set(_cell(e, e.v("h"), LEN_CELL, d), e.n(0)),
        e.mb.set(_cell(e, e.v("h"), CAP_CELL, d), e.n(0)),
        e.ret(e.v("h")),
    )


def _deps(e, tg, out):
    """In the const function's host body: the dependencies for `elem` (constants from here on)."""
    for fn, fn_t, params, fbody in [
        ("grow", "grow_t", ("v", "min_cap"), _grow_body(e, tg)),
        ("free_vec", "free_t", ("v",), _free_body(e, tg)),
        ("new", "new_t", (), _new_body(e, tg)),
    ]:
        out.append(
            e.let(
                fn,
                e.call(
                    e.lower(e.fld(e.v("lib"), "func_dep")),
                    e.rec(
                        p("name", e.cat(e.v("name"), e.s("_" + fn))),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.lower(e.v(fn_t))),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )


def _setup(e):
    """Staged in the caller's context: the vec types for `elem` over the lowered dependencies."""
    out = []
    for name in ["elem", "grow", "free_vec", "new"]:
        out.append(e.let(name, e.lower(e.v(name))))
    for name in ["pv", "pi32", "ppv"]:
        out.append(e.let(name, _up(e, e.v(name), SETUP_MOD)))
    out.append(e.let("pelem", e.call(_up(e, e.fld(e.v("lib"), "ptr"), SETUP_MOD), e.v("elem"))))
    out.append(e.let("slice_of", e.fld(e.call(_up(e, e.fld(e.v("slice"), "type"), SETUP_MOD), e.v("elem")), "of")))
    out.append(e.let("opt_of", e.fld(e.call(_up(e, e.fld(e.v("option"), "type"), SETUP_MOD), e.v("elem")), "of")))
    out.append(
        e.let(
            "raw",
            e.mb.as_(
                e.call(
                    _up(e, e.fld(e.v("vt"), "new"), SETUP_MOD),
                    e.rec(
                        p("elem", e.v("elem")),
                        p("pv", e.v("pv")),
                        p("pi32", e.v("pi32")),
                        p("ppv", e.v("ppv")),
                        p("pelem", e.v("pelem")),
                        p("grow", e.v("grow")),
                        p("slice_of", e.v("slice_of")),
                        p("opt_of", e.v("opt_of")),
                    ),
                ),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(
        e.let(
            "owned",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", e.v("free_vec"))),
            ),
        )
    )
    out.append(e.ret(e.rec(p("type", e.v("owned")), p("raw", e.v("raw")), p("new", e.v("new")))))
    return e.mb.seq(out)


def _vt(e, x):
    """The unowned vec handle type: a pointer carrying the element type, the vec's places and methods, its grow
    dependency and the slice constructor for its elements."""
    fields = [
        p("elem", ty(e)),
        p("pv", ty(e)),
        p("pi32", ty(e)),
        p("ppv", ty(e)),
        p("pelem", ty(e)),
        p("grow", ty(e)),
        p("slice_of", ty(e)),
        p("opt_of", ty(e)),
    ]
    def_iface(e, x, "vt_m", *fields)
    def_obj(e, x, "vt", "vec type", e.rec(*fields))
    def_obj(e, x, "vmeth", "vec method", e.rec(p("kind", str_(e)), p("vt", ty(e)), p("self", e.mb.types_cve())))
    x.append(e.impl_interface(e.v("vt"), t(e, "vt_m"), *[p(k, in_(e, k)) for k, _ in fields]))
    self_type(
        e,
        x,
        "vt",
        e.cat(e.s("vec("), ty_desc(e, in_(e, "elem")), e.s(")")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "vt_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, "pv"), a(e, "key")),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    is_equal(e, xx(e), in_(e, "pv"), a(e, "source_type")),
                )
            ),
        ),
        # A raw pointer becomes a vec handle by retagging (values.atz).
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.match_of(
                e.call(
                    e.mb.reinterpret(),
                    e.tup(loc(e), cve_value(e, a(e, "cv")), e.lower(e.fld(e.v("values"), "retag"))),
                ),
                "__t",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, a(e, "cv")),
                                bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), outer(e)),
                            ),
                        ),
                    ),
                ),
                p("errs", ret_m(e, err_cve(e, loc(e), "vec: only runtime pointers can become vecs"))),
            ),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "vt_m"),
                    is_equal(e, xx(e), in_(e, "elem"), acc(e, xx(e), a(e, "other"), "vt_m", "elem")),
                )
            ),
        ),
    )

    def staged(expr):
        return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(expr)))

    def self_as(type_field):
        return e.mb.as_(graft(e, a(e, "self")), e.lower(in_(e, type_field)))

    x.append(
        e.impl_interface(
            e.v("vt"),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "vec: field must be a constant string")),
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
                    e.if_only(
                        e.eq(e.v("key"), e.s("len")),
                        ret_m(e, ok_cve(e, staged(e.mb.field(self_as("pi32"), e.n(LEN_CELL))))),
                    ),
                    e.if_only(
                        e.eq(e.v("key"), e.s("cap")),
                        ret_m(e, ok_cve(e, staged(e.mb.field(self_as("pi32"), e.n(CAP_CELL))))),
                    ),
                    e.if_only(
                        e.eq(e.v("key"), e.s("data")),
                        ret_m(
                            e,
                            ok_cve(
                                e,
                                staged(e.mb.as_(e.mb.field(self_as("ppv"), e.n(0)), e.lower(in_(e, "pelem")))),
                            ),
                        ),
                    ),
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
                                                p(
                                                    "type",
                                                    mk(
                                                        e,
                                                        "vmeth",
                                                        p("kind", e.s(m)),
                                                        p("vt", outer(e)),
                                                        p(
                                                            "self",
                                                            cv_of(
                                                                e,
                                                                e.call(e.eval_builtin("code_none"), loc(e)),
                                                                cve_value(e, a(e, "self")),
                                                            ),
                                                        ),
                                                    ),
                                                ),
                                                p("data", e.tup()),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                        for m in METHODS
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("vec has no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.list_new(e.mb.types_constkey(), *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in PLACES + METHODS]),
            ),
        )
    )
    # Methods: a callable whose type carries the vec value; the call stages the operation inline.
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        "vmeth",
        e.cat(e.s("vec."), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )

    def vt_field(name):
        return acc(e, xx(e), in_(e, "vt"), "vt_m", name)

    def vself(type_field):
        return e.mb.as_(graft(e, in_(e, "self")), e.lower(e.v(type_field)))

    def cell(index):
        return e.mb.field(vself("pi32"), e.n(index))

    def data():
        return e.mb.as_(e.mb.field(vself("ppv"), e.n(0)), e.lower(e.v("pelem")))

    def slice_of(len_expr):
        """The slice of `len_expr` elements at the data pointer (the constructor is a callable type)."""
        return e.call(e.lower(e.v("slice_of")), e.tup(data(), len_expr))

    def method_body(kind):
        if kind == "at":
            return e.call(e.fld(slice_of(cell(LEN_CELL)), "at"), graft(e, a(e, "argument")))
        if kind == "slice":
            return slice_of(cell(LEN_CELL))
        if kind == "push":
            return e.seq(
                e.if_only(
                    e.eq(cell(LEN_CELL), cell(CAP_CELL)),
                    e.call(e.lower(e.v("grow")), e.tup(vself("pv"), e.mb.operator_add(cell(LEN_CELL), e.n(1)))),
                ),
                e.mb.set(e.mb.field(data(), cell(LEN_CELL)), graft(e, a(e, "argument"))),
                e.mb.set(cell(LEN_CELL), e.mb.operator_add(cell(LEN_CELL), e.n(1))),
            )
        if kind == "pop":
            # `some` of the last element (taken off the vec), or `none` of an empty vec. The tag is computed before
            # the payload, so it sees the length before the decrement; a block yields a value only through a return.
            has = e.not_(e.eq(cell(LEN_CELL), e.n(0)))
            last = e.mb.labeled(
                "pop",
                e.seq(
                    e.mb.set(cell(LEN_CELL), e.mb.operator_sub(cell(LEN_CELL), e.n(1))),
                    e.mb.return_to(
                        "pop",
                        e.call(e.fld(slice_of(e.mb.operator_add(cell(LEN_CELL), e.n(1))), "at"), cell(LEN_CELL)),
                    ),
                ),
            )
            return e.call(
                e.lower(e.v("opt_of")),
                e.tup(
                    e.call(e.lower(e.v("i32")), has),
                    e.if_else(has, last, e.mb.as_(e.n(0), e.lower(e.v("elem")))),
                ),
            )
        if kind == "clear":
            return e.mb.set(cell(LEN_CELL), e.n(0))
        raise AssertionError(kind)

    x.append(
        e.impl_interface(
            e.v("vmeth"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    *[
                        e.let(f, vt_field(f))
                        for f in ["elem", "pv", "pi32", "ppv", "pelem", "grow", "slice_of", "opt_of"]
                    ],
                    e.let("i32", e.lower(e.v("i32"))),
                    *[
                        e.if_only(e.eq(in_(e, "kind"), e.s(kind)), e.seq(*call_result(e, staged(method_body(kind)))))
                        for kind in METHODS
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("vec: unknown method "), in_(e, "kind")))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def const_type_arg(e, label, cv, bind):
    """Binds `bind` to the constant type the code-value `cv` holds, else errors out of the const function."""
    return [
        e.let(bind + "_tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "type"))),
        e.if_only(
            or_b(e, is_runtime(e, cv), e.not_(e.fld(e.v(bind + "_tk"), "is_some"))),
            ret_m(e, err_cve(e, loc(e), label + ": " + bind + " must be a constant type")),
        ),
        e.let(bind, bim(e, asp_iface(e, "type"), "type", e.fld(e.v(bind + "_tk"), "value"), cve_value(e, cv))),
    ]


def size_of(e, label, type_expr, bind):
    """Binds `bind` to the byte size of `type_expr` from values.atz's size aspect, else errors out."""
    return [
        e.let(bind + "_sk", lookup(e, xx(e), type_expr, e.lower(e.fld(e.v("values"), "size_i")))),
        e.if_only(
            e.not_(e.fld(e.v(bind + "_sk"), "is_some")),
            ret_m(
                e,
                err_cve(e, loc(e), e.cat(e.s(label + ": type "), ty_desc(e, type_expr), e.s(" has no size aspect"))),
            ),
        ),
        e.let(bind, bim0(e, e.lower(e.fld(e.v("values"), "size_i")), "size", e.fld(e.v(bind + "_sk"), "value"))),
    ]


def module(e, kind):
    tg = _Target(kind)
    x = []
    tg.imports(e, x)
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.v("i32"))))
    x.append(e.let("ppv", e.call(e.fld(e.v("lib"), "ptr"), e.v("pv"))))
    tg.module_lets(e, x)
    for name, params, ret in [("grow_t", ["pv", "i32"], "void"), ("free_t", ["pv"], "void"), ("new_t", [], "pv")]:
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("lib"), "fn"),
                    e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), p("ret", e.v(ret))),
                ),
            )
        )
    _vt(e, x)
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "vec.type: argument has no value"))),
        *const_type_arg(e, "vec.type", e.v("argv"), "elem"),
        *size_of(e, "vec.type", e.v("elem"), "elem_size"),
        e.let("name", e.cat(e.s("vec_"), ident_of(e, ty_desc(e, e.v("elem"))))),
    ]
    tg.host_lets(e, parts)
    _deps(e, tg, parts)
    parts.append(e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))))
    const_fn(e, x, "vec_b", "vec.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("vec_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
