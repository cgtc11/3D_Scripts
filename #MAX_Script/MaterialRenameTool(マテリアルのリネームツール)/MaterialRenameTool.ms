/* MaterialRenameTool v1.8 / 3ds Max MAXScript */
global MaterialRenameTool_Rollout
try(destroyDialog MaterialRenameTool_Rollout)catch()

rollout MaterialRenameTool_Rollout "マテリアル名変更ツール v1.8" width:1000 height:620
(
 local shown=#(),swatchImages=undefined
 groupBox gt "収集対象" pos:[450,10] width:540 height:64
 radioButtons target labels:#("シーン全体","選択オブジェクト") columns:2 default:1 pos:[465,35]
 groupBox gf "一覧の表示フィルター／並び順" pos:[450,82] width:540 height:110
 dropDownList kind "マテリアル種別：" pos:[465,105] width:350 items:#("すべて","Multi/Sub-Object のみ","Physical Material のみ","Standard Material のみ","その他") selection:1
 button refresh "一覧を更新" pos:[835,112] width:135 height:28
 dropDownList sortOrder "並び順：" pos:[465,154] width:350 items:#("収集順","名前 A → Z","名前 Z → A") selection:2
 label listLabel "マテリアル一覧（Ctrl／Shiftで複数選択）" pos:[15,15] width:420
 dotNetControl materialList "System.Windows.Forms.ListView" pos:[15,35] width:420 height:570
 label countLabel "0件" pos:[460,205] width:520
 groupBox gmode "変更方法" pos:[450,230] width:540 height:92
 radioButtons mode labels:#("検索・置換","先頭＋新名称","完全に新名称") columns:3 default:1 pos:[465,255]
 label fullNameLabel "完全な新名称：" pos:[465,290] width:105
 editText fullName "" pos:[575,284] width:395 text:"Material"
 groupBox greplace "検索・置換" pos:[450,330] width:540 height:64
 editText findText "検索：" pos:[465,354] width:240
 editText replaceText "置換：" pos:[725,354] width:245
 groupBox gcompose "名称の組み立て／連番" pos:[450,402] width:540 height:102
 label keepLabel "元名の先頭を残す文字数：" pos:[465,430] width:175
 spinner keep "" pos:[645,424] width:65 range:[0,999,0] type:#integer
 label newNameLabel "新名称：" pos:[730,430] width:60
 editText newName "" pos:[795,424] width:175
 label separatorLabel "区切り文字：" pos:[465,468] width:75
 editText separator "" pos:[545,462] width:165 text:"_"
 checkBox numbering "連番を付ける" pos:[750,466] checked:true
 label digitsLabel "桁数：" pos:[460,537] width:40
 spinner digits "" pos:[505,530] width:70 range:[1,10,3] type:#integer
 label startLabel "開始番号：" pos:[595,537] width:65
 spinner startNumber "" pos:[665,530] width:95 range:[0,999999999,1] type:#integer
 button renameButton "選択項目の名前を変更" pos:[785,524] width:195 height:36
 label status "準備完了" pos:[460,585] width:520

 fn addUnique a x=if x!=undefined and findItem a x==0 do append a x
 fn walk m a=
 (
  if m==undefined then return false
  addUnique a m
  local n=0;try(n=getNumSubMtls m)catch()
  for i=1 to n do(local s=undefined;try(s=getSubMtl m i)catch();if s!=undefined do walk s a)
  true
 )
 fn collectFrom nodes=
 (
  local a=#()
  for o in nodes where o.material!=undefined do walk o.material a
  a
 )
 fn collectTarget=if target.state==1 then collectFrom objects else collectFrom selection
 fn typeID m=
 (
  local c="";try(c=toLower(classOf m as string))catch()
  if c=="multimaterial" or c=="multi/sub-object" then return 2
  if findString c "physical"!=undefined or isProperty m #base_color or isProperty m #baseColor then return 3
  if c=="standardmaterial" or c=="standard" then return 4
  5
 )
 fn typeLabel m=
 (
  case(typeID m)of
  (
   2:"Multi/Sub-Object"
   3:"Physical"
   4:"Standard"
   default:(local c="その他";try(c=classOf m as string)catch();c)
  )
 )
 fn allowed m=kind.selection==1 or typeID m==kind.selection
 fn compareNameAsc a b=
 (
  local result=stricmp a.name b.name
  if result<0 then -1 else if result>0 then 1 else 0
 )
 fn compareNameDesc a b=-(compareNameAsc a b)
 fn baseColor m=
 (
  for p in #(#base_color,#baseColor,#basecolor,#Base_Color,#diffuse) where isProperty m p do
  (
   local c=undefined;try(c=getProperty m p)catch()
   if isKindOf c Color do return c
  )
  undefined
 )
 fn setupMaterialList=
 (
  materialList.View=(dotNetClass "System.Windows.Forms.View").Details
  materialList.FullRowSelect=true;materialList.HideSelection=false;materialList.MultiSelect=true;materialList.GridLines=true
  materialList.Columns.Clear()
  materialList.Columns.Add "色/No." 65
  materialList.Columns.Add "マテリアル名" 175
  materialList.Columns.Add "種類" 95
  materialList.Columns.Add "Base Color" 80
  swatchImages=dotNetObject "System.Windows.Forms.ImageList"
  swatchImages.ImageSize=dotNetObject "System.Drawing.Size" 18 18
  swatchImages.ColorDepth=(dotNetClass "System.Windows.Forms.ColorDepth").Depth32Bit
  materialList.SmallImageList=swatchImages
 )
 fn addSwatch c=
 (
  local bitmap=dotNetObject "System.Drawing.Bitmap" 18 18
  local graphics=(dotNetClass "System.Drawing.Graphics").FromImage bitmap
  if isKindOf c Color then
  (
   local netColor=(dotNetClass "System.Drawing.Color").FromArgb 255 (c.r as integer) (c.g as integer) (c.b as integer)
   graphics.Clear netColor
  )
  else
  (
   local backgroundColor=(dotNetClass "System.Drawing.Color").FromArgb 255 70 70 70
   local crossColor=(dotNetClass "System.Drawing.Color").FromArgb 255 240 90 90
   local crossPen=dotNetObject "System.Drawing.Pen" crossColor 2.5
   graphics.Clear backgroundColor
   graphics.DrawLine crossPen 3 3 14 14
   graphics.DrawLine crossPen 14 3 3 14
   crossPen.Dispose()
  )
  graphics.Dispose()
  swatchImages.Images.Add bitmap
  local imageIndex=swatchImages.Images.Count-1
  bitmap.Dispose()
  imageIndex
 )
 fn refreshList=
 (
  local all=collectTarget()
  shown=for m in all where allowed m collect m
  if sortOrder.selection==2 then
  (
   qsort shown compareNameAsc
  )
  else if sortOrder.selection==3 then
  (
   qsort shown compareNameDesc
  )
  materialList.BeginUpdate();materialList.Items.Clear();swatchImages.Images.Clear()
  for i=1 to shown.count do
  (
   local m=shown[i],c=baseColor m,colorText="色なし"
   if isKindOf c Color do colorText=(c.r as integer) as string+","+(c.g as integer) as string+","+(c.b as integer) as string
   local numberText=formattedPrint i format:"03d"
   local item=dotNetObject "System.Windows.Forms.ListViewItem" numberText
   item.ImageIndex=addSwatch c;item.Tag=i
   item.SubItems.Add m.name;item.SubItems.Add(typeLabel m);item.SubItems.Add colorText
   materialList.Items.Add item
  )
  materialList.EndUpdate()
  countLabel.text="表示："+shown.count as string+"件 ／ 収集："+all.count as string+"件"
  status.text="一覧を更新しました。"
 )
 fn replaceAll source needle replacement=
 (
  if needle.count==0 then return source
  local result="",rest=source,p=findString rest needle
  while p!=undefined do
  (
   if p>1 do result+=substring rest 1 (p-1)
   result+=replacement
   rest=substring rest (p+needle.count) -1
   p=findString rest needle
  )
  result+rest
 )
 fn pad n d=(local s=n as string;while s.count<d do s="0"+s;s)
 fn lower s=toLower s
 fn used candidate names=findItem names (lower candidate)!=0
 fn uniqueName base names sep d first forceNumber=
 (
  if not forceNumber and not used base names then return base
  local n=first,candidate=base+sep+pad n d
  while used candidate names do(n+=1;candidate=base+sep+pad n d)
  candidate
 )
 fn selectedMaterials=
 (
  local a=#()
  local selectedItems=materialList.SelectedItems
  if selectedItems.Count>0 do
  (
   for itemIndex=0 to selectedItems.Count-1 do
   (
    local shownIndex=selectedItems.Item[itemIndex].Tag as integer
    if shownIndex>=1 and shownIndex<=shown.count do append a shown[shownIndex]
   )
  )
  a
 )
 fn baseName old=
 (
  if mode.state==1 then replaceAll old findText.text replaceText.text
  else if mode.state==2 then
  (
   local n=amin keep.value old.count,prefix=if n>0 then substring old 1 n else ""
   if prefix.count>0 and separator.text.count>0 then prefix+separator.text+newName.text else prefix+newName.text
  )
  else fullName.text
 )
 fn updateMode=
 (
  findText.enabled=mode.state==1;replaceText.enabled=mode.state==1
  keep.enabled=mode.state==2;newName.enabled=mode.state==2
  fullName.enabled=mode.state==3
 )

 on refresh pressed do refreshList()
 on target changed s do refreshList()
 on kind selected i do refreshList()
 on sortOrder selected i do refreshList()
 on mode changed s do updateMode()
 on renameButton pressed do
 (
  local selected=selectedMaterials()
  if selected.count==0 then messageBox "一覧から1件以上のマテリアルを選択してください。" title:"マテリアル名変更ツール v1.8"
  else if mode.state==1 and findText.text.count==0 then messageBox "検索する文字列を入力してください。" title:"マテリアル名変更ツール v1.8"
  else if mode.state==2 and newName.text.count==0 then messageBox "新名称を入力してください。" title:"マテリアル名変更ツール v1.8"
  else if mode.state==3 and fullName.text.count==0 then messageBox "完全な新名称を入力してください。" title:"マテリアル名変更ツール v1.8"
  else
  (
   local all=collectFrom objects,names=#(),nextNumber=startNumber.value
   for m in all where findItem selected m==0 do addUnique names (lower m.name)
   undo "マテリアル名を変更" on
   (
    for m in selected do
    (
     local base=baseName m.name;if base.count==0 do base="Material"
     local finalName=uniqueName base names separator.text digits.value nextNumber numbering.checked
     m.name=finalName;addUnique names (lower finalName);if numbering.checked do nextNumber+=1
    )
   )
   local n=selected.count;refreshList();status.text=n as string+"件の名前を変更しました。"
  )
 )
 on MaterialRenameTool_Rollout open do(setupMaterialList();updateMode();refreshList())
)
createDialog MaterialRenameTool_Rollout
