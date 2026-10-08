"""LLVM extern declarations (C functions) and the primitive type bindings they reference."""

from .eco_mb import p


def llvm_top(e):
    """Field accessor over the module-level `llvm` binding."""
    return lambda name: e.fld(e.v("llvm"), name)


def bind_types(e, out, llvm):
    for t in ["i1", "i8", "i32", "i64", "u8", "u32", "u64", "f32", "f64", "void"]:
        out.append(e.let("t_" + t, llvm(t)))
    out.append(e.let("t_pv", e.call(llvm("ptr"), e.v("t_void"))))
    out.append(e.let("t_pu8", e.call(llvm("ptr"), e.v("t_u8"))))


class Extern:
    def __init__(self, name, params, ret, varargs):
        self.name = name
        self.params = params
        self.ret = ret
        self.varargs = varargs

    def fn_type(self, e, llvm):
        ps = []
        for param in self.params:
            ps.append(e.v("t_" + param))
        return e.call(
            llvm("fn_varargs" if self.varargs else "fn"),
            e.rec(p("params", e.list_new(e.mb.eval_type(), *ps)), p("ret", e.v("t_" + self.ret))),
        )

    def extern_t(self, e, llvm, const_fn_type, *libs):
        lib_exprs = [e.s(lib) for lib in libs]
        return e.call(
            llvm("extern_t"),
            e.rec(
                p("name", e.s(self.name)),
                p("ty", const_fn_type),
                p("libs", e.list_new(e.mb.types_string(), *lib_exprs)),
            ),
        )

    def declare(self, e, extern_fn, const_fn_type, *libs):
        lib_exprs = [e.s(lib) for lib in libs]
        return e.call(extern_fn, e.rec(p("name", e.s(self.name)), p("ty", const_fn_type), p("libs", e.tup(*lib_exprs))))


def global_t(e, llvm, ty):
    return e.call(llvm("global_t"), e.rec(p("ty", ty), p("mem", e.b(False))))
