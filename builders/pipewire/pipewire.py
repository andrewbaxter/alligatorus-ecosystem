"""pipewire-1.6.atz: PipeWire externs, constants, struct types, format pods and owned handle types.

`main_loop`, `stream` and `properties` are destructor.atz types over `pv` whose destroy functions are
`pw_main_loop_destroy`, `pw_stream_destroy` and `pw_properties_free`: a binding holding one destroys it when dropped.
`pw_stream_new_simple` takes ownership of its properties, so the caller hands them over with `.forget()`."""

from collections import namedtuple

from ..memory import destructor
from . import spa_pod
from ..llvm.extern import Extern, bind_types, global_t, llvm_top

LIB = "pipewire-0.3"

_EXTERNS = [
    Extern("pw_init", ["pv", "pv"], "void", False),
    Extern("pw_deinit", [], "void", False),
    Extern("pw_main_loop_new", ["pv"], "pv", False),
    Extern("pw_main_loop_get_loop", ["pv"], "pv", False),
    Extern("pw_main_loop_run", ["pv"], "i32", False),
    Extern("pw_main_loop_quit", ["pv"], "i32", False),
    Extern("pw_main_loop_destroy", ["pv"], "void", False),
    Extern("pw_stream_new_simple", ["pv", "pu8", "pv", "pv", "pv"], "pv", False),
    Extern("pw_stream_connect", ["pv", "u32", "u32", "u32", "pv", "u32"], "i32", False),
    Extern("pw_stream_destroy", ["pv"], "void", False),
    Extern("pw_properties_new", ["pu8"], "pv", True),
    Extern("pw_properties_free", ["pv"], "void", False),
]

# (member, destroy extern): owned pointer types made in the builder body, where the externs are constants
_OWNED = [("main_loop", "pw_main_loop_destroy"), ("stream", "pw_stream_destroy"), ("properties", "pw_properties_free")]

_Konst = namedtuple("_Konst", ["name", "value"])

_KONSTS = [
    _Konst("direction_input", 0),
    _Konst("direction_output", 1),
    _Konst("id_any", 4294967295.0),
    _Konst("flags_autoconnect_map_rt", 21),
    _Konst("pod_type_sequence", 16),
    _Konst("control_midi", 2),
    _Konst("control_ump", 4),
]

_Field = namedtuple("_Field", ["name", "ty"])

_Struct = namedtuple("_Struct", ["name", "fields"])

_STRUCTS = [
    _Struct(
        "spa_chunk",
        [_Field("offset", "u32"), _Field("size", "u32"), _Field("stride", "i32"), _Field("flags", "i32")],
    ),
    _Struct("spa_pod", [_Field("size", "u32"), _Field("type", "u32")]),
    _Struct(
        "pw_stream_events",
        [
            _Field("version", "u32"),
            _Field("destroy", "pv"),
            _Field("state_changed", "pv"),
            _Field("control_info", "pv"),
            _Field("io_changed", "pv"),
            _Field("param_changed", "pv"),
            _Field("add_buffer", "pv"),
            _Field("remove_buffer", "pv"),
            _Field("process", "pv"),
            _Field("drained", "pv"),
            _Field("command", "pv"),
            _Field("trigger_done", "pv"),
        ],
    ),
]

_TailStruct = namedtuple("_TailStruct", ["name", "fields", "views", "after", "len", "align"])

_TAIL_STRUCTS = [
    _TailStruct(
        "spa_pod_control",
        [_Field("offset", "u32"), _Field("type", "u32"), _Field("value", "spa_pod")],
        [_Field("body", "u8"), _Field("words", "u32")],
        "value",
        ["value", "size"],
        8,
    ),
    _TailStruct(
        "spa_pod_sequence",
        [_Field("pod", "spa_pod"), _Field("unit", "u32"), _Field("pad", "u32")],
        [_Field("controls", "spa_pod_control")],
        "pod",
        ["pod", "size"],
        8,
    ),
]

