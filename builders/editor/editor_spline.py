"""editor-spline.atz: editing the smoothed strokes' splines (wat target; dependencies over vector-spline.atz, typed
with the ecosystem's libraries).

The layer shows each stroke's spline: its edit when it has one, else the smoothing layer's fit (editor-smooth.atz).
An edit is an entry of the document's section the layer registers (id: the stroke's): `{"a": amount, "n": [[x, y,
hix, hiy, hox, hoy, t, geom, i0..i(n-1), c0..c(n-1)], ...]}` for `n` channels, the nodes (vector-spline.atz's node
fields) and the smoothing
amount the edit was based on: when the stroke's amount changes the fit changes, and `ed_stale` removes such edits
(and edits of strokes that are gone) in the same change.

The editor gives the channels to edit as a vec (`chds_t`, `chds_raw`, `chds_new`) of channel
descriptors (`chd_t`; `ed_chd(kind, slot, scale, name)` makes one, owned): `kind` (0 a radius: a
circle around the node; 1 an angle in degrees: a line from it; 2 a 2D value: a handle, in the slots `slot` and
`slot` + 1), the channel `slot`, `scale` (mm per unit), and the name (a constant `str`).

The layer is an owned record (`ed_t`, `ed_raw`): `ed_new(st, key, chans, parent, sm, changed)` makes it
(owned) taking the descriptors `chans` (owned), the smoothing layer `sm` (raw; it outlives the layer) and the editor's
callable `changed` (editor-ui.atz `ev_cb`, owned), with its controls in `parent`: the selected node's segment geometry,
the active channel's interpolation over it, and removing the stroke's edit, each handled by a closure the layer owns
(capturing it), which writes the document and then calls `changed` with the event (when nothing was selected the event
is released without a call).

Pointer (`ed_pointer(ed, sm, cv, ev, kind)`, kind 0 down, 1 move, 2 up; 1 when an edit is finished: the editor
commits): pressing a node selects it and drags it; pressing the selected node's active channel handle drags the
channel; pressing a handle of a Bézier segment of the selected node drags the handle; clicking the selected node
again makes the next channel active (the others fade). `ed_insert(ed, sm, cv, ev)` (a double click) adds a node
where the curve is; `ed_key(ed, sm, ev)` removes the selected node on Delete or Backspace. Along the selected stroke,
the active channel is drawn every 4 mm, faded.

`ed_sync(ed, sm)` follows the document and the fits. The splines for later layers, in stroke id order: `ed_count(ed)`,
`ed_id(ed, i)`, `ed_eff(ed, i)` (the record, raw: `sp` its spline, `segs` its prepared segments, valid until the next
sync), `ed_version(ed)` (changes whenever any does). `ed_selected(ed)` is the selected stroke's id (0: none).
`ed_draw(ed, cv, alpha)`."""

from ..collections import closure_wasm, record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_canvas, editor_json, editor_smooth, editor_state, editor_types, editor_ui, vector_spline
from ..wasm import math_wasm
from ..wasm.kit import Kit, library, stack
from .vector_spline import GEOM_BEZIER, NODE_COLUMNS, SUBDIV, channel_at, interp_at, node_at, sample_channel_at

FILE = "editor-spline.atz"
HIT_PX = 8.0
GLYPH_SPACING = 4.0

DRAG_NONE, DRAG_NODE, DRAG_CHANNEL, DRAG_IN, DRAG_OUT = range(5)
GEOMS = ["Line", "Catmull-Rom", "Bézier", "B-spline", "Natural", "Hobby"]
INTERPS = ["Step", "Linear", "Smooth", "Catmull-Rom"]

TEXTS = {
    "t_div": "div",
    "c_status": "ed_status",
    "t_geom": "Segment",
    "t_interp": "Interpolation",
    "t_reset": "Remove this stroke's edits",
    "j_a": '{"a":',
    "j_n": ',"n":[',
    "j_close": "]}",
    "k_a": "a",
    "k_n": "n",
    **{"g%d" % i: name for i, name in enumerate(GEOMS)},
    **{"i%d" % i: name for i, name in enumerate(INTERPS)},
}

HOOKS = [("h_key_code", "get", "KeyboardEvent", "keyCode"), ("h_button", "get", "MouseEvent", "button")]
HANDLES = [("key", "KeyboardEvent"), ("mouse", "MouseEvent")]
UI_TYPES = [
    "node_raw",
    "el_t",
    "el_own",
    "event_raw",
    "select_raw",
    "ev_cb_t",
    "selectw_t",
    "selectw_own",
    "button_t",
    "button_own",
]
SPLINE_TYPES = [pre + "_" + f for pre in ["spline", "segs", "samples"] for f in ["t", "own", "raw"]] + [
    "pt_t",
    "near_t",
]
# The fixed node values of an edit's JSON, in order: the columns, the geometry; the interpolations and the channel
# values (the spline's channel count of each) follow.
NODE_FIXED = [("col", c) for c in NODE_COLUMNS] + [("geom", None)]

