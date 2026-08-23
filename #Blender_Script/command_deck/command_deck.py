bl_info = {
    "name": "Command Deck - Custom Button Panel",
    "author": "DiGiMonkey",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > N-Panel > CmdDeck",
    "description": "Customizable tabbed button panel for frequently used commands (operators, scripts, sliders, colors).",
    "category": "Interface",
}

import bpy
import json
import os
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    EnumProperty, FloatVectorProperty, CollectionProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper

# ---------------------------------------------------------------------------
# Icon list. Primary: pull Blender's FULL built-in icon set (includes system /
# editor / mode icons like the ones in headers, overlays, etc.) via RNA
# introspection. Fallback: curated list below, used only if the introspection
# call fails on some Blender version.
# ---------------------------------------------------------------------------
FALLBACK_ICON_NAMES = [
    "NONE", "MESH_CUBE", "MESH_UVSPHERE", "MESH_CYLINDER", "MESH_PLANE",
    "MOD_ARRAY", "MOD_MIRROR", "MOD_SUBSURF", "MOD_BEVEL", "MOD_BOOLEAN",
    "MODIFIER", "TOOL_SETTINGS", "TRANSFORM_ORIGINS", "ORIENTATION_GLOBAL",
    "SNAP_ON", "PIVOT_CURSOR", "SHADING_RENDERED", "SHADING_SOLID",
    "SHADING_WIRE", "MATERIAL", "TEXTURE", "NODE_MATERIAL", "WORLD",
    "LIGHT", "LIGHT_SUN", "LIGHT_POINT", "CAMERA_DATA", "ARMATURE_DATA",
    "OUTLINER_OB_ARMATURE", "POSE_HLT", "GROUP_BONE", "CONSTRAINT",
    "PARTICLES", "PHYSICS", "FORCE_FORCE", "RENDER_STILL", "RENDER_ANIMATION",
    "FILE_REFRESH", "FILE_TICK", "IMPORT", "EXPORT", "FILEBROWSER",
    "PLAY", "PAUSE", "REC", "LOOP_BACK", "LOOP_FORWARDS",
    "TRIA_UP", "TRIA_DOWN", "TRIA_LEFT", "TRIA_RIGHT",
    "ADD", "REMOVE", "X", "CHECKMARK", "PANEL_CLOSE",
    "COLOR", "BRUSH_DATA", "SCULPTMODE_HLT", "EDITMODE_HLT", "OBJECT_DATAMODE",
    "VPAINT_HLT", "TPAINT_HLT", "UV", "GREASEPENCIL", "TOOL_SETTINGS_UV",
    "SCRIPT", "CONSOLE", "TEXT", "FUND", "SETTINGS", "PREFERENCES",
    "AUTO", "HAND", "HIDE_OFF", "HIDE_ON", "LOCKED", "UNLOCKED",
]


def _get_icon_names():
    """Try to pull Blender's complete built-in icon set. Falls back to the
    curated list above if the RNA introspection path doesn't work on this
    Blender version."""
    try:
        items = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
        names = [item.identifier for item in items]
        if names:
            return names
    except Exception:
        pass
    return FALLBACK_ICON_NAMES


ICON_NAMES = _get_icon_names()
ICON_ITEMS = [
    (n, n, f"Icon: {n}", n, i) for i, n in enumerate(ICON_NAMES)
]

CMD_TYPE_ITEMS = [
    ("OPERATOR", "Operator", "Call a Blender operator, e.g. object.shade_smooth"),
    ("TEXT_SCRIPT", "Text Block Script", "Run a script kept in Blender's Text Editor (separate file)"),
    ("PYTHON_INLINE", "Inline Python", "Run a short python snippet stored in this button"),
    ("MACRO", "Macro (Sequence)", "Run a list of operators/python steps in order, one button = one whole shortcut combo (e.g. S, X, 0, Enter)"),
    ("PROP_SLIDER", "Slider", "Numeric slider + apply button, runs code with variable 'value'"),
    ("PROP_COLOR", "Color Picker", "Color picker + apply button, runs code with variable 'value'"),
    ("PROP_TOGGLE", "Toggle", "On/off toggle button, runs code with variable 'value'"),
    ("LABEL", "Label / Heading", "Not a command. Shows the name as plain (non-clickable) heading text, optionally with an icon."),
]
NON_COMMAND_TYPES = {"LABEL"}
NO_ICON_TYPES = set()
LABELABLE_TYPES = {"OPERATOR", "TEXT_SCRIPT", "PYTHON_INLINE", "PROP_TOGGLE", "MACRO"}

MACRO_STEP_TYPE_ITEMS = [
    ("OPERATOR", "Operator", "Call a Blender operator, e.g. transform.resize"),
    ("PYTHON_INLINE", "Inline Python", "Run a short python snippet"),
]


# ---------------------------------------------------------------------------
# Property groups
# ---------------------------------------------------------------------------
class CTM_MacroStep(bpy.types.PropertyGroup):
    """One step inside a MACRO button - either a single operator call or a
    line of inline python, run in order with the steps before/after it."""
    step_type: EnumProperty(name="Step Type", items=MACRO_STEP_TYPE_ITEMS, default="OPERATOR")
    operator_id: StringProperty(name="Operator ID", description="e.g. transform.resize", default="")
    operator_kwargs: StringProperty(name="Operator Args (python dict)", default="")
    operator_context: EnumProperty(
        name="Execution Context",
        items=[
            ("EXEC_DEFAULT", "Exec (runs once, default)", "For ordinary operators that complete immediately"),
            ("INVOKE_DEFAULT", "Invoke (interactive/modal)", "For tools that wait for mouse input"),
        ],
        default="EXEC_DEFAULT",
    )
    python_code: StringProperty(name="Python Code", default="")


