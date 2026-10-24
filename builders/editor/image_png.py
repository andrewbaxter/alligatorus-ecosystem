"""image-png.atz: PNG files of RGB8 images (wat target; dependencies, typed with the ecosystem's libraries), written
row by row.

`png_begin(out, w, h, dpi)` starts a PNG of `w` x `h` RGB8 pixels appended to the `bytes` `out` (editor-types.atz;
the writer keeps writing into it): the signature, `IHDR` (8-bit truecolor) and `pHYs` (the resolution: `dpi` as
pixels per meter), and yields the writer (owned: `pw_t`). `png_row(pw, row)` adds the next row (a `str` of 3 `w`
bytes, top row first): the rows go through a zlib stream of stored deflate blocks (each row after its filter byte
0, uncompressed), each block of up to 65535 bytes written as its own `IDAT` chunk once full, so the writer holds one
block, never the image. `png_end(pw)` (taking the writer) writes the last block, the Adler-32 and `IEND`; a row of
the wrong length, one too many or too few trap."""

from ..collections import record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_types
from ..wasm.kit import Kit, library, stack

FILE = "image-png.atz"
STORED_MAX = 65535
SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10]

TYPE_EXPORTS = ["pw_t"]
EXPORTS = ["png_begin", "png_row", "png_end"]
# The writer: the output, the image's size, the rows written, the block being filled, the Adler-32 state, whether
# the zlib header is still to come.
WRITER_FIELDS = [
    ("out", "bytes_raw"),
    ("w", "t_i32"),
    ("h", "t_i32"),
    ("rows", "t_i32"),
    ("block", "bytes_t"),
    ("ad_a", "t_i32"),
    ("ad_b", "t_i32"),
    ("first", "t_i32"),
]


def _crc_table():
    out = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if c & 1 else (c >> 1)
        out.append(c)
    return out


