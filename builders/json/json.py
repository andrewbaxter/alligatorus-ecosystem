"""json.atz: the parsing and serializing logic of json, belonging to no target.

Every export is a const function: called from inside a target function body with a record of ops, values of the
caller's target, it stages the json code over those ops in the caller's context, so the code it produces belongs
to whatever target the caller builds for. json-wasm.atz and json-llvm.atz call them once per module, inside the
functions they define, so an app gets one parser and one writer function per reader or sink; nothing here is
staged per use.

`next {ops}` stages the body of a pull parser's `next`: it consumes one value or structural token from the
reader and yields the event for it. The ops:

    int                        the target's int type
    read                       (ctx) -> int: the next byte of input, or a negative int at its end
    event                      the event constructors (per-target union): end, error, null, bool, number,
                               string, key, object_begin, object_end, array_begin, array_end
    p                          the parser's state, a value whose fields are the places below (a value without
                               code of its own: it is spliced wherever the state is touched)

    p.ctx                      the value passed to every read
    p.c                        the lookahead byte, assignable; UNREAD before the first read
    p.state, p.fresh, p.err, p.is_key, p.cp, p.lo, p.h, p.i, p.flag     the registers, assignable ints
    p.data                     a byte buffer (below): the current token's content
    p.stack                    a byte buffer: one byte per open container (1 object, 0 array)

A byte buffer is a value with the methods `push(b)` (b an int), `clear()`, `pop()`, `len() -> int`,
`at(i) -> int` and `slice()`, the buffer's bytes as the target's payload for `number`, `string` and `key`.

`next` returns `end` once the document is complete (and at every call after), `error(code)` when the document is
malformed (and at every call after; the codes are 1 unexpected byte, 2 unexpected end of input, 4 data after the
document, 5 bad escape), `number`, `string` and `key` with the token's bytes as a slice of `data` (valid until
the next call), `bool` with 1 or 0, and the container events. There is no depth limit: the stack grows.

The `write_*` functions each stage one piece of json over `write` ((ctx, b) -> (), a byte of output) and `w`,
the writer's state, a value (without code of its own) whose fields are `ctx`, passed to every write, and
`pending`, an assignable int place that is 1 when a comma is due before the next value (zeroed before the first
value and never touched again by the caller):

    write_null          {write, w}
    write_bool          {write, w, value}       value: 0 false, else true
    write_int           {write, w, int, value}  int: the target's int type
    write_number        {write, w, int, s}      s: the raw bytes of a number (a byte view: len() and at(i))
    write_string        {write, w, int, s}      s: utf-8 bytes, escaped as json needs
    write_key           {write, w, int, s}      an object key, with its colon
    write_object_begin, write_object_end, write_array_begin, write_array_end   {write, w}
"""

from ..eco_mb import p
from ..target_mb import (
    a,
    asp_iface,
    bim,
    body,
    const_eval_in,
    const_fn,
    cve_has,
    cve_type,
    cve_value,
    err_cve,
    graft,
    loc,
    lookup,
    ok_cve,
    ret_m,
    unwrap_cve_m,
    xx,
)

FILE = "json.atz"

ERR_BYTE = 1
ERR_END = 2
ERR_TRAILING = 4
ERR_ESCAPE = 5

# the lookahead before the first read
UNREAD = -2

# parser states
WANT_VALUE = 0
AFTER_VALUE = 1
WANT_KEY = 2
DONE = 3
FAILED = 4

REGISTERS = ["c", "state", "fresh", "err", "is_key", "cp", "lo", "h", "i", "flag"]

EVENTS = [
    "end",
    "error",
    "null",
    "bool",
    "number",
    "string",
    "key",
    "object_begin",
    "object_end",
    "array_begin",
    "array_end",
]

NEXT_OPS = ["int", "read", "event", "p"]

WRITE_OPS = ["write", "w"]


def _op(e, name):
    """The caller's op (a value in the caller's context), grafted into the generated code."""
    return graft(e, e.v("op_" + name))


def _stmt(e, call):
    """A call as a statement: whatever it yields is dropped, so an op may return a value even where a value would
    be an error, such as an `if` without an `else`."""
    return e.seq(call, e.seq())


