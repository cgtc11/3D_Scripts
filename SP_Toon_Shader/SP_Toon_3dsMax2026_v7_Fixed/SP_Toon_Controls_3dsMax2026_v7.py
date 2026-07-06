# -*- coding: utf-8 -*-
"""
SP Toon Controls v7.1 for 3ds Max 2026 / Arnold
Python + pymxs + PySide6

Usage:
1. Open Slate Material Editor.
2. Create an OSL Map and load SP_Toon_User0_3dsMax2026.osl.
3. Select the OSL Map node in the active Slate view.
4. Run this Python file in 3ds Max.
5. Click "Load Selected OSL Map".
"""

from __future__ import annotations

import os
import traceback
from typing import Any, Optional

from pymxs import runtime as rt
from PySide6 import QtCore, QtGui, QtWidgets

WINDOW_OBJECT_NAME = "SPToon3dsMax2026PythonV7Window"

SP_TOON_WINDOW = None

TEXT = {
    "en": {
        "title": "SP Toon Controls v7.1 - 3ds Max 2026",
        "language": "Language",
        "english": "English",
        "japanese": "Japanese",
        "select_help": "Select the OSL Map node in Slate Material Editor.",
        "load_selected": "Load Selected OSL Map",
        "refresh": "Refresh Values",
        "target_none": "Target: Not selected",
        "target": "Target: {name}",
        "not_osl": "The selected Slate node does not appear to be the required OSL Map.",
        "selection_missing": "Select the OSL Map node in the active Slate view first.",
        "section_line_enable": "LINE ENABLE",
        "use_outline": "Use Outline",
        "section_light": "LIGHT POSITION",
        "section_line": "OUTLINE / INLINE",
        "section_toon": "TOON GRADATION",
        "section_color": "COLOR / TEXTURE SETTINGS",
        "section_curvature": "CURVATURE TEXTURE",
        "light_x": "Light Position X",
        "light_y": "Light Position Y",
        "light_z": "Light Position Z",
        "outline_thickness": "Outline Thickness",
        "outline_blur": "Outline Blur",
        "inline_thickness": "Inline Thickness",
        "inline_blur": "Inline Blur",
        "inline_on_top": "Inline on Top",
        "toon_2": "Toon Param 2",
        "toon_3": "Toon Param 3",
        "toon_4": "Toon Param 4",
        "toon_5": "Toon Param 5",
        "toon_6": "Toon Param 6",
        "toon_7": "Toon Param 7",
        "toon_blur": "Toon Blur",
        "base_color": "Base Color",
        "outline_color": "Outline Color",
        "inline_color": "Inline Color",
        "toon_color_2": "Toon Color 2",
        "toon_color_3": "Toon Color 3",
        "toon_color_4": "Toon Color 4",
        "toon_color_5": "Toon Color 5",
        "toon_color_6": "Toon Color 6",
        "toon_color_7": "Toon Color 7",
        "load": "Load",
        "remove": "Remove",
        "texture_none": "Texture: None",
        "texture_name": "Texture: {name}",
        "blur_help": (
            "Set Blur to 0 for hard boundaries. "
            "Outline Blur, Inline Blur, and Toon Blur have a maximum of 5."
        ),
        "property_missing": "OSL parameter was not found: {name}",
        "map_property_missing": "Texture-map input was not found: {name}",
        "texture_dialog": "Choose texture for {name}",
        "connected": "A texture is connected. Remove it before editing the direct value.",
        "error": "Error",
    },
    "ja": {
        "title": "SP Toon コントロール v7.1 - 3ds Max 2026",
        "language": "表示言語",
        "english": "英語",
        "japanese": "日本語",
        "select_help": "Slate Material EditorでOSL Mapノードを選択してください。",
        "load_selected": "選択したOSL Mapを読み込む",
        "refresh": "現在値を再読み込み",
        "target_none": "対象：未選択",
        "target": "対象：{name}",
        "not_osl": "選択したSlateノードは、対象のOSL Mapではない可能性があります。",
        "selection_missing": "アクティブなSlateビューでOSL Mapノードを選択してください。",
        "section_line_enable": "ライン表示",
        "use_outline": "アウトラインを使用",
        "section_light": "ライト位置",
        "section_line": "アウトライン／インライン",
        "section_toon": "トゥーングラデーション",
        "section_color": "色／テクスチャ設定",
        "section_curvature": "カーブチャーテクスチャ",
        "light_x": "ライト位置 X",
        "light_y": "ライト位置 Y",
        "light_z": "ライト位置 Z",
        "outline_thickness": "アウトラインの太さ",
        "outline_blur": "アウトラインのぼかし",
        "inline_thickness": "インラインの太さ",
        "inline_blur": "インラインのぼかし",
        "inline_on_top": "インライン最前面表示",
        "toon_2": "トゥーンパラメーター 2",
        "toon_3": "トゥーンパラメーター 3",
        "toon_4": "トゥーンパラメーター 4",
        "toon_5": "トゥーンパラメーター 5",
        "toon_6": "トゥーンパラメーター 6",
        "toon_7": "トゥーンパラメーター 7",
        "toon_blur": "トゥーンのぼかし",
        "base_color": "ベースカラー",
        "outline_color": "アウトラインカラー",
        "inline_color": "インラインカラー",
        "toon_color_2": "トゥーンカラー 2",
        "toon_color_3": "トゥーンカラー 3",
        "toon_color_4": "トゥーンカラー 4",
        "toon_color_5": "トゥーンカラー 5",
        "toon_color_6": "トゥーンカラー 6",
        "toon_color_7": "トゥーンカラー 7",
        "load": "読込",
        "remove": "解除",
        "texture_none": "テクスチャ：なし",
        "texture_name": "テクスチャ：{name}",
        "blur_help": (
            "ぼかしを0にすると硬い境界になります。"
            "アウトライン、インライン、トゥーンのぼかし最大値は5です。"
        ),
        "property_missing": "OSLパラメーターが見つかりません：{name}",
        "map_property_missing": "テクスチャ入力が見つかりません：{name}",
        "texture_dialog": "{name} のテクスチャを選択",
        "connected": "テクスチャが接続されています。解除してから値を変更してください。",
        "error": "エラー",
    },
}

