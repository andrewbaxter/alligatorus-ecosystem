"""editor-canvas-shaders.atz: editor-canvas.atz's tile shaders as GLSL ES 3.00 text (`vs_text`, `fs_text`, and their
UTF-8 lengths), made at compile time (glsl-es-3.00.atz needs its declarations at a module's top level).
"""

from ..eco_mb import p
from ..target_mb import fn_of


def module(e):
    """The vertex shader makes a strip over `u_rect` (clip space x0, y0, x1, y1) from the vertex index; the fragment
    shader samples `u_tex` scaled by `u_alpha` (premultiplied alpha)."""
    x = []

    def g(name):
        return e.lower(e.fld(e.v("glsl"), name))

    def fn(name, *args):
        return e.call(
            fn_of(e, e.lower(e.fld(e.v("glsl"), "builtins", name))), args[0] if len(args) == 1 else e.tup(*args)
        )

    x.append(e.let("glsl", e.import_local("glsl", "glsl-es-3.00.atz")))
    # The shader modules and the entry point's type are constants made in a lowered setup.
    gs = []
    gs.append(e.let("glsl", e.import_local("glsl", "glsl-es-3.00.atz")))
    gs.append(e.let("vs", e.call(e.fld(e.v("glsl"), "new"), e.tup())))
    gs.append(e.let("fs", e.call(e.fld(e.v("glsl"), "new"), e.tup())))
    gs.append(
        e.let(
            "main_t",
            e.call(
                e.fld(e.v("glsl"), "fn"),
                e.rec(p("params", e.list_new(e.mb.eval_type())), p("ret", e.fld(e.v("glsl"), "void"))),
            ),
        )
    )
    gs.append(e.ret(e.rec(p("vs", e.v("vs")), p("fs", e.v("fs")), p("main_t", e.v("main_t")))))
    x.append(e.let("gsh", e.lower(e.mb.seq(gs))))
    for n in ["vs", "fs", "main_t"]:
        x.append(e.let(n, e.fld(e.v("gsh"), n)))
    for gv in ["gl_VertexID", "gl_Position"]:
        x.append(e.let(gv, e.call(e.fld(e.v("glsl"), "gl_fn"), e.rec(p("name", e.s(gv))))))
    for name, kind, mod, ty_ in [
        ("u_rect", "uniform_fn", "vs", "vec4"),
        ("v_uv_out", "out_fn", "vs", "vec2"),
        ("v_uv", "in_fn", "fs", "vec2"),
        ("u_alpha", "uniform_fn", "fs", "float"),
        ("u_tex", "uniform_fn", "fs", "sampler2D"),
        ("color", "out_fn", "fs", "vec4"),
    ]:
        glsl_name = "v_uv" if name == "v_uv_out" else name
        x.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("glsl"), kind),
                    e.rec(p("mod", e.v(mod)), p("name", e.s(glsl_name)), p("ty", e.fld(e.v("glsl"), ty_))),
                ),
            )
        )
    id_ = e.lower(e.v("gl_VertexID"))
    rect = e.lower(e.v("u_rect"))
    vertex = e.seq(
        e.let("fx", e.call(e.fld(e.mb.operator_and(id_, e.n(1)), "to_float"), g("float"))),
        e.let("fy", e.call(e.fld(e.mb.operator_shr(id_, e.n(1)), "to_float"), g("float"))),
        e.mb.set(e.lower(e.v("v_uv_out")), e.mb.as_(e.tup(e.v("fx"), e.v("fy")), g("vec2"))),
        e.mb.set(
            e.lower(e.v("gl_Position")),
            e.mb.as_(
                e.tup(
                    fn("mix", e.fld(rect, "x"), e.fld(rect, "z"), e.v("fx")),
                    fn("mix", e.fld(rect, "y"), e.fld(rect, "w"), e.v("fy")),
                    e.n(0),
                    e.n(1),
                ),
                g("vec4"),
            ),
        ),
    )
    fragment = e.mb.set(
        e.lower(e.v("color")),
        e.mb.operator_mul(fn("texture", e.lower(e.v("u_tex")), e.lower(e.v("v_uv"))), e.lower(e.v("u_alpha"))),
    )
    for mod, body_ in [("vs", vertex), ("fs", fragment)]:
        x.append(
            e.call(
                e.fld(e.v("glsl"), "export_fn"),
                e.rec(
                    p("mod", e.v(mod)),
                    p("name", e.s("main")),
                    p("params", e.tup()),
                    p("ty", e.v("main_t")),
                    p("body", e.stage(body_)),
                ),
            )
        )
    for mod, name in [("vs", "vs_text"), ("fs", "fs_text")]:
        x.append(e.let(name, e.fld(e.call_m0(e.v(mod), "render"), "glsl")))
        x.append(
            e.let(
                name + "_len",
                e.seq(
                    e.let("__n", e.rec(p("v", e.int_of(0)))),
                    e.foreach(e.call(e.mb.eval_str_utf8(), e.v(name)), "_", e.incr(e.fld(e.v("__n"), "v"))),
                    e.ret(e.fld(e.v("__n"), "v")),
                ),
            )
        )
    x.append(e.ret(e.rec(*[p(n, e.v(n)) for n in ["vs_text", "vs_text_len", "fs_text", "fs_text_len"]])))
    return x
