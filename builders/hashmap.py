"""map-wasm.atz / map-llvm.atz / set-wasm.atz / set-llvm.atz: open-addressing hash tables, from one builder.

`map.type((key, value))` and `set.type(key)` yield `{type, raw, new}` for constant key (and value) types. The key type
must have values.atz's `size`, `hash` and `eq` aspects; the value type its `size`.

A table is a pointer to a header: keys pointer, values pointer (maps), states pointer (one byte per slot: 0 empty,
1 full, 2 removed), then `len`, `cap` and `tombs` as i32, then a scratch key slot. Capacity is a power of two;
probing is linear; the table rehashes to twice its capacity when full plus removed slots reach three quarters.

On a table value: `len` and `cap` are places; `has(k)` → i32, `remove(k)` → i32 (1 when it was present), `clear()`;
maps also have `get(k)` → ptr(value) (null when absent) and `put(k, v)`; sets have `add(k)`. The inline part of a
method stores the key in the header's scratch slot and calls the `<name>_find`, `_insert`, `_remove`, `_clear`,
`_rehash`, `_free`, `_new` and `_null` functions, which are dependencies (`func_dep`): a module gets them when its
code first uses them. Memory comes from wasm-alloc.atz (wasm) or libc (llvm).
"""

from . import destructor, values
from .eco_mb import p
from .target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    body,
    bool_t,
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
    int_t,
    is_equal,
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
    to_str,
    ty,
    ty_desc,
    type_aspect,
    unwrap_cve_m,
    xx,
)
from .vec import const_type_arg, size_of

WASM = "wasm"
LLVM = "llvm"

FILES = {
    (WASM, True): "map-wasm.atz",
    (LLVM, True): "map-llvm.atz",
    (WASM, False): "set-wasm.atz",
    (LLVM, False): "set-llvm.atz",
}

HEADER = 40
SCRATCH = HEADER
MIN_CAP = 8
EMPTY = 0
FULL = 1
REMOVED = 2

PLACES = ["len", "cap"]
DEPS = ["find", "insert", "remove", "clear", "null_fn"]

# Stage depths, as in vec.py: dependency bodies are staged in the const function's host body (host locals one
# lower up, module-level values two up); inline method bodies are staged in a method's host body (same depths).
BODY_MOD = 2
BODY_HOST = 1
SETUP_MOD = 2


def _methods(with_values):
    return (["get", "put"] if with_values else ["add"]) + ["has", "remove", "clear"]


def _up(e, expr, depth):
    for _ in range(depth):
        expr = e.lower(expr)
    return expr


