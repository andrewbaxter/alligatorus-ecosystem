"""editor-raster.atz: painting the edited splines with a bristle brush into an image, and the PNG of it (wat target;
dependencies over raster-brush.atz, typed with the ecosystem's libraries).

The settings are entry 0 of the document's section the layer registers: `{"dpi": d, "model": 0|1, "c": [r, g, b,
r, g, b, r, g, b], "b": [radius, bristles, bristle, deposit, pickup, reload, dry_from, dry_to, tilt, seed], "out":
"path"}`: the resolution, the color model (raster-color.atz: RGB or Kubelka-Munk), three inks the brush runs
through over the strokes, the brush (raster-brush.atz's fields) and the PNG's path (from the ide's directory).

Every change upstream or of the settings starts the painting over at full resolution once nothing has changed for
DEBOUNCE_MS: the image covers the strokes and the brush's reach; the painting runs a few milliseconds each frame
(abandoned for a fresh one when something changes on the way), and the painted tiles show as they are done. When
it is done the PNG is ready.

The layer is an owned record (`rs_t`, `rs_raw`) owning its image, job, textures, buffers and controls:
`rs_new(st, key, ch_pressure, ch_speed, ch_tilt_x, ch_tilt_y, parent, changed)` makes it (owned; the `ch_*`: the
splines' channel slots, -1: none) with its controls in `parent`, each handled by a closure the layer owns (capturing
it), which writes the settings and then calls the editor's callable `changed` (editor-ui.atz `ev_cb`, owned) with the
event. `rs_sync(rs)` follows the document. Each
frame `rs_frame(rs, ed, cv)` paints (editor-spline.atz's splines; the tiles shown on the canvas `cv`) and is 1 when
a PNG is ready: `rs_png(rs)` and `rs_path(rs)` (`str` views; the editor writes it, then calls `rs_written(rs,
status)`). `rs_draw(rs, cv, alpha)` shows the image."""

from ..collections import closure_wasm, record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import (
    editor_canvas,
    editor_json,
    editor_spline,
    editor_state,
    editor_types,
    editor_ui,
    image_png,
    raster_brush,
    raster_color,
    raster_tiles,
    vector_spline,
)
from ..wasm.kit import Kit, library, stack
from .raster_brush import BRUSH_FIELDS
from .vector_spline import CTRL_COLUMNS

FILE = "editor-raster.atz"
DEBOUNCE_MS = 300.0
SLICE_MS = 10.0
MAX_PIXELS = 40_000_000

DEFAULTS = {
    "dpi": 300.0,
    "model": raster_color.KM,
    "c": [0.12, 0.25, 0.75, 0.80, 0.15, 0.30, 0.95, 0.80, 0.10],
    "b": [3.0, 64.0, 0.12, 0.15, 0.04, 0.25, 150.0, 600.0, 0.5, 1.0],
    "out": "calligraphy.png",
}
# The brush controls: (field, label, min, max, step).
BRUSH_CONTROLS = [
    ("radius", "Brush radius (mm)", 0.5, 15, 0.1),
    ("bristles", "Bristles", 4, 512, 1),
    ("bristle", "Bristle size", 0.03, 0.5, 0.01),
    ("deposit", "Ink flow", 0.01, 1, 0.01),
    ("pickup", "Pick up", 0, 0.5, 0.01),
    ("reload", "Reload", 0, 1, 0.01),
    ("tilt", "Tilt", 0, 2, 0.05),
    ("dry_from", "Dries from (mm/s)", 10, 2000, 10),
    ("dry_to", "Dry at (mm/s)", 10, 4000, 10),
]
STATE_IDLE, STATE_WAITING, STATE_PAINTING, STATE_READY = range(4)

