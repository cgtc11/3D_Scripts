# -*- coding: utf-8 -*-
"""
NormalFix Maya 2026 Ver1.0.2

処理順:
1. 自動スムース（Soften / Harden Edge）
2. 既存の明示的法線をリセット
3. 面法線の向きを統一（Conform）
4. Maya標準のウェイト付き頂点法線方式を設定
5. 必要に応じてコンストラクションヒストリを削除

複数メッシュ対応・Undo対応。
Maya 2026 の Script Editor の Python タブから実行してください。
"""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds


TOOL_NAME = "NormalFix Maya 2026"
TOOL_VERSION = "1.0.2"
WINDOW_NAME = "NormalFixMaya2026Window"

_UI = {}


PRESETS = {
    "標準": {
        "auto_smooth": True,
        "smooth_angle": 35.0,
        "reset_explicit": False,
        "conform_faces": False,
        "weighted": True,
        "use_area": True,
        "use_angle": True,
    },
    "ハードサーフェス": {
        "auto_smooth": True,
        "smooth_angle": 5.0,
        "reset_explicit": False,
        "conform_faces": False,
        "weighted": True,
        "use_area": True,
        "use_angle": True,
    },
    "滑らか": {
        "auto_smooth": True,
        "smooth_angle": 90.0,
        "reset_explicit": False,
        "conform_faces": False,
        "weighted": True,
        "use_area": False,
        "use_angle": True,
    },
}


def _long_name(node):
    result = cmds.ls(node, long=True) or []
    return result[0] if result else node


def _selected_meshes():
    """選択から、重複のない有効な非中間mesh shapeを取得する。"""
    selection = cmds.ls(selection=True, long=True, flatten=True) or []
    shapes = []
    seen = set()

    for selected in selection:
        node = selected.split(".", 1)[0]
        if not cmds.objExists(node):
            continue

        node_type = cmds.nodeType(node)
        candidates = []

        if node_type == "mesh":
            candidates = [node]
        elif node_type == "transform":
            candidates = cmds.listRelatives(
                node,
                shapes=True,
                noIntermediate=True,
                fullPath=True,
                type="mesh",
            ) or []
        else:
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            for parent in parents:
                candidates.extend(
                    cmds.listRelatives(
                        parent,
                        shapes=True,
                        noIntermediate=True,
                        fullPath=True,
                        type="mesh",
                    ) or []
                )

        for shape in candidates:
            shape = _long_name(shape)
            if shape in seen:
                continue
            try:
                if cmds.getAttr(shape + ".intermediateObject"):
                    continue
            except Exception:
                continue
            seen.add(shape)
            shapes.append(shape)

    return shapes


def _transforms_from_shapes(shapes):
    transforms = []
    seen = set()
    for shape in shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        if not parents:
            continue
        transform = parents[0]
        if transform not in seen:
            seen.add(transform)
            transforms.append(transform)
    return transforms


def _normal_method(use_area, use_angle):
    """Maya mesh.vertexNormalMethod の値を返す。"""
    if use_area and use_angle:
        return 3  # Angle And Area Weighted
    if use_angle:
        return 1  # Angle Weighted
    if use_area:
        return 2  # Area Weighted
    return 0      # Unweighted


def _unlock_normals(shape):
    """全頂点のロック済みユーザー法線を解除する。"""
    cmds.polyNormalPerVertex(
        shape + ".vtx[*]",
        unFreezeNormal=True,
    )


