"""editor-state-test.atz: a WASI app checking editor-state.atz: commits, the serialized document and undo levels,
applying a level back, loading a document with a section no component registered, and the changed lists; its exit
status is the index of the first failed check."""

from ..eco_mb import p
from . import wasi_test, editor_json, editor_state


def module(e):
    def checks(k):
        v = e.v

        def S(f, *args):
            return k.lib("state", f, *args)

        def J(f, *args):
            return k.lib("json", f, *args)

        def text(t):
            return k.str_of(
                k.ptr_of(k.addr(e.lower(e.call_m(e.v("m"), "cstr", e.s(t)))), "t_pu8"), k.i32(len(t.encode()))
            )

        def buf(t):
            """A new owned buffer of the UTF-8 of `t` (an expression: a block yielding the owned buffer, moved out)."""
            return e.mb.labeled(
                "b",
                e.seq(
                    e.let("__a", k.call("bytes_new", e.tup())),
                    J("jw_text", v("__a"), text(t)),
                    e.mb.return_to("b", k.m(v("__a"), "move", e.tup())),
                ),
            )

        def same(s, t):
            """Whether the `str` `s` is exactly the UTF-8 of `t` (one check per byte, plus the length)."""
            b = t.encode()
            out = [k.check(k.eq(e.fld(s, "len"), e.n(len(b))))]
            for i, c in enumerate(b):
                out.append(k.check(k.eq(e.mb.as_(k.m(s, "at", e.n(i)), k.lo("t_i32")), e.n(c))))
            return out

        def doc_is(t):
            return same(S("st_doc", v("st")), t)

        def level_is(t):
            return same(S("st_level_text", v("st")), t)

        def has(opt):
            return e.match_of(opt, "o", None, p("some", k.i32(1)), p("none", k.i32(0)))

        def put(sec, id_, t):
            return e.seq(e.let("__t", buf(t)), S("st_put", v("st"), v(sec), e.n(id_), v("__t")))

        return [
            e.let("st", S("st_new")),
            e.let("a", S("st_section", v("st"), text("a"))),
            e.let("b", S("st_section", v("st"), text("bb"))),
            put("a", 3, "[2]"),
            put("a", 1, '{"x":1}'),
            put("b", 2, '"s"'),
            k.check(k.eq(S("st_commit", v("st")), e.n(1))),
            *doc_is('{"a":{"1":{"x":1},"3":[2]},"bb":{"2":"s"}}'),
            *level_is('[["a",3,null,[2]],["a",1,null,{"x":1}],["bb",2,null,"s"]]'),
            k.check(k.eq(S("st_changed_count", v("st"), v("a")), e.n(2))),
            k.check(k.eq(S("st_changed_at", v("st"), v("a"), e.n(0)), e.n(3))),
            S("st_changed_clear", v("st"), v("a")),
            k.check(k.eq(S("st_changed_count", v("st"), v("a")), e.n(0))),
            k.check(k.eq(S("st_count", v("st"), v("a")), e.n(2))),
            k.check(k.eq(S("st_id_at", v("st"), v("a"), e.n(1)), e.n(3))),
            k.check(k.eq(S("st_next_id", v("st"), v("a")), e.n(4))),
            # Two changes of one entry are one change; a delete records its text before.
            put("a", 1, '{"x":5}'),
            put("a", 1, '{"x":2}'),
            S("st_del", v("st"), v("a"), e.n(3)),
            k.check(k.eq(S("st_commit", v("st")), e.n(1))),
            *doc_is('{"a":{"1":{"x":2}},"bb":{"2":"s"}}'),
            *level_is('[["a",1,{"x":1},{"x":2}],["a",3,[2],null]]'),
            e.let("l2", buf("")),
            J("jw_text", v("l2"), S("st_level_text", v("st"))),
            S("st_changed_clear", v("st"), v("a")),
            S("st_level", v("st"), k.bytes_str(v("l2")), e.n(0)),
            *doc_is('{"a":{"1":{"x":1},"3":[2]},"bb":{"2":"s"}}'),
            k.check(k.eq(S("st_changed_count", v("st"), v("a")), e.n(2))),
            S("st_level", v("st"), k.bytes_str(v("l2")), e.n(1)),
            *doc_is('{"a":{"1":{"x":2}},"bb":{"2":"s"}}'),
            k.check(k.eq(S("st_commit", v("st")), e.n(0))),
            # A loaded document replaces everything; a section nobody registered stays as it is.
            S("st_load", v("st"), text(' {"zz": {"9" : true}, "a": {"5": 5, "2": [ 1 ]}} ')),
            *doc_is('{"a":{"2":[ 1 ],"5":5},"bb":{},"zz":{"9" : true}}'),
            k.check(k.eq(has(S("st_get", v("st"), v("b"), e.n(2))), e.n(0))),
            k.check(k.eq(has(S("st_get", v("st"), v("a"), e.n(5))), e.n(1))),
            k.check(k.eq(S("st_changed_count", v("st"), v("b")), e.n(1))),
            S("st_load", v("st"), text("")),
            *doc_is('{"a":{},"bb":{}}'),
        ]

    return wasi_test.module(e, [("json", editor_json.FILE), ("state", editor_state.FILE)], checks)