class _Target:
    def __init__(self, kind):
        self.kind = kind
        # i32 cells per pointer cell: the header's pointer cells precede its i32 cells.
        self.ptr_cells = 1 if kind == WASM else 2

    def imports(self, e, out):
        if self.kind == WASM:
            out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
            out.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
        else:
            out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))
            out.append(e.let("heap", e.import_local("libc", "libc-2.42.atz")))

    def null(self, e, depth):
        """The null pointer, in a dependency body."""
        if self.kind == WASM:
            return e.mb.as_(e.n(0), _up(e, e.v("pv"), depth))
        return e.call(
            _up(e, e.fld(e.v("lib"), "ref_fn"), depth),
            e.rec(p("ref", e.s("null")), p("ty", _up(e, e.v("pv_gt"), depth))),
        )

    def module_lets(self, e, out):
        if self.kind == LLVM:
            out.append(
                e.let(
                    "pv_gt",
                    e.call(e.fld(e.v("lib"), "global_t"), e.rec(p("ty", e.v("pv")), p("mem", e.b(False)))),
                )
            )

    def size(self, e, n, depth):
        if self.kind == WASM:
            return n
        return e.call(_up(e, e.fld(e.v("lib"), "u64"), depth), n)

    def malloc(self, e, n, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "malloc"), depth), self.size(e, n, depth))

    def free(self, e, ptr, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "free"), depth), ptr)

    def zero_fill(self, e, dst, n, depth):
        """Zeroes `n` bytes at `dst`; a statement (the wasm intrinsic is instantiated in the body)."""
        if self.kind == WASM:
            return e.call(e.call(_up(e, e.fld(e.v("lib"), "memory_fill_fn"), depth), e.rec()), e.tup(dst, e.n(0), n))
        return e.call(_up(e, e.fld(e.v("heap"), "memset"), depth), e.tup(dst, e.n(0), self.size(e, n, depth)))

    def byte_ptr(self, e, base, offset, ptr_type):
        """`base` plus `offset` bytes, as `ptr_type` (the int and byte-pointer types are host locals)."""
        if self.kind == WASM:
            return e.mb.as_(e.mb.operator_add(e.mb.as_(base, e.lower(e.v("i32"))), e.n(offset)), ptr_type)
        return e.mb.as_(e.mb.operator_add(e.mb.as_(base, e.lower(e.v("pu8"))), e.n(offset)), ptr_type)

    def elem_ptr(self, e, base, idx, size_expr, ptr_type):
        """The address of element `idx` of the array at `base` (as `ptr_type`); `size_expr` is the element size."""
        if self.kind == WASM:
            addr = e.mb.operator_add(e.mb.as_(base, e.lower(e.v("i32"))), e.mb.operator_mul(idx, size_expr))
            return e.mb.as_(addr, ptr_type)
        return e.mb.operator_add(e.mb.as_(base, ptr_type), idx)

    def loop(self, e, depth):
        """An infinite loop value, made in the body from the lowered intrinsic type."""
        if self.kind == WASM:
            return e.call(_up(e, e.fld(e.v("lib"), "loop_fn"), depth), e.rec())
        return e.call(
            _up(e, e.fld(e.v("lib"), "ref_fn"), depth),
            e.rec(p("ref", e.s("loop")), p("ty", _up(e, e.fld(e.v("lib"), "loop"), depth))),
        )


class _Layout:
    """Header cell indices for a target."""

    def __init__(self, tg):
        pc = tg.ptr_cells
        self.keys = 0
        self.vals = 1
        self.states = 2
        self.len = 3 * pc
        self.cap = 3 * pc + 1
        self.tombs = 3 * pc + 2


# Types are always bound one stage above a body: as host locals of the const function for the dependency bodies,
# and as host locals of the method for the inline methods.


def _ptr_cell(e, h, index):
    return e.mb.field(e.mb.as_(h, e.lower(e.v("ppv"))), e.n(index))


def _i32_cell(e, h, index):
    return e.mb.field(e.mb.as_(h, e.lower(e.v("pi32"))), e.n(index))


def _typed(e, ptr_expr, type_name):
    return e.mb.as_(ptr_expr, e.lower(e.v(type_name)))


def _i32(e, n):
    return e.mb.as_(e.n(n), e.lower(e.v("i32")))


def _scratch(e, tg, h):
    """The header's scratch key slot (a place)."""
    return e.mb.field(tg.byte_ptr(e, h, SCRATCH, e.lower(e.v("pkey"))), e.n(0))


def _hash(e, key, depth):
    """The key's 32-bit hash through values.atz (the key type's hash aspect)."""
    return e.call(_up(e, e.fld(e.v("values"), "hash"), depth), key)


def _eq(e, k1, k2, depth):
    """Whether two keys are equal (the target's native comparison), through values.atz."""
    return e.call(_up(e, e.fld(e.v("values"), "eq"), depth), e.tup(k1, k2))


