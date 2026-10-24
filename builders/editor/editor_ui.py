"""editor-ui.atz: the DOM controls of the editor components (wat target; dependencies over webidl-wasm.atz's hooks,
typed with the ecosystem's libraries).

Types (exported): `str` and `bytes` are editor-types.atz's (a text dependency's `str` is `Kit.sconst`); elements are
webidl-wasm.atz handles, owned (`el_t`, released when the binding holding them drops) or raw (`el_raw`, a borrowed
use), for `Element`, `HTMLInputElement` (`input_*`), `HTMLSelectElement` (`select_*`), `Event` (`event_*`), `Node`
(`node_raw`) and `EventTarget` (`target_raw`); `ev_cb` is the callable (closure-wasm.atz) of an event handler,
`callable(event_t)`: its `call` takes the owned event, released when the handler returns unless moved; `frame_cb` is
`callable(f64)` (the frame's time).

`init(root)` adds the stylesheet (classes `ed_*`, styled only with the ide's `--merman-*` variables) to `root`.
`el(parent, tag, class)` appends an element (an owned `Element` handle); `text(el, s)` sets its
text; `attr(el, name, value)`, `attr_num(el, name, x)` (`x` as its shortest text) and `attr_del(el, name)` set and
remove attributes; `attr_int(el, name)` reads an integer attribute (0 when absent); `hide(el, hidden)`; `class(el, s)`
replaces its classes. `listen(target, event, cb)` listens for `event` with the callable `cb` (its raw value) and
yields the listener record (owned; it holds a handle of its own to the target): dropped, it
removes the listener and releases its JS function and that handle.

Controls, each a labeled row appended to `parent`, yield a widget record `{el, listener}` (owned:
the element and the listener reporting its event, both released when the widget is dropped):
`button(parent, label, cb)` (no row: the button itself, reporting `click`; `button_t`, `el` an `Element`);
`range(parent, label, min, max, step, value, cb)` (a slider reporting `input`), `check(parent, label, checked, cb)`
(a checkbox reporting `change`), `textbox(parent, label, cb)` (a text field reporting `change`) and `color(parent,
label, cb)` (a color picker reporting `input`) (`inputw_t`, `el` an `HTMLInputElement`); `select(parent, label,
cb)` (a dropdown reporting `change`, its options added with `option(select, text)`; `selectw_t`, `el` an
`HTMLSelectElement`). Their values: `value(el)` / `set_value(el, x)` (a slider's number),
`selected(el)` / `set_selected(el, i)`, `checked(el)` / `set_checked(el, on)`, `textbox_get(el, into)` (appends the
text to the `bytes` vec `into`) / `textbox_set(el, s)`, `color_get(el)` (its color as an `(f64, f64, f64)` tuple,
0..1) / `color_set(el, rgb)`.

Events: `current(ev)` is the element the listener is on (raw); `prevent(ev)` and `stop(ev)` prevent the default
action and stop the propagation. `now()` is the page's clock (ms); `frame(cb)` calls the callable with the time at
the next animation frame and yields the request's id; `cancel_frame(id)` cancels it."""

from ..collections import closure_wasm, record_wasm
from ..eco_mb import p
from ..memory import destructor
from ..target_mb import fn_of
from . import editor_types
from ..wasm.kit import Kit, library

FILE = "editor-ui.atz"

