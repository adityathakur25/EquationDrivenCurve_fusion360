# EquationDrivenCurve

Fusion add-in for drawing curves from parametric equations, x(t), y(t), z(t).
Works in cartesian, cylindrical (r, theta, z) and spherical (r, theta, phi) coords.
The curve goes into the active sketch, either as an exact spline built to a set accuracy or as a normal fit point spline.

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

Options below the t range:

- **Spline Type**
  - *Exact (fixed spline)*: cubic segments built straight from the equations, split until every part is within Accuracy. Fast and the error is guaranteed. Can't be edited by dragging fit points.
  - *Fit points (editable)*: a normal fit point spline. The error is measured and shown but not guaranteed, and Fusion gets slow above a couple of hundred points, so it's capped at 300.
- **Accuracy**: max allowed distance from the true curve (e.g. `0.005 mm`)
- **Max segments**: upper limit on segments / fit points

Notifications shows the segment count and the max error, measured on the spline Fusion actually created. It turns red if the accuracy wasn't reached.

Some curves to try:

```
helix (cylindrical)      r = 10, theta = 2*pi*t, z = 5*t,  t = 0..6
cycloid (cartesian)      x = 5*(t - sin(t)), y = 5*(1 - cos(t)), z = 0,  t = 0..6*PI
trefoil knot (cartesian) x = sin(t) + 2*sin(2*t), y = cos(t) - 2*cos(2*t), z = -sin(3*t),  t = 0..2*PI
```

## Example: cycloidal drive disc

What I originally wrote this for. 16 pins on a 90 mm pin circle (R = 45), pin dia 13 (Rr = 6.5),
eccentricity E = 1.5, so the disc gets 15 lobes.

Cartesian, t from `0` to `2*PI`:

```
x(t) = (45*cos(t))-(6.5*cos(t+arctan(sin((1-16)*t)/((45/(1.5*16))-cos((1-16)*t)))))-(1.5*cos(16*t)) + 1.5
y(t) = -(45*sin(t))+(6.5*sin(t+arctan(sin((1-16)*t)/((45/(1.5*16))-cos((1-16)*t)))))+(1.5*sin(16*t))
z(t) = 0
```

General form, N = number of pins:

```
x(t) = R*cos(t) - Rr*cos(t + arctan(sin((1-N)*t) / (R/(E*N) - cos((1-N)*t)))) - E*cos(N*t) + E
y(t) = -R*sin(t) + Rr*sin(t + arctan(sin((1-N)*t) / (R/(E*N) - cos((1-N)*t)))) + E*sin(N*t)
```

Notes:
- the `+ E` at the end of x(t) puts the disc centre on the eccentric, with the pin circle centred on the origin. Without it the disc digs into some pins and misses others
- R/(E*N) has to be more than 1, otherwise the profile loops over itself
- with Exact and Accuracy 0.005 mm this comes out as 214 segments, about 0.0035 mm max error, and all 16 pins touch the disc
- for some running clearance, bump Rr up a bit (e.g. 6.6 instead of 6.5)
- second disc (180 deg out of phase): wrap both equations in `-( ... )`, i.e. x2(t) = -(x(t)), y2(t) = -(y(t)). Just changing `+ E` to `- E` does not mesh

More in `resources/help.html` (also opens from the (i) button in the dialog).

`edc_core.py` has no Fusion dependency so the parser can be tested with plain python.
