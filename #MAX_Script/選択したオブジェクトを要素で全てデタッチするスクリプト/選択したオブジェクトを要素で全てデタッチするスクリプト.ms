fn detachAllElements obj =
(
    if classof obj != Editable_Poly do convertToPoly obj

    while true do (
        local faceCount = polyop.getNumFaces obj
        if faceCount == 0 then exit

        local elementFaces = polyop.getElementsUsingFace obj 1
        polyop.setFaceSelection obj elementFaces
        polyop.detachFaces obj elementFaces delete:true asNode:true
    )
)

if selection.count == 0 then (
    messageBox "オブジェクトを選択してください。"
) else (
    for obj in selection do detachAllElements obj
)
