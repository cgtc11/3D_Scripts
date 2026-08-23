-------------------------------------------------------------------------
-- PivotToBottom.ms
-- 選択オブジェクトのピボットを「ワールド空間での底辺（最下面/Z軸）」へ配置するツール
--
-- ■ Z軸（底辺）の配置モード
--   ① 各オブジェクトそれぞれの底辺（個別のバウンディングボックス最下面）
--   ② 選択オブジェクト全体の最下面（複数選択時、全オブジェクトを含めた
--      一番低いZ値に全ピボットを揃える／共通の底辺）
--   ③ ワールド原点の高さ（Z=0）に固定。オブジェクトが浮いていても、
--      実際の底辺ではなく地面の高さ（Z=0）にピボットを配置したい場合に使う
--
-- ■ X/Y（底辺以外の軸）の配置モード
--   ・中央に配置する のチェックを外す → 現在のピボットのX/Yをそのまま維持
--   ・中央に配置する をON にした場合:
--       個別 : 各オブジェクト自身のバウンディングボックス中心
--       全体 : 選択オブジェクト全体を含めたバウンディングボックス中心
--       親に合わせる : 親オブジェクトのX/Y位置に合わせる（親がない場合は個別中心）
--
-- ジオメトリ自体は一切移動せず、ピボットのみを移動します（Affect Pivot Only相当）。
-- .pivot への代入はワールド座標で行い、親ローカルへの二重変換は行いません。
-- オブジェクトが回転していても、ワールド空間での実際の頂点位置を基準に
-- 最下面・中心を計算します。
--
-- 動作確認想定: 3ds Max 2023 / 2024 / 2025 / 2026 以降
-------------------------------------------------------------------------

