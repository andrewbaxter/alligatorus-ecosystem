"""editor-canvas.atz: the drawing area of an editor (wat target; dependencies over webidl-wasm.atz's hooks, typed
with the ecosystem's libraries).

A canvas is three stacked canvas elements filling a container: a grid (2D), the raster layers (WebGL2) and the
vector layers (2D, on top, taking the pointer). The area doesn't follow the ide's theme: its background is a fixed
neutral grey, and the grid and vector layers draw by inverting what is under them (white, blended by difference), so
they show over the background, the paper and any ink alike. World coordinates are millimetres, y down; the view has
a center (the world point at the middle of the area) and a scale (CSS pixels per millimetre).

A canvas is an owned record (`cv_t`, `cv_raw`: record-wasm.atz) holding its elements, contexts, WebGL program and
uniform locations, its listeners, toolbar buttons and child (all owned: dropping the canvas releases them) and its
view. `cv_new(parent, fit, child)` makes one in `parent` (a node) and yields the owned record. The toolbar:
recentering and toggling the grid are handled by closures the canvas owns (capturing it), fitting by the editor's
callable `fit` (editor-ui.atz `ev_cb`, owned: the editor knows the extent, and calls `cv_fit`). The canvas listens
on its top element: panning (the middle or right button) and zooming (the wheel) are its own, the context menu is
suppressed, and every other pointer event goes to the `child` (an owned `cv_child` interface value, iface-wasm.atz:
`down(ev)`, `move(ev)`, `up(ev)`, `dblclick(ev)`, each with the raw `Event`; `cv_wx`/`cv_wy` give its world
position; `cv_capture(cv, ev)` captures the pointer on the area for a drag).

Each frame: `cv_begin(cv)` follows the element's size and the device pixel ratio, clears, draws the grid and the
origin, and sets the vector canvas to world coordinates. Then layers draw: raster layers with `cv_image(cv, tex, x0,
y0, x1, y1, alpha)` (a texture over a world rectangle, premultiplied RGBA, mipmapped), vector layers with
`cv_style(cv, alpha, width)` (`width` in CSS pixels whatever the zoom) and `cv_line`, `cv_circle(cv, x, y, r,
fill)`, `cv_move`/`cv_line_to`/`cv_stroke` (a path). Textures
(`WebGLTexture` handles: `tex_t`, `tex_own`, `tex_raw`): `cv_tex_new(cv)` (owned),
`cv_tex_set(cv, tex, w, h, ptr)` (RGBA8 rows at `ptr`, a `ptr(u8)`, top row first).

The view: `cv_wx(cv, ev)` and `cv_wy(cv, ev)` are a pointer event's world position; `cv_scale(cv)`; `cv_fit(cv,
x0, y0, x1, y1)` (measuring the area first, so it works before the first frame; an empty rectangle: the origin in
the middle, 1 CSS pixel per CSS pixel's worth of millimetres: 96 dpi).
"""

from ..collections import closure_wasm, iface_wasm, record_wasm
from ..eco_mb import p
from . import editor_ui
from ..target_mb import fn_of
from ..wasm import math_wasm
from ..wasm.kit import Kit, library

FILE = "editor-canvas.atz"
SHADERS_FILE = "editor-canvas-shaders.atz"

PX_PER_MM = 96 / 25.4

