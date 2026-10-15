"""map-wasm.atz / map-llvm.atz / set-wasm.atz / set-llvm.atz: open-addressing hash tables, from one builder.

`map.type((key, value))` and `set.type(key)` yield `{type, own, raw, new}` for constant key (and value) types
(`new() as own` is an owned table, destructor.atz). The key type
must have values.atz's `size`, `hash` and `eq` aspects; the value type its `size`.

A table is a pointer to a header: keys pointer, values pointer (maps), states pointer (one byte per slot: 0 empty,
1 full, 2 removed), then `len`, `cap` and `tombs` as i32. Capacity is a power of two; probing is linear; the table
rehashes to twice its capacity when full plus removed slots reach three quarters.

On a table value: `len` and `cap` are read-only places (readonly.atz); `has(k)` → i32, `remove(k)` → i32 (1 when it
was present), `clear()`; values with a destructor (destructor.atz owned types) are taken by `put` (an owned
temporary or a `move()`), handed out by `get` as borrows (destructor.borrow) and destroyed by `remove`, by an
overwriting `put`, by `clear` and by the owned table's drop; keys are plain values (a key type with a destructor is
refused);
maps also have `get(k)` → option(ptr(value)) (option.atz; `some` of the value's place) and `put(k, v)`; sets have
`add(k)`. Each method is a call of its own function (`<name>_has`, `_get`, `_put`, `_add`, `_remove_key`, `_clear`)
over the `<name>_find`, `_insert`, `_remove`, `_rehash`, `_free` and `_new` functions; all are dependencies
(`func_dep`): a module gets each when its code first uses it. Memory comes from wasm-alloc.atz (wasm) or libc (llvm);
an allocation that fails traps, as does a capacity whose array byte size no longer fits the 32-bit size arithmetic.
"""