def normalize_name(value: Any) -> str:
    return "".join(character.lower() for character in str(value) if character.isalnum())

def get_property_names(target: Any) -> list[Any]:
    try:
        return list(rt.getPropNames(target))
    except Exception:
        return []

def find_value_property(target: Any, parameter: str) -> Optional[Any]:
    wanted = normalize_name(parameter)
    for prop in get_property_names(target):
        current = normalize_name(prop)
        if current in {wanted, "param" + wanted}:
            return prop
    return None

def find_map_property(target: Any, parameter: str) -> Optional[Any]:
    wanted = normalize_name(parameter) + "map"
    for prop in get_property_names(target):
        current = normalize_name(prop)
        if current in {wanted, "param" + wanted}:
            return prop
    value_prop = find_value_property(target, parameter)
    if value_prop is not None:
        try:
            value = rt.getProperty(target, value_prop)
            if value is not None and rt.isKindOf(value, rt.TextureMap):
                return value_prop
        except Exception:
            pass
    return None

def get_selected_slate_reference() -> Optional[Any]:
    try:
        active_view = int(rt.sme.activeView)
    except Exception:
        return None
    if active_view <= 0:
        return None
    try:
        view = rt.sme.GetView(active_view)
        selected_nodes = view.GetSelectedNodes()
    except Exception:
        return None
    if selected_nodes is None:
        return None
    try:
        count = len(selected_nodes)
    except TypeError:
        try:
            count = int(selected_nodes.count)
        except Exception:
            count = 0
    if count < 1:
        return None
    try:
        node = selected_nodes[0]
    except Exception:
        try:
            node = selected_nodes[1]
        except Exception:
            return None
    for attribute_name in ("reference", "Reference"):
        try:
            return getattr(node, attribute_name)
        except Exception:
            pass
    try:
        return rt.getProperty(node, rt.name("reference"))
    except Exception:
        return None

def _extract_rgb(value: Any) -> tuple[float, float, float]:
    try:
        return (float(value.r), float(value.g), float(value.b))
    except Exception:
        pass
    try:
        return (float(value.x), float(value.y), float(value.z))
    except Exception:
        pass
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return (128.0, 128.0, 128.0)

