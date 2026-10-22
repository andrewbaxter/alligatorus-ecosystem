"""synth-midi-sine.atz / synth-midi-sine-ir.atz: PipeWire MIDI-driven sine synth (llvm app)."""

import math

from ..pipewire import pipewire
from ..root_mode import root_mode_finish
from .. import target_mb as tm
from ..target_mb import fn_of, int_as

TWO_PI = 2.0 * math.pi
AMP = 0.2
RATE = 48000.0


def _lo(e, name):
    return e.lower(e.v(name))


_LLVM_TYPES = ["i32", "u32", "f32", "f64", "void"]


def _refs_setup(e):
    return e.v


def _refs_top(e):
    return lambda name: e.fld(e.v("k"), name)


def _ty(e, refs, name):
    base = name[len("t_") :]
    if base in _LLVM_TYPES:
        return e.fld(refs("llvm"), base)
    return refs(name)


class _Cx:
    def __init__(self):
        self.setup = []
        self.fields = []
        self.top = []


def _def_type(e, cx, name, type_expr):
    cx.fields.append(e.p(name, type_expr))


def _def_value(e, cx, name, value):
    cx.top.append(e.let(name, value))


def _call_fn(e, fn, arg):
    return e.call(_lo(e, fn), arg)


def _call_fn_tup(e, fn, *args):
    return e.call(_lo(e, fn), e.tup(*args))


def _conv(e, type_, value):
    return e.mb.as_(value, e.lower(_ty(e, _refs_top(e), type_)))


def _set(e, base, value):
    return e.mb.set(base, value)


def _cstr(e, cx, bind, content):
    _def_value(e, cx, bind, e.call_m(_refs_top(e)("ll"), "cstr", e.s(content)))


def _global(e, cx, bind, name, type_, init):
    top = _refs_top(e)
    _def_value(
        e,
        cx,
        bind,
        e.call(
            e.fld(_refs_top(e)("llvm"), "global_fn"),
            e.rec(e.p("mod", top("ll")), e.p("name", e.s(name)), e.p("ty", _ty(e, top, type_)), e.p("init", init)),
        ),
    )


def _func(e, cx, name, param_names, param_types, ret, body):
    top = _refs_top(e)
    setup = _refs_setup(e)
    names = []
    types = []
    for param_name, param_type in zip(param_names, param_types):
        names.append(e.s(param_name))
        types.append(_ty(e, setup, param_type))
    _def_type(
        e,
        cx,
        name + "_fn_t",
        e.call_m(
            e.v("llvm"),
            "fn",
            e.rec(e.p("params", e.list_new(e.mb.eval_type(), *types)), e.p("ret", _ty(e, setup, ret))),
        ),
    )
    _def_value(
        e,
        cx,
        name,
        e.call(
            e.fld(_refs_top(e)("llvm"), "export_fn" if name == "main" else "func_fn"),
            e.rec(
                e.p("mod", top("ll")),
                e.p("name", e.s(name)),
                e.p("params", e.tup(*names)),
                e.p("ty", top(name + "_fn_t")),
                e.p("body", e.stage(body)),
            ),
        ),
    )


def _events(e, cx, bind, name, process):
    top = _refs_top(e)
    fields = []
    fields.append(e.p("version", e.n(2)))
    for f in [
        "destroy",
        "state_changed",
        "control_info",
        "io_changed",
        "param_changed",
        "add_buffer",
        "remove_buffer",
        "process",
        "drained",
        "command",
        "trigger_done",
    ]:
        fields.append(e.p(f, e.v(process if f == "process" else "nullp")))
    _def_value(
        e,
        cx,
        bind,
        e.call(
            e.fld(_refs_top(e)("llvm"), "global_const_fn"),
            e.rec(
                e.p("mod", top("ll")),
                e.p("name", e.s(name)),
                e.p("ty", top("t_events")),
                e.p("init", e.rec(*fields)),
            ),
        ),
    )


def _pw_t(e, refs, name):
    return e.call_m(refs("pw"), name, e.tup())


