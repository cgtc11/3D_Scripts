/*
    Select Element Direction Faces

    1. Editable Poly の Element レベルで対象要素を選択
    2. ボタンを押す
    3. 選択要素内の指定方向を向く面だけを Polygon 選択

    判定基準はワールド Z 軸です。
*/

try (destroyDialog SelectFaceRollout) catch ()

rollout SelectFaceRollout "SelectFace" width:330
(
    spinner spnAngle "許容角度: " range:[0.0, 180.0, 10.0] type:#float scale:1 fieldWidth:70
    label lblInfo "0°=指定方向のみ / 最大180°" align:#center
    label lblAxis "ワールド軸: 右+X / 左-X / 後+Y / 前-Y / 上+Z / 下-Z" align:#center

    groupBox grpZ "上下 (Z)" width:300 height:72 align:#center
    button btnTopBottom "上面＋下面" pos:[25,88] width:90 height:28
    button btnTop "上面のみ" pos:[120,88] width:90 height:28
    button btnBottom "下面のみ" pos:[215,88] width:90 height:28

    groupBox grpX "左右 (X)" width:300 height:72 align:#center
    button btnLeftRight "左面＋右面" pos:[25,164] width:90 height:28
    button btnRight "右面のみ" pos:[120,164] width:90 height:28
    button btnLeft "左面のみ" pos:[215,164] width:90 height:28

    groupBox grpY "前後 (Y)" width:300 height:72 align:#center
    button btnFrontBack "前面＋後面" pos:[25,240] width:90 height:28
    button btnBack "後面のみ" pos:[120,240] width:90 height:28
    button btnFront "前面のみ" pos:[215,240] width:90 height:28

    groupBox grpRadial "各Elementの円柱中心基準 (Z軸)" width:300 height:72 align:#center
    button btnOuterInner "外側＋内側" pos:[25,316] width:90 height:28
    button btnOuter "外側のみ" pos:[120,316] width:90 height:28
    button btnInner "内側のみ" pos:[215,316] width:90 height:28
    button btnInvert "選択Element内で面選択を反転" pos:[25,360] width:280 height:30

    fn getFaceWorldCenter obj faceIndex =
    (
        local vertexIndices = polyop.getFaceVerts obj faceIndex
        local faceCenter = [0, 0, 0]

        for vertexIndex in vertexIndices do
            faceCenter += polyop.getVert obj vertexIndex node:obj

        if vertexIndices.count > 0 do faceCenter /= vertexIndices.count
        faceCenter
    )

    fn getElementWorldCenter obj faceIndex =
    (
        local seedFace = #{}
        seedFace[faceIndex] = true

        local elementFaces = polyop.getElementsUsingFace obj seedFace
        local elementVerts = polyop.getVertsUsingFace obj elementFaces
        local elementCenter = [0, 0, 0]

        for vertexIndex in elementVerts do
            elementCenter += polyop.getVert obj vertexIndex node:obj

        if elementVerts.numberSet > 0 do elementCenter /= elementVerts.numberSet
        elementCenter
    )

    fn selectCaps mode =
    (
        if selection.count != 1 then
        (
            messageBox "Editable Polyを1個だけ選択してください。" title:"Select Top / Bottom"
            return false
        )

        local obj = selection[1]
        if classOf obj.baseObject != Editable_Poly then
        (
            messageBox "選択オブジェクトはEditable Polyではありません。" title:"Select Top / Bottom"
            return false
        )

        if subObjectLevel != 4 and subObjectLevel != 5 then
        (
            messageBox "PolygonまたはElementレベルで対象を選択してから実行してください。" title:"Select Direction Faces"
            return false
        )

        local seedFaces = polyop.getFaceSelection obj
        if seedFaces.numberSet == 0 then
        (
            messageBox "対象の面またはElementを選択してください。" title:"Select Direction Faces"
            return false
        )

        -- Polygon選択の場合も、その面が属するElement全体を判定対象にする。
        local selectedElementFaces = polyop.getElementsUsingFace obj seedFaces

        local resultFaces = #{}
        local directionLimit = cos spnAngle.value

        for faceIndex in selectedElementFaces do
        (
            local worldNormal = normalize (polyop.getFaceNormal obj faceIndex node:obj)

            case mode of
            (
                #topBottom:  if abs(worldNormal.z) >= directionLimit do resultFaces[faceIndex] = true
                #top:        if worldNormal.z >= directionLimit do resultFaces[faceIndex] = true
                #bottom:     if worldNormal.z <= -directionLimit do resultFaces[faceIndex] = true
                #leftRight:  if abs(worldNormal.x) >= directionLimit do resultFaces[faceIndex] = true
                #right:      if worldNormal.x >= directionLimit do resultFaces[faceIndex] = true
                #left:       if worldNormal.x <= -directionLimit do resultFaces[faceIndex] = true
                #frontBack:  if abs(worldNormal.y) >= directionLimit do resultFaces[faceIndex] = true
                #back:       if worldNormal.y >= directionLimit do resultFaces[faceIndex] = true
                #front:      if worldNormal.y <= -directionLimit do resultFaces[faceIndex] = true
                #outerInner:
                (
                    local elementCenter = getElementWorldCenter obj faceIndex
                    local radialVector = getFaceWorldCenter obj faceIndex - elementCenter
                    radialVector.z = 0
                    if (length radialVector) > 0.000001 do
                    (
                        local radialDot = dot worldNormal (normalize radialVector)
                        if abs(radialDot) >= directionLimit do resultFaces[faceIndex] = true
                    )
                )
                #outer:
                (
                    local elementCenter = getElementWorldCenter obj faceIndex
                    local radialVector = getFaceWorldCenter obj faceIndex - elementCenter
                    radialVector.z = 0
                    if (length radialVector) > 0.000001 do
                    (
                        if (dot worldNormal (normalize radialVector)) >= directionLimit do resultFaces[faceIndex] = true
                    )
                )
                #inner:
                (
                    local elementCenter = getElementWorldCenter obj faceIndex
                    local radialVector = getFaceWorldCenter obj faceIndex - elementCenter
                    radialVector.z = 0
                    if (length radialVector) > 0.000001 do
                    (
                        if (dot worldNormal (normalize radialVector)) <= -directionLimit do resultFaces[faceIndex] = true
                    )
                )
            )
        )

        if resultFaces.numberSet == 0 then
        (
            messageBox "条件に合う面がありません。\n許容角度を少し大きくして再実行してください。" title:"Select Top / Bottom"
            return false
        )

        subObjectLevel = 4
        polyop.setFaceSelection obj resultFaces
        update obj
        completeRedraw()
        format "Direction Face Selection: % face(s).\n" resultFaces.numberSet
        true
    )

    fn invertFaceSelection =
    (
        if selection.count != 1 then
        (
            messageBox "Editable Polyを1個だけ選択してください。" title:"Invert Face Selection"
            return false
        )

        local obj = selection[1]
        if classOf obj.baseObject != Editable_Poly then
        (
            messageBox "選択オブジェクトはEditable Polyではありません。" title:"Invert Face Selection"
            return false
        )

        if subObjectLevel != 4 then
        (
            messageBox "Polygonサブオブジェクトレベルで実行してください。" title:"Invert Face Selection"
            return false
        )

        local currentFaces = polyop.getFaceSelection obj
        if currentFaces.numberSet == 0 then
        (
            messageBox "反転の基準にする面を選択してください。" title:"Invert Face Selection"
            return false
        )

        local elementFaces = polyop.getElementsUsingFace obj currentFaces
        polyop.setFaceSelection obj (elementFaces - currentFaces)
        update obj
        completeRedraw()
        true
    )

    on btnTopBottom pressed do selectCaps #topBottom
    on btnTop pressed do selectCaps #top
    on btnBottom pressed do selectCaps #bottom
    on btnLeftRight pressed do selectCaps #leftRight
    on btnRight pressed do selectCaps #right
    on btnLeft pressed do selectCaps #left
    on btnFrontBack pressed do selectCaps #frontBack
    on btnBack pressed do selectCaps #back
    on btnFront pressed do selectCaps #front
    on btnOuterInner pressed do selectCaps #outerInner
    on btnOuter pressed do selectCaps #outer
    on btnInner pressed do selectCaps #inner
    on btnInvert pressed do invertFaceSelection()
)

createDialog SelectFaceRollout width:330 height:402
