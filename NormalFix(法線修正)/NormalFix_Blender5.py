# -*- coding: utf-8 -*-
"""
NormalFix Blender 5 Ver1.0.2

実行すると、3Dビューのサイドバー（Nキー）に
「NormalFix」タブが追加されます。

処理順:
1. 指定角度で自動スムース
2. カスタム分割法線をリセット
3. 面法線を外向きに再計算
4. Weighted Normalモディファイアを追加
5. 必要に応じて全モディファイアを適用

複数メッシュ対応・Undo対応。
"""

bl_info = {
    "name": "NormalFix Blender 5",
    "author": "OpenAI Codex",
    "version": (1, 0, 2),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > NormalFix",
    "description": "Fix polygon normals and hard-surface shading",
    "category": "Mesh",
}

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup

# Text Editorから再実行した場合は、前回登録したクラスを先に解除する。
try:
    unregister()
except (NameError, RuntimeError):
    pass


TOOL_VERSION = "1.0.2"
WEIGHTED_MODIFIER_NAME = "NormalFix_Weighted"


PRESET_ITEMS = (
    ("STANDARD", "標準", "35度・面積＋角度ウェイト"),
    ("HARD_SURFACE", "ハードサーフェス", "5度・面積＋角度ウェイト"),
    ("SMOOTH", "滑らか", "90度・角度ウェイト"),
)


WEIGHT_MODE_ITEMS = (
    ("FACE_AREA_WITH_ANGLE", "面積＋角度", "面積とコーナー角度で重み付け"),
    ("FACE_AREA", "面積", "面の面積で重み付け"),
    ("CORNER_ANGLE", "角度", "コーナー角度で重み付け"),
)


def _preset_changed(settings, _context):
    if settings.preset == "STANDARD":
        settings.use_auto_smooth = True
        settings.smooth_angle = math.radians(35.0)
        settings.use_weighted_normals = True
        settings.weight_mode = "FACE_AREA_WITH_ANGLE"
    elif settings.preset == "HARD_SURFACE":
        settings.use_auto_smooth = True
        settings.smooth_angle = math.radians(5.0)
        settings.use_weighted_normals = True
        settings.weight_mode = "FACE_AREA_WITH_ANGLE"
    elif settings.preset == "SMOOTH":
        settings.use_auto_smooth = True
        settings.smooth_angle = math.radians(90.0)
        settings.use_weighted_normals = True
        settings.weight_mode = "CORNER_ANGLE"


class NORMALFIX_PG_settings(PropertyGroup):
    preset: EnumProperty(
        name="プリセット",
        items=PRESET_ITEMS,
        default="STANDARD",
        update=_preset_changed,
    )
    use_auto_smooth: BoolProperty(
        name="最初に自動スムースを適用",
        default=True,
    )
    smooth_angle: FloatProperty(
        name="スムース角度",
        description="この角度を超える隣接面のエッジをシャープにします",
        subtype="ANGLE",
        unit="ROTATION",
        min=0.0,
        max=math.pi,
        default=math.radians(35.0),
    )
    reset_custom_normals: BoolProperty(
        name="既存のカスタム法線をリセット",
        default=False,
    )
    recalculate_outside: BoolProperty(
        name="面法線を外向きに再計算（反転面の修正）",
        default=False,
    )
    use_weighted_normals: BoolProperty(
        name="Weighted Normalで補正",
        default=True,
    )
    weight_mode: EnumProperty(
        name="ウェイト方式",
        items=WEIGHT_MODE_ITEMS,
        default="FACE_AREA_WITH_ANGLE",
    )
    keep_sharp: BoolProperty(
        name="シャープエッジを維持",
        default=True,
    )
    apply_modifiers: BoolProperty(
        name="最後にすべてのモディファイアを適用する",
        description=(
            "NormalFix以外も含む全モディファイアを上から順に適用します。"
            "戻す場合はUndoを使用してください"
        ),
        default=True,
    )


def _selected_mesh_objects(context):
    """処理開始時点の選択から、重複のないメッシュを取得する。"""
    result = []
    seen = set()
    for obj in list(context.selected_objects):
        if obj.type != "MESH" or obj.name in seen:
            continue
        if obj.library is not None:
            continue
        seen.add(obj.name)
        result.append(obj)
    return result


def _set_active_only(context, obj):
    for selected in list(context.selected_objects):
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _restore_selection(context, objects, active_object):
    for selected in list(context.selected_objects):
        selected.select_set(False)
    for obj in objects:
        if obj and obj.name in bpy.data.objects:
            obj.select_set(True)
    if active_object and active_object.name in bpy.data.objects:
        context.view_layer.objects.active = active_object
    elif objects:
        context.view_layer.objects.active = objects[0]


def _apply_auto_smooth(mesh, angle):
    """Blender 5方式で全面をスムーズ化し、角度からSharpを設定する。"""
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=float(angle))
    mesh.update()


def _clear_custom_normals(context, obj):
    mesh = obj.data
    if not mesh.has_custom_normals:
        return

    _set_active_only(context, obj)
    result = bpy.ops.mesh.customdata_custom_splitnormals_clear()
    if "FINISHED" not in result:
        raise RuntimeError("カスタム分割法線をクリアできませんでした。")


def _recalculate_face_normals(mesh):
    """接続面の向きから面法線を外向きへ統一する。"""
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        mesh.update()
    finally:
        bm.free()


