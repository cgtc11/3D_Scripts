/*
    ShowSystemColorOnly v1.0
    3ds Max MAXScript

    マテリアル未割り当て（システムカラー）のジオメトリだけを表示します。
*/

global ShowSystemColorOnly_Rollout

try (destroyDialog ShowSystemColorOnly_Rollout) catch()

rollout ShowSystemColorOnly_Rollout "システムカラーのみ表示 v1.0" width:400 height:225
(
    local savedVisibility = #() -- #(node, wasHidden)

    label lblDescription "マテリアル未割り当てのジオメトリだけを表示します。" pos:[20,18] width:360 height:20
    label lblCondition "判定条件：オブジェクトの material が undefined" pos:[20,42] width:360 height:20

    button btnShowOnly "システムカラーのオブジェクトだけ表示" pos:[20,74] width:360 height:38
    button btnRestore "実行前の表示状態に戻す" pos:[20,122] width:175 height:32
    button btnShowAll "ジオメトリをすべて表示" pos:[205,122] width:175 height:32

    label lblStatus "準備完了" pos:[20,170] width:360 height:38

    fn saveCurrentVisibility =
    (
        savedVisibility = #()

        for obj in geometry do
        (
            append savedVisibility #(obj, obj.isHidden)
        )
    )

    fn showOnlySystemColorObjects =
    (
        saveCurrentVisibility()

        local noMaterialCount = 0
        local assignedCount = 0

        undo "システムカラーのみ表示" on
        (
            for obj in geometry do
            (
                if obj.material == undefined then
                (
                    unhide obj
                    noMaterialCount += 1
                )
                else
                (
                    hide obj
                    assignedCount += 1
                )
            )
        )

        redrawViews()

        lblStatus.text =
            "表示：" + noMaterialCount as string + "個　" +
            "非表示：" + assignedCount as string + "個"
    )

    fn restoreVisibility =
    (
        if savedVisibility.count == 0 then
        (
            messageBox "保存された表示状態がありません。" title:"システムカラーのみ表示 v1.0"
            false
        )
        else
        (
            local restoredCount = 0

            undo "表示状態を復元" on
            (
                for entry in savedVisibility do
                (
                    local obj = entry[1]

                    if isValidNode obj do
                    (
                        if entry[2] then hide obj else unhide obj
                        restoredCount += 1
                    )
                )
            )

            redrawViews()
            lblStatus.text = "実行前の表示状態へ " + restoredCount as string + "個復元しました。"
            true
        )
    )

    fn showAllGeometry =
    (
        local shownCount = 0

        undo "ジオメトリをすべて表示" on
        (
            for obj in geometry do
            (
                unhide obj
                shownCount += 1
            )
        )

        redrawViews()
        lblStatus.text = "ジオメトリを " + shownCount as string + "個表示しました。"
    )

    on btnShowOnly pressed do showOnlySystemColorObjects()
    on btnRestore pressed do restoreVisibility()
    on btnShowAll pressed do showAllGeometry()
)

createDialog ShowSystemColorOnly_Rollout