CSS = """
.ed_app [hidden] { display: none !important; }
.ed_app { display: flex; flex: 1 1 0; min-width: 0; min-height: 0; background: var(--merman-background);
  color: var(--merman-text-color); font-family: var(--merman-font-family); font-size: var(--merman-font-size); }
.ed_row { display: flex; flex-direction: row; align-items: center; gap: var(--merman-spacing-inline_gap); }
.ed_col { display: flex; flex-direction: column; gap: var(--merman-spacing-inline_gap); }
.ed_side { flex: none; width: 20em; overflow: auto; padding: var(--merman-spacing-panel);
  border-left: 1px solid var(--merman-hover-color); display: flex; flex-direction: column;
  gap: var(--merman-spacing-panel); }
.ed_section { display: flex; flex-direction: column; gap: var(--merman-spacing-inline_gap); }
.ed_heading { font-weight: bold; }
.ed_label { flex: none; min-width: 6em; opacity: 0.8; }
.ed_button, .ed_input { font: inherit; color: inherit; background: var(--merman-details-background);
  border: 1px solid var(--merman-hover-color); border-radius: 0.3em;
  padding: var(--merman-spacing-row_transverse) var(--merman-spacing-row_converse); }
.ed_button { cursor: pointer; }
.ed_button:hover, .ed_input:focus { border-color: var(--merman-cursor-color); outline: none; }
input[type=range].ed_input { flex: 1 1 0; min-width: 0; padding: 0; accent-color: var(--merman-cursor-color); }
input[type=checkbox].ed_input { accent-color: var(--merman-cursor-color); }
input[type=text].ed_input, select.ed_input { flex: 1 1 0; min-width: 0; }
.ed_layer { display: flex; flex-direction: row; align-items: center; gap: var(--merman-spacing-inline_gap);
  padding: var(--merman-spacing-row_transverse) var(--merman-spacing-row_converse);
  border: 1px solid transparent; border-radius: 0.3em; cursor: pointer; }
.ed_layer:hover { border-color: var(--merman-hover-color); }
.ed_layer_selected, .ed_layer_selected:hover { border-color: var(--merman-cursor-color); }
.ed_layer_name { flex: 1 1 0; }
.ed_canvas { position: relative; flex: 1 1 0; min-width: 0; min-height: 0; overflow: hidden; touch-action: none;
  background: #c8c8c8; isolation: isolate; }
.ed_canvas > canvas { position: absolute; left: 0; top: 0; width: 100%; height: 100%; }
.ed_canvas > canvas:nth-of-type(1), .ed_canvas > canvas:nth-of-type(3) { mix-blend-mode: difference; }
.ed_toolbar { position: absolute; left: var(--merman-spacing-panel); top: var(--merman-spacing-panel);
  display: flex; gap: var(--merman-spacing-inline_gap); }
.ed_status { opacity: 0.6; }
"""

HOOKS = [
    ("h_dup", "intrinsic", "", "handle_dup"),
    ("h_owner", "get", "Node", "ownerDocument"),
    ("h_create", "op", "Document", "createElement"),
    ("h_append", "op", "Node", "appendChild"),
    ("h_insert_before", "op", "Node", "insertBefore"),
    ("h_remove", "op", "Element", "remove"),
    ("h_text", "set", "Node", "textContent"),
    ("h_class", "set", "Element", "className"),
    ("h_set_attr", "op", "Element", "setAttribute"),
    ("h_get_attr", "op", "Element", "getAttribute"),
    ("h_del_attr", "op", "Element", "removeAttribute"),
    ("h_listen", "op", "EventTarget", "addEventListener"),
    ("h_listener", "callback", "EventListener", ""),
    ("h_frame_cb", "callback", "FrameRequestCallback", ""),
    ("h_raf", "op", "Window", "requestAnimationFrame"),
    ("h_caf", "op", "Window", "cancelAnimationFrame"),
    ("h_performance", "get", "Window", "performance"),
    ("h_now", "op", "Performance", "now"),
    ("h_current", "get", "Event", "currentTarget"),
    ("h_prevent", "op", "Event", "preventDefault"),
    ("h_stop", "op", "Event", "stopPropagation"),
    ("h_value_num", "get", "HTMLInputElement", "valueAsNumber"),
    ("h_set_value_num", "set", "HTMLInputElement", "valueAsNumber"),
    ("h_checked", "get", "HTMLInputElement", "checked"),
    ("h_set_checked", "set", "HTMLInputElement", "checked"),
    ("h_value_str", "get", "HTMLInputElement", "value"),
    ("h_set_value_str", "set", "HTMLInputElement", "value"),
    ("h_selected", "get", "HTMLSelectElement", "selectedIndex"),
    ("h_set_selected", "set", "HTMLSelectElement", "selectedIndex"),
    ("h_string_len", "intrinsic", "", "string_len"),
    ("h_string_copy", "intrinsic", "", "string_copy"),
    ("h_num_format", "intrinsic", "", "num_format"),
]

