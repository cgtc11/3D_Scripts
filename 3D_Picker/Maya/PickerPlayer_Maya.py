# -*- coding: utf-8 -*-
import json
import os
import math
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance

def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None

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
    """
    if not action:
        return
    atype = action.get("type", "attribute_toggle")
    if atype == "attribute_toggle":
        attr   = action.get("attr", "")
        values = action.get("values", [0, 1])
        if not attr:
            return
        for target in targets:
            resolved = _resolve_attr(target, attr)
            if resolved is None:
                continue
            full = f"{target}.{resolved}"
            try:
                val = cmds.getAttr(full)
                mid = (float(values[0]) + float(values[1])) / 2.0
                new_val = values[0] if float(val) >= mid else values[1]
                cmds.setAttr(full, new_val)
            except Exception:
                pass

# ------------------------------------------------------------------ #
#  表示条件評価
# ------------------------------------------------------------------ #

def evaluate_visibility(items):
    """
    各リージョンの visible_when 条件を評価し item.visible を更新する。
    visible_when が None のリージョンは常に visible=True。
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
#  共通描画関数
# ------------------------------------------------------------------ #

def draw_shape(painter, t, sr, color, is_selected):
    painter.setPen(QtGui.QPen(color, 4 if is_selected else 1))
    brush = QtGui.QBrush(color) if "_fill" in t else QtCore.Qt.NoBrush

    if t in ("rect", "rect_fill"):
        if "_fill" in t: painter.fillRect(sr, color)
        painter.drawRect(sr)
    elif t in ("circle", "circle_fill"):
        if "_fill" in t:
            painter.setBrush(brush); painter.drawEllipse(sr); painter.setBrush(QtCore.Qt.NoBrush)
        else: painter.drawEllipse(sr)
    elif t == "cross":
        cx, cy = sr.center().x(), sr.center().y()
        painter.drawLine(sr.left(), cy, sr.right(), cy); painter.drawLine(cx, sr.top(), cx, sr.bottom())
    elif "diamond" in t:
        poly = QtGui.QPolygon([QtCore.QPoint(sr.center().x(), sr.top()), QtCore.QPoint(sr.right(), sr.center().y()), QtCore.QPoint(sr.center().x(), sr.bottom()), QtCore.QPoint(sr.left(), sr.center().y())])
        if "_fill" in t: painter.setBrush(brush)
        painter.drawPolygon(poly); painter.setBrush(QtCore.Qt.NoBrush)
    elif "tri_" in t:
        if "up"    in t: pts = [sr.bottomLeft(), sr.bottomRight(), QtCore.QPoint(sr.center().x(), sr.top())]
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
        poly = QtGui.QPolygon(); center = sr.center(); ro = min(sr.width(), sr.height())/2; ri = ro/2.5
        for j in range(10):
            r = ro if j%2==0 else ri; angle = (j*36-90)*math.pi/180
            poly << QtCore.QPoint(center.x()+r*math.cos(angle), center.y()+r*math.sin(angle))
        if "_fill" in t: painter.setBrush(brush)
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
        self.action       = action        # dict or None
        self.visible_when = visible_when  # dict or None
        self.visible      = True          # ランタイムフラグ

    @property
    def has_switch(self):
        return self.action is not None

    @property
    def select_names(self):
        return list(self.names)

# ------------------------------------------------------------------ #
#  PickerCanvas
# ------------------------------------------------------------------ #

