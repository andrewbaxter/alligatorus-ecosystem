"""calligraphy.atz: an editor for brush calligraphy, assembled from the editor components.

A drawing area (editor-canvas.atz) and a list of four layers (editor-layers.atz), each with its controls:

1. Strokes (editor-record.atz): pen strokes with everything the pointer reports.
2. Smoothing (editor-smooth.atz): each stroke smoothed into a spline with three channels: the speed, the pressure
   and the tilt.
3. Splines (editor-spline.atz): the splines edited; an edit is undone when the stroke's smoothing changes.
4. Brush (editor-raster.atz): the splines painted with a bristle brush in inks mixing like pigments, the speed drying
   the brush, the pressure spreading it and the tilt leaning it; the image is written to a PNG.

The pointer on the drawing area goes to the selected layer (the middle and right buttons pan, the wheel zooms). The
document is `calligraphy.json` next to this module. The app record owns the listeners (dropped first), the layers,
the layer list, the clear button and the canvas."""

from .app import App
from . import editor_canvas, editor_layers, editor_raster, editor_record, editor_smooth, editor_spline, vector_spline

# The layers' ids (editor-layers.atz: not 0), in list order.
LAYER_STROKES, LAYER_SMOOTHING, LAYER_SPLINES, LAYER_BRUSH = 1, 2, 3, 4
LAYERS = [
    (LAYER_STROKES, "n_strokes"),
    (LAYER_SMOOTHING, "n_smoothing"),
    (LAYER_SPLINES, "n_splines"),
    (LAYER_BRUSH, "n_brush"),
]
# The splines' channels: (kind, slot, scale mm per unit, name, the recorded column smoothing reads: an index in
# editor-record.atz's CHANNELS, -1 the speed).
CHANNELS = [
    (0, 0, 0.01, "Speed (mm/s)", -1),
    (0, 1, 4.0, "Pressure", editor_record.CHANNELS.index("pressure")),
    (2, 2, 0.1, "Tilt (degrees)", editor_record.CHANNELS.index("tilt_x")),
]
TILT_Y_COLUMN = editor_record.CHANNELS.index("tilt_y")
# The channels' slots, as the brush reads them (the tilt's y is the 2D channel's second slot).
SLOT_SPEED, SLOT_PRESSURE, SLOT_TILT = (ch[1] for ch in CHANNELS)

TEXTS = {
    "s_div": "div",
    "s_app": "ed_app",
    "s_side": "ed_side",
    "s_tabindex": "tabindex",
    "s_zero": "0",
    "k_layers": "layers",
    "k_strokes": "strokes",
    "k_smoothing": "smoothing",
    "k_splines": "splines",
    "k_brush": "brush",
    "n_strokes": "Strokes",
    "n_smoothing": "Smoothing",
    "n_splines": "Splines",
    "n_brush": "Brush",
    "t_clear": "Remove all strokes",
    "e_keydown": "keydown",
    **{"c_name%d" % i: ch[3] for i, ch in enumerate(CHANNELS)},
}


