bl_info = {
    "name": "Tab Manager",
    "author": "DiGiMonkey",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "Preferences > Add-ons > Tab Manager",
    "description": "Organize N-panel (sidebar) tabs into folders",
    "category": "Interface",
}

import bpy
import json
import os
import sys
from collections import defaultdict
from bpy.types import AddonPreferences, PropertyGroup, Operator, Menu
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    EnumProperty,
)

# ---------------------------------------------------------------------------
# 翻訳(i18n)
# ---------------------------------------------------------------------------
# bl_label / bl_description / プロパティの name・description は、
# 翻訳辞書さえ登録しておけばBlenderが自動で表示を切り替えてくれる
# (Blenderの「言語」設定 + 「インターフェースを翻訳」がONの場合)。
# f-stringなどで組み立てる動的なテキスト(件数・パス等を埋め込むもの)は
# 自動翻訳の対象にならないため、_tr() で先にテンプレート部分だけ翻訳してから
# 値を埋め込むようにしている。
try:
    _CTXT_DEFAULT = bpy.app.translations.contexts.default
    _CTXT_OPERATOR = bpy.app.translations.contexts.operator_default
except Exception:
    _CTXT_DEFAULT = '*'
    _CTXT_OPERATOR = 'Operator'


def _tr(text):
    """動的に組み立てる文字列のテンプレート部分を翻訳する。
    固定文字列(bl_label/bl_descriptionやプロパティ名など)はBlenderが
    自動で翻訳するため、ここを通す必要はない。"""
    try:
        return bpy.app.translations.pgettext_iface(text, _CTXT_DEFAULT)
    except Exception:
        return text


