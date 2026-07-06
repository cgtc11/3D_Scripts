# SP Toon Controls v1.0 for Maya 2026 / MtoA
# Default UI language: English
# Run this file in Maya Script Editor's Python tab.
#
# Features:
# - English / Japanese UI switching
# - Light Position controls
# - Toon Param 2-7 and Toon Blur
# - Outline / Inline Thickness and Blur
# - Color controls
# - Texture loading and removal
# - Curvature texture loading and removal

import os
import maya.cmds as cmds
from functools import partial


WINDOW_NAME = "SPToonMaya2026V1_0Window"


TEXT = {
    "en": {
        "window_title": "SP Toon Controls v1.0",
        "language": "Language",
        "english": "English",
        "japanese": "Japanese",
        "select_osl_help": "Select the purple aiOslShader node.",
        "load_selected": "Load Selected OSL",
        "refresh": "Refresh Values",
        "target_none": "Target node: Not selected",
        "target": "Target node: {node}",
        "all_found": "All parameters were found.",
        "missing": "Missing: {items}",
        "line_enable": "LINE ENABLE",
        "use_outline": "Use Outline",
        "light_position": "LIGHT POSITION",
        "outline_inline": "OUTLINE / INLINE",
        "toon_gradation": "TOON GRADATION",
        "color_texture": "COLOR / TEXTURE SETTINGS",
        "curvature_texture": "CURVATURE TEXTURE",
        "light_x": "Light Position X",
        "light_y": "Light Position Y",
        "light_z": "Light Position Z",
        "outline_thickness": "Outline Thickness",
        "outline_blur": "Outline Blur",
        "inline_thickness": "Inline Thickness",
        "inline_blur": "Inline Blur",
        "inline_on_top": "Inline on Top",
        "toon_param_2": "Toon Param 2",
        "toon_param_3": "Toon Param 3",
        "toon_param_4": "Toon Param 4",
        "toon_param_5": "Toon Param 5",
        "toon_param_6": "Toon Param 6",
        "toon_param_7": "Toon Param 7",
        "toon_blur": "Toon Blur",
        "base_color": "Base Color",
        "outline_color": "Outline Color",
        "inline_color": "Inline Color",
        "toon_color_2": "Toon Color 2",
        "toon_color_3": "Toon Color 3",
        "toon_color_4": "Toon Color 4",
        "toon_color_5": "Toon Color 5",
        "toon_color_6": "Toon Color 6",
        "toon_color_7": "Toon Color 7",
        "texture_none": "Texture: None",
        "texture_name": "Texture: {name}",
        "load": "Load",
        "remove": "Remove",
        "blur_help": (
            "Set Blur to 0 for hard boundaries. Increase the value to soften "
            "Outline, Inline, and Toon transitions."
        ),
        "select_warning": "Select the purple aiOslShader node.",
        "load_osl_first": "Load an aiOslShader node first.",
        "connected_warning": (
            "{plug} is connected from {source}. The value cannot be edited "
            "while the connection exists."
        ),
        "color_connected_warning": (
            "{plug} is connected from {source}. Remove the texture before "
            "editing the color."
        ),
        "parameter_not_found": "OSL input was not found: {parameter}",
        "image_filename_missing": "The aiImage filename attribute was not found.",
        "image_color_output_missing": "The aiImage color output was not found.",
        "image_scalar_output_missing": "The aiImage scalar output was not found.",
        "choose_texture": "Choose texture for {parameter}",
    },
    "ja": {
        "window_title": "SP Toon コントロール v1.0",
        "language": "表示言語",
        "english": "英語",
        "japanese": "日本語",
        "select_osl_help": "紫色の aiOslShader ノードを選択してください。",
        "load_selected": "選択したOSLを読み込む",
        "refresh": "現在値を再読み込み",
        "target_none": "対象ノード：未選択",
        "target": "対象ノード：{node}",
        "all_found": "すべての入力を検出しました。",
        "missing": "未検出：{items}",
        "line_enable": "ライン表示",
        "use_outline": "アウトラインを使用",
        "light_position": "ライト位置",
        "outline_inline": "アウトライン／インライン",
        "toon_gradation": "トゥーングラデーション",
        "color_texture": "色／テクスチャ設定",
        "curvature_texture": "カーブチャーテクスチャ",
        "light_x": "ライト位置 X",
        "light_y": "ライト位置 Y",
        "light_z": "ライト位置 Z",
        "outline_thickness": "アウトラインの太さ",
        "outline_blur": "アウトラインのぼかし",
        "inline_thickness": "インラインの太さ",
        "inline_blur": "インラインのぼかし",
        "inline_on_top": "インライン最前面表示",
        "toon_param_2": "トゥーンパラメーター 2",
        "toon_param_3": "トゥーンパラメーター 3",
        "toon_param_4": "トゥーンパラメーター 4",
        "toon_param_5": "トゥーンパラメーター 5",
        "toon_param_6": "トゥーンパラメーター 6",
        "toon_param_7": "トゥーンパラメーター 7",
        "toon_blur": "トゥーンのぼかし",
        "base_color": "ベースカラー",
        "outline_color": "アウトラインカラー",
        "inline_color": "インラインカラー",
        "toon_color_2": "トゥーンカラー 2",
        "toon_color_3": "トゥーンカラー 3",
        "toon_color_4": "トゥーンカラー 4",
        "toon_color_5": "トゥーンカラー 5",
        "toon_color_6": "トゥーンカラー 6",
        "toon_color_7": "トゥーンカラー 7",
        "texture_none": "テクスチャ：なし",
        "texture_name": "テクスチャ：{name}",
        "load": "読込",
        "remove": "解除",
        "blur_help": (
            "ぼかしを0にすると硬い境界になります。値を上げると、"
            "アウトライン、インライン、トゥーン段階の境界が滑らかになります。"
        ),
        "select_warning": "紫色の aiOslShader ノードを選択してください。",
        "load_osl_first": "先に aiOslShader ノードを読み込んでください。",
        "connected_warning": (
            "{plug} には {source} が接続されています。"
            "接続中は数値を変更できません。"
        ),
        "color_connected_warning": (
            "{plug} には {source} が接続されています。"
            "テクスチャを解除してから色を変更してください。"
        ),
        "parameter_not_found": "OSL入力が見つかりません：{parameter}",
        "image_filename_missing": "aiImageのファイル名属性が見つかりません。",
        "image_color_output_missing": "aiImageのカラー出力が見つかりません。",
        "image_scalar_output_missing": "aiImageの単チャンネル出力が見つかりません。",
        "choose_texture": "{parameter} のテクスチャを選択",
    },
}


