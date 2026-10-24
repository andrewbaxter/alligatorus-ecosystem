"""webidl-events-test.atz: wasm web app exercising typed WebIDL callbacks (closure-wasm.atz callables) and the
intrinsics: `_start` creates a canvas and listens for `pointerdown` and `keydown` on the body with two closures
capturing the canvas and body handles; the pointer closure adopts the event as a `PointerEvent` and writes
`pressure * 1000` and `tiltX + 100` into the canvas's width and height and the number of coalesced events into the
body's `tabIndex`; the key closure copies the `KeyboardEvent.key` string into memory (`string_len`, `string_copy`)
and sets it as the body's `data-key` attribute (harness/verify-web-events.sh)."""

from ..collections import closure_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from ..wasm.wat import bind_types

KEY_CAP = 64
HOOKS = [
    ("h_dup", "intrinsic", "", "handle_dup"),
    ("h_document", "get", "Window", "document"),
    ("h_body", "get", "Document", "body"),
    ("h_create", "op", "Document", "createElement"),
    ("h_append", "op", "Node", "appendChild"),
    ("h_listen", "op", "EventTarget", "addEventListener"),
    ("h_listener", "callback", "EventListener", ""),
    ("h_pressure", "get", "PointerEvent", "pressure"),
    ("h_tilt_x", "get", "PointerEvent", "tiltX"),
    ("h_coalesced", "op", "PointerEvent", "getCoalescedEvents"),
    ("h_key", "get", "KeyboardEvent", "key"),
    ("h_width", "set", "HTMLCanvasElement", "width"),
    ("h_height", "set", "HTMLCanvasElement", "height"),
    ("h_tab_index", "set", "HTMLElement", "tabIndex"),
    ("h_set_attr", "op", "Element", "setAttribute"),
    ("h_seq_len", "intrinsic", "", "seq_len"),
    ("h_string_len", "intrinsic", "", "string_len"),
    ("h_string_copy", "intrinsic", "", "string_copy"),
    ("h_num_format", "intrinsic", "", "num_format"),
    ("h_num_parse", "intrinsic", "", "num_parse"),
    ("h_pow", "intrinsic", "", "pow"),
]
HANDLES = [
    ("ev_h", "Event"),
    ("body_h", "HTMLElement"),
    ("canvas_h", "HTMLCanvasElement"),
    ("pe_h", "PointerEvent"),
    ("ke_h", "KeyboardEvent"),
]
TYPES = ["m", "start_fn_t", "t_i32", "t_u8", "t_u32", "t_f64", "ev_cb_t"] + [h[0] for h in HANDLES]
STRINGS = ["canvas", "pointerdown", "keydown", "data-key", "data-p"]
LEVEL2 = [h[0] for h in HOOKS] + ["s_" + t for t in STRINGS] + ["key_buf", "down_make", "key_make"]


def _len(e, s):
    return e.n(len(s.encode()))


def _hook(e, kind, iface, member):
    return e.call(e.fld(e.v("webidl"), kind), e.rec(e.p("iface", e.s(iface)), e.p("member", e.s(member))))


def _call(e, hook, *args):
    return e.call(e.lower(e.v(hook)), args[0] if len(args) == 1 else e.tup(*args))


def _str(e, name):
    return [e.lower(e.v("s_" + name)), _len(e, name)]


