"""vector-spline-test.atz: a WASI app checking vector-spline.atz: every geometry through (or, B-spline, near) its
nodes, the natural and Hobby splines smooth across nodes (Hobby's handles against reference values), arc lengths,
even sampling with channel interpolation, node insertion and removal, and fitting a recorded quarter circle; it
prints the index of the first failed check (exit status 1)."""

import math

from ..wasm import math_wasm
from . import wasi_test, vector_spline
from .vector_spline import sample_channel_at, track_channel_at

# A quarter circle of radius 50 mm recorded at 100 samples a second over a second: t, x, y, pressure.
RAW = [
    (i * 10.0, 50 * math.cos(math.pi / 2 * i / 100), 50 * math.sin(math.pi / 2 * i / 100), i / 100) for i in range(101)
]


def module(e):
    def checks(k):
        v = e.v

        def S(f, *args):
            return k.lib("spline", f, *args)

        def near(a, b, tol):
            return k.le(k.fabs(k.sub(a, b)), e.n(tol))

        def col(rec, name, i):
            return k.m(e.fld(rec, name), "at", i)

        def nd(sp, i):
            """Node `i` of the spline `sp` (raw)."""
            return e.mb.as_(k.m(e.fld(sp, "nodes"), "at", i), e.lower(e.fld(e.v("spline"), "node_raw")))

        def nat(sp, name, i):
            return e.fld(nd(sp, i), name)

        def chan(sp, i, c):
            return k.m(e.fld(nd(sp, i), "c"), "at", c)

        def chani(sp, i, c):
            return k.m(e.fld(nd(sp, i), "ci"), "at", c)

        def count(rec, name="x"):
            return e.fld(e.fld(rec, name), "len")

        def pt(i, u):
            """Statements binding `pt` to the point of segment `i` at `u`."""
            return [e.let("pt", S("sp_point", v("segs"), e.n(i), k.f64(u)))]

        def ptf(j):
            return e.mb.field(v("pt"), e.n(j))

        def nodes(name, pts, geom, values):
            out = [e.let(name, S("sp_new", e.n(1)))]
            for (x, y), val in zip(pts, values):
                out += [
                    e.let("ni", S("sp_push", v(name))),
                    k.set(nat(v(name), "x", v("ni")), k.f64(x)),
                    k.set(nat(v(name), "y", v("ni")), k.f64(y)),
                    k.set(nat(v(name), "geom", v("ni")), k.i32(geom)),
                    k.set(chan(v(name), v("ni"), e.n(0)), k.f64(val)),
                    k.set(chani(v(name), v("ni"), e.n(0)), k.i32(1)),
                ]
            return out

        pts = [(0, 0), (10, 0), (10, 10), (0, 10), (-5, 5)]
        out = [e.let("segs", S("segs_new"))]
        # interpolating geometries pass through the nodes at the segments' ends
        for geom in [0, 1, 4, 5]:
            out += nodes("g%d" % geom, pts, geom, [0, 1, 2, 3, 4])
            out += [S("sp_prepare", v("g%d" % geom), v("segs")), k.check(k.eq(count(v("segs"), "x0"), e.n(4)))]
            for i in range(4):
                out += [
                    *pt(i, 1),
                    k.check(near(ptf(0), e.n(pts[i + 1][0]), 1e-9)),
                    k.check(near(ptf(1), e.n(pts[i + 1][1]), 1e-9)),
                ]
        # a line's length is its chord; the natural spline is smooth: its tangent continues across a node
        out += [
            S("sp_prepare", v("g0"), v("segs")),
            k.check(near(S("sp_length", v("segs")), e.n(10 + 10 + 10 + math.hypot(5, 5)), 1e-9)),
        ]
        out += [
            S("sp_prepare", v("g4"), v("segs")),
            *pt(1, 1),
            e.let("tx", ptf(2)),
            e.let("ty", ptf(3)),
            *pt(2, 0),
            k.check(near(ptf(2), v("tx"), 1e-9)),
            k.check(near(ptf(3), v("ty"), 1e-9)),
        ]
        # Hobby's spline is smooth across a node too, and its third segment's handles are MetaPost's (a reference
        # implementation of the same equations)
        out += [
            S("sp_prepare", v("g5"), v("segs")),
            *pt(1, 1),
            e.let("hx", ptf(2)),
            e.let("hy", ptf(3)),
            *pt(2, 0),
            k.check(near(ptf(2), v("hx"), 1e-9)),
            k.check(near(ptf(3), v("hy"), 1e-9)),
            *[
                k.check(near(col(v("segs"), field, e.n(2)), e.n(want), 1e-9))
                for field, want in [
                    ("x1", 7.26168544900934),
                    ("y1", 12.388223340350548),
                    ("x2", 3.2210275258485326),
                    ("y2", 11.910649090507773),
                ]
            ],
        ]
        # the B-spline's segment starts at (a + 4b + c) / 6
        out += nodes("g3", pts, 3, [0, 0, 0, 0, 0])
        out += [
            S("sp_prepare", v("g3"), v("segs")),
            *pt(1, 0),
            k.check(near(ptf(0), e.n((0 + 4 * 10 + 10) / 6), 1e-9)),
            k.check(near(ptf(1), e.n((0 + 0 + 10) / 6), 1e-9)),
        ]
        # sampling a line every 1 mm: 36 samples plus the end, the channel linear over each segment
        out += [
            S("sp_prepare", v("g0"), v("segs")),
            e.let("smp", S("samples_new")),
            S("sp_sample", v("g0"), v("segs"), k.f64(1), v("smp")),
            k.check(k.eq(count(v("smp")), e.n(30 + int(math.hypot(5, 5)) + 2))),
            k.check(near(col(v("smp"), "x", e.n(5)), e.n(5), 1e-6)),
            k.check(near(sample_channel_at(k, e, v("smp"), e.n(5), e.n(0)), e.n(0.5), 1e-6)),
            k.check(near(col(v("smp"), "s", e.n(5)), e.n(5), 1e-9)),
            k.check(k.eq(col(v("smp"), "seg", e.n(5)), e.n(0))),
        ]
        # inserting a node shifts the ones after it (and their channels); removing it restores them
        out += [
            S("sp_insert", v("g0"), e.n(1)),
            k.check(k.eq(S("sp_count", v("g0")), e.n(6))),
            k.check(near(nat(v("g0"), "x", e.n(1)), e.n(0), 1e-9)),
            k.check(near(nat(v("g0"), "x", e.n(2)), e.n(10), 1e-9)),
            k.check(near(chan(v("g0"), e.n(2), e.n(0)), e.n(1), 1e-9)),
            k.check(k.eq(chani(v("g0"), e.n(2), e.n(0)), e.n(1))),
            S("sp_remove", v("g0"), e.n(1)),
            k.check(k.eq(S("sp_count", v("g0")), e.n(5))),
            k.check(near(nat(v("g0"), "x", e.n(1)), e.n(10), 1e-9)),
            k.check(near(chan(v("g0"), e.n(1), e.n(0)), e.n(1), 1e-9)),
            k.check(k.eq(S("sp_nearest_node", v("g0"), k.f64(9), k.f64(9)), e.n(2))),
            e.let("ns", S("sp_nearest_seg", v("segs"), k.f64(5), k.f64(-1))),
            k.check(k.eq(e.mb.field(v("ns"), e.n(0)), e.n(0))),
            k.check(near(e.mb.field(v("ns"), e.n(1)), e.n(0.5), 1e-9)),
        ]
        # fitting the quarter circle: few nodes, ends near the ends, the curve near the circle, pressure kept and the
        # speed (channel 1, computed into the track: a quarter of a 100 mm circle per second)
        out.append(e.let("track", S("track_new")))
        for i, (t, x, y, pr) in enumerate(RAW):
            if i == 0:
                speed = 0
            else:
                tp, xp, yp, _ = RAW[i - 1]
                speed = math.hypot(x - xp, y - yp) * 1000 / (t - tp)
            if i == 0:
                speed = math.hypot(RAW[1][1] - x, RAW[1][2] - y) * 1000 / (RAW[1][0] - t)
            out += [
                k.m(e.fld(v("track"), "t"), "push", k.f64(t)),
                k.m(e.fld(v("track"), "x"), "push", k.f64(x)),
                k.m(e.fld(v("track"), "y"), "push", k.f64(y)),
                *[
                    k.m(e.fld(v("track"), "c"), "push", k.f64(val))
                    for val in [pr, speed] + [0] * (vector_spline.CHANNELS - 2)
                ],
            ]
        out += [
            e.let("fit", S("sp_new", e.n(2))),
            S("sp_fit", v("track"), e.n(2), k.f64(0.5), v("fit")),
            k.check(k.ge(S("sp_count", v("fit")), e.n(3))),
            k.check(k.le(S("sp_count", v("fit")), e.n(20))),
            k.check(near(nat(v("fit"), "x", e.n(0)), e.n(50), 1.0)),
            k.check(near(nat(v("fit"), "y", e.n(0)), e.n(0), 1.0)),
            S("sp_prepare", v("fit"), v("segs")),
            k.check(near(S("sp_length", v("segs")), e.n(math.pi * 25), 2.0)),
            S("sp_sample", v("fit"), v("segs"), k.f64(2), v("smp")),
            e.let("worst", k.f64(0)),
            k.for_(
                "i",
                0,
                count(v("smp")),
                "circle",
                e.let(
                    "off",
                    k.fabs(
                        k.sub(k.lib("math", "m_hypot", col(v("smp"), "x", v("i")), col(v("smp"), "y", v("i"))), e.n(50))
                    ),
                ),
                k.if_(k.gt(v("off"), v("worst")), e.mb.set(v("worst"), v("off"))),
            ),
            k.check(k.lt(v("worst"), e.n(0.3))),
            e.let("mid", k.div(e.mb.as_(count(v("smp")), k.lo("t_i32")), e.n(2))),
            k.check(near(sample_channel_at(k, e, v("smp"), v("mid"), e.n(0)), e.n(0.5), 0.1)),
            k.check(near(sample_channel_at(k, e, v("smp"), v("mid"), e.n(1)), e.n(math.pi * 25), 3.0)),
            k.check(near(track_channel_at(k, e, v("track"), e.n(50), e.n(0)), e.n(0.5), 1e-9)),
        ]
        return out

    return wasi_test.module(e, [("math", math_wasm.FILE), ("spline", vector_spline.FILE)], checks)
