# コマンドデッキ 早見表(まとめ直し版) + 各種機能の使い方

このファイルは、これまでのやり取りで確認・作成した内容を全部まとめ直したものです。
「タイプ」が **オペレーター** のものは Operator ID / Operator Args / Execution Context を、
「タイプ」が **Inline Python** のものは Python Code の欄にそのまま貼り付けてください。
「タイプ」が **Macro (Sequence)** のものは、複数ステップに分けて登録します(後述)。

自信度の目安:◎確実(動作確認済み) / ○たぶん大丈夫(標準的な命名から推測) / △要確認(未確認、または環境依存)

---

## 1. 早見表

### 移動・回転・拡縮(ツール切り替え)

| 項目 | タイプ | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|---|
| 移動 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.move"}` | Exec | ◎ |
| 回転 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.rotate"}` | Exec | ◎ |
| 拡縮 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.scale"}` | Exec | ◎ |
| ボックス選択 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.select_box"}` | Exec | ○ |
| 円選択 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.select_circle"}` | Exec | ○ |
| なげなわ選択 | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.select_lasso"}` | Exec | ○ |
| アノテート | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.annotate"}` | Exec | ◎ |
| アノテート消しゴム | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.annotate_eraser"}` | Exec | △ |
| メジャー(分度器) | オペレーター | `wm.tool_set_by_id` | `{"name": "builtin.measure"}` | Exec | ○ |

Custom Expression(Highlight If用、共通パターン):
`context.workspace.tools.from_space_view3d_mode(context.mode, create=False).idname == 'builtin.移動なら move'`
※移動/回転/拡縮/頂点/エッジ/フェースは「Active Tool」系のプリセットが既にあるので自分で書く必要なし。

### 頂点・辺・面の選択モード(編集モード中のみ有効)

| 項目 | タイプ | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|---|
| Vertex | オペレーター | `mesh.select_mode` | `{"type": "VERT"}` | Exec | ◎ |
| Edge | オペレーター | `mesh.select_mode` | `{"type": "EDGE"}` | Exec | ◎ |
| Face | オペレーター | `mesh.select_mode` | `{"type": "FACE"}` | Exec | ◎ |

Highlight Ifのプリセット「Mesh Select Mode: Vertex/Edge/Face」が既にあります。

### 座標系(グローバル・ローカル・法線) - Inline Python

| 項目 | Python Code | Custom Expression |
|---|---|---|
| グローバル | `context.scene.transform_orientation_slots[0].type = 'GLOBAL'` | `... == 'GLOBAL'` |
| ローカル | `context.scene.transform_orientation_slots[0].type = 'LOCAL'` | `... == 'LOCAL'` |
| 法線(ノーマル) | `context.scene.transform_orientation_slots[0].type = 'NORMAL'` | `... == 'NORMAL'` |

### ビューポートシェーディング - Inline Python

| 項目 | Python Code | Custom Expression |
|---|---|---|
| ワイヤーフレーム | `context.space_data.shading.type = 'WIREFRAME'` | `... == 'WIREFRAME'` |
| ソリッド | `context.space_data.shading.type = 'SOLID'` | `... == 'SOLID'` |
| マテリアルプレビュー | `context.space_data.shading.type = 'MATERIAL'` | `... == 'MATERIAL'` |
| レンダー | `context.space_data.shading.type = 'RENDERED'` | `... == 'RENDERED'` |

### スナップ(ON/OFF切り替え)

| 項目 | タイプ | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|---|
| スナップ切り替え | オペレーター | `wm.context_toggle` | `{"data_path": "scene.tool_settings.use_snap"}` | Exec | ○ |

### 選択の縮小・拡大

| 項目 | タイプ | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|---|
| 選択の縮小 | オペレーター | `mesh.select_less` | (空欄) | Exec | ○ |
| 選択の拡大 | オペレーター | `mesh.select_more` | (空欄) | Exec | ○ |

### ループ選択・リング選択(Blender 5.1で仕様変更あり)

Blender 5.1で、以前の`mesh.loop_multi_select(ring=True/False)`という1つのオペレーターが分割されました。

| 項目 | タイプ | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|---|
| ループ選択(選択範囲から) | オペレーター | `mesh.loop_multi_select` | `{}` | Exec | ○(`ring`引数は無くなった) |

**リング選択**は、クリック位置の情報(`edge_index`)を要求する作りに変わっているため、ボタンからはInline Pythonで「今選択しているエッジ」を自動で探して渡す必要があります:

```python
import bmesh; obj = context.edit_object; bm = bmesh.from_edit_mesh(obj.data); edge = next((e for e in reversed(bm.select_history) if isinstance(e, bmesh.types.BMEdge)), None) or next((e for e in bm.edges if e.select), None); bpy.ops.mesh.edgering_select(object_index=0, edge_index=edge.index) if edge else None
```
※`ring`引数はもう存在しないので入れない。事前にエッジを1本選択してから押す。

