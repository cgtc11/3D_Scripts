# -*- coding: utf-8 -*-
import json
import os
import math
from PySide6 import QtWidgets, QtCore, QtGui
from pymxs import runtime as mxs

# --- スタイル設定 ---
STYLESHEET = """
    QWidget { background-color: #2b2b2b; color: #dcdcdc; font-family: 'Segoe UI', sans-serif; font-size: 11px; }
    QGroupBox { border: 1px solid #3a3a3a; margin-top: 15px; padding-top: 10px; font-weight: bold; }
    QPushButton { background-color: #3f3f3f; border: 1px solid #555; border-radius: 2px; padding: 2px; color: #ffffff; }
    QPushButton:hover { background-color: #4f4f4f; }
    QPushButton:disabled { background-color: #333; border-color: #444; color: #555; }
    QLineEdit { background-color: #1a1a1a; color: #ffffff; border: 1px solid #333; padding: 1px; }
    QLineEdit:disabled { background-color: #222; color: #555; border-color: #2a2a2a; }
    QComboBox { background-color: #1a1a1a; color: #ffffff; border: 1px solid #333; }
    QComboBox:disabled { background-color: #222; color: #555; border-color: #2a2a2a; }
    QSpinBox { background-color: #1a1a1a; color: #ffffff; border: 1px solid #333; }
    QSpinBox:disabled { background-color: #222; color: #555; border-color: #2a2a2a; }
    QLabel:disabled { color: #555; }
    QListWidget { background-color: #1a1a1a; border: 1px solid #333; outline: none; }
    QListWidget::item:selected { background-color: #3d5a73; }
    QScrollArea { border: 1px solid #333; background-color: #1a1a1a; }
"""

SHAPE_TYPES = [
    "rect", "rect_fill", "circle", "circle_fill", "cross",
    "diamond", "diamond_fill", "tri_up", "tri_up_fill",
    "tri_down", "tri_down_fill", "tri_left", "tri_left_fill",
    "tri_right", "tri_right_fill", "double_circle", "star", "star_fill"
]

# ------------------------------------------------------------------ #
#  アクション実行
# ------------------------------------------------------------------ #

def _resolve_attr(obj_name, attr):
    """mxs.getProperty → getattr の順に試みる。見つからなければ None。"""
    node = mxs.getNodeByName(obj_name)
    if node is None: return None
    try:
        mxs.getProperty(node, mxs.Name(attr)); return attr
    except Exception: pass
    try:
        getattr(node, attr); return attr
    except Exception: pass
    return None

def execute_action(action, targets):
    """戻り値: (成功 True/False, エラーメッセージ or None)"""
    if not action: return False, "アクションが定義されていません"
    atype = action.get("type", "attribute_toggle")
    if atype == "attribute_toggle":
        attr   = action.get("attr", "")
        values = action.get("values", [0, 1])
        if not attr: return False, "attr が空です"
        errors = []
        for target in targets:
            resolved = _resolve_attr(target, attr)
            if resolved is None:
                errors.append(f"{target}: プロパティ '{attr}' が見つかりません"); continue
            node = mxs.getNodeByName(target)
            try:
                try:    val = mxs.getProperty(node, mxs.Name(resolved))
                except: val = getattr(node, resolved)
                mid = (float(values[0]) + float(values[1])) / 2.0
                new_val = values[0] if float(val) >= mid else values[1]
                try:    mxs.setProperty(node, mxs.Name(resolved), new_val)
                except: setattr(node, resolved, new_val)
            except Exception as e: errors.append(str(e))
        return (False, "\n".join(errors)) if errors else (True, None)
    return False, f"不明なアクションタイプ: {atype}"

# ------------------------------------------------------------------ #
#  表示条件評価
# ------------------------------------------------------------------ #

def evaluate_visibility(items):
    """visible_when 条件を評価して item.visible を更新する。"""
    for item in items:
        vw = item.visible_when
        if not vw:
            item.visible = True; continue
        target = vw.get("target", ""); attr = vw.get("attr", ""); value = vw.get("value", 0)
        if not target or not attr:
            item.visible = True; continue
        resolved = _resolve_attr(target, attr)
        if resolved is None:
            item.visible = True; continue
        node = mxs.getNodeByName(target)
        if node is None:
            item.visible = True; continue
        try:
            try:    val = mxs.getProperty(node, mxs.Name(resolved))
            except: val = getattr(node, resolved)
            item.visible = (abs(float(val) - float(value)) < 0.001)
        except Exception:
            item.visible = True

# ------------------------------------------------------------------ #
#  描画
# ------------------------------------------------------------------ #

