bl_info = {
    "name": "UI Layout Preset Manager",
    "author": "Claude",
    "version": (0, 14, 0),
    "blender": (4, 0, 0),
    "location": "3Dビューポート > サイドバー(Nパネル) > UIプリセット",
    "description": "レイアウト(.blend方式)とアドオン有効化状態(JSON方式)をプリセットとして記憶/削除/名前変更/切替。どちらもファイルをまたいで保持されます",
    "category": "Interface",
}

import bpy
import os
import json
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy.props import StringProperty, IntProperty, CollectionProperty
from bpy.app.handlers import persistent

# このアドオン自身のモジュール名(アドオンプリセット復元時に自分自身を無効化しないためのガード)
SELF_MODULE = __name__ if __name__ != "__main__" else None

PRESET_SUBDIR = "ui_presets"


def _preset_dir():
    path = ""
    try:
        path = bpy.utils.user_resource('CONFIG', path=PRESET_SUBDIR, create=True)
    except Exception:
        path = ""

    if not path:
        # フォールバック: user_resourceが失敗/空文字を返した場合
        try:
            base = bpy.utils.user_resource('CONFIG', create=True)
        except Exception:
            base = os.path.join(os.path.expanduser("~"), ".blender_ui_presets")
        path = os.path.join(base, PRESET_SUBDIR)

    os.makedirs(path, exist_ok=True)
    return path


UI_PRESETS_ORDER_FILENAME = "ui_presets_order.json"


def _ui_presets_order_path():
    return os.path.join(_preset_dir(), UI_PRESETS_ORDER_FILENAME)


def _load_ui_presets_order():
    path = _ui_presets_order_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_ui_presets_order(order):
    path = _ui_presets_order_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _next_available_ui_preset_name(base="設定"):
    order = _load_ui_presets_order()
    existing = set(order)
    try:
        existing |= set(f[:-6] for f in os.listdir(_preset_dir()) if f.endswith(".blend"))
    except Exception:
        pass
    n = 1
    while f"{base}{n}" in existing:
        n += 1
    return f"{base}{n}"


def _sync_preset_list(scene):
    """順序JSON + ディスク上の.blend一覧をもとに scene.ui_presets を再構築する(順序を保持)"""
    try:
        preset_dir = _preset_dir()
        disk_names = set(
            f[:-6] for f in os.listdir(preset_dir) if f.endswith(".blend")
        )
    except Exception:
        disk_names = set()

    order = _load_ui_presets_order()
    order = [n for n in order if n in disk_names]  # 実体が無いものは除外

    known = set(order)
    for name in sorted(disk_names - known):  # 順序に無い(外部追加された)ものは末尾に
        order.append(name)

    _save_ui_presets_order(order)

    coll = scene.ui_presets
    coll.clear()
    for name in order:
        item = coll.add()
        item.name = name

    if scene.ui_preset_index >= len(coll):
        scene.ui_preset_index = max(0, len(coll) - 1)


ADDON_PRESETS_FILENAME = "addon_presets.json"


def _addon_presets_path():
    return os.path.join(_preset_dir(), ADDON_PRESETS_FILENAME)


def _load_addon_presets_data():
    path = _addon_presets_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_addon_presets_data(data):
    path = _addon_presets_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _sync_addon_preset_list(scene):
    """JSONファイル(ui_presetsフォルダ内)を正として scene.addon_presets を再構築する"""
    data = _load_addon_presets_data()
    coll = scene.addon_presets
    coll.clear()
    for entry in data:
        item = coll.add()
        item.name = entry.get("name", "Addon Preset")
        item.addon_data = json.dumps(entry.get("modules", []))

    if scene.addon_preset_index >= len(coll):
        scene.addon_preset_index = max(0, len(coll) - 1)


@persistent
def _on_load_post(dummy):
    for scene in bpy.data.scenes:
        try:
            _sync_preset_list(scene)
        except Exception:
            pass
        try:
            _sync_addon_preset_list(scene)
        except Exception:
            pass


# ----------------------------------------------------------------------
# データ構造: レイアウトプリセット一覧(表示用。実体はディスク上の.blend)
# ----------------------------------------------------------------------

class UIPresetItem(PropertyGroup):
    name: StringProperty(name="名前", default="Preset")


# ----------------------------------------------------------------------
# オペレーター: レイアウトプリセット(.blendファイル方式)
# ----------------------------------------------------------------------

