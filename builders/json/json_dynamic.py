"""json-dynamic.atz: json.atz over the dynamic target, the one `builtins.define` builds for, so json is parsed
and written on the host at compile time.

- `event`: the union of parse events and its constructors: `end`, `error` (an int code), `null`, `bool` (an int),
  `number`, `string`, `key` (a `list(ubyte)`), `object_begin`, `object_end`, `array_begin`, `array_end`.
- `reader`: an object reading a `list(ubyte)`: `reader.new({bytes, pos})`.
- `parser`: `parser.new(r)` is a parser over the reader `r`; `p.next()` consumes one value or structural token
  and yields its event (`end` at the end of the document and after; `error` once the document is malformed and
  after).
- `writer`: `writer.new(())` collects compact json; `w.null()`, `w.bool(v)`, `w.int(v)`, `w.number(s)`,
  `w.string(s)`, `w.key(s)` (s a `list(ubyte)`), `w.object_begin()`, `w.object_end()`, `w.array_begin()`,
  `w.array_end()` write one piece each, `w.clear()` starts over and `w.text()` is what was written, as a string.
- `bytebuf`: the byte buffer object json.atz's logic works through (`push`, `clear`, `pop`, `len`, `at`,
  `slice`), over a `list(ubyte)` and a length. Bytes are unsigned throughout (`ubyte`); `text` converts to the
  signed bytes `str_from_utf8` takes.

Mutable state across calls lives in an object's fields (a value lowered into a function body is a constant
snapshot). The parser's `next` and the writer's pieces stage json.atz's logic once each, in the methods here.
"""

from ..target_mb import t
from . import json

FILE = "json-dynamic.atz"

EVENTS = json.EVENTS
LIST_EVENTS = ["number", "string", "key"]
INT_EVENTS = ["error", "bool"]

WRITER_PIECES = {
    "null": None,
    "bool": "int",
    "int": "int",
    "number": "bytes",
    "string": "bytes",
    "key": "bytes",
    "object_begin": None,
    "object_end": None,
    "array_begin": None,
    "array_end": None,
}


def _in(e, field):
    return e.fld(e.v("inner"), field)


def _arg(e):
    return e.v("arg")


def _ubyte(e):
    return e.mb.builtin("types", "ubyte")


def _bytes_t(e):
    return e.list_type(_ubyte(e))


def _method(e, out, obj, name, arg_type, ret, body):
    """A method of `obj`; `ret` is None for one yielding nothing."""
    ret_type = e.option_type_some(ret) if ret is not None else e.option_type_none()
    out.append(e.method_impl(e.v(obj), name, arg_type, ret_type, e.stage(body)))


def _func(e, out, name, arg_type, ret, body):
    """A function of the set, bound as `name` (its value) from `name_b`; `ret` is None for one yielding nothing."""
    ret_type = e.option_type_some(ret) if ret is not None else e.option_type_none()
    out.append(e.let(name + "_b", e.def_func(e.v("d"), "json_dynamic." + name)))
    out.append(e.func_impl(e.v(name + "_b"), arg_type, ret_type, e.option_type_none(), e.stage(body)))
    out.append(e.let(name, e.fld(e.v(name + "_b"), "func")))


def _bytebuf(e, top):
    top.append(e.let("bytebuf", e.def_object(e.v("d"), "json byte buffer")))
    top.append(e.object_impl(e.v("bytebuf"), e.rec(e.p("items", _bytes_t(e)), e.p("n", e.mb.types_int()))))
    byte = e.mb.as_(_arg(e), _ubyte(e))
    _method(
        e,
        top,
        "bytebuf",
        "push",
        e.mb.types_int(),
        None,
        e.seq(
            e.if_else(
                e.mb.operator_lt(_in(e, "n"), e.fld(_in(e, "items"), "len")),
                e.call_m(_in(e, "items"), "set", e.tup(_in(e, "n"), byte)),
                e.push(_in(e, "items"), byte),
            ),
            e.mb.set(_in(e, "n"), e.mb.operator_add(_in(e, "n"), e.int_of(1))),
        ),
    )
    _method(e, top, "bytebuf", "clear", e.tup(), None, e.mb.set(_in(e, "n"), e.int_of(0)))
    _method(e, top, "bytebuf", "pop", e.tup(), None, e.mb.set(_in(e, "n"), e.mb.operator_sub(_in(e, "n"), e.int_of(1))))
    _method(e, top, "bytebuf", "len", e.tup(), e.mb.types_int(), e.seq(e.ret(_in(e, "n"))))
    _method(
        e,
        top,
        "bytebuf",
        "at",
        e.mb.types_int(),
        e.mb.types_int(),
        e.seq(e.ret(e.mb.as_(e.call_m(_in(e, "items"), "get", _arg(e)), e.mb.types_int()))),
    )
    _method(
        e,
        top,
        "bytebuf",
        "slice",
        e.tup(),
        _bytes_t(e),
        e.seq(
            e.let("out", e.list_new(_ubyte(e))),
            e.let("i", e.int_of(0)),
            e.foreach(
                _in(e, "items"),
                "b",
                e.seq(
                    e.if_only(e.mb.operator_lt(e.v("i"), _in(e, "n")), e.push(e.v("out"), e.v("b"))),
                    e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.int_of(1))),
                ),
            ),
            e.ret(e.v("out")),
        ),
    )


