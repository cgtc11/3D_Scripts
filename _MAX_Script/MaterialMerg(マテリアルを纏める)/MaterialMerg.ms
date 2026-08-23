/*
    DiGi Material Manager
    Target: Autodesk 3ds Max 2026

    Features:
    - Lists materials referenced by the current scene.
    - Displays the base color as a list icon.
    - Displays the original name list and a compact color-only palette side by side.
    - Displays Multi/Sub-Object parent materials as an X icon instead of a color swatch.
    - Saves and restores the arranged color palette with the 3ds Max scene.
    - Can hide Multi/Sub-Object parent materials from both material views.
    - Sorts the palette by numeric hue, perceptual color, or brightness and inserts selected Multi/Sub slots by drag-and-drop.
    - Remaps face material IDs after palette drag insertion to preserve the rendered appearance.
    - Allows visual palette reordering when the selected materials do not share one editable Multi/Sub parent.
    - Renames leaf materials using RGB(R,G,B), adding _01 only when names overlap.
    - Consolidates leaf materials that share an exact name or displayed Base Color.
    - Consolidates manually selected leaf materials into the first selected instance.
    - Consolidates selected slots inside one MultiMaterial and compacts the remaining IDs.
    - Consolidates similar-color leaf materials using RGB distance and per-channel tolerances.
    - Hides repeated rows of the same material instance in flat list mode.
    - Displays live total, used, unused, and MultiMaterial counts.
    - Shows operation messages in a scrollable log field.
    - Merges selected top-level Multi/Sub-Object materials and remaps face IDs.
    - Moves a sub-material up/down while remapping face IDs to preserve appearance.
    - Removes unassigned material nodes from Slate/CME references.
*/

try (destroyDialog DiGiMaterialManager_Rollout) catch()

global DMM_Rows
global DMM_RowData
global DMM_IDMap
global DMM_Assignment
global DMM_SortItem
global DMM_InstanceMaterialGroup
global DMM_InstanceTargetGroup
global DMM_EmptySlotMaterial
global DMM_SortColumn
global DMM_SortAscending
global DMM_ColorSortItem
global DMM_PaletteAppDataID
global DMM_RemoveMaterialsFromSceneLibrary
global DMM_ForceRemoveUnusedMaterialReferences
global DMM_GetBaseColor
global DMM_GetPerceptualColorSortValues
global DMM_CollectMaterialCandidates
global DMM_RootIDUsageCache
global DMM_RootIDUsageEntry
persistent global DMM_SavedPaletteOrder

struct DMM_RowData
(
    mat,
    parentMat,
    rootMat,
    slotIndex = 0,
    materialID = 0,
    depth = 0,
    usedCount = 0,
    sourceRows = undefined
)

struct DMM_IDMap
(
    oldMat,
    oldID = 0,
    newID = 0
)

struct DMM_Assignment
(
    node,
    oldMat,
    target,
    targetKind
)

struct DMM_SortItem
(
    mat,
    rowData,
    slotIndex = 0,
    materialID = 0,
    usage = 0,
    originalIndex = 0
)

struct DMM_ColorSortItem
(
    rowIndex = 0,
    hue = 0.0,
    saturation = 0.0,
    brightness = 0.0,
    perceptualHue = 0.0,
    perceptualChroma = 0.0,
    perceptualLightness = 0.0,
    perceptualHueBand = 0,
    originalPosition = 0
)

struct DMM_RootIDUsageEntry
(
    rootMat,
    materialIDs = #(),
    objectCounts = #()
)

DMM_RootIDUsageCache = #()

struct DMM_InstanceMaterialGroup
(
    mat,
    nodes
)

struct DMM_InstanceTargetGroup
(
    target,
    materialGroups
)

DMM_Rows = #()
DMM_SortColumn = -1
DMM_SortAscending = true
DMM_PaletteAppDataID = 1145916752

if DMM_SavedPaletteOrder == undefined do DMM_SavedPaletteOrder = #()

fn DMM_GetPaletteMaterialKey mat createIfMissing:false =
(
    if mat == undefined then return "__DMM_UNDEFINED__"

    local materialKey = undefined
    try (materialKey = getAppData mat DMM_PaletteAppDataID) catch()

    if createIfMissing and (materialKey == undefined or materialKey == "") do
    (
        local guidValue = (dotNetClass "System.Guid").NewGuid()
        materialKey = guidValue.ToString()
        try (setAppData mat DMM_PaletteAppDataID materialKey) catch (materialKey = undefined)
    )

    materialKey
)

fn DMM_MigrateSavedPaletteOrderToKeys =
(
    if DMM_SavedPaletteOrder == undefined or DMM_SavedPaletteOrder.count == 0 then return false

    local migratedOrder = #()

    for savedEntry in DMM_SavedPaletteOrder do
    (
        local validEntry = false
        try (validEntry = savedEntry.count >= 5) catch()

        if validEntry do
        (
            local alreadyUsesKeys = false
            try (alreadyUsesKeys = (classOf savedEntry[1]) == String) catch()

            if alreadyUsesKeys then
            (
                append migratedOrder savedEntry
            )
            else
            (
                append migratedOrder #(
                    DMM_GetPaletteMaterialKey savedEntry[1] createIfMissing:true,
                    DMM_GetPaletteMaterialKey savedEntry[2] createIfMissing:true,
                    DMM_GetPaletteMaterialKey savedEntry[3] createIfMissing:true,
                    savedEntry[4],
                    savedEntry[5]
                )
            )
        )
    )

    DMM_SavedPaletteOrder = migratedOrder
    true
)

DMM_MigrateSavedPaletteOrderToKeys()

if DMM_EmptySlotMaterial == undefined do
(
    DMM_EmptySlotMaterial = StandardMaterial name:"__DMM_EMPTY_SLOT__" diffuse:(color 128 128 128)
)

fn DMM_IsMulti mat =
(
    mat != undefined and (classOf mat == MultiMaterial)
)

fn DMM_AppendUniqueReference values value =
(
    if value != undefined and (findItem values value) == 0 do append values value
    values
)

fn DMM_MaterialContains rootMat targetMat visited:#() =
(
    if rootMat == undefined or targetMat == undefined then return false
    if rootMat == targetMat then return true
    if (findItem visited rootMat) > 0 then return false

    append visited rootMat

    if DMM_IsMulti rootMat do
    (
        for subMat in rootMat.materialList where subMat != undefined do
        (
            if DMM_MaterialContains subMat targetMat visited:visited do return true
        )
    )

    false
)

fn DMM_AppendMaterialTree rootMat output visited:#() =
(
    if rootMat == undefined then return output
    if (findItem visited rootMat) > 0 then return output

    append visited rootMat
    DMM_AppendUniqueReference output rootMat

    if DMM_IsMulti rootMat do
    (
        for subMat in rootMat.materialList where subMat != undefined do
        (
            DMM_AppendMaterialTree subMat output visited:visited
        )
    )

    output
)

fn DMM_GetAssignedRootMaterials =
(
    local roots = #()

    for obj in objects where isValidNode obj do
    (
        local objMat = undefined
        try (objMat = obj.material) catch()
        if objMat != undefined do DMM_AppendUniqueReference roots objMat
    )

    roots
)

fn DMM_IsChildOfAnotherSceneMaterial candidate allSceneMats assignedRoots =
(
    for assignedMat in assignedRoots do
    (
        if assignedMat != candidate and DMM_MaterialContains assignedMat candidate do return true
    )

    for possibleParent in allSceneMats do
    (
        if possibleParent != candidate and DMM_IsMulti possibleParent do
        (
            if DMM_MaterialContains possibleParent candidate do return true
        )
    )

    false
)

fn DMM_GetDisplayRootMaterials =
(
    local roots = DMM_GetAssignedRootMaterials()
    local assignedRoots = #()
    local allSceneMats = #()

    join assignedRoots roots

    for mat in sceneMaterials where mat != undefined and mat != DMM_EmptySlotMaterial do DMM_AppendUniqueReference allSceneMats mat

    for mat in allSceneMats do
    (
        if (findItem roots mat) == 0 do
        (
            if not (DMM_IsChildOfAnotherSceneMaterial mat allSceneMats assignedRoots) do append roots mat
        )
    )

    roots
)

fn DMM_GetNodesUsingRootMaterial rootMat =
(
    local result = #()

    for obj in objects where isValidNode obj do
    (
        local objMat = undefined
        try (objMat = obj.material) catch()
        if objMat == rootMat do append result obj
    )

    result
)

fn DMM_NodeUsesMaterialID node materialID =
(
    if node == undefined or materialID < 1 then return false

    local meshValue = undefined
    local usesMaterialID = false

    try
    (
        meshValue = snapshotAsMesh node
        local faceCount = getNumFaces meshValue

        for faceIndex = 1 to faceCount do
        (
            if (not usesMaterialID) and ((getFaceMatID meshValue faceIndex) == materialID) do usesMaterialID = true
        )
    )
    catch()

    meshValue = undefined
    usesMaterialID
)

fn DMM_GetMaterialNameForSort mat =
(
    if mat == undefined or mat.name == undefined then "" else (toLower mat.name)
)

fn DMM_GetMaterialTypeNameForSort mat =
(
    if mat == undefined then "empty" else (toLower ((classOf mat) as string))
)

fn DMM_GetMaterialTypeRank mat =
(
    if DMM_IsMulti mat then return 0
    if mat == undefined then return 3

    local typeName = DMM_GetMaterialTypeNameForSort mat
    if matchPattern typeName pattern:"*physical*" then 1 else 2
)

fn DMM_CompareInteger firstValue secondValue =
(
    if firstValue < secondValue then -1 else if firstValue > secondValue then 1 else 0
)

fn DMM_CompareString firstValue secondValue =
(
    if firstValue < secondValue then -1 else if firstValue > secondValue then 1 else 0
)

fn DMM_CompareNumber firstValue secondValue =
(
    if firstValue < secondValue then -1 else if firstValue > secondValue then 1 else 0
)

fn DMM_CompareColorSortItems firstItem secondItem sortMode:#hue =
(
    local result = 0

    if sortMode == #hue then
    (
        local firstGray = if firstItem.saturation < 0.001 then 1 else 0
        local secondGray = if secondItem.saturation < 0.001 then 1 else 0
        result = DMM_CompareInteger firstGray secondGray
        if result == 0 do result = DMM_CompareNumber firstItem.hue secondItem.hue
        if result == 0 do result = DMM_CompareNumber firstItem.brightness secondItem.brightness
    )
    else if sortMode == #visual then
    (
        -- OKLChの彩度が低い色は無彩色として最後へまとめる。
        local firstNeutral = if firstItem.perceptualChroma < 0.025 then 1 else 0
        local secondNeutral = if secondItem.perceptualChroma < 0.025 then 1 else 0
        result = DMM_CompareInteger firstNeutral secondNeutral

        if result == 0 do
        (
            if firstNeutral == 1 then
            (
                -- 白から黒へ並べる。
                result = DMM_CompareNumber secondItem.perceptualLightness firstItem.perceptualLightness
            )
            else
            (
                -- 近い色相を帯にまとめ、その中を明るい色から暗い色へ並べる。
                result = DMM_CompareInteger firstItem.perceptualHueBand secondItem.perceptualHueBand
                if result == 0 do result = DMM_CompareNumber secondItem.perceptualLightness firstItem.perceptualLightness
                if result == 0 do result = DMM_CompareNumber secondItem.perceptualChroma firstItem.perceptualChroma
                if result == 0 do result = DMM_CompareNumber firstItem.perceptualHue secondItem.perceptualHue
            )
        )
    )
    else
    (
        result = DMM_CompareNumber firstItem.brightness secondItem.brightness
        if result == 0 do result = DMM_CompareNumber firstItem.hue secondItem.hue
    )

    if result == 0 then
        DMM_CompareInteger firstItem.originalPosition secondItem.originalPosition
    else
        result
)

fn DMM_CompareSortItems firstItem secondItem sortColumn:-1 ascending:true =
(
    local result = 0

    case sortColumn of
    (
        0:
        (
            result = DMM_CompareString (DMM_GetMaterialNameForSort firstItem.mat) (DMM_GetMaterialNameForSort secondItem.mat)
            if result == 0 do result = DMM_CompareString (DMM_GetMaterialTypeNameForSort firstItem.mat) (DMM_GetMaterialTypeNameForSort secondItem.mat)
        )
        1:
        (
            result = DMM_CompareInteger (DMM_GetMaterialTypeRank firstItem.mat) (DMM_GetMaterialTypeRank secondItem.mat)
            if result == 0 do result = DMM_CompareString (DMM_GetMaterialTypeNameForSort firstItem.mat) (DMM_GetMaterialTypeNameForSort secondItem.mat)
            if result == 0 do result = DMM_CompareString (DMM_GetMaterialNameForSort firstItem.mat) (DMM_GetMaterialNameForSort secondItem.mat)
        )
        2:
        (
            if firstItem.slotIndex == 0 and secondItem.slotIndex == 0 then
                return (DMM_CompareInteger firstItem.originalIndex secondItem.originalIndex)
            else
                result = DMM_CompareInteger firstItem.materialID secondItem.materialID
        )
        3:
        (
            result = DMM_CompareInteger firstItem.usage secondItem.usage
            if result == 0 do result = DMM_CompareString (DMM_GetMaterialNameForSort firstItem.mat) (DMM_GetMaterialNameForSort secondItem.mat)
        )
        default:
        (
            return (DMM_CompareInteger firstItem.originalIndex secondItem.originalIndex)
        )
    )

    if result != 0 then
    (
        if ascending then result else (-result)
    )
    else
    (
        DMM_CompareInteger firstItem.originalIndex secondItem.originalIndex
    )
)

fn DMM_GetSortedRootMaterials roots =
(
    if DMM_SortColumn < 0 then return roots

    local sortItems = #()
    local sortedRoots = #()

    for index = 1 to roots.count do
    (
        local rootMat = roots[index]
        local usageCount = (DMM_GetNodesUsingRootMaterial rootMat).count
        append sortItems (DMM_SortItem mat:rootMat usage:usageCount originalIndex:index)
    )

    if sortItems.count > 1 do
    (
        qsort sortItems DMM_CompareSortItems sortColumn:DMM_SortColumn ascending:DMM_SortAscending
    )

    for sortItem in sortItems do append sortedRoots sortItem.mat
    sortedRoots
)

fn DMM_GetSortedSubItems multiMat usedCount =
(
    local sortItems = #()

    for slotIndex = 1 to multiMat.materialList.count do
    (
        local slotMat = multiMat.materialList[slotIndex]
        local slotMaterialID = multiMat.materialIDList[slotIndex]
        append sortItems (DMM_SortItem mat:slotMat slotIndex:slotIndex materialID:slotMaterialID usage:usedCount originalIndex:slotIndex)
    )

    if DMM_SortColumn >= 0 and sortItems.count > 1 do
    (
        qsort sortItems DMM_CompareSortItems sortColumn:DMM_SortColumn ascending:DMM_SortAscending
    )

    sortItems
)

fn DMM_GetRowsSortedIgnoringHierarchy rows sortColumn =
(
    local sortItems = #()
    local sortedRows = #()

    for index = 1 to rows.count do
    (
        local row = rows[index]
        local rowMat = row.mat
        local rowSlotIndex = row.slotIndex
        local rowMaterialID = row.materialID
        local rowUsedCount = row.usedCount
        append sortItems (DMM_SortItem mat:rowMat rowData:row slotIndex:rowSlotIndex materialID:rowMaterialID usage:rowUsedCount originalIndex:index)
    )

    if sortItems.count > 1 do
    (
        qsort sortItems DMM_CompareSortItems sortColumn:sortColumn ascending:DMM_SortAscending
    )

    for sortItem in sortItems do append sortedRows sortItem.rowData
    sortedRows
)

fn DMM_FindGroupedRowIndex groupedRows targetMaterial =
(
    if targetMaterial == undefined then return 0

    for rowIndex = 1 to groupedRows.count do
    (
        if groupedRows[rowIndex].mat == targetMaterial do return rowIndex
    )

    0
)

fn DMM_GetRowsWithoutRepeatedInstances rows =
(
    local groupedRows = #()

    for sourceRow in rows do
    (
        local groupIndex = DMM_FindGroupedRowIndex groupedRows sourceRow.mat

        if groupIndex == 0 then
        (
            local groupedSources = #(sourceRow)
            local groupedMaterial = sourceRow.mat
            local groupedParentMaterial = sourceRow.parentMat
            local groupedRootMaterial = sourceRow.rootMat
            local groupedSlotIndex = sourceRow.slotIndex
            local groupedMaterialID = sourceRow.materialID
            local groupedDepth = sourceRow.depth
            local groupedUsedCount = sourceRow.usedCount
            local groupedRow = DMM_RowData mat:groupedMaterial parentMat:groupedParentMaterial rootMat:groupedRootMaterial slotIndex:groupedSlotIndex materialID:groupedMaterialID depth:groupedDepth usedCount:groupedUsedCount sourceRows:groupedSources
            append groupedRows groupedRow
        )
        else
        (
            append groupedRows[groupIndex].sourceRows sourceRow
        )
    )

    for groupedRow in groupedRows do
    (
        if (groupedRow.sourceRows != undefined) and (groupedRow.sourceRows.count > 1) do
        (
            local countedRoots = #()
            local totalUsedCount = 0

            for sourceRow in groupedRow.sourceRows do
            (
                local sourceRoot = sourceRow.rootMat
                if sourceRoot != undefined and (findItem countedRoots sourceRoot) == 0 do
                (
                    append countedRoots sourceRoot
                    totalUsedCount += sourceRow.usedCount
                )
            )

            groupedRow.usedCount = totalUsedCount
        )
    )

    groupedRows
)

fn DMM_GetBaseColorInfo mat =
(
    if mat == undefined then return #(false, color 96 96 96)

    local propertyOrder = #(#base_color, #baseColor, #diffuse, #diffuse_color, #color)

    for propName in propertyOrder do
    (
        if isProperty mat propName do
        (
            local value = undefined
            try (value = getProperty mat propName) catch()

            if value != undefined do
            (
                local converted = undefined
                try (converted = value as color) catch()
                if converted != undefined do return #(true, converted)
            )
        )
    )

    local materialProperties = #()
    try (materialProperties = getPropNames mat) catch()

    for propName in materialProperties do
    (
        local propertyText = toLower (propName as string)
        local normalizedPropertyText = substituteString propertyText "_" ""
        local isBaseColorProperty = (normalizedPropertyText == "basecolor") or (normalizedPropertyText == "diffusecolor") or (normalizedPropertyText == "diffuse") or (normalizedPropertyText == "color")

        if isBaseColorProperty do
        (
            local dynamicValue = undefined
            try (dynamicValue = getProperty mat propName) catch()

            if dynamicValue != undefined do
            (
                local dynamicConverted = undefined
                try (dynamicConverted = dynamicValue as color) catch()
                if dynamicConverted != undefined do return #(true, dynamicConverted)
            )
        )
    )

    #(false, color 96 96 96)
)

fn DMM_GetBaseColor mat =
(
    (DMM_GetBaseColorInfo mat)[2]
)

fn DMM_SetBaseColor mat newColor =
(
    if mat == undefined or DMM_IsMulti mat then return false

    local propertyOrder = #(#base_color, #baseColor, #diffuse, #diffuse_color, #color)

    for propName in propertyOrder do
    (
        if isProperty mat propName do
        (
            local succeeded = false
            try
            (
                setProperty mat propName newColor
                succeeded = true
            )
            catch()
            if succeeded do return true
        )
    )

    local materialProperties = #()
    try (materialProperties = getPropNames mat) catch()

    for propName in materialProperties do
    (
        local propertyText = toLower (propName as string)
        local normalizedPropertyText = substituteString propertyText "_" ""
        local isBaseColorProperty = (normalizedPropertyText == "basecolor") or (normalizedPropertyText == "diffusecolor") or (normalizedPropertyText == "diffuse") or (normalizedPropertyText == "color")

        if isBaseColorProperty do
        (
            local succeeded = false
            try
            (
                setProperty mat propName newColor
                succeeded = true
            )
            catch()
            if succeeded do return true
        )
    )

    false
)

-- Keep this function after DMM_GetBaseColor. When the script is wrapped in a
-- macroScript (.mcr), a later local function name otherwise resolves to
-- undefined even if the standalone .ms version has a global declaration.
fn DMM_GetColorSortValues mat =
(
    local baseColor = DMM_GetBaseColor mat
    local redValue = baseColor.r as float
    local greenValue = baseColor.g as float
    local blueValue = baseColor.b as float
    local maxValue = redValue
    local minValue = redValue

    if greenValue > maxValue do maxValue = greenValue
    if blueValue > maxValue do maxValue = blueValue
    if greenValue < minValue do minValue = greenValue
    if blueValue < minValue do minValue = blueValue

    local difference = maxValue - minValue
    local hueValue = 0.0
    local saturationValue = if maxValue > 0.0 then (difference / maxValue) else 0.0

    if difference > 0.0 do
    (
        if maxValue == redValue then
            hueValue = 60.0 * ((greenValue - blueValue) / difference)
        else if maxValue == greenValue then
            hueValue = 60.0 * (((blueValue - redValue) / difference) + 2.0)
        else
            hueValue = 60.0 * (((redValue - greenValue) / difference) + 4.0)

        if hueValue < 0.0 do hueValue += 360.0
    )

    local brightnessValue = (redValue * 0.2126) + (greenValue * 0.7152) + (blueValue * 0.0722)
    #(hueValue, saturationValue, brightnessValue)
)

