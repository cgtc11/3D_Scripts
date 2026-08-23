import base64
import codecs
import html
import io
import os
import re
import shutil
import subprocess
import tempfile
import tkinter as tk
import xml.etree.ElementTree as ET
from tkinter import messagebox, ttk, filedialog
from PIL import Image

DEFAULT_TOOLBAR_IDENTITIES = {
    "Main Toolbar",
    "Axis Constraints",
    "Layers",
    "State Sets",
    "Extras",
    "Render Shortcuts",
    "Snaps",
    "Animation Layers",
    "Containers",
    "MassFX Toolbar",
    "SnapPivotToolbar",
    "メイン ツールバー",
    "軸コンストレイント",
    "レイヤ",
    "ステート セット",
    "拡張",
    "レンダリング ショートカット",
    "スナップ",
    "アニメーション レイヤ",
    "コンテナ",
    "MassFX ツールバー",
    "作業基点スナップ ツール",
}

DEFAULT_ICON_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQQAAAEECAYAAADOCEoKAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAE8WlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFj"
    "a2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0"
    "az0iQWRvYmUgWE1QIENvcmUgMTAuMC1jMDAwIDI1LkcuZDIwZTQ2NiwgMjAyNS8xMi8wOC0yMDo1MDoyMSAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRm"
    "PSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJo"
    "dHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0i"
    "aHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0"
    "RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI3"
    "LjggKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wOC0wNVQxNTo0NToyOCswOTowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDgtMDVUMTU6NDk6"
    "MDUrMDk6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDgtMDVUMTU6NDk6MDUrMDk6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29s"
    "b3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOmNiMjE3OTJlLTY2YTMtY2U0Zi05MDhhLWEzOWQ4YmYyNzMxNyIgeG1wTU06RG9jdW1lbnRJ"
    "RD0ieG1wLmRpZDpjYjIxNzkyZS02NmEzLWNlNGYtOTA4YS1hMzlkOGJmMjczMTciIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpjYjIxNzky"
    "ZS02NmEzLWNlNGYtOTA4YS1hMzlkOGJmMjczMTciPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBz"
    "dEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOmNiMjE3OTJlLTY2YTMtY2U0Zi05MDhhLWEzOWQ4YmYyNzMxNyIgc3RFdnQ6d2hlbj0iMjAyNi0wOC0wNVQxNTo0"
    "NToyOCswOTowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI3LjggKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0"
    "b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/PtXeDAoAADlNSURBVHic7Z0LkKTXVd/P"
    "1+/u6el5z+zOzj61a60WpNVakmVhLGHiMjiiwCkgNnERKAiQAJUKTkxVqBDMoygqJuZRmFTCm0RlE5QqBaM4VsAqLLAk6y3ZK613pX3Nzuy8Z/rd/b1S/3P7"
    "9vb09vRj+t19fqVWz+x093e/r7/7v+eec+65huu6JAiCADxyGQRB0Pioj3nxZjq2lcmfeTue+d6vryd+cjtvTW2mTdrMWd1umiBUxMD/XJeiPg+N+b00GvTR"
    "TCR4/tBo+O+nI8HX50eCz3zg6Ojr1CX6UhBevJmJJU1rYSdnnornzSe2cyaZjkuW7ZLDV1wQehPXdckwDL5fU45Ldt4mx8ifybt0BgPZZtb87M10/vWZcOCl"
    "Dx4bfanT7TP6yYfwykomvJkzz2xl86cSpvW5nbxFacumzYxFa5k8pfI2xXM2xfNiIQi9jccg8hoGeQyDn/0eg0I+D0UDPor6fXTX5Mh/e/ds7DcfPhy92Ml2"
    "9Y2F8MpqJhzPW8fjOfPFnbxJSdPmR8ayKWc7ZDsuOS6RS/0jcMLw4rh44F69db+mLYMytksJ06bJsP8n1zPmU19dTGW+bWFksVPt6mlBeHUl48/ZzmTKsud2"
    "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"
    "rkJggg=="
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