class UIPRESET_OT_refresh(Operator):
    bl_idname = "uipreset.refresh"
    bl_label = "更新"
    bl_description = "保存フォルダの内容とリストを同期します"

    def execute(self, context):
        _sync_preset_list(context.scene)
        return {'FINISHED'}


class UIPRESET_OT_save_blend(Operator):
    bl_idname = "uipreset.save_blend"
    bl_label = "現在の状態を記憶"
    bl_description = "現在のファイルの状態を新しいテンプレートとして保存します(現在編集中のファイルには影響しません)"

    preset_name: StringProperty(name="名前", default="設定1")

    def invoke(self, context, event):
        self.preset_name = _next_available_ui_preset_name()
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.preset_name.strip()
        if not name:
            self.report({'WARNING'}, "名前を入力してください")
            return {'CANCELLED'}

        order = _load_ui_presets_order()
        try:
            disk_existing = set(
                f[:-6] for f in os.listdir(_preset_dir()) if f.endswith(".blend")
            )
        except Exception:
            disk_existing = set()
        existing_all = set(order) | disk_existing

        renamed = False
        if name in existing_all:
            n = 2
            candidate = f"{name}_{n}"
            while candidate in existing_all:
                n += 1
                candidate = f"{name}_{n}"
            name = candidate
            renamed = True

        filepath = os.path.join(_preset_dir(), name + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True)

        order.append(name)
        _save_ui_presets_order(order)

        scene = context.scene
        _sync_preset_list(scene)
        for i, item in enumerate(scene.ui_presets):
            if item.name == name:
                scene.ui_preset_index = i
                break

        if renamed:
            self.report({'INFO'}, f"名前が重複していたため '{name}' として保存しました")
        else:
            self.report({'INFO'}, f"'{name}' を保存しました")
        return {'FINISHED'}


