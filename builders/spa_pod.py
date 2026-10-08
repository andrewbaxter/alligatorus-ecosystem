"""spa-pod-1.6.atz: SPA pod builder and the SPA constants it uses."""

from collections import namedtuple

SpaConst = namedtuple("SpaConst", ["name", "value"])

SPA_TYPE_ID = SpaConst("type_id", 3)
SPA_TYPE_INT = SpaConst("type_int", 4)
SPA_TYPE_ARRAY = SpaConst("type_array", 13)
SPA_TYPE_OBJECT = SpaConst("type_object", 15)
SPA_TYPE_OBJECT_FORMAT = SpaConst("type_object_format", 0x40003)
SPA_PARAM_ENUM_FORMAT = SpaConst("param_enum_format", 3)
SPA_FORMAT_MEDIA_TYPE = SpaConst("format_media_type", 1)
SPA_FORMAT_MEDIA_SUBTYPE = SpaConst("format_media_subtype", 2)
SPA_FORMAT_AUDIO_FORMAT = SpaConst("format_audio_format", 0x10001)
SPA_FORMAT_AUDIO_RATE = SpaConst("format_audio_rate", 0x10003)
SPA_FORMAT_AUDIO_CHANNELS = SpaConst("format_audio_channels", 0x10004)
SPA_FORMAT_AUDIO_POSITION = SpaConst("format_audio_position", 0x10005)
SPA_MEDIA_TYPE_AUDIO = SpaConst("media_type_audio", 1)
SPA_MEDIA_TYPE_APPLICATION = SpaConst("media_type_application", 6)
SPA_MEDIA_SUBTYPE_RAW = SpaConst("media_subtype_raw", 1)
SPA_MEDIA_SUBTYPE_CONTROL = SpaConst("media_subtype_control", 0x60001)
SPA_AUDIO_FORMAT_F32 = SpaConst("audio_format_f32", 0x11B)
SPA_AUDIO_CHANNEL_UNKNOWN = SpaConst("audio_channel_unknown", 0)
SPA_AUDIO_CHANNEL_FL = SpaConst("audio_channel_fl", 3)
SPA_AUDIO_CHANNEL_FR = SpaConst("audio_channel_fr", 4)

_SPA_CONSTS = [
    SPA_TYPE_ID,
    SPA_TYPE_INT,
    SPA_TYPE_ARRAY,
    SPA_TYPE_OBJECT,
    SPA_TYPE_OBJECT_FORMAT,
    SPA_PARAM_ENUM_FORMAT,
    SPA_FORMAT_MEDIA_TYPE,
    SPA_FORMAT_MEDIA_SUBTYPE,
    SPA_FORMAT_AUDIO_FORMAT,
    SPA_FORMAT_AUDIO_RATE,
    SPA_FORMAT_AUDIO_CHANNELS,
    SPA_FORMAT_AUDIO_POSITION,
    SPA_MEDIA_TYPE_AUDIO,
    SPA_MEDIA_TYPE_APPLICATION,
    SPA_MEDIA_SUBTYPE_RAW,
    SPA_MEDIA_SUBTYPE_CONTROL,
    SPA_AUDIO_FORMAT_F32,
    SPA_AUDIO_CHANNEL_UNKNOWN,
    SPA_AUDIO_CHANNEL_FL,
    SPA_AUDIO_CHANNEL_FR,
]


def _spa(e, c):
    return e.lower(e.v(c.name))


def _pod_new(e):
    return e.call(e.lower(e.fld(e.v("pod_b"), "new")), e.rec(e.p("bytes", e.list_new(e.mb.builtin("types", "ubyte")))))


def _pod_bytes(e):
    return e.fld(e.v("inner"), "bytes")


def _self(e, method, arg):
    return e.call_m(e.v("outer"), method, arg)


def _byte_of(e, v, shift):
    return e.mb.operator_and(v if shift == 0 else e.mb.operator_ushr(v, e.n(shift)), e.n(255))


def _pod_method(e, out, name, arg, ret, body):
    out.append(e.method_impl(e.v("pod_b"), name, arg, ret, e.stage(body)))


