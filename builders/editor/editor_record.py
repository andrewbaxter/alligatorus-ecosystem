"""editor-record.atz: recording stylus strokes on an editor-canvas.atz area (wat target; dependencies, typed with the
ecosystem's libraries).

A stroke is an entry of the document's section the recorder registers (id: the stroke's, in recording order):
`{"s": [[t, x, y, pressure, tilt_x, tilt_y, twist, tangential, altitude, azimuth, width, height], ...]}`, a sample
per pointer event (the coalesced ones included): `t` ms (the event's time), `x`, `y` world mm, then the pointer's
fields (pressure 0..1, tilts and twist in degrees, angles in radians, contact size in CSS pixels). In memory a
stroke is a record (`stroke_t`, `stroke_raw`) of its `id`, its `stamp` and one `f64s` column per field (`CHANNELS`,
the field names: `s.x`, `s.pressure`, ...; `s.t.len` is the sample count).

The recorder is an owned record (`rc_t`, `rc_raw`): `rec_new(st, key)` makes one on the store `st`
(borrowed: the store outlives it) with the section `key`, yielding the owned record (with its
strokes). `rec_pointer(rc, cv, ev, kind)` takes a pointer event of the canvas `cv` (kind 0 down, 1 move, 2 up):
the primary button starts a stroke, moves add samples, and the release puts it in the document and is its id (else
0; the editor commits then). `rec_sync(rc)` follows the document; `rec_clear(rc)` removes every stroke. Strokes, in
id order: `rec_count(rc)`, `rec_id(rc, i)`, `rec_stroke(rc, i)` (the raw record, valid until the next sync),
`rec_stamp(rc, i)` (changes whenever the stroke does), `rec_find(rc, id)` (negative: none). `rec_draw(rc, cv,
alpha)` draws them, and the stroke being recorded. `rec_channel_at(s, c, j)` is sample `j` of column `c` (an index
in `CHANNELS`) of the stroke `s`."""

from ..collections import record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_canvas, editor_json, editor_state, editor_types, editor_ui
from ..wasm.kit import Kit, library, stack

FILE = "editor-record.atz"

CHANNELS = [
    "t",
    "x",
    "y",
    "pressure",
    "tilt_x",
    "tilt_y",
    "twist",
    "tangential",
    "altitude",
    "azimuth",
    "width",
    "height",
]

HOOKS = [
    ("h_pressure", "get", "PointerEvent", "pressure"),
    ("h_tilt_x", "get", "PointerEvent", "tiltX"),
    ("h_tilt_y", "get", "PointerEvent", "tiltY"),
    ("h_twist", "get", "PointerEvent", "twist"),
    ("h_tangential", "get", "PointerEvent", "tangentialPressure"),
    ("h_altitude", "get", "PointerEvent", "altitudeAngle"),
    ("h_azimuth", "get", "PointerEvent", "azimuthAngle"),
    ("h_width", "get", "PointerEvent", "width"),
    ("h_height", "get", "PointerEvent", "height"),
    ("h_coalesced", "op", "PointerEvent", "getCoalescedEvents"),
    ("h_button", "get", "MouseEvent", "button"),
    ("h_time", "get", "Event", "timeStamp"),
    ("h_seq_len", "intrinsic", "", "seq_len"),
    ("h_seq_get", "intrinsic", "", "seq_get"),
]
HANDLES = [("event", "Event"), ("mouse", "MouseEvent"), ("pointer", "PointerEvent")]
UI_TYPES = ["event_raw"]
CANVAS_TYPES = ["cv_raw"]

TEXTS = {"j_open": '{"s":[', "j_close": "]}", "k_s": "s"}

TYPE_EXPORTS = ["rc_t", "rc_raw", "stroke_raw"]
EXPORTS = [
    "rec_new",
    "rec_pointer",
    "rec_sync",
    "rec_clear",
    "rec_count",
    "rec_id",
    "rec_stroke",
    "rec_stamp",
    "rec_find",
    "rec_channel_at",
    "rec_draw",
]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("idmap", e.import_local("idmap", "idmap-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("canvas", e.import_local("canvas", editor_canvas.FILE)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))


def _record(e, x, name, fields):
    """A record type `name` over `fields` (name, type binding): binds `<name>_t/_own/_raw/_make`."""
    x.append(
        e.let(
            name + "_r",
            e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in fields])))),
        )
    )
    for f in ["t", "raw"]:
        x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    x.append(e.let(name + "_make", e.fld(e.v(name + "_r"), "new")))
    return [name + "_" + f for f in ["t", "raw", "make"]]


