bl_info = {
    "name": "Op Recorder (Command Deck helper)",
    "author": "DiGiM + Claude",
    "version": (3, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Op Recorder",
    "description": "Always shows the most recently run operator's Type / "
                   "Operator ID / Operator Args / Execution Context live in "
                   "the panel, in normal copy/paste-able text fields (click "
                   "and drag to select, Ctrl+C to copy) - handy for filling "
                   "in Command Deck buttons.",
    "category": "Development",
}

import bpy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
LIKELY_NEEDS_INVOKE = {
    "mesh.inset", "mesh.bevel", "mesh.loopcut", "mesh.knife_tool",
    "mesh.bridge_edge_loops", "mesh.rip", "mesh.rip_edge",
    "transform.translate", "transform.rotate", "transform.resize",
    "transform.shrink_fatten", "transform.edge_slide", "transform.vert_slide",
    "view3d.select_box", "view3d.select_circle", "view3d.select_lasso",
}


def _idname_to_pyname(bl_idname):
    """Convert 'MESH_OT_inset' -> 'mesh.inset'."""
    if "_OT_" in bl_idname:
        mod, func = bl_idname.split("_OT_", 1)
        return f"{mod.lower()}.{func}"
    return bl_idname


def _capture_operator_info(op):
    """Return (operator_id, kwargs_repr, warning_or_None)."""
    operator_id = _idname_to_pyname(op.bl_idname)

    kwargs = {}
    props = op.properties
    for p in props.bl_rna.properties:
        if p.identifier == 'rna_type':
            continue
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
    try:
        if kwargs_repr:
            eval(kwargs_repr)
    except Exception:
        kwargs_repr = ""
        warning = "Some captured values could not be safely re-used and were dropped."

    return operator_id, kwargs_repr, warning


def _context_guess(operator_id):
    return "INVOKE_DEFAULT" if operator_id in LIKELY_NEEDS_INVOKE else "EXEC_DEFAULT"


# ---------------------------------------------------------------------------
# Always-on background watcher (bpy.app.timers) - keeps polling
# window_manager.operators forever, no button press needed.
# ---------------------------------------------------------------------------
_last_count = 0


def _oprec_poll():
    global _last_count
    try:
        wm = bpy.context.window_manager
        scene = bpy.context.scene
    except Exception:
        return 0.15

    if wm is None or scene is None:
        return 0.15

    current = len(wm.operators)
    if current > _last_count:
        op = wm.operators[-1]
        _last_count = current
        operator_id, kwargs_repr, warning = _capture_operator_info(op)
        context_guess = _context_guess(operator_id)

        scene.oprec_live_type = "Operator"
        scene.oprec_live_id = operator_id
        scene.oprec_live_args = kwargs_repr if kwargs_repr else "(none)"
        scene.oprec_live_context = context_guess

        screen = bpy.context.screen
        for area in (screen.areas if screen else []):
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    elif current < _last_count:
        # Undo, or a new file/window_manager - just resync quietly.
        _last_count = current

    return 0.15  # keep rescheduling forever


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class OPREC_PT_panel(bpy.types.Panel):
    bl_label = "Op Recorder"
    bl_idname = "OPREC_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Op Recorder"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="現在の操作 (Live)", icon='INFO')
        # prop() draws an editable text field, which - unlike label() - can
        # be click-and-drag selected and copied with Ctrl+C.
        box.prop(scene, "oprec_live_type", text="Type")
        box.prop(scene, "oprec_live_id", text="Operator ID")
        box.prop(scene, "oprec_live_args", text="Operator Args")
        box.prop(scene, "oprec_live_context", text="Execution Context")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
classes = (
    OPREC_PT_panel,
)


def register():
    global _last_count
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.oprec_live_type = bpy.props.StringProperty(default="")
    bpy.types.Scene.oprec_live_id = bpy.props.StringProperty(default="")
    bpy.types.Scene.oprec_live_args = bpy.props.StringProperty(default="")
    bpy.types.Scene.oprec_live_context = bpy.props.StringProperty(default="")

    try:
        _last_count = len(bpy.context.window_manager.operators)
    except Exception:
        _last_count = 0

    if not bpy.app.timers.is_registered(_oprec_poll):
        bpy.app.timers.register(_oprec_poll, first_interval=0.15, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_oprec_poll):
        bpy.app.timers.unregister(_oprec_poll)

    del bpy.types.Scene.oprec_live_context
    del bpy.types.Scene.oprec_live_args
    del bpy.types.Scene.oprec_live_id
    del bpy.types.Scene.oprec_live_type

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