def _probe(e, tg, lay, h, key, depth, on_found, on_empty, label=None):
    """Linear probing from the key's hash. `on_found(idx)` and `on_empty(idx)` are the bodies run (inside the loop,
    so they must leave it with a return) when a full slot with an equal key, or an empty slot, is reached. With
    `label`, the loop sits in a block of that name."""
    loop = e.foreach(
        tg.loop(e, depth),
        "_",
        e.seq(
            e.let("st", e.mb.field(e.v("states"), e.v("idx"))),
            e.if_only(e.eq(e.v("st"), e.n(EMPTY)), on_empty(e.v("idx"))),
            e.if_only(
                e.eq(e.v("st"), e.n(FULL)),
                e.if_only(_eq(e, e.mb.field(e.v("keys"), e.v("idx")), key, depth), on_found(e.v("idx"))),
            ),
            e.mb.set(e.v("idx"), e.mb.operator_and(e.mb.operator_add(e.v("idx"), e.n(1)), e.v("mask"))),
        ),
    )
    return e.seq(
        e.let("mask", e.mb.operator_sub(_i32_cell(e, h, lay.cap), e.n(1))),
        e.let("idx", e.mb.operator_and(_hash(e, key, depth), e.v("mask"))),
        e.let("keys", _typed(e, _ptr_cell(e, h, lay.keys), "pkey")),
        e.let("states", _typed(e, _ptr_cell(e, h, lay.states), "pu8")),
        e.mb.labeled(label, loop) if label else loop,
    )


def _insert_body(e, tg, lay, h, key, depth):
    """Inserts `key` (fresh in the table) at the first empty or removed slot; yields its index."""
    return e.mb.labeled(
        "ins",
        e.seq(
            e.let("mask", e.mb.operator_sub(_i32_cell(e, h, lay.cap), e.n(1))),
            e.let("idx", e.mb.operator_and(_hash(e, key, depth), e.v("mask"))),
            e.let("keys", _typed(e, _ptr_cell(e, h, lay.keys), "pkey")),
            e.let("states", _typed(e, _ptr_cell(e, h, lay.states), "pu8")),
            e.foreach(
                tg.loop(e, depth),
                "_",
                e.seq(
                    e.let("st", e.mb.field(e.v("states"), e.v("idx"))),
                    e.if_only(
                        e.not_(e.eq(e.v("st"), e.n(FULL))),
                        e.seq(
                            e.if_only(
                                e.eq(e.v("st"), e.n(REMOVED)),
                                e.mb.set(
                                    _i32_cell(e, h, lay.tombs), e.mb.operator_sub(_i32_cell(e, h, lay.tombs), e.n(1))
                                ),
                            ),
                            e.mb.set(e.mb.field(e.v("states"), e.v("idx")), e.n(FULL)),
                            e.mb.set(e.mb.field(e.v("keys"), e.v("idx")), key),
                            e.mb.set(_i32_cell(e, h, lay.len), e.mb.operator_add(_i32_cell(e, h, lay.len), e.n(1))),
                            e.mb.return_to("ins", e.v("idx")),
                        ),
                    ),
                    e.mb.set(e.v("idx"), e.mb.operator_and(e.mb.operator_add(e.v("idx"), e.n(1)), e.v("mask"))),
                ),
            ),
            e.mb.return_to("ins", _i32(e, 0)),
        ),
    )


def _alloc_arrays(e, tg, lay, with_values, h, cap):
    """Allocates zeroed arrays for `cap` slots into the header `h` and sets cap, len and tombs."""
    d = BODY_MOD
    out = [
        e.mb.set(
            _ptr_cell(e, h, lay.keys),
            tg.malloc(e, e.mb.operator_mul(cap, _up(e, e.v("key_size"), BODY_HOST)), d),
        ),
        e.mb.set(_ptr_cell(e, h, lay.states), tg.malloc(e, cap, d)),
        tg.zero_fill(e, _ptr_cell(e, h, lay.states), cap, d),
        e.mb.set(_i32_cell(e, h, lay.cap), cap),
        e.mb.set(_i32_cell(e, h, lay.len), e.n(0)),
        e.mb.set(_i32_cell(e, h, lay.tombs), e.n(0)),
    ]
    if with_values:
        out.insert(
            1,
            e.mb.set(
                _ptr_cell(e, h, lay.vals),
                tg.malloc(e, e.mb.operator_mul(cap, _up(e, e.v("value_size"), BODY_HOST)), d),
            ),
        )
    return e.seq(*out)