class CTM_Button(bpy.types.PropertyGroup):
    name: StringProperty(name="Label", default="New Button")
    icon: EnumProperty(name="Icon", items=ICON_ITEMS, default="NONE")
    cmd_type: EnumProperty(name="Type", items=CMD_TYPE_ITEMS, default="OPERATOR")

    operator_id: StringProperty(name="Operator ID", description="e.g. object.shade_smooth", default="")
    operator_kwargs: StringProperty(name="Operator Args (python dict)", default="")
    operator_context: EnumProperty(
        name="Execution Context",
        description=(
            "Most operators (shade smooth, add modifier, etc.) just run once and finish - "
            "use Exec for those. Interactive tools that wait for you to click/drag in the "
            "viewport (Knife, Loop Cut, Bevel-drag, etc.) need Invoke instead, or they will "
            "either fail or silently do nothing."
        ),
        items=[
            ("EXEC_DEFAULT", "Exec (runs once, default)", "For ordinary operators that complete immediately"),
            ("INVOKE_DEFAULT", "Invoke (interactive/modal)", "For tools that wait for mouse input, e.g. Knife, Loop Cut"),
        ],
        default="EXEC_DEFAULT",
    )

    script_name: StringProperty(name="Text Block Name", description="Name of the script in Blender's Text Editor", default="")
    python_code: StringProperty(name="Python Code", default="")

    macro_steps: CollectionProperty(type=CTM_MacroStep)
    macro_active_index: IntProperty(default=0)

    slider_value: FloatProperty(name="Value", default=0.0)
    slider_min: FloatProperty(name="Min", default=0.0)
    slider_max: FloatProperty(name="Max", default=1.0)

    color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0.0, max=1.0, default=(1.0, 1.0, 1.0, 1.0))
    toggle_value: BoolProperty(name="State", default=False)

    scale_x: FloatProperty(name="Width Scale", default=1.0, min=0.1, max=10.0)
    scale_y: FloatProperty(name="Height Scale", default=1.0, min=0.1, max=10.0)
    show_color_tag: BoolProperty(name="Show Color Tag", default=False)
    icon_only: BoolProperty(
        name="Icon Only",
        description="Hide the text label on the button. The label still shows as a tooltip on mouse hover.",
        default=False,
    )
    grid_row: IntProperty(name="Row", description="Vertical position in the tab's grid (1 = top)", default=1, min=1)
    grid_col: IntProperty(name="Col", description="Horizontal position in the tab's grid (1 = left)", default=1, min=1)
    span_cols: IntProperty(
        name="Width (in Cols)",
        description="How many grid columns wide this button occupies, filling the space of the columns to its right",
        default=1, min=1,
    )
    highlight_preset: EnumProperty(
        name="Highlight If",
        description="Show the same 'pressed/active' look as Blender's own mode buttons when this condition is true",
        items=[
            ("NONE", "No Highlight", "Never highlighted (unless Toggle type manages its own state)"),
            ("OBJECT_MODE", "In Object Mode", ""),
            ("EDIT_MODE", "In Edit Mode", ""),
            ("SCULPT_MODE", "In Sculpt Mode", ""),
            ("VERTEX_PAINT_MODE", "In Vertex Paint Mode", ""),
            ("WEIGHT_PAINT_MODE", "In Weight Paint Mode", ""),
            ("TEXTURE_PAINT_MODE", "In Texture Paint Mode", ""),
            ("POSE_MODE", "In Pose Mode", ""),
            ("MESH_SELECT_VERT", "Mesh Select Mode: Vertex", ""),
            ("MESH_SELECT_EDGE", "Mesh Select Mode: Edge", ""),
            ("MESH_SELECT_FACE", "Mesh Select Mode: Face", ""),
            ("TOOL_MOVE", "Active Tool: Move", ""),
            ("TOOL_ROTATE", "Active Tool: Rotate", ""),
            ("TOOL_SCALE", "Active Tool: Scale", ""),
            ("ORIENT_GLOBAL", "Orientation: Global", ""),
            ("ORIENT_LOCAL", "Orientation: Local", ""),
            ("ORIENT_NORMAL", "Orientation: Normal", ""),
            ("CUSTOM", "Custom Expression...", "Write your own python condition below"),
        ],
        default="NONE",
    )
    highlight_expr: StringProperty(
        name="Custom Expression",
        description=(
            "Only used when Highlight If is set to 'Custom Expression'. "
            "Re-checked every time the panel redraws, so keep it cheap. "
            "Example: tuple(context.tool_settings.mesh_select_mode) == (True, False, False)"
        ),
        default="",
    )


class CTM_Tab(bpy.types.PropertyGroup):
    name: StringProperty(name="Tab Name", default="Tab")
    buttons: CollectionProperty(type=CTM_Button)
    active_index: IntProperty(default=0)
    columns: IntProperty(name="Columns", description="Horizontal divisions: how many buttons fit side by side", default=4, min=1, max=20)
    rows: IntProperty(name="Rows", description="Vertical divisions: how many rows of buttons fit top to bottom", default=4, min=1, max=40)


def _get_tabs(context):
    return context.scene.ctm_tabs


def _get_button(context, tab_index, button_index):
    tabs = _get_tabs(context)
    if not (0 <= tab_index < len(tabs)):
        return None
    tab = tabs[tab_index]
    if not (0 <= button_index < len(tab.buttons)):
        return None
    return tab.buttons[button_index]


def _idname_to_pyname(bl_idname):
    """Convert 'OBJECT_OT_shade_smooth' -> 'object.shade_smooth'."""
    if "_OT_" in bl_idname:
        mod, func = bl_idname.split("_OT_", 1)
        return f"{mod.lower()}.{func}"
    return bl_idname


def _capture_operator_info(op):
    """Given a bpy.types.OperatorProperties entry from window_manager.operators
    (i.e. an operator that just finished running), return
    (operator_id, kwargs_repr, warning_or_None) suitable for storing on a
    button or macro step. Shared by both the single-operator recorder and
    the macro-step recorder."""
    operator_id = _idname_to_pyname(op.bl_idname)

    kwargs = {}
    props = op.properties
    for p in props.bl_rna.properties:
        if p.identifier == 'rna_type':
            continue
        # POINTER/COLLECTION properties (e.g. a macro operator's nested
        # sub-operator settings, like extrude's built-in move step) are
        # bpy structs, not plain values. Their repr() is not valid
        # Python, so trying to re-run them later causes a SyntaxError.
        # Skip them; simple values (bool/int/float/string/enum/vector)
        # are unaffected and still get captured.
        if p.type in {'POINTER', 'COLLECTION'}:
            continue
        try:
            if not props.is_property_set(p.identifier):
                continue
            val = getattr(props, p.identifier)
            if hasattr(val, '__len__') and not isinstance(val, str):
                val = list(val)
            kwargs[p.identifier] = val
        except Exception:
            continue

    kwargs_repr = repr(kwargs) if kwargs else ""
    warning = None
    # Safety check: make sure what we're about to save can actually be
    # eval()'d back, so we never save something that will error later.
    try:
        if kwargs_repr:
            eval(kwargs_repr)
    except Exception:
        kwargs_repr = ""
        warning = "Some captured values could not be saved safely and were skipped."

    return operator_id, kwargs_repr, warning


def _get_active_tool_id(context):
    """Returns the idname of the currently active tool in the 3D Viewport
    (e.g. 'builtin.move'), or None if it can't be determined."""
    try:
        tool = context.workspace.tools.from_space_view3d_mode(context.mode, create=False)
        return tool.idname if tool else None
    except Exception:
        return None


def _find_view3d_window(context):
    """Find a VIEW_3D area's WINDOW region.

    Many viewport-space operators (transform.translate/rotate/resize,
    mesh.knife_tool, and similar interactive tools) check that they were
    invoked from the 3D Viewport's own WINDOW region. Our buttons live in
    the sidebar (a 'UI' region of the same VIEW_3D area), which is a
    different region - so calling these operators directly from a sidebar
    button click can silently fail (no error, the button just doesn't do
    anything, because Blender disables it once its poll() check fails).

    Returns (area, region) for a VIEW_3D's WINDOW region if one exists in
    the current screen, otherwise (None, None).
    """
    screen = getattr(context, "screen", None)
    if screen is None:
        return None, None
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    return area, region
    return None, None