def take_fields(e, out, cv, names, prefix):
    """Binds `<prefix><name>` to the code value of each named field of the record code value `cv`."""
    out.append(e.let(prefix + "_rk", lookup(e, xx(e), cve_type(e, cv), asp_iface(e, "record"))))
    out.append(
        e.if_only(
            e.not_(e.fld(e.v(prefix + "_rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "json: the " + prefix.rstrip("_") + " argument must be a record")),
        )
    )
    out.append(
        e.let(
            prefix + "_fields",
            bim(
                e,
                asp_iface(e, "record"),
                "take_fields",
                e.fld(e.v(prefix + "_rk"), "value"),
                e.rec(e.p("xx", xx(e)), e.p("loc", loc(e)), e.p("value", cve_value(e, cv))),
            ),
        )
    )
    for name in names:
        out.append(e.let(prefix + name, unwrap_cve_m(e, e.call_m(e.v(prefix + "_fields"), "get", e.s(name)))))


def take_argument(e, out, names):
    """Binds `op_<name>` to the code value of each named field of the argument record."""
    out.append(e.let("argv", a(e, "argument")))
    out.append(
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "json: the argument has no value")))
    )
    take_fields(e, out, e.v("argv"), names, "op_")


def _const_func(e, top, name, ops, gen, extra=()):
    """The json const function `name` taking the record of ops `ops`, staging `gen` in the caller's context."""
    prelude = []
    take_argument(e, prelude, ops)
    prelude.extend(extra)
    const_fn(
        e,
        top,
        name + "_b",
        "json." + name,
        body(e, *prelude, ret_m(e, ok_cve(e, unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(gen)))))),
    )


# --- generated code helpers ---


def _reg(e, name):
    """A field of the parser's state: a register, the reader's argument or a vec."""
    return e.fld(_op(e, "p"), name)


def _c(e):
    return _reg(e, "c")


def _is(e, byte):
    return e.eq(_c(e), e.n(ord(byte)))


def _isnt(e, byte):
    return e.mb.operator_ne(_c(e), e.n(ord(byte)))


def _between(e, value, low, high, then):
    """`then` when low <= value <= high."""
    return e.if_only(e.mb.operator_ge(value, e.n(low)), e.if_only(e.mb.operator_le(value, e.n(high)), then))


def _set(e, name, value):
    return e.mb.set(_reg(e, name), value)


def _next(e):
    """Advances the lookahead byte."""
    return _set(e, "c", e.call(_op(e, "read"), _reg(e, "ctx")))


def _loop(e, label, *stmts):
    return e.mb.labeled(label, e.mb.loop(e.seq(*stmts)))


def _break(e, label):
    return e.mb.return_label(label)


def _ev(e, name, *args):
    """An event, made through the caller's constructor."""
    return e.call(graft(e, e.v("ev_" + name)), args[0] if len(args) == 1 else e.tup(*args))


def _yield(e, name, *args):
    """Ends `next` with the event."""
    return e.mb.return_to("next", _ev(e, name, *args))


def _fail(e, code=None):
    """Reports an error (an unexpected byte or end of input unless `code` is given) and stops parsing."""
    if code is None:
        report = e.if_else(e.mb.operator_lt(_c(e), e.n(0)), _set(e, "err", e.n(ERR_END)), _set(e, "err", e.n(ERR_BYTE)))
    else:
        report = _set(e, "err", e.n(code))
    return e.seq(report, _set(e, "state", e.n(FAILED)), _yield(e, "error", _reg(e, "err")))


def _vec(e, name, method, *args):
    """A call of the vec method as a statement."""
    return _stmt(e, e.call(e.fld(_reg(e, name), method), args[0] if len(args) == 1 else e.tup(*args)))


def _push(e, b):
    """Appends `b` (an int) to the data."""
    return _vec(e, "data", "push", b)


def _stack_len(e):
    return e.call(e.fld(_reg(e, "stack"), "len"), e.tup())


def _stack_top(e):
    """The kind of the innermost container."""
    return e.call(e.fld(_reg(e, "stack"), "at"), e.mb.operator_sub(_stack_len(e), e.n(1)))


def _stack_pop(e):
    return _vec(e, "stack", "pop", e.tup())


def _data_slice(e):
    return e.call(e.fld(_reg(e, "data"), "slice"), e.tup())


def _skip_ws(e):
    checks = []
    for ws in " \t\n\r":
        checks.append((_is(e, ws), _next(e)))
    return _loop(e, "ws", e.mb.if_of(checks, _break(e, "ws")))


