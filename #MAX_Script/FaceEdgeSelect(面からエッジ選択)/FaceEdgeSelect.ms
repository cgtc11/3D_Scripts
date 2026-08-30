/*
    FaceEdgeSelect v019
    Multi-object / Edit Poly modifier supported.
*/

try (destroyDialog FaceEdgeSelectUI_v019) catch()

rollout FaceEdgeSelectUI_v019 "FaceEdgeSelect v019" width:310 height:158
(
    groupBox grpMode "1. 選択するエッジ" pos:[10,10] width:290 height:72
    radioButtons rbMode labels:#("選択面を構成する全エッジ", "選択面内のハードエッジ") \
        default:2 columns:1 pos:[25,32]

    button btnSelect "2. 複数オブジェクトを処理" pos:[20,94] width:270 height:38
    label lblVersion "v019" pos:[256,137] width:42 height:16

    fn findEditPolyModifier obj =
    (
        local resultModifier = undefined
        for modifierIndex = 1 to obj.modifiers.count while resultModifier == undefined do
        (
            if classof obj.modifiers[modifierIndex] == Edit_Poly do
                resultModifier = obj.modifiers[modifierIndex]
        )
        resultModifier
    )

    fn ensureEditPolyModifier obj =
    (
        local editMod = findEditPolyModifier obj
        if editMod != undefined then
        (
            modPanel.setCurrentObject editMod
            return editMod
        )

        local incomingFaces = #{}
        if classof obj.baseObject == Editable_Poly do
            incomingFaces = polyop.getFaceSelection obj

        editMod = Edit_Poly()
        addModifier obj editMod
        modPanel.setCurrentObject editMod
        EditPolyMod.SetEPolySelLevel editMod #Face
        subObjectLevel = 4

        -- 本体の面選択がある場合だけ明示的に引き継ぐ
        editMod.useStackSelection = false

        if incomingFaces.numberSet > 0 do
            EditPolyMod.SetSelection editMod #Face incomingFaces node:obj

        editMod
    )

    fn getAllFaces obj editMod =
    (
        local allFaces = #{}
        local faceCount = EditPolyMod.GetNumFaces editMod node:obj
        for faceIndex = 1 to faceCount do allFaces[faceIndex] = true
        allFaces
    )

    fn getSelectedFaceEdges obj editMod selectedFaces =
    (
        local resultEdges = #{}

        for faceIndex in selectedFaces do
        (
            local degree = EditPolyMod.GetFaceDegree editMod faceIndex node:obj
            for sideIndex = 1 to degree do
            (
                local edgeIndex = EditPolyMod.GetFaceEdge editMod faceIndex sideIndex node:obj
                if edgeIndex > 0 do resultEdges[edgeIndex] = true
            )
        )

        resultEdges
    )

    fn selectAllFaceEdges obj editMod selectedFaces =
    (
        EditPolyMod.SetSelection editMod #Face selectedFaces node:obj
        EditPolyMod.ConvertSelection editMod #Face #Edge requireAll:false
        EditPolyMod.SetEPolySelLevel editMod #Edge
    )

    fn selectHardFaceEdges obj editMod selectedFaces =
    (
        local selectedFaceEdges = getSelectedFaceEdges obj editMod selectedFaces
        local emptyEdges = #{}

        EditPolyMod.SetEPolySelLevel editMod #Edge
        EditPolyMod.SetSelection editMod #Edge emptyEdges node:obj

        -- v011/v015と同じ3ds Max標準ハードエッジ判定
        EditPolyMod.ButtonOp editMod #SelectHardEdges
        update obj

        local nativeHardEdges = EditPolyMod.GetSelection editMod #Edge node:obj
        local scopedHardEdges = nativeHardEdges * selectedFaceEdges
        EditPolyMod.SetSelection editMod #Edge scopedHardEdges node:obj
    )

    on btnSelect pressed do
    (
        if selection.count == 0 then
        (
            messageBox "オブジェクトを1つ以上選択してください。" title:"FaceEdgeSelect v019"
            return false
        )

        local originalNodes = selection as array
        local failedNodes = #()

        undo "FaceEdgeSelect v019" on
        (
            max modify mode

            for obj in originalNodes do
            (
                try
                (
                    -- 標準ButtonOpを対象ノードへ確実に適用するため一時的に単独選択
                    select obj
                    local editMod = ensureEditPolyModifier obj
                    local selectedFaces = EditPolyMod.GetSelection editMod #Face node:obj

                    -- 面選択が無い場合は、そのオブジェクトの全ポリゴンを対象にする
                    if selectedFaces.numberSet == 0 then
                    (
                        selectedFaces = getAllFaces obj editMod
                        EditPolyMod.SetSelection editMod #Face selectedFaces node:obj
                    )

                    if rbMode.state == 1 then
                        selectAllFaceEdges obj editMod selectedFaces
                    else
                        selectHardFaceEdges obj editMod selectedFaces

                    update obj
                )
                catch
                (
                    local errorText = getCurrentException()
                    append failedNodes (obj.name + ": " + (errorText as string))
                )
            )

            select originalNodes
            subObjectLevel = 2
            redrawViews()
        )

        local reportText = ""
        if failedNodes.count > 0 do
            reportText += ("処理エラー: " + (failedNodes as string))

        if reportText != "" do
            messageBox reportText title:"FaceEdgeSelect v019"
    )
)

createDialog FaceEdgeSelectUI_v019 style:#(#style_titlebar, #style_sysmenu, #style_toolwindow)
