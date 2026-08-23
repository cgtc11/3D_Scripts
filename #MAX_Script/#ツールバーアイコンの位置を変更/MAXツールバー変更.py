# -*- coding: utf-8 -*-
r"""
MAXのツールバー配置変更.py
3ds Max の .cuix (UIカスタムファイル) のツールバーのボタン順を
GUIで確認・並び替え・上書き保存するツール。

使い方: このファイルをダブルクリックして起動。
        最初にファイル選択ダイアログが出るので .cuix ファイルを選ぶ。
"""

import tkinter as tk
from tkinter import ttk, filedialog
import xml.etree.ElementTree as ET
import shutil
import os

# ---------------- 3ds Max 風カラーパレット ----------------
BG_MAIN      = "#3a3a3a"   # メイン背景（Maxのパネルグレー）
BG_PANEL     = "#333333"   # パネル背景
BG_LIST      = "#232323"   # リスト背景（Maxのビューポート寄りの濃さ）
FG_TEXT      = "#d6d6d6"   # 通常テキスト
FG_DIM       = "#8a8a8a"   # 補助テキスト
ACCENT       = "#3ea6ff"   # 選択ハイライト（Maxのアクセントブルー）
ACCENT_DARK  = "#1f6fae"
BORDER       = "#1e1e1e"
BTN_BG       = "#4a4a4a"
BTN_ACTIVE   = "#5a5a5a"
BTN_PRESSED  = "#2f2f2f"

FONT_UI   = ("Segoe UI", 9)
FONT_HEAD = ("Segoe UI", 9, "bold")


class CuixReorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("3ds Max ツールバー並び替え")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(680, 420)

        self.file_path = None
        self.tree = None
        self.xml_root = None
        self.windows = []              # [(index, Element), ...]
        self.current_items_elem = None
        self.current_items = []        # 編集中のItem要素のリスト（並び順そのまま）

        self._setup_style()
        self._build_ui()
        # 起動時は自動で開かず、ボタンを押すまで待つ

    # ---------------- スタイル設定 ----------------
    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG_MAIN, foreground=FG_TEXT, font=FONT_UI)
        style.configure("TFrame", background=BG_MAIN)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG_MAIN, foreground=FG_TEXT, font=FONT_UI)
        style.configure("Head.TLabel", background=BG_MAIN, foreground=FG_DIM, font=FONT_HEAD)
        style.configure("Status.TLabel", background=BG_MAIN, foreground=ACCENT, font=FONT_UI)
        style.configure("Path.TLabel", background=BG_MAIN, foreground=FG_DIM, font=FONT_UI)

        style.configure(
            "TButton",
            background=BTN_BG,
            foreground=FG_TEXT,
            bordercolor=BORDER,
            focusthickness=0,
            focuscolor=BTN_BG,
            padding=(10, 5),
            font=FONT_UI,
        )
        style.map(
            "TButton",
            background=[("active", BTN_ACTIVE), ("pressed", BTN_PRESSED)],
            foreground=[("disabled", FG_DIM)],
        )

        style.configure(
            "Accent.TButton",
            background=ACCENT_DARK,
            foreground="#ffffff",
            bordercolor=BORDER,
            focusthickness=0,
            focuscolor=ACCENT_DARK,
            padding=(12, 5),
            font=FONT_HEAD,
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT), ("pressed", ACCENT_DARK)],
        )

        style.configure("Vertical.TScrollbar",
                         background=BTN_BG, troughcolor=BG_LIST,
                         bordercolor=BG_MAIN, arrowcolor=FG_TEXT)

    def _make_listbox(self, parent):
        lb = tk.Listbox(
            parent,
            bg=BG_LIST,
            fg=FG_TEXT,
            selectbackground=ACCENT_DARK,
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            bd=0,
            font=FONT_UI,
            activestyle="none",
            exportselection=False,
        )
        return lb

    # ---------------- UI構築 ----------------
    def _build_ui(self):
        # ---- 上部: 案内文 ----
        info = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        info.pack(fill="x")
        self.info_label = ttk.Label(
            info,
            text="カスタマイズ＞ユーザーインターフェイスをカスタマイズ＞ツールバー＞保存　で書き出した〇〇.cuixを読み込んでください。",
            style="Path.TLabel",
            anchor="w",
            justify="left",
        )
        self.info_label.pack(fill="x")
        self.root.bind("<Configure>", self._on_root_resize)

        # ---- 上部: ファイルパス ----
        top = ttk.Frame(self.root, padding=(10, 4, 10, 4))
        top.pack(fill="x")
        self.path_label = ttk.Label(top, text="ファイル未選択", style="Path.TLabel", anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="ファイルを開く...", command=self.open_file).pack(side="right")

        # ---- 区切り線 ----
        sep1 = tk.Frame(self.root, bg=BORDER, height=1)
        sep1.pack(fill="x", padx=0)

        # ---- メインエリア ----
        main = ttk.Frame(self.root, padding=(10, 8, 10, 8))
        main.pack(fill="both", expand=True)

        # 左: ツールバー一覧
        left = ttk.Frame(main, style="Panel.TFrame")
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="ツールバー / ウィンドウ一覧", style="Head.TLabel").pack(
            anchor="w", padx=2, pady=(0, 4)
        )
        self.toolbar_list = self._make_listbox(left)
        self.toolbar_list.pack(fill="both", expand=True)
        self.toolbar_list.bind("<<ListboxSelect>>", self.on_toolbar_select)

        # 中央: 矢印区切り
        mid = ttk.Frame(main)
        mid.pack(side="left", fill="y", padx=8)
        ttk.Label(mid, text="→", font=("Segoe UI", 14), foreground=FG_DIM).pack(
            expand=True
        )

        # 右: アイテム一覧 + 並び替えボタン
        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(0, 0))
        ttk.Label(right, text="ボタン並び（選択して ▲▼ で移動）", style="Head.TLabel").pack(
            anchor="w", padx=2, pady=(0, 4)
        )

        list_row = ttk.Frame(right)
        list_row.pack(fill="both", expand=True)
        self.item_list = self._make_listbox(list_row)
        self.item_list.pack(side="left", fill="both", expand=True)

        move_col = ttk.Frame(list_row)
        move_col.pack(side="left", fill="y", padx=(6, 0))
        ttk.Button(move_col, text="▲", width=3, command=self.move_up).pack(pady=(0, 4))
        ttk.Button(move_col, text="▼", width=3, command=self.move_down).pack()

        gap = tk.Frame(move_col, bg=BG_MAIN, height=14)
        gap.pack()

        ttk.Button(
            move_col, text="セパレータ追加", command=self.add_separator
        ).pack(pady=(0, 4), fill="x")
        ttk.Button(
            move_col, text="削除", command=self.delete_item
        ).pack(fill="x")

        # ---- 下部: ステータス + 保存 ----
        sep2 = tk.Frame(self.root, bg=BORDER, height=1)
        sep2.pack(fill="x")

        bottom = ttk.Frame(self.root, padding=(10, 6, 10, 8))
        bottom.pack(fill="x")
        self.status_label = ttk.Label(
            bottom,
            text="",
            style="Status.TLabel",
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            bottom, text="上書き保存", style="Accent.TButton", command=self.save
        ).pack(side="right")

    def _on_root_resize(self, event):
        if event.widget is not self.root:
            return
        new_wrap = max(200, event.width - 20)
        if self.info_label.cget("wraplength") != new_wrap:
            self.info_label.config(wraplength=new_wrap)

    # ---------------- ファイル読み込み ----------------
    def open_file(self):
        path = filedialog.askopenfilename(
            title="cuixファイルを選択",
            filetypes=[("3ds Max UI files", "*.cuix"), ("All files", "*.*")],
        )
        if not path:
            if self.file_path is None:
                self.status_label.config(text="ファイルが選択されませんでした。")
            return

        try:
            tree = ET.parse(path)
        except Exception as e:
            self.status_label.config(text="読み込み失敗: {}".format(e))
            return

        self.file_path = path
        self.tree = tree
        self.xml_root = tree.getroot()
        self.path_label.config(text=path)
        self.load_windows()

    def load_windows(self):
        self.windows = list(
            enumerate(self.xml_root.findall(".//CUIWindows/Window"), start=1)
        )
        self.toolbar_list.delete(0, "end")
        for i, w in self.windows:
            objname = w.get("objectName", "")
            name = w.get("name", "")
            wtype = w.get("type", "")
            kind = "[ツールバー]" if wtype == "T" else "[その他]"
            self.toolbar_list.insert(
                "end", "  {}.  {}  ({})  {}".format(i, name, objname, kind)
            )
        self.item_list.delete(0, "end")
        self.current_items_elem = None
        self.current_items = []

    # ---------------- ツールバー選択 ----------------
    def on_toolbar_select(self, event):
        sel = self.toolbar_list.curselection()
        if not sel:
            return
        _, w = self.windows[sel[0]]
        items_elem = w.find("Items")
        self.item_list.delete(0, "end")

        if items_elem is None:
            self.current_items_elem = None
            self.current_items = []
            self.status_label.config(text="このウィンドウはボタンを持たないタイプです。")
            return

        self.current_items_elem = items_elem
        self.current_items = list(items_elem)
        self.refresh_item_list()

    @staticmethod
    def get_item_label(item):
        if item.get("type") == "CTB_SEPARATOR":
            return "— (セパレータ) —"
        for attr in ("label", "tip", "actionID", "iconName"):
            v = item.get(attr)
            if v:
                return v
        return "(名称不明アイテム)"

    def refresh_item_list(self):
        self.item_list.delete(0, "end")
        for i, itm in enumerate(self.current_items, start=1):
            self.item_list.insert("end", "  {}.  {}".format(i, self.get_item_label(itm)))

    # ---------------- 並び替え ----------------
    def move_up(self):
        sel = self.item_list.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self.current_items[i - 1], self.current_items[i] = (
            self.current_items[i],
            self.current_items[i - 1],
        )
        self.refresh_item_list()
        self.item_list.selection_set(i - 1)

    def move_down(self):
        sel = self.item_list.curselection()
        if not sel or sel[0] == len(self.current_items) - 1:
            return
        i = sel[0]
        self.current_items[i + 1], self.current_items[i] = (
            self.current_items[i],
            self.current_items[i + 1],
        )
        self.refresh_item_list()
        self.item_list.selection_set(i + 1)

    def add_separator(self):
        if self.current_items_elem is None:
            self.status_label.config(text="先にツールバーを選択してください。")
            return

        sep = ET.Element(
            "Item",
            {
                "typeID": "3",
                "type": "CTB_SEPARATOR",
                "width": "6",
                "height": "16",
                "orientation": "31",
                "visible": "1",
            },
        )

        sel = self.item_list.curselection()
        idx = (sel[0] + 1) if sel else len(self.current_items)
        self.current_items.insert(idx, sep)
        self.refresh_item_list()
        self.item_list.selection_clear(0, "end")
        self.item_list.selection_set(idx)
        self.item_list.see(idx)

    def delete_item(self):
        sel = self.item_list.curselection()
        if not sel:
            self.status_label.config(text="削除する項目を選択してください。")
            return
        idx = sel[0]
        del self.current_items[idx]
        self.refresh_item_list()
        if self.current_items:
            new_sel = min(idx, len(self.current_items) - 1)
            self.item_list.selection_set(new_sel)

    # ---------------- 保存 ----------------
    def save(self):
        if self.file_path is None or self.tree is None:
            self.status_label.config(text="ファイルが読み込まれていません。")
            return

        if self.current_items_elem is not None:
            for itm in list(self.current_items_elem):
                self.current_items_elem.remove(itm)
            for itm in self.current_items:
                self.current_items_elem.append(itm)

        backup_path = self.file_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(self.file_path, backup_path)

        self.tree.write(self.file_path, encoding="utf-8", xml_declaration=False)
        with open(self.file_path, "r", encoding="utf-8") as f:
            body = f.read()
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8" ?>\n')
            f.write(body)

        self.status_label.config(
            text="保存しました: {}   (バックアップ: {})".format(self.file_path, backup_path)
        )


def main():
    root = tk.Tk()
    root.geometry("780x480")
    CuixReorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