from ..memory import destructor, readonly
from ..core import values
from ..eco_mb import p
from ..target_mb import (
    bim0,
    acc,
    a,
    alloc_or_trap,
    asp_iface,
    bim,
    body,
    const_eval_in,
    const_fn,
    conv,
    cve_has,
    cve_type,
    cve_value,
    err_cve,
    fn_of,
    graft,
    handle_methods,
    handle_type,
    has_b,
    ident_of,
    in_,
    int_as,
    int_t,
    loc,
    lookup,
    ret_m,
    self_v,
    str_,
    to_str,
    ty,
    ty_desc,
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
MIN_CAP = 8
EMPTY = 0
FULL = 1
REMOVED = 2

PLACES = ["len", "cap"]
# The internal dependencies a table type carries (callable types), then the methods' dependencies by method name.
DEPS = ["find", "insert", "remove", "clear"]


def _method_deps(with_values):
    return ["m_" + m for m in _methods(with_values) if m != "clear"]


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
        out.append(e.let("option", e.import_local("option", "option-" + self.kind + ".atz")))

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
        return int_as(e, n, _up(e, e.fld(e.v("lib"), "u64"), depth))

    def trap(self, e, depth):
        """A trap statement in target code: the target's trap, a callable type, called through its function value."""
        return e.call(fn_of(e, _up(e, e.fld(e.v("lib"), "trap"), depth)), e.tup())

    def addr_int(self, e, depth):
        """The address-sized integer type (module let)."""
        return _up(e, e.v("i32" if self.kind == WASM else "i64"), depth)

    def malloc(self, e, n, depth):
        """`n` bytes from the heap, or a trap when the allocation fails."""
        return alloc_or_trap(
            e,
            e.call(_up(e, e.fld(e.v("heap"), "malloc"), depth), self.size(e, n, depth)),
            _up(e, e.v("ptr_to_int"), depth),
            self.addr_int(e, depth),
            self.trap(e, depth),
        )

    def free(self, e, ptr, depth):
        """Frees the block at `ptr` (a pointer of any type)."""
        return e.call(
            _up(e, e.fld(e.v("heap"), "free"), depth),
            conv(e, _up(e, e.v("ptr_cast"), depth), ptr, _up(e, e.v("pv"), depth)),
        )

    def zero_fill(self, e, dst, n, depth):
        """Zeroes `n` bytes at `dst`; a statement (the wasm intrinsic is instantiated in the body)."""
        if self.kind == WASM:
            return e.call(e.call(_up(e, e.fld(e.v("lib"), "memory_fill_fn"), depth), e.rec()), e.tup(dst, e.n(0), n))
        return e.call(_up(e, e.fld(e.v("heap"), "memset"), depth), e.tup(dst, e.n(0), self.size(e, n, depth)))

    def byte_ptr(self, e, base, offset, ptr_type):
        """`base` plus `offset` bytes, as `ptr_type` (the int and byte-pointer types are host locals)."""
        if self.kind == WASM:
            return conv(
                e,
                e.lower(e.v("int_to_ptr")),
                e.mb.operator_add(
                    conv(e, e.lower(e.v("ptr_to_int")), base, e.lower(e.v("i32"))), e.n(offset)
                ),
                ptr_type,
            )
        return conv(
            e,
            e.lower(e.v("ptr_cast")),
            e.mb.operator_add(
                conv(e, e.lower(e.v("ptr_cast")), base, e.lower(e.v("pu8"))), e.n(offset)
            ),
            ptr_type,
        )

    def elem_ptr(self, e, base, idx, size_expr, ptr_type):
        """The address of element `idx` of the array at `base` (as `ptr_type`); `size_expr` is the element size."""
        if self.kind == WASM:
            addr = e.mb.operator_add(
                conv(e, e.lower(e.v("ptr_to_int")), base, e.lower(e.v("i32"))),
                e.mb.operator_mul(idx, size_expr),
            )
            return conv(e, e.lower(e.v("int_to_ptr")), addr, ptr_type)
        return e.mb.operator_add(conv(e, e.lower(e.v("ptr_cast")), base, ptr_type), idx)

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
    return e.mb.field(
        conv(e, e.lower(e.v("ptr_cast")), e.mb.as_(h, e.lower(e.v("pv"))), e.lower(e.v("ppv"))), e.n(index)
    )


def _i32_cell(e, h, index):
    return e.mb.field(
        conv(e, e.lower(e.v("ptr_cast")), e.mb.as_(h, e.lower(e.v("pv"))), e.lower(e.v("pi32"))), e.n(index)
    )


def _typed(e, ptr_expr, type_name):
    return conv(e, e.lower(e.v("ptr_cast")), ptr_expr, e.lower(e.v(type_name)))


def _i32(e, n):
    return e.mb.as_(e.n(n), e.lower(e.v("i32")))


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
        # The array byte sizes must fit the (signed 32-bit) size arithmetic: a capacity past that traps.
        e.if_only(e.mb.operator_gt(cap, _up(e, e.v("max_cap_k"), BODY_HOST)), tg.trap(e, d)),
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
            2,
            e.mb.set(
                _ptr_cell(e, h, lay.vals),
                tg.malloc(e, e.mb.operator_mul(cap, _up(e, e.v("value_size"), BODY_HOST)), d),
            ),
        )
        out.insert(
            1,
            e.if_only(e.mb.operator_gt(cap, _up(e, e.v("max_cap_v"), BODY_HOST)), tg.trap(e, d)),
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
    """find(t, key): the index of `key`, or -1."""
    h = e.v("t")
    return e.mb.labeled(
        "f",
        e.seq(
            e.if_only(e.eq(_i32_cell(e, h, lay.cap), e.n(0)), e.mb.return_to("f", _i32(e, -1))),
            _probe(
                e,
                tg,
                lay,
                h,
                e.v("key"),
                BODY_MOD,
                lambda idx: e.mb.return_to("f", idx),
                lambda idx: e.mb.return_to("f", _i32(e, -1)),
            ),
            e.mb.return_to("f", _i32(e, -1)),
        ),
    )


def _insert_fn_body(e, tg, lay):
    """insert(t, key): inserts `key` (known absent), growing first when needed; yields its index."""
    h = e.v("t")

    def rehash():
        return e.call(fn_of(e, _up(e, e.v("rehash"), BODY_HOST)), h)

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
            e.mb.return_to("i", _insert_body(e, tg, lay, h, e.v("key"), BODY_MOD)),
        ),
    )


