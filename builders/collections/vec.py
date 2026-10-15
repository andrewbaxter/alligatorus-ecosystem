"""vec-wasm.atz / vec-llvm.atz: growable arrays on a heap, one module per target from this builder.

`vec.type(elem)` yields `{type, raw, new}` for a constant element type `elem` (which must have values.atz's `size`
aspect):
- a vec is a pointer to a 16-byte header: data pointer at 0, length (i32) at 8, capacity (i32) at 12;
- `new()` yields an empty vec; `new() as type` makes it an owned value (destructor.atz) whose drop frees the data and
  the header; `raw` is the unowned handle type (what `type` wraps);
- on a vec value: `len`, `cap`, `data` (ptr(elem)) are places; `at(i)` is the element place (bounds-checked through
  slice.atz's `slice_idx`: an index out of range traps); `push(x)`, `clear()` are methods; `pop()` is `some` of the
  last element taken off the vec, or `none` when the vec is empty (option.atz); `slice()` is the slice (slice.atz)
  of the current elements.
The methods and the helpers (`vec_<elem>_at`, `_push`, `_pop`, `_clear`, `_slice`, `_grow`, `_free`, `_new`) are
dependencies (`func_dep`): a module gets each when its code first uses it, once. A method call is a call of its
dependency. Memory comes from wasm-alloc.atz (wasm) or libc (llvm). A byte vec plus the target's string conversion
stands in for a growable string.
"""

from ..memory import destructor
from ..core import values
from ..eco_mb import p
from ..target_mb import (
    a,
    bim0,
    body,
    const_eval_in,
    const_fn,
    const_type_arg,
    cve_has,
    err_cve,
    fn_of,
    graft,
    handle_methods,
    handle_type,
    ident_of,
    in_,
    int_as,
    loc,
    lookup,
    ret_m,
    self_v,
    ty,
    ty_desc,
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
        return int_as(e, n, _up(e, e.fld(e.v("lib"), "u64"), depth))

    def malloc(self, e, n, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "malloc"), depth), self.size(e, n, depth))

    def free(self, e, ptr, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "free"), depth), ptr)

    def elem_ptr(self, e, base, idx, size, ptr_type, i32):
        """The address of element `idx` of the array at `base` (a `ptr(elem)`), as `ptr_type`."""
        if self.kind == WASM:
            return e.mb.as_(e.mb.operator_add(e.mb.as_(base, i32), e.mb.operator_mul(idx, size)), ptr_type)
        return e.mb.operator_add(base, idx)

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


def _data(e, v, dm=BODY_MOD, dh=BODY_HOST):
    """The data pointer of the vec `v`, as `ptr(elem)` (in a dependency body staged `dm` below the module and `dh`
    below its host locals)."""
    return e.mb.as_(_data_cell(e, v, dm), _up(e, e.v("pelem"), dh))


def _dep_fn(e, name, *args, dh=BODY_HOST):
    """A call of the dependency `name` (a host local, a callable type) in a dependency body."""
    return e.call(fn_of(e, _up(e, e.v(name), dh)), args[0] if len(args) == 1 else e.tup(*args))


def _at_body(e, tg, dm, dh):
    """at(v, i) -> ptr(elem): the address of element `i`; slice_idx traps when it is out of range."""
    return e.seq(
        e.ret(
            tg.elem_ptr(
                e,
                _data(e, e.v("v"), dm, dh),
                _dep_fn(e, "slice_idx", e.v("i"), _cell(e, e.v("v"), LEN_CELL, dm), dh=dh),
                _up(e, e.v("elem_size"), dh),
                _up(e, e.v("pelem"), dh),
                _up(e, e.v("i32"), dh),
            )
        )
    )


def _push_body(e, tg):
    """push(v, x): grow when full, store at the length, count it."""
    d = BODY_MOD
    return e.seq(
        e.if_only(
            e.eq(_cell(e, e.v("v"), LEN_CELL, d), _cell(e, e.v("v"), CAP_CELL, d)),
            _dep_fn(e, "grow", e.v("v"), e.mb.operator_add(_cell(e, e.v("v"), LEN_CELL, d), e.n(1))),
        ),
        e.mb.set(e.mb.field(_data(e, e.v("v")), _cell(e, e.v("v"), LEN_CELL, d)), e.v("x")),
        e.mb.set(_cell(e, e.v("v"), LEN_CELL, d), e.mb.operator_add(_cell(e, e.v("v"), LEN_CELL, d), e.n(1))),
    )