def draw_shape(painter, t, sr, color, is_selected=False):
    pen_width = 3 if is_selected else 1
    painter.setPen(QtGui.QPen(color, pen_width))
    if "_fill" in t: painter.setBrush(QtGui.QBrush(color))
    else:            painter.setBrush(QtCore.Qt.NoBrush)

    if "rect" in t:       painter.drawRect(sr)
    elif "circle" in t:   painter.drawEllipse(sr)
    elif t == "double_circle":
        painter.drawEllipse(sr)
        inner = sr.adjusted(sr.width()*0.2, sr.height()*0.2, -sr.width()*0.2, -sr.height()*0.2)
        painter.drawEllipse(inner)
    elif t == "cross":
        cx, cy = sr.center().x(), sr.center().y()
        painter.drawLine(sr.left(), cy, sr.right(), cy); painter.drawLine(cx, sr.top(), cx, sr.bottom())
    elif "diamond" in t:
        poly = QtGui.QPolygon([QtCore.QPoint(sr.center().x(), sr.top()), QtCore.QPoint(sr.right(), sr.center().y()), QtCore.QPoint(sr.center().x(), sr.bottom()), QtCore.QPoint(sr.left(), sr.center().y())])
        painter.drawPolygon(poly)
    elif "tri_" in t:
        pts = []
        if "up" in t:    pts = [sr.bottomLeft(), sr.bottomRight(), QtCore.QPoint(sr.center().x(), sr.top())]
        elif "down" in t: pts = [sr.topLeft(),    sr.topRight(),    QtCore.QPoint(sr.center().x(), sr.bottom())]
        elif "left" in t: pts = [sr.topRight(),   sr.bottomRight(), QtCore.QPoint(sr.left(),        sr.center().y())]
        elif "right" in t: pts = [sr.topLeft(),   sr.bottomLeft(),  QtCore.QPoint(sr.right(),       sr.center().y())]
        if pts: painter.drawPolygon(QtGui.QPolygon(pts))
    elif "star" in t:
        poly = QtGui.QPolygon(); center = sr.center()
        ro = min(sr.width(), sr.height())/2; ri = ro/2.5
        for j in range(10):
            r = ro if j%2==0 else ri; angle = (j*36-90)*math.pi/180
            poly << QtCore.QPoint(center.x()+r*math.cos(angle), center.y()+r*math.sin(angle))
        painter.drawPolygon(poly)
    painter.setBrush(QtCore.Qt.NoBrush)

def create_shape_icon(shape_type, color):
    pixmap = QtGui.QPixmap(16, 16); pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap); painter.setRenderHint(QtGui.QPainter.Antialiasing)
    draw_shape(painter, shape_type, QtCore.QRect(1, 1, 14, 14), QtGui.QColor(color), False)
    painter.end(); return QtGui.QIcon(pixmap)

# ------------------------------------------------------------------ #
#  MaxStyleSpinBox / DraggableLabel
# ------------------------------------------------------------------ #

class MaxStyleSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent); self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.setRange(-8000, 8000); self.setFixedWidth(35); self.setAlignment(QtCore.Qt.AlignCenter)

class DraggableLabel(QtWidgets.QLabel):
    def __init__(self, text, target_spin, parent=None):
        super().__init__(text, parent); self.target_spin = target_spin
        self.setCursor(QtCore.Qt.SizeHorCursor); self.last_pos = None
        self.setFixedWidth(10); self.setStyleSheet("color: #888;")
    def mousePressEvent(self, e): self.last_pos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e):
        if self.last_pos:
            delta = e.globalPosition().toPoint().x() - self.last_pos.x()
            if delta != 0: self.target_spin.setValue(self.target_spin.value() + delta); self.last_pos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): self.last_pos = None

# ------------------------------------------------------------------ #
#  ClickRegion
# ------------------------------------------------------------------ #

class ClickRegion:
    def __init__(self, names, rect_data, color, shape_type="rect",
                 next_json="", action=None, visible_when=None):
        self.names        = names if isinstance(names, list) else [names]
        self.rect         = QtCore.QRect(*rect_data)
        self.color        = QtGui.QColor(*color) if isinstance(color, list) else QtGui.QColor(color)
        self.shape_type   = shape_type
        self.next_json    = next_json
        self.action       = action
        self.visible_when = visible_when
        self.visible      = True

    @property
    def has_switch(self): return self.action is not None
    @property
    def has_visibility(self): return self.visible_when is not None
    @property
    def select_names(self): return list(self.names)

# ------------------------------------------------------------------ #
#  ListColorItem
# ------------------------------------------------------------------ #

