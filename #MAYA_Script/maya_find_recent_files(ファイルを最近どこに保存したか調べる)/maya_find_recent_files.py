"""
Maya Recent & AutoSave File Finder
Script Editorに貼り付けて実行
"""

import maya.cmds as cmds
import os
import time
import tempfile


# ──────────────────────────────────────────────
# データ収集
# ──────────────────────────────────────────────

def get_recent_files():
    """Maya の最近使ったファイル一覧を取得"""
    results = []
    try:
        files = cmds.optionVar(q='RecentFilesList') or []
        for f in files:
            if os.path.exists(f):
                mtime = os.path.getmtime(f)
                size  = os.path.getsize(f)
                results.append({
                    'path' : f,
                    'name' : os.path.basename(f),
                    'mtime': mtime,
                    'size' : size,
                    'type' : 'recent',
                })
    except Exception as e:
        cmds.warning('Recent files 取得エラー: ' + str(e))
    return results


def get_autosave_dirs():
    """AutoSave の保存先フォルダ一覧を返す（存在するものだけ）"""
    dirs = []

    # 1. Maya の設定から取得
    try:
        dst = cmds.autoSave(q=True, destinationFolder=True)
        if dst and os.path.isdir(dst):
            dirs.append(dst)
    except Exception:
        pass

    # 2. ユーザープリファレンス内の autosave フォルダ
    try:
        pref_dir = cmds.internalVar(userPrefDir=True)
        candidate = os.path.join(os.path.dirname(pref_dir.rstrip('/\\')), 'autosave')
        if os.path.isdir(candidate) and candidate not in dirs:
            dirs.append(candidate)
    except Exception:
        pass

    # 3. システムのテンポラリフォルダ
    tmp = tempfile.gettempdir()
    if tmp and os.path.isdir(tmp) and tmp not in dirs:
        dirs.append(tmp)

    return dirs


def get_autosave_files():
    """AutoSave ファイルを収集（.ma / .mb）"""
    results = []
    seen    = set()

    for folder in get_autosave_dirs():
        try:
            for fname in os.listdir(folder):
                if not fname.lower().endswith(('.ma', '.mb')):
                    continue
                fpath = os.path.join(folder, fname)
                if fpath in seen or not os.path.isfile(fpath):
                    continue
                seen.add(fpath)
                mtime = os.path.getmtime(fpath)
                size  = os.path.getsize(fpath)
                results.append({
                    'path' : fpath,
                    'name' : fname,
                    'mtime': mtime,
                    'size' : size,
                    'type' : 'autosave',
                })
        except Exception:
            pass

    return results


def format_size(n):
    if n < 1024:
        return '{} B'.format(n)
    elif n < 1024 * 1024:
        return '{:.1f} KB'.format(n / 1024.0)
    else:
        return '{:.1f} MB'.format(n / (1024.0 * 1024))


def format_time(t):
    return time.strftime('%Y-%m-%d  %H:%M:%S', time.localtime(t))


# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────

WIN_ID    = 'mayaFileFinder_win'
SCROLL_ID = 'mayaFileFinder_scroll'

# 現在の全エントリ（フィルタ用）
_all_entries = []


def _make_label(entry):
    tag   = '[Recent]   ' if entry['type'] == 'recent' else '[AutoSave] '
    label = '{}{:<50}  {}    {}'.format(
        tag,
        entry['name'],
        format_time(entry['mtime']),
        format_size(entry['size'])
    )
    return label


def _rebuild_list(filter_text=''):
    """スクロールリストを再描画"""
    cmds.textScrollList(SCROLL_ID, e=True, removeAll=True)

    keyword = filter_text.strip().lower()
    for entry in _all_entries:
        if keyword and keyword not in entry['name'].lower() and keyword not in entry['path'].lower():
            continue
        cmds.textScrollList(SCROLL_ID, e=True, append=_make_label(entry))


def _on_open(*_):
    sel = cmds.textScrollList(SCROLL_ID, q=True, selectIndexedItem=True)
    if not sel:
        cmds.warning('ファイルを選択してください')
        return

    # 表示中のエントリとインデックスを対応させる
    filter_text = cmds.textField('mayaFileFinder_search', q=True, text=True)
    keyword     = filter_text.strip().lower()
    visible     = [e for e in _all_entries
                   if not keyword
                   or keyword in e['name'].lower()
                   or keyword in e['path'].lower()]

    idx   = sel[0] - 1
    if idx < 0 or idx >= len(visible):
        return
    entry = visible[idx]
    path  = entry['path']

    if not os.path.exists(path):
        cmds.warning('ファイルが見つかりません: ' + path)
        return

    # 未保存の変更がある場合は確認
    if cmds.file(q=True, modified=True):
        ans = cmds.confirmDialog(
            title='未保存の変更',
            message='現在のシーンに未保存の変更があります。続行しますか？',
            button=['続行', 'キャンセル'],
            defaultButton='キャンセル',
            cancelButton='キャンセル',
        )
        if ans != '続行':
            return

    cmds.file(path, open=True, force=True)
    print('Opened: ' + path)


def _on_reveal(*_):
    sel = cmds.textScrollList(SCROLL_ID, q=True, selectIndexedItem=True)
    if not sel:
        cmds.warning('ファイルを選択してください')
        return

    filter_text = cmds.textField('mayaFileFinder_search', q=True, text=True)
    keyword     = filter_text.strip().lower()
    visible     = [e for e in _all_entries
                   if not keyword
                   or keyword in e['name'].lower()
                   or keyword in e['path'].lower()]

    idx = sel[0] - 1
    if idx < 0 or idx >= len(visible):
        return
    path = visible[idx]['path']

    import subprocess, sys
    folder = os.path.dirname(path)
    if sys.platform == 'darwin':
        subprocess.call(['open', '-R', path])
    elif sys.platform.startswith('win'):
        subprocess.call(['explorer', '/select,', path.replace('/', '\\')])
    else:
        subprocess.call(['xdg-open', folder])


def _on_refresh(*_):
    global _all_entries
    _all_entries = []

    recent   = get_recent_files()
    autosave = get_autosave_files()

    # mtime 降順でマージ
    combined = recent + autosave
    combined.sort(key=lambda e: e['mtime'], reverse=True)
    _all_entries = combined

    filter_text = cmds.textField('mayaFileFinder_search', q=True, text=True)
    _rebuild_list(filter_text)

    cmds.text('mayaFileFinder_status', e=True,
              label='Recent: {}  /  AutoSave: {}'.format(len(recent), len(autosave)))


def _on_filter_change(text):
    _rebuild_list(text)


def build_ui():
    if cmds.window(WIN_ID, exists=True):
        cmds.deleteUI(WIN_ID)

    cmds.window(WIN_ID, title='Maya File Finder', widthHeight=(820, 480), sizeable=True)
    cmds.columnLayout(adjustableColumn=True)

    # ── ヘッダバー ──
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 300, 80, 80),
                   adjustableColumn=2, columnAlign4=('left','left','left','left'))
    cmds.text(label='検索:', align='right')
    cmds.textField('mayaFileFinder_search', placeholderText='ファイル名 / パスで絞り込み',
                   changeCommand=_on_filter_change,
                   tcc=_on_filter_change)
    cmds.button(label='更新', command=_on_refresh)
    cmds.setParent('..')

    # ── カラムヘッダ（固定テキスト） ──
    cmds.text(label='  種別           ファイル名                                          '
                     '最終更新                    サイズ',
              align='left', font='fixedWidthFont')
    cmds.separator(style='in')

    # ── ファイルリスト ──
    cmds.textScrollList(SCROLL_ID,
                        numberOfRows=18,
                        allowMultiSelection=False,
                        font='fixedWidthFont',
                        doubleClickCommand=_on_open)

    cmds.separator(style='in')

    # ── ボタンバー ──
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(120, 120, 400),
                   adjustableColumn=3, columnAlign3=('left','left','left'))
    cmds.button(label='開く',          command=_on_open,   width=110)
    cmds.button(label='Finderで表示',  command=_on_reveal, width=110)
    cmds.text('mayaFileFinder_status', label='', align='left')
    cmds.setParent('..')

    cmds.showWindow(WIN_ID)

    # 初回ロード
    _on_refresh()


build_ui()
