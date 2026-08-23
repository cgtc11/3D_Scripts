import maya.cmds as cmds

def rename_tool_ui():
    window_id = 'rename_tool_window'
    if cmds.window(window_id, exists=True):
        cmds.deleteUI(window_id)
    
    cmds.window(window_id, title="Object Name Replacer", widthHeight=(350, 260), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnOffset=['both', 10])
    
    cmds.text(label="オブジェクト名の文字列置換", align="left", font="boldLabelFont", height=20)
    
    # --- Target (検索する文字列) ---
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=[60, 200, 50])
    cmds.text(label="Target:")
    target_field = cmds.textField(text="")
    def get_target_name(*args):
        sel = cmds.ls(sl=True)
        if sel:
            # 選択したものの名前（ネームスペースなしの名前）を取得
            short_name = sel[0].split("|")[-1].split(":")[-1]
            cmds.textField(target_field, edit=True, text=short_name)
    cmds.button(label="Get", command=get_target_name)
    cmds.setParent('..')
    
    # --- Replace (新しい文字列) ---
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=[60, 200, 50])
    cmds.text(label="Replace:")
    replace_field = cmds.textField(text="", placeholderText="空なら削除")
    def get_replace_name(*args):
        sel = cmds.ls(sl=True)
        if sel:
            short_name = sel[0].split("|")[-1].split(":")[-1]
            cmds.textField(replace_field, edit=True, text=short_name)
    cmds.button(label="Get", command=get_replace_name)
    cmds.setParent('..')

    cmds.separator(style='in')
    
    # --- 範囲設定 ---
    cmds.text(label="処理範囲", align="left", font="boldLabelFont")
    scope_radio = cmds.radioButtonGrp(labelArray3=['Selected', 'Hierarchy', 'All Scene'], select=1, numberOfRadioButtons=3, columnWidth3=[100, 100, 100])

    # --- 実行処理 ---
    def run_rename(*args):
        search_str = cmds.textField(target_field, query=True, text=True).strip()
        replace_str = cmds.textField(replace_field, query=True, text=True).strip()
        scope = cmds.radioButtonGrp(scope_radio, query=True, select=True)

        if not search_str:
            cmds.warning("Targetに検索したい文字列を入れてください")
            return

        # 対象ノードの収集
        if scope == 1: # Selected
            nodes = cmds.ls(sl=True, long=True)
        elif scope == 2: # Hierarchy
            nodes = cmds.ls(sl=True, long=True, dag=True)
        else: # All Scene
            nodes = cmds.ls(long=True)

        # リネームは階層の深い方から行わないとエラーになるため逆順にする
        nodes.sort(key=len, reverse=True)

        count = 0
        for node in nodes:
            # オブジェクト名（パスを含まない部分）を取得
            old_name = node.split("|")[-1]
            
            if search_str in old_name:
                new_name = old_name.replace(search_str, replace_str)
                try:
                    cmds.rename(node, new_name)
                    count += 1
                except Exception as e:
                    print(u"Error renaming {}: {}".format(old_name, e))
        
        print(u"完了: {} 個の名前を置換しました。 ({} -> {})".format(count, search_str, replace_str))

    # 実行ボタン
    cmds.button(label="名前を置換 / 削除 実行", command=run_rename, height=45, backgroundColor=[0.4, 0.4, 0.6])
    
    cmds.showWindow(window_id)

rename_tool_ui()