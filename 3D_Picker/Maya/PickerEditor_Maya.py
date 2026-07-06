# -*- coding: utf-8 -*-
import json
import os
import math
import maya.cmds as cmds
from PySide6 import QtWidgets, QtCore, QtGui

# --- スタイル設定 ---
STYLESHEET = """
    QWidget { background-color: #2b2b2b; color: #dcdcdc; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
    QGroupBox { border: 1px solid #3a3a3a; margin-top: 10px; padding-top: 10px; font-weight: bold; }
    QPushButton { background-color: #3f3f3f; border: 1px solid #555; border-radius: 3px; padding: 2px; color: #ffffff; }
    QPushButton:hover { background-color: #4f4f4f; }
    QLineEdit { background-color: #1a1a1a; color: #ffffff; border: 1px solid #333; padding: 2px; }
    QLineEdit:disabled { color: #666; background-color: #222; }
    QComboBox { background-color: #1a1a1a; color: #ffffff; border: 1px solid #333; }
    QComboBox:disabled { color: #666; }
    QListWidget { background-color: #1a1a1a; border: 1px solid #333; outline: none; }
    QListWidget::item:selected { background-color: #3d5a73; }
    QLabel#DragLabel { color: #888; font-weight: bold; }
    QLabel#DragLabel:hover { color: #aaa; }
"""

SHAPE_TYPES = [
    "rect", "rect_fill", "circle", "circle_fill", "cross",
    "diamond", "diamond_fill", "tri_up", "tri_up_fill",
    "tri_down", "tri_down_fill", "tri_left", "tri_left_fill",
    "tri_right", "tri_right_fill", "double_circle", "star", "star_fill"
]

# ------------------------------------------------------------------ #
#  アトリビュート解決
# ------------------------------------------------------------------ #

def _resolve_attr(node, attr):
    """
    attr をそのまま試し、失敗したら nice name として listAttr でスキャンして
    一致する内部名を返す。どちらでも見つからなければ None。
    """
    try:
        cmds.getAttr(f"{node}.{attr}")
        return attr
    except Exception:
        pass
    try:
        for a in (cmds.listAttr(node, userDefined=True) or []):
            try:
                if cmds.attributeQuery(a, node=node, niceName=True) == attr:
                    return a
            except Exception:
                pass
            if a == attr:
                return a
    except Exception:
        pass
    return None

# ------------------------------------------------------------------ #
#  アクション実行
# ------------------------------------------------------------------ #

def execute_action(action, targets):
    """
    action dict と対象ノードリストを受け取り処理を実行する。
    attr には内部名・nice name どちらを書いても動作する。
    戻り値: (成功 True/False, エラーメッセージ or None)
    """
    if not action:
        return False, "アクションが定義されていません"
    atype = action.get("type", "attribute_toggle")
    if atype == "attribute_toggle":
        attr   = action.get("attr", "")
        values = action.get("values", [0, 1])
        if not attr:
            return False, "attr が空です"
        errors = []
        for target in targets:
            resolved = _resolve_attr(target, attr)
            if resolved is None:
                errors.append(f"{target}: アトリビュート '{attr}' が見つかりません")
                continue
            full = f"{target}.{resolved}"
            try:
                val = cmds.getAttr(full)
                mid = (float(values[0]) + float(values[1])) / 2.0
                new_val = values[0] if float(val) >= mid else values[1]
                cmds.setAttr(full, new_val)
            except Exception as e:
                errors.append(str(e))
        return (False, "\n".join(errors)) if errors else (True, None)
    return False, f"不明なアクションタイプ: {atype}"

# ------------------------------------------------------------------ #
#  表示条件評価
# ------------------------------------------------------------------ #

def evaluate_visibility(items):
    """
    各リージョンの visible_when 条件を評価し item.visible を更新する。
    visible_when が None のリージョンは常に visible=True。
    Maya のアトリビュートが取得できない場合も visible=True とする。
    """
    for item in items:
        vw = item.visible_when
        if not vw:
            item.visible = True
            continue
        target = vw.get("target", "")
        attr   = vw.get("attr", "")
        value  = vw.get("value", 0)
        if not target or not attr:
            item.visible = True
            continue
        resolved = _resolve_attr(target, attr)
        if resolved is None:
            item.visible = True
            continue
        try:
            val = cmds.getAttr(f"{target}.{resolved}")
            item.visible = (abs(float(val) - float(value)) < 0.001)
        except Exception:
            item.visible = True

# ------------------------------------------------------------------ #
#  図形描画
# ------------------------------------------------------------------ #

