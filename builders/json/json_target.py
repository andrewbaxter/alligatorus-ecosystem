"""json-wasm.atz / json-llvm.atz: json parsers and writers as ordinary target functions, one module per target from
this builder. The parsing and serializing logic comes from json.atz; this module gives it a representation.

`parser({name, read})` yields `{type, raw, new, event}` for a constant reader `read`, a target function
`(ptr(void)) -> i32` (a dependency made in a lowered setup block, a `func_fn` result or an import) returning the
next byte of input or a negative int at its end; the value passed to it is whatever the parser was made with;
`name` is a constant string naming the reader in the dependencies below:
- a parser is a pointer to a 64-byte header: the reader's argument, the byte vecs (vec.atz) of the current token
  and of the container stack, and the state machine's registers;
- `new(ctx)` yields a parser reading through `read(ctx)`; `type(new(ctx))` makes it an owned value
  (destructor.atz) whose drop frees the vecs and the header; `raw` is the unowned handle type;
- on a parser value, `next()` yields the next event: one value or structural token of the document, consumed
  through `read`, as a value of the event union `event.type`, read with `match`. The variants are `end` (the
  document is complete; every later call yields it too), `error` (an int code: 1 unexpected byte, 2 unexpected
  end of input, 4 data after the document, 5 bad escape; every later call yields it too), `null`, `bool` (an int,
  1 or 0), `number`, `string` and `key` (a byte slice, slice.atz, of the token's content, valid until the next
  call or the parser's drop; keys arrive before their values, strings decoded), `object_begin`, `object_end`,
  `array_begin`, `array_end`. `event` also holds the constructors, one per variant, as callable types. There is
  no depth limit.
The functions `json_parser_<name>_new`, `_free` and `_next` are dependencies (`func_dep`): a module gets them when
its code first uses them, once per reader however many parsers it makes. Memory comes from wasm-alloc.atz (wasm) or
libc (llvm).

`writer({name, write})` yields `{type, raw, new}` for a constant sink `write`, a target function
`(ptr(void), i32) -> void` taking a byte of output, and a constant string `name` naming it:
- a writer is a pointer to a 16-byte header: the sink's argument and the comma state;
- `new(ctx)` yields a writer writing through `write(ctx, b)`; `type(new(ctx))` makes it owned; `raw` is the
  unowned handle type;
- on a writer value: `null()`, `bool(v)`, `int(v)`, `number(s)` (the raw bytes of a number, a byte slice),
  `string(s)` and `key(s)` (utf-8 bytes, escaped as json needs; a key ends with its colon), `object_begin()`,
  `object_end()`, `array_begin()`, `array_end()` each write one piece of compact json, with the comma a value
  needs before it; `clear()` forgets the comma state so a new document may start.
The functions `json_writer_<name>_<piece>`, `_new` and `_free` are dependencies.

`slice_reader` is a reader over bytes in memory: `{read, new, free}`, where `new((ptr, len))` yields the value
`read` takes (a block holding the pointer, the length and the position) and `free` releases it. `vec_writer` is a
sink appending to a byte vec: `{write}`, taking the vec's pointer. Both are dependencies (`json_slice_reader_*`,
`json_vec_writer_write`).
"""

from ..collections.vec import const_type_arg
from ..core import values
from ..eco_mb import p
from ..memory import destructor
from ..target_mb import (
    a,
    acc,
    and_b,
    asp_id,
    asp_iface,
    bim,
    body,
    bool_t,
    call_result,
    can_cast_from_self,
    cast_from_self,
    cast_to_panic,
    cast_value,
    code_none,
    code_seq,
    const_eval_in,
    const_fn,
    cv_of,
    cve_code,
    cve_has,
    cve_t,
    cve_type,
    cve_value,
    def_iface,
    def_obj,
    err_cve,
    graft,
    has,
    has_b,
    ident_of,
    in_,
    is_equal,
    loc,
    lookup,
    lookup_v,
    lv,
    mk,
    no_cast_to,
    ok_cve,
    or_b,
    outer,
    ret_m,
    rt_bind_impl,
    rt_dispatch,
    rt_lift_impl,
    rt_use_impl,
    self_type,
    str_,
    t,
    ty,
    ty_desc,
    type_aspect,
    unwrap_cve_m,
    unwrap_m,
    xx,
)
from . import json

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "json-wasm.atz", LLVM: "json-llvm.atz"}

# The parser header: three pointer slots (the reader's argument, the data vec, the stack vec; 8 bytes each on
# llvm, 4 on wasm) from byte 0, then the registers as i32 cells from byte 24.
PTR_SLOT = {"ctx": 0, "data": 1, "stack": 2}
REGISTER_CELL = {name: 6 + i for i, name in enumerate(json.REGISTERS)}
HEADER = 64

# The writer header: the sink's argument, then the comma state.
PENDING_CELL = 2
WRITER_HEADER = 16

EVENTS = json.EVENTS
SLICE_EVENTS = ["number", "string", "key"]
INT_EVENTS = ["error", "bool"]
# What the event type carries: the target's i32, the byte pointer type, the target's unit (the payload type of the
# bare variants), the tuple type `(i32 tag, ptr(u8) data, i32 len, i32 value)` the event is a view of, and the
# byte slice constructor (the payload of number, string and key is a slice).
EVENT_BASE = ["i32", "pu8", "unit", "pt", "slice_of"]

WRITER_PIECES = {
    "null": [],
    "bool": ["v"],
    "int": ["v"],
    "number": ["ptr", "len"],
    "string": ["ptr", "len"],
    "key": ["ptr", "len"],
    "object_begin": [],
    "object_end": [],
    "array_begin": [],
    "array_end": [],
}
WRITER_METHODS = list(WRITER_PIECES) + ["clear"]
WRITER_FIELDS = ["pv", "pi32", "ppv"] + list(WRITER_PIECES)

