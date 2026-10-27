# expression parser + curve sampling, no fusion imports so it can be tested on its own

import math

# expression language


class ExprError(Exception):
    pass


def _sign(x):
    return (x > 0) - (x < 0)


def _rint(x):
    return float(round(x))


def _avg(*a):
    return sum(a) / len(a)


# name: (func, min args, max args), None = any number
FUNCTIONS = {
    'sin': (math.sin, 1, 1), 'cos': (math.cos, 1, 1), 'tan': (math.tan, 1, 1),
    'asin': (math.asin, 1, 1), 'acos': (math.acos, 1, 1), 'atan': (math.atan, 1, 1),
    'sinh': (math.sinh, 1, 1), 'cosh': (math.cosh, 1, 1), 'tanh': (math.tanh, 1, 1),
    'asinh': (math.asinh, 1, 1), 'acosh': (math.acosh, 1, 1), 'atanh': (math.atanh, 1, 1),
    'log2': (math.log2, 1, 1), 'log10': (math.log10, 1, 1),
    'log': (math.log, 1, 1), 'ln': (math.log, 1, 1),  # both natural log, like muparser
    'exp': (math.exp, 1, 1), 'sqrt': (math.sqrt, 1, 1),
    'sign': (_sign, 1, 1), 'rint': (_rint, 1, 1), 'abs': (abs, 1, 1),
    'min': (min, 1, None), 'max': (max, 1, None),
    'sum': (lambda *a: math.fsum(a), 1, None), 'avg': (_avg, 1, None),
    # extras
    'arcsin': (math.asin, 1, 1), 'arccos': (math.acos, 1, 1), 'arctan': (math.atan, 1, 1),
    'arctan2': (math.atan2, 2, 2),  # solidworks style names
    'atan2': (math.atan2, 2, 2), 'pow': (math.pow, 2, 2), 'hypot': (math.hypot, 2, 2),
    'floor': (lambda x: float(math.floor(x)), 1, 1),
    'ceil': (lambda x: float(math.ceil(x)), 1, 1),
    'mod': (math.fmod, 2, 2), 'fmod': (math.fmod, 2, 2),
    'sec': (lambda x: 1.0 / math.cos(x), 1, 1),
    'csc': (lambda x: 1.0 / math.sin(x), 1, 1),
    'cot': (lambda x: 1.0 / math.tan(x), 1, 1),
    'deg': (math.degrees, 1, 1), 'rad': (math.radians, 1, 1),
}

CONSTANTS = {'pi': math.pi, '_pi': math.pi, 'e': math.e, '_e': math.e}
VARIABLES = ('t',)

_TWO_CHAR_OPS = ('&&', '||', '<=', '>=', '==', '!=', '**')
_ONE_CHAR_OPS = '+-*/^(),?:<>'


def _tokenize(src):
    toks = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and src[i + 1].isdigit()):
            j = i
            while j < n and (src[j].isdigit() or src[j] == '.'):
                j += 1
            if j < n and src[j] in 'eE':
                k = j + 1
                if k < n and src[k] in '+-':
                    k += 1
                if k < n and src[k].isdigit():
                    j = k
                    while j < n and src[j].isdigit():
                        j += 1
            text = src[i:j]
            try:
                toks.append(('num', float(text), i))
            except ValueError:
                raise ExprError("Bad number '%s' at position %d" % (text, i + 1))
            i = j
            continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'):
                j += 1
            toks.append(('id', src[i:j], i))
            i = j
            continue
        two = src[i:i + 2]
        if two in _TWO_CHAR_OPS:
            toks.append(('op', '^' if two == '**' else two, i))
            i += 2
            continue
        if c in _ONE_CHAR_OPS:
            toks.append(('op', c, i))
            i += 1
            continue
        raise ExprError("Unexpected character '%s' at position %d" % (c, i + 1))
    toks.append(('end', None, n))
    return toks


