# -*- coding: utf-8 -*-
"""
NormalFix Ver1.3.4
3ds Max用 法線・シェーディング補正ツール

対応方針:
- 最初に指定角度で自動スムースを適用（初期値35度）
- 選択したジオメトリに標準の Weighted Normals モディファイヤを追加
- 既に NormalFix が存在する場合は重複追加せず設定を更新
- 必要に応じて処理後のモディファイアスタックを集約
- 元ジオメトリ、頂点位置、UVは変更しない
- 複数選択対応
- Undo対応
- 3ds Max 2022系(PySide2) / 2025以降(PySide6)を考慮

実行:
3ds Max の [スクリプト] > [スクリプトを実行] などから本ファイルを実行してください。
"""

import pymxs
from pymxs import runtime as rt

try:
    from PySide6 import QtCore, QtWidgets
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtCore, QtWidgets
    PYSIDE_VERSION = 2

try:
    import qtmax
except ImportError:
    qtmax = None


TOOL_NAME = "NormalFix"
TOOL_VERSION = "1.3.4"
AUTOSMOOTH_MODIFIER_NAME = "NormalFix_AutoSmooth"
RESET_MODIFIER_NAME = "NormalFix_Reset"
UNIFY_MODIFIER_NAME = "NormalFix_Unify"
WEIGHTED_MODIFIER_NAME = "NormalFix_Weighted"
TOOL_MODIFIER_NAMES = {
    AUTOSMOOTH_MODIFIER_NAME,
    RESET_MODIFIER_NAME,
    UNIFY_MODIFIER_NAME,
    WEIGHTED_MODIFIER_NAME,
    "NormalFix",  # Ver1.0.0との互換用
}

_dialog_instance = None


# ------------------------------------------------------------
# 3ds Max utilities
# ------------------------------------------------------------

def _get_max_main_window():
    """3ds MaxのメインウィンドウをQt親として返す。"""
    if qtmax is not None:
        try:
            return qtmax.GetQMaxMainWindow()
        except Exception:
            pass

    try:
        return QtWidgets.QWidget.find(int(rt.windows.getMAXHWND()))
    except Exception:
        return None


def _is_geometry_node(node):
    """選択ノードがジオメトリとして扱えるかを判定する。"""
    if node is None:
        return False

    try:
        superclass = rt.superClassOf(node)
        return str(superclass).lower() == "geometryclass"
    except Exception:
        return False


def _selected_geometry_nodes():
    """現在の選択を固定し、ジオメトリだけを返す。"""
    result = []
    try:
        # getCurrentSelectionで処理開始時点の選択配列を複製する。
        # 集約処理がMax側の現在選択を変更しても、この配列は維持される。
        selected_nodes = list(rt.getCurrentSelection())
        for node in selected_nodes:
            if _is_geometry_node(node):
                result.append(node)
    except Exception:
        # 古い環境向けのフォールバック。
        try:
            for node in list(rt.selection):
                if _is_geometry_node(node):
                    result.append(node)
        except Exception:
            pass
    return result


def _restore_selection(nodes):
    """処理後も、有効な全対象ノードを選択状態へ戻す。"""
    valid_nodes = []
    for node in nodes:
        try:
            if rt.isValidNode(node):
                valid_nodes.append(node)
        except Exception:
            continue

    if valid_nodes:
        try:
            rt.select(valid_nodes)
        except Exception:
            pass


def _find_named_modifier(node, modifier_name):
    """指定名のモディファイヤを探す。"""
    try:
        for modifier in list(node.modifiers):
            try:
                if str(modifier.name) == modifier_name:
                    return modifier
            except Exception:
                continue
    except Exception:
        pass
    return None


def _create_weighted_normals():
    """3ds Max標準 Weighted Normals モディファイヤを生成する。"""
    try:
        return rt.Weighted_Normals()
    except Exception:
        try:
            return rt.WeightedNormalsMod()
        except Exception as exc:
            raise RuntimeError(
                "Weighted Normals モディファイヤを作成できません。"
                "3ds Max 2021以降で実行してください。"
            ) from exc


def _create_auto_smooth():
    """自動スムース処理用の Smooth を生成する。"""
    try:
        return rt.Smooth()
    except Exception:
        return rt.SmoothModifier()


