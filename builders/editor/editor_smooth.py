"""editor-smooth.atz: smoothing recorded strokes into splines (wat target; dependencies over vector-spline.atz,
typed with the ecosystem's libraries).

Each recorded stroke (editor-record.atz) is fitted (vector-spline.atz `sp_fit`) with a smoothing amount (mm): the
stroke's own when it has one, else the layer's. The amounts are entries of the document's section the layer
registers: entry 0 the layer's `{"a": amount}` (1 mm when absent), entry `id` a stroke's own. A stroke's fit changes
only with its amount (a recording never changes), so `sm_amount` is what a later layer's edits of the fit are based
on.

The layer is an owned record (`sm_t`, `sm_raw`) owning its fits and controls: `sm_new(st, key, map, nch,
parent, changed)` makes it (owned; `changed`, the editor's callable, owned, is called with the event after a control
changed the document): `map` is an `ints` of `nch` channel selectors for the fit's channels (a recorded stroke's column
by index in editor-record.atz's `CHANNELS`, -1 the speed), and its controls go into `parent`: the layer's amount, the
selected stroke's amount and a button giving the selected stroke the layer's amount again, each handled by a closure the
layer owns (capturing it), which writes the document and then calls `changed`. `sm_select(sm, id)` is the stroke those
controls are for (0: none).

`sm_sync(sm, rec)` refits the strokes whose amount changed and follows the recorder's strokes. Fits by stroke id, in
id order: `sm_find(sm, id)` (an index; negative: none), `sm_count(sm)`, `sm_id(sm, i)`, `sm_fit(sm, i)` (the fit
record, raw: `sp` its spline and `segs` its prepared segments, valid until the next sync), `sm_stamp(sm, i)` (changes
when the fit does), `sm_amount(sm, id)`. `sm_draw(sm, cv, alpha)` draws the fits. `sm_stale(sm, rec)` removes the own
amounts of strokes that are gone."""

from ..collections import closure_wasm, record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_canvas, editor_json, editor_record, editor_state, editor_types, editor_ui, vector_spline
from ..wasm import math_wasm
from ..wasm.kit import Kit, library, stack
from .vector_spline import CHANNELS

FILE = "editor-smooth.atz"
DEFAULT_AMOUNT = 1.0

TEXTS = {
    "t_amount": "Smoothing (mm)",
    "t_own": "This stroke (mm)",
    "t_shared": "Use the layer's smoothing",
    "j_a": '{"a":',
    "k_a": "a",
}
UI_TYPES = ["node_raw", "event_raw", "input_raw", "ev_cb_t", "inputw_t", "inputw_own", "button_t", "button_own"]
# The controls, by index in the record's vecs.
R_AMOUNT, R_OWN = 0, 1

