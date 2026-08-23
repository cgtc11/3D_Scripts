import maya.cmds as cmds

def rig_color_changer_v3_5():
    window_id = 'rig_color_changer_v3_5'
    if cmds.window(window_id, exists=True):
        cmds.deleteUI(window_id)
    
    window_width = 300
    window_height = 350
    
    cmds.window(window_id, title="RigColorChanger v3.5", widthHeight=(window_width, window_height), sizeable=True)
    
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnOffset=['both', 12])
    cmds.separator(style='none', height=5)

    # 画像のパレットに基づいたMaya Index Colors
    maya_rgb = [
        [0.467, 0.467, 0.467], [0.0, 0.0, 0.0], [0.247, 0.247, 0.247], [0.498, 0.498, 0.498],
        [0.608, 0.0, 0.157], [0.0, 0.016, 0.376], [0.0, 0.0, 1.0], [0.0, 0.275, 0.098],
        [0.149, 0.0, 0.263], [0.784, 0.0, 0.784], [0.541, 0.282, 0.2], [0.247, 0.137, 0.122],
        [0.6, 0.145, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.255, 0.6],
        [1.0, 1.0, 1.0], [1.0, 1.0, 0.0], [0.392, 0.863, 1.0], [0.263, 1.0, 0.639],
        [1.0, 0.686, 0.686], [0.89, 0.675, 0.475], [1.0, 1.0, 0.388], [0.0, 0.6, 0.329],
        [0.631, 0.412, 0.188], [0.62, 0.631, 0.188], [0.408, 0.631, 0.188], [0.188, 0.631, 0.365],
        [0.188, 0.631, 0.631], [0.188, 0.404, 0.631], [0.435, 0.188, 0.631], [0.631, 0.188, 0.412]
    ]

    # --- 1. Target (Current Color) / Get エリア ---
    cmds.text(label="Target Color (Source for Replace)", align="left", font="boldLabelFont")
    target_preview = cmds.canvas(width=window_width-24, height=25, rgbValue=maya_rgb[14])
    
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=[80, 100, 60])
    cmds.text(label="Index:")
    target_int = cmds.intField(value=14, editable=False)
    
    def get_color_from_sel(*args):
        sel = cmds.ls(sl=True)
        if not sel: return
        shapes = cmds.listRelatives(sel[0], s=True, f=True) or []
        target_node = shapes[0] if shapes else sel[0]
        if cmds.attributeQuery("overrideEnabled", node=target_node, exists=True):
            if cmds.getAttr(target_node + ".overrideEnabled"):
                col = cmds.getAttr(target_node + ".overrideColor")
                if 0 <= col <= 31:
                    cmds.intField(target_int, edit=True, value=col)
                    cmds.canvas(target_preview, edit=True, rgbValue=maya_rgb[col])
    
    cmds.button(label="Get", command=get_color_from_sel, bgc=[0.35, 0.35, 0.35])
    cmds.setParent('..')

    cmds.separator(style='in', height=5)

    # --- 2. Options ---
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[60, 200], adjustableColumn=2)
    cmds.text(label="Scope:", font="boldLabelFont")
    scope_radio = cmds.radioButtonGrp(labelArray2=['Selected', 'All Scene'], select=2, numberOfRadioButtons=2, columnWidth2=[80, 80])
    cmds.setParent('..')

    force_check = cmds.checkBox(label="Force Override (Ignore Target Color)", value=False)

    cmds.separator(style='in', height=5)

    # --- 3. Click-to-Apply Palette ---
    cmds.text(label="Click Palette to Apply Immediately:", align="left", font="boldLabelFont")
    
    def apply_color_logic(new_index, disable_override=False):
        scope = cmds.radioButtonGrp(scope_radio, query=True, select=True)
        is_force = cmds.checkBox(force_check, query=True, value=True)
        target_color = cmds.intField(target_int, query=True, value=True)

        if scope == 1:
            nodes = cmds.ls(sl=True, dag=True, s=True, long=True)
        else:
            nodes = cmds.ls(type='shape', long=True)
            
        if not nodes: return

        for s in nodes:
            if not cmds.attributeQuery("overrideEnabled", node=s, exists=True):
                continue
            
            is_enabled = cmds.getAttr(s + ".overrideEnabled")
            current_col = cmds.getAttr(s + ".overrideColor")
            
            should_apply = False
            if is_force:
                should_apply = True
            elif is_enabled and current_col == target_color:
                should_apply = True

            if should_apply:
                if disable_override:
                    cmds.setAttr(s + ".overrideEnabled", False)
                else:
                    cmds.setAttr(s + ".overrideEnabled", True)
                    cmds.setAttr(s + ".overrideColor", new_index)

    # Defaultボタン
    cmds.button(label="Default (Override OFF)", height=25, command=lambda x: apply_color_logic(0, disable_override=True))
    
    # パレットUI (Index 1-31)
    cmds.gridLayout(numberOfColumns=8, cellWidthHeight=[33, 25])
    for i in range(1, 32):
        cmds.canvas(rgbValue=maya_rgb[i], pc=lambda i=i: apply_color_logic(i))
    
    cmds.setParent('..')
    cmds.separator(style='none', height=10)
    
    cmds.showWindow(window_id)

rig_color_changer_v3_5()