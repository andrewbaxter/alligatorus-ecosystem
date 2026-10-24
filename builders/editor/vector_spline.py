"""vector-spline.atz: splines with per-node parameters, shared by the spline editor and the rasterizer so both get the
same curve (wat target; dependencies, typed with the ecosystem's libraries).

A spline is an owned record (`spline_t`, `spline_own`, `spline_raw`; `sp_new(nch)` makes an empty one with `nch`
channels, owned) of its channel count `nch` and its `nodes`, a vec of node records (`node_t`, `node_raw`;
`sp_node(sp, i)`, raw): the position `x`, `y`; the Bézier handles relative to the node, in (`hix`, `hiy`) and out
(`hox`, `hoy`); the time `t` (ms); `geom`, the geometry of the segment to the next node (the enumeration `geom`,
enum-wasm.atz: `geom_t`, constants `geom.line`...); and per channel the channel's value (`c`, an `f64s` of `nch`)
and the interpolation of the channel over the segment to the next node (`ci`, a vec of the enumeration `interp`,
`interp_t`; `channel_at`, `interp_at` in the builders). `sp_geom_of(i)`/`sp_geom_index(g)` and
`sp_interp_of(i)`/`sp_interp_index(m)` convert between the enumerations and their indices (a document's). `sp_count(sp)` is the node count; `sp_push(sp)`,
`sp_insert(sp, i)` add a zeroed node (at the end, at `i`), `sp_remove(sp, i)` takes one out, `sp_clear(sp)` all, and
`sp_copy(dst, src)` makes `dst` a copy of `src` (its channel count too).


Geometry, chosen per segment: `line`; `catmull`, centripetal Catmull-Rom (through the nodes, from the neighbors);
`bezier` (the handles); `bspline`, uniform cubic B-spline (the nodes are control points: the curve passes near them);
`natural` (the C2 cubic through a run of such segments that minimizes bending, chord-length parameterized,
handle-less); `hobby` (the METAFONT/MetaPost spline through a run of such segments: tension 1, curl 1 ends,
handle-less). Every segment
compiles to one cubic Bézier: `sp_prepare(sp, segs)` fills the segments record `segs` (`segs_t`; `segs_new()`) with
the four control points (`x0`..`y3` columns) and the arc length table (`l`, `SUBDIV + 1` entries per segment) of the
spline's segments. Channel interpolation, chosen per segment and channel: `step`, `linear`, `smooth` (smoothstep),
`catmull` (uniform Catmull-Rom, from the neighbors' values).

Evaluation: `sp_point(segs, i, u)` is the position and unit tangent `(x, y, tx, ty)` (`pt_t`, a tuple) at parameter
`u` of segment `i`; `sp_length(segs)` is the total arc length; `sp_sample(sp, segs, spacing, out)` fills the samples
record `out` (`samples_t`; `samples_new()`: columns `x`, `y`, `tx`, `ty`, `s` the arc length, `seg`, `u`, `t` and
the channel values `c`, `CHANNELS` per sample) with a sample every `spacing` along the curve (and at its end).
`sp_channel(sp, i, u, c)` is channel `c` at `u` of segment `i`.

Fitting: a recorded track is a record (`track_t`; `track_new()`) of columns per sample: the time `t` (ms), `x`,
`y` (mm) and the channel values `c` (`CHANNELS` per sample; `track_channel_at`). `sp_speeds(xs, ys, ts, out)` gives
a stroke's speeds (mm/s) per sample, for a track's speed channel. `sp_fit(track, nch, amount, out)`
makes the nodes of the track's first `nch` channels: the samples are smoothed with a Gaussian of `amount` mm along
the track, then simplified (Ramer-Douglas-Peucker, tolerance a quarter of `amount`, at least 0.05 mm) to the nodes of
`out` (emptied), centripetal Catmull-Rom segments with linear channels whose handles hold the Catmull-Rom tangents.

Editing: `sp_nearest_node(sp, x, y)` is the node nearest a point (-1 for none) and `sp_nearest_seg(segs, x, y)` the
segment nearest it and the parameter there, `(i, u)` (`near_t`, a tuple; -1 for none).
"""

from ..collections import record_wasm
from ..eco_mb import p
from . import editor_types
from ..wasm import math_wasm
from ..target_mb import fn_of
from ..wasm.kit import Kit, library, stack

FILE = "vector-spline.atz"

# The samples' and tracks' channel slots (a node has as many channels as its spline).
CHANNELS = 8
# The arc length table: lengths at SUBDIV + 1 evenly spaced parameters.
SUBDIV = 32
NODE_COLUMNS = ["x", "y", "hix", "hiy", "hox", "hoy", "t"]
CTRL_COLUMNS = ["x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3"]
SAMPLE_COLUMNS = ["x", "y", "tx", "ty", "s", "u", "t"]

# The geometries of a segment (enum-wasm.atz `geom`) and the interpolations of a channel over one (`interp`), in
# the order their indices (the document's, the editor's dropdowns') count.
GEOMS = ["line", "catmull", "bezier", "bspline", "natural", "hobby"]
SQRT2 = 2**0.5
# Hobby's velocity denominator coefficients: (sqrt 5 - 1) / 2 and (3 - sqrt 5) / 2.
HOBBY_A = (5**0.5 - 1) / 2
HOBBY_B = (3 - 5**0.5) / 2
INTERPS = ["step", "linear", "smooth", "catmull"]

TYPE_EXPORTS = [pre + "_" + f for pre in ["spline", "segs", "samples", "track"] for f in ["t", "own", "raw"]] + [
    "node_t",
    "node_raw",
    "geom",
    "geom_t",
    "interp",
    "interp_t",
    "pt_t",
    "near_t",
]
EXPORTS = [
    "sp_new",
    "sp_count",
    "sp_node",
    "sp_geom_of",
    "sp_geom_index",
    "sp_interp_of",
    "sp_interp_index",
    "sp_speeds",
    "sp_push",
    "sp_insert",
    "sp_remove",
    "sp_clear",
    "sp_copy",
    "segs_new",
    "samples_new",
    "track_new",
    "sp_prepare",
    "sp_point",
    "sp_length",
    "sp_channel",
    "sp_sample",
    "sp_fit",
    "sp_nearest_node",
    "sp_nearest_seg",
]


def node_at(k, e, sp, i, node_raw):
    """Builders: node `i` of the spline `sp` (a raw record), raw (`node_raw`: the raw node type, lowered)."""
    return e.mb.as_(k.m(e.fld(sp, "nodes"), "at", i), node_raw)


def channel_at(k, e, sp, i, c, node_raw):
    """Builders: the place of channel `c` of node `i` of the spline `sp` (a raw record)."""
    return k.m(e.fld(node_at(k, e, sp, i, node_raw), "c"), "at", c)


def interp_at(k, e, sp, i, c, node_raw):
    """Builders: the place of the interpolation of channel `c` over the segment from node `i`."""
    return k.m(e.fld(node_at(k, e, sp, i, node_raw), "ci"), "at", c)


def sample_channel_at(k, e, out, j, c):
    """Builders: the place of channel `c` of sample `j` of the samples record `out` (and of a track)."""
    return k.m(e.fld(out, "c"), "at", k.add(k.mul(j, e.n(CHANNELS)), c))