TRANSLATIONS_EN_US = {
    # --- オペレーター ---
    (_CTXT_OPERATOR, "スキャン"): "Scan",
    (_CTXT_OPERATOR, "現在有効なアドオンのタブを再スキャンします"): "Rescan tabs from currently enabled add-ons",
    (_CTXT_OPERATOR, "適用"): "Apply",
    (_CTXT_OPERATOR, "フォルダの内容・並び順を実際のNパネルへ反映します"): "Apply folder contents and order to the actual N-panel",
    (_CTXT_OPERATOR, "すべて元に戻す"): "Reset All",
    (_CTXT_OPERATOR, "全てのタブをフォルダから出し、元のタブ名に戻します"): "Remove all tabs from folders and restore their original tab names",
    (_CTXT_OPERATOR, "フォルダを追加"): "Add Folder",
    (_CTXT_OPERATOR, "新しいフォルダ（＝Nパネルの新しいタブ）を作成します"): "Create a new folder (a new N-panel tab)",
    (_CTXT_OPERATOR, "新しいフォルダを作って入れる"): "Create New Folder and File Here",
    (_CTXT_OPERATOR, "新しいフォルダを作成し、このタブをそのフォルダに入れます"): "Create a new folder and file this tab into it",
    (_CTXT_OPERATOR, "フォルダを削除"): "Delete Folder",
    (_CTXT_OPERATOR, "フォルダを削除します（中の項目は未整理に戻ります。項目自体は消えません）"): "Delete this folder (its contents return to Unfiled; nothing is deleted)",
    (_CTXT_OPERATOR, "フォルダを並び替え"): "Reorder Folder",
    (_CTXT_OPERATOR, "フォルダの順序を入れ替えます（＝Nパネルのタブの並び順）"): "Change the folder order (the N-panel tab order)",
    (_CTXT_OPERATOR, "フォルダの中身を開閉します"): "Expand or collapse this folder",
    (_CTXT_OPERATOR, "このタブをフォルダから出します（未整理に戻します）"): "Remove this tab from its folder (back to Unfiled)",
    (_CTXT_OPERATOR, "フォルダへ入れる"): "File Into Folder",
    (_CTXT_OPERATOR, "このタブを入れるフォルダを選びます"): "Choose which folder to file this tab into",
    (_CTXT_OPERATOR, "プリセットを保存"): "Save Preset",
    (_CTXT_OPERATOR, "現在のフォルダ構成をJSONファイルに保存します"): "Save the current folder layout to a JSON file",
    (_CTXT_OPERATOR, "プリセットを読み込み"): "Load Preset",
    (_CTXT_OPERATOR, "JSONファイルからフォルダ構成を読み込んで適用します"): "Load and apply a folder layout from a JSON file",

    # --- メニュー / 静的ラベル(オペレーター以外) ---
    (_CTXT_DEFAULT, "フォルダへ入れる"): "File Into Folder",
    (_CTXT_DEFAULT, "フォルダがまだありません"): "No folders yet",
    (_CTXT_DEFAULT, "＋ 新しいフォルダを作って入れる"): "+ Create New Folder and File Here",
    # ↑ layout.operator()のtext上書きはBlenderが"Operator"文脈で探すため、
    #   念のためこちらにも同じ翻訳を登録しておく(v9で追加)
    (_CTXT_OPERATOR, "＋ 新しいフォルダを作って入れる"): "+ Create New Folder and File Here",

    # --- プロパティ名・説明 ---
    (_CTXT_DEFAULT, "フォルダ名"): "Folder Name",
    (_CTXT_DEFAULT, "ID"): "ID",
    (_CTXT_DEFAULT, "タブ名"): "Tab Name",
    (_CTXT_DEFAULT, "元のタブ名"): "Original Tab Name",
    (_CTXT_DEFAULT, "所属アドオン"): "Add-on Module",
    (_CTXT_DEFAULT, "内包パネル"): "Member Panels",
    (_CTXT_DEFAULT, "内包パネル数"): "Member Panel Count",
    (_CTXT_DEFAULT, "フォルダID"): "Folder ID",
    (_CTXT_DEFAULT,
     "同じタブ名を複数の別々のアドオンが使っている可能性があります"
     "（除外はしません。念のための注意表示です）"):
        "This tab name may be shared by multiple unrelated add-ons "
        "(not excluded automatically \u2014 shown as a precaution)",
    (_CTXT_DEFAULT, "起動時の適用待機時間(秒)"): "Apply Delay on Startup (seconds)",
    (_CTXT_DEFAULT, "他のアドオンの読み込みが終わるのを待ってから設定を再適用します"):
        "Wait this long for other add-ons to finish loading before reapplying settings",
    (_CTXT_DEFAULT, "基本タブは無視する"): "Ignore Basic Tabs",
    (_CTXT_DEFAULT,
     "Blender標準タブ(Item/Tool/View/Animationなど)と、複数の無関係なアドオンが"
     "共有している汎用タブ(プリセット一覧など)を管理対象から外し、"
     "そのアドオン固有のタブだけを一覧に表示します"):
        "Excludes Blender's built-in tabs (Item/Tool/View/Animation, etc.) and generic tabs "
        "shared by multiple unrelated add-ons (e.g. preset lists), showing only tabs unique to a single add-on",
    (_CTXT_DEFAULT, "デバッグ情報を表示"): "Show Debug Info",
    (_CTXT_DEFAULT,
     "全てのタブについて、判定に使っている内部情報(モジュール名・"
     "同梱扱いかどうか・ファイルの場所)を表示します。"
     "タブが期待通り表示されない/消える場合の原因調査用です。"):
        "Shows internal detection info for every tab (module name, whether it's treated as "
        "bundled, and its file location). Useful for diagnosing tabs that don't show up as expected.",

    # --- 静的UIラベル ---
    (_CTXT_DEFAULT, "※ Blender標準タブ・Blender同梱アドオン(glTF I/Oなど)は非表示中。設定を変えたら「スキャン」を押し直してください。"):
        "* Blender's built-in tabs and bundled add-ons (e.g. glTF I/O) are hidden. Press \"Scan\" again after changing this setting.",
    (_CTXT_DEFAULT, "デバッグ情報（フィルタを無視して全タブを表示）"): "Debug Info (all tabs, ignoring filters)",
    (_CTXT_DEFAULT, "フォルダ（＝Nパネルのタブ）"): "Folders (= N-panel tabs)",
    (_CTXT_DEFAULT, "＋ フォルダを追加"): "+ Add Folder",
    # ↑ layout.operator()のtext上書きはBlenderが"Operator"文脈で探すため、
    #   前バージョンではここが登録漏れで翻訳されていなかった(v9で修正)
    (_CTXT_OPERATOR, "＋ フォルダを追加"): "+ Add Folder",
    (_CTXT_DEFAULT, "※ 中身が空のフォルダは、適用してもNパネルにタブとして表示されません（Blenderは空のタブを作れないため）。"):
        "* An empty folder will not appear as a tab in the N-panel even after applying (Blender cannot create an empty tab).",
    (_CTXT_DEFAULT, "フォルダがまだありません。下の一覧からタブを選んで追加してください。"):
        "No folders yet. Add one by choosing a tab from the list below.",
    (_CTXT_DEFAULT, "　（空のフォルダ）"): "  (Empty folder)",
    (_CTXT_DEFAULT, "未整理（まだどのフォルダにも入っていないタブ）"): "Unfiled (tabs not yet in any folder)",
    (_CTXT_DEFAULT, "　なし"): "  None",
    (_CTXT_DEFAULT, "※ タブの並び順は「適用」を押した時、フォルダの並び順に沿って管理対象パネル同士の相対順序のみ制御します。"):
        "* Tab order is only controlled, upon \"Apply\", as the relative order among managed panels following the folder order.",
    (_CTXT_DEFAULT, "　反映されない場合はサイドバー(N)を一度閉じて開き直してください。"):
        "  If it isn't reflected, try closing and reopening the sidebar (N).",

    # --- 動的テンプレート(書式化して使うもの。%sや%dはそのまま残す) ---
    (_CTXT_DEFAULT, "%d 件のタブを検出しました"): "Detected %d tab(s)",
    (_CTXT_DEFAULT, "適用しました（変更: %d 件）"): "Applied (%d change(s))",
    (_CTXT_DEFAULT, "保存に失敗しました: %s"): "Failed to save: %s",
    (_CTXT_DEFAULT, "読み込みに失敗しました: %s"): "Failed to load: %s",
    (_CTXT_DEFAULT, "新しいフォルダ%d"): "New Folder %d",
    (_CTXT_DEFAULT, "（%d件のパネル）"): " (%d panels)",
    (_CTXT_DEFAULT, "　⚠共有タブかも"): "  \u26a0 possibly a shared tab",
    (_CTXT_DEFAULT, "　⚠同じタブ名を複数のアドオンが使ってる可能性あり"): "  \u26a0 this tab name may be used by multiple add-ons",
    (_CTXT_DEFAULT, "タブ名『%s』 / パネル: %s (%s)"): "Tab \u201c%s\u201d / Panel: %s (%s)",
    (_CTXT_DEFAULT, "　モジュール: %s　(判定キー: %s)"): "  Module: %s  (detection key: %s)",
    (_CTXT_DEFAULT, "　同梱扱い: %s"): "  Bundled: %s",
    (_CTXT_DEFAULT, "はい（同梱扱い＝非表示対象）"): "Yes (bundled \u2014 hidden)",
    (_CTXT_DEFAULT, "いいえ（ユーザーのタブ扱い）"): "No (treated as your own tab)",
    (_CTXT_DEFAULT, "　ファイルの場所: %s"): "  File location: %s",
    (_CTXT_DEFAULT, "Blenderインストール先(LOCAL): %s"): "Blender install location (LOCAL): %s",
    (_CTXT_DEFAULT, "ユーザーaddonsフォルダ(参考): %s"): "User add-ons folder (reference): %s",
    (_CTXT_DEFAULT, "元に戻しました"): "Reset complete",
    (_CTXT_DEFAULT, "アドオン設定が見つかりません"): "Could not find add-on preferences",
    (_CTXT_DEFAULT, "ファイルが見つかりません"): "File not found",
    (_CTXT_DEFAULT, "プリセットを保存しました"): "Preset saved",
    (_CTXT_DEFAULT, "プリセットを適用しました"): "Preset applied",
    (_CTXT_DEFAULT, "(取得できませんでした)"): "(could not be determined)",

    # --- bl_info ---
    (_CTXT_DEFAULT, "N-panel (サイドバー) のタブをフォルダにまとめて管理できるアドオン"):
        "An add-on that lets you organize N-panel (sidebar) tabs into folders",
}