def _expect_literal(e, text, then):
    """The rest of a literal whose first byte is the lookahead, then `then` with the lookahead past it."""
    stmts = []
    for ch in text[1:]:
        stmts.append(_next(e))
        stmts.append(e.if_only(e.mb.operator_ne(_c(e), e.n(ord(ch))), _fail(e)))
    stmts.append(_next(e))
    stmts.append(_set(e, "state", e.n(AFTER_VALUE)))
    stmts.append(then)
    return e.seq(*stmts)


def _digits(e, label):
    """Collects digits while the lookahead is one."""
    return _loop(
        e,
        label,
        e.if_only(e.mb.operator_lt(_c(e), e.n(ord("0"))), _break(e, label)),
        e.if_only(e.mb.operator_gt(_c(e), e.n(ord("9"))), _break(e, label)),
        _push(e, _c(e)),
        _next(e),
    )


def _require_digit(e):
    return e.seq(
        e.if_only(e.mb.operator_lt(_c(e), e.n(ord("0"))), _fail(e)),
        e.if_only(e.mb.operator_gt(_c(e), e.n(ord("9"))), _fail(e)),
    )


def _number(e):
    return e.seq(
        _vec(e, "data", "clear", e.tup()),
        e.if_only(_is(e, "-"), e.seq(_push(e, _c(e)), _next(e))),
        _require_digit(e),
        e.if_else(
            _is(e, "0"),
            e.seq(_push(e, _c(e)), _next(e)),
            _digits(e, "int_digits"),
        ),
        e.if_only(
            _is(e, "."),
            e.seq(_push(e, _c(e)), _next(e), _require_digit(e), _digits(e, "frac_digits")),
        ),
        _set(e, "flag", e.n(0)),
        e.if_only(_is(e, "e"), _set(e, "flag", e.n(1))),
        e.if_only(_is(e, "E"), _set(e, "flag", e.n(1))),
        e.if_only(
            e.eq(_reg(e, "flag"), e.n(1)),
            e.seq(
                _push(e, _c(e)),
                _next(e),
                _set(e, "flag", e.n(0)),
                e.if_only(_is(e, "+"), _set(e, "flag", e.n(1))),
                e.if_only(_is(e, "-"), _set(e, "flag", e.n(1))),
                e.if_only(e.eq(_reg(e, "flag"), e.n(1)), e.seq(_push(e, _c(e)), _next(e))),
                _require_digit(e),
                _digits(e, "exp_digits"),
            ),
        ),
        _set(e, "state", e.n(AFTER_VALUE)),
        _yield(e, "number", _data_slice(e)),
    )


def _hex4(e, label, into):
    """Reads four hex digits into `into`."""
    return e.seq(
        _set(e, into, e.n(0)),
        _set(e, "i", e.n(0)),
        _loop(
            e,
            label,
            e.if_only(e.mb.operator_ge(_reg(e, "i"), e.n(4)), _break(e, label)),
            _next(e),
            _set(e, "h", e.n(-1)),
            _between(e, _c(e), ord("0"), ord("9"), _set(e, "h", e.mb.operator_sub(_c(e), e.n(ord("0"))))),
            _between(e, _c(e), ord("a"), ord("f"), _set(e, "h", e.mb.operator_sub(_c(e), e.n(ord("a") - 10)))),
            _between(e, _c(e), ord("A"), ord("F"), _set(e, "h", e.mb.operator_sub(_c(e), e.n(ord("A") - 10)))),
            e.if_only(e.mb.operator_lt(_reg(e, "h"), e.n(0)), _fail(e, ERR_ESCAPE)),
            _set(e, into, e.mb.operator_add(e.mb.operator_mul(_reg(e, into), e.n(16)), _reg(e, "h"))),
            _set(e, "i", e.mb.operator_add(_reg(e, "i"), e.n(1))),
        ),
    )


def _utf8(e):
    """Appends the utf-8 encoding of code point `cp` to the data."""
    cp = _reg(e, "cp")

    def part(shift, mask, add):
        return _push(
            e, e.mb.operator_add(e.n(add), e.mb.operator_mod(e.mb.operator_div(cp, e.n(1 << shift)), e.n(mask)))
        )

    return e.mb.if_of(
        [
            (e.mb.operator_lt(cp, e.n(0x80)), _push(e, cp)),
            (e.mb.operator_lt(cp, e.n(0x800)), e.seq(part(6, 0x20, 0xC0), part(0, 0x40, 0x80))),
            (
                e.mb.operator_lt(cp, e.n(0x10000)),
                e.seq(part(12, 0x10, 0xE0), part(6, 0x40, 0x80), part(0, 0x40, 0x80)),
            ),
        ],
        e.seq(part(18, 0x08, 0xF0), part(12, 0x40, 0x80), part(6, 0x40, 0x80), part(0, 0x40, 0x80)),
    )


