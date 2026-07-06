macroScript ObjImp Category:"# Scripts" toolTip:"ObjImp"
Icon:#("ImpExp",1)
(
-- OBJを読み込むMaxScript（C:\Temp\ImpExp.iniの設定に従う）
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
importFile objPath #noPrompt
)
