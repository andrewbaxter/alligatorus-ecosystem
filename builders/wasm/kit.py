"""Shorthand for wat code, all at one staging depth: a module-level name (a type, a dependency,
an import, a hook, a data block) is reached from a staged body by lowering it once (`Kit.lo`). Library modules
build their dependencies in a setup sequence lowered into the module (as wasm-alloc.atz does) and export them;
app modules build at their top level. Addresses are plain i32 values; memory is read and written through typed
pointers made from them (`ptr_of`)."""

from ..eco_mb import p
from ..target_mb import conv, fn_of, is_const_expr
from .wat import bind_types

# The wasm types every module binds (bind_types, plus these pointer types).
PTRS = [("t_pi32", "t_i32"), ("t_pf64", "t_f64"), ("t_pf32", "t_f32"), ("t_pu32", "t_u32")]


def as_seq(e, body_):
    """A function body as a sequence labeled `fn` (a `return` leaves the innermost block, so the function's early
    exits return to the label: `Kit.ret`)."""
    ((kind, _),) = body_["variant"].items()
    return e.mb.labeled("fn", body_ if kind == "seq" else e.seq(body_))


class Kit:
    def __init__(self, e):
        self.e = e

    # --- module-level (host) ---

    def bind(self, out):
        """Binds `wasm` and the wasm types into `out`."""
        e = self.e
        out.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
        bind_types(e, out)
        for name, under in PTRS:
            out.append(e.let(name, e.call(e.fld(e.v("wasm"), "ptr"), e.v(under))))

    def tuple_t(self, names):
        """A wasm tuple type over type binding names (`t_f64`, ...)."""
        e = self.e
        return e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), *[e.v(n) for n in names]))

    def fn_t(self, params, ret):
        """A function type from type binding names (`t_i32`, ...)."""
        e = self.e
        return e.call(
            e.fld(e.v("wasm"), "fn"),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *[e.v(n) for n in params])), p("ret", e.v(ret))),
        )

    def dep(self, out, name, params, param_types, ret, body_):
        """A dependency `name` (bound under that name in `out`): a function defined in the module that uses it."""
        e = self.e
        out.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "func_dep"),
                    e.rec(
                        p("name", e.s(name)),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", self.fn_t(param_types, ret)),
                        p("body", e.stage(as_seq(e, body_))),
                    ),
                ),
            )
        )

    def block(self, out, name, size):
        """A zeroed block of `size` bytes, a dependency bound under `name` (its address is `addr(name)`)."""
        e = self.e
        out.append(
            e.let(name, e.call(e.fld(e.v("wasm"), "alloc_dep"), e.rec(p("name", e.s(name)), p("size", e.int_of(size)))))
        )

    def text(self, out, name, text):
        """A NUL-terminated UTF-8 constant, a dependency bound under `name`; `cstr(name)` is its pointer and
        `len(text)` its byte length."""
        e = self.e
        out.append(
            e.let(name, e.call(e.fld(e.v("wasm"), "cstr_dep"), e.rec(p("name", e.s(name)), p("text", e.s(text)))))
        )

    # --- staged (target code) ---

    def lo(self, name):
        return self.e.lower(self.e.v(name))

    def call(self, f, *args):
        """A call of the module-level function `f` (an import, an export, a hook: a callable value)."""
        e = self.e
        return e.call(self.lo(f), args[0] if len(args) == 1 else e.tup(*args))

    def dcall(self, f, *args):
        """A call of the module-level dependency `f` (a callable type: its function value is the unit cast to it)."""
        e = self.e
        return e.call(fn_of(e, self.lo(f)), args[0] if len(args) == 1 else e.tup(*args))

    def lib(self, lib, f, *args):
        """A call of the function `f` exported by the imported module `lib`."""
        e = self.e
        return e.call(e.lower(e.fld(e.v(lib), f)), args[0] if len(args) == 1 else e.tup(*args))

    def i32(self, v):
        e = self.e
        if isinstance(v, (int, float)):
            v = e.n(v)
        return e.mb.as_(v, self.lo("t_i32"))

    def f64(self, v):
        e = self.e
        if isinstance(v, (int, float)):
            v = e.n(v)
        return e.mb.as_(v, self.lo("t_f64"))

    def ptr_of(self, addr, ptr_type):
        """The i32 address `addr` as a pointer of the type binding `ptr_type` (`t_pf64`, ...)."""
        e = self.e
        if is_const_expr(addr):
            return e.mb.as_(addr, self.lo(ptr_type))
        return conv(e, e.lower(e.fld(e.v("wasm"), "int_to_ptr")), addr, self.lo(ptr_type))

    def addr(self, ptr):
        """A pointer's address (i32)."""
        e = self.e
        return conv(e, e.lower(e.fld(e.v("wasm"), "ptr_to_int")), ptr, self.lo("t_i32"))

    def block_addr(self, name):
        """The address of the block or text dependency `name`."""
        return self.addr(self.e.call(fn_of(self.e, self.lo(name)), self.e.tup()))

    def cstr(self, name):
        """The `ptr(u8)` of the text dependency `name`."""
        e = self.e
        return e.call(fn_of(e, self.lo(name)), e.tup())

    def sconst(self, name, text):
        """The text dependency `name` (holding `text`) as a `str` value (`str_of`, slice-wasm.atz's constructing
        type bound at module level)."""
        return self.str_of(self.ptr_of(self.addr(self.cstr(name)), "t_pu8"), self.i32(len(text.encode())))

    def str_of(self, ptr, len_):
        """A `str` over `ptr` (a `ptr(u8)`) and `len_` (i32)."""
        e = self.e
        return e.mb.as_(e.tup(ptr, len_), self.lo("str_of"))

    def bytes_str(self, b):
        """A `bytes` buffer's contents as a `str`."""
        e = self.e
        return self.str_of(e.fld(b, "data"), e.fld(b, "len"))

    def sempty(self):
        """The empty `str` (over the first text dependency bound as `t_empty`)."""
        return self.str_of(self.ptr_of(self.addr(self.cstr("t_empty")), "t_pu8"), self.i32(0))

    def sargs(self, s):
        """A `str` value as a hook's text argument: (ptr(u8), u32)."""
        e = self.e
        return [e.fld(s, "data"), self.m(e.fld(s, "len"), "wrap", self.lo("t_u32"))]

    def at(self, addr, index, ptr_type="t_pi32"):
        """The place of element `index` of the array of `ptr_type`'s pointee at the address `addr`."""
        e = self.e
        if isinstance(index, int):
            index = e.n(index)
        return e.mb.field(self.ptr_of(addr, ptr_type), index)

    def set(self, place, value):
        return self.e.mb.set(place, value)

    def add(self, a, b):
        return self.e.mb.operator_add(a, b)

    def sub(self, a, b):
        return self.e.mb.operator_sub(a, b)

    def mul(self, a, b):
        return self.e.mb.operator_mul(a, b)

    def div(self, a, b):
        return self.e.mb.operator_div(a, b)

    def lt(self, a, b):
        return self.e.mb.operator_lt(a, b)

    def le(self, a, b):
        return self.e.mb.operator_le(a, b)

    def gt(self, a, b):
        return self.e.mb.operator_gt(a, b)

    def ge(self, a, b):
        return self.e.mb.operator_ge(a, b)

    def loop(self, label, *body):
        """An endless loop, left by `brk(label)`; `cont(label)` goes to the next round."""
        e = self.e
        return e.mb.labeled(
            label,
            e.foreach(
                e.call(e.lower(e.fld(e.v("wasm"), "loop_fn")), e.rec()), "_", e.mb.labeled(label + "_c", e.seq(*body))
            ),
        )

    def brk(self, label):
        return self.e.mb.return_label(label)

    def cont(self, label):
        return self.e.mb.return_label(label + "_c")

    def for_(self, var, start, end, label, *body):
        """`var` from `start` up to (not including) `end` (i32), stepping 1; `brk`/`cont` with `label`."""
        e = self.e
        return e.seq(
            e.let(var, self.i32(start) if isinstance(start, int) else start),
            e.mb.labeled(
                label,
                e.foreach(
                    e.call(e.lower(e.fld(e.v("wasm"), "loop_fn")), e.rec()),
                    "_",
                    e.seq(
                        e.if_only(e.mb.operator_ge(e.v(var), end), e.mb.return_label(label)),
                        e.mb.labeled(label + "_c", e.seq(*body)),
                        e.mb.set(e.v(var), e.mb.operator_add(e.v(var), e.n(1))),
                    ),
                ),
            ),
        )

    def if_(self, cond, *then):
        return self.e.if_only(cond, self.e.seq(*then))

    def ifelse(self, cond, then, else_):
        return self.e.if_else(cond, then, else_)

    def ret(self, v=None):
        """Leaves the function (its body labeled `fn`), with the value `v` when given."""
        e = self.e
        return e.mb.return_to("fn", v) if v is not None else e.mb.return_label("fn")

    def not_(self, v):
        return self.e.not_(v)

    def eq(self, a, b):
        return self.e.eq(a, b)

    def ne(self, a, b):
        return self.e.not_(self.e.eq(a, b))

    def and_(self, a, b):
        """Both conditions (both evaluated)."""
        e = self.e
        return self.ne(e.mb.operator_and(e.mb.as_(a, self.lo("t_i32")), e.mb.as_(b, self.lo("t_i32"))), e.n(0))

    def or_(self, a, b):
        """Either condition (both evaluated)."""
        e = self.e
        return self.ne(e.mb.operator_or(e.mb.as_(a, self.lo("t_i32")), e.mb.as_(b, self.lo("t_i32"))), e.n(0))

    def neg(self, a):
        return self.e.mb.operator_neg(a)

    def band(self, a, b):
        return self.e.mb.operator_and(a, b)

    def bor(self, a, b):
        return self.e.mb.operator_or(a, b)

    def shl(self, a, b):
        return self.e.mb.operator_shl(a, b)

    def shr(self, a, b):
        return self.e.mb.operator_shr(a, b)

    def ushr(self, a, b):
        return self.e.mb.operator_ushr(a, b)

    def rem(self, a, b):
        return self.e.mb.operator_mod(a, b)

    def to_f64(self, v):
        """An integer value converted to f64."""
        return self.m(v, "to_float", self.lo("t_f64"))

    def trunc(self, v):
        """An f64 truncated toward zero to i32."""
        return self.m(v, "trunc", self.lo("t_i32"))

    def floor(self, v):
        return self.m(v, "floor", self.e.tup())

    def ceil(self, v):
        return self.m(v, "ceil", self.e.tup())

    def sqrt(self, v):
        return self.m(v, "sqrt", self.e.tup())

    def fabs(self, v):
        return self.m(v, "abs", self.e.tup())

    def fmin(self, a, b):
        return self.m(a, "min", b)

    def fmax(self, a, b):
        return self.m(a, "max", b)

    def m(self, v, method, *args):
        """A method call on a value: `v.method(args)`; no arguments pass `()`."""
        e = self.e
        return e.call(e.fld(v, method), args[0] if len(args) == 1 else e.tup(*args))