def _free_arrays(e, tg, lay, with_values, h):
    d = BODY_MOD
    out = [tg.free(e, _ptr_cell(e, h, lay.keys), d), tg.free(e, _ptr_cell(e, h, lay.states), d)]
    if with_values:
        out.append(tg.free(e, _ptr_cell(e, h, lay.vals), d))
    return e.seq(*out)


def _rehash_body(e, tg, lay, with_values):
    """rehash(t): moves every full slot into arrays of twice the capacity."""
    d = BODY_MOD
    h = e.v("t")
    copy_value = []
    if with_values:
        copy_value = [
            e.mb.set(
                e.mb.field(_typed(e, _ptr_cell(e, h, lay.vals), "pvalue"), e.v("ni")),
                e.mb.field(e.v("ovals"), e.v("i")),
            )
        ]
    return e.seq(
        e.let("ocap", _i32_cell(e, h, lay.cap)),
        e.let("okeys", _typed(e, _ptr_cell(e, h, lay.keys), "pkey")),
        e.let("ostates", _typed(e, _ptr_cell(e, h, lay.states), "pu8")),
        *([e.let("ovals", _typed(e, _ptr_cell(e, h, lay.vals), "pvalue"))] if with_values else []),
        e.let(
            "ncap",
            e.if_else(e.eq(e.v("ocap"), e.n(0)), _i32(e, MIN_CAP), e.mb.operator_mul(e.v("ocap"), e.n(2))),
        ),
        _alloc_arrays(e, tg, lay, with_values, h, e.v("ncap")),
        e.let("i", _i32(e, 0)),
        e.mb.labeled(
            "move",
            e.foreach(
                tg.loop(e, d),
                "_",
                e.seq(
                    e.if_only(e.eq(e.v("i"), e.v("ocap")), e.mb.return_label("move")),
                    e.if_only(
                        e.eq(e.mb.field(e.v("ostates"), e.v("i")), e.n(FULL)),
                        e.seq(
                            e.let("ni", _insert_body(e, tg, lay, h, e.mb.field(e.v("okeys"), e.v("i")), d)),
                            *copy_value,
                        ),
                    ),
                    e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.n(1))),
                ),
            ),
        ),
        e.if_only(
            e.not_(e.eq(e.v("ocap"), e.n(0))),
            e.seq(
                tg.free(e, e.v("okeys"), d),
                tg.free(e, e.v("ostates"), d),
                *([tg.free(e, e.v("ovals"), d)] if with_values else []),
            ),
        ),
    )


def _find_body(e, tg, lay):
    """find(t): the index of the scratch key, or -1."""
    h = e.v("t")
    return e.mb.labeled(
        "f",
        e.seq(
            e.if_only(e.eq(_i32_cell(e, h, lay.cap), e.n(0)), e.mb.return_to("f", _i32(e, -1))),
            e.let("k", _scratch(e, tg, h)),
            _probe(
                e,
                tg,
                lay,
                h,
                e.v("k"),
                BODY_MOD,
                lambda idx: e.mb.return_to("f", idx),
                lambda idx: e.mb.return_to("f", _i32(e, -1)),
            ),
            e.mb.return_to("f", _i32(e, -1)),
        ),
    )


def _insert_fn_body(e, tg, lay):
    """insert(t): inserts the scratch key (known absent), growing first when needed; yields its index."""
    h = e.v("t")

    def rehash():
        return e.call(_up(e, e.v("rehash"), BODY_HOST), h)

    return e.mb.labeled(
        "i",
        e.seq(
            e.if_only(e.eq(_i32_cell(e, h, lay.cap), e.n(0)), rehash()),
            e.if_only(
                e.mb.operator_gt(
                    e.mb.operator_mul(
                        e.mb.operator_add(
                            e.mb.operator_add(_i32_cell(e, h, lay.len), _i32_cell(e, h, lay.tombs)), e.n(1)
                        ),
                        e.n(4),
                    ),
                    e.mb.operator_mul(_i32_cell(e, h, lay.cap), e.n(3)),
                ),
                rehash(),
            ),
            e.mb.return_to("i", _insert_body(e, tg, lay, h, _scratch(e, tg, h), BODY_MOD)),
        ),
    )


