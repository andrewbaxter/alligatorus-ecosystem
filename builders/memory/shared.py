"""shared-wasm.atz / shared-llvm.atz: reference-counted pointers over destructor.atz, one module per target.

`shared.type({under, destroy})` yields `{type, own, adopt, clone}`:
- `under` is a constant pointer type whose block starts with a 4-byte count that this module owns; `destroy` is a
  constant callable `fn(under) -> void` (a `func_dep` or an extern: the release dependency calls it, so it cannot be
  a module-bound function value) run when the count reaches zero;
- `adopt(p)` sets the count to 1 and yields `p`; `clone(p)` adds one and yields `p`; `as own` on either takes
  the result as an owned value (destructor.atz's adopting type: nothing else coerces into `type`);
- dropping an owned value runs `shared_<under>_release`, which subtracts one and, at zero, calls `destroy(p)` then
  frees the block through the target's allocator (wasm-alloc.atz or libc).
The three functions are dependencies (`func_dep`): a module gets them when its code first uses them.
"""

from . import destructor
from ..eco_mb import p
from ..target_mb import (
    a,
    asp_iface,
    bim,
    body,
    const_eval_in,
    const_fn,
    conv,
    cve_has,
    cve_type,
    cve_value,
    err_cve,
    fn_of,
    ident_of,
    loc,
    lookup,
    ret_m,
    ty_desc,
    unwrap_cve_m,
    xx,
)
from ..collections.vec import const_type_arg

WASM = "wasm"
LLVM = "llvm"

FILES = {WASM: "shared-wasm.atz", LLVM: "shared-llvm.atz"}

# Stage depths, as in vec.py: bodies are staged in the const function's host body.
BODY_MOD = 2
BODY_HOST = 1
SETUP_MOD = 2


def _up(e, expr, depth):
    for _ in range(depth):
        expr = e.lower(expr)
    return expr


def _lo(e, name):
    return e.lower(e.v(name))


def _imports(e, kind, out):
    if kind == WASM:
        out.append(e.let("lib", e.import_local("wasm", "wat-2.0.atz")))
        out.append(e.let("heap", e.import_local("wasm_alloc", "wasm-alloc.atz")))
    else:
        out.append(e.let("lib", e.import_local("llvm", "llvm-ir-22.atz")))
        out.append(e.let("heap", e.import_local("libc", "libc-2.42.atz")))


def _count_cell(e):
    """The count cell of the block `p` points at (the pointer types are host locals)."""
    return e.mb.field(conv(e, e.lower(e.v("ptr_cast")), e.v("p"), _lo(e, "pi32")), e.n(0))


def _release_body(e):
    return e.seq(
        e.let("n", e.mb.operator_sub(_count_cell(e), e.n(1))),
        e.if_else(
            e.eq(e.v("n"), e.n(0)),
            e.seq(
                e.call(fn_of(e, _up(e, e.v("destroy"), BODY_HOST)), e.v("p")),
                e.call(
                    _up(e, e.fld(e.v("heap"), "free"), BODY_MOD),
                    conv(e, e.lower(e.v("ptr_cast")), e.v("p"), _lo(e, "pv")),
                ),
            ),
            e.mb.set(_count_cell(e), e.v("n")),
        ),
    )


def _adopt_body(e):
    return e.seq(e.mb.set(_count_cell(e), e.n(1)), e.ret(e.v("p")))


def _clone_body(e):
    return e.seq(e.mb.set(_count_cell(e), e.mb.operator_add(_count_cell(e), e.n(1))), e.ret(e.v("p")))


def _fn_type(e, params, ret):
    return e.call(
        e.lower(e.fld(e.v("lib"), "fn")), e.rec(p("params", e.list_new(e.mb.eval_type(), *params)), p("ret", ret))
    )