def _find_weighted_modifier(obj):
    for modifier in obj.modifiers:
        if (
            modifier.type == "WEIGHTED_NORMAL"
            and modifier.name == WEIGHTED_MODIFIER_NAME
        ):
            return modifier
    return None


def _configure_weighted_modifier(obj, settings):
    modifier = _find_weighted_modifier(obj)
    if modifier is None:
        modifier = obj.modifiers.new(
            name=WEIGHTED_MODIFIER_NAME,
            type="WEIGHTED_NORMAL",
        )

    modifier.mode = settings.weight_mode
    modifier.keep_sharp = settings.keep_sharp
    if hasattr(modifier, "thresh"):
        modifier.thresh = 0.01
    return modifier


def _apply_all_modifiers(context, obj):
    """対象オブジェクトの全モディファイアをスタック順に適用する。"""
    _set_active_only(context, obj)
    modifier_names = [modifier.name for modifier in obj.modifiers]
    for modifier_name in modifier_names:
        result = bpy.ops.object.modifier_apply(modifier=modifier_name)
        if "FINISHED" not in result:
            raise RuntimeError(
                "モディファイアを適用できません: {}".format(modifier_name)
            )


class NORMALFIX_OT_apply(Operator):
    bl_idname = "normalfix.apply"
    bl_label = "選択メッシュを補正"
    bl_description = "選択中の全メッシュへ法線補正を適用します"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        settings = context.scene.normalfix_settings
        targets = _selected_mesh_objects(context)
        if not targets:
            self.report({"WARNING"}, "編集可能なメッシュが選択されていません。")
            return {"CANCELLED"}

        original_active = context.view_layer.objects.active
        completed = 0
        errors = []

        for obj in targets:
            try:
                mesh = obj.data

                if settings.use_auto_smooth:
                    _apply_auto_smooth(mesh, settings.smooth_angle)

                if settings.reset_custom_normals:
                    _clear_custom_normals(context, obj)

                if settings.recalculate_outside:
                    _recalculate_face_normals(mesh)

                if settings.use_weighted_normals:
                    _configure_weighted_modifier(obj, settings)

                if settings.apply_modifiers:
                    _apply_all_modifiers(context, obj)

                completed += 1
            except Exception as exc:
                errors.append("{}: {}".format(obj.name, exc))

        _restore_selection(context, targets, original_active)

        if errors:
            self.report(
                {"WARNING"},
                "完了 {} / 失敗 {}。詳細はConsoleを確認してください。".format(
                    completed, len(errors)
                ),
            )
            for error in errors:
                print("NormalFix: " + error)
        else:
            suffix = "・全モディファイア適用済み" if settings.apply_modifiers else ""
            self.report(
                {"INFO"},
                "{}個のメッシュを補正しました{}".format(completed, suffix),
            )

        return {"FINISHED"}


class NORMALFIX_OT_remove(Operator):
    bl_idname = "normalfix.remove"
    bl_label = "Weighted Normalを削除"
    bl_description = "未適用のNormalFix Weighted Normalだけを削除します"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        removed = 0
        for obj in _selected_mesh_objects(context):
            for modifier in list(obj.modifiers):
                if (
                    modifier.type == "WEIGHTED_NORMAL"
                    and modifier.name == WEIGHTED_MODIFIER_NAME
                ):
                    obj.modifiers.remove(modifier)
                    removed += 1
        self.report({"INFO"}, "{}個削除しました。".format(removed))
        return {"FINISHED"}


class NORMALFIX_PT_panel(Panel):
    bl_label = "NormalFix Ver{}".format(TOOL_VERSION)
    bl_idname = "NORMALFIX_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NormalFix"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.normalfix_settings

        layout.label(text="複数メッシュを選択して実行します")

        preset_box = layout.box()
        preset_box.label(text="プリセット")
        preset_box.prop(settings, "preset", text="")

        process_box = layout.box()
        process_box.label(text="補正工程")
        process_box.prop(settings, "use_auto_smooth")
        angle_row = process_box.row()
        angle_row.enabled = settings.use_auto_smooth
        angle_row.prop(settings, "smooth_angle")
        process_box.prop(settings, "reset_custom_normals")
        process_box.prop(settings, "recalculate_outside")
        process_box.prop(settings, "use_weighted_normals")

        weighted_column = process_box.column()
        weighted_column.enabled = settings.use_weighted_normals
        weighted_column.prop(settings, "weight_mode")
        weighted_column.prop(settings, "keep_sharp")

        process_box.separator()
        process_box.prop(settings, "apply_modifiers")
        if settings.apply_modifiers:
            warning = process_box.column(align=True)
            warning.alert = True
            warning.label(text="既存モディファイアもすべて適用されます")
            warning.label(text="戻す場合はUndoを使用してください")

        layout.separator()
        apply_button = layout.row()
        apply_button.scale_y = 1.5
        apply_button.operator("normalfix.apply", icon="CHECKMARK")
        layout.operator("normalfix.remove", icon="X")


CLASSES = (
    NORMALFIX_PG_settings,
    NORMALFIX_OT_apply,
    NORMALFIX_OT_remove,
    NORMALFIX_PT_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.normalfix_settings = PointerProperty(
        type=NORMALFIX_PG_settings
    )


def unregister():
    if hasattr(bpy.types.Scene, "normalfix_settings"):
        del bpy.types.Scene.normalfix_settings
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