def _remove_body(e, tg, lay):
    """remove(t): removes the scratch key; yields 1 when it was present."""
    h = e.v("t")
    return e.mb.labeled(
        "r",
        e.seq(
            e.if_only(e.eq(_i32_cell(e, h, lay.cap), e.n(0)), e.mb.return_to("r", _i32(e, 0))),
            e.let("k", _scratch(e, tg, h)),
            _probe(
                e,
                tg,
                lay,
                h,
                e.v("k"),
                BODY_MOD,
                lambda idx: e.seq(
                    e.mb.set(e.mb.field(_typed(e, _ptr_cell(e, h, lay.states), "pu8"), idx), e.n(REMOVED)),
                    e.mb.set(_i32_cell(e, h, lay.len), e.mb.operator_sub(_i32_cell(e, h, lay.len), e.n(1))),
                    e.mb.set(_i32_cell(e, h, lay.tombs), e.mb.operator_add(_i32_cell(e, h, lay.tombs), e.n(1))),
                    e.mb.return_to("r", _i32(e, 1)),
                ),
                lambda idx: e.mb.return_to("r", _i32(e, 0)),
            ),
            e.mb.return_to("r", _i32(e, 0)),
        ),
    )


def _clear_body(e, tg, lay):
    h = e.v("t")
    return e.if_only(
        e.not_(e.eq(_i32_cell(e, h, lay.cap), e.n(0))),
        e.seq(
            tg.zero_fill(e, _ptr_cell(e, h, lay.states), _i32_cell(e, h, lay.cap), BODY_MOD),
            e.mb.set(_i32_cell(e, h, lay.len), e.n(0)),
            e.mb.set(_i32_cell(e, h, lay.tombs), e.n(0)),
        ),
    )


def _free_body(e, tg, lay, with_values):
    h = e.v("t")
    return e.seq(
        e.if_only(e.not_(e.eq(_i32_cell(e, h, lay.cap), e.n(0))), _free_arrays(e, tg, lay, with_values, h)),
        tg.free(e, h, BODY_MOD),
    )


def _new_body(e, tg, lay):
    return e.seq(
        e.let(
            "h",
            tg.malloc(e, e.mb.operator_add(e.n(HEADER), _up(e, e.v("key_size"), BODY_HOST)), BODY_MOD),
        ),
        e.mb.set(_i32_cell(e, e.v("h"), lay.len), e.n(0)),
        e.mb.set(_i32_cell(e, e.v("h"), lay.cap), e.n(0)),
        e.mb.set(_i32_cell(e, e.v("h"), lay.tombs), e.n(0)),
        e.ret(e.v("h")),
    )