def _escape(e):
    """An escape sequence; the lookahead is the byte after the backslash."""
    simple = []
    for ch, out in [
        ('"', '"'),
        ("\\", "\\"),
        ("/", "/"),
        ("b", "\b"),
        ("f", "\f"),
        ("n", "\n"),
        ("r", "\r"),
        ("t", "\t"),
    ]:
        simple.append((_is(e, ch), _push(e, e.n(ord(out)))))
    unicode = e.seq(
        _hex4(e, "hex_hi", "cp"),
        _between(e, _reg(e, "cp"), 0xDC00, 0xDFFF, _fail(e, ERR_ESCAPE)),
        _between(
            e,
            _reg(e, "cp"),
            0xD800,
            0xDBFF,
            e.seq(
                _next(e),
                e.if_only(_isnt(e, "\\"), _fail(e, ERR_ESCAPE)),
                _next(e),
                e.if_only(_isnt(e, "u"), _fail(e, ERR_ESCAPE)),
                _hex4(e, "hex_lo", "lo"),
                e.if_only(e.mb.operator_lt(_reg(e, "lo"), e.n(0xDC00)), _fail(e, ERR_ESCAPE)),
                e.if_only(e.mb.operator_gt(_reg(e, "lo"), e.n(0xDFFF)), _fail(e, ERR_ESCAPE)),
                _set(
                    e,
                    "cp",
                    e.mb.operator_add(
                        e.n(0x10000),
                        e.mb.operator_add(
                            e.mb.operator_mul(e.mb.operator_sub(_reg(e, "cp"), e.n(0xD800)), e.n(0x400)),
                            e.mb.operator_sub(_reg(e, "lo"), e.n(0xDC00)),
                        ),
                    ),
                ),
            ),
        ),
        _utf8(e),
    )
    return e.mb.if_of(simple + [(_is(e, "u"), unicode)], _fail(e, ERR_ESCAPE))


def _string(e):
    """A string whose opening quote is the lookahead; `is_key` says whether it is an object key."""
    return e.seq(
        _vec(e, "data", "clear", e.tup()),
        _loop(
            e,
            "str",
            _next(e),
            e.if_only(e.mb.operator_lt(_c(e), e.n(0)), _fail(e)),
            e.if_only(_is(e, '"'), _break(e, "str")),
            e.mb.if_of(
                [
                    (_is(e, "\\"), e.seq(_next(e), _escape(e))),
                    (e.mb.operator_lt(_c(e), e.n(0x20)), _fail(e)),
                ],
                _push(e, _c(e)),
            ),
        ),
        _next(e),
        e.if_else(
            e.eq(_reg(e, "is_key"), e.n(1)),
            e.seq(
                _skip_ws(e),
                e.if_only(_isnt(e, ":"), _fail(e)),
                _next(e),
                _set(e, "state", e.n(WANT_VALUE)),
                _yield(e, "key", _data_slice(e)),
            ),
            e.seq(_set(e, "state", e.n(AFTER_VALUE)), _yield(e, "string", _data_slice(e))),
        ),
    )


def _open(e, kind, state, begin):
    """Enters an object (kind 1) or array (kind 0) whose opening bracket is the lookahead."""
    return e.seq(
        _vec(e, "stack", "push", e.n(kind)),
        _next(e),
        _set(e, "state", e.n(state)),
        _set(e, "fresh", e.n(1)),
        _yield(e, begin),
    )


def _close(e, end):
    """Leaves the innermost container, whose closing bracket is the lookahead."""
    return e.seq(_stack_pop(e), _next(e), _set(e, "state", e.n(AFTER_VALUE)), _yield(e, end))


