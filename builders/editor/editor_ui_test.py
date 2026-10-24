"""editor-ui-test.atz: an editor with one control of each kind of editor-ui.atz, each writing its value into the
document (section `t`: 1 the button's count, 2 the slider, 3 the dropdown, 4 the checkbox, 5 the text field) as one
undo level; the document's values are shown back in the controls (harness/verify-editor-ui.sh). The app record owns
the widgets (and so their listeners and elements) and the byte buffer the entries are written through.
"""

from ..eco_mb import p
from .app import App


def module(e):
    app = App(
        e,
        "editor-ui-test.json",
        "1",
        [],
        [
            ("sec", "t_i32"),
            ("buf", "bytes_t"),
            ("btn", "button_t"),
            ("rng", "inputw_t"),
            ("sel", "selectw_t"),
            ("chk", "inputw_t"),
            ("txt", "inputw_t"),
        ],
    )
    k = app.k
    v = e.v
    for name, text in [
        ("s_div", "div"),
        ("s_side", "ed_side"),
        ("s_t", "t"),
        ("s_bump", "Bump"),
        ("s_size", "Size"),
        ("s_kind", "Kind"),
        ("s_a", "alpha"),
        ("s_b", "beta"),
        ("s_on", "On"),
        ("s_name", "Name"),
    ]:
        app.text(name, text)

    def S(f, *args):
        return k.lib("state", f, *args)

    def J(f, *args):
        return k.lib("json", f, *args)

    def put(id_, *write):
        """Writes the entry `id_` from the statements `write` (into the buffer `buf`) and commits."""
        return e.seq(
            k.m(app.g("buf"), "clear", e.tup()),
            *write,
            S("st_put", app.st(), app.g("sec"), e.n(id_), app.g("buf")),
            app.commit(),
        )

    def entry(id_, some, none):
        """`some(text)` (a `str`) when the entry `id_` exists, else `none`."""
        return e.match_of(
            S("st_get", app.st(), app.g("sec"), e.n(id_)), "text", None, p("some", some(v("text"))), p("none", none)
        )

    def widget_el(name):
        """A widget's element (a borrow)."""
        return e.fld(app.g(name), "el")

    start = e.seq(
        e.let("sec", S("st_section", v("st"), app.s("s_t"))),
        e.let("buf", k.call("bytes_new", e.tup())),
        e.let("side", app.ui("el", v("root"), app.s("s_div"), app.s("s_side"))),
        e.let("btn", app.ui("button", v("side"), app.s("s_bump"), app.cb("on_bump"))),
        e.let(
            "rng",
            app.ui("range", v("side"), app.s("s_size"), k.f64(0), k.f64(10), k.f64(0.5), k.f64(2), app.cb("on_size")),
        ),
        e.let("sel", app.ui("select", v("side"), app.s("s_kind"), app.cb("on_kind"))),
        app.ui("option", e.fld(v("sel"), "el"), app.s("s_a")),
        app.ui("option", e.fld(v("sel"), "el"), app.s("s_b")),
        e.let("chk", app.ui("check", v("side"), app.s("s_on"), e.n(0), app.cb("on_on"))),
        e.let("txt", app.ui("textbox", v("side"), app.s("s_name"), app.cb("on_name"))),
    )
    fields = {
        "sec": v("sec"),
        "buf": k.m(v("buf"), "move", e.tup()),
        **{w: k.m(v(w), "move", e.tup()) for w in ["btn", "rng", "sel", "chk", "txt"]},
    }
    app.event(
        "on_bump",
        e.seq(
            e.let("n", entry(1, lambda t: J("jr_int", t, e.n(0)), k.i32(0))),
            put(1, J("jw_int", app.g("buf"), k.add(v("n"), e.n(1)))),
        ),
    )
    app.event("on_size", put(2, J("jw_num", app.g("buf"), app.ui("value", widget_el("rng")))))
    app.event("on_kind", put(3, J("jw_int", app.g("buf"), app.ui("selected", widget_el("sel")))))
    app.event("on_on", put(4, J("jw_int", app.g("buf"), app.ui("checked", widget_el("chk")))))
    app.event(
        "on_name",
        e.seq(
            e.let("raw", k.call("bytes_new", e.tup())),
            app.ui("textbox_get", widget_el("txt"), v("raw")),
            put(5, J("jw_str", app.g("buf"), k.bytes_str(v("raw")))),
        ),
    )
    app.frame(e.seq())
    sync = e.seq(
        k.for_(
            "i",
            0,
            S("st_changed_count", app.st(), app.g("sec")),
            "changed",
            e.let("id", S("st_changed_at", app.st(), app.g("sec"), v("i"))),
            e.match_of(
                S("st_get", app.st(), app.g("sec"), v("id")),
                "text",
                None,
                p(
                    "some",
                    e.seq(
                        k.if_(
                            k.eq(v("id"), e.n(2)), app.ui("set_value", widget_el("rng"), J("jr_num", v("text"), e.n(0)))
                        ),
                        k.if_(
                            k.eq(v("id"), e.n(3)),
                            app.ui("set_selected", widget_el("sel"), J("jr_int", v("text"), e.n(0))),
                        ),
                        k.if_(
                            k.eq(v("id"), e.n(4)),
                            app.ui("set_checked", widget_el("chk"), J("jr_int", v("text"), e.n(0))),
                        ),
                    ),
                ),
                p("none", e.seq()),
            ),
        ),
        S("st_changed_clear", app.st(), app.g("sec")),
    )
    return app.finish(start, fields, sync, e.seq(), e.seq())