TYPE_EXPORTS = ["ed_t", "ed_raw", "eff_t", "eff_raw", "chd_t", "chd_raw"] + ["chds_" + f for f in ["t", "raw", "new"]]
EXPORTS = [
    "ed_chd",
    "ed_new",
    "ed_sync",
    "ed_stale",
    "ed_pointer",
    "ed_insert",
    "ed_key",
    "ed_count",
    "ed_id",
    "ed_eff",
    "ed_version",
    "ed_selected",
    "ed_draw",
]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("idmap", e.import_local("idmap", "idmap-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("canvas", e.import_local("canvas", editor_canvas.FILE)))
    x.append(e.let("smooth", e.import_local("smooth", editor_smooth.FILE)))
    x.append(e.let("spline", e.import_local("spline", vector_spline.FILE)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))


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
        x.append(e.let("cv_raw", e.fld(e.v("canvas"), "cv_raw")))
        x.append(e.let("sm_raw", e.fld(e.v("smooth"), "sm_raw")))
        x.append(e.let("st_raw", e.fld(e.v("state"), "st_raw")))
        for n in SPLINE_TYPES:
            x.append(e.let(n, e.fld(e.v("spline"), n)))
        # the spline's node record (`node_raw` is the DOM node here)
        x.append(e.let("spnode_raw", e.fld(e.v("spline"), "node_raw")))
        for pre, iface in HANDLES:
            x.append(e.let("h_" + pre, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))
            x.append(e.let(pre + "_raw", e.fld(e.v("h_" + pre), "raw")))
        return (
            type_names
            + UI_TYPES
            + ["cv_raw", "sm_raw", "st_raw", "spnode_raw"]
            + SPLINE_TYPES
            + [pre + "_raw" for pre, _ in HANDLES]
        )

    def level2(x):
        _imports(e, x)
        names = []
        names += _record(
            e,
            x,
            "chd",
            [("kind", "t_i32"), ("slot", "t_i32"), ("scale", "t_f64"), ("name_ptr", "t_pu8"), ("name_len", "t_i32")],
        )
        names += _record(
            e,
            x,
            "eff",
            [("id", "t_i32"), ("fit_stamp", "t_i32"), ("own", "t_i32"), ("sp", "spline_t"), ("segs", "segs_t")],
        )
        return names

    def level3(x):
        _imports(e, x)
        x.append(e.let("chds_r", e.call(e.fld(e.v("vec"), "type"), e.v("chd_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("chds_" + f, e.fld(e.v("chds_r"), "type" if f == "t" else f)))
        x.append(e.let("effs_r", e.call(e.fld(e.v("idmap"), "type"), e.v("eff_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("effs_" + f, e.fld(e.v("effs_r"), "type" if f == "t" else f)))
        names = ["chds_" + f for f in ["t", "own", "raw", "new"]] + ["effs_" + f for f in ["t", "own", "raw", "new"]]
        # the controls and their closures, vecs the record owns (made before the controls capture it)
        for name, elem in [("selectws", "selectw_t"), ("buttons", "button_t"), ("ev_cbs", "ev_cb_t")]:
            x.append(e.let(name + "_r", e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
            for f in ["t", "own", "raw", "new"]:
                x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
            names += [name + "_" + f for f in ["t", "own", "raw", "new"]]
        return names

    def level4(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "ed",
            [
                ("st", "st_raw"),
                ("sec", "t_i32"),
                ("chans", "chds_t"),
                ("effs", "effs_t"),
                ("buf", "bytes_t"),
                ("smp", "samples_t"),
                ("sel_stroke", "t_i32"),
                ("sel_node", "t_i32"),
                ("active", "t_i32"),
                ("drag", "t_i32"),
                ("moved", "t_i32"),
                ("again", "t_i32"),
                ("label", "el_t"),
                ("sm", "sm_raw"),
                ("selects", "selectws_t"),
                ("buttons", "buttons_t"),
                ("cbs", "ev_cbs_t"),
                ("changed", "ev_cb_t"),
                ("version", "t_i32"),
                ("down_x", "t_f64"),
                ("down_y", "t_f64"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3, level4])
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        if n.endswith("_new"):
            x.append(e.let(n, e.fld(e.v("types"), n)))
    for name, file in [
        ("json", editor_json.FILE),
        ("state", editor_state.FILE),
        ("ui", editor_ui.FILE),
        ("canvas", editor_canvas.FILE),
        ("smooth", editor_smooth.FILE),
        ("spline", vector_spline.FILE),
        ("math", math_wasm.FILE),
        ("closure", closure_wasm.FILE),
    ]:
        x.append(e.let(name, e.import_local(name, file)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    for bind, kind, iface, member in HOOKS:
        x.append(
            e.let(bind, e.call(e.fld(e.v("webidl"), kind), e.rec(p("iface", e.s(iface)), p("member", e.s(member)))))
        )
    for name, text in TEXTS.items():
        k.text(x, name, text)
    v = e.v
    f = k.f64

    def lib(name):
        return lambda fn, *args: k.lib(name, fn, *args)

    J, S, U, C, SM, SP, T, M = (lib(n) for n in ["json", "state", "ui", "canvas", "smooth", "spline", "types", "math"])

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def down(pre, val):
        return e.mb.as_(e.mb.as_(val, k.lo("t_i32")), k.lo(pre + "_raw"))

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def ed(name):
        return e.fld(v("ed"), name)

    def setv(name, val):
        return e.mb.set(v(name), val)

    def col(rec, name):
        return e.fld(rec, name)

    def at(rec, name, i):
        return k.m(col(rec, name), "at", i)

    def nat(sp, name, i):
        """The place of the field `name` of node `i` of the spline `sp`."""
        return e.fld(node_at(k, e, sp, i, k.lo("spnode_raw")), name)

    def nch(sp):
        return e.fld(sp, "nch")

    def chan(sp, i, c):
        return channel_at(k, e, sp, i, c, k.lo("spnode_raw"))

    def chani(sp, i, c):
        return interp_at(k, e, sp, i, c, k.lo("spnode_raw"))

    def count(rec, name="x"):
        return e.mb.as_(e.fld(col(rec, name), "len"), k.lo("t_i32"))

    def chd_at(i):
        """Statements binding `ch` to the channel descriptor `i` (raw)."""
        return [e.let("ch", raw(k.m(ed("chans"), "at", i), "chd"))]

    def cd(name):
        return e.fld(v("ch"), name)

    k.dep(
        x,
        "ed_chd",
        ["kind", "slot", "scale", "name"],
        ["t_i32", "t_i32", "t_f64", "str_t"],
        "chd_t",
        e.ret(
            k.call(
                "chd_make",
                e.rec(
                    p("kind", v("kind")),
                    p("slot", v("slot")),
                    p("scale", v("scale")),
                    p("name_ptr", e.fld(v("name"), "data")),
                    p("name_len", e.fld(v("name"), "len")),
                ),
            )
        ),
    )
    k.dep(
        x,
        "ed_find",
        ["ed", "id"],
        ["ed_raw", "t_i32"],
        "t_i32",
        e.ret(k.m(raw(ed("effs"), "effs"), "index_of", v("id"))),
    )
    # The edit record of stroke `id` (one the order lists is in the map: a missing one traps).
    k.dep(
        x,
        "ed_eff_of",
        ["ed", "id"],
        ["ed_raw", "t_i32"],
        "eff_raw",
        e.match_of(
            k.m(raw(ed("effs"), "effs"), "get", v("id")),
            "pl",
            None,
            p("some", k.ret(raw(e.mb.field(v("pl"), e.n(0)), "eff"))),
            p("none", trap()),
        ),
    )
    # The strokes with splines, in id order.
    k.dep(x, "ed_count", ["ed"], ["ed_raw"], "t_i32", e.ret(e.fld(raw(ed("effs"), "effs"), "len")))
    k.dep(x, "ed_id", ["ed", "i"], ["ed_raw", "t_i32"], "t_i32", e.ret(k.m(raw(ed("effs"), "effs"), "id_at", v("i"))))

    def node_value(sp, i, what, c):
        """The place of a fixed node value: a column or the geometry."""
        return nat(sp, c if what == "col" else "geom", i)

    # The edit of stroke `id` read into `sp` (1), or 0 when it has none.
    k.dep(
        x,
        "ed_read",
        ["ed", "id", "sp"],
        ["ed_raw", "t_i32", "spline_raw"],
        "t_i32",
        e.match_of(
            S("st_get", ed("st"), ed("sec"), v("id")),
            "text",
            None,
            p(
                "some",
                e.seq(
                    SP("sp_clear", v("sp")),
                    e.let("el", J("jr_first", v("text"), J("jr_field", v("text"), e.n(0), ts("k_n")))),
                    k.loop(
                        "nodes",
                        k.if_(k.lt(v("el"), e.n(0)), k.brk("nodes")),
                        e.let("i", SP("sp_push", v("sp"))),
                        e.let("fq", J("jr_first", v("text"), v("el"))),
                        *[
                            e.seq(
                                k.if_(k.lt(v("fq"), e.n(0)), k.brk("nodes")),
                                k.set(
                                    node_value(v("sp"), v("i"), what, c),
                                    (
                                        k.trunc(J("jr_num", v("text"), v("fq")))
                                        if what == "geom"
                                        else J("jr_num", v("text"), v("fq"))
                                    ),
                                ),
                                setv("fq", J("jr_next", v("text"), v("fq"))),
                            )
                            for what, c in NODE_FIXED
                        ],
                        k.for_(
                            "c",
                            0,
                            nch(v("sp")),
                            "interps",
                            k.if_(k.lt(v("fq"), e.n(0)), k.brk("nodes")),
                            k.set(chani(v("sp"), v("i"), v("c")), k.trunc(J("jr_num", v("text"), v("fq")))),
                            setv("fq", J("jr_next", v("text"), v("fq"))),
                        ),
                        k.for_(
                            "c",
                            0,
                            nch(v("sp")),
                            "values",
                            k.if_(k.lt(v("fq"), e.n(0)), k.brk("nodes")),
                            k.set(chan(v("sp"), v("i"), v("c")), J("jr_num", v("text"), v("fq"))),
                            setv("fq", J("jr_next", v("text"), v("fq"))),
                        ),
                        setv("el", J("jr_next", v("text"), v("el"))),
                    ),
                    k.ret(k.i32(1)),
                ),
            ),
            p("none", k.ret(k.i32(0))),
        ),
    )
    k.dep(
        x,
        "ed_write",
        ["ed", "sm", "eff"],
        ["ed_raw", "sm_raw", "eff_raw"],
        "t_void",
        e.seq(
            e.let("buf", raw(ed("buf"), "bytes")),
            e.let("sp", raw(e.fld(v("eff"), "sp"), "spline")),
            k.m(v("buf"), "clear", e.tup()),
            J("jw_text", v("buf"), ts("j_a")),
            J("jw_num", v("buf"), SM("sm_amount", v("sm"), e.fld(v("eff"), "id"))),
            J("jw_text", v("buf"), ts("j_n")),
            k.for_(
                "i",
                0,
                SP("sp_count", v("sp")),
                "nodes",
                k.if_(k.gt(v("i"), e.n(0)), J("jw_byte", v("buf"), e.n(ord(",")))),
                J("jw_byte", v("buf"), e.n(ord("["))),
                *[
                    e.seq(
                        *([J("jw_byte", v("buf"), e.n(ord(",")))] if fi > 0 else []),
                        (
                            J("jw_int", v("buf"), node_value(v("sp"), v("i"), what, c))
                            if what == "geom"
                            else J("jw_num", v("buf"), node_value(v("sp"), v("i"), what, c))
                        ),
                    )
                    for fi, (what, c) in enumerate(NODE_FIXED)
                ],
                k.for_(
                    "c",
                    0,
                    nch(v("sp")),
                    "interps",
                    J("jw_byte", v("buf"), e.n(ord(","))),
                    J("jw_int", v("buf"), chani(v("sp"), v("i"), v("c"))),
                ),
                k.for_(
                    "c",
                    0,
                    nch(v("sp")),
                    "values",
                    J("jw_byte", v("buf"), e.n(ord(","))),
                    J("jw_num", v("buf"), chan(v("sp"), v("i"), v("c"))),
                ),
                J("jw_byte", v("buf"), e.n(ord("]"))),
            ),
            J("jw_text", v("buf"), ts("j_close")),
            S("st_put", ed("st"), ed("sec"), e.fld(v("eff"), "id"), v("buf")),
        ),
    )

    S_GEOM, S_INTERP = 0, 1

    def sel_widget(i):
        """A select control's element (raw): control `i` of the record's selects."""
        return raw(e.fld(k.m(ed("selects"), "at", e.n(i)), "el"), "select")

    k.dep(
        x,
        "ed_show",
        ["ed"],
        ["ed_raw"],
        "t_void",
        e.seq(
            *chd_at(ed("active")),
            U("text", ed("label"), k.str_of(cd("name_ptr"), cd("name_len"))),
            k.if_(k.or_(k.eq(ed("sel_stroke"), e.n(0)), k.lt(ed("sel_node"), e.n(0))), k.ret()),
            e.let("sp", raw(e.fld(k.dcall("ed_eff_of", v("ed"), ed("sel_stroke")), "sp"), "spline")),
            U("set_selected", sel_widget(S_GEOM), nat(v("sp"), "geom", ed("sel_node"))),
            U("set_selected", sel_widget(S_INTERP), chani(v("sp"), ed("sel_node"), cd("slot"))),
        ),
    )
    k.dep(
        x,
        "ed_sync",
        ["ed", "sm"],
        ["ed_raw", "sm_raw"],
        "t_void",
        e.seq(
            e.let("effs", raw(ed("effs"), "effs")),
            # edited strokes rebuild
            k.for_(
                "c",
                0,
                S("st_changed_count", ed("st"), ed("sec")),
                "changed",
                e.let("cid", S("st_changed_at", ed("st"), ed("sec"), v("c"))),
                k.if_(
                    k.ge(k.dcall("ed_find", v("ed"), v("cid")), e.n(0)),
                    k.set(e.fld(k.dcall("ed_eff_of", v("ed"), v("cid")), "fit_stamp"), e.n(-1)),
                ),
            ),
            S("st_changed_clear", ed("st"), ed("sec")),
            # strokes the smoothing layer no longer fits go (from the end: the positions shift)
            e.let("i", e.mb.as_(e.fld(v("effs"), "len"), k.lo("t_i32"))),
            k.loop(
                "gone",
                k.if_(k.le(v("i"), e.n(0)), k.brk("gone")),
                setv("i", k.sub(v("i"), e.n(1))),
                e.let("gid", k.m(v("effs"), "id_at", v("i"))),
                k.if_(
                    k.lt(SM("sm_find", v("sm"), v("gid")), e.n(0)),
                    e.seq(e.let("was", k.m(v("effs"), "remove", v("gid")))),
                    k.set(ed("version"), k.add(ed("version"), e.n(1))),
                ),
            ),
            k.for_(
                "s",
                0,
                SM("sm_count", v("sm")),
                "fits",
                e.let("id", SM("sm_id", v("sm"), v("s"))),
                k.if_(
                    k.lt(k.dcall("ed_find", v("ed"), v("id")), e.n(0)),
                    k.m(
                        v("effs"),
                        "put",
                        e.tup(
                            v("id"),
                            k.call(
                                "eff_make",
                                e.rec(
                                    p("id", v("id")),
                                    p("fit_stamp", k.i32(-1)),
                                    p("own", k.i32(0)),
                                    p("sp", SP("sp_new", e.mb.as_(e.fld(ed("chans"), "len"), k.lo("t_i32")))),
                                    p("segs", SP("segs_new")),
                                ),
                            ),
                        ),
                    ),
                ),
                e.let("ea", k.dcall("ed_eff_of", v("ed"), v("id"))),
                e.let("fs", SM("sm_stamp", v("sm"), v("s"))),
                k.if_(k.eq(e.fld(v("ea"), "fit_stamp"), v("fs")), k.cont("fits")),
                k.set(e.fld(v("ea"), "fit_stamp"), v("fs")),
                k.set(e.fld(v("ea"), "own"), k.dcall("ed_read", v("ed"), v("id"), e.fld(v("ea"), "sp"))),
                k.if_(
                    k.eq(e.fld(v("ea"), "own"), e.n(0)),
                    SP("sp_copy", e.fld(v("ea"), "sp"), e.fld(SM("sm_fit", v("sm"), v("s")), "sp")),
                ),
                SP("sp_prepare", e.fld(v("ea"), "sp"), e.fld(v("ea"), "segs")),
                k.set(ed("version"), k.add(ed("version"), e.n(1))),
            ),
            # the selection follows
            e.let("sa", k.dcall("ed_find", v("ed"), ed("sel_stroke"))),
            k.if_(k.lt(v("sa"), e.n(0)), k.set(ed("sel_stroke"), e.n(0)), k.set(ed("sel_node"), e.n(-1))),
            k.if_(
                k.ge(v("sa"), e.n(0)),
                e.let(
                    "sn", SP("sp_count", raw(e.fld(k.dcall("ed_eff_of", v("ed"), ed("sel_stroke")), "sp"), "spline"))
                ),
                k.if_(k.ge(ed("sel_node"), v("sn")), k.set(ed("sel_node"), k.sub(v("sn"), e.n(1)))),
            ),
            k.dcall("ed_show", v("ed")),
        ),
    )
    k.dep(
        x,
        "ed_stale",
        ["ed", "sm"],
        ["ed_raw", "sm_raw"],
        "t_void",
        e.seq(
            e.let("i", k.i32(0)),
            k.loop(
                "entries",
                k.if_(k.ge(v("i"), S("st_count", ed("st"), ed("sec"))), k.brk("entries")),
                e.let("id", S("st_id_at", ed("st"), ed("sec"), v("i"))),
                e.let("text", S("st_text_at", ed("st"), ed("sec"), v("i"))),
                e.let("base", J("jr_num", v("text"), J("jr_field", v("text"), e.n(0), ts("k_a")))),
                k.if_(
                    k.or_(
                        k.lt(SM("sm_find", v("sm"), v("id")), e.n(0)),
                        k.ne(v("base"), SM("sm_amount", v("sm"), v("id"))),
                    ),
                    S("st_del", ed("st"), ed("sec"), v("id")),
                    k.cont("entries"),
                ),
                setv("i", k.add(v("i"), e.n(1))),
            ),
        ),
    )

    # --- controls ---
    def with_selection(*body):
        """Statements over the selected node (`ea` its edit record, `sp` its spline), then the spline re-prepared and
        the edit written; 0 when nothing is selected, else 1."""
        return e.seq(
            k.if_(k.or_(k.eq(ed("sel_stroke"), e.n(0)), k.lt(ed("sel_node"), e.n(0))), k.ret(k.i32(0))),
            e.let("ea", k.dcall("ed_eff_of", v("ed"), ed("sel_stroke"))),
            e.let("sp", raw(e.fld(v("ea"), "sp"), "spline")),
            *body,
            SP("sp_prepare", v("sp"), e.fld(v("ea"), "segs")),
            k.dcall("ed_write", v("ed"), ed("sm"), v("ea")),
            e.ret(k.i32(1)),
        )

    k.dep(
        x,
        "ed_on_geom",
        ["ed"],
        ["ed_raw"],
        "t_i32",
        with_selection(k.set(nat(v("sp"), "geom", ed("sel_node")), U("selected", sel_widget(S_GEOM)))),
    )
    k.dep(
        x,
        "ed_on_interp",
        ["ed"],
        ["ed_raw"],
        "t_i32",
        with_selection(
            *chd_at(ed("active")),
            e.let("mode", U("selected", sel_widget(S_INTERP))),
            k.set(chani(v("sp"), ed("sel_node"), cd("slot")), v("mode")),
            # a 2D value's second slot goes along
            k.if_(
                k.eq(cd("kind"), e.n(2)), k.set(chani(v("sp"), ed("sel_node"), k.add(cd("slot"), e.n(1))), v("mode"))
            ),
        ),
    )
    k.dep(
        x,
        "ed_on_reset",
        ["ed"],
        ["ed_raw"],
        "t_i32",
        e.seq(
            k.if_(k.eq(ed("sel_stroke"), e.n(0)), k.ret(k.i32(0))),
            S("st_del", ed("st"), ed("sec"), ed("sel_stroke")),
            e.ret(k.i32(1)),
        ),
    )

    # The controls' closures (editor-ui's `ev_cb`): each captures the layer and runs its handler; when it changed the
    # document the editor's `changed` gets the event, else the event is released.
    for name, handler in [("geom_make", "ed_on_geom"), ("interp_make", "ed_on_interp"), ("reset_make", "ed_on_reset")]:
        cap = e.fld(e.v("self"), "ed")
        x.append(
            e.let(
                name,
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("ev_cb_t")),
                            p("capture", e.rec(p("ed", e.v("ed_raw")))),
                            p(
                                "body",
                                e.stage(
                                    k.ifelse(
                                        k.ne(k.dcall(handler, cap), e.n(0)),
                                        e.call(e.fld(e.fld(cap, "changed"), "call"), k.m(e.v("arg"), "move", e.tup())),
                                        e.seq(e.let("released", k.m(e.v("arg"), "move", e.tup()))),
                                    )
                                ),
                            ),
                        ),
                    ),
                    "make",
                ),
            )
        )

    def own_closure(name):
        """A closure capturing the layer (its record, borrowed through its binding `ed`), pushed on its closures."""
        return k.m(ed("cbs"), "push", e.call(fn_of(e, k.lo(name)), e.rec(p("ed", raw(v("ed"), "ed")))))

    def last_cb():
        return k.m(ed("cbs"), "at", k.sub(e.fld(ed("cbs"), "len"), e.n(1)))

    def last_select():
        return e.fld(k.m(ed("selects"), "at", k.sub(e.fld(ed("selects"), "len"), e.n(1))), "el")

    k.dep(
        x,
        "ed_new",
        ["st", "key", "chans", "parent", "sm", "changed"],
        ["st_raw", "str_t", "chds_t", "node_raw", "sm_raw", "ev_cb_t"],
        "ed_t",
        e.seq(
            e.let("label", U("el", v("parent"), ts("t_div"), ts("c_status"))),
            e.let(
                "ed",
                k.call(
                    "ed_make",
                    e.rec(
                        p("st", v("st")),
                        p("sec", S("st_section", v("st"), v("key"))),
                        p("chans", k.m(v("chans"), "move", e.tup())),
                        p("effs", k.call("effs_new", e.tup())),
                        p("buf", k.call("bytes_new", e.tup())),
                        p("smp", SP("samples_new")),
                        p("sel_stroke", k.i32(0)),
                        p("sel_node", k.i32(-1)),
                        p("active", k.i32(0)),
                        p("drag", k.i32(DRAG_NONE)),
                        p("moved", k.i32(0)),
                        p("again", k.i32(0)),
                        p("label", k.m(v("label"), "move", e.tup())),
                        p("sm", v("sm")),
                        p("selects", k.call("selectws_new", e.tup())),
                        p("buttons", k.call("buttons_new", e.tup())),
                        p("cbs", k.call("ev_cbs_new", e.tup())),
                        p("changed", k.m(v("changed"), "move", e.tup())),
                        p("version", k.i32(0)),
                        p("down_x", f(0)),
                        p("down_y", f(0)),
                    ),
                ),
            ),
            # the controls, each with a closure over the layer (made now that the record exists)
            own_closure("geom_make"),
            k.m(ed("selects"), "push", U("select", v("parent"), ts("t_geom"), last_cb())),
            *[U("option", last_select(), ts("g%d" % i)) for i in range(len(GEOMS))],
            own_closure("interp_make"),
            k.m(ed("selects"), "push", U("select", v("parent"), ts("t_interp"), last_cb())),
            *[U("option", last_select(), ts("i%d" % i)) for i in range(len(INTERPS))],
            own_closure("reset_make"),
            k.m(ed("buttons"), "push", U("button", v("parent"), ts("t_reset"), last_cb())),
            e.ret(k.m(v("ed"), "move", e.tup())),
        ),
    )

    # --- channel widgets ---
    # The point the channel `ch`'s widget ends at, for node `i` of `sp` (into `hx`, `hy`).
    def widget_end(sp, i):
        kind = cd("kind")
        slot = cd("slot")
        scale = cd("scale")
        val0 = chan(sp, i, slot)
        val1 = chan(sp, i, k.add(slot, e.n(1)))
        rad = k.mul(val0, e.n(0.017453292519943295))
        return [
            e.let(
                "hx",
                k.ifelse(
                    k.eq(kind, e.n(0)),
                    k.add(nat(sp, "x", i), k.mul(val0, scale)),
                    k.ifelse(
                        k.eq(kind, e.n(1)),
                        k.add(nat(sp, "x", i), k.mul(M("m_cos", rad), scale)),
                        k.add(nat(sp, "x", i), k.mul(val0, scale)),
                    ),
                ),
            ),
            e.let(
                "hy",
                k.ifelse(
                    k.eq(kind, e.n(0)),
                    nat(sp, "y", i),
                    k.ifelse(
                        k.eq(kind, e.n(1)),
                        k.add(nat(sp, "y", i), k.mul(M("m_sin", rad), scale)),
                        k.add(nat(sp, "y", i), k.mul(val1, scale)),
                    ),
                ),
            ),
        ]

    def hit(px_, py_):
        return k.lt(M("m_hypot", k.sub(px_, v("wx")), k.sub(py_, v("wy"))), v("tol"))

    def bezier_before(sp):
        """Whether the selected node has a segment before it, a Bézier one (the index is read only when there is
        one: `and_` evaluates both sides)."""
        return k.ne(
            k.ifelse(
                k.gt(ed("sel_node"), e.n(0)),
                e.mb.as_(k.eq(nat(sp, "geom", k.sub(ed("sel_node"), e.n(1))), e.n(GEOM_BEZIER)), k.lo("t_i32")),
                k.i32(0),
            ),
            e.n(0),
        )

    def bezier_after(sp):
        return k.and_(
            k.lt(ed("sel_node"), k.sub(SP("sp_count", sp), e.n(1))),
            k.eq(nat(sp, "geom", ed("sel_node")), e.n(GEOM_BEZIER)),
        )

    def handle(sp, i, which):
        """The in (`which` "i") or out ("o") handle point of node `i`."""
        return [
            k.add(nat(sp, "x", i), nat(sp, "h" + which + "x", i)),
            k.add(nat(sp, "y", i), nat(sp, "h" + which + "y", i)),
        ]

    k.dep(
        x,
        "ed_pointer",
        ["ed", "sm", "cv", "ev", "kind"],
        ["ed_raw", "sm_raw", "cv_raw", "event_raw", "t_i32"],
        "t_i32",
        e.seq(
            e.let("wx", C("cv_wx", v("cv"), v("ev"))),
            e.let("wy", C("cv_wy", v("cv"), v("ev"))),
            e.let("tol", k.div(e.n(HIT_PX), C("cv_scale", v("cv")))),
            k.if_(
                k.eq(v("kind"), e.n(0)),
                k.if_(
                    k.ne(e.mb.as_(k.call("h_button", down("mouse", v("ev"))), k.lo("t_i32")), e.n(0)), k.ret(k.i32(0))
                ),
                k.set(ed("moved"), e.n(0)),
                k.set(ed("again"), e.n(0)),
                k.set(ed("down_x"), v("wx")),
                k.set(ed("down_y"), v("wy")),
                k.set(ed("drag"), e.n(DRAG_NONE)),
                # the selected node's widgets first
                k.if_(
                    k.and_(k.gt(ed("sel_stroke"), e.n(0)), k.ge(ed("sel_node"), e.n(0))),
                    e.let("sp", raw(e.fld(k.dcall("ed_eff_of", v("ed"), ed("sel_stroke")), "sp"), "spline")),
                    *chd_at(ed("active")),
                    *widget_end(v("sp"), ed("sel_node")),
                    k.if_(hit(v("hx"), v("hy")), k.set(ed("drag"), e.n(DRAG_CHANNEL)), k.ret(k.i32(0))),
                    k.if_(
                        bezier_before(v("sp")),
                        k.if_(
                            hit(*handle(v("sp"), ed("sel_node"), "i")), k.set(ed("drag"), e.n(DRAG_IN)), k.ret(k.i32(0))
                        ),
                    ),
                    k.if_(
                        bezier_after(v("sp")),
                        k.if_(
                            hit(*handle(v("sp"), ed("sel_node"), "o")),
                            k.set(ed("drag"), e.n(DRAG_OUT)),
                            k.ret(k.i32(0)),
                        ),
                    ),
                ),
                # then the nodes, the selected stroke's first
                e.let("best", f(1e300)),
                e.let("bs", k.i32(0)),
                e.let("bn", k.i32(-1)),
                k.for_(
                    "i",
                    0,
                    k.dcall("ed_count", v("ed")),
                    "strokes",
                    e.let("id", k.dcall("ed_id", v("ed"), v("i"))),
                    e.let("sp", raw(e.fld(k.dcall("ed_eff_of", v("ed"), v("id")), "sp"), "spline")),
                    e.let("ni", SP("sp_nearest_node", v("sp"), v("wx"), v("wy"))),
                    k.if_(k.lt(v("ni"), e.n(0)), k.cont("strokes")),
                    e.let(
                        "d",
                        M(
                            "m_hypot",
                            k.sub(nat(v("sp"), "x", v("ni")), v("wx")),
                            k.sub(nat(v("sp"), "y", v("ni")), v("wy")),
                        ),
                    ),
                    k.if_(k.eq(v("id"), ed("sel_stroke")), setv("d", k.mul(v("d"), e.n(0.5)))),
                    k.if_(k.lt(v("d"), v("best")), setv("best", v("d")), setv("bs", v("id")), setv("bn", v("ni"))),
                ),
                k.if_(
                    k.and_(k.ge(v("bn"), e.n(0)), k.lt(v("best"), v("tol"))),
                    k.set(
                        ed("again"),
                        e.mb.as_(k.and_(k.eq(v("bs"), ed("sel_stroke")), k.eq(v("bn"), ed("sel_node"))), k.lo("t_i32")),
                    ),
                    k.set(ed("sel_stroke"), v("bs")),
                    k.set(ed("sel_node"), v("bn")),
                    k.set(ed("drag"), e.n(DRAG_NODE)),
                    SM("sm_select", v("sm"), v("bs")),
                    k.dcall("ed_show", v("ed")),
                    k.ret(k.i32(0)),
                ),
                k.set(ed("sel_stroke"), e.n(0)),
                k.set(ed("sel_node"), e.n(-1)),
                SM("sm_select", v("sm"), k.i32(0)),
                k.ret(k.i32(0)),
            ),
            k.if_(k.eq(ed("drag"), e.n(DRAG_NONE)), k.ret(k.i32(0))),
            k.if_(
                k.gt(
                    M("m_hypot", k.sub(v("wx"), ed("down_x")), k.sub(v("wy"), ed("down_y"))), k.mul(v("tol"), e.n(0.25))
                ),
                k.set(ed("moved"), e.n(1)),
            ),
            e.let("ea", k.dcall("ed_eff_of", v("ed"), ed("sel_stroke"))),
            e.let("sp", raw(e.fld(v("ea"), "sp"), "spline")),
            e.let("n", ed("sel_node")),
            k.if_(
                k.ne(ed("moved"), e.n(0)),
                k.if_(
                    k.eq(ed("drag"), e.n(DRAG_NODE)),
                    k.set(nat(v("sp"), "x", v("n")), v("wx")),
                    k.set(nat(v("sp"), "y", v("n")), v("wy")),
                ),
                k.if_(
                    k.eq(ed("drag"), e.n(DRAG_IN)),
                    k.set(nat(v("sp"), "hix", v("n")), k.sub(v("wx"), nat(v("sp"), "x", v("n")))),
                    k.set(nat(v("sp"), "hiy", v("n")), k.sub(v("wy"), nat(v("sp"), "y", v("n")))),
                ),
                k.if_(
                    k.eq(ed("drag"), e.n(DRAG_OUT)),
                    k.set(nat(v("sp"), "hox", v("n")), k.sub(v("wx"), nat(v("sp"), "x", v("n")))),
                    k.set(nat(v("sp"), "hoy", v("n")), k.sub(v("wy"), nat(v("sp"), "y", v("n")))),
                ),
                k.if_(
                    k.eq(ed("drag"), e.n(DRAG_CHANNEL)),
                    *chd_at(ed("active")),
                    e.let("dx", k.div(k.sub(v("wx"), nat(v("sp"), "x", v("n"))), cd("scale"))),
                    e.let("dy", k.div(k.sub(v("wy"), nat(v("sp"), "y", v("n"))), cd("scale"))),
                    k.if_(
                        k.eq(cd("kind"), e.n(0)),
                        k.set(chan(v("sp"), v("n"), cd("slot")), M("m_hypot", v("dx"), v("dy"))),
                    ),
                    k.if_(
                        k.eq(cd("kind"), e.n(1)),
                        k.set(
                            chan(v("sp"), v("n"), cd("slot")),
                            k.mul(M("m_atan2", v("dy"), v("dx")), e.n(57.29577951308232)),
                        ),
                    ),
                    k.if_(
                        k.eq(cd("kind"), e.n(2)),
                        k.set(chan(v("sp"), v("n"), cd("slot")), v("dx")),
                        k.set(chan(v("sp"), v("n"), k.add(cd("slot"), e.n(1))), v("dy")),
                    ),
                ),
                SP("sp_prepare", v("sp"), e.fld(v("ea"), "segs")),
                k.set(ed("version"), k.add(ed("version"), e.n(1))),
            ),
            k.if_(k.ne(v("kind"), e.n(2)), k.ret(k.i32(0))),
            e.let("was", ed("drag")),
            k.set(ed("drag"), e.n(DRAG_NONE)),
            k.if_(k.ne(ed("moved"), e.n(0)), k.dcall("ed_write", v("ed"), v("sm"), v("ea")), k.ret(k.i32(1))),
            # a click on the selected node: the next channel
            k.if_(
                k.and_(k.eq(v("was"), e.n(DRAG_NODE)), k.ne(ed("again"), e.n(0))),
                k.set(
                    ed("active"), k.rem(k.add(ed("active"), e.n(1)), e.mb.as_(e.fld(ed("chans"), "len"), k.lo("t_i32")))
                ),
                k.dcall("ed_show", v("ed")),
            ),
            e.ret(k.i32(0)),
        ),
    )
    k.dep(
        x,
        "ed_insert",
        ["ed", "sm", "cv", "ev"],
        ["ed_raw", "sm_raw", "cv_raw", "event_raw"],
        "t_i32",
        e.seq(
            e.let("wx", C("cv_wx", v("cv"), v("ev"))),
            e.let("wy", C("cv_wy", v("cv"), v("ev"))),
            e.let("tol", k.div(e.n(HIT_PX), C("cv_scale", v("cv")))),
            k.for_(
                "i",
                0,
                k.dcall("ed_count", v("ed")),
                "strokes",
                e.let("id", k.dcall("ed_id", v("ed"), v("i"))),
                e.let("ea", k.dcall("ed_eff_of", v("ed"), v("id"))),
                e.let("sp", raw(e.fld(v("ea"), "sp"), "spline")),
                e.let("segs", raw(e.fld(v("ea"), "segs"), "segs")),
                e.let("near", SP("sp_nearest_seg", v("segs"), v("wx"), v("wy"))),
                e.let("si", e.mb.field(v("near"), e.n(0))),
                k.if_(k.lt(v("si"), e.n(0)), k.cont("strokes")),
                e.let("u", e.mb.field(v("near"), e.n(1))),
                e.let("pt", SP("sp_point", v("segs"), v("si"), v("u"))),
                e.let("px", e.mb.field(v("pt"), e.n(0))),
                e.let("py", e.mb.field(v("pt"), e.n(1))),
                e.let("tx", e.mb.field(v("pt"), e.n(2))),
                e.let("ty", e.mb.field(v("pt"), e.n(3))),
                k.if_(
                    k.ge(M("m_hypot", k.sub(v("px"), v("wx")), k.sub(v("py"), v("wy"))), v("tol")), k.cont("strokes")
                ),
                e.let("seglen", at(v("segs"), "l", k.add(k.mul(v("si"), e.n(SUBDIV + 1)), e.n(SUBDIV)))),
                # the new node's values from the curve there, before the insertion shifts the nodes
                e.let("nt", M("m_lerp", nat(v("sp"), "t", v("si")), nat(v("sp"), "t", k.add(v("si"), e.n(1))), v("u"))),
                e.let("ng", nat(v("sp"), "geom", v("si"))),
                e.let("cvs", k.call("f64s_new", e.tup())),
                e.let("cis", k.call("ints_new", e.tup())),
                k.for_(
                    "c",
                    0,
                    nch(v("sp")),
                    "chvals",
                    k.m(v("cvs"), "push", SP("sp_channel", v("sp"), v("si"), v("u"), v("c"))),
                    k.m(v("cis"), "push", chani(v("sp"), v("si"), v("c"))),
                ),
                e.let("ni", k.add(v("si"), e.n(1))),
                SP("sp_insert", v("sp"), v("ni")),
                k.set(nat(v("sp"), "x", v("ni")), v("px")),
                k.set(nat(v("sp"), "y", v("ni")), v("py")),
                k.set(nat(v("sp"), "t", v("ni")), v("nt")),
                k.set(nat(v("sp"), "geom", v("ni")), v("ng")),
                k.for_(
                    "c",
                    0,
                    nch(v("sp")),
                    "chset",
                    k.set(chan(v("sp"), v("ni"), v("c")), k.m(v("cvs"), "at", v("c"))),
                    k.set(chani(v("sp"), v("ni"), v("c")), k.m(v("cis"), "at", v("c"))),
                ),
                k.set(nat(v("sp"), "hix", v("ni")), k.mul(v("tx"), k.div(v("seglen"), e.n(-6)))),
                k.set(nat(v("sp"), "hiy", v("ni")), k.mul(v("ty"), k.div(v("seglen"), e.n(-6)))),
                k.set(nat(v("sp"), "hox", v("ni")), k.mul(v("tx"), k.div(v("seglen"), e.n(6)))),
                k.set(nat(v("sp"), "hoy", v("ni")), k.mul(v("ty"), k.div(v("seglen"), e.n(6)))),
                SP("sp_prepare", v("sp"), v("segs")),
                k.set(ed("sel_stroke"), v("id")),
                k.set(ed("sel_node"), v("ni")),
                SM("sm_select", v("sm"), v("id")),
                k.dcall("ed_write", v("ed"), v("sm"), v("ea")),
                k.dcall("ed_show", v("ed")),
                k.ret(k.i32(1)),
            ),
            e.ret(k.i32(0)),
        ),
    )
    k.dep(
        x,
        "ed_key",
        ["ed", "sm", "ev"],
        ["ed_raw", "sm_raw", "event_raw"],
        "t_i32",
        e.seq(
            e.let("code", k.m(k.call("h_key_code", down("key", v("ev"))), "wrap", k.lo("t_i32"))),
            k.if_(k.and_(k.ne(v("code"), e.n(46)), k.ne(v("code"), e.n(8))), k.ret(k.i32(0))),
            k.if_(k.or_(k.eq(ed("sel_stroke"), e.n(0)), k.lt(ed("sel_node"), e.n(0))), k.ret(k.i32(0))),
            e.let("ea", k.dcall("ed_eff_of", v("ed"), ed("sel_stroke"))),
            e.let("sp", raw(e.fld(v("ea"), "sp"), "spline")),
            k.if_(k.le(SP("sp_count", v("sp")), e.n(2)), k.ret(k.i32(0))),
            SP("sp_remove", v("sp"), ed("sel_node")),
            k.if_(k.gt(ed("sel_node"), e.n(0)), k.set(ed("sel_node"), k.sub(ed("sel_node"), e.n(1)))),
            SP("sp_prepare", v("sp"), e.fld(v("ea"), "segs")),
            k.dcall("ed_write", v("ed"), v("sm"), v("ea")),
            k.dcall("ed_show", v("ed")),
            U("prevent", v("ev")),
            e.ret(k.i32(1)),
        ),
    )
    k.dep(
        x,
        "ed_eff",
        ["ed", "i"],
        ["ed_raw", "t_i32"],
        "eff_raw",
        e.ret(k.dcall("ed_eff_of", v("ed"), k.dcall("ed_id", v("ed"), v("i")))),
    )
    k.dep(x, "ed_version", ["ed"], ["ed_raw"], "t_i32", e.ret(ed("version")))
    k.dep(x, "ed_selected", ["ed"], ["ed_raw"], "t_i32", e.ret(ed("sel_stroke")))

    # --- drawing ---
    # A channel's glyph at (x, y) for the values `v0` (the channel's slot) and `v1` (the next).
    k.dep(
        x,
        "ed_glyph",
        ["ed", "cv", "ch", "x", "y", "v0", "v1"],
        ["ed_raw", "cv_raw", "chd_raw", "t_f64", "t_f64", "t_f64", "t_f64"],
        "t_void",
        e.seq(
            e.let("kind", cd("kind")),
            e.let("scale", cd("scale")),
            k.if_(
                k.eq(v("kind"), e.n(0)),
                C("cv_circle", v("cv"), v("x"), v("y"), k.fmax(k.mul(k.fabs(v("v0")), v("scale")), e.n(0.01)), e.n(0)),
            ),
            k.if_(
                k.eq(v("kind"), e.n(1)),
                e.let("rad", k.mul(v("v0"), e.n(0.017453292519943295))),
                C(
                    "cv_line",
                    v("cv"),
                    v("x"),
                    v("y"),
                    k.add(v("x"), k.mul(M("m_cos", v("rad")), v("scale"))),
                    k.add(v("y"), k.mul(M("m_sin", v("rad")), v("scale"))),
                ),
            ),
            k.if_(
                k.eq(v("kind"), e.n(2)),
                C(
                    "cv_line",
                    v("cv"),
                    v("x"),
                    v("y"),
                    k.add(v("x"), k.mul(v("v0"), v("scale"))),
                    k.add(v("y"), k.mul(v("v1"), v("scale"))),
                ),
            ),
        ),
    )

    def glyph(ch, x_, y_, v0, v1):
        return k.dcall("ed_glyph", v("ed"), v("cv"), ch, x_, y_, v0, v1)

    k.dep(
        x,
        "ed_draw",
        ["ed", "cv", "alpha"],
        ["ed_raw", "cv_raw", "t_f64"],
        "t_void",
        e.seq(
            e.let("px", k.div(e.n(1), C("cv_scale", v("cv")))),
            e.let("smp", raw(ed("smp"), "samples")),
            k.for_(
                "i",
                0,
                k.dcall("ed_count", v("ed")),
                "strokes",
                e.let("id", k.dcall("ed_id", v("ed"), v("i"))),
                e.let("ea", k.dcall("ed_eff_of", v("ed"), v("id"))),
                e.let("sp", raw(e.fld(v("ea"), "sp"), "spline")),
                e.let("segs", raw(e.fld(v("ea"), "segs"), "segs")),
                e.let("selected", e.mb.as_(k.eq(v("id"), ed("sel_stroke")), k.lo("t_i32"))),
                C("cv_style", v("cv"), v("alpha"), k.ifelse(k.ne(v("selected"), e.n(0)), f(2), f(1.25))),
                k.for_(
                    "s",
                    0,
                    e.fld(col(v("segs"), "x0"), "len"),
                    "segs",
                    k.for_(
                        "j",
                        0,
                        e.n(17),
                        "steps",
                        e.let("pt", SP("sp_point", v("segs"), v("s"), k.div(k.to_f64(v("j")), e.n(16)))),
                        k.ifelse(
                            k.and_(k.eq(v("s"), e.n(0)), k.eq(v("j"), e.n(0))),
                            C("cv_move", v("cv"), e.mb.field(v("pt"), e.n(0)), e.mb.field(v("pt"), e.n(1))),
                            C("cv_line_to", v("cv"), e.mb.field(v("pt"), e.n(0)), e.mb.field(v("pt"), e.n(1))),
                        ),
                    ),
                ),
                C("cv_stroke", v("cv")),
                k.for_(
                    "n",
                    0,
                    SP("sp_count", v("sp")),
                    "nodes",
                    C(
                        "cv_circle",
                        v("cv"),
                        nat(v("sp"), "x", v("n")),
                        nat(v("sp"), "y", v("n")),
                        k.mul(v("px"), k.ifelse(k.ne(v("selected"), e.n(0)), f(3.5), f(2))),
                        e.n(1),
                    ),
                ),
                k.if_(k.eq(v("selected"), e.n(0)), k.cont("strokes")),
                # the active channel along the stroke, faded
                *chd_at(ed("active")),
                SP("sp_sample", v("sp"), v("segs"), f(GLYPH_SPACING), v("smp")),
                C("cv_style", v("cv"), k.mul(v("alpha"), e.n(0.3)), f(1)),
                k.for_(
                    "g",
                    0,
                    count(v("smp")),
                    "glyphs",
                    glyph(
                        v("ch"),
                        at(v("smp"), "x", v("g")),
                        at(v("smp"), "y", v("g")),
                        sample_channel_at(k, e, v("smp"), v("g"), cd("slot")),
                        sample_channel_at(k, e, v("smp"), v("g"), k.add(cd("slot"), e.n(1))),
                    ),
                ),
                # the selected node's channels: the active one strong with its handle, the others faint
                k.if_(k.lt(ed("sel_node"), e.n(0)), k.cont("strokes")),
                e.let("sn", ed("sel_node")),
                k.for_(
                    "c",
                    0,
                    e.fld(ed("chans"), "len"),
                    "chans",
                    e.let("cc", raw(k.m(ed("chans"), "at", v("c")), "chd")),
                    e.let("strong", e.mb.as_(k.eq(v("c"), ed("active")), k.lo("t_i32"))),
                    C(
                        "cv_style",
                        v("cv"),
                        k.mul(v("alpha"), k.ifelse(k.ne(v("strong"), e.n(0)), f(1), f(0.2))),
                        k.ifelse(k.ne(v("strong"), e.n(0)), f(2), f(1)),
                    ),
                    glyph(
                        v("cc"),
                        nat(v("sp"), "x", v("sn")),
                        nat(v("sp"), "y", v("sn")),
                        chan(v("sp"), v("sn"), e.fld(v("cc"), "slot")),
                        chan(v("sp"), v("sn"), k.add(e.fld(v("cc"), "slot"), e.n(1))),
                    ),
                ),
                *widget_end(v("sp"), v("sn")),
                C("cv_style", v("cv"), v("alpha"), f(1)),
                C("cv_circle", v("cv"), v("hx"), v("hy"), k.mul(v("px"), e.n(4)), e.n(1)),
                # Bézier handles of its segments
                C("cv_style", v("cv"), k.mul(v("alpha"), e.n(0.6)), f(1)),
                k.if_(
                    bezier_before(v("sp")),
                    C(
                        "cv_line",
                        v("cv"),
                        nat(v("sp"), "x", v("sn")),
                        nat(v("sp"), "y", v("sn")),
                        *handle(v("sp"), v("sn"), "i"),
                    ),
                    C("cv_circle", v("cv"), *handle(v("sp"), v("sn"), "i"), k.mul(v("px"), e.n(3)), e.n(1)),
                ),
                k.if_(
                    bezier_after(v("sp")),
                    C(
                        "cv_line",
                        v("cv"),
                        nat(v("sp"), "x", v("sn")),
                        nat(v("sp"), "y", v("sn")),
                        *handle(v("sp"), v("sn"), "o"),
                    ),
                    C("cv_circle", v("cv"), *handle(v("sp"), v("sn"), "o"), k.mul(v("px"), e.n(3)), e.n(1)),
                ),
            ),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
