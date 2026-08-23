/*
    UVGridStraightener.ms
    ------------------------------------------------------------
    目的:
      Unwrap UVW 上で選択した Quad 面を、均一な正方形グリッドへ並べ直す。

    主な仕様:
      - 選択面は Quad のみ対応
      - 「切れているUVを可能な限り繋げる」が OFF:
          現在の UV シームを維持し、UV アイランド単位でグリッド化
      - ON:
          3D メッシュ上で隣接する選択面を追跡し、
          共有3DエッジからUVシームを直接検出。
          標準Stitch Custom（Align ON / Bias 0.5）を実行し、残ったシームは
          3D頂点対応を使って直接TV参照を統合。ループを閉じるシームだけ残す
      - 閉じた円筒など、完全に繋ぐと平面化できない箇所は、
          矛盾した接続を残す（シームとして維持）
      - デバッグログを %TEMP%\UVGridStraightener.log に出力

    注意:
      - Triangle / N-gon / 放射状 / 分岐など、グリッド化で矛盾する要素だけ自動スキップ
      - 分岐・Pole・特殊トポロジーでは安全のため処理をスキップする場合がある
      - できるだけ「選択したい UV アイランド全体」を Face 選択して使用すること
*/

global UGS_DebugEnabled = true
global UGS_LogPath = ((getDir #temp) + "\\UVGridStraightener.log")
global UGS_LastStatus = ""
global UGS_ProgressActive = false
global UGS_ActivityFrame = 0

fn UGS_ActivityText msg =
(
    UGS_ActivityFrame += 1
    if UGS_ActivityFrame > 4 do UGS_ActivityFrame = 1

    case UGS_ActivityFrame of
    (
        1: (msg + " .")
        2: (msg + " ..")
        3: (msg + " ...")
        default: (msg + " ....")
    )
)

fn UGS_ProgressStart =
(
    try
    (
        setProgressCancel false
        progressStart "UV Grid Straightener" allowCancel:false
        UGS_ProgressActive = true
        true
    )
    catch
    (
        UGS_ProgressActive = false
        false
    )
)

fn UGS_ProgressEnd =
(
    if UGS_ProgressActive do
    (
        try(progressEnd())catch()
        UGS_ProgressActive = false
    )
)

fn UGS_ShowActivity pct msg =
(
    local p = pct
    if p < 0 do p = 0
    if p > 100 do p = 100
    p = p as integer

    local s = UGS_ActivityText msg

    try
    (
        if UGS_Rollout != undefined do
        (
            if UGS_Rollout.open do UGS_Rollout.lblStatus.text = s
        )
    )
    catch()

    if UGS_ProgressActive do
    (
        try(progressUpdate p stepName:s)catch()
    )

    -- 長いMAXScriptループ中もWindowsメッセージを処理し、
    -- UIが「応答なし」に見えにくくする。
    try(windows.processPostedMessages())catch()
)

fn UGS_ShowLoopActivity basePct spanPct current total msg =
(
    local p = basePct

    if total > 0 do
        p = basePct + ((spanPct as float) * current / total)

    UGS_ShowActivity p msg
)

struct UGS_FaceData
(
    faceID,
    gv,
    tv,
    uv,
    coords,
    assigned = false,
    componentID = 0
)

struct UGS_EdgeOcc
(
    key,
    faceIndex,
    side,
    g1,
    g2,
    t1,
    t2
)

struct UGS_LinkData
(
    f1,
    s1,
    f2,
    s2,
    accepted = false
)

struct UGS_ComponentData
(
    id,
    faceIndices,
    linkIndices,
    valid = true,
    reason = ""
)

struct UGS_SeamGroup
(
    islandA,
    islandB,
    linkIndices,
    accepted = false
)

struct UGS_GlobalSeamLink
(
    faceA,
    cornerA,
    faceB,
    cornerB,
    g1,
    g2,
    islandA,
    islandB,
    selectedA = false,
    selectedB = false
)

struct UGS_GlobalSeamGroup
(
    islandA,
    islandB,
    linkIndices,
    accepted = false
)

fn UGS_Log msg force:false =
(
    local line = ("[UVGrid] " + (msg as string))
    if UGS_DebugEnabled or force do
    (
        format "%\n" line

        local f = undefined
        try
        (
            f = openFile UGS_LogPath mode:"a"
            if f != undefined do
            (
                format "%\n" line to:f
                close f
            )
        )
        catch
        (
            if f != undefined do try(close f)catch()
        )
    )
)

fn UGS_ResetLog =
(
    local f = undefined
    try
    (
        f = createFile UGS_LogPath
        if f != undefined do close f
    )
    catch()
)

fn UGS_PointEqual2D a b tol:0.0001 =
(
    ((abs (a.x - b.x)) <= tol) and ((abs (a.y - b.y)) <= tol)
)

fn UGS_CoordsEqual a b tol:0.0001 =
(
    if a.count != b.count then return false

    for i = 1 to a.count do
    (
        if not (UGS_PointEqual2D a[i] b[i] tol:tol) do return false
    )
    true
)

fn UGS_RoundInt v =
(
    -- 四捨五入して整数化する。UV座標は負値も取り得るため、
    -- int (truncate) ではなく符号を考慮した四捨五入にする。
    if v >= 0 then ((v + 0.5) as integer)
    else -(((-v) + 0.5) as integer)
)

fn UGS_NextCorner c =
(
    if c < 4 then c + 1 else 1
)

fn UGS_CornerAfter c step =
(
    local r = c
    for i = 1 to step do r = UGS_NextCorner r
    r
)

fn UGS_EdgeKey a b =
(
    local mn = amin a b
    local mx = amax a b
    ((mn as string) + ":" + (mx as string))
)

fn UGS_EdgeCompare a b =
(
    stricmp a.key b.key
)

fn UGS_TVForGeom edgeOcc geomID =
(
    if edgeOcc.g1 == geomID then edgeOcc.t1
    else if edgeOcc.g2 == geomID then edgeOcc.t2
    else 0
)

fn UGS_IsUVContinuous edgeA edgeB =
(
    -- UV上で本当に同じエッジを共有しているかをTV頂点IDで判定。
    -- 3D上で同じエッジでも、TV頂点が分離していればUVシームとして扱う。
    ((edgeA.t1 == edgeB.t1) and (edgeA.t2 == edgeB.t2)) or \
    ((edgeA.t1 == edgeB.t2) and (edgeA.t2 == edgeB.t1))
)

fn UGS_FindUnwrap node =
(
    if node == undefined then return undefined

    local currentObj = undefined
    try(currentObj = modPanel.getCurrentObject())catch()

    if currentObj != undefined do
    (
        if (classOf currentObj) == Unwrap_UVW then return currentObj
    )

    for m in node.modifiers do
    (
        if (classOf m) == Unwrap_UVW then return m
    )

    undefined
)


fn UGS_FindEditPoly node =
(
    if node == undefined then return undefined

    for m in node.modifiers do
    (
        if (classOf m) == Edit_Poly then return m
    )

    undefined
)

fn UGS_AddEditPolyToNode node =
(
    if node == undefined then return false

    -- 既存のEdit Polyがあれば、それをそのまま使用する。
    -- 既存のUnwrap UVWの位置は変更しない。
    local existingEditPoly = UGS_FindEditPoly node
    local ep = existingEditPoly
    local editPolyAdded = false

    if ep == undefined then
    (
        try
        (
            ep = Edit_Poly()
            addModifier node ep
            editPolyAdded = true
        )
        catch
        (
            return false
        )
    )

    -- Edit Polyを追加した後、新しいUnwrap UVWを上に追加する。
    -- 既存のUnwrap UVWがあっても、そのモディファイアは移動・並べ替えしない。
    local newUnwrap = undefined
    try
    (
        newUnwrap = Unwrap_UVW()
        addModifier node newUnwrap
    )
    catch
    (
        if editPolyAdded then
        (
            -- Edit Polyは追加できているので、ここは失敗しても既存状態を壊さない。
        )
        return false
    )

    if newUnwrap != undefined then
    (
        try(modPanel.setCurrentObject newUnwrap ui:true)catch()
        true
    )
    else false
)

fn UGS_AddEditPolyToSelection =
(
    local nodes = for n in selection where isValidNode n collect n

    if nodes.count == 0 then
    (
        messageBox "オブジェクトを選択してください。" title:"UV Grid Straightener"
        return false
    )

    local addedCount = 0
    local existingCount = 0
    local failedCount = 0

    for n in nodes do
    (
        if UGS_FindEditPoly n != undefined then
        (
            existingCount += 1
        )
        else
        (
            if UGS_AddEditPolyToNode n then
                addedCount += 1
            else
                failedCount += 1
        )
    )

    local msg = "Edit Poly + Unwrap UVW処理完了\n\nEdit Poly追加: " + (addedCount as string) + " 個\n既存Edit Poly: " + (existingCount as string)
    if failedCount > 0 do
        msg += "\n失敗: " + (failedCount as string)

    messageBox msg title:"UV Grid Straightener"
    true
)

fn UGS_GetFaceSelection uw node =
(
    local faceSel = #{}

    try(faceSel = uw.getSelectedFacesByNode node)catch()

    -- Face選択が無い場合、選択TV頂点を全部含む面を拾う
    if faceSel.numberSet == 0 do
    (
        local tvSel = #{}
        try(tvSel = uw.getSelectedVerticesByNode node)catch()

        if tvSel.numberSet > 0 do
        (
            local numFaces = uw.numberPolygonsByNode node

            for f = 1 to numFaces do
            (
                local degree = uw.numberPointsInFaceByNode f node
                local allSelected = (degree > 0)

                if allSelected do
                (
                    for c = 1 to degree while allSelected do
                    (
                        local tvID = uw.getVertexIndexFromFaceByNode f c node
                        if not tvSel[tvID] do allSelected = false
                    )
                )

                if allSelected do faceSel[f] = true
            )
        )
    )

    faceSel
)

fn UGS_ReadFaces uw node faceSel =
(
    local faces = #()
    local badFaces = #()

    for faceID in faceSel do
    (
        local degree = uw.numberPointsInFaceByNode faceID node

        if degree != 4 then
        (
            append badFaces faceID
        )
        else
        (
            local gv = #()
            local tv = #()
            local uv = #()

            for c = 1 to 4 do
            (
                local g = uw.getVertexGeomIndexFromFaceByNode faceID c node
                local t = uw.getVertexIndexFromFaceByNode faceID c node
                local p = uw.getVertexPositionByNode currentTime t node

                append gv g
                append tv t
                append uv p
            )

            append faces (UGS_FaceData \
                faceID:faceID \
                gv:gv \
                tv:tv \
                uv:uv \
                coords:#(undefined, undefined, undefined, undefined))
        )
    )

    #(faces, badFaces)
)

fn UGS_MakeSeedCoords faceData =
(
    local p1 = faceData.uv[1]
    local p2 = faceData.uv[2]
    local p3 = faceData.uv[3]

    local d = p2 - p1
    local axis = [1.0, 0.0, 0.0]

    if (abs d.x) >= (abs d.y) then
    (
        axis = [if d.x >= 0.0 then 1.0 else -1.0, 0.0, 0.0]
    )
    else
    (
        axis = [0.0, if d.y >= 0.0 then 1.0 else -1.0, 0.0]
    )

    -- 元UVの表裏方向をできるだけ維持する
    local crossZ = d.x * (p3.y - p1.y) - d.y * (p3.x - p1.x)
    local left = [-axis.y, axis.x, 0.0]
    local offsetVec = if crossZ < 0.0 then -left else left

    #(
        [0.0, 0.0, 0.0],
        axis,
        axis + offsetVec,
        offsetVec
    )
)

fn UGS_PredictNeighborCoords currentFace currentSide neighborFace neighborSide =
(
    local c1 = currentSide
    local c2 = UGS_NextCorner c1

    local gA = currentFace.gv[c1]
    local gB = currentFace.gv[c2]
    local pA = currentFace.coords[c1]
    local pB = currentFace.coords[c2]

    local n1 = neighborSide
    local n2 = UGS_NextCorner n1
    local n3 = UGS_CornerAfter n1 2
    local n4 = UGS_CornerAfter n1 3

    local ngA = neighborFace.gv[n1]
    local ngB = neighborFace.gv[n2]

    local qA = undefined
    local qB = undefined

    if (ngA == gA) and (ngB == gB) then
    (
        qA = pA
        qB = pB
    )
    else if (ngA == gB) and (ngB == gA) then
    (
        qA = pB
        qB = pA
    )
    else
    (
        return undefined
    )

    local curCenter = [0.0, 0.0, 0.0]
    for c = 1 to 4 do curCenter += currentFace.coords[c]
    curCenter /= 4.0

    local edgeVec = qB - qA
    local left = [-edgeVec.y, edgeVec.x, 0.0]
    local mid = (qA + qB) * 0.5
    local toCurrent = curCenter - mid
    local sideDot = toCurrent.x * left.x + toCurrent.y * left.y

    -- 隣面は共有エッジの反対側へ置く
    local offsetVec = if sideDot > 0.0 then -left else left

    local result = #(undefined, undefined, undefined, undefined)
    result[n1] = qA
    result[n2] = qB
    result[n3] = qB + offsetVec
    result[n4] = qA + offsetVec

    result
)

fn UGS_BuildLinks faces stitchMode =
(
    local edges = #()
    local links = #()

    for fi = 1 to faces.count do
    (
        if (mod fi 25) == 0 do
            UGS_ShowActivity 18 ("隣接エッジを解析中 " + (fi as string) + "/" + (faces.count as string))

        local f = faces[fi]

        for s = 1 to 4 do
        (
            local s2 = UGS_NextCorner s
            local g1 = f.gv[s]
            local g2 = f.gv[s2]
            local t1 = f.tv[s]
            local t2 = f.tv[s2]

            append edges (UGS_EdgeOcc \
                key:(UGS_EdgeKey g1 g2) \
                faceIndex:fi \
                side:s \
                g1:g1 g2:g2 \
                t1:t1 t2:t2)
        )
    )

    qsort edges UGS_EdgeCompare

    local i = 1
    while i <= edges.count do
    (
        local j = i + 1
        while (j <= edges.count) and (edges[j].key == edges[i].key) do j += 1

        local countOnEdge = j - i

        if countOnEdge == 2 then
        (
            local a = edges[i]
            local b = edges[i + 1]

            local canLink = stitchMode
            if not stitchMode do canLink = UGS_IsUVContinuous a b

            if canLink do
            (
                append links (UGS_LinkData \
                    f1:a.faceIndex s1:a.side \
                    f2:b.faceIndex s2:b.side)
            )
        )
        else if countOnEdge > 2 then
        (
            UGS_Log ("非多様体エッジを検出。接続対象から除外: geom edge " + edges[i].key + \
                     " / selected faces=" + (countOnEdge as string))
        )

        i = j
    )

    links
)


fn UGS_LinkGeomVerts faces link =
(
    local f = faces[link.f1]
    local s1 = link.s1
    local s2 = UGS_NextCorner s1
    #(f.gv[s1], f.gv[s2])
)

fn UGS_LinksShareGeomVertex faces linkA linkB =
(
    local a = UGS_LinkGeomVerts faces linkA
    local b = UGS_LinkGeomVerts faces linkB

    (a[1] == b[1]) or (a[1] == b[2]) or \
    (a[2] == b[1]) or (a[2] == b[2])
)

fn UGS_BuildStitchPlan faces =
(
    local edges = #()

    for fi = 1 to faces.count do
    (
        local f = faces[fi]

        for s = 1 to 4 do
        (
            local s2 = UGS_NextCorner s

            append edges (UGS_EdgeOcc \
                key:(UGS_EdgeKey f.gv[s] f.gv[s2]) \
                faceIndex:fi \
                side:s \
                g1:f.gv[s] g2:f.gv[s2] \
                t1:f.tv[s] t2:f.tv[s2])
        )
    )

    qsort edges UGS_EdgeCompare

    local faceParent = for i = 1 to faces.count collect i
    local seamLinks = #()
    local continuousEdgeCount = 0

    local i = 1
    while i <= edges.count do
    (
        local j = i + 1
        while (j <= edges.count) and (edges[j].key == edges[i].key) do j += 1

        local countOnEdge = j - i

        if countOnEdge == 2 then
        (
            local a = edges[i]
            local b = edges[i + 1]

            if UGS_IsUVContinuous a b then
            (
                UGS_Union faceParent a.faceIndex b.faceIndex
                continuousEdgeCount += 1
            )
            else
            (
                append seamLinks (UGS_LinkData \
                    f1:a.faceIndex s1:a.side \
                    f2:b.faceIndex s2:b.side)
            )
        )
        else if countOnEdge > 2 then
        (
            UGS_Log ("Stitch対象外: 非多様体エッジ " + edges[i].key + \
                     " / selected faces=" + (countOnEdge as string))
        )

        i = j
    )

    local islandRoots = #()
    for fi = 1 to faces.count do
    (
        local r = UGS_FindRoot faceParent fi
        if (findItem islandRoots r) == 0 do append islandRoots r
    )

    local assigned = for i = 1 to seamLinks.count collect false
    local groups = #()

    for start = 1 to seamLinks.count do
    (
        if not assigned[start] do
        (
            local startLink = seamLinks[start]
            local a0 = UGS_FindRoot faceParent startLink.f1
            local b0 = UGS_FindRoot faceParent startLink.f2
            local mn0 = amin a0 b0
            local mx0 = amax a0 b0

            local queue = #(start)
            local qPos = 1
            local chain = #()
            assigned[start] = true

            while qPos <= queue.count do
            (
                local li = queue[qPos]
                qPos += 1
                append chain li

                for other = 1 to seamLinks.count do
                (
                    if not assigned[other] do
                    (
                        local testLink = seamLinks[other]
                        local a1 = UGS_FindRoot faceParent testLink.f1
                        local b1 = UGS_FindRoot faceParent testLink.f2
                        local mn1 = amin a1 b1
                        local mx1 = amax a1 b1

                        if (mn1 == mn0) and (mx1 == mx0) do
                        (
                            local touches = false

                            for existing in chain while not touches do
                            (
                                if UGS_LinksShareGeomVertex faces seamLinks[existing] testLink do
                                    touches = true
                            )

                            if not touches do
                            (
                                for pending in queue while not touches do
                                (
                                    if UGS_LinksShareGeomVertex faces seamLinks[pending] testLink do
                                        touches = true
                                )
                            )

                            if touches do
                            (
                                assigned[other] = true
                                append queue other
                            )
                        )
                    )
                )
            )

            append groups (UGS_SeamGroup \
                islandA:mn0 \
                islandB:mx0 \
                linkIndices:chain)
        )
    )

    local treeParent = for i = 1 to faces.count collect i

    for fi = 1 to faces.count do
    (
        UGS_Union treeParent fi (UGS_FindRoot faceParent fi)
    )

    local acceptedGroups = 0
    local rejectedGroups = 0

    for gi = 1 to groups.count do
    (
        local g = groups[gi]
        local ra = UGS_FindRoot treeParent g.islandA
        local rb = UGS_FindRoot treeParent g.islandB

        if ra != rb then
        (
            g.accepted = true
            UGS_Union treeParent ra rb
            acceptedGroups += 1
        )
        else
        (
            g.accepted = false
            rejectedGroups += 1
        )

        groups[gi] = g
    )

    UGS_Log ("Initial UV islands: " + (islandRoots.count as string)) force:true
    UGS_Log ("Direct stitch candidate edges: " + (seamLinks.count as string)) force:true
    UGS_Log ("Detected seam chains: " + (groups.count as string)) force:true
    UGS_Log ("Stitch chains accepted: " + (acceptedGroups as string)) force:true
    UGS_Log ("Loop seam chains kept: " + (rejectedGroups as string)) force:true

    #(groups, seamLinks)
)

fn UGS_IsCurrentLinkContinuous uw node faces link =
(
    local f1 = faces[link.f1]
    local f2 = faces[link.f2]

    local a1 = link.s1
    local a2 = UGS_NextCorner a1
    local b1 = link.s2
    local b2 = UGS_NextCorner b1

    local g1a = f1.gv[a1]
    local g1b = f1.gv[a2]

    local t1a = uw.getVertexIndexFromFaceByNode f1.faceID a1 node
    local t1b = uw.getVertexIndexFromFaceByNode f1.faceID a2 node
    local t2a = uw.getVertexIndexFromFaceByNode f2.faceID b1 node
    local t2b = uw.getVertexIndexFromFaceByNode f2.faceID b2 node

    if (f2.gv[b1] == g1a) and (f2.gv[b2] == g1b) then
        ((t1a == t2a) and (t1b == t2b))
    else if (f2.gv[b1] == g1b) and (f2.gv[b2] == g1a) then
        ((t1a == t2b) and (t1b == t2a))
    else
        false
)

fn UGS_ForceStitchLink uw node faces link =
(
    /*
        Stitch Customで残ったシームを、3D頂点対応を使って確実に接続する。
        face2側のTV頂点参照をface1側のTV頂点へ置き換える。

        この処理は「近いUVを溶接」ではなく、
        同じ3Dエッジの対応頂点だけを接続する。
    */

    local f1 = faces[link.f1]
    local f2 = faces[link.f2]

    local a1 = link.s1
    local a2 = UGS_NextCorner a1
    local b1 = link.s2
    local b2 = UGS_NextCorner b1

    local ga1 = f1.gv[a1]
    local ga2 = f1.gv[a2]
    local gb1 = f2.gv[b1]
    local gb2 = f2.gv[b2]

    local ta1 = uw.getVertexIndexFromFaceByNode f1.faceID a1 node
    local ta2 = uw.getVertexIndexFromFaceByNode f1.faceID a2 node

    local changed = 0

    if (gb1 == ga1) and (gb2 == ga2) then
    (
        local tb1 = uw.getVertexIndexFromFaceByNode f2.faceID b1 node
        local tb2 = uw.getVertexIndexFromFaceByNode f2.faceID b2 node

        if tb1 != ta1 do
        (
            uw.setFaceVertexIndexByNode f2.faceID b1 ta1 node
            changed += 1
        )

        if tb2 != ta2 do
        (
            uw.setFaceVertexIndexByNode f2.faceID b2 ta2 node
            changed += 1
        )
    )
    else if (gb1 == ga2) and (gb2 == ga1) then
    (
        local tb1 = uw.getVertexIndexFromFaceByNode f2.faceID b1 node
        local tb2 = uw.getVertexIndexFromFaceByNode f2.faceID b2 node

        if tb1 != ta2 do
        (
            uw.setFaceVertexIndexByNode f2.faceID b1 ta2 node
            changed += 1
        )

        if tb2 != ta1 do
        (
            uw.setFaceVertexIndexByNode f2.faceID b2 ta1 node
            changed += 1
        )
    )
    else
    (
        UGS_Log ("Force Stitch failed: geometry edge mismatch / face " + \
                 (f1.faceID as string) + " <-> " + (f2.faceID as string)) force:true
    )

    changed
)

fn UGS_ForceStitchGroup uw node faces seamLinks seamGroup =
(
    local changedCorners = 0

    for li in seamGroup.linkIndices do
    (
        local link = seamLinks[li]

        if not (UGS_IsCurrentLinkContinuous uw node faces link) do
        (
            changedCorners += UGS_ForceStitchLink uw node faces link
        )
    )

    try(uw.updateView())catch()

    local okCount = 0
    for li in seamGroup.linkIndices do
    (
        if UGS_IsCurrentLinkContinuous uw node faces seamLinks[li] do
            okCount += 1
    )

    UGS_Log ("Force Stitch result: welded edges=" + (okCount as string) + \
             "/" + (seamGroup.linkIndices.count as string) + \
             " / remapped corners=" + (changedCorners as string)) force:true

    okCount
)

fn UGS_StitchGroupCustom uw node faces seamLinks seamGroup =
(
    local tvSel = #{}

    for li in seamGroup.linkIndices do
    (
        local link = seamLinks[li]
        local f1 = faces[link.f1]
        local f2 = faces[link.f2]

        local a1 = link.s1
        local a2 = UGS_NextCorner a1
        local b1 = link.s2
        local b2 = UGS_NextCorner b1

        tvSel[uw.getVertexIndexFromFaceByNode f1.faceID a1 node] = true
        tvSel[uw.getVertexIndexFromFaceByNode f1.faceID a2 node] = true
        tvSel[uw.getVertexIndexFromFaceByNode f2.faceID b1 node] = true
        tvSel[uw.getVertexIndexFromFaceByNode f2.faceID b2 node] = true
    )

    UGS_Log ("Stitch Custom: selected TV verts=" + (tvSel.numberSet as string) + \
             " / seam edges=" + (seamGroup.linkIndices.count as string)) force:true

    local standardStitchOK = true

    try
    (
        uw.selectVerticesByNode tvSel node

        -- 3ds Max標準 Stitch Custom相当
        -- Align Clusters = ON / Bias = 0.5
        uw.stitchVerts true 0.5
        uw.updateView()
    )
    catch
    (
        standardStitchOK = false
        UGS_Log ("標準 Stitch Custom が失敗したため直接接続へ切替: " + \
                 (getCurrentException() as string)) force:true
    )

    local standardOKCount = 0

    if standardStitchOK do
    (
        for li in seamGroup.linkIndices do
        (
            if UGS_IsCurrentLinkContinuous uw node faces seamLinks[li] do
                standardOKCount += 1
        )
    )

    UGS_Log ("Standard Stitch result: welded edges=" + \
             (standardOKCount as string) + "/" + \
             (seamGroup.linkIndices.count as string)) force:true

    -- 標準Stitchで残った部分は、3D頂点対応で直接TV参照を統合する。
    local finalOKCount = standardOKCount

    if standardOKCount < seamGroup.linkIndices.count then
    (
        UGS_Log "Remaining seam edges are being force-stitched." force:true
        finalOKCount = UGS_ForceStitchGroup uw node faces seamLinks seamGroup
    )

    finalOKCount
)

fn UGS_StitchSelectedCustom uw node faces faceSel =
(
    local plan = UGS_BuildStitchPlan faces
    local groups = plan[1]
    local seamLinks = plan[2]

    local acceptedCount = 0
    local weldedEdgeCount = 0
    local originalTVMode = undefined

    -- StitchはVertexモードで実行する。
    -- ModifyパネルのCurrent Objectは変更しないのでUV Editorは閉じない。
    try
    (
        originalTVMode = uw.getTVSubObjectMode()
        uw.setTVSubObjectMode 1
        UGS_Log ("TV subobject mode: " + (originalTVMode as string) + " -> 1") force:true
    )
    catch
    (
        UGS_Log ("TV subobject mode変更をスキップ: " + \
                 (getCurrentException() as string)) force:true
    )

    for gi = 1 to groups.count do
    (
        UGS_ShowLoopActivity 42 15 gi groups.count \
            ("Stitch処理中 " + (gi as string) + "/" + (groups.count as string))

        local g = groups[gi]

        if g.accepted then
        (
            acceptedCount += 1

            UGS_Log ("Stitch chain " + (gi as string) + \
                     ": island " + (g.islandA as string) + \
                     " <-> " + (g.islandB as string) + \
                     " / edges=" + (g.linkIndices.count as string)) force:true

            weldedEdgeCount += UGS_StitchGroupCustom uw node faces seamLinks g
        )
        else
        (
            UGS_Log ("Loop seam preserved: chain " + (gi as string) + \
                     " / edges=" + (g.linkIndices.count as string)) force:true
        )
    )

    -- 元のサブオブジェクトモードへ戻す
    if originalTVMode != undefined do
    (
        try(uw.setTVSubObjectMode originalTVMode)catch()
    )

    -- 元のFace選択へ戻す
    try(uw.selectFacesByNode faceSel node)catch()
    try(uw.updateView())catch()

    UGS_Log ("Auto Stitch finished: chains=" + (acceptedCount as string) + \
             " / welded edges=" + (weldedEdgeCount as string) + \
             " / candidates=" + (seamLinks.count as string)) force:true

    #(acceptedCount, weldedEdgeCount, seamLinks.count)
)

fn UGS_BuildComponents faces links =
(
    local adjacency = for i = 1 to faces.count collect #()

    for li = 1 to links.count do
    (
        append adjacency[links[li].f1] li
        append adjacency[links[li].f2] li
    )

    local components = #()
    local componentID = 0

    for startFace = 1 to faces.count do
    (
        if not faces[startFace].assigned do
        (
            componentID += 1

            local seed = faces[startFace]
            seed.coords = UGS_MakeSeedCoords seed
            seed.assigned = true
            seed.componentID = componentID
            faces[startFace] = seed

            local queue = #(startFace)
            local qPos = 1
            local compFaces = #()
            local compLinks = #()

            while qPos <= queue.count do
            (
                if (mod qPos 20) == 0 do
                    UGS_ShowActivity 28 ("UV要素を追跡中 " + (qPos as string) + "/" + (queue.count as string))

                local fi = queue[qPos]
                qPos += 1
                append compFaces fi

                local curFace = faces[fi]

                for li in adjacency[fi] do
                (
                    if (findItem compLinks li) == 0 do append compLinks li

                    local link = links[li]
                    local other = 0
                    local curSide = 0
                    local otherSide = 0

                    if link.f1 == fi then
                    (
                        other = link.f2
                        curSide = link.s1
                        otherSide = link.s2
                    )
                    else
                    (
                        other = link.f1
                        curSide = link.s2
                        otherSide = link.s1
                    )

                    local otherFace = faces[other]
                    local predicted = UGS_PredictNeighborCoords curFace curSide otherFace otherSide

                    if predicted == undefined then
                    (
                        link.accepted = false
                        links[li] = link
                        UGS_Log ("共有エッジ対応を取得できず接続をスキップ: face " + \
                                 (curFace.faceID as string) + " <-> " + (otherFace.faceID as string))
                    )
                    else if not otherFace.assigned then
                    (
                        otherFace.coords = predicted
                        otherFace.assigned = true
                        otherFace.componentID = componentID
                        faces[other] = otherFace

                        link.accepted = true
                        links[li] = link

                        append queue other
                    )
                    else
                    (
                        if otherFace.componentID == componentID then
                        (
                            if UGS_CoordsEqual otherFace.coords predicted then
                            (
                                link.accepted = true
                                links[li] = link
                            )
                            else
                            (
                                -- 閉じた円筒など、全部繋ぐと平面化できないエッジ
                                link.accepted = false
                                links[li] = link

                                UGS_Log ("グリッド矛盾を検出。ここはシームとして残します: face " + \
                                         (curFace.faceID as string) + " <-> " + \
                                         (otherFace.faceID as string))
                            )
                        )
                    )
                )
            )

            append components (UGS_ComponentData \
                id:componentID \
                faceIndices:compFaces \
                linkIndices:compLinks)
        )
    )

    components
)

fn UGS_ValidateComponent comp faces =
(
    /*
        「完成形が長方形か」では判定しない。

        扇形・曲がった帯などは、トポロジー上は問題なく四角グリッドへ
        直せても、探索途中の仮グリッドでは 14x8 の矩形を完全には
        埋めないことがあるため。

        ここでは以下だけをNGとする。
          1. 同じグリッドセルに複数Faceが重なる
          2. 同じTV頂点に別々のグリッド座標が必要になる

        これにより、以前処理できていた曲がった帯は通し、
        放射状・Pole・分岐など矛盾する要素だけをスキップする。
    */

    local cellKeys = #()

    for fi in comp.faceIndices do
    (
        local f = faces[fi]

        local minX = 1e9
        local minY = 1e9
        local maxX = -1e9
        local maxY = -1e9

        for c = 1 to 4 do
        (
            minX = amin minX f.coords[c].x
            minY = amin minY f.coords[c].y
            maxX = amax maxX f.coords[c].x
            maxY = amax maxY f.coords[c].y
        )

        local cellW = abs (maxX - minX)
        local cellH = abs (maxY - minY)

        if ((abs (cellW - 1.0)) > 0.0001) or ((abs (cellH - 1.0)) > 0.0001) then
        (
            comp.valid = false
            comp.reason = "四角グリッドの1セルとして成立しない要素です。"
            return comp
        )

        local key = ((UGS_RoundInt minX) as string) + ":" + \
                    ((UGS_RoundInt minY) as string)

        if (findItem cellKeys key) != 0 then
        (
            comp.valid = false
            comp.reason = "放射状・分岐・ループ等によりグリッドセルが重なる要素です。"
            return comp
        )

        append cellKeys key
    )

    -- 同一TV頂点に複数のグリッド座標を要求する場合もNG
    local tvIDs = #()
    local tvCoords = #()

    for fi in comp.faceIndices do
    (
        local f = faces[fi]

        for c = 1 to 4 do
        (
            local id = f.tv[c]
            local hit = findItem tvIDs id

            if hit == 0 then
            (
                append tvIDs id
                append tvCoords f.coords[c]
            )
            else
            (
                if not (UGS_PointEqual2D tvCoords[hit] f.coords[c]) then
                (
                    comp.valid = false
                    comp.reason = "同一TV頂点に複数のグリッド座標が必要な要素です。"
                    return comp
                )
            )
        )
    )

    comp
)

fn UGS_FindRoot parent x =
(
    local r = x
    while parent[r] != r do r = parent[r]
    r
)

fn UGS_Union parent a b =
(
    local ra = UGS_FindRoot parent a
    local rb = UGS_FindRoot parent b
    if ra != rb do parent[rb] = ra
)

fn UGS_GetComponentPlacement comp faces scaleMul =
(
    local originalCenter = [0.0, 0.0, 0.0]
    local sampleCount = 0

    local gridMinX = 1e9
    local gridMinY = 1e9
    local gridMaxX = -1e9
    local gridMaxY = -1e9

    local edgeLenSum = 0.0
    local edgeLenCount = 0

    for fi in comp.faceIndices do
    (
        local f = faces[fi]

        for c = 1 to 4 do
        (
            originalCenter += f.uv[c]
            sampleCount += 1

            gridMinX = amin gridMinX f.coords[c].x
            gridMinY = amin gridMinY f.coords[c].y
            gridMaxX = amax gridMaxX f.coords[c].x
            gridMaxY = amax gridMaxY f.coords[c].y

            local c2 = UGS_NextCorner c
            local len = distance f.uv[c] f.uv[c2]
            if len > 0.000001 do
            (
                edgeLenSum += len
                edgeLenCount += 1
            )
        )
    )

    if sampleCount > 0 do originalCenter /= sampleCount as float

    local cellSize = 0.01
    if edgeLenCount > 0 then
        cellSize = (edgeLenSum / edgeLenCount as float) * scaleMul

    if cellSize < 0.000001 do cellSize = 0.01 * scaleMul

    local gridCenter = [(gridMinX + gridMaxX) * 0.5, (gridMinY + gridMaxY) * 0.5, 0.0]

    #(originalCenter, gridCenter, cellSize)
)

fn UGS_GridToUV gridCoord placement =
(
    local originalCenter = placement[1]
    local gridCenter = placement[2]
    local cellSize = placement[3]

    [originalCenter.x + (gridCoord.x - gridCenter.x) * cellSize, originalCenter.y + (gridCoord.y - gridCenter.y) * cellSize, originalCenter.z]
)


fn UGS_AutoConnectCoincidentSeams uw node faceSel tolerance:0.0001 skipLoop:true =
(
    /*
        v1.5:
        グリッド化後などで「見た目上すでに同じ位置に重なっているUVシーム」だけを接続する。

        条件:
          - 選択Face同士が同じ3Dエッジを共有
          - UV上ではまだ別TV頂点
          - 共有エッジ両端のUV座標が一致

        接続:
          Unwrap UVW 標準の WeldSelectedShared() を使用。
          UV位置は移動しない。

        v1.6:
          skipLoop:true (既定) の場合、接続しようとしている2面が
          既に同じUVアイランド（連続したUV領域）であれば、
          それを繋ぐとループになるため接続をスキップする。
    */

    if faceSel.numberSet == 0 then return #(0, 0, 0, 0)

    UGS_ShowActivity 96 "重なったUVシームを自動接続中"
    UGS_Log ("Auto-connect coincident seams: scan start / skipLoop=" + (skipLoop as string)) force:true

    -- ループ判定用: 各Faceを最初は独立したアイランドとして扱い、
    -- 「このパスで実際に接続した候補同士」だけをUnion-Findで束ねていく。
    --
    -- v1.6の以前の実装では、候補以外の「既存の連続UVエッジ」も使って
    -- 最初からアイランドを構築していたため、閉じた球・筒のように
    -- 一部にシームが残っていても他の経路で全体がひと繋がりになっている
    -- 形状では、どの候補も「開始時点で既に同じアイランド」と判定されて
    -- 1件も接続できなくなっていた。
    --
    -- このAuto-Connectは接続前にUV座標の完全一致を確認済みで、かつ
    -- 座標を一切動かさないため、候補同士を繋ぐこと自体が平面展開を
    -- 壊すことはない。本当に避けたいのは「このパスの候補だけを繋いだ
    -- 結果、候補だけでループが閉じてしまう」場合だけなので、
    -- 判定基準をそちらに絞る。
    local islandFaceParent = #()
    local idxByFaceID = #()
    local loopSkippedEdges = 0

    if skipLoop do
    (
        try
        (
            local islandRead = UGS_ReadFaces uw node faceSel
            local islandFaces = islandRead[1]

            islandFaceParent = for i = 1 to islandFaces.count collect i
            for i = 1 to islandFaces.count do idxByFaceID[islandFaces[i].faceID] = i

            UGS_Log ("Auto-connect: loop-check islands built (" + \
                     (islandFaces.count as string) + " faces, candidate-only basis)") force:true
        )
        catch
        (
            UGS_Log ("Auto-connect: loop-check island構築に失敗。ループ判定をスキップします: " + \
                     (getCurrentException() as string)) force:true
            skipLoop = false
        )
    )

    local edges = #()

    for faceID in faceSel do
    (
        local degree = uw.numberPointsInFaceByNode faceID node

        if degree >= 2 do
        (
            for c = 1 to degree do
            (
                local c2 = if c < degree then c + 1 else 1
                local g1 = uw.getVertexGeomIndexFromFaceByNode faceID c node
                local g2 = uw.getVertexGeomIndexFromFaceByNode faceID c2 node
                local t1 = uw.getVertexIndexFromFaceByNode faceID c node
                local t2 = uw.getVertexIndexFromFaceByNode faceID c2 node

                append edges (UGS_EdgeOcc \
                    key:(UGS_EdgeKey g1 g2) \
                    faceIndex:faceID \
                    side:c \
                    g1:g1 g2:g2 \
                    t1:t1 t2:t2)
            )
        )
    )

    qsort edges UGS_EdgeCompare

    -- face/cornerの組だけ保持する。
    -- Weld後にTV indexが変わっても、その都度Faceから再取得できる。
    local candidatePairs = #()

    local i = 1
    while i <= edges.count do
    (
        local j = i + 1

        while (j <= edges.count) and (edges[j].key == edges[i].key) do
            j += 1

        if (j - i) == 2 then
        (
            local a = edges[i]
            local b = edges[i + 1]

            if not (UGS_IsUVContinuous a b) do
                append candidatePairs #(a, b)
        )

        i = j
    )

    local candidateEdges = candidatePairs.count
    local coincidentEdges = 0
    local connectedEdges = 0
    local failedEdges = 0

    local originalTVMode = undefined

    try
    (
        originalTVMode = uw.getTVSubObjectMode()
        uw.setTVSubObjectMode 1
    )
    catch
    (
        UGS_Log ("Auto-connect: Vertexモード切替をスキップ: " + \
                 (getCurrentException() as string)) force:true
    )

    local pairIndex = 0

    for pair in candidatePairs do
    (
        pairIndex += 1

        if (mod pairIndex 20) == 0 do
            UGS_ShowLoopActivity 96 3 pairIndex candidatePairs.count \
                ("重なったシームを接続中 " + \
                 (pairIndex as string) + "/" + \
                 (candidatePairs.count as string))

        local a = pair[1]
        local b = pair[2]

        local degreeA = uw.numberPointsInFaceByNode a.faceIndex node
        local degreeB = uw.numberPointsInFaceByNode b.faceIndex node

        local a2 = if a.side < degreeA then a.side + 1 else 1
        local b2 = if b.side < degreeB then b.side + 1 else 1

        -- 必ず現在のFace参照からTV indexを取り直す
        local ta1 = uw.getVertexIndexFromFaceByNode a.faceIndex a.side node
        local ta2 = uw.getVertexIndexFromFaceByNode a.faceIndex a2 node
        local tb1 = uw.getVertexIndexFromFaceByNode b.faceIndex b.side node
        local tb2 = uw.getVertexIndexFromFaceByNode b.faceIndex b2 node

        local alreadyConnected = \
            ((ta1 == tb1) and (ta2 == tb2)) or \
            ((ta1 == tb2) and (ta2 == tb1))

        if not alreadyConnected do
        (
            local pa1 = uw.getVertexPositionByNode currentTime ta1 node
            local pa2 = uw.getVertexPositionByNode currentTime ta2 node
            local pb1 = uw.getVertexPositionByNode currentTime tb1 node
            local pb2 = uw.getVertexPositionByNode currentTime tb2 node

            local same1 = false
            local same2 = false

            if (a.g1 == b.g1) and (a.g2 == b.g2) then
            (
                same1 = UGS_PointEqual2D pa1 pb1 tol:tolerance
                same2 = UGS_PointEqual2D pa2 pb2 tol:tolerance
            )
            else if (a.g1 == b.g2) and (a.g2 == b.g1) then
            (
                same1 = UGS_PointEqual2D pa1 pb2 tol:tolerance
                same2 = UGS_PointEqual2D pa2 pb1 tol:tolerance
            )

            if same1 and same2 do
            (
                coincidentEdges += 1

                local skipThisEdge = false

                if skipLoop do
                (
                    local idxA = idxByFaceID[a.faceIndex]
                    local idxB = idxByFaceID[b.faceIndex]

                    if idxA != undefined and idxB != undefined then
                    (
                        local rootA = UGS_FindRoot islandFaceParent idxA
                        local rootB = UGS_FindRoot islandFaceParent idxB

                        if rootA == rootB then
                        (
                            skipThisEdge = true
                            loopSkippedEdges += 1
                            UGS_Log ("Auto-connect: ループになるため接続をスキップ: face " + \
                                     (a.faceIndex as string) + " <-> " + \
                                     (b.faceIndex as string))
                        )
                        else
                        (
                            UGS_Union islandFaceParent rootA rootB
                        )
                    )
                )

                if not skipThisEdge do
                (
                local tvSel = #{}
                tvSel[ta1] = true
                tvSel[ta2] = true
                tvSel[tb1] = true
                tvSel[tb2] = true

                local weldOK = true

                try
                (
                    uw.selectVerticesByNode tvSel node
                    uw.WeldSelectedShared()
                )
                catch
                (
                    weldOK = false
                    failedEdges += 1

                    UGS_Log ("Auto-connect WeldSelectedShared failed: face " + \
                             (a.faceIndex as string) + " <-> " + \
                             (b.faceIndex as string) + " / " + \
                             (getCurrentException() as string)) force:true
                )

                if weldOK do
                (
                    -- Weld後に再取得して本当に同じTV edgeになったか確認
                    ta1 = uw.getVertexIndexFromFaceByNode a.faceIndex a.side node
                    ta2 = uw.getVertexIndexFromFaceByNode a.faceIndex a2 node
                    tb1 = uw.getVertexIndexFromFaceByNode b.faceIndex b.side node
                    tb2 = uw.getVertexIndexFromFaceByNode b.faceIndex b2 node

                    local nowConnected = \
                        ((ta1 == tb1) and (ta2 == tb2)) or \
                        ((ta1 == tb2) and (ta2 == tb1))

                    if nowConnected then
                        connectedEdges += 1
                    else
                        failedEdges += 1
                )
                ) -- end if not skipThisEdge
            )
        )
    )

    if originalTVMode != undefined do
    (
        try(uw.setTVSubObjectMode originalTVMode)catch()
    )

    try(uw.selectFacesByNode faceSel node)catch()
    try(uw.updateView())catch()

    UGS_Log ("Auto-connect coincident seams: candidates=" + \
             (candidateEdges as string) + \
             " / coincident=" + (coincidentEdges as string) + \
             " / connected=" + (connectedEdges as string) + \
             " / loop-skipped=" + (loopSkippedEdges as string) + \
             " / failed=" + (failedEdges as string)) force:true

    #(candidateEdges, connectedEdges, failedEdges, loopSkippedEdges)
)

fn UGS_Run stitchMode:false scaleMul:1.0 debugMode:true autoConnect:true skipLoopConnect:true =
(
    UGS_DebugEnabled = debugMode
    UGS_ResetLog()
    UGS_LastStatus = ""

    UGS_Log "===== UV Grid Straightener v1.6 START =====" force:true
    UGS_Log ("Time: " + (localTime as string)) force:true
    try(UGS_Log ("3ds Max version: " + ((maxVersion()) as string)) force:true)catch()

    if selection.count != 1 then
    (
        UGS_LastStatus = "オブジェクトを1つだけ選択してください。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    local node = selection[1]
    local uw = UGS_FindUnwrap node

    if uw == undefined then
    (
        UGS_LastStatus = "選択オブジェクトに Unwrap UVW が見つかりません。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    UGS_Log ("Node: " + node.name) force:true
    UGS_Log ("Unwrap modifier: " + uw.name) force:true
    UGS_Log ("Stitch mode: " + (stitchMode as string)) force:true
    UGS_Log ("Cell scale: " + (scaleMul as string)) force:true
    UGS_Log ("Auto-connect after processing: " + (autoConnect as string)) force:true

    local faceSel = UGS_GetFaceSelection uw node

    if faceSel.numberSet == 0 then
    (
        UGS_LastStatus = "UVエディタで処理対象の Face を選択してください。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    UGS_Log ("Selected faces: " + (faceSel.numberSet as string)) force:true
    UGS_ShowActivity 5 "選択UVを読み取り中"

    local readResult = undefined

    try
    (
        readResult = UGS_ReadFaces uw node faceSel
    )
    catch
    (
        UGS_LastStatus = "UV情報の読み取り中にエラーが発生しました。"
        UGS_Log (UGS_LastStatus + " / " + (getCurrentException() as string)) force:true
        messageBox (UGS_LastStatus + "\nログを確認してください。") title:"UV Grid Straightener"
        return false
    )

    local faces = readResult[1]
    local badFaces = readResult[2]

    if badFaces.count > 0 do
    (
        UGS_Log ("Non-Quad faces skipped: " + (badFaces.count as string)) force:true
        UGS_Log ("Non-Quad face IDs: " + (badFaces as string)) force:true
    )

    if faces.count == 0 then
    (
        UGS_LastStatus = "選択範囲に処理可能なQuad面がありません。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    -- --------------------------------------------------------
    -- まず現在のUVアイランド単位で「四角グリッド化可能か」を判定する。
    -- ここで円形・分岐・穴あき等を除外し、残った要素だけ処理する。
    -- --------------------------------------------------------
    UGS_ShowActivity 12 "UVアイランドを解析中"

    local initialLinks = #()
    local initialComponents = #()

    try
    (
        initialLinks = UGS_BuildLinks faces false
        initialComponents = UGS_BuildComponents faces initialLinks
    )
    catch
    (
        UGS_LastStatus = "初期UV要素の解析中にエラーが発生しました。"
        UGS_Log (UGS_LastStatus + " / " + (getCurrentException() as string)) force:true
        messageBox (UGS_LastStatus + "\nログを確認してください。") title:"UV Grid Straightener"
        return false
    )

    UGS_Log ("Initial UV components: " + (initialComponents.count as string)) force:true
    UGS_ShowActivity 30 "処理可能な要素を判定中"

    local candidateFaceSel = #{}
    local initialValidCount = 0
    local initialSkippedCount = 0

    for ci = 1 to initialComponents.count do
    (
        UGS_ShowLoopActivity 30 10 ci initialComponents.count ("要素を判定中 " + (ci as string) + "/" + (initialComponents.count as string))
        local comp = UGS_ValidateComponent initialComponents[ci] faces
        initialComponents[ci] = comp

        if comp.valid then
        (
            initialValidCount += 1

            for fi in comp.faceIndices do
                candidateFaceSel[faces[fi].faceID] = true

            UGS_Log ("Initial component " + (comp.id as string) + \
                     ": TARGET / faces=" + (comp.faceIndices.count as string)) force:true
        )
        else
        (
            initialSkippedCount += 1
            UGS_Log ("Initial component " + (comp.id as string) + \
                     ": IGNORE / " + comp.reason) force:true
        )
    )

    UGS_Log ("Grid-able components: " + (initialValidCount as string)) force:true
    UGS_Log ("Ignored components: " + (initialSkippedCount as string)) force:true

    if candidateFaceSel.numberSet == 0 then
    (
        UGS_LastStatus = "四角グリッド化可能なUV要素がありませんでした。"
        UGS_Log UGS_LastStatus force:true
        messageBox (UGS_LastStatus + "\n丸形・分岐形状などは自動的に無視されます。") title:"UV Grid Straightener"
        return false
    )

    -- 候補面だけ読み直す。
    readResult = UGS_ReadFaces uw node candidateFaceSel
    faces = readResult[1]

    -- --------------------------------------------------------
    -- v1.1:
    -- グリッド化とStitchは完全に分離。
    -- この処理ではUVトポロジーを接続しない。
    -- 現在のUVシームをそのまま維持してグリッド化する。
    -- --------------------------------------------------------
    UGS_ShowActivity 58 "グリッド化対象を準備中"

    -- 現在のUV接続状態を再解析
    UGS_ShowActivity 64 "最終トポロジーを解析中"

    local links = #()
    local components = #()

    try
    (
        links = UGS_BuildLinks faces false
        components = UGS_BuildComponents faces links
    )
    catch
    (
        UGS_LastStatus = "トポロジー解析中にエラーが発生しました。"
        UGS_Log (UGS_LastStatus + " / " + (getCurrentException() as string)) force:true
        try(uw.selectFacesByNode faceSel node)catch()
        messageBox (UGS_LastStatus + "\nログを確認してください。") title:"UV Grid Straightener"
        return false
    )

    UGS_Log ("Adjacency links: " + (links.count as string)) force:true
    UGS_Log ("Components: " + (components.count as string)) force:true

    local validCount = 0
    local skippedCount = 0

    UGS_ShowActivity 72 "最終チェック中"

    for ci = 1 to components.count do
    (
        UGS_ShowLoopActivity 72 8 ci components.count ("最終チェック中 " + (ci as string) + "/" + (components.count as string))
        local comp = UGS_ValidateComponent components[ci] faces
        components[ci] = comp

        if comp.valid then
        (
            validCount += 1
            UGS_Log ("Final component " + (comp.id as string) + \
                     ": OK / faces=" + (comp.faceIndices.count as string)) force:true
        )
        else
        (
            skippedCount += 1
            UGS_Log ("Final component " + (comp.id as string) + \
                     ": SKIP / " + comp.reason) force:true
        )
    )

    if validCount == 0 then
    (
        UGS_LastStatus = "四角グリッド化できる要素がありませんでした。"
        UGS_Log UGS_LastStatus force:true
        try(uw.selectFacesByNode faceSel node)catch()
        messageBox (UGS_LastStatus + "\nログを確認してください。") title:"UV Grid Straightener"
        return false
    )

    try
    (
        undo "UV Grid Straightener" on
        (
            UGS_ShowActivity 82 "UV座標を書き換え中"
            local totalGridVertices = 0
            local writeCompIndex = 0

            for comp in components where comp.valid do
            (
                writeCompIndex += 1
                UGS_ShowLoopActivity 82 16 writeCompIndex validCount ("UVを整列中 " + (writeCompIndex as string) + "/" + (validCount as string))

                local placement = UGS_GetComponentPlacement comp faces scaleMul
                local writtenTVs = #()

                for fi in comp.faceIndices do
                (
                    local f = faces[fi]

                    for c = 1 to 4 do
                    (
                        local tvID = f.tv[c]

                        if (findItem writtenTVs tvID) == 0 do
                        (
                            local newPos = UGS_GridToUV f.coords[c] placement
                            uw.setVertexPositionByNode currentTime tvID newPos node
                            append writtenTVs tvID
                        )
                    )
                )

                totalGridVertices += writtenTVs.count

                UGS_Log ("Component " + (comp.id as string) + \
                         ": grid vertices=" + (writtenTVs.count as string))
            )

            UGS_Log ("Total grid vertices: " + (totalGridVertices as string)) force:true

            if autoConnect do
            (
                try
                (
                    UGS_AutoConnectCoincidentSeams uw node faceSel skipLoop:skipLoopConnect
                )
                catch
                (
                    UGS_Log ("警告: グリッド化は完了しましたが、自動接続処理をスキップしました: " + \
                             (getCurrentException() as string)) force:true
                )
            )

            -- 実行前のFace選択へ戻す。
            -- UV Editor自体の表示状態には触れない。
            try(uw.selectFacesByNode faceSel node)catch()

            uw.updateView()
            redrawViews()
        )
    )
    catch
    (
        UGS_LastStatus = "UV書き換え中にエラーが発生しました。Undoしてからログを確認してください。"
        UGS_Log (UGS_LastStatus + " / " + (getCurrentException() as string)) force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    local processedFaces = 0
    for comp in components where comp.valid do processedFaces += comp.faceIndices.count

    UGS_LastStatus = ("完了: " + (processedFaces as string) + " faces / " + \
                      (validCount as string) + " element(s)")

    local totalIgnored = initialSkippedCount + skippedCount
    if badFaces.count > 0 do totalIgnored += 1

    if totalIgnored > 0 do
        UGS_LastStatus += (" / ignored " + (totalIgnored as string))

    UGS_ShowActivity 100 "完了"
    UGS_Log UGS_LastStatus force:true
    UGS_Log "===== UV Grid Straightener v1.6 END =====" force:true

    true
)



fn UGS_NextCornerN c degree =
(
    if c < degree then c + 1 else 1
)

fn UGS_GlobalLinksShareGeomVertex linkA linkB =
(
    (linkA.g1 == linkB.g1) or (linkA.g1 == linkB.g2) or \
    (linkA.g2 == linkB.g1) or (linkA.g2 == linkB.g2)
)

fn UGS_IsFaceEdgeContinuousNow uw node faceA cornerA faceB cornerB =
(
    local degreeA = uw.numberPointsInFaceByNode faceA node
    local degreeB = uw.numberPointsInFaceByNode faceB node

    if (degreeA < 2) or (degreeB < 2) then return false

    local cornerA2 = UGS_NextCornerN cornerA degreeA
    local cornerB2 = UGS_NextCornerN cornerB degreeB

    local ta1 = uw.getVertexIndexFromFaceByNode faceA cornerA node
    local ta2 = uw.getVertexIndexFromFaceByNode faceA cornerA2 node
    local tb1 = uw.getVertexIndexFromFaceByNode faceB cornerB node
    local tb2 = uw.getVertexIndexFromFaceByNode faceB cornerB2 node

    ((ta1 == tb1) and (ta2 == tb2)) or \
    ((ta1 == tb2) and (ta2 == tb1))
)

fn UGS_BuildGlobalStitchPlan uw node faceSel gridOnly =
(
    /*
        v1.2:
        「選択Face同士の内部」だけを見るのではなく、
        オブジェクト全Faceの共有3Dエッジを調べる。

        候補条件:
          - 共有3Dエッジである
          - UV上では切れている
          - そのエッジの少なくとも片側Faceがユーザー選択
          - 現在のUVアイランドが別

        これにより、選択したUVアイランドの外周から、
        隣の未選択UVアイランドへ Stitch できる。
    */

    local numFaces = uw.numberPolygonsByNode node
    local edges = #()

    UGS_ShowActivity 12 "全Faceの共有エッジを取得中"

    for faceID = 1 to numFaces do
    (
        if (mod faceID 100) == 0 do
            UGS_ShowLoopActivity 12 18 faceID numFaces \
                ("共有エッジを取得中 " + (faceID as string) + "/" + (numFaces as string))

        local degree = uw.numberPointsInFaceByNode faceID node

        if degree >= 2 do
        (
            for c = 1 to degree do
            (
                local c2 = UGS_NextCornerN c degree
                local g1 = uw.getVertexGeomIndexFromFaceByNode faceID c node
                local g2 = uw.getVertexGeomIndexFromFaceByNode faceID c2 node
                local t1 = uw.getVertexIndexFromFaceByNode faceID c node
                local t2 = uw.getVertexIndexFromFaceByNode faceID c2 node

                append edges (UGS_EdgeOcc \
                    key:(UGS_EdgeKey g1 g2) \
                    faceIndex:faceID \
                    side:c \
                    g1:g1 g2:g2 \
                    t1:t1 t2:t2)
            )
        )
    )

    qsort edges UGS_EdgeCompare

    local faceParent = for i = 1 to numFaces collect i
    local rawSeams = #()
    local sharedGeomEdges = 0
    local continuousUVEdges = 0
    local nonManifoldEdges = 0

    UGS_ShowActivity 32 "UVアイランドとシームを解析中"

    local i = 1
    while i <= edges.count do
    (
        if (mod i 500) == 0 do
            UGS_ShowActivity 32 ("UVシームを解析中 " + (i as string) + "/" + (edges.count as string))

        local j = i + 1
        while (j <= edges.count) and (edges[j].key == edges[i].key) do j += 1

        local countOnEdge = j - i

        if countOnEdge == 2 then
        (
            sharedGeomEdges += 1

            local a = edges[i]
            local b = edges[i + 1]

            if UGS_IsUVContinuous a b then
            (
                UGS_Union faceParent a.faceIndex b.faceIndex
                continuousUVEdges += 1
            )
            else
            (
                -- まずraw seamとして保持。UV island IDはUnion完了後に入れる。
                append rawSeams #(a, b)
            )
        )
        else if countOnEdge > 2 then
        (
            nonManifoldEdges += 1
        )

        i = j
    )

    local islandRoots = #()
    for faceID = 1 to numFaces do
    (
        local r = UGS_FindRoot faceParent faceID
        if (findItem islandRoots r) == 0 do append islandRoots r
    )

    -- gridOnly=true の場合に使用する「グリッド化可能UVアイランド」一覧
    local gridableIslandRoots = #()
    local nongridIslandRoots = #()

    if gridOnly do
    (
        UGS_ShowActivity 43 "UVアイランドのグリッド可否を判定中"

        for islandRoot in islandRoots do
        (
            local islandFaceSel = #{}

            for faceID = 1 to numFaces do
            (
                if (UGS_FindRoot faceParent faceID) == islandRoot do
                    islandFaceSel[faceID] = true
            )

            local islandRead = UGS_ReadFaces uw node islandFaceSel
            local islandFaces = islandRead[1]
            local islandBadFaces = islandRead[2]

            local islandOK = false

            if islandBadFaces.count == 0 and islandFaces.count > 0 then
            (
                local islandLinks = UGS_BuildLinks islandFaces false
                local islandComponents = UGS_BuildComponents islandFaces islandLinks

                if islandComponents.count == 1 then
                (
                    local checkedComp = UGS_ValidateComponent islandComponents[1] islandFaces
                    islandOK = checkedComp.valid

                    if not islandOK do
                    (
                        UGS_Log ("Grid filter: island " + (islandRoot as string) + \
                                 " = IGNORE / " + checkedComp.reason)
                    )
                )
                else
                (
                    UGS_Log ("Grid filter: island " + (islandRoot as string) + \
                             " = IGNORE / component count=" + \
                             (islandComponents.count as string))
                )
            )
            else
            (
                if islandBadFaces.count > 0 then
                    UGS_Log ("Grid filter: island " + (islandRoot as string) + \
                             " = IGNORE / non-Quad faces=" + \
                             (islandBadFaces.count as string))
                else
                    UGS_Log ("Grid filter: island " + (islandRoot as string) + \
                             " = IGNORE / no Quad faces")
            )

            if islandOK then
            (
                append gridableIslandRoots islandRoot
                UGS_Log ("Grid filter: island " + (islandRoot as string) + " = TARGET")
            )
            else
            (
                append nongridIslandRoots islandRoot
            )
        )

        UGS_Log ("Grid filter enabled: grid-able islands=" + \
                 (gridableIslandRoots.count as string) + \
                 " / ignored islands=" + (nongridIslandRoots.count as string)) force:true
    )

    local seamLinks = #()
    local selectedBoundarySeams = 0
    local sameIslandLoopSeams = 0
    local gridFilteredSeams = 0

    for pair in rawSeams do
    (
        local a = pair[1]
        local b = pair[2]

        local selA = faceSel[a.faceIndex]
        local selB = faceSel[b.faceIndex]

        if selA or selB do
        (
            selectedBoundarySeams += 1

            local islandA = UGS_FindRoot faceParent a.faceIndex
            local islandB = UGS_FindRoot faceParent b.faceIndex

            if islandA != islandB then
            (
                local allowSeam = true

                if gridOnly do
                (
                    local aGrid = (findItem gridableIslandRoots islandA) != 0
                    local bGrid = (findItem gridableIslandRoots islandB) != 0
                    allowSeam = aGrid and bGrid
                )

                if allowSeam then
                (
                    append seamLinks (UGS_GlobalSeamLink \
                        faceA:a.faceIndex \
                        cornerA:a.side \
                        faceB:b.faceIndex \
                        cornerB:b.side \
                        g1:a.g1 \
                        g2:a.g2 \
                        islandA:islandA \
                        islandB:islandB \
                        selectedA:selA \
                        selectedB:selB)
                )
                else
                (
                    gridFilteredSeams += 1
                )
            )
            else
            (
                -- 既に別経路で同一UVアイランド。
                -- ここを閉じるとループになるので残す。
                sameIslandLoopSeams += 1
            )
        )
    )

    -- 同じUVアイランド対で、3D頂点を共有して連続している
    -- seam edgeを1本のchainへまとめる。
    local assigned = for k = 1 to seamLinks.count collect false
    local groups = #()

    for start = 1 to seamLinks.count do
    (
        if not assigned[start] do
        (
            local firstLink = seamLinks[start]
            local mnIsland = amin firstLink.islandA firstLink.islandB
            local mxIsland = amax firstLink.islandA firstLink.islandB

            local queue = #(start)
            local qPos = 1
            local chain = #()
            assigned[start] = true

            while qPos <= queue.count do
            (
                local li = queue[qPos]
                qPos += 1
                append chain li

                for other = 1 to seamLinks.count do
                (
                    if not assigned[other] do
                    (
                        local testLink = seamLinks[other]
                        local mnTest = amin testLink.islandA testLink.islandB
                        local mxTest = amax testLink.islandA testLink.islandB

                        if (mnTest == mnIsland) and (mxTest == mxIsland) do
                        (
                            local touches = false

                            for existing in chain while not touches do
                            (
                                if UGS_GlobalLinksShareGeomVertex seamLinks[existing] testLink do
                                    touches = true
                            )

                            if not touches do
                            (
                                for pending in queue while not touches do
                                (
                                    if UGS_GlobalLinksShareGeomVertex seamLinks[pending] testLink do
                                        touches = true
                                )
                            )

                            if touches do
                            (
                                assigned[other] = true
                                append queue other
                            )
                        )
                    )
                )
            )

            append groups (UGS_GlobalSeamGroup \
                islandA:mnIsland \
                islandB:mxIsland \
                linkIndices:chain)
        )
    )

    -- 同じUVアイランド同士を別chainで再度繋ぐとループになるため、
    -- spanning forestとして「最初のchainだけ」採用する。
    local treeParent = for f = 1 to numFaces collect f

    for f = 1 to numFaces do
        UGS_Union treeParent f (UGS_FindRoot faceParent f)

    local acceptedGroups = 0
    local rejectedGroups = 0

    for gi = 1 to groups.count do
    (
        local g = groups[gi]
        local ra = UGS_FindRoot treeParent g.islandA
        local rb = UGS_FindRoot treeParent g.islandB

        if ra != rb then
        (
            g.accepted = true
            UGS_Union treeParent ra rb
            acceptedGroups += 1
        )
        else
        (
            g.accepted = false
            rejectedGroups += 1
        )

        groups[gi] = g
    )

    UGS_Log ("Global faces: " + (numFaces as string)) force:true
    UGS_Log ("Shared geometry edges: " + (sharedGeomEdges as string)) force:true
    UGS_Log ("Current UV islands: " + (islandRoots.count as string)) force:true
    UGS_Log ("Selected boundary seam edges: " + (selectedBoundarySeams as string)) force:true
    if gridOnly do
        UGS_Log ("Grid filter rejected seam edges: " + (gridFilteredSeams as string)) force:true
    UGS_Log ("Stitch candidate seam edges: " + (seamLinks.count as string)) force:true
    UGS_Log ("Loop seams kept: " + (sameIslandLoopSeams as string)) force:true
    UGS_Log ("Stitch seam chains: " + (groups.count as string)) force:true
    UGS_Log ("Accepted stitch chains: " + (acceptedGroups as string)) force:true
    UGS_Log ("Rejected loop chains: " + (rejectedGroups as string)) force:true

    #(groups, seamLinks)
)

fn UGS_SelectSourceVertsForGlobalGroup uw node seamLinks seamGroup =
(
    local tvSel = #{}

    for li in seamGroup.linkIndices do
    (
        local link = seamLinks[li]

        local sourceFace = 0
        local sourceCorner = 0

        -- 片側だけ選択されていれば、必ず選択側をsourceにする。
        -- 両側選択ならA側をsourceにする。
        if link.selectedA then
        (
            sourceFace = link.faceA
            sourceCorner = link.cornerA
        )
        else
        (
            sourceFace = link.faceB
            sourceCorner = link.cornerB
        )

        local degree = uw.numberPointsInFaceByNode sourceFace node
        local sourceCorner2 = UGS_NextCornerN sourceCorner degree

        local t1 = uw.getVertexIndexFromFaceByNode sourceFace sourceCorner node
        local t2 = uw.getVertexIndexFromFaceByNode sourceFace sourceCorner2 node

        tvSel[t1] = true
        tvSel[t2] = true
    )

    tvSel
)

fn UGS_VerifyGlobalGroup uw node seamLinks seamGroup =
(
    local okCount = 0

    for li in seamGroup.linkIndices do
    (
        local link = seamLinks[li]

        if UGS_IsFaceEdgeContinuousNow uw node \
            link.faceA link.cornerA \
            link.faceB link.cornerB do
        (
            okCount += 1
        )
    )

    okCount
)

fn UGS_RetryGlobalGroupPerEdge uw node seamLinks seamGroup =
(
    local retryCount = 0

    for li in seamGroup.linkIndices do
    (
        local link = seamLinks[li]

        if not (UGS_IsFaceEdgeContinuousNow uw node \
            link.faceA link.cornerA \
            link.faceB link.cornerB) do
        (
            local sourceFace = 0
            local sourceCorner = 0

            if link.selectedA then
            (
                sourceFace = link.faceA
                sourceCorner = link.cornerA
            )
            else
            (
                sourceFace = link.faceB
                sourceCorner = link.cornerB
            )

            local degree = uw.numberPointsInFaceByNode sourceFace node
            local sourceCorner2 = UGS_NextCornerN sourceCorner degree

            local tvSel = #{}
            tvSel[uw.getVertexIndexFromFaceByNode sourceFace sourceCorner node] = true
            tvSel[uw.getVertexIndexFromFaceByNode sourceFace sourceCorner2 node] = true

            try
            (
                uw.selectVerticesByNode tvSel node
                uw.stitchVerts true 0.5
                retryCount += 1
            )
            catch
            (
                UGS_Log ("Per-edge Stitch failed: face " + \
                         (sourceFace as string) + " corner " + \
                         (sourceCorner as string) + " / " + \
                         (getCurrentException() as string)) force:true
            )
        )
    )

    try(uw.updateView())catch()

    retryCount
)

fn UGS_StitchSelectedBoundary uw node faceSel gridOnly =
(
    local plan = UGS_BuildGlobalStitchPlan uw node faceSel gridOnly
    local groups = plan[1]
    local seamLinks = plan[2]

    local originalTVMode = undefined
    local acceptedChains = 0
    local weldedEdges = 0
    local processedEdges = 0

    try
    (
        originalTVMode = uw.getTVSubObjectMode()
        uw.setTVSubObjectMode 1
        UGS_Log ("TV subobject mode: " + (originalTVMode as string) + " -> 1") force:true
    )
    catch
    (
        UGS_Log ("TV subobject mode変更をスキップ: " + \
                 (getCurrentException() as string)) force:true
    )

    for gi = 1 to groups.count do
    (
        local g = groups[gi]

        if g.accepted then
        (
            acceptedChains += 1
            processedEdges += g.linkIndices.count

            UGS_ShowLoopActivity 55 35 gi groups.count \
                ("Stitch chain " + (gi as string) + "/" + (groups.count as string))

            local tvSel = UGS_SelectSourceVertsForGlobalGroup uw node seamLinks g

            UGS_Log ("Stitch chain " + (gi as string) + \
                     ": source TV verts=" + (tvSel.numberSet as string) + \
                     " / seam edges=" + (g.linkIndices.count as string)) force:true

            try
            (
                uw.selectVerticesByNode tvSel node
                uw.stitchVerts true 0.5
                uw.updateView()
            )
            catch
            (
                UGS_Log ("Standard Stitch failed on chain " + \
                         (gi as string) + ": " + \
                         (getCurrentException() as string)) force:true
            )

            local okCount = UGS_VerifyGlobalGroup uw node seamLinks g

            if okCount < g.linkIndices.count then
            (
                UGS_Log ("Chain " + (gi as string) + \
                         " partial result " + (okCount as string) + "/" + \
                         (g.linkIndices.count as string) + \
                         ". Retrying remaining edges individually.") force:true

                UGS_RetryGlobalGroupPerEdge uw node seamLinks g
                okCount = UGS_VerifyGlobalGroup uw node seamLinks g
            )

            weldedEdges += okCount

            UGS_Log ("Stitch chain result: " + (okCount as string) + \
                     "/" + (g.linkIndices.count as string) + " edges") force:true
        )
        else
        (
            UGS_Log ("Loop chain preserved: " + (gi as string) + \
                     " / edges=" + (g.linkIndices.count as string)) force:true
        )
    )

    if originalTVMode != undefined do
    (
        try(uw.setTVSubObjectMode originalTVMode)catch()
    )

    try(uw.selectFacesByNode faceSel node)catch()
    try(uw.updateView())catch()

    UGS_Log ("Boundary Auto Stitch finished: chains=" + \
             (acceptedChains as string) + \
             " / welded edges=" + (weldedEdges as string) + \
             " / processed candidate edges=" + (processedEdges as string)) force:true

    #(acceptedChains, weldedEdges, seamLinks.count)
)



fn UGS_RunStitchOnly debugMode:true gridOnly:true autoConnect:true skipLoopConnect:true =
(
    UGS_DebugEnabled = debugMode
    UGS_ResetLog()
    UGS_LastStatus = ""

    UGS_Log "===== UV Grid Straightener v1.6 / STITCH ONLY START =====" force:true
    UGS_Log ("Time: " + (localTime as string)) force:true

    if selection.count != 1 then
    (
        UGS_LastStatus = "オブジェクトを1つだけ選択してください。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    local node = selection[1]
    local uw = UGS_FindUnwrap node

    if uw == undefined then
    (
        UGS_LastStatus = "選択オブジェクトに Unwrap UVW が見つかりません。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    UGS_ShowActivity 5 "Stitch対象Faceを取得中"

    local faceSel = UGS_GetFaceSelection uw node

    if faceSel.numberSet == 0 then
    (
        UGS_LastStatus = "UVエディタでStitchの基準にしたい Face を選択してください。"
        UGS_Log UGS_LastStatus force:true
        messageBox UGS_LastStatus title:"UV Grid Straightener"
        return false
    )

    UGS_Log ("Node: " + node.name) force:true
    UGS_Log ("Selected anchor faces: " + (faceSel.numberSet as string)) force:true
    UGS_Log ("Grid-only Stitch filter: " + (gridOnly as string)) force:true
    UGS_Log ("Auto-connect after processing: " + (autoConnect as string)) force:true

    local result = undefined

    try
    (
        undo "UV Auto Stitch" on
        (
            result = UGS_StitchSelectedBoundary uw node faceSel gridOnly

            if autoConnect do
            (
                try
                (
                    UGS_AutoConnectCoincidentSeams uw node faceSel skipLoop:skipLoopConnect
                )
                catch
                (
                    UGS_Log ("警告: Stitchは完了しましたが、自動接続処理をスキップしました: " + \
                             (getCurrentException() as string)) force:true
                )
            )
        )
    )
    catch
    (
        UGS_LastStatus = "自動Stitch実行中にエラーが発生しました。"
        UGS_Log (UGS_LastStatus + " / " + (getCurrentException() as string)) force:true

        try(uw.selectFacesByNode faceSel node)catch()
        try(uw.updateView())catch()

        messageBox (UGS_LastStatus + "\nログを確認してください。") title:"UV Grid Straightener"
        return false
    )

    local chainCount = result[1]
    local weldedEdges = result[2]
    local candidateEdges = result[3]

    try(uw.selectFacesByNode faceSel node)catch()
    try(uw.updateView())catch()
    try(redrawViews())catch()

    UGS_ShowActivity 100 "Stitch完了"

    if candidateEdges == 0 then
    (
        UGS_LastStatus = "選択Faceの外周にStitch可能なUVシームは見つかりませんでした。"
    )
    else
    (
        UGS_LastStatus = ("Stitch完了: " + (weldedEdges as string) + \
                          "/" + (candidateEdges as string) + " edge(s)")
    )

    UGS_Log UGS_LastStatus force:true
    UGS_Log "===== UV Grid Straightener v1.6 / STITCH ONLY END =====" force:true

    true
)

try(destroyDialog UGS_Rollout)catch()

rollout UGS_Rollout "UV Grid Straightener v1.6" width:360 height:410
(
    label lblInfo1 "グリッド化とStitchは別処理です。Stitchは選択Faceを基準にします。" align:#left
    label lblInfo2 "既定では処理後に、重なった接続可能シームも自動で繋ぎます。" align:#left

    button btnAddEditPoly "ポリゴンを編集を追加" pos:[8,50] width:344 height:28

    spinner spnScale "セルサイズ倍率:" range:[0.01, 100.0, 1.0] type:#float scale:0.01 fieldwidth:70

    button btnRun "選択UVを均一グリッド化" pos:[8,116] width:344 height:34
    button btnStitch "選択UVの外周を自動Stitch" pos:[8,156] width:344 height:34

    checkbox chkAutoConnect "処理時に重なったシームを自動で繋げる" pos:[20,196] checked:true
    checkbox chkStitchGridOnly "グリッド化可能なUV同士のみStitch" pos:[20,220] checked:true
    checkbox chkSkipLoopConnect "ループになる接続はスキップする（推奨）" pos:[20,244] checked:true

    groupBox grpDebug "デバッグ" pos:[8,274] width:344 height:72
    checkbox chkDebug "デバッグログを出力する" pos:[20,297] checked:true
    button btnOpenLog "ログを開く" pos:[210,294] width:125 height:24

    label lblStatus "待機中" pos:[10,354] width:340 height:40 align:#left

    on btnAddEditPoly pressed do
    (
        btnAddEditPoly.enabled = false
        lblStatus.text = "ポリゴンを編集を追加しています..."
        windows.processPostedMessages()

        UGS_AddEditPolyToSelection()

        btnAddEditPoly.enabled = true
        lblStatus.text = "待機中"
        windows.processPostedMessages()
    )

    on btnRun pressed do
    (
        btnRun.enabled = false
        btnStitch.enabled = false
        chkAutoConnect.enabled = false
        chkStitchGridOnly.enabled = false
        chkSkipLoopConnect.enabled = false
        lblStatus.text = "処理を開始しています..."
        windows.processPostedMessages()

        UGS_ProgressStart()
        UGS_ShowActivity 1 "処理を開始しています"

        local ok = false

        try
        (
            ok = UGS_Run \
                stitchMode:false \
                scaleMul:spnScale.value \
                debugMode:chkDebug.checked \
                autoConnect:chkAutoConnect.checked \
                skipLoopConnect:chkSkipLoopConnect.checked
        )
        catch
        (
            UGS_LastStatus = ("予期しないエラー: " + (getCurrentException() as string))
            UGS_Log UGS_LastStatus force:true
            ok = false
        )

        UGS_ProgressEnd()
        btnRun.enabled = true
        btnStitch.enabled = true
        chkAutoConnect.enabled = true
        chkStitchGridOnly.enabled = true
        chkSkipLoopConnect.enabled = true
        lblStatus.text = UGS_LastStatus
        windows.processPostedMessages()
    )

    on btnStitch pressed do
    (
        btnRun.enabled = false
        btnStitch.enabled = false
        chkAutoConnect.enabled = false
        chkStitchGridOnly.enabled = false
        chkSkipLoopConnect.enabled = false
        lblStatus.text = "Stitch処理を開始しています..."
        windows.processPostedMessages()

        UGS_ProgressStart()
        UGS_ShowActivity 1 "Stitch処理を開始しています"

        local ok = false

        try
        (
            ok = UGS_RunStitchOnly \
                debugMode:chkDebug.checked \
                gridOnly:chkStitchGridOnly.checked \
                autoConnect:chkAutoConnect.checked \
                skipLoopConnect:chkSkipLoopConnect.checked
        )
        catch
        (
            UGS_LastStatus = ("予期しないStitchエラー: " + (getCurrentException() as string))
            UGS_Log UGS_LastStatus force:true
            ok = false
        )

        UGS_ProgressEnd()
        btnRun.enabled = true
        btnStitch.enabled = true
        chkAutoConnect.enabled = true
        chkStitchGridOnly.enabled = true
        chkSkipLoopConnect.enabled = true
        lblStatus.text = UGS_LastStatus
        windows.processPostedMessages()
    )

    on btnOpenLog pressed do
    (
        if doesFileExist UGS_LogPath then
            shellLaunch UGS_LogPath ""
        else
            messageBox "まだログファイルがありません。" title:"UV Grid Straightener"
    )
)

createDialog UGS_Rollout style:#(#style_titlebar, #style_sysmenu, #style_toolwindow)
