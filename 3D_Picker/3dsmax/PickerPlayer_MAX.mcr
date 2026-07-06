macroScript PickerPlayer_MAX tooltip:"ピッカー用プレーヤー" Category:"# Scripts" Icon:#("PickerPlayer",1)

(
on execute do
    (
        -- Maxのユーザースクリプトフォルダのパスを取得して合体させる
        local scriptDir = getDir #userScripts
         local pyFile = scriptDir + "\\PickerPlayer_MAX.py"
        
        python.ExecuteFile pyFile
    )
)