-- RGBを知覚的に均等なOKLab/OKLChへ変換する。
-- 通常のHSV色相順はそのまま残し、「視覚順」だけがこの値を使う。
fn DMM_GetPerceptualColorSortValues mat =
(
    local baseColor = DMM_GetBaseColor mat
    local redValue = (baseColor.r as float) / 255.0
    local greenValue = (baseColor.g as float) / 255.0
    local blueValue = (baseColor.b as float) / 255.0

    redValue = if redValue <= 0.04045 then (redValue / 12.92) else (((redValue + 0.055) / 1.055) ^ 2.4)
    greenValue = if greenValue <= 0.04045 then (greenValue / 12.92) else (((greenValue + 0.055) / 1.055) ^ 2.4)
    blueValue = if blueValue <= 0.04045 then (blueValue / 12.92) else (((blueValue + 0.055) / 1.055) ^ 2.4)

    local coneL = (0.4122214708 * redValue) + (0.5363325363 * greenValue) + (0.0514459929 * blueValue)
    local coneM = (0.2119034982 * redValue) + (0.6806995451 * greenValue) + (0.1073969566 * blueValue)
    local coneS = (0.0883024619 * redValue) + (0.2817188376 * greenValue) + (0.6299787005 * blueValue)

    coneL = coneL ^ (1.0 / 3.0)
    coneM = coneM ^ (1.0 / 3.0)
    coneS = coneS ^ (1.0 / 3.0)

    local lightnessValue = (0.2104542553 * coneL) + (0.7936177850 * coneM) - (0.0040720468 * coneS)
    local aValue = (1.9779984951 * coneL) - (2.4285922050 * coneM) + (0.4505937099 * coneS)
    local bValue = (0.0259040371 * coneL) + (0.7827717662 * coneM) - (0.8086757660 * coneS)
    local chromaValue = sqrt ((aValue * aValue) + (bValue * bValue))
    local hueValue = if chromaValue < 0.000001 then 0.0 else (atan2 bValue aValue)
    if hueValue < 0.0 do hueValue += 360.0

    -- 15度単位にすることで、わずかな数値差より見た目のまとまりを優先する。
    local hueBand = (floor (hueValue / 15.0)) as integer
    #(hueValue, chromaValue, lightnessValue, hueBand)
)

fn DMM_ClampColorChannel value =
(
    local result = (floor (value + 0.5)) as integer
    if result < 0 then result = 0
    if result > 255 then result = 255
    result
)

fn DMM_RGBText mat =
(
    local baseColor = DMM_GetBaseColor mat
    local redValue = DMM_ClampColorChannel baseColor.r
    local greenValue = DMM_ClampColorChannel baseColor.g
    local blueValue = DMM_ClampColorChannel baseColor.b

    "RGB(" + (redValue as string) + "," + (greenValue as string) + "," + (blueValue as string) + ")"
)

fn DMM_StripRGBPrefix materialName =
(
    if materialName == undefined or materialName.count == 0 then return "Material"

    if materialName.count >= 4 and (toLower (substring materialName 1 4)) == "rgb(" do
    (
        local endToken = findString materialName ")_"
        if endToken != undefined do
        (
            local startIndex = endToken + 2
            local remaining = materialName.count - startIndex + 1
            if remaining > 0 then return (substring materialName startIndex remaining)
        )
    )

    materialName
)

fn DMM_TwoDigit value =
(
    if value < 10 then ("0" + (value as string)) else (value as string)
)

fn DMM_NameExistsIgnoreCase candidate usedNames =
(
    local lowerCandidate = toLower candidate
    for existingName in usedNames where (toLower existingName) == lowerCandidate do return true
    false
)

fn DMM_MakeUniqueMaterialName baseName usedNames =
(
    local candidate = baseName
    local suffix = 1

    while DMM_NameExistsIgnoreCase candidate usedNames do
    (
        candidate = baseName + "_" + DMM_TwoDigit suffix
        suffix += 1
    )

    append usedNames candidate
    candidate
)

fn DMM_CollectRenameTargets mat output visited:#() =
(
    if mat == undefined then return output
    if (findItem visited mat) > 0 then return output

    append visited mat

    if DMM_IsMulti mat then
    (
        for subMat in mat.materialList where subMat != undefined do
        (
            DMM_CollectRenameTargets subMat output visited:visited
        )
    )
    else
    (
        DMM_AppendUniqueReference output mat
    )

    output
)

fn DMM_RenameMaterials targets =
(
    local renameTargets = #()
    local allMaterials = #()
    local usedNames = #()

    for mat in targets where mat != undefined do DMM_CollectRenameTargets mat renameTargets

    for rootMat in DMM_GetDisplayRootMaterials() do DMM_AppendMaterialTree rootMat allMaterials

    for mat in allMaterials where (findItem renameTargets mat) == 0 do
    (
        if mat.name != undefined do append usedNames mat.name
    )

    undo "Rename Materials By RGB" on
    (
        for mat in renameTargets do
        (
            local baseName = DMM_RGBText mat
            mat.name = DMM_MakeUniqueMaterialName baseName usedNames
        )
    )

    renameTargets.count
)

fn DMM_GetEditableTarget node =
(
    local target = undefined
    try (target = node.baseObject) catch()

    if target == undefined then return undefined
    if isKindOf target Editable_Poly then return #(target, #poly)
    if isKindOf target Editable_Mesh then return #(target, #mesh)

    undefined
)

fn DMM_GetNodeMaterial node =
(
    local nodeMaterial = undefined
    try (nodeMaterial = node.material) catch()
    nodeMaterial
)

fn DMM_FindInstanceTargetGroupIndex targetGroups target =
(
    for index = 1 to targetGroups.count where targetGroups[index].target == target do return index
    0
)

fn DMM_FindInstanceMaterialGroupIndex materialGroups mat =
(
    for index = 1 to materialGroups.count where materialGroups[index].mat == mat do return index
    0
)