class SPToonControlsV1_0:
    def __init__(self):
        self.language = "en"
        self.node = None
        self.controls = {}
        self.color_controls = {}
        self.texture_labels = {}
        self.ui = {}
        self.status = None

        self.slider_sections = [
            (
                "light_position",
                [
                    ("light_x", "LightPositionX", -20.0, 20.0, 10.0),
                    ("light_y", "LightPositionY", -20.0, 20.0, 10.0),
                    ("light_z", "LightPositionZ", -20.0, 20.0, 10.0),
                ],
            ),
            (
                "outline_inline",
                [
                    ("outline_thickness", "OutlineThickness", 0.0, 1.0, 0.2),
                    ("outline_blur", "OutlineBlur", 0.0, 5.0, 0.0),
                    ("inline_thickness", "InlineThickness", 0.0, 1.0, 0.3),
                    ("inline_blur", "InlineBlur", 0.0, 5.0, 0.0),
                    ("inline_on_top", "InlineOnTop", 0.0, 1.0, 1.0),
                ],
            ),
            (
                "toon_gradation",
                [
                    ("toon_param_2", "ToonParam2", -1.0, 1.0, 0.0),
                    ("toon_param_3", "ToonParam3", -1.0, 1.0, -1.0),
                    ("toon_param_4", "ToonParam4", -1.0, 1.0, -1.0),
                    ("toon_param_5", "ToonParam5", -1.0, 1.0, -1.0),
                    ("toon_param_6", "ToonParam6", -1.0, 1.0, -1.0),
                    ("toon_param_7", "ToonParam7", -1.0, 1.0, -1.0),
                    ("toon_blur", "ToonBlur", 0.0, 5.0, 0.0),
                ],
            ),
        ]

        self.color_items = [
            ("base_color", "BaseColor", (1.0, 1.0, 1.0), "sRGB"),
            ("outline_color", "OutlineColor", (0.0, 0.297, 1.0), "sRGB"),
            ("inline_color", "InlineColor", (0.366, 0.027, 0.0), "sRGB"),
            ("toon_color_2", "ToonColor2", (0.554, 0.554, 0.554), "sRGB"),
            ("toon_color_3", "ToonColor3", (0.232, 0.232, 0.232), "sRGB"),
            ("toon_color_4", "ToonColor4", (0.095, 0.095, 0.095), "sRGB"),
            ("toon_color_5", "ToonColor5", (0.070, 0.070, 0.070), "sRGB"),
            ("toon_color_6", "ToonColor6", (0.025, 0.025, 0.025), "sRGB"),
            ("toon_color_7", "ToonColor7", (0.016, 0.016, 0.016), "sRGB"),
        ]

    def tr(self, key, **kwargs):
        value = TEXT[self.language][key]
        return value.format(**kwargs) if kwargs else value

    @staticmethod
    def normalize_name(name):
        return "".join(c.lower() for c in name if c.isalnum())

    def find_attr(self, parameter):
        if not self.node or not cmds.objExists(self.node):
            return None

        candidates = [parameter, "param_" + parameter, "param" + parameter]

        for candidate in candidates:
            if cmds.attributeQuery(candidate, node=self.node, exists=True):
                return candidate

        target = self.normalize_name(parameter)

        for attr in cmds.listAttr(self.node) or []:
            normalized = self.normalize_name(attr)
            if normalized == target or normalized == "param" + target:
                return attr

        return None

    def selected_osl(self):
        for node in cmds.ls(selection=True) or []:
            if cmds.nodeType(node) == "aiOslShader":
                return node
        return None

    def change_language(self, value, *_):
        """
        Maya optionMenuGrp may return either the selected label string
        or an index depending on version/context.
        """
        selected = value

        try:
            selected_index = cmds.optionMenuGrp(
                self.ui["language_menu"],
                query=True,
                select=True,
            )
        except RuntimeError:
            selected_index = None

        selected_text = str(selected).strip().lower()

        if (
            selected_index == 2
            or selected_text in ("japanese", "日本語", "2")
        ):
            self.language = "ja"
        else:
            self.language = "en"

        self.apply_language()
        self.refresh()

    def apply_language(self):
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.window(
                WINDOW_NAME,
                edit=True,
                title=self.tr("window_title"),
            )

        cmds.optionMenuGrp(
            self.ui["language_menu"],
            edit=True,
            label=self.tr("language"),
        )

        cmds.menuItem(
            self.ui["language_en"],
            edit=True,
            label=self.tr("english"),
        )
        cmds.menuItem(
            self.ui["language_ja"],
            edit=True,
            label=self.tr("japanese"),
        )

        cmds.text(
            self.ui["select_help"],
            edit=True,
            label=self.tr("select_osl_help"),
        )
        cmds.button(
            self.ui["load_button"],
            edit=True,
            label=self.tr("load_selected"),
        )
        cmds.button(
            self.ui["refresh_button"],
            edit=True,
            label=self.tr("refresh"),
        )
        cmds.text(
            self.ui["line_enable_heading"],
            edit=True,
            label=self.tr("line_enable"),
        )
        cmds.checkBox(
            self.controls["UseOutline"],
            edit=True,
            label=self.tr("use_outline"),
        )

        for section_key, heading_control in self.ui["section_headings"].items():
            cmds.text(
                heading_control,
                edit=True,
                label=self.tr(section_key),
            )

        for parameter, data in self.controls.items():
            if parameter == "UseOutline":
                continue
            cmds.floatSliderGrp(
                data["control"],
                edit=True,
                label=self.tr(data["label_key"]),
            )

        for parameter, data in self.color_controls.items():
            cmds.colorSliderGrp(
                data["control"],
                edit=True,
                label=self.tr(data["label_key"]),
            )
            cmds.button(
                data["load_button"],
                edit=True,
                label=self.tr("load"),
            )
            cmds.button(
                data["remove_button"],
                edit=True,
                label=self.tr("remove"),
            )

        cmds.text(
            self.ui["curvature_heading"],
            edit=True,
            label=self.tr("curvature_texture"),
        )
        cmds.button(
            self.ui["curvature_load"],
            edit=True,
            label=self.tr("load"),
        )
        cmds.button(
            self.ui["curvature_remove"],
            edit=True,
            label=self.tr("remove"),
        )
        cmds.text(
            self.ui["blur_help"],
            edit=True,
            label=self.tr("blur_help"),
        )

        # Preserve the selected language after menu item labels change.
        cmds.optionMenuGrp(
            self.ui["language_menu"],
            edit=True,
            select=2 if self.language == "ja" else 1,
        )

        for parameter in self.texture_labels:
            self.update_texture_label(parameter)

    def load_selected(self, *_):
        node = self.selected_osl()

        if not node:
            cmds.warning(self.tr("select_warning"))
            return

        self.node = node
        self.refresh()

    def get_incoming(self, parameter):
        attr = self.find_attr(parameter)
        if not attr:
            return None

        plugs = cmds.listConnections(
            self.node + "." + attr,
            source=True,
            destination=False,
            plugs=True,
        ) or []

        return plugs[0] if plugs else None

    def set_float(self, parameter, control, *_):
        attr = self.find_attr(parameter)
        if not attr:
            return

        plug = self.node + "." + attr
        incoming = self.get_incoming(parameter)

        if incoming:
            cmds.warning(
                self.tr(
                    "connected_warning",
                    plug=plug,
                    source=incoming,
                )
            )
            self.refresh()
            return

        value = cmds.floatSliderGrp(control, query=True, value=True)

        try:
            cmds.setAttr(plug, value)
        except RuntimeError as error:
            cmds.warning(str(error))

    def set_outline(self, control, *_):
        attr = self.find_attr("UseOutline")
        if not attr:
            return

        value = 1 if cmds.checkBox(control, query=True, value=True) else 0
        cmds.setAttr(self.node + "." + attr, value)

    def set_color(self, parameter, control, *_):
        attr = self.find_attr(parameter)
        if not attr:
            return

        plug = self.node + "." + attr
        incoming = self.get_incoming(parameter)

        if incoming:
            cmds.warning(
                self.tr(
                    "color_connected_warning",
                    plug=plug,
                    source=incoming,
                )
            )
            self.refresh()
            return

        rgb = cmds.colorSliderGrp(control, query=True, rgbValue=True)

        try:
            cmds.setAttr(plug, rgb[0], rgb[1], rgb[2], type="double3")
        except RuntimeError:
            try:
                cmds.setAttr(plug, rgb[0], rgb[1], rgb[2], type="float3")
            except RuntimeError as error:
                cmds.warning(str(error))

    def create_ai_image(self, parameter, file_path, color_space):
        attr = self.find_attr(parameter)

        if not attr:
            raise RuntimeError(
                self.tr("parameter_not_found", parameter=parameter)
            )

        destination = self.node + "." + attr
        old_source = self.get_incoming(parameter)

        if old_source:
            try:
                cmds.disconnectAttr(old_source, destination)
            except RuntimeError:
                pass

        image_node = cmds.shadingNode(
            "aiImage",
            asTexture=True,
            name="{}_{}_IMG".format(self.node, parameter),
        )

        filename_attr = None
        for candidate in ("filename", "fileName"):
            if cmds.attributeQuery(candidate, node=image_node, exists=True):
                filename_attr = candidate
                break

        if not filename_attr:
            raise RuntimeError(self.tr("image_filename_missing"))

        cmds.setAttr(
            image_node + "." + filename_attr,
            file_path,
            type="string",
        )

        if cmds.attributeQuery("colorSpace", node=image_node, exists=True):
            try:
                cmds.setAttr(
                    image_node + ".colorSpace",
                    color_space,
                    type="string",
                )
            except RuntimeError:
                pass

        source_attr = None
        for candidate in ("outColor", "outValue"):
            if cmds.attributeQuery(candidate, node=image_node, exists=True):
                source_attr = candidate
                break

        if not source_attr:
            raise RuntimeError(self.tr("image_color_output_missing"))

        cmds.connectAttr(
            image_node + "." + source_attr,
            destination,
            force=True,
        )

        return image_node

    def choose_color_texture(self, parameter, color_space, *_):
        if not self.node:
            cmds.warning(self.tr("load_osl_first"))
            return

        result = cmds.fileDialog2(
            fileMode=1,
            caption=self.tr("choose_texture", parameter=parameter),
            fileFilter=(
                "Textures (*.png *.tif *.tiff *.jpg *.jpeg *.exr *.tx *.tga *.bmp);;"
                "All Files (*.*)"
            ),
        )

        if not result:
            return

        try:
            image_node = self.create_ai_image(
                parameter,
                result[0],
                color_space,
            )
            self.refresh()
            cmds.select(image_node, replace=True)
        except RuntimeError as error:
            cmds.warning(str(error))

    def choose_float_texture(self, parameter, *_):
        if not self.node:
            cmds.warning(self.tr("load_osl_first"))
            return

        result = cmds.fileDialog2(
            fileMode=1,
            caption=self.tr("choose_texture", parameter=parameter),
            fileFilter=(
                "Textures (*.png *.tif *.tiff *.jpg *.jpeg *.exr *.tx *.tga *.bmp);;"
                "All Files (*.*)"
            ),
        )

        if not result:
            return

        attr = self.find_attr(parameter)

        if not attr:
            cmds.warning(
                self.tr("parameter_not_found", parameter=parameter)
            )
            return

        destination = self.node + "." + attr
        old_source = self.get_incoming(parameter)

        if old_source:
            try:
                cmds.disconnectAttr(old_source, destination)
            except RuntimeError:
                pass

        image_node = cmds.shadingNode(
            "aiImage",
            asTexture=True,
            name="{}_{}_IMG".format(self.node, parameter),
        )

        filename_attr = None
        for candidate in ("filename", "fileName"):
            if cmds.attributeQuery(candidate, node=image_node, exists=True):
                filename_attr = candidate
                break

        if not filename_attr:
            cmds.warning(self.tr("image_filename_missing"))
            return

        cmds.setAttr(
            image_node + "." + filename_attr,
            result[0],
            type="string",
        )

        if cmds.attributeQuery("colorSpace", node=image_node, exists=True):
            try:
                cmds.setAttr(
                    image_node + ".colorSpace",
                    "Raw",
                    type="string",
                )
            except RuntimeError:
                pass

        source_attr = None
        for candidate in ("outColorR", "outValueR", "outAlpha"):
            if cmds.attributeQuery(candidate, node=image_node, exists=True):
                source_attr = candidate
                break

        if not source_attr:
            cmds.warning(self.tr("image_scalar_output_missing"))
            return

        cmds.connectAttr(
            image_node + "." + source_attr,
            destination,
            force=True,
        )

        self.refresh()
        cmds.select(image_node, replace=True)

    def clear_texture(self, parameter, *_):
        if not self.node:
            return

        attr = self.find_attr(parameter)
        if not attr:
            return

        destination = self.node + "." + attr
        source = self.get_incoming(parameter)

        if not source:
            return

        source_node = source.split(".", 1)[0]

        try:
            cmds.disconnectAttr(source, destination)
        except RuntimeError:
            pass

        if cmds.objExists(source_node) and cmds.nodeType(source_node) == "aiImage":
            try:
                cmds.delete(source_node)
            except RuntimeError:
                pass

        self.refresh()

    def update_texture_label(self, parameter):
        label_control = self.texture_labels.get(parameter)
        if not label_control:
            return

        source = self.get_incoming(parameter)

        if not source:
            text = self.tr("texture_none")
        else:
            source_node = source.split(".", 1)[0]
            path = ""

            for attr in ("filename", "fileName"):
                if cmds.attributeQuery(attr, node=source_node, exists=True):
                    try:
                        path = cmds.getAttr(source_node + "." + attr) or ""
                    except RuntimeError:
                        path = ""

                    if path:
                        break

            display_name = os.path.basename(path) if path else source_node
            text = self.tr("texture_name", name=display_name)

        cmds.text(label_control, edit=True, label=text)

    def refresh(self, *_):
        if not self.node or not cmds.objExists(self.node):
            cmds.text(
                self.status,
                edit=True,
                label=self.tr("target_none"),
            )
            return

        missing = []

        outline_attr = self.find_attr("UseOutline")

        if outline_attr:
            cmds.checkBox(
                self.controls["UseOutline"],
                edit=True,
                enable=True,
                value=bool(cmds.getAttr(self.node + "." + outline_attr)),
            )
        else:
            cmds.checkBox(
                self.controls["UseOutline"],
                edit=True,
                enable=False,
            )
            missing.append("UseOutline")

        for parameter, data in self.controls.items():
            if parameter == "UseOutline":
                continue

            control = data["control"]
            attr = self.find_attr(parameter)

            if not attr:
                cmds.floatSliderGrp(control, edit=True, enable=False)
                missing.append(parameter)
                continue

            incoming = self.get_incoming(parameter)

            try:
                value = float(cmds.getAttr(self.node + "." + attr))
                cmds.floatSliderGrp(
                    control,
                    edit=True,
                    enable=not bool(incoming),
                    value=value,
                )
            except (RuntimeError, TypeError, ValueError):
                cmds.floatSliderGrp(control, edit=True, enable=False)
                missing.append(parameter)

        for parameter, data in self.color_controls.items():
            control = data["control"]
            attr = self.find_attr(parameter)

            if not attr:
                cmds.colorSliderGrp(control, edit=True, enable=False)
                missing.append(parameter)
                self.update_texture_label(parameter)
                continue

            incoming = self.get_incoming(parameter)

            try:
                value = cmds.getAttr(self.node + "." + attr)

                if isinstance(value, (tuple, list)) and value:
                    value = value[0]

                rgb = (
                    float(value[0]),
                    float(value[1]),
                    float(value[2]),
                )

                cmds.colorSliderGrp(
                    control,
                    edit=True,
                    enable=not bool(incoming),
                    rgbValue=rgb,
                )
            except (RuntimeError, TypeError, ValueError, IndexError):
                cmds.colorSliderGrp(control, edit=True, enable=False)
                missing.append(parameter)

            self.update_texture_label(parameter)

        self.update_texture_label("Curvature")

        message = self.tr("target", node=self.node)

        if missing:
            message += "\n" + self.tr(
                "missing",
                items=", ".join(sorted(set(missing))),
            )
        else:
            message += "\n" + self.tr("all_found")

        cmds.text(self.status, edit=True, label=message)

    def build_color_row(self, label_key, parameter, default, color_space):
        control = cmds.colorSliderGrp(
            label=self.tr(label_key),
            rgbValue=default,
            columnWidth4=(150, 60, 170, 40),
            adjustableColumn=3,
            enable=False,
        )

        cmds.colorSliderGrp(
            control,
            edit=True,
            changeCommand=partial(
                self.set_color,
                parameter,
                control,
            ),
        )

        cmds.rowLayout(
            numberOfColumns=3,
            adjustableColumn=1,
            columnWidth3=(335, 90, 90),
        )

        texture_text = cmds.text(
            label=self.tr("texture_none"),
            align="left",
        )

        load_button = cmds.button(
            label=self.tr("load"),
            command=partial(
                self.choose_color_texture,
                parameter,
                color_space,
            ),
        )

        remove_button = cmds.button(
            label=self.tr("remove"),
            command=partial(
                self.clear_texture,
                parameter,
            ),
        )

        cmds.setParent("..")

        self.color_controls[parameter] = {
            "control": control,
            "label_key": label_key,
            "load_button": load_button,
            "remove_button": remove_button,
        }
        self.texture_labels[parameter] = texture_text

    def build(self):
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        window = cmds.window(
            WINDOW_NAME,
            title=self.tr("window_title"),
            sizeable=True,
            widthHeight=(580, 900),
        )

        cmds.scrollLayout(
            horizontalScrollBarThickness=0,
            verticalScrollBarThickness=16,
        )

        cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=6,
        )

        cmds.separator(height=6, style="none")

        language_menu = cmds.optionMenuGrp(
            label=self.tr("language"),
            changeCommand=self.change_language,
            columnWidth2=(120, 180),
        )
        language_en = cmds.menuItem(label=self.tr("english"))
        language_ja = cmds.menuItem(label=self.tr("japanese"))

        self.ui["language_menu"] = language_menu
        self.ui["language_en"] = language_en
        self.ui["language_ja"] = language_ja

        select_help = cmds.text(
            label=self.tr("select_osl_help"),
            align="left",
        )
        load_button = cmds.button(
            label=self.tr("load_selected"),
            height=34,
            command=self.load_selected,
        )
        refresh_button = cmds.button(
            label=self.tr("refresh"),
            height=28,
            command=self.refresh,
        )

        self.ui["select_help"] = select_help
        self.ui["load_button"] = load_button
        self.ui["refresh_button"] = refresh_button

        self.status = cmds.text(
            label=self.tr("target_none"),
            align="left",
            height=42,
        )

        cmds.separator(height=12, style="in")

        line_enable_heading = cmds.text(
            label=self.tr("line_enable"),
            align="left",
            font="boldLabelFont",
        )
        self.ui["line_enable_heading"] = line_enable_heading

        outline_checkbox = cmds.checkBox(
            label=self.tr("use_outline"),
            value=True,
            enable=False,
        )

        cmds.checkBox(
            outline_checkbox,
            edit=True,
            changeCommand=partial(
                self.set_outline,
                outline_checkbox,
            ),
        )

        self.controls["UseOutline"] = outline_checkbox
        self.ui["section_headings"] = {}

        for section_key, items in self.slider_sections:
            cmds.separator(height=14, style="in")

            heading = cmds.text(
                label=self.tr(section_key),
                align="left",
                font="boldLabelFont",
                height=22,
            )
            self.ui["section_headings"][section_key] = heading

            for label_key, parameter, minimum, maximum, default in items:
                control = cmds.floatSliderGrp(
                    label=self.tr(label_key),
                    field=True,
                    minValue=minimum,
                    maxValue=maximum,
                    fieldMinValue=minimum,
                    fieldMaxValue=maximum,
                    value=default,
                    precision=3,
                    sliderStep=0.005,
                    fieldStep=0.005,
                    adjustableColumn=3,
                    columnWidth3=(185, 75, 280),
                    enable=False,
                )

                callback = partial(
                    self.set_float,
                    parameter,
                    control,
                )

                cmds.floatSliderGrp(
                    control,
                    edit=True,
                    dragCommand=callback,
                    changeCommand=callback,
                )

                self.controls[parameter] = {
                    "control": control,
                    "label_key": label_key,
                }

        cmds.separator(height=14, style="in")

        color_heading = cmds.text(
            label=self.tr("color_texture"),
            align="left",
            font="boldLabelFont",
            height=22,
        )
        self.ui["section_headings"]["color_texture"] = color_heading

        for label_key, parameter, default, color_space in self.color_items:
            self.build_color_row(
                label_key,
                parameter,
                default,
                color_space,
            )
            cmds.separator(height=5, style="none")

        cmds.separator(height=14, style="in")

        curvature_heading = cmds.text(
            label=self.tr("curvature_texture"),
            align="left",
            font="boldLabelFont",
            height=22,
        )
        self.ui["curvature_heading"] = curvature_heading

        cmds.rowLayout(
            numberOfColumns=3,
            adjustableColumn=1,
            columnWidth3=(335, 90, 90),
        )

        curvature_text = cmds.text(
            label=self.tr("texture_none"),
            align="left",
        )

        curvature_load = cmds.button(
            label=self.tr("load"),
            command=partial(
                self.choose_float_texture,
                "Curvature",
            ),
        )

        curvature_remove = cmds.button(
            label=self.tr("remove"),
            command=partial(
                self.clear_texture,
                "Curvature",
            ),
        )

        cmds.setParent("..")

        self.texture_labels["Curvature"] = curvature_text
        self.ui["curvature_load"] = curvature_load
        self.ui["curvature_remove"] = curvature_remove

        cmds.separator(height=14, style="in")

        blur_help = cmds.text(
            label=self.tr("blur_help"),
            align="left",
            wordWrap=True,
            height=48,
        )
        self.ui["blur_help"] = blur_help

        cmds.showWindow(window)

        # English is the default.
        cmds.optionMenuGrp(
            language_menu,
            edit=True,
            select=1,
        )

        if self.selected_osl():
            self.load_selected()


global SP_TOON_CONTROLS_V1_0
SP_TOON_CONTROLS_V1_0 = SPToonControlsV1_0()
SP_TOON_CONTROLS_V1_0.build()
