"""raster-brush.atz: a brush of bristles painting wet ink along sampled strokes, a job done in slices (wat target;
dependencies, typed with the ecosystem's libraries).

The brush is an owned record (`brush_t`, `brush_own`, `brush_raw`; `brush_new()` makes one with every field 0, owned) of
f64 fields: `radius` (mm, at full pressure), `bristles` (count, up to 1024), `bristle` (a bristle's tip radius, a
fraction of the brush's), `deposit` (the share of a bristle's ink a fully covered pixel takes per dab), `pickup` (the
share of a pixel's wet ink a bristle takes per dab), `reload` (how far a bristle's ink moves toward fresh ink per dab),
`dry_from`, `dry_to` (speeds, mm/s, over which the brush dries out, depositing less), `tilt` (how far tilt pushes the
bristles, in radii), `seed` (the bristles' layout).


A job is an owned record (`job_t`, `job_own`, `job_raw`): `br_new(img, color, brush, stops, nstops, ch_pressure,
ch_speed, ch_tilt_x, ch_tilt_y)` makes one (owned) painting on the image `img` (raster-tiles.atz, borrowed: it
outlives the job) in the color model `color` (raster-color.atz, owned: the job takes it) with the brush `brush` and
the ink colors of the gradient `stops` (an `f64s`, raster-color.atz's `rc_gradient`; both borrowed) over the run;
the `ch_*` are the samples' channel slots (-1: none; pressure 0..1, speed mm/s, tilt in degrees).
`br_stroke(job, samples)` adds a stroke, a vector-spline.atz samples record spaced a dab apart (owned: the job takes
it). `br_start(job)` lays the bristles out and loads them with the gradient's first color; then `br_step(job, dabs)`
paints up to `dabs` dabs and is 1 once every stroke is painted. The run position of a dab is the time painted before
it over the strokes' total time (each stroke's own span, gaps not counted)."""

from ..collections import record_wasm
from ..eco_mb import p
from . import editor_types, raster_color, raster_tiles, vector_spline
from ..wasm import math_wasm
from ..wasm.kit import Kit, library, stack
from .vector_spline import sample_channel_at

FILE = "raster-brush.atz"

BRUSH_FIELDS = ["radius", "bristles", "bristle", "deposit", "pickup", "reload", "dry_from", "dry_to", "tilt", "seed"]
BRISTLE_COLUMNS = ["ox", "oy", "len", "r0", "r1", "r2", "r3"]

TYPE_EXPORTS = ["brush_t", "brush_own", "brush_raw", "job_t", "job_own", "job_raw"]
EXPORTS = ["brush_new", "br_new", "br_stroke", "br_start", "br_step"]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("color", e.import_local("color", raster_color.FILE)))
    x.append(e.let("tiles", e.import_local("tiles", raster_tiles.FILE)))
    x.append(e.let("spline", e.import_local("spline", vector_spline.FILE)))


def _record(e, x, name, fields):
    x.append(
        e.let(
            name + "_r",
            e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in fields])))),
        )
    )
    for f in ["t", "own", "raw"]:
        x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    x.append(e.let(name + "_make", e.fld(e.v(name + "_r"), "new")))
    return [name + "_" + f for f in ["t", "own", "raw", "make"]]