def _value(e):
    """A value whose first byte is the lookahead (a key when the state wants one), or the end of a container just
    opened."""
    return e.seq(
        _set(e, "is_key", e.mb.operator_div(_reg(e, "state"), e.n(WANT_KEY))),
        e.if_only(
            e.eq(_reg(e, "fresh"), e.n(1)),
            e.seq(
                _set(e, "fresh", e.n(0)),
                e.if_only(e.eq(_reg(e, "is_key"), e.n(1)), e.if_only(_is(e, "}"), _close(e, "object_end"))),
                e.if_only(e.eq(_reg(e, "is_key"), e.n(0)), e.if_only(_is(e, "]"), _close(e, "array_end"))),
            ),
        ),
        e.if_only(e.eq(_reg(e, "is_key"), e.n(1)), e.if_only(_isnt(e, '"'), _fail(e))),
        e.mb.if_of(
            [
                (_is(e, '"'), _string(e)),
                (_is(e, "{"), _open(e, 1, WANT_KEY, "object_begin")),
                (_is(e, "["), _open(e, 0, WANT_VALUE, "array_begin")),
                (_is(e, "t"), _expect_literal(e, "true", _yield(e, "bool", e.n(1)))),
                (_is(e, "f"), _expect_literal(e, "false", _yield(e, "bool", e.n(0)))),
                (_is(e, "n"), _expect_literal(e, "null", _yield(e, "null"))),
                (_is(e, "-"), _number(e)),
            ],
            e.seq(_require_digit(e), _number(e)),
        ),
    )


def _after_value(e):
    """A comma (then the next value), the end of the enclosing container, or the end of the document."""
    return e.seq(
        e.if_only(
            e.eq(_stack_len(e), e.n(0)),
            e.seq(
                e.if_only(e.mb.operator_ge(_c(e), e.n(0)), _fail(e, ERR_TRAILING)),
                _set(e, "state", e.n(DONE)),
                _yield(e, "end"),
            ),
        ),
        e.mb.if_of(
            [
                (
                    _is(e, ","),
                    e.seq(
                        _next(e),
                        _set(e, "state", e.mb.operator_mul(_stack_top(e), e.n(WANT_KEY))),
                    ),
                ),
                (
                    _is(e, "}"),
                    e.seq(e.if_only(e.mb.operator_ne(_stack_top(e), e.n(1)), _fail(e)), _close(e, "object_end")),
                ),
                (
                    _is(e, "]"),
                    e.seq(e.if_only(e.mb.operator_ne(_stack_top(e), e.n(0)), _fail(e)), _close(e, "array_end")),
                ),
            ],
            _fail(e),
        ),
    )


def _next_body(e):
    return e.mb.labeled(
        "next",
        e.seq(
            e.if_only(e.eq(_reg(e, "state"), e.n(FAILED)), _yield(e, "error", _reg(e, "err"))),
            e.if_only(e.eq(_reg(e, "state"), e.n(DONE)), _yield(e, "end")),
            e.if_only(e.eq(_c(e), e.n(UNREAD)), _next(e)),
            _loop(
                e,
                "main",
                _skip_ws(e),
                e.if_else(e.eq(_reg(e, "state"), e.n(AFTER_VALUE)), _after_value(e), _value(e)),
            ),
        ),
    )


# --- serializer ---


def _wf(e, name):
    """A field of the writer's state."""
    return e.fld(_op(e, "w"), name)


def _w(e, byte):
    return _stmt(e, e.call(_op(e, "write"), e.tup(_wf(e, "ctx"), e.n(ord(byte)))))


def _wv(e, value):
    """Writes `value`, an int."""
    return _stmt(e, e.call(_op(e, "write"), e.tup(_wf(e, "ctx"), value)))


def _w_text(e, text):
    return e.seq(*[_w(e, ch) for ch in text])


def _sep(e):
    """A comma when a value precedes the one being written."""
    return e.if_only(e.eq(_wf(e, "pending"), e.n(1)), _w(e, ","))


def _pending(e, value):
    return e.mb.set(_wf(e, "pending"), e.n(value))


def _write_literal(e, text):
    return e.seq(_sep(e), _w_text(e, text), _pending(e, 1))


def _write_bool(e):
    return e.seq(
        _sep(e),
        e.if_else(e.eq(_op(e, "value"), e.n(0)), _w_text(e, "false"), _w_text(e, "true")),
        _pending(e, 1),
    )


def _int(e, value):
    """A number literal as the target's int."""
    return e.mb.as_(e.n(value), _op(e, "int"))


