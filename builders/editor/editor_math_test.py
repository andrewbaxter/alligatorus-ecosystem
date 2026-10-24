"""editor-math-test.atz: a WASI app checking math-wasm.atz's functions and editor-mem.atz's memory functions; it prints
the index of the first failed check (exit status 1)."""

import math

from ..wasm import math_wasm
from . import wasi_test, editor_mem

# (function, arguments, expected): the libm values, to about one ulp.
MATH_CASES = [
    (fn, args, getattr(math, py)(*args))
    for fn, py, args in [
        ("m_exp", "exp", [1.0]),
        ("m_exp", "exp", [-3.25]),
        ("m_exp", "exp", [700.5]),
        ("m_exp", "exp", [-740.0]),
        ("m_log", "log", [10.0]),
        ("m_log", "log", [1e-300]),
        ("m_log", "log", [0.7]),
        ("m_sin", "sin", [0.5]),
        ("m_sin", "sin", [3.0]),
        ("m_sin", "sin", [-100.25]),
        ("m_cos", "cos", [0.5]),
        ("m_cos", "cos", [-2.0]),
        ("m_cos", "cos", [1000.0]),
        ("m_atan2", "atan2", [1.0, 2.0]),
        ("m_atan2", "atan2", [-3.0, -0.5]),
        ("m_atan2", "atan2", [0.3, -1.0]),
        ("m_atan2", "atan2", [5.0, 1.0]),
        ("m_pow", "pow", [2.5, 3.5]),
    ]
]


def module(e):
    def checks(k):
        M = "math"

        def c(f, *args):
            return k.lib(M, f, *args)

        v = e.v
        return [
            # an allocation is zeroed, usable and freed
            e.let("a", k.lib("mem", "mem_alloc", e.n(64))),
            k.check(k.ne(v("a"), e.n(0))),
            k.check(k.eq(k.at(v("a"), 15), e.n(0))),
            k.set(k.at(v("a"), 15), e.n(7)),
            k.check(k.eq(k.at(v("a"), 15), e.n(7))),
            k.lib("mem", "mem_free", v("a")),
            k.check(k.eq(c("m_clamp", k.f64(5), k.f64(0), k.f64(2)), e.n(2))),
            k.check(k.eq(c("m_lerp", k.f64(2), k.f64(4), k.f64(0.25)), e.n(2.5))),
            k.check(k.eq(c("m_hypot", k.f64(3), k.f64(4)), e.n(5))),
            *[
                k.check(
                    k.le(k.fabs(k.sub(c(fn, *[k.f64(a) for a in args]), e.n(want))), e.n(abs(want) * 2e-15 + 1e-300))
                )
                for fn, args, want in MATH_CASES
            ],
        ]

    return wasi_test.module(e, [("math", math_wasm.FILE), ("mem", editor_mem.FILE)], checks)
