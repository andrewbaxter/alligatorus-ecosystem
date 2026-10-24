"""idmap-wasm.atz: maps from i32 ids to values whose ids stay in ascending order (wat target; over map-wasm.atz and
vec-wasm.atz).

`idmap.type(value)` yields `{type, own, raw, new}` for a constant value type `value` (one map-wasm.atz takes):
`new()` yields an owned empty map (destructor.atz; `raw` the unowned handle type, `own` its adopting type). An idmap
is a pointer to an 8-byte header holding the map and the vec of its ids in ascending order (wasm-alloc.atz). On an
idmap value: `len` is a read-only place; `get(id)` is the map's `get` (option.atz: `some` of the value's place, a
borrow for a value with a destructor); `put(id, v)` stores `v` under `id` (taken when it has a destructor), adding
the id to the order when new; `remove(id)` → i32 (1 when it was present) takes the id out of both; `index_of(id)`
is the id's position in the order or, when absent, -(the position it would take) - 1; `id_at(i)` is the id at
position `i` (traps outside the order). Dropping an owned idmap destroys the values. The methods are dependencies
(`idmap_<value>_index`, `_put`, `_remove`, `_new`, `_free`), got by a module when its code first uses them.
"""

from ..core import values
from ..eco_mb import p
from ..memory import destructor, readonly
from ..target_mb import (
    a,
    alloc_or_trap,
    body,
    const_eval_in,
    const_fn,
    conv,
    cve_has,
    err_cve,
    fn_of,
    fn_type_of,
    graft,
    handle_methods,
    handle_type,
    has_b,
    ident_of,
    in_,
    loc,
    ret_m,
    self_v,
    ty,
    ty_desc,
    tuple_elements,
    unwrap_cve_m,
    up,
    xx,
)
from .vec import const_type_arg

FILE = "idmap-wasm.atz"

# The const function's staged setup is two stages below the module; a dependency body made there one more.
SETUP_MOD = 2
BODY_MOD = 3
BODY_SETUP = 1
FIELDS = ["pv", "ppv", "value", "i32", "ro_i32", "map_raw", "ints_raw", "m_index", "m_put", "m_remove"]
METHODS = ["index_of", "put", "remove", "get", "id_at"]


def _func_dep(e, name, params, ty_, body_):
    return e.call(
        up(e, e.fld(e.v("lib"), "func_dep"), SETUP_MOD),
        e.rec(
            p("name", e.cat(e.v("name"), e.s("_" + name))),
            p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
            p("ty", ty_),
            p("body", e.stage(body_)),
        ),
    )


def _dep(e, name, *args):
    return e.call(fn_of(e, up(e, e.v(name), BODY_SETUP)), args[0] if len(args) == 1 else e.tup(*args))


def _cell(e, m, index):
    """Header cell `index` (a pointer) of the idmap `m` in a dependency body."""
    return e.mb.field(
        conv(
            e,
            up(e, e.v("ptr_cast"), BODY_MOD),
            e.mb.as_(m, up(e, e.v("pv"), BODY_SETUP)),
            up(e, e.v("ppv"), BODY_SETUP),
        ),
        e.n(index),
    )


def _order(e):
    return e.mb.as_(_cell(e, e.v("m"), 1), up(e, e.v("ints_raw"), BODY_SETUP))


def _map(e):
    return e.mb.as_(_cell(e, e.v("m"), 0), up(e, e.v("map_raw"), BODY_SETUP))


def _index_body(e):
    """index(m, id): a binary search of the order."""
    i32 = up(e, e.v("i32"), BODY_SETUP)
    return e.mb.labeled(
        "fn",
        e.seq(
            e.let("lo", e.mb.as_(e.n(0), i32)),
            e.let("hi", e.mb.as_(e.fld(_order(e), "len"), i32)),
            e.mb.labeled(
                "search",
                e.foreach(
                    e.call(up(e, e.fld(e.v("lib"), "loop_fn"), BODY_MOD), e.rec()),
                    "_",
                    e.seq(
                        e.if_only(e.not_(e.mb.operator_lt(e.v("lo"), e.v("hi"))), e.mb.return_label("search")),
                        e.let("mid", e.mb.operator_div(e.mb.operator_add(e.v("lo"), e.v("hi")), e.n(2))),
                        e.let("at", e.call(e.fld(_order(e), "at"), e.v("mid"))),
                        e.if_only(e.eq(e.v("at"), e.v("id")), e.mb.return_to("fn", e.v("mid"))),
                        e.if_else(
                            e.mb.operator_lt(e.v("at"), e.v("id")),
                            e.mb.set(e.v("lo"), e.mb.operator_add(e.v("mid"), e.n(1))),
                            e.mb.set(e.v("hi"), e.v("mid")),
                        ),
                    ),
                ),
            ),
            e.mb.return_to("fn", e.mb.operator_sub(e.mb.operator_sub(e.n(0), e.v("lo")), e.n(1))),
        ),
    )


