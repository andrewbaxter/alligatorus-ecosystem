"""editor-json.atz: JSON text for the editor components' documents (wat target; dependencies; editor-types.atz's
`str` and `bytes`).

Writing appends to a `bytes` buffer (borrowed): `jw_num(a, x)` (the shortest text that reads back as the f64 `x`,
which must be finite), `jw_int(a, n)` (an i32 in decimal), `jw_str(a, s)` (the `str` `s`, quoted and escaped),
`jw_text(a, s)` (the bytes of `s` as they are) and `jw_byte(a, b)` (one byte) for punctuation.

Reading scans well-formed JSON text without building anything: the text is a `str` `s` and a position `q` an offset
into it (`s.len` is the end). `jr_ws(s, q)` skips whitespace; `jr_skip(s, q)` is the position past the value at
`q`; `jr_first(s, q)` is the first element of the array, or the first key of the object, at `q` (-1 when empty) and
`jr_next(s, q)` the next one after the element or key at `q` (-1 after the last); `jr_value(s, q)` is the value of
the object key at `q`; `jr_field(s, q, key)` is the value of the field named `key` in the object at `q` (-1 when
missing); `jr_key_is(s, q, key)` is whether the key at `q` is that name; `jr_num(s, q)` reads the number at `q`
(f64); `jr_int(s, q)` reads an integer at `q`, bare or quoted (an object key); `jr_null(s, q)` is whether the value
at `q` is `null`; `jr_text(s, q)` is the value at `q` as a `str` (its bytes up to `jr_skip`).
"""

from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_types
from ..wasm.kit import Kit, library

FILE = "editor-json.atz"

TYPES = ["t_pu8", "str_t", "str_of", "bytes_t", "bytes_own", "bytes_raw", "bytes_new"]
EXPORTS = [
    "jw_num",
    "jw_int",
    "jw_str",
    "jw_text",
    "jw_byte",
    "jr_ws",
    "jr_skip",
    "jr_first",
    "jr_next",
    "jr_value",
    "jr_field",
    "jr_key_is",
    "jr_num",
    "jr_int",
    "jr_null",
    "jr_text",
    "jr_str",
]


