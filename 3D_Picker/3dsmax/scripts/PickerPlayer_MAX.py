# -*- coding: utf-8 -*-
import json
import os
import math
from PySide6 import QtWidgets, QtCore, QtGui
from pymxs import runtime as mxs

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
    if not action: return
    atype = action.get("type", "attribute_toggle")
    if atype == "attribute_toggle":
        attr   = action.get("attr", "")
        values = action.get("values", [0, 1])
        if not attr: return
        for target in targets:
            resolved = _resolve_attr(target, attr)
            if resolved is None: continue
            node = mxs.getNodeByName(target)
            try:
                try:    val = mxs.getProperty(node, mxs.Name(resolved))
                except: val = getattr(node, resolved)
                mid = (float(values[0]) + float(values[1])) / 2.0
                new_val = values[0] if float(val) >= mid else values[1]
                try:    mxs.setProperty(node, mxs.Name(resolved), new_val)
                except: setattr(node, resolved, new_val)
            except Exception: pass

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
#  共通描画関数
# ------------------------------------------------------------------ #

def draw_shape(painter, t, sr, color, is_selected):
    painter.setPen(QtGui.QPen(color, 4 if is_selected else 1))
    if t == "rect": painter.drawRect(sr)
    elif t == "rect_fill": painter.fillRect(sr, color)
    elif t == "circle": painter.drawEllipse(sr)
    elif t == "circle_fill":
        painter.setBrush(color); painter.drawEllipse(sr); painter.setBrush(QtCore.Qt.NoBrush)
    elif t == "cross":
        cx, cy = sr.center().x(), sr.center().y()
        painter.drawLine(sr.left(), cy, sr.right(), cy); painter.drawLine(cx, sr.top(), cx, sr.bottom())
    elif "diamond" in t:
        poly = QtGui.QPolygon([QtCore.QPoint(sr.center().x(), sr.top()), QtCore.QPoint(sr.right(), sr.center().y()), QtCore.QPoint(sr.center().x(), sr.bottom()), QtCore.QPoint(sr.left(), sr.center().y())])
        if "fill" in t: painter.setBrush(color)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    elif "tri_" in t:
        if "up" in t:    pts = [sr.bottomLeft(), sr.bottomRight(), QtCore.QPoint(sr.center().x(), sr.top())]
        elif "down" in t: pts = [sr.topLeft(),    sr.topRight(),    QtCore.QPoint(sr.center().x(), sr.bottom())]
        elif "left" in t: pts = [sr.topRight(),   sr.bottomRight(), QtCore.QPoint(sr.left(),        sr.center().y())]
        elif "right" in t: pts = [sr.topLeft(),   sr.bottomLeft(),  QtCore.QPoint(sr.right(),       sr.center().y())]
        poly = QtGui.QPolygon(pts); (painter.setBrush(color) if "fill" in t else None)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    elif t == "double_circle":
        painter.drawEllipse(sr)
        inner = sr.adjusted(sr.width()*0.2, sr.height()*0.2, -sr.width()*0.2, -sr.height()*0.2); painter.drawEllipse(inner)
    elif "star" in t:
        poly = QtGui.QPolygon(); center = sr.center(); ro = min(sr.width(), sr.height())/2; ri = ro/2.5
        for j in range(10):
            r = ro if j%2==0 else ri; angle = (j*36-90)*math.pi/180
            poly << QtCore.QPoint(center.x()+r*math.cos(angle), center.y()+r*math.sin(angle))
        if "fill" in t: painter.setBrush(color)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    else: painter.drawRect(sr)

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
#  PickerCanvas
# ------------------------------------------------------------------ #

