import bpy
import configparser
import os

# プラグインに関する情報
bl_info = {
    "name": "OBJ_FBX_ImpExp",  		# プラグイン名
    "author": "DigiMonkey",    		# 作者
    "version": (0, 5),         		# バージョン
    "blender": (4, 0, 0),      		# 対応するBlenderバージョン
    "location": "System",      		# プラグインの位置
    "description": "OBJ FBX Imp Exp",  	# 説明
    "category": "System"       		# カテゴリ
}

# 全DCC共通の設定ファイル(Max/Maya/ZBrushと共有)
INI_PATH = "C:/Temp/ImpExp.ini"

DEFAULTS = {
    "folder": "C:/Temp/",
    "obj_name": "model.obj",
    "fbx_name": "model.fbx",
}

# INIを読み込む（無ければデフォルトで新規作成）
def read_ini():
    cfg = configparser.ConfigParser()
    if not os.path.exists(INI_PATH):
        write_ini(DEFAULTS["folder"], DEFAULTS["obj_name"], DEFAULTS["fbx_name"])
        return dict(DEFAULTS)
    cfg.read(INI_PATH)
    if "Path" not in cfg:
        write_ini(DEFAULTS["folder"], DEFAULTS["obj_name"], DEFAULTS["fbx_name"])
        return dict(DEFAULTS)
    return {
        "folder": cfg["Path"].get("folder", DEFAULTS["folder"]),
        "obj_name": cfg["Path"].get("obj_name", DEFAULTS["obj_name"]),
        "fbx_name": cfg["Path"].get("fbx_name", DEFAULTS["fbx_name"]),
    }

# INIに書き込む
def write_ini(folder, obj_name, fbx_name):
    os.makedirs(os.path.dirname(INI_PATH), exist_ok=True)
    cfg = configparser.ConfigParser()
    cfg["Path"] = {
        "folder": folder,
        "obj_name": obj_name,
        "fbx_name": fbx_name,
    }
    with open(INI_PATH, "w") as f:
        cfg.write(f)

def get_obj_path():
    s = read_ini()
    return s["folder"] + s["obj_name"]

def get_fbx_path():
    s = read_ini()
    return s["folder"] + s["fbx_name"]

# 設定変更時にiniへ書き込むコールバック
def update_ini_from_props(self, context):
    write_ini(self.save_folder, self.obj_name, self.fbx_name)

# アドオン設定(保存先ディレクトリ・ファイル名)
class OBJFBXIMPEXP_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    save_folder: bpy.props.StringProperty(
        name="保存先ディレクトリ",
        description="OBJ/FBXの読み込み・書き出し先のフォルダ（Max/Maya/ZBrushと共有）",
        subtype='DIR_PATH',
        default=DEFAULTS["folder"],
        update=update_ini_from_props
    )
    obj_name: bpy.props.StringProperty(
        name="OBJファイル名",
        description="OBJの読み込み・書き出しに使うファイル名",
        default=DEFAULTS["obj_name"],
        update=update_ini_from_props
    )
    fbx_name: bpy.props.StringProperty(
        name="FBXファイル名",
        description="FBXの読み込み・書き出しに使うファイル名",
        default=DEFAULTS["fbx_name"],
        update=update_ini_from_props
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="この設定は C:/Temp/ImpExp.ini に保存され、Max/Maya/ZBrushと共有されます")
        layout.prop(self, "save_folder")
        layout.prop(self, "obj_name")
        layout.prop(self, "fbx_name")

# アドオン起動時にiniの現在値をUIへ反映
def sync_prefs_from_ini():
    try:
        prefs = bpy.context.preferences.addons[__name__].preferences
    except (KeyError, AttributeError):
        return
    s = read_ini()
    prefs.save_folder = s["folder"]
    prefs.obj_name = s["obj_name"]
    prefs.fbx_name = s["fbx_name"]

# UI設定
class MY_PT_ui(bpy.types.Panel):
    bl_label = "OBJ FBX Imp Exp"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ObjFbx"

    def draw(self, context):
        layout = self.layout
        layout.operator("my.button1", text="OBJ Import")
        layout.operator("my.button2", text="OBJ Export")
        layout.operator("my.button3", text="FBX Import")
        layout.operator("my.button4", text="FBX Export")

# OBJのインポート
class MyButton1(bpy.types.Operator):
    bl_label = "OBJ Import"
    bl_idname = "my.button1"
    bl_description = "OBJファイルをインポートします"  # ボタンの説明

    def execute(self, context):
        bpy.ops.wm.obj_import(filepath=get_obj_path())
        print("OBJファイルを読み込みました")
        return {'FINISHED'}

# OBJのエクスポート（選択したオブジェクトのみ）
class MyButton2(bpy.types.Operator):
    bl_label = "OBJ Export"
    bl_idname = "my.button2"
    bl_description = "選択したオブジェクトをOBJファイルとしてエクスポートします"  # ボタンの説明

    def execute(self, context):
        bpy.ops.wm.obj_export(filepath=get_obj_path(), export_selected_objects=True)
        print("OBJファイルを書き出しました")
        return {'FINISHED'}

# FBXのインポート
class MyButton3(bpy.types.Operator):
    bl_label = "FBX Import"
    bl_idname = "my.button3"
    bl_description = "FBXファイルをインポートします"  # ボタンの説明

    def execute(self, context):
        bpy.ops.import_scene.fbx(filepath=get_fbx_path())
        print("FBXファイルを読み込みました")
        return {'FINISHED'}

# FBXのエクスポート（選択したオブジェクトのみ）
class MyButton4(bpy.types.Operator):
    bl_label = "FBX Export"
    bl_idname = "my.button4"
    bl_description = "選択したオブジェクトをFBXファイルとしてエクスポートします"  # ボタンの説明

    def execute(self, context):
        bpy.ops.export_scene.fbx(filepath=get_fbx_path(), use_selection=True)
        print("FBXファイルを書き出しました")
        return {'FINISHED'}

# クラス登録
classes = (
    OBJFBXIMPEXP_AddonPreferences,
    MY_PT_ui,
    MyButton1,
    MyButton2,
    MyButton3,
    MyButton4
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    read_ini()  # 無ければここでC:/Temp/ImpExp.iniを作成
    sync_prefs_from_ini()

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
