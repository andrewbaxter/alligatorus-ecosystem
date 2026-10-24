"""editor-types.atz: the value types the editor modules share, and the operations on them they all need (wat
target).

`str` (`str_t`) is slice-wasm.atz's `slice(u8)`: a `(ptr(u8), i32)` view of UTF-8 text (`str_of` makes one from the
pair; `Kit.sconst`/`Kit.str_of`); `bytes` (`bytes_t`, `bytes_own`, `bytes_raw`, `bytes_new`) is vec-wasm.atz's
`vec(u8)`, a growable byte buffer (`bytes_new()`, owned); `t_pu8` is `ptr(u8)`. A function taking a `bytes`
borrows it (`bytes_raw`); `bytes_str(b)` in the Kit views a buffer's contents as a `str`.

`ints` (`ints_t`, `ints_own`, `ints_raw`, `ints_new`) is `vec(i32)`, `f64s` (`f64s_t`, ...) `vec(f64)` and `f32s`
`vec(f32)`. An
`ints` kept sorted is an index: `ints_find(a, n)` is the position of `n` or, when absent, -(the position to insert
it at) - 1 (the vec's own `insert(i, x)` and `remove(i)` keep it).
"""

from ..wasm.kit import Kit, library

FILE = "editor-types.atz"

EXPORTS = ["t_pu8", "str_t", "str_of"] + [
    pre + "_" + f for pre in ["bytes", "ints", "f64s", "f32s"] for f in ["t", "own", "raw", "new"]
]
FN_EXPORTS = ["ints_find"]


def module(e):
    k = Kit(e)
    x = []
    k.bind(x)
    x.append(e.let("t_pu8", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_u8"))))
    x.append(e.let("slice", e.import_local("slice", "slice-wasm.atz")))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("str_r", e.call(e.fld(e.v("slice"), "type"), e.v("t_u8"))))
    x.append(e.let("str_t", e.fld(e.v("str_r"), "type")))
    x.append(e.let("str_of", e.fld(e.v("str_r"), "of")))
    for pre, elem in [("bytes", "t_u8"), ("ints", "t_i32"), ("f64s", "t_f64"), ("f32s", "t_f32")]:
        x.append(e.let(pre + "_r", e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let(pre + "_" + f, e.fld(e.v(pre + "_r"), "type" if f == "t" else f)))
    v = e.v
    k.dep(
        x,
        "ints_find",
        ["a", "n"],
        ["ints_raw", "t_i32"],
        "t_i32",
        e.seq(
            e.let("lo", k.i32(0)),
            e.let("hi", e.mb.as_(e.fld(v("a"), "len"), k.lo("t_i32"))),
            k.loop(
                "search",
                k.if_(k.ge(v("lo"), v("hi")), k.brk("search")),
                e.let("mid", k.ushr(k.add(v("lo"), v("hi")), e.n(1))),
                e.let("at", k.m(v("a"), "at", v("mid"))),
                k.if_(k.eq(v("at"), v("n")), k.ret(v("mid"))),
                k.ifelse(
                    k.lt(v("at"), v("n")), e.mb.set(v("lo"), k.add(v("mid"), e.n(1))), e.mb.set(v("hi"), v("mid"))
                ),
            ),
            e.ret(k.sub(k.neg(v("lo")), e.n(1))),
        ),
    )
    return library(e, x, EXPORTS, FN_EXPORTS)