TYPE_EXPORTS = ["sm_t", "sm_raw", "fit_t", "fit_raw"]
EXPORTS = [
    "sm_new",
    "sm_select",
    "sm_sync",
    "sm_find",
    "sm_count",
    "sm_id",
    "sm_fit",
    "sm_stamp",
    "sm_amount",
    "sm_draw",
    "sm_stale",
]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("idmap", e.import_local("idmap", "idmap-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    x.append(e.let("state", e.import_local("state", editor_state.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("canvas", e.import_local("canvas", editor_canvas.FILE)))
    x.append(e.let("rec", e.import_local("rec", editor_record.FILE)))
    x.append(e.let("spline", e.import_local("spline", vector_spline.FILE)))


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


SPLINE_TYPES = [pre + "_" + f for pre in ["spline", "segs", "track"] for f in ["t", "own", "raw"]]


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
        x.append(e.let("rc_raw", e.fld(e.v("rec"), "rc_raw")))
        x.append(e.let("stroke_raw", e.fld(e.v("rec"), "stroke_raw")))
        x.append(e.let("st_raw", e.fld(e.v("state"), "st_raw")))
        for n in SPLINE_TYPES:
            x.append(e.let(n, e.fld(e.v("spline"), n)))
        return type_names + UI_TYPES + ["cv_raw", "rc_raw", "stroke_raw", "st_raw"] + SPLINE_TYPES

    def level2(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "fit",
            [
                ("id", "t_i32"),
                ("raw_stamp", "t_i32"),
                ("stamp", "t_i32"),
                ("amount", "t_f64"),
                ("sp", "spline_t"),
                ("segs", "segs_t"),
            ],
        )

    def level3(x):
        _imports(e, x)
        x.append(e.let("fits_r", e.call(e.fld(e.v("idmap"), "type"), e.v("fit_t"))))
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let("fits_" + f, e.fld(e.v("fits_r"), "type" if f == "t" else f)))
        names = ["fits_" + f for f in ["t", "own", "raw", "new"]]
        # the controls and their closures, vecs the record owns (made before the controls capture it)
        for name, elem in [("inputws", "inputw_t"), ("buttons", "button_t"), ("ev_cbs", "ev_cb_t")]:
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
            "sm",
            [
                ("st", "st_raw"),
                ("sec", "t_i32"),
                ("map", "ints_t"),
                ("nch", "t_i32"),
                ("fits", "fits_t"),
                ("buf", "bytes_t"),
                ("selected", "t_i32"),
                ("ranges", "inputws_t"),
                ("buttons", "buttons_t"),
                ("cbs", "ev_cbs_t"),
                ("changed", "ev_cb_t"),
                ("stamp", "t_i32"),
                ("track", "track_t"),
                ("speeds", "f64s_t"),
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
        ("rec", editor_record.FILE),
        ("spline", vector_spline.FILE),
        ("math", math_wasm.FILE),
        ("closure", closure_wasm.FILE),
    ]:
        x.append(e.let(name, e.import_local(name, file)))
    for name, text in TEXTS.items():
        k.text(x, name, text)
    v = e.v
    f = k.f64

    def lib(name):
        return lambda fn, *args: k.lib(name, fn, *args)

    J, S, U, C, R, SP, T, M = (lib(n) for n in ["json", "state", "ui", "canvas", "rec", "spline", "types", "math"])

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def raw(borrow, name):
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def sm(name):
        return e.fld(v("sm"), name)

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def col(rec, name):
        return e.fld(rec, name)

    def at(rec, name, i):
        return k.m(col(rec, name), "at", i)

    # The amount of entry `id`, or -1 when it has none.
    k.dep(
        x,
        "sm_entry",
        ["sm", "id"],
        ["sm_raw", "t_i32"],
        "t_f64",
        e.match_of(
            S("st_get", sm("st"), sm("sec"), v("id")),
            "text",
            None,
            p("some", k.ret(J("jr_num", v("text"), J("jr_field", v("text"), e.n(0), ts("k_a"))))),
            p("none", k.ret(f(-1))),
        ),
    )
    k.dep(
        x,
        "sm_amount",
        ["sm", "id"],
        ["sm_raw", "t_i32"],
        "t_f64",
        e.seq(
            e.let("own", k.dcall("sm_entry", v("sm"), v("id"))),
            k.if_(k.ge(v("own"), e.n(0)), k.ret(v("own"))),
            e.let("shared", k.dcall("sm_entry", v("sm"), k.i32(0))),
            k.if_(k.ge(v("shared"), e.n(0)), k.ret(v("shared"))),
            e.ret(f(DEFAULT_AMOUNT)),
        ),
    )
    k.dep(
        x,
        "sm_put",
        ["sm", "id", "amount"],
        ["sm_raw", "t_i32", "t_f64"],
        "t_void",
        e.seq(
            e.let("buf", raw(sm("buf"), "bytes")),
            k.m(v("buf"), "clear", e.tup()),
            J("jw_text", v("buf"), ts("j_a")),
            J("jw_num", v("buf"), v("amount")),
            J("jw_byte", v("buf"), e.n(ord("}"))),
            S("st_put", sm("st"), sm("sec"), v("id"), v("buf")),
        ),
    )

    def widget_el(i):
        """A range control's input element (raw): control `i` of the record's ranges."""
        return e.mb.as_(e.mb.as_(e.fld(k.m(sm("ranges"), "at", e.n(i)), "el"), k.lo("t_i32")), k.lo("input_raw"))

    # The controls show the layer's amount and the selected stroke's.
    k.dep(
        x,
        "sm_show",
        ["sm"],
        ["sm_raw"],
        "t_void",
        e.seq(
            U("set_value", widget_el(R_AMOUNT), k.dcall("sm_amount", v("sm"), k.i32(0))),
            U("set_value", widget_el(R_OWN), k.dcall("sm_amount", v("sm"), sm("selected"))),
        ),
    )
    k.dep(
        x,
        "sm_select",
        ["sm", "id"],
        ["sm_raw", "t_i32"],
        "t_void",
        e.seq(k.set(sm("selected"), v("id")), k.dcall("sm_show", v("sm"))),
    )
    # The controls' handlers: the layer's amount, the selected stroke's own amount, back to the shared amount.
    k.dep(
        x,
        "sm_on_amount",
        ["sm"],
        ["sm_raw"],
        "t_void",
        k.dcall("sm_put", v("sm"), k.i32(0), U("value", widget_el(R_AMOUNT))),
    )
    k.dep(
        x,
        "sm_on_own",
        ["sm"],
        ["sm_raw"],
        "t_void",
        k.if_(k.gt(sm("selected"), e.n(0)), k.dcall("sm_put", v("sm"), sm("selected"), U("value", widget_el(R_OWN)))),
    )
    k.dep(
        x,
        "sm_on_shared",
        ["sm"],
        ["sm_raw"],
        "t_void",
        k.if_(k.gt(sm("selected"), e.n(0)), S("st_del", sm("st"), sm("sec"), sm("selected"))),
    )
    # The controls' closures (editor-ui's `ev_cb`): each captures the layer, runs its handler, then the editor's
    # `changed` with the event.
    for name, handler in [("amount_make", "sm_on_amount"), ("own_make", "sm_on_own"), ("shared_make", "sm_on_shared")]:
        cap = e.fld(e.v("self"), "sm")
        x.append(
            e.let(
                name,
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("ev_cb_t")),
                            p("capture", e.rec(p("sm", e.v("sm_raw")))),
                            p(
                                "body",
                                e.stage(
                                    e.seq(
                                        k.dcall(handler, cap),
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

    def own_closure(name):
        """A closure capturing the layer (its record, borrowed through its binding `sm`), pushed on its closures."""
        return k.m(sm("cbs"), "push", e.call(fn_of(e, k.lo(name)), e.rec(p("sm", raw(v("sm"), "sm")))))

    def last_cb():
        return k.m(sm("cbs"), "at", k.sub(e.fld(sm("cbs"), "len"), e.n(1)))

    k.dep(
        x,
        "sm_new",
        ["st", "key", "map", "nch", "parent", "changed"],
        ["st_raw", "str_t", "ints_raw", "t_i32", "node_raw", "ev_cb_t"],
        "sm_t",
        e.seq(
            e.let("mapc", k.call("ints_new", e.tup())),
            k.for_("i", 0, v("nch"), "map", k.m(v("mapc"), "push", k.m(v("map"), "at", v("i")))),
            e.let(
                "sm",
                k.call(
                    "sm_make",
                    e.rec(
                        p("st", v("st")),
                        p("sec", S("st_section", v("st"), v("key"))),
                        p("map", k.m(v("mapc"), "move", e.tup())),
                        p("nch", v("nch")),
                        p("fits", k.call("fits_new", e.tup())),
                        p("buf", k.call("bytes_new", e.tup())),
                        p("selected", k.i32(0)),
                        p("ranges", k.call("inputws_new", e.tup())),
                        p("buttons", k.call("buttons_new", e.tup())),
                        p("cbs", k.call("ev_cbs_new", e.tup())),
                        p("changed", k.m(v("changed"), "move", e.tup())),
                        p("stamp", k.i32(0)),
                        p("track", SP("track_new")),
                        p("speeds", k.call("f64s_new", e.tup())),
                    ),
                ),
            ),
            # the controls, each with a closure over the layer (made now that the record exists)
            own_closure("amount_make"),
            k.m(
                sm("ranges"),
                "push",
                U("range", v("parent"), ts("t_amount"), f(0), f(10), f(0.05), f(DEFAULT_AMOUNT), last_cb()),
            ),
            own_closure("own_make"),
            k.m(
                sm("ranges"),
                "push",
                U("range", v("parent"), ts("t_own"), f(0), f(10), f(0.05), f(DEFAULT_AMOUNT), last_cb()),
            ),
            own_closure("shared_make"),
            k.m(sm("buttons"), "push", U("button", v("parent"), ts("t_shared"), last_cb())),
            e.ret(k.m(v("sm"), "move", e.tup())),
        ),
    )
    k.dep(
        x,
        "sm_find",
        ["sm", "id"],
        ["sm_raw", "t_i32"],
        "t_i32",
        e.ret(k.m(raw(sm("fits"), "fits"), "index_of", v("id"))),
    )
    # The fit of stroke `id` (one the order lists is in the map: a missing one traps).
    k.dep(
        x,
        "sm_fit_of",
        ["sm", "id"],
        ["sm_raw", "t_i32"],
        "fit_raw",
        e.match_of(
            k.m(raw(sm("fits"), "fits"), "get", v("id")),
            "pl",
            None,
            p("some", k.ret(raw(e.mb.field(v("pl"), e.n(0)), "fit"))),
            p("none", trap()),
        ),
    )
    # The track of the stroke `s`: its time, position and, per selector of the map, the column or the speed.
    k.dep(
        x,
        "sm_track",
        ["sm", "s"],
        ["sm_raw", "stroke_raw"],
        "t_void",
        e.seq(
            e.let("track", raw(sm("track"), "track")),
            e.let("speeds", raw(sm("speeds"), "f64s")),
            *[k.m(col(v("track"), c), "clear", e.tup()) for c in ["t", "x", "y", "c"]],
            e.let("n", e.mb.as_(e.fld(col(v("s"), "t"), "len"), k.lo("t_i32"))),
            SP("sp_speeds", col(v("s"), "x"), col(v("s"), "y"), col(v("s"), "t"), v("speeds")),
            k.for_(
                "j",
                0,
                v("n"),
                "samples",
                *[k.m(col(v("track"), c), "push", at(v("s"), c, v("j"))) for c in ["t", "x", "y"]],
                k.for_(
                    "c",
                    0,
                    e.n(CHANNELS),
                    "chs",
                    k.ifelse(
                        k.ge(v("c"), sm("nch")),
                        k.m(col(v("track"), "c"), "push", f(0)),
                        e.seq(
                            e.let("sel", k.m(sm("map"), "at", v("c"))),
                            k.m(
                                col(v("track"), "c"),
                                "push",
                                k.ifelse(
                                    k.lt(v("sel"), e.n(0)),
                                    k.m(v("speeds"), "at", v("j")),
                                    R("rec_channel_at", v("s"), v("sel"), v("j")),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "sm_sync",
        ["sm", "rec"],
        ["sm_raw", "rc_raw"],
        "t_void",
        e.seq(
            S("st_changed_clear", sm("st"), sm("sec")),
            e.let("fits", raw(sm("fits"), "fits")),
            # fits of strokes no longer recorded go (from the end: the positions shift)
            e.let("i", e.mb.as_(e.fld(v("fits"), "len"), k.lo("t_i32"))),
            k.loop(
                "gone",
                k.if_(k.le(v("i"), e.n(0)), k.brk("gone")),
                e.mb.set(v("i"), k.sub(v("i"), e.n(1))),
                e.let("gid", k.m(v("fits"), "id_at", v("i"))),
                k.if_(
                    k.lt(R("rec_find", v("rec"), v("gid")), e.n(0)),
                    e.seq(e.let("was", k.m(v("fits"), "remove", v("gid")))),
                ),
            ),
            k.for_(
                "r",
                0,
                R("rec_count", v("rec")),
                "strokes",
                e.let("id", R("rec_id", v("rec"), v("r"))),
                e.let("amount", k.dcall("sm_amount", v("sm"), v("id"))),
                k.if_(
                    k.lt(k.dcall("sm_find", v("sm"), v("id")), e.n(0)),
                    k.m(
                        v("fits"),
                        "put",
                        e.tup(
                            v("id"),
                            k.call(
                                "fit_make",
                                e.rec(
                                    p("id", v("id")),
                                    p("raw_stamp", k.i32(-1)),
                                    p("stamp", k.i32(0)),
                                    p("amount", f(0)),
                                    p("sp", SP("sp_new", sm("nch"))),
                                    p("segs", SP("segs_new")),
                                ),
                            ),
                        ),
                    ),
                ),
                e.let("fa", k.dcall("sm_fit_of", v("sm"), v("id"))),
                e.let("rs", R("rec_stamp", v("rec"), v("r"))),
                k.if_(
                    k.and_(k.eq(e.fld(v("fa"), "raw_stamp"), v("rs")), k.eq(e.fld(v("fa"), "amount"), v("amount"))),
                    k.cont("strokes"),
                ),
                k.set(e.fld(v("fa"), "raw_stamp"), v("rs")),
                k.set(e.fld(v("fa"), "amount"), v("amount")),
                k.dcall("sm_track", v("sm"), R("rec_stroke", v("rec"), v("r"))),
                SP("sp_fit", sm("track"), sm("nch"), v("amount"), e.fld(v("fa"), "sp")),
                SP("sp_prepare", e.fld(v("fa"), "sp"), e.fld(v("fa"), "segs")),
                k.set(sm("stamp"), k.add(sm("stamp"), e.n(1))),
                k.set(e.fld(v("fa"), "stamp"), sm("stamp")),
            ),
            k.dcall("sm_show", v("sm")),
        ),
    )
    k.dep(x, "sm_count", ["sm"], ["sm_raw"], "t_i32", e.ret(e.fld(raw(sm("fits"), "fits"), "len")))
    k.dep(x, "sm_id", ["sm", "i"], ["sm_raw", "t_i32"], "t_i32", e.ret(k.m(raw(sm("fits"), "fits"), "id_at", v("i"))))
    k.dep(
        x,
        "sm_fit",
        ["sm", "i"],
        ["sm_raw", "t_i32"],
        "fit_raw",
        e.ret(k.dcall("sm_fit_of", v("sm"), k.dcall("sm_id", v("sm"), v("i")))),
    )
    k.dep(
        x,
        "sm_stamp",
        ["sm", "i"],
        ["sm_raw", "t_i32"],
        "t_i32",
        e.ret(e.fld(k.dcall("sm_fit", v("sm"), v("i")), "stamp")),
    )
    k.dep(
        x,
        "sm_draw",
        ["sm", "cv", "alpha"],
        ["sm_raw", "cv_raw", "t_f64"],
        "t_void",
        e.seq(
            C("cv_style", v("cv"), v("alpha"), f(1.5)),
            k.for_(
                "i",
                0,
                k.dcall("sm_count", v("sm")),
                "fits",
                e.let("segs", raw(e.fld(k.dcall("sm_fit", v("sm"), v("i")), "segs"), "segs")),
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
            ),
        ),
    )
    k.dep(
        x,
        "sm_stale",
        ["sm", "rec"],
        ["sm_raw", "rc_raw"],
        "t_void",
        e.seq(
            e.let("i", k.i32(0)),
            k.loop(
                "entries",
                k.if_(k.ge(v("i"), S("st_count", sm("st"), sm("sec"))), k.brk("entries")),
                e.let("id", S("st_id_at", sm("st"), sm("sec"), v("i"))),
                k.if_(
                    k.and_(k.gt(v("id"), e.n(0)), k.lt(R("rec_find", v("rec"), v("id")), e.n(0))),
                    S("st_del", sm("st"), sm("sec"), v("id")),
                    k.cont("entries"),
                ),
                e.mb.set(v("i"), k.add(v("i"), e.n(1))),
            ),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
