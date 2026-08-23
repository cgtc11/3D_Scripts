# ============================================================
#  Maya Auto Keyer  v2.0  ── リアルタイム操作録画版
#  録画ボタン → カウントダウン → ユーザーの操作をリアルタイムで記録
# ============================================================
#
#  【v1からの変更点・修正内容】
#  v1 の問題:
#    cmds.currentTime() でタイムラインを強制進行 →
#    Maya がシーンを再評価 → オブジェクトが元の位置に戻る
#
#  v2 の解決策:
#    タイムラインを強制移動しない。
#    代わりに time.time() でリアル経過時間を計測し、
#    cmds.setKeyframe(obj, attribute=attr, time=N) の
#    「time引数付き呼び出し」を使う。
#    この呼び出しは「現在の値をフレームNに記録」する動作なので
#    タイムラインの位置に関係なくユーザーの現在の操作値を保存できる。
#    タイムラインの表示更新は update=False で評価をスキップして行う。
#
#  【使い方】
#  1. Mayaでオブジェクトを選択 → 「＋ 選択を登録」
#  2. キーを打つチャンネルを選択
#  3. カウントダウン秒数・録画時間・右クリック停止を設定
#  4. 「⏺ 録画開始」を押す
#  5. カウントダウン終了後、Mayaで自由にオブジェクトを操作する
#     → 操作した値がリアルタイムでキーとして記録される
#
#  【注意】
#  - キーはリアル経過時間をFPSで換算したフレーム番号に記録
#  - 録画中タイムライン表示は update=False で動くが再評価なし
#  - 右クリック停止中はMayaのコンテキストメニューをブロック
# ============================================================

import time
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    import shiboken2 as shiboken
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    import shiboken6 as shiboken


# ─────────────────────────────────────────────
#  右クリック イベントフィルター
# ─────────────────────────────────────────────
class RightClickStopFilter(QtCore.QObject):
    """
    QApplicationレベルで右クリックを監視。
    録画中に右クリックされたら停止コールバックを呼ぶ。
    True返却でMayaのコンテキストメニューをブロック。
    """
    def __init__(self, stop_callback, parent=None):
        super().__init__(parent)
        self._stop_callback = stop_callback

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.RightButton:
                self._stop_callback()
                return True  # イベント消費 → コンテキストメニューブロック
        return False


