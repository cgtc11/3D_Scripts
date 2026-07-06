macroScript FbxExp Category:"# Scripts" toolTip:"FbxExp"
Icon:#("ImpExp",4)
(
-- FBXを書き出すMaxScript（選択したオブジェクトのみ、C:\Temp\ImpExp.iniの設定に従う）
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

if selection.count > 0 then (
	exportFile fbxPath #noPrompt selectedOnly:true using:FBXEXP
) else (
	messageBox "No objects selected."
)
)