def draw_shape(painter, t, sr, color, is_selected):
    pen_width = 4 if is_selected else 1
    painter.setPen(QtGui.QPen(color, pen_width))
    brush = QtGui.QBrush(color) if "_fill" in t else QtCore.Qt.NoBrush

    if t in ("rect", "rect_fill"):
        if "_fill" in t: painter.fillRect(sr, color)
        painter.drawRect(sr)
    elif t in ("circle", "circle_fill"):
        if "_fill" in t:
            painter.setBrush(brush); painter.drawEllipse(sr); painter.setBrush(QtCore.Qt.NoBrush)
        else:
            painter.drawEllipse(sr)
    elif t == "cross":
        cx, cy = sr.center().x(), sr.center().y()
        painter.drawLine(sr.left(), cy, sr.right(), cy)
        painter.drawLine(cx, sr.top(), cx, sr.bottom())
    elif "diamond" in t:
        poly = QtGui.QPolygon([
            QtCore.QPoint(sr.center().x(), sr.top()),
            QtCore.QPoint(sr.right(), sr.center().y()),
            QtCore.QPoint(sr.center().x(), sr.bottom()),
            QtCore.QPoint(sr.left(), sr.center().y())
        ])
        if "_fill" in t: painter.setBrush(brush)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    elif "tri_" in t:
        if   "up"    in t: pts = [sr.bottomLeft(), sr.bottomRight(), QtCore.QPoint(sr.center().x(), sr.top())]
        elif "down"  in t: pts = [sr.topLeft(),    sr.topRight(),    QtCore.QPoint(sr.center().x(), sr.bottom())]
        elif "left"  in t: pts = [sr.topRight(),   sr.bottomRight(), QtCore.QPoint(sr.left(),        sr.center().y())]
        elif "right" in t: pts = [sr.topLeft(),    sr.bottomLeft(),  QtCore.QPoint(sr.right(),       sr.center().y())]
        poly = QtGui.QPolygon(pts)
        if "_fill" in t: painter.setBrush(brush)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    elif t == "double_circle":
        painter.drawEllipse(sr)
        inner = sr.adjusted(sr.width()*0.2, sr.height()*0.2, -sr.width()*0.2, -sr.height()*0.2)
        painter.drawEllipse(inner)
    elif "star" in t:
        poly = QtGui.QPolygon()
        center = sr.center(); ro = min(sr.width(), sr.height()) / 2; ri = ro / 2.5
        for j in range(10):
            r = ro if j % 2 == 0 else ri
            angle = (j * 36 - 90) * math.pi / 180
            poly << QtCore.QPoint(center.x() + r * math.cos(angle), center.y() + r * math.sin(angle))
        if "_fill" in t: painter.setBrush(brush)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    else:
        painter.drawRect(sr)

def create_shape_icon(shape_type, color=QtCore.Qt.white):
    pixmap = QtGui.QPixmap(20, 20); pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap); painter.setRenderHint(QtGui.QPainter.Antialiasing)
    draw_shape(painter, shape_type, QtCore.QRect(2, 2, 16, 16), QtGui.QColor(color), False)
    painter.end(); return QtGui.QIcon(pixmap)

# ------------------------------------------------------------------ #
#  DragLabel
# ------------------------------------------------------------------ #

