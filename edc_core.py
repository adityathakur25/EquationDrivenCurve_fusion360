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
REL_TOLERANCE = 1e-3  # times bbox diagonal


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
        self.points = points
        self.closed = closed
        self.t_values = t_values


def sample_curve(coord_system, exprs, t_start, t_end,
                 dense=DENSE_SAMPLES, max_points=MAX_FIT_POINTS, rel_tol=REL_TOLERANCE):
    # sample densely, then thin out to what the spline actually needs
    if not (math.isfinite(t_start) and math.isfinite(t_end)):
        raise ExprError('Starting and ending t values must be finite numbers')
    if t_end <= t_start:
        raise ExprError('Ending t value must be greater than the starting t value')

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

    tol = diag * rel_tol
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
    return CurveResult(clean_p, closed, clean_t)