def _remove_body(e, tg, lay, with_values):
    """remove(t, key): removes `key` (destroying its value when values have a destructor); yields 1 when it was
    present."""
    h = e.v("t")

    def body(drops):
        return e.mb.labeled(
            "r",
            e.seq(
                e.if_only(e.eq(_i32_cell(e, h, lay.cap), e.n(0)), e.mb.return_to("r", _i32(e, 0))),
                _probe(
                    e,
                    tg,
                    lay,
                    h,
                    e.v("key"),
                    BODY_MOD,
                    lambda idx: e.seq(
                        _drop_value_at(e, lay, h, idx) if drops else e.seq(),
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

    if not with_values:
        return e.stage(body(False))
    return e.stage(e.if_else(_up(e, e.v("value_drops"), BODY_HOST), body(True), body(False)))


def _clear_body(e, tg, lay, with_values):
    """clear(t): empties the table, destroying the values when they have a destructor."""
    h = e.v("t")

    def drop_all():
        return e.seq(
            e.let("__i", _i32(e, 0)),
            e.let("states", _typed(e, _ptr_cell(e, h, lay.states), "pu8")),
            e.mb.labeled(
                "dr",
                e.foreach(
                    tg.loop(e, BODY_MOD),
                    "_",
                    e.seq(
                        e.if_only(
                            e.not_(e.mb.operator_lt(e.v("__i"), _i32_cell(e, h, lay.cap))), e.mb.return_label("dr")
                        ),
                        e.if_only(
                            e.eq(e.mb.field(e.v("states"), e.v("__i")), e.n(FULL)), _drop_value_at(e, lay, h, e.v("__i"))
                        ),
                        e.mb.set(e.v("__i"), e.mb.operator_add(e.v("__i"), e.n(1))),
                    ),
                ),
            ),
        )

    def body(drops):
        return e.if_only(
            e.not_(e.eq(_i32_cell(e, h, lay.cap), e.n(0))),
            e.seq(
                drop_all() if drops else e.seq(),
                tg.zero_fill(e, _ptr_cell(e, h, lay.states), _i32_cell(e, h, lay.cap), BODY_MOD),
                e.mb.set(_i32_cell(e, h, lay.len), e.n(0)),
                e.mb.set(_i32_cell(e, h, lay.tombs), e.n(0)),
            ),
        )

    if not with_values:
        return e.stage(body(False))
    return e.stage(e.if_else(_up(e, e.v("value_drops"), BODY_HOST), body(True), body(False)))


def _free_body(e, tg, lay, with_values):
    """free(t): destroys the values (through `clear`), frees the arrays and the header."""
    h = e.v("t")
    return e.seq(
        _dep_call(e, "clear", BODY_HOST, h),
        e.if_only(e.not_(e.eq(_i32_cell(e, h, lay.cap), e.n(0))), _free_arrays(e, tg, lay, with_values, h)),
        tg.free(e, h, BODY_MOD),
    )


def _new_body(e, tg, lay):
    return e.seq(
        e.let("h", tg.malloc(e, e.n(HEADER), BODY_MOD)),
        e.mb.set(_i32_cell(e, e.v("h"), lay.len), e.n(0)),
        e.mb.set(_i32_cell(e, e.v("h"), lay.cap), e.n(0)),
        e.mb.set(_i32_cell(e, e.v("h"), lay.tombs), e.n(0)),
        e.ret(e.v("h")),
    )


def _dep_call(e, name, dh, *args):
    """A call of the dependency `name` (a local `dh` stages up) in a dependency body."""
    return e.call(fn_of(e, _up(e, e.v(name), dh)), args[0] if len(args) == 1 else e.tup(*args))


def _has_body(e, tg, lay):
    """has(t, key) -> i32: whether `key` is present."""
    return e.seq(
        e.ret(
            e.mb.as_(e.not_(e.eq(_dep_call(e, "find", BODY_HOST, e.v("t"), e.v("key")), e.n(-1))), e.lower(e.v("i32")))
        )
    )


def _put_body(e, tg, lay):
    """put(t, key, value): stores `value` under `key`, inserting it when absent. A value with a destructor is taken
    out of its parameter (`forget` marks the binding moved: the table owns it now) and the value it replaces is
    destroyed."""

    def body(drops):
        return e.seq(
            e.let("idx", _dep_call(e, "find", BODY_HOST, e.v("t"), e.v("key"))),
            e.if_else(
                e.eq(e.v("idx"), e.n(-1)),
                e.mb.set(e.v("idx"), _dep_call(e, "insert", BODY_HOST, e.v("t"), e.v("key"))),
                _drop_value_at(e, lay, e.v("t"), e.v("idx")) if drops else e.seq(),
            ),
            e.mb.set(
                e.mb.field(_typed(e, _ptr_cell(e, e.v("t"), lay.vals), "pvalue"), e.v("idx")),
                e.call(e.fld(e.v("value"), "forget"), e.tup()) if drops else e.v("value"),
            ),
        )

    # The variant is chosen inside the staged body by the constant condition (one staged body).
    return e.stage(e.if_else(_up(e, e.v("value_drops"), BODY_HOST), body(True), body(False)))


def _drop_value_at(e, lay, h, idx):
    """A statement destroying the value in slot `idx` (values with a destructor): taken as an owned value into a
    binding whose drop destroys it."""
    return e.seq(
        e.let(
            "__o",
            e.mb.as_(e.mb.field(_typed(e, _ptr_cell(e, h, lay.vals), "pvalue"), idx), _up(e, e.v("value_own"), BODY_HOST)),
        )
    )


def _add_body(e, tg, lay):
    """add(t, key): inserts `key` when absent."""
    return e.if_only(
        e.eq(_dep_call(e, "find", BODY_HOST, e.v("t"), e.v("key")), e.n(-1)),
        e.seq(e.let("__i", _dep_call(e, "insert", BODY_HOST, e.v("t"), e.v("key")))),
    )


def _remove_key_body(e, tg, lay):
    """remove_key(t, key) -> i32: the method's function over `remove`."""
    return e.seq(e.ret(_dep_call(e, "remove", BODY_HOST, e.v("t"), e.v("key"))))


def _get_body(e, tg, lay, dm, dh):
    """get(t, key) -> option: `some` of the value's place (a borrow when values have a destructor), or `none`.
    Staged `dm` below the module and `dh` below the setup's locals, where the option type and constructor exist."""
    return e.seq(
        e.let("idx", _dep_call(e, "find", dh, e.v("t"), e.v("key"))),
        e.let("found", e.not_(e.eq(e.v("idx"), e.n(-1)))),
        e.ret(
            _dep_call(
                e,
                "opt_of_t",
                dh,
                e.mb.as_(e.v("found"), _up(e, e.v("i32"), dh)),
                e.if_else(
                    e.v("found"),
                    conv(
                        e,
                        _up(e, e.v("ptr_cast"), dh),
                        tg.elem_ptr(
                            e,
                            _ptr_cell(e, e.v("t"), lay.vals),
                            e.v("idx"),
                            _up(e, e.v("value_size"), dh),
                            _up(e, e.v("pvalue"), dh),
                        ),
                        _up(e, e.v("pvref"), dh),
                    ),
                    conv(e, _up(e, e.v("ptr_cast"), dh), tg.null(e, dm), _up(e, e.v("pvref"), dh)),
                ),
            )
        ),
    )


def _func_dep(e, lib_dep, name, params, ty_, body_, staged=False):
    return e.call(
        lib_dep,
        e.rec(
            p("name", name),
            p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
            p("ty", ty_),
            p("body", body_ if staged else e.stage(body_)),
        ),
    )


# The dependencies whose body maker makes the staged body itself (choosing between variants on the host).
STAGED = {"remove", "clear", "m_put"}


# The function types made in the const function's host body (over the key and value types); the others are module
# values.
HOST_FN_TYPES = ["find_t", "put_t", "add_t"]


def _deps(e, tg, lay, with_values, out):
    """In the const function's host body: the table's dependencies (constants from here on), the internal ones and
    the methods' but `get`, which the setup defines over the option type."""
    deps = [
        ("rehash", "rehash", "rehash_t", ("t",), _rehash_body(e, tg, lay, with_values)),
        ("find", "find", "find_t", ("t", "key"), _find_body(e, tg, lay)),
        ("insert", "insert", "find_t", ("t", "key"), _insert_fn_body(e, tg, lay)),
        ("remove", "remove", "find_t", ("t", "key"), _remove_body(e, tg, lay, with_values)),
        ("clear", "clear", "rehash_t", ("t",), _clear_body(e, tg, lay, with_values)),
        ("free_table", "free", "free_t", ("t",), _free_body(e, tg, lay, with_values)),
        ("new", "new", "new_t", (), _new_body(e, tg, lay)),
        ("m_has", "has", "find_t", ("t", "key"), _has_body(e, tg, lay)),
        ("m_remove", "remove_key", "find_t", ("t", "key"), _remove_key_body(e, tg, lay)),
    ]
    if with_values:
        deps.append(("m_put", "put", "put_t", ("t", "key", "value"), _put_body(e, tg, lay)))
    else:
        deps.append(("m_add", "add", "add_t", ("t", "key"), _add_body(e, tg, lay)))
    for fn, suffix, fn_t, params, fbody in deps:
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
                    fbody,
                    staged=fn in STAGED,
                ),
            )
        )


# The largest byte size the 32-bit size arithmetic handles.
MAX_BYTES = 2147483647


def _fields(with_values):
    return (
        ["key", "pv", "pi32", "ppv", "pu8", "pkey", "pvalue", "value_size", "ro_i32"] + DEPS + _method_deps(with_values)
    )


def _setup(e, tg, lay, with_values):
    """Staged in the caller's context: the table types over the lowered dependencies, and for maps the `get`
    dependency over the option type of the value places."""
    out = []
    for name in (
        ["key", "pkey", "pvalue", "value_size", "name", "free_table", "new"]
        + (["pvref"] if with_values else [])
        + DEPS
        + [d for d in _method_deps(with_values) if d != "m_get"]
    ):
        out.append(e.let(name, e.lower(e.v(name))))
    for tname in ["pv", "pi32", "ppv", "pu8", "i32", "ptr_cast", "ptr_to_int", "int_to_ptr"]:
        out.append(e.let(tname, _up(e, e.v(tname), SETUP_MOD)))
    # The places' type: read-only, so a user cannot desynchronize the length and capacity.
    out.append(e.let("ro_i32", e.call(_up(e, e.fld(e.v("readonly"), "type"), SETUP_MOD), e.v("i32"))))
    if with_values:
        out.append(e.let("opt", e.call(_up(e, e.fld(e.v("option"), "type"), SETUP_MOD), e.v("pvref"))))
        out.append(e.let("opt_t", e.fld(e.v("opt"), "type")))
        out.append(e.let("opt_of_t", e.fld(e.v("opt"), "of_t")))
        out.append(
            e.let(
                "m_get",
                _func_dep(
                    e,
                    _up(e, e.fld(e.v("lib"), "func_dep"), SETUP_MOD),
                    e.cat(e.v("name"), e.s("_get")),
                    ("t", "key"),
                    e.call(
                        _up(e, e.fld(e.v("lib"), "fn"), SETUP_MOD),
                        e.rec(p("params", e.list_new(e.mb.eval_type(), e.v("pv"), e.v("key"))), p("ret", e.v("opt_t"))),
                    ),
                    _get_body(e, tg, lay, SETUP_MOD + 1, 1),
                ),
            )
        )
    fields = [p(k, e.v(k)) for k in _fields(with_values)]
    out.append(
        e.let("raw", e.mb.as_(e.call(_up(e, e.fld(e.v("ht"), "new"), SETUP_MOD), e.rec(*fields)), e.mb.eval_type()))
    )
    out.append(
        e.let(
            "owned_r",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", fn_of(e, e.v("free_table")))),
            ),
        )
    )
    out.append(
        e.ret(
            e.rec(
                p("type", e.fld(e.v("owned_r"), "type")),
                p("own", e.fld(e.v("owned_r"), "own")),
                p("raw", e.v("raw")),
                p("new", fn_of(e, e.v("new"))),
            )
        )
    )
    return e.mb.seq(out)


