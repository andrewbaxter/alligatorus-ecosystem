"""editor-mem.atz: raw memory for the editor protocol's buffers the ide hands over and takes back (wat target;
dependencies). Addresses are i32: `mem_alloc(n)` is `n` zeroed bytes from wasm-alloc.atz (an allocation that fails
traps), `mem_free(a)`."""

from ..target_mb import fn_of
from ..wasm.kit import Kit, library

FILE = "editor-mem.atz"

EXPORTS = ["mem_alloc", "mem_free"]


def module(e):
    k = Kit(e)
    x = []
    k.bind(x)
    x.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    x.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))

    def pv(addr):
        return k.ptr_of(addr, "t_pv")

    def fill(addr, n):
        return e.call(e.call(e.lower(e.fld(e.v("wasm"), "memory_fill_fn")), e.rec()), e.tup(pv(addr), e.n(0), n))

    trap = e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())
    k.dep(
        x,
        "mem_alloc",
        ["n"],
        ["t_i32"],
        "t_i32",
        e.seq(
            e.let("a", k.addr(e.call(e.lower(e.fld(e.v("heap"), "malloc")), e.v("n")))),
            k.if_(k.eq(e.v("a"), e.n(0)), trap),
            fill(e.v("a"), e.v("n")),
            e.ret(e.v("a")),
        ),
    )
    k.dep(x, "mem_free", ["a"], ["t_i32"], "t_void", e.call(e.lower(e.fld(e.v("heap"), "free")), pv(e.v("a"))))
    return library(e, x, [], EXPORTS)