# The handle types bound: (binding prefix, interface). `any` is `handle("")`: JS functions and strings.
HANDLES = [
    ("node", "Node"),
    ("el", "Element"),
    ("target", "EventTarget"),
    ("doc", "Document"),
    ("win", "Window"),
    ("event", "Event"),
    ("input", "HTMLInputElement"),
    ("select", "HTMLSelectElement"),
    ("perf", "Performance"),
    ("listener_fn", "EventListener"),
    ("any", ""),
]

TEXTS = {
    "t_style": "style",
    "t_div": "div",
    "t_span": "span",
    "t_button": "button",
    "t_input": "input",
    "t_select": "select",
    "t_option": "option",
    "t_type": "type",
    "t_range": "range",
    "t_checkbox": "checkbox",
    "t_textfield": "text",
    "t_color": "color",
    "t_min": "min",
    "t_max": "max",
    "t_step": "step",
    "t_hidden": "hidden",
    "t_click": "click",
    "t_input_ev": "input",
    "t_change": "change",
    "t_css": CSS,
    "t_hexdigits": "0123456789abcdef",
    "t_empty": "",
    "c_row": "ed_row",
    "c_label": "ed_label",
    "c_button": "ed_button",
    "c_input": "ed_input",
}

# Level-one names the module and its importers use: the string, byte vec, handle and callable types.
LEVEL1 = (
    ["m", "t_pu8", "str_t", "str_of", "bytes_t", "bytes_own", "bytes_raw", "bytes_new", "rgb_t"]
    + [pre + "_" + f for pre, _ in HANDLES for f in ["raw", "t", "own"]]
    + ["ev_cb_t", "ev_cb_own", "ev_cb_raw", "frame_cb_t", "frame_cb_own", "frame_cb_raw"]
)
LEVEL2 = ["listener_t", "listener_own", "lrec_raw", "lrec_own", "lrec_new", "unlisten"]
WIDGETS = [("button", "el_t"), ("inputw", "input_t"), ("selectw", "select_t")]
TYPE_EXPORTS = (
    [n for n in LEVEL1 if n != "m"]
    + ["listener_t", "listener_own"]
    + [w + "_" + f for w, _ in WIDGETS for f in ["t", "own", "raw"]]
)
EXPORTS = [
    "init",
    "el",
    "text",
    "attr",
    "attr_num",
    "attr_del",
    "attr_int",
    "hide",
    "class",
    "remove",
    "append",
    "insert_before",
    "listen",
    "button",
    "range",
    "select",
    "option",
    "check",
    "textbox",
    "color",
    "color_get",
    "color_set",
    "value",
    "set_value",
    "selected",
    "set_selected",
    "checked",
    "set_checked",
    "textbox_get",
    "textbox_set",
    "current",
    "prevent",
    "stop",
    "now",
    "frame",
    "cancel_frame",
]


def level1(e, k, x0):
    """Level one: the types every editor module shares (made here, constants one level up)."""
    k.bind(x0)
    x0.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    x0.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x0.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    x0.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in editor_types.EXPORTS:
        x0.append(e.let(n, e.fld(e.v("types"), n)))
    x0.append(e.let("rgb_t", e.call(e.fld(e.v("wasm"), "tuple"), e.list_new(e.mb.eval_type(), *[e.v("t_f64")] * 3))))
    for pre, iface in HANDLES:
        x0.append(e.let("h_" + pre, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))
        for f in ["raw", "t", "own"]:
            x0.append(e.let(pre + "_" + f, e.fld(e.v("h_" + pre), "type" if f == "t" else f)))
    for name, arg in [("ev_cb", "event_t"), ("frame_cb", "t_f64")]:
        x0.append(
            e.let(
                name + "_r",
                e.call(e.fld(e.v("closure"), "callable"), e.rec(p("arg", e.v(arg)), p("ret", e.v("t_void")))),
            )
        )
        for f in ["t", "own", "raw"]:
            x0.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))