def module(e):
    app = App(
        e,
        "calligraphy.json",
        "1",
        [
            ("canvas", editor_canvas.FILE),
            ("layers", editor_layers.FILE),
            ("rec", editor_record.FILE),
            ("smooth", editor_smooth.FILE),
            ("edit", editor_spline.FILE),
            ("raster", editor_raster.FILE),
            ("spline", vector_spline.FILE),
        ],
        # Dropped in order: the key listener, then the layers (each borrowing the store, dropped last), the list,
        # the button, the canvas and the app's element.
        [
            ("l_key", "listener_t"),
            ("rs", "raster.rs_t"),
            ("ed", "edit.ed_t"),
            ("sm", "smooth.sm_t"),
            ("rec", "rec.rc_t"),
            ("ll", "layers.ll_t"),
            ("b_clear", "button_t"),
            ("cv", "canvas.cv_t"),
            ("app_el", "el_t"),
        ],
    )
    k = app.k
    v = e.v
    f = k.f64
    for name, text in TEXTS.items():
        app.text(name, text)

    def lib(name):
        return lambda fn, *args: k.lib(name, fn, *args)

    CV0, LL0, REC0, SM0, ED0, RS0 = (lib(n) for n in ["canvas", "layers", "rec", "smooth", "edit", "raster"])

    def g(name):
        return app.g(name)

    # The components' functions over the app's records.
    def CV(fn, *args):
        return CV0(fn, g("cv"), *args)

    def LL(fn, *args):
        return LL0(fn, g("ll"), *args)

    def REC(fn, *args):
        return REC0(fn, g("rec"), *args)

    def SM(fn, *args):
        return SM0(fn, g("sm"), *args)

    def ED(fn, *args):
        return ED0(fn, g("ed"), *args)

    def RS(fn, *args):
        return RS0(fn, g("rs"), *args)

    refresh = e.seq(LL("ll_sync"), REC("rec_sync"), SM("sm_sync", g("rec")), ED("ed_sync", g("sm")), RS("rs_sync"))

    def changed():
        """A change of the document by the editor: an undo level, then everything follows it."""
        return e.seq(app.commit(), refresh)

    sel = LL("ll_selected")

    # the canvas's child: pointer events in the area the canvas did not take, to the selected layer's tool
    def pointer(kind):
        return e.seq(
            k.if_(
                k.eq(sel, e.n(LAYER_STROKES)),
                k.if_(k.gt(REC("rec_pointer", g("cv"), v("ev"), e.n(kind)), e.n(0)), changed()),
            ),
            k.if_(
                k.eq(sel, e.n(LAYER_SPLINES)),
                k.if_(k.ne(ED("ed_pointer", g("sm"), g("cv"), v("ev"), e.n(kind)), e.n(0)), changed()),
            ),
        )

    app.implement(
        "tool",
        "canvas.cv_child_t",
        "canvas.cv_child_own",
        [
            ("down", "ev", "event_raw", pointer(0)),
            ("move", "ev", "event_raw", pointer(1)),
            ("up", "ev", "event_raw", pointer(2)),
            (
                "dblclick",
                "ev",
                "event_raw",
                k.if_(
                    k.eq(sel, e.n(LAYER_SPLINES)),
                    k.if_(k.ne(ED("ed_insert", g("sm"), g("cv"), v("ev")), e.n(0)), changed()),
                ),
            ),
        ],
    )
    start = e.seq(
        e.let("app_el", app.ui("el", v("root"), app.s("s_div"), app.s("s_app"))),
        app.ui("attr", v("app_el"), app.s("s_tabindex"), app.s("s_zero")),
        e.let(
            "cv",
            CV0("cv_new", v("app_el"), app.handler("on_fit"), app.child("tool")),
        ),
        e.let("side", app.ui("el", v("app_el"), app.s("s_div"), app.s("s_side"))),
        e.let("ll", LL0("ll_new", v("st"), app.s("k_layers"), v("side"), app.handler("on_layer"))),
        *[LL0("ll_add", v("ll"), e.n(id_), app.s(n)) for id_, n in LAYERS],
        e.let("rec", REC0("rec_new", v("st"), app.s("k_strokes"))),
        e.let(
            "b_clear",
            app.ui("button", LL0("ll_props", v("ll"), e.n(LAYER_STROKES)), app.s("t_clear"), app.cb("on_clear")),
        ),
        # smoothing: the channels' recorded columns (the tilt's second slot from tilt_y)
        e.let("map", k.call("ints_new", e.tup())),
        *[k.m(v("map"), "push", k.i32(ch[4])) for ch in CHANNELS],
        k.m(v("map"), "push", k.i32(TILT_Y_COLUMN)),
        e.let(
            "sm",
            SM0(
                "sm_new",
                v("st"),
                app.s("k_smoothing"),
                v("map"),
                e.n(len(CHANNELS) + 1),
                LL0("ll_props", v("ll"), e.n(LAYER_SMOOTHING)),
                app.handler("on_smooth"),
            ),
        ),
        e.let("chans", k.lib("edit", "chds_new")),
        *[
            k.m(
                v("chans"),
                "push",
                ED0("ed_chd", e.n(kind), e.n(slot), f(scale), app.s("c_name%d" % i)),
            )
            for i, (kind, slot, scale, _, _) in enumerate(CHANNELS)
        ],
        e.let(
            "ed",
            ED0(
                "ed_new",
                v("st"),
                app.s("k_splines"),
                k.m(v("chans"), "move", e.tup()),
                LL0("ll_props", v("ll"), e.n(LAYER_SPLINES)),
                v("sm"),
                app.handler("on_edit"),
            ),
        ),
        # the brush reads the pressure, speed and tilt slots
        e.let(
            "rs",
            RS0(
                "rs_new",
                v("st"),
                app.s("k_brush"),
                e.n(SLOT_PRESSURE),
                e.n(SLOT_SPEED),
                e.n(SLOT_TILT),
                e.n(SLOT_TILT + 1),
                LL0("ll_props", v("ll"), e.n(LAYER_BRUSH)),
                app.handler("on_raster"),
            ),
        ),
        e.let("l_key", app.ui("listen", v("app_el"), app.s("e_keydown"), app.cb("on_key"))),
    )
    fields = {
        name: k.m(v(name), "move", e.tup())
        for name in ["l_key", "rs", "ed", "sm", "rec", "ll", "b_clear", "cv", "app_el"]
    }

    app.event(
        "on_key",
        k.if_(
            k.eq(sel, e.n(LAYER_SPLINES)),
            k.if_(k.ne(ED("ed_key", g("sm"), v("ev")), e.n(0)), app.ui("stop", v("ev")), changed()),
        ),
    )
    # fit: the splines' extent
    app.callback(
        "on_fit",
        e.seq(
            e.let("x0", f(1e300)),
            e.let("y0", f(1e300)),
            e.let("x1", f(-1e300)),
            e.let("y1", f(-1e300)),
            k.for_(
                "i",
                0,
                ED("ed_count"),
                "strokes",
                e.let("sp", e.mb.as_(e.fld(ED("ed_eff", v("i")), "sp"), e.lower(e.fld(e.v("spline"), "spline_raw")))),
                k.for_(
                    "n",
                    0,
                    k.lib("spline", "sp_count", v("sp")),
                    "nodes",
                    e.let("nd", k.lib("spline", "sp_node", v("sp"), v("n"))),
                    e.mb.set(v("x0"), k.fmin(v("x0"), e.fld(v("nd"), "x"))),
                    e.mb.set(v("x1"), k.fmax(v("x1"), e.fld(v("nd"), "x"))),
                    e.mb.set(v("y0"), k.fmin(v("y0"), e.fld(v("nd"), "y"))),
                    e.mb.set(v("y1"), k.fmax(v("y1"), e.fld(v("nd"), "y"))),
                ),
            ),
            CV("cv_fit", v("x0"), v("y0"), v("x1"), v("y1")),
        ),
    )
    # a layer's visibility or opacity changed (the list wrote it): an undo level
    app.callback("on_layer", changed())
    # removing strokes or changing a smoothing amount drops what depended on it, in the same change
    stale = e.seq(REC("rec_sync"), SM("sm_stale", g("rec")), SM("sm_sync", g("rec")), ED("ed_stale", g("sm")))
    app.event("on_clear", e.seq(REC("rec_clear"), stale, changed()))
    app.callback("on_smooth", e.seq(stale, changed()))
    app.callback("on_edit", changed())
    app.callback("on_raster", changed())

    def visible(layer):
        return k.ne(LL("ll_visible", e.n(layer)), e.n(0))

    def opacity(layer):
        return LL("ll_opacity", e.n(layer))

    app.frame(
        e.seq(
            CV("cv_begin"),
            k.if_(visible(LAYER_BRUSH), RS("rs_draw", g("cv"), opacity(LAYER_BRUSH))),
            k.if_(visible(LAYER_STROKES), REC("rec_draw", g("cv"), opacity(LAYER_STROKES))),
            k.if_(visible(LAYER_SMOOTHING), SM("sm_draw", g("cv"), opacity(LAYER_SMOOTHING))),
            k.if_(visible(LAYER_SPLINES), ED("ed_draw", g("cv"), opacity(LAYER_SPLINES))),
            k.if_(
                k.ne(RS("rs_frame", g("ed"), g("cv")), e.n(0)),
                e.let("path", RS("rs_path")),
                e.let("png", RS("rs_png")),
                k.call(
                    "fs_write",
                    e.n(1),
                    e.fld(v("path"), "data"),
                    e.fld(v("path"), "len"),
                    e.fld(v("png"), "data"),
                    e.fld(v("png"), "len"),
                ),
            ),
        )
    )
    fs = k.if_(k.eq(v("req"), e.n(1)), RS("rs_written", v("status")))
    return app.finish(start, fields, refresh, fs, e.seq())