_SPA_DATA_FIELDS = [
    _Field("type", "u32"),
    _Field("flags", "u32"),
    _Field("fd", "i64"),
    _Field("mapoffset", "u32"),
    _Field("maxsize", "u32"),
]

_PW_BUFFER_FIELDS = [
    _Field("user_data", "pv"),
    _Field("size", "u64"),
    _Field("requested", "u64"),
    _Field("time", "u64"),
]


def _field(e, llvm, name, ty):
    return e.call(llvm("field"), e.rec(e.p("name", e.s(name)), e.p("ty", ty)))


def _field_list(e, llvm, fields):
    return e.list_new(llvm("field_t"), *fields)


def _struct_of(e, llvm, name, fields):
    return e.call(llvm("struct"), e.rec(e.p("name", name), e.p("fields", _field_list(e, llvm, fields))))


# Pod values: ("id", SpaConst) | ("int", int) | ("id_array", [SpaConst])
_PodProp = namedtuple("_PodProp", ["key", "value"])

_PodObject = namedtuple("_PodObject", ["object_type", "object_id", "props"])

_POD_AUDIO_F32_MONO_48K = _PodObject(
    spa_pod.SPA_TYPE_OBJECT_FORMAT,
    spa_pod.SPA_PARAM_ENUM_FORMAT,
    [
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_TYPE, ("id", spa_pod.SPA_MEDIA_TYPE_AUDIO)),
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_SUBTYPE, ("id", spa_pod.SPA_MEDIA_SUBTYPE_RAW)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_FORMAT, ("id", spa_pod.SPA_AUDIO_FORMAT_F32)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_RATE, ("int", 48000)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_CHANNELS, ("int", 1)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_POSITION, ("id_array", [spa_pod.SPA_AUDIO_CHANNEL_UNKNOWN])),
    ],
)

_POD_AUDIO_F32_STEREO_44K1 = _PodObject(
    spa_pod.SPA_TYPE_OBJECT_FORMAT,
    spa_pod.SPA_PARAM_ENUM_FORMAT,
    [
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_TYPE, ("id", spa_pod.SPA_MEDIA_TYPE_AUDIO)),
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_SUBTYPE, ("id", spa_pod.SPA_MEDIA_SUBTYPE_RAW)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_FORMAT, ("id", spa_pod.SPA_AUDIO_FORMAT_F32)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_RATE, ("int", 44100)),
        _PodProp(spa_pod.SPA_FORMAT_AUDIO_CHANNELS, ("int", 2)),
        _PodProp(
            spa_pod.SPA_FORMAT_AUDIO_POSITION,
            ("id_array", [spa_pod.SPA_AUDIO_CHANNEL_FL, spa_pod.SPA_AUDIO_CHANNEL_FR]),
        ),
    ],
)

_POD_MIDI_CONTROL = _PodObject(
    spa_pod.SPA_TYPE_OBJECT_FORMAT,
    spa_pod.SPA_PARAM_ENUM_FORMAT,
    [
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_TYPE, ("id", spa_pod.SPA_MEDIA_TYPE_APPLICATION)),
        _PodProp(spa_pod.SPA_FORMAT_MEDIA_SUBTYPE, ("id", spa_pod.SPA_MEDIA_SUBTYPE_CONTROL)),
    ],
)


def _spa_ref(e, c):
    return e.fld(e.v("spa"), c.name)


def _pod_value(e, props, value):
    kind, data = value
    if kind == "id":
        return e.call_m(e.v(props), "pod_id", _spa_ref(e, data))
    if kind == "int":
        return e.call_m(e.v(props), "pod_int", e.int_of(data))
    if kind == "id_array":
        values = []
        for v in data:
            values.append(_spa_ref(e, v))
        return e.call_m(e.v(props), "pod_id_array", e.list_new(e.mb.types_int(), *values))
    raise AssertionError(kind)


