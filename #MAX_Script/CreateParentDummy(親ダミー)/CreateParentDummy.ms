/*
    Create Parent Dummy

    Result example:
      Before: Unit01 -> base01
      Input : size=100, child name=waku
      After : Unit01 (new dummy) -> waku (selected object) -> base01
*/

try (destroyDialog CreateParentDummyRollout) catch ()

rollout CreateParentDummyRollout "親ダミー作成" width:330
(
    spinner spnDummySize "ダミーの大きさ: " range:[0.001, 1000000.0, 100.0] type:#worldunits fieldWidth:90
    editText edtSpecifiedName "指定する名前: " text:"waku" fieldWidth:140
    radioButtons rbNameMode "名前の割り当て" labels:#("元の名前を親 / 指定名を子", "指定名を親 / 元の名前を子") columns:1 default:1
    button btnCreate "親ダミーを作成" width:290 height:32 align:#center

    fn makeParentDummy target dummySize requestedName nameMode =
    (
        local oldName = target.name
        local oldParent = target.parent
        local oldTransform = target.transform
        local specifiedName = requestedName

        if specifiedName == "" then
        (
            messageBox "指定名を入力してください。" title:"親ダミー作成"
            return false
        )

        local parentDummy = dummy name:(uniqueName oldName) boxsize:[dummySize, dummySize, dummySize]
        parentDummy.transform = oldTransform

        -- Keep the selected object's previous hierarchy.
        if isValidNode oldParent do parentDummy.parent = oldParent

        if nameMode == 1 then
        (
            -- Parent = selected object's original name / Child = specified name
            target.name = uniqueName specifiedName
            parentDummy.name = oldName
        )
        else
        (
            -- Parent = specified name / Child = selected object's original name
            parentDummy.name = uniqueName specifiedName
            target.name = oldName
        )

        target.parent = parentDummy

        select target
        true
    )

    on btnCreate pressed do
    (
        if selection.count == 0 then
        (
            messageBox "親ダミーを作るオブジェクトを選択してください。" title:"親ダミー作成"
        )
        else
        (
            local targets = selection as array
            local createdCount = 0

            undo "Create Parent Dummy" on
            (
                for obj in targets where isValidNode obj do
                (
                    if makeParentDummy obj spnDummySize.value edtSpecifiedName.text rbNameMode.state do createdCount += 1
                )
            )

            if createdCount > 0 do
                format "親ダミー作成: % 個のオブジェクトを処理しました。\n" createdCount
        )
    )
)

createDialog CreateParentDummyRollout