# The record: (field, type binding); the owned handles first, then the view.
FIELDS = [
    ("el", "el_t"),
    ("c_grid", "canvas_t"),
    ("c_gl", "canvas_t"),
    ("c_over", "canvas_t"),
    ("x_grid", "ctx2d_t"),
    ("x_over", "ctx2d_t"),
    ("gl", "gl_t"),
    ("prog", "prog_t"),
    ("u_rect", "uloc_t"),
    ("u_alpha", "uloc_t"),
    ("listeners", "listeners_t"),
    ("buttons", "buttons_t"),
    ("cbs", "ev_cbs_t"),
    ("child", "cv_child_t"),
    ("fit", "ev_cb_t"),
    ("grid_on", "t_i32"),
    ("panning", "t_i32"),
    ("pw", "t_i32"),
    ("ph", "t_i32"),
    ("w", "t_f64"),
    ("h", "t_f64"),
    ("dpr", "t_f64"),
    ("cx", "t_f64"),
    ("cy", "t_f64"),
    ("scale", "t_f64"),
    ("pan_x", "t_f64"),
    ("pan_y", "t_f64"),
]
HOOKS = [
    ("h_context", "op", "HTMLCanvasElement", "getContext"),
    ("h_set_w", "set", "HTMLCanvasElement", "width"),
    ("h_set_h", "set", "HTMLCanvasElement", "height"),
    ("h_client_w", "get", "Element", "clientWidth"),
    ("h_client_h", "get", "Element", "clientHeight"),
    ("h_dpr", "get", "Window", "devicePixelRatio"),
    ("h_capture", "op", "Element", "setPointerCapture"),
    ("h_button", "get", "MouseEvent", "button"),
    ("h_client_x", "get", "MouseEvent", "clientX#0"),
    ("h_client_y", "get", "MouseEvent", "clientY#0"),
    ("h_offset_x", "get", "MouseEvent", "offsetX"),
    ("h_offset_y", "get", "MouseEvent", "offsetY"),
    ("h_pointer_id", "get", "PointerEvent", "pointerId"),
    ("h_delta_y", "get", "WheelEvent", "deltaY"),
    ("h_delta_mode", "get", "WheelEvent", "deltaMode"),
    ("x_set_transform", "op", "CanvasRenderingContext2D", "setTransform#0"),
    ("x_reset", "op", "CanvasRenderingContext2D", "resetTransform"),
    ("x_clear", "op", "CanvasRenderingContext2D", "clearRect"),
    ("x_begin", "op", "CanvasRenderingContext2D", "beginPath"),
    ("x_move", "op", "CanvasRenderingContext2D", "moveTo"),
    ("x_line", "op", "CanvasRenderingContext2D", "lineTo"),
    ("x_arc", "op", "CanvasRenderingContext2D", "arc"),
    ("x_stroke", "op", "CanvasRenderingContext2D", "stroke#0"),
    ("x_fill", "op", "CanvasRenderingContext2D", "fill#0"),
    ("x_line_width", "set", "CanvasRenderingContext2D", "lineWidth"),
    ("x_stroke_style", "set", "CanvasRenderingContext2D", "strokeStyle"),
    ("x_fill_style", "set", "CanvasRenderingContext2D", "fillStyle"),
    ("x_alpha", "set", "CanvasRenderingContext2D", "globalAlpha"),
    ("x_cap", "set", "CanvasRenderingContext2D", "lineCap"),
    ("x_join", "set", "CanvasRenderingContext2D", "lineJoin"),
    ("g_viewport", "op", "WebGL2RenderingContext", "viewport"),
    ("g_clear_color", "op", "WebGL2RenderingContext", "clearColor"),
    ("g_clear", "op", "WebGL2RenderingContext", "clear"),
    ("g_create_shader", "op", "WebGL2RenderingContext", "createShader"),
    ("g_shader_source", "op", "WebGL2RenderingContext", "shaderSource"),
    ("g_compile_shader", "op", "WebGL2RenderingContext", "compileShader"),
    ("g_create_program", "op", "WebGL2RenderingContext", "createProgram"),
    ("g_attach", "op", "WebGL2RenderingContext", "attachShader"),
    ("g_link", "op", "WebGL2RenderingContext", "linkProgram"),
    ("g_use", "op", "WebGL2RenderingContext", "useProgram"),
    ("g_uniform_loc", "op", "WebGL2RenderingContext", "getUniformLocation"),
    ("g_uniform4f", "op", "WebGL2RenderingContext", "uniform4f"),
    ("g_uniform1f", "op", "WebGL2RenderingContext", "uniform1f"),
    ("g_enable", "op", "WebGL2RenderingContext", "enable"),
    ("g_blend", "op", "WebGL2RenderingContext", "blendFunc"),
    ("g_create_tex", "op", "WebGL2RenderingContext", "createTexture"),
    ("g_bind_tex", "op", "WebGL2RenderingContext", "bindTexture"),
    ("g_tex_param", "op", "WebGL2RenderingContext", "texParameteri"),
    ("g_tex_image", "op", "WebGL2RenderingContext", "texImage2D#0"),
    ("g_mipmap", "op", "WebGL2RenderingContext", "generateMipmap"),
    ("g_draw", "op", "WebGL2RenderingContext", "drawArrays"),
]

CONSTS = [
    "VERTEX_SHADER",
    "FRAGMENT_SHADER",
    "TEXTURE_2D",
    "RGBA",
    "UNSIGNED_BYTE",
    "TEXTURE_MIN_FILTER",
    "TEXTURE_MAG_FILTER",
    "TEXTURE_WRAP_S",
    "TEXTURE_WRAP_T",
    "LINEAR",
    "LINEAR_MIPMAP_LINEAR",
    "CLAMP_TO_EDGE",
    "BLEND",
    "ONE",
    "ONE_MINUS_SRC_ALPHA",
    "COLOR_BUFFER_BIT",
    "TRIANGLE_STRIP",
]

TEXTS = {
    "t_empty": "",
    "t_div": "div",
    "t_canvas": "canvas",
    "t_2d": "2d",
    "t_webgl2": "webgl2",
    "t_round": "round",
    "t_white": "#fff",
    "t_u_rect": "u_rect",
    "t_u_alpha": "u_alpha",
    "e_down": "pointerdown",
    "e_move": "pointermove",
    "e_up": "pointerup",
    "e_dblclick": "dblclick",
    "e_wheel": "wheel",
    "e_ctxmenu": "contextmenu",
    "c_canvas": "ed_canvas",
    "c_toolbar": "ed_toolbar",
    "t_recenter": "Recenter",
    "t_fit": "Fit",
    "t_grid": "Grid",
}