def _pod_build(e, body, name, obj):
    props = name + "_props"
    body.append(e.let(props, e.call_m0(e.v("spa"), "new_pod")))
    for prop in obj.props:
        body.append(e.call_m(e.v(props), "prop", _spa_ref(e, prop.key)))
        body.append(_pod_value(e, props, prop.value))
    body.append(e.let(name + "_pod", e.call_m0(e.v("spa"), "new_pod")))
    body.append(
        e.call_m(
            e.v(name + "_pod"),
            "pod_object",
            e.rec(
                e.p("ty", _spa_ref(e, obj.object_type)),
                e.p("id", _spa_ref(e, obj.object_id)),
                e.p("props", e.v(props)),
            ),
        )
    )


def byte_array_type(e, llvm, count):
    return e.call(llvm("array"), e.rec(e.p("elem", llvm("u8")), e.p("count", count)))


_Global = namedtuple("_Global", ["name", "global_name", "init"])

_POD_GLOBALS = [
    _Global("pod_audio_f32_mono_48k", "pw.pod.audio_f32_mono_48k", "audio"),
    _Global("pod_audio_f32_stereo_44k1", "pw.pod.audio_f32_stereo_44k1", "audio_stereo_44k1"),
    _Global("pod_midi_control", "pw.pod.midi_control", "midi"),
]

_PARAMS_GLOBALS = [
    _Global("params_audio", "pw.params.audio", "pod_audio_f32_mono_48k"),
    _Global("params_audio_stereo_44k1", "pw.params.audio_stereo_44k1", "pod_audio_f32_stereo_44k1"),
    _Global("params_midi", "pw.params.midi", "pod_midi_control"),
]