TEXTS = {
    "t_dpi": "Resolution (dpi)",
    "t_model": "Ink mixing",
    "t_rgb": "RGB (paint over)",
    "t_km": "Pigment (Kubelka-Munk)",
    "t_ink0": "First ink",
    "t_ink1": "Middle ink",
    "t_ink2": "Last ink",
    "t_out": "Output file",
    "t_div": "div",
    "c_status": "ed_status",
    "s_waiting": "Waiting for changes to settle",
    "s_painting": "Painting ",
    "s_percent": "%",
    "s_ready": "Painted; saving",
    "s_saved": "Saved ",
    "s_failed": "Saving failed: ",
    "s_large": "The image would be too large at this resolution",
    "s_empty": "Nothing to paint",
    "k_dpi": "dpi",
    "k_model": "model",
    "k_c": "c",
    "k_b": "b",
    "k_out": "out",
    "j_dpi": '{"dpi":',
    "j_model": ',"model":',
    "j_c": ',"c":[',
    "j_b": '],"b":[',
    "j_out": '],"out":',
    "d_out": DEFAULTS["out"],
    **{"l_" + field: label for field, label, *_ in BRUSH_CONTROLS},
}
UI_TYPES = [
    "node_raw",
    "input_raw",
    "select_raw",
    "el_t",
    "el_own",
    "inputw_t",
    "inputw_own",
    "selectw_t",
    "selectw_own",
    "ev_cb_t",
    "rgb_t",
]

TYPE_EXPORTS = ["rs_t"]
EXPORTS = ["rs_new", "rs_sync", "rs_frame", "rs_png", "rs_path", "rs_written", "rs_draw"]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("canvas", e.import_local("canvas", editor_canvas.FILE)))
    x.append(e.let("edit", e.import_local("edit", editor_spline.FILE)))
    x.append(e.let("spline", e.import_local("spline", vector_spline.FILE)))
    x.append(e.let("tiles", e.import_local("tiles", raster_tiles.FILE)))
    x.append(e.let("brush", e.import_local("brush", raster_brush.FILE)))
    x.append(e.let("color", e.import_local("color", raster_color.FILE)))


def _record(e, x, name, fields):
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


LIB_TYPES = [
    ("canvas", ["cv_raw", "tex_t", "tex_own", "tex_raw"]),
    ("edit", ["ed_raw", "eff_raw"]),
    ("spline", ["samples_t", "samples_own", "samples_raw", "segs_raw", "spline_raw"]),
    ("tiles", ["img_t", "img_own", "img_raw", "rect_t"]),
    ("brush", ["brush_t", "brush_own", "brush_raw", "job_t", "job_own", "job_raw"]),
    ("color", ["color_t"]),
    ("state", ["st_raw"]),
]