def _pop_body(e, tg, dm, dh):
    """pop(v) -> option: `some` of the last element (taken off the vec), or `none` of an empty vec. The tag is
    computed before the payload, so it sees the length before the decrement; a block yields a value only through a
    return."""

    def has_elem():
        return e.not_(e.eq(_cell(e, e.v("v"), LEN_CELL, dm), e.n(0)))

    last = e.mb.labeled(
        "pop",
        e.seq(
            e.mb.set(_cell(e, e.v("v"), LEN_CELL, dm), e.mb.operator_sub(_cell(e, e.v("v"), LEN_CELL, dm), e.n(1))),
            e.mb.return_to("pop", e.mb.field(_data(e, e.v("v"), dm, dh), _cell(e, e.v("v"), LEN_CELL, dm))),
        ),
    )
    return e.seq(
        e.ret(
            _dep_fn(
                e,
                "opt_of_t",
                e.mb.as_(has_elem(), _up(e, e.v("i32"), dh)),
                e.if_else(has_elem(), last, e.mb.as_(e.n(0), _up(e, e.v("elem"), dh))),
                dh=dh,
            )
        )
    )


def _clear_body(e, tg):
    return e.seq(e.mb.set(_cell(e, e.v("v"), LEN_CELL, BODY_MOD), e.n(0)))


def _slice_body(e, tg, dm, dh):
    """slice(v) -> slice: the (data, len) tuple as the slice type."""
    return e.seq(
        e.ret(e.mb.as_(e.tup(_data(e, e.v("v"), dm, dh), _cell(e, e.v("v"), LEN_CELL, dm)), _up(e, e.v("slice_t"), dh)))
    )


# The dependencies defined in the const function's host body: (host local, name suffix, function type host local,
# parameter names, body maker).
HOST_DEPS = [
    ("grow", "grow", "grow_t", ("v", "min_cap"), _grow_body),
    ("free_vec", "free", "free_t", ("v",), _free_body),
    ("new", "new", "new_t", (), _new_body),
    ("m_push", "push", "push_t", ("v", "x"), _push_body),
    ("m_clear", "clear", "free_t", ("v",), _clear_body),
]
# The dependencies defined in the setup (staged in the caller's context), whose bodies or types need the slice and
# option types of the elements (constants only there): (setup local, suffix, parameter names, body maker, type maker).
SETUP_DEPS = [
    ("m_at", "at", ("v", "i"), _at_body, lambda e, fn_t: fn_t([e.v("pv"), e.v("i32")], e.v("pelem"))),
    ("m_pop", "pop", ("v",), _pop_body, lambda e, fn_t: fn_t([e.v("pv")], e.v("opt_t"))),
    ("m_slice", "slice", ("v",), _slice_body, lambda e, fn_t: fn_t([e.v("pv")], e.v("slice_t"))),
]
HOST_FN_TYPES = ["push_t"]
# What the vec type carries: the element and pointer types, the slice and option types of its elements, and its
# method dependencies.
FIELDS = ["elem", "pv", "pi32", "ppv", "pelem", "slice_t", "opt_t", "m_at", "m_push", "m_pop", "m_clear", "m_slice"]


def _func_dep(e, lib_dep, name, params, ty_, body_):
    return e.call(
        lib_dep,
        e.rec(
            p("name", name),
            p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
            p("ty", ty_),
            p("body", e.stage(body_)),
        ),
    )


def _deps(e, tg, out):
    """In the const function's host body: the dependencies for `elem` (constants from here on)."""
    for fn, suffix, fn_t, params, fbody in HOST_DEPS:
        ty_ = e.v(fn_t) if fn_t in HOST_FN_TYPES else e.lower(e.v(fn_t))
        out.append(
            e.let(
                fn,
                _func_dep(
                    e,
                    e.lower(e.fld(e.v("lib"), "func_dep")),
                    e.cat(e.v("name"), e.s("_" + suffix)),
                    params,
                    ty_,
                    fbody(e, tg),
                ),
            )
        )