def module(e):
    exprs = []
    exprs.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    exprs.append(e.let("spa", e.import_local("spa", "spa-pod-1.6.atz")))
    exprs.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    llvm = llvm_top(e)
    bind_types(e, exprs, llvm)
    for s in _STRUCTS:
        fields = []
        for f in s.fields:
            fields.append(_field(e, llvm, f.name, e.v("t_" + f.ty)))
        exprs.append(e.let("t_" + s.name, _struct_of(e, llvm, e.s(s.name), fields)))
        exprs.append(e.let("t_p_" + s.name, e.call(llvm("ptr"), e.v("t_" + s.name))))
    for s in _TAIL_STRUCTS:
        fields = []
        for f in s.fields:
            fields.append(_field(e, llvm, f.name, e.v("t_" + f.ty)))
        views = []
        for f in s.views:
            views.append(_field(e, llvm, f.name, e.v("t_" + f.ty)))
        len_ = []
        for seg in s.len:
            len_.append(e.s(seg))
        exprs.append(
            e.let(
                "t_" + s.name,
                e.call(
                    llvm("struct_tail"),
                    e.rec(
                        e.p("name", e.s(s.name)),
                        e.p("fields", _field_list(e, llvm, fields)),
                        e.p(
                            "tail",
                            e.call(
                                llvm("tail"),
                                e.rec(
                                    e.p("views", _field_list(e, llvm, views)),
                                    e.p("after", e.s(s.after)),
                                    e.p("len", e.list_new(e.mb.types_string(), *len_)),
                                    e.p("align", e.n(s.align)),
                                ),
                            ),
                        ),
                    ),
                ),
            )
        )
    members = []
    for ex in _EXTERNS:
        members.append(ex.name)
        exprs.append(e.let(ex.name + "_fn_t", ex.fn_type(e, llvm)))
        exprs.append(e.let(ex.name + "_t", ex.extern_t(e, llvm, e.v(ex.name + "_fn_t"), LIB)))
    for name, _ in _OWNED:
        members.append(name)
        exprs.append(e.let(name + "_t", e.mb.eval_type()))
    exprs.append(e.let("konst_t", global_t(e, llvm, e.v("t_u32"))))
    for k in _KONSTS:
        members.append(k.name)
        exprs.append(e.let(k.name + "_t", e.v("konst_t")))
    _pod_build(e, exprs, "audio", _POD_AUDIO_F32_MONO_48K)
    _pod_build(e, exprs, "audio_stereo_44k1", _POD_AUDIO_F32_STEREO_44K1)
    _pod_build(e, exprs, "midi", _POD_MIDI_CONTROL)
    exprs.append(e.let("const_bytes", e.call(llvm("const_list"), llvm("u8"))))
    for g in _POD_GLOBALS:
        members.append(g.name)
        exprs.append(e.let(g.name + "_t", llvm("gref_t")))
    exprs.append(
        e.let("params_arr_t", e.call(llvm("array"), e.rec(e.p("elem", e.v("t_pv")), e.p("count", e.int_of(1)))))
    )
    for g in _PARAMS_GLOBALS:
        members.append(g.name)
        exprs.append(e.let(g.name + "_t", global_t(e, llvm, e.call(llvm("ptr"), e.v("params_arr_t")))))

    exprs.append(e.let("d", e.define()))
    exprs.append(e.option_type_let())
    exprs.append(e.let("pw_o", e.def_object(e.v("d"), "pipewire 1.6")))
    inner_fields = []
    for m in members:
        inner_fields.append(e.p(m, e.v(m + "_t")))
    exprs.append(e.object_impl(e.v("pw_o"), e.rec(*inner_fields)))
    for m in members:
        exprs.append(
            e.method_impl(e.v("pw_o"), m, e.tup(), e.option_type_some(e.v(m + "_t")), e.stage(e.fld(e.v("inner"), m)))
        )
    struct_names = []
    for s in _STRUCTS:
        struct_names.append(s.name)
    for s in _TAIL_STRUCTS:
        struct_names.append(s.name)
    for name in struct_names:
        exprs.append(
            e.method_impl(
                e.v("pw_o"), name, e.tup(), e.option_type_some(e.mb.eval_type()), e.stage(e.lower_v("t_" + name))
            )
        )

    def llvm_lowered(name):
        return e.lower(e.fld(e.v("llvm"), name))

    spa_data = []
    for f in _SPA_DATA_FIELDS:
        spa_data.append(_field(e, llvm_lowered, f.name, e.lower_v("t_" + f.ty)))
    spa_data.append(_field(e, llvm_lowered, "data", e.call(llvm_lowered("ptr"), e.fld(e.v("arg"), "payload"))))
    spa_data.append(_field(e, llvm_lowered, "chunk", e.lower_v("t_p_spa_chunk")))
    spa_buffer = [
        _field(e, llvm_lowered, "n_metas", e.lower_v("t_u32")),
        _field(e, llvm_lowered, "n_datas", e.lower_v("t_u32")),
        _field(e, llvm_lowered, "metas", e.lower_v("t_pv")),
        _field(e, llvm_lowered, "datas", e.call(llvm_lowered("ptr"), e.v("spa_data"))),
    ]
    pw_buffer = [_field(e, llvm_lowered, "buffer", e.call(llvm_lowered("ptr"), e.v("spa_buffer")))]
    for f in _PW_BUFFER_FIELDS:
        pw_buffer.append(_field(e, llvm_lowered, f.name, e.lower_v("t_" + f.ty)))
    exprs.append(
        e.method_impl(
            e.v("pw_o"),
            "buffer_t",
            e.rec(e.p("name", e.mb.types_string()), e.p("payload", e.mb.eval_type())),
            e.option_type_some(e.mb.eval_type()),
            e.stage(
                e.seq(
                    e.let(
                        "spa_data",
                        _struct_of(e, llvm_lowered, e.cat(e.s("spa_data."), e.fld(e.v("arg"), "name")), spa_data),
                    ),
                    e.let(
                        "spa_buffer",
                        _struct_of(e, llvm_lowered, e.cat(e.s("spa_buffer."), e.fld(e.v("arg"), "name")), spa_buffer),
                    ),
                    e.ret(_struct_of(e, llvm_lowered, e.cat(e.s("pw_buffer."), e.fld(e.v("arg"), "name")), pw_buffer)),
                )
            ),
        )
    )
    exprs.append(
        e.method_impl(
            e.v("pw_o"),
            "dequeue_buffer_t",
            e.mb.eval_type(),
            e.option_type_some(e.mb.eval_type()),
            e.stage(
                e.call(
                    llvm_lowered("fn"),
                    e.rec(
                        e.p("params", e.list_new(e.mb.eval_type(), e.lower_v("t_pv"))),
                        e.p("ret", e.call(llvm_lowered("ptr"), e.v("arg"))),
                    ),
                )
            ),
        )
    )
    exprs.append(
        e.method_impl(
            e.v("pw_o"),
            "queue_buffer_t",
            e.mb.eval_type(),
            e.option_type_some(e.mb.eval_type()),
            e.stage(
                e.call(
                    llvm_lowered("fn"),
                    e.rec(
                        e.p(
                            "params",
                            e.list_new(e.mb.eval_type(), e.lower_v("t_pv"), e.call(llvm_lowered("ptr"), e.v("arg"))),
                        ),
                        e.p("ret", e.lower_v("t_i32")),
                    ),
                )
            ),
        )
    )

    exprs.append(e.let("pw_builder", e.def_func(e.v("d"), "pipewire")))
    body = []
    for ex in _EXTERNS:
        body.append(
            e.let(ex.name, ex.declare(e, e.lower(e.fld(e.v("llvm"), "extern_fn")), e.lower_v(ex.name + "_fn_t"), LIB))
        )
    for name, destroy in _OWNED:
        body.append(
            e.let(
                name,
                e.call(
                    e.lower(e.fld(e.v("destructor"), "type")),
                    e.rec(e.p("under", e.lower_v("t_pv")), e.p("destroy", e.v(destroy))),
                ),
            )
        )
    for k in _KONSTS:
        body.append(
            e.let(
                k.name,
                e.call(
                    e.lower(e.fld(e.v("llvm"), "constant_fn")),
                    e.rec(e.p("ty", e.lower_v("t_u32")), e.p("value", e.n(k.value))),
                ),
            )
        )
    for g in _POD_GLOBALS:
        body.append(
            e.let(
                g.name,
                e.call(
                    e.lower_v("const_bytes"),
                    e.rec(
                        e.p("mod", e.v("arg")),
                        e.p("name", e.s(g.global_name)),
                        e.p("values", e.lower(e.call_m0(e.v(g.init + "_pod"), "bytes"))),
                    ),
                ),
            )
        )
    for g in _PARAMS_GLOBALS:
        body.append(
            e.let(
                g.name,
                e.call(
                    e.lower(e.fld(e.v("llvm"), "global_const_fn")),
                    e.rec(
                        e.p("mod", e.v("arg")),
                        e.p("name", e.s(g.global_name)),
                        e.p("ty", e.lower_v("params_arr_t")),
                        e.p("init", e.tup(e.v(g.init))),
                    ),
                ),
            )
        )
    ctor_fields = []
    for m in members:
        ctor_fields.append(e.p(m, e.v(m)))
    body.append(e.ret(e.call(e.lower(e.fld(e.v("pw_o"), "new")), e.rec(*ctor_fields))))
    exprs.append(
        e.func_impl(
            e.v("pw_builder"),
            e.fld(e.v("llvm"), "mod_t"),
            e.option_type_some(e.fld(e.v("pw_o"), "type")),
            e.mb.opt_none_type(),
            e.stage(e.mb.seq(body)),
        )
    )

    exprs.append(e.finish(e.v("d")))
    exprs.append(e.ret(e.fld(e.v("pw_builder"), "func")))
    return exprs