def _deps(e, tg, lay, with_values, out):
    """In the const function's host body: the table's dependencies (constants from here on)."""
    for fn, suffix, fn_t, params, fbody in [
        ("rehash", "rehash", "rehash_t", ("t",), _rehash_body(e, tg, lay, with_values)),
        ("find", "find", "idx_t", ("t",), _find_body(e, tg, lay)),
        ("insert", "insert", "idx_t", ("t",), _insert_fn_body(e, tg, lay)),
        ("remove", "remove", "idx_t", ("t",), _remove_body(e, tg, lay)),
        ("clear", "clear", "rehash_t", ("t",), _clear_body(e, tg, lay)),
        ("free_table", "free", "free_t", ("t",), _free_body(e, tg, lay, with_values)),
        ("new", "new", "new_t", (), _new_body(e, tg, lay)),
        # The null pointer as a function: the inline methods have no target context of their own to make one in.
        ("null_fn", "null", "new_t", (), e.mb.labeled("fn", e.seq(e.mb.return_to("fn", tg.null(e, BODY_MOD))))),
    ]:
        out.append(
            e.let(
                fn,
                e.call(
                    e.lower(e.fld(e.v("lib"), "func_dep")),
                    e.rec(
                        p("name", e.cat(e.v("name"), e.s("_" + suffix))),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.lower(e.v(fn_t))),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )


def _setup(e):
    """Staged in the caller's context: the table types over the lowered dependencies."""
    out = []
    for name in ["key", "pkey", "pvalue", "value_size", "free_table", "new"] + DEPS:
        out.append(e.let(name, e.lower(e.v(name))))
    for tname in ["pv", "pi32", "ppv", "pu8"]:
        out.append(e.let(tname, _up(e, e.v(tname), SETUP_MOD)))
    fields = [p(k, e.v(k)) for k in ["key", "pv", "pi32", "ppv", "pu8", "pkey", "pvalue", "value_size"] + DEPS]
    out.append(
        e.let("raw", e.mb.as_(e.call(_up(e, e.fld(e.v("ht"), "new"), SETUP_MOD), e.rec(*fields)), e.mb.eval_type()))
    )
    out.append(
        e.let(
            "owned",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", e.v("free_table"))),
            ),
        )
    )
    out.append(e.ret(e.rec(p("type", e.v("owned")), p("raw", e.v("raw")), p("new", e.v("new")))))
    return e.mb.seq(out)


def _ht(e, x, tg, lay, with_values):
    """The unowned table handle type and its inline methods."""
    fields = [p(k, ty(e)) for k in ["key", "pv", "pi32", "ppv", "pu8", "pkey", "pvalue"] + DEPS]
    fields.append(p("value_size", int_t(e)))
    methods = _methods(with_values)
    def_iface(e, x, "ht_m", *fields)
    def_obj(e, x, "ht", "table type", e.rec(*fields))
    def_obj(e, x, "hmeth", "table method", e.rec(p("kind", str_(e)), p("ht", ty(e)), p("self", e.mb.types_cve())))
    x.append(e.impl_interface(e.v("ht"), t(e, "ht_m"), *[p(k, in_(e, k)) for k, _ in fields]))
    label = "map(" if with_values else "set("
    self_type(
        e,
        x,
        "ht",
        e.cat(e.s(label), ty_desc(e, in_(e, "key")), e.s(")")),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "ht_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
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
                p("errs", ret_m(e, err_cve(e, loc(e), "table: only runtime pointers can become tables"))),
            ),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "ht_m"),
                    is_equal(e, xx(e), in_(e, "key"), acc(e, xx(e), a(e, "other"), "ht_m", "key")),
                )
            ),
        ),
    )

    def staged(expr):
        return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(expr)))

    def self_as(type_field):
        return e.mb.as_(graft(e, a(e, "self")), e.lower(in_(e, type_field)))

    def method_value(m):
        return ok_cve(
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
                                "hmeth",
                                p("kind", e.s(m)),
                                p("ht", outer(e)),
                                p(
                                    "self",
                                    cv_of(e, e.call(e.eval_builtin("code_none"), loc(e)), cve_value(e, a(e, "self"))),
                                ),
                            ),
                        ),
                        p("data", e.tup()),
                    ),
                ),
            ),
        )

    x.append(
        e.impl_interface(
            e.v("ht"),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), "table: field must be a constant string")),
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
                        ret_m(e, ok_cve(e, staged(e.mb.field(self_as("pi32"), e.n(lay.len))))),
                    ),
                    e.if_only(
                        e.eq(e.v("key"), e.s("cap")),
                        ret_m(e, ok_cve(e, staged(e.mb.field(self_as("pi32"), e.n(lay.cap))))),
                    ),
                    *[e.if_only(e.eq(e.v("key"), e.s(m)), ret_m(e, method_value(m))) for m in methods],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("table has no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.list_new(e.mb.types_constkey(), *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in PLACES + methods]),
            ),
        )
    )
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        "hmeth",
        e.cat(e.s(label[:-1] + "."), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )

    def ht_field(name):
        return acc(e, xx(e), in_(e, "ht"), "ht_m", name)

    def vself():
        return e.mb.as_(graft(e, in_(e, "self")), e.lower(e.v("pv")))

    def call_dep(name, *args):
        return e.call(e.lower(e.v(name)), args[0] if len(args) == 1 else e.tup(*args))

    def put_scratch(key):
        return e.mb.set(e.mb.field(tg.byte_ptr(e, vself(), SCRATCH, e.lower(e.v("pkey"))), e.n(0)), key)

    def arg(i):
        """The method argument: the whole argument, or element `i` of its tuple (taken in the host body)."""
        if i is None:
            return graft(e, a(e, "argument"))
        return graft(e, e.call_m(e.v("args"), "get", e.s(str(i))))

    def value_place(idx):
        return e.mb.field(_typed(e, _ptr_cell(e, vself(), lay.vals), "pvalue"), idx)

    def method_body(kind):
        if kind == "has":
            return e.mb.labeled(
                "m",
                e.seq(
                    put_scratch(arg(None)),
                    e.mb.return_to("m", e.call(e.lower(e.v("i32")), e.not_(e.eq(call_dep("find", vself()), e.n(-1))))),
                ),
            )
        if kind == "get":
            return e.mb.labeled(
                "m",
                e.seq(
                    put_scratch(arg(None)),
                    e.let("idx", call_dep("find", vself())),
                    e.if_only(
                        e.eq(e.v("idx"), e.n(-1)),
                        e.mb.return_to("m", e.mb.as_(call_dep("null_fn", e.tup()), e.lower(e.v("pvalue")))),
                    ),
                    e.mb.return_to(
                        "m",
                        tg.elem_ptr(
                            e,
                            _ptr_cell(e, vself(), lay.vals),
                            e.v("idx"),
                            e.lower(e.v("value_size")),
                            e.lower(e.v("pvalue")),
                        ),
                    ),
                ),
            )
        if kind == "put":
            return e.seq(
                put_scratch(arg(0)),
                e.let("idx", call_dep("find", vself())),
                e.if_only(e.eq(e.v("idx"), e.n(-1)), e.mb.set(e.v("idx"), call_dep("insert", vself()))),
                e.mb.set(value_place(e.v("idx")), arg(1)),
            )
        if kind == "add":
            return e.seq(
                put_scratch(arg(None)),
                e.if_only(e.eq(call_dep("find", vself()), e.n(-1)), e.seq(e.let("__i", call_dep("insert", vself())))),
            )
        if kind == "remove":
            return e.mb.labeled("m", e.seq(put_scratch(arg(None)), e.mb.return_to("m", call_dep("remove", vself()))))
        if kind == "clear":
            return call_dep("clear", vself())
        raise AssertionError(kind)

    x.append(
        e.impl_interface(
            e.v("hmeth"),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    *[
                        e.let(f, ht_field(f))
                        for f in ["pv", "pi32", "ppv", "pu8", "pkey", "pvalue", "value_size"] + DEPS
                    ],
                    e.let("i32", e.lower(e.v("i32"))),
                    # A tuple argument (put) is split with the tuple aspect: tuples are host values.
                    e.let("args", e.map_new(str_(e), e.mb.types_cve())),
                    e.let("argn", e.rec(p("i", e.int_of(0)))),
                    e.if_only(
                        e.eq(in_(e, "kind"), e.s("put")),
                        e.seq(
                            e.let("tk", lookup(e, xx(e), cve_type(e, a(e, "argument")), asp_iface(e, "tuple"))),
                            e.if_only(
                                e.not_(e.fld(e.v("tk"), "is_some")),
                                ret_m(e, err_cve(e, loc(e), "map.put takes (key, value)")),
                            ),
                            e.foreach(
                                bim(
                                    e,
                                    asp_iface(e, "tuple"),
                                    "take_elements",
                                    e.fld(e.v("tk"), "value"),
                                    e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, a(e, "argument")))),
                                ),
                                "er",
                                e.seq(
                                    e.call_m(
                                        e.v("args"),
                                        "put",
                                        e.tup(to_str(e, e.fld(e.v("argn"), "i")), unwrap_cve_m(e, e.v("er"))),
                                    ),
                                    e.incr(e.fld(e.v("argn"), "i")),
                                ),
                            ),
                        ),
                    ),
                    *[
                        e.if_only(e.eq(in_(e, "kind"), e.s(kind)), ret_m(e, ok_cve(e, staged(method_body(kind)))))
                        for kind in methods
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("table: unknown method "), in_(e, "kind")))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def _tuple_arg(e, label, cv, count):
    """Splits the tuple code-value `cv` into `parts` ("0", "1", ...), requiring exactly `count` elements."""
    msg = label + ": argument must be a tuple of " + str(count) + " types"
    return [
        e.let("tk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "tuple"))),
        e.if_only(e.not_(e.fld(e.v("tk"), "is_some")), ret_m(e, err_cve(e, loc(e), msg))),
        e.let("parts", e.map_new(str_(e), e.mb.types_cve())),
        e.let("pn", e.rec(p("i", e.int_of(0)))),
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
                e.call_m(e.v("parts"), "put", e.tup(to_str(e, e.fld(e.v("pn"), "i")), unwrap_cve_m(e, e.v("er")))),
                e.incr(e.fld(e.v("pn"), "i")),
            ),
        ),
        e.if_only(e.not_(e.eq(e.fld(e.v("pn"), "i"), e.int_of(count))), ret_m(e, err_cve(e, loc(e), msg))),
    ]


