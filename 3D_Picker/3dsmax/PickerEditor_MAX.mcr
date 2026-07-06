macroScript PickerEditor_MAX tooltip:"ピッカー用エディタ" Category:"# Scripts" Icon:#("PickerEditor",1)

(
on execute do
    (
        -- Maxのユーザースクリプトフォルダのパスを取得して合体させる
        local scriptDir = getDir #userScripts
        local pyFile = scriptDir + "\\PickerEditor_MAX.py"
        
        python.ExecuteFile pyFile
    )
)