class PickerCanvas(QtWidgets.QLabel):
    pan_requested       = QtCore.Signal(QtCore.QPoint)
    json_jump_requested = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.registered_items  = []
        self.selected_indices  = set()
        self.origin            = QtCore.QPoint()
        self.selection_rect    = QtCore.QRect()
        self.is_dragging       = False
        self.scale             = 1.0
        self.pixmap_original   = None
        self.last_pan_pos      = None
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
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        for i, item in enumerate(self.registered_items):
            # 非表示アイテムはスキップ
            if not item.visible:
                continue
            sr = QtCore.QRect(
                item.rect.x()*self.scale, item.rect.y()*self.scale,
                item.rect.width()*self.scale, item.rect.height()*self.scale)
            draw_shape(painter, item.shape_type, sr, item.color, i in self.selected_indices)
            if item.has_switch:
                self._draw_switch_badge(painter, sr)
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
        mod = event.modifiers()
        if event.button() == QtCore.Qt.MouseButton.MiddleButton or \
                (event.button() == QtCore.Qt.MouseButton.LeftButton and
                 mod & QtCore.Qt.KeyboardModifier.AltModifier):
            self.last_pan_pos = event.globalPosition().toPoint()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor); return

        raw_pos = QtCore.QPoint(event.position().x() / self.scale,
                                event.position().y() / self.scale)
        # 非表示アイテムをヒット対象から除外
        hit_idx = next((i for i, r in enumerate(self.registered_items)
                        if r.visible and r.rect.contains(raw_pos)), -1)

        if event.button() == QtCore.Qt.MouseButton.RightButton:
            if hit_idx != -1 and self.registered_items[hit_idx].has_switch:
                item = self.registered_items[hit_idx]
                execute_action(item.action, item.select_names)
                # アクション実行後に表示条件を即時評価して更新
                evaluate_visibility(self.registered_items)
                self.update()
            else:
                self.scale = 1.0; self.update_canvas_size(); self.update()
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if hit_idx != -1:
                item = self.registered_items[hit_idx]
                if item.next_json and not (mod & QtCore.Qt.KeyboardModifier.ShiftModifier):
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
            is_shift = (QtWidgets.QApplication.keyboardModifiers() ==
                        QtCore.Qt.KeyboardModifier.ShiftModifier)
            if self.is_dragging:
                new_sel = {i for i, item in enumerate(self.registered_items)
                           if item.visible and self.selection_rect.intersects(QtCore.QRect(
                               item.rect.x()*self.scale, item.rect.y()*self.scale,
                               item.rect.width()*self.scale, item.rect.height()*self.scale))}
                self.selected_indices = (self.selected_indices | new_sel) if is_shift else new_sel
            else:
                raw_pos = QtCore.QPoint(event.position().x() / self.scale,
                                        event.position().y() / self.scale)
                hit_idx = next((i for i, r in enumerate(self.registered_items)
                                if r.visible and r.rect.contains(raw_pos)), -1)
                if hit_idx != -1:
                    if is_shift:
                        if hit_idx in self.selected_indices: self.selected_indices.remove(hit_idx)
                        else: self.selected_indices.add(hit_idx)
                    else: self.selected_indices = {hit_idx}
                elif not is_shift: self.selected_indices.clear()
            self._update_maya_selection(is_shift)
            self.is_dragging = False; self.selection_rect = QtCore.QRect(); self.update()

    def _update_maya_selection(self, is_shift):
        nodes = []
        for idx in self.selected_indices:
            nodes.extend([n for n in self.registered_items[idx].select_names
                          if cmds.objExists(n)])
        if nodes: cmds.select(nodes, replace=not is_shift, add=is_shift)
        elif not is_shift: cmds.select(clear=True)

# ------------------------------------------------------------------ #
#  PickerPlayerMaya
# ------------------------------------------------------------------ #

class PickerPlayerMaya(QtWidgets.QWidget):
    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setAcceptDrops(True)

        self.setup_window_icon()
        self.current_json_path = ""
        self.current_image_name = ""
        self.first_load = True

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.canvas = PickerCanvas()
        self.scroll.setWidget(self.canvas)
        self.main_layout.addWidget(self.scroll)

        self.canvas.pan_requested.connect(self.handle_pan)
        self.canvas.json_jump_requested.connect(self.handle_json_jump)
        self.update_title()

    def setup_window_icon(self):
        script_dir = os.path.dirname(__file__) if "__file__" in globals() else ""
        icon_path = os.path.join(script_dir, "PickerPlayer.png")
        if os.path.exists(icon_path): self.setWindowIcon(QtGui.QIcon(icon_path))

    def update_title(self, json_full_path=""):
        def get_stem(p): return os.path.splitext(os.path.basename(p))[0] if p else ""
        target_json = json_full_path if json_full_path else self.current_json_path
        json_stem = get_stem(target_json)
        self.setWindowTitle(f"Maya Picker | {json_stem if json_stem else 'No Data'}")

    def handle_pan(self, delta):
        h, v = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        h.setValue(h.value() - delta.x()); v.setValue(v.value() - delta.y())

    def handle_json_jump(self, target_path):
        if not os.path.isabs(target_path) and self.current_json_path:
            target_path = os.path.normpath(
                os.path.join(os.path.dirname(self.current_json_path), target_path))
        if os.path.exists(target_path): self.load_json(target_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.load_resource(url.toLocalFile())
        event.acceptProposedAction()

    def load_resource(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg"):
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
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_json_path = path
            self.canvas.registered_items = []; self.canvas.selected_indices.clear()
            for d in data:
                names        = d.get("names", [d.get("name", "Unknown")])
                action       = d.get("action", None)
                visible_when = d.get("visible_when", None)

                # 後方互換: 旧 .Switch サフィックス形式を自動変換
                if action is None:
                    sw = [n for n in names if n.endswith(".Switch")]
                    if sw:
                        obj = sw[0][:-len(".Switch")]
                        action = {"type": "attribute_toggle", "target": obj, "attr": "", "values": [0, 1]}
                        names = [n[:-len(".Switch")] if n.endswith(".Switch") else n for n in names]

                self.canvas.registered_items.append(ClickRegion(
                    names, d["rect"], d.get("color", [0, 255, 0]),
                    d.get("shape_type", "rect"), d.get("next_json", ""),
                    action, visible_when
                ))
            self.update_title(path)
            evaluate_visibility(self.canvas.registered_items)
            self.canvas.update()
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    ui = PickerPlayerMaya()
    ui.show()