def module(e, kind, with_values):
    tg = _Target(kind)
    lay = _Layout(tg)
    label = "map" if with_values else "set"
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
    x.append(e.let("pu8", e.call(e.fld(e.v("lib"), "ptr"), e.fld(e.v("lib"), "u8"))))
    tg.module_lets(e, x)
    for name, params, ret in [
        ("rehash_t", ["pv"], "void"),
        ("idx_t", ["pv"], "i32"),
        ("free_t", ["pv"], "void"),
        ("new_t", [], "pv"),
    ]:
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("lib"), "fn"),
                    e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(pn) for pn in params])), p("ret", e.v(ret))),
                ),
            )
        )
    _ht(e, x, tg, lay, with_values)
    full = label + ".type"
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), full + ": argument has no value"))),
    ]
    if with_values:
        parts.extend(_tuple_arg(e, full, e.v("argv"), 2))
        parts.extend(const_type_arg(e, full, e.call_m(e.v("parts"), "get", e.s("0")), "key"))
        parts.extend(const_type_arg(e, full, e.call_m(e.v("parts"), "get", e.s("1")), "value"))
        parts.extend(size_of(e, full, e.v("value"), "value_size"))
    else:
        parts.extend(const_type_arg(e, full, e.v("argv"), "key"))
        parts.append(e.let("value_size", e.int_of(0)))
    parts.extend(size_of(e, full, e.v("key"), "key_size"))
    for iface, what in [("hash_i", "hash"), ("eq_i", "eq")]:
        parts.append(
            e.if_only(
                e.not_(has_b(e, xx(e), e.v("key"), e.lower(e.fld(e.v("values"), iface)))),
                ret_m(
                    e,
                    err_cve(
                        e,
                        loc(e),
                        e.cat(e.s(full + ": key type "), ty_desc(e, e.v("key")), e.s(" has no " + what + " aspect")),
                    ),
                ),
            )
        )
    name_parts = [e.s(label + "_"), ident_of(e, ty_desc(e, e.v("key")))]
    if with_values:
        name_parts += [e.s("_"), ident_of(e, ty_desc(e, e.v("value")))]
    parts.append(e.let("name", e.cat(*name_parts)))
    # Host copies of the module types: the dependency bodies find every type one lower up.
    for tname in ["i32", "pv", "pi32", "ppv", "pu8"]:
        parts.append(e.let(tname, e.lower(e.v(tname))))
    parts.append(e.let("pkey", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("key"))))
    if with_values:
        parts.append(e.let("pvalue", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("value"))))
    else:
        parts.append(e.let("pvalue", e.v("pv")))
    _deps(e, tg, lay, with_values, parts)
    parts.append(e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))))
    const_fn(e, x, "ht_b", full, body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("ht_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
