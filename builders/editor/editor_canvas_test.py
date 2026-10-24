"""editor-canvas-test.atz: an editor showing editor-canvas.atz: a 2x2 texture over a world rectangle, a circle and a
line on the vector layer, the grid; its pointer and wheel events reach the canvas (harness/verify-editor-canvas.sh).
The app record owns the canvas, the texture and the four listeners on the canvas element.
"""

from .app import App

PIXELS = [255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255]


def module(e):
    app = App(
        e,
        "editor-canvas-test.json",
        "1",
        [("canvas", "editor-canvas.atz")],
        [("cv", "canvas.cv_t"), ("tex", "canvas.tex_t")],
    )
    k = app.k
    v = e.v
    for name, text in [
        ("s_div", "div"),
        ("s_app", "ed_app"),
    ]:
        app.text(name, text)
    app.let(
        "pixels",
        e.call(
            e.fld(e.v("wasm"), "data_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("pixels")),
                e.p("elem", e.v("t_u8")),
                e.p("values", e.tup(*[e.n(b) for b in PIXELS])),
            ),
        ),
    )

    def C(f, *args):
        return k.lib("canvas", f, app.g("cv"), *args)

    def C0(f, *args):
        return k.lib("canvas", f, v("cv"), *args)

    # the canvas's child: nothing of its own
    app.implement(
        "tool",
        "canvas.cv_child_t",
        "canvas.cv_child_own",
        [(m, "ev", "event_raw", e.seq()) for m in ["down", "move", "up", "dblclick"]],
    )
    start = e.seq(
        e.let("main", app.ui("el", v("root"), app.s("s_div"), app.s("s_app"))),
        e.let(
            "cv",
            k.lib("canvas", "cv_new", v("main"), app.handler("on_fit"), app.child("tool")),
        ),
        e.let("tex", C0("cv_tex_new")),
        C0("cv_tex_set", v("tex"), e.n(2), e.n(2), k.ptr_of(k.addr(k.lo("pixels")), "t_pu8")),
    )
    fields = {"cv": k.m(v("cv"), "move", e.tup()), "tex": k.m(v("tex"), "move", e.tup())}
    app.frame(
        e.seq(
            C("cv_begin"),
            C("cv_image", app.g("tex"), k.f64(-10), k.f64(-10), k.f64(10), k.f64(10), k.f64(1)),
            C("cv_style", k.f64(1), k.f64(2)),
            C("cv_circle", k.f64(0), k.f64(0), k.f64(15), e.n(0)),
            C("cv_line", k.f64(-20), k.f64(20), k.f64(20), k.f64(20)),
        )
    )
    app.callback("on_fit", C("cv_fit", k.f64(-10), k.f64(-10), k.f64(10), k.f64(10)))
    return app.finish(start, fields, e.seq(), e.seq(), e.seq())
