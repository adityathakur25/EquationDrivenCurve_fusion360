# EquationDrivenCurve

Fusion add-in for drawing curves from parametric equations, x(t), y(t), z(t).
Works in cartesian, cylindrical (r, theta, z) and spherical (r, theta, phi) coords.
The result is a regular fitted spline in the active sketch.

Inspired by the Code Reclaimers Equation Driven Curve add-in.

## Install

1. Shift+S in Fusion (Utilities > Add-Ins)
2. Add-Ins tab, click the green + next to My Add-Ins
3. Select this folder
4. Run (tick Run on Startup if you want it every time)

## Usage

Open/edit a sketch, then Sketch > Create > Equation Driven Curve.

- lengths are in the document units, angles in radians
- `t` is the parameter, `pi` and `e` are defined
- case sensitive: `sin(t)` works, `Sin(t)` doesn't
- `^` for powers, `cond ? a : b` for if/else
- functions: sin cos tan asin acos atan atan2 sinh cosh tanh sqrt exp ln log log10 log2 abs sign min max floor ceil mod ...

Some curves to try:

```
helix (cylindrical)      r = 10, theta = 2*pi*t, z = 5*t,  t = 0..6
cycloid (cartesian)      x = 5*(t - sin(t)), y = 5*(1 - cos(t)), z = 0,  t = 0..6*PI
trefoil knot (cartesian) x = sin(t) + 2*sin(2*t), y = cos(t) - 2*cos(2*t), z = -sin(3*t),  t = 0..2*PI
```

More in `resources/help.html` (also opens from the (i) button in the dialog).

`edc_core.py` has no Fusion dependency so the parser can be tested with plain python.