track_channel_at = sample_channel_at


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("enum", e.import_local("enum", "enum-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))


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

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        x.append(e.let("pt_t", k.tuple_t(["t_f64"] * 4)))
        x.append(e.let("near_t", k.tuple_t(["t_i32", "t_f64"])))
        names = type_names + ["pt_t", "near_t"]
        for name, variants in [("geom", GEOMS), ("interp", INTERPS)]:
            x.append(e.let(name, e.call(e.fld(e.v("enum"), "type"), e.tup(*[e.s(n) for n in variants]))))
            x.append(e.let(name + "_t", e.fld(e.v(name), "type")))
            for n in variants:
                x.append(e.let(name + "_" + n, e.fld(e.v(name), n)))
            names += [name, name + "_t"] + [name + "_" + n for n in variants]
        return names

    def level2(x):
        _imports(e, x)
        x.append(e.let("interps_r", e.call(e.fld(e.v("vec"), "type"), e.v("interp_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("interps_" + f, e.fld(e.v("interps_r"), "type" if f == "t" else f)))
        return ["interps_" + f for f in ["t", "own", "raw", "new"]]

    def level2b(x):
        _imports(e, x)
        names = []
        names += _record(
            e,
            x,
            "node",
            [(c, "t_f64") for c in NODE_COLUMNS] + [("geom", "geom_t"), ("c", "f64s_t"), ("ci", "interps_t")],
        )
        names += _record(e, x, "segs", [(c, "f64s_t") for c in CTRL_COLUMNS] + [("l", "f64s_t")])
        names += _record(
            e, x, "samples", [(c, "f64s_t") for c in SAMPLE_COLUMNS] + [("seg", "ints_t"), ("c", "f64s_t")]
        )
        names += _record(e, x, "track", [(c, "f64s_t") for c in ["t", "x", "y", "c"]])
        return names

    def level3(x):
        _imports(e, x)
        x.append(e.let("nodes_r", e.call(e.fld(e.v("vec"), "type"), e.v("node_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("nodes_" + f, e.fld(e.v("nodes_r"), "type" if f == "t" else f)))
        return ["nodes_" + f for f in ["t", "own", "raw", "new"]]

    def level4(x):
        _imports(e, x)
        return _record(e, x, "spline", [("nodes", "nodes_t"), ("nch", "t_i32")])

    x, names = stack(e, k, [level1, level2, level2b, level3, level4])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(e.let("math", e.import_local("math", math_wasm.FILE)))
    v = e.v
    f = k.f64

    def M(fn, *args):
        return k.lib("math", fn, *args)

    def T(fn, *args):
        return k.lib("types", fn, *args)

    def setv(name, val):
        return e.mb.set(v(name), val)

    def col(rec, name):
        return e.fld(rec, name)

    def at(rec, name, i):
        """The place of entry `i` of the column `name` of the record `rec`."""
        return k.m(col(rec, name), "at", i)

    def node(sp, i):
        return node_at(k, e, sp, i, k.lo("node_raw"))

    def nat(sp, name, i):
        """The place of the field `name` of node `i` of the spline `sp`."""
        return e.fld(node(sp, i), name)

    def chan(sp, i, c):
        return channel_at(k, e, sp, i, c, k.lo("node_raw"))

    def chani(sp, i, c):
        return interp_at(k, e, sp, i, c, k.lo("node_raw"))

    def gc(name):
        """The geometry constant `name`."""
        return e.call(k.lo("geom_" + name), e.tup())

    def ic(name):
        """The interpolation constant `name`."""
        return e.call(k.lo("interp_" + name), e.tup())

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def seg_l(segs, i, j):
        """The arc length table entry `j` of segment `i`."""
        return at(segs, "l", k.add(k.mul(i, e.n(SUBDIV + 1)), j))

    def push_n(rec, name, zero, n):
        """Appends `n` entries `zero` to the column `name` of `rec`."""
        return k.for_("__z", 0, n, "zeros", k.m(col(rec, name), "push", zero))

    def zeros(name, n):
        """Statements binding `name` to a new owned `f64s` of `n` zeros (a solve's scratch)."""
        return [
            e.let(name, k.call("f64s_new", e.tup())),
            k.for_("__z", 0, n, "zeros_" + name, k.m(v(name), "push", f(0))),
        ]

    k.dep(
        x,
        "sp_new",
        ["nch"],
        ["t_i32"],
        "spline_t",
        e.ret(k.call("spline_make", e.rec(p("nodes", k.call("nodes_new", e.tup())), p("nch", v("nch"))))),
    )
    k.dep(
        x,
        "sp_count",
        ["sp"],
        ["spline_raw"],
        "t_i32",
        e.ret(e.mb.as_(e.fld(col(v("sp"), "nodes"), "len"), k.lo("t_i32"))),
    )
    k.dep(x, "sp_node", ["sp", "i"], ["spline_raw", "t_i32"], "node_raw", e.ret(node(v("sp"), v("i"))))
    # The geometries and interpolations by index (a document's, a dropdown's), and back; an index out of range traps.
    for name, variants, c in [("geom", GEOMS, gc), ("interp", INTERPS, ic)]:
        k.dep(
            x,
            "sp_%s_of" % name,
            ["i"],
            ["t_i32"],
            name + "_t",
            e.seq(*[k.if_(k.eq(v("i"), e.n(n)), k.ret(c(vn))) for n, vn in enumerate(variants)], trap()),
        )
        k.dep(
            x,
            "sp_%s_index" % name,
            ["v"],
            [name + "_t"],
            "t_i32",
            e.ret(e.match_of(v("v"), "_", None, *[p(vn, k.i32(n)) for n, vn in enumerate(variants)])),
        )
    # A zeroed node of the spline's channel count (owned).
    k.dep(
        x,
        "sp_node_new",
        ["sp"],
        ["spline_raw"],
        "node_t",
        e.seq(
            e.let("cz", k.call("f64s_new", e.tup())),
            e.let("iz", k.call("interps_new", e.tup())),
            k.for_("__c", 0, col(v("sp"), "nch"), "chs", k.m(v("cz"), "push", f(0)), k.m(v("iz"), "push", ic("step"))),
            e.ret(
                k.call(
                    "node_make",
                    e.rec(
                        *[p(c, f(0)) for c in NODE_COLUMNS],
                        p("geom", gc("line")),
                        p("c", k.m(v("cz"), "move", e.tup())),
                        p("ci", k.m(v("iz"), "move", e.tup())),
                    ),
                )
            ),
        ),
    )
    k.dep(
        x,
        "sp_push",
        ["sp"],
        ["spline_raw"],
        "t_i32",
        e.seq(
            e.let("i", k.dcall("sp_count", v("sp"))),
            k.m(col(v("sp"), "nodes"), "push", k.dcall("sp_node_new", v("sp"))),
            e.ret(v("i")),
        ),
    )
    k.dep(
        x,
        "sp_insert",
        ["sp", "i"],
        ["spline_raw", "t_i32"],
        "t_void",
        k.m(col(v("sp"), "nodes"), "insert", e.tup(v("i"), k.dcall("sp_node_new", v("sp")))),
    )
    k.dep(
        x,
        "sp_remove",
        ["sp", "i"],
        ["spline_raw", "t_i32"],
        "t_void",
        e.seq(e.let("gone", k.m(col(v("sp"), "nodes"), "remove", v("i")))),
    )
    k.dep(x, "sp_clear", ["sp"], ["spline_raw"], "t_void", k.m(col(v("sp"), "nodes"), "clear", e.tup()))
    k.dep(
        x,
        "sp_copy",
        ["dst", "src"],
        ["spline_raw", "spline_raw"],
        "t_void",
        e.seq(
            k.dcall("sp_clear", v("dst")),
            k.set(col(v("dst"), "nch"), col(v("src"), "nch")),
            k.for_(
                "i",
                0,
                k.dcall("sp_count", v("src")),
                "nodes",
                e.let("j", k.dcall("sp_push", v("dst"))),
                *[k.set(nat(v("dst"), c, v("j")), nat(v("src"), c, v("i"))) for c in NODE_COLUMNS + ["geom"]],
                k.for_(
                    "c",
                    0,
                    col(v("src"), "nch"),
                    "chs",
                    k.set(chan(v("dst"), v("j"), v("c")), chan(v("src"), v("i"), v("c"))),
                    k.set(chani(v("dst"), v("j"), v("c")), chani(v("src"), v("i"), v("c"))),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "segs_new",
        [],
        [],
        "segs_t",
        e.ret(
            k.call(
                "segs_make",
                e.rec(*[p(c, k.call("f64s_new", e.tup())) for c in CTRL_COLUMNS], p("l", k.call("f64s_new", e.tup()))),
            )
        ),
    )
    k.dep(
        x,
        "samples_new",
        [],
        [],
        "samples_t",
        e.ret(
            k.call(
                "samples_make",
                e.rec(
                    *[p(c, k.call("f64s_new", e.tup())) for c in SAMPLE_COLUMNS],
                    p("seg", k.call("ints_new", e.tup())),
                    p("c", k.call("f64s_new", e.tup())),
                ),
            )
        ),
    )
    k.dep(
        x,
        "track_new",
        [],
        [],
        "track_t",
        e.ret(k.call("track_make", e.rec(*[p(c, k.call("f64s_new", e.tup())) for c in ["t", "x", "y", "c"]]))),
    )
    # The segments record resized to `n` segments (zeroed).
    k.dep(
        x,
        "segs_resize",
        ["segs", "n"],
        ["segs_raw", "t_i32"],
        "t_void",
        e.seq(
            *[k.m(col(v("segs"), c), "clear", e.tup()) for c in CTRL_COLUMNS + ["l"]],
            *[push_n(v("segs"), c, f(0), v("n")) for c in CTRL_COLUMNS],
            push_n(v("segs"), "l", f(0), k.mul(v("n"), e.n(SUBDIV + 1))),
        ),
    )

    # --- preparing: each segment as a cubic Bézier ---

    def set_ctrl(segs, i, xs, ys):
        out = []
        for j in range(4):
            out.append(k.set(at(segs, "x%d" % j, i), xs[j]))
            out.append(k.set(at(segs, "y%d" % j, i), ys[j]))
        return out

    def nx(sp, i):
        return nat(sp, "x", i)

    def ny(sp, i):
        return nat(sp, "y", i)

    # The centripetal Catmull-Rom segment `i` from node b to node c, with a before and d after (the ends repeat).
    k.dep(
        x,
        "sp_catmull",
        [n + q for n in "abcd" for q in "xy"] + ["segs", "i"],
        ["t_f64"] * 8 + ["segs_raw", "t_i32"],
        "t_void",
        e.seq(
            # knot intervals: square roots of the chords (centripetal), never zero
            e.let("d0", k.fmax(k.sqrt(M("m_hypot", k.sub(v("bx"), v("ax")), k.sub(v("by"), v("ay")))), e.n(1e-6))),
            e.let("d1", k.fmax(k.sqrt(M("m_hypot", k.sub(v("cx"), v("bx")), k.sub(v("cy"), v("by")))), e.n(1e-6))),
            e.let("d2", k.fmax(k.sqrt(M("m_hypot", k.sub(v("dx"), v("cx")), k.sub(v("dy"), v("cy")))), e.n(1e-6))),
            *[
                e.let(
                    "m1" + q,
                    k.mul(
                        v("d1"),
                        k.add(
                            k.sub(
                                k.div(k.sub(v("b" + q), v("a" + q)), v("d0")),
                                k.div(k.sub(v("c" + q), v("a" + q)), k.add(v("d0"), v("d1"))),
                            ),
                            k.div(k.sub(v("c" + q), v("b" + q)), v("d1")),
                        ),
                    ),
                )
                for q in "xy"
            ],
            *[
                e.let(
                    "m2" + q,
                    k.mul(
                        v("d1"),
                        k.add(
                            k.sub(
                                k.div(k.sub(v("c" + q), v("b" + q)), v("d1")),
                                k.div(k.sub(v("d" + q), v("b" + q)), k.add(v("d1"), v("d2"))),
                            ),
                            k.div(k.sub(v("d" + q), v("c" + q)), v("d2")),
                        ),
                    ),
                )
                for q in "xy"
            ],
            *set_ctrl(
                v("segs"),
                v("i"),
                [v("bx"), k.add(v("bx"), k.div(v("m1x"), e.n(3))), k.sub(v("cx"), k.div(v("m2x"), e.n(3))), v("cx")],
                [v("by"), k.add(v("by"), k.div(v("m1y"), e.n(3))), k.sub(v("cy"), k.div(v("m2y"), e.n(3))), v("cy")],
            ),
        ),
    )

    def bez(c0, c1, c2, c3, u):
        mu = k.sub(e.n(1), u)
        return k.add(
            k.add(k.mul(k.mul(k.mul(mu, mu), mu), c0), k.mul(k.mul(k.mul(e.n(3), k.mul(mu, mu)), u), c1)),
            k.add(k.mul(k.mul(k.mul(e.n(3), mu), k.mul(u, u)), c2), k.mul(k.mul(k.mul(u, u), u), c3)),
        )

    def dbez(c0, c1, c2, c3, u):
        mu = k.sub(e.n(1), u)
        return k.add(
            k.add(
                k.mul(k.mul(e.n(3), k.mul(mu, mu)), k.sub(c1, c0)), k.mul(k.mul(k.mul(e.n(6), mu), u), k.sub(c2, c1))
            ),
            k.mul(k.mul(e.n(3), k.mul(u, u)), k.sub(c3, c2)),
        )

    # The position and unit tangent at parameter u of the prepared segment `i`.
    k.dep(
        x,
        "sp_point",
        ["segs", "i", "u"],
        ["segs_raw", "t_i32", "t_f64"],
        "pt_t",
        e.seq(
            *[e.let(c, at(v("segs"), c, v("i"))) for c in CTRL_COLUMNS],
            e.let("px", bez(v("x0"), v("x1"), v("x2"), v("x3"), v("u"))),
            e.let("py", bez(v("y0"), v("y1"), v("y2"), v("y3"), v("u"))),
            e.let("dx", dbez(v("x0"), v("x1"), v("x2"), v("x3"), v("u"))),
            e.let("dy", dbez(v("y0"), v("y1"), v("y2"), v("y3"), v("u"))),
            # the unit tangent (the zero vector where the derivative vanishes: coincident nodes)
            e.let("dl", M("m_hypot", v("dx"), v("dy"))),
            e.let("nl", k.ifelse(k.gt(v("dl"), e.n(0)), v("dl"), f(1))),
            e.ret(e.mb.as_(e.tup(v("px"), v("py"), k.div(v("dx"), v("nl")), k.div(v("dy"), v("nl"))), k.lo("pt_t"))),
        ),
    )
    # The arc length table of the prepared segment `i`.
    k.dep(
        x,
        "sp_measure",
        ["segs", "i"],
        ["segs_raw", "t_i32"],
        "t_void",
        e.seq(
            e.let("acc", f(0)),
            e.let("px", at(v("segs"), "x0", v("i"))),
            e.let("py", at(v("segs"), "y0", v("i"))),
            k.set(seg_l(v("segs"), v("i"), e.n(0)), f(0)),
            k.for_(
                "j",
                1,
                e.n(SUBDIV + 1),
                "steps",
                e.let("pt", k.dcall("sp_point", v("segs"), v("i"), k.div(k.to_f64(v("j")), e.n(SUBDIV)))),
                e.let("qx", e.mb.field(v("pt"), e.n(0))),
                e.let("qy", e.mb.field(v("pt"), e.n(1))),
                setv("acc", k.add(v("acc"), M("m_hypot", k.sub(v("qx"), v("px")), k.sub(v("qy"), v("py"))))),
                setv("px", v("qx")),
                setv("py", v("qy")),
                k.set(seg_l(v("segs"), v("i"), v("j")), v("acc")),
            ),
        ),
    )

    def scratch(name, j):
        """The solve's scratch column `name` at `j`."""
        return k.m(v(name), "at", j)

    # The natural spline through the nodes from..to (a run of natural segments): second derivatives by the Thomas
    # algorithm over chord-length knots, then each segment's Bézier.
    k.dep(
        x,
        "sp_natural",
        ["sp", "segs", "from", "to"],
        ["spline_raw", "segs_raw", "t_i32", "t_i32"],
        "t_void",
        e.seq(
            e.let("n", k.sub(v("to"), v("from"))),
            # per node j: h (chord to the next), mx, my (second derivatives), c' and dx', dy' of the elimination
            *[s for name in ["h", "mx", "my", "cp", "dpx", "dpy"] for s in zeros(name, k.add(v("n"), e.n(1)))],
            k.for_(
                "j",
                0,
                v("n"),
                "chords",
                e.let("ia", k.add(v("from"), v("j"))),
                e.let("ib", k.add(v("ia"), e.n(1))),
                k.set(
                    scratch("h", v("j")),
                    k.fmax(
                        M(
                            "m_hypot",
                            k.sub(nx(v("sp"), v("ib")), nx(v("sp"), v("ia"))),
                            k.sub(ny(v("sp"), v("ib")), ny(v("sp"), v("ia"))),
                        ),
                        e.n(1e-6),
                    ),
                ),
            ),
            # forward elimination over the interior nodes 1..n-1 (the ends' second derivatives are 0)
            k.for_(
                "j",
                1,
                v("n"),
                "fwd",
                e.let("hp", scratch("h", k.sub(v("j"), e.n(1)))),
                e.let("hn", scratch("h", v("j"))),
                e.let("ip", k.add(k.add(v("from"), v("j")), e.n(-1))),
                e.let("ic", k.add(v("from"), v("j"))),
                e.let("inx", k.add(k.add(v("from"), v("j")), e.n(1))),
                e.let("diag", k.mul(e.n(2), k.add(v("hp"), v("hn")))),
                e.let("cprev", k.ifelse(k.gt(v("j"), e.n(1)), scratch("cp", k.sub(v("j"), e.n(1))), f(0))),
                e.let("den", k.sub(v("diag"), k.mul(v("hp"), v("cprev")))),
                k.set(scratch("cp", v("j")), k.div(v("hn"), v("den"))),
                *[
                    e.seq(
                        e.let(
                            "rhs" + q,
                            k.mul(
                                e.n(6),
                                k.sub(
                                    k.div(k.sub(nat(v("sp"), q, v("inx")), nat(v("sp"), q, v("ic"))), v("hn")),
                                    k.div(k.sub(nat(v("sp"), q, v("ic")), nat(v("sp"), q, v("ip"))), v("hp")),
                                ),
                            ),
                        ),
                        e.let(
                            "dprev" + q, k.ifelse(k.gt(v("j"), e.n(1)), scratch("dp" + q, k.sub(v("j"), e.n(1))), f(0))
                        ),
                        k.set(
                            scratch("dp" + q, v("j")),
                            k.div(k.sub(v("rhs" + q), k.mul(v("hp"), v("dprev" + q))), v("den")),
                        ),
                    )
                    for q in "xy"
                ],
            ),
            # back substitution
            e.let("jb", k.sub(v("n"), e.n(1))),
            k.loop(
                "back",
                k.if_(k.lt(v("jb"), e.n(1)), k.brk("back")),
                *[
                    k.set(
                        scratch("m" + q, v("jb")),
                        k.sub(
                            scratch("dp" + q, v("jb")),
                            k.mul(scratch("cp", v("jb")), scratch("m" + q, k.add(v("jb"), e.n(1)))),
                        ),
                    )
                    for q in "xy"
                ],
                setv("jb", k.sub(v("jb"), e.n(1))),
            ),
            # each segment's Bézier: the end derivatives of its cubic
            k.for_(
                "j",
                0,
                v("n"),
                "segs",
                e.let("h", scratch("h", v("j"))),
                e.let("ia", k.add(v("from"), v("j"))),
                e.let("ib", k.add(v("ia"), e.n(1))),
                *[
                    stmt
                    for q in "xy"
                    for stmt in [
                        e.let("ma" + q, scratch("m" + q, v("j"))),
                        e.let("mb" + q, scratch("m" + q, k.add(v("j"), e.n(1)))),
                        e.let("sl" + q, k.div(k.sub(nat(v("sp"), q, v("ib")), nat(v("sp"), q, v("ia"))), v("h"))),
                        e.let(
                            "da" + q,
                            k.sub(
                                v("sl" + q),
                                k.div(k.mul(v("h"), k.add(k.mul(e.n(2), v("ma" + q)), v("mb" + q))), e.n(6)),
                            ),
                        ),
                        e.let(
                            "db" + q,
                            k.add(
                                v("sl" + q),
                                k.div(k.mul(v("h"), k.add(v("ma" + q), k.mul(e.n(2), v("mb" + q)))), e.n(6)),
                            ),
                        ),
                    ]
                ],
                *set_ctrl(
                    v("segs"),
                    v("ia"),
                    [
                        nx(v("sp"), v("ia")),
                        k.add(nx(v("sp"), v("ia")), k.div(k.mul(v("dax"), v("h")), e.n(3))),
                        k.sub(nx(v("sp"), v("ib")), k.div(k.mul(v("dbx"), v("h")), e.n(3))),
                        nx(v("sp"), v("ib")),
                    ],
                    [
                        ny(v("sp"), v("ia")),
                        k.add(ny(v("sp"), v("ia")), k.div(k.mul(v("day"), v("h")), e.n(3))),
                        k.sub(ny(v("sp"), v("ib")), k.div(k.mul(v("dby"), v("h")), e.n(3))),
                        ny(v("sp"), v("ib")),
                    ],
                ),
            ),
        ),
    )

    # Hobby's velocity function (tension 1): the handle length over a third of the chord, for departure angle th and
    # arrival angle ph.
    k.dep(
        x,
        "sp_hobby_velocity",
        ["th", "ph"],
        ["t_f64", "t_f64"],
        "t_f64",
        e.seq(
            e.let("st", M("m_sin", v("th"))),
            e.let("sp", M("m_sin", v("ph"))),
            e.let("ct", M("m_cos", v("th"))),
            e.let("cpp", M("m_cos", v("ph"))),
            e.ret(
                k.div(
                    k.add(
                        e.n(2),
                        k.mul(
                            k.mul(
                                k.mul(e.n(SQRT2), k.sub(v("st"), k.div(v("sp"), e.n(16)))),
                                k.sub(v("sp"), k.div(v("st"), e.n(16))),
                            ),
                            k.sub(v("ct"), v("cpp")),
                        ),
                    ),
                    k.add(k.add(e.n(1), k.mul(e.n(HOBBY_A), v("ct"))), k.mul(e.n(HOBBY_B), v("cpp"))),
                )
            ),
        ),
    )

    def hv(name, j):
        """Hobby's per-node scratch value `name` of node j of the run."""
        return scratch(name, j)

    # Hobby's spline through the nodes from..to (a run of Hobby segments), MetaPost's with tension 1 and curl 1 ends:
    # the departure angles th_j (from each chord) make the mock curvature continuous at the interior nodes, with
    # th_0 + th_1 = -psi_1 and th_n-1 + th_n = 0 at the ends (psi_j the turning angle at node j, psi_n = 0) substituted
    # into the first and last rows, leaving a diagonally dominant tridiagonal system (Thomas algorithm); the arrival
    # angles are ph_j+1 = -psi_j+1 - th_j+1, and the control points come from Hobby's velocity function. A run of one
    # segment is straight.
    k.dep(
        x,
        "sp_hobby",
        ["sp", "segs", "from", "to"],
        ["spline_raw", "segs_raw", "t_i32", "t_i32"],
        "t_void",
        e.seq(
            e.let("n", k.sub(v("to"), v("from"))),
            # per node j: d and w (the chord to the next node: length and angle), psi, the row (a, b, c, r) and the
            # elimination's c', then th
            *[
                s
                for name in ["d", "w", "psi", "a", "b", "c", "r", "cp", "th"]
                for s in zeros(name, k.add(v("n"), e.n(1)))
            ],
            k.for_(
                "j",
                0,
                v("n"),
                "chords",
                e.let("ia", k.add(v("from"), v("j"))),
                e.let("ib", k.add(v("ia"), e.n(1))),
                e.let("dx", k.sub(nx(v("sp"), v("ib")), nx(v("sp"), v("ia")))),
                e.let("dy", k.sub(ny(v("sp"), v("ib")), ny(v("sp"), v("ia")))),
                k.set(hv("d", v("j")), k.fmax(M("m_hypot", v("dx"), v("dy")), e.n(1e-6))),
                k.set(hv("w", v("j")), M("m_atan2", v("dy"), v("dx"))),
            ),
            # the turning angles: the angle from the previous chord to the next (atan2 of their cross and dot)
            k.set(hv("psi", e.n(0)), f(0)),
            k.set(hv("psi", v("n")), f(0)),
            k.for_(
                "j",
                1,
                v("n"),
                "turns",
                e.let("ia", k.add(k.add(v("from"), v("j")), e.n(-1))),
                e.let("ib", k.add(v("from"), v("j"))),
                e.let("ic", k.add(k.add(v("from"), v("j")), e.n(1))),
                e.let("ux", k.sub(nx(v("sp"), v("ib")), nx(v("sp"), v("ia")))),
                e.let("uy", k.sub(ny(v("sp"), v("ib")), ny(v("sp"), v("ia")))),
                e.let("vx", k.sub(nx(v("sp"), v("ic")), nx(v("sp"), v("ib")))),
                e.let("vy", k.sub(ny(v("sp"), v("ic")), ny(v("sp"), v("ib")))),
                k.set(
                    hv("psi", v("j")),
                    M(
                        "m_atan2",
                        k.sub(k.mul(v("ux"), v("vy")), k.mul(v("uy"), v("vx"))),
                        k.add(k.mul(v("ux"), v("vx")), k.mul(v("uy"), v("vy"))),
                    ),
                ),
            ),
            k.ifelse(
                k.eq(v("n"), e.n(1)),
                e.seq(k.set(hv("th", e.n(0)), f(0)), k.set(hv("th", e.n(1)), f(0))),
                e.seq(
                    # the rows of th_1..th_n-1
                    k.for_(
                        "j",
                        1,
                        v("n"),
                        "rows",
                        e.let("dp", hv("d", k.sub(v("j"), e.n(1)))),
                        e.let("dn", hv("d", v("j"))),
                        k.set(hv("a", v("j")), k.div(e.n(1), v("dp"))),
                        k.set(hv("b", v("j")), k.add(k.div(e.n(2), v("dp")), k.div(e.n(2), v("dn")))),
                        k.set(hv("c", v("j")), k.div(e.n(1), v("dn"))),
                        k.set(
                            hv("r", v("j")),
                            k.sub(
                                k.div(k.mul(e.n(-2), hv("psi", v("j"))), v("dp")),
                                k.div(hv("psi", k.add(v("j"), e.n(1))), v("dn")),
                            ),
                        ),
                    ),
                    # the curl ends: th_0 = -psi_1 - th_1 into row 1, th_n = -th_n-1 into row n-1
                    k.set(hv("b", e.n(1)), k.sub(hv("b", e.n(1)), hv("a", e.n(1)))),
                    k.set(hv("r", e.n(1)), k.add(hv("r", e.n(1)), k.mul(hv("a", e.n(1)), hv("psi", e.n(1))))),
                    k.set(hv("a", e.n(1)), f(0)),
                    e.let("last", k.sub(v("n"), e.n(1))),
                    k.set(hv("b", v("last")), k.sub(hv("b", v("last")), hv("c", v("last")))),
                    k.set(hv("c", v("last")), f(0)),
                    # forward elimination
                    k.for_(
                        "j",
                        1,
                        v("n"),
                        "fwd",
                        e.let("cprev", k.ifelse(k.gt(v("j"), e.n(1)), hv("cp", k.sub(v("j"), e.n(1))), f(0))),
                        e.let("rprev", k.ifelse(k.gt(v("j"), e.n(1)), hv("th", k.sub(v("j"), e.n(1))), f(0))),
                        e.let("den", k.sub(hv("b", v("j")), k.mul(hv("a", v("j")), v("cprev")))),
                        k.set(hv("cp", v("j")), k.div(hv("c", v("j")), v("den"))),
                        k.set(
                            hv("th", v("j")),
                            k.div(k.sub(hv("r", v("j")), k.mul(hv("a", v("j")), v("rprev"))), v("den")),
                        ),
                    ),
                    # back substitution (th holds r' until replaced)
                    e.let("jb", k.sub(v("n"), e.n(2))),
                    k.loop(
                        "back",
                        k.if_(k.lt(v("jb"), e.n(1)), k.brk("back")),
                        k.set(
                            hv("th", v("jb")),
                            k.sub(hv("th", v("jb")), k.mul(hv("cp", v("jb")), hv("th", k.add(v("jb"), e.n(1))))),
                        ),
                        setv("jb", k.sub(v("jb"), e.n(1))),
                    ),
                    k.set(hv("th", e.n(0)), k.sub(k.sub(f(0), hv("psi", e.n(1))), hv("th", e.n(1)))),
                    k.set(hv("th", v("n")), k.sub(f(0), hv("th", v("last")))),
                ),
            ),
            # each segment's Bézier
            k.for_(
                "j",
                0,
                v("n"),
                "segs",
                e.let("ia", k.add(v("from"), v("j"))),
                e.let("ib", k.add(v("ia"), e.n(1))),
                # (the angles as locals, named apart from the scratch columns)
                e.let("tha", hv("th", v("j"))),
                e.let("phb", k.sub(k.sub(f(0), hv("psi", k.add(v("j"), e.n(1)))), hv("th", k.add(v("j"), e.n(1))))),
                e.let("dd", k.div(hv("d", v("j")), e.n(3))),
                e.let("wj", hv("w", v("j"))),
                e.let("rho", k.mul(v("dd"), k.dcall("sp_hobby_velocity", v("tha"), v("phb")))),
                e.let("sig", k.mul(v("dd"), k.dcall("sp_hobby_velocity", v("phb"), v("tha")))),
                e.let("wa", k.add(v("wj"), v("tha"))),
                e.let("wb", k.sub(v("wj"), v("phb"))),
                *set_ctrl(
                    v("segs"),
                    v("ia"),
                    [
                        nx(v("sp"), v("ia")),
                        k.add(nx(v("sp"), v("ia")), k.mul(v("rho"), M("m_cos", v("wa")))),
                        k.sub(nx(v("sp"), v("ib")), k.mul(v("sig"), M("m_cos", v("wb")))),
                        nx(v("sp"), v("ib")),
                    ],
                    [
                        ny(v("sp"), v("ia")),
                        k.add(ny(v("sp"), v("ia")), k.mul(v("rho"), M("m_sin", v("wa")))),
                        k.sub(ny(v("sp"), v("ib")), k.mul(v("sig"), M("m_sin", v("wb")))),
                        ny(v("sp"), v("ib")),
                    ],
                ),
            ),
        ),
    )

    def clampi(i, n):
        """The node index `i` kept within 0..n-1."""
        return k.ifelse(k.lt(i, e.n(0)), k.i32(0), k.ifelse(k.ge(i, n), k.sub(n, e.n(1)), i))

    k.dep(
        x,
        "sp_prepare",
        ["sp", "segs"],
        ["spline_raw", "segs_raw"],
        "t_void",
        e.seq(
            e.let("n", k.dcall("sp_count", v("sp"))),
            e.let("ns", k.ifelse(k.gt(v("n"), e.n(0)), k.sub(v("n"), e.n(1)), k.i32(0))),
            k.dcall("segs_resize", v("segs"), v("ns")),
            k.for_(
                "i",
                0,
                v("ns"),
                "segs",
                e.let("b", v("i")),
                e.let("c", k.add(v("i"), e.n(1))),
                e.let("g", nat(v("sp"), "geom", v("b"))),
                *[e.let(n + q, nat(v("sp"), q, v(n))) for n in "bc" for q in "xy"],
                # the neighbours beyond the ends are phantom nodes, the ends' reflections of their neighbours
                *[
                    e.let(
                        "a" + q,
                        k.ifelse(
                            k.eq(v("i"), e.n(0)),
                            k.sub(k.mul(e.n(2), v("b" + q)), v("c" + q)),
                            nat(v("sp"), q, k.sub(v("i"), e.n(1))),
                        ),
                    )
                    for q in "xy"
                ],
                *[
                    e.let(
                        "d" + q,
                        k.ifelse(
                            k.ge(k.add(v("i"), e.n(2)), v("n")),
                            k.sub(k.mul(e.n(2), v("c" + q)), v("b" + q)),
                            nat(v("sp"), q, k.add(v("i"), e.n(2))),
                        ),
                    )
                    for q in "xy"
                ],
                e.match_of(
                    v("g"),
                    "_",
                    None,
                    p(
                        "line",
                        e.seq(
                        *set_ctrl(
                            v("segs"),
                            v("i"),
                            [
                                v("bx"),
                                k.add(v("bx"), k.div(k.sub(v("cx"), v("bx")), e.n(3))),
                                k.sub(v("cx"), k.div(k.sub(v("cx"), v("bx")), e.n(3))),
                                v("cx"),
                            ],
                            [
                                v("by"),
                                k.add(v("by"), k.div(k.sub(v("cy"), v("by")), e.n(3))),
                                k.sub(v("cy"), k.div(k.sub(v("cy"), v("by")), e.n(3))),
                                v("cy"),
                            ],
                        ),
                        ),
                    ),
                    p("catmull", k.dcall("sp_catmull", *[v(n + q) for n in "abcd" for q in "xy"], v("segs"), v("i")),),
                    p(
                        "bezier",
                        e.seq(
                        *set_ctrl(
                            v("segs"),
                            v("i"),
                            [
                                v("bx"),
                                k.add(v("bx"), nat(v("sp"), "hox", v("b"))),
                                k.add(v("cx"), nat(v("sp"), "hix", v("c"))),
                                v("cx"),
                            ],
                            [
                                v("by"),
                                k.add(v("by"), nat(v("sp"), "hoy", v("b"))),
                                k.add(v("cy"), nat(v("sp"), "hiy", v("c"))),
                                v("cy"),
                            ],
                        ),
                        ),
                    ),
                    p(
                        "bspline",
                        e.seq(
                        *set_ctrl(
                            v("segs"),
                            v("i"),
                            *[
                                [
                                    k.div(k.add(k.add(v("a" + q), k.mul(e.n(4), v("b" + q))), v("c" + q)), e.n(6)),
                                    k.div(k.add(k.mul(e.n(2), v("b" + q)), v("c" + q)), e.n(3)),
                                    k.div(k.add(v("b" + q), k.mul(e.n(2), v("c" + q))), e.n(3)),
                                    k.div(k.add(k.add(v("b" + q), k.mul(e.n(4), v("c" + q))), v("d" + q)), e.n(6)),
                                ]
                                for q in "xy"
                            ],
                        ),
                        ),
                    ),
                    # natural and Hobby segments are solved as runs, below
                    p("natural", e.seq()),
                    p("hobby", e.seq()),
                ),
            # runs of natural segments, then of Hobby segments: each solved as a whole
            *[
                e.seq(
                    e.let("run", k.i32(-1)),
                    k.for_(
                        "i",
                        0,
                        k.add(v("ns"), e.n(1)),
                        "runs",
                        e.let(
                            "in_run",
                            k.and_(
                                k.lt(v("i"), v("ns")), k.eq(nat(v("sp"), "geom", clampi(v("i"), v("n"))), gc(kind))
                            ),
                        ),
                        k.if_(k.and_(v("in_run"), k.lt(v("run"), e.n(0))), setv("run", v("i"))),
                        k.if_(
                            k.and_(k.not_(v("in_run")), k.ge(v("run"), e.n(0))),
                            k.dcall(solve, v("sp"), v("segs"), v("run"), v("i")),
                            setv("run", e.n(-1)),
                        ),
                    ),
                )
                for kind, solve in [("natural", "sp_natural"), ("hobby", "sp_hobby")]
            ],
            k.for_("i", 0, v("ns"), "measure", k.dcall("sp_measure", v("segs"), v("i"))),
        ),
    )
    k.dep(
        x,
        "sp_length",
        ["segs"],
        ["segs_raw"],
        "t_f64",
        e.seq(
            e.let("acc", f(0)),
            k.for_(
                "i",
                0,
                e.fld(col(v("segs"), "x0"), "len"),
                "sum",
                setv("acc", k.add(v("acc"), seg_l(v("segs"), v("i"), e.n(SUBDIV)))),
            ),
            e.ret(v("acc")),
        ),
    )

    # --- channels ---
    k.dep(
        x,
        "sp_channel",
        ["sp", "i", "u", "c"],
        ["spline_raw", "t_i32", "t_f64", "t_i32"],
        "t_f64",
        e.seq(
            e.let("n", k.dcall("sp_count", v("sp"))),
            e.let("v1", chan(v("sp"), v("i"), v("c"))),
            k.if_(k.ge(k.add(v("i"), e.n(1)), v("n")), k.ret(v("v1"))),
            e.let("v2", chan(v("sp"), k.add(v("i"), e.n(1)), v("c"))),
            e.match_of(
                chani(v("sp"), v("i"), v("c")),
                "_",
                None,
                p("step", k.ret(v("v1"))),
                p("linear", k.ret(M("m_lerp", v("v1"), v("v2"), v("u")))),
                p(
                    "smooth",
                    k.ret(
                        M(
                            "m_lerp",
                            v("v1"),
                            v("v2"),
                            k.mul(k.mul(v("u"), v("u")), k.sub(e.n(3), k.mul(e.n(2), v("u")))),
                        )
                    ),
                ),
                p("catmull", e.seq()),
            ),
            # Catmull-Rom on the values (phantom values beyond the ends: the ends' reflections of their neighbours)
            e.let(
                "v0",
                k.ifelse(
                    k.eq(v("i"), e.n(0)),
                    k.sub(k.mul(e.n(2), v("v1")), v("v2")),
                    chan(v("sp"), k.sub(v("i"), e.n(1)), v("c")),
                ),
            ),
            e.let(
                "v3",
                k.ifelse(
                    k.ge(k.add(v("i"), e.n(2)), v("n")),
                    k.sub(k.mul(e.n(2), v("v2")), v("v1")),
                    chan(v("sp"), k.add(v("i"), e.n(2)), v("c")),
                ),
            ),
            e.let("u2", k.mul(v("u"), v("u"))),
            e.let("u3", k.mul(v("u2"), v("u"))),
            e.ret(
                k.mul(
                    e.n(0.5),
                    k.add(
                        k.add(k.mul(e.n(2), v("v1")), k.mul(k.sub(v("v2"), v("v0")), v("u"))),
                        k.add(
                            k.mul(
                                k.add(
                                    k.sub(k.mul(e.n(2), v("v0")), k.mul(e.n(5), v("v1"))),
                                    k.sub(k.mul(e.n(4), v("v2")), v("v3")),
                                ),
                                v("u2"),
                            ),
                            k.mul(
                                k.add(k.sub(k.mul(e.n(3), v("v1")), v("v0")), k.sub(v("v3"), k.mul(e.n(3), v("v2")))),
                                v("u3"),
                            ),
                        ),
                    ),
                )
            ),
        ),
    )

    # --- sampling by arc length ---
    # The parameter of segment `i` at arc length `l` into it (from its table, linear between entries).
    k.dep(
        x,
        "sp_param",
        ["segs", "i", "l"],
        ["segs_raw", "t_i32", "t_f64"],
        "t_f64",
        e.seq(
            k.for_(
                "j",
                1,
                e.n(SUBDIV + 1),
                "find",
                e.let("lj", seg_l(v("segs"), v("i"), v("j"))),
                k.if_(
                    k.ge(v("lj"), v("l")),
                    e.let("lp", seg_l(v("segs"), v("i"), k.sub(v("j"), e.n(1)))),
                    e.let(
                        "frac",
                        k.ifelse(
                            k.gt(k.sub(v("lj"), v("lp")), e.n(1e-12)),
                            k.div(k.sub(v("l"), v("lp")), k.sub(v("lj"), v("lp"))),
                            f(0),
                        ),
                    ),
                    k.ret(k.div(k.add(k.to_f64(k.sub(v("j"), e.n(1))), v("frac")), e.n(SUBDIV))),
                ),
            ),
            e.ret(f(1)),
        ),
    )
    # A sample appended to `out`: segment `i` at `u`, at arc length `s`.
    k.dep(
        x,
        "sp_fill",
        ["sp", "segs", "i", "u", "s", "out"],
        ["spline_raw", "segs_raw", "t_i32", "t_f64", "t_f64", "samples_raw"],
        "t_void",
        e.seq(
            e.let("pt", k.dcall("sp_point", v("segs"), v("i"), v("u"))),
            *[k.m(col(v("out"), c), "push", e.mb.field(v("pt"), e.n(j))) for j, c in enumerate(["x", "y", "tx", "ty"])],
            k.m(col(v("out"), "s"), "push", v("s")),
            k.m(col(v("out"), "seg"), "push", v("i")),
            k.m(col(v("out"), "u"), "push", v("u")),
            k.m(
                col(v("out"), "t"),
                "push",
                M("m_lerp", nat(v("sp"), "t", v("i")), nat(v("sp"), "t", k.add(v("i"), e.n(1))), v("u")),
            ),
            # the spline's channels, then zeros up to the samples' slots
            k.for_(
                "c",
                0,
                e.n(CHANNELS),
                "chs",
                k.m(
                    col(v("out"), "c"),
                    "push",
                    k.ifelse(
                        k.lt(v("c"), col(v("sp"), "nch")),
                        k.dcall("sp_channel", v("sp"), v("i"), v("u"), v("c")),
                        f(0),
                    ),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "sp_sample",
        ["sp", "segs", "spacing", "out"],
        ["spline_raw", "segs_raw", "t_f64", "samples_raw"],
        "t_void",
        e.seq(
            *[k.m(col(v("out"), c), "clear", e.tup()) for c in SAMPLE_COLUMNS + ["seg", "c"]],
            e.let("ns", e.mb.as_(e.fld(col(v("segs"), "x0"), "len"), k.lo("t_i32"))),
            k.if_(k.eq(v("ns"), e.n(0)), k.ret()),
            e.let("base", f(0)),
            e.let("next", f(0)),
            k.for_(
                "i",
                0,
                v("ns"),
                "segs",
                e.let("len", seg_l(v("segs"), v("i"), e.n(SUBDIV))),
                k.loop(
                    "inside",
                    k.if_(k.gt(k.sub(v("next"), v("base")), v("len")), k.brk("inside")),
                    e.let("u", k.dcall("sp_param", v("segs"), v("i"), k.sub(v("next"), v("base")))),
                    k.dcall("sp_fill", v("sp"), v("segs"), v("i"), v("u"), v("next"), v("out")),
                    setv("next", k.add(v("next"), v("spacing"))),
                ),
                setv("base", k.add(v("base"), v("len"))),
            ),
            # the end
            k.dcall("sp_fill", v("sp"), v("segs"), k.sub(v("ns"), e.n(1)), f(1), v("base"), v("out")),
        ),
    )

    # --- fitting ---
    def tc(j, c):
        return sample_channel_at(k, e, v("track"), j, c)

    def izeros(name, n):
        """Statements binding `name` to a new owned `ints` of `n` zeros."""
        return [
            e.let(name, k.call("ints_new", e.tup())),
            k.for_("__z", 0, n, "zeros_" + name, k.m(v(name), "push", k.i32(0))),
        ]

    # The speed (mm/s) at each sample of a stroke (positions `xs`, `ys` in mm, times `ts` in ms) into `out`: the
    # distance from the sample before over the time (at least a millisecond); the first sample's is its successor's.
    k.dep(
        x,
        "sp_speeds",
        ["xs", "ys", "ts", "out"],
        ["f64s_raw"] * 4,
        "t_void",
        e.seq(
            k.m(v("out"), "clear", e.tup()),
            e.let("n", e.mb.as_(e.fld(v("xs"), "len"), k.lo("t_i32"))),
            k.for_(
                "j",
                0,
                v("n"),
                "speeds",
                k.ifelse(
                    k.eq(v("j"), e.n(0)),
                    k.m(v("out"), "push", f(0)),
                    e.seq(
                        e.let("jp", k.sub(v("j"), e.n(1))),
                        e.let(
                            "dd",
                            M(
                                "m_hypot",
                                k.sub(k.m(v("xs"), "at", v("j")), k.m(v("xs"), "at", v("jp"))),
                                k.sub(k.m(v("ys"), "at", v("j")), k.m(v("ys"), "at", v("jp"))),
                            ),
                        ),
                        e.let("dt", k.fmax(k.sub(k.m(v("ts"), "at", v("j")), k.m(v("ts"), "at", v("jp"))), e.n(1e-3))),
                        k.m(v("out"), "push", k.div(k.mul(v("dd"), e.n(1000)), v("dt"))),
                    ),
                ),
            ),
            k.if_(k.gt(v("n"), e.n(1)), k.set(k.m(v("out"), "at", e.n(0)), k.m(v("out"), "at", e.n(1)))),
        ),
    )
    k.dep(
        x,
        "sp_fit",
        ["track", "nch", "amount", "out"],
        ["track_raw", "t_i32", "t_f64", "spline_raw"],
        "t_void",
        e.seq(
            k.dcall("sp_clear", v("out")),
            k.set(col(v("out"), "nch"), v("nch")),
            e.let("n", e.mb.as_(e.fld(col(v("track"), "x"), "len"), k.lo("t_i32"))),
            k.if_(k.eq(v("n"), e.n(0)), k.ret()),
            # per sample: distance along the track, then the smoothed x, y, t and channels
            *zeros("dist", v("n")),
            *zeros("sx", v("n")),
            *zeros("sy", v("n")),
            *zeros("st", v("n")),
            *zeros("sc", k.mul(v("n"), v("nch"))),
            e.let("acc", f(0)),
            k.for_(
                "j",
                0,
                v("n"),
                "dists",
                k.if_(
                    k.gt(v("j"), e.n(0)),
                    e.let("jp", k.sub(v("j"), e.n(1))),
                    e.let(
                        "dd",
                        M(
                            "m_hypot",
                            k.sub(at(v("track"), "x", v("j")), at(v("track"), "x", v("jp"))),
                            k.sub(at(v("track"), "y", v("j")), at(v("track"), "y", v("jp"))),
                        ),
                    ),
                    setv("acc", k.add(v("acc"), v("dd"))),
                ),
                k.set(scratch("dist", v("j")), v("acc")),
            ),
            e.let("sigma", k.fmax(v("amount"), e.n(1e-6))),
            e.let("reach", k.mul(v("sigma"), e.n(3))),
            e.let("lo", k.i32(0)),
            k.for_(
                "j",
                0,
                v("n"),
                "smooth",
                e.let("dj", scratch("dist", v("j"))),
                k.loop(
                    "advance",
                    k.if_(
                        k.ge(k.sub(v("dj"), scratch("dist", v("lo"))), v("reach")),
                        setv("lo", k.add(v("lo"), e.n(1))),
                        k.cont("advance"),
                    ),
                    k.brk("advance"),
                ),
                e.let("wsum", f(0)),
                e.let("ax", f(0)),
                e.let("ay", f(0)),
                e.let("atime", f(0)),
                k.for_(
                    "m",
                    v("lo"),
                    v("n"),
                    "window",
                    e.let("dm", scratch("dist", v("m"))),
                    k.if_(k.gt(k.sub(v("dm"), v("dj")), v("reach")), k.brk("window")),
                    e.let("q", k.div(k.sub(v("dm"), v("dj")), v("sigma"))),
                    e.let("w", M("m_exp", k.mul(k.mul(v("q"), v("q")), e.n(-0.5)))),
                    setv("wsum", k.add(v("wsum"), v("w"))),
                    setv("ax", k.add(v("ax"), k.mul(v("w"), at(v("track"), "x", v("m"))))),
                    setv("ay", k.add(v("ay"), k.mul(v("w"), at(v("track"), "y", v("m"))))),
                    setv("atime", k.add(v("atime"), k.mul(v("w"), at(v("track"), "t", v("m"))))),
                    k.for_(
                        "c",
                        0,
                        v("nch"),
                        "chs",
                        e.let("slot", k.add(k.mul(v("j"), v("nch")), v("c"))),
                        k.set(
                            scratch("sc", v("slot")), k.add(scratch("sc", v("slot")), k.mul(v("w"), tc(v("m"), v("c"))))
                        ),
                    ),
                ),
                k.set(scratch("sx", v("j")), k.div(v("ax"), v("wsum"))),
                k.set(scratch("sy", v("j")), k.div(v("ay"), v("wsum"))),
                k.set(scratch("st", v("j")), k.div(v("atime"), v("wsum"))),
                k.for_(
                    "c",
                    0,
                    v("nch"),
                    "norm",
                    e.let("slot", k.add(k.mul(v("j"), v("nch")), v("c"))),
                    k.set(scratch("sc", v("slot")), k.div(scratch("sc", v("slot")), v("wsum"))),
                ),
            ),
            # simplification: Ramer-Douglas-Peucker over the smoothed points, marking kept samples
            *izeros("keep", v("n")),
            e.let("stack", k.call("ints_new", e.tup())),
            k.set(scratch("keep", e.n(0)), k.i32(1)),
            k.set(scratch("keep", k.sub(v("n"), e.n(1))), k.i32(1)),
            e.let("tol", k.fmax(k.mul(v("amount"), e.n(0.25)), e.n(0.05))),
            k.m(v("stack"), "push", k.i32(0)),
            k.m(v("stack"), "push", k.sub(v("n"), e.n(1))),
            k.loop(
                "rdp",
                k.if_(k.eq(e.fld(v("stack"), "len"), e.n(0)), k.brk("rdp")),
                e.let("ib", scratch("stack", k.sub(e.fld(v("stack"), "len"), e.n(1)))),
                e.let("ia", scratch("stack", k.sub(e.fld(v("stack"), "len"), e.n(2)))),
                e.seq(e.let("gone1", k.m(v("stack"), "pop", e.tup()))),
                e.seq(e.let("gone2", k.m(v("stack"), "pop", e.tup()))),
                k.if_(k.le(k.sub(v("ib"), v("ia")), e.n(1)), k.cont("rdp")),
                e.let("px", scratch("sx", v("ia"))),
                e.let("py", scratch("sy", v("ia"))),
                e.let("bx", k.sub(scratch("sx", v("ib")), v("px"))),
                e.let("by", k.sub(scratch("sy", v("ib")), v("py"))),
                e.let("bl", M("m_hypot", v("bx"), v("by"))),
                e.let("best", f(-1)),
                e.let("bi", k.i32(-1)),
                k.for_(
                    "m",
                    k.add(v("ia"), e.n(1)),
                    v("ib"),
                    "far",
                    e.let("mx", k.sub(scratch("sx", v("m")), v("px"))),
                    e.let("my", k.sub(scratch("sy", v("m")), v("py"))),
                    e.let(
                        "dmb",
                        k.ifelse(
                            k.gt(v("bl"), e.n(1e-9)),
                            k.div(k.fabs(k.sub(k.mul(v("mx"), v("by")), k.mul(v("my"), v("bx")))), v("bl")),
                            M("m_hypot", v("mx"), v("my")),
                        ),
                    ),
                    k.if_(k.gt(v("dmb"), v("best")), setv("best", v("dmb")), setv("bi", v("m"))),
                ),
                k.if_(
                    k.gt(v("best"), v("tol")),
                    k.set(scratch("keep", v("bi")), k.i32(1)),
                    k.m(v("stack"), "push", v("ia")),
                    k.m(v("stack"), "push", v("bi")),
                    k.m(v("stack"), "push", v("bi")),
                    k.m(v("stack"), "push", v("ib")),
                ),
            ),
            # the kept samples become the nodes
            k.for_(
                "j",
                0,
                v("n"),
                "nodes",
                k.if_(k.eq(scratch("keep", v("j")), e.n(0)), k.cont("nodes")),
                e.let("i", k.dcall("sp_push", v("out"))),
                k.set(nat(v("out"), "x", v("i")), scratch("sx", v("j"))),
                k.set(nat(v("out"), "y", v("i")), scratch("sy", v("j"))),
                k.set(nat(v("out"), "t", v("i")), scratch("st", v("j"))),
                k.set(nat(v("out"), "geom", v("i")), gc("catmull")),
                k.for_(
                    "c",
                    0,
                    v("nch"),
                    "chs",
                    k.set(chan(v("out"), v("i"), v("c")), scratch("sc", k.add(k.mul(v("j"), v("nch")), v("c")))),
                    k.set(chani(v("out"), v("i"), v("c")), ic("linear")),
                ),
            ),
            # handles: the Catmull-Rom segments' Bézier controls, relative to their nodes
            e.let("segs", k.dcall("segs_new")),
            k.dcall("sp_prepare", v("out"), v("segs")),
            k.for_(
                "i",
                0,
                e.fld(col(v("segs"), "x0"), "len"),
                "handles",
                e.let("ib", k.add(v("i"), e.n(1))),
                k.set(nat(v("out"), "hox", v("i")), k.sub(at(v("segs"), "x1", v("i")), nx(v("out"), v("i")))),
                k.set(nat(v("out"), "hoy", v("i")), k.sub(at(v("segs"), "y1", v("i")), ny(v("out"), v("i")))),
                k.set(nat(v("out"), "hix", v("ib")), k.sub(at(v("segs"), "x2", v("i")), nx(v("out"), v("ib")))),
                k.set(nat(v("out"), "hiy", v("ib")), k.sub(at(v("segs"), "y2", v("i")), ny(v("out"), v("ib")))),
            ),
        ),
    )

    # --- editing ---
    k.dep(
        x,
        "sp_nearest_node",
        ["sp", "x", "y"],
        ["spline_raw", "t_f64", "t_f64"],
        "t_i32",
        e.seq(
            e.let("best", f(1e300)),
            e.let("bi", k.i32(-1)),
            k.for_(
                "i",
                0,
                k.dcall("sp_count", v("sp")),
                "nodes",
                e.let("d", M("m_hypot", k.sub(nx(v("sp"), v("i")), v("x")), k.sub(ny(v("sp"), v("i")), v("y")))),
                k.if_(k.lt(v("d"), v("best")), setv("best", v("d")), setv("bi", v("i"))),
            ),
            e.ret(v("bi")),
        ),
    )
    k.dep(
        x,
        "sp_nearest_seg",
        ["segs", "x", "y"],
        ["segs_raw", "t_f64", "t_f64"],
        "near_t",
        e.seq(
            e.let("best", f(1e300)),
            e.let("bi", k.i32(-1)),
            e.let("bu", f(0)),
            k.for_(
                "i",
                0,
                e.fld(col(v("segs"), "x0"), "len"),
                "segs",
                k.for_(
                    "j",
                    0,
                    e.n(SUBDIV + 1),
                    "steps",
                    e.let("u", k.div(k.to_f64(v("j")), e.n(SUBDIV))),
                    e.let("pt", k.dcall("sp_point", v("segs"), v("i"), v("u"))),
                    e.let(
                        "d",
                        M(
                            "m_hypot",
                            k.sub(e.mb.field(v("pt"), e.n(0)), v("x")),
                            k.sub(e.mb.field(v("pt"), e.n(1)), v("y")),
                        ),
                    ),
                    k.if_(k.lt(v("d"), v("best")), setv("best", v("d")), setv("bi", v("i")), setv("bu", v("u"))),
                ),
            ),
            e.ret(e.mb.as_(e.tup(v("bi"), v("bu")), k.lo("near_t"))),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
