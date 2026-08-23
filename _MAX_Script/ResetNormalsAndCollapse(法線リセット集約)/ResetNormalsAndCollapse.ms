try (destroyDialog ResetNormalsAndCollapseUI) catch ()

rollout ResetNormalsAndCollapseUI "法線リセット＋自動スムース v010"
(
    label statusLabel "複数モデルを選択してください" width:230 align:#center
    spinner smoothAngleSpinner "自動スムース角度:" range:[0.0,180.0,45.0] type:#float scale:1.0 fieldWidth:60 align:#center
    checkbox collapseCheckBox "最後に集約" checked:true align:#center
    button runButton "選択モデルを一括処理" width:190 height:36 align:#center

    on runButton pressed do
    (
        local targets = #()
        for obj in (selection as array) do
        (
            if ((isValidNode obj) and ((superClassOf obj) == GeometryClass)) do append targets obj
        )

        if targets.count == 0 then
        (
            statusLabel.text = "モデルが選択されていません"
        )
        else
        (
            local smoothAngle = smoothAngleSpinner.value
            local shouldCollapse = collapseCheckBox.checked

            try
            (
                undo "法線リセット＋自動スムース" on
                (
                    with redraw off
                    (
                        -- 複数選択を維持したままModifyパネルを開く
                        select targets
                        max modify mode
                        subObjectLevel = 0

                        -- 選択全体へ共有のEdit Normalsを1回で追加
                        local editNormalsModifier = Edit_Normals()
                        modPanel.addModToSelection editNormalsModifier

                        -- 面数を保存し、共有Edit Normals内の全モデルの法線をリセット
                        local faceCounts = #()
                        for obj in targets do
                        (
                            append faceCounts (editNormalsModifier.GetNumFaces node:obj)

                            local normalCount = editNormalsModifier.GetNumNormals node:obj
                            if normalCount > 0 do
                            (
                                local allNormals = #{1..normalCount}
                                editNormalsModifier.Reset selection:allNormals node:obj
                            )
                        )

                        -- 選択全体へ共有のEdit Polyを1回で追加
                        local editPolyModifier = Edit_Poly()
                        modPanel.addModToSelection editPolyModifier
                        modPanel.setCurrentObject editPolyModifier ui:true

                        -- 要素レベルへ移動
                        editPolyModifier.SetEPolySelLevel #Element
                        subObjectLevel = 5

                        -- 共有Edit Poly内の各ノードですべての要素を選択
                        for i = 1 to targets.count do
                        (
                            if faceCounts[i] > 0 do
                            (
                                local allFaces = #{1..faceCounts[i]}
                                editPolyModifier.SetSelection #Face allFaces node:targets[i]
                            )
                        )

                        -- 全ノードの選択設定後、自動スムースを1回だけ確定
                        editPolyModifier.autoSmoothThreshold = smoothAngle
                        editPolyModifier.SetOperation #Autosmooth
                        editPolyModifier.Commit()

                        -- 自動スムース確定後、必要な場合だけ集約
                        if shouldCollapse then
                        (
                            subObjectLevel = 0
                            collapseStack targets
                            select targets
                        )
                    )
                )

                redrawViews()

                if shouldCollapse then
                (
                    statusLabel.text = ((targets.count as string) + "個完了・集約済み")
                )
                else
                (
                    statusLabel.text = ((targets.count as string) + "個完了・全モデル確定済み")
                )
            )
            catch
            (
                statusLabel.text = "処理に失敗しました"
                format "一括処理失敗: %\n" (getCurrentException())
            )
        )
    )
)

createDialog ResetNormalsAndCollapseUI 280 158
