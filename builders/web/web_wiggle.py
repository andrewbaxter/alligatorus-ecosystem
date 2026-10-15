"""web-wiggle.atz: wasm + WebGL2 demo drawing a wiggling square via glsl shaders and a uniform block."""

from ..wasm.wat import bind_types

BLOCK = "u"
SIZE_CM = 3.0


def _g(e, name):
    return e.lower(e.fld(e.v("glsl"), name))


def _fn(e, name, arg):
    return e.call(e.lower(e.fld(e.v("glsl"), "builtins", name)), arg)


def _fn_tup(e, name, *args):
    return e.call(e.lower(e.fld(e.v("glsl"), "builtins", name)), e.tup(*args))


def block_fields(e):
    return e.tup(e.tup(e.s("time"), e.fld(e.v("glsl"), "float")), e.tup(e.s("resolution"), e.fld(e.v("glsl"), "vec2")))


def shader_setup(e):
    setup = []
    setup.append(e.let("glsl", e.import_local("glsl", "glsl-es-3.00.atz")))
    setup.append(e.let("vs", e.call(e.fld(e.v("glsl"), "new"), e.tup())))
    setup.append(e.let("fs", e.call(e.fld(e.v("glsl"), "new"), e.tup())))
    setup.append(
        e.let(
            "main_t",
            e.call(
                e.fld(e.v("glsl"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.fld(e.v("glsl"), "void"))),
            ),
        )
    )
    setup.append(e.ret(e.rec(e.p("vs", e.v("vs")), e.p("fs", e.v("fs")), e.p("main_t", e.v("main_t")))))
    return setup


def shaders(e, out):
    id_ = e.lower(e.v("gl_VertexID"))
    vertex_body = e.stage(
        e.seq(
            e.let(
                "x",
                e.mb.operator_sub(
                    e.mb.as_(e.mb.operator_shl(e.mb.operator_and(id_, e.n(1)), e.n(2)), _g(e, "float")), e.n(1)
                ),
            ),
            e.let(
                "y",
                e.mb.operator_sub(
                    e.mb.as_(e.mb.operator_shl(e.mb.operator_and(id_, e.n(2)), e.n(1)), _g(e, "float")), e.n(1)
                ),
            ),
            e.mb.set(e.lower(e.v("gl_Position")), e.mb.as_(e.tup(e.v("x"), e.v("y"), e.n(0), e.n(1)), _g(e, "vec4"))),
        )
    )
    u = e.lower(e.v("u"))
    frag = e.lower(e.v("gl_FragCoord"))
    qx = e.fld(e.v("q"), "x")
    qy = e.fld(e.v("q"), "y")
    half = e.n(0.5)
    s_top = e.mb.operator_mul(e.mb.operator_add(qx, e.n(1)), half)
    s_right = e.mb.operator_add(e.mb.operator_mul(e.mb.operator_add(e.mb.operator_neg(qy), e.n(1)), half), e.n(1))
    s_bottom = e.mb.operator_add(e.mb.operator_mul(e.mb.operator_add(e.mb.operator_neg(qx), e.n(1)), half), e.n(2))
    s_left = e.mb.operator_add(e.mb.operator_mul(e.mb.operator_add(qy, e.n(1)), half), e.n(3))
    fragment_body = e.stage(
        e.seq(
            e.let(
                "p",
                e.mb.operator_sub(
                    e.mb.operator_mul(e.mb.operator_div(e.fld(frag, "xy"), e.fld(u, "resolution")), e.n(2)), e.n(1)
                ),
            ),
            e.let("a", _fn(e, "abs", e.v("p"))),
            e.let("d", _fn_tup(e, "max", e.fld(e.v("a"), "x"), e.fld(e.v("a"), "y"))),
            e.let("q", e.mb.operator_div(e.v("p"), e.v("d"))),
            e.let(
                "s",
                e.if_else(
                    e.mb.operator_ge(e.fld(e.v("a"), "y"), e.fld(e.v("a"), "x")),
                    e.if_else(e.mb.operator_gt(e.fld(e.v("p"), "y"), e.n(0)), s_top, s_bottom),
                    e.if_else(e.mb.operator_gt(e.fld(e.v("p"), "x"), e.n(0)), s_right, s_left),
                ),
            ),
            e.let(
                "wave",
                e.mb.operator_mul(
                    _fn(
                        e,
                        "sin",
                        e.mb.operator_sub(
                            e.mb.operator_mul(e.v("s"), e.n(6.283185307179586)),
                            e.mb.operator_mul(e.fld(u, "time"), e.n(3)),
                        ),
                    ),
                    e.n(0.05),
                ),
            ),
            e.let("dist", e.mb.operator_sub(e.v("d"), e.mb.operator_add(e.v("wave"), e.n(0.6)))),
            e.let("aa", _fn(e, "fwidth", e.v("dist"))),
            e.let("cov", _fn_tup(e, "smoothstep", e.mb.operator_neg(e.v("aa")), e.v("aa"), e.v("dist"))),
            e.mb.set(
                e.lower(e.v("color")),
                e.mb.as_(
                    e.tup(
                        _fn_tup(
                            e, "mix", e.mb.as_(e.n(0), _g(e, "vec3")), e.mb.as_(e.n(0.5), _g(e, "vec3")), e.v("cov")
                        ),
                        e.n(1),
                    ),
                    _g(e, "vec4"),
                ),
            ),
        )
    )
    for gv in ["gl_VertexID", "gl_Position", "gl_FragCoord"]:
        out.append(e.let(gv, e.call(e.fld(e.v("glsl"), "gl_fn"), e.rec(e.p("name", e.s(gv))))))
    out.append(
        e.let(
            "color",
            e.call(
                e.fld(e.v("glsl"), "out_fn"),
                e.rec(e.p("mod", e.v("fs")), e.p("name", e.s("color")), e.p("ty", e.fld(e.v("glsl"), "vec4"))),
            ),
        )
    )
    out.append(
        e.call(
            e.fld(e.v("glsl"), "func_fn"),
            e.rec(
                e.p("mod", e.v("vs")),
                e.p("name", e.s("main")),
                e.p("params", e.tup()),
                e.p("ty", e.v("main_t")),
                e.p("body", vertex_body),
            ),
        )
    )
    out.append(
        e.call(
            e.fld(e.v("glsl"), "func_fn"),
            e.rec(
                e.p("mod", e.v("fs")),
                e.p("name", e.s("main")),
                e.p("params", e.tup()),
                e.p("ty", e.v("main_t")),
                e.p("body", fragment_body),
            ),
        )
    )