def max_color_to_qcolor(value: Any) -> QtGui.QColor:
    red, green, blue = _extract_rgb(value)
    try:
        class_name = str(rt.classOf(value)).lower()
    except Exception:
        class_name = type(value).__name__.lower()
    if "color" not in class_name:
        largest = max(abs(red), abs(green), abs(blue))
        if largest <= 1.0001:
            red *= 255.0
            green *= 255.0
            blue *= 255.0
    return QtGui.QColor(
        max(0, min(255, int(round(red)))),
        max(0, min(255, int(round(green)))),
        max(0, min(255, int(round(blue)))),
    )

def qcolor_to_max_color(value: QtGui.QColor) -> Any:
    return rt.color(int(value.red()), int(value.green()), int(value.blue()))

class FloatControl(QtWidgets.QWidget):
    valueChanged = QtCore.Signal(float)
    def __init__(self, label: str, minimum: float, maximum: float, value: float, decimals: int = 3, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.decimals = decimals
        self.scale = 10 ** decimals
        self.label = QtWidgets.QLabel(label)
        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(0.005 if maximum <= 5.0 else 0.1)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(int(round(minimum * self.scale)), int(round(maximum * self.scale)))
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.spin, 0, 1)
        layout.addWidget(self.slider, 1, 0, 1, 2)
        self.spin.valueChanged.connect(self._spin_changed)
        self.slider.valueChanged.connect(self._slider_changed)
        self.set_value(value, emit=False)
    def _spin_changed(self, value: float) -> None:
        blocked = self.slider.blockSignals(True)
        self.slider.setValue(int(round(value * self.scale)))
        self.slider.blockSignals(blocked)
        self.valueChanged.emit(float(value))
    def _slider_changed(self, value: int) -> None:
        float_value = value / self.scale
        blocked = self.spin.blockSignals(True)
        self.spin.setValue(float_value)
        self.spin.blockSignals(blocked)
        self.valueChanged.emit(float(float_value))
    def set_label(self, text: str) -> None:
        self.label.setText(text)
    def set_value(self, value: float, emit: bool = False) -> None:
        blocked_spin = self.spin.blockSignals(not emit)
        blocked_slider = self.slider.blockSignals(not emit)
        self.spin.setValue(float(value))
        self.slider.setValue(int(round(float(value) * self.scale)))
        self.spin.blockSignals(blocked_spin)
        self.slider.blockSignals(blocked_slider)
    def set_enabled(self, enabled: bool) -> None:
        self.spin.setEnabled(enabled)
        self.slider.setEnabled(enabled)

class ColorSwatchButton(QtWidgets.QAbstractButton):
    def __init__(self, color: QtGui.QColor, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self.setMinimumSize(110, 30)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(self._color.name().upper())
    def color(self) -> QtGui.QColor:
        return QtGui.QColor(self._color)
    def set_color(self, color: QtGui.QColor) -> None:
        self._color = QtGui.QColor(color)
        self.setToolTip(self._color.name().upper())
        self.update()
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QtGui.QPen(self.palette().color(QtGui.QPalette.Mid), 1))
        painter.setBrush(QtGui.QBrush(self._color))
        painter.drawRoundedRect(rect, 3, 3)
        text_color = QtGui.QColor(0, 0, 0) if self._color.lightness() > 145 else QtGui.QColor(255, 255, 255)
        painter.setPen(text_color)
        painter.drawText(rect, QtCore.Qt.AlignCenter, self._color.name().upper())

