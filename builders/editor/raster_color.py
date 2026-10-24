"""raster-color.atz: how ink mixes, in two swappable models behind one interface (wat target; dependencies, typed with
the ecosystem's libraries).

Wet ink, on the paper or in a bristle, is an `ink_t`, a tuple of four f64 values whose meaning is the model's: RGB
premultiplied linear red, green, blue and coverage, mixing by painting over; Kubelka-Munk (three bands) the pigments'
absorption (K, scattering taken as 1) of red, green and blue summed by concentration, and the amount, so mixed inks
absorb what each absorbs (blue and yellow make green). Paper pixels are four f32 values of the same, in an `f32s`
(editor-types.atz) at a pixel's index (its first value's).

A model is a `color` interface value (iface-wasm.atz: `color_t` owned, `color_raw` borrowed): `rc_model(model)`
makes one (owned) for the model index `model` (0 RGB, 1 Kubelka-Munk; the two implementations are stateless). Its
methods: `ink((lr, lg, lb))` is one unit of ink of a linear RGB color; `deposit((data, i, ink, amount))` puts
`amount` (0..1) of the ink `ink` (an amount-weighted mixture: its fourth value is its amount) on the pixel at `i` of
`data`; `take((data, i, frac, ink))` takes the fraction `frac` of the pixel's ink and is `ink` plus it; `rgb((data,
i))` is the pixel over white paper as linear RGB (`rgb_t`, three f64). Model-free: `rc_mix(dst, src, frac)` is `dst`
moved the fraction `frac` toward `src` (a reservoir refilled); `rc_srgb(c)` encodes a linear value for display
(0..255, rounded), `rc_linear(c)` decodes one; `rc_gradient(stops, n, t)` is the linear RGB color at `t` (0..1) of
`n` evenly spaced sRGB stops (an `f64s` of three values each), interpolated in linear light.
"""

from ..collections import iface_wasm
from ..eco_mb import p
from ..memory import destructor
from . import editor_types
from ..wasm import math_wasm
from ..wasm.kit import Kit, library, stack

FILE = "raster-color.atz"
RGB = 0
KM = 1
# The paper's reflectance (a little below white, so its absorption is finite).
PAPER = 0.97
# The interface's methods: (name, argument type binding, result type binding).
METHODS = [
    ("ink", "rgb_t", "ink_t"),
    ("deposit", "deposit_args_t", "t_void"),
    ("take", "take_args_t", "ink_t"),
    ("rgb", "rgb_args_t", "rgb_t"),
]

TYPE_EXPORTS = ["ink_t", "rgb_t", "color_t", "color_raw"]
EXPORTS = ["rc_model", "rc_mix", "rc_srgb", "rc_linear", "rc_gradient"]


