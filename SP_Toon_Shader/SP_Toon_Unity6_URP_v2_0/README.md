# SP Toon Shader URP — Unity 6 v2.0

## 対応環境

- Unity 6
- Universal Render Pipeline（URP）
- メンテナー：DiGiMonkey

## 導入方法

### 推奨：プロジェクトのPackagesフォルダーへ配置

解凍後の次のフォルダーを、

```text
com.digimonkey.sp-toon-urp
```

Unityプロジェクト内の `Packages` フォルダーへコピーしてください。

```text
UnityProject
├─ Assets
├─ Packages
│  ├─ manifest.json
│  └─ com.digimonkey.sp-toon-urp
│     ├─ package.json
│     ├─ Runtime
│     ├─ Editor
│     ├─ README.md
│     └─ LICENSE.md
└─ ProjectSettings
```

Unityプロジェクトを開くと、Package Managerが自動的に認識します。

## マテリアル作成

1. Projectウィンドウで右クリック
2. `Create > Material`
3. Shaderを `DiGiMonkey/SP Toon URP` に変更
4. マテリアルをモデルへ割り当て

---

## パラメーター解説

### Lighting

| パラメーター | 説明 |
|---|---|
| HDR Enabled | ONにするとUnityシーンのライト（Directional / Point / Spot）とSkybox/HDRIを使用してトゥーン判定を行う。OFFはLight Positionのみ使用。 |
| HDR Ambient Strength | HDR Enabled ON時のみ有効。Skybox/HDRI環境光をトゥーン判定に加える補助値。通常は0のままで使用。 |
| Light Position | HDR Enabled OFF時に使用する手動ライト位置（XYZ）。Numeric欄とX/Y/Zスライダーで操作でき、相互に同期する。 |

---

### Hull Outline（インバーテッドハル）

法線方向にメッシュを膨らませる方式のアウトライン。シルエット外側に出るクラシックなアニメ風ライン。

| パラメーター | 説明 |
|---|---|
| Use Hull Outline | ONでHull Outlineを有効化。OFFにしてもOutlineなど他の描画には影響しない。 |
| Width | アウトラインの太さ（0〜0.1）。単位はワールドスペース。 |
| Hull Outline Color | アウトラインの色。 |
| Hull Outline Texture | アウトラインにテクスチャを乗算。 |
| Noise Strength | アウトライン幅にノイズを加える強さ（0〜5）。0=均一、上げるほどランダムな太さになる。 |
| Noise Scale | ノイズの密度（0.1〜200）。小さい値=大きなうねり、大きい値=細かいばらつき。ワールド座標ベースのため、カメラを動かしても線が震えない。 |

---

### Outline（NdVアウトライン）

法線とカメラ方向の角度（N dot V）を使ったシェーダー表面上のアウトライン。インバーテッドハルとは独立した別のエフェクト。

| パラメーター | 説明 |
|---|---|
| Use Outline | ONでOutlineを有効化。 |
| Reverse Outline | ONにするとマスクを反転し、アウトラインが内側に入る。 |
| Outline Thickness | アウトラインの範囲（0〜1）。NdV値との比較しきい値。 |
| Outline Blur | アウトライン境界のぼかし量（0〜5）。0=シャープ、上げるほどグラデーション。 |
| Outline Color | アウトラインの色。 |
| Outline Texture | アウトラインにテクスチャを乗算。 |

---

### Inline（インライン）

Curvature Map（曲率マップ）を使ってメッシュの凹み部分や折れ目にラインを入れる。Substance Painterなどでベイクしたマップを使用する。

| パラメーター | 説明 |
|---|---|
| Inline Thickness | インラインの範囲（0〜1）。Curvature値との比較しきい値。 |
| Inline Blur | インライン境界のぼかし量（0〜5）。 |
| Inline on Top | 0.0=Outlineが最前面（Inlineの上にOutlineを描画）、1.0=Inlineが最前面（Outlineの上にInlineを描画）。中間値はブレンド。 |
| Inline Color | インラインの色。 |
| Inline Texture | インラインにテクスチャを乗算。 |
| Inline Curvature Map | Substance Painterなどでベイクしたカーブチャーマップ。白黒が逆の場合はInvert Curvatureを使用。 |
| Invert Curvature | ONにするとCurvature Mapの白黒を反転する。 |

---

### Toon Gradation（トゥーン階調）

ライティング値（N dot L）を使って複数の色段階に分けるトゥーンシェーディング。各色はColors / Texturesセクションで設定する。

| パラメーター | 説明 |
|---|---|
| Toon Param 2〜7 | 各トゥーン色が切り替わるNdLのしきい値（-1〜1）。-1.0=常に非表示、0.0=明暗境界、1.0=完全ライト側。Param3〜7のデフォルト-1.0は非表示状態。 |
| Toon Blur | 全トゥーン境界に共通で適用するぼかし量（0〜5）。0=シャープな2値切り替え、上げるほどグラデーション。 |

**合成順序：**  
Base Color → Toon Color 2 → 3 → 4 → 5 → 6 → 7（後の色が上書き）

---

### Normal Map

法線マップでトゥーン境界をデコボコにする。NdLの計算前に適用するためトゥーン階調の形状が変化する。

| パラメーター | 説明 |
|---|---|
| Normal Map | タンジェント空間の法線マップテクスチャ。 |
| Normal Strength | 法線の強さ（-5〜5）。1.0=通常、マイナスで法線反転（凹凸が逆になる）。 |