class ListColorItem(QtWidgets.QWidget):
    color_changed        = QtCore.Signal(object, QtGui.QColor)
    rect_changed         = QtCore.Signal(object, str, int)
    names_changed        = QtCore.Signal(object, list)
    type_changed         = QtCore.Signal(object, str)
    next_json_changed    = QtCore.Signal(object, str)
    action_changed       = QtCore.Signal(object, object)
    visible_when_changed = QtCore.Signal(object, object)
    layout_changed       = QtCore.Signal(object)

    def __init__(self, reg_item, parent=None):
        super().__init__(parent)
        self.block_signals = False
        self.associated_reg = reg_item
        self.current_color = reg_item.color

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 2, 2); outer.setSpacing(1)

        # ── 上段 ────────────────────────────────────────────────────
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(2, 0, 0, 0); layout.setSpacing(4); layout.addSpacing(40)

        self.names_edit = QtWidgets.QLineEdit()
        self.names_edit.editingFinished.connect(self.on_ui_data_changed)
        layout.addWidget(self.names_edit, 1)

        self.btn_path = QtWidgets.QPushButton("..."); self.btn_path.setFixedWidth(20)
        self.btn_path.clicked.connect(self.browse_path); layout.addWidget(self.btn_path)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setIconSize(QtCore.QSize(14, 14)); self.type_combo.setFixedWidth(45)
        for st in SHAPE_TYPES: self.type_combo.addItem(create_shape_icon(st, self.current_color), "", st)
        self.type_combo.currentIndexChanged.connect(self.on_type_ui_changed)
        layout.addWidget(self.type_combo)

        self.spins = {}; self.labels = []
        for lbl_t, key in [("X", "x"), ("Y", "y"), ("W", "w"), ("H", "h")]:
            sb = MaxStyleSpinBox()
            sb.valueChanged.connect(lambda val, k=key: self.on_rect_ui_changed(k, val))
            lbl = DraggableLabel(lbl_t, sb); self.labels.append(lbl)
            layout.addWidget(lbl); layout.addWidget(sb); self.spins[key] = sb

        self.color_btn = QtWidgets.QPushButton("■"); self.color_btn.setFixedSize(18, 18)
        self.color_btn.clicked.connect(self.pick_new_color); layout.addWidget(self.color_btn)

        # Action トグルボタン
        self.btn_action_toggle = QtWidgets.QPushButton("▶ Action")
        self.btn_action_toggle.setCheckable(True); self.btn_action_toggle.setFixedWidth(62)
        self.btn_action_toggle.setStyleSheet(
            "QPushButton { color: #777; font-size: 10px; }"
            "QPushButton:checked { color: #ffcc44; border-color: #776622; }")
        self.btn_action_toggle.toggled.connect(self._on_action_toggle)
        layout.addWidget(self.btn_action_toggle)

        # Visible When トグルボタン
        self.btn_vis_toggle = QtWidgets.QPushButton("▶ Visible")
        self.btn_vis_toggle.setCheckable(True); self.btn_vis_toggle.setFixedWidth(62)
        self.btn_vis_toggle.setStyleSheet(
            "QPushButton { color: #777; font-size: 10px; }"
            "QPushButton:checked { color: #66ccff; border-color: #224466; }")
        self.btn_vis_toggle.toggled.connect(self._on_vis_toggle)
        layout.addWidget(self.btn_vis_toggle)

        outer.addLayout(layout)

        # ── Action パネル ─────────────────────────────────────────────
        self.action_panel = QtWidgets.QFrame()
        self.action_panel.setStyleSheet("QFrame { background-color: #1e1e1e; border-top: 1px solid #3a3a3a; }")
        ap = QtWidgets.QHBoxLayout(self.action_panel)
        ap.setContentsMargins(44, 3, 4, 3); ap.setSpacing(4)
        ap.addWidget(QtWidgets.QLabel("Attr:"))
        self.action_attr_edit = QtWidgets.QLineEdit()
        self.action_attr_edit.setPlaceholderText("property name"); self.action_attr_edit.setFixedWidth(140)
        self.action_attr_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_attr_edit)
        ap.addWidget(QtWidgets.QLabel("Val:"))
        self.action_val0_edit = QtWidgets.QLineEdit("0"); self.action_val0_edit.setFixedWidth(32)
        self.action_val0_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_val0_edit)
        ap.addWidget(QtWidgets.QLabel("⇄"))
        self.action_val1_edit = QtWidgets.QLineEdit("1"); self.action_val1_edit.setFixedWidth(32)
        self.action_val1_edit.editingFinished.connect(self._on_action_changed)
        ap.addWidget(self.action_val1_edit)
        ap.addStretch()
        self.action_panel.setVisible(False)
        outer.addWidget(self.action_panel)

        # ── Visible When パネル ───────────────────────────────────────
        self.vis_panel = QtWidgets.QFrame()
        self.vis_panel.setStyleSheet("QFrame { background-color: #1a2030; border-top: 1px solid #224466; }")
        vp = QtWidgets.QHBoxLayout(self.vis_panel)
        vp.setContentsMargins(44, 3, 4, 3); vp.setSpacing(4)
        vp.addWidget(QtWidgets.QLabel("Target:"))
        self.vis_target_edit = QtWidgets.QLineEdit()
        self.vis_target_edit.setPlaceholderText("node name"); self.vis_target_edit.setFixedWidth(110)
        self.vis_target_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_target_edit)
        vp.addWidget(QtWidgets.QLabel("Attr:"))
        self.vis_attr_edit = QtWidgets.QLineEdit()
        self.vis_attr_edit.setPlaceholderText("property name"); self.vis_attr_edit.setFixedWidth(110)
        self.vis_attr_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_attr_edit)
        vp.addWidget(QtWidgets.QLabel("="))
        self.vis_value_edit = QtWidgets.QLineEdit("0"); self.vis_value_edit.setFixedWidth(32)
        self.vis_value_edit.editingFinished.connect(self._on_vis_changed)
        vp.addWidget(self.vis_value_edit)
        vp.addStretch()
        self.vis_panel.setVisible(False)
        outer.addWidget(self.vis_panel)

        self.update_ui_silently(reg_item.names, reg_item.rect, self.current_color, reg_item.shape_type, reg_item.next_json)
        if reg_item.action:       self._load_action(reg_item.action)
        if reg_item.visible_when: self._load_vis(reg_item.visible_when)

    # ── Action パネル ────────────────────────────────────────────────

    def _on_action_toggle(self, checked):
        self.action_panel.setVisible(checked)
        self.btn_action_toggle.setText("▼ Action" if checked else "▶ Action")
        if not checked: self.action_changed.emit(self, None)
        else:           self._on_action_changed()
        self.layout_changed.emit(self)

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
        self.action_changed.emit(self, action)

    # ── Visible When パネル ───────────────────────────────────────────

    def _on_vis_toggle(self, checked):
        self.vis_panel.setVisible(checked)
        self.btn_vis_toggle.setText("▼ Visible" if checked else "▶ Visible")
        if not checked: self.visible_when_changed.emit(self, None)
        else:           self._on_vis_changed()
        self.layout_changed.emit(self)

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
        self.visible_when_changed.emit(self, vw)

    # ── 既存ヘルパー ─────────────────────────────────────────────────

    def update_ui_silently(self, names, rect, color, shape_type, next_json):
        self.block_signals = True; self.current_color = color
        txt = next_json if next_json else ", ".join(names)
        if self.names_edit.text() != txt: self.names_edit.setText(txt)
        for k, v in zip(["x","y","w","h"], [rect.x(), rect.y(), rect.width(), rect.height()]):
            self.spins[k].setValue(v)
        if shape_type in SHAPE_TYPES: self.type_combo.setCurrentIndex(SHAPE_TYPES.index(shape_type))
        self.color_btn.setStyleSheet(f"color: {color.name()}; background-color: #1a1a1a; border: 1px solid #555;")
        for i in range(self.type_combo.count()): self.type_combo.setItemIcon(i, create_shape_icon(SHAPE_TYPES[i], color))
        self.block_signals = False

    def on_rect_ui_changed(self, k, v):
        if not self.block_signals: self.rect_changed.emit(self, k, v)

    def on_type_ui_changed(self, idx):
        if not self.block_signals: self.type_changed.emit(self, SHAPE_TYPES[idx])

    def on_ui_data_changed(self):
        if not self.block_signals:
            t = self.names_edit.text()
            if t.endswith(".json"): self.next_json_changed.emit(self, t); self.names_changed.emit(self, [])
            else: self.next_json_changed.emit(self, ""); self.names_changed.emit(self, [n.strip() for n in t.split(",") if n.strip()])

    def browse_path(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select JSON", "", "*.json")
        if p: self.names_edit.setText(os.path.basename(p)); self.on_ui_data_changed()

    def pick_new_color(self):
        c = QtWidgets.QColorDialog.getColor(self.current_color, self)
        if c.isValid(): self.color_changed.emit(self, c)

    def set_edit_enabled(self, e):
        self.names_edit.setEnabled(e); self.btn_path.setEnabled(e)
        self.type_combo.setEnabled(e); self.color_btn.setEnabled(e)
        self.btn_action_toggle.setEnabled(e); self.btn_vis_toggle.setEnabled(e)
        for sb in self.spins.values(): sb.setEnabled(e)
        for lb in self.labels: lb.setEnabled(e)
        for w in (self.action_attr_edit, self.action_val0_edit, self.action_val1_edit,
                  self.vis_target_edit, self.vis_attr_edit, self.vis_value_edit):
            w.setEnabled(e)

# ------------------------------------------------------------------ #
#  ImageCanvas
# ------------------------------------------------------------------ #

class ImageCanvas(QtWidgets.QLabel):
    request_deselect     = QtCore.Signal(bool)
    region_clicked       = QtCore.Signal(int, bool)
    region_right_clicked = QtCore.Signal(int)
    multi_region_moved   = QtCore.Signal(list, int, int)
    pan_requested        = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True)
        self.pixmap_original = None; self.scale = 1.0
        self.temp_rect = QtCore.QRect(); self.registered_items = []
        self.mode = "setup"; self.selected_indices = set()
        self.start_pos = None; self.last_pan_pos = None; self.is_dragging = False
        self.setMouseTracking(True); self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

    def set_image(self, pix):
        if pix and not pix.isNull(): self.pixmap_original = pix; self.update_canvas_size()

    def update_canvas_size(self):
        if self.pixmap_original:
            ns = self.pixmap_original.size() * self.scale
            self.setPixmap(self.pixmap_original.scaled(ns, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.setFixedSize(ns)

    def paintEvent(self, event):
        super().paintEvent(event); painter = QtGui.QPainter(self); painter.setRenderHint(QtGui.QPainter.Antialiasing)
        for i, item in enumerate(self.registered_items):
            sr = QtCore.QRect(int(item.rect.x()*self.scale), int(item.rect.y()*self.scale),
                              int(item.rect.width()*self.scale), int(item.rect.height()*self.scale))
            if self.mode == "selector":
                if not item.visible: continue
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
            painter.setPen(QtGui.QPen(QtCore.Qt.red, 1, QtCore.Qt.DashLine)); painter.drawRect(self.temp_rect)

    def _draw_switch_badge(self, painter, sr):
        bw = max(10, int(sr.width() * 0.28)); bh = max(8, int(sr.height() * 0.28))
        badge_rect = QtCore.QRect(sr.right() - bw + 1, sr.top() - 1, bw, bh)
        painter.save()
        painter.setPen(QtCore.Qt.NoPen); painter.setBrush(QtGui.QColor(255, 180, 0, 200))
        painter.drawRoundedRect(badge_rect, 2, 2)
        painter.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1))
        font = painter.font(); font.setPixelSize(max(7, bh - 2)); font.setBold(True); painter.setFont(font)
        painter.drawText(badge_rect, QtCore.Qt.AlignCenter, "⇄")
        painter.restore()

    def _hit_test(self, raw):
        for i, r in enumerate(self.registered_items):
            if self.mode == "selector" and not r.visible: continue
            if r.rect.contains(raw): return i
        return -1

    def mousePressEvent(self, event):
        mod = event.modifiers()
        # raw は常に整数 QPoint に統一（QPointF のまま渡すと QRect.contains がクラッシュする）
        raw = QtCore.QPoint(int(event.position().x() / self.scale),
                            int(event.position().y() / self.scale))
        pos = event.position().toPoint()
        is_mod = bool(mod & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier))
        if event.button() == QtCore.Qt.MiddleButton or (event.button() == QtCore.Qt.LeftButton and mod & QtCore.Qt.AltModifier):
            self.last_pan_pos = event.globalPosition().toPoint(); self.setCursor(QtCore.Qt.ClosedHandCursor); return

        hit = self._hit_test(raw)

        if event.button() == QtCore.Qt.RightButton:
            if self.mode == "selector" and hit != -1:
                self.region_right_clicked.emit(hit)
            return

        if hit != -1:
            if self.mode == "setup" and not is_mod:
                if hit not in self.selected_indices: self.region_clicked.emit(hit, False)
                self.is_dragging = True; self.drag_last_raw = raw; self.setCursor(QtCore.Qt.SizeAllCursor)
            else:
                self.region_clicked.emit(hit, is_mod)
                # セレクターモード: MAX オブジェクトを選択
                if self.mode == "selector":
                    sel_names = self.registered_items[hit].select_names
                    nodes = [mxs.getNodeByName(n) for n in sel_names]
                    nodes = [n for n in nodes if n]
                    if nodes:
                        if is_mod: mxs.selectMore(nodes)
                        else: mxs.select(nodes)
                    elif not is_mod:
                        mxs.deselect(mxs.selection)
        else:
            if self.mode == "setup": self.start_pos = pos; self.temp_rect = QtCore.QRect()
            self.request_deselect.emit(is_mod)
            if self.mode == "selector" and not is_mod:
                mxs.deselect(mxs.selection)

    def mouseMoveEvent(self, event):
        if self.last_pan_pos:
            delta = event.globalPosition().toPoint() - self.last_pan_pos
            self.pan_requested.emit(delta); self.last_pan_pos = event.globalPosition().toPoint(); return
        if self.is_dragging:
            raw = QtCore.QPoint(int(event.position().x() / self.scale),
                                int(event.position().y() / self.scale))
            dx = raw.x() - self.drag_last_raw.x()
            dy = raw.y() - self.drag_last_raw.y()
            if dx != 0 or dy != 0:
                self.multi_region_moved.emit(list(self.selected_indices), dx, dy)
                self.drag_last_raw = raw
        elif self.start_pos:
            self.temp_rect = QtCore.QRect(self.start_pos, event.position().toPoint()).normalized(); self.update()

    def mouseReleaseEvent(self, e):
        self.start_pos = self.last_pan_pos = None; self.is_dragging = False
        self.setCursor(QtCore.Qt.ArrowCursor); self.update()

    def wheelEvent(self, e):
        self.scale *= (1.1 if e.angleDelta().y() > 0 else 0.9)
        self.scale = max(0.1, min(self.scale, 10.0)); self.update_canvas_size(); self.update()

