  <h1> Simple 3D Picker </h1>
  <p>オブジェクト選択するピッカーを作成するスクリプトと<br>
ピッカーとして使用するスクリプトの２つ<br>
3dsMAX、Maya、Blenderの３つで見た目と使用方法が同じように制作<br></p>
  <hr>
  <h2 id="3dsMAX版 ピッカー">
  <a href="https://github.com/cgtc11/Picker/tree/main/3dsmax">3dsMAX版 Download</a>
　</h2>
  <p><strong>目的:</strong> 3dsMAX2025以降で使用可能なセット　おまけ付き</p><br>

  <h2 id="Maya版 ピッカー">
  <a href="https://github.com/cgtc11/Picker/tree/main/Maya">Maya版 Download</a>
　</h2>
  <p><strong>目的:</strong> Maya2025以降で使用可能なセット</p><br>

  <h2 id="Blender版 ピッカー">
  <a href="https://github.com/cgtc11/Picker/tree/main/Blender">Blender版 Download</a>
　</h2>
  <p><strong>目的:</strong> Blender5.1以降で使用可能なセット</p><br>
<br>
■ PickerEditor<br>
<br>
１．ピッカーとして使う画像を用意（ここが肝心でここが全て）<br>
<br>
２．作業画面にドラッグ＆ドロップで画像を読み込み<br>
　反応の欲しい場所をマウス左ドラッグで囲い関連付けして作成<br>
　右にリストが作成されるので、囲った場所が気に入らない場合は数値を変更して微調整<br>
　位置とサイズ、色を後から変更可<br>
 <br>
<img alt="BipedScaler" src="https://github.com/cgtc11/image/blob/main/PickerEditor_MAX2.png" /><br>
<br>
　オブジェクトを選択（複数可）して「GetSelect」ボタンで名前表示（手動入力可）<br>
　囲って作成したエリアと、選択オブジェクト名の両方を確認して「ResistarArea」ボタンを押すと関連付け<br>
　リスト選択して「DeleteSelected」でリストを消せます<br>
<br>
　設定はJOSN形式で保存、読込できます<br>
　中は開けば解るような単純なものなので、テキストベースで編集も可<br>
　画像と同じ名前で同じフォルダ内に保存しておくと画像読込時に同時に開きます<br>
<br>
MAX版、Maya版、Blender版の見た目と使い方はほぼ同じ<br>
<img alt="BipedScaler" src="https://github.com/cgtc11/image/blob/main/PickerEditor2.png" /><br>
<br>
■ PickerPlayer<br>
１．起動後、ピッカーとして使用する画像をウィンドウにドラッグ＆ドロップ<br>
　プレーヤーは複数起動可能。別キャラは別ウインドウで扱ってください<br>
<br>
　設定ファイルをドラッグ＆ドロップ<br>
　画像と同じ名前で同じフォルダ内に設定ファイルがあると画像読込時に同時に開きます<br>
<br>
　登録した四角部分をクリックすると登録したオブジェクトが選択できます<br>
　単純なピッカーです、名称とか曲線等は画像に描き込んでください<br>
<br>
・画像をドラッグ＆ドロップで読み込み、設定ファイルは画像と同名なら自動で読み込まれる<br>
・MAXの場合はCTRL+クリック、Maya、BlenderはShift+クリックで複数選択可、もう一度クリックで解除<br>
・ドラッグで囲っても複数選択可<br>
・複数起動可<br>
<br>
プレーヤーも同じ見え方です。単純な選択ツールなので、人以外でも対応可<br>
<img alt="BipedScaler" src="https://github.com/cgtc11/image/blob/main/PickerPlayer3.png" /><br>
<br>
