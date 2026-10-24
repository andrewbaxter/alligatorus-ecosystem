"""editor-state.atz: an editor's document, kept in the ide's undo history (wat target; dependencies; the ecosystem's
records, vecs, maps and editor-types.atz's `str` and `bytes`).

The document is one JSON object of sections, each an object of entries keyed by an entry id (a positive i32 as
text), each entry any JSON value: `{"<section>": {"<id>": <entry>, ...}, ...}`. Each component of an editor owns a
section (registered with the key the editor gives it) and keeps its entries as JSON text in the store; the store is
the one truth, and a component rebuilds what it shows from the entries that changed.

The store is an owned record (`st_t`, `st_raw`): `st_new()` makes one (owned) (it owns its sections,
entries, changes, texts; dropping it frees everything). A section holds its entries in a map from id to text
(map-wasm.atz, which owns the texts) and their ids in a sorted vec (`order`), the iteration order.
`st_section(st, key)` registers a section (a constant `str` key) and is its index. `st_put(st, sec, id, text)` sets
entry `id` to the bytes of the `bytes` buffer `text` (copied) and `st_del(st, sec, id)` removes it;
`st_get(st, sec, id)` is `some` of the entry's text (a `str` view into the store, valid until the entry changes) or
`none` (`opt_str`: option.atz over `str`). `st_count(st, sec)`, `st_id_at(st, sec, i)` and `st_text_at(st, sec, i)`
walk a section's entries in id order, and `st_next_id(st, sec)` is one past its largest id (1 for an empty section).

Every put and delete since the last commit is one change of the document: `st_commit(st)` serializes the document
and an undo level holding each changed entry before and after (`[["<section>", <id>, <before or null>, <after or
null>], ...]`), and is 1 when there was anything to commit (the editor then hands `st_level_text(st)` to `doc_edit`;
`st_doc(st)` is the serialized document, both `str` views). `st_level(st, text, redo)` applies a level handed back by
undo (the `before`s) or redo (the `after`s), and `st_load(st, text)` replaces everything with a document's text
(empty text: an empty document); both re-serialize the document. Sections in a document that no component
registered are kept as they are.

Every entry that a put, delete, level or load touches is listed as changed in its section until the component
takes the list: `st_changed_count(st, sec)`, `st_changed_at(st, sec, i)` (an id; the entry may be gone),
`st_changed_clear(st, sec)`. An entry's text is never empty (a JSON value has a byte), so an empty `bytes` stands
for an absent `before`/`after` in a change."""

from ..collections import record_wasm
from ..eco_mb import p
from ..target_mb import fn_of
from . import editor_json, editor_types
from ..wasm.kit import Kit, library, stack

FILE = "editor-state.atz"

TYPE_EXPORTS = ["st_t", "st_raw"]
EXPORTS = [
    "st_new",
    "st_section",
    "st_put",
    "st_del",
    "st_get",
    "st_count",
    "st_id_at",
    "st_text_at",
    "st_next_id",
    "st_commit",
    "st_level",
    "st_load",
    "st_doc",
    "st_level_text",
    "st_changed_count",
    "st_changed_at",
    "st_changed_clear",
]


def _record(e, x, name, fields):
    """A record type `name` over `fields` (name, type binding): binds `<name>_t/_own/_raw/_make`."""
    x.append(
        e.let(
            name + "_r",
            e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in fields])))),
        )
    )
    for f in ["t", "raw"]:
        x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    x.append(e.let(name + "_make", e.fld(e.v(name + "_r"), "new")))
    return [name + "_" + f for f in ["t", "raw", "make"]]


