"""editor-layers.atz: an editor's list of layers (wat target; dependencies over editor-ui.atz, typed with the
ecosystem's libraries).

Each layer has an id (the editor's, not 0) and a row: a visibility checkbox, its name, an opacity slider; clicking a
row selects its layer, and the selected layer's properties (an element the layer fills with its controls) show under
the list. Visibility and opacity are entries of the document's section the list registers (entry: the layer's id,
`{"v": 0|1, "o": opacity}`), so they are undone like everything else; the selection is the view's.

The list is an owned record (`ll_t`, `ll_raw`) owning its elements, rows and closures: `ll_new(st, key,
parent, changed)` makes it in `parent` (a node; the properties under it), its section under `key`, taking the
editor's callable `changed` (editor-ui.atz `ev_cb`, owned), called with the event after a row changes the document
(the editor commits), yielding the owned record. `ll_add(ll, id, name)` adds a layer at the end (the first added is
selected): its row's listeners are closures capturing the list and the id, so a row knows which layer it is.
`ll_remove(ll, id)` removes a layer, its row and its entry (the selection moves to the first layer);
`ll_move(ll, id, to)` moves a layer's row to position `to`; `ll_select(ll, id)`. `ll_props(ll, id)` is the element
for the layer's properties (raw); `ll_visible(ll, id)`, `ll_opacity(ll, id)`, `ll_selected(ll)` (0: none).
`ll_sync(ll)` follows the document."""

from ..collections import closure_wasm, record_wasm
from ..eco_mb import p
from . import editor_json, editor_state, editor_types, editor_ui
from ..target_mb import fn_of
from ..wasm.kit import Kit, library, stack

FILE = "editor-layers.atz"

TEXTS = {
    "t_div": "div",
    "t_span": "span",
    "t_input": "input",
    "t_type": "type",
    "t_checkbox": "checkbox",
    "t_range": "range",
    "t_min": "min",
    "t_max": "max",
    "t_step": "step",
    "t_change": "change",
    "t_input_ev": "input",
    "t_click": "click",
    "c_section": "ed_section",
    "c_heading": "ed_heading",
    "c_layer": "ed_layer",
    "c_layer_sel": "ed_layer ed_layer_selected",
    "c_name": "ed_layer_name",
    "c_input": "ed_input",
    "t_layers": "Layers",
    "j_v": '{"v":',
    "j_o": ',"o":',
    "k_v": "v",
    "k_o": "o",
}
UI_TYPES = ["el_t", "el_own", "el_raw", "node_raw", "input_raw", "event_raw", "listener_t", "listener_own", "ev_cb_t"]
# The row's record: the listeners (dropped first), their closures, the elements, the entry's values.
ROW_FIELDS = [
    ("l_sel", "listener_t"),
    ("l_check", "listener_t"),
    ("l_range", "listener_t"),
    ("cb_sel", "ev_cb_t"),
    ("cb_check", "ev_cb_t"),
    ("cb_range", "ev_cb_t"),
    ("row", "el_t"),
    ("check", "el_t"),
    ("range", "el_t"),
    ("props", "el_t"),
    ("visible", "t_i32"),
    ("opacity", "t_f64"),
    ("id", "t_i32"),
]

TYPE_EXPORTS = ["ll_t"]
EXPORTS = [
    "ll_new",
    "ll_add",
    "ll_remove",
    "ll_move",
    "ll_select",
    "ll_props",
    "ll_visible",
    "ll_opacity",
    "ll_selected",
    "ll_sync",
]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))


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


