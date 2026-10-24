"""math-wasm.atz: elementary math for the wat target, every function a dependency a module gets on first use.

Computed in wasm so every host computes the same results (math_kernels.py: fdlibm's argument reductions and kernel
polynomials): `m_sin`, `m_cos`, `m_exp`, `m_log` (f64 -> f64), `m_atan2(y, x)`, `m_pow(x, y)` (a positive `x`);
`m_clamp(x, lo, hi)`, `m_lerp(a, b, t)`, `m_hypot(x, y)`."""

from ..eco_mb import p
from . import math_kernels
from .kit import Kit, fn_exports

FILE = "math-wasm.atz"

EXPORTS = ["m_sin", "m_cos", "m_exp", "m_log", "m_atan2", "m_pow", "m_clamp", "m_lerp", "m_hypot"]


def module(e):
    k = Kit(e)
    x = []
    k.bind(x)
    math_kernels.define(e, k, x)
    k.dep(
        x,
        "m_clamp",
        ["x", "lo", "hi"],
        ["t_f64", "t_f64", "t_f64"],
        "t_f64",
        e.ret(k.fmin(k.fmax(e.v("x"), e.v("lo")), e.v("hi"))),
    )
    k.dep(
        x,
        "m_lerp",
        ["a", "b", "t"],
        ["t_f64", "t_f64", "t_f64"],
        "t_f64",
        e.ret(k.add(e.v("a"), k.mul(k.sub(e.v("b"), e.v("a")), e.v("t")))),
    )
    k.dep(
        x,
        "m_hypot",
        ["x", "y"],
        ["t_f64", "t_f64"],
        "t_f64",
        e.ret(k.sqrt(k.add(k.mul(e.v("x"), e.v("x")), k.mul(e.v("y"), e.v("y"))))),
    )
    x.append(e.ret(e.rec(*[p(n, e.v(n)) for n in EXPORTS])))
    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(fn_exports(e, e.v("k"), EXPORTS)))
    return top