def _vec(e, x, name, elem):
    """A vec type `name` of `elem` (a type binding): binds `<name>_t/_own/_raw/_new`."""
    x.append(e.let(name + "_r", e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
    for f in ["t", "own", "raw", "new"]:
        x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    return [name + "_" + f for f in ["t", "own", "raw", "new"]]


def _map(e, x, name, key, value):
    """A map type `name` from `key` to `value` (type bindings): binds `<name>_t/_own/_raw/_new`."""
    x.append(e.let(name + "_r", e.call(e.fld(e.v("map"), "type"), e.tup(e.v(key), e.v(value)))))
    for f in ["t", "own", "raw", "new"]:
        x.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    return [name + "_" + f for f in ["t", "own", "raw", "new"]]


def _imports(e, x):
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("map", e.import_local("map", "map-wasm.atz")))
    x.append(e.let("option", e.import_local("option", "option-wasm.atz")))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))


def module(e):
    k = Kit(e)

    def level1(x):
        _imports(e, x)
        for n in editor_types.EXPORTS:
            x.append(e.let(n, e.fld(e.v("types"), n)))
        names = list(editor_types.EXPORTS)
        names += _record(
            e, x, "change", [("sec", "t_i32"), ("id", "t_i32"), ("before", "bytes_t"), ("after", "bytes_t")]
        )
        names += _record(e, x, "extra", [("key", "bytes_t"), ("value", "bytes_t")])
        x.append(e.let("opt_str_r", e.call(e.fld(e.v("option"), "type"), e.v("str_t"))))
        for f in ["t", "some", "none"]:
            x.append(e.let("opt_str_" + f, e.fld(e.v("opt_str_r"), "type" if f == "t" else f)))
        return names + ["opt_str_t", "opt_str_some", "opt_str_none"]

    def level2(x):
        _imports(e, x)
        names = []
        names += _map(e, x, "entries", "t_i32", "bytes_t")
        names += _vec(e, x, "changes", "change_t")
        names += _vec(e, x, "extras", "extra_t")
        return names

    def level3(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "section",
            [
                ("key", "bytes_t"),
                ("entries", "entries_t"),
                ("order", "ints_t"),
                ("changed", "ints_t"),
            ],
        )

    def level4(x):
        _imports(e, x)
        return _vec(e, x, "sections", "section_t")

    def level5(x):
        _imports(e, x)
        return _record(
            e,
            x,
            "st",
            [
                ("sections", "sections_t"),
                ("changes", "changes_t"),
                ("doc", "bytes_t"),
                ("level", "bytes_t"),
                ("extra", "extras_t"),
            ],
        )

    x, names = stack(e, k, [level1, level2, level3, level4, level5])
    x.append(e.let("json", e.import_local("json", editor_json.FILE)))
    x.append(e.let("types", e.import_local("types", editor_types.FILE)))
    k.text(x, "st_null", "null")
    v = e.v

    def J(f, *args):
        return k.lib("json", f, *args)

    def T(f, *args):
        return k.lib("types", f, *args)

    def st(name):
        return e.fld(v("st"), name)

    def sec(i):
        """Section `i` of the store (a borrow of the record)."""
        return k.m(st("sections"), "at", i)

    def raw(borrow, name):
        """A borrow (an owned field or element, which cannot be bound) as its raw type `<name>_raw`, for binding."""
        return e.mb.as_(borrow, k.lo(name + "_raw"))

    def order_of(s):
        """Statements binding `order` to section `s`'s sorted ids."""
        return [e.let("order", raw(e.fld(sec(s), "order"), "ints"))]

    def entries_of(s):
        """Statements binding `ents` to section `s`'s entries map."""
        return [e.let("ents", raw(e.fld(sec(s), "entries"), "entries"))]

    def new_bytes():
        return k.call("bytes_new", e.tup())

    def bytes_copy(name, src):
        """Statements binding `name` to a new owned buffer holding the bytes of the `str` `src`."""
        return [e.let(name, new_bytes()), J("jw_text", v(name), src)]

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def with_text(ents, id_, use):
        """A statement running `use(s)` with `s` the text of entry `id_` in the map `ents` as a `str` (an entry the
        order lists is in the map: a missing one traps). The arms are statements: a handle value merged through a
        match comes out as its representation."""
        return e.match_of(
            k.m(ents, "get", id_),
            "pl",
            None,
            p("some", use(k.bytes_str(e.mb.field(v("pl"), e.n(0))))),
            p("none", trap()),
        )

    def secs_count():
        return e.fld(st("sections"), "len")

    k.dep(
        x,
        "st_new",
        [],
        [],
        "st_t",
        e.seq(
            e.let("sections", k.call("sections_new", e.tup())),
            e.let("changes", k.call("changes_new", e.tup())),
            e.let("doc", new_bytes()),
            e.let("level", new_bytes()),
            e.let("extra", k.call("extras_new", e.tup())),
            e.ret(
                k.call(
                    "st_make",
                    e.rec(
                        *[p(f, k.m(v(f), "move", e.tup())) for f in ["sections", "changes", "doc", "level", "extra"]]
                    ),
                )
            ),
        ),
    )
    k.dep(
        x,
        "st_section",
        ["st", "key"],
        ["st_raw", "str_t"],
        "t_i32",
        e.seq(
            e.let("i", secs_count()),
            e.let("entries", k.call("entries_new", e.tup())),
            e.let("order", k.call("ints_new", e.tup())),
            e.let("changed", k.call("ints_new", e.tup())),
            # the section keeps its own copy of the key: the caller's text may not outlive the store
            e.let("keyb", k.call("bytes_new", e.tup())),
            k.m(v("keyb"), "extend", v("key")),
            k.m(
                st("sections"),
                "push",
                k.call(
                    "section_make",
                    e.rec(
                        p("key", k.m(v("keyb"), "move", e.tup())),
                        p("entries", k.m(v("entries"), "move", e.tup())),
                        p("order", k.m(v("order"), "move", e.tup())),
                        p("changed", k.m(v("changed"), "move", e.tup())),
                    ),
                ),
            ),
            e.ret(v("i")),
        ),
    )

    def key_of(sa):
        return k.bytes_str(e.fld(sa, "key"))

    # The index of entry `id` in the section's order (ids ascending), or, when missing, -(insertion index) - 1.
    k.dep(
        x,
        "st_find",
        ["st", "sec", "id"],
        ["st_raw", "t_i32", "t_i32"],
        "t_i32",
        e.seq(*order_of(v("sec")), e.ret(T("ints_find", v("order"), v("id")))),
    )
    k.dep(
        x,
        "st_mark",
        ["st", "sec", "id"],
        ["st_raw", "t_i32", "t_i32"],
        "t_void",
        e.seq(
            e.let("ch", raw(e.fld(sec(v("sec")), "changed"), "ints")),
            k.for_("i", 0, e.fld(v("ch"), "len"), "seen", k.if_(k.eq(k.m(v("ch"), "at", v("i")), v("id")), k.ret())),
            k.m(v("ch"), "push", v("id")),
        ),
    )
    # Sets entry `id` to `text` (a buffer the store takes), or removes it when `has` is 0; marks it changed.
    k.dep(
        x,
        "st_set_raw",
        ["st", "sec", "id", "has", "text"],
        ["st_raw", "t_i32", "t_i32", "t_i32", "bytes_t"],
        "t_void",
        e.seq(
            *entries_of(v("sec")),
            *order_of(v("sec")),
            e.let("i", k.dcall("st_find", v("st"), v("sec"), v("id"))),
            k.dcall("st_mark", v("st"), v("sec"), v("id")),
            # Both branches take the buffer (a binding moved on one path must be moved on every path): the removal
            # drops it.
            k.ifelse(
                k.eq(v("has"), e.n(0)),
                e.seq(
                    k.if_(
                        k.ge(v("i"), e.n(0)),
                        e.seq(e.let("gone", k.m(v("ents"), "remove", v("id")))),
                        k.m(v("order"), "remove", v("i")),
                    ),
                    e.seq(e.let("unused", k.m(v("text"), "move", e.tup()))),
                ),
                e.seq(
                    k.m(v("ents"), "put", e.tup(v("id"), k.m(v("text"), "move", e.tup()))),
                    k.if_(
                        k.lt(v("i"), e.n(0)), k.m(v("order"), "insert", e.tup(k.sub(k.neg(v("i")), e.n(1)), v("id")))
                    ),
                ),
            ),
        ),
    )
    k.dep(
        x,
        "st_get",
        ["st", "sec", "id"],
        ["st_raw", "t_i32", "t_i32"],
        "opt_str_t",
        e.seq(
            *entries_of(v("sec")),
            e.match_of(
                k.m(v("ents"), "get", v("id")),
                "pl",
                None,
                p("some", k.ret(k.call("opt_str_some", k.bytes_str(e.mb.field(v("pl"), e.n(0)))))),
                p("none", k.ret(k.call("opt_str_none", e.tup()))),
            ),
        ),
    )
    # Records a change of entry `id` (its text before the first change since the last commit, and after), then sets
    # it (`has` 0: removes it; `text` is taken).
    k.dep(
        x,
        "st_change",
        ["st", "sec", "id", "has", "text"],
        ["st_raw", "t_i32", "t_i32", "t_i32", "bytes_t"],
        "t_void",
        e.seq(
            e.let("chs", raw(st("changes"), "changes")),
            e.let("found", k.i32(-1)),
            k.for_(
                "i",
                0,
                e.fld(v("chs"), "len"),
                "look",
                e.let("c", raw(k.m(v("chs"), "at", v("i")), "change")),
                k.if_(
                    k.and_(k.eq(e.fld(v("c"), "sec"), v("sec")), k.eq(e.fld(v("c"), "id"), v("id"))),
                    e.mb.set(v("found"), v("i")),
                    k.brk("look"),
                ),
            ),
            k.if_(
                k.lt(v("found"), e.n(0)),
                # The change starts with empty buffers (the record takes them); the text before is copied in
                # through the stored record.
                k.m(
                    v("chs"),
                    "push",
                    k.call(
                        "change_make",
                        e.rec(
                            p("sec", v("sec")),
                            p("id", v("id")),
                            p("before", k.call("bytes_new", e.tup())),
                            p("after", k.call("bytes_new", e.tup())),
                        ),
                    ),
                ),
                e.mb.set(v("found"), k.sub(e.fld(v("chs"), "len"), e.n(1))),
                e.let("c2", raw(k.m(v("chs"), "at", v("found")), "change")),
                e.match_of(
                    k.dcall("st_get", v("st"), v("sec"), v("id")),
                    "old",
                    None,
                    p("some", J("jw_text", e.fld(v("c2"), "before"), v("old"))),
                    p("none", e.seq()),
                ),
            ),
            e.let("c3", raw(k.m(v("chs"), "at", v("found")), "change")),
            k.m(e.fld(v("c3"), "after"), "clear", e.tup()),
            k.if_(k.ne(v("has"), e.n(0)), J("jw_text", e.fld(v("c3"), "after"), k.bytes_str(v("text")))),
            k.dcall("st_set_raw", v("st"), v("sec"), v("id"), v("has"), k.m(v("text"), "move", e.tup())),
        ),
    )
    k.dep(
        x,
        "st_put",
        ["st", "sec", "id", "text"],
        ["st_raw", "t_i32", "t_i32", "bytes_raw"],
        "t_void",
        e.seq(
            *bytes_copy("copy", k.bytes_str(v("text"))),
            k.dcall("st_change", v("st"), v("sec"), v("id"), k.i32(1), k.m(v("copy"), "move", e.tup())),
        ),
    )
    k.dep(
        x,
        "st_del",
        ["st", "sec", "id"],
        ["st_raw", "t_i32", "t_i32"],
        "t_void",
        e.seq(
            k.if_(k.lt(k.dcall("st_find", v("st"), v("sec"), v("id")), e.n(0)), k.ret()),
            k.dcall("st_change", v("st"), v("sec"), v("id"), k.i32(0), new_bytes()),
        ),
    )
    k.dep(
        x, "st_count", ["st", "sec"], ["st_raw", "t_i32"], "t_i32", e.ret(e.fld(e.fld(sec(v("sec")), "order"), "len"))
    )
    k.dep(
        x,
        "st_id_at",
        ["st", "sec", "i"],
        ["st_raw", "t_i32", "t_i32"],
        "t_i32",
        e.ret(k.m(e.fld(sec(v("sec")), "order"), "at", v("i"))),
    )
    k.dep(
        x,
        "st_text_at",
        ["st", "sec", "i"],
        ["st_raw", "t_i32", "t_i32"],
        "str_t",
        e.seq(
            *entries_of(v("sec")),
            with_text(v("ents"), k.m(e.fld(sec(v("sec")), "order"), "at", v("i")), lambda s_: k.ret(s_)),
        ),
    )
    k.dep(
        x,
        "st_next_id",
        ["st", "sec"],
        ["st_raw", "t_i32"],
        "t_i32",
        e.seq(
            *order_of(v("sec")),
            e.let("n", e.fld(v("order"), "len")),
            k.if_(k.eq(v("n"), e.n(0)), k.ret(k.i32(1))),
            e.ret(k.add(k.m(v("order"), "at", k.sub(v("n"), e.n(1))), e.n(1))),
        ),
    )

    def put_byte(dst, ch):
        return J("jw_byte", dst, e.n(ord(ch)))

    k.dep(
        x,
        "st_serialize",
        ["st"],
        ["st_raw"],
        "t_void",
        e.seq(
            e.let("d", raw(st("doc"), "bytes")),
            k.m(v("d"), "clear", e.tup()),
            put_byte(v("d"), "{"),
            e.let("first", k.i32(1)),
            k.for_(
                "s",
                0,
                secs_count(),
                "secs",
                e.let("sa", raw(sec(v("s")), "section")),
                k.if_(k.eq(v("first"), e.n(0)), put_byte(v("d"), ",")),
                e.mb.set(v("first"), e.n(0)),
                J("jw_str", v("d"), key_of(v("sa"))),
                put_byte(v("d"), ":"),
                put_byte(v("d"), "{"),
                e.let("ents", raw(e.fld(v("sa"), "entries"), "entries")),
                e.let("order", raw(e.fld(v("sa"), "order"), "ints")),
                k.for_(
                    "i",
                    0,
                    e.fld(v("order"), "len"),
                    "ents",
                    e.let("id", k.m(v("order"), "at", v("i"))),
                    k.if_(k.gt(v("i"), e.n(0)), put_byte(v("d"), ",")),
                    put_byte(v("d"), '"'),
                    J("jw_int", v("d"), v("id")),
                    put_byte(v("d"), '"'),
                    put_byte(v("d"), ":"),
                    with_text(v("ents"), v("id"), lambda s_: J("jw_text", v("d"), s_)),
                ),
                put_byte(v("d"), "}"),
            ),
            k.for_(
                "j",
                0,
                e.fld(st("extra"), "len"),
                "extra",
                e.let("ex", raw(k.m(st("extra"), "at", v("j")), "extra")),
                k.if_(k.eq(v("first"), e.n(0)), put_byte(v("d"), ",")),
                e.mb.set(v("first"), e.n(0)),
                J("jw_text", v("d"), k.bytes_str(e.fld(v("ex"), "key"))),
                put_byte(v("d"), ":"),
                J("jw_text", v("d"), k.bytes_str(e.fld(v("ex"), "value"))),
            ),
            put_byte(v("d"), "}"),
        ),
    )
    k.dep(
        x,
        "st_commit",
        ["st"],
        ["st_raw"],
        "t_i32",
        e.seq(
            e.let("chs", raw(st("changes"), "changes")),
            k.if_(k.eq(e.fld(v("chs"), "len"), e.n(0)), k.ret(k.i32(0))),
            e.let("lv", raw(st("level"), "bytes")),
            k.m(v("lv"), "clear", e.tup()),
            put_byte(v("lv"), "["),
            k.for_(
                "i",
                0,
                e.fld(v("chs"), "len"),
                "chs",
                e.let("c", raw(k.m(v("chs"), "at", v("i")), "change")),
                e.let("sa", raw(sec(e.fld(v("c"), "sec")), "section")),
                k.if_(k.gt(v("i"), e.n(0)), put_byte(v("lv"), ",")),
                put_byte(v("lv"), "["),
                J("jw_str", v("lv"), key_of(v("sa"))),
                put_byte(v("lv"), ","),
                J("jw_int", v("lv"), e.fld(v("c"), "id")),
                *[
                    e.seq(
                        put_byte(v("lv"), ","),
                        k.ifelse(
                            k.eq(e.fld(e.fld(v("c"), side), "len"), e.n(0)),
                            J("jw_text", v("lv"), k.sconst("st_null", "null")),
                            J("jw_text", v("lv"), k.bytes_str(e.fld(v("c"), side))),
                        ),
                    )
                    for side in ["before", "after"]
                ],
                put_byte(v("lv"), "]"),
            ),
            put_byte(v("lv"), "]"),
            k.m(v("chs"), "clear", e.tup()),
            k.dcall("st_serialize", v("st")),
            e.ret(k.i32(1)),
        ),
    )
    # The index of the registered section whose key is the string at `q` of `text`, or -1.
    k.dep(
        x,
        "st_section_of",
        ["st", "text", "q"],
        ["st_raw", "str_t", "t_i32"],
        "t_i32",
        e.seq(
            k.for_(
                "s",
                0,
                secs_count(),
                "secs",
                k.if_(k.ne(J("jr_key_is", v("text"), v("q"), key_of(sec(v("s")))), e.n(0)), k.ret(v("s"))),
            ),
            e.ret(k.i32(-1)),
        ),
    )

    def value_bytes(name, text, q):
        """Statements binding `name` to a new owned buffer of the JSON value at `q` of `text`."""
        return bytes_copy(name, J("jr_text", text, q))

    k.dep(
        x,
        "st_level",
        ["st", "text", "redo"],
        ["st_raw", "str_t", "t_i32"],
        "t_void",
        e.seq(
            e.let("c", J("jr_first", v("text"), e.n(0))),
            k.loop(
                "chs",
                k.if_(k.lt(v("c"), e.n(0)), k.brk("chs")),
                e.let("f0", J("jr_first", v("text"), v("c"))),
                e.let("sec", k.dcall("st_section_of", v("st"), v("text"), v("f0"))),
                e.let("f1", J("jr_next", v("text"), v("f0"))),
                e.let("id", J("jr_int", v("text"), v("f1"))),
                e.let("f2", J("jr_next", v("text"), v("f1"))),
                e.let("f3", J("jr_next", v("text"), v("f2"))),
                e.let("side", k.ifelse(k.eq(v("redo"), e.n(0)), v("f2"), v("f3"))),
                k.if_(
                    k.ge(v("sec"), e.n(0)),
                    e.let("isnull", J("jr_null", v("text"), v("side"))),
                    *value_bytes("val", v("text"), v("side")),
                    k.dcall(
                        "st_set_raw",
                        v("st"),
                        v("sec"),
                        v("id"),
                        k.ifelse(k.ne(v("isnull"), e.n(0)), k.i32(0), k.i32(1)),
                        k.m(v("val"), "move", e.tup()),
                    ),
                ),
                e.mb.set(v("c"), J("jr_next", v("text"), v("c"))),
            ),
            k.dcall("st_serialize", v("st")),
        ),
    )
    k.dep(
        x,
        "st_load",
        ["st", "text"],
        ["st_raw", "str_t"],
        "t_void",
        e.seq(
            # Every entry there was is changed (it may be gone).
            k.for_(
                "s",
                0,
                secs_count(),
                "clear",
                *order_of(v("s")),
                k.loop(
                    "drop",
                    k.if_(k.eq(e.fld(v("order"), "len"), e.n(0)), k.brk("drop")),
                    k.dcall(
                        "st_set_raw",
                        v("st"),
                        v("s"),
                        k.m(v("order"), "at", k.sub(e.fld(v("order"), "len"), e.n(1))),
                        k.i32(0),
                        new_bytes(),
                    ),
                ),
            ),
            k.m(st("extra"), "clear", e.tup()),
            k.m(st("changes"), "clear", e.tup()),
            e.let("q", J("jr_ws", v("text"), e.n(0))),
            k.if_(k.ge(v("q"), e.fld(v("text"), "len")), k.dcall("st_serialize", v("st")), k.ret()),
            e.let("sk", J("jr_first", v("text"), v("q"))),
            k.loop(
                "secs",
                k.if_(k.lt(v("sk"), e.n(0)), k.brk("secs")),
                e.let("sec", k.dcall("st_section_of", v("st"), v("text"), v("sk"))),
                e.let("sv", J("jr_value", v("text"), v("sk"))),
                k.ifelse(
                    k.lt(v("sec"), e.n(0)),
                    e.seq(
                        *value_bytes("ka", v("text"), v("sk")),
                        *value_bytes("va", v("text"), v("sv")),
                        k.m(
                            st("extra"),
                            "push",
                            k.call(
                                "extra_make",
                                e.rec(
                                    p("key", k.m(v("ka"), "move", e.tup())),
                                    p("value", k.m(v("va"), "move", e.tup())),
                                ),
                            ),
                        ),
                    ),
                    e.seq(
                        e.let("ek", J("jr_first", v("text"), v("sv"))),
                        k.loop(
                            "ents",
                            k.if_(k.lt(v("ek"), e.n(0)), k.brk("ents")),
                            *value_bytes("ev", v("text"), J("jr_value", v("text"), v("ek"))),
                            k.dcall(
                                "st_set_raw",
                                v("st"),
                                v("sec"),
                                J("jr_int", v("text"), v("ek")),
                                k.i32(1),
                                k.m(v("ev"), "move", e.tup()),
                            ),
                            e.mb.set(v("ek"), J("jr_next", v("text"), v("ek"))),
                        ),
                    ),
                ),
                e.mb.set(v("sk"), J("jr_next", v("text"), v("sk"))),
            ),
            k.dcall("st_serialize", v("st")),
        ),
    )
    k.dep(x, "st_doc", ["st"], ["st_raw"], "str_t", e.ret(k.bytes_str(st("doc"))))
    k.dep(x, "st_level_text", ["st"], ["st_raw"], "str_t", e.ret(k.bytes_str(st("level"))))
    k.dep(
        x,
        "st_changed_count",
        ["st", "sec"],
        ["st_raw", "t_i32"],
        "t_i32",
        e.ret(e.fld(e.fld(sec(v("sec")), "changed"), "len")),
    )
    k.dep(
        x,
        "st_changed_at",
        ["st", "sec", "i"],
        ["st_raw", "t_i32", "t_i32"],
        "t_i32",
        e.ret(k.m(e.fld(sec(v("sec")), "changed"), "at", v("i"))),
    )
    k.dep(
        x,
        "st_changed_clear",
        ["st", "sec"],
        ["st_raw", "t_i32"],
        "t_void",
        k.m(e.fld(sec(v("sec")), "changed"), "clear", e.tup()),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