# The handle types bound: (binding prefix, interface).
HANDLES = [
    ("canvas", "HTMLCanvasElement"),
    ("ctx2d", "CanvasRenderingContext2D"),
    ("gl", "WebGL2RenderingContext"),
    ("prog", "WebGLProgram"),
    ("shader", "WebGLShader"),
    ("tex", "WebGLTexture"),
    ("uloc", "WebGLUniformLocation"),
    ("mouse", "MouseEvent"),
    ("pointer", "PointerEvent"),
    ("wheel", "WheelEvent"),
    ("any", ""),
]
UI_TYPES = [
    "el_t",
    "el_own",
    "el_raw",
    "node_raw",
    "target_raw",
    "event_raw",
    "button_t",
    "button_own",
    "str_t",
    "str_of",
    "ev_cb_t",
    "listener_t",
]
VEC_TYPES = [("listeners", "listener_t"), ("buttons", "button_t"), ("ev_cbs", "ev_cb_t")]
# The child interface's methods, each taking the raw `Event`.
CHILD_METHODS = ["down", "move", "up", "dblclick"]
LEVEL1 = (
    ["t_pu8"]
    + UI_TYPES
    + [name + "_" + f for name, _ in VEC_TYPES for f in ["t", "own", "raw", "new"]]
    + ["cv_child_" + f for f in ["t", "own", "raw"]]
    + [pre + "_" + f for pre, _ in HANDLES for f in ["t", "own", "raw"]]
    + ["k_" + c for c in CONSTS]
)
TYPE_EXPORTS = ["cv_t", "cv_raw", "tex_t", "tex_own", "tex_raw", "cv_child_t", "cv_child_own"]
EXPORTS = [
    "cv_new",
    "cv_begin",
    "cv_image",
    "cv_tex_new",
    "cv_tex_set",
    "cv_style",
    "cv_line",
    "cv_circle",
    "cv_move",
    "cv_line_to",
    "cv_stroke",
    "cv_capture",
    "cv_wx",
    "cv_wy",
    "cv_scale",
    "cv_fit",
]


