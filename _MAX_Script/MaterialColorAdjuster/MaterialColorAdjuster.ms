/* MaterialColorAdjuster v1.5 / 3ds Max MAXScript */
global MaterialColorAdjuster_Rollout
try(destroyDialog MaterialColorAdjuster_Rollout)catch()

rollout MaterialColorAdjuster_Rollout "マテリアル色調整 v1.5" width:520 height:900
(
 local mats=#(), originals=#(), locking=false
 groupBox g1 "対象" pos:[10,10] width:500 height:62
 radioButtons rbTarget labels:#("シーン全体","選択オブジェクト") columns:2 default:1 pos:[28,34]
 button btnCollect "マテリアルを収集して元色を保存" pos:[20,82] width:235 height:32
 button btnRestore "保存した元色に戻す" pos:[265,82] width:235 height:32
 label lblStatus "元色はまだ保存されていません。" pos:[20,120] width:480
 groupBox g2 "元色データファイル" pos:[10,148] width:500 height:62
 button btnSaveFile "元色をファイルへ保存..." pos:[20,172] width:235 height:28
 button btnLoadFile "元色をファイルから読み込み..." pos:[265,172] width:235 height:28
 checkBox chkRealtime "スライダー操作をリアルタイムで反映" pos:[20,220] width:300 checked:true
 button btnReset "調整値を初期化" pos:[365,218] width:135 height:25

 groupBox gs "シャドウ RGB（-255 ～ 255）" pos:[10,250] width:500 height:126
 label lsr "赤" pos:[25,278]; slider sr pos:[55,272] width:390 range:[0,510,255] type:#integer ticks:0; label vsr "0" pos:[455,278] width:45
 label lsg "緑" pos:[25,310]; slider sg pos:[55,304] width:390 range:[0,510,255] type:#integer ticks:0; label vsg "0" pos:[455,310] width:45
 label lsb "青" pos:[25,342]; slider sb pos:[55,336] width:390 range:[0,510,255] type:#integer ticks:0; label vsb "0" pos:[455,342] width:45
 groupBox gm "中間調 RGB（-255 ～ 255）" pos:[10,384] width:500 height:126
 label lmr "赤" pos:[25,412]; slider mr pos:[55,406] width:390 range:[0,510,255] type:#integer ticks:0; label vmr "0" pos:[455,412] width:45
 label lmg "緑" pos:[25,444]; slider mg pos:[55,438] width:390 range:[0,510,255] type:#integer ticks:0; label vmg "0" pos:[455,444] width:45
 label lmb "青" pos:[25,476]; slider mb pos:[55,470] width:390 range:[0,510,255] type:#integer ticks:0; label vmb "0" pos:[455,476] width:45
 groupBox gh "ハイライト RGB（-255 ～ 255）" pos:[10,518] width:500 height:126
 label lhr "赤" pos:[25,546]; slider hr pos:[55,540] width:390 range:[0,510,255] type:#integer ticks:0; label vhr "0" pos:[455,546] width:45
 label lhg "緑" pos:[25,578]; slider hg pos:[55,572] width:390 range:[0,510,255] type:#integer ticks:0; label vhg "0" pos:[455,578] width:45
 label lhb "青" pos:[25,610]; slider hb pos:[55,604] width:390 range:[0,510,255] type:#integer ticks:0; label vhb "0" pos:[455,610] width:45
 groupBox gg "色相・彩度・明るさ・コントラスト" pos:[10,652] width:500 height:232
 label lhu "色相" pos:[25,679]; slider hue pos:[75,673] width:365 range:[0,360,180] type:#integer ticks:0; label vhu "0°" pos:[450,679] width:55
 label lsa "彩度" pos:[25,711]; slider sat pos:[75,705] width:365 range:[0,300,100] type:#integer ticks:0; label vsa "100%" pos:[450,711] width:55
 label lco "コントラスト" pos:[25,743] width:70; slider con pos:[95,737] width:345 range:[0,300,100] type:#integer ticks:0; label vco "100%" pos:[450,743] width:55
 label lbr "明るさ" pos:[25,775]; slider bri pos:[75,769] width:365 range:[0,300,100] type:#integer ticks:0; label vbr "100%" pos:[450,775] width:55
 label lrange "明るさ・コントラストを適用する元色の明度範囲" pos:[25,806] width:450
 label llow "下限" pos:[25,835]; slider rangeLow pos:[75,829] width:365 range:[0,100,0] type:#integer ticks:0; label vlow "0" pos:[450,835] width:55
 label lhigh "上限" pos:[25,867]; slider rangeHigh pos:[75,861] width:365 range:[0,100,100] type:#integer ticks:0; label vhigh "100" pos:[450,867] width:55

 fn addUnique a x = if x!=undefined and findItem a x==0 do append a x
 fn walk m a =
 (
  if m==undefined then return false
  addUnique a m
  local n=0; try(n=getNumSubMtls m)catch()
  for i=1 to n do( local s=undefined; try(s=getSubMtl m i)catch(); if s!=undefined do walk s a )
  true
 )
 fn collectMats =
 (
  local a=#(), nodes=if rbTarget.state==1 then objects else selection
  for o in nodes where o.material!=undefined do walk o.material a
  a
 )
 fn colorProp m =
 (
  for p in #(#base_color,#baseColor,#basecolor,#Base_Color,#diffuse) where isProperty m p do
  (local v=undefined; try(v=getProperty m p)catch(); if isKindOf v Color do return p)
  undefined
 )
 fn textProp s = (for p in #(#base_color,#baseColor,#basecolor,#Base_Color,#diffuse) where p as string==s do return p; undefined)
 fn cl x=amax 0.0 (amin 1.0 x)
 fn ss a b x=(local t=cl((x-a)/(b-a)); t*t*(3-2*t))
 fn hueShift r g b degrees =
 (
  local maxValue=amax r (amax g b), minValue=amin r (amin g b)
  local delta=maxValue-minValue, h=0.0, s=0.0, v=maxValue
  if delta>0.000001 do
  (
   if maxValue==r then h=60.0*((g-b)/delta)
   else if maxValue==g then h=60.0*(((b-r)/delta)+2.0)
   else h=60.0*(((r-g)/delta)+4.0)
   if h<0.0 do h+=360.0
  )
  if maxValue>0.000001 do s=delta/maxValue
  h+=degrees
  while h<0.0 do h+=360.0
  while h>=360.0 do h-=360.0
  local chroma=v*s, x=chroma*(1.0-abs((mod (h/60.0) 2.0)-1.0)), m=v-chroma
  local rr=0.0,gg=0.0,bb=0.0
  if h<60.0 then(rr=chroma;gg=x)
  else if h<120.0 then(rr=x;gg=chroma)
  else if h<180.0 then(gg=chroma;bb=x)
  else if h<240.0 then(gg=x;bb=chroma)
  else if h<300.0 then(rr=x;bb=chroma)
  else(rr=chroma;bb=x)
  #(rr+m,gg+m,bb+m)
 )
 fn resultColor c =
 (
  local r=c.r/255.0,g=c.g/255.0,b=c.b/255.0, originalY=cl(0.2126*r+0.7152*g+0.0722*b), y=originalY
  local sw=1-ss 0.0 0.5 y, hw=ss 0.5 1.0 y, mw=cl(1-sw-hw)
  r+=(((sr.value-255)*sw+(mr.value-255)*mw+(hr.value-255)*hw)/255.0)
  g+=(((sg.value-255)*sw+(mg.value-255)*mw+(hg.value-255)*hw)/255.0)
  b+=(((sb.value-255)*sw+(mb.value-255)*mw+(hb.value-255)*hw)/255.0)
  local shifted=hueShift r g b (hue.value-180)
  r=shifted[1];g=shifted[2];b=shifted[3]
  local s=sat.value/100.0, y2=0.2126*r+0.7152*g+0.0722*b
  r=y2+(r-y2)*s; g=y2+(g-y2)*s; b=y2+(b-y2)*s
  local originalPercent=originalY*100.0
  if originalPercent>=rangeLow.value and originalPercent<=rangeHigh.value do
  (
   local k=con.value/100.0; r=(r-.5)*k+.5; g=(g-.5)*k+.5; b=(b-.5)*k+.5
   local q=bri.value/100.0; r*=q;g*=q;b*=q
  )
  color (cl(r)*255) (cl(g)*255) (cl(b)*255)
 )
 fn labels =
 (
  vsr.text=(sr.value-255) as string;vsg.text=(sg.value-255) as string;vsb.text=(sb.value-255) as string
  vmr.text=(mr.value-255) as string;vmg.text=(mg.value-255) as string;vmb.text=(mb.value-255) as string
  vhr.text=(hr.value-255) as string;vhg.text=(hg.value-255) as string;vhb.text=(hb.value-255) as string
  vhu.text=(hue.value-180) as string+"°";vsa.text=sat.value as string+"%";vco.text=con.value as string+"%";vbr.text=bri.value as string+"%"
  vlow.text=rangeLow.value as string;vhigh.text=rangeHigh.value as string
 )
 fn preview =
 (
  if originals.count==0 then return false
  with undo off(for e in originals where e[1]!=undefined and isProperty e[1] e[2] do try(setProperty e[1] e[2](resultColor e[3]))catch())
  redrawViews(); true
 )
 fn changed=(labels();if not locking and chkRealtime.checked do preview())
 fn capture =
 (
  mats=collectMats(); originals=#()
  for m in mats do(local p=colorProp m,c=undefined;if p!=undefined do try(c=copy(getProperty m p))catch();if isKindOf c Color do append originals #(m,p,c))
  lblStatus.text="元色を "+originals.count as string+" 件保存しました（検出 "+mats.count as string+" 件）。"
 )
 fn restore =
 (
  if originals.count==0 then false else
  (undo "マテリアルの元色を復元" on(for e in originals where e[1]!=undefined and isProperty e[1] e[2] do try(setProperty e[1] e[2](copy e[3]))catch());redrawViews();true)
 )
 fn resetValues =
 (
  locking=true
  sr.value=255;sg.value=255;sb.value=255;mr.value=255;mg.value=255;mb.value=255;hr.value=255;hg.value=255;hb.value=255
  hue.value=180;sat.value=100;con.value=100;bri.value=100;rangeLow.value=0;rangeHigh.value=100;locking=false;changed()
 )
 fn writeData f =
 (
  setINISetting f "MaterialColorAdjuster" "Version" "1.5"
  setINISetting f "MaterialColorAdjuster" "Count" (originals.count as string)
  for i=1 to originals.count do
  (local e=originals[i],c=e[3],s="Material_"+i as string;setINISetting f s "Name" e[1].name;setINISetting f s "Property"(e[2] as string);setINISetting f s "Red"(c.r as string);setINISetting f s "Green"(c.g as string);setINISetting f s "Blue"(c.b as string))
 )
 fn readData f =
 (
  local n=(getINISetting f "MaterialColorAdjuster" "Count") as integer, available=collectMats(), loaded=#(), used=#()
  for i=1 to n do
  (
   local s="Material_"+i as string, mn=getINISetting f s "Name", p=textProp(getINISetting f s "Property"), hit=undefined
   if p!=undefined do
   (
    for m in available while hit==undefined do
     if findItem used m==0 and m.name==mn and isProperty m p do hit=m
   )
   if hit!=undefined do
   (local r=(getINISetting f s "Red")as float,g=(getINISetting f s "Green")as float,b=(getINISetting f s "Blue")as float;append loaded #(hit,p,color r g b);append used hit)
  )
  mats=available;originals=loaded;loaded.count
 )

 on btnCollect pressed do capture()
 on btnRestore pressed do if not restore() do messageBox "復元できる元色がありません。" title:"マテリアル色調整 v1.5"
 on btnReset pressed do resetValues()
 on chkRealtime changed state do if state do preview()
 on btnSaveFile pressed do
 (
  if originals.count==0 then messageBox "先に元色を保存してください。" title:"マテリアル色調整 v1.5" else
  (local f=getSaveFileName caption:"元色データを保存" types:"マテリアル色データ (*.mca)|*.mca|すべてのファイル (*.*)|*.*|" filename:"MaterialColors_v1_5.mca";if f!=undefined do(writeData f;lblStatus.text="元色データを保存しました: "+filenameFromPath f))
 )
 on btnLoadFile pressed do
 (
  local f=getOpenFileName caption:"元色データを読み込み" types:"マテリアル色データ (*.mca)|*.mca|すべてのファイル (*.*)|*.*|"
  if f!=undefined do(local n=readData f;if n>0 then(lblStatus.text="元色を "+n as string+" 件読み込みました。";if chkRealtime.checked do preview())else messageBox "対象マテリアルと一致するデータがありません。\n対象範囲とマテリアル名を確認してください。" title:"マテリアル色調整 v1.5")
 )
 on sr changed v do changed();on sg changed v do changed();on sb changed v do changed()
 on mr changed v do changed();on mg changed v do changed();on mb changed v do changed()
 on hr changed v do changed();on hg changed v do changed();on hb changed v do changed()
 on hue changed v do changed();on sat changed v do changed();on con changed v do changed();on bri changed v do changed()
 on rangeLow changed v do
 (
  if not locking and v>rangeHigh.value do(locking=true;rangeHigh.value=v;locking=false)
  changed()
 )
 on rangeHigh changed v do
 (
  if not locking and v<rangeLow.value do(locking=true;rangeLow.value=v;locking=false)
  changed()
 )
 on MaterialColorAdjuster_Rollout open do
 (
  -- 初回表示時も値を明示的に代入し、つまみの描画位置と内部値を同期する。
  locking=true

  sr.range=[0,510,255]; sg.range=[0,510,255]; sb.range=[0,510,255]
  mr.range=[0,510,255]; mg.range=[0,510,255]; mb.range=[0,510,255]
  hr.range=[0,510,255]; hg.range=[0,510,255]; hb.range=[0,510,255]
  hue.range=[0,360,180];sat.range=[0,300,100];con.range=[0,300,100];bri.range=[0,300,100]
  rangeLow.range=[0,100,0];rangeHigh.range=[0,100,100]

  sr.value=255; sg.value=255; sb.value=255
  mr.value=255; mg.value=255; mb.value=255
  hr.value=255; hg.value=255; hb.value=255
  hue.value=180;sat.value=100;con.value=100;bri.value=100
  rangeLow.value=0;rangeHigh.value=100

  locking=false
  labels()
  capture()
 )
)
createDialog MaterialColorAdjuster_Rollout
