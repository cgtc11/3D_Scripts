-------------------------------------------------------------------------
-- UV_AlignPerElement.ms  (v02: 重なり回避オプション追加)
-- Unwrap UVW で選択しているUV(頂点／エッジ／フェース／エレメント、
-- どのサブオブジェクトモードでもOK)を、要素（シェル）ごとにグループ分けし、
-- 各要素の形状は維持したまま平行移動させて、
-- 上／下／左／右／中央のいずれかに整列させるツール
--
--        [上]
--   [左] [中央] [右]
--        [下]
--
--   上   : 全要素の中で一番高い"最上部"の高さに、各要素の最上部を揃える
--   下   : 全要素の中で一番低い"最下部"の高さに、各要素の最下部を揃える
--   左   : 全要素の中で一番左の位置に、各要素の左端を揃える
--   右   : 全要素の中で一番右の位置に、各要素の右端を揃える
--   中央 : 全要素をまとめたバウンディングボックスの中心に、
--          各要素自身の中心が来るように揃える
--
-- 選択されている部分が属する要素だけを調べるので、選択していない
-- 他の要素には触れません。処理後は元の選択状態に戻します。
--
-- 各要素の形（頂点間の相対位置）は変えず、平行移動のみで整列します。
--
-- [v02 追加] 「重なりを自動回避」チェックを ON にすると、整列後に
-- 各要素のバウンディングボックス同士が重なっていないかをチェックし、
-- 重なっている要素を（上下整列時は横方向／左右整列時は縦方向／
-- 中央整列時は指定した方向）へ少しずつずらして重ならないようにします。
-- 「隙間」スピナーで、ずらした要素同士の間隔を調整できます。
--
-- 動作確認想定: 3ds Max 2023 / 2024 / 2025 / 2026 以降
-- (頂点/エッジモードでの動作は未検証の関数を含みます。エラーが出た場合は
--  そのエラー画面を報告してください)
-------------------------------------------------------------------------