# Stage depths, as in vec.py: the dependencies are made in the const function's host body and their bodies are
# staged there, so a body sees the host locals one lower up and module-level values two up; the setup staged in the
# caller's context also sits one below the host body.
BODY_MOD = 2
BODY_HOST = 1
SETUP_MOD = 2


def _up(e, expr, depth):
    for _ in range(depth):
        expr = e.lower(expr)
    return expr


class _Target:
    """What differs between the wasm and llvm modules: imports, the allocator, sizes, pointer width, null."""

    def __init__(self, kind):
        self.kind = kind

    def imports(self, e, out):
        if self.kind == WASM:
            out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
            out.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
        else:
            out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))
            out.append(e.let("heap", e.import_local("libc", "libc-2.42.atz")))
        out.append(e.let("slice", e.import_local("slice", "slice-" + self.kind + ".atz")))
        out.append(e.let("vec", e.import_local("vec", "vec-" + self.kind + ".atz")))

    def module_lets(self, e, out):
        """Module-level types the null reference needs."""
        if self.kind == LLVM:
            out.append(
                e.let(
                    "pu8_gt",
                    e.call(e.fld(e.v("lib"), "global_t"), e.rec(p("ty", e.v("pu8")), p("mem", e.b(False)))),
                )
            )

    def null_let(self, e, out, depth):
        """In host code `depth` below the module: llvm's null byte pointer (a reference whose type must be a
        constant there)."""
        if self.kind == LLVM:
            out.append(
                e.let(
                    "null_v",
                    e.call(
                        _up(e, e.fld(e.v("lib"), "ref_fn"), depth),
                        e.rec(p("ref", e.s("null")), p("ty", _up(e, e.v("pu8_gt"), depth))),
                    ),
                )
            )

    def null(self, e, pu8):
        """The null byte pointer in staged code one below host code that ran `null_let`; `pu8` is the lowered
        pointer type."""
        if self.kind == WASM:
            return e.mb.as_(e.n(0), pu8)
        return e.mb.as_(_up(e, e.v("null_v"), BODY_HOST), pu8)

    def size(self, e, n, depth):
        """`n` as the allocator's size argument."""
        if self.kind == WASM:
            return n
        return e.call(_up(e, e.fld(e.v("lib"), "u64"), depth), n)

    def malloc(self, e, n, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "malloc"), depth), self.size(e, n, depth))

    def free(self, e, ptr, depth):
        return e.call(_up(e, e.fld(e.v("heap"), "free"), depth), ptr)


def _staged(e, expr):
    return unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(expr)))


def _codes(e, *codes):
    return unwrap_m(e, code_seq(e, *codes), e.mb.types_cve())


def _retag(e, cv, typ):
    """The runtime value of `cv` (a variable reference) viewed as `typ` (values.atz), with the code of `cv`."""
    retag = e.lower(e.fld(e.v("values"), "retag"))
    return cv_of(
        e,
        cve_code(e, cv),
        bim(e, retag, "retag", e.call(e.mb.must_reinterpret(), e.tup(cve_value(e, cv), retag)), typ),
    )


def _variant(e, key, type_):
    return e.call(
        e.eval_builtin("aspect_union_variant"),
        e.rec(p("key", e.mb.as_(e.s(key), e.mb.types_constkey())), p("type", type_)),
    )


def _pcell(e, h, slot, depth):
    """Pointer slot `slot` of the header `h` (a ptr(void) place)."""
    return e.mb.field(e.mb.as_(h, _up(e, e.v("ppv"), depth)), e.n(slot))


def _cell(e, h, index, depth):
    """i32 cell `index` of the header `h`."""
    return e.mb.field(e.mb.as_(h, _up(e, e.v("pi32"), depth)), e.n(index))