def module(e):
    k = Kit(e)
    type_names = [n for n in editor_types.EXPORTS if not n.endswith("_new")]

    def level1(x):
        _imports(e, x)
        for n in type_names:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        for n in UI_TYPES:
            x.append(e.let(n, e.fld(e.v("ui"), n)))
        x.append(e.let("st_raw", e.fld(e.v("state"), "st_raw")))
        return type_names + UI_TYPES + ["st_raw"]

    def level2(x):
        _imports(e, x)
        return _record(e, x, "row", ROW_FIELDS)

    def level3(x):
        _imports(e, x)
        x.append(e.let("rows_r", e.call(e.fld(e.v("vec"), "type"), e.v("row_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("rows_" + f, e.fld(e.v("rows_r"), "type" if f == "t" else f)))
        return ["rows_" + f for f in ["t", "own", "raw", "new"]]

    def level4(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "ll",
            [
                ("st", "st_raw"),
                ("sec", "t_i32"),
                ("list", "el_t"),
                ("props", "el_t"),
                ("rows", "rows_t"),
                ("selected", "t_i32"),
                ("buf", "bytes_t"),
                ("changed", "ev_cb_t"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3, level4])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    x.append(e.let("json", e.import_local("json", editor_json.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    for name, text in TEXTS.items():
        k.text(x, name, text)
    v = e.v
    f = k.f64

    def J(fn, *args):
        return k.lib("json", fn, *args)

    def S(fn, *args):
        return k.lib("state", fn, *args)

    def U(fn, *args):
        return k.lib("ui", fn, *args)

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def down(pre, val):
        return e.mb.as_(e.mb.as_(val, k.lo("t_i32")), k.lo(pre + "_raw"))

    def ll(name):
        return e.fld(v("ll"), name)

    def row_at(i):
        """Statements binding `r` to row `i` (raw)."""
        return [e.let("r", raw(k.m(ll("rows"), "at", i), "row"))]

    def row_of(id_):
        """Statements binding `r` to layer `id_`'s row (raw; a missing layer traps)."""
        return [e.let("r", k.dcall("ll_row", v("ll"), id_))]

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def rf(name):
        return e.fld(v("r"), name)

    k.dep(
        x,
        "ll_new",
        ["st", "key", "parent", "changed"],
        ["st_raw", "str_t", "node_raw", "ev_cb_t"],
        "ll_t",
        e.seq(
            e.let("list", U("el", v("parent"), ts("t_div"), ts("c_section"))),
            e.let("head", U("el", v("list"), ts("t_div"), ts("c_heading"))),
            U("text", v("head"), ts("t_layers")),
            e.let("props", U("el", v("parent"), ts("t_div"), ts("c_section"))),
            e.ret(
                k.call(
                    "ll_make",
                    e.rec(
                        p("st", v("st")),
                        p("sec", S("st_section", v("st"), v("key"))),
                        p("list", k.m(v("list"), "move", e.tup())),
                        p("props", k.m(v("props"), "move", e.tup())),
                        p("rows", k.call("rows_new", e.tup())),
                        p("selected", k.i32(0)),
                        p("buf", k.call("bytes_new", e.tup())),
                        p("changed", k.m(v("changed"), "move", e.tup())),
                    ),
                )
            ),
        ),
    )
    # The row of layer `id`: its position (-1: none), its record.
    k.dep(
        x,
        "ll_find",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_i32",
        e.seq(
            k.for_(
                "i", 0, e.fld(ll("rows"), "len"), "rows", *row_at(v("i")), k.if_(k.eq(rf("id"), v("id")), k.ret(v("i")))
            ),
            e.ret(k.i32(-1)),
        ),
    )
    k.dep(
        x,
        "ll_row",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "row_raw",
        e.seq(
            e.let("i", k.dcall("ll_find", v("ll"), v("id"))),
            k.if_(k.lt(v("i"), e.n(0)), trap()),
            e.ret(raw(k.m(ll("rows"), "at", v("i")), "row")),
        ),
    )
    # The rows' look and the properties shown: the selected layer's.
    k.dep(
        x,
        "ll_show",
        ["ll"],
        ["ll_raw"],
        "t_void",
        k.for_(
            "i",
            0,
            e.fld(ll("rows"), "len"),
            "rows",
            *row_at(v("i")),
            k.ifelse(
                k.eq(rf("id"), ll("selected")),
                U("class", rf("row"), ts("c_layer_sel")),
                U("class", rf("row"), ts("c_layer")),
            ),
            U("hide", rf("props"), e.mb.as_(k.ne(rf("id"), ll("selected")), k.lo("t_i32"))),
        ),
    )

    # Writes layer `id`'s entry from its row.
    k.dep(
        x,
        "ll_put",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_void",
        e.seq(
            *row_of(v("id")),
            e.let("buf", raw(ll("buf"), "bytes")),
            k.m(v("buf"), "clear", e.tup()),
            J("jw_text", v("buf"), ts("j_v")),
            J("jw_int", v("buf"), rf("visible")),
            J("jw_text", v("buf"), ts("j_o")),
            J("jw_num", v("buf"), rf("opacity")),
            J("jw_byte", v("buf"), e.n(ord("}"))),
            S("st_put", ll("st"), ll("sec"), v("id"), v("buf")),
        ),
    )
    # The rows' handlers: layer `id`'s row changed its visibility or opacity (written to the document), or was
    # clicked (selected).
    k.dep(
        x,
        "ll_on_visible",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_void",
        e.seq(
            *row_of(v("id")),
            k.set(rf("visible"), U("checked", down("input", rf("check")))),
            k.dcall("ll_put", v("ll"), v("id")),
        ),
    )
    k.dep(
        x,
        "ll_on_opacity",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_void",
        e.seq(
            *row_of(v("id")),
            k.set(rf("opacity"), U("value", down("input", rf("range")))),
            k.dcall("ll_put", v("ll"), v("id")),
        ),
    )
    k.dep(
        x,
        "ll_select",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_void",
        e.seq(k.set(ll("selected"), v("id")), k.dcall("ll_show", v("ll"))),
    )
    # The rows' closures (editor-ui's `ev_cb`): each captures the list and its layer's id, runs the handler and,
    # after a change of the document, the editor's `changed` with the event.
    for name, handler, notify in [
        ("sel_make", "ll_select", False),
        ("check_make", "ll_on_visible", True),
        ("range_make", "ll_on_opacity", True),
    ]:
        cap = e.v("self")
        steps = [k.dcall(handler, e.fld(cap, "ll"), e.fld(cap, "id"))]
        if notify:
            steps.append(e.call(e.fld(e.fld(e.fld(cap, "ll"), "changed"), "call"), k.m(e.v("arg"), "move", e.tup())))
        x.append(
            e.let(
                name,
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("ev_cb_t")),
                            p("capture", e.rec(p("ll", e.v("ll_raw")), p("id", e.v("t_i32")))),
                            p("body", e.stage(e.seq(*steps))),
                        ),
                    ),
                    "make",
                ),
            )
        )

    def row_closure(name):
        """A row's closure capturing the list and the layer's id: `fn_of(lo(name))({ll, id})`."""
        return e.call(fn_of(e, k.lo(name)), e.rec(p("ll", v("ll")), p("id", v("id"))))

    k.dep(
        x,
        "ll_add",
        ["ll", "id", "name"],
        ["ll_raw", "t_i32", "str_t"],
        "t_void",
        e.seq(
            k.if_(k.or_(k.eq(v("id"), e.n(0)), k.ge(k.dcall("ll_find", v("ll"), v("id")), e.n(0))), trap()),
            e.let("row", U("el", ll("list"), ts("t_div"), ts("c_layer"))),
            e.let("cb_sel", row_closure("sel_make")),
            e.let("l_sel", U("listen", v("row"), ts("t_click"), v("cb_sel"))),
            e.let("check", U("el", v("row"), ts("t_input"), ts("c_input"))),
            U("attr", v("check"), ts("t_type"), ts("t_checkbox")),
            U("set_checked", down("input", v("check")), e.n(1)),
            e.let("cb_check", row_closure("check_make")),
            e.let("l_check", U("listen", v("check"), ts("t_change"), v("cb_check"))),
            e.let("label", U("el", v("row"), ts("t_span"), ts("c_name"))),
            U("text", v("label"), v("name")),
            e.let("range", U("el", v("row"), ts("t_input"), ts("c_input"))),
            U("attr", v("range"), ts("t_type"), ts("t_range")),
            U("attr_num", v("range"), ts("t_min"), f(0)),
            U("attr_num", v("range"), ts("t_max"), f(1)),
            U("attr_num", v("range"), ts("t_step"), f(0.05)),
            U("set_value", down("input", v("range")), f(1)),
            e.let("cb_range", row_closure("range_make")),
            e.let("l_range", U("listen", v("range"), ts("t_input_ev"), v("cb_range"))),
            e.let("props", U("el", ll("props"), ts("t_div"), ts("c_section"))),
            k.m(
                ll("rows"),
                "push",
                k.call(
                    "row_make",
                    e.rec(
                        *[
                            p(name, k.m(v(name), "move", e.tup()))
                            for name in [
                                "l_sel",
                                "l_check",
                                "l_range",
                                "cb_sel",
                                "cb_check",
                                "cb_range",
                                "row",
                                "check",
                                "range",
                                "props",
                            ]
                        ],
                        p("visible", k.i32(1)),
                        p("opacity", f(1)),
                        p("id", v("id")),
                    ),
                ),
            ),
            k.if_(k.eq(ll("selected"), e.n(0)), k.set(ll("selected"), v("id"))),
            k.dcall("ll_show", v("ll")),
        ),
    )
    k.dep(
        x,
        "ll_remove",
        ["ll", "id"],
        ["ll_raw", "t_i32"],
        "t_void",
        e.seq(
            e.let("i", k.dcall("ll_find", v("ll"), v("id"))),
            k.if_(k.lt(v("i"), e.n(0)), trap()),
            *row_at(v("i")),
            U("remove", rf("row")),
            U("remove", rf("props")),
            e.seq(e.let("gone", k.m(ll("rows"), "remove", v("i")))),
            S("st_del", ll("st"), ll("sec"), v("id")),
            k.if_(
                k.eq(ll("selected"), v("id")),
                k.ifelse(
                    k.gt(e.fld(ll("rows"), "len"), e.n(0)),
                    k.set(ll("selected"), e.fld(raw(k.m(ll("rows"), "at", e.n(0)), "row"), "id")),
                    k.set(ll("selected"), k.i32(0)),
                ),
            ),
            k.dcall("ll_show", v("ll")),
        ),
    )
    k.dep(
        x,
        "ll_move",
        ["ll", "id", "to"],
        ["ll_raw", "t_i32", "t_i32"],
        "t_void",
        e.seq(
            e.let("i", k.dcall("ll_find", v("ll"), v("id"))),
            k.if_(
                k.or_(k.lt(v("i"), e.n(0)), k.or_(k.lt(v("to"), e.n(0)), k.ge(v("to"), e.fld(ll("rows"), "len")))),
                trap(),
            ),
            e.let("moved", k.m(ll("rows"), "remove", v("i"))),
            k.m(ll("rows"), "insert", e.tup(v("to"), k.m(v("moved"), "move", e.tup()))),
            *row_at(v("to")),
            k.ifelse(
                k.lt(k.add(v("to"), e.n(1)), e.fld(ll("rows"), "len")),
                U(
                    "insert_before",
                    ll("list"),
                    rf("row"),
                    e.fld(raw(k.m(ll("rows"), "at", k.add(v("to"), e.n(1))), "row"), "row"),
                ),
                U("append", ll("list"), rf("row")),
            ),
        ),
    )
    k.dep(x, "ll_props", ["ll", "id"], ["ll_raw", "t_i32"], "el_raw", e.seq(*row_of(v("id")), e.ret(rf("props"))))
    k.dep(x, "ll_visible", ["ll", "id"], ["ll_raw", "t_i32"], "t_i32", e.seq(*row_of(v("id")), e.ret(rf("visible"))))
    k.dep(x, "ll_opacity", ["ll", "id"], ["ll_raw", "t_i32"], "t_f64", e.seq(*row_of(v("id")), e.ret(rf("opacity"))))
    k.dep(x, "ll_selected", ["ll"], ["ll_raw"], "t_i32", e.ret(ll("selected")))
    k.dep(
        x,
        "ll_sync",
        ["ll"],
        ["ll_raw"],
        "t_void",
        e.seq(
            k.for_(
                "c",
                0,
                S("st_changed_count", ll("st"), ll("sec")),
                "changed",
                e.let("id", S("st_changed_at", ll("st"), ll("sec"), v("c"))),
                e.let("i", k.dcall("ll_find", v("ll"), v("id"))),
                k.if_(k.lt(v("i"), e.n(0)), k.cont("changed")),
                *row_at(v("i")),
                e.match_of(
                    S("st_get", ll("st"), ll("sec"), v("id")),
                    "text",
                    None,
                    p(
                        "some",
                        e.seq(
                            k.set(rf("visible"), J("jr_int", v("text"), J("jr_field", v("text"), e.n(0), ts("k_v")))),
                            k.set(rf("opacity"), J("jr_num", v("text"), J("jr_field", v("text"), e.n(0), ts("k_o")))),
                        ),
                    ),
                    p("none", e.seq(k.set(rf("visible"), e.n(1)), k.set(rf("opacity"), f(1)))),
                ),
                U("set_checked", down("input", rf("check")), rf("visible")),
                U("set_value", down("input", rf("range")), rf("opacity")),
            ),
            S("st_changed_clear", ll("st"), ll("sec")),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