def module(e):
    k = Kit(e)

    # The vec constructors (dependency function values) are bound at the top from the import, not passed through the
    # levels' records.
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        for n in UI_TYPES:
            x.append(e.let(n, e.fld(e.v("ui"), n)))
        for n in CANVAS_TYPES:
            x.append(e.let(n, e.fld(e.v("canvas"), n)))
        x.append(e.let("st_raw", e.fld(e.v("state"), "st_raw")))
        for pre, iface in HANDLES:
            x.append(e.let("h_" + pre, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))
            for f in ["raw", "own"]:
                x.append(e.let(pre + "_" + f, e.fld(e.v("h_" + pre), f)))
        return (
            list(type_names)
            + UI_TYPES
            + CANVAS_TYPES
            + ["st_raw"]
            + [pre + "_" + f for pre, _ in HANDLES for f in ["raw", "own"]]
        )

    def level2(x):
        _imports(e, x)
        return _record(e, x, "stroke", [("id", "t_i32"), ("stamp", "t_i32")] + [(c, "f64s_t") for c in CHANNELS])

    def level3(x):
        _imports(e, x)
        x.append(e.let("strokes_r", e.call(e.fld(e.v("idmap"), "type"), e.v("stroke_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("strokes_" + f, e.fld(e.v("strokes_r"), "type" if f == "t" else f)))
        return ["strokes_" + f for f in ["t", "own", "raw", "new"]]

    def level4(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "rc",
            [
                ("st", "st_raw"),
                ("sec", "t_i32"),
                ("strokes", "strokes_t"),
                ("live", "stroke_t"),
                ("drawing", "t_i32"),
                ("stamp", "t_i32"),
                ("buf", "bytes_t"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3, level4])
    x.append(e.let("json", e.import_local("json", editor_json.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(e.let("canvas", e.import_local("canvas", editor_canvas.FILE)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    for bind, kind, iface, member in HOOKS:
        x.append(
            e.let(bind, e.call(e.fld(e.v("webidl"), kind), e.rec(p("iface", e.s(iface)), p("member", e.s(member)))))
        )
    for name, text in TEXTS.items():
        k.text(x, name, text)
    v = e.v

    def J(f, *args):
        return k.lib("json", f, *args)

    def S(f, *args):
        return k.lib("state", f, *args)

    def T(f, *args):
        return k.lib("types", f, *args)

    def C(f, *args):
        return k.lib("canvas", f, *args)

    def raw(borrow, name):
        """A borrow (an owned field or element, which cannot be bound) as its raw type `<name>_raw`, for binding."""
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def down(pre, val):
        """`val` (a raw handle) downcast to `pre`'s raw handle type."""
        return e.mb.as_(e.mb.as_(val, k.lo("t_i32")), k.lo(pre + "_raw"))

    def r(name):
        return e.fld(v("rc"), name)

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def to64(val):
        return e.mb.as_(val, k.lo("t_f64"))

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def new_stroke(id_):
        """A new stroke record (raw) with the id `id_` and empty columns."""
        return k.call(
            "stroke_make",
            e.rec(p("id", id_), p("stamp", k.i32(0)), *[p(c, k.call("f64s_new", e.tup())) for c in CHANNELS]),
        )

    def column(s, c):
        """The column `c` of the stroke `s` (a raw record), a borrow of its `f64s`."""
        return e.fld(s, c)

    def clear_stroke(s):
        return e.seq(*[k.m(column(s, c), "clear", e.tup()) for c in CHANNELS])

    k.dep(
        x,
        "rec_new",
        ["st", "key"],
        ["st_raw", "str_t"],
        "rc_t",
        e.ret(
            k.call(
                "rc_make",
                e.rec(
                    p("st", v("st")),
                    p("sec", S("st_section", v("st"), v("key"))),
                    p("strokes", k.call("strokes_new", e.tup())),
                    p("live", new_stroke(k.i32(0))),
                    p("drawing", k.i32(0)),
                    p("stamp", k.i32(0)),
                    p("buf", k.call("bytes_new", e.tup())),
                ),
            )
        ),
    )
    # One sample of the pointer event `ev` appended to the live stroke.
    k.dep(
        x,
        "rec_sample",
        ["rc", "cv", "ev"],
        ["rc_raw", "cv_raw", "event_raw"],
        "t_void",
        e.seq(
            e.let("live", raw(r("live"), "stroke")),
            e.let("pe", down("pointer", v("ev"))),
            *[
                k.m(column(v("live"), c), "push", val)
                for c, val in zip(
                    CHANNELS,
                    [
                        k.call("h_time", v("ev")),
                        C("cv_wx", v("cv"), v("ev")),
                        C("cv_wy", v("cv"), v("ev")),
                        to64(k.call("h_pressure", v("pe"))),
                        k.to_f64(k.call("h_tilt_x", v("pe"))),
                        k.to_f64(k.call("h_tilt_y", v("pe"))),
                        k.to_f64(k.call("h_twist", v("pe"))),
                        to64(k.call("h_tangential", v("pe"))),
                        k.call("h_altitude", v("pe")),
                        k.call("h_azimuth", v("pe")),
                        k.call("h_width", v("pe")),
                        k.call("h_height", v("pe")),
                    ],
                )
            ],
        ),
    )
    k.dep(
        x,
        "rec_pointer",
        ["rc", "cv", "ev", "kind"],
        ["rc_raw", "cv_raw", "event_raw", "t_i32"],
        "t_i32",
        e.seq(
            e.let("live", raw(r("live"), "stroke")),
            k.if_(
                k.eq(v("kind"), e.n(0)),
                k.if_(
                    k.ne(e.mb.as_(k.call("h_button", down("mouse", v("ev"))), k.lo("t_i32")), e.n(0)), k.ret(k.i32(0))
                ),
                k.set(r("drawing"), e.n(1)),
                clear_stroke(v("live")),
                C("cv_capture", v("cv"), v("ev")),
                k.dcall("rec_sample", v("rc"), v("cv"), v("ev")),
                k.ret(k.i32(0)),
            ),
            k.if_(k.eq(r("drawing"), e.n(0)), k.ret(k.i32(0))),
            # A move carries its coalesced events (none: the event itself); the sequence and each event are
            # handles released when their bindings drop.
            e.let("seq", k.call("h_coalesced", down("pointer", v("ev")))),
            e.let("n", k.m(k.call("h_seq_len", v("seq")), "wrap", k.lo("t_i32"))),
            k.ifelse(
                k.eq(v("n"), e.n(0)),
                k.dcall("rec_sample", v("rc"), v("cv"), v("ev")),
                k.for_(
                    "i",
                    0,
                    v("n"),
                    "coalesced",
                    e.let("one", k.call("h_seq_get", v("seq"), k.m(v("i"), "wrap", k.lo("t_u32")))),
                    k.dcall("rec_sample", v("rc"), v("cv"), down("event", v("one"))),
                ),
            ),
            k.if_(k.ne(v("kind"), e.n(2)), k.ret(k.i32(0))),
            k.set(r("drawing"), e.n(0)),
            # The stroke into the document.
            e.let("id", S("st_next_id", r("st"), r("sec"))),
            e.let("buf", raw(r("buf"), "bytes")),
            k.m(v("buf"), "clear", e.tup()),
            J("jw_text", v("buf"), ts("j_open")),
            k.for_(
                "j",
                0,
                e.fld(column(v("live"), "t"), "len"),
                "samples",
                k.if_(k.gt(v("j"), e.n(0)), J("jw_byte", v("buf"), e.n(ord(",")))),
                J("jw_byte", v("buf"), e.n(ord("["))),
                *[
                    e.seq(
                        *([J("jw_byte", v("buf"), e.n(ord(",")))] if ci > 0 else []),
                        e.let("val", k.m(column(v("live"), c), "at", v("j"))),
                        # a field the device doesn't give (NaN) is 0
                        J("jw_num", v("buf"), k.ifelse(k.ne(v("val"), v("val")), k.f64(0), v("val"))),
                    )
                    for ci, c in enumerate(CHANNELS)
                ],
                J("jw_byte", v("buf"), e.n(ord("]"))),
            ),
            J("jw_text", v("buf"), ts("j_close")),
            S("st_put", r("st"), r("sec"), v("id"), v("buf")),
            clear_stroke(v("live")),
            e.ret(v("id")),
        ),
    )
    k.dep(
        x,
        "rec_find",
        ["rc", "id"],
        ["rc_raw", "t_i32"],
        "t_i32",
        e.ret(k.m(raw(r("strokes"), "strokes"), "index_of", v("id"))),
    )
    # The stroke with the id `id` (one the order lists is in the map: a missing one traps).
    k.dep(
        x,
        "rec_stroke_of",
        ["rc", "id"],
        ["rc_raw", "t_i32"],
        "stroke_raw",
        e.match_of(
            k.m(raw(r("strokes"), "strokes"), "get", v("id")),
            "pl",
            None,
            p("some", k.ret(raw(e.mb.field(v("pl"), e.n(0)), "stroke"))),
            p("none", trap()),
        ),
    )
    k.dep(
        x,
        "rec_sync",
        ["rc"],
        ["rc_raw"],
        "t_void",
        e.seq(
            e.let("strokes", raw(r("strokes"), "strokes")),
            k.for_(
                "c",
                0,
                S("st_changed_count", r("st"), r("sec")),
                "changed",
                e.let("id", S("st_changed_at", r("st"), r("sec"), v("c"))),
                e.let("was", k.m(v("strokes"), "remove", v("id"))),
                e.match_of(
                    S("st_get", r("st"), r("sec"), v("id")),
                    "text",
                    None,
                    p(
                        "some",
                        e.seq(
                            e.let("sr", new_stroke(v("id"))),
                            e.let("el", J("jr_first", v("text"), J("jr_field", v("text"), e.n(0), ts("k_s")))),
                            k.loop(
                                "samples",
                                k.if_(k.lt(v("el"), e.n(0)), k.brk("samples")),
                                e.let("fq", J("jr_first", v("text"), v("el"))),
                                *[
                                    e.seq(
                                        k.if_(k.lt(v("fq"), e.n(0)), k.brk("samples")),
                                        k.m(column(v("sr"), c), "push", J("jr_num", v("text"), v("fq"))),
                                        e.mb.set(v("fq"), J("jr_next", v("text"), v("fq"))),
                                    )
                                    for c in CHANNELS
                                ],
                                e.mb.set(v("el"), J("jr_next", v("text"), v("el"))),
                            ),
                            k.set(r("stamp"), k.add(r("stamp"), e.n(1))),
                            k.set(e.fld(v("sr"), "stamp"), r("stamp")),
                            k.m(v("strokes"), "put", e.tup(v("id"), k.m(v("sr"), "move", e.tup()))),
                        ),
                    ),
                    p("none", e.seq()),
                ),
            ),
            S("st_changed_clear", r("st"), r("sec")),
        ),
    )
    k.dep(
        x,
        "rec_clear",
        ["rc"],
        ["rc_raw"],
        "t_void",
        e.seq(
            e.let("strokes", raw(r("strokes"), "strokes")),
            k.for_(
                "i",
                0,
                e.fld(v("strokes"), "len"),
                "all",
                S("st_del", r("st"), r("sec"), k.m(v("strokes"), "id_at", v("i"))),
            ),
        ),
    )
    k.dep(x, "rec_count", ["rc"], ["rc_raw"], "t_i32", e.ret(e.fld(raw(r("strokes"), "strokes"), "len")))
    k.dep(
        x,
        "rec_id",
        ["rc", "i"],
        ["rc_raw", "t_i32"],
        "t_i32",
        e.ret(k.m(raw(r("strokes"), "strokes"), "id_at", v("i"))),
    )
    k.dep(
        x,
        "rec_stroke",
        ["rc", "i"],
        ["rc_raw", "t_i32"],
        "stroke_raw",
        e.ret(k.dcall("rec_stroke_of", v("rc"), k.dcall("rec_id", v("rc"), v("i")))),
    )
    k.dep(
        x,
        "rec_stamp",
        ["rc", "i"],
        ["rc_raw", "t_i32"],
        "t_i32",
        e.ret(e.fld(k.dcall("rec_stroke", v("rc"), v("i")), "stamp")),
    )

    k.dep(
        x,
        "rec_channel_at",
        ["s", "c", "j"],
        ["stroke_raw", "t_i32", "t_i32"],
        "t_f64",
        e.seq(
            *[
                k.if_(k.eq(v("c"), e.n(i)), k.ret(k.m(column(v("s"), name), "at", v("j"))))
                for i, name in enumerate(CHANNELS)
            ],
            trap(),
        ),
    )
    # A stroke's samples as segments whose width follows the pressure (0.2 to 1.2 mm).
    k.dep(
        x,
        "rec_draw_stroke",
        ["s", "cv", "alpha"],
        ["stroke_raw", "cv_raw", "t_f64"],
        "t_void",
        k.for_(
            "j",
            1,
            e.fld(column(v("s"), "t"), "len"),
            "segs",
            e.let("pw", k.add(e.n(0.2), k.m(column(v("s"), "pressure"), "at", v("j")))),
            C("cv_style", v("cv"), v("alpha"), k.mul(v("pw"), C("cv_scale", v("cv")))),
            C(
                "cv_line",
                v("cv"),
                k.m(column(v("s"), "x"), "at", k.sub(v("j"), e.n(1))),
                k.m(column(v("s"), "y"), "at", k.sub(v("j"), e.n(1))),
                k.m(column(v("s"), "x"), "at", v("j")),
                k.m(column(v("s"), "y"), "at", v("j")),
            ),
        ),
    )
    k.dep(
        x,
        "rec_draw",
        ["rc", "cv", "alpha"],
        ["rc_raw", "cv_raw", "t_f64"],
        "t_void",
        e.seq(
            k.for_(
                "i",
                0,
                k.dcall("rec_count", v("rc")),
                "strokes",
                k.dcall("rec_draw_stroke", k.dcall("rec_stroke", v("rc"), v("i")), v("cv"), v("alpha")),
            ),
            k.dcall("rec_draw_stroke", raw(r("live"), "stroke"), v("cv"), v("alpha")),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