# ─────────────────────────────────────────────
#  メインウィンドウ
# ─────────────────────────────────────────────
class MayaAutoKeyer(QtWidgets.QDialog):

    FPS_MAP = {
        'game': 15, 'film': 24, 'pal': 25, 'ntsc': 30,
        'show': 48, 'palf': 50, 'ntscf': 60,
        '2fps': 2, '3fps': 3, '4fps': 4, '5fps': 5,
        '6fps': 6, '8fps': 8, '10fps': 10, '12fps': 12,
        '16fps': 16, '20fps': 20, '40fps': 40, '75fps': 75,
        '80fps': 80, '100fps': 100, '120fps': 120, '125fps': 125,
        '150fps': 150, '200fps': 200, '240fps': 240, '250fps': 250,
        '300fps': 300, '375fps': 375, '400fps': 400, '500fps': 500,
        '600fps': 600, '750fps': 750, '1200fps': 1200,
        '1500fps': 1500, '2000fps': 2000, '3000fps': 3000,
        '6000fps': 6000,
    }

    def __init__(self, parent=None):
        if parent is None:
            ptr = omui.MQtUtil.mainWindow()
            parent = shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
        super().__init__(parent)

        self._registered_objects  = []
        self._is_recording        = False
        self._countdown_timer     = None
        self._record_timer        = None
        self._right_click_filter  = None
        self._current_countdown   = 0

        # 録画用: リアル時間ベース
        self._record_start_time   = 0.0   # time.time() の録画開始時刻
        self._start_frame         = 0.0   # 録画開始時のタイムライン位置
        self._fps                 = 24.0
        self._max_duration_sec    = -1.0  # -1 = 無制限

        self.setWindowTitle("Maya Auto Keyer  v2")
        self.setMinimumWidth(360)
        self._setup_ui()
        self._setup_style()

    # ──────────────────────────────────────────
    #  UI 構築
    # ──────────────────────────────────────────
    def _setup_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── オブジェクト登録 ──────────────────
        grp_obj = QtWidgets.QGroupBox("対象オブジェクト")
        lay_obj = QtWidgets.QVBoxLayout(grp_obj)

        btn_row = QtWidgets.QHBoxLayout()
        self._btn_add    = QtWidgets.QPushButton("＋ 選択を登録")
        self._btn_remove = QtWidgets.QPushButton("－ 削除")
        self._btn_clear  = QtWidgets.QPushButton("全削除")
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        btn_row.addWidget(self._btn_clear)
        lay_obj.addLayout(btn_row)

        self._obj_list = QtWidgets.QListWidget()
        self._obj_list.setMaximumHeight(110)
        self._obj_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay_obj.addWidget(self._obj_list)
        root.addWidget(grp_obj)

        # ── チャンネル選択 ────────────────────
        grp_ch = QtWidgets.QGroupBox("キーを打つチャンネル")
        lay_ch = QtWidgets.QHBoxLayout(grp_ch)
        self._chk_translate = QtWidgets.QCheckBox("移動 (T)")
        self._chk_rotate    = QtWidgets.QCheckBox("回転 (R)")
        self._chk_scale     = QtWidgets.QCheckBox("スケール (S)")
        self._chk_translate.setChecked(True)
        self._chk_rotate.setChecked(True)
        lay_ch.addWidget(self._chk_translate)
        lay_ch.addWidget(self._chk_rotate)
        lay_ch.addWidget(self._chk_scale)
        root.addWidget(grp_ch)

        # ── タイミング設定 ────────────────────
        grp_time = QtWidgets.QGroupBox("タイミング設定")
        lay_form = QtWidgets.QFormLayout(grp_time)
        lay_form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)
        lay_form.setLabelAlignment(QtCore.Qt.AlignRight)

        self._spin_countdown = QtWidgets.QSpinBox()
        self._spin_countdown.setRange(0, 60)
        self._spin_countdown.setValue(3)
        self._spin_countdown.setSuffix(" 秒")
        self._spin_countdown.setToolTip("録画開始前のカウントダウン（0で即時）")
        lay_form.addRow("カウントダウン:", self._spin_countdown)

        dur_row = QtWidgets.QHBoxLayout()
        self._chk_use_duration = QtWidgets.QCheckBox("有効")
        self._chk_use_duration.setChecked(True)
        self._spin_duration = QtWidgets.QSpinBox()
        self._spin_duration.setRange(1, 3600)
        self._spin_duration.setValue(3)
        self._spin_duration.setSuffix(" 秒")
        self._spin_duration.setEnabled(True)
        self._spin_duration.setToolTip("録画の最大時間（秒）")
        dur_row.addWidget(self._chk_use_duration)
        dur_row.addWidget(self._spin_duration)
        dur_row.addStretch()
        lay_form.addRow("録画時間制限:", dur_row)

        self._chk_rightclick = QtWidgets.QCheckBox("右クリックで録画停止する")
        self._chk_rightclick.setChecked(True)
        self._chk_rightclick.setToolTip(
            "有効時：録画中の右クリックで停止\n（Mayaのコンテキストメニューはブロックされます）"
        )
        lay_form.addRow("右クリック停止:", self._chk_rightclick)

        root.addWidget(grp_time)

        # ── ステータス / 経過時間 ─────────────
        self._lbl_status = QtWidgets.QLabel("待機中")
        self._lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        self._lbl_status.setMinimumHeight(50)
        fnt = self._lbl_status.font()
        fnt.setPointSize(18)
        fnt.setBold(True)
        self._lbl_status.setFont(fnt)
        root.addWidget(self._lbl_status)

        self._lbl_frame_info = QtWidgets.QLabel("")
        self._lbl_frame_info.setAlignment(QtCore.Qt.AlignCenter)
        fnt2 = self._lbl_frame_info.font()
        fnt2.setPointSize(10)
        self._lbl_frame_info.setFont(fnt2)
        root.addWidget(self._lbl_frame_info)

        # ── 録画ボタン ────────────────────────
        ctrl_row = QtWidgets.QHBoxLayout()
        self._btn_record = QtWidgets.QPushButton("⏺  録画開始")
        self._btn_stop   = QtWidgets.QPushButton("⏹  停止")
        self._btn_stop.setEnabled(False)
        self._btn_record.setMinimumHeight(38)
        self._btn_stop.setMinimumHeight(38)
        ctrl_row.addWidget(self._btn_record)
        ctrl_row.addWidget(self._btn_stop)
        root.addLayout(ctrl_row)

        # ── シグナル接続 ──────────────────────
        self._btn_add.clicked.connect(self._add_selected_objects)
        self._btn_remove.clicked.connect(self._remove_selected_items)
        self._btn_clear.clicked.connect(self._clear_all_objects)
        self._btn_record.clicked.connect(self._start_recording)
        self._btn_stop.clicked.connect(self._stop_recording)
        self._chk_use_duration.toggled.connect(self._spin_duration.setEnabled)

    def _setup_style(self):
        self.setStyleSheet("""
            QDialog { background:#2b2b2b; color:#e0e0e0; }
            QGroupBox {
                font-weight:bold; color:#aaaaaa;
                border:1px solid #555; border-radius:4px;
                margin-top:8px; padding-top:6px;
            }
            QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
            QPushButton {
                background:#444; color:#e0e0e0;
                border:1px solid #666; border-radius:3px; padding:4px 10px;
            }
            QPushButton:hover   { background:#555; }
            QPushButton:pressed { background:#333; }
            QPushButton:disabled { color:#666; }
            QListWidget {
                background:#1e1e1e; color:#ccc;
                border:1px solid #444; border-radius:3px;
            }
            QSpinBox {
                background:#1e1e1e; color:#ccc;
                border:1px solid #444; border-radius:3px; padding:2px;
            }
            QCheckBox { color:#ccc; }
            QLabel    { color:#e0e0e0; }
        """)
        self._btn_record.setStyleSheet(
            "QPushButton { background:#7a1a1a; color:#ff9090; border:1px solid #aa3333;"
            " border-radius:3px; font-weight:bold; padding:4px 10px; }"
            "QPushButton:hover    { background:#922020; }"
            "QPushButton:disabled { background:#3a2020; color:#665555; }"
        )
        self._btn_stop.setStyleSheet(
            "QPushButton { background:#1a4a7a; color:#90c0ff; border:1px solid #3366aa;"
            " border-radius:3px; font-weight:bold; padding:4px 10px; }"
            "QPushButton:hover    { background:#1e5a8a; }"
            "QPushButton:disabled { background:#1a2a3a; color:#446688; }"
        )

    # ──────────────────────────────────────────
    #  オブジェクト管理
    # ──────────────────────────────────────────
    def _add_selected_objects(self):
        sel = cmds.ls(selection=True, long=False) or []
        added = 0
        for obj in sel:
            if obj not in self._registered_objects:
                self._registered_objects.append(obj)
                self._obj_list.addItem(obj)
                added += 1
        if not sel:
            QtWidgets.QMessageBox.information(
                self, "情報", "Mayaでオブジェクトを選択してから押してください。")

    def _remove_selected_items(self):
        for item in self._obj_list.selectedItems():
            name = item.text()
            if name in self._registered_objects:
                self._registered_objects.remove(name)
            self._obj_list.takeItem(self._obj_list.row(item))

    def _clear_all_objects(self):
        self._registered_objects.clear()
        self._obj_list.clear()

    # ──────────────────────────────────────────
    #  録画制御
    # ──────────────────────────────────────────
    def _start_recording(self):
        if not self._registered_objects:
            QtWidgets.QMessageBox.warning(
                self, "警告",
                "オブジェクトが登録されていません。\n先にオブジェクトを選択して「選択を登録」を押してください。")
            return
        if not any([self._chk_translate.isChecked(),
                    self._chk_rotate.isChecked(),
                    self._chk_scale.isChecked()]):
            QtWidgets.QMessageBox.warning(
                self, "警告", "キーを打つチャンネルを1つ以上選択してください。")
            return

        self._is_recording = True
        self._btn_record.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._lbl_frame_info.setText("")

        countdown = self._spin_countdown.value()
        self._current_countdown = countdown

        if countdown > 0:
            self._set_status(f"⏳  {countdown}", color="#ffcc44")
            self._countdown_timer = QtCore.QTimer(self)
            self._countdown_timer.timeout.connect(self._countdown_tick)
            self._countdown_timer.start(1000)
        else:
            self._begin_keying()

    def _countdown_tick(self):
        self._current_countdown -= 1
        if self._current_countdown <= 0:
            self._countdown_timer.stop()
            self._countdown_timer = None
            self._begin_keying()
        else:
            self._set_status(f"⏳  {self._current_countdown}", color="#ffcc44")

    def _begin_keying(self):
        self._set_status("⏺  録画中", color="#ff4444")

        # FPS 取得
        time_unit = cmds.currentUnit(query=True, time=True)
        self._fps = float(self.FPS_MAP.get(time_unit, 24))

        # 録画開始フレームと開始リアル時刻を記録
        self._start_frame       = int(cmds.currentTime(query=True))
        self._record_start_time = time.time()
        self._last_keyed_frame  = self._start_frame - 1  # 初回フレームをキーさせるため-1

        # 録画上限時間
        if self._chk_use_duration.isChecked():
            self._max_duration_sec = float(self._spin_duration.value())
        else:
            self._max_duration_sec = -1.0

        # 右クリック停止フィルター登録
        if self._chk_rightclick.isChecked():
            self._right_click_filter = RightClickStopFilter(self._stop_recording)
            QtWidgets.QApplication.instance().installEventFilter(self._right_click_filter)

        # キー打ちタイマー
        # 間隔はFPSより少し短めにして取りこぼしを防ぐ
        interval_ms = max(1, int(1000.0 / self._fps / 2))
        self._record_timer = QtCore.QTimer(self)
        self._record_timer.timeout.connect(self._key_tick)
        self._record_timer.start(interval_ms)

    def _key_tick(self):
        """
        リアル経過時間からフレームを計算し、
        タイムラインを動かさずに現在の値をキーとして記録する。

        ポイント:
          cmds.setKeyframe(obj, attribute=attr, time=N)
          は「今この瞬間の値をフレームNに書き込む」動作。
          currentTime を変えないので Maya のシーン再評価が走らず
          ユーザーが動かした位置がそのまま記録される。

          フレーム番号は int() で整数に丸め、
          同じフレームに2度キーを打たないよう _last_keyed_frame で管理。
          時間制限・右クリックはどちらが先でも _stop_recording() が呼ばれ、
          _stop_recording() 内のガードで二重実行を防ぐ。
        """
        if not self._is_recording:
            return

        elapsed_sec = time.time() - self._record_start_time

        # ── 時間上限チェック（右クリックと独立して動作）──
        if self._max_duration_sec > 0 and elapsed_sec >= self._max_duration_sec:
            self._stop_recording()
            return

        # リアル経過時間 → 整数フレーム番号
        current_frame = int(self._start_frame + elapsed_sec * self._fps)

        # このフレームはすでにキー済みならスキップ（1フレーム1キー保証）
        if current_frame <= self._last_keyed_frame:
            # フレームが変わっていなくてもUI更新だけ行う
            self._lbl_frame_info.setText(
                f"経過: {elapsed_sec:.1f}s  /  Frame: {current_frame}"
            )
            return

        self._last_keyed_frame = current_frame

        # キーを打つアトリビュートを収集
        attrs = []
        if self._chk_translate.isChecked():
            attrs += ['tx', 'ty', 'tz']
        if self._chk_rotate.isChecked():
            attrs += ['rx', 'ry', 'rz']
        if self._chk_scale.isChecked():
            attrs += ['sx', 'sy', 'sz']

        # 登録オブジェクト全てに「現在値を整数フレームにキー打ち」
        for obj in self._registered_objects:
            if not cmds.objExists(obj):
                continue
            for attr in attrs:
                try:
                    cmds.setKeyframe(obj, attribute=attr, time=current_frame)
                except Exception:
                    pass  # ロック済みアトリビュートはスキップ

        # タイムラインの表示を update=False で進める
        # （update=False = シーン再評価なし → 位置リセットしない）
        cmds.currentTime(current_frame, update=False)

        # UIに経過時間とフレーム表示
        self._lbl_frame_info.setText(
            f"経過: {elapsed_sec:.1f}s  /  Frame: {current_frame}"
        )

    def _stop_recording(self):
        if not self._is_recording:
            return  # 二重呼び出し防止

        self._is_recording = False

        for timer_attr in ('_countdown_timer', '_record_timer'):
            t = getattr(self, timer_attr, None)
            if t is not None:
                t.stop()
                setattr(self, timer_attr, None)

        if self._right_click_filter is not None:
            QtWidgets.QApplication.instance().removeEventFilter(self._right_click_filter)
            self._right_click_filter = None

        self._btn_record.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status("✔  完了", color="#66ff88")

    # ──────────────────────────────────────────
    #  ステータス表示
    # ──────────────────────────────────────────
    def _set_status(self, text, color="#e0e0e0"):
        self._lbl_status.setText(text)
        self._lbl_status.setStyleSheet(f"color:{color}; font-weight:bold;")

    def closeEvent(self, event):
        self._stop_recording()
        super().closeEvent(event)


# ─────────────────────────────────────────────
#  起動エントリーポイント
# ─────────────────────────────────────────────
def launch():
    global _maya_auto_keyer_instance
    try:
        _maya_auto_keyer_instance.close()
        _maya_auto_keyer_instance.deleteLater()
    except Exception:
        pass

    _maya_auto_keyer_instance = MayaAutoKeyer()
    _maya_auto_keyer_instance.show()
    _maya_auto_keyer_instance.raise_()


launch()
