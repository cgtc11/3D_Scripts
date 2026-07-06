import maya.cmds as cmds
import os
import maya.mel as mel

class BBCleaner(object):
    def __init__(self):
        self.window_id = "BBCleanerWin"
        self.title = "BBCleaner v1.3"
        self.size = (300, 260)

    def create_ui(self):
        if cmds.window(self.window_id, exists=True):
            cmds.deleteUI(self.window_id)

        self.window = cmds.window(self.window_id, title=self.title, widthHeight=self.size, menuBar=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnOffset=['both', 15])
        
        cmds.separator(height=10, style='none')
        cmds.text(label="BBCleaner - Scene Cleanup", align='center', font="boldLabelFont")
        
        self.cb_mental = cmds.checkBox(label="Mental Rayの残骸を完全削除", value=True)
        self.cb_unknown = cmds.checkBox(label="その他の未知のノード/プラグイン削除", value=True)
        self.cb_namespace = cmds.checkBox(label="不要なネームスペースの統合", value=True)
        self.cb_panels = cmds.checkBox(label="無効なパネル構成のリセット", value=True)
        self.cb_optimize = cmds.checkBox(label="標準のシーン最適化を実行", value=True)

        cmds.separator(height=10)
        cmds.button(label="クリーンアップ実行！", height=45, backgroundColor=[0.4, 0.5, 0.4], command=self.execute_clean)
        cmds.showWindow(self.window)

    def execute_clean(self, *args):
        # 1. Mental Ray 関連の特定ノードを削除
        if cmds.checkBox(self.cb_mental, q=True, v=True):
            # メンタルレイ特有のノードタイプ・キーワードを指定して検索
            mr_types = ["mentalrayGlobals", "mentalrayItemsList", "mentalrayOptions", "mentalrayFramebuffer"]
            for m_type in mr_types:
                nodes = cmds.ls(type=m_type)
                if nodes:
                    for n in nodes:
                        if cmds.objExists(n):
                            cmds.lockNode(n, lock=False)
                            cmds.delete(n)
            print("Done: Mental Ray関連のノードを削除しました。")

        # 2. 未知のノード (unknown) とプラグインの削除
        if cmds.checkBox(self.cb_unknown, q=True, v=True):
            unodes = cmds.ls(type="unknown")
            if unodes:
                for n in unodes:
                    if cmds.objExists(n):
                        cmds.lockNode(n, lock=False)
                        cmds.delete(n)
            uplugins = cmds.unknownPlugin(query=True, list=True)
            if uplugins:
                for p in uplugins:
                    try: cmds.unknownPlugin(p, remove=True)
                    except: pass
            print("Done: 未知のデータを削除しました。")

        # 3. ネームスペースの統合
        if cmds.checkBox(self.cb_namespace, q=True, v=True):
            all_ns = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
            target_ns = [ns for ns in all_ns if ns not in [":UI", ":shared"]]
            target_ns.reverse()
            for ns in target_ns:
                try: cmds.namespace(removeNamespace=ns, mergeNamespaceWithParent=True)
                except: pass

        # 4. パネルリセット
        if cmds.checkBox(self.cb_panels, q=True, v=True):
            all_p = cmds.lsUI(panels=True) or []
            for p in all_p:
                if "modelPanel" not in p:
                    try: cmds.deleteUI(p, panel=True)
                    except: pass

        # 5. 標準最適化
        if cmds.checkBox(self.cb_optimize, q=True, v=True):
            mel.eval('cleanUpScene(1)')

        cmds.confirmDialog(title='完了', message='メンタルレイを含む掃除が完了しました！\n別名で保存してMayaを再起動してください。', button=['了解'])

def show():
    ui = BBCleaner()
    ui.create_ui()