def _handle_type(e, x, obj, iface, desc, fields, places, methods, under="pv"):
    """A handle type over a representation (the field `under`: a pointer, or a tuple): its field aspect gives the
    places (`places` maps a name to the staged place over `self_as`, the handle as one of its types) and the methods;
    it delegates the rest to the representation and retags from its values."""
    def_iface(e, x, iface, *fields)
    def_obj(e, x, obj, desc, e.rec(*fields))
    x.append(e.impl_interface(e.v(obj), t(e, iface), *[p(k, in_(e, k)) for k, _ in fields]))
    self_type(
        e,
        x,
        obj,
        e.s(desc),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, iface + "_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
            ],
            type_aspect(e, xx(e), in_(e, under), a(e, "key")),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    is_equal(e, xx(e), in_(e, under), a(e, "source_type")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.match_of(
                e.call(
                    e.mb.reinterpret(),
                    e.tup(loc(e), cve_value(e, a(e, "cv")), e.lower(e.fld(e.v("values"), "retag"))),
                ),
                "__t",
                None,
                p(
                    "ok",
                    ret_m(
                        e,
                        ok_cve(
                            e,
                            cv_of(
                                e,
                                cve_code(e, a(e, "cv")),
                                bim(e, e.lower(e.fld(e.v("values"), "retag")), "retag", e.v("__t"), outer(e)),
                            ),
                        ),
                    ),
                ),
                p("errs", ret_m(e, err_cve(e, loc(e), desc + ": only runtime values can become one"))),
            ),
        ),
        e.mb.as_(e.b(False), bool_t(e)),
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), iface))),
    )
    meth = obj + "_meth"
    def_obj(e, x, meth, desc + " method", e.rec(p("kind", str_(e)), p("ht", ty(e)), p("self", e.mb.types_cve())))

    def self_as(type_field):
        return e.mb.as_(graft(e, a(e, "self")), e.lower(in_(e, type_field)))

    x.append(
        e.impl_interface(
            e.v(obj),
            asp_iface(e, "field"),
            p(
                "field",
                body(
                    e,
                    e.if_only(
                        e.not_(has_b(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const())),
                        ret_m(e, err_cve(e, loc(e), desc + ": field must be a constant string")),
                    ),
                    e.let(
                        "key",
                        bim(
                            e,
                            e.mb.eval_aspect_string_const(),
                            "get",
                            lookup_v(e, xx(e), cve_type(e, a(e, "key")), e.mb.eval_aspect_string_const()),
                            cve_value(e, a(e, "key")),
                        ),
                    ),
                    *[
                        e.if_only(e.eq(e.v("key"), e.s(name)), ret_m(e, ok_cve(e, _staged(e, place(self_as)))))
                        for name, place in places.items()
                    ],
                    *[
                        e.if_only(
                            e.eq(e.v("key"), e.s(m)),
                            ret_m(
                                e,
                                ok_cve(
                                    e,
                                    cv_of(
                                        e,
                                        cve_code(e, a(e, "self")),
                                        e.call(
                                            e.eval_builtin("value_object_const"),
                                            e.rec(
                                                p(
                                                    "type",
                                                    mk(
                                                        e,
                                                        meth,
                                                        p("kind", e.s(m)),
                                                        p("ht", outer(e)),
                                                        p(
                                                            "self",
                                                            cv_of(
                                                                e,
                                                                e.call(e.eval_builtin("code_none"), loc(e)),
                                                                cve_value(e, a(e, "self")),
                                                            ),
                                                        ),
                                                    ),
                                                ),
                                                p("data", e.tup()),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        )
                        for m in methods
                    ],
                    e.ret(err_cve(e, loc(e), e.cat(e.s(desc + " has no field "), e.v("key")))),
                ),
            ),
            p("type_opt", e.option_type_lowered_none()),
            p(
                "keys",
                e.list_new(
                    e.mb.types_constkey(),
                    *[e.mb.as_(e.s(k), e.mb.types_constkey()) for k in list(places) + methods],
                ),
            ),
        )
    )
    no = e.mb.as_(e.b(False), bool_t(e))
    self_type(
        e,
        x,
        meth,
        e.cat(e.s(desc + "."), in_(e, "kind")),
        e.aspect_dispatch(asp_id(e, "function")),
        no,
        cast_to_panic(e),
        no,
        cast_to_panic(e),
        no,
    )
    return meth


def _method_impl(e, x, meth, iface, fields, methods, method_body, prelude=()):
    """The call of a handle method: `method_body(kind)` is the staged operation over the handle's fields (host
    locals of the field names) and `self_v`, the handle value; `prelude` are host statements run first."""

    def dispatch(kind):
        return e.if_only(e.eq(in_(e, "kind"), e.s(kind)), e.seq(*call_result(e, _staged(e, method_body(kind)))))

    x.append(
        e.impl_interface(
            e.v(meth),
            asp_iface(e, "function"),
            p(
                "call",
                body(
                    e,
                    *[e.let(f, acc(e, xx(e), in_(e, "ht"), iface, f)) for f, _ in fields],
                    *prelude,
                    *[dispatch(kind) for kind in methods],
                    e.ret(err_cve(e, loc(e), e.cat(e.s("json: unknown method "), in_(e, "kind")))),
                ),
            ),
            p("exception_type", e.option_type_lowered_none()),
        )
    )


def _self_v(e, type_field="pv"):
    """The handle value in a method body's staged code."""
    return e.mb.as_(graft(e, in_(e, "self")), e.lower(e.v(type_field)))


def _event_objs(e, x, tg):
    """The event union type `evt` over the tuple `pt`, and its constructors `evc` (one callable per variant)."""
    base_fields = [p(f, ty(e)) for f in EVENT_BASE]
    evc_fields = [p("kind", str_(e))] + base_fields
    def_iface(e, x, "evc_m", *evc_fields)
    def_obj(e, x, "evc", "json event constructor", e.rec(*evc_fields))
    def_iface(e, x, "evt_m", *base_fields)
    def_obj(e, x, "evt", "json event type", e.rec(*base_fields))
    no = no_cast_to(e)

    x.append(e.impl_interface(e.v("evc"), t(e, "evc_m"), *[p(f, in_(e, f)) for f, _ in evc_fields]))
    self_type(
        e,
        x,
        "evc",
        e.cat(e.s("json.event."), in_(e, "kind")),
        rt_dispatch(e, e.mb.types_string(), e.aspect_dispatch(asp_id(e, "function"))),
        can_cast_from_self(e),
        cast_from_self(e),
        no,
        cast_to_panic(e),
        body(
            e,
            e.ret(
                and_b(
                    e,
                    has(e, xx(e), a(e, "other"), "evc_m"),
                    e.eq(in_(e, "kind"), acc(e, xx(e), a(e, "other"), "evc_m", "kind")),
                )
            ),
        ),
    )
    rt_lift_impl(e, x, "evc")
    rt_bind_impl(e, x, "evc", e.mb.types_string())
    rt_use_impl(e, x, "evc")

    def result(tuple_cv):
        """Ends a constructor call: the tuple `tuple_cv` viewed as the event type, after the callee's own code."""
        return e.seq(
            e.let("tv", tuple_cv),
            e.let("ev", _retag(e, e.v("tv"), mk(e, "evt", *[p(f, in_(e, f)) for f in EVENT_BASE]))),
            ret_m(
                e,
                ok_cve(
                    e,
                    cv_of(e, _codes(e, cve_code(e, a(e, "self")), cve_code(e, e.v("ev"))), cve_value(e, e.v("ev"))),
                ),
            ),
        )

    def tag(kind):
        return e.n(EVENTS.index(kind))

    def as_pt(tuple_expr):
        return e.mb.as_(tuple_expr, e.lower(in_(e, "pt")))

    def ctor(kind):
        if kind in SLICE_EVENTS:
            # The argument is a slice: a pair of a pointer and a length, read once through a binding.
            return result(
                _staged(
                    e,
                    e.mb.labeled(
                        "ev",
                        e.seq(
                            e.let("s", graft(e, a(e, "argument"))),
                            e.mb.return_to(
                                "ev",
                                as_pt(e.tup(tag(kind), e.fld(e.v("s"), "data"), e.fld(e.v("s"), "len"), e.n(0))),
                            ),
                        ),
                    ),
                )
            )
        if kind in INT_EVENTS:
            return e.seq(
                e.let("c", unwrap_cve_m(e, cast_value(e, xx(e), loc(e), in_(e, "i32"), a(e, "argument")))),
                result(
                    _staged(
                        e, as_pt(e.tup(tag(kind), tg.null(e, e.lower(in_(e, "pu8"))), e.n(0), graft(e, e.v("c"))))
                    )
                ),
            )
        return e.seq(
            e.let("z", _staged(e, as_pt(e.tup(tag(kind), tg.null(e, e.lower(in_(e, "pu8"))), e.n(0), e.n(0))))),
            result(
                cv_of(e, _codes(e, cve_code(e, a(e, "argument")), cve_code(e, e.v("z"))), cve_value(e, e.v("z")))
            ),
        )

    parts = []
    tg.null_let(e, parts, 1)
    for kind in EVENTS:
        parts.append(e.if_only(e.eq(in_(e, "kind"), e.s(kind)), ctor(kind)))
    parts.append(e.ret(err_cve(e, loc(e), e.cat(e.s("json: unknown event "), in_(e, "kind")))))
    x.append(
        e.impl_interface(
            e.v("evc"),
            e.eval_builtin("aspect_function"),
            p("call", body(e, *parts)),
            p("exception_type", e.option_type_lowered_none()),
        )
    )

    # The event type: the tuple's aspects, except that it has no components and matches as a union.
    x.append(e.impl_interface(e.v("evt"), t(e, "evt_m"), *[p(f, in_(e, f)) for f in EVENT_BASE]))
    self_type(
        e,
        x,
        "evt",
        e.s("json.event"),
        e.mb.if_of(
            [
                (e.eq(a(e, "key"), asp_id(e, "union")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), lv(e, "evt_m_id")), e.opt_some(e.mb.types_aspect(), outer(e))),
                (e.eq(a(e, "key"), asp_id(e, "field")), e.opt_none(e.mb.types_aspect())),
            ],
            type_aspect(e, xx(e), in_(e, "pt"), a(e, "key")),
        ),
        body(
            e,
            e.ret(
                or_b(
                    e,
                    is_equal(e, xx(e), outer(e), a(e, "source_type")),
                    is_equal(e, xx(e), in_(e, "pt"), a(e, "source_type")),
                )
            ),
        ),
        body(
            e,
            e.if_only(is_equal(e, xx(e), outer(e), cve_type(e, a(e, "cv"))), ret_m(e, ok_cve(e, a(e, "cv")))),
            e.if_only(
                e.not_(is_equal(e, xx(e), in_(e, "pt"), cve_type(e, a(e, "cv")))),
                ret_m(e, err_cve(e, loc(e), "json: only the event tuple can become an event")),
            ),
            e.ret(ok_cve(e, _retag(e, a(e, "cv"), outer(e)))),
        ),
        no,
        cast_to_panic(e),
        body(e, e.ret(has(e, xx(e), a(e, "other"), "evt_m"))),
    )

    def payload_type(kind):
        if kind in SLICE_EVENTS:
            return in_(e, "slice_of")
        if kind in INT_EVENTS:
            return in_(e, "i32")
        return in_(e, "unit")

    def tuple_of(base_cv):
        return _retag(e, base_cv, in_(e, "pt"))

    def extract(kind):
        if kind in SLICE_EVENTS:
            payload = e.call(
                e.lower(in_(e, "slice_of")),
                e.tup(e.mb.field(graft(e, e.v("tv")), e.n(1)), e.mb.field(graft(e, e.v("tv")), e.n(2))),
            )
            return ret_m(e, e.eresult_ok(cve_t(e), _staged(e, payload)))
        if kind in INT_EVENTS:
            return ret_m(e, e.eresult_ok(cve_t(e), _staged(e, e.mb.field(graft(e, e.v("tv")), e.n(3)))))
        return ret_m(
            e,
            e.eresult_ok(
                cve_t(e),
                cv_of(
                    e,
                    code_none(e, loc(e)),
                    e.call(
                        e.eval_builtin("value_object_const"),
                        e.rec(p("type", in_(e, "unit")), p("data", e.tup())),
                    ),
                ),
            ),
        )

    x.append(
        e.impl_interface(
            e.v("evt"),
            e.eval_builtin("aspect_union"),
            p(
                "variants",
                e.list_new(
                    e.mb.builtin("types", "aspect_union_variant"),
                    *[_variant(e, kind, payload_type(kind)) for kind in EVENTS],
                ),
            ),
            p(
                "test",
                body(
                    e,
                    e.let("tv", tuple_of(a(e, "base"))),
                    e.let("vi", a(e, "variant_index")),
                    e.ret(
                        e.eresult_ok(
                            cve_t(e),
                            _staged(e, e.eq(e.mb.field(graft(e, e.v("tv")), e.n(0)), e.lower(e.v("vi")))),
                        )
                    ),
                ),
            ),
            p(
                "extract",
                body(
                    e,
                    e.let("tv", tuple_of(a(e, "base"))),
                    *[e.if_only(e.eq(a(e, "variant_index"), e.int_of(i)), extract(kind)) for i, kind in enumerate(EVENTS)],
                    e.ret(err_cve(e, loc(e), "json: no such event variant")),
                ),
            ),
        )
    )


def _dep(e, out, name, fn, fn_t, params, fbody):
    """In a const function's host body: the dependency `<name>_<fn>` with the host-level type `fn_t`."""
    out.append(
        e.let(
            fn,
            e.call(
                e.lower(e.fld(e.v("lib"), "func_dep")),
                e.rec(
                    p("name", e.cat(e.v(name), e.s("_" + fn))),
                    p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                    p("ty", fn_t),
                    p("body", e.stage(fbody)),
                ),
            ),
        )
    )


def _fn_t(e, params, ret, depth):
    """A function type over host-level types, `depth` below the module."""
    return e.call(
        _up(e, e.fld(e.v("lib"), "fn"), depth),
        e.rec(p("params", e.list_new(e.mb.eval_type(), *params)), p("ret", ret)),
    )


# ---- byte buffers and views: what json.atz touches bytes through ----

BUF_FIELDS = ["pv", "pi32", "ppv", "bytes_raw", "i32", "u8"]
BUF_METHODS = ["push", "clear", "pop", "len", "at", "slice"]
VIEW_FIELDS = ["pu8", "i32", "pt2"]
VIEW_METHODS = ["len", "at"]


def _buffer_types(e, x):
    """`jbuf`, a byte vec's pointer with json.atz's buffer methods (bytes as ints), and `jview`, a (pointer, length)
    tuple with its view methods."""
    fields = [p(f, ty(e)) for f in BUF_FIELDS]
    meth = _handle_type(e, x, "jbuf", "jbuf_m", "json byte buffer", fields, {}, BUF_METHODS)

    def vec():
        return e.mb.as_(_self_v(e), e.lower(e.v("bytes_raw")))

    def buf_body(kind):
        if kind == "push":
            return e.call(e.fld(vec(), "push"), e.call(e.lower(e.v("u8")), graft(e, a(e, "argument"))))
        if kind == "clear":
            return e.call(e.fld(vec(), "clear"), e.tup())
        if kind == "pop":
            return e.mb.set(e.fld(vec(), "len"), e.mb.operator_sub(e.fld(vec(), "len"), e.n(1)))
        if kind == "len":
            return e.fld(vec(), "len")
        if kind == "at":
            return e.call(e.lower(e.v("i32")), e.call(e.fld(vec(), "at"), graft(e, a(e, "argument"))))
        if kind == "slice":
            return e.call(e.fld(vec(), "slice"), e.tup())
        raise AssertionError(kind)

    _method_impl(e, x, meth, "jbuf_m", fields, BUF_METHODS, buf_body)

    fields = [p(f, ty(e)) for f in VIEW_FIELDS]
    meth = _handle_type(e, x, "jview", "jview_m", "json byte view", fields, {}, VIEW_METHODS, under="pt2")

    def tv():
        return graft(e, e.v("tv"))

    def view_body(kind):
        if kind == "len":
            return e.mb.field(tv(), e.n(1))
        if kind == "at":
            return e.call(
                e.lower(e.v("i32")),
                e.mb.field(e.mb.as_(e.mb.field(tv(), e.n(0)), e.lower(e.v("pu8"))), graft(e, a(e, "argument"))),
            )
        raise AssertionError(kind)

    _method_impl(
        e, x, meth, "jview_m", fields, VIEW_METHODS, view_body, prelude=[e.let("tv", _retag(e, in_(e, "self"), e.v("pt2")))]
    )


# ---- the parser ----

PARSER_FIELDS = ["pv", "pi32", "ppv", "buf", "next"]


def _parser_new_body(e, tg):
    d = BODY_MOD
    stmts = [
        e.let("h", tg.malloc(e, e.n(HEADER), d)),
        e.mb.set(_pcell(e, e.v("h"), PTR_SLOT["ctx"], d), e.v("ctx")),
        e.mb.set(_pcell(e, e.v("h"), PTR_SLOT["data"], d), e.call(_up(e, e.v("bytes_new"), d), e.tup())),
        e.mb.set(_pcell(e, e.v("h"), PTR_SLOT["stack"], d), e.call(_up(e, e.v("bytes_new"), d), e.tup())),
    ]
    for name, index in REGISTER_CELL.items():
        stmts.append(e.mb.set(_cell(e, e.v("h"), index, d), e.n(json.UNREAD if name == "c" else 0)))
    stmts.append(e.ret(e.v("h")))
    return e.seq(*stmts)


def _parser_free_body(e, tg):
    d = BODY_MOD

    def owned_vec(slot):
        return e.call(
            _up(e, e.v("bytes_type"), d),
            e.mb.as_(_pcell(e, e.v("p"), slot, d), _up(e, e.v("bytes_raw"), d)),
        )

    return e.seq(
        e.seq(e.let("data", owned_vec(PTR_SLOT["data"])), e.let("stack", owned_vec(PTR_SLOT["stack"]))),
        tg.free(e, e.v("p"), d),
    )


def _parser_next_body(e, tg):
    d = BODY_MOD
    ops = [
        p("int", _up(e, e.v("i32"), d)),
        p("read", _up(e, e.v("read"), BODY_HOST)),
        p("event", e.rec(*[p(kind, _up(e, e.v("ev_" + kind), BODY_HOST)) for kind in EVENTS])),
        p("p", e.mb.as_(e.v("p"), _up(e, e.v("places"), BODY_HOST))),
    ]
    return e.seq(e.ret(e.call(_up(e, e.fld(e.v("json"), "next"), d), e.rec(*ops))))


def _parser_setup(e):
    """Staged in the caller's context: the parser types over the lowered dependencies, and the events."""
    out = []
    for name in ["new", "free", "next", "event_t"] + ["ev_" + kind for kind in EVENTS]:
        out.append(e.let(name, e.lower(e.v(name))))
    for name in ["pv", "pi32", "ppv"]:
        out.append(e.let(name, _up(e, e.v(name), SETUP_MOD)))
    out.append(e.let("buf", e.lower(e.v("buf"))))
    out.append(
        e.let(
            "raw",
            e.mb.as_(
                e.call(_up(e, e.fld(e.v("jpt"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in PARSER_FIELDS])),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(
        e.let(
            "owned",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", e.v("free"))),
            ),
        )
    )
    out.append(
        e.ret(
            e.rec(
                p("type", e.v("owned")),
                p("raw", e.v("raw")),
                p("new", e.v("new")),
                p("event", e.rec(p("type", e.v("event_t")), *[p(kind, e.v("ev_" + kind)) for kind in EVENTS])),
            )
        )
    )
    return e.mb.seq(out)


def _handle_places(e, slots, cells, vec_slots=()):
    """The places of a handle: pointer slots (ptr(void)), i32 cells, and byte vecs in pointer slots."""
    places = {}
    for name, slot in slots.items():
        places[name] = lambda self_as, slot=slot: e.mb.field(self_as("ppv"), e.n(slot))
    for name, index in cells.items():
        places[name] = lambda self_as, index=index: e.mb.field(self_as("pi32"), e.n(index))
    for name, slot in vec_slots:
        places[name] = lambda self_as, slot=slot: e.mb.as_(e.mb.field(self_as("ppv"), e.n(slot)), e.lower(in_(e, "buf")))
    return places


def _parser_const_fn(e, x, tg):
    fields = [p(f, ty(e)) for f in PARSER_FIELDS]
    places = _handle_places(
        e, {"ctx": PTR_SLOT["ctx"]}, REGISTER_CELL, [("data", PTR_SLOT["data"]), ("stack", PTR_SLOT["stack"])]
    )
    meth = _handle_type(e, x, "jpt", "jpt_m", "json parser", fields, places, ["next"])

    def method_body(kind):
        return e.call(e.lower(e.v("next")), _self_v(e))

    _method_impl(e, x, meth, "jpt_m", fields, ["next"], method_body)

    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "json.parser: argument has no value"))),
        e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
        e.if_only(
            e.not_(e.fld(e.v("rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "json.parser: argument must be {name, read}")),
        ),
        e.let(
            "fields",
            bim(
                e,
                asp_iface(e, "record"),
                "take_fields",
                e.fld(e.v("rk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, e.v("argv")))),
            ),
        ),
        e.let("readcv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("read")))),
        e.if_only(e.not_(cve_has(e, e.v("readcv"))), ret_m(e, err_cve(e, loc(e), "json.parser: read has no value"))),
        e.let("namecv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("name")))),
        e.if_only(
            e.not_(has_b(e, xx(e), cve_type(e, e.v("namecv")), e.mb.eval_aspect_string_const())),
            ret_m(e, err_cve(e, loc(e), "json.parser: name must be a constant string")),
        ),
        # The reader is called from the next dependency, so it must be a constant callable (a dependency, a function
        # or an import), which is a callable type.
        *const_type_arg(e, "json.parser", e.v("readcv"), "read"),
        e.let(
            "name",
            e.cat(
                e.s("json_parser_"),
                ident_of(
                    e,
                    bim(
                        e,
                        e.mb.eval_aspect_string_const(),
                        "get",
                        lookup_v(e, xx(e), cve_type(e, e.v("namecv")), e.mb.eval_aspect_string_const()),
                        cve_value(e, e.v("namecv")),
                    ),
                ),
            ),
        ),
    ]
    for name in EVENT_BASE + ["pv", "void"]:
        parts.append(e.let(name, e.lower(e.v(name))))
    tg.null_let(e, parts, 1)
    parts.append(
        e.let(
            "event_t",
            e.mb.as_(
                e.call(e.lower(e.fld(e.v("evt"), "new")), e.rec(*[p(f, e.v(f)) for f in EVENT_BASE])),
                e.mb.eval_type(),
            ),
        )
    )
    for kind in EVENTS:
        parts.append(
            e.let(
                "ev_" + kind,
                e.mb.as_(
                    e.call(
                        e.lower(e.fld(e.v("evc"), "new")),
                        e.rec(p("kind", e.s(kind)), *[p(f, e.v(f)) for f in EVENT_BASE]),
                    ),
                    e.mb.eval_type(),
                ),
            )
        )
    parts.append(e.let("new_t", _fn_t(e, [e.v("pv")], e.v("pv"), 1)))
    parts.append(e.let("free_t", _fn_t(e, [e.v("pv")], e.v("void"), 1)))
    parts.append(e.let("next_t", _fn_t(e, [e.v("pv")], e.v("event_t"), 1)))
    for name in ["pi32", "ppv", "bytes_raw", "u8"]:
        parts.append(e.let(name, e.lower(e.v(name))))
    parts.append(
        e.let(
            "buf",
            e.mb.as_(
                e.call(e.lower(e.fld(e.v("jbuf"), "new")), e.rec(*[p(f, e.v(f)) for f in BUF_FIELDS])), e.mb.eval_type()
            ),
        )
    )
    # The handle the dependencies use for the state's places: it never calls `next`, so that field is a stand-in.
    parts.append(
        e.let(
            "places",
            e.mb.as_(
                e.call(
                    e.lower(e.fld(e.v("jpt"), "new")),
                    e.rec(*[p(f, e.v(f)) for f in PARSER_FIELDS if f != "next"], p("next", e.v("pv"))),
                ),
                e.mb.eval_type(),
            ),
        )
    )
    _dep(e, parts, "name", "new", e.v("new_t"), ["ctx"], _parser_new_body(e, tg))
    _dep(e, parts, "name", "free", e.v("free_t"), ["p"], _parser_free_body(e, tg))
    _dep(e, parts, "name", "next", e.v("next_t"), ["p"], _parser_next_body(e, tg))
    parts.append(
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_parser_setup(e))))))
    )
    const_fn(e, x, "parser_b", "json.parser", body(e, *parts))


# ---- the writer ----


def _writer_piece_body(e, tg, piece):
    d = BODY_MOD
    ops = [
        p("write", _up(e, e.v("write"), BODY_HOST)),
        p("w", e.mb.as_(e.v("w"), _up(e, e.v("places"), BODY_HOST))),
    ]
    params = WRITER_PIECES[piece]
    if piece != "bool" and params:
        ops.append(p("int", _up(e, e.v("i32"), d)))
    if params == ["v"]:
        ops.append(p("value", e.v("v")))
    if params != ["ptr", "len"]:
        return e.call(_up(e, e.fld(e.v("json"), "write_" + piece), d), e.rec(*ops))
    # The view is bound first: json.atz splices `s` wherever it touches the bytes, so it must carry no code.
    ops.append(p("s", e.v("sv")))
    call = e.call(_up(e, e.fld(e.v("json"), "write_" + piece), d), e.rec(*ops))
    return e.seq(
        e.let(
            "sv",
            e.mb.as_(e.mb.as_(e.tup(e.v("ptr"), e.v("len")), _up(e, e.v("pt2"), d)), _up(e, e.v("view"), BODY_HOST)),
        ),
        call,
    )


def _writer_new_body(e, tg):
    d = BODY_MOD
    return e.seq(
        e.let("h", tg.malloc(e, e.n(WRITER_HEADER), d)),
        e.mb.set(_pcell(e, e.v("h"), 0, d), e.v("ctx")),
        e.mb.set(_cell(e, e.v("h"), PENDING_CELL, d), e.n(0)),
        e.ret(e.v("h")),
    )


def _writer_setup(e):
    out = []
    for name in ["new", "free"] + list(WRITER_PIECES):
        out.append(e.let(name, e.lower(e.v(name))))
    for name in ["pv", "pi32", "ppv"]:
        out.append(e.let(name, _up(e, e.v(name), SETUP_MOD)))
    out.append(
        e.let(
            "raw",
            e.mb.as_(
                e.call(_up(e, e.fld(e.v("jwt"), "new"), SETUP_MOD), e.rec(*[p(f, e.v(f)) for f in WRITER_FIELDS])),
                e.mb.eval_type(),
            ),
        )
    )
    out.append(
        e.let(
            "owned",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("raw")), p("destroy", e.v("free"))),
            ),
        )
    )
    out.append(e.ret(e.rec(p("type", e.v("owned")), p("raw", e.v("raw")), p("new", e.v("new")))))
    return e.mb.seq(out)


def _writer_const_fn(e, x, tg):
    fields = [p(f, ty(e)) for f in WRITER_FIELDS]
    places = _handle_places(e, {"ctx": 0}, {"pending": PENDING_CELL})
    meth = _handle_type(e, x, "jwt", "jwt_m", "json writer", fields, places, WRITER_METHODS)

    def method_body(kind):
        if kind == "clear":
            return e.mb.set(e.mb.field(_self_v(e, "pi32"), e.n(PENDING_CELL)), e.n(0))
        params = WRITER_PIECES[kind]
        dep = e.lower(e.v(kind))
        if not params:
            return e.call(dep, _self_v(e))
        if params == ["v"]:
            return e.call(dep, e.tup(_self_v(e), graft(e, a(e, "argument"))))
        return e.seq(
            e.let("s", graft(e, a(e, "argument"))),
            e.call(dep, e.tup(_self_v(e), e.fld(e.v("s"), "data"), e.fld(e.v("s"), "len"))),
        )

    _method_impl(e, x, meth, "jwt_m", fields, WRITER_METHODS, method_body)

    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "json.writer: argument has no value"))),
        e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
        e.if_only(
            e.not_(e.fld(e.v("rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "json.writer: argument must be {name, write}")),
        ),
        e.let(
            "fields",
            bim(
                e,
                asp_iface(e, "record"),
                "take_fields",
                e.fld(e.v("rk"), "value"),
                e.rec(p("xx", xx(e)), p("loc", loc(e)), p("value", cve_value(e, e.v("argv")))),
            ),
        ),
        e.let("writecv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("write")))),
        e.if_only(e.not_(cve_has(e, e.v("writecv"))), ret_m(e, err_cve(e, loc(e), "json.writer: write has no value"))),
        e.let("namecv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s("name")))),
        e.if_only(
            e.not_(has_b(e, xx(e), cve_type(e, e.v("namecv")), e.mb.eval_aspect_string_const())),
            ret_m(e, err_cve(e, loc(e), "json.writer: name must be a constant string")),
        ),
        *const_type_arg(e, "json.writer", e.v("writecv"), "write"),
        e.let(
            "name",
            e.cat(
                e.s("json_writer_"),
                ident_of(
                    e,
                    bim(
                        e,
                        e.mb.eval_aspect_string_const(),
                        "get",
                        lookup_v(e, xx(e), cve_type(e, e.v("namecv")), e.mb.eval_aspect_string_const()),
                        cve_value(e, e.v("namecv")),
                    ),
                ),
            ),
        ),
    ]
    for name in ["pv", "pu8", "i32", "void"]:
        parts.append(e.let(name, e.lower(e.v(name))))
    parts.append(e.let("new_t", _fn_t(e, [e.v("pv")], e.v("pv"), 1)))
    parts.append(e.let("w_t", _fn_t(e, [e.v("pv")], e.v("void"), 1)))
    for name in ["pi32", "ppv", "pt2"]:
        parts.append(e.let(name, e.lower(e.v(name))))
    parts.append(
        e.let(
            "view",
            e.mb.as_(
                e.call(e.lower(e.fld(e.v("jview"), "new")), e.rec(*[p(f, e.v(f)) for f in VIEW_FIELDS])),
                e.mb.eval_type(),
            ),
        )
    )
    # The handle the dependencies use for the state's places: it never calls the pieces, so those are stand-ins.
    parts.append(
        e.let(
            "places",
            e.mb.as_(
                e.call(
                    e.lower(e.fld(e.v("jwt"), "new")),
                    e.rec(*[p(f, e.v(f)) for f in ["pv", "pi32", "ppv"]], *[p(k, e.v("pv")) for k in WRITER_PIECES]),
                ),
                e.mb.eval_type(),
            ),
        )
    )
    parts.append(e.let("wi_t", _fn_t(e, [e.v("pv"), e.v("i32")], e.v("void"), 1)))
    parts.append(e.let("ws_t", _fn_t(e, [e.v("pv"), e.v("pu8"), e.v("i32")], e.v("void"), 1)))
    _dep(e, parts, "name", "new", e.v("new_t"), ["ctx"], _writer_new_body(e, tg))
    _dep(e, parts, "name", "free", e.v("w_t"), ["w"], tg.free(e, e.v("w"), BODY_MOD))
    for piece, params in WRITER_PIECES.items():
        fn_t = {0: "w_t", 1: "wi_t", 2: "ws_t"}[len(params)]
        _dep(e, parts, "name", piece, e.v(fn_t), ["w"] + params, _writer_piece_body(e, tg, piece))
    parts.append(
        e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_writer_setup(e))))))
    )
    const_fn(e, x, "writer_b", "json.writer", body(e, *parts))