def _apply_auto_smooth(modifier, node, angle):
    """指定角度でスムージンググループを自動設定する。"""
    _set_if_available(modifier, "autosmooth", True)
    _set_if_available(modifier, "threshold", float(angle))
    _set_if_available(modifier, "preventIndirect", True)


def _create_edit_normals():
    """明示的法線をリセットする Edit Normals を生成する。"""
    try:
        return rt.Edit_Normals()
    except Exception:
        return rt.EditNormals()


def _create_normal_modifier():
    """面法線を統一する Normal モディファイヤを生成する。"""
    return rt.NormalModifier()


def _reset_explicit_normals(modifier, node):
    """Edit Normals上の全法線をUnspecifiedへ戻す。"""
    interface = modifier.EditNormalsMod
    count = int(interface.GetNumNormals(node=node))
    if count <= 0:
        return
    # pymxs上で確実に全要素を立てたMAXScript BitArrayを生成する。
    selection = rt.execute("#{1..%d}" % count)
    interface.Reset(selection=selection, node=node)


def _set_if_available(obj, property_name, value):
    """
    バージョン差でプロパティが存在しない場合を考慮し、
    存在するプロパティだけ設定する。
    """
    try:
        if rt.isProperty(obj, property_name):
            rt.setProperty(obj, property_name, value)
            return True
    except Exception:
        pass

    try:
        setattr(obj, property_name, value)
        return True
    except Exception:
        return False


def _configure_modifier(modifier, settings):
    """Weighted Normals の設定値を反映する。"""
    try:
        modifier.name = WEIGHTED_MODIFIER_NAME
    except Exception:
        pass

    _set_if_available(modifier, "useAreaWeight", settings["use_area"])
    _set_if_available(modifier, "useAngleWeight", settings["use_angle"])
    _set_if_available(modifier, "useConvexAngle", settings["use_convex"])
    _set_if_available(
        modifier,
        "useSmoothingGroups",
        settings["use_smoothing_groups"],
    )
    _set_if_available(
        modifier,
        "useHardEdgeAngle",
        settings["use_hard_edge_angle"],
    )

    _set_if_available(
        modifier,
        "hardEdgeAngle",
        float(settings["hard_edge_angle"]),
    )
    _set_if_available(
        modifier,
        "blendingCoeff",
        float(settings["blending"]),
    )
    _set_if_available(
        modifier,
        "boundaryCoeff",
        float(settings["boundary"]),
    )
    _set_if_available(
        modifier,
        "smoothingCoeff",
        float(settings["smoothing"]),
    )
    _set_if_available(
        modifier,
        "smoothingIterLimit",
        int(settings["smoothing_iterations"]),
    )

    _set_if_available(
        modifier,
        "displayNormals",
        settings["display_normals"],
    )
    _set_if_available(
        modifier,
        "normalLength",
        float(settings["normal_length"]),
    )


