"""raster-tiles.atz: a painted image (wat target; dependencies, typed with the ecosystem's libraries): `w` x `h`
pixels of wet ink (four f32 each, raster-color.atz's models; `color` a model value, borrowed) over a world rectangle,
shown as display tiles of TILE x TILE pixels that are redrawn when painted on.

An image is an owned record (`img_t`, `img_own`, `img_raw`): `rt_new(w, h, x0, y0, mmpp)` makes one whose top-left
pixel corner is at world (x0, y0) mm, `mmpp` mm per pixel (owned: dropping it frees the pixels);
its fields `w`, `h`, `x0`, `y0`, `mmpp` read it back and `data` is its `f32s` of pixels. `rt_px(img, x, y)` is a
pixel's index in `data`; `rt_mark(img, x0, y0, x1, y1)` makes the tiles
over a pixel rectangle dirty. Tiles: `rt_tiles(img)` is their count (row by row), `rt_dirty(img, i)` /
`rt_clean(img, i)`, `rt_tile_w(img, i)` and `rt_tile_h(img, i)` (edge tiles are smaller), `rt_tile_rect(img, i)`
(its world rectangle x0, y0, x1, y1: `rect_t`, four f64), `rt_tile_rgba(img, i, color, out)` (its pixels as opaque
RGBA8 rows over white, `rt_tile_w` wide, into the emptied `bytes` `out`). `rt_rgb8_row(img, color, y, out)` writes
row `y` as RGB8 the same way."""

from ..collections import record_wasm
from ..eco_mb import p
from . import editor_types, raster_color
from ..wasm.kit import Kit, library, stack

FILE = "raster-tiles.atz"
TILE = 256

TYPE_EXPORTS = ["img_t", "img_own", "img_raw", "rect_t"]
EXPORTS = [
    "rt_new",
    "rt_px",
    "rt_mark",
    "rt_tiles",
    "rt_dirty",
    "rt_clean",
    "rt_tile_w",
    "rt_tile_h",
    "rt_tile_rect",
    "rt_tile_rgba",
    "rt_rgb8_row",
]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))