# ---- a reader over memory and a sink into a vec ----

SR_LEN_CELL = 2
SR_POS_CELL = 3
SR_HEADER = 16


def _readers(e, x, tg):
    """The slice reader and vec writer dependencies, module-level values (their bodies see the module one up)."""
    d = 1

    def dep(name, fn_t, params, fbody):
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("lib"), "func_dep"),
                    e.rec(
                        p("name", e.s(name)),
                        p("params", e.list_new(e.mb.types_string(), *[e.s(pn) for pn in params])),
                        p("ty", e.v(fn_t)),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )

    x.append(e.let("sr_read_t", _fn_t(e, [e.v("pv")], e.v("i32"), 0)))
    x.append(e.let("sr_new_t", _fn_t(e, [e.v("pu8"), e.v("i32")], e.v("pv"), 0)))
    x.append(e.let("sr_free_t", _fn_t(e, [e.v("pv")], e.v("void"), 0)))
    x.append(e.let("vw_write_t", _fn_t(e, [e.v("pv"), e.v("i32")], e.v("void"), 0)))
    dep(
        "json_slice_reader_read",
        "sr_read_t",
        ["r"],
        e.seq(
            e.let("b", e.mb.as_(e.n(-1), _up(e, e.v("i32"), d))),
            e.if_only(
                e.mb.operator_lt(_cell(e, e.v("r"), SR_POS_CELL, d), _cell(e, e.v("r"), SR_LEN_CELL, d)),
                e.seq(
                    e.mb.set(
                        e.v("b"),
                        e.call(
                            _up(e, e.v("i32"), d),
                            e.mb.field(
                                e.mb.as_(_pcell(e, e.v("r"), 0, d), _up(e, e.v("pu8"), d)),
                                _cell(e, e.v("r"), SR_POS_CELL, d),
                            ),
                        ),
                    ),
                    e.mb.set(
                        _cell(e, e.v("r"), SR_POS_CELL, d), e.mb.operator_add(_cell(e, e.v("r"), SR_POS_CELL, d), e.n(1))
                    ),
                ),
            ),
            e.ret(e.v("b")),
        ),
    )
    dep(
        "json_slice_reader_new",
        "sr_new_t",
        ["ptr", "len"],
        e.seq(
            e.let("r", tg.malloc(e, e.n(SR_HEADER), d)),
            e.mb.set(_pcell(e, e.v("r"), 0, d), e.v("ptr")),
            e.mb.set(_cell(e, e.v("r"), SR_LEN_CELL, d), e.v("len")),
            e.mb.set(_cell(e, e.v("r"), SR_POS_CELL, d), e.n(0)),
            e.ret(e.v("r")),
        ),
    )
    dep("json_slice_reader_free", "sr_free_t", ["r"], tg.free(e, e.v("r"), d))
    dep(
        "json_vec_writer_write",
        "vw_write_t",
        ["v", "b"],
        e.call(
            e.fld(e.mb.as_(e.v("v"), _up(e, e.v("bytes_raw"), d)), "push"),
            e.call(_up(e, e.v("u8"), d), e.v("b")),
        ),
    )
    x.append(
        e.let(
            "slice_reader",
            e.rec(
                p("read", e.v("json_slice_reader_read")),
                p("new", e.v("json_slice_reader_new")),
                p("free", e.v("json_slice_reader_free")),
            ),
        )
    )
    x.append(e.let("vec_writer", e.rec(p("write", e.v("json_vec_writer_write")))))


