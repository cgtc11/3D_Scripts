macroScript ObjExp Category:"# Scripts" toolTip:"ObjExp"
Icon:#("ImpExp",2)
(
-- OBJを書き出すMaxScript（選択したオブジェクトのみ、C:\Temp\ImpExp.iniの設定に従う）
local iniPath = "C:\\Temp\\ImpExp.ini"
local folder = "C:\\Temp\\"
local objName = "model.obj"

if doesFileExist iniPath then (
	local f = getINISetting iniPath "Path" "folder"
	local o = getINISetting iniPath "Path" "obj_name"
	if f != "" do folder = f
	if o != "" do objName = o
)

local objPath = folder + objName

if selection.count > 0 then (
	exportFile objPath #noPrompt selectedOnly:true using:OBJExporter
) else (
	messageBox "No objects selected."
)
)