def apply_normal_fix(settings):
    """
    選択オブジェクトへ法線補正を適用する。

    戻り値:
        (applied_count, updated_count, consolidated_count,
         skipped_names, errors)
    """
    nodes = _selected_geometry_nodes()
    if not nodes:
        return 0, 0, 0, [], ["ジオメトリが選択されていません。"]

    applied_count = 0
    updated_count = 0
    consolidated_count = 0
    skipped_names = []
    errors = []

    # pymxs.undo 内で例外を外へ投げるとブロック全体がUndoされるため、
    # ノード単位のエラーはここで捕捉する。
    with pymxs.undo(True, "NormalFix"):
        for node in nodes:
            try:
                had_tool_modifier = any(
                    str(modifier.name) in TOOL_MODIFIER_NAMES
                    for modifier in list(node.modifiers)
                )
                changed = False

                if settings["use_auto_smooth"]:
                    smooth_mod = _find_named_modifier(
                        node, AUTOSMOOTH_MODIFIER_NAME
                    )
                    if smooth_mod is None:
                        smooth_mod = _create_auto_smooth()
                        smooth_mod.name = AUTOSMOOTH_MODIFIER_NAME
                        rt.addModifier(node, smooth_mod)
                    _apply_auto_smooth(
                        smooth_mod,
                        node,
                        settings["auto_smooth_angle"],
                    )
                    changed = True

                if settings["reset_explicit"]:
                    reset_mod = _find_named_modifier(node, RESET_MODIFIER_NAME)
                    if reset_mod is None:
                        reset_mod = _create_edit_normals()
                        reset_mod.name = RESET_MODIFIER_NAME
                        rt.addModifier(node, reset_mod)
                    _reset_explicit_normals(reset_mod, node)
                    changed = True

                if settings["unify_faces"]:
                    unify_mod = _find_named_modifier(node, UNIFY_MODIFIER_NAME)
                    if unify_mod is None:
                        unify_mod = _create_normal_modifier()
                        unify_mod.name = UNIFY_MODIFIER_NAME
                        rt.addModifier(node, unify_mod)
                    _set_if_available(unify_mod, "unify", True)
                    _set_if_available(unify_mod, "flip", False)
                    changed = True

                if settings["use_weighted"]:
                    modifier = _find_named_modifier(node, WEIGHTED_MODIFIER_NAME)
                    if modifier is None:
                        # Ver1.0.0のモディファイヤがあれば引き継ぐ。
                        modifier = _find_named_modifier(node, "NormalFix")
                    if modifier is None:
                        modifier = _create_weighted_normals()
                        _configure_modifier(modifier, settings)
                        rt.addModifier(node, modifier)
                    else:
                        _configure_modifier(modifier, settings)
                    changed = True

                if changed:
                    if had_tool_modifier:
                        updated_count += 1
                    else:
                        applied_count += 1

                    if settings["consolidate_modifiers"]:
                        # 補正結果をメッシュへ確定し、スタック全体を集約する。
                        # 元へ戻す場合は、このUndoブロックをUndoする。
                        rt.collapseStack(node)
                        consolidated_count += 1
                else:
                    skipped_names.append(str(node.name))

            except Exception as exc:
                errors.append("{}: {}".format(getattr(node, "name", "<unknown>"), exc))

    try:
        _restore_selection(nodes)
        rt.redrawViews()
    except Exception:
        pass

    return (
        applied_count,
        updated_count,
        consolidated_count,
        skipped_names,
        errors,
    )


def remove_normal_fix():
    """
    選択オブジェクトから、このツールで追加した補正だけを削除する。

    戻り値:
        (removed_count, not_found_count, errors)
    """
    nodes = _selected_geometry_nodes()
    if not nodes:
        return 0, 0, ["ジオメトリが選択されていません。"]

    removed_count = 0
    not_found_count = 0
    errors = []

    with pymxs.undo(True, "Remove NormalFix"):
        for node in nodes:
            try:
                modifiers = []
                for modifier in list(node.modifiers):
                    if str(modifier.name) in TOOL_MODIFIER_NAMES:
                        modifiers.append(modifier)
                if not modifiers:
                    not_found_count += 1
                    continue

                for modifier in modifiers:
                    rt.deleteModifier(node, modifier)
                removed_count += 1

            except Exception as exc:
                errors.append("{}: {}".format(getattr(node, "name", "<unknown>"), exc))

    try:
        _restore_selection(nodes)
        rt.redrawViews()
    except Exception:
        pass

    return removed_count, not_found_count, errors


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