def _setup(e):
    """Staged in the caller's context: the owned type over the lowered release dependency."""
    out = []
    for name in ["under", "release", "adopt", "clone"]:
        out.append(e.let(name, e.lower(e.v(name))))
    out.append(
        e.let(
            "owned_r",
            e.call(
                e.fld(_up(e, e.v("destructor"), SETUP_MOD), "type"),
                e.rec(p("under", e.v("under")), p("destroy", fn_of(e, e.v("release")))),
            ),
        )
    )
    out.append(
        e.ret(
            e.rec(
                p("type", e.fld(e.v("owned_r"), "type")),
                p("own", e.fld(e.v("owned_r"), "own")),
                p("adopt", fn_of(e, e.v("adopt"))),
                p("clone", fn_of(e, e.v("clone"))),
            )
        )
    )
    return e.mb.seq(out)


def module(e, kind):
    x = []
    _imports(e, kind, x)
    x.append(e.let("destructor", e.import_local("destructor", destructor.FILE)))
    x.append(e.let("d", e.define()))
    x.append(e.option_type_let())
    x.append(e.let("void", e.fld(e.v("lib"), "void")))
    x.append(e.let("pv", e.call(e.fld(e.v("lib"), "ptr"), e.v("void"))))
    x.append(e.let("pi32", e.call(e.fld(e.v("lib"), "ptr"), e.fld(e.v("lib"), "i32"))))
    x.append(e.let("ptr_cast", e.fld(e.v("lib"), "ptr_cast")))
    parts = [
        e.let("argv", a(e, "argument")),
        e.if_only(e.not_(cve_has(e, e.v("argv"))), ret_m(e, err_cve(e, loc(e), "shared.type: argument has no value"))),
        e.let("rk", lookup(e, xx(e), cve_type(e, e.v("argv")), asp_iface(e, "record"))),
        e.if_only(
            e.not_(e.fld(e.v("rk"), "is_some")),
            ret_m(e, err_cve(e, loc(e), "shared.type: argument must be {under, destroy}")),
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
    ]
    for name in ["under", "destroy"]:
        parts.append(e.let(name + "cv", unwrap_cve_m(e, e.call_m(e.v("fields"), "get", e.s(name)))))
        parts.append(
            e.if_only(
                e.not_(cve_has(e, e.v(name + "cv"))),
                ret_m(e, err_cve(e, loc(e), "shared.type: " + name + " has no value")),
            )
        )
    parts.extend(const_type_arg(e, "shared.type", e.v("undercv"), "under"))
    # The destroy function is called from the release dependency, so it must be a constant callable (a dependency
    # or an extern), which is a callable type.
    parts.extend(const_type_arg(e, "shared.type", e.v("destroycv"), "destroy"))
    parts.append(e.let("name", e.cat(e.s("shared_"), ident_of(e, ty_desc(e, e.v("under"))))))
    for tname in ["pv", "pi32", "ptr_cast"]:
        parts.append(e.let(tname, e.lower(e.v(tname))))
    parts.append(e.let("release_t", _fn_type(e, [e.v("under")], e.lower(e.v("void")))))
    parts.append(e.let("id_t", _fn_type(e, [e.v("under")], e.v("under"))))
    for fn, fn_t, fbody in [
        ("release", "release_t", _release_body(e)),
        ("adopt", "id_t", _adopt_body(e)),
        ("clone", "id_t", _clone_body(e)),
    ]:
        parts.append(
            e.let(
                fn,
                e.call(
                    e.lower(e.fld(e.v("lib"), "func_dep")),
                    e.rec(
                        p("name", e.cat(e.v("name"), e.s("_" + fn))),
                        p("params", e.list_new(e.mb.types_string(), e.s("p"))),
                        p("ty", e.v(fn_t)),
                        p("body", e.stage(fbody)),
                    ),
                ),
            )
        )
    parts.append(e.ret(e.eresult_ok(e.mb.types_cve(), unwrap_cve_m(e, const_eval_in(e, xx(e), e.stage(_setup(e)))))))
    const_fn(e, x, "shctor_b", "shared.type", body(e, *parts))
    x.append(e.finish(e.v("d")))
    x.append(e.ret(e.rec(p("type", e.fld(e.v("shctor_b"), "func")))))

    top = []
    top.append(e.let("k", e.lower(e.mb.seq(x))))
    top.append(e.ret(e.rec(p("type", e.fld(e.v("k"), "type")))))
    return top