def stack(e, k, levels):
    """Nested lowered levels for a library whose types build on each other (a record over a vec over a record...):
    `levels` is a list of functions `f(x) -> names`, each appending its statements to a fresh list `x` (the kit's
    types bound, the previous levels' names re-bound) and returning the names it defines for the levels after it.
    Returns (the last level's statements, every name) for the module's own `top` to lower.
    """
    names = []
    x = None
    for i, f in enumerate(levels):
        prev = x
        x = []
        k.bind(x)
        if prev is not None:
            prev.append(e.ret(e.rec(*[p(n, e.v(n)) for n in names])))
            x.append(e.let("k%d" % i, e.lower(e.mb.seq(prev))))
            for n in names:
                x.append(e.let(n, e.fld(e.v("k%d" % i), n)))
        names = names + list(f(x))
    return x, names


def fn_exports(e, k, names):
    """The record of `k`'s dependencies `names` as function values (what a library module returns)."""
    return e.rec(*[p(name, fn_of(e, e.fld(k, name))) for name in names])


def library(e, x, type_exports, exports):
    """A library module's top: `x` (its last level's statements) returns `type_exports` and the dependencies
    `exports` by name, and the module lowers it and returns the types and the dependencies as function values."""
    x.append(e.ret(e.rec(*[p(n, e.v(n)) for n in type_exports + exports])))
    return [
        e.let("k", e.lower(e.mb.seq(x))),
        e.ret(
            e.rec(
                *[p(n, e.fld(e.v("k"), n)) for n in type_exports],
                *[p(n, fn_of(e, e.fld(e.v("k"), n))) for n in exports],
            )
        ),
    ]