class NormalFixDialog(QtWidgets.QDialog):
    PRESETS = {
        "標準": {
            "auto_smooth_angle": 35.0,
            "use_area": True,
            "use_angle": True,
            "use_convex": True,
            "use_smoothing_groups": True,
            "use_hard_edge_angle": True,
            "hard_edge_angle": 45.0,
            "blending": 1.0,
            "boundary": 0.5,
            "smoothing": 0.0,
            "smoothing_iterations": 10,
        },
        "ハードサーフェス": {
            "auto_smooth_angle": 5.0,
            "use_area": True,
            "use_angle": True,
            "use_convex": True,
            "use_smoothing_groups": True,
            "use_hard_edge_angle": True,
            "hard_edge_angle": 30.0,
            "blending": 1.0,
            "boundary": 0.25,
            "smoothing": 0.0,
            "smoothing_iterations": 10,
        },
        "滑らか": {
            "auto_smooth_angle": 90.0,
            "use_area": True,
            "use_angle": True,
            "use_convex": True,
            "use_smoothing_groups": False,
            "use_hard_edge_angle": False,
            "hard_edge_angle": 60.0,
            "blending": 1.0,
            "boundary": 0.5,
            "smoothing": 0.35,
            "smoothing_iterations": 10,
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("{} Ver{}".format(TOOL_NAME, TOOL_VERSION))
        self.setMinimumWidth(390)

        try:
            self.setWindowFlag(QtCore.Qt.Tool, True)
        except Exception:
            pass

        self._build_ui()
        self._connect_signals()
        self._apply_preset("標準")

        if qtmax is not None:
            try:
                qtmax.DisableMaxAcceleratorsOnFocus(self, True)
            except Exception:
                pass

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        info_label = QtWidgets.QLabel(
            "選択したジオメトリの法線を補正し、\n"
            "ポリゴン面の不自然な陰影を軽減します。"
        )
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        pipeline_group = QtWidgets.QGroupBox("補正工程")
        pipeline_layout = QtWidgets.QVBoxLayout(pipeline_group)
        self.use_auto_smooth_check = QtWidgets.QCheckBox(
            "最初に自動スムースを適用"
        )
        self.use_auto_smooth_check.setChecked(True)
        auto_smooth_layout = QtWidgets.QHBoxLayout()
        auto_smooth_layout.addSpacing(20)
        auto_smooth_layout.addWidget(QtWidgets.QLabel("スムース角度"))
        self.auto_smooth_angle = QtWidgets.QDoubleSpinBox()
        self.auto_smooth_angle.setRange(0.0, 180.0)
        self.auto_smooth_angle.setDecimals(1)
        self.auto_smooth_angle.setSingleStep(5.0)
        self.auto_smooth_angle.setValue(35.0)
        self.auto_smooth_angle.setSuffix("°")
        auto_smooth_layout.addWidget(self.auto_smooth_angle)
        auto_smooth_layout.addStretch(1)
        self.reset_explicit_check = QtWidgets.QCheckBox(
            "既存の明示的法線をリセット"
        )
        self.unify_faces_check = QtWidgets.QCheckBox(
            "面法線の向きを統一（反転面の修正）"
        )
        self.use_weighted_check = QtWidgets.QCheckBox(
            "Weighted Normalsでシェーディングを補正"
        )
        self.reset_explicit_check.setChecked(False)
        self.unify_faces_check.setChecked(False)
        self.use_weighted_check.setChecked(True)
        self.consolidate_check = QtWidgets.QCheckBox(
            "最後にモディファイアを集約する"
        )
        self.consolidate_check.setToolTip(
            "補正後にモディファイアスタック全体をメッシュへ確定します。"
            "元へ戻す場合はUndoを使用してください。"
        )
        self.consolidate_check.setChecked(True)
        pipeline_layout.addWidget(self.use_auto_smooth_check)
        pipeline_layout.addLayout(auto_smooth_layout)
        pipeline_layout.addWidget(self.reset_explicit_check)
        pipeline_layout.addWidget(self.unify_faces_check)
        pipeline_layout.addWidget(self.use_weighted_check)
        pipeline_layout.addWidget(self.consolidate_check)
        main_layout.addWidget(pipeline_group)

        # Preset
        preset_group = QtWidgets.QGroupBox("プリセット")
        preset_layout = QtWidgets.QHBoxLayout(preset_group)

        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(list(self.PRESETS.keys()))
        preset_layout.addWidget(self.preset_combo, 1)

        self.reset_button = QtWidgets.QPushButton("標準に戻す")
        preset_layout.addWidget(self.reset_button)

        main_layout.addWidget(preset_group)

        # Weighting
        weighting_group = QtWidgets.QGroupBox("重み付け")
        weighting_layout = QtWidgets.QGridLayout(weighting_group)

        self.area_check = QtWidgets.QCheckBox("面積")
        self.angle_check = QtWidgets.QCheckBox("角度")
        self.convex_check = QtWidgets.QCheckBox("凸角を使用")
        self.smoothing_groups_check = QtWidgets.QCheckBox(
            "スムージンググループを維持"
        )

        weighting_layout.addWidget(self.area_check, 0, 0)
        weighting_layout.addWidget(self.angle_check, 0, 1)
        weighting_layout.addWidget(self.convex_check, 1, 0)
        weighting_layout.addWidget(self.smoothing_groups_check, 1, 1)

        main_layout.addWidget(weighting_group)

        # Edge
        edge_group = QtWidgets.QGroupBox("エッジ")
        edge_layout = QtWidgets.QGridLayout(edge_group)

        self.hard_edge_check = QtWidgets.QCheckBox("ハードエッジ角度を使用")
        self.hard_edge_angle = QtWidgets.QDoubleSpinBox()
        self.hard_edge_angle.setRange(0.0, 180.0)
        self.hard_edge_angle.setDecimals(1)
        self.hard_edge_angle.setSingleStep(5.0)
        self.hard_edge_angle.setSuffix("°")

        self.boundary_spin = QtWidgets.QDoubleSpinBox()
        self.boundary_spin.setRange(0.0, 1.0)
        self.boundary_spin.setDecimals(2)
        self.boundary_spin.setSingleStep(0.05)

        edge_layout.addWidget(self.hard_edge_check, 0, 0)
        edge_layout.addWidget(self.hard_edge_angle, 0, 1)
        edge_layout.addWidget(QtWidgets.QLabel("境界ブレンド"), 1, 0)
        edge_layout.addWidget(self.boundary_spin, 1, 1)

        main_layout.addWidget(edge_group)

        # Fine tuning
        detail_group = QtWidgets.QGroupBox("微調整")
        detail_layout = QtWidgets.QGridLayout(detail_group)

        self.blending_spin = QtWidgets.QDoubleSpinBox()
        self.blending_spin.setRange(0.0, 1.0)
        self.blending_spin.setDecimals(2)
        self.blending_spin.setSingleStep(0.05)

        self.smoothing_spin = QtWidgets.QDoubleSpinBox()
        self.smoothing_spin.setRange(0.0, 1.0)
        self.smoothing_spin.setDecimals(2)
        self.smoothing_spin.setSingleStep(0.05)

        self.iterations_spin = QtWidgets.QSpinBox()
        self.iterations_spin.setRange(1, 100)

        detail_layout.addWidget(QtWidgets.QLabel("補正ブレンド"), 0, 0)
        detail_layout.addWidget(self.blending_spin, 0, 1)
        detail_layout.addWidget(QtWidgets.QLabel("スムージング"), 1, 0)
        detail_layout.addWidget(self.smoothing_spin, 1, 1)
        detail_layout.addWidget(QtWidgets.QLabel("反復回数"), 2, 0)
        detail_layout.addWidget(self.iterations_spin, 2, 1)

        main_layout.addWidget(detail_group)

        # Display normals
        display_group = QtWidgets.QGroupBox("確認表示")
        display_layout = QtWidgets.QGridLayout(display_group)

        self.display_normals_check = QtWidgets.QCheckBox("法線を表示")
        self.normal_length_spin = QtWidgets.QDoubleSpinBox()
        self.normal_length_spin.setRange(0.01, 100000.0)
        self.normal_length_spin.setDecimals(2)
        self.normal_length_spin.setValue(10.0)

        display_layout.addWidget(self.display_normals_check, 0, 0)
        display_layout.addWidget(self.normal_length_spin, 0, 1)

        main_layout.addWidget(display_group)

        # Buttons
        self.apply_button = QtWidgets.QPushButton("選択オブジェクトを補正")
        self.apply_button.setMinimumHeight(38)
        main_layout.addWidget(self.apply_button)

        button_layout = QtWidgets.QHBoxLayout()
        self.remove_button = QtWidgets.QPushButton("補正を削除")
        self.undo_button = QtWidgets.QPushButton("Undo")
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.undo_button)
        main_layout.addLayout(button_layout)

        self.status_label = QtWidgets.QLabel("待機中")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        main_layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        self.reset_button.clicked.connect(
            lambda: self.preset_combo.setCurrentText("標準")
        )
        self.hard_edge_check.toggled.connect(
            self.hard_edge_angle.setEnabled
        )
        self.use_auto_smooth_check.toggled.connect(
            self.auto_smooth_angle.setEnabled
        )
        self.display_normals_check.toggled.connect(
            self.normal_length_spin.setEnabled
        )

        self.apply_button.clicked.connect(self._on_apply)
        self.remove_button.clicked.connect(self._on_remove)
        self.undo_button.clicked.connect(self._on_undo)

    def _apply_preset(self, preset_name):
        preset = self.PRESETS.get(str(preset_name))
        if not preset:
            return

        self.area_check.setChecked(preset["use_area"])
        self.auto_smooth_angle.setValue(preset["auto_smooth_angle"])
        self.angle_check.setChecked(preset["use_angle"])
        self.convex_check.setChecked(preset["use_convex"])
        self.smoothing_groups_check.setChecked(
            preset["use_smoothing_groups"]
        )
        self.hard_edge_check.setChecked(
            preset["use_hard_edge_angle"]
        )
        self.hard_edge_angle.setValue(preset["hard_edge_angle"])
        self.blending_spin.setValue(preset["blending"])
        self.boundary_spin.setValue(preset["boundary"])
        self.smoothing_spin.setValue(preset["smoothing"])
        self.iterations_spin.setValue(
            preset["smoothing_iterations"]
        )

        self.hard_edge_angle.setEnabled(
            self.hard_edge_check.isChecked()
        )
        self.normal_length_spin.setEnabled(
            self.display_normals_check.isChecked()
        )

    def _collect_settings(self):
        return {
            "use_auto_smooth": self.use_auto_smooth_check.isChecked(),
            "auto_smooth_angle": self.auto_smooth_angle.value(),
            "reset_explicit": self.reset_explicit_check.isChecked(),
            "unify_faces": self.unify_faces_check.isChecked(),
            "use_weighted": self.use_weighted_check.isChecked(),
            "consolidate_modifiers": self.consolidate_check.isChecked(),
            "use_area": self.area_check.isChecked(),
            "use_angle": self.angle_check.isChecked(),
            "use_convex": self.convex_check.isChecked(),
            "use_smoothing_groups":
                self.smoothing_groups_check.isChecked(),
            "use_hard_edge_angle": self.hard_edge_check.isChecked(),
            "hard_edge_angle": self.hard_edge_angle.value(),
            "blending": self.blending_spin.value(),
            "boundary": self.boundary_spin.value(),
            "smoothing": self.smoothing_spin.value(),
            "smoothing_iterations": self.iterations_spin.value(),
            "display_normals": self.display_normals_check.isChecked(),
            "normal_length": self.normal_length_spin.value(),
        }

    def _on_apply(self):
        settings = self._collect_settings()
        applied, updated, consolidated, skipped, errors = apply_normal_fix(
            settings
        )

        lines = [
            "追加: {} / 更新: {} / 集約: {}".format(
                applied, updated, consolidated
            )
        ]

        if skipped:
            lines.append(
                "対象外: {}".format(", ".join(skipped))
            )

        if errors:
            lines.append("エラー:")
            lines.extend(errors)

        self.status_label.setText("\n".join(lines))

    def _on_remove(self):
        removed, not_found, errors = remove_normal_fix()

        lines = [
            "削除: {} / 補正なし: {}".format(removed, not_found)
        ]

        if errors:
            lines.append("エラー:")
            lines.extend(errors)

        self.status_label.setText("\n".join(lines))

    def _on_undo(self):
        try:
            pymxs.run_undo()
            rt.redrawViews()
            self.status_label.setText("Undoを実行しました。")
        except Exception as exc:
            self.status_label.setText(
                "Undoに失敗しました: {}".format(exc)
            )


def show_normal_fix():
    """ツールUIを表示する。"""
    global _dialog_instance

    try:
        if _dialog_instance is not None:
            _dialog_instance.close()
            _dialog_instance.deleteLater()
    except Exception:
        pass

    _dialog_instance = NormalFixDialog(
        parent=_get_max_main_window()
    )
    _dialog_instance.show()
    _dialog_instance.raise_()
    _dialog_instance.activateWindow()

    return _dialog_instance


if __name__ == "__main__":
    show_normal_fix()