(
	global rollUVAlignPerElement

	fn UVA_findUnwrapMod obj =
	(
		local m = undefined
		for i = 1 to obj.modifiers.count while m == undefined do
		(
			if classOf obj.modifiers[i] == Unwrap_UVW do m = obj.modifiers[i]
		)
		m
	)

	-- 1オブジェクト分: 選択されているUV(頂点/エッジ/フェース/エレメントいずれか)を
	-- 要素ごとにグループ化し、各グループの情報を返す
	-- #(obj, mod, verts, positions, minU, maxU, minV, maxV, centerU, centerV)
	fn UVA_collectGroupsForObject obj =
	(
		local result = #()
		local mod = UVA_findUnwrapMod obj
		if mod == undefined do return result

		local curMode = 1
		try (curMode = mod.getTVSubObjectMode()) catch()

		-- ① 元の選択状態を保存し、真の「対象頂点セット」を求める
		local origSelVerts = undefined
		local origSelForRestore = undefined -- 復元用（そのモードでの元の選択）

		case curMode of
		(
			1: -- 頂点モード
			(
				origSelVerts = mod.getSelectedVertices()
				origSelForRestore = origSelVerts
			)
			2: -- エッジモード
			(
				local origSelEdges = mod.getSelectedEdges()
				origSelForRestore = origSelEdges
				mod.edgeToVertSelect()
				origSelVerts = mod.getSelectedVertices()
			)
			default: -- フェース(3) / エレメント(4) モード
			(
				local origSelFaces = mod.getSelectedFaces()
				origSelForRestore = origSelFaces
				mod.faceToVertSelect()
				origSelVerts = mod.getSelectedVertices()
			)
		)

		if origSelVerts == undefined do return result
		local origSelVertsArr = origSelVerts as array
		if origSelVertsArr.count == 0 do return result

		-- ② 対象頂点が触れているフェースを求め、それを起点に要素を探索する
		mod.setTVSubObjectMode 1
		mod.selectVertices origSelVerts
		mod.vertToFaceSelect()
		local seedFacesBA = mod.getSelectedFaces()
		local seedFacesArr = seedFacesBA as array

		local processed = #{}
		local t = currentTime

		for f in seedFacesArr do
		(
			if not processed[f] do
			(
				mod.setTVSubObjectMode 3
				mod.selectFaces #{f}
				mod.selectElement()
				local elemFacesBA = mod.getSelectedFaces()
				processed += elemFacesBA

				-- この要素の全頂点を求め、元の対象頂点セットと交差させる
				mod.selectFaces elemFacesBA
				mod.faceToVertSelect()
				local elemVertsBA = mod.getSelectedVertices()
				local groupVertsBA = elemVertsBA * origSelVerts
				local groupVertsArr = groupVertsBA as array

				if groupVertsArr.count > 0 do
				(
					local minU = 1e30
					local maxU = -1e30
					local minV = 1e30
					local maxV = -1e30
					local positions = #()

					for vi in groupVertsArr do
					(
						local p = mod.getVertexPosition t vi
						append positions p
						if p.x < minU do minU = p.x
						if p.x > maxU do maxU = p.x
						if p.y < minV do minV = p.y
						if p.y > maxV do maxV = p.y
					)

					local centerU = (minU + maxU) / 2.0
					local centerV = (minV + maxV) / 2.0

					append result #(obj, mod, groupVertsArr, positions, minU, maxU, minV, maxV, centerU, centerV)
				)
			)
		)

		-- ③ 選択状態と元のサブオブジェクトモードを復元
		mod.setTVSubObjectMode curMode
		case curMode of
		(
			1: mod.selectVertices origSelForRestore
			2: mod.selectEdges origSelForRestore
			default: mod.selectFaces origSelForRestore
		)

		result
	)

	-- [v02] 重なり回避パス用ヘルパー関数
	-- MAXScriptでは入れ子のfnから外側のfnのローカル変数／引数を直接参照できない
	-- ("外部のローカル変数参照はここでは許可されません")ため、必要な値はすべて
	-- 引数として渡すトップレベルの関数として用意する。

	-- groups[idx] と移動量 dUs[idx], dVs[idx] から、現在のバウンディングボックスを求める
	-- 戻り値: #(minU, maxU, minV, maxV)
	fn UVA_getBBoxAt groups dUs dVs idx =
	(
		local g = groups[idx]
		#(g[5] + dUs[idx], g[6] + dUs[idx], g[7] + dVs[idx], g[8] + dVs[idx])
	)

	-- 2つのバウンディングボックスが、shiftAxisと垂直な方向で範囲が重なっているか判定する
	-- （垂直方向で重なっていない＝そもそも別の行／列にいる要素同士は、間隔を気にしなくてよい）
	fn UVA_perpOverlap a b eps shiftAxis =
	(
		if shiftAxis == #u then
			(a[3] < b[4] - eps) and (a[4] > b[3] + eps)
		else
			(a[1] < b[2] - eps) and (a[2] > b[1] + eps)
	)

	-- シフト軸（#u なら横位置、#v なら縦位置）上での、要素idxの現在位置を求める
	fn UVA_axisValAt groups dUs dVs shiftAxis idx =
	(
		local bb = UVA_getBBoxAt groups dUs dVs idx
		if shiftAxis == #u then bb[1] else bb[3]
	)

	-- 重なり回避パス本体
	-- groups   : UVA_collectGroupsForObject と同じ形式の配列
	-- dUs, dVs : groups と同じ順番・同じ要素数の移動量配列（このまま書き換える）
	-- shiftAxis: #u（横方向にずらす）または #v（縦方向にずらす）
	-- gap      : 同じ「レーン」（垂直方向の範囲が重なっている）要素同士の間に確保する隙間
	--            （UV空間の単位）。以前の実行結果より隙間を小さくした場合は詰める方向にも動く。
	fn UVA_resolveOverlaps groups dUs dVs shiftAxis gap =
	(
		local n = groups.count
		if n < 2 do return()

		local eps = 1e-6

		-- シフト軸方向の現在位置が小さい要素から順に処理する（挿入ソート）
		local order = #()
		for i = 1 to n do append order i

		for i = 2 to order.count do
		(
			local key = order[i]
			local keyVal = UVA_axisValAt groups dUs dVs shiftAxis key
			local j = i - 1
			while j >= 1 and (UVA_axisValAt groups dUs dVs shiftAxis order[j]) > keyVal do
			(
				order[j + 1] = order[j]
				j -= 1
			)
			order[j + 1] = key
		)

		local placed = #()
		for idx in order do
		(
			local myBox = UVA_getBBoxAt groups dUs dVs idx
			local naturalMin = if shiftAxis == #u then myBox[1] else myBox[3]

			-- 既に配置済みの要素のうち、垂直方向で範囲が重なっている（＝同じ「レーン」にいる）
			-- ものだけを対象に、必要な位置（隙間ぶん離した位置）を求める。
			-- 見つかった場合は、現在の位置がその要求より近くても遠くても、
			-- 常にその位置へ合わせる（＝押し広げるだけでなく、詰める方向にも動く）。
			local hasConflict = false
			local requiredMin = naturalMin

			for pIdx in placed do
			(
				local pBox = UVA_getBBoxAt groups dUs dVs pIdx
				if UVA_perpOverlap myBox pBox eps shiftAxis do
				(
					local neededMin = (if shiftAxis == #u then pBox[2] else pBox[4]) + gap
					if not hasConflict then
					(
						requiredMin = neededMin
						hasConflict = true
					)
					else if neededMin > requiredMin do requiredMin = neededMin
				)
			)

			local shiftAmount = requiredMin - naturalMin
			if shiftAmount != 0.0 do
			(
				if shiftAxis == #u then dUs[idx] += shiftAmount else dVs[idx] += shiftAmount
			)

			append placed idx
		)
	)

	-- 選択オブジェクト全体に対して整列を実行
	-- mode            : #top / #bottom / #left / #right / #center
	-- avoidOverlap    : true にすると重なり回避パスを実行する
	-- gap             : 重なり回避時にずらした要素同士に空ける隙間
	-- shiftAxisForCenter : #center モードで重なりを回避する方向（#u または #v）
	-- fitUV           : true の場合、整列（＋重なり回避）後の全要素の外接ボックスが
	--                   UVタイル(0～1)からはみ出していたら、全体を均等に縮小して収める
	fn UVA_applyToSelection mode avoidOverlap gap shiftAxisForCenter fitUV =
	(
		local objs = for o in selection collect o
		if objs.count == 0 do
		(
			messageBox "オブジェクトを選択してください。" title:"エラー"
			return()
		)

		local allGroups = #()
		for obj in objs do
			join allGroups (UVA_collectGroupsForObject obj)

		if allGroups.count == 0 do
		(
			messageBox "整列対象が見つかりませんでした。\nUnwrap UVWの編集中に、整列させたい頂点／エッジ／フェースを選択してから実行してください。" title:"情報"
			return()
		)

		local targetV_top = -1e30
		local targetV_bottom = 1e30
		local targetU_left = 1e30
		local targetU_right = -1e30
		local overallMinU = 1e30
		local overallMaxU = -1e30
		local overallMinV = 1e30
		local overallMaxV = -1e30

		for g in allGroups do
		(
			local gMinU = g[5]
			local gMaxU = g[6]
			local gMinV = g[7]
			local gMaxV = g[8]
			if gMaxV > targetV_top do targetV_top = gMaxV
			if gMinV < targetV_bottom do targetV_bottom = gMinV
			if gMinU < targetU_left do targetU_left = gMinU
			if gMaxU > targetU_right do targetU_right = gMaxU
			if gMinU < overallMinU do overallMinU = gMinU
			if gMaxU > overallMaxU do overallMaxU = gMaxU
			if gMinV < overallMinV do overallMinV = gMinV
			if gMaxV > overallMaxV do overallMaxV = gMaxV
		)

		local overallCenterU = (overallMinU + overallMaxU) / 2.0
		local overallCenterV = (overallMinV + overallMaxV) / 2.0

		-- ① まず各要素の基本の移動量（整列のみ）を求める
		local dUs = #()
		local dVs = #()
		for g in allGroups do
		(
			local gMinU = g[5]
			local gMaxU = g[6]
			local gMinV = g[7]
			local gMaxV = g[8]
			local gCenterU = g[9]
			local gCenterV = g[10]

			local dU = 0.0
			local dV = 0.0

			case mode of
			(
				#top:    dV = targetV_top - gMaxV
				#bottom: dV = targetV_bottom - gMinV
				#left:   dU = targetU_left - gMinU
				#right:  dU = targetU_right - gMaxU
				#center: ( dU = overallCenterU - gCenterU; dV = overallCenterV - gCenterV )
			)

			append dUs dU
			append dVs dV
		)

		-- ② 重なり回避（オプション）
		if avoidOverlap do
		(
			local shiftAxis = case mode of
			(
				#top:    #u
				#bottom: #u
				#left:   #v
				#right:  #v
				#center: shiftAxisForCenter
				default: #u
			)
			UVA_resolveOverlaps allGroups dUs dVs shiftAxis gap
		)

		-- ③ UV内(0～1)に収める（オプション）
		-- 整列（＋重なり回避）後の全要素をまとめた外接ボックスがUVタイルの
		-- 幅または高さ1.0を超えていたら、その外接ボックスの左下(minU,minV)を
		-- 基点にして、縦横同じ比率で縮小し、はみ出た分を収める
		local fitScale = 1.0
		local pivotU = 0.0
		local pivotV = 0.0

		if fitUV do
		(
			local finalMinU = 1e30
			local finalMaxU = -1e30
			local finalMinV = 1e30
			local finalMaxV = -1e30

			for i = 1 to allGroups.count do
			(
				local g = allGroups[i]
				local mnU = g[5] + dUs[i]
				local mxU = g[6] + dUs[i]
				local mnV = g[7] + dVs[i]
				local mxV = g[8] + dVs[i]
				if mnU < finalMinU do finalMinU = mnU
				if mxU > finalMaxU do finalMaxU = mxU
				if mnV < finalMinV do finalMinV = mnV
				if mxV > finalMaxV do finalMaxV = mxV
			)

			pivotU = finalMinU
			pivotV = finalMinV

			local widthUV = finalMaxU - finalMinU
			local heightUV = finalMaxV - finalMinV

			if widthUV > 1.0 do fitScale = amin fitScale (1.0 / widthUV)
			if heightUV > 1.0 do fitScale = amin fitScale (1.0 / heightUV)
		)

		-- ④ 実際に頂点を移動する（fitUVがONで縮小が必要な場合は、位置と形状をまとめて縮小する）
		local t = currentTime

		undo "UVを要素ごとに整列（形状維持）" on
		(
			for i = 1 to allGroups.count do
			(
				local g = allGroups[i]
				local mod = g[2]
				local verts = g[3]
				local positions = g[4]
				local dU = dUs[i]
				local dV = dVs[i]

				for k = 1 to verts.count do
				(
					local vi = verts[k]
					local p = positions[k]
					local movedU = p.x + dU
					local movedV = p.y + dV
					local newU = pivotU + (movedU - pivotU) * fitScale
					local newV = pivotV + (movedV - pivotV) * fitScale
					local newP = [newU, newV, p.z]
					mod.setVertexPosition t vi newP
				)
			)
		)

		local statusSuffix = ""
		if avoidOverlap do statusSuffix += "・重なり回避あり"
		if fitUV and fitScale < 1.0 do statusSuffix += ("・UV内に縮小(x" + (fitScale as string) + ")")

		format "% 個の要素を整列しました（形状は維持%）。\n" allGroups.count statusSuffix
		completeRedraw()
	)

	-- objの既存モディファイアの中に、指定クラスのモディファイアがあるか調べる
	fn UVA_hasModifierOfClass obj cls =
	(
		local found = false
		for m in obj.modifiers while not found do
		(
			if classOf m == cls do found = true
		)
		found
	)

	-- nodeの既存モディファイアからEdit_Polyを探す
	fn UVA_findEditPoly node =
	(
		local found = undefined
		for m in node.modifiers while found == undefined do
		(
			if classOf m == Edit_Poly do found = m
		)
		found
	)

	-- UVGridStraightener.ms の挙動に合わせる:
	-- ・Edit Polyが既に無ければ Edit Poly を追加する
	-- ・Edit Polyを追加した場合、既存のUnwrap UVWがあっても触らず、
	--   新しいUnwrap UVWを別途スタックの上に追加してカレントにする
	-- ・Edit Polyが既にある場合は、Unwrap UVWの有無に関わらず何もしない
	fn UVA_addEditPolyToNode node =
	(
		if node == undefined do return false

		local ep = undefined
		try
		(
			ep = Edit_Poly()
			addModifier node ep
		)
		catch
		(
			return false
		)

		local newUnwrap = undefined
		try
		(
			newUnwrap = Unwrap_UVW()
			addModifier node newUnwrap
		)
		catch
		(
			return false
		)

		try (modPanel.setCurrentObject newUnwrap ui:true) catch()
		true
	)

	fn UVA_addEditPolyToSelection =
	(
		local nodes = for n in selection where isValidNode n collect n

		if nodes.count == 0 do
		(
			messageBox "オブジェクトを選択してください。" title:"エラー"
			return false
		)

		local addedCount = 0
		local existingCount = 0
		local failedCount = 0

		for n in nodes do
		(
			if UVA_findEditPoly n != undefined then
			(
				existingCount += 1
			)
			else
			(
				if UVA_addEditPolyToNode n then addedCount += 1 else failedCount += 1
			)
		)

		local msg = "ポリゴンを編集の追加：完了\n\n追加: " + (addedCount as string) + " 個\n既にあった: " + (existingCount as string) + " 個"
		if failedCount > 0 do msg += "\n失敗: " + (failedCount as string) + " 個"

		messageBox msg title:"UVを要素ごとに整列"
		true
	)

	try (destroyDialog rollUVAlignPerElement) catch()

	rollout rollUVAlignPerElement "UVを要素ごとに整列（形状維持）" width:280 height:428
	(
		button btnAddMods "ポリゴンを編集の追加" pos:[20,8] width:240 height:26

		label lblInfo "Unwrap UVWで整列したいUVを選択してから押してください" pos:[10,42] width:260 height:28

		button btnTop    "上"   pos:[110,74]  width:60 height:28
		button btnLeft   "左"   pos:[40,108]  width:60 height:28
		button btnCenter "中央" pos:[110,108] width:60 height:28
		button btnRight  "右"   pos:[180,108] width:60 height:28
		button btnBottom "下"   pos:[110,142] width:60 height:28

		group "重なり回避（オプション）"
		(
			checkbutton chkAvoid "重なりを自動回避する" pos:[20,186] width:240 height:22 checked:false

			label lblAxis "中央整列時の回避方向：" pos:[20,220] width:240 height:16
			radiobuttons rdoAxis "" pos:[36,242] width:220 height:40 \
				labels:#("横方向(U)にずらす", "縦方向(V)にずらす") default:1 columns:1

			label lblGap "隙間：" pos:[20,290] width:50 height:16
			spinner spnGap "" pos:[70,288] width:100 height:16 range:[0.0,10.0,0.02] type:#float scale:0.001
		)

		group "UVタイルに収める（オプション）"
		(
			checkbox chkFitUV "UV内に収める" pos:[20,352] width:220 height:16 checked:false
		)

		label lblStatus "" pos:[10,384] width:260 height:32

		fn UVA_currentAxisOverride = (if rdoAxis.state == 1 then #u else #v)

		on btnAddMods pressed do
		(
			btnAddMods.enabled = false
			lblStatus.text = "ポリゴンを編集を追加しています..."
			windows.processPostedMessages()

			UVA_addEditPolyToSelection()

			btnAddMods.enabled = true
			lblStatus.text = "待機中"
			windows.processPostedMessages()
		)
		on btnTop    pressed do ( UVA_applyToSelection #top    chkAvoid.checked spnGap.value (UVA_currentAxisOverride()) chkFitUV.checked; lblStatus.text = "上端に整列しました（形状維持）" )
		on btnBottom pressed do ( UVA_applyToSelection #bottom chkAvoid.checked spnGap.value (UVA_currentAxisOverride()) chkFitUV.checked; lblStatus.text = "下端に整列しました（形状維持）" )
		on btnLeft   pressed do ( UVA_applyToSelection #left   chkAvoid.checked spnGap.value (UVA_currentAxisOverride()) chkFitUV.checked; lblStatus.text = "左端に整列しました（形状維持）" )
		on btnRight  pressed do ( UVA_applyToSelection #right  chkAvoid.checked spnGap.value (UVA_currentAxisOverride()) chkFitUV.checked; lblStatus.text = "右端に整列しました（形状維持）" )
		on btnCenter pressed do ( UVA_applyToSelection #center chkAvoid.checked spnGap.value (UVA_currentAxisOverride()) chkFitUV.checked; lblStatus.text = "中央に整列しました（形状維持）" )
	)

	createDialog rollUVAlignPerElement
)