def module(e):
    k = Kit(e)
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        for n in UI_TYPES:
            x.append(e.let(n, e.fld(e.v("ui"), n)))
        for lib, ns in LIB_TYPES:
            for n in ns:
                x.append(e.let(n, e.fld(e.v(lib), n)))
        return type_names + UI_TYPES + [n for _, ns in LIB_TYPES for n in ns]

    def level2(x):
        _imports(e, x)
        names = []
        for name, elem in [
            ("texs", "tex_t"),
            ("inputws", "inputw_t"),
            ("selectws", "selectw_t"),
            ("ev_cbs", "ev_cb_t"),
        ]:
            x.append(e.let(name + "_r", e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
            for f in ["t", "own", "raw", "new"]:
                x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
            names += [name + "_" + f for f in ["t", "own", "raw", "new"]]
        # the image and the job of the painting under way, none between paintings
        x.append(e.let("option", e.import_local("option", "option-wasm.atz")))
        for name, elem in [("img_opt", "img_t"), ("job_opt", "job_t")]:
            x.append(e.let(name + "_r", e.call(e.fld(e.v("option"), "type"), e.v(elem))))
            for f in ["t", "some", "none"]:
                x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
            names += [name + "_" + f for f in ["t", "some", "none"]]
        return names

    def level3(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "rs",
            [
                ("st", "st_raw"),
                ("sec", "t_i32"),
                ("img", "img_opt_t"),
                ("job", "job_opt_t"),
                ("state", "t_i32"),
                ("seen", "t_i32"),
                ("model", "t_i32"),
                ("color", "color_t"),
                ("texs", "texs_t"),
                ("tilebuf", "bytes_t"),
                ("png", "bytes_t"),
                ("path", "bytes_t"),
                ("stops", "f64s_t"),
                ("brush", "brush_t"),
                ("buf", "bytes_t"),
                ("status", "el_t"),
                ("inputs", "inputws_t"),
                ("selects", "selectws_t"),
                ("c_ink", "inputws_t"),
                ("r_brush", "inputws_t"),
                ("cbs", "ev_cbs_t"),
                ("changed", "ev_cb_t"),
                ("ch_p", "t_i32"),
                ("ch_v", "t_i32"),
                ("ch_tx", "t_i32"),
                ("ch_ty", "t_i32"),
                ("total", "t_i32"),
                ("done", "t_i32"),
                ("dpi", "t_f64"),
                ("changed_at", "t_f64"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    for name, file in [
        ("json", editor_json.FILE),
        ("state", editor_state.FILE),
        ("ui", editor_ui.FILE),
        ("canvas", editor_canvas.FILE),
        ("edit", editor_spline.FILE),
        ("spline", vector_spline.FILE),
        ("tiles", raster_tiles.FILE),
        ("brush", raster_brush.FILE),
        ("png", image_png.FILE),
        ("color", raster_color.FILE),
        ("closure", closure_wasm.FILE),
    ]:
        x.append(e.let(name, e.import_local(name, file)))
    for name, text in TEXTS.items():
        k.text(x, name, text)
    v = e.v
    f = k.f64

    def lib(name):
        return lambda fn, *args: k.lib(name, fn, *args)

    J, S, U, C, ED, SP, T, B, P, CO = (
        lib(n) for n in ["json", "state", "ui", "canvas", "edit", "spline", "tiles", "brush", "png", "color"]
    )

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def rs(name):
        return e.fld(v("rs"), name)

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def down(pre, val):
        return e.mb.as_(e.mb.as_(val, k.lo("t_i32")), k.lo(pre + "_raw"))

    def setv(name, val):
        return e.mb.set(v(name), val)

    def bfield(name):
        return e.fld(rs("brush"), name)

    def stop(i):
        return k.m(rs("stops"), "at", i)

    def widget_el(borrow, pre):
        """A control's element (raw `pre` handle) from its widget record (a borrow)."""
        return down(pre, e.fld(borrow, "el"))

    R_DPI, T_OUT = 0, 1

    def input_widget(i):
        return widget_el(k.m(rs("inputs"), "at", e.n(i)), "input")

    def model_widget():
        return widget_el(k.m(rs("selects"), "at", e.n(0)), "select")

    def ink_widget(i):
        return widget_el(k.m(rs("c_ink"), "at", e.n(i)), "input")

    def brush_widget(i):
        return widget_el(k.m(rs("r_brush"), "at", e.n(i)), "input")

    def status(*parts):
        """The status line: the texts and `bytes` `parts` (a text name, or ("bytes", expr))."""
        out = [e.let("sbuf", raw(rs("buf"), "bytes")), k.m(v("sbuf"), "clear", e.tup())]
        for part in parts:
            if isinstance(part, tuple):
                out.append(J("jw_text", v("sbuf"), k.bytes_str(part[1])))
            else:
                out.append(J("jw_text", v("sbuf"), ts(part)))
        out.append(U("text", rs("status"), k.bytes_str(v("sbuf"))))
        return e.seq(*out)

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    # The image and the job of the painting under way (raw); none between paintings: a caller checks the state.
    k.dep(
        x,
        "rs_img",
        ["rs"],
        ["rs_raw"],
        "img_raw",
        e.match_of(rs("img"), "o", None, p("some", k.ret(e.mb.as_(v("o"), k.lo("img_raw")))), p("none", trap())),
    )
    k.dep(
        x,
        "rs_job",
        ["rs"],
        ["rs_raw"],
        "job_raw",
        e.match_of(rs("job"), "o", None, p("some", k.ret(e.mb.as_(v("o"), k.lo("job_raw")))), p("none", trap())),
    )
    k.dep(
        x,
        "rs_defaults",
        ["rs"],
        ["rs_raw"],
        "t_void",
        e.seq(
            k.set(rs("dpi"), f(DEFAULTS["dpi"])),
            k.set(rs("model"), e.n(DEFAULTS["model"])),
            k.set(rs("color"), CO("rc_model", rs("model"))),
            *[k.set(stop(e.n(i)), f(c)) for i, c in enumerate(DEFAULTS["c"])],
            *[k.set(bfield(name), f(val)) for name, val in zip(BRUSH_FIELDS, DEFAULTS["b"])],
            e.let("path", raw(rs("path"), "bytes")),
            k.m(v("path"), "clear", e.tup()),
            J("jw_text", v("path"), ts("d_out")),
        ),
    )

    def rgb_of_stop(i):
        return e.mb.as_(e.tup(*[stop(e.n(3 * i + c)) for c in range(3)]), k.lo("rgb_t"))

    # The controls show the settings.
    k.dep(
        x,
        "rs_show",
        ["rs"],
        ["rs_raw"],
        "t_void",
        e.seq(
            U("set_value", input_widget(R_DPI), rs("dpi")),
            U("set_selected", model_widget(), rs("model")),
            *[U("color_set", ink_widget(i), rgb_of_stop(i)) for i in range(3)],
            *[U("set_value", brush_widget(i), bfield(field)) for i, (field, *_) in enumerate(BRUSH_CONTROLS)],
            U("textbox_set", input_widget(T_OUT), k.bytes_str(rs("path"))),
        ),
    )
    k.dep(
        x,
        "rs_on_change",
        ["rs"],
        ["rs_raw"],
        "t_void",
        e.seq(
            k.set(rs("dpi"), U("value", input_widget(R_DPI))),
            k.set(rs("model"), U("selected", model_widget())),
            k.set(rs("color"), CO("rc_model", rs("model"))),
            *[
                e.seq(
                    e.let("c%d" % i, U("color_get", ink_widget(i))),
                    *[k.set(stop(e.n(3 * i + c)), e.mb.field(v("c%d" % i), e.n(c))) for c in range(3)],
                )
                for i in range(3)
            ],
            *[k.set(bfield(field), U("value", brush_widget(i))) for i, (field, *_) in enumerate(BRUSH_CONTROLS)],
            e.let("path", raw(rs("path"), "bytes")),
            k.m(v("path"), "clear", e.tup()),
            U("textbox_get", input_widget(T_OUT), v("path")),
            # the settings' entry
            e.let("buf", raw(rs("buf"), "bytes")),
            k.m(v("buf"), "clear", e.tup()),
            J("jw_text", v("buf"), ts("j_dpi")),
            J("jw_num", v("buf"), rs("dpi")),
            J("jw_text", v("buf"), ts("j_model")),
            J("jw_int", v("buf"), rs("model")),
            J("jw_text", v("buf"), ts("j_c")),
            *[
                stmt
                for i in range(9)
                for stmt in ([J("jw_byte", v("buf"), e.n(ord(",")))] if i else [])
                + [J("jw_num", v("buf"), stop(e.n(i)))]
            ],
            J("jw_text", v("buf"), ts("j_b")),
            *[
                stmt
                for i, field in enumerate(BRUSH_FIELDS)
                for stmt in ([J("jw_byte", v("buf"), e.n(ord(",")))] if i else [])
                + [J("jw_num", v("buf"), bfield(field))]
            ],
            J("jw_text", v("buf"), ts("j_out")),
            J("jw_str", v("buf"), k.bytes_str(v("path"))),
            J("jw_byte", v("buf"), e.n(ord("}"))),
            S("st_put", rs("st"), rs("sec"), k.i32(0), v("buf")),
        ),
    )
    # The controls' closure (editor-ui's `ev_cb`): captures the layer, writes the settings, then the editor's
    # `changed` with the event.
    cap = e.fld(e.v("self"), "rs")
    x.append(
        e.let(
            "change_make",
            e.fld(
                e.call(
                    e.fld(e.v("closure"), "new"),
                    e.rec(
                        p("callable", e.v("ev_cb_t")),
                        p("capture", e.rec(p("rs", e.v("rs_raw")))),
                        p(
                            "body",
                            e.stage(
                                e.seq(
                                    k.dcall("rs_on_change", cap),
                                    e.call(e.fld(e.fld(cap, "changed"), "call"), k.m(e.v("arg"), "move", e.tup())),
                                )
                            ),
                        ),
                    ),
                ),
                "make",
            ),
        )
    )

    def change_cb():
        return k.m(rs("cbs"), "at", e.n(0))

    k.dep(
        x,
        "rs_new",
        ["st", "key", "cp", "cv", "ctx", "cty", "parent", "changed"],
        ["st_raw", "str_t", "t_i32", "t_i32", "t_i32", "t_i32", "node_raw", "ev_cb_t"],
        "rs_t",
        e.seq(
            e.let("stops", k.call("f64s_new", e.tup())),
            k.for_("i", 0, e.n(9), "stops", k.m(v("stops"), "push", f(0))),
            e.let("brush", B("brush_new")),
            e.let("status", U("el", v("parent"), ts("t_div"), ts("c_status"))),
            e.let(
                "rs",
                k.call(
                    "rs_make",
                    e.rec(
                        p("st", v("st")),
                        p("sec", S("st_section", v("st"), v("key"))),
                        p("img", k.call("img_opt_none", e.tup())),
                        p("job", k.call("job_opt_none", e.tup())),
                        p("state", k.i32(STATE_IDLE)),
                        p("seen", k.i32(-1)),
                        p("model", k.i32(DEFAULTS["model"])),
                        p("color", CO("rc_model", k.i32(DEFAULTS["model"]))),
                        p("texs", k.call("texs_new", e.tup())),
                        p("tilebuf", k.call("bytes_new", e.tup())),
                        p("png", k.call("bytes_new", e.tup())),
                        p("path", k.call("bytes_new", e.tup())),
                        p("stops", k.m(v("stops"), "move", e.tup())),
                        p("brush", k.m(v("brush"), "move", e.tup())),
                        p("buf", k.call("bytes_new", e.tup())),
                        p("status", k.m(v("status"), "move", e.tup())),
                        p("inputs", k.call("inputws_new", e.tup())),
                        p("selects", k.call("selectws_new", e.tup())),
                        p("c_ink", k.call("inputws_new", e.tup())),
                        p("r_brush", k.call("inputws_new", e.tup())),
                        p("cbs", k.call("ev_cbs_new", e.tup())),
                        p("changed", k.m(v("changed"), "move", e.tup())),
                        p("ch_p", v("cp")),
                        p("ch_v", v("cv")),
                        p("ch_tx", v("ctx")),
                        p("ch_ty", v("cty")),
                        p("total", k.i32(0)),
                        p("done", k.i32(0)),
                        p("dpi", f(DEFAULTS["dpi"])),
                        p("changed_at", f(0)),
                    ),
                ),
            ),
            # the controls, sharing one closure over the layer (made now that the record exists)
            k.m(rs("cbs"), "push", e.call(fn_of(e, k.lo("change_make")), e.rec(p("rs", raw(v("rs"), "rs"))))),
            k.m(
                rs("inputs"),
                "push",
                U("range", v("parent"), ts("t_dpi"), f(50), f(600), f(1), f(DEFAULTS["dpi"]), change_cb()),
            ),
            k.m(rs("inputs"), "push", U("textbox", v("parent"), ts("t_out"), change_cb())),
            k.m(rs("selects"), "push", U("select", v("parent"), ts("t_model"), change_cb())),
            U("option", e.fld(k.m(rs("selects"), "at", e.n(0)), "el"), ts("t_rgb")),
            U("option", e.fld(k.m(rs("selects"), "at", e.n(0)), "el"), ts("t_km")),
            *[k.m(rs("c_ink"), "push", U("color", v("parent"), ts("t_ink%d" % i), change_cb())) for i in range(3)],
            *[
                k.m(
                    rs("r_brush"),
                    "push",
                    U("range", v("parent"), ts("l_" + field), f(lo), f(hi), f(step), f(dflt), change_cb()),
                )
                for (field, _, lo, hi, step), dflt in zip(
                    BRUSH_CONTROLS, [DEFAULTS["b"][BRUSH_FIELDS.index(field)] for field, *_ in BRUSH_CONTROLS]
                )
            ],
            k.dcall("rs_defaults", v("rs")),
            k.dcall("rs_show", v("rs")),
            e.ret(k.m(v("rs"), "move", e.tup())),
        ),
    )

    def waiting():
        return e.seq(k.set(rs("state"), e.n(STATE_WAITING)), k.set(rs("changed_at"), U("now")), status("s_waiting"))

    k.dep(
        x,
        "rs_sync",
        ["rs"],
        ["rs_raw"],
        "t_void",
        e.seq(
            k.if_(k.eq(S("st_changed_count", rs("st"), rs("sec")), e.n(0)), k.ret()),
            S("st_changed_clear", rs("st"), rs("sec")),
            k.dcall("rs_defaults", v("rs")),
            e.match_of(
                S("st_get", rs("st"), rs("sec"), k.i32(0)),
                "text",
                None,
                p(
                    "some",
                    e.seq(
                        k.set(rs("dpi"), J("jr_num", v("text"), J("jr_field", v("text"), e.n(0), ts("k_dpi")))),
                        k.set(rs("model"), J("jr_int", v("text"), J("jr_field", v("text"), e.n(0), ts("k_model")))),
                        k.set(rs("color"), CO("rc_model", rs("model"))),
                        e.let("cq", J("jr_first", v("text"), J("jr_field", v("text"), e.n(0), ts("k_c")))),
                        k.for_(
                            "i",
                            0,
                            e.n(9),
                            "inks",
                            k.if_(k.lt(v("cq"), e.n(0)), k.brk("inks")),
                            k.set(stop(v("i")), J("jr_num", v("text"), v("cq"))),
                            setv("cq", J("jr_next", v("text"), v("cq"))),
                        ),
                        e.let("bq", J("jr_first", v("text"), J("jr_field", v("text"), e.n(0), ts("k_b")))),
                        *[
                            e.seq(
                                k.if_(k.ge(v("bq"), e.n(0)), k.set(bfield(field), J("jr_num", v("text"), v("bq")))),
                                k.if_(k.ge(v("bq"), e.n(0)), setv("bq", J("jr_next", v("text"), v("bq")))),
                            )
                            for field in BRUSH_FIELDS
                        ],
                        # the path: the JSON string, unescaped
                        e.let("path", raw(rs("path"), "bytes")),
                        k.m(v("path"), "clear", e.tup()),
                        e.let("pq", J("jr_str", v("text"), J("jr_field", v("text"), e.n(0), ts("k_out")), v("path"))),
                    ),
                ),
                p("none", e.seq()),
            ),
            k.dcall("rs_show", v("rs")),
            waiting(),
        ),
    )

    def segs_col(name, s):
        return k.m(e.fld(v("segs"), name), "at", s)

    # Starts painting: the image over the strokes and the brush's reach, the strokes sampled a dab apart.
    k.dep(
        x,
        "rs_start",
        ["rs", "ed"],
        ["rs_raw", "ed_raw"],
        "t_void",
        e.seq(
            k.if_(
                k.eq(ED("ed_count", v("ed")), e.n(0)),
                k.set(rs("state"), e.n(STATE_IDLE)),
                k.set(rs("job"), k.call("job_opt_none", e.tup())),
                k.set(rs("img"), k.call("img_opt_none", e.tup())),
                status("s_empty"),
                k.ret(),
            ),
            e.let("x0", f(1e300)),
            e.let("y0", f(1e300)),
            e.let("x1", f(-1e300)),
            e.let("y1", f(-1e300)),
            k.for_(
                "i",
                0,
                ED("ed_count", v("ed")),
                "strokes",
                e.let("segs", raw(e.fld(ED("ed_eff", v("ed"), v("i")), "segs"), "segs")),
                k.for_(
                    "s",
                    0,
                    e.fld(e.fld(v("segs"), "x0"), "len"),
                    "segs",
                    *[
                        stmt
                        for q in range(4)
                        for stmt in [
                            setv("x0", k.fmin(v("x0"), segs_col(CTRL_COLUMNS[2 * q], v("s")))),
                            setv("x1", k.fmax(v("x1"), segs_col(CTRL_COLUMNS[2 * q], v("s")))),
                            setv("y0", k.fmin(v("y0"), segs_col(CTRL_COLUMNS[2 * q + 1], v("s")))),
                            setv("y1", k.fmax(v("y1"), segs_col(CTRL_COLUMNS[2 * q + 1], v("s")))),
                        ]
                    ],
                ),
            ),
            k.if_(
                k.gt(v("x0"), v("x1")),
                k.set(rs("state"), e.n(STATE_IDLE)),
                k.set(rs("job"), k.call("job_opt_none", e.tup())),
                k.set(rs("img"), k.call("img_opt_none", e.tup())),
                status("s_empty"),
                k.ret(),
            ),
            e.let("pad", k.add(k.mul(bfield("radius"), k.add(e.n(1.5), bfield("tilt"))), e.n(2))),
            setv("x0", k.sub(v("x0"), v("pad"))),
            setv("y0", k.sub(v("y0"), v("pad"))),
            setv("x1", k.add(v("x1"), v("pad"))),
            setv("y1", k.add(v("y1"), v("pad"))),
            e.let("mmpp", k.div(e.n(25.4), k.fmax(rs("dpi"), e.n(1)))),
            e.let("w", k.trunc(k.ceil(k.div(k.sub(v("x1"), v("x0")), v("mmpp"))))),
            e.let("h", k.trunc(k.ceil(k.div(k.sub(v("y1"), v("y0")), v("mmpp"))))),
            k.if_(
                k.gt(k.mul(k.to_f64(v("w")), k.to_f64(v("h"))), e.n(MAX_PIXELS)),
                k.set(rs("state"), e.n(STATE_IDLE)),
                k.set(rs("job"), k.call("job_opt_none", e.tup())),
                k.set(rs("img"), k.call("img_opt_none", e.tup())),
                status("s_large"),
                k.ret(),
            ),
            # the new image, then the new job over it (the old job is dropped with its strokes)
            k.set(rs("img"), k.call("img_opt_some", T("rt_new", v("w"), v("h"), v("x0"), v("y0"), v("mmpp")))),
            e.let("img", k.dcall("rs_img", v("rs"))),
            k.set(
                rs("job"),
                k.call(
                    "job_opt_some",
                    B(
                        "br_new",
                        v("img"),
                        CO("rc_model", rs("model")),
                        raw(rs("brush"), "brush"),
                        raw(rs("stops"), "f64s"),
                        k.i32(3),
                        rs("ch_p"),
                        rs("ch_v"),
                        rs("ch_tx"),
                        rs("ch_ty"),
                    ),
                ),
            ),
            e.let("job", k.dcall("rs_job", v("rs"))),
            e.let(
                "spacing",
                k.fmax(k.mul(k.mul(bfield("radius"), bfield("bristle")), e.n(0.35)), k.mul(v("mmpp"), e.n(0.5))),
            ),
            k.set(rs("total"), e.n(0)),
            k.set(rs("done"), e.n(0)),
            k.for_(
                "i",
                0,
                ED("ed_count", v("ed")),
                "sample",
                e.let("eff", ED("ed_eff", v("ed"), v("i"))),
                e.let("smp", SP("samples_new")),
                SP("sp_sample", e.fld(v("eff"), "sp"), e.fld(v("eff"), "segs"), v("spacing"), v("smp")),
                k.set(rs("total"), k.add(rs("total"), e.fld(e.fld(v("smp"), "x"), "len"))),
                B("br_stroke", v("job"), k.m(v("smp"), "move", e.tup())),
            ),
            B("br_start", v("job")),
            k.set(rs("state"), e.n(STATE_PAINTING)),
        ),
    )
    # The painted tiles to their textures.
    k.dep(
        x,
        "rs_upload",
        ["rs", "cv"],
        ["rs_raw", "cv_raw"],
        "t_void",
        e.match_of(
            rs("img"),
            "img",
            None,
            p("none", e.seq()),
            p(
                "some",
                e.seq(
                    e.let("n", T("rt_tiles", v("img"))),
                    e.let("texs", raw(rs("texs"), "texs")),
                    k.loop(
                        "texs",
                        k.if_(k.ge(e.fld(v("texs"), "len"), v("n")), k.brk("texs")),
                        k.m(v("texs"), "push", C("cv_tex_new", v("cv"))),
                    ),
                    e.let("tilebuf", raw(rs("tilebuf"), "bytes")),
                    k.for_(
                        "i",
                        0,
                        v("n"),
                        "tiles",
                        k.if_(k.eq(T("rt_dirty", v("img"), v("i")), e.n(0)), k.cont("tiles")),
                        T("rt_clean", v("img"), v("i")),
                        T("rt_tile_rgba", v("img"), v("i"), rs("color"), v("tilebuf")),
                        C(
                            "cv_tex_set",
                            v("cv"),
                            k.m(v("texs"), "at", v("i")),
                            T("rt_tile_w", v("img"), v("i")),
                            T("rt_tile_h", v("img"), v("i")),
                            e.fld(v("tilebuf"), "data"),
                        ),
                    ),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "rs_frame",
        ["rs", "ed", "cv"],
        ["rs_raw", "ed_raw", "cv_raw"],
        "t_i32",
        e.seq(
            e.let("now", U("now")),
            k.if_(k.ne(ED("ed_version", v("ed")), rs("seen")), k.set(rs("seen"), ED("ed_version", v("ed"))), waiting()),
            k.if_(
                k.and_(
                    k.eq(rs("state"), e.n(STATE_WAITING)), k.ge(k.sub(v("now"), rs("changed_at")), e.n(DEBOUNCE_MS))
                ),
                k.dcall("rs_start", v("rs"), v("ed")),
            ),
            k.if_(k.ne(rs("state"), e.n(STATE_PAINTING)), k.ret(k.i32(0))),
            e.let("job", k.dcall("rs_job", v("rs"))),
            e.let("finished", k.i32(0)),
            k.loop(
                "slice",
                k.if_(k.ne(B("br_step", v("job"), e.n(32)), e.n(0)), setv("finished", e.n(1)), k.brk("slice")),
                k.set(rs("done"), k.add(rs("done"), e.n(32))),
                k.if_(k.ge(k.sub(U("now"), v("now")), e.n(SLICE_MS)), k.brk("slice")),
            ),
            k.dcall("rs_upload", v("rs"), v("cv")),
            e.let("png", raw(rs("png"), "bytes")),
            k.if_(
                k.eq(v("finished"), e.n(0)),
                k.m(v("png"), "clear", e.tup()),
                J(
                    "jw_int",
                    v("png"),
                    k.div(
                        k.mul(k.ifelse(k.lt(rs("done"), rs("total")), rs("done"), rs("total")), e.n(100)),
                        k.ifelse(k.gt(rs("total"), e.n(0)), rs("total"), k.i32(1)),
                    ),
                ),
                status("s_painting", ("bytes", v("png")), "s_percent"),
                k.ret(k.i32(0)),
            ),
            # done: the PNG
            e.let("img", k.dcall("rs_img", v("rs"))),
            k.m(v("png"), "clear", e.tup()),
            e.let("pw", P("png_begin", v("png"), e.fld(v("img"), "w"), e.fld(v("img"), "h"), rs("dpi"))),
            e.let("rowbuf", k.call("bytes_new", e.tup())),
            k.for_(
                "y",
                0,
                e.fld(v("img"), "h"),
                "rows",
                T("rt_rgb8_row", v("img"), rs("color"), v("y"), v("rowbuf")),
                P("png_row", v("pw"), k.bytes_str(v("rowbuf"))),
            ),
            P("png_end", k.m(v("pw"), "move", e.tup())),
            k.set(rs("state"), e.n(STATE_READY)),
            status("s_ready"),
            e.ret(k.i32(1)),
        ),
    )
    k.dep(x, "rs_png", ["rs"], ["rs_raw"], "str_t", e.ret(k.bytes_str(rs("png"))))
    k.dep(x, "rs_path", ["rs"], ["rs_raw"], "str_t", e.ret(k.bytes_str(rs("path"))))
    k.dep(
        x,
        "rs_written",
        ["rs", "ok"],
        ["rs_raw", "t_i32"],
        "t_void",
        e.seq(
            k.if_(
                k.eq(rs("state"), e.n(STATE_READY)),
                k.set(rs("state"), e.n(STATE_IDLE)),
                k.set(rs("job"), k.call("job_opt_none", e.tup())),
                k.set(rs("img"), k.call("img_opt_none", e.tup())),
            ),
            k.ifelse(
                k.eq(v("ok"), e.n(0)),
                status("s_saved", ("bytes", rs("path"))),
                status("s_failed", ("bytes", rs("path"))),
            ),
        ),
    )
    k.dep(
        x,
        "rs_draw",
        ["rs", "cv", "alpha"],
        ["rs_raw", "cv_raw", "t_f64"],
        "t_void",
        e.match_of(
            rs("img"),
            "img",
            None,
            p("none", e.seq()),
            p(
                "some",
                e.seq(
                    e.let("n", T("rt_tiles", v("img"))),
                    e.let("texs", raw(rs("texs"), "texs")),
                    k.if_(k.lt(e.fld(v("texs"), "len"), v("n")), k.ret()),
                    k.for_(
                        "i",
                        0,
                        v("n"),
                        "tiles",
                        e.let("r", T("rt_tile_rect", v("img"), v("i"))),
                        C(
                            "cv_image",
                            v("cv"),
                            k.m(v("texs"), "at", v("i")),
                            *[e.mb.field(v("r"), e.n(c)) for c in range(4)],
                            v("alpha"),
                        ),
                    ),
                ),
            ),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