def _put_body(e):
    """put(m, id, v): the value into the map (taken when it has a destructor), the id into the order when new."""
    stored = e.if_else(up(e, e.v("drops"), BODY_SETUP), e.call(e.fld(e.v("v"), "move"), e.tup()), e.v("v"))
    return e.seq(
        e.call(e.fld(_map(e), "put"), e.tup(e.v("id"), stored)),
        e.let("i", _dep(e, "m_index", e.v("m"), e.v("id"))),
        e.if_only(
            e.mb.operator_lt(e.v("i"), e.n(0)),
            e.call(
                e.fld(_order(e), "insert"),
                e.tup(e.mb.operator_sub(e.mb.operator_sub(e.n(0), e.v("i")), e.n(1)), e.v("id")),
            ),
        ),
    )


def _remove_body(e):
    """remove(m, id) -> i32: the id out of the order when present, then out of the map (its result)."""
    return e.seq(
        e.let("i", _dep(e, "m_index", e.v("m"), e.v("id"))),
        e.if_only(
            e.not_(e.mb.operator_lt(e.v("i"), e.n(0))),
            e.seq(e.let("__gone", e.call(e.fld(_order(e), "remove"), e.v("i")))),
        ),
        e.ret(e.call(e.fld(_map(e), "remove"), e.v("id"))),
    )


def _new_body(e):
    """new() -> pv: the header over a new map and a new order (the caller's owning constructor adopts it)."""
    pv = up(e, e.v("pv"), BODY_SETUP)
    return e.seq(
        e.let(
            "m",
            alloc_or_trap(
                e,
                e.call(up(e, e.fld(e.v("heap"), "malloc"), BODY_MOD), e.n(8)),
                up(e, e.v("ptr_to_int"), BODY_MOD),
                up(e, e.v("i32"), BODY_SETUP),
                e.call(fn_of(e, up(e, e.fld(e.v("lib"), "trap"), BODY_MOD)), e.tup()),
            ),
        ),
        e.let("__map", e.call(up(e, e.v("map_new"), BODY_SETUP), e.tup())),
        e.let("__order", e.call(up(e, e.v("ints_new"), BODY_SETUP), e.tup())),
        e.mb.set(_cell(e, e.v("m"), 0), e.mb.as_(e.call(e.fld(e.v("__map"), "forget"), e.tup()), pv)),
        e.mb.set(_cell(e, e.v("m"), 1), e.mb.as_(e.call(e.fld(e.v("__order"), "forget"), e.tup()), pv)),
        e.ret(e.v("m")),
    )


def _free_body(e):
    """free(m): the map and the order adopted into dropping bindings, then the header freed."""
    return e.seq(
        e.seq(e.let("__m", e.mb.as_(_map(e), up(e, e.v("map_own"), BODY_SETUP)))),
        e.seq(e.let("__o", e.mb.as_(_order(e), up(e, e.v("ints_own"), BODY_SETUP)))),
        e.call(up(e, e.fld(e.v("heap"), "free"), BODY_MOD), e.v("m")),
    )