def module(e):
    k = Kit(e)
    x0 = []
    level1(e, k, x0)
    x0.append(e.ret(e.rec(*[p(n, e.v(n)) for n in LEVEL1])))

    # Level two: the listener record and its owned type (the unlisten dependency needs its hook here).
    x1 = []
    k.bind(x1)
    x1.append(e.let("k0", e.lower(e.mb.seq(x0))))
    for n in LEVEL1:
        x1.append(e.let(n, e.fld(e.v("k0"), n)))
    x1.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x1.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x1.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x1.append(
        e.let(
            "h_unlisten",
            e.call(
                e.fld(e.v("webidl"), "op"),
                e.rec(p("iface", e.s("EventTarget")), p("member", e.s("removeEventListener"))),
            ),
        )
    )
    v = e.v
    # The listener record, and the listener type over it: dropping a listener removes it (`unlisten`), which then
    # drops the record (its target and function handles, owned fields).
    x1.append(
        e.let(
            "lrec",
            e.call(
                e.fld(e.v("record"), "type"),
                e.rec(
                    p(
                        "fields",
                        e.rec(
                            p("target", e.v("target_t")),
                            p("ev", e.v("bytes_t")),
                            p("fn", e.v("listener_fn_t")),
                        ),
                    )
                ),
            ),
        )
    )
    for f in ["raw", "own", "new"]:
        x1.append(e.let("lrec_" + f, e.fld(e.v("lrec"), f)))
    k.dep(
        x1,
        "unlisten",
        ["r"],
        ["lrec_raw"],
        "t_void",
        e.seq(
            k.call(
                "h_unlisten",
                e.fld(v("r"), "target"),
                e.fld(e.fld(v("r"), "ev"), "data"),
                k.m(e.fld(e.fld(v("r"), "ev"), "len"), "wrap", k.lo("t_u32")),
                e.n(1),
                e.fld(v("r"), "fn"),
                e.n(0),
                e.n(0),
            ),
            # the record and its function handle
            e.let("owned", e.mb.as_(v("r"), k.lo("lrec_own"))),
        ),
    )
    x1.append(
        e.let(
            "listener_r",
            e.call(e.fld(e.v("destructor"), "type"), e.rec(p("under", e.v("lrec_raw")), p("destroy", e.v("unlisten")))),
        )
    )
    x1.append(e.let("listener_t", e.fld(e.v("listener_r"), "type")))
    x1.append(e.let("listener_own", e.fld(e.v("listener_r"), "own")))
    x1.append(e.ret(e.rec(*[p(n, e.v(n)) for n in LEVEL1 + LEVEL2])))

    # Level three: the widget records and the dependencies.
    x = []
    k.bind(x)
    x.append(e.let("k1", e.lower(e.mb.seq(x1))))
    for n in LEVEL1 + LEVEL2:
        x.append(e.let(n, e.fld(e.v("k1"), n)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    for bind, kind, iface, member in HOOKS:
        x.append(
            e.let(bind, e.call(e.fld(e.v("webidl"), kind), e.rec(p("iface", e.s(iface)), p("member", e.s(member)))))
        )
    for name, text in TEXTS.items():
        k.text(x, name, text)
    for w, el_t in WIDGETS:
        x.append(
            e.let(
                w + "_r",
                e.call(
                    e.fld(e.v("record"), "type"),
                    e.rec(p("fields", e.rec(p("el", e.v(el_t)), p("listener", e.v("listener_t"))))),
                ),
            )
        )
        for f in ["t", "own", "raw", "new"]:
            x.append(e.let(w + "_" + f, e.fld(e.v(w + "_r"), "type" if f == "t" else f)))

    def raw(pre, val):
        return e.mb.as_(val, k.lo(pre + "_raw"))

    def s(value):
        return k.sargs(value)

    def t(name):
        return k.sargs(k.sconst(name, TEXTS[name]))

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def dep(name, params, types, ret, body_):
        k.dep(x, name, params, types, ret, body_)

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    # The owned document of a node (an element in a document has one; a missing one traps).
    dep(
        "node_doc",
        ["node"],
        ["node_raw"],
        "doc_t",
        e.match_of(
            k.call("h_owner", v("node")),
            "d",
            None,
            p("some", k.ret(k.m(v("d"), "move", e.tup()))),
            p("none", trap()),
        ),
    )

    def with_doc(node, *rest):
        """Statements run with `doc`, the owned document of `node`."""
        return [e.let("doc", k.dcall("node_doc", raw("node", node))), *rest]

    dep(
        "init",
        ["root"],
        ["el_raw"],
        "t_void",
        e.seq(
            *with_doc(
                v("root"),
                e.let("style", k.call("h_create", raw("doc", v("doc")), *t("t_style"), e.n(0), e.n(0), e.n(0))),
                k.call("h_text", raw("node", v("style")), e.n(1), *t("t_css")),
                k.call("h_append", raw("node", v("root")), raw("node", v("style"))),
            )
        ),
    )
    dep(
        "el",
        ["parent", "tag", "cls"],
        ["node_raw", "str_t", "str_t"],
        "el_t",
        e.seq(
            *with_doc(
                v("parent"),
                e.let("el", k.call("h_create", raw("doc", v("doc")), *s(v("tag")), e.n(0), e.n(0), e.n(0))),
                k.if_(k.gt(e.fld(v("cls"), "len"), e.n(0)), k.call("h_class", raw("el", v("el")), *s(v("cls")))),
                k.call("h_append", raw("node", v("parent")), raw("node", v("el"))),
                e.ret(k.m(v("el"), "move", e.tup())),
            )
        ),
    )

    def el(parent, tag, cls):
        return k.dcall("el", raw("node", parent), ts(tag), ts(cls))

    dep("text", ["el", "s"], ["node_raw", "str_t"], "t_void", k.call("h_text", v("el"), e.n(1), *s(v("s"))))
    dep(
        "attr",
        ["el", "name", "value"],
        ["el_raw", "str_t", "str_t"],
        "t_void",
        k.call("h_set_attr", v("el"), *s(v("name")), *s(v("value"))),
    )

    def read_string(h, into):
        """Appends the JS string handle `h` (owned) to the byte vec `into`."""
        return [
            e.let("n", k.m(k.call("h_string_len", v(h)), "wrap", k.lo("t_i32"))),
            e.let("at", e.fld(v(into), "len")),
            k.for_("i", 0, v("n"), "grow", k.m(v(into), "push", e.n(0))),
            k.call(
                "h_string_copy",
                v(h),
                k.ptr_of(k.add(k.addr(e.fld(v(into), "data")), v("at")), "t_pu8"),
                k.m(v("n"), "wrap", k.lo("t_u32")),
            ),
        ]

    def bytes_str(b):
        """A byte vec's contents as a `str`."""
        return k.str_of(e.fld(b, "data"), e.fld(b, "len"))

    dep(
        "attr_num",
        ["el", "name", "x"],
        ["el_raw", "str_t", "t_f64"],
        "t_void",
        e.seq(
            e.let("h", k.call("h_num_format", v("x"))),
            e.let("buf", k.call("bytes_new", e.tup())),
            *read_string("h", "buf"),
            k.call("h_set_attr", v("el"), *s(v("name")), *s(bytes_str(v("buf")))),
        ),
    )
    dep("attr_del", ["el", "name"], ["el_raw", "str_t"], "t_void", k.call("h_del_attr", v("el"), *s(v("name"))))
    dep(
        "attr_int",
        ["el", "name"],
        ["el_raw", "str_t"],
        "t_i32",
        e.match_of(
            k.call("h_get_attr", v("el"), *s(v("name"))),
            "h",
            None,
            p("none", k.ret(k.i32(0))),
            p(
                "some",
                e.seq(
                    e.let("buf", k.call("bytes_new", e.tup())),
                    *read_string("h", "buf"),
                    e.let("q", k.i32(0)),
                    e.let("end", e.fld(v("buf"), "len")),
                    e.let("negative", k.i32(0)),
                    k.if_(
                        k.and_(
                            k.lt(v("q"), v("end")), k.eq(e.mb.as_(k.m(v("buf"), "at", v("q")), k.lo("t_i32")), e.n(45))
                        ),
                        e.mb.set(v("negative"), e.n(1)),
                        e.mb.set(v("q"), k.add(v("q"), e.n(1))),
                    ),
                    e.let("r", k.i32(0)),
                    k.loop(
                        "digits",
                        k.if_(k.ge(v("q"), v("end")), k.brk("digits")),
                        e.let("c", e.mb.as_(k.m(v("buf"), "at", v("q")), k.lo("t_i32"))),
                        k.if_(k.or_(k.lt(v("c"), e.n(48)), k.gt(v("c"), e.n(57))), k.brk("digits")),
                        e.mb.set(v("r"), k.add(k.mul(v("r"), e.n(10)), k.sub(v("c"), e.n(48)))),
                        e.mb.set(v("q"), k.add(v("q"), e.n(1))),
                    ),
                    k.ret(k.ifelse(k.ne(v("negative"), e.n(0)), k.neg(v("r")), v("r"))),
                ),
            ),
        ),
    )
    dep(
        "hide",
        ["el", "hidden"],
        ["el_raw", "t_i32"],
        "t_void",
        k.ifelse(
            k.ne(v("hidden"), e.n(0)),
            k.call("h_set_attr", v("el"), *t("t_hidden"), *t("t_hidden")),
            k.call("h_del_attr", v("el"), *t("t_hidden")),
        ),
    )
    dep("class", ["el", "cls"], ["el_raw", "str_t"], "t_void", k.call("h_class", v("el"), *s(v("cls"))))
    dep("remove", ["el"], ["el_raw"], "t_void", k.call("h_remove", v("el")))
    dep("append", ["parent", "el"], ["node_raw", "node_raw"], "t_void", k.call("h_append", v("parent"), v("el")))
    dep(
        "insert_before",
        ["parent", "el", "ref"],
        ["node_raw", "node_raw", "node_raw"],
        "t_void",
        k.call("h_insert_before", v("parent"), v("el"), e.n(1), v("ref")),
    )
    dep(
        "listen",
        ["target", "ev", "cb"],
        ["target_raw", "str_t", "ev_cb_raw"],
        "listener_t",
        e.seq(
            e.let("fn", k.call("h_listener", k.lib("closure", "callback_of", v("cb")))),
            k.call("h_listen", v("target"), *s(v("ev")), e.n(1), v("fn"), e.n(0), e.n(0)),
            # The listener keeps a handle of its own to the target: its removal does not depend on who else still
            # holds the element.
            e.let("tdup", k.call("h_dup", v("target"))),
            # the record keeps its own copy of the event name: the caller's text may not outlive the listener
            e.let("evb", k.call("bytes_new", e.tup())),
            k.m(v("evb"), "extend", v("ev")),
            e.let(
                "rec",
                k.call(
                    "lrec_new",
                    e.rec(
                        p("target", e.mb.as_(k.m(v("tdup"), "move", e.tup()), k.lo("target_own"))),
                        p("ev", k.m(v("evb"), "move", e.tup())),
                        p("fn", k.m(v("fn"), "move", e.tup())),
                    ),
                ),
            ),
            e.ret(e.mb.as_(k.m(v("rec"), "forget", e.tup()), k.lo("listener_own"))),
        ),
    )

    def row(parent, label):
        """A labeled row in `parent`: binds `row`."""
        return [
            e.let("row", el(parent, "t_div", "c_row")),
            e.let("lab", el(v("row"), "t_span", "c_label")),
            k.dcall("text", raw("node", v("lab")), label),
        ]

    def input_(kind):
        """An input of type `kind` in the row (binds `in`, an owned `HTMLInputElement`)."""
        return [
            e.let("in0", el(v("row"), "t_input", "c_input")),
            k.dcall("attr", v("in0"), ts("t_type"), ts(kind)),
            e.let("in", e.mb.as_(k.m(v("in0"), "move", e.tup()), k.lo("input_own"))),
        ]

    dep(
        "button",
        ["parent", "label", "cb"],
        ["node_raw", "str_t", "ev_cb_raw"],
        "button_t",
        e.seq(
            e.let("b", el(v("parent"), "t_button", "c_button")),
            k.dcall("text", raw("node", v("b")), v("label")),
            e.let("l", k.dcall("listen", raw("target", v("b")), ts("t_click"), v("cb"))),
            e.ret(
                k.call(
                    "button_new",
                    e.rec(p("el", k.m(v("b"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep(
        "range",
        ["parent", "label", "min", "max", "step", "value", "cb"],
        ["node_raw", "str_t", "t_f64", "t_f64", "t_f64", "t_f64", "ev_cb_raw"],
        "inputw_t",
        e.seq(
            *row(v("parent"), v("label")),
            *input_("t_range"),
            k.dcall("attr_num", raw("el", v("in")), ts("t_min"), v("min")),
            k.dcall("attr_num", raw("el", v("in")), ts("t_max"), v("max")),
            k.dcall("attr_num", raw("el", v("in")), ts("t_step"), v("step")),
            k.call("h_set_value_num", v("in"), v("value")),
            e.let("l", k.dcall("listen", raw("target", v("in")), ts("t_input_ev"), v("cb"))),
            e.ret(
                k.call(
                    "inputw_new",
                    e.rec(p("el", k.m(v("in"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep(
        "select",
        ["parent", "label", "cb"],
        ["node_raw", "str_t", "ev_cb_raw"],
        "selectw_t",
        e.seq(
            *row(v("parent"), v("label")),
            e.let("sel0", el(v("row"), "t_select", "c_input")),
            e.let("sel", e.mb.as_(k.m(v("sel0"), "move", e.tup()), k.lo("select_own"))),
            e.let("l", k.dcall("listen", raw("target", v("sel")), ts("t_change"), v("cb"))),
            e.ret(
                k.call(
                    "selectw_new",
                    e.rec(p("el", k.m(v("sel"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep(
        "option",
        ["sel", "s"],
        ["select_raw", "str_t"],
        "t_void",
        e.seq(
            e.let("o", k.dcall("el", raw("node", v("sel")), ts("t_option"), k.sempty())),
            k.dcall("text", raw("node", v("o")), v("s")),
        ),
    )
    dep(
        "check",
        ["parent", "label", "checked", "cb"],
        ["node_raw", "str_t", "t_i32", "ev_cb_raw"],
        "inputw_t",
        e.seq(
            *row(v("parent"), v("label")),
            *input_("t_checkbox"),
            k.call("h_set_checked", v("in"), v("checked")),
            e.let("l", k.dcall("listen", raw("target", v("in")), ts("t_change"), v("cb"))),
            e.ret(
                k.call(
                    "inputw_new",
                    e.rec(p("el", k.m(v("in"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep(
        "textbox",
        ["parent", "label", "cb"],
        ["node_raw", "str_t", "ev_cb_raw"],
        "inputw_t",
        e.seq(
            *row(v("parent"), v("label")),
            *input_("t_textfield"),
            e.let("l", k.dcall("listen", raw("target", v("in")), ts("t_change"), v("cb"))),
            e.ret(
                k.call(
                    "inputw_new",
                    e.rec(p("el", k.m(v("in"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep(
        "color",
        ["parent", "label", "cb"],
        ["node_raw", "str_t", "ev_cb_raw"],
        "inputw_t",
        e.seq(
            *row(v("parent"), v("label")),
            *input_("t_color"),
            e.let("l", k.dcall("listen", raw("target", v("in")), ts("t_input_ev"), v("cb"))),
            e.ret(
                k.call(
                    "inputw_new",
                    e.rec(p("el", k.m(v("in"), "move", e.tup())), p("listener", k.m(v("l"), "move", e.tup()))),
                )
            ),
        ),
    )
    dep("value", ["el"], ["input_raw"], "t_f64", e.ret(k.call("h_value_num", v("el"))))
    dep("set_value", ["el", "x"], ["input_raw", "t_f64"], "t_void", k.call("h_set_value_num", v("el"), v("x")))
    dep("selected", ["el"], ["select_raw"], "t_i32", e.ret(k.call("h_selected", v("el"))))
    dep("set_selected", ["el", "i"], ["select_raw", "t_i32"], "t_void", k.call("h_set_selected", v("el"), v("i")))
    dep("checked", ["el"], ["input_raw"], "t_i32", e.ret(k.call("h_checked", v("el"))))
    dep("set_checked", ["el", "on"], ["input_raw", "t_i32"], "t_void", k.call("h_set_checked", v("el"), v("on")))
    dep(
        "textbox_get",
        ["el", "into"],
        ["input_raw", "bytes_raw"],
        "t_void",
        e.seq(e.let("h", k.call("h_value_str", v("el"))), *read_string("h", "into")),
    )
    dep("textbox_set", ["el", "s"], ["input_raw", "str_t"], "t_void", k.call("h_set_value_str", v("el"), *s(v("s"))))

    def hexval(c):
        """A hexadecimal digit's value (an ASCII code: '0'-'9', 'a'-'f')."""
        return k.ifelse(k.le(c, e.n(57)), k.sub(c, e.n(48)), k.sub(c, e.n(87)))

    def hexat(buf, i):
        return hexval(e.mb.as_(k.m(buf, "at", e.n(i)), k.lo("t_i32")))

    dep(
        "color_get",
        ["el"],
        ["input_raw"],
        "rgb_t",
        e.seq(
            e.let("buf", k.call("bytes_new", e.tup())),
            k.dcall("textbox_get", v("el"), v("buf")),
            k.if_(
                k.lt(e.fld(v("buf"), "len"), e.n(7)),
                k.ret(e.mb.as_(e.tup(k.f64(0), k.f64(0), k.f64(0)), k.lo("rgb_t"))),
            ),
            e.ret(
                e.mb.as_(
                    e.tup(
                        *[
                            k.div(
                                k.to_f64(k.add(k.mul(hexat(v("buf"), 1 + 2 * i), e.n(16)), hexat(v("buf"), 2 + 2 * i))),
                                e.n(255),
                            )
                            for i in range(3)
                        ]
                    ),
                    k.lo("rgb_t"),
                )
            ),
        ),
    )

    def hexdigit(n):
        return e.mb.as_(k.at(k.add(k.addr(k.cstr("t_hexdigits")), n), 0, "t_pu8"), k.lo("t_u8"))

    dep(
        "color_set",
        ["el", "rgb"],
        ["input_raw", "rgb_t"],
        "t_void",
        e.seq(
            e.let("buf", k.call("bytes_new", e.tup())),
            k.m(v("buf"), "push", e.mb.as_(e.n(35), k.lo("t_u8"))),
            *[
                stmt
                for i in range(3)
                for stmt in [
                    e.let(
                        "b%d" % i,
                        k.trunc(
                            k.fmin(
                                k.fmax(
                                    k.floor(k.add(k.mul(e.mb.field(v("rgb"), e.n(i)), e.n(255)), e.n(0.5))), k.f64(0)
                                ),
                                k.f64(255),
                            )
                        ),
                    ),
                    k.m(v("buf"), "push", hexdigit(k.shr(v("b%d" % i), e.n(4)))),
                    k.m(v("buf"), "push", hexdigit(k.band(v("b%d" % i), e.n(15)))),
                ]
            ],
            k.dcall("textbox_set", v("el"), bytes_str(v("buf"))),
        ),
    )
    # The event's current target as an owned element (an event dispatched to an element has one; none traps).
    dep(
        "current",
        ["ev"],
        ["event_raw"],
        "el_t",
        e.match_of(
            k.call("h_current", v("ev")),
            "c",
            None,
            p("some", k.ret(e.mb.as_(k.m(v("c"), "move", e.tup()), k.lo("el_own")))),
            p("none", trap()),
        ),
    )
    dep("prevent", ["ev"], ["event_raw"], "t_void", k.call("h_prevent", v("ev")))
    dep("stop", ["ev"], ["event_raw"], "t_void", k.call("h_stop", v("ev")))
    dep(
        "now",
        [],
        [],
        "t_f64",
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            e.let("perf", k.call("h_performance", v("win"))),
            e.ret(k.call("h_now", v("perf"))),
        ),
    )
    dep(
        "frame",
        ["cb"],
        ["frame_cb_raw"],
        "t_i32",
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            e.let("fn", k.call("h_frame_cb", k.lib("closure", "callback_of", v("cb")))),
            e.ret(k.m(k.call("h_raf", v("win"), v("fn")), "wrap", k.lo("t_i32"))),
        ),
    )
    dep(
        "cancel_frame",
        ["id"],
        ["t_i32"],
        "t_void",
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            k.call("h_caf", v("win"), k.m(v("id"), "wrap", k.lo("t_u32"))),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
