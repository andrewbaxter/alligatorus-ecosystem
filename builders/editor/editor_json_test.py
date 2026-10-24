"""editor-json-test.atz: a WASI app checking editor-json.atz's integer and string writing and its scanning reader
(the number text conversions need the browser's intrinsics and are checked in the editor harness); its exit status
it prints the index of the first failed check (exit status 1)."""

from . import wasi_test, editor_json

DOC = ' { "a" : 1, "list": [1, [2, 3], {"x": "y\\"z"}], "-7": null , "s": "q,}"} '
UNESCAPED = 'a"b\\c\n/\u00e9\U0001f600'
ESCAPED = ' "a\\"b\\\\c\\n\\/\\u00e9\\ud83d\\ude00"'


def module(e):
    def checks(k):
        v = e.v

        def J(f, *args):
            return k.lib("json", f, *args)

        def text(t):
            """A constant text as a `str`."""
            return k.str_of(
                k.ptr_of(k.addr(e.lower(e.call_m(e.v("m"), "cstr", e.s(t)))), "t_pu8"), k.i32(len(t.encode()))
            )

        def byte(s, q):
            return e.mb.as_(k.m(s, "at", q), k.lo("t_i32"))

        def same(buf, t):
            """Whether the buffer holds exactly the UTF-8 of `t` (one check per byte, plus the length)."""
            b = t.encode()
            out = [k.check(k.eq(e.fld(buf, "len"), e.n(len(b))))]
            for i, c in enumerate(b):
                out.append(k.check(k.eq(byte(buf, e.n(i)), e.n(c))))
            return out

        return [
            e.let("w", k.call("bytes_new", e.tup())),
            J("jw_int", v("w"), k.i32(-1204)),
            J("jw_byte", v("w"), e.n(ord(","))),
            J("jw_int", v("w"), k.i32(0)),
            J("jw_byte", v("w"), e.n(ord(","))),
            J("jw_str", v("w"), text('a"b\\c\n')),
            *same(v("w"), '-1204,0,"a\\"b\\\\c\\u000a"'),
            e.let("d", text(DOC)),
            # the field "a" is the 1 after its colon
            e.let("fa", J("jr_field", v("d"), e.n(0), text("a"))),
            k.check(k.eq(J("jr_int", v("d"), v("fa")), e.n(1))),
            e.let("fl", J("jr_field", v("d"), e.n(0), text("list"))),
            k.check(k.eq(byte(v("d"), v("fl")), e.n(ord("[")))),
            e.let("e0", J("jr_first", v("d"), v("fl"))),
            k.check(k.eq(J("jr_int", v("d"), v("e0")), e.n(1))),
            e.let("e1", J("jr_next", v("d"), v("e0"))),
            k.check(k.eq(J("jr_int", v("d"), J("jr_first", v("d"), v("e1"))), e.n(2))),
            e.let("e2", J("jr_next", v("d"), v("e1"))),
            k.check(k.eq(byte(v("d"), J("jr_field", v("d"), v("e2"), text("x"))), e.n(ord('"')))),
            k.check(k.eq(J("jr_next", v("d"), v("e2")), e.n(-1))),
            # the keys in order: a, list, -7 (read as an integer), s
            e.let("k0", J("jr_first", v("d"), e.n(0))),
            k.check(k.ne(J("jr_key_is", v("d"), v("k0"), text("a")), e.n(0))),
            e.let("k1", J("jr_next", v("d"), v("k0"))),
            k.check(k.ne(J("jr_key_is", v("d"), v("k1"), text("list")), e.n(0))),
            e.let("k2", J("jr_next", v("d"), v("k1"))),
            k.check(k.eq(J("jr_int", v("d"), v("k2")), e.n(-7))),
            k.check(k.ne(J("jr_null", v("d"), J("jr_value", v("d"), v("k2"))), e.n(0))),
            e.let("k3", J("jr_next", v("d"), v("k2"))),
            e.let("sv", J("jr_value", v("d"), v("k3"))),
            k.check(k.eq(e.fld(J("jr_text", v("d"), v("sv")), "len"), e.n(5))),
            k.check(k.eq(J("jr_next", v("d"), v("k3")), e.n(-1))),
            k.check(k.eq(J("jr_field", v("d"), e.n(0), text("zz")), e.n(-1))),
            # a string unescaped: the escapes, a two-byte and a four-byte (surrogate pair) code point
            e.let("es", text(ESCAPED)),
            e.let("u", k.call("bytes_new", e.tup())),
            k.check(k.eq(J("jr_str", v("es"), e.n(0), v("u")), e.n(len(ESCAPED.encode())))),
            *same(v("u"), UNESCAPED),
        ]

    return wasi_test.module(e, [("json", editor_json.FILE)], checks)
