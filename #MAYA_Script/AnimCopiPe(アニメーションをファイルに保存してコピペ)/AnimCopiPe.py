import maya.cmds as cmds
import json
import os
import re
import glob

class AnimTransferFinalV5:
    def __init__(self):
        self.desktop = os.path.join(os.path.expanduser("~"), "Desktop").replace("\\", "/")
        self.create_ui()

    def get_file_path(self):
        name = cmds.textField(self.name_field, q=True, text=True).strip()
        if not name:
            name = "anim_data"
        return os.path.join(self.desktop, name + ".json").replace("\\", "/")

    def get_thumb_path(self):
        name = cmds.textField(self.name_field, q=True, text=True).strip()
        if not name:
            name = "anim_data"
        return os.path.join(self.desktop, name).replace("\\", "/")

    def create_ui(self):
        if cmds.window("AnimTransferV4Win", exists=True):
            cmds.deleteUI("AnimTransferV4Win")

        cmds.window("AnimTransferV4Win", title="Anim Transfer v2.2", widthHeight=(370, 450))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnOffset=['both', 10])

        # ── ファイル名 ────────────────────────────────────
        cmds.separator(h=6, style='none')
        cmds.text(label="【読込/保存 ファイル名】　Desktop保存", align="left", fn="boldLabelFont")
        self.name_field = cmds.textField(text="anim_data", placeholderText="ファイル名（拡張子不要）")

        self.save_thumb = cmds.checkBox(label="サムネイルも保存する（800x400 JPG）", value=False)

        # ── 保存設定 ──────────────────────────────────────
        cmds.separator(h=4, style='in')
        cmds.text(label="【保存設定】", align="left", fn="boldLabelFont")
        self.include_hierarchy = cmds.checkBox(label="階層下すべて含む", value=True)
        self.scene_wide = cmds.checkBox(
            label="シーン全体保存（コントロールリグ構造が複雑な場合）",
            value=False,
            onCommand=self.on_scene_wide_on,
            offCommand=self.on_scene_wide_off
        )

        # ── 貼り付け照合モード ────────────────────────────
        cmds.separator(h=4, style='in')
        cmds.text(label="【貼り付け照合モード】", align="left", fn="boldLabelFont")

        self.match_mode_col = cmds.radioCollection()
        self.match_name     = cmds.radioButton(   # ← デフォルト
            label="名前が同じもの同士でコピー",
            annotation="ショートネームが一致するノードにだけコピー。一致しないものはスキップ",
            select=True
        )
        self.match_order    = cmds.radioButton(
            label="順番ベース（名前無視）",
            annotation="保存順と貼り付け先の順番だけで対応付けします"
        )
        self.match_hier_lr  = cmds.radioButton(
            label="階層ベース・L/R を混同しない",
            annotation="順番で対応付けしつつ、L側↔R側になる場合はスキップ"
        )
        self.match_strict   = cmds.radioButton(
            label="名前・構造・順番すべて一致のみ",
            annotation="ノード数と全ノード名が完全一致しない場合は移植を中止"
        )

        cmds.separator(h=6, style='none')
        cmds.button(label="アニメーションをデスクトップへ保存", command=self.save_anim, bgc=[0.4, 0.5, 0.4])
        cmds.button(label="アニメーションを読み込んで貼り付け", command=self.load_anim, bgc=[0.4, 0.4, 0.6])
        cmds.separator(h=6, style='none')

        cmds.showWindow("AnimTransferV4Win")

    # ── UI コールバック ───────────────────────────────────
    def on_scene_wide_on(self, *args):
        cmds.checkBox(self.include_hierarchy, e=True, enable=False)

    def on_scene_wide_off(self, *args):
        cmds.checkBox(self.include_hierarchy, e=True, enable=True)

    # ── ノード収集 ────────────────────────────────────────
    def expand_hierarchy(self, root):
        all_descendants = cmds.listRelatives(root, ad=True, fullPath=True) or []
        filtered = [n for n in all_descendants if cmds.nodeType(n) in ('transform', 'joint')]
        filtered.reverse()
        return filtered

    def get_short_name(self, full_path):
        return full_path.split("|")[-1]

    def get_save_nodes(self, selections):
        nodes = []
        include_hier = cmds.checkBox(self.include_hierarchy, q=True, v=True)
        for root in selections:
            nodes.append(root)
            if include_hier:
                nodes.extend(self.expand_hierarchy(root))
        return nodes

    def get_scene_animated_nodes(self):
        anim_curves = cmds.ls(type='animCurve') or []
        animated_nodes = set()
        for curve in anim_curves:
            connections = cmds.listConnections(curve, destination=True, source=False) or []
            for conn in connections:
                if cmds.nodeType(conn) in ('transform', 'joint'):
                    animated_nodes.add(cmds.ls(conn, l=True)[0])
        if not animated_nodes:
            return []
        all_nodes = cmds.ls(type=['transform', 'joint'], l=True) or []
        return [n for n in all_nodes if n in animated_nodes]

    def get_load_nodes(self, selections):
        nodes = []
        for root in selections:
            nodes.append(root)
            nodes.extend(self.expand_hierarchy(root))
        return nodes

    # ── L/R 判定 ──────────────────────────────────────────
    def get_lr_side(self, name):
        if re.match(r'^[Ll]_', name) or re.match(r'^[Ll]eft[_\s]', name, re.IGNORECASE):
            return 'L'
        if re.match(r'^[Rr]_', name) or re.match(r'^[Rr]ight[_\s]', name, re.IGNORECASE):
            return 'R'
        if re.search(r'[_\s][Ll]$', name) or re.search(r'[_\s][Ll]eft$', name, re.IGNORECASE):
            return 'L'
        if re.search(r'[_\s][Rr]$', name) or re.search(r'[_\s][Rr]ight$', name, re.IGNORECASE):
            return 'R'
        return 'none'

    # ── サムネイル保存 ────────────────────────────────────
    def save_thumbnail(self):
        thumb_base = self.get_thumb_path()
        current_frame = cmds.currentTime(q=True)
        try:
            cmds.playblast(
                frame=[current_frame],
                format='image',
                compression='jpg',
                widthHeight=[800, 400],
                filename=thumb_base,
                percent=100,
                viewer=False,
                showOrnaments=False,
                forceOverwrite=True
            )
            # playblast はフレーム番号付きで出力するのでリネーム
            # 例: anim_data.0048.jpg → anim_data.jpg
            pattern = thumb_base + ".*.jpg"
            files = sorted(glob.glob(pattern))
            if files:
                dest = thumb_base + ".jpg"
                if os.path.exists(dest):
                    os.remove(dest)
                os.rename(files[-1], dest)
                print(f"サムネイル保存: {dest}")
        except Exception as e:
            cmds.warning(f"サムネイル保存に失敗しました: {e}")

    # ── キーデータ収集 ────────────────────────────────────
    def collect_key_data(self, node, attr):
        times = cmds.keyframe(node, at=attr, q=True, tc=True)
        if not times:
            return None
        values      = cmds.keyframe(node, at=attr, q=True, vc=True)               or []
        in_types    = cmds.keyTangent(node, at=attr, q=True, inTangentType=True)  or []
        out_types   = cmds.keyTangent(node, at=attr, q=True, outTangentType=True) or []
        in_angles   = cmds.keyTangent(node, at=attr, q=True, inAngle=True)        or []
        out_angles  = cmds.keyTangent(node, at=attr, q=True, outAngle=True)       or []
        in_weights  = cmds.keyTangent(node, at=attr, q=True, inWeight=True)       or []
        out_weights = cmds.keyTangent(node, at=attr, q=True, outWeight=True)      or []
        keys = []
        for j, t in enumerate(times):
            keys.append({
                "t":  t,
                "v":  values[j]       if j < len(values)       else 0.0,
                "it": in_types[j]     if j < len(in_types)     else "auto",
                "ot": out_types[j]    if j < len(out_types)    else "auto",
                "ia": in_angles[j]    if j < len(in_angles)    else 0.0,
                "oa": out_angles[j]   if j < len(out_angles)   else 0.0,
                "iw": in_weights[j]   if j < len(in_weights)   else 1.0,
                "ow": out_weights[j]  if j < len(out_weights)  else 1.0,
            })
        return keys

    def apply_key_data(self, node, attr, key_list):
        is_new_format = key_list and isinstance(key_list[0], dict)
        if is_new_format:
            for k in key_list:
                cmds.setKeyframe(node, at=attr, time=k["t"], v=k["v"])
            for k in key_list:
                cmds.keyTangent(node, at=attr, time=(k["t"], k["t"]),
                                inTangentType=k["it"], outTangentType=k["ot"])
            for k in key_list:
                if k["it"] == "fixed" or k["ot"] == "fixed":
                    cmds.keyTangent(node, at=attr, time=(k["t"], k["t"]),
                                    lock=False,
                                    inAngle=k["ia"],  outAngle=k["oa"],
                                    inWeight=k["iw"], outWeight=k["ow"])
        else:
            for item in key_list:
                cmds.setKeyframe(node, at=attr, time=item[0], v=item[1])

    def paste_node(self, target_node, node_data):
        anim_items = {k: v for k, v in node_data.items() if k != "__name__"}
        skipped = 0
        for attr, key_list in anim_items.items():
            if not cmds.attributeQuery(attr, node=target_node, exists=True):
                skipped += 1
                continue
            if cmds.getAttr(f"{target_node}.{attr}", lock=True):
                skipped += 1
                continue
            try:
                self.apply_key_data(target_node, attr, key_list)
            except Exception as e:
                print(f"Skip: {target_node}.{attr} ({e})")
                skipped += 1
        return skipped

    # ── 保存 ─────────────────────────────────────────────
    def save_anim(self, *args):
        file_path = self.get_file_path()
        use_scene = cmds.checkBox(self.scene_wide, q=True, v=True)

        if use_scene:
            nodes = self.get_scene_animated_nodes()
            if not nodes:
                cmds.warning("シーン内にアニメーションが見つかりません。")
                return
        else:
            sel = cmds.ls(sl=True, l=True)
            if not sel:
                cmds.warning("保存したいオブジェクトを選択してください。")
                return
            nodes = self.get_save_nodes(sel)

        all_data = []
        for node in nodes:
            node_anim = {"__name__": self.get_short_name(node)}
            for attr in (cmds.listAttr(node, k=True) or []):
                keys = self.collect_key_data(node, attr)
                if keys:
                    node_anim[attr] = keys
            all_data.append(node_anim)

        with open(file_path, 'w') as f:
            json.dump(all_data, f)

        # サムネイル
        if cmds.checkBox(self.save_thumb, q=True, v=True):
            self.save_thumbnail()

        cmds.confirmDialog(title="完了", message=f"{len(nodes)} ノードのアニメーションを保存しました。\n{file_path}")

    # ── 貼り付け ──────────────────────────────────────────
    def load_anim(self, *args):
        file_path = self.get_file_path()
        if not os.path.exists(file_path):
            cmds.error(f"データファイルが見つかりません:\n{file_path}")
            return

        sel = cmds.ls(sl=True, l=True)
        if not sel:
            cmds.warning("貼り付け先のオブジェクトを選択してください。")
            return

        with open(file_path, 'r') as f:
            all_data = json.load(f)

        target_nodes = self.get_load_nodes(sel)
        selected     = cmds.radioCollection(self.match_mode_col, q=True, select=True)

        # ── 厳密一致チェック ──────────────────────────────
        if selected == self.match_strict:
            if len(all_data) != len(target_nodes):
                cmds.confirmDialog(
                    title="移植中止",
                    message=(
                        f"ノード数が一致しません。\n"
                        f"保存: {len(all_data)}  /  貼り付け先: {len(target_nodes)}"
                    )
                )
                return
            for i, (nd, tn) in enumerate(zip(all_data, target_nodes)):
                src = nd.get("__name__", "")
                dst = self.get_short_name(tn)
                if src != dst:
                    cmds.confirmDialog(
                        title="移植中止",
                        message=(
                            f"ノード名が一致しません（index {i}）。\n"
                            f"保存側: {src}  /  貼り付け先: {dst}"
                        )
                    )
                    return
            selected = self.match_order  # チェック通過→順番モードで続行

        # 既存キー削除
        for t_node in target_nodes:
            try:
                cmds.cutKey(t_node, clear=True)
            except:
                pass

        skipped_nodes = 0
        skipped_attrs = 0

        # ── 名前ベース（デフォルト）──────────────────────
        if selected == self.match_name:
            target_map = {}
            for tn in target_nodes:
                sn = self.get_short_name(tn)
                target_map.setdefault(sn, []).append(tn)
            for node_data in all_data:
                src_name = node_data.get("__name__", "")
                matched  = target_map.get(src_name, [])
                if not matched:
                    skipped_nodes += 1
                    continue
                for tn in matched:
                    skipped_attrs += self.paste_node(tn, node_data)

        # ── 階層ベース・L/R考慮 ──────────────────────────
        elif selected == self.match_hier_lr:
            for i, node_data in enumerate(all_data):
                if i >= len(target_nodes):
                    break
                target_node = target_nodes[i]
                src_name = node_data.get("__name__", "")
                dst_name = self.get_short_name(target_node)
                src_side = self.get_lr_side(src_name)
                dst_side = self.get_lr_side(dst_name)
                if src_side != 'none' and dst_side != 'none' and src_side != dst_side:
                    print(f"L/R mismatch skip: {src_name} -> {dst_name}")
                    skipped_nodes += 1
                    continue
                skipped_attrs += self.paste_node(target_node, node_data)

        # ── 順番ベース ────────────────────────────────────
        else:
            for i, node_data in enumerate(all_data):
                if i >= len(target_nodes):
                    break
                skipped_attrs += self.paste_node(target_nodes[i], node_data)

        msg = "アニメーションの移植が完了しました。"
        if skipped_nodes:
            msg += f"\n（スキップしたノード: {skipped_nodes}）"
        if skipped_attrs:
            msg += f"\n（スキップしたアトリビュート: {skipped_attrs}）"
        cmds.confirmDialog(title="完了", message=msg)

# 実行
AnimTransferFinalV5()