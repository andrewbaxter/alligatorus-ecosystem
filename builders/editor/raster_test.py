"""raster-test.atz: a WASI app checking raster-color.atz, raster-tiles.atz, raster-brush.atz and image-png.atz: a
blue stroke then a yellow one crossing it make green where they cross in the Kubelka-Munk model, and yellow over blue
in the RGB model; the image encodes as a PNG with the right chunks; it prints the index of the first
failed check (exit status 1)."""

import struct
import zlib

from ..wasm import math_wasm
from . import wasi_test, vector_spline, raster_color, raster_tiles, raster_brush, image_png
from .raster_brush import BRUSH_FIELDS

W, H, MMPP = 64, 32, 0.5
BRUSH_VALUES = {
    "radius": 2.0,
    "bristles": 48,
    "bristle": 0.25,
    "deposit": 0.5,
    "pickup": 0.05,
    "reload": 0.3,
    "dry_from": 1e6,
    "dry_to": 2e6,
    "tilt": 0.0,
    "seed": 7,
}
IHDR = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
IHDR_CRC = zlib.crc32(b"IHDR" + IHDR)
PNG_LEN = 8 + (12 + 13) + (12 + 9) + (12 + 2 + 5 + H * (1 + 3 * W) + 4) + 12


def module(e):
    def checks(k):
        v = e.v

        def S(f, *args):
            return k.lib("spline", f, *args)

        def col(rec, name, i):
            return k.m(e.fld(rec, name), "at", i)

        def nat(sp, name, i):
            """The field `name` of node `i` of the spline `sp`."""
            node = e.mb.as_(k.m(e.fld(sp, "nodes"), "at", i), e.lower(e.fld(e.v("spline"), "node_raw")))
            return e.fld(node, name)

        def stroke(name, pts):
            """Statements binding `name` to an owned samples record of the line through `pts`, sampled a quarter
            millimetre apart."""
            out = [e.let(name + "_n", S("sp_new", e.n(0)))]
            for i, (px_, py_) in enumerate(pts):
                out += [
                    e.let("nd", S("sp_push", v(name + "_n"))),
                    k.set(nat(v(name + "_n"), "x", v("nd")), k.f64(px_)),
                    k.set(nat(v(name + "_n"), "y", v("nd")), k.f64(py_)),
                    k.set(nat(v(name + "_n"), "t", v("nd")), k.f64(i * 1000.0)),
                ]
            out += [
                e.let(name + "_s", S("segs_new")),
                S("sp_prepare", v(name + "_n"), v(name + "_s")),
                e.let(name, S("samples_new")),
                S("sp_sample", v(name + "_n"), v(name + "_s"), k.f64(0.25), v(name)),
            ]
            return out

        def paint(model, stroke_name, color):
            """Paints a copy of the stroke `stroke_name` in `color` on `img` with a job of its own."""
            return [
                e.let("st", k.call("f64s_new", e.tup())),
                *[k.m(v("st"), "push", k.f64(c)) for c in color],
                e.let("copy", S("samples_new")),
                *[
                    k.for_(
                        "i",
                        0,
                        e.fld(e.fld(v(stroke_name), c), "len"),
                        "copy_" + c,
                        k.m(e.fld(v("copy"), c), "push", col(v(stroke_name), c, v("i"))),
                    )
                    for c in vector_spline.SAMPLE_COLUMNS + ["seg", "c"]
                ],
                e.let(
                    "job",
                    k.lib(
                        "brush",
                        "br_new",
                        v("img"),
                        k.lib("color", "rc_model", e.n(model)),
                        v("brush"),
                        v("st"),
                        e.n(1),
                        e.n(-1),
                        e.n(-1),
                        e.n(-1),
                        e.n(-1),
                    ),
                ),
                k.lib("brush", "br_stroke", v("job"), k.m(v("copy"), "move", e.tup())),
                k.lib("brush", "br_start", v("job")),
                k.check(k.eq(k.lib("brush", "br_step", v("job"), e.n(3)), e.n(0))),
                k.loop("paint", k.if_(k.ne(k.lib("brush", "br_step", v("job"), e.n(50)), e.n(0)), k.brk("paint"))),
            ]

        def rgb_at(px_, py_):
            return [
                e.let(
                    "rgb",
                    k.m(
                        v("color"),
                        "rgb",
                        e.tup(e.fld(v("img"), "data"), k.lib("tiles", "rt_px", v("img"), e.n(px_), e.n(py_))),
                    ),
                ),
                e.let("r", e.mb.field(v("rgb"), e.n(0))),
                e.let("g", e.mb.field(v("rgb"), e.n(1))),
                e.let("b", e.mb.field(v("rgb"), e.n(2))),
            ]

        def png_byte(i):
            return e.mb.as_(k.m(v("png"), "at", i), k.lo("t_i32"))

        out = [
            e.let("brush", k.lib("brush", "brush_new")),
            *[k.set(e.fld(v("brush"), name), k.f64(BRUSH_VALUES[name])) for name in BRUSH_FIELDS],
            *stroke("horiz", [(2, 8), (30, 8)]),
            *stroke("vert", [(16, 1), (16, 15)]),
        ]
        blue = (0.1, 0.2, 0.9)
        yellow = (0.95, 0.85, 0.1)
        # Kubelka-Munk: blue, then yellow across it: green where they cross, each color alone elsewhere
        out += [
            e.let("model", k.i32(1)),
            e.let("color", k.lib("color", "rc_model", v("model"))),
            e.let("img", k.lib("tiles", "rt_new", e.n(W), e.n(H), k.f64(0), k.f64(0), k.f64(MMPP))),
            *paint(1, "horiz", blue),
            *paint(1, "vert", yellow),
            e.seq(*rgb_at(32, 16), k.check(k.gt(v("g"), v("r"))), k.check(k.gt(v("g"), v("b")))),
            e.seq(*rgb_at(10, 16), k.check(k.gt(v("b"), v("r"))), k.check(k.gt(v("b"), v("g")))),
            e.seq(*rgb_at(32, 4), k.check(k.gt(v("r"), v("b"))), k.check(k.gt(v("g"), v("b")))),
            # bare paper is white
            e.seq(*rgb_at(60, 30), k.check(k.gt(v("r"), e.n(0.9))), k.check(k.gt(v("b"), e.n(0.9)))),
            k.check(k.ne(k.lib("tiles", "rt_dirty", v("img"), e.n(0)), e.n(0))),
            # the PNG of it, row by row
            e.let("png", k.call("bytes_new", e.tup())),
            e.let("pw", k.lib("png", "png_begin", v("png"), e.n(W), e.n(H), k.f64(300))),
            e.let("rowbuf", k.call("bytes_new", e.tup())),
            k.for_(
                "y",
                0,
                e.n(H),
                "rows",
                k.lib("tiles", "rt_rgb8_row", v("img"), v("color"), v("y"), v("rowbuf")),
                k.check(k.eq(e.fld(v("rowbuf"), "len"), e.n(W * 3))),
                k.lib("png", "png_row", v("pw"), k.bytes_str(v("rowbuf"))),
            ),
            k.lib("png", "png_end", k.m(v("pw"), "move", e.tup())),
            k.check(k.eq(e.fld(v("png"), "len"), e.n(PNG_LEN))),
            *[k.check(k.eq(png_byte(e.n(i)), e.n(b))) for i, b in enumerate([137, 80, 78, 71])],
            *[k.check(k.eq(png_byte(e.n(8 + 8 + 13 + i)), e.n(b))) for i, b in enumerate(struct.pack(">I", IHDR_CRC))],
            *[
                k.check(k.eq(png_byte(k.sub(e.fld(v("png"), "len"), e.n(4 - i))), e.n(b)))
                for i, b in enumerate([0xAE, 0x42, 0x60, 0x82])
            ],
        ]
        # RGB: the yellow covers the blue where they cross (a fresh image, assigned over the old one)
        out += [
            e.mb.set(v("img"), k.lib("tiles", "rt_new", e.n(W), e.n(H), k.f64(0), k.f64(0), k.f64(MMPP))),
            e.mb.set(v("model"), e.n(0)),
            e.mb.set(v("color"), k.lib("color", "rc_model", v("model"))),
            *paint(0, "horiz", blue),
            *paint(0, "vert", yellow),
            e.seq(*rgb_at(32, 16), k.check(k.gt(v("r"), v("b"))), k.check(k.gt(v("g"), v("b")))),
        ]
        return out

    return wasi_test.module(
        e,
        [
            ("math", math_wasm.FILE),
            ("spline", vector_spline.FILE),
            ("color", raster_color.FILE),
            ("tiles", raster_tiles.FILE),
            ("brush", raster_brush.FILE),
            ("png", image_png.FILE),
        ],
        checks,
    )