class PickerCanvas(QtWidgets.QLabel):
    pan_requested       = QtCore.Signal(QtCore.QPoint)
    json_jump_requested = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.registered_items = []; self.selected_indices = set()
        self.origin = QtCore.QPoint(); self.selection_rect = QtCore.QRect()
        self.is_dragging = False; self.scale = 1.0; self.pixmap_original = None; self.last_pan_pos = None
        self.setMouseTracking(True)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet("background-color: #1a1a1a; border: None;")

    def set_image(self, pixmap):
        self.pixmap_original = pixmap; self.update_canvas_size()

    def update_canvas_size(self):
        if self.pixmap_original:
            new_size = self.pixmap_original.size() * self.scale
            self.setPixmap(self.pixmap_original.scaled(
                new_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation))
            self.setFixedSize(new_size)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self); painter.setRenderHint(QtGui.QPainter.Antialiasing)
        for i, item in enumerate(self.registered_items):
            if not item.visible: continue
            sr = QtCore.QRect(item.rect.x()*self.scale, item.rect.y()*self.scale,
                              item.rect.width()*self.scale, item.rect.height()*self.scale)
            draw_shape(painter, item.shape_type, sr, item.color, i in self.selected_indices)
            if item.has_switch: self._draw_switch_badge(painter, sr)
        if self.is_dragging and not self.selection_rect.isNull():
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white, 1, QtCore.Qt.PenStyle.DashLine))
            painter.drawRect(self.selection_rect)

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

    def wheelEvent(self, event):
        self.scale *= 1.1 if event.angleDelta().y() > 0 else 0.9
        self.scale = max(0.1, min(self.scale, 10.0)); self.update_canvas_size(); self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.MiddleButton or \
           (event.button() == QtCore.Qt.MouseButton.LeftButton and
            event.modifiers() & QtCore.Qt.KeyboardModifier.AltModifier):
            self.last_pan_pos = event.globalPosition().toPoint()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor); return

        raw_pos = QtCore.QPoint(int(event.position().x() / self.scale),
                                int(event.position().y() / self.scale))
        hit_idx = next((i for i, r in enumerate(self.registered_items)
                        if r.visible and r.rect.contains(raw_pos)), -1)

        # 右クリック: アクション実行 / 空白ならズームリセット
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            if hit_idx != -1 and self.registered_items[hit_idx].has_switch:
                item = self.registered_items[hit_idx]
                execute_action(item.action, item.select_names)
                # アクション実行後に表示条件を即時評価
                evaluate_visibility(self.registered_items)
                self.update()
            else:
                self.scale = 1.0; self.update_canvas_size(); self.update()
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if hit_idx != -1:
                item = self.registered_items[hit_idx]
                if item.next_json:
                    self.json_jump_requested.emit(item.next_json); return
            self.origin = event.position().toPoint()
            self.selection_rect = QtCore.QRect(self.origin, QtCore.QSize()); self.is_dragging = False

    def mouseMoveEvent(self, event):
        if self.last_pan_pos:
            delta = event.globalPosition().toPoint() - self.last_pan_pos
            self.pan_requested.emit(delta); self.last_pan_pos = event.globalPosition().toPoint(); return
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            if not self.is_dragging and (event.position().toPoint() - self.origin).manhattanLength() > 5:
                self.is_dragging = True
            if self.is_dragging:
                self.selection_rect = QtCore.QRect(self.origin, event.position().toPoint()).normalized()
                self.update()

    def mouseReleaseEvent(self, event):
        self.last_pan_pos = None; self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            is_ctrl = (QtWidgets.QApplication.keyboardModifiers() ==
                       QtCore.Qt.KeyboardModifier.ControlModifier)
            if self.is_dragging:
                new_sel = {i for i, item in enumerate(self.registered_items)
                           if item.visible and self.selection_rect.intersects(QtCore.QRect(
                               item.rect.x()*self.scale, item.rect.y()*self.scale,
                               item.rect.width()*self.scale, item.rect.height()*self.scale))}
                self.selected_indices = (self.selected_indices | new_sel) if is_ctrl else new_sel
            else:
                raw_pos = QtCore.QPoint(int(event.position().x() / self.scale),
                                        int(event.position().y() / self.scale))
                hit_idx = next((i for i, r in enumerate(self.registered_items)
                                if r.visible and r.rect.contains(raw_pos)), -1)
                if hit_idx != -1:
                    if is_ctrl:
                        if hit_idx in self.selected_indices: self.selected_indices.remove(hit_idx)
                        else: self.selected_indices.add(hit_idx)
                    else: self.selected_indices = {hit_idx}
                elif not is_ctrl: self.selected_indices.clear()
            self._update_max_selection(is_ctrl)
            self.is_dragging = False; self.selection_rect = QtCore.QRect(); self.update()

    def _update_max_selection(self, is_ctrl):
        nodes_to_select = []
        for idx in self.selected_indices:
            region = self.registered_items[idx]
            nodes = [mxs.getNodeByName(name) for name in region.select_names]
            nodes_to_select.extend([n for n in nodes if n])
        if nodes_to_select:
            if is_ctrl: mxs.selectMore(nodes_to_select)
            else: mxs.select(nodes_to_select)
        elif not is_ctrl:
            mxs.deselect(mxs.selection)

