macroScript FbxImp Category:"# Scripts" toolTip:"FbxImp"
Icon:#("ImpExp",3)
(
-- FBXを読み込むMaxScript（C:\Temp\ImpExp.iniの設定に従う）
local iniPath = "C:\\Temp\\ImpExp.ini"
local folder = "C:\\Temp\\"
local fbxName = "model.fbx"

if doesFileExist iniPath then (
	local f = getINISetting iniPath "Path" "folder"
	local x = getINISetting iniPath "Path" "fbx_name"
	if f != "" do folder = f
	if x != "" do fbxName = x
)

local fbxPath = folder + fbxName
importFile fbxPath #noPrompt
)