def _bytebuf_new(e, items, n):
    return e.call(e.lower(e.fld(e.v("bytebuf"), "new")), e.rec(e.p("items", items), e.p("n", n)))


def _reader(e, top):
    top.append(e.let("reader", e.def_object(e.v("d"), "json byte reader")))
    top.append(e.object_impl(e.v("reader"), e.rec(e.p("bytes", _bytes_t(e)), e.p("pos", e.mb.types_int()))))
    # read(): the next byte, or -1 at the end.
    _method(
        e,
        top,
        "reader",
        "read",
        e.tup(),
        e.mb.types_int(),
        e.seq(
            e.let("r", e.int_of(-1)),
            e.if_only(
                e.mb.operator_lt(_in(e, "pos"), e.fld(_in(e, "bytes"), "len")),
                e.seq(
                    e.mb.set(e.v("r"), e.mb.as_(e.call_m(_in(e, "bytes"), "get", _in(e, "pos")), e.mb.types_int())),
                    e.mb.set(_in(e, "pos"), e.mb.operator_add(_in(e, "pos"), e.int_of(1))),
                ),
            ),
            e.ret(e.v("r")),
        ),
    )
    # The parser's read op: a function of the reader (json.atz calls `read(p.ctx)`).
    _func(e, top, "read", t(e, "reader"), e.mb.types_int(), e.seq(e.ret(e.call_m(_arg(e), "read", e.tup()))))


def _events(e, top):
    top.append(e.let("event_u", e.call_m0(e.v("d"), "union")))
    for kind in EVENTS:
        if kind in LIST_EVENTS:
            type_ref = _bytes_t(e)
        elif kind in INT_EVENTS:
            type_ref = e.mb.types_int()
        else:
            type_ref = e.tup()
        top.append(
            e.let(
                "ev_" + kind,
                e.call_m(e.v("event_u"), "variant", e.rec(e.p("tag", e.s(kind)), e.p("type_ref", type_ref))),
            )
        )


def _parser(e, top):
    fields = [e.p("ctx", t(e, "reader"))]
    for name in json.REGISTERS:
        fields.append(e.p(name, e.mb.types_int()))
    fields.append(e.p("data", t(e, "bytebuf")))
    fields.append(e.p("stack", t(e, "bytebuf")))
    top.append(e.let("parser", e.def_object(e.v("d"), "json parser")))
    top.append(e.object_impl(e.v("parser"), e.rec(*fields)))
    _method(
        e,
        top,
        "parser",
        "next",
        e.tup(),
        t(e, "event_u"),
        e.seq(
            e.ret(
                e.call(
                    e.fld(e.lower(e.v("json")), "next"),
                    e.rec(
                        e.p("int", e.mb.types_int()),
                        e.p("read", e.lower(e.v("read"))),
                        e.p("event", e.rec(*[e.p(kind, e.lower(e.v("ev_" + kind))) for kind in EVENTS])),
                        e.p("p", e.v("inner")),
                    ),
                )
            )
        ),
    )
    init = [e.p("ctx", _arg(e))]
    for name in json.REGISTERS:
        init.append(e.p(name, e.int_of(json.UNREAD if name == "c" else 0)))
    for name in ["data", "stack"]:
        init.append(e.p(name, _bytebuf_new(e, e.list_new(_ubyte(e)), e.int_of(0))))
    _func(
        e,
        top,
        "parser_new",
        t(e, "reader"),
        t(e, "parser"),
        e.seq(e.ret(e.call(e.lower(e.fld(e.v("parser"), "new")), e.rec(*init)))),
    )