TRANSLATIONS_DICT = {
    "en_US": TRANSLATIONS_EN_US,
}


# ---------------------------------------------------------------------------
# パネル収集ユーティリティ
# ---------------------------------------------------------------------------

def get_all_subclasses(cls):
    subs = set()
    for c in cls.__subclasses__():
        subs.add(c)
        subs.update(get_all_subclasses(c))
    return subs


def get_raw_eligible_classes():
    """N-panel (VIEW_3D の UI リージョン) にタブを持つ、
    サブパネルではないトップレベルのPanelクラスを全て集める（フィルタ無し）"""
    result = []
    for cls in get_all_subclasses(bpy.types.Panel):
        try:
            if getattr(cls, "bl_space_type", None) != "VIEW_3D":
                continue
            if getattr(cls, "bl_region_type", None) != "UI":
                continue
            if getattr(cls, "bl_parent_id", None):
                continue  # サブパネルは独立したタブを持たない
            if not hasattr(cls, "bl_category"):
                continue
            result.append(cls)
        except Exception:
            continue
    return result


def _get_user_addons_root():
    """ユーザーが自分でアドオンを追加する場所(例:
    C:\\Users\\xxx\\AppData\\Roaming\\Blender Foundation\\Blender\\5.1\\scripts\\addons)を取得する。
    まず専用API(user_resource)で直接 'addons' フォルダを取得し、失敗したら
    resource_path('USER') の基準フォルダにフォールバックする。
    取得できない場合は None を返す（＝判定不能として扱う）。"""
    path = None
    try:
        path = bpy.utils.user_resource('SCRIPTS', path="addons")
    except Exception:
        path = None
    if not path:
        try:
            path = bpy.utils.resource_path('USER')
        except Exception:
            path = None
    if not path:
        return None
    # Windows は "C:" と "c:" のようにドライブレターの大文字小文字が
    # 食い違うことがあるため、比較の際は必ず normcase を通す。
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _get_bundled_root():
    """Blender本体のインストール先（同梱スクリプト・同梱アドオン/拡張機能が
    置かれている場所）を取得する。resource_path('LOCAL') を使う。
    取得できない場合は None を返す。"""
    try:
        path = bpy.utils.resource_path('LOCAL')
    except Exception:
        path = None
    if not path:
        return None
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def get_addon_module_key(module_name):
    """モジュール名から「アドオンを一意に識別する部分」を取り出す。

    通常のレガシーアドオンは module_name の先頭1要素がそのままアドオン名になる
    (例: "nexus_addon.ui" → "nexus_addon")。

    Blender 4.2以降の拡張機能(Extensions)は "bl_ext.<リポジトリ名>.<アドオン名>"
    という3階層の名前空間になっており、先頭1要素("bl_ext")だけを見ると
    全く別のアドオン同士が同じ名前に見えてしまう。そのため bl_ext から
    始まる場合は先頭3要素までをキーとして扱う。"""
    parts = (module_name or "").split(".")
    if not parts or not parts[0]:
        return module_name or ""
    if parts[0] == "bl_ext" and len(parts) >= 3:
        return ".".join(parts[:3])
    return parts[0]