def module(e, kind):
    tg = _Target(kind)
    x = []
    tg.imports(e, x)
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("values", e.import_local("values", values.FILE)))
    x.append(e.let("json", e.import_local("json", json.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    for prim in ["i32", "u8", "void", "unit"]:
        x.append(e.let(prim, e.fld(e.v("lib"), prim)))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.v("i32"))))
    x.append(e.let("ppv", e.call(e.fld(e.v("lib"), "ptr"), e.v("pv"))))
    x.append(e.let("pu8", e.call(e.fld(e.v("lib"), "ptr"), e.v("u8"))))
    x.append(
        e.let(
            "pt",
            e.call(
                e.fld(e.v("lib"), "tuple"),
                e.list_new(e.mb.eval_type(), e.v("i32"), e.v("pu8"), e.v("i32"), e.v("i32")),
            ),
        )
    )
    x.append(e.let("pt2", e.call(e.fld(e.v("lib"), "tuple"), e.list_new(e.mb.eval_type(), e.v("pu8"), e.v("i32")))))
    tg.module_lets(e, x)
    x.append(e.let("bytes", e.call(e.fld(e.v("vec"), "type"), e.v("u8"))))
    for f in ["type", "raw", "new"]:
        x.append(e.let("bytes_" + f, e.fld(e.v("bytes"), f)))
    x.append(e.let("slice_of", e.fld(e.call(e.fld(e.v("slice"), "type"), e.v("u8")), "of")))
    _event_objs(e, x, tg)
    _buffer_types(e, x)
    _parser_const_fn(e, x, tg)
    _writer_const_fn(e, x, tg)
    _readers(e, x, tg)
    x.append(e.finish(e.v("d")))
    exports = ["parser", "writer", "slice_reader", "vec_writer"]
    x.append(
        e.ret(
            e.rec(
                p("parser", e.fld(e.v("parser_b"), "func")),
                p("writer", e.fld(e.v("writer_b"), "func")),
                p("slice_reader", e.v("slice_reader")),
                p("vec_writer", e.v("vec_writer")),
            )
        )
    )

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(*[p(n, e.fld(e.v("k"), n)) for n in exports])))
    return top