def _run_operator_call(context, operator_id, operator_kwargs_str, operator_context, reporter=None):
    """Shared logic for calling a bpy.ops operator from a string id + string
    kwargs, with the same viewport-override / cursor-warp handling used for
    regular OPERATOR buttons. Used by both single OPERATOR buttons and each
    OPERATOR step inside a MACRO button. Returns the operator's result set
    (e.g. {'FINISHED'}) so the caller can decide whether to continue."""
    if "." not in operator_id:
        raise ValueError("Operator ID must be like 'object.shade_smooth'")
    mod, func = operator_id.split(".", 1)
    kwargs = eval(operator_kwargs_str) if operator_kwargs_str.strip() else {}
    op_func = getattr(getattr(bpy.ops, mod), func)

    print(f"[Command Deck] --- running {operator_id} ---")
    print(f"[Command Deck] operator_context = {operator_context}, kwargs = {kwargs}")
    try:
        print(f"[Command Deck] poll() = {op_func.poll()}")
    except Exception as poll_e:
        print(f"[Command Deck] poll() raised: {poll_e}")

    v3d_area, v3d_region = _find_view3d_window(context)
    print(f"[Command Deck] VIEW_3D window region found = {v3d_area is not None}")

    if v3d_area is not None and operator_context == 'INVOKE_DEFAULT':
        cx = v3d_region.x + v3d_region.width // 2
        cy = v3d_region.y + v3d_region.height // 2
        context.window.cursor_warp(cx, cy)
        print(f"[Command Deck] warped cursor to viewport center ({cx}, {cy})")

    if v3d_area is not None:
        with context.temp_override(area=v3d_area, region=v3d_region):
            result = op_func(operator_context, **kwargs)
    else:
        result = op_func(operator_context, **kwargs)
    print(f"[Command Deck] result = {result}")
    return result


def _find_or_grow_slot(tab, exclude_index):
    """Find the first free (row, col) in the tab's grid (1-based, top-left is
    (1, 1)). If none is free within the current number of rows, grow the tab
    by one row and place it there (column 1)."""
    occupied = set()
    for i, b in enumerate(tab.buttons):
        if i == exclude_index:
            continue
        occupied.add((b.grid_row, b.grid_col))
    cols = max(tab.columns, 1)
    rows = max(tab.rows, 1)
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            if (r, c) not in occupied:
                return r, c
    new_row = rows + 1
    tab.rows = new_row
    return new_row, 1


# ---------------------------------------------------------------------------
# UI List
# ---------------------------------------------------------------------------
class CTM_UL_buttons(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon=item.icon if item.icon != "NONE" else "DOT")
        row.label(text=item.cmd_type)


class CTM_UL_macro_steps(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=f"{index + 1}.")
        if item.step_type == 'OPERATOR':
            row.label(text=item.operator_id or "(operator id not set)", icon='TOOL_SETTINGS')
        else:
            row.label(text="Inline Python", icon='SCRIPT')


# ---------------------------------------------------------------------------
# Operators - tab management
# ---------------------------------------------------------------------------
class CTM_OT_tab_add(bpy.types.Operator):
    bl_idname = "ctm.tab_add"
    bl_label = "Add Tab"

    def execute(self, context):
        tabs = _get_tabs(context)
        t = tabs.add()
        t.name = f"Tab {len(tabs)}"
        context.scene.ctm_active_tab = len(tabs) - 1
        return {'FINISHED'}


class CTM_OT_tab_remove(bpy.types.Operator):
    bl_idname = "ctm.tab_remove"
    bl_label = "Remove Tab"
    tab_index: IntProperty()

    def execute(self, context):
        tabs = _get_tabs(context)
        if 0 <= self.tab_index < len(tabs):
            tabs.remove(self.tab_index)
            context.scene.ctm_active_tab = max(0, min(context.scene.ctm_active_tab, len(tabs) - 1))
        return {'FINISHED'}


class CTM_OT_tab_move(bpy.types.Operator):
    bl_idname = "ctm.tab_move"
    bl_label = "Move Tab"
    tab_index: IntProperty()
    direction: StringProperty(default="UP")  # UP or DOWN

    def execute(self, context):
        tabs = _get_tabs(context)
        idx = self.tab_index
        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if 0 <= new_idx < len(tabs):
            tabs.move(idx, new_idx)
            context.scene.ctm_active_tab = new_idx
        return {'FINISHED'}


class CTM_OT_tab_select(bpy.types.Operator):
    bl_idname = "ctm.tab_select"
    bl_label = "Select Tab"
    tab_index: IntProperty()

    def execute(self, context):
        context.scene.ctm_active_tab = self.tab_index
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operators - button management
# ---------------------------------------------------------------------------
class CTM_OT_button_add(bpy.types.Operator):
    bl_idname = "ctm.button_add"
    bl_label = "Add Button"
    bl_description = (
        "Add a new button. If a button is currently selected in the list, "
        "the new one takes that button's grid row - every button at or "
        "below that row (in any column) has its row number pushed down by "
        "one to make room, like inserting a new row into the grid."
    )

    def execute(self, context):
        tabs = _get_tabs(context)
        if len(tabs) == 0:
            self.report({'WARNING'}, "Add a tab first")
            return {'CANCELLED'}
        tab = tabs[context.scene.ctm_active_tab]

        insert_at = tab.active_index if 0 <= tab.active_index < len(tab.buttons) else None
        ref_row = tab.buttons[insert_at].grid_row if insert_at is not None else None

        tab.buttons.add()
        new_index = len(tab.buttons) - 1

        if insert_at is not None and insert_at != new_index:
            tab.buttons.move(new_index, insert_at)
            new_index = insert_at

        # Re-fetch the button by index AFTER any move() call. Holding onto
        # the reference returned by add() and writing to it after a move()
        # is unsafe - move() reorders the underlying collection, and the
        # old reference can end up pointing at a different button, which is
        # exactly what caused another button's position to be overwritten.
        b = tab.buttons[new_index]
        b.name = f"Button {new_index + 1}"

        if ref_row is not None:
            # Push every OTHER button sitting at or below the reference row
            # (in any column) down by one row, then drop the new button
            # into the now-empty row - like inserting a row in a grid.
            for i, other in enumerate(tab.buttons):
                if i == new_index:
                    continue
                if other.grid_row >= ref_row:
                    other.grid_row += 1
            b.grid_row = ref_row
            b.grid_col = 1
            max_row_used = max((btn.grid_row for btn in tab.buttons), default=1)
            if max_row_used > tab.rows:
                tab.rows = max_row_used
        else:
            r, c = _find_or_grow_slot(tab, new_index)
            b.grid_row = r
            b.grid_col = c
        tab.active_index = new_index
        return {'FINISHED'}


class CTM_OT_button_remove(bpy.types.Operator):
    bl_idname = "ctm.button_remove"
    bl_label = "Remove Button"

    def execute(self, context):
        tabs = _get_tabs(context)
        tab = tabs[context.scene.ctm_active_tab]
        idx = tab.active_index
        if 0 <= idx < len(tab.buttons):
            tab.buttons.remove(idx)
            tab.active_index = max(0, min(idx, len(tab.buttons) - 1))
        return {'FINISHED'}


class CTM_OT_button_move(bpy.types.Operator):
    bl_idname = "ctm.button_move"
    bl_label = "Move Button"
    bl_description = "UP/DOWN moves by one slot. TOP/BOTTOM jumps straight to the start/end of the list in one click"
    direction: StringProperty(default="UP")

    def execute(self, context):
        tabs = _get_tabs(context)
        tab = tabs[context.scene.ctm_active_tab]
        idx = tab.active_index
        if not (0 <= idx < len(tab.buttons)):
            return {'CANCELLED'}

        if self.direction == "UP":
            new_idx = idx - 1
        elif self.direction == "DOWN":
            new_idx = idx + 1
        elif self.direction == "TOP":
            new_idx = 0
        elif self.direction == "BOTTOM":
            new_idx = len(tab.buttons) - 1
        else:
            new_idx = idx

        if 0 <= new_idx < len(tab.buttons) and new_idx != idx:
            tab.buttons.move(idx, new_idx)
            tab.active_index = new_idx
        return {'FINISHED'}