# ------------------------------------------------------------------ #
#  PickerEditor
# ------------------------------------------------------------------ #

class PickerEditor(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("PickerEditor - Max Version")
        self.resize(1150, 750); self.setStyleSheet(STYLESHEET)
        self.setAcceptDrops(True); self.is_syncing = False
        self.current_json_path = ""; self.last_used_color = QtGui.QColor(0, 255, 0)

        main_v = QtWidgets.QVBoxLayout(self); main_v.setContentsMargins(5, 5, 5, 5)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        left_w = QtWidgets.QWidget(); left_v = QtWidgets.QVBoxLayout(left_w); left_v.setContentsMargins(0,0,0,0)
        self.scroll = QtWidgets.QScrollArea(); self.canvas = ImageCanvas()
        self.scroll.setWidget(self.canvas); left_v.addWidget(self.scroll)
        self.btn_mode = QtWidgets.QPushButton("Switch to SELECTOR Mode")
        self.btn_mode.setCheckable(True); self.btn_mode.setFixedHeight(35)
        self.btn_mode.toggled.connect(self.toggle_mode); left_v.addWidget(self.btn_mode)

        right_w = QtWidgets.QWidget(); right_panel = QtWidgets.QVBoxLayout(right_w); right_panel.setContentsMargins(0,0,0,0)
        self.setup_group = QtWidgets.QGroupBox("Registration"); setup_v = QtWidgets.QVBoxLayout(self.setup_group)

        replace_h = QtWidgets.QHBoxLayout()
        self.edit_find = QtWidgets.QLineEdit(); self.edit_find.setPlaceholderText("Find...")
        self.edit_replace = QtWidgets.QLineEdit(); self.edit_replace.setPlaceholderText("Replace...")
        btn_replace = QtWidgets.QPushButton("Replace All"); btn_replace.clicked.connect(self.batch_replace_names)
        replace_h.addWidget(self.edit_find); replace_h.addWidget(self.edit_replace); replace_h.addWidget(btn_replace)
        setup_v.addLayout(replace_h)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setDragEnabled(True); self.list_widget.setAcceptDrops(True)
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.list_widget.model().rowsMoved.connect(self.sync_data_order_from_ui)
        self.list_widget.itemSelectionChanged.connect(self.sync_selection_to_canvas)
        setup_v.addWidget(self.list_widget)

        get_h = QtWidgets.QHBoxLayout(); self.edit_names = QtWidgets.QLineEdit()
        btn_get = QtWidgets.QPushButton("Get Selected")
        btn_get.clicked.connect(lambda: self.edit_names.setText(", ".join([o.name for o in list(mxs.selection)])))
        get_h.addWidget(self.edit_names); get_h.addWidget(btn_get); setup_v.addLayout(get_h)
        self.btn_reg = QtWidgets.QPushButton("Register Area"); self.btn_reg.setFixedHeight(30)
        self.btn_reg.clicked.connect(self.do_register); setup_v.addWidget(self.btn_reg)
        self.btn_del = QtWidgets.QPushButton("Delete Selected"); self.btn_del.clicked.connect(self.delete_items)
        setup_v.addWidget(self.btn_del)
        right_panel.addWidget(self.setup_group)
        file_h = QtWidgets.QHBoxLayout(); btn_save = QtWidgets.QPushButton("Save JSON"); btn_load = QtWidgets.QPushButton("Load JSON")
        btn_save.clicked.connect(self.save_json); btn_load.clicked.connect(self.load_json)
        file_h.addWidget(btn_save); file_h.addWidget(btn_load); right_panel.addLayout(file_h)

        self.splitter.addWidget(left_w); self.splitter.addWidget(right_w)
        self.splitter.setStretchFactor(0, 1); self.splitter.setStretchFactor(1, 1)
        main_v.addWidget(self.splitter)

        self.canvas.request_deselect.connect(lambda mod: (self.list_widget.clearSelection() if not mod else None))
        self.canvas.region_clicked.connect(self.handle_canvas_region_click)
        self.canvas.region_right_clicked.connect(self.handle_action_execute)
        self.canvas.multi_region_moved.connect(self.handle_multi_move)
        self.canvas.pan_requested.connect(self.handle_pan)

    # ── アクション実行（右クリック） ─────────────────────────────────

    def handle_action_execute(self, idx):
        reg = self.canvas.registered_items[idx]
        if not reg.has_switch: return
        ok, msg = execute_action(reg.action, reg.select_names)
        if not ok and msg:
            QtWidgets.QMessageBox.warning(self, "Action Error", msg)
        # アクション実行後に表示条件を即時評価
        evaluate_visibility(self.canvas.registered_items)
        self.canvas.update()

    # ── 既存メソッド ─────────────────────────────────────────────────

    def batch_replace_names(self):
        f, r = self.edit_find.text(), self.edit_replace.text()
        if not f: return
        self.is_syncing = True
        for i, reg in enumerate(self.canvas.registered_items):
            if not reg.next_json:
                reg.names = [n.replace(f, r) for n in reg.names]
                w = self.list_widget.itemWidget(self.list_widget.item(i))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
        self.is_syncing = False

    def sync_data_order_from_ui(self, *args):
        new_items = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i); w = self.list_widget.itemWidget(it)
            if hasattr(w, 'associated_reg'): new_items.append(w.associated_reg)
        self.canvas.registered_items = new_items; self.sync_selection_to_canvas(); self.canvas.update()

    def _get_target_rows(self, widget):
        row = -1
        for i in range(self.list_widget.count()):
            if self.list_widget.itemWidget(self.list_widget.item(i)) == widget: row = i; break
        if row == -1: return set()
        sel = {i.row() for i in self.list_widget.selectedIndexes()}; return sel if row in sel else {row}

    def handle_rect_sync(self, widget, key, val):
        if self.is_syncing: return
        try:
            self.is_syncing = True; rows = self._get_target_rows(widget)
            for r in rows:
                reg = self.canvas.registered_items[r]; rl = list(reg.rect.getRect())
                rl[{"x":0,"y":1,"w":2,"h":3}[key]] = val; reg.rect = QtCore.QRect(*rl)
                w = self.list_widget.itemWidget(self.list_widget.item(r))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
            self.canvas.update()
        finally: self.is_syncing = False

    def handle_color_sync(self, widget, c):
        if self.is_syncing: return
        try:
            self.is_syncing = True; self.last_used_color = c; rows = self._get_target_rows(widget)
            for r in rows:
                reg = self.canvas.registered_items[r]; reg.color = c
                w = self.list_widget.itemWidget(self.list_widget.item(r))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
            self.canvas.update()
        finally: self.is_syncing = False

    def handle_type_sync(self, widget, t):
        if self.is_syncing: return
        try:
            self.is_syncing = True; rows = self._get_target_rows(widget)
            for r in rows:
                reg = self.canvas.registered_items[r]; reg.shape_type = t
                w = self.list_widget.itemWidget(self.list_widget.item(r))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
            self.canvas.update()
        finally: self.is_syncing = False

    def handle_names_sync(self, widget, names):
        if self.is_syncing: return
        try:
            self.is_syncing = True; rows = self._get_target_rows(widget)
            for r in rows:
                reg = self.canvas.registered_items[r]; reg.names = names
                w = self.list_widget.itemWidget(self.list_widget.item(r))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
        finally: self.is_syncing = False

    def handle_next_json_sync(self, widget, p):
        if self.is_syncing: return
        try:
            self.is_syncing = True; rows = self._get_target_rows(widget)
            for r in rows:
                reg = self.canvas.registered_items[r]; reg.next_json = p
                w = self.list_widget.itemWidget(self.list_widget.item(r))
                if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
        finally: self.is_syncing = False

    def handle_action_sync(self, widget, action):
        rows = self._get_target_rows(widget)
        for r in rows:
            if r < len(self.canvas.registered_items):
                self.canvas.registered_items[r].action = action
        self.canvas.update()

    def handle_visible_when_sync(self, widget, vw):
        rows = self._get_target_rows(widget)
        for r in rows:
            if r < len(self.canvas.registered_items):
                self.canvas.registered_items[r].visible_when = vw
        self.canvas.update()

    def handle_layout_changed(self, widget):
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if self.list_widget.itemWidget(it) == widget:
                it.setSizeHint(widget.sizeHint()); break

    def handle_canvas_region_click(self, row, is_mod):
        it = self.list_widget.item(row)
        if it:
            if is_mod: it.setSelected(not it.isSelected())
            else: self.list_widget.clearSelection(); self.list_widget.setCurrentRow(row); it.setSelected(True)

    def handle_pan(self, d):
        self.scroll.horizontalScrollBar().setValue(self.scroll.horizontalScrollBar().value()-d.x())
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().value()-d.y())

    def handle_multi_move(self, indices, dx, dy):
        for idx in indices:
            reg = self.canvas.registered_items[idx]; reg.rect.translate(dx, dy)
            w = self.list_widget.itemWidget(self.list_widget.item(idx))
            if w: w.update_ui_silently(reg.names, reg.rect, reg.color, reg.shape_type, reg.next_json)
        self.canvas.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        self.handle_dropped_file(e.mimeData().urls()[0].toLocalFile()); e.acceptProposedAction()

    def handle_dropped_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".tga"]:
            pix = QtGui.QPixmap(path)
            if not pix.isNull():
                self.canvas.set_image(pix); self.setWindowTitle(f"Picker: {os.path.basename(path)}")
                json_p = os.path.splitext(path)[0] + ".json"
                if os.path.exists(json_p): self.load_json_at_path(json_p)
        elif ext == ".json": self.load_json_at_path(path)

    def do_register(self):
        names = [n.strip() for n in self.edit_names.text().split(",") if n.strip()] or ["Control"]
        s = self.canvas.scale; r = self.canvas.temp_rect
        raw = [int(r.x()/s), int(r.y()/s), int(r.width()/s), int(r.height()/s)] if not r.isNull() else [10, 10, 40, 40]
        reg = ClickRegion(names, raw, self.last_used_color)
        self.canvas.registered_items.append(reg)
        self.add_list_item(reg)
        self.canvas.temp_rect = QtCore.QRect(); self.canvas.update()

    def add_list_item(self, reg):
        it = QtWidgets.QListWidgetItem(self.list_widget)
        w = ListColorItem(reg)
        w.rect_changed.connect(self.handle_rect_sync)
        w.color_changed.connect(self.handle_color_sync)
        w.type_changed.connect(self.handle_type_sync)
        w.names_changed.connect(self.handle_names_sync)
        w.next_json_changed.connect(self.handle_next_json_sync)
        w.action_changed.connect(self.handle_action_sync)
        w.visible_when_changed.connect(self.handle_visible_when_sync)
        w.layout_changed.connect(self.handle_layout_changed)
        it.setSizeHint(w.sizeHint()); self.list_widget.addItem(it); self.list_widget.setItemWidget(it, w)

    def sync_selection_to_canvas(self):
        self.canvas.selected_indices = {i.row() for i in self.list_widget.selectedIndexes()}; self.canvas.update()

    def delete_items(self):
        for r in sorted([self.list_widget.row(it) for it in self.list_widget.selectedItems()], reverse=True):
            self.list_widget.takeItem(r); self.canvas.registered_items.pop(r)
        self.canvas.update()

    def toggle_mode(self, checked):
        self.canvas.mode = "selector" if checked else "setup"; self.setup_group.setEnabled(not checked)
        for i in range(self.list_widget.count()):
            w = self.list_widget.itemWidget(self.list_widget.item(i))
            if w: w.set_edit_enabled(not checked)
        if checked:
            evaluate_visibility(self.canvas.registered_items)
        else:
            for reg in self.canvas.registered_items: reg.visible = True
        self.canvas.update()

    def save_json(self):
        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save JSON", self.current_json_path, "*.json")
        if p:
            lines = []
            for i in self.canvas.registered_items:
                path = os.path.basename(i.next_json) if i.next_json else ""
                lines.append(json.dumps({
                    "names": i.names, "rect": list(i.rect.getRect()),
                    "color": list(i.color.getRgb()), "shape_type": i.shape_type,
                    "next_json": path, "action": i.action, "visible_when": i.visible_when
                }, ensure_ascii=False))
            with open(p, 'w', encoding='utf-8') as f: f.write("[\n" + ",\n".join(lines) + "\n]")
            self.current_json_path = p; self.setWindowTitle(f"Picker: {os.path.basename(p)}")

    def load_json(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open JSON", self.current_json_path, "*.json")
        if p: self.load_json_at_path(p)

    def load_json_at_path(self, p):
        if p and os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f: data = json.load(f)
            self.canvas.registered_items = []; self.list_widget.clear(); base = os.path.dirname(p)
            for d in data:
                nj = d.get("next_json", ""); full = os.path.join(base, nj) if nj else ""
                st = d.get("shape_type", d.get("type", "rect"))
                action       = d.get("action", None)
                visible_when = d.get("visible_when", None)
                reg = ClickRegion(d.get("names", []), d["rect"], d["color"], st, full, action, visible_when)
                self.canvas.registered_items.append(reg); self.add_list_item(reg)
            self.canvas.update(); self.current_json_path = p; self.setWindowTitle(f"Picker: {os.path.basename(p)}")

if __name__ == "__main__":
    for w in QtWidgets.QApplication.allWidgets():
        if w.windowTitle().startswith("PickerEditor - Max"): w.close(); w.deleteLater()
    ui = PickerEditor(); ui.show()