class ColorTextureControl(QtWidgets.QWidget):
    colorChanged = QtCore.Signal(QtGui.QColor)
    loadRequested = QtCore.Signal()
    removeRequested = QtCore.Signal()
    def __init__(self, label: str, color: QtGui.QColor, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.label = QtWidgets.QLabel(label)
        self.color_button = ColorSwatchButton(color)
        self.texture_label = QtWidgets.QLabel()
        self.load_button = QtWidgets.QPushButton()
        self.remove_button = QtWidgets.QPushButton()
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.label)
        top.addStretch(1)
        top.addWidget(self.color_button)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.texture_label, 1)
        bottom.addWidget(self.load_button)
        bottom.addWidget(self.remove_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addLayout(bottom)
        self._color = QtGui.QColor(color)
        self._update_color_style()
        self.color_button.clicked.connect(self._choose_color)
        self.load_button.clicked.connect(self.loadRequested)
        self.remove_button.clicked.connect(self.removeRequested)
    def _choose_color(self) -> None:
        selected = QtWidgets.QColorDialog.getColor(self._color, self)
        if selected.isValid():
            self._color = selected
            self._update_color_style()
            self.colorChanged.emit(QtGui.QColor(selected))
    def _update_color_style(self) -> None:
        self.color_button.set_color(self._color)
    def set_label(self, text: str) -> None:
        self.label.setText(text)
    def set_button_labels(self, load_text: str, remove_text: str) -> None:
        self.load_button.setText(load_text)
        self.remove_button.setText(remove_text)
    def set_color(self, color: QtGui.QColor) -> None:
        self._color = QtGui.QColor(color)
        self._update_color_style()
    def set_texture_text(self, text: str) -> None:
        self.texture_label.setText(text)
    def set_direct_color_enabled(self, enabled: bool) -> None:
        self.color_button.setEnabled(enabled)

class SPToonWindow(QtWidgets.QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.language = "en"
        self.target = None
        self.float_controls: dict[str, FloatControl] = {}
        self.color_controls: dict[str, ColorTextureControl] = {}
        self.section_boxes: dict[str, QtWidgets.QGroupBox] = {}
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setMinimumWidth(560)
        self.resize(620, 950)
        self._build_ui()
        self.apply_language()
        self.refresh_values()
    def tr_text(self, key: str, **kwargs: Any) -> str:
        value = TEXT[self.language][key]
        return value.format(**kwargs) if kwargs else value
    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        language_row = QtWidgets.QHBoxLayout()
        self.language_label = QtWidgets.QLabel()
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItems(["English", "Japanese"])
        language_row.addWidget(self.language_label)
        language_row.addWidget(self.language_combo)
        language_row.addStretch(1)
        root.addLayout(language_row)
        self.help_label = QtWidgets.QLabel()
        root.addWidget(self.help_label)
        button_row = QtWidgets.QHBoxLayout()
        self.load_selected_button = QtWidgets.QPushButton()
        self.refresh_button = QtWidgets.QPushButton()
        button_row.addWidget(self.load_selected_button)
        button_row.addWidget(self.refresh_button)
        root.addLayout(button_row)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)
        content = QtWidgets.QWidget()
        scroll.setWidget(content)
        content_layout = QtWidgets.QVBoxLayout(content)
        line_enable_box = QtWidgets.QGroupBox()
        self.section_boxes["section_line_enable"] = line_enable_box
        line_enable_layout = QtWidgets.QVBoxLayout(line_enable_box)
        self.use_outline_checkbox = QtWidgets.QCheckBox()
        line_enable_layout.addWidget(self.use_outline_checkbox)
        content_layout.addWidget(line_enable_box)
        float_sections = [
            (
                "section_light",
                [
                    ("light_x", "LightPositionX", -20.0, 20.0, 10.0),
                    ("light_y", "LightPositionY", -20.0, 20.0, 10.0),
                    ("light_z", "LightPositionZ", -20.0, 20.0, 10.0),
                ],
            ),
            (
                "section_line",
                [
                    ("outline_thickness", "OutlineThickness", 0.0, 1.0, 0.2),
                    ("outline_blur", "OutlineBlur", 0.0, 5.0, 0.0),
                    ("inline_thickness", "InlineThickness", 0.0, 1.0, 0.3),
                    ("inline_blur", "InlineBlur", 0.0, 5.0, 0.0),
                    ("inline_on_top", "InlineOnTop", 0.0, 1.0, 1.0),
                ],
            ),
            (
                "section_toon",
                [
                    ("toon_2", "ToonParam2", -1.0, 1.0, 0.0),
                    ("toon_3", "ToonParam3", -1.0, 1.0, -1.0),
                    ("toon_4", "ToonParam4", -1.0, 1.0, -1.0),
                    ("toon_5", "ToonParam5", -1.0, 1.0, -1.0),
                    ("toon_6", "ToonParam6", -1.0, 1.0, -1.0),
                    ("toon_7", "ToonParam7", -1.0, 1.0, -1.0),
                    ("toon_blur", "ToonBlur", 0.0, 5.0, 0.0),
                ],
            ),
        ]
        for section_key, items in float_sections:
            box = QtWidgets.QGroupBox()
            self.section_boxes[section_key] = box
            box_layout = QtWidgets.QVBoxLayout(box)
            for label_key, parameter, minimum, maximum, default in items:
                control = FloatControl("", minimum, maximum, default)
                control.setProperty("label_key", label_key)
                control.valueChanged.connect(
                    lambda value, name=parameter: self.set_float_value(name, value)
                )
                self.float_controls[parameter] = control
                box_layout.addWidget(control)
            content_layout.addWidget(box)
        color_box = QtWidgets.QGroupBox()
        self.section_boxes["section_color"] = color_box
        color_layout = QtWidgets.QVBoxLayout(color_box)
        color_items = [
            ("base_color", "BaseColor", QtGui.QColor(255, 255, 255)),
            ("outline_color", "OutlineColor", QtGui.QColor(0, 76, 255)),
            ("inline_color", "InlineColor", QtGui.QColor(93, 7, 0)),
            ("toon_color_2", "ToonColor2", QtGui.QColor(141, 141, 141)),
            ("toon_color_3", "ToonColor3", QtGui.QColor(59, 59, 59)),
            ("toon_color_4", "ToonColor4", QtGui.QColor(24, 24, 24)),
            ("toon_color_5", "ToonColor5", QtGui.QColor(18, 18, 18)),
            ("toon_color_6", "ToonColor6", QtGui.QColor(6, 6, 6)),
            ("toon_color_7", "ToonColor7", QtGui.QColor(4, 4, 4)),
        ]
        for label_key, parameter, default in color_items:
            control = ColorTextureControl("", default)
            control.setProperty("label_key", label_key)
            control.colorChanged.connect(
                lambda value, name=parameter: self.set_color_value(name, value)
            )
            control.loadRequested.connect(
                lambda name=parameter: self.load_texture(name)
            )
            control.removeRequested.connect(
                lambda name=parameter: self.remove_texture(name)
            )
            self.color_controls[parameter] = control
            color_layout.addWidget(control)
        content_layout.addWidget(color_box)
        curvature_box = QtWidgets.QGroupBox()
        self.section_boxes["section_curvature"] = curvature_box
        curvature_layout = QtWidgets.QHBoxLayout(curvature_box)
        self.curvature_texture_label = QtWidgets.QLabel()
        self.curvature_load_button = QtWidgets.QPushButton()
        self.curvature_remove_button = QtWidgets.QPushButton()
        curvature_layout.addWidget(self.curvature_texture_label, 1)
        curvature_layout.addWidget(self.curvature_load_button)
        curvature_layout.addWidget(self.curvature_remove_button)
        content_layout.addWidget(curvature_box)
        self.blur_help_label = QtWidgets.QLabel()
        self.blur_help_label.setWordWrap(True)
        content_layout.addWidget(self.blur_help_label)
        content_layout.addStretch(1)
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.load_selected_button.clicked.connect(self.load_selected_osl)
        self.refresh_button.clicked.connect(self.refresh_values)
        self.use_outline_checkbox.toggled.connect(self.set_use_outline)
        self.curvature_load_button.clicked.connect(
            lambda: self.load_texture("Curvature")
        )
        self.curvature_remove_button.clicked.connect(
            lambda: self.remove_texture("Curvature")
        )
    def change_language(self, index: int) -> None:
        self.language = "ja" if index == 1 else "en"
        self.apply_language()
        self.refresh_values()
    def apply_language(self) -> None:
        self.setWindowTitle(self.tr_text("title"))
        self.language_label.setText(self.tr_text("language"))
        blocked = self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItems(
            [self.tr_text("english"), self.tr_text("japanese")]
        )
        self.language_combo.setCurrentIndex(1 if self.language == "ja" else 0)
        self.language_combo.blockSignals(blocked)
        self.help_label.setText(self.tr_text("select_help"))
        self.load_selected_button.setText(self.tr_text("load_selected"))
        self.refresh_button.setText(self.tr_text("refresh"))
        self.use_outline_checkbox.setText(self.tr_text("use_outline"))
        self.blur_help_label.setText(self.tr_text("blur_help"))
        for section_key, box in self.section_boxes.items():
            box.setTitle(self.tr_text(section_key))
        for control in self.float_controls.values():
            control.set_label(self.tr_text(control.property("label_key")))
        for control in self.color_controls.values():
            control.set_label(self.tr_text(control.property("label_key")))
            control.set_button_labels(
                self.tr_text("load"),
                self.tr_text("remove"),
            )
        self.curvature_load_button.setText(self.tr_text("load"))
        self.curvature_remove_button.setText(self.tr_text("remove"))
    def show_error(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, self.tr_text("error"), message)
    def load_selected_osl(self) -> None:
        selected = get_selected_slate_reference()
        if selected is None:
            self.show_error(self.tr_text("selection_missing"))
            return
        required_property = find_value_property(selected, "ToonParam2")
        if required_property is None:
            self.show_error(self.tr_text("not_osl"))
            return
        self.target = selected
        self.refresh_values()
    def property_value(self, parameter: str, default: Any) -> Any:
        if self.target is None:
            return default
        prop = find_value_property(self.target, parameter)
        if prop is None:
            return default
        try:
            return rt.getProperty(self.target, prop)
        except Exception:
            return default
    def set_property_value(self, parameter: str, value: Any) -> bool:
        if self.target is None:
            return False
        prop = find_value_property(self.target, parameter)
        if prop is None:
            self.show_error(self.tr_text("property_missing", name=parameter))
            return False
        try:
            rt.setProperty(self.target, prop, value)
            rt.redrawViews()
            return True
        except Exception as error:
            self.show_error(str(error))
            return False
    def map_value(self, parameter: str) -> Any:
        if self.target is None:
            return None
        prop = find_map_property(self.target, parameter)
        if prop is None:
            return None
        try:
            return rt.getProperty(self.target, prop)
        except Exception:
            return None
    def set_float_value(self, parameter: str, value: float) -> None:
        if self.target is None:
            return
        if self.map_value(parameter) is not None:
            self.show_error(self.tr_text("connected"))
            self.refresh_values()
            return
        self.set_property_value(parameter, float(value))
    def set_use_outline(self, checked: bool) -> None:
        if self.target is None:
            return
        self.set_property_value("UseOutline", 1 if checked else 0)
    def set_color_value(self, parameter: str, value: QtGui.QColor) -> None:
        if self.target is None:
            return
        if self.map_value(parameter) is not None:
            self.show_error(self.tr_text("connected"))
            self.refresh_values()
            return
        prop = find_value_property(self.target, parameter)
        if prop is None:
            self.show_error(self.tr_text("property_missing", name=parameter))
            return
        before = rt.getProperty(self.target, prop)
        new_color = qcolor_to_max_color(value)
        try:
            rt.setProperty(self.target, prop, new_color)
            try:
                rt.notifyDependents(self.target)
            except Exception:
                pass
            try:
                rt.redrawViews()
            except Exception:
                pass
            try:
                rt.completeRedraw()
            except Exception:
                pass
        except Exception as error:
            self.show_error("Color assignment failed for {}\nProperty: {}\nBefore: {} / {}\nInput: {} / {}\n\n{}".format(parameter, prop, before, rt.classOf(before), new_color, rt.classOf(new_color), error))
            return
        after = rt.getProperty(self.target, prop)
        if str(before) == str(after) and before != new_color:
            self.show_error("The color property did not change.\nParameter: {}\nBefore: {}\nAfter: {}".format(parameter, before, after))
            return
        self.refresh_values()
    def load_texture(self, parameter: str) -> None:
        if self.target is None:
            self.show_error(self.tr_text("selection_missing"))
            return
        map_prop = find_map_property(self.target, parameter)
        if map_prop is None:
            self.show_error(self.tr_text("map_property_missing", name=parameter))
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr_text("texture_dialog", name=parameter),
            "",
            "Image Files (*.png *.tif *.tiff *.jpg *.jpeg *.exr *.tga *.bmp *.tx);;All Files (*.*)"
        )
        if not path:
            return
        try:
            bitmap_map = rt.Bitmaptexture(filename=path)
            bitmap_map.name = "SP_{}_Texture".format(parameter)
            rt.setProperty(self.target, map_prop, bitmap_map)
            rt.redrawViews()
        except Exception as error:
            self.show_error(str(error))
            return
        self.refresh_values()
    def remove_texture(self, parameter: str) -> None:
        if self.target is None:
            return
        map_prop = find_map_property(self.target, parameter)
        if map_prop is None:
            return
        try:
            rt.setProperty(self.target, map_prop, None)
            rt.redrawViews()
        except Exception as error:
            self.show_error(str(error))
            return
        self.refresh_values()
    def texture_display_name(self, parameter: str) -> str:
        texture = self.map_value(parameter)
        if texture is None:
            return self.tr_text("texture_none")
        path = ""
        for prop_name in ("filename", "fileName"):
            try:
                path = str(rt.getProperty(texture, rt.name(prop_name)) or '')
            except Exception:
                path = ""
            if path:
                break
        name = os.path.basename(path) if path else str(getattr(texture, "name", texture))
        return self.tr_text("texture_name", name=name)
    def refresh_values(self) -> None:
        if self.target is None:
            self.status_label.setText(self.tr_text("target_none"))
            self.use_outline_checkbox.setEnabled(False)
            for control in self.float_controls.values():
                control.set_enabled(False)
            for control in self.color_controls.values():
                control.set_direct_color_enabled(False)
                control.set_texture_text(self.tr_text("texture_none"))
            self.curvature_texture_label.setText(self.tr_text("texture_none"))
            return
        target_name = str(getattr(self.target, 'name', self.target))
        self.status_label.setText(self.tr_text("target", name=target_name))
        blocked = self.use_outline_checkbox.blockSignals(True)
        self.use_outline_checkbox.setChecked(bool(int(self.property_value("UseOutline", 1))))
        self.use_outline_checkbox.blockSignals(blocked)
        self.use_outline_checkbox.setEnabled(True)
        defaults = {
            "LightPositionX": 10.0,
            "LightPositionY": 10.0,
            "LightPositionZ": 10.0,
            "OutlineThickness": 0.2,
            "OutlineBlur": 0.0,
            "InlineThickness": 0.3,
            "InlineBlur": 0.0,
            "InlineOnTop": 1.0,
            "ToonParam2": 0.0,
            "ToonParam3": -1.0,
            "ToonParam4": -1.0,
            "ToonParam5": -1.0,
            "ToonParam6": -1.0,
            "ToonParam7": -1.0,
            "ToonBlur": 0.0,
        }
        for parameter, control in self.float_controls.items():
            value = self.property_value(parameter, defaults[parameter])
            try:
                control.set_value(float(value), emit=False)
            except Exception:
                control.set_value(defaults[parameter], emit=False)
            control.set_enabled(self.map_value(parameter) is None)
        color_defaults = {
            "BaseColor": rt.color(255, 255, 255),
            "OutlineColor": rt.color(0, 76, 255),
            "InlineColor": rt.color(93, 7, 0),
            "ToonColor2": rt.color(141, 141, 141),
            "ToonColor3": rt.color(59, 59, 59),
            "ToonColor4": rt.color(24, 24, 24),
            "ToonColor5": rt.color(18, 18, 18),
            "ToonColor6": rt.color(6, 6, 6),
            "ToonColor7": rt.color(4, 4, 4),
        }
        for parameter, control in self.color_controls.items():
            value = self.property_value(parameter, color_defaults[parameter])
            control.set_color(max_color_to_qcolor(value))
            has_texture = self.map_value(parameter) is not None
            control.set_direct_color_enabled(not has_texture)
            control.set_texture_text(self.texture_display_name(parameter))
        self.curvature_texture_label.setText(self.texture_display_name("Curvature"))

def close_existing_window() -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT_NAME:
            widget.close()
            widget.deleteLater()

def show_sp_toon_window() -> SPToonWindow:
    global SP_TOON_WINDOW
    close_existing_window()
    SP_TOON_WINDOW = SPToonWindow()
    SP_TOON_WINDOW.show()
    SP_TOON_WINDOW.raise_()
    SP_TOON_WINDOW.activateWindow()
    return SP_TOON_WINDOW

try:
    show_sp_toon_window()
except Exception:
    traceback.print_exc()
    raise