def module(e):
    exprs = []
    exprs.append(e.let("d", e.define()))
    exprs.append(e.option_type_let())
    pod_t = e.fld(e.v("pod_b"), "type")
    int_t = e.mb.types_int()
    byte_t = e.mb.builtin("types", "ubyte")
    for c in _SPA_CONSTS:
        exprs.append(e.let(c.name, e.mb.num(c.value)))
    exprs.append(e.let("pod_b", e.def_object(e.v("d"), "spa pod builder")))
    exprs.append(e.object_impl(e.v("pod_b"), e.rec(e.p("bytes", e.list_type(byte_t)))))
    _pod_method(e, exprs, "bytes", e.tup(), e.option_type_some(e.list_type(byte_t)), _pod_bytes(e))
    _pod_method(
        e,
        exprs,
        "len",
        e.tup(),
        e.option_type_some(int_t),
        e.seq(
            e.let("n", e.rec(e.p("v", e.int_of(0)))),
            e.foreach(_pod_bytes(e), "_", e.incr(e.fld(e.v("n"), "v"))),
            e.ret(e.fld(e.v("n"), "v")),
        ),
    )
    _pod_method(
        e,
        exprs,
        "u32",
        int_t,
        e.option_type_none(),
        e.seq(
            e.push(_pod_bytes(e), _byte_of(e, e.v("arg"), 0)),
            e.push(_pod_bytes(e), _byte_of(e, e.v("arg"), 8)),
            e.push(_pod_bytes(e), _byte_of(e, e.v("arg"), 16)),
            e.push(_pod_bytes(e), _byte_of(e, e.v("arg"), 24)),
        ),
    )
    pad_steps = []
    for _ in range(7):
        pad_steps.append(
            e.if_only(
                e.mb.operator_ne(e.mb.operator_mod(_self(e, "len", e.tup()), e.int_of(8)), e.int_of(0)),
                e.push(_pod_bytes(e), e.n(0)),
            )
        )
    _pod_method(e, exprs, "pad", e.tup(), e.option_type_none(), e.seq(*pad_steps))
    _pod_method(
        e,
        exprs,
        "append",
        pod_t,
        e.option_type_none(),
        e.foreach(e.call_m(e.v("arg"), "bytes", e.tup()), "b", e.push(_pod_bytes(e), e.v("b"))),
    )
    _pod_method(
        e,
        exprs,
        "pod",
        e.rec(e.p("ty", int_t), e.p("body", pod_t)),
        e.option_type_none(),
        e.seq(
            _self(e, "u32", e.call_m(e.fld(e.v("arg"), "body"), "len", e.tup())),
            _self(e, "u32", e.fld(e.v("arg"), "ty")),
            _self(e, "append", e.fld(e.v("arg"), "body")),
            _self(e, "pad", e.tup()),
        ),
    )
    for scalar in ["pod_id", "pod_int"]:
        _pod_method(
            e,
            exprs,
            scalar,
            int_t,
            e.option_type_none(),
            e.seq(
                e.let("b", _pod_new(e)),
                e.call_m(e.v("b"), "u32", e.v("arg")),
                _self(
                    e,
                    "pod",
                    e.rec(
                        e.p("ty", _spa(e, SPA_TYPE_ID if scalar == "pod_id" else SPA_TYPE_INT)),
                        e.p("body", e.v("b")),
                    ),
                ),
            ),
        )
    _pod_method(
        e,
        exprs,
        "pod_id_array",
        e.list_type(int_t),
        e.option_type_none(),
        e.seq(
            e.let("b", _pod_new(e)),
            e.call_m(e.v("b"), "u32", e.n(4)),
            e.call_m(e.v("b"), "u32", _spa(e, SPA_TYPE_ID)),
            e.foreach(e.v("arg"), "v", e.call_m(e.v("b"), "u32", e.v("v"))),
            _self(e, "pod", e.rec(e.p("ty", _spa(e, SPA_TYPE_ARRAY)), e.p("body", e.v("b")))),
        ),
    )
    _pod_method(
        e, exprs, "prop", int_t, e.option_type_none(), e.seq(_self(e, "u32", e.v("arg")), _self(e, "u32", e.n(0)))
    )
    _pod_method(
        e,
        exprs,
        "pod_object",
        e.rec(e.p("ty", int_t), e.p("id", int_t), e.p("props", pod_t)),
        e.option_type_none(),
        e.seq(
            e.let("b", _pod_new(e)),
            e.call_m(e.v("b"), "u32", e.fld(e.v("arg"), "ty")),
            e.call_m(e.v("b"), "u32", e.fld(e.v("arg"), "id")),
            e.call_m(e.v("b"), "append", e.fld(e.v("arg"), "props")),
            _self(e, "pod", e.rec(e.p("ty", _spa(e, SPA_TYPE_OBJECT)), e.p("body", e.v("b")))),
        ),
    )
    exprs.append(e.let("new_pod_b", e.def_func(e.v("d"), "new_pod")))
    exprs.append(
        e.func_impl(e.v("new_pod_b"), e.tup(), e.option_type_some(pod_t), e.mb.opt_none_type(), e.stage(_pod_new(e)))
    )
    exprs.append(e.finish(e.v("d")))
    exports = []
    exports.append(e.p("new_pod", e.fld(e.v("new_pod_b"), "func")))
    exports.append(e.p("pod_t", pod_t))
    for c in _SPA_CONSTS:
        exports.append(e.p(c.name, e.v(c.name)))
    exprs.append(e.ret(e.rec(*exports)))
    return exprs
