# Equation driven curve add-in for Fusion.
# Sketch > Create > Equation Driven Curve, needs an active sketch.
# Lengths are in document units, angles in radians.

import json
import os
import sys
import traceback
import html

import adsk.core
import adsk.fusion

_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    from . import edc_core as core
except ImportError:
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    import edc_core as core

# fusion keeps submodules cached between stop/run, so force a fresh copy
import importlib
importlib.reload(core)

CMD_ID = 'asahu_EquationDrivenCurve'
CMD_NAME = 'Equation Driven Curve'
CMD_TOOLTIP = 'Create a 3D curve in the active sketch from parametric equations x(t), y(t), z(t).'
CMD_TOOLTIP_DESC = ('Choose Cartesian, Cylindrical or Spherical coordinates, type the equations in '
                    'terms of t (pi is predefined, names are case-sensitive) and the t range. '
                    'Lengths use the document units, angles are in radians.')
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SketchCreatePanel'
# put the button after the spline dropdown if it exists
POSITION_AFTER = ('SplineDropDown', 'ConicCurveCmd')

RESOURCES = os.path.join(_HERE, 'resources')
ICON_FOLDER = os.path.join(RESOURCES, 'icon')
HELP_FILE = os.path.join(RESOURCES, 'help.html')
SETTINGS_FILE = os.path.join(_HERE, 'settings.json')

_app = None
_ui = None
_handlers = []  # handlers get garbage collected otherwise

# settings

_DEFAULT_SETTINGS = {
    'coordSystem': core.CARTESIAN,
    'equations': {cs: list(core.DEFAULT_EQUATIONS[cs]) for cs in core.COORD_SYSTEMS},
    'tStart': '0',
    'tEnd': '3',
}


def _load_settings():
    s = json.loads(json.dumps(_DEFAULT_SETTINGS))
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if data.get('coordSystem') in core.COORD_SYSTEMS:
            s['coordSystem'] = data['coordSystem']
        for cs in core.COORD_SYSTEMS:
            eq = data.get('equations', {}).get(cs)
            if isinstance(eq, list) and len(eq) == 3 and all(isinstance(e, str) for e in eq):
                s['equations'][cs] = eq
        for k in ('tStart', 'tEnd'):
            if isinstance(data.get(k), str) and data[k].strip():
                s[k] = data[k]
    except Exception:
        pass
    return s


def _save_settings(s):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as fh:
            json.dump(s, fh, indent=2)
    except Exception:
        pass


# helpers

def _eq_id(cs, i):
    return 'eq_%s_%d' % (cs.lower(), i)


def _active_sketch():
    return adsk.fusion.Sketch.cast(_app.activeEditObject)


def _length_factor():
    # fusion works in cm internally
    design = adsk.fusion.Design.cast(_app.activeProduct)
    if not design:
        return 1.0
    um = design.fusionUnitsManager
    try:
        return um.convert(1.0, um.defaultLengthUnits, 'cm')
    except Exception:
        return 1.0


class _State:
    # cache so validate/preview/execute don't all re-evaluate the same curve

    def __init__(self):
        self.cache_key = None
        self.cache_result = None
        self.cache_error = None


_state = _State()


def _read_inputs(inputs):
    dd = adsk.core.DropDownCommandInput.cast(inputs.itemById('coordSystem'))
    cs = dd.selectedItem.name if dd.selectedItem else core.CARTESIAN
    exprs = [adsk.core.StringValueCommandInput.cast(inputs.itemById(_eq_id(cs, i))).value
             for i in range(3)]
    t0_in = adsk.core.ValueCommandInput.cast(inputs.itemById('tStart'))
    t1_in = adsk.core.ValueCommandInput.cast(inputs.itemById('tEnd'))
    return cs, exprs, t0_in, t1_in


def _evaluate(inputs):
    cs, exprs, t0_in, t1_in = _read_inputs(inputs)
    if not t0_in.isValidExpression:
        return None, 'Starting t value is not a valid expression'
    if not t1_in.isValidExpression:
        return None, 'Ending t value is not a valid expression'
    key = (cs, tuple(exprs), t0_in.value, t1_in.value)
    if key == _state.cache_key:
        return _state.cache_result, _state.cache_error
    try:
        res, err = core.sample_curve(cs, exprs, t0_in.value, t1_in.value), None
    except core.ExprError as e:
        res, err = None, str(e)
    except Exception as e:
        res, err = None, 'Error: %s' % e
    _state.cache_key, _state.cache_result, _state.cache_error = key, res, err
    return res, err