class UIPRESET_OT_delete_blend(Operator):
    bl_idname = "uipreset.delete_blend"
    bl_label = "削除"
    bl_description = "選択中のプリセットファイルを削除します"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        idx = scene.ui_preset_index
        if not (0 <= idx < len(scene.ui_presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}

        name = scene.ui_presets[idx].name
        filepath = os.path.join(_preset_dir(), name + ".blend")
        try:
            os.remove(filepath)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        order = _load_ui_presets_order()
        if name in order:
            order.remove(name)
        _save_ui_presets_order(order)

        _sync_preset_list(scene)
        self.report({'INFO'}, f"'{name}' を削除しました")
        return {'FINISHED'}


class UIPRESET_OT_rename_blend(Operator):
    bl_idname = "uipreset.rename_blend"
    bl_label = "名前を変更"
    bl_description = "選択中のプリセットの名前を変更します"

    new_name: StringProperty(name="新しい名前")

    def invoke(self, context, event):
        scene = context.scene
        idx = scene.ui_preset_index
        if not (0 <= idx < len(scene.ui_presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}
        self.new_name = scene.ui_presets[idx].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        idx = scene.ui_preset_index
        if not (0 <= idx < len(scene.ui_presets)):
            return {'CANCELLED'}

        old_name = scene.ui_presets[idx].name
        new_name = self.new_name.strip()
        if not new_name or new_name == old_name:
            return {'FINISHED'}

        old_path = os.path.join(_preset_dir(), old_name + ".blend")
        new_path = os.path.join(_preset_dir(), new_name + ".blend")

        if os.path.exists(new_path):
            self.report({'WARNING'}, "同じ名前のプリセットが既にあります")
            return {'CANCELLED'}

        try:
            os.rename(old_path, new_path)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        order = _load_ui_presets_order()
        if old_name in order:
            order[order.index(old_name)] = new_name
        else:
            order.append(new_name)
        _save_ui_presets_order(order)

        _sync_preset_list(scene)
        for i, item in enumerate(scene.ui_presets):
            if item.name == new_name:
                scene.ui_preset_index = i
                break

        self.report({'INFO'}, f"'{old_name}' を '{new_name}' に変更しました")
        return {'FINISHED'}


class UIPRESET_OT_load_blend(Operator):
    bl_idname = "uipreset.load_blend"
    bl_label = "この状態に戻す"
    bl_description = "選択中の状態に切り替えます(現在のシーンデータは破棄されます)"

    def execute(self, context):
        scene = context.scene
        idx = scene.ui_preset_index
        if not (0 <= idx < len(scene.ui_presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}

        name = scene.ui_presets[idx].name
        filepath = os.path.join(_preset_dir(), name + ".blend")
        if not os.path.exists(filepath):
            self.report({'ERROR'}, "ファイルが見つかりません")
            return {'CANCELLED'}

        bpy.ops.wm.read_homefile(filepath=filepath, load_ui=True)
        return {'FINISHED'}


# ----------------------------------------------------------------------
# データ構造 / オペレーター: アドオン有効化プリセット(従来通りシーン内蔵)
# ----------------------------------------------------------------------

class AddonPresetItem(PropertyGroup):
    name: StringProperty(name="名前", default="Addon Preset")
    addon_data: StringProperty(default="[]")  # JSON文字列(有効モジュール名リスト)


class ADDONPRESET_OT_save(Operator):
    bl_idname = "addonpreset.save"
    bl_label = "現在の有効化状態を記憶"
    bl_description = "現在有効なアドオンの一覧を新規プリセットとして保存"

    def execute(self, context):
        enabled = sorted(context.preferences.addons.keys())
        data = _load_addon_presets_data()
        existing_names = set(d.get("name", "") for d in data)

        n = len(data) + 1
        name = f"Addon Preset {n}"
        while name in existing_names:
            n += 1
            name = f"Addon Preset {n}"

        data.append({"name": name, "modules": enabled})
        _save_addon_presets_data(data)

        scene = context.scene
        _sync_addon_preset_list(scene)
        for i, item in enumerate(scene.addon_presets):
            if item.name == name:
                scene.addon_preset_index = i
                break

        self.report({'INFO'}, f"'{name}' を保存しました({len(enabled)}件)")
        return {'FINISHED'}


class ADDONPRESET_OT_delete(Operator):
    bl_idname = "addonpreset.delete"
    bl_label = "削除"
    bl_description = "選択中のアドオンプリセットを削除"

    def execute(self, context):
        scene = context.scene
        idx = scene.addon_preset_index
        presets = scene.addon_presets
        if not (0 <= idx < len(presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}

        target_name = presets[idx].name
        data = _load_addon_presets_data()
        data = [d for d in data if d.get("name") != target_name]
        _save_addon_presets_data(data)

        _sync_addon_preset_list(scene)
        return {'FINISHED'}


class ADDONPRESET_OT_rename(Operator):
    bl_idname = "addonpreset.rename"
    bl_label = "名前を変更"
    bl_description = "選択中のアドオンプリセットの名前を変更します"

    new_name: StringProperty(name="新しい名前")

    def invoke(self, context, event):
        scene = context.scene
        idx = scene.addon_preset_index
        if not (0 <= idx < len(scene.addon_presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}
        self.new_name = scene.addon_presets[idx].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        idx = scene.addon_preset_index
        if not (0 <= idx < len(scene.addon_presets)):
            return {'CANCELLED'}

        old_name = scene.addon_presets[idx].name
        new_name = self.new_name.strip()
        if not new_name or new_name == old_name:
            return {'FINISHED'}

        data = _load_addon_presets_data()
        if any(d.get("name") == new_name for d in data):
            self.report({'WARNING'}, "同じ名前のプリセットが既にあります")
            return {'CANCELLED'}

        for d in data:
            if d.get("name") == old_name:
                d["name"] = new_name
                break
        _save_addon_presets_data(data)

        _sync_addon_preset_list(scene)
        for i, item in enumerate(scene.addon_presets):
            if item.name == new_name:
                scene.addon_preset_index = i
                break

        self.report({'INFO'}, f"'{old_name}' を '{new_name}' に変更しました")
        return {'FINISHED'}


class ADDONPRESET_OT_restore(Operator):
    bl_idname = "addonpreset.restore"
    bl_label = "この状態に戻す"
    bl_description = "選択中のプリセットの有効化状態に完全一致させる(記憶していないアドオンは無効化されます)"

    def execute(self, context):
        scene = context.scene
        idx = scene.addon_preset_index
        presets = scene.addon_presets
        if not (0 <= idx < len(presets)):
            self.report({'WARNING'}, "プリセットが選択されていません")
            return {'CANCELLED'}

        try:
            target_list = json.loads(presets[idx].addon_data)
        except Exception:
            self.report({'ERROR'}, "プリセットデータが壊れています")
            return {'CANCELLED'}

        target_set = set(target_list)
        current_set = set(context.preferences.addons.keys())

        to_enable = target_set - current_set
        to_disable = current_set - target_set
        if SELF_MODULE:
            to_disable.discard(SELF_MODULE)  # 自分自身は無効化しない

        failed = []

        for module in sorted(to_enable):
            try:
                bpy.ops.preferences.addon_enable(module=module)
            except Exception:
                failed.append(f"有効化失敗: {module}")

        for module in sorted(to_disable):
            try:
                bpy.ops.preferences.addon_disable(module=module)
            except Exception:
                failed.append(f"無効化失敗: {module}")

        if failed:
            self.report({'WARNING'}, " / ".join(failed))
        else:
            self.report({'INFO'}, f"'{presets[idx].name}' の状態に復元しました")

        return {'FINISHED'}


# ----------------------------------------------------------------------
# UIリスト
# ----------------------------------------------------------------------

class UIPRESET_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='FILE_BLEND')


class ADDONPRESET_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='PLUGIN')


# ----------------------------------------------------------------------
# パネル
# ----------------------------------------------------------------------

class UIPRESET_PT_panel(Panel):
    bl_label = "UIプリセット"
    bl_idname = "UIPRESET_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Upri"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        try:
            row_header = layout.row(align=True)
            row_header.label(text="")
            row_header.operator("uipreset.refresh", icon='FILE_REFRESH', text="更新")

            layout.template_list(
                "UIPRESET_UL_list", "", scene, "ui_presets",
                scene, "ui_preset_index", rows=4
            )

            row = layout.row(align=True)
            row.operator("uipreset.save_blend", icon='ADD', text="記憶")
            row.operator("uipreset.delete_blend", icon='REMOVE', text="削除")
            row.operator("uipreset.rename_blend", icon='GREASEPENCIL', text="")

            layout.operator("uipreset.load_blend", icon='LOOP_BACK', text="この状態に戻す")
            layout.label(text="※切替時は現在のシーンが破棄されます", icon='INFO')
        except Exception as e:
            layout.label(text="エラーが発生しました:", icon='ERROR')
            layout.label(text=str(e))


class ADDONPRESET_PT_panel(Panel):
    bl_label = "アドオン有効化プリセット"
    bl_idname = "ADDONPRESET_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Upri"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.template_list(
            "ADDONPRESET_UL_list", "", scene, "addon_presets",
            scene, "addon_preset_index", rows=4
        )

        row = layout.row(align=True)
        row.operator("addonpreset.save", icon='ADD', text="記憶")
        row.operator("addonpreset.delete", icon='REMOVE', text="削除")
        row.operator("addonpreset.rename", icon='GREASEPENCIL', text="")

        layout.operator("addonpreset.restore", icon='LOOP_BACK', text="この状態に戻す")
        layout.label(text="※記憶していないアドオンは無効化されます", icon='INFO')


# ----------------------------------------------------------------------
# 登録
# ----------------------------------------------------------------------

classes = (
    UIPresetItem,
    UIPRESET_OT_refresh,
    UIPRESET_OT_save_blend,
    UIPRESET_OT_delete_blend,
    UIPRESET_OT_rename_blend,
    UIPRESET_OT_load_blend,
    AddonPresetItem,
    ADDONPRESET_OT_save,
    ADDONPRESET_OT_delete,
    ADDONPRESET_OT_rename,
    ADDONPRESET_OT_restore,
    UIPRESET_UL_list,
    ADDONPRESET_UL_list,
    UIPRESET_PT_panel,
    ADDONPRESET_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ui_presets = CollectionProperty(type=UIPresetItem)
    bpy.types.Scene.ui_preset_index = IntProperty(default=0)
    bpy.types.Scene.addon_presets = CollectionProperty(type=AddonPresetItem)
    bpy.types.Scene.addon_preset_index = IntProperty(default=0)

    bpy.app.handlers.load_post.append(_on_load_post)

    # アドオン有効化直後の初期同期(失敗しても致命的ではないので握りつぶす)
    try:
        for scene in bpy.data.scenes:
            _sync_preset_list(scene)
            _sync_addon_preset_list(scene)
    except Exception:
        pass


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    del bpy.types.Scene.addon_preset_index
    del bpy.types.Scene.addon_presets
    del bpy.types.Scene.ui_preset_index
    del bpy.types.Scene.ui_presets
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
