"""math-wasm.atz's elementary functions in wasm (fdlibm's argument reductions and kernel polynomials), so every
browser computes the same results: `m_exp`, `m_log`, `m_pow` (a positive base), `m_sin`, `m_cos` (arguments up to
about 1e9 in magnitude) and `m_atan2`."""

# sin and cos on [-pi/4, pi/4], exp on [-ln2/2, ln2/2], log of a mantissa in [sqrt(2)/2, sqrt(2)), atan on
# [-7/16, 7/16] with the breakpoints' values.
SIN = [
    -1.66666666666666324348e-01,
    8.33333333332248946124e-03,
    -1.98412698298579493134e-04,
    2.75573137070700676789e-06,
    -2.50507602534068634195e-08,
    1.58969099521155010221e-10,
]
COS = [
    4.16666666666666019037e-02,
    -1.38888888888741095749e-03,
    2.48015872894767294178e-05,
    -2.75573143513906633035e-07,
    2.08757232129817482790e-09,
    -1.13596475577881948265e-11,
]
EXP = [
    1.66666666666666019037e-01,
    -2.77777777770155933842e-03,
    6.61375632143793436117e-05,
    -1.65339022054652515390e-06,
    4.13813679705723846039e-08,
]
LOG = [
    6.666666666666735130e-01,
    3.999999999940941908e-01,
    2.857142874366239149e-01,
    2.222219843214978396e-01,
    1.818357216161805012e-01,
    1.531383769920937332e-01,
    1.479819860511658591e-01,
]
ATAN = [
    3.33333333333329318027e-01,
    -1.99999999998764832476e-01,
    1.42857142725034663711e-01,
    -1.11111104054623557880e-01,
    9.09088713343650656196e-02,
    -7.69187620504482999495e-02,
    6.66107313738753120669e-02,
    -5.83357013379057348645e-02,
    4.97687799461593236017e-02,
    -3.65315727442169155270e-02,
    1.62858201153657823623e-02,
]
ATAN_HI = [
    4.63647609000806093515e-01,
    7.85398163397448278999e-01,
    9.82793723247329054082e-01,
    1.57079632679489655800e00,
]
ATAN_LO = [
    2.26987774529616870924e-17,
    3.06161699786838301793e-17,
    1.39033110312309984516e-17,
    6.12323399573676603587e-17,
]
PIO2_1 = 1.57079632673412561417e00
PIO2_1T = 6.07710050650619224932e-11
TWO_OVER_PI = 6.36619772367581382433e-01
LN2_HI = 6.93147180369123816490e-01
LN2_LO = 1.90821492927058770002e-10
INV_LN2 = 1.44269504088896338700e00
PI = 3.141592653589793
TWO32 = 4294967296.0


def _poly(k, z, coeffs):
    """coeffs[0] + z * (coeffs[1] + z * (...)) (Horner)."""
    acc = k.f64(coeffs[-1])
    for c in reversed(coeffs[:-1]):
        acc = k.add(k.f64(c), k.mul(z, acc))
    return acc