def _ht(e, x, tg, lay, with_values):
    """The unowned table handle type: a pointer carrying the key (and value) types, its places and its method
    dependencies."""
    fields = [p(k, int_t(e) if k == "value_size" else ty(e)) for k in _fields(with_values)]
    methods = _methods(with_values)
    label = "map" if with_values else "set"
    places = {
        "len": lambda self_as: e.mb.as_(e.mb.field(self_as("pi32"), e.n(lay.len)), e.lower(in_(e, "ro_i32"))),
        "cap": lambda self_as: e.mb.as_(e.mb.field(self_as("pi32"), e.n(lay.cap)), e.lower(in_(e, "ro_i32"))),
    }
    meth = handle_type(
        e,
        x,
        "ht",
        "ht_m",
        label,
        fields,
        places,
        methods,
        under="pv",
        desc_expr=e.cat(e.s(label + "("), ty_desc(e, in_(e, "key")), e.s(")")),
        identity="key",
        ptr_cast=e.lower(e.v("ptr_cast")),
    )

    def dep(kind):
        return fn_of(e, e.lower(e.v("clear" if kind == "clear" else "m_" + kind)))

    def part(i):
        return graft(e, e.call_m(e.v("parts"), "get", e.s(str(i))))

    def method_body(kind):
        if kind == "clear":
            return e.call(dep(kind), self_v(e))
        if kind == "put":
            return e.call(dep(kind), e.tup(self_v(e), part(0), part(1)))
        return e.call(dep(kind), e.tup(self_v(e), graft(e, a(e, "argument"))))

    kind_prelude = {"put": _tuple_arg(e, label + ".put", a(e, "argument"), 2)} if with_values else {}
    handle_methods(e, x, meth, "ht_m", fields, methods, method_body, kind_prelude=kind_prelude)