def module(e):
    k = Kit(e)
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]

    def level1(x):
        x.append(e.let("types", e.import_local("types", editor_types.FILE)))
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        return type_names

    def level2(x):
        x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
        x.append(
            e.let(
                "pw_r",
                e.call(
                    e.fld(e.v("record"), "type"),
                    e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in WRITER_FIELDS]))),
                ),
            )
        )
        x.append(e.let("pw_t", e.fld(e.v("pw_r"), "type")))
        x.append(e.let("pw_raw", e.fld(e.v("pw_r"), "raw")))
        x.append(e.let("pw_make", e.fld(e.v("pw_r"), "new")))
        return ["pw_t", "pw_raw", "pw_make"]

    x, names = stack(e, k, [level1, level2])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(
        e.let(
            "crc_table",
            e.call(
                e.fld(e.v("wasm"), "data_dep"),
                e.rec(
                    p("name", e.s("png_crc_table")),
                    p("elem", e.v("t_i32")),
                    p("values", e.tup(*[e.n(c - (1 << 32) if c >= 1 << 31 else c) for c in _crc_table()])),
                ),
            ),
        )
    )
    v = e.v

    def setv(name, val):
        return e.mb.set(v(name), val)

    def put(a, val):
        """One byte: the low 8 bits of the i32 `val` (a python int: a constant byte)."""
        if isinstance(val, int):
            return k.m(a, "push", e.mb.as_(e.n(val & 0xFF), k.lo("t_u8")))
        return k.m(a, "push", k.m(k.band(val, e.n(0xFF)), "wrap", k.lo("t_u8")))

    def be32(a, val):
        """A big-endian 32-bit i32 value (an expression read four times: a binding or a constant)."""
        return e.seq(*[put(a, k.ushr(val, e.n(sh))) for sh in [24, 16, 8, 0]])

    def text(a, s):
        return e.seq(*[put(a, ord(ch)) for ch in s])

    def byte_at(a, i):
        return e.mb.as_(k.m(a, "at", i), k.lo("t_i32"))

    k.dep(
        x,
        "png_crc",
        ["s"],
        ["str_t"],
        "t_i32",
        e.seq(
            e.let("table", e.call(fn_of(e, k.lo("crc_table")), e.tup())),
            e.let("c", k.i32(-1)),
            k.for_(
                "i",
                0,
                e.fld(v("s"), "len"),
                "bytes",
                e.let("ix", k.band(e.mb.operator_xor(v("c"), byte_at(v("s"), v("i"))), e.n(0xFF))),
                setv("c", e.mb.operator_xor(e.mb.field(v("table"), v("ix")), k.ushr(v("c"), e.n(8)))),
            ),
            e.ret(e.mb.operator_xor(v("c"), e.n(-1))),
        ),
    )

    def chunk(a, kind, *data):
        """A chunk: the length (patched in once the data is written), the type, the data, the CRC of type and
        data."""
        return e.seq(
            e.let("len_at", e.mb.as_(e.fld(a, "len"), k.lo("t_i32"))),
            be32(a, k.i32(0)),
            e.let("type_at", e.mb.as_(e.fld(a, "len"), k.lo("t_i32"))),
            text(a, kind),
            *data,
            e.let("dlen", k.sub(k.sub(e.fld(a, "len"), v("type_at")), e.n(4))),
            *[
                k.set(
                    k.m(a, "at", k.add(v("len_at"), e.n(i))),
                    k.m(k.band(k.ushr(v("dlen"), e.n(sh)), e.n(0xFF)), "wrap", k.lo("t_u8")),
                )
                for i, sh in enumerate([24, 16, 8, 0])
            ],
            # bound first: `be32` reads its value four times, and the buffer grows as it writes
            e.let(
                "crc",
                k.dcall(
                    "png_crc",
                    k.str_of(
                        k.ptr_of(k.add(k.addr(e.fld(a, "data")), v("type_at")), "t_pu8"),
                        k.sub(e.fld(a, "len"), v("type_at")),
                    ),
                ),
            ),
            be32(a, v("crc")),
        )

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def pw(name):
        return e.fld(v("pw"), name)

    k.dep(
        x,
        "png_begin",
        ["out", "w", "h", "dpi"],
        ["bytes_raw", "t_i32", "t_i32", "t_f64"],
        "pw_t",
        e.seq(
            *[put(v("out"), b_) for b_ in SIGNATURE],
            chunk(
                v("out"),
                "IHDR",
                be32(v("out"), v("w")),
                be32(v("out"), v("h")),
                put(v("out"), 8),
                put(v("out"), 2),
                put(v("out"), 0),
                put(v("out"), 0),
                put(v("out"), 0),
            ),
            e.let("ppm", k.trunc(k.floor(k.add(k.div(v("dpi"), e.n(0.0254)), e.n(0.5))))),
            chunk(v("out"), "pHYs", be32(v("out"), v("ppm")), be32(v("out"), v("ppm")), put(v("out"), 1)),
            e.ret(
                k.call(
                    "pw_make",
                    e.rec(
                        p("out", v("out")),
                        p("w", v("w")),
                        p("h", v("h")),
                        p("rows", k.i32(0)),
                        p("block", k.call("bytes_new", e.tup())),
                        p("ad_a", k.i32(1)),
                        p("ad_b", k.i32(0)),
                        p("first", k.i32(1)),
                    ),
                )
            ),
        ),
    )
    # The block so far as an IDAT chunk (the zlib header before the first; the Adler-32 after the last).
    k.dep(
        x,
        "png_flush",
        ["pw", "last"],
        ["pw_raw", "t_i32"],
        "t_void",
        e.seq(
            e.let("o", pw("out")),
            e.let("blk", e.mb.as_(pw("block"), k.lo("bytes_raw"))),
            e.let("n", e.mb.as_(e.fld(v("blk"), "len"), k.lo("t_i32"))),
            chunk(
                v("o"),
                "IDAT",
                k.if_(k.ne(pw("first"), e.n(0)), put(v("o"), 0x78), put(v("o"), 0x01), k.set(pw("first"), k.i32(0))),
                put(v("o"), v("last")),
                put(v("o"), v("n")),
                put(v("o"), k.ushr(v("n"), e.n(8))),
                put(v("o"), e.mb.operator_xor(v("n"), e.n(0xFFFF))),
                put(v("o"), k.ushr(e.mb.operator_xor(v("n"), e.n(0xFFFF)), e.n(8))),
                k.for_("i", 0, v("n"), "copy", k.m(v("o"), "push", k.m(v("blk"), "at", v("i")))),
                k.if_(k.ne(v("last"), e.n(0)), be32(v("o"), k.bor(k.shl(pw("ad_b"), e.n(16)), pw("ad_a")))),
            ),
            k.m(v("blk"), "clear", e.tup()),
        ),
    )

    def take(b):
        """One byte of the filtered stream (an i32 expression) into the block and the Adler-32; a full block goes
        out."""
        return e.seq(
            e.let("b", b),
            k.m(v("blk"), "push", k.m(v("b"), "wrap", k.lo("t_u8"))),
            k.set(pw("ad_a"), k.rem(k.add(pw("ad_a"), v("b")), e.n(65521))),
            k.set(pw("ad_b"), k.rem(k.add(pw("ad_b"), pw("ad_a")), e.n(65521))),
            k.if_(k.eq(e.fld(v("blk"), "len"), e.n(STORED_MAX)), k.dcall("png_flush", v("pw"), k.i32(0))),
        )

    k.dep(
        x,
        "png_row",
        ["pw", "row"],
        ["pw_raw", "str_t"],
        "t_void",
        e.seq(
            k.if_(k.ne(e.fld(v("row"), "len"), k.mul(pw("w"), e.n(3))), trap()),
            k.if_(k.ge(pw("rows"), pw("h")), trap()),
            e.let("blk", e.mb.as_(pw("block"), k.lo("bytes_raw"))),
            take(k.i32(0)),
            k.for_("i", 0, e.fld(v("row"), "len"), "row", take(byte_at(v("row"), v("i")))),
            k.set(pw("rows"), k.add(pw("rows"), e.n(1))),
        ),
    )
    k.dep(
        x,
        "png_end",
        ["pw"],
        ["pw_t"],
        "t_void",
        e.seq(
            k.if_(k.ne(pw("rows"), pw("h")), trap()),
            k.dcall("png_flush", v("pw"), k.i32(1)),
            chunk(pw("out"), "IEND"),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