class StandaloneMaxInstaller(TkinterDnD.Tk if HAS_DND else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3ds Max ツール一括インストーラー v14")
        self.geometry("1140x620")
        self.minsize(1080, 600)

        # タイトルバーとタスクバーに内蔵のRegisterScript.pngを使用する。
        self._window_icon = tk.PhotoImage(data=DEFAULT_ICON_PNG_BASE64)
        self.iconphoto(True, self._window_icon)
        
        self.selected_files = []
        self.cuix_path = ""
        self.workspace_cuix_path = ""
        self.script_records = {}
        self.toolbar_records = {}

        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(main_frame, width=430, bd=1, relief=tk.GROOVE)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_frame.pack_propagate(False)

        # ── バージョン選択エリア ──
        frame_ver = tk.Frame(self.left_frame, padx=10, pady=6)
        frame_ver.pack(fill=tk.X)
        
        tk.Label(frame_ver, text="対象 3ds Max Ver:", font=("Meiryo", 9, "bold"), width=14, anchor="w").pack(side=tk.LEFT)
        
        self.max_root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Autodesk", "3dsMax")
        installed_versions = self.find_3dsmax_versions()

        self.ver_cb = ttk.Combobox(frame_ver, values=installed_versions, width=10, state="readonly", font=("Meiryo", 9))
        if installed_versions:
            self.ver_cb.set(installed_versions[0])
        else:
            self.ver_cb.configure(state="disabled")
        self.ver_cb.pack(side=tk.LEFT, padx=5)
        self.ver_cb.bind("<<ComboboxSelected>>", self.update_paths)

        # ── usermacrosパス設定エリア ──
        frame_mcr = tk.Frame(self.left_frame, padx=10, pady=2)
        frame_mcr.pack(fill=tk.X)
        tk.Label(frame_mcr, text="usermacros:", font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        self.ent_mcr = tk.Entry(frame_mcr, font=("Meiryo", 9))
        self.ent_mcr.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.btn_open_mcr = tk.Button(frame_mcr, text="開く", font=("Meiryo", 8, "bold"), width=8, command=lambda: self.open_folder(self.ent_mcr.get()))
        self.btn_open_mcr.pack(side=tk.LEFT)

        # ── userscriptsパス設定エリア (Python用追加) ──
        frame_scr = tk.Frame(self.left_frame, padx=10, pady=2)
        frame_scr.pack(fill=tk.X)
        tk.Label(frame_scr, text="userscripts:", font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        self.ent_scr = tk.Entry(frame_scr, font=("Meiryo", 9))
        self.ent_scr.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.btn_open_scr = tk.Button(frame_scr, text="開く", font=("Meiryo", 8, "bold"), width=8, command=lambda: self.open_folder(self.ent_scr.get()))
        self.btn_open_scr.pack(side=tk.LEFT)

        # ── usericonsパス設定エリア ──
        frame_ico = tk.Frame(self.left_frame, padx=10, pady=2)
        frame_ico.pack(fill=tk.X)
        tk.Label(frame_ico, text="usericons:", font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        self.ent_ico = tk.Entry(frame_ico, font=("Meiryo", 9))
        self.ent_ico.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.btn_open_ico = tk.Button(frame_ico, text="開く", font=("Meiryo", 8, "bold"), width=8, command=lambda: self.open_folder(self.ent_ico.get()))
        self.btn_open_ico.pack(side=tk.LEFT)
        
        self.update_paths(None)

        # ── カテゴリ設定エリア ──
        frame_cat = tk.Frame(self.left_frame, padx=10, pady=2)
        frame_cat.pack(fill=tk.X)
        tk.Label(frame_cat, text="Category:", font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        self.ent_cat = tk.Entry(frame_cat, font=("Meiryo", 9))
        self.ent_cat.insert(0, "# Scripts")
        self.ent_cat.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.ent_cat.bind("<KeyRelease>", self.update_preview)

        # ── ツールバー名設定エリア ──
        frame_toolbar = tk.Frame(self.left_frame, padx=10, pady=2)
        frame_toolbar.pack(fill=tk.X)
        tk.Label(frame_toolbar, text="ツールバー名:", font=("Meiryo", 9), width=12, anchor="w").pack(side=tk.LEFT)
        self.ent_toolbar = tk.Entry(frame_toolbar, font=("Meiryo", 9))
        self.ent_toolbar.insert(0, "# Scripts")
        self.ent_toolbar.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.ent_toolbar.bind("<KeyRelease>", self.update_preview)
        
        # ── ファイル選択エリア ──
        frame_file = tk.Frame(self.left_frame, padx=10, pady=6)
        frame_file.pack(fill=tk.X)
        
        self.btn_select = tk.Button(frame_file, text="ファイルを選択 (.py / .ms / .mcr / .png)", font=("Meiryo", 9, "bold"), bg="#f1f5f9", fg="#1e293b", command=self.open_file_dialog)
        self.btn_select.pack(fill=tk.X, pady=2)
        
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.handle_drop)

        # ── プレビュー・確認エリア ──
        frame_info = tk.LabelFrame(self.left_frame, text=" 選択ファイル & 保存先プレビュー ", font=("Meiryo", 9, "bold"), padx=10, pady=6)
        frame_info.pack(fill=tk.X, padx=10, pady=4)
        
        self.lbl_file_status = tk.Label(frame_info, text="選択ファイル: なし", font=("Meiryo", 9), anchor="w", fg="#334155")
        self.lbl_file_status.pack(fill=tk.X)
        
        self.lbl_save_status = tk.Label(frame_info, text="保存名: -", font=("Meiryo", 9, "bold"), anchor="w", fg="#0369a1", justify="left")
        self.lbl_save_status.pack(fill=tk.X, pady=2)

        # ── 実行ボタン ──
        self.btn_execute = tk.Button(self.left_frame, text="変換・配置・ツールバー登録を実行", font=("Meiryo", 10, "bold"), bg="#94a3b8", fg="#ffffff", state=tk.DISABLED, command=self.execute_process)
        self.btn_execute.pack(fill=tk.X, padx=10, pady=8)

        self.build_management_panel()
        self.refresh_management_lists()

    def find_3dsmax_versions(self):
        if not os.path.isdir(self.max_root):
            return []
        versions = []
        try:
            for entry in os.scandir(self.max_root):
                if not entry.is_dir():
                    continue
                match = re.fullmatch(r"(\d{4}) - 64bit", entry.name)
                if match:
                    versions.append(match.group(1))
        except OSError:
            return []
        return sorted(set(versions), key=int, reverse=True)

    def build_management_panel(self):
        """右側に登録済みスクリプトと標準外ツールバーの管理欄を作成する。"""
        header = tk.Frame(self.right_frame, padx=8, pady=8)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="登録済み項目の管理",
            font=("Meiryo", 10, "bold")
        ).pack(side=tk.LEFT)
        tk.Button(
            header,
            text="再読込",
            width=8,
            font=("Meiryo", 8, "bold"),
            command=self.refresh_management_lists
        ).pack(side=tk.RIGHT)

        script_frame = tk.LabelFrame(
            self.right_frame,
            text=" 登録スクリプト（usermacros） ",
            font=("Meiryo", 9, "bold"),
            padx=6,
            pady=6
        )
        script_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        script_tree_frame = tk.Frame(script_frame)
        script_tree_frame.pack(fill=tk.BOTH, expand=True)
        self.script_tree = ttk.Treeview(
            script_tree_frame,
            columns=("macro", "category", "toolbar"),
            show="headings",
            selectmode="extended",
            height=10
        )
        self.script_tree.heading("macro", text="スクリプト")
        self.script_tree.heading("category", text="Category")
        self.script_tree.heading("toolbar", text="ツールバー")
        self.script_tree.column("macro", width=145, minwidth=100, anchor=tk.W)
        self.script_tree.column("category", width=100, minwidth=75, anchor=tk.W)
        self.script_tree.column("toolbar", width=125, minwidth=90, anchor=tk.W)
        script_scroll = ttk.Scrollbar(
            script_tree_frame,
            orient=tk.VERTICAL,
            command=self.script_tree.yview
        )
        self.script_tree.configure(yscrollcommand=script_scroll.set)
        self.script_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        script_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(
            script_frame,
            text="選択スクリプトを削除",
            font=("Meiryo", 9, "bold"),
            bg="#fee2e2",
            fg="#991b1b",
            command=self.delete_selected_scripts
        ).pack(fill=tk.X, pady=(6, 0))

        toolbar_frame = tk.LabelFrame(
            self.right_frame,
            text=" 標準以外のツールバー ",
            font=("Meiryo", 9, "bold"),
            padx=6,
            pady=6
        )
        toolbar_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        toolbar_tree_frame = tk.Frame(toolbar_frame)
        toolbar_tree_frame.pack(fill=tk.BOTH, expand=True)
        self.toolbar_tree = ttk.Treeview(
            toolbar_tree_frame,
            columns=("toolbar", "source"),
            show="headings",
            selectmode="extended",
            height=8
        )
        self.toolbar_tree.heading("toolbar", text="ツールバー")
        self.toolbar_tree.heading("source", text="登録先")
        self.toolbar_tree.column("toolbar", width=235, minwidth=130, anchor=tk.W)
        self.toolbar_tree.column("source", width=115, minwidth=90, anchor=tk.W)
        toolbar_scroll = ttk.Scrollbar(
            toolbar_tree_frame,
            orient=tk.VERTICAL,
            command=self.toolbar_tree.yview
        )
        self.toolbar_tree.configure(yscrollcommand=toolbar_scroll.set)
        self.toolbar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        toolbar_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Button(
            toolbar_frame,
            text="選択ツールバーを削除",
            font=("Meiryo", 9, "bold"),
            bg="#fee2e2",
            fg="#991b1b",
            command=self.delete_selected_toolbars
        ).pack(fill=tk.X, pady=(6, 0))

        self.management_status = tk.Label(
            self.right_frame,
            text="",
            font=("Meiryo", 8),
            fg="#475569",
            anchor="w"
        )
        self.management_status.pack(fill=tk.X, padx=10, pady=(0, 8))

    def read_macro_text(self, file_path):
        """MacroScriptをUTF-8または日本語Windows環境の文字コードで読み込む。"""
        with open(file_path, "rb") as source_file:
            raw_data = source_file.read()
        for encoding in ("utf-8-sig", "cp932"):
            try:
                return raw_data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_data.decode("utf-8", errors="replace")

    def collect_registered_scripts(self):
        """usermacros内の.mcrを、削除対象となる登録スクリプトとして収集する。"""
        records = []
        macro_dir = self.ent_mcr.get().strip()
        if not os.path.isdir(macro_dir):
            return records

        toolbar_locations = self.collect_action_toolbar_locations()

        for file_name in sorted(os.listdir(macro_dir), key=str.lower):
            if not file_name.lower().endswith(".mcr"):
                continue
            mcr_path = os.path.join(macro_dir, file_name)
            if not os.path.isfile(mcr_path):
                continue
            base_name = os.path.splitext(file_name)[0]
            try:
                content = self.read_macro_text(mcr_path)
                macro_name, category_name = self.extract_macro_identity(
                    content,
                    base_name,
                    ""
                )
            except OSError:
                macro_name = base_name
                category_name = ""
            action_id = f"{macro_name}`{category_name}"
            records.append({
                "base_name": base_name,
                "macro_name": macro_name,
                "category": category_name,
                "action_id": action_id,
                "toolbar": self.format_toolbar_locations(
                    toolbar_locations.get(action_id, {})
                ),
                "mcr_path": mcr_path,
            })
        return records

    def collect_action_toolbar_locations(self):
        """両CUIXを解析し、actionIDごとの登録ツールバーを収集する。"""
        locations = {}
        source_paths = (
            ("MaxStart", self.cuix_path),
            ("Workspace", self.workspace_cuix_path),
        )

        for source_name, cuix_path in source_paths:
            if not os.path.isfile(cuix_path):
                continue
            try:
                text_data, _, _ = self.load_cuix_text(cuix_path)
                root = ET.fromstring(text_data)
            except (OSError, ValueError, ET.ParseError):
                continue

            for window in root.findall(".//Window"):
                if window.get("type") != "T":
                    continue
                object_name = (window.get("objectName") or "").strip()
                toolbar_name = (window.get("name") or object_name).strip()
                if not toolbar_name:
                    continue

                for item in window.findall(".//Item"):
                    action_id = (item.get("actionID") or "").strip()
                    if not action_id:
                        continue
                    source_locations = locations.setdefault(action_id, {})
                    source_locations.setdefault(source_name, set()).add(toolbar_name)

        return locations

    @staticmethod
    def format_toolbar_locations(source_locations):
        """CUIXごとの配置先を、一覧表示向けの短い文字列へ整形する。"""
        if not source_locations:
            return "（未登録）"

        maxstart_names = source_locations.get("MaxStart", set())
        workspace_names = source_locations.get("Workspace", set())

        if maxstart_names and maxstart_names == workspace_names:
            return " / ".join(sorted(maxstart_names, key=str.lower))

        parts = []
        for source_name, names in (
            ("MaxStart", maxstart_names),
            ("Workspace", workspace_names),
        ):
            if names:
                toolbar_text = " / ".join(sorted(names, key=str.lower))
                parts.append(f"{source_name}: {toolbar_text}")
        return " / ".join(parts) if parts else "（未登録）"

    def collect_custom_toolbars(self):
        """両CUIXから3ds Max 2025の標準ツールバーを除いたツールバーを収集する。"""
        records = {}
        source_paths = (
            ("MaxStart", self.cuix_path),
            ("Workspace", self.workspace_cuix_path),
        )
        for source_name, cuix_path in source_paths:
            if not os.path.isfile(cuix_path):
                continue
            try:
                text_data, _, _ = self.load_cuix_text(cuix_path)
                root = ET.fromstring(text_data)
            except (OSError, ValueError, ET.ParseError):
                continue

            for window in root.findall(".//Window"):
                if window.get("type") != "T":
                    continue
                object_name = (window.get("objectName") or "").strip()
                display_name = (window.get("name") or object_name).strip()
                identity = object_name or display_name
                if not identity:
                    continue
                if (
                    object_name in DEFAULT_TOOLBAR_IDENTITIES
                    or display_name in DEFAULT_TOOLBAR_IDENTITIES
                ):
                    continue
                record = records.setdefault(identity, {
                    "identity": identity,
                    "display_name": display_name or identity,
                    "sources": set(),
                })
                record["sources"].add(source_name)
        return sorted(records.values(), key=lambda item: item["display_name"].lower())

    def refresh_management_lists(self):
        """右側のスクリプト・ツールバー一覧を現在のファイル内容から更新する。"""
        if not hasattr(self, "script_tree"):
            return

        for item_id in self.script_tree.get_children():
            self.script_tree.delete(item_id)
        for item_id in self.toolbar_tree.get_children():
            self.toolbar_tree.delete(item_id)

        self.script_records = {}
        for index, record in enumerate(self.collect_registered_scripts()):
            item_id = f"script_{index}"
            self.script_records[item_id] = record
            self.script_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    record["base_name"],
                    record["category"] or "（未取得）",
                    record["toolbar"]
                )
            )

        self.toolbar_records = {}
        for index, record in enumerate(self.collect_custom_toolbars()):
            item_id = f"toolbar_{index}"
            self.toolbar_records[item_id] = record
            source_text = "両方" if len(record["sources"]) == 2 else next(iter(record["sources"]))
            self.toolbar_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(record["display_name"], source_text)
            )

        self.management_status.config(
            text=f"スクリプト {len(self.script_records)}件 / ツールバー {len(self.toolbar_records)}件"
        )

    def update_paths(self, event):
        ver = self.ver_cb.get()
        if not ver:
            self.cuix_path = ""
            self.workspace_cuix_path = ""
            for ent in (self.ent_mcr, self.ent_scr, self.ent_ico):
                ent.delete(0, tk.END)
            for btn in (self.btn_open_mcr, self.btn_open_scr, self.btn_open_ico):
                self.update_button_status(btn, "")
            self.refresh_management_lists()
            return

        base_dir = os.path.join(self.max_root, f"{ver} - 64bit", "JPN")
        
        mcr_path = os.path.join(base_dir, "usermacros")
        scr_path = os.path.join(base_dir, "scripts") # Python用の配置先
        ico_path = os.path.join(base_dir, "usericons")
        ui_dir = os.path.join(base_dir, "ja-JP", "UI")
        self.cuix_path = os.path.join(ui_dir, "MaxStartUI.cuix")
        self.workspace_cuix_path = os.path.join(
            ui_dir,
            "Workspaces",
            "usersave",
            "Workspace1__usersave__.cuix"
        )
        
        self.ent_mcr.delete(0, tk.END)
        self.ent_mcr.insert(0, mcr_path)
        
        self.ent_scr.delete(0, tk.END)
        self.ent_scr.insert(0, scr_path)
        
        self.ent_ico.delete(0, tk.END)
        self.ent_ico.insert(0, ico_path)

        self.update_button_status(self.btn_open_mcr, mcr_path)
        self.update_button_status(self.btn_open_scr, scr_path)
        self.update_button_status(self.btn_open_ico, ico_path)
        self.refresh_management_lists()

    def update_button_status(self, btn, path):
        if os.path.exists(path):
            btn.config(bg="#e0f2fe", fg="#0369a1", state=tk.NORMAL)
        else:
            btn.config(bg="#fee2e2", fg="#991b1b", state=tk.DISABLED)

    def open_folder(self, path):
        if os.path.exists(path):
            subprocess.Popen(f'explorer "{path}"')
        else:
            messagebox.showwarning("フォルダなし", f"指定されたフォルダは存在しません:\n\n{path}")

    def handle_drop(self, event):
        files = self.tk.splitlist(event.data)
        cleaned_files = [f.strip('{}') for f in files]
        self.set_selected_files(cleaned_files)

    def open_file_dialog(self):
        files = filedialog.askopenfilenames(
            title="スクリプトやアイコン画像を選択",
            filetypes=[
                ("サポート対象ファイル", "*.py *.ms *.mcr *.png"),
                ("Python (.py)", "*.py"),
                ("MAXScript (.ms)", "*.ms"),
                ("MacroScript (.mcr)", "*.mcr"),
                ("PNG画像 (.png)", "*.png"),
                ("すべてのファイル", "*.*")
            ]
        )
        if files:
            self.set_selected_files(list(files))

    def set_selected_files(self, files):
        self.selected_files = files
        self.update_preview()
        self.btn_execute.config(state=tk.NORMAL, bg="#0284c7", fg="#ffffff")

    def update_preview(self, event=None):
        if not self.selected_files:
            return

        files = self.selected_files
        file_names = [os.path.basename(f) for f in files]
        
        _, base_name, _, script_path = self.parse_files(files)

        self.lbl_file_status.config(text=f"選択ファイル: {', '.join(file_names)}", fg="#1e293b")
        
        preview_text = f"usermacros: {base_name}.mcr\n"
        # Pythonファイルの場合はscriptsへの配置もプレビューに表示
        if script_path and script_path.lower().endswith(".py"):
            preview_text += f"userscripts: {base_name}.py\n"
            
        preview_text += (
            f"usericons : {base_name}_16a.bmp, {base_name}_16i.bmp\n"
            f"            {base_name}_24a.bmp, {base_name}_24i.bmp\n"
            f"toolbar  : {self.ent_toolbar.get().strip() or '# Scripts'}（2つのCUIXへ登録）\n"
            "CUIX     : ja-JP\\UI\\MaxStartUI.cuix\n"
            "           ja-JP\\UI\\Workspaces\\usersave\\Workspace1__usersave__.cuix"
        )
        self.lbl_save_status.config(text=preview_text)

    def parse_files(self, files):
        png_path = None
        script_path = None

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext == ".png":
                png_path = f
            elif ext in [".py", ".ms", ".mcr"]:
                script_path = f

        base_name = "CustomTool"
        if png_path:
            base_name = os.path.splitext(os.path.basename(png_path))[0]
            for suffix in ["_16a", "_16i", "_24a", "_24i", "_16", "_24"]:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
        elif script_path:
            base_name = os.path.splitext(os.path.basename(script_path))[0]

        return files, base_name, png_path, script_path

    def is_3dsmax_running(self):
        """CUIXの終了時上書きを避けるため、3ds Maxの起動状態を確認する。"""
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq 3dsmax.exe", "/NH"],
                capture_output=True,
                text=True,
                errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return "3dsmax.exe" in result.stdout.lower()
        except OSError:
            return False

    def load_cuix_text(self, cuix_path):
        """CUIXを読み込み、BOM・改行形式を保持するための情報も返す。"""
        with open(cuix_path, "rb") as cuix_file:
            raw_data = cuix_file.read()

        has_bom = raw_data.startswith(codecs.BOM_UTF8)
        text_data = raw_data.decode("utf-8-sig")
        newline = "\r\n" if b"\r\n" in raw_data else "\n"

        root = ET.fromstring(text_data)
        if root.tag != "ADSK_CUI" or root.find("CUIWindows") is None:
            raise ValueError("対応するCUIX形式ではありません。")

        return text_data, newline, has_bom

    @staticmethod
    def strip_maxscript_comments(content):
        """文字列を維持したままMAXScriptの行・ブロックコメントを除去する。"""
        result = []
        index = 0
        in_string = False
        content_length = len(content)

        while index < content_length:
            char = content[index]
            next_char = content[index + 1] if index + 1 < content_length else ""

            if in_string:
                result.append(char)
                if char == "\\" and index + 1 < content_length:
                    index += 1
                    result.append(content[index])
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char == "-" and next_char == "-":
                while index < content_length and content[index] not in "\r\n":
                    index += 1
                continue

            if char == "/" and next_char == "*":
                index += 2
                while index < content_length:
                    if (
                        content[index] == "*"
                        and index + 1 < content_length
                        and content[index + 1] == "/"
                    ):
                        index += 2
                        break
                    if content[index] in "\r\n":
                        result.append(content[index])
                    index += 1
                continue

            result.append(char)
            index += 1

        return "".join(result)

    def has_macro_script_definition(self, content):
        """コメント以外にMacroScript定義があるか確認する。"""
        code = self.strip_maxscript_comments(content)
        return re.search(r"\bmacroScript\s+([^\s(]+)", code, flags=re.IGNORECASE) is not None

    def extract_macro_identity(self, content, default_name, default_category):
        """既存.mcr内にMacroScript定義がある場合は、その名前とCategoryを使用する。"""
        code = self.strip_maxscript_comments(content)
        macro_match = re.search(
            r"\bmacroScript\s+([^\s(]+)",
            code,
            flags=re.IGNORECASE
        )
        category_match = re.search(
            r"\bCategory\s*:\s*\"([^\"]*)\"",
            code,
            flags=re.IGNORECASE
        )
        macro_name = macro_match.group(1) if macro_match else default_name
        category_name = category_match.group(1) if category_match else default_category
        return macro_name, category_name

    def find_window_blocks(self, text_data):
        """CUIWindows直下のWindow要素を、元テキスト上の位置を保ったまま取得する。"""
        pattern = re.compile(
            r"<Window\b[^>]*?/>|<Window\b[^>]*>.*?</Window>",
            flags=re.DOTALL
        )
        blocks = []
        for match in pattern.finditer(text_data):
            try:
                element = ET.fromstring(match.group(0))
            except ET.ParseError:
                continue
            blocks.append((match, element))
        return blocks

    def write_cuix_text(self, cuix_path, text_data, has_bom):
        """変更後のXMLを検証し、一時ファイル経由でCUIXへ置換する。"""
        ET.fromstring(text_data)
        encoded_data = text_data.encode("utf-8")
        if has_bom:
            encoded_data = codecs.BOM_UTF8 + encoded_data

        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="CUIX_",
                suffix=".tmp",
                dir=os.path.dirname(cuix_path),
                delete=False
            ) as output_file:
                temp_file = output_file.name
                output_file.write(encoded_data)
            os.replace(temp_file, cuix_path)
        finally:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)

    def expand_match_to_full_line(self, text_data, start, end, newline):
        """XML要素だけの行であれば、インデントと改行を含む削除範囲へ広げる。"""
        previous_newline = text_data.rfind(newline, 0, start)
        line_start = previous_newline + len(newline) if previous_newline >= 0 else 0
        next_newline = text_data.find(newline, end)
        line_end = next_newline + len(newline) if next_newline >= 0 else end
        if (
            not text_data[line_start:start].strip()
            and not text_data[end:next_newline if next_newline >= 0 else end].strip()
        ):
            return line_start, line_end
        return start, end

    def remove_actions_from_cuix(self, cuix_path, action_ids):
        """指定MacroScriptのボタン定義をCUIX内の全ツールバーから削除する。"""
        text_data, newline, has_bom = self.load_cuix_text(cuix_path)
        new_text = text_data
        removed_count = 0
        item_pattern = re.compile(
            r"<Item\b[^>]*?/>|<Item\b[^>]*>.*?</Item>",
            flags=re.DOTALL
        )

        for window_match, _ in reversed(self.find_window_blocks(text_data)):
            window_text = window_match.group(0)
            new_window_text = window_text
            for item_match in reversed(list(item_pattern.finditer(window_text))):
                try:
                    item_element = ET.fromstring(item_match.group(0))
                except ET.ParseError:
                    continue
                if item_element.get("actionID") not in action_ids:
                    continue
                start, end = self.expand_match_to_full_line(
                    new_window_text,
                    item_match.start(),
                    item_match.end(),
                    newline
                )
                new_window_text = new_window_text[:start] + new_window_text[end:]
                removed_count += 1
            if new_window_text != window_text:
                new_text = (
                    new_text[:window_match.start()]
                    + new_window_text
                    + new_text[window_match.end():]
                )

        if new_text != text_data:
            self.write_cuix_text(cuix_path, new_text, has_bom)
        return removed_count

    def remove_toolbars_from_cuix(self, cuix_path, toolbar_identities):
        """指定した標準外ツールバーのWindow要素をCUIXから削除する。"""
        text_data, newline, has_bom = self.load_cuix_text(cuix_path)
        new_text = text_data
        removed_count = 0
        for window_match, window_element in reversed(self.find_window_blocks(text_data)):
            if window_element.get("type") != "T":
                continue
            object_name = (window_element.get("objectName") or "").strip()
            display_name = (window_element.get("name") or "").strip()
            if (
                object_name not in toolbar_identities
                and display_name not in toolbar_identities
            ):
                continue
            if (
                object_name in DEFAULT_TOOLBAR_IDENTITIES
                or display_name in DEFAULT_TOOLBAR_IDENTITIES
            ):
                continue
            start, end = self.expand_match_to_full_line(
                new_text,
                window_match.start(),
                window_match.end(),
                newline
            )
            new_text = new_text[:start] + new_text[end:]
            removed_count += 1

        if new_text != text_data:
            self.write_cuix_text(cuix_path, new_text, has_bom)
        return removed_count

    def validate_management_targets(self):
        """削除前に3ds Maxの終了と両CUIXの存在・形式を確認する。"""
        if self.is_3dsmax_running():
            messagebox.showwarning(
                "3ds Maxを終了してください",
                "登録内容を安全に削除するため、\n"
                "3ds Maxをすべて終了してから再実行してください。"
            )
            return None

        cuix_paths = (self.cuix_path, self.workspace_cuix_path)
        for cuix_path in cuix_paths:
            if not os.path.isfile(cuix_path):
                messagebox.showerror(
                    "CUIXがありません",
                    f"次のファイルを確認できません:\n\n{cuix_path}"
                )
                return None
            try:
                self.load_cuix_text(cuix_path)
            except Exception as error:
                messagebox.showerror(
                    "CUIXを確認できません",
                    f"次のCUIXの解析に失敗しました:\n\n"
                    f"{cuix_path}\n\n{error}"
                )
                return None
        return cuix_paths

    def delete_selected_scripts(self):
        """選択したユーザーマクロ、関連ファイル、CUIX内のボタンを削除する。"""
        selected_ids = self.script_tree.selection()
        records = [self.script_records[item_id] for item_id in selected_ids]
        if not records:
            messagebox.showwarning("未選択", "削除するスクリプトを選択してください。")
            return

        names_text = "\n".join(f"・{record['base_name']}" for record in records)
        if not messagebox.askyesno(
            "スクリプト削除の確認",
            "次のスクリプト、同名Python、アイコン、\n"
            "ツールバー内の登録ボタンを削除します。\n\n"
            f"{names_text}\n\n削除しますか？",
            icon="warning"
        ):
            return

        cuix_paths = self.validate_management_targets()
        if cuix_paths is None:
            return

        try:
            action_ids = {record["action_id"] for record in records}
            removed_buttons = sum(
                self.remove_actions_from_cuix(cuix_path, action_ids)
                for cuix_path in cuix_paths
            )

            target_scripts = self.ent_scr.get().strip()
            target_icons = self.ent_ico.get().strip()
            deleted_files = 0
            for record in records:
                base_name = record["base_name"]
                delete_paths = [
                    record["mcr_path"],
                    os.path.join(target_scripts, f"{base_name}.py"),
                    os.path.join(target_scripts, "startup", f"{base_name}_RegisterScriptToolbar.py"),
                ]
                delete_paths.extend(
                    os.path.join(target_icons, f"{base_name}_{suffix}.bmp")
                    for suffix in ("16a", "16i", "24a", "24i")
                )
                for delete_path in delete_paths:
                    if os.path.isfile(delete_path):
                        os.remove(delete_path)
                        deleted_files += 1

            self.refresh_management_lists()
            messagebox.showinfo(
                "削除完了",
                f"スクリプト {len(records)}件を削除しました。\n\n"
                f"・削除ファイル: {deleted_files}件\n"
                f"・削除ボタン定義: {removed_buttons}件"
            )
        except Exception as error:
            messagebox.showerror("削除エラー", f"削除中にエラーが発生しました:\n\n{error}")

    def delete_selected_toolbars(self):
        """選択した標準外ツールバーを両CUIXから削除する。"""
        selected_ids = self.toolbar_tree.selection()
        records = [self.toolbar_records[item_id] for item_id in selected_ids]
        if not records:
            messagebox.showwarning("未選択", "削除するツールバーを選択してください。")
            return

        names_text = "\n".join(f"・{record['display_name']}" for record in records)
        if not messagebox.askyesno(
            "ツールバー削除の確認",
            "次のツールバーを両CUIXから削除します。\n"
            "スクリプト本体は削除しません。\n\n"
            f"{names_text}\n\n削除しますか？",
            icon="warning"
        ):
            return

        cuix_paths = self.validate_management_targets()
        if cuix_paths is None:
            return

        try:
            toolbar_identities = {record["identity"] for record in records}
            removed_toolbars = sum(
                self.remove_toolbars_from_cuix(cuix_path, toolbar_identities)
                for cuix_path in cuix_paths
            )
            self.refresh_management_lists()
            messagebox.showinfo(
                "削除完了",
                f"ツールバー定義を{removed_toolbars}件削除しました。"
            )
        except Exception as error:
            messagebox.showerror("削除エラー", f"削除中にエラーが発生しました:\n\n{error}")

    def register_toolbar_in_cuix(self, cuix_path, toolbar_name, category_name, macro_name):
        """CUIXの既存内容を維持し、指定ツールバーへマクロを登録する。"""
        text_data, newline, has_bom = self.load_cuix_text(cuix_path)
        action_id = f"{macro_name}`{category_name}"
        window_blocks = self.find_window_blocks(text_data)

        target_match = None
        target_element = None
        legacy_object_names = {f"RegisterScriptToolbar::{toolbar_name}"}
        if toolbar_name == "Scripts":
            legacy_object_names.add("RegisterScriptToolbar::# Scripts")
        elif toolbar_name == "# Scripts":
            # v03～v08が既定値で作成した「Scripts」は同じ用途の旧名として移行する。
            legacy_object_names.add("Scripts")

        # まず3ds Max標準名のツールバーを優先する。
        for window_match, window_element in window_blocks:
            if (
                window_element.get("type") == "T"
                and (
                    window_element.get("name") == toolbar_name
                    or window_element.get("objectName") == toolbar_name
                )
            ):
                target_match = window_match
                target_element = window_element
                break

        # v01～v02のQt方式がCUIXへ残っている場合は、同じバーとして再利用する。
        if target_match is None:
            for window_match, window_element in window_blocks:
                if (
                    window_element.get("type") == "T"
                    and window_element.get("objectName") in legacy_object_names
                ):
                    target_match = window_match
                    target_element = window_element
                    break

        esc_toolbar = html.escape(toolbar_name, quote=True)
        esc_action = html.escape(action_id, quote=True)
        esc_macro = html.escape(macro_name, quote=True)
        item_line = (
            f'                <Item typeID="2" type="CTB_MACROBUTTON" '
            f'width="0" height="0" controlID="0" macroTypeID="3" '
            f'macroType="MB_TYPE_ACTION" actionTableID="647394" '
            f'imageID="-1" imageName="" actionID="{esc_action}" '
            f'tip="{esc_macro}" label="{esc_macro}" />'
        )

        if target_match is not None:
            window_text = target_match.group(0)

            if target_element.get("objectName") in legacy_object_names:
                window_text = re.sub(
                    r'(\bobjectName\s*=\s*")[^"]*(")',
                    lambda match: match.group(1) + esc_toolbar + match.group(2),
                    window_text,
                    count=1
                )
                window_text = re.sub(
                    r'(\bname\s*=\s*")[^"]*(")',
                    lambda match: match.group(1) + esc_toolbar + match.group(2),
                    window_text,
                    count=1
                )

            # 指定ツールバー内に同じボタンがある場合は、その定義を上書きする。
            existing_item_match = None
            item_pattern = re.compile(
                r"<Item\b[^>]*?/>|<Item\b[^>]*>.*?</Item>",
                flags=re.DOTALL
            )
            for item_match in item_pattern.finditer(window_text):
                try:
                    item_element = ET.fromstring(item_match.group(0))
                except ET.ParseError:
                    continue
                if item_element.get("actionID") == action_id:
                    existing_item_match = item_match
                    break

            if existing_item_match is not None:
                new_window_text = (
                    window_text[:existing_item_match.start()]
                    + item_line.lstrip()
                    + window_text[existing_item_match.end():]
                )
                result_text = "指定ツールバーの既存ボタンを上書き"
            else:
                items_close = window_text.rfind("</Items>")
                if items_close < 0:
                    stripped_window = window_text.rstrip()
                    if stripped_window.endswith("/>"):
                        open_window = stripped_window[:-2].rstrip() + ">"
                        new_window_text = newline.join([
                            open_window,
                            "            <Items>",
                            item_line,
                            "            </Items>",
                            "        </Window>"
                        ])
                    else:
                        window_close = window_text.rfind("</Window>")
                        if window_close < 0:
                            raise ValueError("対象ツールバーの終了位置を確認できません。")
                        window_line_start = window_text.rfind(newline, 0, window_close)
                        if window_line_start < 0:
                            window_line_start = window_close
                        else:
                            window_line_start += len(newline)
                        items_text = newline.join([
                            "            <Items>",
                            item_line,
                            "            </Items>",
                            "        "
                        ])
                        new_window_text = (
                            window_text[:window_line_start]
                            + items_text
                            + window_text[window_close:]
                        )
                else:
                    items_line_start = window_text.rfind(newline, 0, items_close)
                    if items_line_start < 0:
                        items_line_start = items_close
                    else:
                        items_line_start += len(newline)
                    new_window_text = (
                        window_text[:items_line_start]
                        + item_line
                        + newline
                        + "            "
                        + window_text[items_close:]
                    )
                result_text = "既存ツールバーへ追加"
            new_text = (
                text_data[:target_match.start()]
                + new_window_text
                + text_data[target_match.end():]
            )
        else:
            close_position = text_data.rfind("</CUIWindows>")
            if close_position < 0:
                raise ValueError("CUIWindows要素の終了位置を確認できません。")
            close_line_start = text_data.rfind(newline, 0, close_position)
            if close_line_start < 0:
                close_line_start = close_position
            else:
                close_line_start += len(newline)
            window_text = newline.join([
                f'        <Window objectName="{esc_toolbar}" name="{esc_toolbar}" type="T" cType="1" toolbarRows="1">',
                "            <Items>",
                item_line,
                "            </Items>",
                "        </Window>",
                "    "
            ])
            new_text = (
                text_data[:close_line_start]
                + window_text
                + text_data[close_position:]
            )
            result_text = "ツールバーを新規作成して追加"

        self.write_cuix_text(cuix_path, new_text, has_bom)

        return result_text

    def remove_legacy_startup_script(self, target_scripts, macro_name):
        """v01～v03が生成したQtツールバー起動スクリプトを削除する。"""
        legacy_path = os.path.join(
            target_scripts,
            "startup",
            f"{macro_name}_RegisterScriptToolbar.py"
        )
        if os.path.isfile(legacy_path):
            os.remove(legacy_path)
            return legacy_path
        return None

    def execute_process(self):
        if not self.selected_files:
            return

        target_macros = self.ent_mcr.get().strip()
        target_scripts = self.ent_scr.get().strip()
        target_icons = self.ent_ico.get().strip()
        category_name = self.ent_cat.get().strip()
        toolbar_name = self.ent_toolbar.get().strip()

        if not category_name:
            messagebox.showwarning("Category未入力", "Categoryを入力してください。")
            return
        if not toolbar_name:
            messagebox.showwarning("ツールバー名未入力", "ツールバー名を入力してください。")
            return

        _, base_name, png_path, script_path = self.parse_files(self.selected_files)

        # Max終了時にCUIXが上書きされるため、起動中は処理しない。
        if script_path:
            if self.is_3dsmax_running():
                messagebox.showwarning(
                    "3ds Maxを終了してください",
                    "2つのCUIXを安全に更新するため、\n"
                    "3ds Maxをすべて終了してから再実行してください。"
                )
                return
            cuix_paths = (self.cuix_path, self.workspace_cuix_path)
            for cuix_path in cuix_paths:
                if not os.path.isfile(cuix_path):
                    messagebox.showerror(
                        "CUIXがありません",
                        f"次のファイルを確認できません:\n\n{cuix_path}"
                    )
                    return
                try:
                    self.load_cuix_text(cuix_path)
                except Exception as error:
                    messagebox.showerror(
                        "CUIXを確認できません",
                        f"次のCUIXの解析に失敗しました:\n\n"
                        f"{cuix_path}\n\n{error}"
                    )
                    return
        
        # フォルダの存在確認・自動生成
        if not os.path.exists(target_macros):
            os.makedirs(target_macros, exist_ok=True)
        if not os.path.exists(target_scripts):
            os.makedirs(target_scripts, exist_ok=True)
        if not os.path.exists(target_icons):
            os.makedirs(target_icons, exist_ok=True)

        try:
            macro_name = base_name
            registered_category = category_name
            cuix_results = []
            removed_legacy_path = None

            # アイコン変換処理。PNG未指定時は内蔵のRegisterScript.pngを使用する。
            if png_path and os.path.exists(png_path):
                img = Image.open(png_path).convert("RGBA")
            else:
                img = Image.open(
                    io.BytesIO(base64.b64decode(DEFAULT_ICON_PNG_BASE64))
                ).convert("RGBA")

            try:
                for size in [16, 24]:
                    resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
                    
                    bw_img = Image.new("RGB", resized_img.size, (0, 0, 0))
                    pixels = resized_img.load()
                    bw_pixels = bw_img.load()
                    
                    for y in range(size):
                        for x in range(size):
                            r, g, b, a = pixels[x, y]
                            if a > 10:
                                bw_pixels[x, y] = (255, 255, 255)
                            else:
                                bw_pixels[x, y] = (0, 0, 0)
                    
                    active_path = os.path.join(target_icons, f"{base_name}_{size}a.bmp")
                    bw_img.save(active_path, "BMP")
                    
                    color_bg = Image.new("RGB", resized_img.size, (0, 0, 0))
                    if resized_img.mode == 'RGBA':
                        color_bg.paste(resized_img, mask=resized_img.split()[3])
                    else:
                        color_bg.paste(resized_img)
                        
                    inactive_path = os.path.join(target_icons, f"{base_name}_{size}i.bmp")
                    color_bg.save(inactive_path, "BMP")
            finally:
                img.close()

            # スクリプト配置・変換処理
            if script_path and os.path.exists(script_path):
                ext = os.path.splitext(script_path)[1].lower()
                
                if ext == ".py":
                    # Pythonファイルの場合は userscripts フォルダへコピー
                    dest_py = os.path.join(target_scripts, f"{base_name}.py")
                    shutil.copy(script_path, dest_py)
                    
                    # python.ExecuteFile を使った .mcr ラッパーを自動生成
                    mcr_content = f"""macroScript {base_name} Category:"{category_name}" toolTip:"{base_name}" Icon:#("{base_name}", 1)
(
\tpython.ExecuteFile (getDir #userscripts + "\\\\{base_name}.py")
)
"""
                    dest_mcr = os.path.join(target_macros, f"{base_name}.mcr")
                    with open(dest_mcr, "w", encoding="utf-8") as mf:
                        mf.write(mcr_content)
                        
                else:
                    # 従来の .ms / .mcr の処理
                    with open(script_path, "r", encoding="utf-8", errors="ignore") as sf:
                        content = sf.read().strip()
                    
                    if self.has_macro_script_definition(content):
                        macro_name, registered_category = self.extract_macro_identity(
                            content,
                            base_name,
                            category_name
                        )
                        dest_mcr = os.path.join(target_macros, f"{base_name}.mcr")
                        shutil.copy(script_path, dest_mcr)
                    else:
                        if content.startswith("(") and content.endswith(")"):
                            inner_content = content[1:-1].strip()
                        else:
                            inner_content = content

                        mcr_content = f"""macroScript {base_name} Category:"{category_name}" toolTip:"{base_name}" Icon:#("{base_name}", 1)
(
{inner_content}
)
"""
                        dest_mcr = os.path.join(target_macros, f"{base_name}.mcr")
                        with open(dest_mcr, "w", encoding="utf-8") as mf:
                            mf.write(mcr_content)

                # 起動元と現在のワークスペースの両CUIXへ同じボタンを登録する。
                for cuix_path in (self.cuix_path, self.workspace_cuix_path):
                    cuix_result = self.register_toolbar_in_cuix(
                        cuix_path,
                        toolbar_name,
                        registered_category,
                        macro_name
                    )
                    cuix_results.append(
                        f"{os.path.basename(cuix_path)}: {cuix_result}"
                    )
                removed_legacy_path = self.remove_legacy_startup_script(
                    target_scripts,
                    base_name
                )
            
            selected_ver = self.ver_cb.get()
            legacy_text = (
                "旧Qt起動ファイルを削除済み"
                if removed_legacy_path
                else "旧Qt起動ファイルなし"
            )
            cuix_text = "\n".join(f"・{result}" for result in cuix_results)
            if not cuix_text:
                cuix_text = "・CUIX: 対象スクリプトなし"
            messagebox.showinfo(
                "成功",
                f"3ds Max {selected_ver} への配置が完了しました！\n\n"
                f"・ツール名: {macro_name}\n"
                f"・Category: {registered_category}\n"
                f"・ツールバー: {toolbar_name}\n\n"
                f"{cuix_text}\n"
                f"・旧方式: {legacy_text}\n\n"
                "ツールバーへの追加は、次回3ds Max起動時に反映されます。"
            )
            self.update_paths(None)

        except Exception as e:
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{str(e)}")

if __name__ == "__main__":
    app = StandaloneMaxInstaller()
    app.mainloop()