def _host_types(e, out):
    """In the const function's host body: the element-dependent types and function types."""
    out.append(e.let("i32", e.lower(e.v("i32"))))
    out.append(e.let("pelem", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("elem"))))
    out.append(
        e.let(
            "push_t",
            e.call(
                e.lower(e.fld(e.v("lib"), "fn")),
                e.rec(
                    p("params", e.list_new(e.mb.eval_type(), e.lower(e.v("pv")), e.v("elem"))),
                    p("ret", e.lower(e.v("void"))),
                ),
            ),
        )
    )


def _setup(e, tg):
    """Staged in the caller's context: the slice and option types of the elements (from their factories), the
    dependencies that need them, and the vec types over all of it (constants here)."""
    out = []
    for name in ["elem", "pelem", "elem_size", "name", "free_vec", "new", "m_push", "m_clear"]:
        out.append(e.let(name, e.lower(e.v(name))))
    for name in ["pv", "pi32", "ppv", "i32"]:
        out.append(e.let(name, _up(e, e.v(name), SETUP_MOD)))
    out.append(e.let("sl", e.call(_up(e, e.fld(e.v("slice"), "type"), SETUP_MOD), e.v("elem"))))
    out.append(e.let("slice_t", e.fld(e.v("sl"), "type")))
    out.append(e.let("slice_idx", e.fld(e.v("sl"), "idx")))
    out.append(e.let("opt", e.call(_up(e, e.fld(e.v("option"), "type"), SETUP_MOD), e.v("elem"))))
    out.append(e.let("opt_t", e.fld(e.v("opt"), "type")))
    out.append(e.let("opt_of_t", e.fld(e.v("opt"), "of_t")))

    def fn_t(params, ret):
        return e.call(
            _up(e, e.fld(e.v("lib"), "fn"), SETUP_MOD),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *params)), p("ret", ret)),
        )

    for fn, suffix, params, fbody, make_t in SETUP_DEPS:
        out.append(
            e.let(
                fn,
                _func_dep(
                    e,
                    _up(e, e.fld(e.v("lib"), "func_dep"), SETUP_MOD),
                    e.cat(e.v("name"), e.s("_" + suffix)),
                    params,
                    make_t(e, fn_t),
                    fbody(e, tg, SETUP_MOD + 1, 1),
                ),
            )
        )
    out.append(
        e.let(
            "raw",
            e.mb.as_(
                e.call(_up(e, e.fld(e.v("vt"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in FIELDS])),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(
        e.let(
            "owned",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", fn_of(e, e.v("free_vec")))),
            ),
        )
    )
    out.append(e.ret(e.rec(p("type", e.v("owned")), p("raw", e.v("raw")), p("new", fn_of(e, e.v("new"))))))
    return e.mb.seq(out)


def _vt(e, x):
    """The unowned vec handle type: a pointer carrying the element type, the vec's places and its method
    dependencies."""
    fields = [p(f, ty(e)) for f in FIELDS]
    places = {
        "len": lambda self_as: e.mb.field(self_as("pi32"), e.n(LEN_CELL)),
        "cap": lambda self_as: e.mb.field(self_as("pi32"), e.n(CAP_CELL)),
        "data": lambda self_as: e.mb.as_(e.mb.field(self_as("ppv"), e.n(0)), e.lower(in_(e, "pelem"))),
    }
    meth = handle_type(
        e,
        x,
        "vt",
        "vt_m",
        "vec",
        fields,
        places,
        METHODS,
        under="pv",
        desc_expr=e.cat(e.s("vec("), ty_desc(e, in_(e, "elem")), e.s(")")),
        identity="elem",
    )

    def dep(kind):
        return fn_of(e, e.lower(e.v("m_" + kind)))

    def method_body(kind):
        if kind == "at":
            return e.mb.field(e.call(dep(kind), e.tup(self_v(e), graft(e, a(e, "argument")))), e.n(0))
        if kind == "push":
            return e.call(dep(kind), e.tup(self_v(e), graft(e, a(e, "argument"))))
        return e.call(dep(kind), self_v(e))

    handle_methods(e, x, meth, "vt_m", fields, METHODS, method_body)


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
    _host_types(e, parts)
    _deps(e, tg, parts)
    parts.append(
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e, tg))))))
    )
    const_fn(e, x, "vec_b", "vec.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("vec_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