# ------------------------------------------------------------------ #
#  PickerPlayer
# ------------------------------------------------------------------ #

class PickerPlayer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        if parent is None:
            try:
                from qtmax import GetQMaxMainWindow
                parent = GetQMaxMainWindow()
            except ImportError: pass

        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setAcceptDrops(True)
        self.current_json_path = ""; self.current_image_name = ""; self.first_load = True

        self.main_layout = QtWidgets.QVBoxLayout(self); self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.canvas = PickerCanvas(); self.scroll.setWidget(self.canvas)
        self.main_layout.addWidget(self.scroll)

        self.canvas.pan_requested.connect(self.handle_pan)
        self.canvas.json_jump_requested.connect(self.handle_json_jump)
        self.update_title()

    def update_title(self, json_full_path=""):
        def get_stem(p): return os.path.splitext(os.path.basename(p))[0] if p else ""
        img_stem  = get_stem(self.current_image_name) if self.current_image_name else "No Image"
        target    = json_full_path if json_full_path else self.current_json_path
        json_stem = get_stem(target) if target else "No Data"
        self.setWindowTitle(f"{img_stem} | {json_stem}")

    def handle_pan(self, delta):
        h, v = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        h.setValue(h.value() - delta.x()); v.setValue(v.value() - delta.y())

    def handle_json_jump(self, target_path):
        if not os.path.isabs(target_path) and self.current_json_path:
            target_path = os.path.join(os.path.dirname(self.current_json_path), target_path)
        if os.path.exists(target_path): self.load_json(target_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.load_resource(url.toLocalFile())
        event.acceptProposedAction()

    def load_resource(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in [".png", ".jpg", ".jpeg"]:
            pix = QtGui.QPixmap(path)
            if not pix.isNull():
                self.current_image_name = os.path.basename(path); self.canvas.set_image(pix)
                if self.first_load: self.resize(pix.width(), pix.height()); self.first_load = False
                json_path = os.path.splitext(path)[0] + ".json"
                if os.path.exists(json_path): self.load_json(json_path)
                else: self.update_title()
        elif ext == ".json": self.load_json(path)

    def load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            self.current_json_path = path
            self.canvas.registered_items = []; self.canvas.selected_indices.clear()
            for d in data:
                names        = d.get("names", [d.get("name", "Unknown")])
                action       = d.get("action", None)
                visible_when = d.get("visible_when", None)
                self.canvas.registered_items.append(ClickRegion(
                    names, d["rect"], d.get("color", [0, 255, 0]),
                    d.get("shape_type", "rect"), d.get("next_json", ""), action, visible_when
                ))
            self.update_title(path)
            # ロード後に初期状態を評価
            evaluate_visibility(self.canvas.registered_items)
            self.canvas.update()
        except Exception: pass

if __name__ == "__main__":
    ui = PickerPlayer(); ui.show()