def _setup(e):
    """Staged in the caller's context: the map and order types over the value, the dependencies and the idmap
    types."""
    out = []
    for name in ["value", "name", "drops"]:
        out.append(e.let(name, e.lower(e.v(name))))
    for name in ["i32", "void", "readonly", "pv", "ppv", "ptr_cast", "ptr_to_int"]:
        out.append(e.let(name, up(e, e.v(name), SETUP_MOD)))
    out.append(e.let("mapr", e.call(up(e, e.fld(e.v("map"), "type"), SETUP_MOD), e.tup(e.v("i32"), e.v("value")))))
    out.append(e.let("intsr", e.call(up(e, e.fld(e.v("vec"), "type"), SETUP_MOD), e.v("i32"))))
    for pre, src in [("map", "mapr"), ("ints", "intsr")]:
        for f in ["raw", "own", "new"]:
            out.append(e.let(pre + "_" + f, e.fld(e.v(src), f)))
    out.append(e.let("ro_i32", e.call(e.fld(e.v("readonly"), "type"), e.v("i32"))))
    lib = up(e, e.v("lib"), SETUP_MOD)
    for name, params, fn_params, ret, fbody in [
        ("m_index", ("m", "id"), [e.v("pv"), e.v("i32")], e.v("i32"), _index_body),
        ("m_put", ("m", "id", "v"), [e.v("pv"), e.v("i32"), e.v("value")], e.v("void"), _put_body),
        ("m_remove", ("m", "id"), [e.v("pv"), e.v("i32")], e.v("i32"), _remove_body),
        ("new", (), [], e.v("pv"), _new_body),
        ("free", ("m",), [e.v("pv")], e.v("void"), _free_body),
    ]:
        out.append(
            e.let(name, _func_dep(e, name.replace("m_", ""), params, fn_type_of(e, lib, fn_params, ret), fbody(e)))
        )
    out.append(
        e.let(
            "raw",
            e.mb.as_(
                e.call(up(e, e.fld(e.v("it"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in FIELDS])),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(
        e.let(
            "owned_r",
            e.call(
                e.fld(up(e, e.v("destructor"), SETUP_MOD), "owning"),
                e.rec(p("under", e.v("raw")), p("destroy", e.v("free")), p("new", e.v("new"))),
            ),
        )
    )
    out.append(
        e.ret(
            e.rec(
                p("type", e.fld(e.v("owned_r"), "type")),
                p("own", e.fld(e.v("owned_r"), "own")),
                p("raw", e.v("raw")),
                p("new", e.fld(e.v("owned_r"), "new")),
            )
        )
    )
    return e.mb.seq(out)


def _it(e, x):
    """The unowned idmap handle type: the header pointer carrying the value type, the map and order types and the
    method dependencies."""
    fields = [p(f, ty(e)) for f in FIELDS]

    def part(self_as, index, field):
        return e.mb.as_(e.mb.field(self_as("ppv"), e.n(index)), e.lower(in_(e, field)))

    places = {
        "len": lambda self_as: e.mb.as_(e.fld(part(self_as, 1, "ints_raw"), "len"), e.lower(in_(e, "ro_i32"))),
    }
    meth = handle_type(
        e,
        x,
        "it",
        "it_m",
        "idmap",
        fields,
        places,
        METHODS,
        under="pv",
        desc_expr=e.cat(e.s("idmap("), ty_desc(e, in_(e, "value")), e.s(")")),
        identity="value",
        ptr_cast=e.lower(e.v("ptr_cast")),
    )

    def dep(kind):
        return fn_of(e, e.lower(e.v("m_" + kind)))

    def self_part(index, field):
        return e.mb.as_(
            e.mb.field(conv(e, up(e, e.v("ptr_cast"), 2), self_v(e), e.lower(e.v("ppv"))), e.n(index)),
            e.lower(e.v(field)),
        )

    def method_body(kind):
        if kind == "index_of":
            return e.call(dep("index"), e.tup(self_v(e), graft(e, a(e, "argument"))))
        if kind == "put":
            return e.call(
                dep("put"),
                e.tup(
                    self_v(e),
                    graft(e, e.call_m(e.v("__put"), "get", e.int_of(0))),
                    graft(e, e.call_m(e.v("__put"), "get", e.int_of(1))),
                ),
            )
        if kind == "remove":
            return e.call(dep("remove"), e.tup(self_v(e), graft(e, a(e, "argument"))))
        if kind == "get":
            return e.call(e.fld(self_part(0, "map_raw"), "get"), graft(e, a(e, "argument")))
        if kind == "id_at":
            return e.call(e.fld(self_part(1, "ints_raw"), "at"), graft(e, a(e, "argument")))
        raise AssertionError(kind)

    handle_methods(
        e,
        x,
        meth,
        "it_m",
        fields,
        METHODS,
        method_body,
        kind_prelude={"put": tuple_elements(e, "idmap: put takes (id, value)", a(e, "argument"), "__put", 2)},
    )


def module(e):
    x = []
    x.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
    x.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    x.append(e.let("map", e.import_local("map", "map-wasm.atz")))
    x.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("readonly", e.import_local("readonly", readonly.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("i32", e.fld(e.v("lib"), "i32")))
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("ppv", e.call(e.fld(e.v("lib"), "ptr"), e.v("pv"))))
    for name in ["ptr_cast", "ptr_to_int"]:
        x.append(e.let(name, e.fld(e.v("lib"), name)))
    _it(e, x)
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "idmap.type: argument has no value"))),
        *const_type_arg(e, "idmap.type", e.v("argv"), "value"),
        e.let("name", e.cat(e.s("idmap_"), ident_of(e, ty_desc(e, e.v("value"))))),
        e.let("drops", has_b(e, xx(e), e.v("value"), e.mb.eval_aspect_drop_dynamic())),
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), loc(e), e.stage(_setup(e)))))),
    ]
    const_fn(e, x, "idmap_b", "idmap.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("idmap_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