def _update_notification(inputs):
    box = adsk.core.TextBoxCommandInput.cast(inputs.itemById('notifications'))
    if not box:
        return
    res, err = _evaluate(inputs)
    if err:
        box.numRows = 3
        box.formattedText = '<span style="color:#d00000">%s</span>' % html.escape(err)
    else:
        n = len(res.points)
        msg = '%d spline control%s' % (n, '' if n == 1 else 's')
        if res.closed:
            msg += ' (closed)'
        box.numRows = 1
        box.formattedText = msg


def _update_visibility(inputs):
    dd = adsk.core.DropDownCommandInput.cast(inputs.itemById('coordSystem'))
    sel = dd.selectedItem.name if dd.selectedItem else core.CARTESIAN
    for cs in core.COORD_SYSTEMS:
        for i in range(3):
            inputs.itemById(_eq_id(cs, i)).isVisible = (cs == sel)


def _create_curve(sketch, res):
    f = _length_factor()
    pts = adsk.core.ObjectCollection.create()
    for x, y, z in res.points:
        pts.add(adsk.core.Point3D.create(x * f, y * f, z * f))
    sketch.isComputeDeferred = True
    try:
        spline = sketch.sketchCurves.sketchFittedSplines.add(pts)
        if res.closed:
            try:
                spline.isClosed = True
            except Exception:
                pass
    finally:
        sketch.isComputeDeferred = False
    return spline


def _collect_settings(inputs):
    dd = adsk.core.DropDownCommandInput.cast(inputs.itemById('coordSystem'))
    s = {
        'coordSystem': dd.selectedItem.name if dd.selectedItem else core.CARTESIAN,
        'equations': {},
        'tStart': adsk.core.ValueCommandInput.cast(inputs.itemById('tStart')).expression,
        'tEnd': adsk.core.ValueCommandInput.cast(inputs.itemById('tEnd')).expression,
    }
    for cs in core.COORD_SYSTEMS:
        s['equations'][cs] = [adsk.core.StringValueCommandInput.cast(
            inputs.itemById(_eq_id(cs, i))).value for i in range(3)]
    return s


def _report(where):
    if _ui:
        _ui.messageBox('%s failed:\n%s' % (where, traceback.format_exc()), CMD_NAME)


# event handlers

class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = adsk.core.CommandCreatedEventArgs.cast(args).command
            inputs = cmd.commandInputs
            _state.__init__()

            if not _active_sketch():
                _ui.messageBox('Please create or edit a sketch first, then run '
                               '"%s" from Sketch > Create.' % CMD_NAME, CMD_NAME)
                inputs.addTextBoxCommandInput('noSketch', '', 'No active sketch.', 1, True)
                cmd.isOKButtonVisible = False
                return

            try:
                if os.path.exists(HELP_FILE):
                    cmd.helpFile = HELP_FILE  # (i) button
            except Exception:
                pass

            try:
                cmd.setDialogInitialSize(340, 330)
                cmd.setDialogMinimumSize(300, 250)
            except Exception:
                pass

            s = _load_settings()

            dd = inputs.addDropDownCommandInput('coordSystem', 'Coordinate System',
                                                adsk.core.DropDownStyles.TextListDropDownStyle)
            for cs in core.COORD_SYSTEMS:
                dd.listItems.add(cs, cs == s['coordSystem'], '')
            dd.tooltip = 'Coordinate system the equations are written in'

            for cs in core.COORD_SYSTEMS:
                for i, (label, tip) in enumerate(core.FIELD_LABELS[cs]):
                    si = inputs.addStringValueInput(_eq_id(cs, i), label, s['equations'][cs][i])
                    si.tooltip = tip
                    si.tooltipDescription = ('Expression in t. Example: t * cos(2 * pi * t). '
                                             'Functions: sin cos tan asin acos atan atan2 sinh cosh '
                                             'tanh sqrt exp ln log log10 log2 abs sign min max ... '
                                             'Use ^ for power and cond ? a : b for if-else.')
                    si.isVisible = (cs == s['coordSystem'])

            t0 = inputs.addValueInput('tStart', 'Starting t value', '',
                                      adsk.core.ValueInput.createByString(s['tStart']))
            t0.tooltip = 'Value of t where the curve starts'
            t1 = inputs.addValueInput('tEnd', 'Ending t value', '',
                                      adsk.core.ValueInput.createByString(s['tEnd']))
            t1.tooltip = 'Value of t where the curve ends'
            if not t0.isValidExpression:
                t0.expression = '0'
            if not t1.isValidExpression:
                t1.expression = '3'

            inputs.addTextBoxCommandInput('notifications', 'Notifications', '', 1, True)
            _update_notification(inputs)

            for event, handler in ((cmd.inputChanged, InputChangedHandler()),
                                   (cmd.validateInputs, ValidateInputsHandler()),
                                   (cmd.executePreview, ExecutePreviewHandler()),
                                   (cmd.execute, ExecuteHandler()),
                                   (cmd.destroy, DestroyHandler())):
                event.add(handler)
                _handlers.append(handler)
        except Exception:
            _report('Command created')


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            args = adsk.core.InputChangedEventArgs.cast(args)
            inputs = args.inputs
            if inputs.itemById('coordSystem') is None:
                inputs = args.input.parentCommand.commandInputs
            if args.input.id == 'notifications':
                return
            if args.input.id == 'coordSystem':
                _update_visibility(inputs)
            _update_notification(inputs)
        except Exception:
            _report('Input changed')


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            args = adsk.core.ValidateInputsEventArgs.cast(args)
            if args.inputs.itemById('coordSystem') is None:
                return
            res, err = _evaluate(args.inputs)
            args.areInputsValid = res is not None and err is None
        except Exception:
            args.areInputsValid = False