class DragLabel(QtWidgets.QLabel):
    def __init__(self, text, target_spin, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DragLabel"); self.target_spin = target_spin
        self.setCursor(QtCore.Qt.SizeHorCursor); self.last_x = 0

    def mousePressEvent(self, event): self.last_x = event.globalPos().x()
    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            dx = event.globalPos().x() - self.last_x
            self.target_spin.setValue(self.target_spin.value() + dx)
            self.last_x = event.globalPos().x()

# ------------------------------------------------------------------ #
#  ClickRegion
# ------------------------------------------------------------------ #

class ClickRegion:
    """
    action      : 右クリックで実行するアクション dict（None で無効）
    visible_when: 表示条件 dict（None で常に表示）
                  例: {"target": "arm_sw", "attr": "ikFkSwitch", "value": 0}
    visible     : evaluate_visibility() が更新するランタイムフラグ
    """
    def __init__(self, names, rect_data, color, shape_type="rect",
                 next_json="", action=None, visible_when=None):
        self.names        = names if isinstance(names, list) else [names]
        self.rect         = QtCore.QRect(*rect_data)
        self.color        = QtGui.QColor(*color) if isinstance(color, list) else QtGui.QColor(color)
        self.shape_type   = shape_type
        self.next_json    = next_json
        self.action       = action        # dict or None
        self.visible_when = visible_when  # dict or None
        self.visible      = True          # ランタイムフラグ

    @property
    def has_switch(self):
        return self.action is not None

    @property
    def has_visibility(self):
        return self.visible_when is not None

    @property
    def select_names(self):
        return list(self.names)

# ------------------------------------------------------------------ #
#  ListColorItem
# ------------------------------------------------------------------ #

class ListColorItem(QtWidgets.QWidget):
    color_changed        = QtCore.Signal(int, QtGui.QColor)
    rect_changed         = QtCore.Signal(int, str, int)
    names_changed        = QtCore.Signal(int, list)
    type_changed         = QtCore.Signal(int, str)
    next_json_changed    = QtCore.Signal(int, str)
    action_changed       = QtCore.Signal(int, object)
    visible_when_changed = QtCore.Signal(int, object)
    layout_changed       = QtCore.Signal(int)

    def __init__(self, names, rect, color, shape_type, next_json,
                 action, visible_when, index, parent=None):
        super().__init__(parent)
        self.index = index; self.block_signals = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 5, 2); outer.setSpacing(1)

        # ── 上段（既存レイアウト完全保持） ────────────────────────────
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0); top.setSpacing(3)
        top.addSpacing(40)

        display_text = os.path.basename(next_json) if next_json else ", ".join(names)
        self.names_edit = QtWidgets.QLineEdit(display_text)
        self.names_edit.editingFinished.connect(self.on_ui_data_changed)
        top.addWidget(self.names_edit, 1)

        self.btn_path = QtWidgets.QPushButton("..."); self.btn_path.setFixedWidth(22)
        self.btn_path.clicked.connect(self.browse_path); top.addWidget(self.btn_path)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setIconSize(QtCore.QSize(16, 16)); self.type_combo.setFixedWidth(55)
        for st in SHAPE_TYPES: self.type_combo.addItem(create_shape_icon(st, color), "", st)
        if shape_type in SHAPE_TYPES: self.type_combo.setCurrentIndex(SHAPE_TYPES.index(shape_type))
        self.type_combo.currentIndexChanged.connect(self.on_type_ui_changed)
        top.addWidget(self.type_combo)

        self.spins = {}; self.labels = []
        for lbl_t, key in [("X","x"),("Y","y"),("W","w"),("H","h")]:
            sb = QtWidgets.QSpinBox(); sb.setButtonSymbols(QtWidgets.QSpinBox.NoButtons)
            sb.setRange(-20000, 20000); sb.setFixedWidth(40)
            sb.valueChanged.connect(lambda val, k=key: self.on_rect_ui_changed(k, val))
            lbl = DragLabel(lbl_t, sb); lbl.setFixedWidth(12)
            self.labels.append(lbl); top.addWidget(lbl); top.addWidget(sb); self.spins[key] = sb

        self.sync_spins(rect)
        self.color_btn = QtWidgets.QPushButton("■"); self.color_btn.setFixedSize(20, 20)
        self.set_btn_color(color); self.color_btn.clicked.connect(self.pick_new_color)
        top.addWidget(self.color_btn)

        # Action トグルボタン
        self.btn_action_toggle = QtWidgets.QPushButton("▶ Action")
        self.btn_action_toggle.setCheckable(True); self.btn_action_toggle.setFixedWidth(65)
        self.btn_action_toggle.setStyleSheet(
            "QPushButton { color: #777; font-size: 11px; }"
            "QPushButton:checked { color: #ffcc44; border-color: #776622; }")
        self.btn_action_toggle.toggled.connect(self._on_action_toggle)
        top.addWidget(self.btn_action_toggle)

        # Visible When トグルボタン
        self.btn_vis_toggle = QtWidgets.QPushButton("▶ Visible")
        self.btn_vis_toggle.setCheckable(True); self.btn_vis_toggle.setFixedWidth(65)
        self.btn_vis_toggle.setStyleSheet(
            "QPushButton { color: #777; font-size: 11px; }"
            "QPushButton:checked { color: #66ccff; border-color: #224466; }")
        self.btn_vis_toggle.toggled.connect(self._on_vis_toggle)
        top.addWidget(self.btn_vis_toggle)

        outer.addLayout(top)

        # ── Action パネル ─────────────────────────────────────────────
        self.action_panel = QtWidgets.QFrame()
        self.action_panel.setStyleSheet(
            "QFrame { background-color: #1e1e1e; border-top: 1px solid #3a3a3a; }")
        ap = QtWidgets.QHBoxLayout(self.action_panel)
        ap.setContentsMargins(44, 3, 5, 3); ap.setSpacing(4)

        ap.addWidget(QtWidgets.QLabel("Attr:"))
        self.action_attr_edit = QtWidgets.QLineEdit()
        self.action_attr_edit.setPlaceholderText("attr name"); self.action_attr_edit.setFixedWidth(130)
        self.action_attr_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_attr_edit)
        ap.addWidget(QtWidgets.QLabel("Val:"))
        self.action_val0_edit = QtWidgets.QLineEdit("0"); self.action_val0_edit.setFixedWidth(35)
        self.action_val0_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_val0_edit)
        ap.addWidget(QtWidgets.QLabel("⇄"))
        self.action_val1_edit = QtWidgets.QLineEdit("1"); self.action_val1_edit.setFixedWidth(35)
        self.action_val1_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_val1_edit)
        ap.addStretch()
        self.action_panel.setVisible(False)
        outer.addWidget(self.action_panel)

        # ── Visible When パネル ───────────────────────────────────────
        self.vis_panel = QtWidgets.QFrame()
        self.vis_panel.setStyleSheet(
            "QFrame { background-color: #1a2030; border-top: 1px solid #224466; }")
        vp = QtWidgets.QHBoxLayout(self.vis_panel)
        vp.setContentsMargins(44, 3, 5, 3); vp.setSpacing(4)

        vp.addWidget(QtWidgets.QLabel("Target:"))
        self.vis_target_edit = QtWidgets.QLineEdit()
        self.vis_target_edit.setPlaceholderText("node name"); self.vis_target_edit.setFixedWidth(120)
        self.vis_target_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_target_edit)
        vp.addWidget(QtWidgets.QLabel("Attr:"))
        self.vis_attr_edit = QtWidgets.QLineEdit()
        self.vis_attr_edit.setPlaceholderText("attr name"); self.vis_attr_edit.setFixedWidth(120)
        self.vis_attr_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_attr_edit)
        vp.addWidget(QtWidgets.QLabel("="))
        self.vis_value_edit = QtWidgets.QLineEdit("0"); self.vis_value_edit.setFixedWidth(35)
        self.vis_value_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_value_edit)
        vp.addStretch()
        self.vis_panel.setVisible(False)
        outer.addWidget(self.vis_panel)

        # 初期値ロード
        if action:       self._load_action(action)
        if visible_when: self._load_vis(visible_when)

    # ── Action パネル ────────────────────────────────────────────────

    def _on_action_toggle(self, checked):
        self.action_panel.setVisible(checked)
        self.btn_action_toggle.setText("▼ Action" if checked else "▶ Action")
        if not checked: self.action_changed.emit(self.index, None)
        else:           self._on_action_changed()
        self.layout_changed.emit(self.index)

    def _load_action(self, action):
        self.block_signals = True
        self.action_attr_edit.setText(action.get("attr", ""))
        vals = action.get("values", [0, 1])
        self.action_val0_edit.setText(str(vals[0]) if len(vals) > 0 else "0")
        self.action_val1_edit.setText(str(vals[1]) if len(vals) > 1 else "1")
        self.block_signals = False
        self.btn_action_toggle.setChecked(True)

    def _on_action_changed(self, *args):
        if self.block_signals: return
        def _num(s):
            try: v = float(s); return int(v) if v == int(v) else v
            except Exception: return 0
        action = {
            "type":   "attribute_toggle",
            "attr":   self.action_attr_edit.text().strip(),
            "values": [_num(self.action_val0_edit.text()), _num(self.action_val1_edit.text())]
        }
        self.action_changed.emit(self.index, action)

    # ── Visible When パネル ───────────────────────────────────────────

    def _on_vis_toggle(self, checked):
        self.vis_panel.setVisible(checked)
        self.btn_vis_toggle.setText("▼ Visible" if checked else "▶ Visible")
        if not checked: self.visible_when_changed.emit(self.index, None)
        else:           self._on_vis_changed()
        self.layout_changed.emit(self.index)

    def _load_vis(self, vw):
        self.block_signals = True
        self.vis_target_edit.setText(vw.get("target", ""))
        self.vis_attr_edit.setText(vw.get("attr", ""))
        self.vis_value_edit.setText(str(vw.get("value", 0)))
        self.block_signals = False
        self.btn_vis_toggle.setChecked(True)

    def _on_vis_changed(self, *args):
        if self.block_signals: return
        def _num(s):
            try: v = float(s); return int(v) if v == int(v) else v
            except Exception: return 0
        vw = {
            "target": self.vis_target_edit.text().strip(),
            "attr":   self.vis_attr_edit.text().strip(),
            "value":  _num(self.vis_value_edit.text())
        }
        self.visible_when_changed.emit(self.index, vw)

    # ── 既存ヘルパー ─────────────────────────────────────────────────

    def browse_path(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select JSON", "", "*.json")
        if p: rel = os.path.basename(p); self.names_edit.setText(rel); self.on_ui_data_changed()

    def on_ui_data_changed(self):
        text = self.names_edit.text()
        if text.endswith(".json"):
            rel = os.path.basename(text)
            if text != rel: self.names_edit.setText(rel)
            self.next_json_changed.emit(self.index, rel)
            self.names_changed.emit(self.index, [])
        else:
            self.next_json_changed.emit(self.index, "")
            self.names_changed.emit(self.index, [n.strip() for n in text.split(",") if n.strip()])

    def sync_spins(self, rect):
        self.block_signals = True
        self.spins["x"].setValue(rect.x()); self.spins["y"].setValue(rect.y())
        self.spins["w"].setValue(rect.width()); self.spins["h"].setValue(rect.height())
        self.block_signals = False

    def on_rect_ui_changed(self, k, v):
        if not self.block_signals: self.rect_changed.emit(self.index, k, v)

    def on_type_ui_changed(self, idx):
        if not self.block_signals: self.type_changed.emit(self.index, SHAPE_TYPES[idx])

    def set_btn_color(self, c):
        self.current_color = c
        self.color_btn.setStyleSheet(f"color: {c.name()}; background-color: #2b2b2b; border: 1px solid #555;")
        self.block_signals = True
        for i in range(self.type_combo.count()):
            self.type_combo.setItemIcon(i, create_shape_icon(SHAPE_TYPES[i], c))
        self.block_signals = False

    def pick_new_color(self):
        c = QtWidgets.QColorDialog.getColor(self.current_color, self, "Color", QtWidgets.QColorDialog.ShowAlphaChannel)
        if c.isValid(): self.set_btn_color(c); self.color_changed.emit(self.index, c)

    def set_edit_enabled(self, e):
        self.names_edit.setEnabled(e); self.color_btn.setEnabled(e)
        self.type_combo.setEnabled(e); self.btn_path.setEnabled(e)
        for sb in self.spins.values(): sb.setEnabled(e)
        for lb in self.labels: lb.setEnabled(e)
        for w in (self.action_attr_edit, self.action_val0_edit, self.action_val1_edit,
                  self.vis_target_edit, self.vis_attr_edit, self.vis_value_edit):
            w.setEnabled(e)

# ------------------------------------------------------------------ #
#  DraggableListWidget
# ------------------------------------------------------------------ #

class DraggableListWidget(QtWidgets.QListWidget):
    order_changed = QtCore.Signal()
    def dropEvent(self, event):
        super().dropEvent(event); self.order_changed.emit()

# ------------------------------------------------------------------ #
#  ImageCanvas
# ------------------------------------------------------------------ #

class ImageCanvas(QtWidgets.QLabel):
    request_deselect     = QtCore.Signal(bool)
    region_clicked       = QtCore.Signal(int, bool)
    region_right_clicked = QtCore.Signal(int)
    multi_region_moved   = QtCore.Signal(list, int, int)
    file_dropped         = QtCore.Signal(str)
    pan_requested        = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_pos = None; self.temp_rect = QtCore.QRect()
        self.registered_items = []; self.mode = "setup"
        self.scale = 1.0; self.pixmap_original = None; self.last_pan_pos = None
        self.selected_indices = set(); self.is_dragging_items = False; self.drag_start_pt = None
        self.setMouseTracking(True); self.setAcceptDrops(True); self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("background-color: #1a1a1a; color: #555; border: 2px dashed #333;")
        self.setText("DROP IMAGE OR JSON")

    def set_image(self, pix):
        self.pixmap_original = pix; self.scale = 1.0; self.update_canvas_size()
        self.setStyleSheet("background-color: #111; border: none;")
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

    def update_canvas_size(self):
        if self.pixmap_original:
            ns = self.pixmap_original.size() * self.scale
            self.setPixmap(self.pixmap_original.scaled(
                ns, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.setFixedSize(ns)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self); painter.setRenderHint(QtGui.QPainter.Antialiasing)
        for i, item in enumerate(self.registered_items):
            sr = QtCore.QRect(
                item.rect.x() * self.scale, item.rect.y() * self.scale,
                item.rect.width() * self.scale, item.rect.height() * self.scale)

            if self.mode == "selector":
                if not item.visible:
                    continue
                draw_shape(painter, item.shape_type, sr, item.color, i in self.selected_indices)
                if item.has_switch: self._draw_switch_badge(painter, sr)
            else:
                if item.has_visibility and not item.visible:
                    painter.setOpacity(0.25)
                    draw_shape(painter, item.shape_type, sr, item.color, i in self.selected_indices)
                    if item.has_switch: self._draw_switch_badge(painter, sr)
                    painter.setOpacity(1.0)
                    continue
                draw_shape(painter, item.shape_type, sr, item.color, i in self.selected_indices)
                if item.has_switch: self._draw_switch_badge(painter, sr)

        if self.mode == "setup" and not self.temp_rect.isNull():
            painter.setPen(QtGui.QPen(QtCore.Qt.red, 1, QtCore.Qt.DashLine))
            painter.drawRect(self.temp_rect)

    def _draw_switch_badge(self, painter, sr):
        """右上: アクションバッジ（黄）"""
        bw = max(10, int(sr.width() * 0.28)); bh = max(8, int(sr.height() * 0.28))
        badge_rect = QtCore.QRect(sr.right() - bw + 1, sr.top() - 1, bw, bh)
        painter.save()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(255, 180, 0, 200))
        painter.drawRoundedRect(badge_rect, 2, 2)
        painter.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1))
        font = painter.font(); font.setPixelSize(max(7, bh - 2)); font.setBold(True)
        painter.setFont(font)
        painter.drawText(badge_rect, QtCore.Qt.AlignCenter, "⇄")
        painter.restore()

    def _hit_test(self, raw):
        """クリック判定: セレクターモードでは非表示アイテムを除外する"""
        for i, r in enumerate(self.registered_items):
            if self.mode == "selector" and not r.visible:
                continue
            if r.rect.contains(raw):
                return i
        return -1

    def mousePressEvent(self, event):
        mod = event.modifiers(); pos = event.pos()
        raw = pos / self.scale
        is_mod = bool(mod & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier))

        if event.button() == QtCore.Qt.MiddleButton or \
                (event.button() == QtCore.Qt.LeftButton and mod & QtCore.Qt.AltModifier):
            self.last_pan_pos = event.globalPos(); self.setCursor(QtCore.Qt.ClosedHandCursor); return

        idx = self._hit_test(raw)

        # ---- 右クリック ----
        if event.button() == QtCore.Qt.RightButton:
            if self.mode == "selector" and idx != -1:
                self.region_right_clicked.emit(idx)
            return

        # ---- 左クリック ----
        if idx != -1:
            item = self.registered_items[idx]
            if self.mode == "selector" and item.next_json and not is_mod:
                target = item.next_json
                if not os.path.isabs(target) and self.window().current_json_path:
                    target = os.path.join(os.path.dirname(self.window().current_json_path), target)
                self.window().load_json(target); return

            if self.mode == "setup" and not is_mod:
                if idx not in self.selected_indices: self.region_clicked.emit(idx, False)
                self.is_dragging_items = True; self.drag_start_pt = raw
            else:
                self.region_clicked.emit(idx, is_mod)
                if self.mode == "selector":
                    sel = item.select_names
                    if sel: cmds.select(sel, toggle=is_mod, replace=not is_mod)
        else:
            self.start_pos = pos if self.mode == "setup" else None
            self.request_deselect.emit(is_mod)
            if self.mode == "selector" and not is_mod: cmds.select(cl=True)

    def mouseMoveEvent(self, event):
        if self.last_pan_pos:
            d = event.globalPos() - self.last_pan_pos
            self.pan_requested.emit(d); self.last_pan_pos = event.globalPos(); return
        if self.is_dragging_items and self.drag_start_pt:
            raw = event.pos() / self.scale
            dx, dy = int(raw.x() - self.drag_start_pt.x()), int(raw.y() - self.drag_start_pt.y())
            if dx != 0 or dy != 0:
                self.multi_region_moved.emit(list(self.selected_indices), dx, dy)
                self.drag_start_pt = raw; return
        if self.mode == "setup" and self.start_pos:
            self.temp_rect = QtCore.QRect(self.start_pos, event.pos()).normalized(); self.update()

    def mouseReleaseEvent(self, event):
        self.start_pos = self.last_pan_pos = None
        self.is_dragging_items = False; self.setCursor(QtCore.Qt.ArrowCursor); self.update()

    def wheelEvent(self, event):
        self.scale *= 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale = max(0.1, min(self.scale, 10.0)); self.update_canvas_size(); self.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls(): self.file_dropped.emit(u.toLocalFile())
        e.acceptProposedAction()