def _writer(e, top):
    top.append(e.let("writer", e.def_object(e.v("d"), "json writer")))
    # The fields are what json.atz touches: `ctx`, passed to the sink (the out buffer), and `pending`.
    top.append(e.object_impl(e.v("writer"), e.rec(e.p("ctx", t(e, "bytebuf")), e.p("pending", e.mb.types_int()))))
    _func(
        e,
        top,
        "write",
        e.tup(t(e, "bytebuf"), e.mb.types_int()),
        None,
        e.call_m(e.mb.field(_arg(e), e.n(0)), "push", e.mb.field(_arg(e), e.n(1))),
    )

    def piece(kind, extra):
        return e.call(
            e.fld(e.lower(e.v("json")), "write_" + kind),
            e.rec(
                e.p("write", e.lower(e.v("write"))),
                e.p("w", e.v("inner")),
                *extra,
            ),
        )

    for kind, arg in WRITER_PIECES.items():
        if arg is None:
            _method(e, top, "writer", kind, e.tup(), None, piece(kind, []))
        elif arg == "int":
            extra = [e.p("value", _arg(e))]
            if kind == "int":
                extra.append(e.p("int", e.mb.types_int()))
            _method(e, top, "writer", kind, e.mb.types_int(), None, piece(kind, extra))
        else:
            # The bytes as a buffer value, bound first: json.atz splices `s` wherever it touches them.
            _method(
                e,
                top,
                "writer",
                kind,
                _bytes_t(e),
                None,
                e.seq(
                    e.let("sb", _bytebuf_new(e, _arg(e), e.fld(_arg(e), "len"))),
                    piece(kind, [e.p("int", e.mb.types_int()), e.p("s", e.v("sb"))]),
                ),
            )
    _method(
        e,
        top,
        "writer",
        "clear",
        e.tup(),
        None,
        e.seq(e.call_m(_in(e, "ctx"), "clear", e.tup()), e.mb.set(_in(e, "pending"), e.int_of(0))),
    )
    _method(
        e,
        top,
        "writer",
        "text",
        e.tup(),
        e.mb.types_string(),
        e.seq(
            e.let("signed", e.list_new(e.mb.types_byte())),
            e.foreach(
                e.call_m(_in(e, "ctx"), "slice", e.tup()),
                "b",
                e.push(e.v("signed"), e.mb.as_(e.v("b"), e.mb.types_byte())),
            ),
            e.ret(
                e.match_of(
                    e.call(e.eval_builtin("str_from_utf8"), e.v("signed")),
                    "__s",
                    None,
                    e.p("some", e.v("__s")),
                    e.p("none", e.mb.panic(e.s("json: the output is not valid UTF-8"))),
                )
            ),
        ),
    )
    _func(
        e,
        top,
        "writer_new",
        e.tup(),
        t(e, "writer"),
        e.seq(
            e.ret(
                e.call(
                    e.lower(e.fld(e.v("writer"), "new")),
                    e.rec(
                        e.p("ctx", _bytebuf_new(e, e.list_new(_ubyte(e)), e.int_of(0))),
                        e.p("pending", e.int_of(0)),
                    ),
                )
            )
        ),
    )


def module(e):
    top = []
    top.append(e.let("json", e.import_local("json", json.FILE)))
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    _bytebuf(e, top)
    _reader(e, top)
    _events(e, top)
    _parser(e, top)
    _writer(e, top)
    top.append(e.finish(e.v("d")))
    top.append(
        e.ret(
            e.rec(
                e.p(
                    "event",
                    e.rec(e.p("type", t(e, "event_u")), *[e.p(kind, e.v("ev_" + kind)) for kind in EVENTS]),
                ),
                e.p("reader", e.rec(e.p("type", t(e, "reader")), e.p("new", e.fld(e.v("reader"), "new")))),
                e.p("parser", e.rec(e.p("type", t(e, "parser")), e.p("new", e.v("parser_new")))),
                e.p("writer", e.rec(e.p("type", t(e, "writer")), e.p("new", e.v("writer_new")))),
                e.p("bytebuf", e.rec(e.p("type", t(e, "bytebuf")), e.p("new", e.fld(e.v("bytebuf"), "new")))),
            )
        )
    )
    return top