def _apply_to_shape(shape, settings):
    """1つのmesh shapeへ一連の法線処理を適用する。"""
    transform_list = cmds.listRelatives(
        shape, parent=True, fullPath=True
    ) or []
    if not transform_list:
        raise RuntimeError("親Transformが見つかりません。")
    transform = transform_list[0]

    if settings["auto_smooth"]:
        cmds.polySoftEdge(
            shape,
            angle=float(settings["smooth_angle"]),
            constructionHistory=True,
            name="NormalFix_AutoSmooth",
        )

    # vertexNormalMethodを反映するには、ロック済み法線を解除する必要がある。
    if settings["reset_explicit"] or settings["weighted"]:
        _unlock_normals(shape)

    if settings["conform_faces"]:
        cmds.polyNormal(
            shape,
            normalMode=2,
            constructionHistory=True,
            name="NormalFix_Conform",
        )

    if settings["weighted"]:
        method = _normal_method(
            settings["use_area"],
            settings["use_angle"],
        )
        attribute = shape + ".vertexNormalMethod"
        if not cmds.objExists(attribute):
            raise RuntimeError(
                "vertexNormalMethod属性が見つかりません。"
            )
        cmds.setAttr(attribute, method)

    if settings["delete_history"]:
        # Max版の「最後にモディファイアを集約」に相当する確定処理。
        # 対象Transformの既存履歴も削除されるため、戻す場合はUndoを使う。
        cmds.delete(transform, constructionHistory=True)


def _collect_settings():
    return {
        "auto_smooth": cmds.checkBox(
            _UI["auto_smooth"], query=True, value=True
        ),
        "smooth_angle": cmds.floatSliderGrp(
            _UI["smooth_angle"], query=True, value=True
        ),
        "reset_explicit": cmds.checkBox(
            _UI["reset_explicit"], query=True, value=True
        ),
        "conform_faces": cmds.checkBox(
            _UI["conform_faces"], query=True, value=True
        ),
        "weighted": cmds.checkBox(
            _UI["weighted"], query=True, value=True
        ),
        "use_area": cmds.checkBox(
            _UI["use_area"], query=True, value=True
        ),
        "use_angle": cmds.checkBox(
            _UI["use_angle"], query=True, value=True
        ),
        "delete_history": cmds.checkBox(
            _UI["delete_history"], query=True, value=True
        ),
    }


def apply_normal_fix(*_):
    shapes = _selected_meshes()
    if not shapes:
        _set_status("ポリゴンメッシュが選択されていません。")
        cmds.warning("NormalFix: ポリゴンメッシュを選択してください。")
        return

    transforms = _transforms_from_shapes(shapes)
    settings = _collect_settings()
    completed = 0
    errors = []

    cmds.undoInfo(openChunk=True, chunkName="NormalFix Maya 2026")
    try:
        for shape in shapes:
            try:
                _apply_to_shape(shape, settings)
                completed += 1
            except Exception as exc:
                errors.append("{}: {}".format(shape, exc))
    finally:
        cmds.undoInfo(closeChunk=True)

    existing_transforms = [
        node for node in transforms if cmds.objExists(node)
    ]
    if existing_transforms:
        cmds.select(existing_transforms, replace=True)

    lines = [
        "対象: {} / 完了: {} / 失敗: {}".format(
            len(shapes), completed, len(errors)
        )
    ]
    if settings["delete_history"] and completed:
        lines.append("最後にコンストラクションヒストリを削除しました。")
    if errors:
        lines.append("\n".join(errors))
        for error in errors:
            cmds.warning("NormalFix: " + error)

    _set_status("\n".join(lines))


def run_undo(*_):
    try:
        cmds.undo()
        _set_status("Undoを実行しました。")
    except Exception as exc:
        _set_status("Undoに失敗しました: {}".format(exc))


def _set_status(message):
    control = _UI.get("status")
    if control and cmds.control(control, exists=True):
        cmds.scrollField(control, edit=True, text=message)


def _set_dependent_controls(*_):
    auto_enabled = cmds.checkBox(
        _UI["auto_smooth"], query=True, value=True
    )
    weighted_enabled = cmds.checkBox(
        _UI["weighted"], query=True, value=True
    )
    cmds.floatSliderGrp(
        _UI["smooth_angle"], edit=True, enable=auto_enabled
    )
    cmds.checkBox(_UI["use_area"], edit=True, enable=weighted_enabled)
    cmds.checkBox(_UI["use_angle"], edit=True, enable=weighted_enabled)