class _Parser:
    # turns the expression into a python expression string
    # precedence low to high: ?:  ||  &&  comparisons  + -  * /  unary -  ^

    def __init__(self, src):
        self.toks = _tokenize(src)
        self.pos = 0

    def peek(self):
        return self.toks[self.pos]

    def take(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def is_op(self, *ops):
        k, v, _ = self.peek()
        return k == 'op' and v in ops

    def expect(self, op):
        k, v, p = self.take()
        if k != 'op' or v != op:
            got = 'end of expression' if k == 'end' else "'%s'" % v
            raise ExprError("Expected '%s' but found %s at position %d" % (op, got, p + 1))

    def parse(self):
        if self.peek()[0] == 'end':
            raise ExprError('Expression is empty')
        out = self.ternary()
        k, v, p = self.peek()
        if k != 'end':
            hint = ' (use * for multiplication, e.g. 2*t)' if k in ('id', 'num') else ''
            raise ExprError("Unexpected '%s' at position %d%s" % (v, p + 1, hint))
        return out

    def ternary(self):
        cond = self.logic_or()
        if self.is_op('?'):
            self.take()
            a = self.ternary()
            self.expect(':')
            b = self.ternary()
            return '((%s) if (%s) else (%s))' % (a, cond, b)
        return cond

    def logic_or(self):
        left = self.logic_and()
        while self.is_op('||'):
            self.take()
            right = self.logic_and()
            left = '_b(bool(%s) or bool(%s))' % (left, right)
        return left

    def logic_and(self):
        left = self.compare()
        while self.is_op('&&'):
            self.take()
            right = self.compare()
            left = '_b(bool(%s) and bool(%s))' % (left, right)
        return left

    def compare(self):
        left = self.additive()
        while self.is_op('==', '!=', '<', '>', '<=', '>='):
            op = self.take()[1]
            right = self.additive()
            left = '_b((%s) %s (%s))' % (left, op, right)
        return left

    def additive(self):
        left = self.multiplicative()
        while self.is_op('+', '-'):
            op = self.take()[1]
            right = self.multiplicative()
            left = '(%s %s %s)' % (left, op, right)
        return left

    def multiplicative(self):
        left = self.unary()
        while self.is_op('*', '/'):
            op = self.take()[1]
            right = self.unary()
            left = '(%s %s %s)' % (left, op, right) if op == '*' else '_div(%s, %s)' % (left, right)
        return left

    def unary(self):
        if self.is_op('-'):
            self.take()
            return '(-%s)' % self.unary()
        if self.is_op('+'):
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        base = self.primary()
        if self.is_op('^'):
            self.take()
            exp = self.unary()  # right assoc, so 2^3^2 = 512 and 2^-1 works
            return '_pow(%s, %s)' % (base, exp)
        return base

    def primary(self):
        k, v, p = self.take()
        if k == 'num':
            return repr(v)
        if k == 'op' and v == '(':
            inner = self.ternary()
            self.expect(')')
            return '(%s)' % inner
        if k == 'id':
            if self.is_op('('):
                if v not in FUNCTIONS:
                    hint = ''
                    if v.lower() in FUNCTIONS:
                        hint = " (names are case-sensitive - did you mean '%s'?)" % v.lower()
                    raise ExprError("Unknown function '%s' at position %d%s" % (v, p + 1, hint))
                self.take()
                args = []
                if not self.is_op(')'):
                    args.append(self.ternary())
                    while self.is_op(','):
                        self.take()
                        args.append(self.ternary())
                self.expect(')')
                _, lo, hi = FUNCTIONS[v]
                if len(args) < lo or (hi is not None and len(args) > hi):
                    raise ExprError("Wrong number of arguments for '%s'" % v)
                return "_f[%r](%s)" % (v, ', '.join(args))
            if v in VARIABLES:
                return v
            if v in CONSTANTS:
                return repr(CONSTANTS[v])
            if v in FUNCTIONS:
                raise ExprError("Function '%s' needs parentheses, e.g. %s(t)" % (v, v))
            hint = ''
            low = v.lower()
            if low in VARIABLES or low in CONSTANTS or low in FUNCTIONS:
                hint = " (names are case-sensitive - did you mean '%s'?)" % low
            raise ExprError("Unknown name '%s' at position %d%s" % (v, p + 1, hint))
        if k == 'end':
            raise ExprError('Unexpected end of expression')
        raise ExprError("Unexpected '%s' at position %d" % (v, p + 1))


def _div(a, b):
    if b == 0:
        if a == 0:
            return float('nan')
        return math.copysign(float('inf'), a) * (1 if math.copysign(1, b) > 0 else -1)
    return a / b


def _pow(a, b):
    try:
        r = a ** b
    except (OverflowError, ZeroDivisionError):
        return float('nan')
    if isinstance(r, complex):
        return float('nan')
    return float(r)


_ENV = {
    '__builtins__': {'bool': bool},
    '_f': {k: v[0] for k, v in FUNCTIONS.items()},
    '_b': lambda x: 1.0 if x else 0.0,
    '_div': _div,
    '_pow': _pow,
}


def compile_expression(src):
    # returns f(t). domain errors (sqrt(-1) etc) give nan instead of raising
    py = _Parser(src.strip()).parse()
    fn = eval('lambda t: ' + py, dict(_ENV))  # only our own generated code goes in here

    def f(t):
        try:
            return float(fn(t))
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return float('nan')
    f.source = src
    return f


# coordinate systems

CARTESIAN = 'Cartesian'
CYLINDRICAL = 'Cylindrical'
SPHERICAL = 'Spherical'
COORD_SYSTEMS = (CARTESIAN, CYLINDRICAL, SPHERICAL)

# (label, tooltip) for the 3 equation inputs
FIELD_LABELS = {
    CARTESIAN: (('x(t) =', 'X coordinate'),
                ('y(t) =', 'Y coordinate'),
                ('z(t) =', 'Z coordinate (normal to the sketch plane)')),
    CYLINDRICAL: (('r(t) =', 'Radius, measured from the sketch Z axis'),
                  ('θ(t) =', 'Angle theta in the sketch XY plane, from +X, in radians'),
                  ('z(t) =', 'Height along the sketch Z axis')),
    SPHERICAL: (('r(t) =', 'Distance from the sketch origin'),
                ('θ(t) =', 'Polar angle theta from the +Z axis, in radians'),
                ('φ(t) =', 'Azimuth angle phi in the XY plane from +X, in radians')),
}

DEFAULT_EQUATIONS = {
    CARTESIAN: ('t * cos(2 * pi * t)', 't * sin(2 * pi * t)', '0'),
    CYLINDRICAL: ('t', '2 * pi * t', '0'),
    SPHERICAL: ('3', 'pi * t / 3', '4 * pi * t'),
}


def make_point_function(coord_system, f1, f2, f3):
    if coord_system == CARTESIAN:
        return lambda t: (f1(t), f2(t), f3(t))
    if coord_system == CYLINDRICAL:
        def g(t):
            r, th, z = f1(t), f2(t), f3(t)
            return (r * math.cos(th), r * math.sin(th), z)
        return g
    if coord_system == SPHERICAL:
        def g(t):
            r, th, ph = f1(t), f2(t), f3(t)
            s = math.sin(th)
            return (r * s * math.cos(ph), r * s * math.sin(ph), r * math.cos(th))
        return g
    raise ValueError('Unknown coordinate system: %s' % coord_system)


# sampling

DENSE_SAMPLES = 8192
MAX_FIT_POINTS = 1000
REL_TOLERANCE = 2e-4  # times bbox diagonal, used when no accuracy is given
START_FACTOR = 8.0    # first pass uses a polyline tolerance this many times coarser


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ap = (p[0] - a[0], p[1] - a[1], p[2] - a[2])
    L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    if L2 == 0.0:
        return math.sqrt(ap[0] ** 2 + ap[1] ** 2 + ap[2] ** 2)
    u = (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    d = (ap[0] - u * ab[0], ap[1] - u * ab[1], ap[2] - u * ab[2])
    return math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)


def _simplify(points, tol):
    # douglas-peucker, returns indices to keep
    n = len(points)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = points[i], points[j]
        best, best_k = -1.0, -1
        for k in range(i + 1, j):
            d = _seg_dist(points[k], a, b)
            if d > best:
                best, best_k = d, k
        if best > tol:
            keep[best_k] = True
            stack.append((i, best_k))
            stack.append((best_k, j))
    return [k for k in range(n) if keep[k]]


class CurveResult:
    def __init__(self, points, closed, t_values):
        self.points = points          # fit points
        self.closed = closed
        self.t_values = t_values      # t of each fit point
        self.max_error = None         # measured against the real spline, if refine() ran
        self.reached_limit = False
        # filled in by sample_curve
        self.func = None
        self.t_start = self.t_end = None
        self.dense_points = None
        self.dense_ts = None
        self.diag = None


def sample_curve(coord_system, exprs, t_start, t_end, dense=None,
                 max_points=MAX_FIT_POINTS, rel_tol=REL_TOLERANCE, abs_tol=None, start_tol=None):
    # sample densely, then thin out to what the spline actually needs
    if not (math.isfinite(t_start) and math.isfinite(t_end)):
        raise ExprError('Starting and ending t values must be finite numbers')
    if t_end <= t_start:
        raise ExprError('Ending t value must be greater than the starting t value')
    max_points = max(4, int(max_points))
    if dense is None:
        dense = max(DENSE_SAMPLES, min(6 * max_points, 40000))

    fs = []
    for label, src in zip(FIELD_LABELS[coord_system], exprs):
        try:
            fs.append(compile_expression(src))
        except ExprError as e:
            raise ExprError('%s %s' % (label[0].replace(' =', ':'), e))
    g = make_point_function(coord_system, *fs)

    ts = [t_start + (t_end - t_start) * i / dense for i in range(dense + 1)]
    pts = []
    for t in ts:
        p = g(t)
        if not all(math.isfinite(c) for c in p):
            raise ExprError('The equations give an invalid value (NaN or infinity) at t = %.6g' % t)
        pts.append(p)

    xs, ys, zs = zip(*pts)
    diag = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
    if diag < 1e-12:
        raise ExprError('The curve collapses to a single point')

    # starting point set. a cubic through these is usually much closer than the
    # polyline, so start a few times coarser than the target and let refine() add more
    tol = diag * rel_tol if abs_tol is None else max(abs_tol * START_FACTOR, diag * 1e-7)
    if start_tol is not None:
        tol = max(start_tol, diag * 1e-7)
    idx = _simplify(pts, tol)
    while len(idx) > max_points:
        tol *= 1.5
        idx = _simplify(pts, tol)

    out_pts = [pts[i] for i in idx]
    out_ts = [ts[i] for i in idx]

    # fitted splines don't like duplicate points
    eps = diag * 1e-9
    clean_p, clean_t = [out_pts[0]], [out_ts[0]]
    for p, t in zip(out_pts[1:], out_ts[1:]):
        if _dist(p, clean_p[-1]) > eps:
            clean_p.append(p)
            clean_t.append(t)

    closed = len(clean_p) >= 4 and _dist(clean_p[0], clean_p[-1]) <= diag * 1e-7
    if closed:
        clean_p.pop()
        clean_t.pop()
    if len(clean_p) < 2:
        raise ExprError('The curve collapses to a single point')
    res = CurveResult(clean_p, closed, clean_t)
    res.func = g
    res.t_start, res.t_end = t_start, t_end
    res.dense_points, res.dense_ts = pts, ts
    res.diag = diag
    return res


class _SegGrid:
    # spatial hash of polyline segments for nearest-segment queries.
    # several levels with growing cell size so far away points stay cheap.
    def __init__(self, poly):
        self.poly = poly
        lens = sorted(_dist(poly[i], poly[i + 1]) for i in range(len(poly) - 1))
        h = lens[len(lens) // 2] * 2.0 if lens else 1.0
        if h <= 0.0:
            h = max(lens[-1] if lens else 0.0, 1e-9)
        lo = [min(p[k] for p in poly) for k in range(3)]
        hi = [max(p[k] for p in poly) for k in range(3)]
        span = max(hi[k] - lo[k] for k in range(3))
        self.levels = []
        while True:
            self.levels.append(self._build(h))
            if h > span:
                break
            h *= 8.0

    def _build(self, h):
        poly = self.poly
        cells = {}
        for i in range(len(poly) - 1):
            p, q = poly[i], poly[i + 1]
            lo = [int(math.floor(min(p[k], q[k]) / h)) for k in range(3)]
            hi = [int(math.floor(max(p[k], q[k]) / h)) for k in range(3)]
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    for z in range(lo[2], hi[2] + 1):
                        cells.setdefault((x, y, z), []).append(i)
        keys = list(cells)
        bounds = [(min(k[d] for k in keys), max(k[d] for k in keys)) for d in range(3)]
        return h, cells, bounds

    def nearest(self, p):
        poly = self.poly
        best, best_i = float('inf'), -1
        for h, cells, bounds in self.levels:
            c = [int(math.floor(p[k] / h)) for k in range(3)]
            for r in range(0, 4):
                rng = [range(max(c[d] - r, bounds[d][0]), min(c[d] + r, bounds[d][1]) + 1) for d in range(3)]
                for x in rng[0]:
                    for y in rng[1]:
                        for z in rng[2]:
                            if max(abs(x - c[0]), abs(y - c[1]), abs(z - c[2])) != r:
                                continue
                            for i in cells.get((x, y, z), ()):
                                d = _seg_dist(p, poly[i], poly[i + 1])
                                if d < best:
                                    best, best_i = d, i
                # everything closer than r*h has been looked at
                if best <= r * h:
                    return best, best_i
        if best_i < 0:
            for i in range(len(poly) - 1):
                d = _seg_dist(p, poly[i], poly[i + 1])
                if d < best:
                    best, best_i = d, i
        return best, best_i


def _match(a, b):
    # for every point of a: (distance to polyline b, index of closest b segment)
    grid = _SegGrid(b)
    dists, where = [], []
    for p in a:
        d, i = grid.nearest(p)
        dists.append(d)
        where.append(i)
    return dists, where


def deviation(curve_pts, spline_pts):
    """Two-way max distance between the true curve and the spline, plus
    a per-true-sample error list used to decide where to add points."""
    d1, _ = _match(curve_pts, spline_pts)
    d2, w2 = _match(spline_pts, curve_pts)
    per_sample = list(d1)
    for d, i in zip(d2, w2):          # spline wandering away between samples
        if d > per_sample[i]:
            per_sample[i] = d
    return max(max(d1), max(d2)), per_sample


def refine(res, tol, max_points, spline_eval, max_iter=10):
    """Add fit points until the real spline is within tol of the curve.

    spline_eval(points, closed) must build the spline from the fit points and
    return it as a dense list of points (same units, start to end, back to the
    start point when closed). It's called once per iteration.
    """
    import bisect
    pts, ts = list(res.points), list(res.t_values)
    g = res.func
    truth = res.dense_points
    truth_t = res.dense_ts
    worst = None
    goal = tol * 0.9   # small margin, the check itself is sampled
    for it in range(max_iter + 1):
        sp = spline_eval(pts, res.closed)
        worst, per = deviation(truth, sp)
        if worst <= goal or len(pts) >= max_points or it == max_iter:
            break
        # worst error per span between fit points
        span_err = {}
        for k, e in enumerate(per):
            if e > goal:
                s = bisect.bisect_right(ts, truth_t[k]) - 1
                s = min(max(s, 0), len(ts) - 1)
                if e > span_err.get(s, 0.0):
                    span_err[s] = e
        if not span_err:
            break
        room = max_points - len(pts)
        bad = sorted(span_err, key=lambda s: -span_err[s])[:room]
        for s in sorted(bad, reverse=True):
            ta = ts[s]
            tb = ts[s + 1] if s + 1 < len(ts) else res.t_end
            tm = 0.5 * (ta + tb)
            if tb - ta <= 1e-12 * max(1.0, abs(res.t_end - res.t_start)):
                continue
            pts.insert(s + 1, g(tm))
            ts.insert(s + 1, tm)
    res.points, res.t_values = pts, ts
    res.max_error = worst
    res.reached_limit = worst > tol
    return res


# exact mode: piecewise cubic hermite using the real tangents, split until
# every span is within tolerance. parameterised by t itself, so the error can
# be checked point for point against the equations.

def _deriv(g, t, t0, t1):
    h = (t1 - t0) * 1e-7
    for kind in ('c', 'f', 'b'):
        if kind == 'c' and t - h >= t0 and t + h <= t1:
            a, b = g(t - h), g(t + h)
            d = [(b[i] - a[i]) / (2 * h) for i in range(3)]
        elif kind == 'f' and t + 2 * h <= t1 + 1e-15:
            a, b, c = g(t), g(t + h), g(t + 2 * h)
            d = [(-3 * a[i] + 4 * b[i] - c[i]) / (2 * h) for i in range(3)]
        elif kind == 'b' and t - 2 * h >= t0 - 1e-15:
            a, b, c = g(t), g(t - h), g(t - 2 * h)
            d = [(3 * a[i] - 4 * b[i] + c[i]) / (2 * h) for i in range(3)]
        else:
            continue
        if all(math.isfinite(x) for x in d):
            return tuple(d)
    return None


def _bez(p0, p1, p2, p3, s):
    u = 1.0 - s
    a, b, c, d = u * u * u, 3 * u * u * s, 3 * u * s * s, s * s * s
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
            a * p0[2] + b * p1[2] + c * p2[2] + d * p3[2])


class HermiteCurve:
    def __init__(self):
        self.t = []           # node parameters
        self.ctrl = []        # 3n+1 bezier control points
        self.max_error = 0.0
        self.reached_limit = False

    @property
    def spans(self):
        return len(self.t) - 1

    def knots(self):
        k = [self.t[0]] * 4
        for t in self.t[1:-1]:
            k += [t] * 3
        k += [self.t[-1]] * 4
        return k

    def point(self, t):
        import bisect
        i = min(max(bisect.bisect_right(self.t, t) - 1, 0), self.spans - 1)
        a, b = self.t[i], self.t[i + 1]
        c = self.ctrl[3 * i:3 * i + 4]
        return _bez(c[0], c[1], c[2], c[3], (t - a) / (b - a))


def hermite_fit(res, tol, max_spans=2000, checks=12):
    g, t0, t1 = res.func, res.t_start, res.t_end
    goal = tol * 0.9
    nodes = sorted(set(list(res.t_values) + [t0, t1]))
    P, D = {}, {}

    def node(t):
        if t not in P:
            P[t] = g(t)
            d = _deriv(g, t, t0, t1)
            D[t] = d
        return P[t], D[t]

    def span(a, b):
        pa, da = node(a)
        pb, db = node(b)
        h = b - a
        if da is None or db is None:
            sec = [(pb[i] - pa[i]) / h for i in range(3)]
            da = da or tuple(sec)
            db = db or tuple(sec)
        c1 = (pa[0] + h / 3 * da[0], pa[1] + h / 3 * da[1], pa[2] + h / 3 * da[2])
        c2 = (pb[0] - h / 3 * db[0], pb[1] - h / 3 * db[1], pb[2] - h / 3 * db[2])
        err = 0.0
        for j in range(1, checks + 1):
            s = j / (checks + 1.0)
            q = _bez(pa, c1, c2, pb, s)
            r = g(a + s * h)
            e = _dist(q, r)
            if not math.isfinite(e):
                e = float('inf')
            if e > err:
                err = e
        return (pa, c1, c2, pb), err

    spans = {}
    for a, b in zip(nodes, nodes[1:]):
        spans[(a, b)] = span(a, b)
    limit = False
    while True:
        bad = [k for k, v in spans.items() if v[1] > goal and (k[1] - k[0]) > 1e-12 * (t1 - t0)]
        if not bad:
            break
        room = max_spans - len(spans)
        if room <= 0:
            limit = True
            break
        bad.sort(key=lambda k: -spans[k][1])
        for a, b in bad[:room]:
            m = 0.5 * (a + b)
            del spans[(a, b)]
            spans[(a, m)] = span(a, m)
            spans[(m, b)] = span(m, b)
    keys = sorted(spans)
    hc = HermiteCurve()
    hc.t = [keys[0][0]] + [k[1] for k in keys]
    for i, k in enumerate(keys):
        c = spans[k][0]
        hc.ctrl += list(c) if i == 0 else list(c[1:])
    if res.closed:
        hc.ctrl[-1] = hc.ctrl[0]      # make the ends meet exactly
    hc.max_error = max(v[1] for v in spans.values())
    hc.reached_limit = limit
    return hc


def check_parametric(func, curve_point, t0, t1, n=20000):
    # max |curve(t) - func(t)| over n+1 evenly spaced t values
    worst = 0.0
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        e = _dist(curve_point(t), func(t))
        if e > worst:
            worst = e
    return worst