class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            args = adsk.core.CommandEventArgs.cast(args)
            inputs = args.command.commandInputs
            sketch = _active_sketch()
            if not sketch or inputs.itemById('coordSystem') is None:
                return
            res, err = _evaluate(inputs)
            _update_notification(inputs)
            if res is None:
                return
            _create_curve(sketch, res)
            args.isValidResult = True  # reuse preview on OK
        except Exception:
            _report('Preview')


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            args = adsk.core.CommandEventArgs.cast(args)
            inputs = args.command.commandInputs
            sketch = _active_sketch()
            if not sketch or inputs.itemById('coordSystem') is None:
                return
            res, err = _evaluate(inputs)
            if res is None:
                args.executeFailed = True
                args.executeFailedMessage = err or 'Invalid input'
                return
            _create_curve(sketch, res)
        except Exception:
            _report('Execute')


class DestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            args = adsk.core.CommandEventArgs.cast(args)
            inputs = args.command.commandInputs
            if (inputs.itemById('coordSystem') is not None and
                    args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason):
                _save_settings(_collect_settings(inputs))
        except Exception:
            pass
        finally:
            _handlers[:] = [h for h in _handlers if isinstance(h, CommandCreatedHandler)]


# add-in entry points

def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        icon = ICON_FOLDER if os.path.isdir(ICON_FOLDER) else ''
        cmd_def = _ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_TOOLTIP, icon)
        try:
            cmd_def.tooltipDescription = CMD_TOOLTIP_DESC
        except Exception:
            pass

        handler = CommandCreatedHandler()
        cmd_def.commandCreated.add(handler)
        _handlers.append(handler)

        ws = _ui.workspaces.itemById(WORKSPACE_ID)
        panel = ws.toolbarPanels.itemById(PANEL_ID) if ws else None
        if panel:
            old = panel.controls.itemById(CMD_ID)
            if old:
                old.deleteMe()
            control = None
            for pos in POSITION_AFTER:
                if panel.controls.itemById(pos):
                    try:
                        control = panel.controls.addCommand(cmd_def, pos, False)
                        break
                    except Exception:
                        control = None
            if control is None:
                control = panel.controls.addCommand(cmd_def)
            control.isVisible = True
    except Exception:
        if _ui:
            _ui.messageBox('Failed to start %s:\n%s' % (CMD_NAME, traceback.format_exc()))


def stop(context):
    try:
        ui = _ui or adsk.core.Application.get().userInterface
        ws = ui.workspaces.itemById(WORKSPACE_ID)
        panel = ws.toolbarPanels.itemById(PANEL_ID) if ws else None
        if panel:
            ctrl = panel.controls.itemById(CMD_ID)
            if ctrl:
                ctrl.deleteMe()
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        _handlers.clear()
    except Exception:
        if _ui:
            _ui.messageBox('Failed to stop %s:\n%s' % (CMD_NAME, traceback.format_exc()))
