macroScript Bipedkey tooltip:"Bipedkey" Category:"# Scripts" Icon:#("Bipedkey",1)
(
--********************************************************************************************

(
	-- 1. 元のスクリプトからドット絵描画エンジンを移植
	fn CreateImage p = (
		c = bitmap p[1].count p.count gamma:0.45
		for y = 1 to p.count do (
			for x = 1 to p[y].count do (setPixels c [x,y] p[y][x])
		)
		c
	)

	-- 2. 動作関数
	fn getAllBipBones = (for obj in geometry where classof obj == Biped_Object collect obj)

	-- 3. ロールアウト定義（タイトルをBipedKeyに変更）
	rollout MiniBipSel "BipedKey"
	(
		local b_sz = 22
		
		-- 上段（赤丸）
		button btn_all "A" pos:[35, 5] width:b_sz height:b_sz toolTip:"Select All"
		button btn_vis "V" pos:[57, 5] width:b_sz height:b_sz toolTip:"Show/Hide"
		button btn_box "B" pos:[79, 5] width:b_sz height:b_sz toolTip:"Box Mode"
		button btn_xry "X" pos:[101, 5] width:b_sz height:b_sz toolTip:"X-Ray"

		-- 下段（赤丸）
		button btn_set "●" pos:[5, 32] width:b_sz height:b_sz toolTip:"Set Key"
		button btn_key "A" pos:[27, 32] width:b_sz height:b_sz toolTip:"Key All"
		button btn_del "X" pos:[49, 32] width:b_sz height:b_sz toolTip:"Delete Key"
		button btn_pla "P" pos:[71, 32] width:b_sz height:b_sz toolTip:"Planted"
		button btn_sli "S" pos:[93, 32] width:b_sz height:b_sz toolTip:"Sliding"
		button btn_fre "F" pos:[115, 32] width:b_sz height:b_sz toolTip:"Free"
		checkbutton btn_lck "L" pos:[137, 32] width:b_sz height:b_sz toolTip:"Lock COM"

		-- イベント処理 (ActionID 972555510 を使用)
		on btn_all pressed do select (getAllBipBones())
		on btn_set pressed do (max motion mode; actionMan.executeAction 972555510 "40015")
		on btn_pla pressed do (for o in selection where classof o == Biped_Object do biped.setPlantedKey o)
		on btn_sli pressed do (for o in selection where classof o == Biped_Object do biped.setSlidingKey o)
		on btn_fre pressed do (for o in selection where classof o == Biped_Object do biped.setFreeKey o)
		on btn_lck changed state s do (max motion mode; actionMan.executeAction 972555510 "40185")
	)

	-- 既存のダイアログがあれば閉じてから作成
	try(destroyDialog MiniBipSel)catch()
	createdialog MiniBipSel width:165 height:60
)

--********************************************************************************************
)