def _call(e, hook, *args):
    return e.call(e.lower(e.v(hook)), args[0] if len(args) == 1 else e.tup(*args))


def _str(e, name, text):
    return [e.lower(e.v(name)), e.n(len(text.encode()))]


def _cell(e, data, index):
    return e.mb.field(e.lower(e.v(data)), e.n(index))


BODY_STYLE = "margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#808080"
CANVAS_STYLE = "width:" + str(int(SIZE_CM)) + "cm;height:" + str(int(SIZE_CM)) + "cm"


def _byte_count(e, text):
    return e.seq(
        e.let("__n", e.rec(e.p("v", e.int_of(0)))),
        e.foreach(e.call(e.mb.eval_str_utf8(), text), "_", e.incr(e.fld(e.v("__n"), "v"))),
        e.ret(e.fld(e.v("__n"), "v")),
    )


def module(e):
    setup = []
    setup.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    setup.append(e.let("m", e.call(e.fld(e.v("wasm"), "new"), e.tup())))
    bind_types(e, setup)
    setup.append(
        e.let(
            "start_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type())), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup.append(
        e.let(
            "frame_fn_t",
            e.call(
                e.fld(e.v("wasm"), "fn"),
                e.rec(e.p("params", e.list_new(e.mb.eval_type(), e.v("t_f64"))), e.p("ret", e.v("t_void"))),
            ),
        )
    )
    setup_out = []
    for n in ["m", "start_fn_t", "frame_fn_t", "t_i32", "t_u32", "t_f32", "t_f64"]:
        setup_out.append(e.p(n, e.v(n)))
    setup.append(e.ret(e.rec(*setup_out)))
    shader_setup_ = shader_setup(e)

    top = []
    top.append(e.let("wasm", e.import_local("wasm", "wat-2.0.atz")))
    top.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    top.append(e.let("web", e.import_local("web", "web-wasm.atz")))
    top.append(e.let("glsl", e.import_local("glsl", "glsl-es-3.00.atz")))
    top.append(e.let("uniforms", e.import_local("uniforms", "webgl-uniforms.atz")))
    top.append(e.let("k", e.lower(e.mb.seq(setup))))
    for n in ["m", "start_fn_t", "frame_fn_t", "t_i32", "t_u32", "t_f32", "t_f64"]:
        top.append(e.let(n, e.fld(e.v("k"), n)))
    top.append(e.let("g", e.lower(e.mb.seq(shader_setup_))))
    for n in ["vs", "fs", "main_t"]:
        top.append(e.let(n, e.fld(e.v("g"), n)))
    top.append(
        e.let(
            "u",
            e.call(
                e.fld(e.v("uniforms"), "glsl_fn"),
                e.rec(e.p("mod", e.v("fs")), e.p("name", e.s(BLOCK)), e.p("fields", block_fields(e))),
            ),
        )
    )
    top.append(
        e.let(
            "ub",
            e.call(
                e.fld(e.v("uniforms"), "wasm_fn"),
                e.rec(e.p("mod", e.v("m")), e.p("name", e.s(BLOCK)), e.p("fields", block_fields(e))),
            ),
        )
    )
    shaders(e, top)
    top.append(e.let("vtext", e.fld(e.call_m0(e.v("vs"), "render"), "glsl")))
    top.append(e.let("ftext", e.fld(e.call_m0(e.v("fs"), "render"), "glsl")))
    top.append(e.let("vsrc", e.call_m(e.v("m"), "cstr", e.v("vtext"))))
    top.append(e.let("fsrc", e.call_m(e.v("m"), "cstr", e.v("ftext"))))
    top.append(e.let("vlen", _byte_count(e, e.v("vtext"))))
    top.append(e.let("flen", _byte_count(e, e.v("ftext"))))
    for bind, text in [
        ("s_canvas", "canvas"),
        ("s_style", "style"),
        ("s_body_style", BODY_STYLE),
        ("s_canvas_style", CANVAS_STYLE),
        ("s_webgl2", "webgl2"),
        ("s_block", BLOCK + "_block"),
        ("s_frame", "frame"),
    ]:
        top.append(e.let(bind, e.call_m(e.v("m"), "cstr", e.s(text))))
    for name, count in [("cells", 3), ("out", 2)]:
        zeros = []
        for _ in range(count):
            zeros.append(e.n(0))
        top.append(
            e.let(
                name,
                e.call(
                    e.fld(e.v("wasm"), "data_fn"),
                    e.rec(
                        e.p("mod", e.v("m")),
                        e.p("name", e.s(name)),
                        e.p("elem", e.v("t_i32")),
                        e.p("values", e.tup(*zeros)),
                    ),
                ),
            )
        )
    hooks = [
        ("h_document", "get", "Window", "document"),
        ("h_body", "get", "Document", "body"),
        ("h_create", "op", "Document", "createElement"),
        ("h_set_attr", "op", "Element", "setAttribute"),
        ("h_append", "op", "Node", "appendChild"),
        ("h_dpr", "get", "Window", "devicePixelRatio"),
        ("h_client_width", "get", "Element", "clientWidth"),
        ("h_width", "set", "HTMLCanvasElement", "width"),
        ("h_height", "set", "HTMLCanvasElement", "height"),
        ("h_get_context", "op", "HTMLCanvasElement", "getContext"),
        ("h_raf", "op", "Window", "requestAnimationFrame"),
        ("h_create_shader", "op", "WebGL2RenderingContext", "createShader"),
        ("h_shader_source", "op", "WebGL2RenderingContext", "shaderSource"),
        ("h_compile_shader", "op", "WebGL2RenderingContext", "compileShader"),
        ("h_create_program", "op", "WebGL2RenderingContext", "createProgram"),
        ("h_attach", "op", "WebGL2RenderingContext", "attachShader"),
        ("h_link", "op", "WebGL2RenderingContext", "linkProgram"),
        ("h_use_program", "op", "WebGL2RenderingContext", "useProgram"),
        ("h_create_buffer", "op", "WebGL2RenderingContext", "createBuffer"),
        ("h_bind_buffer", "op", "WebGL2RenderingContext", "bindBuffer"),
        ("h_bind_buffer_base", "op", "WebGL2RenderingContext", "bindBufferBase"),
        ("h_block_index", "op", "WebGL2RenderingContext", "getUniformBlockIndex"),
        ("h_block_binding", "op", "WebGL2RenderingContext", "uniformBlockBinding"),
        ("h_viewport", "op", "WebGL2RenderingContext", "viewport"),
        ("h_buffer_data", "op", "WebGL2RenderingContext", "bufferData#1"),
        ("h_draw_arrays", "op", "WebGL2RenderingContext", "drawArrays"),
        ("c_vertex", "const", "WebGL2RenderingContext", "VERTEX_SHADER"),
        ("c_fragment", "const", "WebGL2RenderingContext", "FRAGMENT_SHADER"),
        ("c_uniform_buffer", "const", "WebGL2RenderingContext", "UNIFORM_BUFFER"),
        ("c_dynamic_draw", "const", "WebGL2RenderingContext", "DYNAMIC_DRAW"),
        ("c_triangles", "const", "WebGL2RenderingContext", "TRIANGLES"),
    ]
    out = _cell(e, "out", 1)
    canvas = _str(e, "s_canvas", "canvas")
    style = _str(e, "s_style", "style")
    body_style = _str(e, "s_body_style", BODY_STYLE)
    canvas_style = _str(e, "s_canvas_style", CANVAS_STYLE)
    webgl2 = _str(e, "s_webgl2", "webgl2")
    block = _str(e, "s_block", BLOCK + "_block")
    frame = _str(e, "s_frame", "frame")
    px = e.v("px")
    start_body = e.stage(
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            e.let("doc", _call(e, "h_document", e.v("win"))),
            _call(e, "h_body", e.v("doc"), e.lower(e.v("out"))),
            e.let("body", out),
            _call(e, "h_set_attr", e.v("body"), style[0], style[1], body_style[0], body_style[1]),
            e.let("canvas", _call(e, "h_create", e.v("doc"), canvas[0], canvas[1], e.n(0), e.n(0), e.n(0))),
            _call(e, "h_set_attr", e.v("canvas"), style[0], style[1], canvas_style[0], canvas_style[1]),
            _call(e, "h_append", e.v("body"), e.v("canvas")),
            e.let("dpr", _call(e, "h_dpr", e.v("win"))),
            e.let("cw", _call(e, "h_client_width", e.v("canvas"))),
            e.let(
                "px",
                e.mb.as_(
                    e.mb.operator_mul(e.mb.as_(e.v("cw"), e.lower(e.v("t_f64"))), e.v("dpr")), e.lower(e.v("t_i32"))
                ),
            ),
            _call(e, "h_width", e.v("canvas"), e.mb.as_(px, e.lower(e.v("t_u32")))),
            _call(e, "h_height", e.v("canvas"), e.mb.as_(px, e.lower(e.v("t_u32")))),
            _call(e, "h_get_context", e.v("canvas"), webgl2[0], webgl2[1], e.n(0), e.n(0), e.lower(e.v("out"))),
            e.let("gl", out),
            e.mb.set(_cell(e, "cells", 1), e.v("gl")),
            _call(e, "h_create_shader", e.v("gl"), e.lower(e.v("c_vertex")), e.lower(e.v("out"))),
            e.let("vsh", out),
            _call(e, "h_shader_source", e.v("gl"), e.v("vsh"), e.lower(e.v("vsrc")), e.lower(e.v("vlen"))),
            _call(e, "h_compile_shader", e.v("gl"), e.v("vsh")),
            _call(e, "h_create_shader", e.v("gl"), e.lower(e.v("c_fragment")), e.lower(e.v("out"))),
            e.let("fsh", out),
            _call(e, "h_shader_source", e.v("gl"), e.v("fsh"), e.lower(e.v("fsrc")), e.lower(e.v("flen"))),
            _call(e, "h_compile_shader", e.v("gl"), e.v("fsh")),
            e.let("prog", _call(e, "h_create_program", e.v("gl"))),
            _call(e, "h_attach", e.v("gl"), e.v("prog"), e.v("vsh")),
            _call(e, "h_attach", e.v("gl"), e.v("prog"), e.v("fsh")),
            _call(e, "h_link", e.v("gl"), e.v("prog")),
            _call(e, "h_use_program", e.v("gl"), e.n(1), e.v("prog")),
            e.let("buf", _call(e, "h_create_buffer", e.v("gl"))),
            _call(e, "h_bind_buffer", e.v("gl"), e.lower(e.v("c_uniform_buffer")), e.n(1), e.v("buf")),
            _call(e, "h_bind_buffer_base", e.v("gl"), e.lower(e.v("c_uniform_buffer")), e.n(0), e.n(1), e.v("buf")),
            e.let("idx", _call(e, "h_block_index", e.v("gl"), e.v("prog"), block[0], block[1])),
            _call(e, "h_block_binding", e.v("gl"), e.v("prog"), e.v("idx"), e.n(0)),
            _call(e, "h_viewport", e.v("gl"), e.n(0), e.n(0), px, px),
            e.mb.set(
                e.fld(e.lower(e.v("ub")), "resolution"),
                e.tup(e.mb.as_(px, e.lower(e.v("t_f32"))), e.mb.as_(px, e.lower(e.v("t_f32")))),
            ),
            e.let("cb", e.call(e.lower(e.fld(e.v("webidl"), "callback")), e.tup(frame[0], frame[1]))),
            _call(e, "h_raf", e.v("win"), e.v("cb")),
            # The window and callback handles outlive `_start`: they leave ownership into the cells.
            e.mb.set(_cell(e, "cells", 0), e.call(e.fld(e.v("win"), "forget"), e.tup())),
            e.mb.set(_cell(e, "cells", 2), e.call(e.fld(e.v("cb"), "forget"), e.tup())),
        )
    )
    frame_body = e.stage(
        e.seq(
            e.mb.set(
                e.fld(e.lower(e.v("ub")), "time"),
                e.mb.as_(e.mb.operator_mul(e.v("t"), e.n(0.001)), e.lower(e.v("t_f32"))),
            ),
            e.let("gl", _cell(e, "cells", 1)),
            _call(
                e,
                "h_buffer_data",
                e.v("gl"),
                e.lower(e.v("c_uniform_buffer")),
                e.n(1),
                e.fld(e.lower(e.v("ub")), "ptr"),
                e.fld(e.lower(e.v("ub")), "size"),
                e.lower(e.v("c_dynamic_draw")),
            ),
            _call(e, "h_draw_arrays", e.v("gl"), e.lower(e.v("c_triangles")), e.n(0), e.n(3)),
            _call(e, "h_raf", _cell(e, "cells", 0), _cell(e, "cells", 2)),
        )
    )
    for bind, kind, iface, member in hooks:
        top.append(
            e.let(bind, e.call(e.fld(e.v("webidl"), kind), e.rec(e.p("iface", e.s(iface)), e.p("member", e.s(member)))))
        )
    top.append(
        e.call(
            e.fld(e.v("wasm"), "func_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("_start")),
                e.p("params", e.tup()),
                e.p("ty", e.v("start_fn_t")),
                e.p("body", start_body),
            ),
        )
    )
    top.append(
        e.call(
            e.fld(e.v("wasm"), "func_fn"),
            e.rec(
                e.p("mod", e.v("m")),
                e.p("name", e.s("frame")),
                e.p("params", e.tup(e.s("t"))),
                e.p("ty", e.v("frame_fn_t")),
                e.p("body", frame_body),
            ),
        )
    )
    top.append(e.call_m(e.v("m"), "export", e.s("_start")))
    top.append(e.call_m(e.v("m"), "export", e.s("frame")))
    top.append(e.ret(e.call(e.fld(e.v("web"), "build"), e.call_m0(e.v("m"), "render"))))
    return top