def is_bundled_or_core(cls):
    """Blender本体に最初から入っている（＝ユーザーが自分でインストールしたのではない）
    パネルかどうかを判定する。

    2つの方法を併用する:
    1. bl_ui モジュール配下 → Blender公式のUIスクリプト(Item/Tool/View/Animationなど)
    2. モジュールの実ファイルの場所が、Blenderのインストール先
       (resource_path('LOCAL')) の中にある場合 → glTF I/Oなど、標準同梱の
       アドオン/拡張機能。ユーザーが追加した拡張機能は、レガシーアドオンと同じく
       ユーザーのプロファイル(AppData/Roamingなど)の中に置かれるため、
       この判定には含まれない。

    ※以前のバージョンでは「ユーザーのaddonsフォルダの中にあるか」を基準にしていたが、
      Blender 4.2以降の拡張機能はaddonsフォルダとは別の場所(extensions/user_default等)
      に置かれるため、そちらは正しく「ユーザーのタブ」と判定されない恐れがあった。
      「Blenderのインストール先の中にあるかどうか」を基準にする方が、
      レガシーアドオン・拡張機能のどちらにも対応できる。

    カテゴリ名(タブ名)の文字列比較では判定しない。判定できない場合は
    False（＝除外しない・安全側）を返す。"""
    module_name = getattr(cls, "__module__", "") or ""
    key = get_addon_module_key(module_name)
    if key == "bl_ui":
        return True

    mod = sys.modules.get(key)
    file_path = getattr(mod, "__file__", None) if mod else None
    if not file_path:
        return False  # 場所が分からないものは誤って隠さない

    bundled_root = _get_bundled_root()
    if not bundled_root:
        return False

    file_path = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))
    return file_path.startswith(bundled_root)


def compute_shared_categories(classes):
    """同じタブ名(bl_category)を複数の異なるアドオンが使っている場合、
    それは複数のアドオンが同じ名前を偶然使っている「共有タブ」かもしれない、という
    “注意喚起用”の判定。これに該当しても一覧からは除外しない（誤判定で
    ユーザーが管理したいタブを消してしまうのを避けるため）。UI側で
    ⚠マークを出すためだけに使う。"""
    cat_modules = defaultdict(set)
    for cls in classes:
        cat = getattr(cls, "bl_category", "") or ""
        mod = get_addon_module_key(getattr(cls, "__module__", "") or "")
        cat_modules[cat].add(mod)
    return {cat for cat, mods in cat_modules.items() if len(mods) > 1}


def get_manageable_panel_classes(prefs):
    """現在の設定(ignore_basic_tabs)を反映した、管理対象候補のパネルクラス一覧。
    ignore_basic_tabs が True の場合、Blender標準タブ・Blender同梱アドオンのタブ
    (glTF I/Oなど)を除外する。タブ名が他アドオンと被っているかどうかでは除外しない
    （その場合はUI上に警告表示するのみ）。"""
    raw = get_raw_eligible_classes()
    if prefs.ignore_basic_tabs:
        raw = [c for c in raw if not is_bundled_or_core(c)]
    return raw


def _debug_rows():
    """デバッグ表示用: フィルタを一切かけず、見えている全パネルについて
    判定に使っている内部情報を一覧化する。"""
    raw = get_raw_eligible_classes()
    rows = []
    for cls in raw:
        module_name = getattr(cls, "__module__", "") or ""
        key = get_addon_module_key(module_name)
        mod = sys.modules.get(key)
        file_path = getattr(mod, "__file__", None) if mod else None
        rows.append({
            "category": getattr(cls, "bl_category", "") or "",
            "label": getattr(cls, "bl_label", cls.__name__),
            "idname": panel_idname(cls),
            "module_full": module_name,
            "module_key": key,
            "bundled": is_bundled_or_core(cls),
            "file_path": file_path or "(不明)",
        })
    rows.sort(key=lambda r: (r["category"], r["label"]))
    return rows


def panel_idname(cls):
    return getattr(cls, "bl_idname", None) or cls.__name__


def get_prefs():
    addon = bpy.context.preferences.addons.get(__name__)
    if addon is None:
        return None
    return addon.preferences


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

class TABMGR_Folder(PropertyGroup):
    uid: StringProperty(name="ID")
    name: StringProperty(name="フォルダ名", default="新しいフォルダ")
    expanded: BoolProperty(default=True)



class TABMGR_PanelItem(PropertyGroup):
    """1行 = 1つの「既存のタブ(bl_category)」を表す。
    同じタブ名を複数のパネルが共有している場合(=Blender上で既に1つのタブに
    まとまっている場合)も、ここでは1行にまとめる。member_idnames に
    実際に含まれるパネルのidnameを ';' 区切りで保持する。"""
    idname: StringProperty(name="ID")  # = 元のタブ名(category)そのもの。一意キー
    label: StringProperty(name="タブ名")
    original_category: StringProperty(name="元のタブ名")
    category: StringProperty(name="タブ名")
    module: StringProperty(name="所属アドオン")
    member_idnames: StringProperty(name="内包パネル", default="")  # ";" 区切り
    member_count: IntProperty(name="内包パネル数", default=0)
    folder_uid: StringProperty(name="フォルダID", default="")  # "" = 未整理
    missing: BoolProperty(default=False)
    shared_warning: BoolProperty(
        default=False,
        description="同じタブ名を複数の別々のアドオンが使っている可能性があります"
                    "（除外はしません。念のための注意表示です）",
    )


# ---------------------------------------------------------------------------
# フォルダ操作ヘルパー
# ---------------------------------------------------------------------------