**注意**: フェース/頂点選択モードで使うと、選択したエッジに対して**垂直方向**のフェースループのように見える選択になります。これはBlender本体のCtrl+Alt+クリックでも同じ、仕様どおりの挙動です。

### インセット・ベベル・ブリッジなど(3ds Max/Maya用語の対応表)

| 項目 | Operator ID | Operator Args | Execution Context | 確度 |
|---|---|---|---|---|
| インセット | `mesh.inset` | `{}` | **Invoke** | ◎ |
| ベベル | `mesh.bevel` | `{}` | **Invoke** | ◎ |
| ブリッジ | `mesh.bridge_edge_loops` | `{}` | Exec | ◎ |
| 選択非表示 | `mesh.hide` | `{"unselected": False}` | Exec | ◎ |
| すべて表示 | `mesh.reveal` | `{"select": True}` | Exec | ◎ |
| 面反転 | `mesh.flip_normals` | `{}` | Exec | ◎ |
| アタッチ(オブジェクトモード専用) | `object.join` | `{}` | Exec | ○ |
| デタッチ | `mesh.separate` | `{"type": "SELECTED"}` | Exec | ○ |
| ソフトエッジ | `mesh.mark_sharp` | `{"clear": True}` | Exec | ○ |
| ハードエッジ | `mesh.mark_sharp` | `{"clear": False}` | Exec | ○ |

### 凸凹をならす(スムーズ/リラックス)

LoopToolsはBlender 4.2以降**同梱廃止**、Extensionsから別途インストールが必要(Preferences → Get Extensions → "LoopTools"で検索)。

| 項目 | Operator ID | Operator Args | Execution Context | 確度 | 備考 |
|---|---|---|---|---|---|
| スムーズ(標準機能) | `mesh.vertices_smooth` | `{"factor": 0.5, "repeat": 1}` | Exec | ○ | 繰り返すと縮んで丸くなる |
| スムーズ(体積保持) | `mesh.vertices_smooth_laplacian` | `{"repeat": 1, "lambda_factor": 0.00005, "lambda_border": 0.00005}` | Exec | ○ | やや自然 |
| リラックス(LoopTools要インストール) | `mesh.looptools_relax` | `{}` | Exec | △ | 要LoopTools有効化 |
| 平面化(LoopTools要インストール) | `mesh.looptools_flatten` | `{}` | Exec | △ | 要LoopTools有効化 |

### 平面化(法線に対してZ=0にする、標準機能のみで再現)- Inline Python

選択頂点の平均法線を軸にした平面へ、各頂点を投影します。

```python
import bmesh, mathutils; bm = bmesh.from_edit_mesh(context.edit_object.data); sv = [v for v in bm.verts if v.select]; n = (sum((v.normal for v in sv), mathutils.Vector((0,0,0)))); n.normalize() if n.length > 0 else None; c = sum((v.co for v in sv), mathutils.Vector((0,0,0))) / len(sv) if sv else None; [setattr(v, 'co', v.co - n * (v.co - c).dot(n)) for v in sv] if (sv and n.length > 0) else None; bmesh.update_edit_mesh(context.edit_object.data)
```
※`mathutils`のimportを忘れると`NameError`になるので注意。

### コンストレイント(3ds Max用語)

| 項目 | タイプ | Operator ID / Python Code | Execution Context | 確度 |
|---|---|---|---|---|
| エッジ拘束(頂点スライド) | オペレーター | `transform.vert_slide` / `{}` | **Invoke** | ◎ |

面拘束(Face)は、スナップを「面」+「個別投影」にするON/OFFトグル。Inline Python:
```python
ts = context.scene.tool_settings; on = not (ts.use_snap and 'FACE' in ts.snap_elements and ts.use_snap_project); ts.use_snap = on; ts.snap_elements = {'FACE'} if on else ts.snap_elements; ts.use_snap_project = on
```
Highlight If (Custom Expression): `context.scene.tool_settings.use_snap and context.scene.tool_settings.use_snap_project`

### ピボット関連

| 項目 | タイプ | Python Code | Custom Expression | 確度 |
|---|---|---|---|---|
| ピボット:中間点 | Inline Python | `context.scene.tool_settings.transform_pivot_point = 'MEDIAN_POINT'` | `... == 'MEDIAN_POINT'` | ◎ |
| ピボット編集(Affect Only Origins) | Inline Python | `context.scene.tool_settings.use_transform_data_origin = not context.scene.tool_settings.use_transform_data_origin` | `context.scene.tool_settings.use_transform_data_origin` | ◎ |
| 原点を形状中心へ(オブジェクトモード) | オペレーター | `object.origin_set` / `{"type": "ORIGIN_GEOMETRY", "center": "MEDIAN"}` | Exec | ◎ |