def define(e, k, x):
    """Adds the functions' dependencies to the setup `x`."""
    v = e.v
    f = k.f64

    def setv(name, val):
        return e.mb.set(v(name), val)

    inf = k.div(f(1), f(0))
    # 2^n for an i32 n, by squaring (exact wherever a double can be scaled by it).
    k.dep(
        x,
        "m_pow2",
        ["n"],
        ["t_i32"],
        "t_f64",
        e.seq(
            e.let("base", k.ifelse(k.lt(v("n"), e.n(0)), f(0.5), f(2))),
            e.let("m", k.ifelse(k.lt(v("n"), e.n(0)), k.neg(v("n")), v("n"))),
            e.let("r", f(1)),
            k.loop(
                "bits",
                k.if_(k.eq(v("m"), e.n(0)), k.brk("bits")),
                k.if_(k.ne(k.band(v("m"), e.n(1)), e.n(0)), setv("r", k.mul(v("r"), v("base")))),
                setv("base", k.mul(v("base"), v("base"))),
                setv("m", k.shr(v("m"), e.n(1))),
            ),
            e.ret(v("r")),
        ),
    )
    k.dep(
        x,
        "m_exp",
        ["x"],
        ["t_f64"],
        "t_f64",
        e.seq(
            k.if_(k.ne(v("x"), v("x")), k.ret(v("x"))),
            k.if_(k.gt(v("x"), e.n(709.782712893384)), k.ret(inf)),
            k.if_(k.lt(v("x"), e.n(-745.1332191019412)), k.ret(f(0))),
            e.let("kf", k.m(k.mul(v("x"), e.n(INV_LN2)), "nearest", e.tup())),
            e.let("r", k.sub(k.sub(v("x"), k.mul(v("kf"), e.n(LN2_HI))), k.mul(v("kf"), e.n(LN2_LO)))),
            e.let("rr", k.mul(v("r"), v("r"))),
            e.let("c", k.sub(v("r"), k.mul(v("rr"), _poly(k, v("rr"), EXP)))),
            e.let("er", k.sub(f(1), k.sub(k.div(k.mul(v("r"), v("c")), k.sub(v("c"), e.n(2))), v("r")))),
            e.let("ki", k.trunc(v("kf"))),
            # 2^k in two steps where it alone would underflow
            k.if_(
                k.lt(v("ki"), e.n(-1000)),
                k.ret(
                    k.mul(k.mul(v("er"), k.dcall("m_pow2", k.add(v("ki"), e.n(500)))), k.dcall("m_pow2", k.i32(-500)))
                ),
            ),
            e.ret(k.mul(v("er"), k.dcall("m_pow2", v("ki")))),
        ),
    )

    def scale_loop(label, cond, factor, step):
        return k.loop(
            label,
            k.if_(cond, k.brk(label)),
            setv("m", k.mul(v("m"), e.n(factor))),
            setv("ex", k.add(v("ex"), e.n(step))),
        )

    k.dep(
        x,
        "m_log",
        ["x"],
        ["t_f64"],
        "t_f64",
        e.seq(
            k.if_(k.ne(v("x"), v("x")), k.ret(v("x"))),
            k.if_(k.eq(v("x"), e.n(0)), k.ret(k.neg(inf))),
            k.if_(k.lt(v("x"), e.n(0)), k.ret(k.div(f(0), f(0)))),
            k.if_(k.eq(v("x"), inf), k.ret(v("x"))),
            # x = m * 2^ex with m in [sqrt(2)/2, sqrt(2))
            e.let("m", v("x")),
            e.let("ex", k.i32(0)),
            scale_loop("big", k.lt(v("m"), e.n(TWO32)), 1 / TWO32, 32),
            scale_loop("small", k.ge(v("m"), e.n(1 / TWO32)), TWO32, -32),
            scale_loop("down", k.lt(v("m"), e.n(1.4142135623730951)), 0.5, 1),
            scale_loop("up", k.ge(v("m"), e.n(0.7071067811865476)), 2, -1),
            e.let("fm", k.sub(v("m"), e.n(1))),
            e.let("sv", k.div(v("fm"), k.add(e.n(2), v("fm")))),
            e.let("z", k.mul(v("sv"), v("sv"))),
            e.let("w", k.mul(v("z"), v("z"))),
            e.let("t1", k.mul(v("w"), _poly(k, v("w"), [LOG[1], LOG[3], LOG[5]]))),
            e.let("t2", k.mul(v("z"), _poly(k, v("w"), [LOG[0], LOG[2], LOG[4], LOG[6]]))),
            e.let("rr", k.add(v("t2"), v("t1"))),
            e.let("hfsq", k.mul(k.mul(e.n(0.5), v("fm")), v("fm"))),
            e.let("lm", k.sub(v("fm"), k.sub(v("hfsq"), k.mul(v("sv"), k.add(v("hfsq"), v("rr")))))),
            e.let("ef", k.to_f64(v("ex"))),
            e.ret(k.add(k.mul(v("ef"), e.n(LN2_HI)), k.add(v("lm"), k.mul(v("ef"), e.n(LN2_LO))))),
        ),
    )
    k.dep(
        x,
        "m_pow",
        ["x", "y"],
        ["t_f64", "t_f64"],
        "t_f64",
        e.seq(
            k.if_(k.eq(v("y"), e.n(0)), k.ret(f(1))),
            k.if_(k.eq(v("x"), e.n(0)), k.ret(f(0))),
            e.ret(k.dcall("m_exp", k.mul(v("y"), k.dcall("m_log", v("x"))))),
        ),
    )
    # sin (cosine 0) and cos (cosine 1): the argument less the nearest multiple n of pi/2, then the kernel of the
    # quadrant n + cosine.
    k.dep(
        x,
        "m_sincos",
        ["x", "cosine"],
        ["t_f64", "t_i32"],
        "t_f64",
        e.seq(
            k.if_(k.ne(v("x"), v("x")), k.ret(v("x"))),
            e.let("nf", k.m(k.mul(v("x"), e.n(TWO_OVER_PI)), "nearest", e.tup())),
            e.let("y", k.sub(k.sub(v("x"), k.mul(v("nf"), e.n(PIO2_1))), k.mul(v("nf"), e.n(PIO2_1T)))),
            e.let("q", k.band(k.add(k.trunc(v("nf")), v("cosine")), e.n(3))),
            e.let("z", k.mul(v("y"), v("y"))),
            e.let("ks", k.add(v("y"), k.mul(k.mul(v("z"), v("y")), _poly(k, v("z"), SIN)))),
            e.let(
                "kc", k.add(k.sub(f(1), k.mul(e.n(0.5), v("z"))), k.mul(k.mul(v("z"), v("z")), _poly(k, v("z"), COS)))
            ),
            k.if_(k.eq(v("q"), e.n(0)), k.ret(v("ks"))),
            k.if_(k.eq(v("q"), e.n(1)), k.ret(v("kc"))),
            k.if_(k.eq(v("q"), e.n(2)), k.ret(k.neg(v("ks")))),
            e.ret(k.neg(v("kc"))),
        ),
    )
    k.dep(x, "m_sin", ["x"], ["t_f64"], "t_f64", e.ret(k.dcall("m_sincos", v("x"), k.i32(0))))
    k.dep(x, "m_cos", ["x"], ["t_f64"], "t_f64", e.ret(k.dcall("m_sincos", v("x"), k.i32(1))))
    # atan of a non-negative x
    k.dep(
        x,
        "m_atan_pos",
        ["x"],
        ["t_f64"],
        "t_f64",
        e.seq(
            e.let("id", k.i32(-1)),
            k.if_(
                k.ge(v("x"), e.n(0.4375)),
                k.ifelse(
                    k.lt(v("x"), e.n(0.6875)),
                    e.seq(
                        setv("id", e.n(0)),
                        setv("x", k.div(k.sub(k.mul(e.n(2), v("x")), e.n(1)), k.add(e.n(2), v("x")))),
                    ),
                    k.ifelse(
                        k.lt(v("x"), e.n(1.1875)),
                        e.seq(setv("id", e.n(1)), setv("x", k.div(k.sub(v("x"), e.n(1)), k.add(v("x"), e.n(1))))),
                        k.ifelse(
                            k.lt(v("x"), e.n(2.4375)),
                            e.seq(
                                setv("id", e.n(2)),
                                setv("x", k.div(k.sub(v("x"), e.n(1.5)), k.add(e.n(1), k.mul(e.n(1.5), v("x"))))),
                            ),
                            e.seq(setv("id", e.n(3)), setv("x", k.div(e.n(-1), v("x")))),
                        ),
                    ),
                ),
            ),
            e.let("z", k.mul(v("x"), v("x"))),
            e.let("w", k.mul(v("z"), v("z"))),
            e.let("s1", k.mul(v("z"), _poly(k, v("w"), ATAN[0::2]))),
            e.let("s2", k.mul(v("w"), _poly(k, v("w"), ATAN[1::2]))),
            k.if_(k.lt(v("id"), e.n(0)), k.ret(k.sub(v("x"), k.mul(v("x"), k.add(v("s1"), v("s2")))))),
            *[
                k.if_(
                    k.eq(v("id"), e.n(i)),
                    k.ret(
                        k.sub(
                            f(ATAN_HI[i]), k.sub(k.sub(k.mul(v("x"), k.add(v("s1"), v("s2"))), e.n(ATAN_LO[i])), v("x"))
                        )
                    ),
                )
                for i in range(3)
            ],
            e.ret(k.sub(f(ATAN_HI[3]), k.sub(k.sub(k.mul(v("x"), k.add(v("s1"), v("s2"))), e.n(ATAN_LO[3])), v("x")))),
        ),
    )
    k.dep(
        x,
        "m_atan2",
        ["y", "x"],
        ["t_f64", "t_f64"],
        "t_f64",
        e.seq(
            k.if_(k.or_(k.ne(v("x"), v("x")), k.ne(v("y"), v("y"))), k.ret(k.add(v("x"), v("y")))),
            k.if_(
                k.eq(v("x"), e.n(0)),
                k.if_(k.gt(v("y"), e.n(0)), k.ret(f(PI / 2))),
                k.if_(k.lt(v("y"), e.n(0)), k.ret(f(-PI / 2))),
                k.ret(f(0)),
            ),
            e.let("t", k.dcall("m_atan_pos", k.fabs(k.div(v("y"), v("x"))))),
            e.let("a", k.ifelse(k.lt(k.mul(v("y"), v("x")), e.n(0)), k.neg(v("t")), v("t"))),
            k.if_(k.gt(v("x"), e.n(0)), k.ret(v("a"))),
            k.if_(k.ge(v("y"), e.n(0)), k.ret(k.add(v("a"), e.n(PI)))),
            e.ret(k.sub(v("a"), e.n(PI))),
        ),
    )