def create_folder(prefs, name=None):
    prefs.folder_counter += 1
    f = prefs.folders.add()
    f.uid = f"f{prefs.folder_counter}"
    f.name = name or (_tr("新しいフォルダ%d") % len(prefs.folders))
    f.expanded = True
    return f


# ---------------------------------------------------------------------------
# スキャン / 適用 ロジック
# ---------------------------------------------------------------------------

def do_scan(prefs):
    """現在の設定でパネルを再スキャンし、prefs.items を更新する。
    同じタブ名(bl_category)を持つ複数パネルは1つのタブとしてまとめる。
    フォルダに入れてある項目は、条件から外れても(missing表示のまま)消さない。
    未整理のまま見つからなくなった項目は一覧から取り除く。"""
    classes = get_manageable_panel_classes(prefs)

    groups = defaultdict(list)
    for cls in classes:
        cat = getattr(cls, "bl_category", "") or ""
        groups[cat].append(cls)

    existing = {item.idname: item for item in prefs.items}
    found_keys = set()

    for cat, group_classes in groups.items():
        found_keys.add(cat)
        modules = sorted({(getattr(c, "__module__", "") or "").split(".")[0] for c in group_classes})
        member_ids = [panel_idname(c) for c in group_classes]
        warn = len(modules) > 1

        if cat in existing:
            item = existing[cat]
            item.label = cat
            item.module = ", ".join(modules)
            item.member_idnames = ";".join(member_ids)
            item.member_count = len(member_ids)
            item.missing = False
            item.shared_warning = warn
            if not item.original_category:
                item.original_category = cat
        else:
            item = prefs.items.add()
            item.idname = cat
            item.label = cat
            item.original_category = cat
            item.category = cat
            item.module = ", ".join(modules)
            item.member_idnames = ";".join(member_ids)
            item.member_count = len(member_ids)
            item.folder_uid = ""
            item.missing = False
            item.shared_warning = warn

    remove_indices = []
    for i, item in enumerate(prefs.items):
        if item.idname in found_keys:
            continue
        if item.folder_uid:
            item.missing = True
        else:
            remove_indices.append(i)
    for i in reversed(remove_indices):
        prefs.items.remove(i)


def apply_settings(prefs):
    """フォルダの並び順と、フォルダに入れられたタブのタブ名を実際のパネルへ反映する。
    1つのタブに複数パネルが含まれる場合は全メンバーをまとめて移動する。
    フォルダから出された(未整理に戻った)タブは、元のタブ名に戻す
    （フォルダを削除した後も「適用」を押せば確実に反映されるようにするため）。"""
    raw = get_raw_eligible_classes()
    by_id = {panel_idname(c): c for c in raw}

    targets = []  # (item, cls, target_category)

    # 1) フォルダに入れられているタブ → フォルダ名へ
    for folder in prefs.folders:
        for item in prefs.items:
            if item.folder_uid != folder.uid or item.missing:
                continue
            member_ids = [m for m in item.member_idnames.split(";") if m]
            for mid in member_ids:
                cls = by_id.get(mid)
                if cls is None:
                    continue
                targets.append((item, cls, folder.name))

    # 2) 未整理(=どのフォルダにも入っていない)タブ → 元のタブ名に戻す
    #    フォルダ削除・「フォルダから出す」操作をした後、まだ実際のパネルには
    #    フォルダ名が残ったままになっているケースをここで解消する。
    for item in prefs.items:
        if item.folder_uid or item.missing:
            continue
        member_ids = [m for m in item.member_idnames.split(";") if m]
        for mid in member_ids:
            cls = by_id.get(mid)
            if cls is None:
                continue
            if getattr(cls, "bl_category", "") != item.original_category:
                targets.append((item, cls, item.original_category))

    if not targets:
        return 0

    changed = 0

    # 1) タブ名(bl_category)をフォルダ名に合わせて再登録
    for item, cls, target_cat in targets:
        if getattr(cls, "bl_category", "") != target_cat:
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            cls.bl_category = target_cat
            try:
                bpy.utils.register_class(cls)
            except Exception:
                pass
            changed += 1

    # 2) フォルダの並び順どおりにタブが並ぶよう、対象パネルを
    #    unregister -> register し直す（管理対象同士の相対順序のみ制御可能）
    for item, cls, _ in targets:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for item, cls, _ in targets:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass

    return changed


def reset_settings(prefs):
    """全タブをフォルダから出し、元のタブ名に戻す（内包パネル全て）"""
    raw = get_raw_eligible_classes()
    by_id = {panel_idname(c): c for c in raw}
    touched = []
    for item in prefs.items:
        item.folder_uid = ""
        member_ids = [m for m in item.member_idnames.split(";") if m]
        for mid in member_ids:
            cls = by_id.get(mid)
            if cls is not None and getattr(cls, "bl_category", "") != item.original_category:
                touched.append((item.original_category, cls))
    for target_cat, cls in touched:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        cls.bl_category = target_cat
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# オペレーター: スキャン / 適用 / リセット
# ---------------------------------------------------------------------------

class TABMGR_OT_scan(Operator):
    bl_idname = "tabmgr.scan"
    bl_label = "スキャン"
    bl_description = "現在有効なアドオンのタブを再スキャンします"

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            self.report({'ERROR'}, _tr("アドオン設定が見つかりません"))
            return {'CANCELLED'}
        do_scan(prefs)
        self.report({'INFO'}, _tr("%d 件のタブを検出しました") % len(prefs.items))
        return {'FINISHED'}