# ------------------------------------------------------------------ #
#  MayaPickerEditor
# ------------------------------------------------------------------ #

class MayaPickerEditor(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Maya Picker Editor"); self.resize(1100, 750); self.setStyleSheet(STYLESHEET)
        icon_path = os.path.join(os.path.dirname(__file__), "PickerEditor.png")
        if os.path.exists(icon_path): self.setWindowIcon(QtGui.QIcon(icon_path))
        self.current_json_path = ""; self.last_used_color = QtGui.QColor(255, 255, 255, 255)

        main_layout = QtWidgets.QVBoxLayout(self)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # --- 左ペイン ---
        left_w = QtWidgets.QWidget(); left_v = QtWidgets.QVBoxLayout(left_w)
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True)
        self.canvas = ImageCanvas(); self.scroll.setWidget(self.canvas); left_v.addWidget(self.scroll)
        self.btn_mode = QtWidgets.QPushButton("Switch to SELECTOR Mode")
        self.btn_mode.setCheckable(True); self.btn_mode.setFixedHeight(40)
        self.btn_mode.toggled.connect(self.toggle_mode); left_v.addWidget(self.btn_mode)

        # --- 右ペイン ---
        right_w = QtWidgets.QWidget(); right_v = QtWidgets.QVBoxLayout(right_w)
        self.setup_group = QtWidgets.QGroupBox("Registration")
        setup_v = QtWidgets.QVBoxLayout(self.setup_group)
        rep_h = QtWidgets.QHBoxLayout()
        self.edit_f = QtWidgets.QLineEdit(); self.edit_r = QtWidgets.QLineEdit()
        btn_rep = QtWidgets.QPushButton("Replace All")
        btn_rep.clicked.connect(self.batch_replace)
        rep_h.addWidget(self.edit_f); rep_h.addWidget(self.edit_r); rep_h.addWidget(btn_rep)
        setup_v.addLayout(rep_h)
        self.list_widget = DraggableListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setDragEnabled(True); self.list_widget.setAcceptDrops(True)
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.order_changed.connect(self.sync_data_to_list_order)
        self.list_widget.itemSelectionChanged.connect(self.on_list_selection_changed)
        setup_v.addWidget(self.list_widget)
        get_h = QtWidgets.QHBoxLayout()
        self.edit_names = QtWidgets.QLineEdit(); btn_get = QtWidgets.QPushButton("Get Selected")
        btn_get.clicked.connect(lambda: self.edit_names.setText(", ".join(cmds.ls(sl=True))))
        get_h.addWidget(self.edit_names); get_h.addWidget(btn_get); setup_v.addLayout(get_h)
        right_v.addWidget(self.setup_group)
        self.btn_reg = QtWidgets.QPushButton("Register Area"); self.btn_reg.setFixedHeight(30)
        self.btn_reg.clicked.connect(self.do_register)
        self.btn_del = QtWidgets.QPushButton("Delete Selected"); self.btn_del.setFixedHeight(30)
        self.btn_del.clicked.connect(self.delete_items)
        right_v.addWidget(self.btn_reg); right_v.addWidget(self.btn_del)
        file_h = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Save JSON"); btn_load = QtWidgets.QPushButton("Load JSON")
        btn_save.clicked.connect(self.save_json); btn_load.clicked.connect(lambda: self.load_json())
        file_h.addWidget(btn_save); file_h.addWidget(btn_load); right_v.addLayout(file_h)

        self.splitter.addWidget(left_w); self.splitter.addWidget(right_w)
        self.splitter.setSizes([300, 800]); main_layout.addWidget(self.splitter)

        self.canvas.request_deselect.connect(lambda mod: (self.list_widget.clearSelection() if not mod else None))
        self.canvas.region_clicked.connect(self.handle_canvas_region_click)
        self.canvas.region_right_clicked.connect(self.handle_action_execute)
        self.canvas.multi_region_moved.connect(self.handle_multi_move)
        self.canvas.file_dropped.connect(self.handle_drop_file)
        self.canvas.pan_requested.connect(self.handle_pan)

    # ── アクション実行（右クリック） ─────────────────────────────────

    def handle_action_execute(self, idx):
        reg = self.canvas.registered_items[idx]
        if not reg.has_switch: return
        ok, msg = execute_action(reg.action, reg.select_names)
        if not ok and msg:
            QtWidgets.QMessageBox.warning(self, "Action Error", msg)
        # アクション実行後に表示条件を即時評価して更新
        evaluate_visibility(self.canvas.registered_items)
        self.canvas.update()

    # ── 既存メソッド ─────────────────────────────────────────────────

    def on_list_selection_changed(self):
        self.canvas.selected_indices = {i.row() for i in self.list_widget.selectedIndexes()}
        self.canvas.update()

    def sync_data_to_list_order(self):
        new_items = []; old_items = list(self.canvas.registered_items)
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w: new_items.append(old_items[w.index]); w.index = i
        self.canvas.registered_items = new_items; self.canvas.update()

    def handle_canvas_region_click(self, row, is_mod):
        it = self.list_widget.item(row)
        if is_mod:
            it.setSelected(not it.isSelected()) if it else None
        else:
            self.list_widget.clearSelection()
            if it: self.list_widget.setCurrentRow(row); it.setSelected(True)

    def handle_multi_move(self, rows, dx, dy):
        for r in rows:
            reg = self.canvas.registered_items[r]; reg.rect.translate(dx, dy)
            w = self.list_widget.itemWidget(self.list_widget.item(r))
            if w: w.sync_spins(reg.rect)
        self.canvas.update()

    def handle_pan(self, d):
        self.scroll.horizontalScrollBar().setValue(self.scroll.horizontalScrollBar().value() - d.x())
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().value() - d.y())

    def handle_drop_file(self, p):
        ext = os.path.splitext(p)[1].lower()
        if ext in (".png", ".jpg", ".jpeg"):
            self.canvas.set_image(QtGui.QPixmap(p)); self.scroll.setWidgetResizable(False)
            json_path = os.path.splitext(p)[0] + ".json"
            if os.path.exists(json_path): self.load_json(json_path)
        elif ext == ".json": self.load_json(p)

    def batch_replace(self):
        f, r = self.edit_f.text(), self.edit_r.text()
        if f:
            for i, reg in enumerate(self.canvas.registered_items):
                if not reg.next_json:
                    reg.names = [n.replace(f, r) for n in reg.names]
                    w = self.list_widget.itemWidget(self.list_widget.item(i))
                    if w: w.names_edit.setText(", ".join(reg.names))

    def do_register(self):
        s = self.canvas.scale; r = self.canvas.temp_rect
        raw = [int(r.x()/s), int(r.y()/s), int(r.width()/s), int(r.height()/s)] \
              if not r.isNull() else [10, 10, 50, 50]
        names = [n.strip() for n in self.edit_names.text().split(",") if n.strip()] or ["Control"]
        reg = ClickRegion(names, raw, self.last_used_color)
        self.canvas.registered_items.append(reg)
        self.add_list_item(reg.names, reg.rect, reg.color, reg.shape_type, "", None, None)
        self.canvas.temp_rect = QtCore.QRect(); self.canvas.update()

    def add_list_item(self, names, rect, color, shape_type,
                      next_json="", action=None, visible_when=None):
        it = QtWidgets.QListWidgetItem(self.list_widget)
        w = ListColorItem(names, rect, color, shape_type, next_json, action, visible_when,
                          self.list_widget.count() - 1)
        w.names_changed.connect(lambda i, n: setattr(self.canvas.registered_items[i], 'names', n))
        w.rect_changed.connect(self.handle_rect_sync)
        w.color_changed.connect(self.handle_color_sync)
        w.type_changed.connect(self.handle_type_sync)
        w.next_json_changed.connect(lambda i, p: setattr(self.canvas.registered_items[i], 'next_json', p))
        w.action_changed.connect(lambda i, a: setattr(self.canvas.registered_items[i], 'action', a))
        w.visible_when_changed.connect(lambda i, v: setattr(self.canvas.registered_items[i], 'visible_when', v))
        w.layout_changed.connect(lambda _i: it.setSizeHint(w.sizeHint()))
        it.setSizeHint(w.sizeHint())
        self.list_widget.addItem(it); self.list_widget.setItemWidget(it, w)
        w.set_edit_enabled(not self.btn_mode.isChecked())

    def handle_rect_sync(self, idx, k, v):
        sel_rows = [i.row() for i in self.list_widget.selectedIndexes()]
        targets = sel_rows if idx in sel_rows else [idx]
        for r in targets:
            reg = self.canvas.registered_items[r]; rect = list(reg.rect.getRect())
            rect[{"x":0,"y":1,"w":2,"h":3}[k]] = v; reg.rect = QtCore.QRect(*rect)
            w = self.list_widget.itemWidget(self.list_widget.item(r))
            if w and r != idx:
                w.block_signals = True; w.spins[k].setValue(v); w.block_signals = False
        self.canvas.update()

    def handle_color_sync(self, idx, c):
        self.last_used_color = c
        sel_rows = [i.row() for i in self.list_widget.selectedIndexes()]
        targets = sel_rows if idx in sel_rows else [idx]
        for r in targets:
            self.canvas.registered_items[r].color = c
            w = self.list_widget.itemWidget(self.list_widget.item(r))
            if w and r != idx: w.set_btn_color(c)
        self.canvas.update()

    def handle_type_sync(self, idx, t):
        sel_rows = [i.row() for i in self.list_widget.selectedIndexes()]
        targets = sel_rows if idx in sel_rows else [idx]
        for r in targets:
            self.canvas.registered_items[r].shape_type = t
            w = self.list_widget.itemWidget(self.list_widget.item(r))
            if w and r != idx:
                w.block_signals = True; w.type_combo.setCurrentIndex(SHAPE_TYPES.index(t)); w.block_signals = False
        self.canvas.update()

    def delete_items(self):
        for r in sorted([self.list_widget.row(it) for it in self.list_widget.selectedItems()], reverse=True):
            self.list_widget.takeItem(r); self.canvas.registered_items.pop(r)
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w: w.index = i
        self.canvas.update()

    def toggle_mode(self, checked):
        self.canvas.mode = "selector" if checked else "setup"
        self.setup_group.setEnabled(not checked)
        self.btn_reg.setEnabled(not checked); self.btn_del.setEnabled(not checked)
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w: w.set_edit_enabled(not checked)
        if checked:
            # セレクターモード開始 → 初期状態を即評価
            evaluate_visibility(self.canvas.registered_items)
        else:
            # セットアップモード → 全リージョン visible=True にリセット
            for reg in self.canvas.registered_items:
                reg.visible = True
        self.canvas.update()

    def save_json(self):
        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save JSON", self.current_json_path, "*.json")
        if p:
            lines = []
            for i in self.canvas.registered_items:
                path = os.path.basename(i.next_json) if i.next_json else ""
                d = {
                    "names":        i.names,
                    "rect":         list(i.rect.getRect()),
                    "color":        list(i.color.getRgb()),
                    "shape_type":   i.shape_type,
                    "next_json":    path,
                    "action":       i.action,
                    "visible_when": i.visible_when
                }
                lines.append(json.dumps(d, ensure_ascii=False))
            with open(p, 'w', encoding='utf-8') as f:
                f.write("[\n" + ",\n".join(lines) + "\n]")
            self.current_json_path = p

    def load_json(self, p=None):
        if not p:
            p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open JSON", self.current_json_path, "*.json")
        if p and os.path.exists(p):
            self.current_json_path = p
            base_dir = os.path.dirname(p)
            data = json.load(open(p, 'r', encoding='utf-8'))
            self.canvas.registered_items = []; self.list_widget.clear()
            for d in data:
                path = d.get("next_json", "")
                rel  = os.path.basename(path) if path else ""
                full = os.path.join(base_dir, rel) if rel else ""
                names        = d.get("names", [])
                action       = d.get("action", None)
                visible_when = d.get("visible_when", None)

                # 後方互換: 旧 .Switch サフィックス形式を自動変換
                if action is None:
                    sw = [n for n in names if n.endswith(".Switch")]
                    if sw:
                        obj = sw[0][:-len(".Switch")]
                        action = {"type": "attribute_toggle", "target": obj, "attr": "", "values": [0, 1]}
                        names = [n[:-len(".Switch")] if n.endswith(".Switch") else n for n in names]

                reg = ClickRegion(names, d["rect"], d["color"],
                                  d.get("shape_type", "rect"), full, action, visible_when)
                self.canvas.registered_items.append(reg)
                self.add_list_item(reg.names, reg.rect, reg.color, reg.shape_type,
                                   rel, reg.action, reg.visible_when)
            self.canvas.update()


# ------------------------------------------------------------------ #
#  エントリポイント
# ------------------------------------------------------------------ #

maya_picker_editor_instance = None

def show():
    global maya_picker_editor_instance
    try:
        if maya_picker_editor_instance:
            maya_picker_editor_instance.close(); maya_picker_editor_instance.deleteLater()
    except Exception: pass
    parent = next((w for w in QtWidgets.QApplication.topLevelWidgets() if w.objectName() == "MayaWindow"), None)
    maya_picker_editor_instance = MayaPickerEditor(parent=parent)
    if parent: maya_picker_editor_instance.setWindowFlags(QtCore.Qt.Window)
    maya_picker_editor_instance.show()

if __name__ == "__main__": show()