def module(e, mode):
    cx = _Cx()
    setup = cx.setup
    top = cx.top
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    setup.append(e.let("ll", e.call(e.fld(e.v("llvm"), "new"), e.tup())))
    setup.append(e.let("c", e.import_local("libc", "libc-2.42.atz")))
    setup.append(e.let("pw", e.call(e.import_local("pipewire", "pipewire-1.6.atz"), e.v("ll"))))
    setup.append(e.let("t_pv", e.call_m(e.v("llvm"), "ptr", e.fld(e.v("llvm"), "void"))))
    setup.append(e.let("t_events", _pw_t(e, _refs_setup(e), "pw_stream_events")))
    for n in ["llvm", "ll", "c", "pw", "t_pv", "t_events"]:
        cx.fields.append(e.p(n, e.v(n)))
    # The control pointer type: a sequence's end (its `next`) is compared against the control cursor as one.
    setup.append(e.let("t_pctrl", e.call_m(e.v("llvm"), "ptr", _pw_t(e, _refs_setup(e), "spa_pod_control"))))
    cx.fields.append(e.p("t_pctrl", e.v("t_pctrl")))
    for stream in ["audio", "midi"]:
        payload = e.fld(e.v("llvm"), "f32") if stream == "audio" else _pw_t(e, _refs_setup(e), "spa_pod_sequence")
        setup.append(
            e.let(
                "t_buf_" + stream,
                e.call_m(e.v("pw"), "buffer_t", e.rec(e.p("name", e.s(stream)), e.p("payload", payload))),
            )
        )
        # The global (reference) types of the pointers compared against null (null is a reference of a global type).
        for kind, pointee in [("pbuf", e.v("t_buf_" + stream)), ("ppayload", payload)]:
            setup.append(
                e.let(
                    "gt_" + kind + "_" + stream,
                    e.call(
                        e.fld(e.v("llvm"), "global_t"),
                        e.rec(e.p("ty", e.call_m(e.v("llvm"), "ptr", pointee)), e.p("mem", e.b(False))),
                    ),
                )
            )
            cx.fields.append(e.p("gt_" + kind + "_" + stream, e.v("gt_" + kind + "_" + stream)))
        for op in ["dequeue", "queue"]:
            _def_type(e, cx, op + "_" + stream + "_fn_t", e.call_m(e.v("pw"), op + "_buffer_t", e.v("t_buf_" + stream)))
            _def_value(
                e,
                cx,
                op + "_" + stream,
                e.call(
                    e.fld(_refs_top(e)("llvm"), "extern_fn"),
                    e.rec(
                        e.p("libs", e.tup(e.s(pipewire.LIB))),
                        e.p("name", e.s("pw_stream_" + op + "_buffer")),
                        e.p("ty", _refs_top(e)(op + "_" + stream + "_fn_t")),
                    ),
                ),
            )
    _def_type(e, cx, "t_range_u32", e.call_m(e.v("llvm"), "range", e.fld(e.v("llvm"), "u32")))
    _def_value(e, cx, "nullp", e.call_m(_refs_top(e)("ll"), "null", e.tup()))
    _def_value(e, cx, "ptr_cast", e.fld(_refs_top(e)("llvm"), "ptr_cast"))
    _def_value(e, cx, "t_pctrl", _refs_top(e)("t_pctrl"))
    # The null reference under each pointer type it is compared against (pointers never convert implicitly).
    for stream in ["audio", "midi"]:
        for kind in ["pbuf", "ppayload"]:
            _def_value(
                e,
                cx,
                "null_" + kind + "_" + stream,
                e.call(
                    e.fld(_refs_top(e)("llvm"), "ref_fn"),
                    e.rec(e.p("ref", e.s("null")), e.p("ty", _refs_top(e)("gt_" + kind + "_" + stream))),
                ),
            )
    _def_value(e, cx, "range_u32", _refs_top(e)("t_range_u32"))
    _def_value(
        e,
        cx,
        "loop",
        e.call(
            e.fld(_refs_top(e)("llvm"), "ref_fn"),
            e.rec(e.p("ref", e.s("loop")), e.p("ty", e.fld(_refs_top(e)("llvm"), "loop"))),
        ),
    )

    for fn in ["sin", "exp2"]:
        _def_value(e, cx, fn, e.fld(_refs_top(e)("c"), fn))
    for fn in [
        "pw_init",
        "pw_deinit",
        "pw_main_loop_new",
        "pw_main_loop_get_loop",
        "pw_main_loop_run",
        "pw_stream_new_simple",
        "pw_stream_connect",
        "pw_properties_new",
        "main_loop",
        "stream",
        "properties",
        "own_main_loop",
        "own_stream",
        "own_properties",
        "direction_input",
        "direction_output",
        "id_any",
        "flags_autoconnect_map_rt",
        "pod_type_sequence",
        "control_midi",
        "control_ump",
        "params_audio",
        "params_midi",
    ]:
        _def_value(e, cx, fn, _pw_t(e, _refs_top(e), fn))

    _global(e, cx, "g_phase", "g_phase", "t_f64", e.n(0))
    _global(e, cx, "g_inc", "g_inc", "t_f64", e.n(0))
    _global(e, cx, "g_gate", "g_gate", "t_f64", e.n(0))
    _global(e, cx, "g_note", "g_note", "t_u32", e.n(0))
    _global(e, cx, "g_audio_stream", "g_audio_stream", "t_pv", e.v("nullp"))
    _global(e, cx, "g_midi_stream", "g_midi_stream", "t_pv", e.v("nullp"))

    _cstr(e, cx, "s_media_type", "media.type")
    _cstr(e, cx, "s_audio", "Audio")
    _cstr(e, cx, "s_media_category", "media.category")
    _cstr(e, cx, "s_playback", "Playback")
    _cstr(e, cx, "s_media_role", "media.role")
    _cstr(e, cx, "s_music", "Music")
    _cstr(e, cx, "s_midi", "Midi")
    _cstr(e, cx, "s_capture", "Capture")
    _cstr(e, cx, "s_dsp", "DSP")
    _cstr(e, cx, "s_aname", "atsynth-out")
    _cstr(e, cx, "s_mname", "atsynth-midi-in")

    _func(
        e,
        cx,
        "on_process",
        ["data"],
        ["t_pv"],
        "t_void",
        e.seq(
            e.let("buf", _call_fn(e, "dequeue_audio", _lo(e, "g_audio_stream"))),
            e.if_only(
                e.mb.operator_ne(e.v("buf"), _lo(e, "null_pbuf_audio")),
                e.seq(
                    e.let("datas", e.fld(e.v("buf"), "buffer", "datas")),
                    e.let("out", e.fld(e.v("datas"), "data")),
                    e.if_only(
                        e.mb.operator_ne(e.v("out"), _lo(e, "null_ppayload_audio")),
                        e.seq(
                            e.let("maxframes", e.mb.operator_div(e.fld(e.v("datas"), "maxsize"), e.n(4))),
                            e.let("req", e.fld(e.v("buf"), "requested")),
                            e.let(
                                "n0",
                                e.if_else(
                                    e.eq(e.v("req"), e.n(0)),
                                    e.v("maxframes"),
                                    int_as(e, e.v("req"), e.lower(_ty(e, _refs_top(e), "t_u32"))),
                                ),
                            ),
                            e.let(
                                "n",
                                e.if_else(e.mb.operator_gt(e.v("n0"), e.v("maxframes")), e.v("maxframes"), e.v("n0")),
                            ),
                            e.foreach(
                                e.call(
                                    fn_of(e, _lo(e, "range_u32")),
                                    e.call(e.fld(e.v("n"), "wrap"), e.lower(_ty(e, _refs_top(e), "t_u32"))),
                                ),
                                "i",
                                e.seq(
                                    e.let(
                                        "sv",
                                        e.mb.operator_mul(_call_fn(e, "sin", _lo(e, "g_phase")), _lo(e, "g_gate")),
                                    ),
                                    _set(
                                        e,
                                        e.mb.field(e.v("out"), e.v("i")),
                                        e.call(e.fld(e.v("sv"), "to_float"), e.lower(_ty(e, _refs_top(e), "t_f32"))),
                                    ),
                                    _set(e, _lo(e, "g_phase"), e.mb.operator_add(_lo(e, "g_phase"), _lo(e, "g_inc"))),
                                    e.if_only(
                                        e.mb.operator_gt(_lo(e, "g_phase"), e.n(TWO_PI)),
                                        _set(e, _lo(e, "g_phase"), e.mb.operator_sub(_lo(e, "g_phase"), e.n(TWO_PI))),
                                    ),
                                ),
                            ),
                            e.let("chunk", e.fld(e.v("datas"), "chunk")),
                            _set(e, e.fld(e.v("chunk"), "offset"), e.n(0)),
                            _set(e, e.fld(e.v("chunk"), "size"), e.mb.operator_mul(e.v("n"), e.n(4))),
                            _set(e, e.fld(e.v("chunk"), "stride"), e.n(4)),
                        ),
                    ),
                    _call_fn_tup(e, "queue_audio", _lo(e, "g_audio_stream"), e.v("buf")),
                ),
            ),
        ),
    )

    midi_event = e.if_else(
        e.eq(e.v("ctype"), _lo(e, "control_midi")),
        e.seq(
            e.let("d", e.fld(e.v("c"), "body")),
            _set(e, e.v("st"), e.mb.operator_and(_conv(e, "t_u32", e.mb.field(e.v("d"), e.n(0))), e.n(240))),
            _set(e, e.v("note"), _conv(e, "t_u32", e.mb.field(e.v("d"), e.n(1)))),
            _set(e, e.v("vel"), _conv(e, "t_u32", e.mb.field(e.v("d"), e.n(2)))),
            _set(e, e.v("have"), e.n(1)),
        ),
        e.if_only(
            e.eq(e.v("ctype"), _lo(e, "control_ump")),
            e.seq(
                e.let("w", e.mb.field(e.fld(e.v("c"), "words"), e.n(0))),
                e.if_only(
                    e.eq(e.mb.operator_shr(e.v("w"), e.n(28)), e.n(2)),
                    e.seq(
                        _set(e, e.v("st"), e.mb.operator_and(e.mb.operator_shr(e.v("w"), e.n(16)), e.n(240))),
                        _set(e, e.v("note"), e.mb.operator_and(e.mb.operator_shr(e.v("w"), e.n(8)), e.n(127))),
                        _set(e, e.v("vel"), e.mb.operator_and(e.v("w"), e.n(127))),
                        _set(e, e.v("have"), e.n(1)),
                    ),
                ),
            ),
        ),
    )
    note_event = e.if_only(
        e.mb.operator_ne(e.v("have"), e.n(0)),
        e.if_else(
            e.mb.operator_and(e.eq(e.v("st"), e.n(144)), e.mb.operator_ne(e.v("vel"), e.n(0))),
            e.seq(
                _set(
                    e,
                    _lo(e, "g_inc"),
                    e.mb.operator_mul(
                        _call_fn(
                            e,
                            "exp2",
                            e.mb.operator_div(e.mb.operator_sub(_conv(e, "t_f64", e.v("note")), e.n(69)), e.n(12)),
                        ),
                        e.n(TWO_PI * 440.0 / RATE),
                    ),
                ),
                _set(e, _lo(e, "g_note"), e.v("note")),
                _set(e, _lo(e, "g_gate"), e.n(AMP)),
            ),
            e.if_only(
                e.mb.operator_or(
                    e.eq(e.v("st"), e.n(128)),
                    e.mb.operator_and(e.eq(e.v("st"), e.n(144)), e.eq(e.v("vel"), e.n(0))),
                ),
                e.if_only(e.eq(e.v("note"), _lo(e, "g_note")), _set(e, _lo(e, "g_gate"), e.n(0))),
            ),
        ),
    )
    _func(
        e,
        cx,
        "on_midi",
        ["data"],
        ["t_pv"],
        "t_void",
        e.seq(
            e.let("buf", _call_fn(e, "dequeue_midi", _lo(e, "g_midi_stream"))),
            e.if_only(
                e.mb.operator_ne(e.v("buf"), _lo(e, "null_pbuf_midi")),
                e.seq(
                    e.let("seqp", e.fld(e.v("buf"), "buffer", "datas", "data")),
                    e.if_only(
                        e.mb.operator_ne(e.v("seqp"), _lo(e, "null_ppayload_midi")),
                        e.if_only(
                            e.eq(e.fld(e.v("seqp"), "pod", "type"), _lo(e, "pod_type_sequence")),
                            e.seq(
                                e.let(
                                    "end",
                                    tm.conv(e, _lo(e, "ptr_cast"), e.fld(e.v("seqp"), "next"), _lo(e, "t_pctrl")),
                                ),
                                e.let("c", e.fld(e.v("seqp"), "controls")),
                                e.mb.labeled(
                                    "scan",
                                    e.foreach(
                                        _lo(e, "loop"),
                                        "_",
                                        e.seq(
                                            e.if_only(
                                                e.mb.operator_gt(e.mb.operator_add(e.v("c"), e.n(1)), e.v("end")),
                                                e.mb.return_label("scan"),
                                            ),
                                            e.let("st", _conv(e, "t_u32", e.n(0))),
                                            e.let("note", _conv(e, "t_u32", e.n(0))),
                                            e.let("vel", _conv(e, "t_u32", e.n(0))),
                                            e.let("have", _conv(e, "t_u32", e.n(0))),
                                            e.let("ctype", e.fld(e.v("c"), "type")),
                                            midi_event,
                                            note_event,
                                            _set(e, e.v("c"), e.fld(e.v("c"), "next")),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                    _call_fn_tup(e, "queue_midi", _lo(e, "g_midi_stream"), e.v("buf")),
                ),
            ),
        ),
    )

    _events(e, cx, "g_audio_events", "pw.events.audio", "on_process")
    _events(e, cx, "g_midi_events", "pw.events.midi", "on_midi")

    _func(
        e,
        cx,
        "main",
        [],
        [],
        "t_i32",
        e.seq(
            _call_fn_tup(e, "pw_init", _lo(e, "nullp"), _lo(e, "nullp")),
            # The PipeWire objects live in this block: at its end the streams are destroyed, then the loop, before
            # pw_deinit. The streams take ownership of their properties.
            e.seq(
                e.let("mloop", e.mb.as_(_call_fn(e, "pw_main_loop_new", _lo(e, "nullp")), _lo(e, "own_main_loop"))),
                e.let("l", _call_fn(e, "pw_main_loop_get_loop", e.v("mloop"))),
                e.let(
                    "aprops",
                    e.mb.as_(
                        _call_fn_tup(
                            e,
                            "pw_properties_new",
                            _lo(e, "s_media_type"),
                            _lo(e, "s_audio"),
                            _lo(e, "s_media_category"),
                            _lo(e, "s_playback"),
                            _lo(e, "s_media_role"),
                            _lo(e, "s_music"),
                            _lo(e, "nullp"),
                        ),
                        _lo(e, "own_properties"),
                    ),
                ),
                e.let(
                    "astream",
                    e.mb.as_(
                        _call_fn_tup(
                            e,
                            "pw_stream_new_simple",
                            e.v("l"),
                            _lo(e, "s_aname"),
                            e.call(e.fld(e.v("aprops"), "forget"), e.tup()),
                            _lo(e, "g_audio_events"),
                            _lo(e, "nullp"),
                        ),
                        _lo(e, "own_stream"),
                    ),
                ),
                _set(e, _lo(e, "g_audio_stream"), e.v("astream")),
                e.let(
                    "mprops",
                    e.mb.as_(
                        _call_fn_tup(
                            e,
                            "pw_properties_new",
                            _lo(e, "s_media_type"),
                            _lo(e, "s_midi"),
                            _lo(e, "s_media_category"),
                            _lo(e, "s_capture"),
                            _lo(e, "s_media_role"),
                            _lo(e, "s_dsp"),
                            _lo(e, "nullp"),
                        ),
                        _lo(e, "own_properties"),
                    ),
                ),
                e.let(
                    "mstream",
                    e.mb.as_(
                        _call_fn_tup(
                            e,
                            "pw_stream_new_simple",
                            e.v("l"),
                            _lo(e, "s_mname"),
                            e.call(e.fld(e.v("mprops"), "forget"), e.tup()),
                            _lo(e, "g_midi_events"),
                            _lo(e, "nullp"),
                        ),
                        _lo(e, "own_stream"),
                    ),
                ),
                _set(e, _lo(e, "g_midi_stream"), e.v("mstream")),
                _call_fn_tup(
                    e,
                    "pw_stream_connect",
                    e.v("astream"),
                    _lo(e, "direction_output"),
                    _lo(e, "id_any"),
                    _lo(e, "flags_autoconnect_map_rt"),
                    _lo(e, "params_audio"),
                    e.n(1),
                ),
                _call_fn_tup(
                    e,
                    "pw_stream_connect",
                    e.v("mstream"),
                    _lo(e, "direction_input"),
                    _lo(e, "id_any"),
                    _lo(e, "flags_autoconnect_map_rt"),
                    _lo(e, "params_midi"),
                    e.n(1),
                ),
                _call_fn(e, "pw_main_loop_run", e.v("mloop")),
            ),
            _call_fn(e, "pw_deinit", e.tup()),
            e.ret(e.n(0)),
        ),
    )

    top.append(root_mode_finish(mode, e, _refs_top(e)("llvm"), _refs_top(e)("ll")))
    setup.append(e.ret(e.rec(*cx.fields)))
    module_ = []
    module_.append(e.let("k", e.lower(e.mb.seq(setup))))
    module_.extend(top)
    return module_