他のピボット種類は`transform_pivot_point`の値だけ変えればOK:`INDIVIDUAL_ORIGINS`(個別)/ `CURSOR`(3Dカーソル)/ `ACTIVE_ELEMENT`(アクティブ)/ `BOUNDING_BOX_CENTER`(バウンディングボックス中心)。

---

## 2. Command Deck本体の機能まとめ

### Macro (Sequence) タイプ
複数のオペレーター/Inline Pythonをステップとして登録し、上から順に実行するボタンタイプ。
- 編集モードでボタンのTypeを`Macro (Sequence)`にすると、ステップ一覧(Add/Remove/↑↓)が出る
- 「Record Steps」ボタンで、実際に一連の操作(例: S→X→0→Enter)を行うと、実行されたオペレーターが1つずつ自動でステップに追加され続ける(Stopを押すまで)
- 途中のステップが失敗(CANCELLED)したら、そこでマクロ全体を止めてエラー表示

### Add(追加)ボタンの挙動
リストで何か選択している状態で「追加」を押すと、新しいボタンは**選択中のボタンの「縦(グリッド行)」の位置に割り込んで挿入**され、その行以降にある全ボタン(列問わず)の縦が+1されます。何も選択していなければ、今まで通り空いている位置に追加されます。

### Grid Row (縦) Shift ボタン
選択中のボタン(とそれ以降)の縦(グリッド行)を、追加とは関係なく単独で+1 / -1できます。新しいボタンを追加せずに行を空けたい/詰めたい時に使用。

### 一覧の並び替え
↑↓(1段ずつ)に加えて、先頭へ/末尾へ一気に移動するボタンも追加済み。

### ツールバー非表示設定
Edit > Preferences > Add-ons > Command Deck に「ツールバーを表示」チェックがあります。オフにすると、パネル上部の「編集モード / エクスポート / インポート / 設定保存」の行が隠れます(チェックを外すと同時に、安全に編集モードもOFFになります)。

### 削除済み機能
「Auto Arrange」は、大量にボタンを配置した状態で押すと全部の配置が壊れ、しかも元に戻せない不具合があったため、機能ごと完全に削除しました。

---

## 3. Op Recorder(独立した診断ツール)

`op_recorder.py` という、Command Deckとは別のアドオンです。3Dビューポートのサイドバーに「Op Recorder」タブが追加され、何か操作するたびに自動で以下がリアルタイム表示されます(ボタンを押す必要なし):

- Type
- Operator ID
- Operator Args
- Context(推測)

4項目は普通の入力欄になっているので、クリック&ドラッグで選択してCtrl+Cでコピーできます。Command Deckの記録機能がうまく働かない時の確認用に使ってください。

※「Context(推測)」は決め打ちリストによる推測であり、確実な判定ではありません(Blenderは実行時のコンテキストを後から取得する手段を持っていないため)。

---

## 4. Data Path(データの場所)の調べ方

一覧に無い設定を自分で見つけたいときは、この方法を使ってください。

### 手順
1. Blenderの画面で、調べたい設定のボタンやチェックボックス、アイコンの上にマウスを持っていく
2. その状態で右クリックする
3. 出てきたメニューから「Copy Data Path(データパスをコピー)」を選ぶ(無ければ「Copy Full Data Path」)
4. コピーされた文字(例: `space_data.shading.type`)の前に`context.`を付け足せば、そのままCustom ExpressionやInline Pythonで使える

### ツール(道具)の名前を調べたいとき
右クリックで「Copy Data Path」が出ない場合、Blenderの「テキストエディタ」で以下を実行:
```python
import bpy
print(bpy.context.workspace.tools.from_space_view3d_mode(bpy.context.mode, create=False).idname)
```
Window → Toggle System Consoleでコンソールを開いておくと、結果がそこに表示されます。

---

## 5. まだ未確認・要注意な項目一覧

- アノテート消しゴム(`builtin.annotate_eraser`)、アノテートLine/Poly(`builtin.annotate_line` / `builtin.annotate_polygon`)
- スナップ切り替え(`wm.context_toggle`)
- メジャー(`builtin.measure`)
- アタッチ/デタッチ(`object.join` / `mesh.separate`)、ソフト/ハードエッジ(`mesh.mark_sharp`)
- 面拘束のInline Pythonトグル(`use_snap_project`というプロパティ名が実在するか)
- ループ選択の`mesh.loop_multi_select`(Blender 5.1で引数無しになっているか)

これらは「Record This Button」またはOp Recorderで一度実機確認してから使うことをおすすめします。