def module(e):
    k = Kit(e)
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]
    outer_types = ["ink_t", "rgb_t", "color_t", "img_raw", "samples_t", "samples_own", "samples_raw"]

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        x.append(e.let("ink_t", e.fld(e.v("color"), "ink_t")))
        x.append(e.let("rgb_t", e.fld(e.v("color"), "rgb_t")))
        x.append(e.let("color_t", e.fld(e.v("color"), "color_t")))
        x.append(e.let("img_raw", e.fld(e.v("tiles"), "img_raw")))
        for n in ["samples_t", "samples_own", "samples_raw"]:
            x.append(e.let(n, e.fld(e.v("spline"), n)))
        return type_names + outer_types

    def level2(x):
        _imports(e, x)
        names = []
        names += _record(e, x, "brush", [(f, "t_f64") for f in BRUSH_FIELDS])
        names += _record(e, x, "bristles", [(c, "f64s_t") for c in BRISTLE_COLUMNS])
        x.append(e.let("strokes_r", e.call(e.fld(e.v("vec"), "type"), e.v("samples_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("strokes_" + f, e.fld(e.v("strokes_r"), "type" if f == "t" else f)))
        return names + ["strokes_" + f for f in ["t", "own", "raw", "new"]]

    def level3(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "job",
            [
                ("img", "img_raw"),
                ("color", "color_t"),
                ("brush", "brush_raw"),
                ("stops", "f64s_raw"),
                ("nstops", "t_i32"),
                ("strokes", "strokes_t"),
                ("bristles", "bristles_t"),
                ("ch_p", "t_i32"),
                ("ch_v", "t_i32"),
                ("ch_tx", "t_i32"),
                ("ch_ty", "t_i32"),
                ("si", "t_i32"),
                ("ki", "t_i32"),
                ("f0", "t_f64"),
                ("f1", "t_f64"),
                ("f2", "t_f64"),
                ("f3", "t_f64"),
                ("total", "t_f64"),
                ("before", "t_f64"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(e.let("math", e.import_local("math", math_wasm.FILE)))
    x.append(e.let("color", e.import_local("color", raster_color.FILE)))
    x.append(e.let("tiles", e.import_local("tiles", raster_tiles.FILE)))
    v = e.v
    f = k.f64

    def M(fn, *args):
        return k.lib("math", fn, *args)

    def C(fn, *args):
        return k.lib("color", fn, *args)

    def T(fn, *args):
        return k.lib("tiles", fn, *args)

    def j(name):
        return e.fld(v("job"), name)

    def b(name):
        return e.fld(j("brush"), name)

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def setv(name, val):
        return e.mb.set(v(name), val)

    def col(rec, name):
        return e.fld(rec, name)

    def at(rec, name, i):
        return k.m(col(rec, name), "at", i)

    def fld(tup, i):
        return e.mb.field(tup, e.n(i))

    def ink(*vals):
        return e.mb.as_(e.tup(*vals), k.lo("ink_t"))

    def fresh():
        return ink(*[j("f%d" % c) for c in range(4)])

    def chan(smp, i, slot, default):
        """Sample `i`'s channel in the slot `slot` (an i32, -1: none), else `default`."""
        return k.ifelse(k.lt(slot, e.n(0)), f(default), sample_channel_at(k, e, smp, i, slot))

    k.dep(
        x,
        "brush_new",
        [],
        [],
        "brush_t",
        e.ret(k.call("brush_make", e.rec(*[p(name, f(0)) for name in BRUSH_FIELDS]))),
    )
    k.dep(
        x,
        "br_new",
        ["img", "color", "brush", "stops", "nstops", "cp", "cv", "ctx", "cty"],
        ["img_raw", "color_t", "brush_raw", "f64s_raw", "t_i32"] + ["t_i32"] * 4,
        "job_t",
        e.ret(
            k.call(
                "job_make",
                e.rec(
                    p("img", v("img")),
                    p("color", k.m(v("color"), "move", e.tup())),
                    p("brush", v("brush")),
                    p("stops", v("stops")),
                    p("nstops", v("nstops")),
                    p("strokes", k.call("strokes_new", e.tup())),
                    p(
                        "bristles",
                        k.call("bristles_make", e.rec(*[p(c, k.call("f64s_new", e.tup())) for c in BRISTLE_COLUMNS])),
                    ),
                    p("ch_p", v("cp")),
                    p("ch_v", v("cv")),
                    p("ch_tx", v("ctx")),
                    p("ch_ty", v("cty")),
                    p("si", k.i32(0)),
                    p("ki", k.i32(0)),
                    *[p("f%d" % c, f(0)) for c in range(4)],
                    p("total", f(0)),
                    p("before", f(0)),
                ),
            )
        ),
    )
    k.dep(
        x,
        "br_stroke",
        ["job", "samples"],
        ["job_raw", "samples_t"],
        "t_void",
        e.seq(
            e.let("n", e.mb.as_(e.fld(col(v("samples"), "t"), "len"), k.lo("t_i32"))),
            k.if_(
                k.gt(v("n"), e.n(1)),
                k.set(
                    j("total"),
                    k.add(
                        j("total"), k.sub(at(v("samples"), "t", k.sub(v("n"), e.n(1))), at(v("samples"), "t", e.n(0)))
                    ),
                ),
            ),
            k.m(j("strokes"), "push", k.m(v("samples"), "move", e.tup())),
        ),
    )

    # The fresh ink at run position `t` (0..1) into the job's `f0`..`f3`.
    k.dep(
        x,
        "br_fresh",
        ["job", "t"],
        ["job_raw", "t_f64"],
        "t_void",
        e.seq(
            e.let("rgb", C("rc_gradient", j("stops"), j("nstops"), v("t"))),
            e.let("nk", k.m(j("color"), "ink", v("rgb"))),
            *[k.set(j("f%d" % c), fld(v("nk"), c)) for c in range(4)],
        ),
    )

    def rand():
        """The next value of the layout's generator in [0, 1) (a 32-bit LCG in the i32 `state`)."""
        return e.seq(
            setv("state", k.add(k.mul(v("state"), e.n(1664525)), e.n(1013904223))),
            e.ret(k.div(k.m(k.ushr(v("state"), e.n(8)), "to_float", k.lo("t_f64")), e.n(16777216))),
        )

    k.dep(
        x,
        "br_start",
        ["job"],
        ["job_raw"],
        "t_void",
        e.seq(
            k.set(j("si"), e.n(0)),
            k.set(j("ki"), e.n(0)),
            k.set(j("before"), f(0)),
            e.let("brs", raw(j("bristles"), "bristles")),
            *[k.m(col(v("brs"), c), "clear", e.tup()) for c in BRISTLE_COLUMNS],
            k.dcall("br_fresh", v("job"), f(0)),
            e.let("state", k.trunc(b("seed"))),
            e.let("count", k.trunc(M("m_clamp", b("bristles"), f(1), f(1024)))),
            k.for_(
                "i",
                0,
                v("count"),
                "lay",
                # a point of the unit disk, by rejection
                k.loop(
                    "disk",
                    e.let("ux", k.sub(k.mul(rand(), e.n(2)), e.n(1))),
                    e.let("uy", k.sub(k.mul(rand(), e.n(2)), e.n(1))),
                    k.if_(
                        k.le(k.add(k.mul(v("ux"), v("ux")), k.mul(v("uy"), v("uy"))), e.n(1)),
                        k.m(col(v("brs"), "ox"), "push", v("ux")),
                        k.m(col(v("brs"), "oy"), "push", v("uy")),
                        k.brk("disk"),
                    ),
                ),
                k.m(col(v("brs"), "len"), "push", k.add(e.n(0.5), k.mul(e.n(0.5), rand()))),
                *[k.m(col(v("brs"), "r%d" % c), "push", j("f%d" % c)) for c in range(4)],
            ),
        ),
    )
    # One dab of every bristle at sample `i` of the stroke `smp` (its t0 the stroke's first time).
    k.dep(
        x,
        "br_dab",
        ["job", "smp", "i", "t0"],
        ["job_raw", "samples_raw", "t_i32", "t_f64"],
        "t_void",
        e.seq(
            e.let("img", j("img")),
            e.let("data", raw(e.fld(v("img"), "data"), "f32s")),
            e.let("mmpp", e.fld(v("img"), "mmpp")),
            e.let("w", e.fld(v("img"), "w")),
            e.let("h", e.fld(v("img"), "h")),
            e.let("pr", M("m_clamp", chan(v("smp"), v("i"), j("ch_p"), 1.0), f(0), f(1))),
            e.let("speed", chan(v("smp"), v("i"), j("ch_v"), 0.0)),
            e.let("tlx", k.div(chan(v("smp"), v("i"), j("ch_tx"), 0.0), e.n(90))),
            e.let("tly", k.div(chan(v("smp"), v("i"), j("ch_ty"), 0.0), e.n(90))),
            e.let(
                "dry",
                M(
                    "m_clamp",
                    k.div(k.sub(v("speed"), b("dry_from")), k.fmax(k.sub(b("dry_to"), b("dry_from")), e.n(1e-6))),
                    f(0),
                    f(0.85),
                ),
            ),
            # the run position and the fresh ink there
            e.let(
                "run",
                k.ifelse(
                    k.gt(j("total"), e.n(0)),
                    k.div(k.add(j("before"), k.sub(at(v("smp"), "t", v("i")), v("t0"))), j("total")),
                    f(0),
                ),
            ),
            k.dcall("br_fresh", v("job"), v("run")),
            # the brush in pixels: its contact radius grows with pressure
            e.let("rad", k.div(k.mul(b("radius"), k.add(e.n(0.3), k.mul(e.n(0.7), v("pr")))), v("mmpp"))),
            e.let("cx", k.div(k.sub(at(v("smp"), "x", v("i")), e.fld(v("img"), "x0")), v("mmpp"))),
            e.let("cy", k.div(k.sub(at(v("smp"), "y", v("i")), e.fld(v("img"), "y0")), v("mmpp"))),
            e.let("ax", at(v("smp"), "tx", v("i"))),
            e.let("ay", at(v("smp"), "ty", v("i"))),
            e.let(
                "rb", k.fmax(k.mul(k.mul(b("bristle"), v("rad")), k.add(e.n(0.6), k.mul(e.n(0.6), v("pr")))), e.n(0.5))
            ),
            e.let("brs", raw(j("bristles"), "bristles")),
            k.for_(
                "q",
                0,
                e.fld(col(v("brs"), "ox"), "len"),
                "bristles",
                # the longer bristles touch first; more touch as the brush is pressed
                k.if_(k.lt(at(v("brs"), "len", v("q")), k.sub(e.n(1), k.mul(v("pr"), e.n(1.2)))), k.cont("bristles")),
                # flattened along the stroke, pushed by the tilt (the shorter bristles more)
                e.let("along", k.mul(at(v("brs"), "ox", v("q")), e.n(0.6))),
                e.let("across", at(v("brs"), "oy", v("q"))),
                e.let("lean", k.mul(k.mul(b("tilt"), v("rad")), k.sub(e.n(1.5), at(v("brs"), "len", v("q"))))),
                e.let(
                    "bx",
                    k.add(
                        k.add(v("cx"), k.mul(k.sub(k.mul(v("along"), v("ax")), k.mul(v("across"), v("ay"))), v("rad"))),
                        k.mul(v("tlx"), v("lean")),
                    ),
                ),
                e.let(
                    "by",
                    k.add(
                        k.add(v("cy"), k.mul(k.add(k.mul(v("along"), v("ay")), k.mul(v("across"), v("ax"))), v("rad"))),
                        k.mul(v("tly"), v("lean")),
                    ),
                ),
                e.let("x0", k.trunc(k.fmax(k.floor(k.sub(v("bx"), k.add(v("rb"), e.n(1)))), e.n(0)))),
                e.let("y0", k.trunc(k.fmax(k.floor(k.sub(v("by"), k.add(v("rb"), e.n(1)))), e.n(0)))),
                e.let(
                    "x1",
                    k.trunc(k.fmin(k.ceil(k.add(v("bx"), k.add(v("rb"), e.n(1)))), k.to_f64(k.sub(v("w"), e.n(1))))),
                ),
                e.let(
                    "y1",
                    k.trunc(k.fmin(k.ceil(k.add(v("by"), k.add(v("rb"), e.n(1)))), k.to_f64(k.sub(v("h"), e.n(1))))),
                ),
                k.if_(k.or_(k.gt(v("x0"), v("x1")), k.gt(v("y0"), v("y1"))), k.cont("bristles")),
                # the bristle's ink, a tuple updated through the dab
                e.let("res", ink(*[at(v("brs"), "r%d" % c, v("q")) for c in range(4)])),
                k.for_(
                    "py",
                    v("y0"),
                    k.add(v("y1"), e.n(1)),
                    "rows",
                    k.for_(
                        "px",
                        v("x0"),
                        k.add(v("x1"), e.n(1)),
                        "cols",
                        e.let(
                            "dist",
                            M(
                                "m_hypot",
                                k.sub(k.add(k.to_f64(v("px")), e.n(0.5)), v("bx")),
                                k.sub(k.add(k.to_f64(v("py")), e.n(0.5)), v("by")),
                            ),
                        ),
                        e.let("cov", M("m_clamp", k.sub(k.add(v("rb"), e.n(0.5)), v("dist")), f(0), f(1))),
                        k.if_(k.le(v("cov"), e.n(0)), k.cont("cols")),
                        e.let("pa", T("rt_px", v("img"), v("px"), v("py"))),
                        # the bristle takes up some of the wet ink there, then lays some of its own
                        setv(
                            "res",
                            k.m(j("color"), "take", e.tup(v("data"), v("pa"), k.mul(b("pickup"), v("cov")), v("res"))),
                        ),
                        e.let("have", fld(v("res"), 3)),
                        e.let(
                            "amount",
                            k.fmin(
                                k.mul(k.mul(k.mul(b("deposit"), v("cov")), k.sub(e.n(1), v("dry"))), v("have")),
                                v("have"),
                            ),
                        ),
                        k.m(j("color"), "deposit", e.tup(v("data"), v("pa"), v("res"), v("amount"))),
                        k.if_(
                            k.gt(v("have"), e.n(1e-12)),
                            e.let("keepf", k.sub(e.n(1), k.div(v("amount"), v("have")))),
                            setv("res", ink(*[k.mul(fld(v("res"), c), v("keepf")) for c in range(4)])),
                        ),
                    ),
                ),
                T("rt_mark", v("img"), v("x0"), v("y0"), v("x1"), v("y1")),
                # the bristle soaks up fresh ink
                setv("res", C("rc_mix", v("res"), fresh(), b("reload"))),
                *[k.set(at(v("brs"), "r%d" % c, v("q")), fld(v("res"), c)) for c in range(4)],
            ),
        ),
    )
    k.dep(
        x,
        "br_step",
        ["job", "dabs"],
        ["job_raw", "t_i32"],
        "t_i32",
        e.seq(
            e.let("left", v("dabs")),
            e.let("strokes", raw(j("strokes"), "strokes")),
            k.loop(
                "work",
                k.if_(k.ge(j("si"), e.fld(v("strokes"), "len")), k.ret(k.i32(1))),
                k.if_(k.le(v("left"), e.n(0)), k.ret(k.i32(0))),
                e.let("samples", raw(k.m(v("strokes"), "at", j("si")), "samples")),
                e.let("n", e.mb.as_(e.fld(col(v("samples"), "t"), "len"), k.lo("t_i32"))),
                k.if_(
                    k.ge(j("ki"), v("n")),
                    # the stroke is done: its time counts toward the run
                    k.if_(
                        k.gt(v("n"), e.n(1)),
                        k.set(
                            j("before"),
                            k.add(
                                j("before"),
                                k.sub(at(v("samples"), "t", k.sub(v("n"), e.n(1))), at(v("samples"), "t", e.n(0))),
                            ),
                        ),
                    ),
                    k.set(j("si"), k.add(j("si"), e.n(1))),
                    k.set(j("ki"), e.n(0)),
                    k.cont("work"),
                ),
                k.dcall("br_dab", v("job"), v("samples"), j("ki"), at(v("samples"), "t", e.n(0))),
                k.set(j("ki"), k.add(j("ki"), e.n(1))),
                setv("left", k.sub(v("left"), e.n(1))),
            ),
            e.ret(k.i32(0)),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