class CTM_OT_button_shift_rows(bpy.types.Operator):
    bl_idname = "ctm.button_shift_rows"
    bl_label = "Shift Rows"
    bl_description = (
        "DOWN: add 1 to the grid Row (縦) of the selected button and every "
        "button at or below that row (any column) - makes room to insert "
        "new rows manually. UP: subtract 1 from the same set - closes a gap."
    )
    direction: StringProperty(default="DOWN")

    def execute(self, context):
        tabs = _get_tabs(context)
        tab = tabs[context.scene.ctm_active_tab]
        idx = tab.active_index
        if not (0 <= idx < len(tab.buttons)):
            self.report({'WARNING'}, "Select a button in the list first")
            return {'CANCELLED'}

        ref_row = tab.buttons[idx].grid_row

        if self.direction == "UP" and ref_row <= 1:
            self.report({'WARNING'}, "Already at Row 1 - nothing above to close the gap with")
            return {'CANCELLED'}

        delta = 1 if self.direction == "DOWN" else -1
        for btn in tab.buttons:
            if btn.grid_row >= ref_row:
                btn.grid_row = max(1, btn.grid_row + delta)

        if self.direction == "DOWN":
            max_row_used = max((b.grid_row for b in tab.buttons), default=1)
            if max_row_used > tab.rows:
                tab.rows = max_row_used

        return {'FINISHED'}


class CTM_OT_macro_step_add(bpy.types.Operator):
    bl_idname = "ctm.macro_step_add"
    bl_label = "Add Macro Step"
    tab_index: IntProperty()
    button_index: IntProperty()

    def execute(self, context):
        btn = _get_button(context, self.tab_index, self.button_index)
        if btn is None:
            return {'CANCELLED'}
        btn.macro_steps.add()
        btn.macro_active_index = len(btn.macro_steps) - 1
        return {'FINISHED'}


class CTM_OT_macro_step_remove(bpy.types.Operator):
    bl_idname = "ctm.macro_step_remove"
    bl_label = "Remove Macro Step"
    tab_index: IntProperty()
    button_index: IntProperty()

    def execute(self, context):
        btn = _get_button(context, self.tab_index, self.button_index)
        if btn is None:
            return {'CANCELLED'}
        idx = btn.macro_active_index
        if 0 <= idx < len(btn.macro_steps):
            btn.macro_steps.remove(idx)
            btn.macro_active_index = max(0, min(idx, len(btn.macro_steps) - 1))
        return {'FINISHED'}


class CTM_OT_macro_step_move(bpy.types.Operator):
    bl_idname = "ctm.macro_step_move"
    bl_label = "Move Macro Step"
    tab_index: IntProperty()
    button_index: IntProperty()
    direction: StringProperty(default="UP")

    def execute(self, context):
        btn = _get_button(context, self.tab_index, self.button_index)
        if btn is None:
            return {'CANCELLED'}
        idx = btn.macro_active_index
        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if 0 <= new_idx < len(btn.macro_steps):
            btn.macro_steps.move(idx, new_idx)
            btn.macro_active_index = new_idx
        return {'FINISHED'}