---

### Ambient Occlusion（AO）

AOマップをトゥーン色に乗算合成する。接触部や凹み部分を常時暗くする効果。

| パラメーター | 説明 |
|---|---|
| AO Map | グレースケールのAOテクスチャ（Rチャンネル使用）。白=AO無し、黒=AO最大。 |
| AO Strength | AOの強さ（0〜5）。0=AO無効、上げるほど影響が強くなる。 |
| AO Color | AO適用部分の色。黒=暗い影、任意の色に変更可能（色付きAOが可能）。 |

---

### Rim Light（リムライト）

`(1 - NdV)^Sharpness × NdL` でライト方向側のエッジのみ光らせる。逆光で後ろから光が当たるような表現。

| パラメーター | 説明 |
|---|---|
| Use Rim Light | ONでリムライトを有効化。 |
| Rim Strength | リムの明るさ（0〜20）。トゥーン色の後に加算合成。 |
| Rim Sharpness | リムの鋭さ（0〜50）。小さい=広いリム、大きい=細く鋭いリム。 |
| Rim Color | リムライトの色。 |

---

### Thickness（薄膜透過 / SSS風）

Thickness Mapで逆光時の透過感を表現する。耳・指先・草・薄い布など、光が透ける素材向け。

| パラメーター | 説明 |
|---|---|
| Use Thickness | ONでThicknessを有効化。 |
| Thickness Map | グレースケールテクスチャ。白=薄い（透けやすい）、黒=厚い（透けにくい）。 |
| Thickness Strength | 透過の強さ（0〜10）。トゥーン色の後に加算合成。 |
| Thickness Color | 透過光の色。暖色（オレンジ・赤）を指定すると皮膚透過らしい見た目になる。 |

---

### MatCap（World Space Normals）

カメラ空間の法線方向でテクスチャをUV参照する。セルルックな金属光沢・ハイライト・環境反射風の表現に使用。

| パラメーター | 説明 |
|---|---|
| Use MatCap | ONでMatCapを有効化。 |
| MatCap Texture | 球面テクスチャ（MatCap画像）。 |
| MatCap Strength | MatCapの強さ（0〜10）。 |
| Blend Mode (Add / Multiply) | Add=加算合成（明るくなる）、Multiply=乗算合成（色味が変わる）。 |

---

### Colors / Textures

| パラメーター | 説明 |
|---|---|
| Base Color / Texture | 最も明るい面の色とテクスチャ。色とテクスチャは乗算される。 |
| Toon Color 2〜7 / Texture | 各トゥーン段階の色とテクスチャ。Toon Param 2〜7のしきい値で切り替わる。 |
| Base Texture Mapping | Base TextureのTiling / Offset設定。 |

---

### Surface

| パラメーター | 説明 |
|---|---|
| Surface Mode | 描画モードを5択で選択（下記参照）。 |
| Opacity Map | グレースケールテクスチャ。白=不透明、黒=透明。未割り当て時は全面不透明。 |
| Invert Opacity Map | ONでOpacity Mapの白黒を反転する。 |
| Alpha Clip (0/1) | Cutout / Cutout Both Sidesモード時のみ有効。ONにするとOpacity Mapを0/1の二値に変換する。 |
| Opacity Level | Alpha Clip ON時のしきい値（0〜1）。この値より暗い部分が透明になる。 |

#### Surface Mode 一覧

| モード | 説明 | 用途 |
|---|---|---|
| Opaque | 片面・不透明 | 通常のキャラクター・背景 |
| Cutout | 片面・Opacity Mapで0/1切り抜き | 片面の草・フェンスなど |
| Transparent | 片面・半透明 | 瓶・ガラス（片面） |
| Cutout Both Sides | 両面・Opacity Mapで0/1切り抜き | 髪・草・木の葉 |
| Transparent Both Sides | 両面・半透明 | 瓶・ガラス（両面）・水面 |

---

## 合成順序（Fragシェーダー内）

```
Base Color × Base Texture
  → Toon Gradation（Normal Map適用後のNdLで判定）
  → × AO（乗算）
  → + Rim Light（加算）
  → + Thickness SSS（加算）
  → + / × MatCap（加算 or 乗算）
  → Inline / Outline の合成（Inline on Topで順序制御）
  → Hull Outline（別パス・Cull Front）
```

---

## テクスチャ出力について（Substance Painter）

| テクスチャ | 用途 |
|---|---|
| Curvature | Inline Curvature Map |
| Ambient Occlusion | AO Map |
| Normal Map（World Space） | Normal Map |
| Thickness | Thickness Map |

---

## v2.0 新機能

- **Hull Outline（インバーテッドハル）** 追加：幅・色・テクスチャ・ノイズ対応
- **Normal Map** 追加：トゥーン境界に影響、強度マイナスで法線反転
- **Ambient Occlusion** 追加：乗算合成、AO色変更可
- **Rim Light** 追加：ライト方向連動、強度・シャープネス・色
- **Thickness SSS** 追加：逆光透過感、Thickness Map対応
- **MatCap（World Space Normals）** 追加：Add / Multiply選択
- **Surface Mode** 追加：Opaque / Cutout / Transparent / Cutout Both Sides / Transparent Both Sidesの5択
- **Opacity Map** 追加：白黒テクスチャで透明度制御、反転トグル付き
- **Inline on Top** 追加：InlineとOutlineの描画順をスライダーで制御