def module(e):
    k = Kit(e)
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        x.append(e.let("rect_t", k.tuple_t(["t_f64"] * 4)))
        return type_names + ["rect_t"]

    def level2(x):
        _imports(e, x)
        fields = [
            ("w", "t_i32"),
            ("h", "t_i32"),
            ("tx", "t_i32"),
            ("ty", "t_i32"),
            ("x0", "t_f64"),
            ("y0", "t_f64"),
            ("mmpp", "t_f64"),
            ("data", "f32s_t"),
            ("dirty", "ints_t"),
        ]
        x.append(
            e.let(
                "img_r",
                e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in fields])))),
            )
        )
        for f in ["t", "own", "raw"]:
            x.append(e.let("img_" + f, e.fld(e.v("img_r"), "type" if f == "t" else f)))
        x.append(e.let("img_make", e.fld(e.v("img_r"), "new")))
        return ["img_t", "img_own", "img_raw", "img_make"]

    x, names = stack(e, k, [level1, level2])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(e.let("color", e.import_local("color", raster_color.FILE)))
    x.append(e.let("color_raw", e.fld(e.v("color"), "color_raw")))
    v = e.v

    def C(fn, *args):
        return k.lib("color", fn, *args)

    def g(name):
        return e.fld(v("img"), name)

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def u8(val):
        return k.m(k.trunc(val), "wrap", k.lo("t_u8"))

    def f32(val):
        return e.mb.as_(e.n(val), k.lo("t_f32"))

    k.dep(
        x,
        "rt_new",
        ["w", "h", "x0", "y0", "mmpp"],
        ["t_i32", "t_i32", "t_f64", "t_f64", "t_f64"],
        "img_t",
        e.seq(
            e.let("data", k.call("f32s_new", e.tup())),
            k.for_("i", 0, k.mul(k.mul(v("w"), v("h")), e.n(4)), "pixels", k.m(v("data"), "push", f32(0))),
            e.let("tx", k.div(k.add(v("w"), e.n(TILE - 1)), e.n(TILE))),
            e.let("ty", k.div(k.add(v("h"), e.n(TILE - 1)), e.n(TILE))),
            e.let("dirty", k.call("ints_new", e.tup())),
            k.for_("i", 0, k.mul(v("tx"), v("ty")), "tiles", k.m(v("dirty"), "push", k.i32(1))),
            e.ret(
                k.call(
                    "img_make",
                    e.rec(
                        p("w", v("w")),
                        p("h", v("h")),
                        p("tx", v("tx")),
                        p("ty", v("ty")),
                        p("x0", v("x0")),
                        p("y0", v("y0")),
                        p("mmpp", v("mmpp")),
                        p("data", k.m(v("data"), "move", e.tup())),
                        p("dirty", k.m(v("dirty"), "move", e.tup())),
                    ),
                )
            ),
        ),
    )
    k.dep(
        x,
        "rt_px",
        ["img", "x", "y"],
        ["img_raw", "t_i32", "t_i32"],
        "t_i32",
        e.ret(k.mul(k.add(k.mul(v("y"), g("w")), v("x")), e.n(4))),
    )

    def clamp_i(val, lo, hi):
        return k.ifelse(k.lt(val, lo), lo, k.ifelse(k.gt(val, hi), hi, val))

    k.dep(
        x,
        "rt_mark",
        ["img", "x0", "y0", "x1", "y1"],
        ["img_raw"] + ["t_i32"] * 4,
        "t_void",
        e.seq(
            e.let("ta", clamp_i(k.div(v("x0"), e.n(TILE)), k.i32(0), k.sub(g("tx"), e.n(1)))),
            e.let("tb", clamp_i(k.div(v("x1"), e.n(TILE)), k.i32(0), k.sub(g("tx"), e.n(1)))),
            e.let("tc", clamp_i(k.div(v("y0"), e.n(TILE)), k.i32(0), k.sub(g("ty"), e.n(1)))),
            e.let("td", clamp_i(k.div(v("y1"), e.n(TILE)), k.i32(0), k.sub(g("ty"), e.n(1)))),
            e.let("dirty", raw(g("dirty"), "ints")),
            k.for_(
                "j",
                v("tc"),
                k.add(v("td"), e.n(1)),
                "rows",
                k.for_(
                    "i",
                    v("ta"),
                    k.add(v("tb"), e.n(1)),
                    "cols",
                    k.set(k.m(v("dirty"), "at", k.add(k.mul(v("j"), g("tx")), v("i"))), k.i32(1)),
                ),
            ),
        ),
    )
    k.dep(x, "rt_tiles", ["img"], ["img_raw"], "t_i32", e.ret(k.mul(g("tx"), g("ty"))))
    k.dep(x, "rt_dirty", ["img", "i"], ["img_raw", "t_i32"], "t_i32", e.ret(k.m(g("dirty"), "at", v("i"))))
    k.dep(x, "rt_clean", ["img", "i"], ["img_raw", "t_i32"], "t_void", k.set(k.m(g("dirty"), "at", v("i")), k.i32(0)))

    def tile_x(i):
        return k.mul(k.rem(i, g("tx")), e.n(TILE))

    def tile_y(i):
        return k.mul(k.div(i, g("tx")), e.n(TILE))

    k.dep(
        x,
        "rt_tile_w",
        ["img", "i"],
        ["img_raw", "t_i32"],
        "t_i32",
        e.ret(k.ifelse(k.gt(k.add(tile_x(v("i")), e.n(TILE)), g("w")), k.sub(g("w"), tile_x(v("i"))), k.i32(TILE))),
    )
    k.dep(
        x,
        "rt_tile_h",
        ["img", "i"],
        ["img_raw", "t_i32"],
        "t_i32",
        e.ret(k.ifelse(k.gt(k.add(tile_y(v("i")), e.n(TILE)), g("h")), k.sub(g("h"), tile_y(v("i"))), k.i32(TILE))),
    )
    k.dep(
        x,
        "rt_tile_rect",
        ["img", "i"],
        ["img_raw", "t_i32"],
        "rect_t",
        e.ret(
            e.mb.as_(
                e.tup(
                    k.add(g("x0"), k.mul(k.to_f64(tile_x(v("i"))), g("mmpp"))),
                    k.add(g("y0"), k.mul(k.to_f64(tile_y(v("i"))), g("mmpp"))),
                    k.add(
                        g("x0"),
                        k.mul(k.to_f64(k.add(tile_x(v("i")), k.dcall("rt_tile_w", v("img"), v("i")))), g("mmpp")),
                    ),
                    k.add(
                        g("y0"),
                        k.mul(k.to_f64(k.add(tile_y(v("i")), k.dcall("rt_tile_h", v("img"), v("i")))), g("mmpp")),
                    ),
                ),
                k.lo("rect_t"),
            )
        ),
    )

    def push_rgb(out, px_index, alpha):
        """Pushes a pixel's display bytes (and 255 when `alpha`)."""
        return e.seq(
            e.let("rgb", k.m(v("color"), "rgb", e.tup(raw(g("data"), "f32s"), px_index))),
            *[k.m(out, "push", u8(C("rc_srgb", e.mb.field(v("rgb"), e.n(c))))) for c in range(3)],
            *([k.m(out, "push", e.mb.as_(e.n(255), k.lo("t_u8")))] if alpha else []),
        )

    k.dep(
        x,
        "rt_tile_rgba",
        ["img", "i", "color", "out"],
        ["img_raw", "t_i32", "color_raw", "bytes_raw"],
        "t_void",
        e.seq(
            k.m(v("out"), "clear", e.tup()),
            e.let("tw", k.dcall("rt_tile_w", v("img"), v("i"))),
            e.let("th", k.dcall("rt_tile_h", v("img"), v("i"))),
            e.let("ox", tile_x(v("i"))),
            e.let("oy", tile_y(v("i"))),
            k.for_(
                "yy",
                0,
                v("th"),
                "rows",
                k.for_(
                    "xx",
                    0,
                    v("tw"),
                    "cols",
                    push_rgb(
                        v("out"), k.dcall("rt_px", v("img"), k.add(v("ox"), v("xx")), k.add(v("oy"), v("yy"))), True
                    ),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "rt_rgb8_row",
        ["img", "color", "y", "out"],
        ["img_raw", "color_raw", "t_i32", "bytes_raw"],
        "t_void",
        e.seq(
            k.m(v("out"), "clear", e.tup()),
            k.for_("xx", 0, g("w"), "cols", push_rgb(v("out"), k.dcall("rt_px", v("img"), v("xx"), v("y")), False)),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
