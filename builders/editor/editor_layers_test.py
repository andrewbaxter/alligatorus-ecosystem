"""editor-layers-test.atz: an editor with a layer list (editor-layers.atz) of three layers (ids 1, 2, 3: A, B, C) and
two buttons: one moves C first, one removes B. A row's visibility and opacity write the document as undo levels
(harness/verify-editor-layers.sh)."""

from . import editor_layers
from .app import App

LAYERS = [(1, "n_a"), (2, "n_b"), (3, "n_c")]


def module(e):
    app = App(
        e,
        "editor-layers-test.json",
        "1",
        [("layers", editor_layers.FILE)],
        [("b_move", "button_t"), ("b_remove", "button_t"), ("ll", "layers.ll_t")],
    )
    k = app.k
    v = e.v
    for name, text in [
        ("s_div", "div"),
        ("s_side", "ed_side"),
        ("k_layers", "layers"),
        ("s_move", "Move C first"),
        ("s_remove", "Remove B"),
        ("n_a", "A"),
        ("n_b", "B"),
        ("n_c", "C"),
    ]:
        app.text(name, text)

    def LL(f, *args):
        return k.lib("layers", f, app.g("ll"), *args)

    start = e.seq(
        e.let("side", app.ui("el", v("root"), app.s("s_div"), app.s("s_side"))),
        e.let("b_move", app.ui("button", v("side"), app.s("s_move"), app.cb("on_move"))),
        e.let("b_remove", app.ui("button", v("side"), app.s("s_remove"), app.cb("on_remove"))),
        e.let("ll", k.lib("layers", "ll_new", v("st"), app.s("k_layers"), v("side"), app.handler("on_layer"))),
        *[k.lib("layers", "ll_add", v("ll"), e.n(id_), app.s(name)) for id_, name in LAYERS],
    )
    fields = {name: k.m(v(name), "move", e.tup()) for name in ["b_move", "b_remove", "ll"]}
    app.callback("on_layer", app.commit())
    app.event("on_move", LL("ll_move", e.n(3), e.n(0)))
    app.event("on_remove", e.seq(LL("ll_remove", e.n(2)), app.commit()))
    app.frame(e.seq())
    return app.finish(start, fields, LL("ll_sync"), e.seq(), e.seq())