class TABMGR_OT_apply(Operator):
    bl_idname = "tabmgr.apply"
    bl_label = "適用"
    bl_description = "フォルダの内容・並び順を実際のNパネルへ反映します"

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            self.report({'ERROR'}, _tr("アドオン設定が見つかりません"))
            return {'CANCELLED'}
        changed = apply_settings(prefs)
        self.report({'INFO'}, _tr("適用しました（変更: %d 件）") % changed)
        return {'FINISHED'}


class TABMGR_OT_reset(Operator):
    bl_idname = "tabmgr.reset_all"
    bl_label = "すべて元に戻す"
    bl_description = "全てのタブをフォルダから出し、元のタブ名に戻します"

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        reset_settings(prefs)
        self.report({'INFO'}, _tr("元に戻しました"))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# オペレーター: フォルダ操作
# ---------------------------------------------------------------------------

class TABMGR_OT_add_folder(Operator):
    bl_idname = "tabmgr.add_folder"
    bl_label = "フォルダを追加"
    bl_description = "新しいフォルダ（＝Nパネルの新しいタブ）を作成します"

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        create_folder(prefs)
        prefs.active_folder_index = len(prefs.folders) - 1
        return {'FINISHED'}


class TABMGR_OT_add_folder_and_assign(Operator):
    bl_idname = "tabmgr.add_folder_and_assign"
    bl_label = "新しいフォルダを作って入れる"
    bl_description = "新しいフォルダを作成し、このタブをそのフォルダに入れます"
    item_index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        f = create_folder(prefs)
        if 0 <= self.item_index < len(prefs.items):
            prefs.items[self.item_index].folder_uid = f.uid
        prefs.active_folder_index = len(prefs.folders) - 1
        return {'FINISHED'}


class TABMGR_OT_remove_folder(Operator):
    bl_idname = "tabmgr.remove_folder"
    bl_label = "フォルダを削除"
    bl_description = "フォルダを削除します（中の項目は未整理に戻ります。項目自体は消えません）"
    index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None or not (0 <= self.index < len(prefs.folders)):
            return {'CANCELLED'}
        folder = prefs.folders[self.index]
        for item in prefs.items:
            if item.folder_uid == folder.uid:
                item.folder_uid = ""
        prefs.folders.remove(self.index)
        prefs.active_folder_index = min(prefs.active_folder_index, len(prefs.folders) - 1)
        return {'FINISHED'}


class TABMGR_OT_move_folder(Operator):
    bl_idname = "tabmgr.move_folder"
    bl_label = "フォルダを並び替え"
    bl_description = "フォルダの順序を入れ替えます（＝Nパネルのタブの並び順）"
    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        new_index = self.index - 1 if self.direction == 'UP' else self.index + 1
        if 0 <= new_index < len(prefs.folders):
            prefs.folders.move(self.index, new_index)
            prefs.active_folder_index = new_index
        return {'FINISHED'}


class TABMGR_OT_toggle_folder(Operator):
    bl_idname = "tabmgr.toggle_folder"
    bl_label = ""
    bl_description = "フォルダの中身を開閉します"
    index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None or not (0 <= self.index < len(prefs.folders)):
            return {'CANCELLED'}
        prefs.folders[self.index].expanded = not prefs.folders[self.index].expanded
        return {'FINISHED'}


class TABMGR_OT_unfile_item(Operator):
    bl_idname = "tabmgr.unfile_item"
    bl_label = ""
    bl_description = "このタブをフォルダから出します（未整理に戻します）"
    item_index: IntProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None or not (0 <= self.item_index < len(prefs.items)):
            return {'CANCELLED'}
        prefs.items[self.item_index].folder_uid = ""
        return {'FINISHED'}


class TABMGR_OT_assign_to_folder(Operator):
    bl_idname = "tabmgr.assign_to_folder"
    bl_label = "フォルダへ入れる"
    item_index: IntProperty()
    folder_uid: StringProperty()

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None or not (0 <= self.item_index < len(prefs.items)):
            return {'CANCELLED'}
        prefs.items[self.item_index].folder_uid = self.folder_uid
        return {'FINISHED'}


class TABMGR_MT_pick_folder(Menu):
    bl_idname = "TABMGR_MT_pick_folder"
    bl_label = "フォルダへ入れる"

    def draw(self, context):
        prefs = get_prefs()
        layout = self.layout
        if prefs is None:
            return
        idx = context.window_manager.tabmgr_menu_index
        if not prefs.folders:
            layout.label(text="フォルダがまだありません")
        for folder in prefs.folders:
            op = layout.operator(TABMGR_OT_assign_to_folder.bl_idname, text=folder.name, icon='FILE_FOLDER')
            op.item_index = idx
            op.folder_uid = folder.uid
        layout.separator()
        op2 = layout.operator(TABMGR_OT_add_folder_and_assign.bl_idname, text="＋ 新しいフォルダを作って入れる", icon='NEWFOLDER')
        op2.item_index = idx