def module(e):
    k = Kit(e)

    def level1(x):
        x.append(e.let("types", e.import_local("types", editor_types.FILE)))
        for n in ["f64s_raw", "f32s_raw"]:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        x.append(e.let("t_pv", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_void"))))
        x.append(e.let("ink_t", k.tuple_t(["t_f64"] * 4)))
        x.append(e.let("rgb_t", k.tuple_t(["t_f64"] * 3)))
        x.append(e.let("deposit_args_t", k.tuple_t(["f32s_raw", "t_i32", "ink_t", "t_f64"])))
        x.append(e.let("take_args_t", k.tuple_t(["f32s_raw", "t_i32", "t_f64", "ink_t"])))
        x.append(e.let("rgb_args_t", k.tuple_t(["f32s_raw", "t_i32"])))
        # a model is stateless: its handle's destroy is nothing
        k.dep(x, "rc_model_destroy", ["m"], ["t_pv"], "t_void", e.seq())
        return [
            "f64s_raw",
            "f32s_raw",
            "t_pv",
            "ink_t",
            "rgb_t",
            "deposit_args_t",
            "take_args_t",
            "rgb_args_t",
            "rc_model_destroy",
        ]

    def level2(x):
        x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
        x.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
        x.append(
            e.let(
                "model_r",
                e.call(
                    e.fld(e.v("destructor"), "type"),
                    e.rec(p("under", e.v("t_pv")), p("destroy", e.v("rc_model_destroy"))),
                ),
            )
        )
        x.append(e.let("model_t", e.fld(e.v("model_r"), "type")))
        x.append(
            e.let(
                "color_r",
                e.call(
                    e.fld(e.v("iface"), "declare"),
                    e.rec(
                        p(
                            "methods",
                            e.rec(*[p(m, e.rec(p("arg", e.v(arg)), p("ret", e.v(ret)))) for m, arg, ret in METHODS]),
                        )
                    ),
                ),
            )
        )
        for f in ["t", "own", "raw"]:
            x.append(e.let("color_" + f, e.fld(e.v("color_r"), "type" if f == "t" else f)))
        return ["model_t", "color_t", "color_own", "color_raw"]

    def level3(x):
        x.append(e.let("math", e.import_local("math", math_wasm.FILE)))
        v = e.v
        f = k.f64

        def M(fn, *args):
            return k.lib("math", fn, *args)

        def ink(*vals):
            return e.mb.as_(e.tup(*vals), k.lo("ink_t"))

        def rgb(*vals):
            return e.mb.as_(e.tup(*vals), k.lo("rgb_t"))

        def fld(tup, i):
            return e.mb.field(tup, e.n(i))

        def px(i):
            """The paper value `i` from the pixel's index (f32), as f64."""
            return k.m(k.m(v("data"), "at", k.add(v("i"), e.n(i))), "to_float", k.lo("t_f64"))

        def set_px(i, val):
            return k.set(k.m(v("data"), "at", k.add(v("i"), e.n(i))), k.m(val, "to_float", k.lo("t_f32")))

        # sRGB decoding and encoding (the standard curve).
        k.dep(
            x,
            "rc_linear",
            ["c"],
            ["t_f64"],
            "t_f64",
            e.seq(
                k.if_(k.le(v("c"), e.n(0.04045)), k.ret(k.div(v("c"), e.n(12.92)))),
                e.ret(M("m_pow", k.div(k.add(v("c"), e.n(0.055)), e.n(1.055)), k.f64(2.4))),
            ),
        )
        k.dep(
            x,
            "rc_srgb",
            ["c"],
            ["t_f64"],
            "t_f64",
            e.seq(
                e.let("cl", M("m_clamp", v("c"), f(0), f(1))),
                e.let(
                    "s",
                    k.ifelse(
                        k.le(v("cl"), e.n(0.0031308)),
                        k.mul(v("cl"), e.n(12.92)),
                        k.sub(k.mul(e.n(1.055), M("m_pow", v("cl"), k.f64(1 / 2.4))), e.n(0.055)),
                    ),
                ),
                e.ret(k.floor(k.add(k.mul(v("s"), e.n(255)), e.n(0.5)))),
            ),
        )

        def ks(r):
            """Kubelka-Munk absorption over scattering of a reflectance (kept within 0.001..0.999)."""
            rr = M("m_clamp", r, f(0.001), f(0.999))
            return k.div(k.mul(k.sub(e.n(1), rr), k.sub(e.n(1), rr)), k.mul(e.n(2), rr))

        # The two models' methods: dependencies over the model handle and the method's argument tuple.
        def method(name, args_t, ret, names, *body_):
            k.dep(
                x,
                name,
                ["self", "args"],
                ["t_pv", args_t],
                ret,
                e.seq(*[e.let(n, e.mb.field(v("args"), e.n(i))) for i, n in enumerate(names)], *body_),
            )

        method("rgb_ink", "rgb_t", "ink_t", ["lr", "lg", "lb"], e.ret(ink(v("lr"), v("lg"), v("lb"), f(1))))
        method("km_ink", "rgb_t", "ink_t", ["lr", "lg", "lb"], e.ret(ink(ks(v("lr")), ks(v("lg")), ks(v("lb")), f(1))))
        # painting over: the ink's color at coverage `amount` over what is there
        method(
            "rgb_deposit",
            "deposit_args_t",
            "t_void",
            ["data", "i", "ink", "amount"],
            e.let("have", fld(v("ink"), 3)),
            k.if_(k.le(v("have"), e.n(1e-12)), k.ret()),
            e.let("a", M("m_clamp", v("amount"), f(0), f(1))),
            *[
                set_px(c, k.add(k.mul(k.div(fld(v("ink"), c), v("have")), v("a")), k.mul(px(c), k.sub(e.n(1), v("a")))))
                for c in range(3)
            ],
            set_px(3, k.add(v("a"), k.mul(px(3), k.sub(e.n(1), v("a"))))),
        )
        # pigment adds to pigment
        method(
            "km_deposit",
            "deposit_args_t",
            "t_void",
            ["data", "i", "ink", "amount"],
            e.let("have", fld(v("ink"), 3)),
            k.if_(k.le(v("have"), e.n(1e-12)), k.ret()),
            *[set_px(c, k.add(px(c), k.mul(k.div(fld(v("ink"), c), v("have")), v("amount")))) for c in range(3)],
            set_px(3, k.add(px(3), v("amount"))),
        )
        # taking is the same in both models: a fraction of each value
        method(
            "rc_take_m",
            "take_args_t",
            "ink_t",
            ["data", "i", "frac", "ink"],
            *[e.let("t%d" % c, k.mul(px(c), v("frac"))) for c in range(4)],
            *[set_px(c, k.sub(px(c), v("t%d" % c))) for c in range(4)],
            e.ret(ink(*[k.add(fld(v("ink"), c), v("t%d" % c)) for c in range(4)])),
        )
        # premultiplied color over white
        method(
            "rgb_rgb",
            "rgb_args_t",
            "rgb_t",
            ["data", "i"],
            e.ret(rgb(*[k.add(px(c), k.sub(e.n(1), px(3))) for c in range(3)])),
        )
        paper_k = ((1 - PAPER) ** 2) / (2 * PAPER)
        method(
            "km_rgb",
            "rgb_args_t",
            "rgb_t",
            ["data", "i"],
            *[e.let("q%d" % c, k.add(e.n(paper_k), px(c))) for c in range(3)],
            e.ret(
                rgb(
                    *[
                        k.sub(
                            k.add(e.n(1), v("q%d" % c)),
                            k.sqrt(k.add(k.mul(v("q%d" % c), v("q%d" % c)), k.mul(e.n(2), v("q%d" % c)))),
                        )
                        for c in range(3)
                    ]
                )
            ),
        )
        k.dep(
            x,
            "rc_mix",
            ["dst", "src", "frac"],
            ["ink_t", "ink_t", "t_f64"],
            "ink_t",
            e.ret(ink(*[M("m_lerp", fld(v("dst"), c), fld(v("src"), c), v("frac")) for c in range(4)])),
        )
        k.dep(
            x,
            "rc_gradient",
            ["stops", "n", "t"],
            ["f64s_raw", "t_i32", "t_f64"],
            "rgb_t",
            e.seq(
                k.if_(
                    k.le(v("n"), e.n(1)),
                    k.ret(rgb(*[k.dcall("rc_linear", k.m(v("stops"), "at", e.n(c))) for c in range(3)])),
                ),
                e.let("pos", k.mul(M("m_clamp", v("t"), f(0), f(1)), k.to_f64(k.sub(v("n"), e.n(1))))),
                e.let("i0", k.trunc(k.fmin(k.floor(v("pos")), k.to_f64(k.sub(v("n"), e.n(2)))))),
                e.let("fr", k.sub(v("pos"), k.to_f64(v("i0")))),
                e.let("a", k.mul(v("i0"), e.n(3))),
                e.let("b", k.add(v("a"), e.n(3))),
                e.ret(
                    rgb(
                        *[
                            M(
                                "m_lerp",
                                k.dcall("rc_linear", k.m(v("stops"), "at", k.add(v("a"), e.n(c)))),
                                k.dcall("rc_linear", k.m(v("stops"), "at", k.add(v("b"), e.n(c)))),
                                v("fr"),
                            )
                            for c in range(3)
                        ]
                    )
                ),
            ),
        )
        return [
            "rgb_ink",
            "km_ink",
            "rgb_deposit",
            "km_deposit",
            "rc_take_m",
            "rgb_rgb",
            "km_rgb",
            "rc_mix",
            "rc_srgb",
            "rc_linear",
            "rc_gradient",
        ]

    def level4(x):
        x.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
        for pre in ["rgb", "km"]:
            x.append(
                e.let(
                    pre + "_up",
                    e.fld(
                        e.call(
                            e.fld(e.v("iface"), "impl"),
                            e.rec(
                                p("iface", e.v("color_t")),
                                p("self", e.v("model_t")),
                                p(
                                    "methods",
                                    e.rec(
                                        p("ink", e.v(pre + "_ink")),
                                        p("deposit", e.v(pre + "_deposit")),
                                        p("take", e.v("rc_take_m")),
                                        p("rgb", e.v(pre + "_rgb")),
                                    ),
                                ),
                            ),
                        ),
                        "upcast",
                    ),
                )
            )
        v = e.v
        k.dep(
            x,
            "rc_model",
            ["model"],
            ["t_i32"],
            "color_t",
            e.ret(
                k.ifelse(
                    k.eq(v("model"), e.n(RGB)),
                    e.mb.as_(k.dcall("rgb_up", k.ptr_of(k.i32(0), "t_pv")), k.lo("color_own")),
                    e.mb.as_(k.dcall("km_up", k.ptr_of(k.i32(0), "t_pv")), k.lo("color_own")),
                )
            ),
        )
        return ["rc_model"]

    x, names = stack(e, k, [level1, level2, level3, level4])
    return library(e, x, TYPE_EXPORTS, EXPORTS)