def _write_int(e):
    """The decimal digits of `value`, most significant first, found by a power of ten below it."""
    return e.seq(
        _sep(e),
        e.let("v", _op(e, "value")),
        e.if_only(
            e.mb.operator_lt(e.v("v"), e.n(0)),
            e.seq(_w(e, "-"), e.mb.set(e.v("v"), e.mb.operator_sub(e.n(0), e.v("v")))),
        ),
        e.let("p", _int(e, 1)),
        _loop(
            e,
            "scale",
            e.if_only(e.mb.operator_gt(e.v("p"), e.mb.operator_div(e.v("v"), e.n(10))), _break(e, "scale")),
            e.mb.set(e.v("p"), e.mb.operator_mul(e.v("p"), e.n(10))),
        ),
        _loop(
            e,
            "digits",
            e.if_only(e.eq(e.v("p"), e.n(0)), _break(e, "digits")),
            _wv(e, e.mb.operator_add(e.n(ord("0")), e.mb.operator_mod(e.mb.operator_div(e.v("v"), e.v("p")), e.n(10)))),
            e.mb.set(e.v("p"), e.mb.operator_div(e.v("p"), e.n(10))),
        ),
        _pending(e, 1),
    )


def _hex_digit(e, value):
    return e.if_else(
        e.mb.operator_lt(value, e.n(10)),
        e.mb.operator_add(value, e.n(ord("0"))),
        e.mb.operator_add(value, e.n(ord("a") - 10)),
    )


def _escaped_byte(e, b):
    simple = []
    for ch, out in [
        ('"', '\\"'),
        ("\\", "\\\\"),
        ("\n", "\\n"),
        ("\r", "\\r"),
        ("\t", "\\t"),
        ("\b", "\\b"),
        ("\f", "\\f"),
    ]:
        simple.append((e.eq(b, e.n(ord(ch))), _w_text(e, out)))
    control = e.seq(
        _w_text(e, "\\u00"),
        _wv(e, _hex_digit(e, e.mb.operator_div(b, e.n(16)))),
        _wv(e, _hex_digit(e, e.mb.operator_mod(b, e.n(16)))),
    )
    return e.mb.if_of(simple + [(e.mb.operator_lt(b, e.n(0x20)), control)], _wv(e, b))


def _each_byte(e, label, then):
    """`then` for each byte `b` of the slice `s`."""
    return e.seq(
        e.let("n", e.call(e.fld(_op(e, "s"), "len"), e.tup())),
        e.let("i", _int(e, 0)),
        _loop(
            e,
            label,
            e.if_only(e.mb.operator_ge(e.v("i"), e.v("n")), _break(e, label)),
            e.let("b", e.call(e.fld(_op(e, "s"), "at"), e.v("i"))),
            then,
            e.mb.set(e.v("i"), e.mb.operator_add(e.v("i"), e.n(1))),
        ),
    )


def _write_number(e):
    return e.seq(_sep(e), _each_byte(e, "raw", _wv(e, e.v("b"))), _pending(e, 1))


def _write_string(e, is_key):
    return e.seq(
        _sep(e),
        _w(e, '"'),
        _each_byte(e, "esc", _escaped_byte(e, e.v("b"))),
        _w(e, '"'),
        e.seq(_w(e, ":"), _pending(e, 0)) if is_key else _pending(e, 1),
    )


def module(e):
    top = []
    top.append(e.let("d", e.define()))
    top.append(e.option_type_let())
    event_fields = []
    take_fields(e, event_fields, e.v("op_event"), EVENTS, "ev_")
    _const_func(e, top, "next", NEXT_OPS, _next_body(e), extra=event_fields)
    writers = [
        ("write_null", WRITE_OPS, _write_literal(e, "null")),
        ("write_bool", WRITE_OPS + ["value"], _write_bool(e)),
        ("write_int", WRITE_OPS + ["int", "value"], _write_int(e)),
        ("write_number", WRITE_OPS + ["int", "s"], _write_number(e)),
        ("write_string", WRITE_OPS + ["int", "s"], _write_string(e, False)),
        ("write_key", WRITE_OPS + ["int", "s"], _write_string(e, True)),
        ("write_object_begin", WRITE_OPS, e.seq(_sep(e), _w(e, "{"), _pending(e, 0))),
        ("write_object_end", WRITE_OPS, e.seq(_w(e, "}"), _pending(e, 1))),
        ("write_array_begin", WRITE_OPS, e.seq(_sep(e), _w(e, "["), _pending(e, 0))),
        ("write_array_end", WRITE_OPS, e.seq(_w(e, "]"), _pending(e, 1))),
    ]
    for name, ops, gen in writers:
        _const_func(e, top, name, ops, gen)
    top.append(e.finish(e.v("d")))
    exports = [e.p("next", e.fld(e.v("next_b"), "func"))]
    for name, _, _ in writers:
        exports.append(e.p(name, e.fld(e.v(name + "_b"), "func")))
    top.append(e.ret(e.rec(*exports)))
    return top
