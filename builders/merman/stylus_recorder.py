"""stylus-recorder.atz: an editor pane recording stylus strokes (editor-record.atz) on a drawing area
(editor-canvas.atz): every pointer sample with all its fields, a stroke per undo level, the strokes kept in
`stylus-recorder.json` next to this module; the middle and right buttons pan, the wheel zooms, and a button removes
every stroke. The app record owns the canvas, the recorder, the button and the listeners on the canvas element
(harness/verify-stylus-recorder.sh)."""

from ..editor.app import App
from ..editor import editor_canvas, editor_record

TEXTS = {
    "s_div": "div",
    "s_app": "ed_app",
    "s_side": "ed_side",
    "k_strokes": "strokes",
    "t_clear": "Remove all strokes",
}


def module(e):
    app = App(
        e,
        "stylus-recorder.json",
        "2",
        [("canvas", editor_canvas.FILE), ("rec", editor_record.FILE)],
        [("cv", "canvas.cv_t"), ("rec", "rec.rc_t"), ("b_clear", "button_t")],
    )
    k = app.k
    v = e.v
    for name, text in TEXTS.items():
        app.text(name, text)

    def CV(fn, *args):
        return k.lib("canvas", fn, app.g("cv"), *args)

    def REC(fn, *args):
        return k.lib("rec", fn, app.g("rec"), *args)

    refresh = REC("rec_sync")
    # the canvas's child: the pointer events the canvas did not take record strokes
    app.implement(
        "tool",
        "canvas.cv_child_t",
        "canvas.cv_child_own",
        [
            *[
                (
                    m,
                    "ev",
                    "event_raw",
                    k.if_(k.gt(REC("rec_pointer", app.g("cv"), v("ev"), e.n(kind)), e.n(0)), app.commit(), refresh),
                )
                for kind, m in enumerate(["down", "move", "up"])
            ],
            ("dblclick", "ev", "event_raw", e.seq()),
        ],
    )
    start = e.seq(
        e.let("main", app.ui("el", v("root"), app.s("s_div"), app.s("s_app"))),
        e.let("cv", k.lib("canvas", "cv_new", v("main"), app.handler("on_fit"), app.child("tool"))),
        e.let("side", app.ui("el", v("main"), app.s("s_div"), app.s("s_side"))),
        e.let("b_clear", app.ui("button", v("side"), app.s("t_clear"), app.cb("on_clear"))),
        e.let("rec", k.lib("rec", "rec_new", v("st"), app.s("k_strokes"))),
    )
    fields = {name: k.m(v(name), "move", e.tup()) for name in ["cv", "rec", "b_clear"]}
    # fit: the recorded samples' extent
    f = k.f64

    def col(name):
        return e.fld(v("s"), name)

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
                REC("rec_count"),
                "strokes",
                e.let("s", REC("rec_stroke", v("i"))),
                k.for_(
                    "j",
                    0,
                    e.fld(col("x"), "len"),
                    "samples",
                    e.mb.set(v("x0"), k.fmin(v("x0"), k.m(col("x"), "at", v("j")))),
                    e.mb.set(v("x1"), k.fmax(v("x1"), k.m(col("x"), "at", v("j")))),
                    e.mb.set(v("y0"), k.fmin(v("y0"), k.m(col("y"), "at", v("j")))),
                    e.mb.set(v("y1"), k.fmax(v("y1"), k.m(col("y"), "at", v("j")))),
                ),
            ),
            CV("cv_fit", v("x0"), v("y0"), v("x1"), v("y1")),
        ),
    )
    app.event("on_clear", e.seq(REC("rec_clear"), app.commit(), refresh))
    app.frame(e.seq(CV("cv_begin"), REC("rec_draw", app.g("cv"), k.f64(1))))
    return app.finish(start, fields, refresh, e.seq(), e.seq())