def _tuple_arg(e, label, cv, count):
    """Splits the tuple code-value `cv` into `parts` ("0", "1", ...), requiring exactly `count` elements."""
    msg = label + ": argument must be a tuple of " + str(count)
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
    x.append(e.let("readonly", e.import_local("readonly", readonly.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("i64", e.fld(e.v("lib"), "i64")))
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.v("i32"))))
    x.append(e.let("ppv", e.call(e.fld(e.v("lib"), "ptr"), e.v("pv"))))
    x.append(e.let("pu8", e.call(e.fld(e.v("lib"), "ptr"), e.fld(e.v("lib"), "u8"))))
    for name in ["ptr_cast", "ptr_to_int", "int_to_ptr"]:
        x.append(e.let(name, e.fld(e.v("lib"), name)))
    tg.module_lets(e, x)
    for name, params, ret in [
        ("rehash_t", ["pv"], "void"),
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
        # Values with a destructor are stored as their under type (`value_raw`); `get` hands out borrows
        # (`value_ref`); `remove`, `put` and `clear` destroy them through the adopting type (`value_own`).
        parts.append(e.let("value_drops", has_b(e, xx(e), e.v("value"), e.mb.eval_aspect_drop_dynamic())))
        parts.append(e.let("owned_m", e.lower(e.fld(e.v("destructor"), "owned_m"))))
        parts.append(
            e.let(
                "value_raw",
                e.if_else(
                    e.v("value_drops"),
                    bim0(e, e.v("owned_m"), "under", e.fld(lookup(e, xx(e), e.v("value"), e.v("owned_m")), "value")),
                    e.v("value"),
                ),
            )
        )
        parts.append(
            e.let(
                "value_ref",
                e.if_else(
                    e.v("value_drops"), e.call(e.lower(e.fld(e.v("destructor"), "borrow")), e.v("value")), e.v("value")
                ),
            )
        )
        parts.append(
            e.let(
                "value_own",
                e.if_else(
                    e.v("value_drops"), e.call(e.lower(e.fld(e.v("destructor"), "adopt")), e.v("value")), e.v("value")
                ),
            )
        )
        parts.extend(size_of(e, full, e.v("value"), "value_size"))
        parts.append(e.let("max_cap_v", e.mb.operator_div(e.int_of(MAX_BYTES), e.v("value_size"))))
    else:
        parts.extend(const_type_arg(e, full, e.v("argv"), "key"))
        parts.append(e.let("value_size", e.int_of(0)))
    parts.extend(size_of(e, full, e.v("key"), "key_size"))
    parts.append(
        e.if_only(
            has_b(e, xx(e), e.v("key"), e.mb.eval_aspect_drop_dynamic()),
            ret_m(
                e,
                err_cve(
                    e,
                    loc(e),
                    e.cat(e.s(full + ": key type "), ty_desc(e, e.v("key")), e.s(" has a destructor; keys are plain")),
                ),
            ),
        )
    )
    # The largest capacities whose array byte sizes the 32-bit size arithmetic handles.
    parts.append(e.let("max_cap_k", e.mb.operator_div(e.int_of(MAX_BYTES), e.v("key_size"))))
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
    for tname in ["i32", "pv", "pi32", "ppv", "pu8", "void", "ptr_cast", "ptr_to_int", "int_to_ptr"]:
        parts.append(e.let(tname, e.lower(e.v(tname))))
    parts.append(e.let("pkey", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("key"))))
    if with_values:
        parts.append(e.let("pvalue", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("value_raw"))))
        parts.append(e.let("pvref", e.call(e.lower(e.fld(e.v("lib"), "ptr")), e.v("value_ref"))))
    else:
        parts.append(e.let("pvalue", e.v("pv")))

    def fn_t(params, ret):
        return e.call(
            e.lower(e.fld(e.v("lib"), "fn")), e.rec(p("params", e.list_new(e.mb.eval_type(), *params)), p("ret", ret))
        )

    parts.append(e.let("find_t", fn_t([e.v("pv"), e.v("key")], e.v("i32"))))
    if with_values:
        parts.append(e.let("put_t", fn_t([e.v("pv"), e.v("key"), e.v("value")], e.v("void"))))
    else:
        parts.append(e.let("add_t", fn_t([e.v("pv"), e.v("key")], e.v("void"))))
    _deps(e, tg, lay, with_values, parts)
    parts.append(
        e.ret(
            e.eresult_ok(
                e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e, tg, lay, with_values))))
            )
        )
    )
    const_fn(e, x, "ht_b", full, body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("ht_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