fn DMM_CollectInstanceTargetGroups =
(
    local targetGroups = #()

    for node in objects where isValidNode node do
    (
        local targetInfo = DMM_GetEditableTarget node

        if targetInfo != undefined do
        (
            local target = targetInfo[1]
            local targetGroupIndex = DMM_FindInstanceTargetGroupIndex targetGroups target

            if targetGroupIndex == 0 do
            (
                append targetGroups (DMM_InstanceTargetGroup target:target materialGroups:#())
                targetGroupIndex = targetGroups.count
            )

            local nodeMaterial = DMM_GetNodeMaterial node
            local materialGroups = targetGroups[targetGroupIndex].materialGroups
            local materialGroupIndex = DMM_FindInstanceMaterialGroupIndex materialGroups nodeMaterial

            if materialGroupIndex == 0 do
            (
                append materialGroups (DMM_InstanceMaterialGroup mat:nodeMaterial nodes:#())
                materialGroupIndex = materialGroups.count
            )

            append materialGroups[materialGroupIndex].nodes node
        )
    )

    targetGroups
)

fn DMM_GetInstanceGroupsToMakeUnique targetGroup selectedMaterials =
(
    local selectedGroups = #()
    local outsideGroupCount = 0
    local groupsToMakeUnique = #()

    for materialGroup in targetGroup.materialGroups do
    (
        if (findItem selectedMaterials materialGroup.mat) > 0 then
            append selectedGroups materialGroup
        else
            outsideGroupCount += 1
    )

    if selectedGroups.count == 0 or targetGroup.materialGroups.count < 2 then return groupsToMakeUnique

    if outsideGroupCount > 0 then
    (
        join groupsToMakeUnique selectedGroups
    )
    else
    (
        for index = 2 to selectedGroups.count do append groupsToMakeUnique selectedGroups[index]
    )

    groupsToMakeUnique
)

fn DMM_PreflightNecessaryInstanceUniqueness selectedMaterials =
(
    local errors = #()
    local groupCount = 0
    local nodeCount = 0

    for oldMat in selectedMaterials do
    (
        for node in DMM_GetNodesUsingRootMaterial oldMat do
        (
            if DMM_GetEditableTarget node == undefined do
            (
                append errors (node.name + " : Editable Poly / Editable Mesh ではありません。")
            )
        )
    )

    if errors.count == 0 do
    (
        local targetGroups = DMM_CollectInstanceTargetGroups()

        for targetGroup in targetGroups do
        (
            local groupsToMakeUnique = DMM_GetInstanceGroupsToMakeUnique targetGroup selectedMaterials

            for materialGroup in groupsToMakeUnique do
            (
                local nodesToCheck = #()
                join nodesToCheck materialGroup.nodes
                local canMakeUnique = false
                try (canMakeUnique = InstanceMgr.CanMakeObjectsUnique nodesToCheck) catch()

                if canMakeUnique then
                (
                    groupCount += 1
                    nodeCount += nodesToCheck.count
                )
                else
                (
                    local nodeNames = ""
                    for node in nodesToCheck do nodeNames += node.name + " "
                    append errors (nodeNames + ": インスタンスをユニーク化できません。")
                )
            )
        )
    )

    #(errors.count == 0, errors, groupCount, nodeCount)
)

fn DMM_MakeNecessaryInstancesUnique selectedMaterials =
(
    local errors = #()
    local groupCount = 0
    local nodeCount = 0
    local targetGroups = DMM_CollectInstanceTargetGroups()

    for targetGroup in targetGroups do
    (
        local groupsToMakeUnique = DMM_GetInstanceGroupsToMakeUnique targetGroup selectedMaterials

        for materialGroup in groupsToMakeUnique do
        (
            local nodesToMakeUnique = #()
            join nodesToMakeUnique materialGroup.nodes
            local madeUnique = false
            try (madeUnique = InstanceMgr.MakeObjectsUnique &nodesToMakeUnique #group) catch()

            if madeUnique then
            (
                groupCount += 1
                nodeCount += nodesToMakeUnique.count
            )
            else
            (
                local nodeNames = ""
                for node in nodesToMakeUnique do nodeNames += node.name + " "
                append errors (nodeNames + ": インスタンスのユニーク化に失敗しました。")
            )
        )
    )

    #(errors.count == 0, errors, groupCount, nodeCount)
)

fn DMM_ValidateMaterialAssignments oldMaterials =
(
    local assignments = #()
    local errors = #()
    local seenTargets = #()
    local seenTargetMats = #()

    for oldMat in oldMaterials do
    (
        for node in DMM_GetNodesUsingRootMaterial oldMat do
        (
            local targetInfo = DMM_GetEditableTarget node

            if targetInfo == undefined then
            (
                append errors (node.name + " : Editable Poly / Editable Mesh ではありません。")
            )
            else
            (
                local target = targetInfo[1]
                local existingIndex = findItem seenTargets target

                if existingIndex > 0 and seenTargetMats[existingIndex] != oldMat then
                (
                    append errors (node.name + " : 同じベースオブジェクトが異なるマルチサブで共有されています。")
                )
                else
                (
                    if existingIndex == 0 do
                    (
                        append seenTargets target
                        append seenTargetMats oldMat
                    )

                    for otherNode in objects where isValidNode otherNode do
                    (
                        local otherTargetInfo = DMM_GetEditableTarget otherNode
                        if otherTargetInfo != undefined and otherTargetInfo[1] == target do
                        (
                            local otherMaterial = undefined
                            try (otherMaterial = otherNode.material) catch()

                            if otherMaterial != undefined and otherMaterial != oldMat do
                            (
                                local sharedError = otherNode.name + " : 同じベースオブジェクトを別のマテリアルで共有しています。"
                                if (findItem errors sharedError) == 0 do append errors sharedError
                            )
                        )
                    )

                    append assignments (DMM_Assignment node:node oldMat:oldMat target:target targetKind:targetInfo[2])
                )
            )
        )
    )

    #(assignments, errors)
)

fn DMM_FindMappedID idMaps oldMat oldID =
(
    for idMap in idMaps where idMap.oldMat == oldMat and idMap.oldID == oldID do return idMap.newID
    oldID
)

fn DMM_RemapTargetFaceIDs target targetKind oldMat idMaps =
(
    if targetKind == #poly then
    (
        local faceCount = polyop.getNumFaces target
        local destinationIDs = #()
        local destinationFaces = #()

        for faceIndex = 1 to faceCount do
        (
            local oldID = polyop.getFaceMatID target faceIndex
            local newID = DMM_FindMappedID idMaps oldMat oldID

            if newID != oldID do
            (
                local bucketIndex = findItem destinationIDs newID
                if bucketIndex == 0 do
                (
                    append destinationIDs newID
                    append destinationFaces #{}
                    bucketIndex = destinationIDs.count
                )
                destinationFaces[bucketIndex][faceIndex] = true
            )
        )

        for index = 1 to destinationIDs.count do
        (
            polyop.setFaceMatID target destinationFaces[index] destinationIDs[index]
        )
    )
    else if targetKind == #mesh do
    (
        local faceCount = getNumFaces target

        for faceIndex = 1 to faceCount do
        (
            local oldID = getFaceMatID target faceIndex
            local newID = DMM_FindMappedID idMaps oldMat oldID
            if newID != oldID do setFaceMatID target faceIndex newID
        )

        update target
    )

    notifyDependents target partID:#all
    true
)

fn DMM_RemapAssignments assignments idMaps newMaterial:undefined =
(
    local processedTargets = #()

    for assignment in assignments do
    (
        if (findItem processedTargets assignment.target) == 0 do
        (
            DMM_RemapTargetFaceIDs assignment.target assignment.targetKind assignment.oldMat idMaps
            append processedTargets assignment.target
        )
    )

    if newMaterial != undefined do
    (
        for assignment in assignments do assignment.node.material = newMaterial
    )

    redrawViews()
    true
)

fn DMM_FindSubMaterialIndex materials targetMat =
(
    for index = 1 to materials.count where materials[index] == targetMat do return index
    0
)

fn DMM_BuildMergedMaterial selectedMaterials mergeInstances =
(
    local mergedSubMaterials = #()
    local idMaps = #()

    for oldMulti in selectedMaterials do
    (
        for slotIndex = 1 to oldMulti.materialList.count do
        (
            local subMat = oldMulti.materialList[slotIndex]
            local oldID = oldMulti.materialIDList[slotIndex]

            if subMat != undefined do
            (
                local mergedIndex = 0
                if mergeInstances do mergedIndex = DMM_FindSubMaterialIndex mergedSubMaterials subMat

                if mergedIndex == 0 do
                (
                    append mergedSubMaterials subMat
                    mergedIndex = mergedSubMaterials.count
                )

                append idMaps (DMM_IDMap oldMat:oldMulti oldID:oldID newID:mergedIndex)
            )
        )
    )

    if mergedSubMaterials.count == 0 then return undefined

    local usedNames = #()
    for rootMat in DMM_GetDisplayRootMaterials() where rootMat.name != undefined do append usedNames rootMat.name
    local mergedName = DMM_MakeUniqueMaterialName (selectedMaterials[1].name + "_Merged") usedNames
    local mergedMaterial = MultiMaterial numsubs:mergedSubMaterials.count name:mergedName

    for index = 1 to mergedSubMaterials.count do
    (
        mergedMaterial.materialList[index] = mergedSubMaterials[index]
        mergedMaterial.materialIDList[index] = index
        mergedMaterial.names[index] = mergedSubMaterials[index].name
        mergedMaterial.mapEnabled[index] = true
    )

    #(mergedMaterial, idMaps)
)

fn DMM_RemoveMaterialsFromSlate removeMaterials =
(
    local removedNodeCount = 0

    try
    (
        local viewCount = sme.GetNumViews()

        for viewIndex = 1 to viewCount do
        (
            local view = sme.GetView viewIndex
            local referencesToDelete = #()

            for nodeIndex = 1 to view.GetNumNodes() do
            (
                local slateNode = view.GetNode nodeIndex
                local nodeReference = undefined
                try (nodeReference = slateNode.reference) catch()

                if nodeReference != undefined and (findItem removeMaterials nodeReference) > 0 do
                (
                    DMM_AppendUniqueReference referencesToDelete nodeReference
                )
            )

            if referencesToDelete.count > 0 do
            (
                view.SelectNone()
                view.SetSelectedNodes referencesToDelete
                removedNodeCount += (view.GetSelectedNodes()).count
                view.DeleteSelection()
            )
        )
    )
    catch()

    removedNodeCount
)

fn DMM_RemoveMaterialsFromCompactEditor removeMaterials =
(
    local replacedCount = 0

    try
    (
        for slotIndex = 1 to meditMaterials.count do
        (
            if (findItem removeMaterials meditMaterials[slotIndex]) > 0 do
            (
                meditMaterials[slotIndex] = DMM_EmptySlotMaterial
                replacedCount += 1
            )
        )
    )
    catch()

    replacedCount
)

fn DMM_ClearSlateParameterReference removeMaterials =
(
    local clearedCount = 0

    try
    (
        local currentMaterial = sme.GetMtlInParamEditor()
        local shouldClear = false

        if currentMaterial != undefined do
        (
            for removeMaterial in removeMaterials do
            (
                if (not shouldClear) and (DMM_MaterialContains removeMaterial currentMaterial) do shouldClear = true
            )
        )

        if shouldClear do
        (
            sme.SetMtlInParamEditor DMM_EmptySlotMaterial
            clearedCount = 1
        )
    )
    catch()

    clearedCount
)

-- These helpers must precede DMM_MergeMultiMaterials when installed inside a
-- macroScript; otherwise the later function resolves as undefined.
fn DMM_IsMaterialValue value =
(
    if value == undefined then return false

    local result = false
    try (result = (superClassOf value == Material)) catch()
    result
)

fn DMM_CollectMaterialCandidates =
(
    local candidates = #()

    for mat in sceneMaterials where DMM_IsMaterialValue mat do
    (
        if mat != DMM_EmptySlotMaterial do DMM_AppendUniqueReference candidates mat
    )

    try
    (
        for viewIndex = 1 to sme.GetNumViews() do
        (
            local view = sme.GetView viewIndex

            for nodeIndex = 1 to view.GetNumNodes() do
            (
                local slateNode = view.GetNode nodeIndex
                local nodeReference = undefined
                try (nodeReference = slateNode.reference) catch()

                if DMM_IsMaterialValue nodeReference and nodeReference != DMM_EmptySlotMaterial do
                (
                    DMM_AppendUniqueReference candidates nodeReference
                )
            )
        )
    )
    catch()

    try
    (
        for slotIndex = 1 to meditMaterials.count do
        (
            local slotMaterial = meditMaterials[slotIndex]
            if DMM_IsMaterialValue slotMaterial and slotMaterial != DMM_EmptySlotMaterial do
            (
                DMM_AppendUniqueReference candidates slotMaterial
            )
        )
    )
    catch()

    candidates
)

fn DMM_MergeMultiMaterials selectedMaterials mergeInstances makeNecessaryUnique =
(
    if selectedMaterials.count < 2 then return #(false, "結合するマルチサブを2つ以上選択してください。")

    for otherRoot in DMM_GetDisplayRootMaterials() where (findItem selectedMaterials otherRoot) == 0 do
    (
        for selectedMat in selectedMaterials do
        (
            if DMM_MaterialContains otherRoot selectedMat do
            (
                return #(false, selectedMat.name + " は別のマテリアルの中からも参照されています。\n参照元を外してから結合してください。")
            )
        )
    )

    local assignedNodeCount = 0
    for selectedMaterial in selectedMaterials do assignedNodeCount += (DMM_GetNodesUsingRootMaterial selectedMaterial).count
    if assignedNodeCount == 0 then return #(false, "選択したマルチサブを使用しているオブジェクトがありません。")

    local assignments = #()

    if makeNecessaryUnique then
    (
        local preflight = DMM_PreflightNecessaryInstanceUniqueness selectedMaterials

        if not preflight[1] then
        (
            local preflightErrorText = "インスタンスをユニーク化できないため、処理を中止しました。\n\n"
            for errorLine in preflight[2] do preflightErrorText += errorLine + "\n"
            return #(false, preflightErrorText)
        )
    )
    else
    (
        local validation = DMM_ValidateMaterialAssignments selectedMaterials
        assignments = validation[1]
        local errors = validation[2]

        if errors.count > 0 then
        (
            local errorText = "次のオブジェクトは安全にIDを書き換えられないため、処理を中止しました。\n\n"
            for errorLine in errors do errorText += errorLine + "\n"
            return #(false, errorText)
        )
    )

    local buildResult = DMM_BuildMergedMaterial selectedMaterials mergeInstances
    if buildResult == undefined then return #(false, "結合できるサブマテリアルがありません。")

    local mergedMaterial = buildResult[1]
    local idMaps = buildResult[2]
    local uniqueResult = #(true, #(), 0, 0)
    local operationErrors = #()
    local operationSucceeded = false

    undo "Merge Multi/Sub Materials" on
    (
        with redraw off
        (
            if makeNecessaryUnique do uniqueResult = DMM_MakeNecessaryInstancesUnique selectedMaterials

            if uniqueResult[1] do
            (
                if makeNecessaryUnique do
                (
                    local validationAfterUnique = DMM_ValidateMaterialAssignments selectedMaterials
                    assignments = validationAfterUnique[1]
                    operationErrors = validationAfterUnique[2]
                )

                if operationErrors.count == 0 and assignments.count > 0 do
                (
                    DMM_RemapAssignments assignments idMaps newMaterial:mergedMaterial
                    operationSucceeded = true
                )
            )
        )
    )

    if not operationSucceeded then
    (
        if uniqueResult[3] > 0 do try (max undo) catch()

        local operationErrorText = "結合処理を中止しました。\n\n"
        for errorLine in uniqueResult[2] do operationErrorText += errorLine + "\n"
        for errorLine in operationErrors do operationErrorText += errorLine + "\n"
        if assignments.count == 0 do operationErrorText += "処理対象のオブジェクトがありません。\n"
        return #(false, operationErrorText)
    )

    DMM_RemoveMaterialsFromSlate selectedMaterials
    DMM_RemoveMaterialsFromCompactEditor selectedMaterials
    gc light:true

    local remainingCount = 0
    local remainingCandidates = DMM_CollectMaterialCandidates()
    for oldMat in selectedMaterials where (findItem remainingCandidates oldMat) > 0 do remainingCount += 1

    local resultText = "結合しました: " + mergedMaterial.name
    if uniqueResult[3] > 0 do
    (
        resultText += " / " + (uniqueResult[3] as string) + "グループ、" + (uniqueResult[4] as string) + "オブジェクトを必要な範囲だけユニーク化しました。"
    )
    if remainingCount > 0 do
    (
        resultText += " / " + (remainingCount as string) + "個の旧マテリアルは別の参照から使用されているため残っています。"
    )

    #(true, resultText)
)

fn DMM_SwapMultiSlots parentMat firstSlot secondSlot =
(
    if parentMat == undefined or not (DMM_IsMulti parentMat) then return #(false, "マルチサブが見つかりません。")
    if firstSlot < 1 or secondSlot < 1 then return #(false, "移動先がありません。")
    if firstSlot > parentMat.materialList.count or secondSlot > parentMat.materialList.count then return #(false, "移動先がありません。")

    local validation = DMM_ValidateMaterialAssignments #(parentMat)
    local assignments = validation[1]
    local errors = validation[2]

    if errors.count > 0 then
    (
        local errorText = "次のオブジェクトは安全にIDを書き換えられないため、処理を中止しました。\n\n"
        for errorLine in errors do errorText += errorLine + "\n"
        return #(false, errorText)
    )

    local firstID = parentMat.materialIDList[firstSlot]
    local secondID = parentMat.materialIDList[secondSlot]
    local idMaps = #(
        DMM_IDMap oldMat:parentMat oldID:firstID newID:secondID,
        DMM_IDMap oldMat:parentMat oldID:secondID newID:firstID
    )

    undo "Move Multi/Sub Material ID" on
    (
        with redraw off
        (
            local tempMaterial = parentMat.materialList[firstSlot]
            local tempName = parentMat.names[firstSlot]
            local tempEnabled = parentMat.mapEnabled[firstSlot]

            parentMat.materialList[firstSlot] = parentMat.materialList[secondSlot]
            parentMat.names[firstSlot] = parentMat.names[secondSlot]
            parentMat.mapEnabled[firstSlot] = parentMat.mapEnabled[secondSlot]

            parentMat.materialList[secondSlot] = tempMaterial
            parentMat.names[secondSlot] = tempName
            parentMat.mapEnabled[secondSlot] = tempEnabled

            DMM_RemapAssignments assignments idMaps
        )
    )

    #(true, "ID " + (firstID as string) + " と ID " + (secondID as string) + " を入れ替えました。")
)

fn DMM_MoveMultiSlotsBefore parentMat selectedSlotIndices targetSlotIndex =
(
    if parentMat == undefined or not (DMM_IsMulti parentMat) then return #(false, "マルチサブが見つかりません。")
    if selectedSlotIndices.count == 0 then return #(false, "移動するサブマテリアルを選択してください。")

    sort selectedSlotIndices

    local slotCount = parentMat.materialList.count
    if targetSlotIndex < 1 do targetSlotIndex = 1
    if targetSlotIndex > (slotCount + 1) do targetSlotIndex = slotCount + 1

    for slotIndex in selectedSlotIndices do
    (
        if slotIndex < 1 or slotIndex > slotCount then return #(false, "移動するスロットが見つかりません。リストを更新してください。")
    )

    if targetSlotIndex <= slotCount and (findItem selectedSlotIndices targetSlotIndex) > 0 then
    (
        return #(false, "選択中の色と同じ位置へは挿入できません。")
    )

    local validation = DMM_ValidateMaterialAssignments #(parentMat)
    local assignments = validation[1]
    local errors = validation[2]

    if errors.count > 0 then
    (
        local errorText = "次のオブジェクトは安全にIDを書き換えられないため、処理を中止しました。\n\n"
        for errorLine in errors do errorText += errorLine + "\n"
        return #(false, errorText)
    )

    local oldMaterials = #()
    local oldIDs = #()
    local oldNames = #()
    local oldEnabledStates = #()
    local remainingSlotIndices = #()
    local removedBeforeTarget = 0

    for slotIndex = 1 to slotCount do
    (
        append oldMaterials parentMat.materialList[slotIndex]
        append oldIDs parentMat.materialIDList[slotIndex]

        local slotName = ""
        local slotEnabled = true
        try (slotName = parentMat.names[slotIndex]) catch()
        try (slotEnabled = parentMat.mapEnabled[slotIndex]) catch()
        append oldNames slotName
        append oldEnabledStates slotEnabled

        if (findItem selectedSlotIndices slotIndex) == 0 then
            append remainingSlotIndices slotIndex
        else if slotIndex < targetSlotIndex do
            removedBeforeTarget += 1
    )

    local insertPosition = targetSlotIndex - removedBeforeTarget
    if insertPosition < 1 do insertPosition = 1
    if insertPosition > (remainingSlotIndices.count + 1) do insertPosition = remainingSlotIndices.count + 1

    local newSlotOrder = #()
    join newSlotOrder remainingSlotIndices
    for selectedIndex = selectedSlotIndices.count to 1 by -1 do
    (
        insertItem selectedSlotIndices[selectedIndex] newSlotOrder insertPosition
    )

    local idMaps = #()
    for newSlotIndex = 1 to newSlotOrder.count do
    (
        local oldSlotIndex = newSlotOrder[newSlotIndex]
        append idMaps (DMM_IDMap oldMat:parentMat oldID:oldIDs[oldSlotIndex] newID:oldIDs[newSlotIndex])
    )

    local operationSucceeded = false

    try
    (
        undo "Drag Multi/Sub Material IDs" on
        (
            with redraw off
            (
                for newSlotIndex = 1 to newSlotOrder.count do
                (
                    local oldSlotIndex = newSlotOrder[newSlotIndex]
                    parentMat.materialList[newSlotIndex] = oldMaterials[oldSlotIndex]
                    try (parentMat.names[newSlotIndex] = oldNames[oldSlotIndex]) catch()
                    try (parentMat.mapEnabled[newSlotIndex] = oldEnabledStates[oldSlotIndex]) catch()
                )

                if idMaps.count > 0 do DMM_RemapAssignments assignments idMaps
                notifyDependents parentMat partID:#all
                operationSucceeded = true
            )
        )
    )
    catch (operationSucceeded = false)

    if not operationSucceeded then return #(false, "ドラッグによるIDの並び替えに失敗しました。")

    redrawViews()
    #(true, (selectedSlotIndices.count as string) + "個のサブマテリアルをID " + (oldIDs[insertPosition] as string) + " の位置へ挿入し、面IDも追従させました。")
)

fn DMM_CollectUsedMaterials =
(
    local usedMaterials = #()

    for rootMat in DMM_GetAssignedRootMaterials() do
    (
        DMM_AppendMaterialTree rootMat usedMaterials
    )

    usedMaterials
)

fn DMM_CollectLeafMaterialCandidates =
(
    local allMaterials = #()
    local visited = #()
    local leafMaterials = #()

    for row in DMM_Rows do
    (
        local rowMaterial = row.mat
        if (rowMaterial != undefined) and (rowMaterial != DMM_EmptySlotMaterial) and (not (DMM_IsMulti rowMaterial)) do
        (
            DMM_AppendUniqueReference leafMaterials rowMaterial
        )
    )

    for rootMat in DMM_CollectMaterialCandidates() do
    (
        DMM_AppendMaterialTree rootMat allMaterials visited:visited
    )

    for mat in allMaterials do
    (
        if (mat != undefined) and (mat != DMM_EmptySlotMaterial) and (not (DMM_IsMulti mat)) do
        (
            DMM_AppendUniqueReference leafMaterials mat
        )
    )

    leafMaterials
)

fn DMM_GetDuplicateMaterialKey mat mergeMode =
(
    if mat == undefined or DMM_IsMulti mat then return undefined

    if mergeMode == #name then
    (
        local materialName = ""
        try (materialName = mat.name as string) catch()
        if materialName.count == 0 then undefined else materialName
    )
    else if mergeMode == #baseColor then
    (
        local colorInfo = DMM_GetBaseColorInfo mat
        if (not colorInfo[1]) then return undefined

        local baseColor = colorInfo[2]
        local redValue = DMM_ClampColorChannel baseColor.r
        local greenValue = DMM_ClampColorChannel baseColor.g
        local blueValue = DMM_ClampColorChannel baseColor.b
        (redValue as string) + "," + (greenValue as string) + "," + (blueValue as string)
    )
    else
    (
        undefined
    )
)

fn DMM_BuildDuplicateMaterialReplacements mergeMode =
(
    local keys = #()
    local canonicalMaterials = #()
    local groupSizes = #()
    local replacements = #()

    for mat in DMM_CollectLeafMaterialCandidates() do
    (
        local key = DMM_GetDuplicateMaterialKey mat mergeMode

        if key != undefined do
        (
            local keyIndex = findItem keys key

            if keyIndex == 0 then
            (
                append keys key
                append canonicalMaterials mat
                append groupSizes 1
            )
            else
            (
                append replacements #(mat, canonicalMaterials[keyIndex])
                groupSizes[keyIndex] += 1
            )
        )
    )

    local groupCount = 0
    for groupSize in groupSizes where groupSize > 1 do groupCount += 1

    #(replacements, groupCount)
)

fn DMM_FindMaterialReplacement replacements sourceMaterial =
(
    for replacement in replacements where replacement[1] == sourceMaterial do return replacement[2]
    undefined
)

fn DMM_ReplaceMaterialsInCompactEditor replacements =
(
    local replacedCount = 0

    try
    (
        for slotIndex = 1 to meditMaterials.count do
        (
            local slotMaterial = meditMaterials[slotIndex]
            local replacementMaterial = DMM_FindMaterialReplacement replacements slotMaterial
            if replacementMaterial != undefined do
            (
                meditMaterials[slotIndex] = replacementMaterial
                replacedCount += 1
            )
        )
    )
    catch()

    replacedCount
)

fn DMM_ReplaceSlateParameterReference replacements =
(
    local replacedCount = 0

    try
    (
        local currentMaterial = sme.GetMtlInParamEditor()
        local replacementMaterial = DMM_FindMaterialReplacement replacements currentMaterial

        if replacementMaterial != undefined do
        (
            sme.SetMtlInParamEditor replacementMaterial
            replacedCount = 1
        )
    )
    catch()

    replacedCount
)

fn DMM_ApplyMaterialReplacements replacements groupCount resultHeading =
(
    if replacements.count == 0 then return #(false, "置換するマテリアルがありません。")

    local duplicateMaterials = #()
    for replacement in replacements do DMM_AppendUniqueReference duplicateMaterials replacement[1]

    local allMaterials = #()
    local visited = #()

    for row in DMM_Rows do
    (
        local rowsForRootCollection = #(row)
        if (row.sourceRows != undefined) and (row.sourceRows.count > 0) do rowsForRootCollection = row.sourceRows

        for sourceRow in rowsForRootCollection do
        (
            local rowRootMaterial = sourceRow.rootMat
            if rowRootMaterial != undefined do
            (
                DMM_AppendMaterialTree rowRootMaterial allMaterials visited:visited
            )
        )
    )

    for rootMat in DMM_CollectMaterialCandidates() do
    (
        DMM_AppendMaterialTree rootMat allMaterials visited:visited
    )

    local objectCount = 0
    local multiSlotCount = 0

    undo "Merge Duplicate Materials" on
    (
        with redraw off
        (
            for obj in objects where isValidNode obj do
            (
                local objectMaterial = undefined
                try (objectMaterial = obj.material) catch()
                local replacementMaterial = DMM_FindMaterialReplacement replacements objectMaterial

                if replacementMaterial != undefined do
                (
                    obj.material = replacementMaterial
                    objectCount += 1
                )
            )

            for parentMaterial in allMaterials where DMM_IsMulti parentMaterial do
            (
                for slotIndex = 1 to parentMaterial.materialList.count do
                (
                    local slotMaterial = parentMaterial.materialList[slotIndex]
                    local replacementMaterial = DMM_FindMaterialReplacement replacements slotMaterial

                    if replacementMaterial != undefined do
                    (
                        parentMaterial.materialList[slotIndex] = replacementMaterial
                        try (parentMaterial.names[slotIndex] = replacementMaterial.name) catch()
                        multiSlotCount += 1
                    )
                )
            )
        )
    )

    local compactCount = DMM_ReplaceMaterialsInCompactEditor replacements
    local parameterCount = DMM_ReplaceSlateParameterReference replacements
    local slateCount = DMM_RemoveMaterialsFromSlate duplicateMaterials

    DMM_Rows = #()
    allMaterials = undefined
    duplicateMaterials = undefined
    gc light:true
    redrawViews()

    local resultText = resultHeading
    resultText += "\n置換したマテリアル: " + (replacements.count as string)
    resultText += ", オブジェクト: " + (objectCount as string)
    resultText += ", MultiMaterialスロット: " + (multiSlotCount as string)
    resultText += ", SMEノード: " + (slateCount as string)
    resultText += ", CMEスロット: " + (compactCount as string)
    if parameterCount > 0 do resultText += ", Parameter Editor: 1"
    resultText += "\nオブジェクトとMultiMaterialの置換はUndoで戻せます。"

    #(true, resultText)
)

fn DMM_MergeDuplicateMaterials mergeMode =
(
    local buildResult = DMM_BuildDuplicateMaterialReplacements mergeMode
    local replacements = buildResult[1]
    local groupCount = buildResult[2]

    if replacements.count == 0 then
    (
        if mergeMode == #name then
            return #(false, "同じ名前の別マテリアルは見つかりませんでした。\n同じ行が複数見えていても、すでに同じインスタンスを別の親またはIDから参照している場合があります。")
        else
            return #(false, "同じBase Colorの別マテリアルは見つかりませんでした。\n同じ行が複数見えていても、すでに同じインスタンスを別の親またはIDから参照している場合があります。")
    )

    local resultHeading = ""
    if mergeMode == #name then
        resultHeading = (groupCount as string) + "組の同じ名前を結合しました。"
    else
        resultHeading = (groupCount as string) + "組の同じBase Colorを結合しました。"

    DMM_ApplyMaterialReplacements replacements groupCount resultHeading
)

fn DMM_CompactMergedMaterialSlots targetMaterial =
(
    if targetMaterial == undefined then return #(0, 0)

    local removedSlotCount = 0
    local skippedParentCount = 0

    for parentMaterial in DMM_GetDisplayRootMaterials() where DMM_IsMulti parentMaterial do
    (
        local matchingSlots = #()

        for slotIndex = 1 to parentMaterial.materialList.count do
        (
            if parentMaterial.materialList[slotIndex] == targetMaterial do append matchingSlots slotIndex
        )

        if matchingSlots.count > 1 do
        (
            local validation = DMM_ValidateMaterialAssignments #(parentMaterial)
            local assignments = validation[1]
            local errors = validation[2]

            if errors.count > 0 then
            (
                skippedParentCount += 1
            )
            else
            (
                local keptSlotIndex = matchingSlots[1]
                local remainingMaterials = #()
                local remainingSlotIndices = #()
                local remainingNames = #()
                local remainingEnabledStates = #()

                for slotIndex = 1 to parentMaterial.materialList.count do
                (
                    local removeDuplicateSlot = (slotIndex != keptSlotIndex) and ((findItem matchingSlots slotIndex) > 0)

                    if not removeDuplicateSlot do
                    (
                        local slotName = ""
                        local slotEnabled = true
                        try (slotName = parentMaterial.names[slotIndex]) catch()
                        try (slotEnabled = parentMaterial.mapEnabled[slotIndex]) catch()

                        append remainingMaterials parentMaterial.materialList[slotIndex]
                        append remainingSlotIndices slotIndex
                        append remainingNames slotName
                        append remainingEnabledStates slotEnabled
                    )
                )

                local keptNewID = findItem remainingSlotIndices keptSlotIndex
                local idMaps = #()

                for slotIndex = 1 to parentMaterial.materialList.count do
                (
                    local oldMaterialID = parentMaterial.materialIDList[slotIndex]
                    local survivingIndex = findItem remainingSlotIndices slotIndex
                    local newMaterialID = if survivingIndex > 0 then survivingIndex else keptNewID
                    append idMaps (DMM_IDMap oldMat:parentMaterial oldID:oldMaterialID newID:newMaterialID)
                )

                local operationSucceeded = false

                try
                (
                    undo "Compact Merged Material IDs" on
                    (
                        with redraw off
                        (
                            if idMaps.count > 0 do DMM_RemapAssignments assignments idMaps

                            parentMaterial.numsubs = remainingMaterials.count

                            for remainingIndex = 1 to remainingMaterials.count do
                            (
                                parentMaterial.materialList[remainingIndex] = remainingMaterials[remainingIndex]
                                parentMaterial.materialIDList[remainingIndex] = remainingIndex
                                try (parentMaterial.names[remainingIndex] = remainingNames[remainingIndex]) catch()
                                try (parentMaterial.mapEnabled[remainingIndex] = remainingEnabledStates[remainingIndex]) catch()
                            )

                            notifyDependents parentMaterial partID:#all
                            operationSucceeded = true
                        )
                    )
                )
                catch (operationSucceeded = false)

                if operationSucceeded then
                    removedSlotCount += matchingSlots.count - 1
                else
                    skippedParentCount += 1
            )
        )
    )

    #(removedSlotCount, skippedParentCount)
)

fn DMM_RemoveMaterialsFromSceneLibrary removeMaterials =
(
    local replacedCount = 0

    try
    (
        for sceneIndex = sceneMaterials.count to 1 by -1 do
        (
            if (findItem removeMaterials sceneMaterials[sceneIndex]) > 0 do
            (
                sceneMaterials[sceneIndex] = DMM_EmptySlotMaterial
                replacedCount += 1
            )
        )
    )
    catch()

    replacedCount
)

fn DMM_ForceRemoveUnusedMaterialReferences unusedMaterials =
(
    local forcedReferenceCount = 0

    for unusedMaterial in unusedMaterials do
    (
        if unusedMaterial != undefined and unusedMaterial != DMM_EmptySlotMaterial do
        (
            local replaced = false
            try
            (
                replaceInstances unusedMaterial DMM_EmptySlotMaterial
                replaced = true
            )
            catch()

            if replaced do forcedReferenceCount += 1
        )
    )

    forcedReferenceCount
)

fn DMM_MergeSelectedMaterials selectedMaterials =
(
    if selectedMaterials.count < 2 then
    (
        return #(false, "別インスタンスの通常マテリアルを2つ以上選択してください。\n選択した複数行が同じインスタンスの場合、親またはIDが異なっていても結合済みです。")
    )

    for selectedMaterial in selectedMaterials do
    (
        if (selectedMaterial == undefined) or (DMM_IsMulti selectedMaterial) do
        (
            return #(false, "手動結合では通常マテリアルだけを選択してください。MultiMaterialとEmptyは選択できません。")
        )
    )

    local canonicalMaterial = selectedMaterials[1]
    local replacements = #()

    for materialIndex = 2 to selectedMaterials.count do
    (
        local materialToReplace = selectedMaterials[materialIndex]
        if materialToReplace != canonicalMaterial do
        (
            append replacements #(materialToReplace, canonicalMaterial)
        )
    )

    local result = DMM_ApplyMaterialReplacements replacements 1 ("選択したマテリアルを「" + canonicalMaterial.name + "」へ結合しました。")

    if result[1] do
    (
        local sourceMaterials = #()
        for replacement in replacements do DMM_AppendUniqueReference sourceMaterials replacement[1]

        local compactResult = DMM_CompactMergedMaterialSlots canonicalMaterial
        local sceneLibraryCount = DMM_RemoveMaterialsFromSceneLibrary sourceMaterials
        local forcedReferenceCount = DMM_ForceRemoveUnusedMaterialReferences sourceMaterials

        DMM_Rows = #()
        try (clearUndoBuffer()) catch()
        try (setSaveRequired true) catch()
        gc light:true
        redrawViews()

        result[2] = substituteString result[2] "\nオブジェクトとMultiMaterialの置換はUndoで戻せます。" ""
        result[2] += "\r\n削除した重複IDスロット: " + (compactResult[1] as string)
        result[2] += ", シーン材質参照: " + (sceneLibraryCount as string)
        result[2] += ", その他参照: " + (forcedReferenceCount as string)
        if compactResult[2] > 0 do result[2] += "\r\n警告: " + (compactResult[2] as string) + "個のMultiMaterialはIDを安全に詰められませんでした。"
        result[2] += "\r\n結合元の未使用マテリアルを削除し、Undo履歴を消去しました。"
    )

    result
)

fn DMM_SelectedRowsShareDirectMultiParent selectedRows =
(
    if selectedRows.count < 2 then return false

    local firstRow = selectedRows[1]
    local sharedParent = firstRow.parentMat

    if sharedParent == undefined or not (DMM_IsMulti sharedParent) then return false
    if firstRow.rootMat != sharedParent then return false

    for row in selectedRows do
    (
        if row.parentMat != sharedParent then return false
        if row.rootMat != sharedParent then return false
        if row.slotIndex < 1 then return false
    )

    true
)

fn DMM_MergeSelectedMultiSlots selectedRows =
(
    if not (DMM_SelectedRowsShareDirectMultiParent selectedRows) then
    (
        return #(false, "同じMultiMaterial内の通常マテリアルを2つ以上選択してください。")
    )

    local targetRow = selectedRows[1]
    local parentMaterial = targetRow.parentMat
    local targetSlotIndex = targetRow.slotIndex
    local sourceMaterialCandidates = #()

    if targetRow.mat == undefined or DMM_IsMulti targetRow.mat then
    (
        return #(false, "最初に選択する行は通常マテリアルにしてください。")
    )

    local selectedSlotIndices = #()

    for row in selectedRows do
    (
        local hasGroupedSources = (row.sourceRows != undefined) and (row.sourceRows.count > 1)
        if hasGroupedSources then
        (
            return #(false, "同一インスタンスの複数IDが1行にまとめられています。\n「親子を見て並べる」をONにして、統一するIDを選択してください。")
        )

        if row.mat == undefined or DMM_IsMulti row.mat then
        (
            return #(false, "通常マテリアルの行だけを選択してください。")
        )

        if row.slotIndex > parentMaterial.materialList.count then
        (
            return #(false, "選択したスロットが見つかりません。リストを更新してから選択し直してください。")
        )

        if (findItem selectedSlotIndices row.slotIndex) == 0 do append selectedSlotIndices row.slotIndex
        if row.slotIndex != targetSlotIndex and row.mat != targetRow.mat do DMM_AppendUniqueReference sourceMaterialCandidates row.mat
    )

    if selectedSlotIndices.count < 2 then
    (
        return #(false, "統一するIDを2つ以上選択してください。")
    )

    local targetMaterialID = parentMaterial.materialIDList[targetSlotIndex]

    local validation = DMM_ValidateMaterialAssignments #(parentMaterial)
    local assignments = validation[1]
    local errors = validation[2]

    if errors.count > 0 then
    (
        local errorText = "次のオブジェクトは安全にIDを書き換えられないため、処理を中止しました。\n\n"
        for errorLine in errors do errorText += errorLine + "\n"
        return #(false, errorText)
    )

    local remainingMaterials = #()
    local remainingSlotIndices = #()
    local remainingNames = #()
    local remainingEnabledStates = #()

    for slotIndex = 1 to parentMaterial.materialList.count do
    (
        local isSelectedSourceSlot = ((findItem selectedSlotIndices slotIndex) > 0) and (slotIndex != targetSlotIndex)

        if not isSelectedSourceSlot do
        (
            local slotMaterial = parentMaterial.materialList[slotIndex]
            local slotName = ""
            local slotEnabled = true
            try (slotName = parentMaterial.names[slotIndex]) catch()
            try (slotEnabled = parentMaterial.mapEnabled[slotIndex]) catch()

            append remainingMaterials slotMaterial
            append remainingSlotIndices slotIndex
            append remainingNames slotName
            append remainingEnabledStates slotEnabled
        )
    )

    local targetNewID = findItem remainingSlotIndices targetSlotIndex
    if targetNewID == 0 then
    (
        return #(false, "統一先のスロットを保持できませんでした。リストを更新してから選択し直してください。")
    )

    -- Every surviving slot receives a consecutive ID. Removed source slots
    -- point to the surviving first-clicked slot, so face IDs and the list stay aligned.
    local idMaps = #()

    for slotIndex = 1 to parentMaterial.materialList.count do
    (
        local oldMaterialID = parentMaterial.materialIDList[slotIndex]
        local survivingIndex = findItem remainingSlotIndices slotIndex
        local newMaterialID = targetNewID

        if survivingIndex > 0 do newMaterialID = survivingIndex
        append idMaps (DMM_IDMap oldMat:parentMaterial oldID:oldMaterialID newID:newMaterialID)
    )

    local operationSucceeded = false

    try
    (
        undo "Merge Selected MultiMaterial IDs" on
        (
            with redraw off
            (
                if idMaps.count > 0 do DMM_RemapAssignments assignments idMaps

                parentMaterial.numsubs = remainingMaterials.count

                for remainingIndex = 1 to remainingMaterials.count do
                (
                    parentMaterial.materialList[remainingIndex] = remainingMaterials[remainingIndex]
                    parentMaterial.materialIDList[remainingIndex] = remainingIndex
                    try (parentMaterial.names[remainingIndex] = remainingNames[remainingIndex]) catch()
                    try (parentMaterial.mapEnabled[remainingIndex] = remainingEnabledStates[remainingIndex]) catch()
                )

                notifyDependents parentMaterial partID:#all
                operationSucceeded = true
            )
        )
    )
    catch (operationSucceeded = false)

    if (not operationSucceeded) then
    (
        return #(false, "MultiMaterial内のID統一に失敗しました。")
    )

    local usedMaterialsAfterMerge = DMM_CollectUsedMaterials()
    local unusedSourceMaterials = #()

    for sourceMaterial in sourceMaterialCandidates do
    (
        if (findItem usedMaterialsAfterMerge sourceMaterial) == 0 do append unusedSourceMaterials sourceMaterial
    )

    local removedSlateCount = 0
    local removedCompactCount = 0
    local removedParameterCount = 0
    local removedSceneLibraryCount = 0
    local forcedReferenceCount = 0

    if unusedSourceMaterials.count > 0 do
    (
        removedSlateCount = DMM_RemoveMaterialsFromSlate unusedSourceMaterials
        removedCompactCount = DMM_RemoveMaterialsFromCompactEditor unusedSourceMaterials
        removedParameterCount = DMM_ClearSlateParameterReference unusedSourceMaterials
        removedSceneLibraryCount = DMM_RemoveMaterialsFromSceneLibrary unusedSourceMaterials
        forcedReferenceCount = DMM_ForceRemoveUnusedMaterialReferences unusedSourceMaterials
        try (clearUndoBuffer()) catch()
        try (setSaveRequired true) catch()
    )

    DMM_Rows = #()
    gc light:true
    redrawViews()

    local removedSlotCount = selectedSlotIndices.count - 1
    local resultText = "旧ID " + (targetMaterialID as string) + " のマテリアルを残し、新ID " + (targetNewID as string) + " へ統一しました。"
    resultText += "\r\n削除したMultiMaterialスロット: " + (removedSlotCount as string)
    resultText += "\r\n残ったIDを1～" + (remainingMaterials.count as string) + "へ詰め、面IDも再設定しました。"
    resultText += "\r\nIDの基準: 最初に選択した「" + targetRow.mat.name + "」"
    if unusedSourceMaterials.count > 0 do
    (
        resultText += "\r\n結合後に未使用となったマテリアル: " + (unusedSourceMaterials.count as string) + "個を削除"
        resultText += " (SME:" + (removedSlateCount as string) + ", CME:" + (removedCompactCount as string)
        resultText += ", Parameter:" + (removedParameterCount as string) + ", Scene:" + (removedSceneLibraryCount as string)
        resultText += ", 強制解除:" + (forcedReferenceCount as string) + ")"
        resultText += "\r\nUndo履歴を消去しました。"
    )

    #(true, resultText)
)

fn DMM_GetColorDifferenceData firstMaterial secondMaterial =
(
    local firstColorInfo = DMM_GetBaseColorInfo firstMaterial
    local secondColorInfo = DMM_GetBaseColorInfo secondMaterial

    if (not firstColorInfo[1]) or (not secondColorInfo[1]) then return undefined

    local firstColor = firstColorInfo[2]
    local secondColor = secondColorInfo[2]
    local redDifference = abs (firstColor.r - secondColor.r)
    local greenDifference = abs (firstColor.g - secondColor.g)
    local blueDifference = abs (firstColor.b - secondColor.b)
    local rgbDistance = sqrt ((redDifference * redDifference) + (greenDifference * greenDifference) + (blueDifference * blueDifference))

    #(redDifference, greenDifference, blueDifference, rgbDistance)
)

fn DMM_ColorDifferencesAreAllowed differenceData rgbTolerance redTolerance greenTolerance blueTolerance =
(
    if differenceData == undefined then return false

    local useRGBDistance = rgbTolerance > 0
    local useRedTolerance = redTolerance > 0
    local useGreenTolerance = greenTolerance > 0
    local useBlueTolerance = blueTolerance > 0

    if useRGBDistance and differenceData[4] > rgbTolerance then return false
    if useRedTolerance and differenceData[1] > redTolerance then return false
    if useGreenTolerance and differenceData[2] > greenTolerance then return false
    if useBlueTolerance and differenceData[3] > blueTolerance then return false

    if (not useRGBDistance) and (not useRedTolerance) and (not useGreenTolerance) and (not useBlueTolerance) then
    (
        return (differenceData[1] == 0) and (differenceData[2] == 0) and (differenceData[3] == 0)
    )

    true
)

fn DMM_AreSimilarColorMaterials candidateMaterial targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance =
(
    if (candidateMaterial == undefined) or (targetMaterial == undefined) then return false
    if candidateMaterial == targetMaterial then return false
    if (DMM_IsMulti candidateMaterial) or (DMM_IsMulti targetMaterial) then return false
    if (classOf candidateMaterial) != (classOf targetMaterial) then return false

    local differenceData = DMM_GetColorDifferenceData candidateMaterial targetMaterial
    DMM_ColorDifferencesAreAllowed differenceData rgbTolerance redTolerance greenTolerance blueTolerance
)

fn DMM_ColorDifferenceText firstMaterial secondMaterial =
(
    local differenceData = DMM_GetColorDifferenceData firstMaterial secondMaterial
    if differenceData == undefined then return "Color取得不可"

    "R差=" + (differenceData[1] as string) + ", G差=" + (differenceData[2] as string) + ", B差=" + (differenceData[3] as string) + ", RGB距離=" + (differenceData[4] as string)
)

fn DMM_ColorToleranceText rgbTolerance redTolerance greenTolerance blueTolerance =
(
    "RGB距離=" + (rgbTolerance as string) + ", R差=" + (redTolerance as string) + ", G差=" + (greenTolerance as string) + ", B差=" + (blueTolerance as string)
)

fn DMM_BuildSimilarColorReplacementsForTarget targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance =
(
    local replacements = #()

    for candidateMaterial in DMM_CollectLeafMaterialCandidates() do
    (
        if DMM_AreSimilarColorMaterials candidateMaterial targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance do
        (
            append replacements #(candidateMaterial, targetMaterial)
        )
    )

    replacements
)

fn DMM_BuildAutoSimilarColorReplacements rgbTolerance redTolerance greenTolerance blueTolerance =
(
    local materials = DMM_CollectLeafMaterialCandidates()
    local replacements = #()
    local mergedSources = #()
    local groupCount = 0
    local totalPairs = 0
    local processedPairs = 0
    local progressWasStarted = false
    local comparisonSucceeded = true

    if materials.count > 1 do totalPairs = (materials.count * (materials.count - 1)) / 2

    try
    (
        progressStart "似た色のマテリアルを比較中..."
        progressWasStarted = true

        for targetIndex = 1 to materials.count do
        (
            local targetMaterial = materials[targetIndex]
            local targetWasMerged = (findItem mergedSources targetMaterial) > 0
            local targetCandidateCount = 0

            if not targetWasMerged do
            (
                if targetIndex < materials.count do
                (
                    for candidateIndex = (targetIndex + 1) to materials.count do
                    (
                        local candidateMaterial = materials[candidateIndex]
                        processedPairs += 1

                        if totalPairs > 0 do
                        (
                            progressUpdate (((processedPairs as float) / (totalPairs as float)) * 100.0)
                        )

                        local candidateWasMerged = (findItem mergedSources candidateMaterial) > 0
                        if (not candidateWasMerged) and (DMM_AreSimilarColorMaterials candidateMaterial targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance) do
                        (
                            append replacements #(candidateMaterial, targetMaterial)
                            DMM_AppendUniqueReference mergedSources candidateMaterial
                            targetCandidateCount += 1
                        )
                    )
                )

                if targetCandidateCount > 0 do groupCount += 1
            )
        )

        progressUpdate 100
    )
    catch (comparisonSucceeded = false)

    if progressWasStarted do try (progressEnd()) catch()

    #(replacements, groupCount, comparisonSucceeded)
)

fn DMM_GetSimilarColorReport targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance =
(
    if targetMaterial == undefined or DMM_IsMulti targetMaterial then
    (
        return #(false, "色差を確認する通常マテリアルを1つ選択してください。")
    )

    local reportText = "基準: " + targetMaterial.name + "\r\n"
    reportText += "許容値: " + (DMM_ColorToleranceText rgbTolerance redTolerance greenTolerance blueTolerance)
    local comparedCount = 0
    local candidateCount = 0

    for candidateMaterial in DMM_CollectLeafMaterialCandidates() do
    (
        if (candidateMaterial != targetMaterial) and ((classOf candidateMaterial) == (classOf targetMaterial)) do
        (
            local differenceData = DMM_GetColorDifferenceData candidateMaterial targetMaterial
            if differenceData != undefined do
            (
                local isCandidate = DMM_ColorDifferencesAreAllowed differenceData rgbTolerance redTolerance greenTolerance blueTolerance
                local resultMark = if isCandidate then "候補" else "対象外"
                reportText += "\r\n" + resultMark + ": " + candidateMaterial.name + " [" + (DMM_ColorDifferenceText candidateMaterial targetMaterial) + "]"
                comparedCount += 1
                if isCandidate do candidateCount += 1
            )
        )
    )

    if comparedCount == 0 do reportText += "\r\n比較できる同クラスのマテリアルはありません。"
    reportText += "\r\n比較数: " + (comparedCount as string) + ", 結合候補: " + (candidateCount as string)

    #(true, reportText)
)

fn DMM_MergeSimilarColorMaterials targetMaterial automaticMode rgbTolerance redTolerance greenTolerance blueTolerance =
(
    local replacements = #()
    local groupCount = 0

    if automaticMode then
    (
        local buildResult = DMM_BuildAutoSimilarColorReplacements rgbTolerance redTolerance greenTolerance blueTolerance
        replacements = buildResult[1]
        groupCount = buildResult[2]
        if (not buildResult[3]) then return #(false, "似た色の比較中にエラーが発生したため、処理を中止しました。")
    )
    else
    (
        if targetMaterial == undefined or DMM_IsMulti targetMaterial then
        (
            return #(false, "基準にする通常マテリアルを1つ選択してください。")
        )

        replacements = DMM_BuildSimilarColorReplacementsForTarget targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance
        if replacements.count > 0 do groupCount = 1
    )

    if replacements.count == 0 then
    (
        return #(false, "現在の許容値では、結合できる似た色のマテリアルがありません。")
    )

    local resultHeading = ""
    if automaticMode then
        resultHeading = (groupCount as string) + "組の似た色を一覧の上から順番に結合しました。"
    else
        resultHeading = (replacements.count as string) + "個を「" + targetMaterial.name + "」へ結合しました。"

    local result = DMM_ApplyMaterialReplacements replacements groupCount resultHeading
    if result[1] do
    (
        result[2] += "\r\n許容値: " + (DMM_ColorToleranceText rgbTolerance redTolerance greenTolerance blueTolerance)
        for replacement in replacements do
        (
            local sourceMaterial = replacement[1]
            local destinationMaterial = replacement[2]
            result[2] += "\r\n" + sourceMaterial.name + " -> " + destinationMaterial.name + " [" + (DMM_ColorDifferenceText sourceMaterial destinationMaterial) + "]"
        )
    )

    result
)

fn DMM_CollectAllKnownMaterials =
(
    local allMaterials = #()
    local visited = #()

    for rootMat in DMM_GetAssignedRootMaterials() do
    (
        DMM_AppendMaterialTree rootMat allMaterials visited:visited
    )

    for rootMat in DMM_CollectMaterialCandidates() do
    (
        DMM_AppendMaterialTree rootMat allMaterials visited:visited
    )

    allMaterials
)

fn DMM_GetMaterialStatistics =
(
    local allMaterials = DMM_CollectAllKnownMaterials()
    local usedMaterials = DMM_CollectUsedMaterials()
    local usedCount = 0
    local unusedCount = 0
    local multiMaterialCount = 0

    for mat in allMaterials do
    (
        if (findItem usedMaterials mat) > 0 then
            usedCount += 1
        else
            unusedCount += 1

        if DMM_IsMulti mat do multiMaterialCount += 1
    )

    #(allMaterials.count, usedCount, unusedCount, multiMaterialCount)
)

fn DMM_CollectUnusedSceneMaterials usedMaterials =
(
    local unusedMaterials = #()

    for mat in DMM_CollectAllKnownMaterials() do
    (
        if (findItem usedMaterials mat) == 0 do DMM_AppendUniqueReference unusedMaterials mat
    )

    unusedMaterials
)

fn DMM_DeleteUnusedMaterials =
(
    local usedMaterials = DMM_CollectUsedMaterials()
    local unusedBefore = DMM_CollectUnusedSceneMaterials usedMaterials
    local unusedCount = unusedBefore.count
    local slateCount = DMM_RemoveMaterialsFromSlate unusedBefore
    local compactCount = DMM_RemoveMaterialsFromCompactEditor unusedBefore
    local parameterCount = DMM_ClearSlateParameterReference unusedBefore
    local sceneLibraryCount = DMM_RemoveMaterialsFromSceneLibrary unusedBefore
    local forcedReferenceCount = DMM_ForceRemoveUnusedMaterialReferences unusedBefore

    DMM_Rows = #()
    usedMaterials = undefined
    unusedBefore = undefined

    -- 強制参照解除で古いマテリアルをUndoが保持しないよう、履歴を明示的に破棄する。
    try (clearUndoBuffer()) catch()
    try (setSaveRequired true) catch()
    gc()
    redrawViews()

    local usedAfter = DMM_CollectUsedMaterials()
    local unusedAfter = DMM_CollectUnusedSceneMaterials usedAfter

    -- sceneMaterialsの内部更新が1回目のGC後に反映されるケースに備え、残存分を再度解除する。
    if unusedAfter.count > 0 do
    (
        sceneLibraryCount += DMM_RemoveMaterialsFromSceneLibrary unusedAfter
        forcedReferenceCount += DMM_ForceRemoveUnusedMaterialReferences unusedAfter
        usedAfter = undefined
        unusedAfter = undefined
        try (clearUndoBuffer()) catch()
        try (setSaveRequired true) catch()
        gc()

        usedAfter = DMM_CollectUsedMaterials()
        unusedAfter = DMM_CollectUnusedSceneMaterials usedAfter
    )

    #(unusedCount, slateCount, compactCount, unusedAfter.count, parameterCount, forcedReferenceCount, sceneLibraryCount)
)

-- Returns every assigned root material that contains the specified Multi/Sub.
-- A nested Multi/Sub can be shared by more than one root, so all roots must be
-- checked before one of its slots can be considered unused.
fn DMM_GetAssignedRootsContainingMaterial targetMaterial =
(
    local containingRoots = #()

    if targetMaterial == undefined then return containingRoots

    for rootMaterial in DMM_GetAssignedRootMaterials() do
    (
        if DMM_MaterialContains rootMaterial targetMaterial do
        (
            DMM_AppendUniqueReference containingRoots rootMaterial
        )
    )

    containingRoots
)

fn DMM_FindRootIDUsageEntry rootMaterial =
(
    for cacheEntry in DMM_RootIDUsageCache where cacheEntry.rootMat == rootMaterial do return cacheEntry
    undefined
)

fn DMM_GetCachedRootIDUsageCount rootMaterial materialID =
(
    local cacheEntry = DMM_FindRootIDUsageEntry rootMaterial
    if cacheEntry == undefined then return 0

    local idIndex = findItem cacheEntry.materialIDs materialID
    if idIndex == 0 then 0 else cacheEntry.objectCounts[idIndex]
)

-- Reads each assigned object's mesh only once. The previous implementation
-- called snapshotAsMesh once for every slot, which made list refreshes scale as
-- slots x objects and caused Color moves/merges to become very slow.
fn DMM_RebuildMaterialIDUsageCache =
(
    DMM_RootIDUsageCache = #()

    for rootMaterial in DMM_GetAssignedRootMaterials() do
    (
        local cacheEntry = DMM_RootIDUsageEntry rootMat:rootMaterial

        for node in DMM_GetNodesUsingRootMaterial rootMaterial do
        (
            local meshValue = undefined
            local nodeMaterialIDs = #()

            try
            (
                meshValue = snapshotAsMesh node
                local faceCount = getNumFaces meshValue

                for faceIndex = 1 to faceCount do
                (
                    local faceMaterialID = getFaceMatID meshValue faceIndex
                    if faceMaterialID > 0 and (findItem nodeMaterialIDs faceMaterialID) == 0 do append nodeMaterialIDs faceMaterialID
                )
            )
            catch()

            for materialID in nodeMaterialIDs do
            (
                local idIndex = findItem cacheEntry.materialIDs materialID

                if idIndex == 0 then
                (
                    append cacheEntry.materialIDs materialID
                    append cacheEntry.objectCounts 1
                )
                else
                (
                    cacheEntry.objectCounts[idIndex] += 1
                )
            )

            try (delete meshValue) catch()
            meshValue = undefined
        )

        append DMM_RootIDUsageCache cacheEntry
    )

    true
)

fn DMM_IsMultiSlotIDUsed parentMaterial materialID =
(
    if parentMaterial == undefined or materialID < 1 then return false

    for rootMaterial in DMM_GetAssignedRootsContainingMaterial parentMaterial do
    (
        if (DMM_GetCachedRootIDUsageCount rootMaterial materialID) > 0 do return true
    )

    false
)

fn DMM_GetMultiSlotUsageCount parentMaterial materialID =
(
    if parentMaterial == undefined or materialID < 1 then return 0

    local usageCount = 0

    for rootMaterial in DMM_GetAssignedRootsContainingMaterial parentMaterial do
    (
        usageCount += DMM_GetCachedRootIDUsageCount rootMaterial materialID
    )

    usageCount
)

fn DMM_CanCompactMultiMaterialIDs parentMaterial =
(
    if parentMaterial == undefined or not (DMM_IsMulti parentMaterial) then return false

    local containingRoots = DMM_GetAssignedRootsContainingMaterial parentMaterial
    if containingRoots.count == 0 then return false

    -- A material that is nested in another assigned root cannot be renumbered
    -- independently because the same face IDs are evaluated by both levels.
    for rootMaterial in containingRoots where rootMaterial != parentMaterial do return false

    local seenIDs = #()
    for materialID in parentMaterial.materialIDList do
    (
        if (findItem seenIDs materialID) > 0 then return false
        append seenIDs materialID
    )

    true
)

-- Removes unused slots. For a directly assigned, non-shared Multi/Sub whose
-- geometry can be edited safely, the surviving IDs and face IDs are compacted
-- to 1..N. Nested/shared materials retain their original IDs.
fn DMM_RemoveMultiSlotIndicesPreserveIDs parentMaterial removeSlotIndices =
(
    if parentMaterial == undefined or not (DMM_IsMulti parentMaterial) then return #(false, 0, 0, "Multi/Subが見つかりません。", false)

    local remainingMaterials = #()
    local remainingIDs = #()
    local remainingNames = #()
    local remainingEnabledStates = #()
    local removedCount = 0
    local protectedLastSlotCount = 0
    local compactIDs = DMM_CanCompactMultiMaterialIDs parentMaterial
    local assignments = #()
    local idMaps = #()

    for slotIndex = 1 to parentMaterial.materialList.count do
    (
        if (findItem removeSlotIndices slotIndex) == 0 then
        (
            append remainingMaterials parentMaterial.materialList[slotIndex]
            append remainingIDs parentMaterial.materialIDList[slotIndex]

            local slotName = ""
            local slotEnabled = true
            try (slotName = parentMaterial.names[slotIndex]) catch()
            try (slotEnabled = parentMaterial.mapEnabled[slotIndex]) catch()
            append remainingNames slotName
            append remainingEnabledStates slotEnabled
        )
        else
        (
            removedCount += 1
        )
    )

    -- 3ds MaxのMulti/Subを有効な状態に保つため、全枠削除になる場合は1枠だけ残す。
    if remainingMaterials.count == 0 and parentMaterial.materialList.count > 0 do
    (
        append remainingMaterials parentMaterial.materialList[1]
        append remainingIDs parentMaterial.materialIDList[1]

        local firstName = ""
        local firstEnabled = true
        try (firstName = parentMaterial.names[1]) catch()
        try (firstEnabled = parentMaterial.mapEnabled[1]) catch()
        append remainingNames firstName
        append remainingEnabledStates firstEnabled
        removedCount -= 1
        protectedLastSlotCount = 1
    )

    if compactIDs do
    (
        local needsIDCompaction = false
        for slotIndex = 1 to remainingIDs.count where remainingIDs[slotIndex] != slotIndex do needsIDCompaction = true

        if not needsIDCompaction then
        (
            compactIDs = false
        )
        else
        (
            local validation = DMM_ValidateMaterialAssignments #(parentMaterial)
            assignments = validation[1]
            if validation[2].count > 0 do compactIDs = false
        )
    )

    if compactIDs do
    (
        for newSlotIndex = 1 to remainingIDs.count do
        (
            append idMaps (DMM_IDMap oldMat:parentMaterial oldID:remainingIDs[newSlotIndex] newID:newSlotIndex)
            remainingIDs[newSlotIndex] = newSlotIndex
        )
    )

    local operationSucceeded = false

    try
    (
        undo "Remove Unused Multi/Sub Slots" on
        (
            if compactIDs and idMaps.count > 0 do DMM_RemapAssignments assignments idMaps
            parentMaterial.numsubs = remainingMaterials.count

            for newSlotIndex = 1 to remainingMaterials.count do
            (
                parentMaterial.materialList[newSlotIndex] = remainingMaterials[newSlotIndex]
                parentMaterial.materialIDList[newSlotIndex] = remainingIDs[newSlotIndex]
                try (parentMaterial.names[newSlotIndex] = remainingNames[newSlotIndex]) catch()
                try (parentMaterial.mapEnabled[newSlotIndex] = remainingEnabledStates[newSlotIndex]) catch()
            )

            notifyDependents parentMaterial partID:#all
            operationSucceeded = true
        )
    )
    catch (operationSucceeded = false)

    if not operationSucceeded then return #(false, 0, protectedLastSlotCount, "スロットの削除に失敗しました。", false)

    #(true, removedCount, protectedLastSlotCount, "", compactIDs)
)

fn DMM_RemoveUnusedSlotsFromMulti parentMaterial selectedSlotIndices:undefined =
(
    if parentMaterial == undefined or not (DMM_IsMulti parentMaterial) then return #(false, 0, 0, 0, "Multi/Subが見つかりません。")

    local removeSlotIndices = #()
    local usedSlotCount = 0

    for slotIndex = 1 to parentMaterial.materialList.count do
    (
        local shouldCheck = selectedSlotIndices == undefined or (findItem selectedSlotIndices slotIndex) > 0

        if shouldCheck do
        (
            local materialID = parentMaterial.materialIDList[slotIndex]

            if DMM_IsMultiSlotIDUsed parentMaterial materialID then
                usedSlotCount += 1
            else
                append removeSlotIndices slotIndex
        )
    )

    local removeResult = DMM_RemoveMultiSlotIndicesPreserveIDs parentMaterial removeSlotIndices
    #(removeResult[1], removeResult[2], usedSlotCount, removeResult[3], removeResult[4], removeResult[5])
)

fn DMM_CollectAssignedMultiMaterials =
(
    local multiMaterials = #()
    local allMaterials = #()

    for rootMaterial in DMM_GetAssignedRootMaterials() do
    (
        DMM_AppendMaterialTree rootMaterial allMaterials
    )

    for materialValue in allMaterials where DMM_IsMulti materialValue do
    (
        DMM_AppendUniqueReference multiMaterials materialValue
    )

    multiMaterials
)

fn DMM_RemoveAllUnusedMultiSlots =
(
    local removedCount = 0
    local usedSlotCount = 0
    local protectedLastSlotCount = 0
    local failedCount = 0
    local compactedMaterialCount = 0

    for parentMaterial in DMM_CollectAssignedMultiMaterials() do
    (
        local result = DMM_RemoveUnusedSlotsFromMulti parentMaterial

        if result[1] then
        (
            removedCount += result[2]
            usedSlotCount += result[3]
            protectedLastSlotCount += result[4]
            if result[6] do compactedMaterialCount += 1
        )
        else
        (
            failedCount += 1
        )
    )

    redrawViews()
    #(failedCount == 0, removedCount, usedSlotCount, protectedLastSlotCount, failedCount, compactedMaterialCount)
)

-- Define the nested-row helper before DMM_AddRowsRecursive.
-- MAXScript resolves a not-yet-defined function name inside a function body as
-- an undefined local value, which caused the runtime error on nested Multi/Subs.
fn DMM_AddNestedRowsOnly multiMat rootMat parentDepth usedCount visited =
(
    if multiMat == undefined then return false
    if (findItem visited multiMat) > 0 then return false

    append visited multiMat

    local sortedSubItems = DMM_GetSortedSubItems multiMat usedCount

    for sortItem in sortedSubItems do
    (
        local slotIndex = sortItem.slotIndex
        local subMat = sortItem.mat
        local subID = sortItem.materialID

        local slotUsedCount = DMM_GetMultiSlotUsageCount multiMat subID
        append DMM_Rows (DMM_RowData mat:subMat parentMat:multiMat rootMat:rootMat slotIndex:slotIndex materialID:subID depth:(parentDepth + 1) usedCount:slotUsedCount)

        if subMat != undefined and DMM_IsMulti subMat do
        (
            DMM_AddNestedRowsOnly subMat rootMat (parentDepth + 1) usedCount visited
        )
    )

    true
)

fn DMM_AddRowsRecursive mat parentMat rootMat depth usedCount visited:#() =
(
    if mat == undefined then return false
    if (findItem visited mat) > 0 then return false

    append visited mat
    append DMM_Rows (DMM_RowData mat:mat parentMat:parentMat rootMat:rootMat depth:depth usedCount:usedCount)

    if DMM_IsMulti mat do
    (
        local sortedSubItems = DMM_GetSortedSubItems mat usedCount

        for sortItem in sortedSubItems do
        (
            local slotIndex = sortItem.slotIndex
            local subMat = sortItem.mat
            local subID = sortItem.materialID

            local slotUsedCount = DMM_GetMultiSlotUsageCount mat subID
            append DMM_Rows (DMM_RowData mat:subMat parentMat:mat rootMat:rootMat slotIndex:slotIndex materialID:subID depth:(depth + 1) usedCount:slotUsedCount)

            if subMat != undefined and DMM_IsMulti subMat do
            (
                DMM_AddNestedRowsOnly subMat rootMat (depth + 1) usedCount visited
            )
        )
    )

    true
)

rollout DiGiMaterialManager_Rollout "DiGi Material Manager" width:1320 height:840
(
    label lblNameView "マテリアル一覧" pos:[10,8] width:150 height:18
    dotNetControl lvMaterials "System.Windows.Forms.ListView" pos:[10,30] width:565 height:800

    label lblMaterialStats "総マテリアル数: 0    使用マテリアル数: 0    未使用マテリアル数: 0    マルチマテリアル数: 0" pos:[590,10] width:720 height:18
    label lblColorView "Colorパレット" pos:[590,37] width:80 height:18
    checkbox chkHideMultiInPalette "マルチサブを非表示" pos:[675,36] width:130 height:18 checked:true
    button btnPaletteSave "配置保存" pos:[810,30] width:75 height:25
    button btnPaletteLoad "保存配置" pos:[890,30] width:75 height:25
    button btnPaletteOriginal "元の順番" pos:[970,30] width:75 height:25
    button btnPaletteHue "色相順" pos:[1050,30] width:65 height:25
    button btnPaletteVisual "視覚順" pos:[1120,30] width:70 height:25
    button btnPaletteBrightness "明るさ順" pos:[1195,30] width:115 height:25

    dotNetControl dgvColors "System.Windows.Forms.DataGridView" pos:[590,60] width:720 height:300

    groupBox grpSelectedInfo "選択中のマテリアル" pos:[590,365] width:720 height:55
    label lblSelectedInfo1 "Name: -    Color: -" pos:[605,378] width:305 height:16
    label lblSelectedInfo2 "Type: -    ID: -    Usage: -" pos:[605,400] width:210 height:16
    button btnTemporaryColorSnapshot "色を一時保存" pos:[915,375] width:90 height:21
    button btnRestoreTemporaryColors "保存色に戻す" pos:[1010,375] width:90 height:21 enabled:false
    button btnFlashColorLocations "場所確認" pos:[1105,375] width:80 height:21
    button btnApplyColorGradient "グラデーション" pos:[1190,375] width:115 height:21
    spinner spnEditRed "R:" pos:[820,399] width:75 height:18 range:[0,255,255] type:#integer fieldWidth:45
    spinner spnEditGreen "G:" pos:[900,399] width:75 height:18 range:[0,255,255] type:#integer fieldWidth:45
    spinner spnEditBlue "B:" pos:[980,399] width:75 height:18 range:[0,255,255] type:#integer fieldWidth:45
    button btnApplyNumericRGB "RGBを適用" pos:[1060,397] width:100 height:21

    button btnRefresh "リスト更新" pos:[590,430] width:110 height:30
    button btnRenameSelected "選択をRGB名に変換" pos:[710,430] width:160 height:30
    button btnRenameAll "すべてRGB名に変換" pos:[880,430] width:160 height:30
    checkbox chkKeepHierarchy "親子を見て並べる" pos:[1080,437] width:180 height:18 checked:false

    button btnShowInSlate "SMEで選択" pos:[590,465] width:140 height:28
    button btnSelectAssignedObjects "割り当てオブジェクトを選択" pos:[740,465] width:220 height:28
    button btnMergeSameName "同じ名前を結合" pos:[970,465] width:170 height:28
    button btnMergeSameBaseColor "同じBase Colorを結合" pos:[1150,465] width:170 height:28

    button btnMergeSelectedMaterials "選択した通常マテリアルを結合" pos:[590,500] width:720 height:28

    groupBox grpSimilarColor "似た色を結合" pos:[590,535] width:720 height:100
    spinner spnRGBDistance "RGB距離:" pos:[605,557] width:165 height:18 range:[0,442,8] type:#integer fieldWidth:55
    spinner spnRedTolerance "R差:" pos:[785,557] width:140 height:18 range:[0,255,0] type:#integer fieldWidth:55
    spinner spnGreenTolerance "G差:" pos:[940,557] width:140 height:18 range:[0,255,0] type:#integer fieldWidth:55
    spinner spnBlueTolerance "B差:" pos:[1095,557] width:140 height:18 range:[0,255,0] type:#integer fieldWidth:55
    label lblColorToleranceHint "同じTypeのみ。RGB距離を先に判定し、R/G/Bは1以上だけ追加制限します。すべて0なら同色のみ。" pos:[605,580] width:700 height:18
    button btnPreviewSimilarColor "選択との色差をログ表示" pos:[605,603] width:225 height:25
    button btnMergeSimilarToSelected "選択を基準に似た色を結合" pos:[840,603] width:230 height:25
    button btnAutoMergeSimilarColor "似た色を上から自動結合" pos:[1080,603] width:225 height:25

    groupBox grpMerge "マルチサブ結合" pos:[590,640] width:450 height:80
    checkbox chkMergeInstances "同一インスタンスのサブマテリアルをまとめる" pos:[605,665] width:270 height:18 checked:true
    checkbox chkMakeNecessaryUnique "必要なインスタンスをユニーク化して結合" pos:[605,690] width:270 height:18 checked:false
    button btnMerge "選択したマルチサブを結合" pos:[880,660] width:145 height:50

    groupBox grpMove "IDを上下に移動" pos:[1050,640] width:280 height:80
    button btnMoveUp "上へ" pos:[1070,665] width:110 height:35
    button btnMoveDown "下へ" pos:[1200,665] width:110 height:35

    groupBox grpCleanup "未使用スロット / マテリアル" pos:[590,725] width:720 height:55
    button btnDeleteSelectedSlots "選択スロット削除" pos:[600,740] width:125 height:28
    button btnDeleteAllUnusedSlots "未使用スロット一括" pos:[730,740] width:145 height:28
    button btnCompactSelectedIDs "選択ID欠番整理" pos:[880,740] width:125 height:28
    button btnDeleteUnused "未使用材質削除" pos:[1010,740] width:130 height:28
    checkbox chkDeleteUnusedAndClearUndo "Undo不可許可" pos:[1145,746] width:100 height:18 checked:true
    label lblCleanup "先に保存" pos:[1245,746] width:65 height:18

    dotNetControl txtLog "System.Windows.Forms.TextBox" pos:[590,785] width:720 height:45
    timer tmrLoadNumericRGB interval:150 active:false

    local imageList
    local selectionOrder = #()
    local isRefreshingList = false
    local colorRowOrder = #()
    local colorColumnCount = 30
    local isRefreshingPalette = false
    local isSyncingSelection = false
    local activeMaterialView = #name
    local colorDragStartX = 0
    local colorDragStartY = 0
    local isColorDragging = false
    local colorMouseIsDown = false
    local colorDragArmed = false
    local colorDragSelectedPositions = #()
    local colorStableSelectedPositions = #()
    local isColorLinearSelecting = false
    local colorSelectionAnchorPosition = 0
    local colorSelectionCurrentPosition = 0
    local skipSavedPaletteLoadOnce = false
    local temporaryColorMaterials = #()
    local temporaryColors = #()
    local hasTemporaryColorSnapshot = false

    fn MakeColorBitmap mat =
    (
        local baseColor = DMM_GetBaseColor mat
        local redValue = DMM_ClampColorChannel baseColor.r
        local greenValue = DMM_ClampColorChannel baseColor.g
        local blueValue = DMM_ClampColorChannel baseColor.b
        local bitmap = dotNetObject "System.Drawing.Bitmap" 20 20
        local graphicsClass = dotNetClass "System.Drawing.Graphics"
        local drawingColor = dotNetClass "System.Drawing.Color"
        local graphics = graphicsClass.FromImage bitmap

        if DMM_IsMulti mat then
        (
            graphics.Clear (drawingColor.FromArgb 255 55 55 55)
            local multiPen = dotNetObject "System.Drawing.Pen" drawingColor.OrangeRed 3.0
            graphics.DrawLine multiPen 4 4 16 16
            graphics.DrawLine multiPen 16 4 4 16
            multiPen.Dispose()
        )
        else
        (
            graphics.Clear (drawingColor.FromArgb 255 redValue greenValue blueValue)
        )

        graphics.Dispose()
        bitmap
    )

    fn MaterialTypeText mat =
    (
        if mat == undefined then "Empty" else ((classOf mat) as string)
    )

    fn IndentedMaterialName row =
    (
        local indent = ""
        if chkKeepHierarchy.checked do
        (
            for index = 1 to row.depth do indent += "    "
        )

        if row.mat == undefined then
            (indent + "<Empty>")
        else if DMM_IsMulti row.mat then
            (indent + "[Multi] " + row.mat.name)
        else
            (indent + row.mat.name)
    )

    fn AddListRow row =
    (
        local imageIndex = imageList.Images.Count
        imageList.Images.Add (MakeColorBitmap row.mat)

        local item = lvMaterials.Items.Add (IndentedMaterialName row)
        item.ImageIndex = imageIndex
        item.SubItems.Add (MaterialTypeText row.mat)

        local sourceRowCount = 0
        if row.sourceRows != undefined do sourceRowCount = row.sourceRows.count

        if sourceRowCount > 1 then
            item.SubItems.Add "複数"
        else if row.slotIndex > 0 then
            item.SubItems.Add (row.materialID as string)
        else
            item.SubItems.Add "-"

        if row.usedCount > 0 then
            item.SubItems.Add ((row.usedCount as string) + " object(s)")
        else
            item.SubItems.Add "未使用"

        item
    )

    fn ClearSelectedMaterialInfo =
    (
        lblSelectedInfo1.text = "Name: -    Color: -"
        lblSelectedInfo2.text = "Type: -    ID: -    Usage: -"
    )

    fn SelectedMaterialIDText row =
    (
        local sourceRowCount = 0
        if row.sourceRows != undefined do sourceRowCount = row.sourceRows.count

        if sourceRowCount > 1 then
            "複数"
        else if row.slotIndex > 0 then
            (row.materialID as string)
        else
            "-"
    )

    fn SelectedMaterialUsageText row =
    (
        if row.usedCount > 0 then
            ((row.usedCount as string) + " object(s)")
        else
            "未使用"
    )

    fn UpdateSelectedMaterialInfo row =
    (
        if row == undefined then
        (
            ClearSelectedMaterialInfo()
        )
        else
        (
            local materialName = if row.mat == undefined then "<Empty>" else row.mat.name
            local colorText = if DMM_IsMulti row.mat then "<Multi>" else (DMM_RGBText row.mat)
            lblSelectedInfo1.text = "Name: " + materialName + "    Color: " + colorText
            lblSelectedInfo2.text = "Type: " + (MaterialTypeText row.mat)
            lblSelectedInfo2.text += "    ID: " + (SelectedMaterialIDText row)
            lblSelectedInfo2.text += "    Usage: " + (SelectedMaterialUsageText row)
        )
    )

    fn IsPaletteRowVisible row =
    (
        not (chkHideMultiInPalette.checked and DMM_IsMulti row.mat)
    )

    fn GetVisiblePaletteRowCount =
    (
        local visibleCount = 0
        for row in DMM_Rows where (IsPaletteRowVisible row) do visibleCount += 1
        visibleCount
    )

    fn ResetColorRowOrder =
    (
        colorRowOrder = #()
        for rowIndex = 1 to DMM_Rows.count where (IsPaletteRowVisible DMM_Rows[rowIndex]) do append colorRowOrder rowIndex
    )

    fn BuildSavedPaletteEntry row = #(
        DMM_GetPaletteMaterialKey row.mat createIfMissing:true,
        DMM_GetPaletteMaterialKey row.parentMat createIfMissing:true,
        DMM_GetPaletteMaterialKey row.rootMat createIfMissing:true,
        row.slotIndex,
        row.materialID
    )

    fn SavedEntryMatchesRow entry row exactMatch:true =
    (
        if entry == undefined then return false
        if entry.count < 5 then return false

        if exactMatch then
        (
            entry[1] == (DMM_GetPaletteMaterialKey row.mat) and
            entry[2] == (DMM_GetPaletteMaterialKey row.parentMat) and
            entry[3] == (DMM_GetPaletteMaterialKey row.rootMat) and
            entry[4] == row.slotIndex and
            entry[5] == row.materialID
        )
        else
        (
            entry[1] != "__DMM_UNDEFINED__" and entry[1] == (DMM_GetPaletteMaterialKey row.mat)
        )
    )

    fn FindPaletteRowForSavedEntry entry usedRows =
    (
        for rowIndex = 1 to DMM_Rows.count do
        (
            if (not usedRows[rowIndex]) and (IsPaletteRowVisible DMM_Rows[rowIndex]) and (SavedEntryMatchesRow entry DMM_Rows[rowIndex] exactMatch:true) do return rowIndex
        )

        for rowIndex = 1 to DMM_Rows.count do
        (
            if (not usedRows[rowIndex]) and (IsPaletteRowVisible DMM_Rows[rowIndex]) and (SavedEntryMatchesRow entry DMM_Rows[rowIndex] exactMatch:false) do return rowIndex
        )

        0
    )

    fn SaveColorPaletteOrder =
    (
        DMM_SavedPaletteOrder = #()

        for sourceRowIndex in colorRowOrder do
        (
            if sourceRowIndex >= 1 and sourceRowIndex <= DMM_Rows.count do append DMM_SavedPaletteOrder (BuildSavedPaletteEntry DMM_Rows[sourceRowIndex])
        )

        #(true, (DMM_SavedPaletteOrder.count as string) + "色のColor配置をシーンに保存しました。.maxファイルも保存してください。")
    )

    fn ColorPositionFromCell rowIndex columnIndex =
    (
        local position = (rowIndex * colorColumnCount) + columnIndex + 1
        if position >= 1 and position <= colorRowOrder.count then position else 0
    )

    fn GetSelectedColorPositions =
    (
        local positions = #()

        for index = 0 to (dgvColors.SelectedCells.Count - 1) do
        (
            local cell = dgvColors.SelectedCells.Item[index]
            local position = ColorPositionFromCell cell.RowIndex cell.ColumnIndex
            if position > 0 and (findItem positions position) == 0 do append positions position
        )

        sort positions
        positions
    )

    fn GetSelectedColorRowIndices =
    (
        local rowIndices = #()
        for position in GetSelectedColorPositions() do append rowIndices colorRowOrder[position]
        rowIndices
    )

    fn SetLinearColorSelection startPosition endPosition =
    (
        if startPosition < 1 or endPosition < 1 then return false
        if startPosition > colorRowOrder.count or endPosition > colorRowOrder.count then return false

        local firstPosition = amin startPosition endPosition
        local lastPosition = amax startPosition endPosition
        local previousSyncState = isSyncingSelection

        isSyncingSelection = true
        dgvColors.SuspendLayout()
        dgvColors.ClearSelection()

        for position = firstPosition to lastPosition do
        (
            local gridRowIndex = (floor (((position - 1) as float) / colorColumnCount)) as integer
            local gridColumnIndex = mod (position - 1) colorColumnCount
            dgvColors.Rows.Item[gridRowIndex].Cells.Item[gridColumnIndex].Selected = true
        )

        for itemIndex = 0 to (lvMaterials.Items.Count - 1) do
        (
            if lvMaterials.Items.Item[itemIndex].Selected do lvMaterials.Items.Item[itemIndex].Selected = false
        )
        selectionOrder = #()

        dgvColors.ResumeLayout()
        isSyncingSelection = previousSyncState
        activeMaterialView = #color

        -- 選択情報と各処理の基準は、必ず左上の色にする。
        UpdateSelectedMaterialInfo DMM_Rows[colorRowOrder[firstPosition]]
        txtLog.Text = "Colorパレット: " + ((lastPosition - firstPosition + 1) as string) + " color(s) selected / 左上から順番 / 選択済みの色をドラッグで配置変更"
        dgvColors.Invalidate()
        true
    )

    fn ApplyGradientToSelectedColors =
    (
        local selectedRowIndices = GetSelectedColorRowIndices()
        if selectedRowIndices.count < 3 then return #(false, "グラデーションには3色以上を選択してください。先頭色と末尾色が両端になります。")

        local selectedMaterials = #()

        for rowIndex in selectedRowIndices do
        (
            local rowMaterial = DMM_Rows[rowIndex].mat

            if rowMaterial == undefined or DMM_IsMulti rowMaterial then
            (
                return #(false, "EmptyまたはMulti/Subを含めず、通常マテリアルだけを選択してください。")
            )

            if (findItem selectedMaterials rowMaterial) > 0 then
            (
                return #(false, "同じマテリアルインスタンスが複数含まれています。異なるマテリアルだけを選択してください。")
            )

            if not (DMM_GetBaseColorInfo rowMaterial)[1] then
            (
                return #(false, rowMaterial.name + " のBase Colorを取得できません。")
            )

            append selectedMaterials rowMaterial
        )

        local startColor = DMM_GetBaseColor selectedMaterials[1]
        local endColor = DMM_GetBaseColor selectedMaterials[selectedMaterials.count]
        local changedCount = 0
        local failedMaterialName = ""
        local startedHold = false
        local operationFailed = false

        try
        (
            -- Rollout/.NET event handlers are not always inside the macroScript
            -- auto-undo context. Start the 3ds Max hold explicitly so material
            -- ParamBlock changes register restore objects.
            if not (theHold.Holding()) do
            (
                theHold.Begin()
                startedHold = true
            )

            for materialIndex = 2 to (selectedMaterials.count - 1) do
            (
                local amount = ((materialIndex - 1) as float) / ((selectedMaterials.count - 1) as float)
                local redValue = DMM_ClampColorChannel (startColor.r + ((endColor.r - startColor.r) * amount))
                local greenValue = DMM_ClampColorChannel (startColor.g + ((endColor.g - startColor.g) * amount))
                local blueValue = DMM_ClampColorChannel (startColor.b + ((endColor.b - startColor.b) * amount))
                local gradientColor = color redValue greenValue blueValue

                if DMM_SetBaseColor selectedMaterials[materialIndex] gradientColor then
                (
                    notifyDependents selectedMaterials[materialIndex] partID:#all
                    changedCount += 1
                )
                else if failedMaterialName == "" do
                (
                    failedMaterialName = selectedMaterials[materialIndex].name
                )
            )

            if startedHold do theHold.Accept "Material Color Gradient"
        )
        catch
        (
            operationFailed = true
            if startedHold and theHold.Holding() do theHold.Cancel()
        )

        if operationFailed then return #(false, "グラデーション処理に失敗しました。変更内容は取り消しました。")

        if failedMaterialName != "" then
        (
            return #(false, failedMaterialName + " のBase Colorを変更できませんでした。変更可能な材質はUndoで戻せます。")
        )

        redrawViews()
        #(true, (selectedMaterials.count as string) + "色を、先頭と末尾の色からグラデーション化しました。中間変更: " + (changedCount as string))
    )

    fn PopulateColorGrid selectedRowIndices:#() =
    (
        isRefreshingPalette = true
        dgvColors.SuspendLayout()
        dgvColors.Rows.Clear()

        local requiredRowCount = 0
        if colorRowOrder.count > 0 do requiredRowCount = (ceil ((colorRowOrder.count as float) / colorColumnCount)) as integer

        for rowNumber = 1 to requiredRowCount do
        (
            local addedRowIndex = dgvColors.Rows.Add()
            dgvColors.Rows.Item[addedRowIndex].Height = 25
        )

        dgvColors.ClearSelection()

        local drawingColor = dotNetClass "System.Drawing.Color"

        for position = 1 to colorRowOrder.count do
        (
            local gridRowIndex = (floor (((position - 1) as float) / colorColumnCount)) as integer
            local gridColumnIndex = mod (position - 1) colorColumnCount
            local sourceRowIndex = colorRowOrder[position]
            local sourceRow = DMM_Rows[sourceRowIndex]
            local baseColor = DMM_GetBaseColor sourceRow.mat
            local displayColor = if DMM_IsMulti sourceRow.mat then
                (drawingColor.FromArgb 255 55 55 55)
            else
                (drawingColor.FromArgb 255 (DMM_ClampColorChannel baseColor.r) (DMM_ClampColorChannel baseColor.g) (DMM_ClampColorChannel baseColor.b))
            local cell = dgvColors.Rows.Item[gridRowIndex].Cells.Item[gridColumnIndex]

            cell.Value = ""
            cell.Style.BackColor = displayColor
            cell.Style.SelectionBackColor = displayColor
            cell.Style.ForeColor = displayColor
            cell.Style.SelectionForeColor = displayColor

            if (findItem selectedRowIndices sourceRowIndex) > 0 do cell.Selected = true
        )

        dgvColors.ResumeLayout()
        dgvColors.Invalidate()
        colorStableSelectedPositions = GetSelectedColorPositions()
        isRefreshingPalette = false
    )

    -- MAXScriptのロールアウト内関数は、呼び出し先を先に定義しておく必要がある。
    fn ApplyPaletteVisibility =
    (
        local visibleOrder = #()

        for rowIndex in colorRowOrder do
        (
            if (rowIndex >= 1) and (rowIndex <= DMM_Rows.count) and (IsPaletteRowVisible DMM_Rows[rowIndex]) do append visibleOrder rowIndex
        )

        for rowIndex = 1 to DMM_Rows.count do
        (
            if (IsPaletteRowVisible DMM_Rows[rowIndex]) and ((findItem visibleOrder rowIndex) == 0) do append visibleOrder rowIndex
        )

        colorRowOrder = visibleOrder
        PopulateColorGrid()
    )

    fn LoadSavedColorPaletteOrder quiet:false =
    (
        if DMM_SavedPaletteOrder == undefined or DMM_SavedPaletteOrder.count == 0 then
        (
            ResetColorRowOrder()
            PopulateColorGrid()
            return #(false, "保存済みのColor配置はありません。")
        )

        local restoredOrder = #()
        local usedRows = #()
        for rowIndex = 1 to DMM_Rows.count do append usedRows false

        for savedEntry in DMM_SavedPaletteOrder do
        (
            local matchedRowIndex = FindPaletteRowForSavedEntry savedEntry usedRows
            if matchedRowIndex > 0 do
            (
                append restoredOrder matchedRowIndex
                usedRows[matchedRowIndex] = true
            )
        )

        for rowIndex = 1 to DMM_Rows.count do
        (
            if (not usedRows[rowIndex]) and (IsPaletteRowVisible DMM_Rows[rowIndex]) do append restoredOrder rowIndex
        )

        colorRowOrder = restoredOrder

        -- 結合・削除で消えたマテリアルの保存キーを取り除き、現在の配置に更新する。
        DMM_SavedPaletteOrder = #()
        for sourceRowIndex in colorRowOrder do append DMM_SavedPaletteOrder (BuildSavedPaletteEntry DMM_Rows[sourceRowIndex])

        PopulateColorGrid()
        #(true, (restoredOrder.count as string) + "色の保存配置を復元しました。")
    )

    fn SortColorPalette sortMode =
    (
        local selectedRows = GetSelectedColorRowIndices()
        local sortItems = #()

        for position = 1 to colorRowOrder.count do
        (
            local sourceRowIndex = colorRowOrder[position]
            local sortValues = DMM_GetColorSortValues DMM_Rows[sourceRowIndex].mat
            local perceptualValues = #(0.0, 0.0, 0.0, 0)
            if sortMode == #visual do perceptualValues = DMM_GetPerceptualColorSortValues DMM_Rows[sourceRowIndex].mat
            append sortItems (DMM_ColorSortItem rowIndex:sourceRowIndex hue:sortValues[1] saturation:sortValues[2] brightness:sortValues[3] perceptualHue:perceptualValues[1] perceptualChroma:perceptualValues[2] perceptualLightness:perceptualValues[3] perceptualHueBand:perceptualValues[4] originalPosition:position)
        )

        if sortItems.count > 1 do qsort sortItems DMM_CompareColorSortItems sortMode:sortMode

        colorRowOrder = #()
        for sortItem in sortItems do append colorRowOrder sortItem.rowIndex
        PopulateColorGrid selectedRowIndices:selectedRows
    )

    fn MoveSelectedColorsBefore targetPosition selectedPositions:undefined =
    (
        if selectedPositions == undefined do selectedPositions = GetSelectedColorPositions()
        if selectedPositions.count == 0 then return #(false, "移動する色を選択してください。", false)
        if targetPosition < 1 do targetPosition = 1
        if targetPosition > (colorRowOrder.count + 1) do targetPosition = colorRowOrder.count + 1
        if targetPosition <= colorRowOrder.count and (findItem selectedPositions targetPosition) > 0 then
        (
            return #(false, "選択中の色と同じ位置へは挿入できません。", false)
        )

        local selectedRows = #()
        for selectedPosition in selectedPositions do
        (
            append selectedRows DMM_Rows[colorRowOrder[selectedPosition]]
        )

        local parentMaterial = selectedRows[1].parentMat
        local selectedSlotIndices = #()
        local canMoveActualIDs = (parentMaterial != undefined)

        for row in selectedRows do
        (
            local hasHiddenInstances = (row.sourceRows != undefined) and (row.sourceRows.count > 1)
            if hasHiddenInstances or parentMaterial == undefined or row.parentMat != parentMaterial or row.rootMat != parentMaterial or row.slotIndex < 1 do canMoveActualIDs = false
            if (findItem selectedSlotIndices row.slotIndex) == 0 do append selectedSlotIndices row.slotIndex
        )

        local targetSlotIndex = 1
        if parentMaterial != undefined and DMM_IsMulti parentMaterial then
            targetSlotIndex = parentMaterial.materialList.count + 1
        else
            canMoveActualIDs = false

        if targetPosition >= 1 and targetPosition <= colorRowOrder.count do
        (
            local targetRow = DMM_Rows[colorRowOrder[targetPosition]]
            if canMoveActualIDs and targetRow.parentMat == parentMaterial and targetRow.rootMat == parentMaterial and targetRow.slotIndex > 0 then
                targetSlotIndex = targetRow.slotIndex
            else
                canMoveActualIDs = false
        )

        if canMoveActualIDs then
        (
            local actualResult = DMM_MoveMultiSlotsBefore parentMaterial selectedSlotIndices targetSlotIndex
            return #(actualResult[1], actualResult[2], actualResult[1])
        )

        -- IDを持たないルート材質や別マルチ間の移動は、パレットの表示順だけを変更する。
        local movingRows = #()
        local remainingRows = #()
        local removedBeforeTarget = 0

        for position = 1 to colorRowOrder.count do
        (
            if (findItem selectedPositions position) > 0 then
            (
                append movingRows colorRowOrder[position]
                if position < targetPosition do removedBeforeTarget += 1
            )
            else
            (
                append remainingRows colorRowOrder[position]
            )
        )

        local insertPosition = targetPosition - removedBeforeTarget
        if insertPosition < 1 do insertPosition = 1
        if insertPosition > (remainingRows.count + 1) do insertPosition = remainingRows.count + 1

        colorRowOrder = remainingRows
        for movingIndex = movingRows.count to 1 by -1 do
        (
            insertItem movingRows[movingIndex] colorRowOrder insertPosition
        )

        PopulateColorGrid selectedRowIndices:movingRows
        #(true, "Colorパレットの表示順を変更しました。この項目には共通のIDがないため、IDは変更していません。", false)
    )

    fn UpdateViewMode =
    (
        if colorRowOrder.count != GetVisiblePaletteRowCount() do
        (
            ResetColorRowOrder()
            PopulateColorGrid()
        )

        try (setControlPos DiGiMaterialManager_Rollout lvMaterials [10,30]) catch()
        try (setControlPos DiGiMaterialManager_Rollout dgvColors [590,60]) catch()
        try (showControl DiGiMaterialManager_Rollout lvMaterials true) catch()
        try (showControl DiGiMaterialManager_Rollout dgvColors true) catch()
        lvMaterials.Visible = true
        dgvColors.Visible = true
        lvMaterials.Enabled = true
        dgvColors.Enabled = true
        lvMaterials.Refresh()
        dgvColors.Refresh()
    )

    fn UpdateSortHeaders =
    (
        local headerNames = #("Name", "Type", "ID", "Usage")

        for columnIndex = 0 to 3 do
        (
            local headerText = headerNames[columnIndex + 1]

            if DMM_SortColumn == columnIndex do
            (
                if DMM_SortAscending then
                    headerText += " ▲"
                else
                    headerText += " ▼"
            )

            lvMaterials.Columns.Item[columnIndex].Text = headerText
        )
    )

    fn RefreshMaterialList =
    (
        isRefreshingList = true
        selectionOrder = #()
        DMM_RebuildMaterialIDUsageCache()
        lvMaterials.BeginUpdate()
        lvMaterials.Items.Clear()
        imageList.Images.Clear()
        DMM_Rows = #()

        local roots = DMM_GetDisplayRootMaterials()
        roots = DMM_GetSortedRootMaterials roots

        for rootMat in roots do
        (
            local usedCount = (DMM_GetNodesUsingRootMaterial rootMat).count
            DMM_AddRowsRecursive rootMat undefined rootMat 0 usedCount
        )

        local originalRowCount = DMM_Rows.count

        if not chkKeepHierarchy.checked do
        (
            if DMM_SortColumn >= 0 do
            (
                DMM_Rows = DMM_GetRowsSortedIgnoringHierarchy DMM_Rows DMM_SortColumn
            )

            DMM_Rows = DMM_GetRowsWithoutRepeatedInstances DMM_Rows
        )

        local hiddenInstanceCount = originalRowCount - DMM_Rows.count
        local hiddenMultiCount = 0

        if chkHideMultiInPalette.checked do
        (
            local rowCountBeforeMultiFilter = DMM_Rows.count
            DMM_Rows = for row in DMM_Rows where (not (DMM_IsMulti row.mat)) collect row
            hiddenMultiCount = rowCountBeforeMultiFilter - DMM_Rows.count
        )

        for row in DMM_Rows do AddListRow row

        if skipSavedPaletteLoadOnce then
        (
            skipSavedPaletteLoadOnce = false
            ResetColorRowOrder()
            PopulateColorGrid()
        )
        else
        (
            LoadSavedColorPaletteOrder quiet:true
        )

        lvMaterials.EndUpdate()

        local statistics = DMM_GetMaterialStatistics()
        lblMaterialStats.text = "総マテリアル数: " + (statistics[1] as string)
        lblMaterialStats.text += "    使用マテリアル数: " + (statistics[2] as string)
        lblMaterialStats.text += "    未使用マテリアル数: " + (statistics[3] as string)
        lblMaterialStats.text += "    マルチマテリアル数: " + (statistics[4] as string)

        txtLog.Text = (roots.count as string) + " root material(s), " + (DMM_Rows.count as string) + " row(s)"
        if hiddenInstanceCount > 0 do txtLog.Text += " / 同一インスタンス " + (hiddenInstanceCount as string) + "行を非表示"
        if hiddenMultiCount > 0 do txtLog.Text += " / マルチサブ " + (hiddenMultiCount as string) + "行を非表示"
        txtLog.Text += " / 列見出しクリックでソート"
        ClearSelectedMaterialInfo()
        isRefreshingList = false
    )

    fn GetSelectedRows =
    (
        if activeMaterialView == #color then
        (
            local colorSelectedRows = #()

            -- SelectedCellsやCurrentCellの内部順には依存せず、パレットの
            -- 左上から右、次の段へという表示順で必ず返す。
            for position in GetSelectedColorPositions() do
            (
                local sourceRowIndex = colorRowOrder[position]
                append colorSelectedRows DMM_Rows[sourceRowIndex]
            )

            return colorSelectedRows
        )

        local selectedRows = #()
        local addedRowIndices = #()

        for zeroBasedRowIndex in selectionOrder do
        (
            if zeroBasedRowIndex >= 0 and zeroBasedRowIndex < lvMaterials.Items.Count do
            (
                local listItem = lvMaterials.Items.Item[zeroBasedRowIndex]

                if listItem.Selected do
                (
                    local rowIndex = zeroBasedRowIndex + 1
                    if rowIndex <= DMM_Rows.count do
                    (
                        append selectedRows DMM_Rows[rowIndex]
                        append addedRowIndices zeroBasedRowIndex
                    )
                )
            )
        )

        for index = 0 to (lvMaterials.SelectedIndices.Count - 1) do
        (
            local zeroBasedRowIndex = lvMaterials.SelectedIndices.Item[index]

            if (findItem addedRowIndices zeroBasedRowIndex) == 0 do
            (
                local rowIndex = zeroBasedRowIndex + 1
                if rowIndex >= 1 and rowIndex <= DMM_Rows.count do append selectedRows DMM_Rows[rowIndex]
            )
        )

        selectedRows
    )

    fn GetSelectedMaterials includeUndefined:false =
    (
        local selectedMaterials = #()

        for row in GetSelectedRows() do
        (
            if includeUndefined or row.mat != undefined do DMM_AppendUniqueReference selectedMaterials row.mat
        )

        selectedMaterials
    )

    fn LoadNumericRGBFromSingleSelection =
    (
        local selectedRows = GetSelectedRows()
        if selectedRows.count != 1 then return false

        local selectedMaterial = selectedRows[1].mat
        if selectedMaterial == undefined or DMM_IsMulti selectedMaterial then return false

        local colorInfo = DMM_GetBaseColorInfo selectedMaterial
        if not colorInfo[1] then return false

        -- Run only after the mouse interaction is complete. Updating rollout
        -- spinners from DataGridView.SelectionChanged can re-enter the .NET
        -- selection event and collapse a multi-selection.
        spnEditRed.value = DMM_ClampColorChannel colorInfo[2].r
        spnEditGreen.value = DMM_ClampColorChannel colorInfo[2].g
        spnEditBlue.value = DMM_ClampColorChannel colorInfo[2].b
        true
    )

    fn GetActiveSlateView =
    (
        try (sme.Open()) catch()

        local viewCount = 0
        try (viewCount = sme.GetNumViews()) catch()

        if viewCount == 0 do
        (
            local createdViewIndex = 0
            try (createdViewIndex = sme.CreateView "DiGi Material Manager") catch()

            if createdViewIndex > 0 do
            (
                try (sme.activeView = createdViewIndex) catch()
                try (viewCount = sme.GetNumViews()) catch()
            )
        )

        if viewCount == 0 then return undefined

        local viewIndex = 1
        try (viewIndex = sme.activeView) catch()
        if viewIndex == undefined do viewIndex = 1
        if viewIndex < 1 or viewIndex > viewCount do viewIndex = 1
        try (sme.activeView = viewIndex) catch()

        local view = undefined
        try (view = sme.GetView viewIndex) catch()
        view
    )

    fn SelectMaterialsInSlate =
    (
        local selectedMaterials = GetSelectedMaterials()
        if selectedMaterials.count == 0 then return #(false, "SMEで選択するマテリアルをリストから選択してください。")

        local view = GetActiveSlateView()
        if view == undefined then return #(false, "スレートマテリアルエディタのビューを取得できませんでした。")

        local createdCount = 0

        for selectedMaterial in selectedMaterials do
        (
            local slateNode = undefined
            try (slateNode = view.GetNodeByRef selectedMaterial) catch()

            if slateNode == undefined do
            (
                local nodePosition = [(createdCount * 220.0), 0.0]
                try (slateNode = view.CreateNode selectedMaterial &nodePosition) catch()
                if slateNode != undefined do createdCount += 1
            )
        )

        try (view.SetSelectedNodes selectedMaterials) catch()
        try (sme.SetMtlInParamEditor selectedMaterials[1]) catch()
        try (view.ZoomExtents type:#selected) catch()
        try (view.SetFocus()) catch()

        local selectedNodeCount = 0
        try (selectedNodeCount = (view.GetSelectedNodes()).count) catch()

        if selectedNodeCount == 0 then
            #(false, "SMEでマテリアルノードを選択できませんでした。")
        else
            #(true, (selectedNodeCount as string) + "個のマテリアルをSMEで選択しました。新規ノード: " + (createdCount as string))
    )

    fn SelectObjectsUsingSelectedRows =
    (
        local selectedRows = GetSelectedRows()
        if selectedRows.count == 0 then return #(false, "割り当てオブジェクトを探すマテリアルをリストから選択してください。")

        local nodesToSelect = #()

        for row in selectedRows do
        (
            local sourceRows = #(row)
            if (row.sourceRows != undefined) and (row.sourceRows.count > 0) do sourceRows = row.sourceRows

            for sourceRow in sourceRows do
            (
                if sourceRow.rootMat != undefined do
                (
                    local rootNodes = DMM_GetNodesUsingRootMaterial sourceRow.rootMat

                    if sourceRow.slotIndex > 0 and sourceRow.materialID > 0 then
                    (
                        for node in rootNodes where (DMM_NodeUsesMaterialID node sourceRow.materialID) do
                        (
                            DMM_AppendUniqueReference nodesToSelect node
                        )
                    )
                    else
                    (
                        for node in rootNodes do DMM_AppendUniqueReference nodesToSelect node
                    )
                )
            )
        )

        if nodesToSelect.count == 0 then return #(false, "選択したマテリアルを割り当てているオブジェクトはありません。")

        try (select nodesToSelect) catch()
        redrawViews()
        #(true, (nodesToSelect.count as string) + "個のオブジェクトを選択しました。")
    )

    fn FlashObjectsUsingSelectedColors =
    (
        local selectedRows = GetSelectedRows()
        if selectedRows.count == 0 then return #(false, "場所を確認する色をColorパレットまたは一覧から選択してください。")

        local nodesToFlash = #()
        local hiddenNodeCount = 0

        for row in selectedRows do
        (
            local sourceRows = #(row)
            if row.sourceRows != undefined and row.sourceRows.count > 0 do sourceRows = row.sourceRows

            for sourceRow in sourceRows do
            (
                if sourceRow.rootMat != undefined do
                (
                    local rootNodes = DMM_GetNodesUsingRootMaterial sourceRow.rootMat

                    for node in rootNodes do
                    (
                        local usesSelectedColor = true
                        if sourceRow.slotIndex > 0 and sourceRow.materialID > 0 do
                        (
                            usesSelectedColor = DMM_NodeUsesMaterialID node sourceRow.materialID
                        )

                        if usesSelectedColor and (findItem nodesToFlash node) == 0 do
                        (
                            local nodeIsHidden = false
                            try (nodeIsHidden = node.isHidden) catch()

                            if nodeIsHidden then
                                hiddenNodeCount += 1
                            else
                                append nodesToFlash node
                        )
                    )
                )
            )
        )

        if nodesToFlash.count == 0 then
        (
            local noResultText = "選択色を表示中のオブジェクトでは確認できませんでした。"
            if hiddenNodeCount > 0 do noResultText += " 非表示オブジェクト: " + (hiddenNodeCount as string)
            return #(false, noResultText)
        )

        try
        (
            for flashIndex = 1 to 3 do
            (
                flashNodes nodesToFlash
                forceCompleteRedraw()
            )
        )
        catch
        (
            return #(false, "ビューポートでの点滅表示に失敗しました。")
        )

        local resultText = (nodesToFlash.count as string) + "個のオブジェクトを点滅表示しました。"
        if hiddenNodeCount > 0 do resultText += " / 非表示のため対象外: " + (hiddenNodeCount as string)
        #(true, resultText)
    )

    fn ShowOperationResult result =
    (
        if result[1] then
            txtLog.Text = result[2]
        else
            messageBox result[2] title:"DiGi Material Manager"
    )

    on DiGiMaterialManager_Rollout open do
    (
        local formsView = dotNetClass "System.Windows.Forms.View"
        local formsBorder = dotNetClass "System.Windows.Forms.BorderStyle"
        local formsScrollBars = dotNetClass "System.Windows.Forms.ScrollBars"
        local gridSelectionMode = dotNetClass "System.Windows.Forms.DataGridViewSelectionMode"
        local gridColumnSortMode = dotNetClass "System.Windows.Forms.DataGridViewColumnSortMode"
        local gridScrollBars = dotNetClass "System.Windows.Forms.ScrollBars"
        local systemColors = dotNetClass "System.Drawing.SystemColors"

        lvMaterials.View = formsView.Details
        lvMaterials.FullRowSelect = true
        lvMaterials.MultiSelect = true
        lvMaterials.HideSelection = false
        lvMaterials.GridLines = true
        lvMaterials.OwnerDraw = true
        lvMaterials.BorderStyle = formsBorder.FixedSingle

        lvMaterials.Columns.Add "Name" 190
        lvMaterials.Columns.Add "Type" 160
        lvMaterials.Columns.Add "ID" 55
        lvMaterials.Columns.Add "Usage" 120

        imageList = dotNetObject "System.Windows.Forms.ImageList"
        imageList.ImageSize = dotNetObject "System.Drawing.Size" 20 20
        imageList.ColorDepth = (dotNetClass "System.Windows.Forms.ColorDepth").Depth32Bit
        lvMaterials.SmallImageList = imageList

        dgvColors.AllowUserToAddRows = false
        dgvColors.AllowUserToDeleteRows = false
        dgvColors.AllowUserToOrderColumns = false
        dgvColors.AllowUserToResizeColumns = false
        dgvColors.AllowUserToResizeRows = false
        dgvColors.AutoGenerateColumns = false
        dgvColors.ColumnHeadersVisible = false
        dgvColors.RowHeadersVisible = false
        dgvColors.MultiSelect = true
        dgvColors.ReadOnly = true
        dgvColors.SelectionMode = gridSelectionMode.CellSelect
        dgvColors.BorderStyle = formsBorder.FixedSingle
        dgvColors.BackgroundColor = (dotNetClass "System.Drawing.Color").Black
        dgvColors.DefaultCellStyle.BackColor = (dotNetClass "System.Drawing.Color").Black
        dgvColors.DefaultCellStyle.SelectionBackColor = (dotNetClass "System.Drawing.Color").Black
        dgvColors.GridColor = (dotNetClass "System.Drawing.Color").FromArgb 48 48 48
        dgvColors.ScrollBars = gridScrollBars.Vertical
        dgvColors.AllowDrop = true

        for columnIndex = 1 to colorColumnCount do
        (
            local paletteColumn = dotNetObject "System.Windows.Forms.DataGridViewTextBoxColumn"
            -- 30 columns x 24px fills the 740px palette width after borders
            -- and the vertical scrollbar, without changing the window size.
            paletteColumn.Width = 24
            paletteColumn.MinimumWidth = 20
            paletteColumn.SortMode = gridColumnSortMode.NotSortable
            dgvColors.Columns.Add paletteColumn
        )

        txtLog.Multiline = true
        txtLog.ReadOnly = true
        txtLog.WordWrap = true
        txtLog.ScrollBars = formsScrollBars.Vertical
        txtLog.BackColor = systemColors.Control

        UpdateSortHeaders()
        RefreshMaterialList()
        UpdateViewMode()
    )

    on lvMaterials SelectedIndexChanged args do
    (
        if (not isRefreshingList) and (not isSyncingSelection) do
        (
            activeMaterialView = #name
            isSyncingSelection = true
            dgvColors.ClearSelection()
            isSyncingSelection = false

            txtLog.Text = "名前リスト: " + (lvMaterials.SelectedIndices.Count as string) + " row(s) selected"

            local selectedRow = undefined
            if lvMaterials.FocusedItem != undefined do
            (
                local rowIndex = lvMaterials.FocusedItem.Index + 1
                if rowIndex >= 1 and rowIndex <= DMM_Rows.count do selectedRow = DMM_Rows[rowIndex]
            )
            UpdateSelectedMaterialInfo selectedRow
        )
    )

    on lvMaterials DrawColumnHeader args do
    (
        args.DrawDefault = true
    )

    on lvMaterials DrawSubItem args do
    (
        if args.ColumnIndex != 0 then
        (
            args.DrawDefault = true
        )
        else
        (
            local systemColors = dotNetClass "System.Drawing.SystemColors"
            local solidBrushClass = dotNetClass "System.Drawing.SolidBrush"
            local stringFormatClass = dotNetClass "System.Drawing.StringFormat"
            local stringAlignment = dotNetClass "System.Drawing.StringAlignment"
            local stringTrimming = dotNetClass "System.Drawing.StringTrimming"
            local rectangleFClass = dotNetClass "System.Drawing.RectangleF"
            local isSelected = args.Item.Selected
            local backgroundColor = if isSelected then systemColors.Highlight else systemColors.Window
            local textColor = if isSelected then systemColors.HighlightText else systemColors.WindowText
            local backgroundBrush = dotNetObject solidBrushClass backgroundColor
            local textBrush = dotNetObject solidBrushClass textColor
            local textFormat = dotNetObject stringFormatClass

            args.Graphics.FillRectangle backgroundBrush args.Bounds

            local imageIndex = args.Item.ImageIndex
            local imageX = args.Bounds.X + 2
            local imageY = args.Bounds.Y + ((args.Bounds.Height - imageList.ImageSize.Height) / 2)

            if imageIndex >= 0 and imageIndex < imageList.Images.Count do
            (
                -- ListViewの選択描画を通さず、色見本を元の色のまま描く。
                args.Graphics.DrawImage imageList.Images.Item[imageIndex] imageX imageY imageList.ImageSize.Width imageList.ImageSize.Height
            )

            textFormat.Alignment = stringAlignment.Near
            textFormat.LineAlignment = stringAlignment.Center
            textFormat.Trimming = stringTrimming.EllipsisCharacter

            local textX = imageX + imageList.ImageSize.Width + 4
            local textWidth = args.Bounds.Right - textX - 2
            local textBounds = dotNetObject rectangleFClass textX args.Bounds.Y textWidth args.Bounds.Height
            args.Graphics.DrawString args.SubItem.Text lvMaterials.Font textBrush textBounds textFormat

            backgroundBrush.Dispose()
            textBrush.Dispose()
            textFormat.Dispose()
        )
    )

    on dgvColors CellPainting args do
    (
        if args.RowIndex >= 0 and args.ColumnIndex >= 0 do
        (
            local position = ColorPositionFromCell args.RowIndex args.ColumnIndex

            if position > 0 then
            (
                local drawingColor = dotNetClass "System.Drawing.Color"
                local solidBrushClass = dotNetClass "System.Drawing.SolidBrush"
                local penClass = dotNetClass "System.Drawing.Pen"
                local sourceRowIndex = colorRowOrder[position]
                local sourceRow = DMM_Rows[sourceRowIndex]
                local isMultiCell = DMM_IsMulti sourceRow.mat
                local baseColor = DMM_GetBaseColor sourceRow.mat
                local displayColor = if isMultiCell then
                    (drawingColor.FromArgb 255 55 55 55)
                else
                    (drawingColor.FromArgb 255 (DMM_ClampColorChannel baseColor.r) (DMM_ClampColorChannel baseColor.g) (DMM_ClampColorChannel baseColor.b))
                local isSelected = false
                try (isSelected = dgvColors.Rows.Item[args.RowIndex].Cells.Item[args.ColumnIndex].Selected) catch()
                local fillBrush = dotNetObject solidBrushClass displayColor
                local borderColor = if isSelected then drawingColor.White else drawingColor.FromArgb 48 48 48
                local borderWidth = if isSelected then 3.0 else 1.0
                local borderPen = dotNetObject penClass borderColor borderWidth

                args.Graphics.FillRectangle fillBrush args.CellBounds
                args.Graphics.DrawRectangle borderPen args.CellBounds.X args.CellBounds.Y (args.CellBounds.Width - 1) (args.CellBounds.Height - 1)

                if isMultiCell do
                (
                    local multiPen = dotNetObject penClass drawingColor.OrangeRed 4.0
                    local margin = 7
                    args.Graphics.DrawLine multiPen (args.CellBounds.X + margin) (args.CellBounds.Y + margin) (args.CellBounds.Right - margin) (args.CellBounds.Bottom - margin)
                    args.Graphics.DrawLine multiPen (args.CellBounds.Right - margin) (args.CellBounds.Y + margin) (args.CellBounds.X + margin) (args.CellBounds.Bottom - margin)
                    multiPen.Dispose()
                )

                fillBrush.Dispose()
                borderPen.Dispose()
                args.Handled = true
            )
        )
    )

    on dgvColors SelectionChanged args do
    (
        if (not isRefreshingPalette) and (not isSyncingSelection) do
        (
            activeMaterialView = #color
            isSyncingSelection = true
            for itemIndex = 0 to (lvMaterials.Items.Count - 1) do
            (
                if lvMaterials.Items.Item[itemIndex].Selected do lvMaterials.Items.Item[itemIndex].Selected = false
            )
            selectionOrder = #()
            isSyncingSelection = false

            local selectedRow = undefined
            local selectedPositions = GetSelectedColorPositions()
            if selectedPositions.count > 0 do
            (
                local firstPosition = selectedPositions[1]
                selectedRow = DMM_Rows[colorRowOrder[firstPosition]]
            )

            UpdateSelectedMaterialInfo selectedRow
            txtLog.Text = "Colorパレット: " + (dgvColors.SelectedCells.Count as string) + " color(s) selected / 選択済みの色をドラッグで配置変更"
            dgvColors.Invalidate()
        )
    )

    on dgvColors MouseDown args do
    (
        colorDragStartX = args.X
        colorDragStartY = args.Y
        isColorDragging = false
        colorMouseIsDown = true
        colorDragArmed = false
        isColorLinearSelecting = false
        colorDragSelectedPositions = for stablePosition in colorStableSelectedPositions collect stablePosition

        local formsControl = dotNetClass "System.Windows.Forms.Control"
        local formsKeys = dotNetClass "System.Windows.Forms.Keys"
        local formsMouseButtons = dotNetClass "System.Windows.Forms.MouseButtons"
        local controlPressed = dotNet.CompareEnums formsControl.ModifierKeys formsKeys.Control
        local shiftPressed = dotNet.CompareEnums formsControl.ModifierKeys formsKeys.Shift

        local hitInfo = dgvColors.HitTest args.X args.Y
        if args.Button == formsMouseButtons.Left and hitInfo.RowIndex >= 0 and hitInfo.ColumnIndex >= 0 do
        (
            local hitPosition = ColorPositionFromCell hitInfo.RowIndex hitInfo.ColumnIndex

            if (not controlPressed) and (not shiftPressed) and hitPosition > 0 and (findItem colorDragSelectedPositions hitPosition) > 0 then
            (
                -- 押す前から選択済みだった色の左ドラッグだけを配置移動にする。
                -- 今回のMouseDownで新しく選ばれた色は配置移動にしない。
                colorDragArmed = true
                dgvColors.Capture = true
            )
            else if hitPosition > 0 then
            (
                if shiftPressed then
                (
                    if colorSelectionAnchorPosition < 1 do colorSelectionAnchorPosition = hitPosition
                    colorSelectionCurrentPosition = hitPosition
                    isColorLinearSelecting = true
                    SetLinearColorSelection colorSelectionAnchorPosition colorSelectionCurrentPosition
                )
                else if not controlPressed then
                (
                    -- 通常ドラッグの選択は矩形ではなく、パレット順の連続範囲にする。
                    colorSelectionAnchorPosition = hitPosition
                    colorSelectionCurrentPosition = hitPosition
                    isColorLinearSelecting = true
                    SetLinearColorSelection hitPosition hitPosition
                )
                else
                (
                    -- Ctrlクリックは個別追加を許可するが、処理時の順番は左上順にする。
                    colorSelectionAnchorPosition = hitPosition
                    colorSelectionCurrentPosition = hitPosition
                )
            )
        )
    )

    on dgvColors MouseMove args do
    (
        if colorMouseIsDown and isColorLinearSelecting and (not colorDragArmed) then
        (
            local hitInfo = dgvColors.HitTest args.X args.Y
            if hitInfo.RowIndex >= 0 and hitInfo.ColumnIndex >= 0 do
            (
                local hitPosition = ColorPositionFromCell hitInfo.RowIndex hitInfo.ColumnIndex
                if hitPosition > 0 and hitPosition != colorSelectionCurrentPosition do
                (
                    colorSelectionCurrentPosition = hitPosition
                    SetLinearColorSelection colorSelectionAnchorPosition colorSelectionCurrentPosition
                )
            )
        )
        else if colorMouseIsDown and colorDragArmed and (not isColorDragging) and colorDragSelectedPositions.count > 0 do
        (
            local distanceX = abs (args.X - colorDragStartX)
            local distanceY = abs (args.Y - colorDragStartY)

            if distanceX >= 4 or distanceY >= 4 do
            (
                isColorDragging = true
                dgvColors.Cursor = (dotNetClass "System.Windows.Forms.Cursors").Hand
            )
        )
    )

    on dgvColors MouseUp args do
    (
        local completedColorDrag = isColorDragging

        if isColorLinearSelecting do
        (
            local hitInfo = dgvColors.HitTest args.X args.Y
            if hitInfo.RowIndex >= 0 and hitInfo.ColumnIndex >= 0 do
            (
                local hitPosition = ColorPositionFromCell hitInfo.RowIndex hitInfo.ColumnIndex
                if hitPosition > 0 do
                (
                    colorSelectionCurrentPosition = hitPosition
                    SetLinearColorSelection colorSelectionAnchorPosition colorSelectionCurrentPosition
                )
            )
        )

        if isColorDragging do
        (
            local hitInfo = dgvColors.HitTest args.X args.Y
            local targetPosition = colorRowOrder.count + 1

            if hitInfo.RowIndex >= 0 and hitInfo.ColumnIndex >= 0 do
            (
                local hitPosition = ColorPositionFromCell hitInfo.RowIndex hitInfo.ColumnIndex
                if hitPosition > 0 do targetPosition = hitPosition
            )

            local moveResult = MoveSelectedColorsBefore targetPosition selectedPositions:colorDragSelectedPositions

            if moveResult[1] then
            (
                if moveResult[3] do
                (
                    skipSavedPaletteLoadOnce = true
                    RefreshMaterialList()
                )
                txtLog.Text = moveResult[2]
            )
            else
            (
                messageBox moveResult[2] title:"DiGi Material Manager"
            )
        )

        isColorDragging = false
        colorMouseIsDown = false
        isColorLinearSelecting = false
        if colorDragArmed do dgvColors.Capture = false
        colorDragArmed = false
        colorDragSelectedPositions = #()
        dgvColors.Cursor = (dotNetClass "System.Windows.Forms.Cursors").Default

        -- DataGridViewが選択を確定した後でのみRGB欄を更新する。
        -- MouseUpイベント内で直接spinnerを変更すると、範囲選択の確定処理へ
        -- 再入して複数選択を1セルへ戻すことがある。
        colorStableSelectedPositions = GetSelectedColorPositions()

        if not completedColorDrag do
        (
            tmrLoadNumericRGB.active = false
            tmrLoadNumericRGB.active = true
        )
    )

    on lvMaterials ItemSelectionChanged args do
    (
        if (not isRefreshingList) and (not isSyncingSelection) do
        (
            local zeroBasedRowIndex = args.ItemIndex
            local existingOrderIndex = findItem selectionOrder zeroBasedRowIndex

            if args.IsSelected then
            (
                if existingOrderIndex == 0 do append selectionOrder zeroBasedRowIndex
            )
            else
            (
                if existingOrderIndex > 0 do deleteItem selectionOrder existingOrderIndex
            )
        )
    )

    on lvMaterials MouseUp args do
    (
        tmrLoadNumericRGB.active = false
        tmrLoadNumericRGB.active = true
    )

    on tmrLoadNumericRGB tick do
    (
        tmrLoadNumericRGB.active = false
        colorStableSelectedPositions = GetSelectedColorPositions()
        LoadNumericRGBFromSingleSelection()
    )

    on lvMaterials ColumnClick args do
    (
        local clickedColumn = args.Column

        if DMM_SortColumn == clickedColumn then
            DMM_SortAscending = not DMM_SortAscending
        else
        (
            DMM_SortColumn = clickedColumn
            DMM_SortAscending = true
        )

        UpdateSortHeaders()
        RefreshMaterialList()
    )

    on btnPaletteOriginal pressed do
    (
        local selectedRows = GetSelectedColorRowIndices()
        ResetColorRowOrder()
        PopulateColorGrid selectedRowIndices:selectedRows
        txtLog.Text = "Color表示をリストと同じ元の順番へ戻しました。"
    )

    on btnPaletteSave pressed do ShowOperationResult (SaveColorPaletteOrder())

    on btnPaletteLoad pressed do ShowOperationResult (LoadSavedColorPaletteOrder())

    on btnFlashColorLocations pressed do ShowOperationResult (FlashObjectsUsingSelectedColors())

    on btnApplyNumericRGB pressed do
    (
        local selectedRows = GetSelectedRows()
        local selectedMaterials = #()
        local invalidSelection = false

        for selectedRow in selectedRows do
        (
            if selectedRow.mat == undefined or DMM_IsMulti selectedRow.mat then
                invalidSelection = true
            else
                DMM_AppendUniqueReference selectedMaterials selectedRow.mat
        )

        if selectedRows.count == 0 then
        (
            messageBox "RGB値を変更する色をColorパレットまたは一覧から選択してください。" title:"DiGi Material Manager"
        )
        else if invalidSelection or selectedMaterials.count == 0 then
        (
            messageBox "EmptyまたはMulti/Subを含めず、通常マテリアルだけを選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local selectedRowIndices = GetSelectedColorRowIndices()
            local newColor = color spnEditRed.value spnEditGreen.value spnEditBlue.value
            local changedCount = 0
            local failedCount = 0
            local startedHold = false

            try
            (
                if not (theHold.Holding()) do
                (
                    theHold.Begin()
                    startedHold = true
                )

                for selectedMaterial in selectedMaterials do
                (
                    if DMM_SetBaseColor selectedMaterial newColor then
                    (
                        notifyDependents selectedMaterial partID:#all
                        changedCount += 1
                    )
                    else
                    (
                        failedCount += 1
                    )
                )

                if startedHold do theHold.Accept "Set Material RGB"
            )
            catch
            (
                if startedHold and theHold.Holding() do theHold.Cancel()
                failedCount = selectedMaterials.count
                changedCount = 0
            )

            redrawViews()
            PopulateColorGrid selectedRowIndices:selectedRowIndices
            if selectedRows.count > 0 do UpdateSelectedMaterialInfo selectedRows[1]

            local resultText = (changedCount as string) + "個のマテリアルを RGB(" + (spnEditRed.value as string) + "," + (spnEditGreen.value as string) + "," + (spnEditBlue.value as string) + ") に変更しました。"
            if failedCount > 0 do resultText += " / 変更失敗: " + (failedCount as string)
            txtLog.Text = resultText
        )
    )

    on btnTemporaryColorSnapshot pressed do
    (
        local selectedRowIndices = GetSelectedColorRowIndices()

        if selectedRowIndices.count == 0 then
        (
            messageBox "一時保存する色をColorパレットで選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local saveFailed = false
            local failureText = ""
            local newTemporaryColorMaterials = #()
            local newTemporaryColors = #()

            for rowIndex in selectedRowIndices do
            (
                if not saveFailed do
                (
                    local rowMaterial = DMM_Rows[rowIndex].mat

                    if rowMaterial == undefined or DMM_IsMulti rowMaterial then
                    (
                        saveFailed = true
                        failureText = "EmptyまたはMulti/Subを含めず、通常マテリアルだけを選択してください。"
                    )
                    else if (findItem newTemporaryColorMaterials rowMaterial) == 0 then
                    (
                        local colorInfo = DMM_GetBaseColorInfo rowMaterial

                        if not colorInfo[1] then
                        (
                            saveFailed = true
                            failureText = rowMaterial.name + " のBase Colorを取得できません。"
                        )
                        else
                        (
                            append newTemporaryColorMaterials rowMaterial
                            append newTemporaryColors colorInfo[2]
                        )
                    )
                )
            )

            if saveFailed then
            (
                -- 保存失敗時は、直前まで使えていた一時保存を消さない。
                messageBox failureText title:"DiGi Material Manager"
            )
            else
            (
                temporaryColorMaterials = newTemporaryColorMaterials
                temporaryColors = newTemporaryColors
                hasTemporaryColorSnapshot = true
                btnRestoreTemporaryColors.enabled = true
                txtLog.Text = (temporaryColorMaterials.count as string) + "色を一時保存しました。以前の一時保存は上書きされました。"
            )
        )
    )

    on btnRestoreTemporaryColors pressed do
    (
        if hasTemporaryColorSnapshot and temporaryColorMaterials.count > 0 then
        (
            local restoreSelectedRowIndices = GetSelectedColorRowIndices()
            local restoredCount = 0
            local failedCount = 0

            for materialIndex = 1 to temporaryColorMaterials.count do
            (
                local savedMaterial = temporaryColorMaterials[materialIndex]

                if savedMaterial != undefined and DMM_SetBaseColor savedMaterial temporaryColors[materialIndex] then
                (
                    notifyDependents savedMaterial partID:#all
                    restoredCount += 1
                )
                else
                (
                    failedCount += 1
                )
            )

            redrawViews()
            PopulateColorGrid selectedRowIndices:restoreSelectedRowIndices

            local resultText = (restoredCount as string) + "色を一時保存状態へ復元しました。保存内容は維持されています。"
            if failedCount > 0 do resultText += " / 復元失敗: " + (failedCount as string)
            txtLog.Text = resultText
            if failedCount > 0 do messageBox resultText title:"DiGi Material Manager"
        )
    )

    on btnApplyColorGradient pressed do
    (
        local selectedRowIndices = GetSelectedColorRowIndices()
        local result = ApplyGradientToSelectedColors()

        if result[1] do PopulateColorGrid selectedRowIndices:selectedRowIndices
        ShowOperationResult result
    )

    on btnPaletteHue pressed do
    (
        SortColorPalette #hue
        txtLog.Text = "Color表示を色相順に並べました。選択済みの色をドラッグ挿入するまではIDを変更しません。"
    )

    on btnPaletteVisual pressed do
    (
        SortColorPalette #visual
        txtLog.Text = "Color表示を視覚順に並べました。近い色をまとめ、白・灰・黒は最後に並べています。選択済みの色をドラッグ挿入するまではIDを変更しません。"
    )

    on btnPaletteBrightness pressed do
    (
        SortColorPalette #brightness
        txtLog.Text = "Color表示を暗い色から明るい色の順に並べました。選択済みの色をドラッグ挿入するまではIDを変更しません。"
    )

    on chkHideMultiInPalette changed state do
    (
        RefreshMaterialList()
        if state then
            txtLog.Text = "左右の一覧からマルチサブ親材質を非表示にしました。"
        else
            txtLog.Text = "左右の一覧にマルチサブ親材質を表示しました。"
    )

    on chkKeepHierarchy changed state do RefreshMaterialList()

    on chkDeleteUnusedAndClearUndo changed state do btnDeleteUnused.enabled = state

    on btnShowInSlate pressed do ShowOperationResult (SelectMaterialsInSlate())

    on btnSelectAssignedObjects pressed do ShowOperationResult (SelectObjectsUsingSelectedRows())

    on btnMergeSameName pressed do
    (
        local result = DMM_MergeDuplicateMaterials #name
        if result[1] do RefreshMaterialList()
        ShowOperationResult result
    )

    on btnMergeSameBaseColor pressed do
    (
        local result = DMM_MergeDuplicateMaterials #baseColor
        if result[1] do RefreshMaterialList()
        ShowOperationResult result
    )

    on btnMergeSelectedMaterials pressed do
    (
        local selectedRows = GetSelectedRows()
        local result = undefined

        if DMM_SelectedRowsShareDirectMultiParent selectedRows then
        (
            result = DMM_MergeSelectedMultiSlots selectedRows
        )
        else
        (
            local selectedMaterials = GetSelectedMaterials()
            result = DMM_MergeSelectedMaterials selectedMaterials
        )

        if result[1] do RefreshMaterialList()
        ShowOperationResult result
    )

    on btnPreviewSimilarColor pressed do
    (
        local selectedMaterials = GetSelectedMaterials()

        if selectedMaterials.count != 1 then
        (
            messageBox "色差を確認する通常マテリアルを1つ選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local targetMaterial = selectedMaterials[1]
            local rgbTolerance = spnRGBDistance.value
            local redTolerance = spnRedTolerance.value
            local greenTolerance = spnGreenTolerance.value
            local blueTolerance = spnBlueTolerance.value
            local result = DMM_GetSimilarColorReport targetMaterial rgbTolerance redTolerance greenTolerance blueTolerance
            ShowOperationResult result
        )
    )

    on btnMergeSimilarToSelected pressed do
    (
        local selectedMaterials = GetSelectedMaterials()

        if selectedMaterials.count != 1 then
        (
            messageBox "基準にする通常マテリアルを1つ選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local targetMaterial = selectedMaterials[1]
            local rgbTolerance = spnRGBDistance.value
            local redTolerance = spnRedTolerance.value
            local greenTolerance = spnGreenTolerance.value
            local blueTolerance = spnBlueTolerance.value
            local result = DMM_MergeSimilarColorMaterials targetMaterial false rgbTolerance redTolerance greenTolerance blueTolerance
            if result[1] do RefreshMaterialList()
            ShowOperationResult result
        )
    )

    on btnAutoMergeSimilarColor pressed do
    (
        local rgbTolerance = spnRGBDistance.value
        local redTolerance = spnRedTolerance.value
        local greenTolerance = spnGreenTolerance.value
        local blueTolerance = spnBlueTolerance.value
        local result = DMM_MergeSimilarColorMaterials undefined true rgbTolerance redTolerance greenTolerance blueTolerance
        if result[1] do RefreshMaterialList()
        ShowOperationResult result
    )

    on btnRefresh pressed do RefreshMaterialList()

    on btnRenameSelected pressed do
    (
        local selectedMaterials = GetSelectedMaterials()

        if selectedMaterials.count == 0 then
        (
            messageBox "名前を変換するマテリアルを選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local renamedCount = DMM_RenameMaterials selectedMaterials
            RefreshMaterialList()
            txtLog.Text = (renamedCount as string) + " material(s) renamed"
        )
    )

    on btnRenameAll pressed do
    (
        local roots = DMM_GetDisplayRootMaterials()
        local renamedCount = DMM_RenameMaterials roots
        RefreshMaterialList()
        txtLog.Text = (renamedCount as string) + " material(s) renamed"
    )

    on btnMerge pressed do
    (
        local selectedMultiMaterials = #()

        for row in GetSelectedRows() do
        (
            if row.parentMat == undefined and DMM_IsMulti row.mat do
            (
                DMM_AppendUniqueReference selectedMultiMaterials row.mat
            )
        )

        local result = DMM_MergeMultiMaterials selectedMultiMaterials chkMergeInstances.checked chkMakeNecessaryUnique.checked
        if result[1] do RefreshMaterialList()
        ShowOperationResult result
    )

    on btnMoveUp pressed do
    (
        local selectedRows = GetSelectedRows()

        if selectedRows.count != 1 then
        (
            messageBox "移動するサブマテリアルを1つ選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local row = selectedRows[1]
            local hasHiddenInstances = (row.sourceRows != undefined) and (row.sourceRows.count > 1)

            if hasHiddenInstances then
            (
                messageBox "同一インスタンスの複数行をまとめて表示しています。\n「親子を見て並べる」をONにして、移動するIDを選択してください。" title:"DiGi Material Manager"
            )
            else if row.parentMat == undefined or row.parentMat != row.rootMat then
            (
                messageBox "移動するサブマテリアルを1つ選択してください。" title:"DiGi Material Manager"
            )
            else
            (
                local result = DMM_SwapMultiSlots row.parentMat row.slotIndex (row.slotIndex - 1)
                if result[1] do RefreshMaterialList()
                ShowOperationResult result
            )
        )
    )

    on btnMoveDown pressed do
    (
        local selectedRows = GetSelectedRows()

        if selectedRows.count != 1 then
        (
            messageBox "移動するサブマテリアルを1つ選択してください。" title:"DiGi Material Manager"
        )
        else
        (
            local row = selectedRows[1]
            local hasHiddenInstances = (row.sourceRows != undefined) and (row.sourceRows.count > 1)

            if hasHiddenInstances then
            (
                messageBox "同一インスタンスの複数行をまとめて表示しています。\n「親子を見て並べる」をONにして、移動するIDを選択してください。" title:"DiGi Material Manager"
            )
            else if row.parentMat == undefined or row.parentMat != row.rootMat then
            (
                messageBox "移動するサブマテリアルを1つ選択してください。" title:"DiGi Material Manager"
            )
            else
            (
                local result = DMM_SwapMultiSlots row.parentMat row.slotIndex (row.slotIndex + 1)
                if result[1] do RefreshMaterialList()
                ShowOperationResult result
            )
        )
    )

    on btnCompactSelectedIDs pressed do
    (
        local selectedRows = GetSelectedRows()
        local targetMultiMaterials = #()

        for selectedRow in selectedRows do
        (
            local sourceRows = #(selectedRow)
            if selectedRow.sourceRows != undefined and selectedRow.sourceRows.count > 0 do sourceRows = selectedRow.sourceRows

            for sourceRow in sourceRows do
            (
                local targetMulti = undefined

                if DMM_IsMulti sourceRow.mat then
                    targetMulti = sourceRow.mat
                else if DMM_IsMulti sourceRow.parentMat then
                    targetMulti = sourceRow.parentMat

                if targetMulti != undefined do DMM_AppendUniqueReference targetMultiMaterials targetMulti
            )
        )

        -- If nothing is selected in this tool, use the current Slate Material
        -- Editor selection. This matches the user's natural workflow when the
        -- Multi/Sub node itself is already selected in SME.
        if targetMultiMaterials.count == 0 do
        (
            local slateView = GetActiveSlateView()
            local slateSelections = #()
            if slateView != undefined do try (slateSelections = slateView.GetSelectedNodes()) catch()

            for slateSelection in slateSelections do
            (
                local slateMaterial = slateSelection
                if not (DMM_IsMaterialValue slateMaterial) do try (slateMaterial = slateSelection.reference) catch()

                if DMM_IsMulti slateMaterial then
                (
                    DMM_AppendUniqueReference targetMultiMaterials slateMaterial
                )
                else
                (
                    -- A selected child material resolves to each Multi/Sub that
                    -- contains it in the manager's current rows.
                    for sourceRow in DMM_Rows where sourceRow.mat == slateMaterial and DMM_IsMulti sourceRow.parentMat do
                    (
                        DMM_AppendUniqueReference targetMultiMaterials sourceRow.parentMat
                    )
                )
            )
        )

        if targetMultiMaterials.count == 0 then
        (
            messageBox "IDを整理するMulti/Sub、またはその中のマテリアル行を、一覧かSlate Material Editorで選択してください。" title:"DiGi Material Manager"
        )
        else if queryBox ((targetMultiMaterials.count as string) + "個のMulti/SubのID欠番を1からの連番に整理しますか？\n対応する面のMaterial IDも同時に変更します。") title:"DiGi Material Manager" then
        (
            local compactedCount = 0
            local alreadyOrderedCount = 0
            local skippedCount = 0

            for targetMulti in targetMultiMaterials do
            (
                local needsCompaction = false

                for slotIndex = 1 to targetMulti.materialIDList.count where targetMulti.materialIDList[slotIndex] != slotIndex do
                (
                    needsCompaction = true
                )

                if not needsCompaction then
                (
                    alreadyOrderedCount += 1
                )
                else if not (DMM_CanCompactMultiMaterialIDs targetMulti) then
                (
                    skippedCount += 1
                )
                else
                (
                    local result = DMM_RemoveMultiSlotIndicesPreserveIDs targetMulti #()

                    if result[1] and result[5] then
                        compactedCount += 1
                    else
                        skippedCount += 1
                )
            )

            RefreshMaterialList()

            local resultText = "IDを連番化: " + (compactedCount as string) + "材質"
            if alreadyOrderedCount > 0 do resultText += " / 整理済み: " + (alreadyOrderedCount as string)
            if skippedCount > 0 do resultText += " / 安全のためスキップ: " + (skippedCount as string)
            txtLog.Text = resultText
            messageBox resultText title:"DiGi Material Manager"
        )
    )

    on btnDeleteSelectedSlots pressed do
    (
        local selectedRows = GetSelectedRows()
        local parentMaterials = #()
        local parentSlotGroups = #()

        for selectedRow in selectedRows do
        (
            local sourceRows = #(selectedRow)
            if selectedRow.sourceRows != undefined and selectedRow.sourceRows.count > 0 do sourceRows = selectedRow.sourceRows

            for sourceRow in sourceRows do
            (
                if sourceRow.parentMat != undefined and DMM_IsMulti sourceRow.parentMat and sourceRow.slotIndex > 0 do
                (
                    local parentIndex = findItem parentMaterials sourceRow.parentMat

                    if parentIndex == 0 do
                    (
                        append parentMaterials sourceRow.parentMat
                        append parentSlotGroups #()
                        parentIndex = parentMaterials.count
                    )

                    if (findItem parentSlotGroups[parentIndex] sourceRow.slotIndex) == 0 do
                    (
                        append parentSlotGroups[parentIndex] sourceRow.slotIndex
                    )
                )
            )
        )

        if parentMaterials.count == 0 then
        (
            messageBox "削除するMulti/Sub内のスロットを選択してください。\n親マテリアル自体は対象にできません。" title:"DiGi Material Manager"
        )
        else if queryBox ((selectedRows.count as string) + "行の選択から、面で未使用のスロットだけを削除しますか？\n使用中のIDは削除しません。") title:"DiGi Material Manager" then
        (
            local removedCount = 0
            local usedSlotCount = 0
            local protectedLastSlotCount = 0
            local failedCount = 0
            local compactedMaterialCount = 0

            for parentIndex = 1 to parentMaterials.count do
            (
                local result = DMM_RemoveUnusedSlotsFromMulti parentMaterials[parentIndex] selectedSlotIndices:parentSlotGroups[parentIndex]

                if result[1] then
                (
                    removedCount += result[2]
                    usedSlotCount += result[3]
                    protectedLastSlotCount += result[4]
                    if result[6] do compactedMaterialCount += 1
                )
                else
                (
                    failedCount += 1
                )
            )

            RefreshMaterialList()
            local resultText = (removedCount as string) + "個の選択スロットを削除しました。"
            if compactedMaterialCount > 0 do resultText += " / ID連番化: " + (compactedMaterialCount as string) + "材質"
            if usedSlotCount > 0 do resultText += " / 使用中のため保護: " + (usedSlotCount as string)
            if protectedLastSlotCount > 0 do resultText += " / 最後の1枠を保護: " + (protectedLastSlotCount as string)
            if failedCount > 0 do resultText += " / 処理失敗: " + (failedCount as string)
            txtLog.Text = resultText
            messageBox resultText title:"DiGi Material Manager"
        )
    )

    on btnDeleteAllUnusedSlots pressed do
    (
        if queryBox "割り当て済みMulti/Subを調べ、面で使われていないスロットをすべて削除しますか？\n安全に変更できる材質はIDと面IDも1からの連番にします。使用中のIDは保護します。" title:"DiGi Material Manager" then
        (
            local result = DMM_RemoveAllUnusedMultiSlots()
            RefreshMaterialList()

            local resultText = (result[2] as string) + "個の未使用スロットを削除しました。"
            if result[6] > 0 do resultText += " / ID連番化: " + (result[6] as string) + "材質"
            if result[4] > 0 do resultText += " / 最後の1枠を保護: " + (result[4] as string)
            if result[5] > 0 do resultText += " / 処理失敗: " + (result[5] as string)
            txtLog.Text = resultText
            messageBox resultText title:"DiGi Material Manager"
        )
    )

    on btnDeleteUnused pressed do
    (
        if not chkDeleteUnusedAndClearUndo.checked then
        (
            messageBox "チェックが外れているため、未使用マテリアルを残しました。" title:"DiGi Material Manager"
        )
        else
        (
            local unusedMaterials = DMM_CollectUnusedSceneMaterials (DMM_CollectUsedMaterials())

            if unusedMaterials.count == 0 then
            (
                messageBox "未使用マテリアルは見つかりませんでした。" title:"DiGi Material Manager"
            )
            else if queryBox ((unusedMaterials.count as string) + "個の未使用マテリアルを削除しますか？\n別のシーン参照がある場合も強制解除します。\nUndo履歴は消去され、処理前には戻れません。\n先にシーンを保存してください。") title:"DiGi Material Manager" do
            (
                unusedMaterials = undefined
                local result = DMM_DeleteUnusedMaterials()
                RefreshMaterialList()

                local resultText = (result[1] as string) + "個を処理しました。"
                resultText += " SME: " + (result[2] as string)
                resultText += ", CME: " + (result[3] as string)
                resultText += ", Parameter Editor: " + (result[5] as string)
                resultText += ", Scene Materials: " + (result[7] as string)
                resultText += ", シーン参照強制解除: " + (result[6] as string)
                resultText += "\nUndo履歴を消去しました。"

                if result[4] > 0 do
                (
                    resultText += "\n\n警告: " + (result[4] as string) + "個は参照の強制解除後も残りました。"
                )

                messageBox resultText title:"DiGi Material Manager"
            )
        )
    )
)

createDialog DiGiMaterialManager_Rollout style:#(#style_titlebar, #style_sysmenu, #style_minimizebox)