def module(e):
    # Level one: the module, the types and the callback signature (the owned event in, nothing out).
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    setup.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)

    def fn_t(params, ret):
        return e.call(
            e.fld(e.v("wasm"), "fn"),
            e.rec(e.p("params", e.list_new(e.mb.eval_type(), *[e.v(p_) for p_ in params])), e.p("ret", e.v(ret))),
        )

    setup.append(e.let("start_fn_t", fn_t([], "t_void")))
    # the handle types, and the callback signature: the owned event in, nothing out
    for name, iface in HANDLES:
        setup.append(e.let(name, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))
    setup.append(
        e.let(
            "ev_cb",
            e.call(
                e.fld(e.v("closure"), "callable"),
                e.rec(p("arg", e.fld(e.v("ev_h"), "type")), p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(e.let("ev_cb_t", e.fld(e.v("ev_cb"), "type")))
    setup.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in TYPES])))

    # Level two: the hooks, the handle types, the strings, the key buffer and the two closures over level one.
    setup2 = []
    setup2.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup2.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    setup2.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    setup2.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in TYPES:
        setup2.append(e.let(n, e.fld(e.v("k"), n)))
    for bind, kind, iface, member in HOOKS:
        setup2.append(e.let(bind, _hook(e, kind, iface, member)))
    for text in STRINGS:
        setup2.append(e.let("s_" + text, e.call_m(e.v("m"), "cstr", e.s(text))))
    setup2.append(
        e.let(
            "key_buf",
            e.call(
                e.fld(e.v("wasm"), "data_fn"),
                e.rec(
                    e.p("mod", e.v("m")),
                    e.p("name", e.s("key_buf")),
                    e.p("elem", e.v("t_u8")),
                    e.p("values", e.tup(*[e.n(0)] * KEY_CAP)),
                ),
            ),
        )
    )

    def cap(name):
        return e.fld(e.v("self"), name)

    canvas_raw = e.mb.as_(cap("canvas"), e.lower(e.fld(e.v("canvas_h"), "raw")))
    body_raw = e.mb.as_(cap("body"), e.lower(e.fld(e.v("body_h"), "raw")))
    data_p = _str(e, "data-p")
    down_body = e.seq(
        e.let("pe", e.mb.as_(e.call(e.fld(e.v("arg"), "move"), e.tup()), e.lower(e.fld(e.v("pe_h"), "own")))),
        e.let("p", e.mb.as_(_call(e, "h_pressure", e.v("pe")), e.lower(e.v("t_f64")))),
        # The pressure goes through its text (num_format, string_copy, num_parse) and pow(p, 1).
        e.let("ps", _call(e, "h_num_format", _call(e, "h_pow", e.v("p"), e.n(1)))),
        e.let("pn", _call(e, "h_string_len", e.v("ps"))),
        _call(e, "h_string_copy", e.v("ps"), e.lower(e.v("key_buf")), e.n(KEY_CAP)),
        _call(e, "h_set_attr", body_raw, data_p[0], data_p[1], e.lower(e.v("key_buf")), e.v("pn")),
        e.let("pp", _call(e, "h_num_parse", e.lower(e.v("key_buf")), e.v("pn"))),
        e.let("w", e.call(e.fld(e.mb.operator_mul(e.v("pp"), e.n(1000)), "trunc"), e.lower(e.v("t_u32")))),
        _call(e, "h_width", canvas_raw, e.v("w")),
        _call(
            e,
            "h_height",
            canvas_raw,
            e.call(e.fld(e.mb.operator_add(_call(e, "h_tilt_x", e.v("pe")), e.n(100)), "wrap"), e.lower(e.v("t_u32"))),
        ),
        e.let("seq", _call(e, "h_coalesced", e.v("pe"))),
        _call(
            e, "h_tab_index", body_raw, e.call(e.fld(_call(e, "h_seq_len", e.v("seq")), "wrap"), e.lower(e.v("t_i32")))
        ),
    )
    attr = _str(e, "data-key")
    key_body = e.seq(
        e.let("ke", e.mb.as_(e.call(e.fld(e.v("arg"), "move"), e.tup()), e.lower(e.fld(e.v("ke_h"), "own")))),
        e.let("key", _call(e, "h_key", e.v("ke"))),
        e.let("n", _call(e, "h_string_len", e.v("key"))),
        _call(e, "h_string_copy", e.v("key"), e.lower(e.v("key_buf")), e.n(KEY_CAP)),
        _call(e, "h_set_attr", body_raw, attr[0], attr[1], e.lower(e.v("key_buf")), e.v("n")),
    )
    for name, caps, body_ in [("down", ["canvas", "body"], down_body), ("key", ["body"], key_body)]:
        setup2.append(
            e.let(
                name + "_make",
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("ev_cb_t")),
                            p("capture", e.rec(*[p(c, e.fld(e.v(c + "_h"), "type")) for c in caps])),
                            p("body", e.stage(body_)),
                        ),
                    ),
                    "make",
                ),
            )
        )
    setup2.append(e.ret(e.rec(*[e.p(n, e.v(n)) for n in TYPES + LEVEL2])))

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    top.append(e.let("web", e.import_local("web", "web-wasm.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup2))))
    for n in TYPES + LEVEL2:
        top.append(e.let(n, e.fld(e.v("k"), n)))

    def listen(target, event, cb):
        """Registers the owned callable `cb` for `event`; the closure and the JS function handle outlive `_start`."""
        ev = _str(e, event)
        return e.seq(
            e.let("js_" + cb, _call(e, "h_listener", e.call(e.lower(e.fld(e.v("closure"), "callback_of")), e.v(cb)))),
            _call(e, "h_listen", target, ev[0], ev[1], e.n(1), e.v("js_" + cb), e.n(0), e.n(0)),
            e.call(e.fld(e.v("js_" + cb), "forget"), e.tup()),
            e.call(e.fld(e.v(cb), "forget"), e.tup()),
        )

    canvas = _str(e, "canvas")

    def body_dup():
        """A duplicate of the body handle, owned (`handle_dup` yields any handle; adopted as the body's type)."""
        return e.mb.as_(_call(e, "h_dup", e.v("body")), e.lower(e.fld(e.v("body_h"), "own")))

    start_body = e.stage(
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            e.let("doc", _call(e, "h_document", e.v("win"))),
            # `Document.body` is nullable: its option is matched (the page has one; none traps).
            e.match_of(
                _call(e, "h_body", e.v("doc")),
                "body0",
                None,
                p("none", e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())),
                p(
                    "some",
                    e.seq(
                        e.let(
                            "body",
                            e.mb.as_(
                                e.call(e.fld(e.v("body0"), "move"), e.tup()), e.lower(e.fld(e.v("body_h"), "own"))
                            ),
                        ),
                        e.let("canvas", _call(e, "h_create", e.v("doc"), canvas[0], canvas[1], e.n(0), e.n(0), e.n(0))),
                        _call(e, "h_append", e.v("body"), e.v("canvas")),
                        # The closures own the canvas and duplicates of the body handle (never destroyed: the page
                        # keeps them); the listeners borrow the body, released when `_start` returns.
                        e.let(
                            "on_down",
                            e.call(
                                fn_of(e, e.lower(e.v("down_make"))),
                                e.rec(
                                    p(
                                        "canvas",
                                        e.mb.as_(
                                            e.call(e.fld(e.v("canvas"), "move"), e.tup()),
                                            e.lower(e.fld(e.v("canvas_h"), "own")),
                                        ),
                                    ),
                                    p("body", body_dup()),
                                ),
                            ),
                        ),
                        e.let("on_key", e.call(fn_of(e, e.lower(e.v("key_make"))), e.rec(p("body", body_dup())))),
                        listen(e.v("body"), "pointerdown", "on_down"),
                        listen(e.v("body"), "keydown", "on_key"),
                    ),
                ),
            ),
        )
    )
    top.append(
        e.call(
            e.fld(e.v("wasm"), "export_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("_start")),
                e.p("params", e.tup()),
                e.p("ty", e.v("start_fn_t")),
                e.p("body", start_body),
            ),
        )
    )
    top.append(e.ret(e.call(e.fld(e.v("web"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