class CTM_OT_button_execute(bpy.types.Operator):
    bl_idname = "ctm.button_execute"
    bl_label = ""
    bl_options = {'INTERNAL'}
    tab_index: IntProperty()
    button_index: IntProperty()

    @classmethod
    def description(cls, context, properties):
        # Dynamic tooltip: shows the button's own label on hover, which is
        # what makes "Icon Only" buttons still identifiable without text.
        try:
            tabs = context.scene.ctm_tabs
            tab = tabs[properties.tab_index]
            btn = tab.buttons[properties.button_index]
            return btn.name or ""
        except Exception:
            return ""

    def execute(self, context):
        tabs = _get_tabs(context)
        if not (0 <= self.tab_index < len(tabs)):
            return {'CANCELLED'}
        tab = tabs[self.tab_index]
        if not (0 <= self.button_index < len(tab.buttons)):
            return {'CANCELLED'}
        btn = tab.buttons[self.button_index]
        if btn.cmd_type in NON_COMMAND_TYPES:
            return {'CANCELLED'}
        try:
            if btn.cmd_type == 'OPERATOR':
                _run_operator_call(context, btn.operator_id, btn.operator_kwargs, btn.operator_context)

            elif btn.cmd_type == 'MACRO':
                if len(btn.macro_steps) == 0:
                    self.report({'WARNING'}, "This macro has no steps yet")
                    return {'CANCELLED'}
                for i, step in enumerate(btn.macro_steps):
                    if step.step_type == 'OPERATOR':
                        result = _run_operator_call(context, step.operator_id, step.operator_kwargs, step.operator_context)
                        if result and 'CANCELLED' in result and 'FINISHED' not in result:
                            self.report({'ERROR'}, f"Step {i + 1} ({step.operator_id}) was cancelled - stopped macro")
                            return {'CANCELLED'}
                    else:
                        exec(step.python_code, {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context})

            elif btn.cmd_type == 'TEXT_SCRIPT':
                text = bpy.data.texts.get(btn.script_name)
                if text is None:
                    self.report({'ERROR'}, f"Text block '{btn.script_name}' not found")
                    return {'CANCELLED'}
                exec(compile(text.as_string(), text.name, 'exec'),
                     {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context})

            elif btn.cmd_type == 'PYTHON_INLINE':
                exec(btn.python_code, {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context})

            elif btn.cmd_type == 'PROP_SLIDER':
                exec(btn.python_code, {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context, 'value': btn.slider_value})

            elif btn.cmd_type == 'PROP_COLOR':
                exec(btn.python_code, {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context, 'value': tuple(btn.color)})

            elif btn.cmd_type == 'PROP_TOGGLE':
                btn.toggle_value = not btn.toggle_value
                exec(btn.python_code, {'bpy': bpy, 'C': context, 'D': bpy.data, 'context': context, 'value': btn.toggle_value})

        except Exception as e:
            self.report({'ERROR'}, f"{type(e).__name__}: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Record: capture the next operator the user runs, and fill it into a button
# ---------------------------------------------------------------------------
class CTM_OT_record_operator(bpy.types.Operator):
    bl_idname = "ctm.record_operator"
    bl_label = "Record This Button"
    bl_description = "Click, then perform the action you want (menu item / shortcut) in Blender. It will be captured automatically."
    tab_index: IntProperty()
    button_index: IntProperty()

    _timer = None
    _start_count = 0

    def invoke(self, context, event):
        tabs = _get_tabs(context)
        if not (0 <= self.tab_index < len(tabs)):
            return {'CANCELLED'}
        tab = tabs[self.tab_index]
        if not (0 <= self.button_index < len(tab.buttons)):
            return {'CANCELLED'}
        btn = tab.buttons[self.button_index]

        wm = context.window_manager
        self._start_count = len(wm.operators)
        context.scene.ctm_recording = True
        context.scene.ctm_recording_label = f"{tab.name} / {btn.name}"
        self._timer = wm.event_timer_add(0.15, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.scene.ctm_recording:
            # cancelled via the Cancel button in the panel
            self._stop_timer(context)
            return {'CANCELLED'}

        if event.type == 'ESC':
            self._stop_timer(context)
            context.scene.ctm_recording = False
            return {'CANCELLED'}

        if event.type == 'TIMER':
            wm = context.window_manager
            if len(wm.operators) > self._start_count:
                op = wm.operators[-1]
                self._capture(context, op)
                self._stop_timer(context)
                context.scene.ctm_recording = False
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def _capture(self, context, op):
        tabs = _get_tabs(context)
        tab = tabs[self.tab_index]
        btn = tab.buttons[self.button_index]

        operator_id, kwargs_repr, warning = _capture_operator_info(op)
        btn.operator_id = operator_id
        btn.operator_kwargs = kwargs_repr
        if warning:
            self.report({'WARNING'}, warning)
        self.report({'INFO'}, f"Captured: {btn.operator_id}")

    def _stop_timer(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CTM_OT_record_macro_step(bpy.types.Operator):
    bl_idname = "ctm.record_macro_step"
    bl_label = "Record Macro Steps"
    bl_description = (
        "Click, then perform your whole sequence of actions in Blender "
        "(e.g. press S, X, 0, Enter). Each operator you run is appended as "
        "its own step, in order, until you press Stop/Cancel or Esc."
    )
    tab_index: IntProperty()
    button_index: IntProperty()

    _timer = None
    _start_count = 0

    def invoke(self, context, event):
        btn = _get_button(context, self.tab_index, self.button_index)
        if btn is None:
            return {'CANCELLED'}
        tab = _get_tabs(context)[self.tab_index]

        wm = context.window_manager
        self._start_count = len(wm.operators)
        context.scene.ctm_recording = True
        context.scene.ctm_recording_label = f"{tab.name} / {btn.name} (macro)"
        self._timer = wm.event_timer_add(0.15, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.scene.ctm_recording:
            self._stop_timer(context)
            return {'CANCELLED'}

        if event.type == 'ESC':
            self._stop_timer(context)
            context.scene.ctm_recording = False
            return {'CANCELLED'}

        if event.type == 'TIMER':
            wm = context.window_manager
            if len(wm.operators) > self._start_count:
                op = wm.operators[-1]
                self._start_count = len(wm.operators)
                self._capture(context, op)
                # Deliberately do NOT stop here - keep recording further
                # steps until the user presses Stop/Cancel or Esc, so a
                # whole multi-key combo can be captured as one macro.

        return {'PASS_THROUGH'}

    def _capture(self, context, op):
        btn = _get_button(context, self.tab_index, self.button_index)
        if btn is None:
            return
        operator_id, kwargs_repr, warning = _capture_operator_info(op)
        step = btn.macro_steps.add()
        step.step_type = 'OPERATOR'
        step.operator_id = operator_id
        step.operator_kwargs = kwargs_repr
        btn.macro_active_index = len(btn.macro_steps) - 1
        if warning:
            self.report({'WARNING'}, warning)
        self.report({'INFO'}, f"Step {len(btn.macro_steps)} captured: {operator_id}")

    def _stop_timer(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


class CTM_OT_record_cancel(bpy.types.Operator):
    bl_idname = "ctm.record_cancel"
    bl_label = "Cancel Recording"

    def execute(self, context):
        context.scene.ctm_recording = False
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Icon browser: click-only, categorized nested menus.
#
# The earlier version embedded a live text-search field inside the popup.
# In testing, typing into that field put Blender into a text-edit state that
# then required pressing Enter before ANY further click (including picking
# an icon) registered. That is a property of embedding an editable text
# field inside a popup/menu, not something fixable with more code around it.
#
# This version has NO text field at all: click a category, then click an
# icon. Both are plain button clicks, which is the standard, reliable way
# Blender menus behave (like the right-click menu or Add Object menu) -
# every click both selects and closes, no Enter needed.
#
# For typing-based search, use the existing "Icon" dropdown field instead
# (a few lines above the Browse Icons button) - that is Blender's own native
# enum dropdown, which has its own built-in type-to-filter for long lists.
# ---------------------------------------------------------------------------
class CTM_OT_icon_pick(bpy.types.Operator):
    bl_idname = "ctm.icon_pick"
    bl_label = "Pick Icon"
    bl_options = {'INTERNAL'}
    tab_index: IntProperty()
    button_index: IntProperty()
    icon_name: StringProperty()

    def execute(self, context):
        tabs = _get_tabs(context)
        if not (0 <= self.tab_index < len(tabs)):
            return {'CANCELLED'}
        tab = tabs[self.tab_index]
        if not (0 <= self.button_index < len(tab.buttons)):
            return {'CANCELLED'}
        tab.buttons[self.button_index].icon = self.icon_name
        return {'FINISHED'}


class CTM_OT_icon_search_browser(bpy.types.Operator):
    bl_idname = "ctm.icon_search_browser"
    bl_label = "Icon Search"
    bl_description = "Type to filter icons by name, then click one to pick it"
    tab_index: IntProperty()
    button_index: IntProperty()
    search: StringProperty(name="Search", default="")
    page: IntProperty(name="Page", default=0, min=0)

    _PAGE_SIZE = 144
    _COLS = 12

    def invoke(self, context, event):
        context.scene.ctm_icon_pick_tab = self.tab_index
        context.scene.ctm_icon_pick_button = self.button_index
        self.search = ""
        self.page = 0
        return context.window_manager.invoke_props_dialog(self, width=480)

    def check(self, context):
        # Tells Blender to redraw this dialog whenever a property (the
        # search text, or the page number) changes, so the filtered icon
        # list updates live as you type or page. This is the officially
        # supported way to do that - unlike the earlier attempts
        # (invoke_popup / Menu), this dialog is specifically designed by
        # Blender for live-interactive content.
        return True

    def draw(self, context):
        layout = self.layout
        layout.label(text="Type to filter. Click an icon to pick it (applies right away),")
        layout.label(text="then press OK (or Enter) to close this window.")
        layout.prop(self, "search", icon='VIEWZOOM', text="Search")

        names = [n for n in ICON_NAMES if self.search.upper() in n]
        total_pages = max(1, -(-len(names) // self._PAGE_SIZE))  # ceil division
        if self.page >= total_pages:
            self.page = total_pages - 1
        if self.page < 0:
            self.page = 0

        start = self.page * self._PAGE_SIZE
        shown = names[start:start + self._PAGE_SIZE]

        info_row = layout.row(align=True)
        info_row.label(text=f"{len(names)} icon(s) match")
        if total_pages > 1:
            layout.prop(self, "page", text=f"Page (0 - {total_pages - 1})")

        for i in range(0, len(shown), self._COLS):
            row = layout.row(align=True)
            for n in shown[i:i + self._COLS]:
                op = row.operator("ctm.icon_pick", text="", icon=n if n != "NONE" else 'BLANK1')
                op.tab_index = context.scene.ctm_icon_pick_tab
                op.button_index = context.scene.ctm_icon_pick_button
                op.icon_name = n

    def execute(self, context):
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------
FIELDS = [
    "name", "icon", "cmd_type", "operator_id", "operator_kwargs", "operator_context",
    "script_name", "python_code", "slider_value", "slider_min", "slider_max",
    "toggle_value", "scale_x", "scale_y", "show_color_tag",
    "icon_only", "grid_row", "grid_col", "span_cols", "highlight_preset", "highlight_expr",
]

DEFAULTS_FILENAME = "command_deck_defaults.json"


def _get_defaults_path():
    """Same folder as this addon file. Deleting the addon's folder/file also
    removes this - it does not live anywhere else on disk."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULTS_FILENAME)


MACRO_STEP_FIELDS = ["step_type", "operator_id", "operator_kwargs", "operator_context", "python_code"]


def _serialize_tabs(tabs):
    data = []
    for tab in tabs:
        tab_data = {"name": tab.name, "columns": tab.columns, "rows": tab.rows, "buttons": []}
        for btn in tab.buttons:
            bd = {f: getattr(btn, f) for f in FIELDS}
            bd["color"] = list(btn.color)
            bd["macro_steps"] = [
                {f: getattr(step, f) for f in MACRO_STEP_FIELDS} for step in btn.macro_steps
            ]
            tab_data["buttons"].append(bd)
        data.append(tab_data)
    return data


def _deserialize_tabs(tabs_collection, data):
    tabs_collection.clear()
    for tab_data in data:
        tab = tabs_collection.add()
        tab.name = tab_data.get("name", "Tab")
        tab.columns = tab_data.get("columns", 4)
        tab.rows = tab_data.get("rows", 4)
        for bd in tab_data.get("buttons", []):
            btn = tab.buttons.add()
            for f in FIELDS:
                if f in bd:
                    setattr(btn, f, bd[f])
            if "color" in bd:
                btn.color = bd["color"]
            for sd in bd.get("macro_steps", []):
                step = btn.macro_steps.add()
                for f in MACRO_STEP_FIELDS:
                    if f in sd:
                        setattr(step, f, sd[f])


class CTM_OT_export_layout(bpy.types.Operator, ExportHelper):
    bl_idname = "ctm.export_layout"
    bl_label = "Export Layout (JSON)"
    filename_ext = ".json"

    def execute(self, context):
        data = _serialize_tabs(_get_tabs(context))
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.report({'INFO'}, f"Exported to {self.filepath}")
        return {'FINISHED'}


class CTM_OT_import_layout(bpy.types.Operator, ImportHelper):
    bl_idname = "ctm.import_layout"
    bl_label = "Import Layout (JSON)"
    filename_ext = ".json"

    def execute(self, context):
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _deserialize_tabs(_get_tabs(context), data)
        context.scene.ctm_active_tab = 0
        self.report({'INFO'}, f"Imported from {self.filepath}")
        return {'FINISHED'}


class CTM_OT_save_defaults(bpy.types.Operator):
    bl_idname = "ctm.save_defaults"
    bl_label = "設定保存"
    bl_description = (
        "Save the current tabs/buttons as the default. Saved next to this "
        "addon's own file, and automatically loaded every time a file is "
        "opened (as long as that file doesn't already have its own tabs)."
    )

    def execute(self, context):
        data = _serialize_tabs(_get_tabs(context))
        path = _get_defaults_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save defaults: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Saved as default ({path})")
        return {'FINISHED'}


@bpy.app.handlers.persistent
def _ctm_load_post_handler(dummy):
    """Runs after any .blend file finishes loading (including Blender's own
    startup file). If the current scene doesn't already have its own tabs
    set up, and a saved default exists, load it automatically."""
    scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return
    if len(scene.ctm_tabs) > 0:
        return
    path = _get_defaults_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _deserialize_tabs(scene.ctm_tabs, data)
    except Exception as e:
        print(f"[Command Deck] Failed to auto-load defaults: {e}")


# ---------------------------------------------------------------------------
# Addon Preferences (Edit > Preferences > Add-ons > Command Deck)
# ---------------------------------------------------------------------------
def _on_show_toolbar_update(self, context):
    # This runs at the moment the checkbox is actually clicked (a safe
    # place to write data), NOT during panel draw() (writing data during
    # draw() is not allowed in Blender and can silently abort the rest of
    # that panel's drawing - which is why buttons were disappearing).
    if not self.show_toolbar:
        for scene in bpy.data.scenes:
            if scene.ctm_edit_mode:
                scene.ctm_edit_mode = False


class CTM_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    show_toolbar: BoolProperty(
        name="ツールバーを表示 (編集モード / エクスポート / インポート / 設定保存)",
        description="オフにすると、パネル上部の「編集モード・↑・↓・設定保存」の行を隠します。"
                    "隠している間もタブとボタンは普通に押せます。再表示したいときはここに戻ってチェックを入れ直してください。",
        default=True,
        update=_on_show_toolbar_update,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "show_toolbar")


def _get_prefs(context):
    return context.preferences.addons[__name__].preferences


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------
class CTM_PT_panel(bpy.types.Panel):
    bl_label = "Command Deck"
    bl_idname = "CTM_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CmdDeck"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tabs = scene.ctm_tabs

        try:
            show_toolbar = _get_prefs(context).show_toolbar
        except Exception:
            show_toolbar = True

        if show_toolbar:
            header = layout.row(align=True)
            header.prop(scene, "ctm_edit_mode", text="Edit Mode", toggle=True, icon='TOOL_SETTINGS')
            header.operator("ctm.export_layout", text="", icon='EXPORT')
            header.operator("ctm.import_layout", text="", icon='IMPORT')
            header.operator("ctm.save_defaults", text="設定保存", icon='FILE_TICK')

        if scene.ctm_recording:
            rec_box = layout.box()
            rec_row = rec_box.row(align=True)
            rec_row.alert = True
            rec_row.label(text=f"● Recording for: {scene.ctm_recording_label}", icon='REC')
            rec_row2 = rec_box.row(align=True)
            if scene.ctm_recording_label.endswith("(macro)"):
                rec_row2.label(text="Perform your whole sequence of actions, then press Stop.")
                rec_row2.operator("ctm.record_cancel", text="Stop", icon='CHECKMARK')
            else:
                rec_row2.label(text="Now perform ONLY the target action (menu / shortcut).")
                rec_row2.operator("ctm.record_cancel", text="Cancel", icon='X')

        # Tab row
        tab_row = layout.row(align=True)
        tab_row.scale_y = 1.2
        for i, tab in enumerate(tabs):
            op = tab_row.operator("ctm.tab_select", text=tab.name, depress=(i == scene.ctm_active_tab))
            op.tab_index = i
        if scene.ctm_edit_mode:
            tab_row.operator("ctm.tab_add", text="", icon='ADD')

        if len(tabs) == 0:
            layout.label(text="Add a tab to get started.", icon='INFO')
            return

        active_idx = max(0, min(scene.ctm_active_tab, len(tabs) - 1))
        tab = tabs[active_idx]
        box = layout.box()

        if scene.ctm_edit_mode:
            self.draw_edit_mode(context, box, tabs, active_idx, tab)
        else:
            self.draw_run_mode(context, box, active_idx, tab)

    def draw_run_mode(self, context, layout, tab_index, tab):
        if len(tab.buttons) == 0:
            layout.label(text="No buttons yet. Switch to Edit Mode to add some.", icon='INFO')
            return

        # span_owner maps every (row, col) cell covered by a button - including
        # cells to the right of its own top-left position when span_cols > 1 -
        # to that button's index, so those extra cells are skipped instead of
        # getting their own separate (empty) column.
        span_owner = {}
        for b_idx, btn in enumerate(tab.buttons):
            r, c = btn.grid_row, btn.grid_col
            span = max(1, btn.span_cols)
            for dc in range(span):
                span_owner[(r, c + dc)] = b_idx

        rows = max(tab.rows, 1)
        cols = max(tab.columns, 1)

        for r in range(1, rows + 1):
            row_layout = layout.row(align=True)
            c = 1
            while c <= cols:
                b_idx = span_owner.get((r, c))
                if b_idx is None:
                    cell = row_layout.column(align=True)
                    cell.label(text="")
                    c += 1
                    continue
                btn = tab.buttons[b_idx]
                if btn.grid_col != c:
                    # A cell can only be consumed by a span starting to its
                    # left; if this isn't that button's own top-left column,
                    # something overlaps (e.g. two buttons claim the same
                    # cell) - skip forward one cell rather than draw it twice.
                    c += 1
                    continue
                span = max(1, btn.span_cols)
                cell = row_layout.column(align=True)
                cell.scale_x = span  # wider cell gets proportionally more of the row's width
                self._draw_button_cell(context, cell, tab_index, b_idx, btn)
                c += span

    def _eval_highlight(self, context, btn):
        """Returns True/False based on highlight_preset, or None (meaning:
        no override, use the button's own state, e.g. Toggle's toggle_value)."""
        preset = btn.highlight_preset
        try:
            if preset == 'NONE':
                return None
            if preset == 'OBJECT_MODE':
                return context.mode == 'OBJECT'
            if preset == 'EDIT_MODE':
                return context.mode.startswith('EDIT_')
            if preset == 'SCULPT_MODE':
                return context.mode == 'SCULPT'
            if preset == 'VERTEX_PAINT_MODE':
                return context.mode == 'PAINT_VERTEX'
            if preset == 'WEIGHT_PAINT_MODE':
                return context.mode == 'PAINT_WEIGHT'
            if preset == 'TEXTURE_PAINT_MODE':
                return context.mode == 'PAINT_TEXTURE'
            if preset == 'POSE_MODE':
                return context.mode == 'POSE'
            if preset == 'MESH_SELECT_VERT':
                return bool(context.tool_settings.mesh_select_mode[0])
            if preset == 'MESH_SELECT_EDGE':
                return bool(context.tool_settings.mesh_select_mode[1])
            if preset == 'MESH_SELECT_FACE':
                return bool(context.tool_settings.mesh_select_mode[2])
            if preset in {'TOOL_MOVE', 'TOOL_ROTATE', 'TOOL_SCALE'}:
                wanted = {'TOOL_MOVE': 'builtin.move', 'TOOL_ROTATE': 'builtin.rotate',
                          'TOOL_SCALE': 'builtin.scale'}[preset]
                return _get_active_tool_id(context) == wanted
            if preset in {'ORIENT_GLOBAL', 'ORIENT_LOCAL', 'ORIENT_NORMAL'}:
                wanted = {'ORIENT_GLOBAL': 'GLOBAL', 'ORIENT_LOCAL': 'LOCAL',
                          'ORIENT_NORMAL': 'NORMAL'}[preset]
                return context.scene.transform_orientation_slots[0].type == wanted
            if preset == 'CUSTOM':
                expr = btn.highlight_expr.strip()
                if not expr:
                    return None
                return bool(eval(expr, {'bpy': bpy, 'C': context, 'context': context}))
        except Exception:
            return None

    def _draw_button_cell(self, context, cell, tab_index, b_idx, btn):
        row = cell.row(align=True)
        row.scale_x = btn.scale_x
        row.scale_y = btn.scale_y

        if btn.cmd_type == 'LABEL':
            row.label(text=btn.name, icon=btn.icon if btn.icon != "NONE" else 'NONE')
            return

        label_text = "" if (btn.icon_only and btn.cmd_type in LABELABLE_TYPES) else btn.name
        highlight = self._eval_highlight(context, btn)

        if btn.cmd_type in {'OPERATOR', 'TEXT_SCRIPT', 'PYTHON_INLINE', 'MACRO'}:
            op = row.operator("ctm.button_execute", text=label_text,
                               icon=btn.icon if btn.icon != "NONE" else 'NONE',
                               depress=bool(highlight))
            op.tab_index = tab_index
            op.button_index = b_idx

        elif btn.cmd_type == 'PROP_SLIDER':
            row.prop(btn, "slider_value", text=btn.name, slider=True)
            op = row.operator("ctm.button_execute", text="", icon='PLAY')
            op.tab_index = tab_index
            op.button_index = b_idx

        elif btn.cmd_type == 'PROP_COLOR':
            row.prop(btn, "color", text=btn.name)
            op = row.operator("ctm.button_execute", text="", icon='PLAY')
            op.tab_index = tab_index
            op.button_index = b_idx

        elif btn.cmd_type == 'PROP_TOGGLE':
            depress = highlight if highlight is not None else btn.toggle_value
            op = row.operator("ctm.button_execute", text=label_text,
                               icon=btn.icon if btn.icon != "NONE" else 'NONE',
                               depress=depress)
            op.tab_index = tab_index
            op.button_index = b_idx

        if btn.show_color_tag:
            tag_row = cell.row(align=True)
            tag_row.enabled = False
            tag_row.scale_y = 0.3
            tag_row.prop(btn, "color", text="")

    def draw_macro_steps(self, context, box, tab_index, button_index, btn):
        box.label(text="Steps (run top to bottom):")
        box.template_list("CTM_UL_macro_steps", "", btn, "macro_steps", btn, "macro_active_index", rows=4)

        row = box.row(align=True)
        add_op = row.operator("ctm.macro_step_add", text="Add Step", icon='ADD')
        add_op.tab_index = tab_index
        add_op.button_index = button_index
        rem_op = row.operator("ctm.macro_step_remove", text="Remove", icon='REMOVE')
        rem_op.tab_index = tab_index
        rem_op.button_index = button_index
        up_op = row.operator("ctm.macro_step_move", text="", icon='TRIA_UP')
        up_op.tab_index = tab_index
        up_op.button_index = button_index
        up_op.direction = "UP"
        down_op = row.operator("ctm.macro_step_move", text="", icon='TRIA_DOWN')
        down_op.tab_index = tab_index
        down_op.button_index = button_index
        down_op.direction = "DOWN"

        rec_row = box.row(align=True)
        rec_row.enabled = not context.scene.ctm_recording
        rec_op = rec_row.operator("ctm.record_macro_step", text="Record Steps (perform your whole shortcut combo)", icon='REC')
        rec_op.tab_index = tab_index
        rec_op.button_index = button_index

        if len(btn.macro_steps) == 0:
            return
        s_idx = max(0, min(btn.macro_active_index, len(btn.macro_steps) - 1))
        step = btn.macro_steps[s_idx]

        step_box = box.box()
        step_box.label(text=f"Step {s_idx + 1}")
        step_box.prop(step, "step_type")
        if step.step_type == 'OPERATOR':
            step_box.prop(step, "operator_id")
            step_box.prop(step, "operator_kwargs")
            step_box.prop(step, "operator_context")
        else:
            step_box.prop(step, "python_code")

    def draw_edit_mode(self, context, layout, tabs, tab_index, tab):
        # Tab settings
        row = layout.row(align=True)
        row.prop(tab, "name", text="Tab Name")
        grid_row = layout.row(align=True)
        grid_row.prop(tab, "columns", text="Cols (横)")
        grid_row.prop(tab, "rows", text="Rows (縦)")
        mv = layout.row(align=True)
        op = mv.operator("ctm.tab_move", text="", icon='TRIA_UP'); op.tab_index = tab_index; op.direction = "UP"
        op = mv.operator("ctm.tab_move", text="", icon='TRIA_DOWN'); op.tab_index = tab_index; op.direction = "DOWN"
        op = mv.operator("ctm.tab_remove", text="Delete Tab", icon='X'); op.tab_index = tab_index

        # Conflict warning: two buttons assigned to the same (row, col)
        seen = {}
        conflicts = set()
        for b in tab.buttons:
            key = (b.grid_row, b.grid_col)
            if key in seen:
                conflicts.add(key)
            seen[key] = True
        if conflicts:
            warn = layout.box()
            warn.alert = True
            warn.label(text="Position conflict (same Row/Col) at: " +
                       ", ".join(f"R{r}C{c}" for r, c in sorted(conflicts)), icon='ERROR')

        layout.separator()

        # Button list
        layout.template_list("CTM_UL_buttons", "", tab, "buttons", tab, "active_index", rows=4)
        row = layout.row(align=True)
        row.operator("ctm.button_add", text="Add", icon='ADD')
        row.operator("ctm.button_remove", text="Remove", icon='REMOVE')
        op = row.operator("ctm.button_move", text="", icon='TRIA_UP'); op.direction = "UP"
        op = row.operator("ctm.button_move", text="", icon='TRIA_DOWN'); op.direction = "DOWN"
        op = row.operator("ctm.button_move", text="", icon='TRIA_UP_BAR'); op.direction = "TOP"
        op = row.operator("ctm.button_move", text="", icon='TRIA_DOWN_BAR'); op.direction = "BOTTOM"

        row2 = layout.row(align=True)
        row2.label(text="Grid Row (縦) Shift:")
        op = row2.operator("ctm.button_shift_rows", text="-1", icon='TRIA_UP'); op.direction = "UP"
        op = row2.operator("ctm.button_shift_rows", text="+1", icon='TRIA_DOWN'); op.direction = "DOWN"

        if len(tab.buttons) == 0:
            return
        idx = max(0, min(tab.active_index, len(tab.buttons) - 1))
        btn = tab.buttons[idx]

        box = layout.box()
        box.prop(btn, "name")
        box.prop(btn, "cmd_type")

        if btn.cmd_type not in NO_ICON_TYPES:
            box.prop(btn, "icon")
            search_row = box.row(align=True)
            search_op = search_row.operator("ctm.icon_search_browser", text="Search by Name...", icon='VIEWZOOM')
            search_op.tab_index = tab_index
            search_op.button_index = idx

        if btn.cmd_type == 'OPERATOR':
            box.prop(btn, "operator_id")
            box.prop(btn, "operator_kwargs")
            box.prop(btn, "operator_context")
            rec_row = box.row(align=True)
            rec_row.enabled = not context.scene.ctm_recording
            rec_op = rec_row.operator("ctm.record_operator", text="Record This Button", icon='REC')
            rec_op.tab_index = tab_index
            rec_op.button_index = idx
        elif btn.cmd_type == 'MACRO':
            self.draw_macro_steps(context, box, tab_index, idx, btn)
        elif btn.cmd_type == 'TEXT_SCRIPT':
            box.prop_search(btn, "script_name", bpy.data, "texts")
        elif btn.cmd_type == 'PYTHON_INLINE':
            box.prop(btn, "python_code")
        elif btn.cmd_type == 'PROP_SLIDER':
            r = box.row()
            r.prop(btn, "slider_min")
            r.prop(btn, "slider_max")
            box.prop(btn, "python_code", text="On Apply Code")
        elif btn.cmd_type == 'PROP_COLOR':
            box.prop(btn, "python_code", text="On Apply Code")
        elif btn.cmd_type == 'PROP_TOGGLE':
            box.prop(btn, "python_code", text="On Toggle Code")
        elif btn.cmd_type in NON_COMMAND_TYPES:
            box.label(text="Layout-only item: not a command, nothing to configure here.", icon='INFO')

        if btn.cmd_type in LABELABLE_TYPES:
            box.prop(btn, "icon_only")

        row = box.row(align=True)
        row.prop(btn, "scale_x")
        row.prop(btn, "scale_y")
        row.prop(btn, "show_color_tag", toggle=True, icon='COLOR')
        if btn.show_color_tag:
            box.prop(btn, "color")

        pos_row = box.row(align=True)
        pos_row.prop(btn, "grid_col", text="横")
        pos_row.prop(btn, "grid_row", text="縦")
        box.prop(btn, "span_cols", text="Width (in Cols)")

        if btn.cmd_type not in NON_COMMAND_TYPES:
            box.prop(btn, "highlight_preset")
            if btn.highlight_preset == 'CUSTOM':
                box.prop(btn, "highlight_expr")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
classes = (
    CTM_MacroStep,
    CTM_Button,
    CTM_Tab,
    CTM_UL_buttons,
    CTM_UL_macro_steps,
    CTM_OT_tab_add,
    CTM_OT_tab_remove,
    CTM_OT_tab_move,
    CTM_OT_tab_select,
    CTM_OT_button_add,
    CTM_OT_button_remove,
    CTM_OT_button_move,
    CTM_OT_button_shift_rows,
    CTM_OT_macro_step_add,
    CTM_OT_macro_step_remove,
    CTM_OT_macro_step_move,
    CTM_OT_button_execute,
    CTM_OT_record_operator,
    CTM_OT_record_macro_step,
    CTM_OT_record_cancel,
    CTM_OT_icon_pick,
    CTM_OT_icon_search_browser,
    CTM_OT_export_layout,
    CTM_OT_import_layout,
    CTM_OT_save_defaults,
    CTM_AddonPreferences,
    CTM_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ctm_tabs = CollectionProperty(type=CTM_Tab)
    bpy.types.Scene.ctm_active_tab = IntProperty(default=0)
    bpy.types.Scene.ctm_edit_mode = BoolProperty(name="Edit Mode", default=False)
    bpy.types.Scene.ctm_recording = BoolProperty(name="Recording", default=False)
    bpy.types.Scene.ctm_recording_label = StringProperty(name="Recording Target", default="")
    bpy.types.Scene.ctm_icon_search = StringProperty(name="Icon Search", default="")
    bpy.types.Scene.ctm_icon_pick_tab = IntProperty(default=0)
    bpy.types.Scene.ctm_icon_pick_button = IntProperty(default=0)

    if _ctm_load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_ctm_load_post_handler)
    # Also try loading right now - load_post won't fire again for a file
    # that was already open before this addon got enabled.
    try:
        _ctm_load_post_handler(None)
    except Exception as e:
        print(f"[Command Deck] Initial defaults load skipped: {e}")


def unregister():
    if _ctm_load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_ctm_load_post_handler)
    del bpy.types.Scene.ctm_icon_pick_button
    del bpy.types.Scene.ctm_icon_pick_tab
    del bpy.types.Scene.ctm_icon_search
    del bpy.types.Scene.ctm_recording_label
    del bpy.types.Scene.ctm_recording
    del bpy.types.Scene.ctm_edit_mode
    del bpy.types.Scene.ctm_active_tab
    del bpy.types.Scene.ctm_tabs
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