def _apply_preset(*_):
    preset_name = cmds.optionMenu(
        _UI["preset"], query=True, value=True
    )
    preset = PRESETS.get(preset_name)
    if not preset:
        return

    cmds.checkBox(
        _UI["auto_smooth"], edit=True, value=preset["auto_smooth"]
    )
    cmds.floatSliderGrp(
        _UI["smooth_angle"], edit=True, value=preset["smooth_angle"]
    )
    cmds.checkBox(
        _UI["reset_explicit"], edit=True,
        value=preset["reset_explicit"]
    )
    cmds.checkBox(
        _UI["conform_faces"], edit=True,
        value=preset["conform_faces"]
    )
    cmds.checkBox(
        _UI["weighted"], edit=True, value=preset["weighted"]
    )
    cmds.checkBox(
        _UI["use_area"], edit=True, value=preset["use_area"]
    )
    cmds.checkBox(
        _UI["use_angle"], edit=True, value=preset["use_angle"]
    )
    _set_dependent_controls()


def show_normal_fix():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME, window=True)

    window = cmds.window(
        WINDOW_NAME,
        title="{} Ver{}".format(TOOL_NAME, TOOL_VERSION),
        sizeable=True,
        widthHeight=(410, 525),
    )

    cmds.columnLayout(adjustableColumn=True, rowSpacing=7)
    cmds.separator(height=5, style="none")
    cmds.text(
        label=(
            "選択したポリゴンメッシュの法線と\n"
            "不自然なシェーディングを一括補正します。"
        ),
        align="center",
    )

    cmds.frameLayout(
        label="プリセット", collapsable=False, marginWidth=8,
        marginHeight=7
    )
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    _UI["preset"] = cmds.optionMenu(changeCommand=_apply_preset)
    for preset_name in PRESETS:
        cmds.menuItem(label=preset_name)
    cmds.button(label="標準に戻す", command=lambda *_: _reset_preset())
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(
        label="補正工程", collapsable=False, marginWidth=8,
        marginHeight=7
    )
    _UI["auto_smooth"] = cmds.checkBox(
        label="最初に自動スムースを適用",
        value=True,
        changeCommand=_set_dependent_controls,
    )
    _UI["smooth_angle"] = cmds.floatSliderGrp(
        label="スムース角度",
        field=True,
        minValue=0.0,
        maxValue=180.0,
        fieldMinValue=0.0,
        fieldMaxValue=180.0,
        value=35.0,
        columnWidth3=(120, 60, 180),
    )
    _UI["reset_explicit"] = cmds.checkBox(
        label="既存の明示的法線をリセット", value=False
    )
    _UI["conform_faces"] = cmds.checkBox(
        label="面法線の向きを統一（反転面の修正）", value=False
    )
    _UI["weighted"] = cmds.checkBox(
        label="ウェイト付き頂点法線で補正",
        value=True,
        changeCommand=_set_dependent_controls,
    )
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(190, 190))
    _UI["use_area"] = cmds.checkBox(label="面積ウェイト", value=True)
    _UI["use_angle"] = cmds.checkBox(label="角度ウェイト", value=True)
    cmds.setParent("..")
    _UI["delete_history"] = cmds.checkBox(
        label="最後にコンストラクションヒストリを削除する",
        value=True,
        annotation=(
            "対象メッシュの既存ヒストリも削除します。"
            "元へ戻す場合はUndoを使用してください。"
        ),
    )
    cmds.setParent("..")

    cmds.separator(height=8, style="none")
    cmds.button(
        label="選択メッシュを補正",
        height=42,
        command=apply_normal_fix,
    )
    cmds.button(label="Undo", height=28, command=run_undo)

    _UI["status"] = cmds.scrollField(
        editable=False,
        wordWrap=True,
        text="待機中",
        height=75,
    )
    cmds.separator(height=5, style="none")

    cmds.showWindow(window)
    _apply_preset()
    return window


def _reset_preset():
    cmds.optionMenu(_UI["preset"], edit=True, value="標準")
    _apply_preset()


if __name__ == "__main__":
    show_normal_fix()