class TABMGR_OT_open_folder_menu(Operator):
    bl_idname = "tabmgr.open_folder_menu"
    bl_label = ""
    bl_description = "このタブを入れるフォルダを選びます"
    item_index: IntProperty()

    def execute(self, context):
        context.window_manager.tabmgr_menu_index = self.item_index
        bpy.ops.wm.call_menu(name=TABMGR_MT_pick_folder.bl_idname)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# オペレーター: プリセット保存/読込
# ---------------------------------------------------------------------------

class TABMGR_OT_save_preset(Operator):
    bl_idname = "tabmgr.save_preset"
    bl_label = "プリセットを保存"
    bl_description = "現在のフォルダ構成をJSONファイルに保存します"
    filepath: StringProperty(subtype="FILE_PATH", default="tab_manager_preset.json")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        data = {
            "folders": [{"uid": f.uid, "name": f.name} for f in prefs.folders],
            "items": [
                {
                    "idname": it.idname,
                    "label": it.label,
                    "original_category": it.original_category,
                    "folder_uid": it.folder_uid,
                }
                for it in prefs.items
            ],
        }
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.report({'ERROR'}, _tr("保存に失敗しました: %s") % e)
            return {'CANCELLED'}
        self.report({'INFO'}, _tr("プリセットを保存しました"))
        return {'FINISHED'}


class TABMGR_OT_load_preset(Operator):
    bl_idname = "tabmgr.load_preset"
    bl_label = "プリセットを読み込み"
    bl_description = "JSONファイルからフォルダ構成を読み込んで適用します"
    filepath: StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        if not os.path.exists(self.filepath):
            self.report({'ERROR'}, _tr("ファイルが見つかりません"))
            return {'CANCELLED'}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, _tr("読み込みに失敗しました: %s") % e)
            return {'CANCELLED'}

        do_scan(prefs)

        prefs.folders.clear()
        old_to_new = {}
        for f_data in data.get("folders", []):
            nf = create_folder(prefs, name=f_data.get("name", "フォルダ"))
            old_to_new[f_data.get("uid", "")] = nf.uid

        by_id = {it.idname: it for it in prefs.items}
        for it_data in data.get("items", []):
            it = by_id.get(it_data.get("idname"))
            if it is None:
                continue
            old_uid = it_data.get("folder_uid", "")
            it.folder_uid = old_to_new.get(old_uid, "")

        apply_settings(prefs)
        self.report({'INFO'}, _tr("プリセットを適用しました"))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# UI (環境設定)
# ---------------------------------------------------------------------------

