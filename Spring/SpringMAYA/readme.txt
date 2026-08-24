インストール手順

SpringMAYA.png と SpringMAYA.py　を
C:\Users\〇自分の名前〇〇\Documents\maya\scripts
にコピー

Mayaを起動して pythonに以下を貼り付け

import importlib, sys
importlib.reload(sys.modules["SpringMAYA"]) if "SpringMAYA" in sys.modules else importlib.import_module("SpringMAYA")

マウス真ん中ドラッグでカスタムの中に入れる。
右クリックで編集に入り、アイコンを指定して完了