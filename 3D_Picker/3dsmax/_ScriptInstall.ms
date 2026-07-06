messageBox "スクリプトをインストールします\nいいですか?" title:"Confirmation"

(
    -- このインストーラーがある場所を取得
    local currentDir = getFilenamePath (getSourceFileName())
    
    -- 1. usericons フォルダのコピー ----------------------------
    local srcIconDir = currentDir + "usericons\\"
    local dstIconDir = getDir #userIcons
    
    if doesDirectoryExist srcIconDir then (
        -- フォルダがなければ作成
        if not (doesDirectoryExist dstIconDir) do makeDir dstIconDir
        
        local iconFiles = getFiles (srcIconDir + "*.*")
        for f in iconFiles do (
            local target = dstIconDir + "\\" + (filenameFromPath f)
            if doesFileExist target do deleteFile target
            copyFile f target
        )
    ) else (
        messageBox "usericonsフォルダが見つかりません"
    )

    -- 2. scripts フォルダ（Python本体）のコピー --------------------
    local srcPyDir = currentDir + "scripts\\"
    local dstPyDir = getDir #userScripts
    
    if doesDirectoryExist srcPyDir then (
        local pyFiles = getFiles (srcPyDir + "*.*")
        for f in pyFiles do (
            local target = dstPyDir + "\\" + (filenameFromPath f)
            if doesFileExist target do deleteFile target
            copyFile f target
        )
    ) else (
        messageBox "scriptsフォルダが見つかりません"
    )

    -- 3. マクロ（.mcr）の登録 --------------------------------
    local mcr1 = currentDir + "PickerEditor_MAX.mcr"
    local mcr2 = currentDir + "PickerPlayer_MAX.mcr"
    local mcr3 = currentDir + "Bipedkey.mcr"

    if doesFileExist mcr1 then fileIn mcr1 else print "mcr1が見つかりません"
    if doesFileExist mcr2 then fileIn mcr2 else print "mcr2が見つかりません"
    if doesFileExist mcr3 then fileIn mcr3 else print "mcr3が見つかりません"

    messageBox "インストールできました\nツールバーのカスタマイズから「# Scripts」を探してください"
)