class TABMGR_Preferences(AddonPreferences):
    bl_idname = __name__

    items: CollectionProperty(type=TABMGR_PanelItem)
    folders: CollectionProperty(type=TABMGR_Folder)
    active_folder_index: IntProperty()
    folder_counter: IntProperty(default=0)
    startup_delay: FloatProperty(
        name="起動時の適用待機時間(秒)",
        description="他のアドオンの読み込みが終わるのを待ってから設定を再適用します",
        default=1.5, min=0.0, max=10.0,
    )
    ignore_basic_tabs: BoolProperty(
        name="基本タブは無視する",
        description="Blender標準タブ(Item/Tool/View/Animationなど)と、複数の無関係なアドオンが"
                    "共有している汎用タブ(プリセット一覧など)を管理対象から外し、"
                    "そのアドオン固有のタブだけを一覧に表示します",
        default=True,
    )
    show_debug: BoolProperty(
        name="デバッグ情報を表示",
        description="全てのタブについて、判定に使っている内部情報(モジュール名・"
                    "同梱扱いかどうか・ファイルの場所)を表示します。"
                    "タブが期待通り表示されない/消える場合の原因調査用です。",
        default=False,
    )

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.operator(TABMGR_OT_scan.bl_idname, icon='FILE_REFRESH')
        row.operator(TABMGR_OT_apply.bl_idname, icon='CHECKMARK')
        row.operator(TABMGR_OT_reset.bl_idname, icon='LOOP_BACK')

        row = layout.row(align=True)
        row.operator(TABMGR_OT_save_preset.bl_idname, icon='EXPORT')
        row.operator(TABMGR_OT_load_preset.bl_idname, icon='IMPORT')

        layout.prop(self, "startup_delay")
        layout.prop(self, "ignore_basic_tabs")
        if self.ignore_basic_tabs:
            layout.label(
                text="※ Blender標準タブ・Blender同梱アドオン(glTF I/Oなど)は非表示中。設定を変えたら「スキャン」を押し直してください。",
                icon='INFO',
            )

        layout.prop(self, "show_debug")
        if self.show_debug:
            box = layout.box()
            box.label(text="デバッグ情報（フィルタを無視して全タブを表示）", icon='CONSOLE')
            not_found = _tr("(取得できませんでした)")
            bundled_root = _get_bundled_root() or not_found
            user_root = _get_user_addons_root() or not_found
            box.label(text=_tr("Blenderインストール先(LOCAL): %s") % str(bundled_root))
            box.label(text=_tr("ユーザーaddonsフォルダ(参考): %s") % str(user_root))
            for r in _debug_rows():
                line = box.box()
                line.label(text=_tr("タブ名『%s』 / パネル: %s (%s)") % (r['category'], r['label'], r['idname']))
                line.label(text=_tr("　モジュール: %s　(判定キー: %s)") % (r['module_full'], r['module_key']))
                bundled_text = _tr("はい（同梱扱い＝非表示対象）") if r['bundled'] else _tr("いいえ（ユーザーのタブ扱い）")
                line.label(text=_tr("　同梱扱い: %s") % bundled_text)
                line.label(text=_tr("　ファイルの場所: %s") % r['file_path'])

        layout.separator()
        row = layout.row()
        row.label(text="フォルダ（＝Nパネルのタブ）", icon='FILE_FOLDER')
        row.operator(TABMGR_OT_add_folder.bl_idname, text="＋ フォルダを追加", icon='NEWFOLDER')
        layout.label(
            text="※ 中身が空のフォルダは、適用してもNパネルにタブとして表示されません（Blenderは空のタブを作れないため）。",
            icon='INFO',
        )

        if not self.folders:
            layout.label(text="フォルダがまだありません。下の一覧からタブを選んで追加してください。")

        for f_index, folder in enumerate(self.folders):
            box = layout.box()
            header = box.row(align=True)
            header.operator(
                TABMGR_OT_toggle_folder.bl_idname, text="",
                icon='TRIA_DOWN' if folder.expanded else 'TRIA_RIGHT',
            ).index = f_index
            header.prop(folder, "name", text="")
            up = header.operator(TABMGR_OT_move_folder.bl_idname, text="", icon='TRIA_UP')
            up.direction = 'UP'
            up.index = f_index
            down = header.operator(TABMGR_OT_move_folder.bl_idname, text="", icon='TRIA_DOWN')
            down.direction = 'DOWN'
            down.index = f_index
            header.operator(TABMGR_OT_remove_folder.bl_idname, text="", icon='X').index = f_index

            if folder.expanded:
                filed = [(i, it) for i, it in enumerate(self.items) if it.folder_uid == folder.uid]
                if not filed:
                    box.label(text="　（空のフォルダ）")
                for i, it in filed:
                    r = box.row(align=True)
                    if it.missing:
                        icon = 'ERROR'
                    elif it.shared_warning:
                        icon = 'QUESTION'
                    else:
                        icon = 'MENU_PANEL'
                    text = "　" + (it.label or it.idname)
                    if it.member_count > 1:
                        text += _tr("（%d件のパネル）") % it.member_count
                    if it.shared_warning and not it.missing:
                        text += _tr("　⚠共有タブかも")
                    r.label(text=text, icon=icon)
                    r.operator(TABMGR_OT_unfile_item.bl_idname, text="", icon='X').item_index = i

        layout.separator()
        layout.label(text="未整理（まだどのフォルダにも入っていないタブ）")
        unfiled = [(i, it) for i, it in enumerate(self.items) if not it.folder_uid and not it.missing]
        if not unfiled:
            layout.label(text="　なし")
        for i, it in unfiled:
            r = layout.row(align=True)
            icon = 'QUESTION' if it.shared_warning else 'MENU_PANEL'
            text = it.label or it.idname
            if it.member_count > 1:
                text += _tr("（%d件のパネル）") % it.member_count
            if it.shared_warning:
                text += _tr("　⚠同じタブ名を複数のアドオンが使ってる可能性あり")
            r.label(text=text, icon=icon)
            r.operator(TABMGR_OT_open_folder_menu.bl_idname, text="フォルダへ入れる", icon='DOWNARROW_HLT').item_index = i

        layout.separator()
        layout.label(
            text="※ タブの並び順は「適用」を押した時、フォルダの並び順に沿って管理対象パネル同士の相対順序のみ制御します。",
            icon='INFO',
        )
        layout.label(text="　反映されない場合はサイドバー(N)を一度閉じて開き直してください。")


# ---------------------------------------------------------------------------
# 起動時の自動適用
# ---------------------------------------------------------------------------

def _delayed_apply():
    prefs = get_prefs()
    if prefs is not None and len(prefs.folders) > 0:
        apply_settings(prefs)
    return None


@bpy.app.handlers.persistent
def _on_load_post(dummy):
    prefs = get_prefs()
    delay = prefs.startup_delay if prefs else 1.5
    bpy.app.timers.register(_delayed_apply, first_interval=delay)


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

classes = (
    TABMGR_Folder,
    TABMGR_PanelItem,
    TABMGR_OT_scan,
    TABMGR_OT_apply,
    TABMGR_OT_reset,
    TABMGR_OT_add_folder,
    TABMGR_OT_add_folder_and_assign,
    TABMGR_OT_remove_folder,
    TABMGR_OT_move_folder,
    TABMGR_OT_toggle_folder,
    TABMGR_OT_unfile_item,
    TABMGR_OT_assign_to_folder,
    TABMGR_MT_pick_folder,
    TABMGR_OT_open_folder_menu,
    TABMGR_OT_save_preset,
    TABMGR_OT_load_preset,
    TABMGR_Preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.tabmgr_menu_index = IntProperty(default=0)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    try:
        bpy.app.translations.register(__name__, TRANSLATIONS_DICT)
    except Exception:
        pass

    prefs = get_prefs()
    delay = prefs.startup_delay if prefs else 1.5
    bpy.app.timers.register(_delayed_apply, first_interval=delay)


def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass

    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    if hasattr(bpy.types.WindowManager, "tabmgr_menu_index"):
        del bpy.types.WindowManager.tabmgr_menu_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