def module(e):
    k = Kit(e)
    # Level one: the handle types, the editor-ui types, the WebGL constants.
    x0 = []
    k.bind(x0)
    x0.append(e.let("t_pu8", e.call(e.fld(e.v("wasm"), "ptr"), e.v("t_u8"))))
    x0.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x0.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    for n in UI_TYPES:
        x0.append(e.let(n, e.fld(e.v("ui"), n)))
    # the listeners, the toolbar's buttons and their closures, vecs the record owns (made before the closures
    # capture it)
    x0.append(e.let("vec", e.import_local("vec", "vec-wasm.atz")))
    for name, elem in VEC_TYPES:
        x0.append(e.let(name + "_r", e.call(e.fld(e.v("vec"), "type"), e.v(elem))))
        for f in ["t", "own", "raw", "new"]:
            x0.append(e.let(name + "_" + f, e.fld(e.v(name + "_r"), "type" if f == "t" else f)))
    # the child interface
    x0.append(e.let("iface", e.import_local("iface", iface_wasm.FILE)))
    x0.append(
        e.let(
            "cv_child_r",
            e.call(
                e.fld(e.v("iface"), "declare"),
                e.rec(
                    p(
                        "methods",
                        e.rec(
                            *[p(m, e.rec(p("arg", e.v("event_raw")), p("ret", e.v("t_void")))) for m in CHILD_METHODS]
                        ),
                    )
                ),
            ),
        )
    )
    for f in ["t", "own", "raw"]:
        x0.append(e.let("cv_child_" + f, e.fld(e.v("cv_child_r"), f if f != "t" else "type")))
    for pre, iface in HANDLES:
        x0.append(e.let("h_" + pre, e.call(e.fld(e.v("webidl"), "handle"), e.s(iface))))
        for f in ["raw", "t", "own"]:
            x0.append(e.let(pre + "_" + f, e.fld(e.v("h_" + pre), "type" if f == "t" else f)))
    for c in CONSTS:
        x0.append(
            e.let(
                "k_" + c,
                e.call(
                    e.fld(e.v("webidl"), "const"), e.rec(p("iface", e.s("WebGL2RenderingContext")), p("member", e.s(c)))
                ),
            )
        )
    x0.append(e.ret(e.rec(*[p(n, e.v(n)) for n in LEVEL1])))

    # Level two: the record, the hooks and the dependencies.
    x = []
    k.bind(x)
    x.append(e.let("k0", e.lower(e.mb.seq(x0))))
    for n in LEVEL1:
        x.append(e.let(n, e.fld(e.v("k0"), n)))
    x.append(e.let("webidl", e.import_local("webidl", "webidl-wasm.atz")))
    x.append(e.let("math", e.import_local("math", math_wasm.FILE)))
    x.append(e.let("ui", e.import_local("ui", editor_ui.FILE)))
    x.append(e.let("record", e.import_local("record", record_wasm.FILE)))
    x.append(e.let("closure", e.import_local("closure", closure_wasm.FILE)))
    for bind, kind, iface, member in HOOKS:
        x.append(
            e.let(bind, e.call(e.fld(e.v("webidl"), kind), e.rec(p("iface", e.s(iface)), p("member", e.s(member)))))
        )
    for name, text in TEXTS.items():
        k.text(x, name, text)
    x.append(e.let("shaders", e.import_local("shaders", SHADERS_FILE)))
    for name in ["vs_text", "fs_text"]:
        x.append(e.let(name + "_len", e.fld(e.v("shaders"), name + "_len")))
        x.append(
            e.let(
                "c_" + name,
                e.call(
                    e.fld(e.v("wasm"), "cstr_dep"), e.rec(p("name", e.s(name)), p("text", e.fld(e.v("shaders"), name)))
                ),
            )
        )
    x.append(
        e.let(
            "cv_r", e.call(e.fld(e.v("record"), "type"), e.rec(p("fields", e.rec(*[p(f, e.v(t)) for f, t in FIELDS]))))
        )
    )
    for f in ["t", "raw"]:
        x.append(e.let("cv_" + f, e.fld(e.v("cv_r"), "type" if f == "t" else f)))
    x.append(e.let("cv_make", e.fld(e.v("cv_r"), "new")))
    v = e.v

    def M(f, *args):
        return k.lib("math", f, *args)

    def U(f, *args):
        return k.lib("ui", f, *args)

    def raw(pre, val):
        return e.mb.as_(val, k.lo(pre + "_raw"))

    def down(pre, val):
        """`val` (a raw handle) downcast to `pre`'s raw handle type."""
        return raw(pre, e.mb.as_(val, k.lo("t_i32")))

    def c(name):
        return e.fld(v("cv"), name)

    def trap():
        return e.call(fn_of(e, e.lower(e.fld(e.v("wasm"), "trap"))), e.tup())

    def ts(name):
        return k.sconst(name, TEXTS[name])

    def t(name):
        return k.sargs(ts(name))

    def K(cname):
        return k.lo("k_" + cname)

    def gl():
        return c("gl")

    def x2(name):
        return c(name)

    def f64(i):
        return e.mb.as_(i, k.lo("t_f64"))

    k.dep(
        x,
        "cv_canvas",
        ["parent"],
        ["node_raw"],
        "el_t",
        e.seq(
            e.let("el", U("el", v("parent"), ts("t_canvas"), k.sempty())),
            e.ret(k.m(v("el"), "move", e.tup())),
        ),
    )

    # The nullable results the canvas needs are never null here (a fresh canvas gives its contexts, a live WebGL
    # context its shaders and uniform locations): a missing one traps.
    k.dep(
        x,
        "cv_context",
        ["canvas", "kind", "len"],
        ["canvas_raw", "t_pu8", "t_u32"],
        "any_t",
        e.match_of(
            k.call("h_context", v("canvas"), v("kind"), v("len"), e.n(0), e.n(0)),
            "c",
            None,
            p("some", k.ret(k.m(v("c"), "move", e.tup()))),
            p("none", trap()),
        ),
    )
    k.dep(
        x,
        "cv_shader",
        ["gl", "kind"],
        ["gl_raw", "t_u32"],
        "shader_t",
        e.match_of(
            k.call("g_create_shader", v("gl"), v("kind")),
            "s",
            None,
            p("some", k.ret(k.m(v("s"), "move", e.tup()))),
            p("none", trap()),
        ),
    )
    k.dep(
        x,
        "cv_uloc",
        ["gl", "prog", "name", "len"],
        ["gl_raw", "prog_raw", "t_pu8", "t_u32"],
        "uloc_t",
        e.match_of(
            k.call("g_uniform_loc", v("gl"), v("prog"), v("name"), v("len")),
            "u",
            None,
            p("some", k.ret(k.m(v("u"), "move", e.tup()))),
            p("none", trap()),
        ),
    )

    def context(canvas, kind, own_name):
        """The canvas's context of `kind` as the owned context type `own_name`."""
        return e.mb.as_(k.dcall("cv_context", canvas, *t(kind)), k.lo(own_name))

    def shader(glv, prog, kind, text, len_name):
        """Statements compiling a shader and attaching it to `prog` (the shader handle released after)."""
        return [
            e.let("sh", k.dcall("cv_shader", glv, K(kind))),
            k.call("g_shader_source", glv, v("sh"), k.cstr(text), e.lower(e.v(len_name))),
            k.call("g_compile_shader", glv, v("sh")),
            k.call("g_attach", glv, prog, v("sh")),
        ]

    k.dep(x, "cv_scale", ["cv"], ["cv_raw"], "t_f64", e.ret(c("scale")))
    # The area captures the pointer of `ev` (a child's drag goes on outside the area).
    k.dep(
        x,
        "cv_capture",
        ["cv", "ev"],
        ["cv_raw", "event_raw"],
        "t_void",
        k.call("h_capture", c("c_over"), k.call("h_pointer_id", down("pointer", v("ev")))),
    )

    # world to CSS pixels of the area
    def sx(wx):
        return k.add(k.mul(k.sub(wx, c("cx")), c("scale")), k.mul(c("w"), e.n(0.5)))

    def sy(wy):
        return k.add(k.mul(k.sub(wy, c("cy")), c("scale")), k.mul(c("h"), e.n(0.5)))

    def wx_of(px):
        return k.add(c("cx"), k.div(k.sub(px, k.mul(c("w"), e.n(0.5))), c("scale")))

    def wy_of(py):
        return k.add(c("cy"), k.div(k.sub(py, k.mul(c("h"), e.n(0.5))), c("scale")))

    def set_world(ctx):
        """The 2D context drawing in world coordinates."""
        d = k.mul(c("scale"), c("dpr"))
        return k.call(
            "x_set_transform",
            x2(ctx),
            d,
            k.f64(0),
            k.f64(0),
            d,
            k.mul(k.sub(k.mul(c("w"), e.n(0.5)), k.mul(c("cx"), c("scale"))), c("dpr")),
            k.mul(k.sub(k.mul(c("h"), e.n(0.5)), k.mul(c("cy"), c("scale"))), c("dpr")),
        )

    def white(ctx):
        return [k.call("x_stroke_style", x2(ctx), *t("t_white")), k.call("x_fill_style", x2(ctx), *t("t_white"))]

    # The grid: lines every 1, 2 or 5 times a power of ten millimetres, at least 24 CSS pixels apart; the origin's
    # axes stronger.
    k.dep(
        x,
        "cv_grid_draw",
        ["cv"],
        ["cv_raw"],
        "t_void",
        e.seq(
            e.let("step", k.f64(1)),
            k.loop(
                "pick",
                k.if_(k.ge(k.mul(v("step"), c("scale")), e.n(24)), k.brk("pick")),
                k.ifelse(
                    k.lt(k.mul(k.mul(v("step"), e.n(2)), c("scale")), e.n(24)),
                    k.ifelse(
                        k.lt(k.mul(k.mul(v("step"), e.n(5)), c("scale")), e.n(24)),
                        e.mb.set(v("step"), k.mul(v("step"), e.n(10))),
                        e.mb.set(v("step"), k.mul(v("step"), e.n(5))),
                    ),
                    e.mb.set(v("step"), k.mul(v("step"), e.n(2))),
                ),
            ),
            k.loop(
                "shrink",
                k.if_(k.lt(k.mul(k.mul(v("step"), e.n(0.5)), c("scale")), e.n(24)), k.brk("shrink")),
                e.mb.set(v("step"), k.mul(v("step"), e.n(0.5))),
            ),
            set_world("x_grid"),
            *white("x_grid"),
            k.call("x_alpha", x2("x_grid"), k.f64(0.25)),
            k.call("x_line_width", x2("x_grid"), k.div(e.n(1), c("scale"))),
            e.let("x0", wx_of(k.f64(0))),
            e.let("x1", wx_of(c("w"))),
            e.let("y0", wy_of(k.f64(0))),
            e.let("y1", wy_of(c("h"))),
            k.call("x_begin", x2("x_grid")),
            e.let("gx", k.mul(k.floor(k.div(v("x0"), v("step"))), v("step"))),
            k.loop(
                "vert",
                k.if_(k.gt(v("gx"), v("x1")), k.brk("vert")),
                k.call("x_move", x2("x_grid"), v("gx"), v("y0")),
                k.call("x_line", x2("x_grid"), v("gx"), v("y1")),
                e.mb.set(v("gx"), k.add(v("gx"), v("step"))),
            ),
            e.let("gy", k.mul(k.floor(k.div(v("y0"), v("step"))), v("step"))),
            k.loop(
                "horiz",
                k.if_(k.gt(v("gy"), v("y1")), k.brk("horiz")),
                k.call("x_move", x2("x_grid"), v("x0"), v("gy")),
                k.call("x_line", x2("x_grid"), v("x1"), v("gy")),
                e.mb.set(v("gy"), k.add(v("gy"), v("step"))),
            ),
            k.call("x_stroke", x2("x_grid")),
            k.call("x_alpha", x2("x_grid"), k.f64(0.6)),
            k.call("x_begin", x2("x_grid")),
            k.call("x_move", x2("x_grid"), k.f64(0), v("y0")),
            k.call("x_line", x2("x_grid"), k.f64(0), v("y1")),
            k.call("x_move", x2("x_grid"), v("x0"), k.f64(0)),
            k.call("x_line", x2("x_grid"), v("x1"), k.f64(0)),
            k.call("x_stroke", x2("x_grid")),
            k.call("x_alpha", x2("x_grid"), k.f64(1)),
        ),
    )
    # The area's CSS size and the device pixel ratio, as they are now.
    k.dep(
        x,
        "cv_measure",
        ["cv"],
        ["cv_raw"],
        "t_void",
        e.seq(
            e.let("win", e.call(e.lower(e.fld(e.v("webidl"), "global")), e.tup())),
            k.set(c("dpr"), k.call("h_dpr", v("win"))),
            k.set(c("w"), f64(k.call("h_client_w", c("el")))),
            k.set(c("h"), f64(k.call("h_client_h", c("el")))),
        ),
    )
    k.dep(
        x,
        "cv_begin",
        ["cv"],
        ["cv_raw"],
        "t_void",
        e.seq(
            k.dcall("cv_measure", v("cv")),
            e.let("pw", k.trunc(k.ceil(k.mul(c("w"), c("dpr"))))),
            e.let("ph", k.trunc(k.ceil(k.mul(c("h"), c("dpr"))))),
            k.if_(
                k.or_(k.ne(v("pw"), c("pw")), k.ne(v("ph"), c("ph"))),
                k.set(c("pw"), v("pw")),
                k.set(c("ph"), v("ph")),
                *[
                    e.seq(
                        k.call("h_set_w", c(cn), k.m(v("pw"), "wrap", k.lo("t_u32"))),
                        k.call("h_set_h", c(cn), k.m(v("ph"), "wrap", k.lo("t_u32"))),
                    )
                    for cn in ["c_grid", "c_gl", "c_over"]
                ],
                k.call("x_cap", x2("x_over"), *t("t_round")),
                k.call("x_join", x2("x_over"), *t("t_round")),
            ),
            *[
                e.seq(
                    k.call("x_reset", x2(ctx)),
                    k.call("x_clear", x2(ctx), k.f64(0), k.f64(0), f64(c("pw")), f64(c("ph"))),
                )
                for ctx in ["x_grid", "x_over"]
            ],
            k.call("g_viewport", gl(), e.n(0), e.n(0), c("pw"), c("ph")),
            k.call("g_clear_color", gl(), e.n(0), e.n(0), e.n(0), e.n(0)),
            k.call("g_clear", gl(), K("COLOR_BUFFER_BIT")),
            k.if_(k.ne(c("grid_on"), e.n(0)), k.dcall("cv_grid_draw", v("cv"))),
            set_world("x_over"),
        ),
    )
    k.dep(
        x,
        "cv_style",
        ["cv", "alpha", "width"],
        ["cv_raw", "t_f64", "t_f64"],
        "t_void",
        e.seq(
            *white("x_over"),
            k.call("x_alpha", x2("x_over"), v("alpha")),
            k.call("x_line_width", x2("x_over"), k.div(v("width"), c("scale"))),
        ),
    )
    k.dep(
        x,
        "cv_line",
        ["cv", "x0", "y0", "x1", "y1"],
        ["cv_raw", "t_f64", "t_f64", "t_f64", "t_f64"],
        "t_void",
        e.seq(
            k.call("x_begin", x2("x_over")),
            k.call("x_move", x2("x_over"), v("x0"), v("y0")),
            k.call("x_line", x2("x_over"), v("x1"), v("y1")),
            k.call("x_stroke", x2("x_over")),
        ),
    )
    k.dep(
        x,
        "cv_circle",
        ["cv", "x", "y", "r", "fill"],
        ["cv_raw", "t_f64", "t_f64", "t_f64", "t_i32"],
        "t_void",
        e.seq(
            k.call("x_begin", x2("x_over")),
            k.call("x_arc", x2("x_over"), v("x"), v("y"), v("r"), k.f64(0), k.f64(6.283185307179586), e.n(0), e.n(0)),
            k.ifelse(
                k.ne(v("fill"), e.n(0)),
                k.call("x_fill", x2("x_over"), e.n(0), e.n(0), e.n(0)),
                k.call("x_stroke", x2("x_over")),
            ),
        ),
    )
    # A path: `cv_move` starts it at a point, `cv_line_to` extends it, `cv_stroke` strokes it.
    k.dep(
        x,
        "cv_move",
        ["cv", "x", "y"],
        ["cv_raw", "t_f64", "t_f64"],
        "t_void",
        e.seq(k.call("x_begin", x2("x_over")), k.call("x_move", x2("x_over"), v("x"), v("y"))),
    )
    k.dep(
        x,
        "cv_line_to",
        ["cv", "x", "y"],
        ["cv_raw", "t_f64", "t_f64"],
        "t_void",
        k.call("x_line", x2("x_over"), v("x"), v("y")),
    )
    k.dep(x, "cv_stroke", ["cv"], ["cv_raw"], "t_void", k.call("x_stroke", x2("x_over")))
    k.dep(
        x,
        "cv_tex_new",
        ["cv"],
        ["cv_raw"],
        "tex_t",
        e.seq(
            e.let("tex", k.call("g_create_tex", gl())),
            k.call("g_bind_tex", gl(), K("TEXTURE_2D"), e.n(1), v("tex")),
            k.call("g_tex_param", gl(), K("TEXTURE_2D"), K("TEXTURE_MIN_FILTER"), K("LINEAR_MIPMAP_LINEAR")),
            k.call("g_tex_param", gl(), K("TEXTURE_2D"), K("TEXTURE_MAG_FILTER"), K("LINEAR")),
            k.call("g_tex_param", gl(), K("TEXTURE_2D"), K("TEXTURE_WRAP_S"), K("CLAMP_TO_EDGE")),
            k.call("g_tex_param", gl(), K("TEXTURE_2D"), K("TEXTURE_WRAP_T"), K("CLAMP_TO_EDGE")),
            e.ret(k.m(v("tex"), "move", e.tup())),
        ),
    )
    k.dep(
        x,
        "cv_tex_set",
        ["cv", "tex", "w", "h", "ptr"],
        ["cv_raw", "tex_raw", "t_i32", "t_i32", "t_pu8"],
        "t_void",
        e.seq(
            k.call("g_bind_tex", gl(), K("TEXTURE_2D"), e.n(1), v("tex")),
            k.call(
                "g_tex_image",
                gl(),
                K("TEXTURE_2D"),
                e.n(0),
                K("RGBA"),
                v("w"),
                v("h"),
                e.n(0),
                K("RGBA"),
                K("UNSIGNED_BYTE"),
                e.n(1),
                v("ptr"),
                k.m(k.mul(k.mul(v("w"), v("h")), e.n(4)), "wrap", k.lo("t_u32")),
            ),
            k.call("g_mipmap", gl(), K("TEXTURE_2D")),
        ),
    )

    def clip_x(wx):
        return k.sub(k.mul(k.div(sx(wx), c("w")), e.n(2)), e.n(1))

    def clip_y(wy):
        return k.sub(e.n(1), k.mul(k.div(sy(wy), c("h")), e.n(2)))

    def f32(val):
        return k.m(val, "to_float", k.lo("t_f32"))

    k.dep(
        x,
        "cv_image",
        ["cv", "tex", "x0", "y0", "x1", "y1", "alpha"],
        ["cv_raw", "tex_raw", "t_f64", "t_f64", "t_f64", "t_f64", "t_f64"],
        "t_void",
        e.seq(
            k.call("g_bind_tex", gl(), K("TEXTURE_2D"), e.n(1), v("tex")),
            k.call(
                "g_uniform4f",
                gl(),
                e.n(1),
                c("u_rect"),
                f32(clip_x(v("x0"))),
                f32(clip_y(v("y0"))),
                f32(clip_x(v("x1"))),
                f32(clip_y(v("y1"))),
            ),
            k.call("g_uniform1f", gl(), e.n(1), c("u_alpha"), f32(v("alpha"))),
            k.call("g_draw", gl(), K("TRIANGLE_STRIP"), e.n(0), e.n(4)),
        ),
    )
    k.dep(
        x,
        "cv_wx",
        ["cv", "ev"],
        ["cv_raw", "event_raw"],
        "t_f64",
        e.ret(wx_of(k.call("h_offset_x", down("mouse", v("ev"))))),
    )
    k.dep(
        x,
        "cv_wy",
        ["cv", "ev"],
        ["cv_raw", "event_raw"],
        "t_f64",
        e.ret(wy_of(k.call("h_offset_y", down("mouse", v("ev"))))),
    )
    k.dep(
        x,
        "cv_pointer",
        ["cv", "ev", "kind"],
        ["cv_raw", "event_raw", "t_i32"],
        "t_i32",
        e.seq(
            e.let("me", down("mouse", v("ev"))),
            e.let("px", f64(k.call("h_client_x", v("me")))),
            e.let("py", f64(k.call("h_client_y", v("me")))),
            k.if_(
                k.eq(v("kind"), e.n(0)),
                e.let("button", e.mb.as_(k.call("h_button", v("me")), k.lo("t_i32"))),
                k.if_(k.and_(k.ne(v("button"), e.n(1)), k.ne(v("button"), e.n(2))), k.ret(k.i32(0))),
                k.set(c("panning"), e.n(1)),
                k.set(c("pan_x"), v("px")),
                k.set(c("pan_y"), v("py")),
                k.call("h_capture", c("c_over"), k.call("h_pointer_id", down("pointer", v("ev")))),
                U("prevent", v("ev")),
                k.ret(k.i32(1)),
            ),
            k.if_(k.eq(c("panning"), e.n(0)), k.ret(k.i32(0))),
            k.set(c("cx"), k.sub(c("cx"), k.div(k.sub(v("px"), c("pan_x")), c("scale")))),
            k.set(c("cy"), k.sub(c("cy"), k.div(k.sub(v("py"), c("pan_y")), c("scale")))),
            k.set(c("pan_x"), v("px")),
            k.set(c("pan_y"), v("py")),
            k.if_(k.eq(v("kind"), e.n(2)), k.set(c("panning"), e.n(0))),
            e.ret(k.i32(1)),
        ),
    )
    k.dep(
        x,
        "cv_wheel",
        ["cv", "ev"],
        ["cv_raw", "event_raw"],
        "t_void",
        e.seq(
            U("prevent", v("ev")),
            e.let("dy", k.call("h_delta_y", down("wheel", v("ev")))),
            # lines and pages as about 16 and 400 pixels
            e.let("mode", k.m(k.call("h_delta_mode", down("wheel", v("ev"))), "wrap", k.lo("t_i32"))),
            k.if_(k.eq(v("mode"), e.n(1)), e.mb.set(v("dy"), k.mul(v("dy"), e.n(16)))),
            k.if_(k.eq(v("mode"), e.n(2)), e.mb.set(v("dy"), k.mul(v("dy"), e.n(400)))),
            e.let("ox", k.call("h_offset_x", down("mouse", v("ev")))),
            e.let("oy", k.call("h_offset_y", down("mouse", v("ev")))),
            e.let("wx", wx_of(v("ox"))),
            e.let("wy", wy_of(v("oy"))),
            e.let("f", M("m_exp", k.mul(v("dy"), e.n(-0.0015)))),
            k.set(c("scale"), M("m_clamp", k.mul(c("scale"), v("f")), k.f64(0.01), k.f64(10000))),
            k.set(c("cx"), k.sub(v("wx"), k.div(k.sub(v("ox"), k.mul(c("w"), e.n(0.5))), c("scale")))),
            k.set(c("cy"), k.sub(v("wy"), k.div(k.sub(v("oy"), k.mul(c("h"), e.n(0.5))), c("scale")))),
        ),
    )
    k.dep(
        x,
        "cv_recenter",
        ["cv"],
        ["cv_raw"],
        "t_void",
        e.seq(k.set(c("cx"), k.f64(0)), k.set(c("cy"), k.f64(0)), k.set(c("scale"), k.f64(PX_PER_MM))),
    )
    k.dep(
        x,
        "cv_fit",
        ["cv", "x0", "y0", "x1", "y1"],
        ["cv_raw", "t_f64", "t_f64", "t_f64", "t_f64"],
        "t_void",
        e.seq(
            k.if_(k.or_(k.le(v("x1"), v("x0")), k.le(v("y1"), v("y0"))), k.dcall("cv_recenter", v("cv")), k.ret()),
            k.dcall("cv_measure", v("cv")),
            k.set(c("cx"), k.mul(k.add(v("x0"), v("x1")), e.n(0.5))),
            k.set(c("cy"), k.mul(k.add(v("y0"), v("y1")), e.n(0.5))),
            k.set(
                c("scale"),
                k.mul(k.fmin(k.div(c("w"), k.sub(v("x1"), v("x0"))), k.div(c("h"), k.sub(v("y1"), v("y0")))), e.n(0.9)),
            ),
        ),
    )
    k.dep(x, "cv_grid", ["cv"], ["cv_raw"], "t_void", k.set(c("grid_on"), k.sub(e.n(1), c("grid_on"))))
    # The canvas's closures (editor-ui's `ev_cb`), each capturing it: the toolbar's change its view; the listeners'
    # pan (`cv_pointer`, else the child gets the event), zoom, suppress the context menu and pass double clicks on.
    # The event is released after.
    cap = e.fld(e.v("self"), "cv")

    def child(method):
        return e.call(e.fld(e.fld(cap, "child"), method), e.v("arg"))

    closures = [
        ("recenter_make", k.dcall("cv_recenter", cap)),
        ("grid_make", k.dcall("cv_grid", cap)),
        *[
            (m + "_make", k.if_(k.eq(k.dcall("cv_pointer", cap, e.v("arg"), e.n(kind)), e.n(0)), child(m)))
            for kind, m in enumerate(["down", "move", "up"])
        ],
        ("dblclick_make", child("dblclick")),
        ("wheel_make", k.dcall("cv_wheel", cap, e.v("arg"))),
        ("ctxmenu_make", U("prevent", e.v("arg"))),
    ]
    for name, body_ in closures:
        x.append(
            e.let(
                name,
                e.fld(
                    e.call(
                        e.fld(e.v("closure"), "new"),
                        e.rec(
                            p("callable", e.v("ev_cb_t")),
                            p("capture", e.rec(p("cv", e.v("cv_raw")))),
                            p("body", e.stage(body_)),
                        ),
                    ),
                    "make",
                ),
            )
        )

    def own_closure(name):
        """A closure capturing the canvas (its record, borrowed through its binding `cv`), pushed on its closures."""
        return k.m(c("cbs"), "push", e.call(fn_of(e, k.lo(name)), e.rec(p("cv", raw("cv", v("cv"))))))

    def last_cb():
        return k.m(c("cbs"), "at", k.sub(e.fld(c("cbs"), "len"), e.n(1)))

    k.dep(
        x,
        "cv_new",
        ["parent", "fit", "child"],
        ["node_raw", "ev_cb_t", "cv_child_t"],
        "cv_t",
        e.seq(
            e.let("el", U("el", v("parent"), ts("t_div"), ts("c_canvas"))),
            *[
                stmt
                for cn in ["c_grid", "c_gl", "c_over"]
                for stmt in [
                    e.let("cv_el", k.dcall("cv_canvas", raw("node", v("el")))),
                    e.let(cn, e.mb.as_(k.m(v("cv_el"), "move", e.tup()), k.lo("canvas_own"))),
                ]
            ],
            e.let("bar", U("el", raw("node", v("el")), ts("t_div"), ts("c_toolbar"))),
            e.let("x_grid", context(v("c_grid"), "t_2d", "ctx2d_own")),
            e.let("x_over", context(v("c_over"), "t_2d", "ctx2d_own")),
            e.let("gl", context(v("c_gl"), "t_webgl2", "gl_own")),
            k.call("x_cap", v("x_over"), *t("t_round")),
            k.call("x_join", v("x_over"), *t("t_round")),
            # The tile program.
            e.let("prog", k.call("g_create_program", v("gl"))),
            *shader(v("gl"), v("prog"), "VERTEX_SHADER", "c_vs_text", "vs_text_len"),
            *shader(v("gl"), v("prog"), "FRAGMENT_SHADER", "c_fs_text", "fs_text_len"),
            k.call("g_link", v("gl"), v("prog")),
            k.call("g_use", v("gl"), e.n(1), v("prog")),
            e.let("u_rect", k.dcall("cv_uloc", v("gl"), v("prog"), *t("t_u_rect"))),
            e.let("u_alpha", k.dcall("cv_uloc", v("gl"), v("prog"), *t("t_u_alpha"))),
            k.call("g_enable", v("gl"), K("BLEND")),
            k.call("g_blend", v("gl"), K("ONE"), K("ONE_MINUS_SRC_ALPHA")),
            e.let(
                "cv",
                k.call(
                    "cv_make",
                    e.rec(
                        *[p(f, k.m(v(f), "move", e.tup())) for f, _ in FIELDS[:10]],
                        p("listeners", k.call("listeners_new", e.tup())),
                        p("buttons", k.call("buttons_new", e.tup())),
                        p("cbs", k.call("ev_cbs_new", e.tup())),
                        p("child", k.m(v("child"), "move", e.tup())),
                        p("fit", k.m(v("fit"), "move", e.tup())),
                        p("grid_on", k.i32(1)),
                        p("panning", k.i32(0)),
                        p("pw", k.i32(0)),
                        p("ph", k.i32(0)),
                        p("w", k.f64(0)),
                        p("h", k.f64(0)),
                        p("dpr", k.f64(1)),
                        p("cx", k.f64(0)),
                        p("cy", k.f64(0)),
                        p("scale", k.f64(PX_PER_MM)),
                        p("pan_x", k.f64(0)),
                        p("pan_y", k.f64(0)),
                    ),
                ),
            ),
            # the listeners and the toolbar's buttons over closures capturing the canvas (made now that the record
            # exists)
            *[
                stmt
                for ev in ["down", "move", "up", "dblclick", "wheel", "ctxmenu"]
                for stmt in [
                    own_closure(ev + "_make"),
                    k.m(c("listeners"), "push", U("listen", c("c_over"), ts("e_" + ev), last_cb())),
                ]
            ],
            own_closure("recenter_make"),
            k.m(c("buttons"), "push", U("button", raw("node", v("bar")), ts("t_recenter"), last_cb())),
            k.m(c("buttons"), "push", U("button", raw("node", v("bar")), ts("t_fit"), c("fit"))),
            own_closure("grid_make"),
            k.m(c("buttons"), "push", U("button", raw("node", v("bar")), ts("t_grid"), last_cb())),
            e.ret(k.m(v("cv"), "move", e.tup())),
        ),
    )
    return library(e, x, TYPE_EXPORTS, EXPORTS)