(
	global rollPivotToBottom

	-- ワールド空間での軸並行バウンディングボックスを取得 (#(min, max))
	fn PB_getWorldBBox obj =
	(
		local bb = nodeGetBoundingBox obj (matrix3 1)
		#(bb[1], bb[2])
	)

	-- ジオメトリを動かさずにピボットだけをワールド座標posへ移動する
	fn PB_setPivotWorld obj worldPos =
	(
		-- .pivot は現在の作業座標系（デフォルトはワールド座標系）で解釈される。
		-- 親がいる場合でも親の逆行列で変換してはいけない。
		obj.pivot = worldPos
	)

	-- ピボットを移動すると、リンクしている子オブジェクトの見た目の位置まで
	-- 一緒にズレてしまう（.pivotは自分のジオメトリしか補償してくれない）ため、
	-- 子の現在のワールド変換を記録→ピボット移動→子の変換を元に戻す、という
	-- 手順で「子は一切動かさない」ようにする
	fn PB_setPivotWorldPreserveChildren obj worldPos =
	(
		local childTMs = #()
		for c in obj.children do append childTMs #(c, c.transform)

		PB_setPivotWorld obj worldPos

		for pair in childTMs do pair[1].transform = pair[2]
	)

	-- 選択オブジェクト全体を含めた結合バウンディングボックスを取得
	fn PB_getCombinedBBox objs =
	(
		local minX = 1e30
		local minY = 1e30
		local minZ = 1e30
		local maxX = -1e30
		local maxY = -1e30
		local maxZ = -1e30
		for obj in objs do
		(
			local bb = PB_getWorldBBox obj
			local mn = bb[1]
			local mx = bb[2]
			if mn.x < minX do minX = mn.x
			if mn.y < minY do minY = mn.y
			if mn.z < minZ do minZ = mn.z
			if mx.x > maxX do maxX = mx.x
			if mx.y > maxY do maxY = mx.y
			if mx.z > maxZ do maxZ = mx.z
		)
		#([minX, minY, minZ], [maxX, maxY, maxZ])
	)

	-- オブジェクト1個分のターゲットピボット位置を計算する
	-- zMode  : 1=個別の底辺  2=共通(全体)の底辺  3=ワールド原点の高さ(Z=0)
	-- xyMode : 0=現状維持  1=個別の中心  2=全体の中心  3=親に合わせる
	-- 「親に合わせる」では、親の現在のワールド座標をそのままX/Yに使用する。
	-- PB_applyAll は親→子の順で処理するため、中央配置された親の位置を
	-- 子がそのまま引き継ぐ。
	fn PB_computeTargetPos obj zMode commonMinZ xyMode commonCenterXY =
	(
		local bb = PB_getWorldBBox obj
		local mn = bb[1]
		local mx = bb[2]

		local z
		case zMode of
		(
			2: z = commonMinZ
			3: z = 0.0
			default: z = mn.z
		)

		local x, y
		case xyMode of
		(
			1: ( x = (mn.x + mx.x) / 2.0; y = (mn.y + mx.y) / 2.0 )
			2: ( x = commonCenterXY.x; y = commonCenterXY.y )
			3:
			(
				if obj.parent != undefined then
				(
					local parentWorldPos = obj.parent.transform.pos
					x = parentWorldPos.x
					y = parentWorldPos.y
				)
				else
				(
					-- 親がいない場合は個別の中心にフォールバック
					x = (mn.x + mx.x) / 2.0
					y = (mn.y + mx.y) / 2.0
				)
			)
			default:
			(
				local curWorldPos = obj.transform.pos
				x = curWorldPos.x
				y = curWorldPos.y
			)
		)
		[x, y, z]
	)

	-- オブジェクトの階層の深さ（親を何回辿るとルートに着くか）を返す
	fn PB_getDepth obj =
	(
		local depth = 0
		local cur = obj.parent
		while cur != undefined do
		(
			depth += 1
			cur = cur.parent
		)
		depth
	)

	fn PB_applyAll objs zMode xyMode =
	(
		local commonMinZ = undefined
		local commonCenterXY = undefined

		if zMode == 2 or xyMode == 2 do
		(
			local cbb = PB_getCombinedBBox objs
			local cmn = cbb[1]
			local cmx = cbb[2]
			if zMode == 2 do commonMinZ = cmn.z
			if xyMode == 2 do commonCenterXY = [(cmn.x + cmx.x) / 2.0, (cmn.y + cmx.y) / 2.0]
		)

		-- 階層の浅い順（親→子）に並び替えてから、1つずつ計算してすぐ適用する。
		-- こうすることで「親に合わせる」を計算する時点で、親が既に
		-- 新しい位置へ移動済みになっているので、確実に親の新しい位置に揃う
		local depths = for obj in objs collect (PB_getDepth obj)
		local order = #()
		for i = 1 to objs.count do append order i

		-- 単純なバブルソート（深さの浅い順=親→子になるよう並べ替え）
		for i = 1 to order.count - 1 do
		(
			for j = 1 to order.count - i do
			(
				if depths[order[j]] > depths[order[j + 1]] do
				(
					local tmp = order[j]
					order[j] = order[j + 1]
					order[j + 1] = tmp
				)
			)
		)

		local sortedObjs = for i in order collect objs[i]

		for obj in sortedObjs do
		(
			local pos = PB_computeTargetPos obj zMode commonMinZ xyMode commonCenterXY
			PB_setPivotWorldPreserveChildren obj pos
		)

		format "ピボットを配置しました（対象: %個, Zモード:%, XYモード:%）\n" objs.count zMode xyMode
	)

	-- 指定オブジェクトとその子孫すべてを「子→親」の順（下の階層から先）で集める
	fn PB_collectSelfAndDescendants obj resultArr =
	(
		for c in obj.children do PB_collectSelfAndDescendants c resultArr
		appendIfUnique resultArr obj
	)

	-- 選択オブジェクト＋その子孫すべてのスケールを100%にリセットする
	-- （見た目のサイズ・位置・回転は変えず、スケール値だけを正規化する）
	fn PB_resetScaleHierarchy objs =
	(
		local allNodes = #()
		for obj in objs do PB_collectSelfAndDescendants obj allNodes

		-- PB_collectSelfAndDescendants は子→親の順で格納するが、スケールは
		-- 親を後からリセットすると子のローカルスケールへ再び影響が出る。
		-- そのため配列を逆順に走査し、必ず親→子→孫の順で100%にする。
		local count = 0
		for i = allNodes.count to 1 by -1 do
		(
			local n = allNodes[i]
			try
			(
				ResetScale n
				count += 1
			)
			catch()
		)

		format "スケールをリセットしました（対象: %個, 親子階層を含む）\n" count
		count
	)

	-- 1オブジェクト分の回転リセット
	-- worldZero: true=ワールド上でゼロ回転にする / false=親基準（ローカル）でゼロ回転にする
	-- ※ ResetTransformの仕様上、回転と同時にスケールも100%にリセットされます
	fn PB_resetRotationNode obj worldZero =
	(
		if worldZero and obj.parent != undefined then
		(
			local origParent = obj.parent
			obj.parent = undefined -- 一時的に親子関係を解除（ワールド変換は維持される）
			try (ResetTransform obj) catch()
			obj.parent = origParent -- 元の親に戻す（ワールド変換は維持される）
		)
		else
		(
			try (ResetTransform obj) catch()
		)
	)

	-- 選択オブジェクト＋その子孫すべての回転をリセットする
	fn PB_resetRotationHierarchy objs worldZero =
	(
		local allNodes = #()
		for obj in objs do PB_collectSelfAndDescendants obj allNodes

		local count = 0
		for n in allNodes do
		(
			try
			(
				PB_resetRotationNode n worldZero
				count += 1
			)
			catch()
		)

		local modeName = if worldZero then "ワールド上ゼロ" else "ローカル(親基準)でゼロ"
		format "回転をリセットしました（対象: %個, モード:%）\n" count modeName
		count
	)

	-- 選択オブジェクト＋その子孫すべてをEditable Polyへ集約する
	fn PB_collapseToEditablePolyHierarchy objs =
	(
		local allNodes = #()
		for obj in objs do PB_collectSelfAndDescendants obj allNodes

		local convertible = for n in allNodes where (canConvertTo n Editable_Poly) collect n
		local convertedCount = 0

		-- selectionを一括で渡すと、ノードによってはcollapseStack/convertToが
		-- 適用されないため、階層内の各ノードを1個ずつ確実に処理する。
		for n in convertible do
		(
			try
			(
				collapseStack n
				convertTo n Editable_Poly
				convertedCount += 1
			)
			catch
			(
				format "集約に失敗しました: %\n" n.name
			)
		)

		format "Editable Polyへ集約しました（成功: %個 / 対象:%個 / 全%個中, 親子階層を含む）\n" convertedCount convertible.count allNodes.count

		convertedCount
	)

	try (destroyDialog rollPivotToBottom) catch()

	rollout rollPivotToBottom "ピボットを底辺へ配置 (子の位置を保護) v6.5" width:340
	(
		group "底辺（Z軸）の配置モード"
		(
			radiobuttons rdoZ \
				labels:#("① 各オブジェクトそれぞれの底辺（個別）", \
						 "② 選択オブジェクト全体の最下面（共通）", \
						 "③ ワールド原点の高さ（Z=0）") \
				default:1 columns:1
		)

		group "底辺以外の軸（X/Y）の配置"
		(
			checkbox chkCenterXY "中央に配置する" checked:true
			radiobuttons rdoXY \
				labels:#("個別（各オブジェクト自身の中心）", \
						 "全体（選択オブジェクト全体の中心）", \
						 "親に合わせる（親オブジェクトのX/Y位置）") \
				default:1 columns:1
		)

		label lblStatus "選択オブジェクト数: 0" align:#left
		button btnApply "選択オブジェクトに適用" width:300 height:32

		group "スケールのリセット"
		(
			button btnResetScale "スケールをリセット（親子階層を含む）" width:316 height:32
		)

		group "回転のリセット"
		(
			radiobuttons rdoRot \
				labels:#("ワールド上ゼロ", "ローカル(親基準)でゼロ") \
				default:1 columns:1
			button btnResetRot "回転をリセット（親子階層を含む）" width:316 height:32
		)

		group "モディファイア／変換"
		(
			button btnCollapse "集約（Editable Polyへ）" width:316 height:32
		)

		on chkCenterXY changed state do
		(
			rdoXY.enabled = state
		)

		on rollPivotToBottom open do
		(
			lblStatus.text = "選択オブジェクト数: " + (selection.count as string)
			rdoXY.enabled = chkCenterXY.checked
		)

		on btnApply pressed do
		(
			local objs = for o in selection collect o

			if objs.count == 0 then
			(
				messageBox "オブジェクトを選択してください。" title:"エラー"
			)
			else
			(
				local zMode = rdoZ.state
				local xyMode = if chkCenterXY.checked then rdoXY.state else 0

				undo "ピボットを底辺へ移動" on
				(
					PB_applyAll objs zMode xyMode
				)
				lblStatus.text = "選択オブジェクト数: " + (objs.count as string) + "（完了）"
			)
		)

		on btnResetScale pressed do
		(
			local objs = for o in selection collect o

			if objs.count == 0 then
			(
				messageBox "オブジェクトを選択してください。" title:"エラー"
			)
			else
			(
				undo "スケールをリセット（階層含む）" on
				(
					local n = PB_resetScaleHierarchy objs
					lblStatus.text = "選択オブジェクト数: " + (objs.count as string) + "（スケールリセット完了: " + (n as string) + "個）"
				)
			)
		)

		on btnResetRot pressed do
		(
			local objs = for o in selection collect o

			if objs.count == 0 then
			(
				messageBox "オブジェクトを選択してください。" title:"エラー"
			)
			else
			(
				local worldZero = (rdoRot.state == 1)
				undo "回転をリセット（階層含む）" on
				(
					local n = PB_resetRotationHierarchy objs worldZero
					lblStatus.text = "選択オブジェクト数: " + (objs.count as string) + "（回転リセット完了: " + (n as string) + "個）"
				)
			)
		)

		on btnCollapse pressed do
		(
			local objs = for o in selection collect o

			if objs.count == 0 then
			(
				messageBox "オブジェクトを選択してください。" title:"エラー"
			)
			else
			(
				undo "Editable Polyへ集約（階層含む）" on
				(
					local n = PB_collapseToEditablePolyHierarchy objs
					lblStatus.text = "選択オブジェクト数: " + (objs.count as string) + "（Editable Polyへ集約完了: " + (n as string) + "個）"
				)
				select objs
			)
		)
	)

	createDialog rollPivotToBottom
)
