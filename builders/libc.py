"""libc-2.42.atz: libc/libm externs."""

from .extern import Extern, bind_types, llvm_top

EXTERNS = [
    Extern("sin", ["f64"], "f64", False),
    Extern("exp2", ["f64"], "f64", False),
    Extern("fmod", ["f64", "f64"], "f64", False),
    Extern("sinf", ["f32"], "f32", False),
    Extern("cosf", ["f32"], "f32", False),
    Extern("tanf", ["f32"], "f32", False),
    Extern("expf", ["f32"], "f32", False),
    Extern("exp2f", ["f32"], "f32", False),
    Extern("logf", ["f32"], "f32", False),
    Extern("powf", ["f32", "f32"], "f32", False),
    Extern("sqrtf", ["f32"], "f32", False),
    Extern("floorf", ["f32"], "f32", False),
    Extern("fabsf", ["f32"], "f32", False),
    Extern("fmodf", ["f32", "f32"], "f32", False),
    Extern("pow", ["f64", "f64"], "f64", False),
    Extern("exp", ["f64"], "f64", False),
    Extern("log", ["f64"], "f64", False),
    Extern("cos", ["f64"], "f64", False),
    Extern("tan", ["f64"], "f64", False),
    Extern("sqrt", ["f64"], "f64", False),
    Extern("floor", ["f64"], "f64", False),
    Extern("fabs", ["f64"], "f64", False),
    Extern("memset", ["pv", "i32", "u64"], "pv", False),
    Extern("memcpy", ["pv", "pv", "u64"], "pv", False),
    Extern("puts", ["pu8"], "i32", False),
    Extern("exit", ["i32"], "void", False),
    Extern("printf", ["pu8"], "i32", True),
    Extern("malloc", ["u64"], "pv", False),
    Extern("calloc", ["u64", "u64"], "pv", False),
    Extern("realloc", ["pv", "u64"], "pv", False),
    Extern("free", ["pv"], "void", False),
]

MATH_LIB = "m"

NOT_MATH = ["memset", "memcpy", "puts", "exit", "printf", "malloc", "calloc", "realloc", "free"]


def module(e):
    setup = []
    setup.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    llvm = llvm_top(e)
    bind_types(e, setup, llvm)
    type_fields = []
    for ex in EXTERNS:
        setup.append(e.let(ex.name + "_fn_t", ex.fn_type(e, llvm)))
        type_fields.append(e.p(ex.name + "_fn_t", e.v(ex.name + "_fn_t")))
    setup.append(e.ret(e.rec(*type_fields)))

    top = []
    top.append(e.let("llvm", e.import_local("llvm", "llvm-ir-22.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    fields = []
    for ex in EXTERNS:
        libs = [] if ex.name in NOT_MATH else [MATH_LIB]
        fields.append(
            e.p(ex.name, ex.declare(e, e.fld(e.v("llvm"), "extern_fn"), e.fld(e.v("k"), ex.name + "_fn_t"), *libs))
        )
    top.append(e.ret(e.rec(*fields)))
    return top