def module(e):
    k = Kit(e)
    x = []
    k.bind(x)
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    for n in TYPES:
        x.append(e.let(n, e.fld(e.v("types"), n)))
    for name in ["num_format", "num_parse", "string_len", "string_copy"]:
        x.append(
            e.let(
                "h_" + name,
                e.call(e.fld(e.v("webidl"), "intrinsic"), e.rec(p("iface", e.s("")), p("member", e.s(name)))),
            )
        )
    v = e.v

    def byte(q):
        """The byte of `s` at `q` (an i32)."""
        return e.mb.as_(k.m(v("s"), "at", q), k.lo("t_i32"))

    def is_(q, c):
        return k.eq(byte(q), e.n(ord(c)))

    def end():
        return e.fld(v("s"), "len")

    def push(a, b):
        """Appends the byte `b` (an i32 expression) to the buffer `a`."""
        return k.m(a, "push", k.m(k.i32(b), "wrap", k.lo("t_u8")))

    def push_text(a, s):
        """Appends the `str` `s` to `a` (`s` is bound first: the loop counter shadows the caller's names)."""
        return e.seq(
            e.let("__s", s),
            k.for_(
                "__i",
                0,
                e.fld(v("__s"), "len"),
                "copy",
                push(a, e.mb.as_(k.m(v("__s"), "at", v("__i")), k.lo("t_i32"))),
            ),
        )

    k.dep(
        x,
        "jw_num",
        ["a", "x"],
        ["bytes_raw", "t_f64"],
        "t_void",
        e.seq(
            e.let("h", k.call("h_num_format", v("x"))),
            e.let("n", k.m(k.call("h_string_len", v("h")), "wrap", k.lo("t_i32"))),
            e.let("at", e.fld(v("a"), "len")),
            k.for_("i", 0, v("n"), "grow", push(v("a"), e.n(0))),
            k.call(
                "h_string_copy",
                v("h"),
                k.ptr_of(k.add(k.addr(e.fld(v("a"), "data")), v("at")), "t_pu8"),
                k.m(v("n"), "wrap", k.lo("t_u32")),
            ),
        ),
    )
    # Digits are produced backwards into a scratch block, then appended.
    k.block(x, "jw_digits", 16)
    k.dep(
        x,
        "jw_int",
        ["a", "n"],
        ["bytes_raw", "t_i32"],
        "t_void",
        e.seq(
            k.if_(k.lt(v("n"), e.n(0)), push(v("a"), e.n(ord("-")))),
            # The magnitude as u32 covers the most negative i32.
            e.let("m", k.m(k.ifelse(k.lt(v("n"), e.n(0)), k.neg(v("n")), v("n")), "wrap", k.lo("t_u32"))),
            e.let("buf", k.block_addr("jw_digits")),
            e.let("i", k.i32(16)),
            k.loop(
                "digits",
                e.mb.set(v("i"), k.sub(v("i"), e.n(1))),
                k.set(
                    k.at(k.add(v("buf"), v("i")), 0, "t_pu8"),
                    k.m(k.add(k.rem(v("m"), e.n(10)), e.n(ord("0"))), "wrap", k.lo("t_u8")),
                ),
                e.mb.set(v("m"), k.div(v("m"), e.n(10))),
                k.if_(k.eq(v("m"), e.n(0)), k.brk("digits")),
            ),
            push_text(v("a"), k.str_of(k.ptr_of(k.add(v("buf"), v("i")), "t_pu8"), k.sub(e.n(16), v("i")))),
        ),
    )
    k.text(x, "jw_hex", "0123456789abcdef")
    k.text(x, "jw_u00", "\\u00")

    def hexdigit(n):
        return e.mb.as_(k.at(k.add(k.addr(k.cstr("jw_hex")), n), 0, "t_pu8"), k.lo("t_i32"))

    k.dep(
        x,
        "jw_str",
        ["a", "s"],
        ["bytes_raw", "str_t"],
        "t_void",
        e.seq(
            push(v("a"), e.n(ord('"'))),
            k.for_(
                "i",
                0,
                end(),
                "chars",
                e.let("c", byte(v("i"))),
                k.if_(
                    k.or_(k.eq(v("c"), e.n(ord('"'))), k.eq(v("c"), e.n(ord("\\")))),
                    push(v("a"), e.n(ord("\\"))),
                    push(v("a"), v("c")),
                    k.cont("chars"),
                ),
                k.if_(
                    k.lt(v("c"), e.n(32)),
                    push_text(v("a"), k.sconst("jw_u00", "\\u00")),
                    push(v("a"), hexdigit(k.shr(v("c"), e.n(4)))),
                    push(v("a"), hexdigit(k.band(v("c"), e.n(15)))),
                    k.cont("chars"),
                ),
                push(v("a"), v("c")),
            ),
            push(v("a"), e.n(ord('"'))),
        ),
    )
    k.dep(x, "jw_text", ["a", "s"], ["bytes_raw", "str_t"], "t_void", push_text(v("a"), v("s")))
    k.dep(x, "jw_byte", ["a", "b"], ["bytes_raw", "t_i32"], "t_void", push(v("a"), v("b")))
    # Reading.
    k.dep(
        x,
        "jr_ws",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            k.loop(
                "ws",
                k.if_(k.ge(v("q"), end()), k.brk("ws")),
                e.let("c", byte(v("q"))),
                k.if_(
                    k.not_(
                        k.or_(
                            k.or_(k.eq(v("c"), e.n(32)), k.eq(v("c"), e.n(9))),
                            k.or_(k.eq(v("c"), e.n(10)), k.eq(v("c"), e.n(13))),
                        )
                    ),
                    k.brk("ws"),
                ),
                e.mb.set(v("q"), k.add(v("q"), e.n(1))),
            ),
            e.ret(v("q")),
        ),
    )

    def ws(q):
        return k.dcall("jr_ws", v("s"), q)

    def skip_str(q):
        return k.dcall("jr_skip_str", v("s"), q)

    # The position past the string whose opening quote is at `q`.
    k.dep(
        x,
        "jr_skip_str",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            e.mb.set(v("q"), k.add(v("q"), e.n(1))),
            k.loop(
                "s",
                k.if_(k.ge(v("q"), end()), k.ret(v("q"))),
                e.let("c", byte(v("q"))),
                k.if_(k.eq(v("c"), e.n(ord("\\"))), e.mb.set(v("q"), k.add(v("q"), e.n(2))), k.cont("s")),
                e.mb.set(v("q"), k.add(v("q"), e.n(1))),
                k.if_(k.eq(v("c"), e.n(ord('"'))), k.ret(v("q"))),
            ),
            e.ret(v("q")),
        ),
    )
    k.dep(
        x,
        "jr_skip",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            e.mb.set(v("q"), ws(v("q"))),
            k.if_(k.ge(v("q"), end()), k.ret(v("q"))),
            e.let("c", byte(v("q"))),
            k.if_(k.eq(v("c"), e.n(ord('"'))), k.ret(skip_str(v("q")))),
            k.if_(
                k.or_(k.eq(v("c"), e.n(ord("{"))), k.eq(v("c"), e.n(ord("[")))),
                e.let("depth", k.i32(0)),
                k.loop(
                    "nest",
                    k.if_(k.ge(v("q"), end()), k.ret(v("q"))),
                    e.let("d", byte(v("q"))),
                    k.if_(k.eq(v("d"), e.n(ord('"'))), e.mb.set(v("q"), skip_str(v("q"))), k.cont("nest")),
                    k.if_(
                        k.or_(k.eq(v("d"), e.n(ord("{"))), k.eq(v("d"), e.n(ord("[")))),
                        e.mb.set(v("depth"), k.add(v("depth"), e.n(1))),
                    ),
                    k.if_(
                        k.or_(k.eq(v("d"), e.n(ord("}"))), k.eq(v("d"), e.n(ord("]")))),
                        e.mb.set(v("depth"), k.sub(v("depth"), e.n(1))),
                    ),
                    e.mb.set(v("q"), k.add(v("q"), e.n(1))),
                    k.if_(k.eq(v("depth"), e.n(0)), k.ret(v("q"))),
                ),
            ),
            # A number, true, false or null: up to a delimiter.
            k.loop(
                "atom",
                k.if_(k.ge(v("q"), end()), k.brk("atom")),
                e.let("d", byte(v("q"))),
                k.if_(
                    k.or_(
                        k.or_(k.eq(v("d"), e.n(ord(","))), k.eq(v("d"), e.n(ord("}")))),
                        k.or_(k.eq(v("d"), e.n(ord("]"))), k.le(v("d"), e.n(32))),
                    ),
                    k.brk("atom"),
                ),
                e.mb.set(v("q"), k.add(v("q"), e.n(1))),
            ),
            e.ret(v("q")),
        ),
    )
    k.dep(
        x,
        "jr_first",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            e.let("r", ws(k.add(ws(v("q")), e.n(1)))),
            k.if_(k.ge(v("r"), end()), k.ret(k.i32(-1))),
            k.if_(k.or_(is_(v("r"), "}"), is_(v("r"), "]")), k.ret(k.i32(-1))),
            e.ret(v("r")),
        ),
    )
    k.dep(
        x,
        "jr_value",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        # past the key, the whitespace, the colon and the whitespace
        e.ret(ws(k.add(ws(skip_str(ws(v("q")))), e.n(1)))),
    )
    k.dep(
        x,
        "jr_next",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            e.let("r", ws(v("q"))),
            # an object key: past its value too
            k.if_(
                is_(v("r"), '"'),
                e.let("after", ws(skip_str(v("r")))),
                k.if_(
                    k.and_(k.lt(v("after"), end()), is_(v("after"), ":")),
                    e.mb.set(v("r"), k.dcall("jr_value", v("s"), v("r"))),
                ),
            ),
            e.mb.set(v("r"), ws(k.dcall("jr_skip", v("s"), v("r")))),
            k.if_(k.ge(v("r"), end()), k.ret(k.i32(-1))),
            k.if_(k.not_(is_(v("r"), ",")), k.ret(k.i32(-1))),
            e.ret(ws(k.add(v("r"), e.n(1)))),
        ),
    )
    k.dep(
        x,
        "jr_key_is",
        ["s", "q", "key"],
        ["str_t", "t_i32", "str_t"],
        "t_i32",
        e.seq(
            e.let("b", k.add(ws(v("q")), e.n(1))),
            e.let("close", k.sub(skip_str(k.sub(v("b"), e.n(1))), e.n(1))),
            k.if_(k.ne(k.sub(v("close"), v("b")), e.fld(v("key"), "len")), k.ret(k.i32(0))),
            k.for_(
                "i",
                0,
                e.fld(v("key"), "len"),
                "cmp",
                k.if_(
                    k.ne(byte(k.add(v("b"), v("i"))), e.mb.as_(k.m(v("key"), "at", v("i")), k.lo("t_i32"))),
                    k.ret(k.i32(0)),
                ),
            ),
            e.ret(k.i32(1)),
        ),
    )
    k.dep(
        x,
        "jr_field",
        ["s", "q", "key"],
        ["str_t", "t_i32", "str_t"],
        "t_i32",
        e.seq(
            e.let("r", k.dcall("jr_first", v("s"), v("q"))),
            k.loop(
                "keys",
                k.if_(k.lt(v("r"), e.n(0)), k.ret(k.i32(-1))),
                k.if_(
                    k.ne(k.dcall("jr_key_is", v("s"), v("r"), v("key")), e.n(0)),
                    k.ret(k.dcall("jr_value", v("s"), v("r"))),
                ),
                e.mb.set(v("r"), k.dcall("jr_next", v("s"), v("r"))),
            ),
            e.ret(k.i32(-1)),
        ),
    )
    k.dep(
        x,
        "jr_num",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_f64",
        e.seq(
            e.let("b", ws(v("q"))),
            e.let("t", k.dcall("jr_skip", v("s"), v("b"))),
            e.ret(
                k.call(
                    "h_num_parse",
                    k.ptr_of(k.add(k.addr(e.fld(v("s"), "data")), v("b")), "t_pu8"),
                    k.m(k.sub(v("t"), v("b")), "wrap", k.lo("t_u32")),
                )
            ),
        ),
    )
    k.dep(
        x,
        "jr_int",
        ["s", "q"],
        ["str_t", "t_i32"],
        "t_i32",
        e.seq(
            e.let("r", ws(v("q"))),
            k.if_(is_(v("r"), '"'), e.mb.set(v("r"), k.add(v("r"), e.n(1)))),
            e.let("negative", k.i32(0)),
            k.if_(is_(v("r"), "-"), e.mb.set(v("negative"), e.n(1)), e.mb.set(v("r"), k.add(v("r"), e.n(1)))),
            e.let("n", k.i32(0)),
            k.loop(
                "digits",
                k.if_(k.ge(v("r"), end()), k.brk("digits")),
                e.let("c", byte(v("r"))),
                k.if_(k.or_(k.lt(v("c"), e.n(ord("0"))), k.gt(v("c"), e.n(ord("9")))), k.brk("digits")),
                e.mb.set(v("n"), k.add(k.mul(v("n"), e.n(10)), k.sub(v("c"), e.n(ord("0"))))),
                e.mb.set(v("r"), k.add(v("r"), e.n(1))),
            ),
            e.ret(k.ifelse(k.ne(v("negative"), e.n(0)), k.neg(v("n")), v("n"))),
        ),
    )
    k.dep(x, "jr_null", ["s", "q"], ["str_t", "t_i32"], "t_i32", e.ret(e.mb.as_(is_(v("q"), "n"), k.lo("t_i32"))))
    k.dep(
        x,
        "jr_text",
        ["s", "q"],
        ["str_t", "t_i32"],
        "str_t",
        e.seq(e.let("b", ws(v("q"))), e.ret(k.m(v("s"), "sub", e.tup(v("b"), k.dcall("jr_skip", v("s"), v("b")))))),
    )

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def setv(name, val):
        return e.mb.set(v(name), val)

    def hexval(c):
        """The value of a hex digit (an i32 expression: '0'-'9', 'A'-'F' or 'a'-'f')."""
        return k.ifelse(
            k.le(c, e.n(ord("9"))),
            k.sub(c, e.n(48)),
            k.ifelse(k.le(c, e.n(ord("F"))), k.sub(c, e.n(55)), k.sub(c, e.n(87))),
        )

    def hex4(at):
        """The code of four hex digits at `at`."""
        return k.bor(
            k.bor(k.shl(hexval(byte(at)), e.n(12)), k.shl(hexval(byte(k.add(at, e.n(1)))), e.n(8))),
            k.bor(k.shl(hexval(byte(k.add(at, e.n(2)))), e.n(4)), hexval(byte(k.add(at, e.n(3))))),
        )

    def utf8(a, cp):
        """The code point `cp` (an i32 binding) as UTF-8 into `a`."""

        def cont(sh):
            return push(a, k.bor(e.n(0x80), k.band(k.shr(cp, e.n(sh)), e.n(63))))

        return k.ifelse(
            k.lt(cp, e.n(0x80)),
            push(a, cp),
            k.ifelse(
                k.lt(cp, e.n(0x800)),
                e.seq(push(a, k.bor(e.n(0xC0), k.shr(cp, e.n(6)))), cont(0)),
                k.ifelse(
                    k.lt(cp, e.n(0x10000)),
                    e.seq(push(a, k.bor(e.n(0xE0), k.shr(cp, e.n(12)))), cont(6), cont(0)),
                    e.seq(push(a, k.bor(e.n(0xF0), k.shr(cp, e.n(18)))), cont(12), cont(6), cont(0)),
                ),
            ),
        )

    def unescaped(c):
        """The byte an escape letter `c` (an i32 binding) stands for (`"`, `\\` and `/` stand for themselves)."""
        out = c
        for ch, b in [("b", 8), ("f", 12), ("n", 10), ("r", 13), ("t", 9)]:
            out = k.ifelse(k.eq(c, e.n(ord(ch))), k.i32(b), out)
        return out

    # The JSON string at `q` (after whitespace) unescaped into the buffer `out`; the position after its closing
    # quote. Anything but a string traps.
    k.dep(
        x,
        "jr_str",
        ["s", "q", "out"],
        ["str_t", "t_i32", "bytes_raw"],
        "t_i32",
        e.seq(
            e.let("i", ws(v("q"))),
            k.if_(k.not_(is_(v("i"), '"')), trap()),
            setv("i", k.add(v("i"), e.n(1))),
            k.loop(
                "chars",
                k.if_(k.ge(v("i"), end()), trap()),
                e.let("c", byte(v("i"))),
                k.if_(k.eq(v("c"), e.n(ord('"'))), k.brk("chars")),
                k.ifelse(
                    k.ne(v("c"), e.n(ord("\\"))),
                    e.seq(push(v("out"), v("c")), setv("i", k.add(v("i"), e.n(1)))),
                    e.seq(
                        e.let("x", byte(k.add(v("i"), e.n(1)))),
                        setv("i", k.add(v("i"), e.n(2))),
                        k.ifelse(
                            k.eq(v("x"), e.n(ord("u"))),
                            e.seq(
                                e.let("cp", hex4(v("i"))),
                                setv("i", k.add(v("i"), e.n(4))),
                                # a high surrogate pairs with the low one escaped right after it
                                k.if_(
                                    k.and_(k.ge(v("cp"), e.n(0xD800)), k.le(v("cp"), e.n(0xDBFF))),
                                    k.if_(k.not_(k.and_(is_(v("i"), "\\"), is_(k.add(v("i"), e.n(1)), "u"))), trap()),
                                    e.let("lo", hex4(k.add(v("i"), e.n(2)))),
                                    setv(
                                        "cp",
                                        k.add(
                                            e.n(0x10000),
                                            k.add(
                                                k.shl(k.sub(v("cp"), e.n(0xD800)), e.n(10)), k.sub(v("lo"), e.n(0xDC00))
                                            ),
                                        ),
                                    ),
                                    setv("i", k.add(v("i"), e.n(6))),
                                ),
                                utf8(v("out"), v("cp")),
                            ),
                            push(v("out"), unescaped(v("x"))),
                        ),
                    ),
                ),
            ),
            e.ret(k.add(v("i"), e.n(1))),
        ),
    )
    return library(e, x, [], EXPORTS)
