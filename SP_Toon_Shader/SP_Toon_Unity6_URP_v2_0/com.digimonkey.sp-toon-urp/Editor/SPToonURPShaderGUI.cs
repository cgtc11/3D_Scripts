using UnityEditor;
using UnityEngine;

namespace DiGiMonkey
{
    public sealed class SPToonURPShaderGUI : ShaderGUI
    {
        private static MaterialProperty Find(
            string propertyName,
            MaterialProperty[] properties)
        {
            return FindProperty(propertyName, properties, false);
        }

        private static void DrawProperty(
            MaterialEditor editor,
            MaterialProperty property,
            string label = null)
        {
            if (property == null) return;
            editor.ShaderProperty(
                property,
                string.IsNullOrEmpty(label)
                    ? property.displayName
                    : label);
        }

        private static void DrawTextureColor(
            MaterialEditor editor,
            MaterialProperty texture,
            MaterialProperty color,
            string label)
        {
            if (texture == null || color == null) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField(label, EditorStyles.miniBoldLabel);
            EditorGUI.indentLevel++;
            editor.ColorProperty(color, "Color");
            editor.TexturePropertySingleLine(new GUIContent("Texture"), texture);
            EditorGUI.indentLevel--;
            EditorGUILayout.EndVertical();
        }

        private static void DrawTextureOnly(
            MaterialEditor editor,
            MaterialProperty texture,
            string label)
        {
            if (texture == null) return;
            editor.TexturePropertySingleLine(new GUIContent(label), texture);
        }

        public override void OnGUI(
            MaterialEditor materialEditor,
            MaterialProperty[] properties)
        {
            // ── Lighting ──
            MaterialProperty useHDR          = Find("_UseHDR",          properties);
            MaterialProperty hdrStrength     = Find("_HDRStrength",     properties);
            MaterialProperty lightPosition   = Find("_LightPosition",   properties);

            // ── Hull Outline ──
            MaterialProperty useHullOutline      = Find("_UseHullOutline",   properties);
            MaterialProperty hullOutlineWidth    = Find("_HullOutlineWidth", properties);
            MaterialProperty hullOutlineColor    = Find("_HullOutlineColor", properties);
            MaterialProperty hullOutlineMap      = Find("_HullOutlineMap",   properties);
            MaterialProperty hullNoiseStrength = Find("_HullNoiseStrength", properties);
            MaterialProperty hullNoiseScale    = Find("_HullNoiseScale",    properties);

            // ── Outline ──
            MaterialProperty useOutline      = Find("_UseOutline",      properties);
            MaterialProperty reverseOutline  = Find("_ReverseOutline",  properties);
            MaterialProperty outlineThickness= Find("_OutlineThickness",properties);
            MaterialProperty outlineBlur     = Find("_OutlineBlur",     properties);
            MaterialProperty outlineColor    = Find("_OutlineColor",    properties);
            MaterialProperty outlineMap      = Find("_OutlineMap",      properties);

            // ── Inline ──
            MaterialProperty inlineThickness = Find("_InlineThickness", properties);
            MaterialProperty inlineBlur      = Find("_InlineBlur",      properties);
            MaterialProperty inlineOnTop     = Find("_InlineOnTop",     properties);
            MaterialProperty inlineColor     = Find("_InlineColor",     properties);
            MaterialProperty inlineMap       = Find("_InlineMap",       properties);
            MaterialProperty curvatureMap    = Find("_CurvatureMap",    properties);
            MaterialProperty invertCurvature = Find("_InvertCurvature", properties);

            // ── Toon Gradation ──
            MaterialProperty toonParam2 = Find("_ToonParam2", properties);
            MaterialProperty toonParam3 = Find("_ToonParam3", properties);
            MaterialProperty toonParam4 = Find("_ToonParam4", properties);
            MaterialProperty toonParam5 = Find("_ToonParam5", properties);
            MaterialProperty toonParam6 = Find("_ToonParam6", properties);
            MaterialProperty toonParam7 = Find("_ToonParam7", properties);
            MaterialProperty toonBlur   = Find("_ToonBlur",   properties);

            // ── Normal Map ──
            MaterialProperty normalMap      = Find("_NormalMap",      properties);
            MaterialProperty normalStrength = Find("_NormalStrength",  properties);

            // ── AO ──
            MaterialProperty aoMap      = Find("_AOMap",      properties);
            MaterialProperty aoStrength = Find("_AOStrength", properties);
            MaterialProperty aoColor    = Find("_AOColor",    properties);

            // ── Rim ──
            MaterialProperty useRim      = Find("_UseRim",       properties);
            MaterialProperty rimStrength = Find("_RimStrength",  properties);
            MaterialProperty rimSharpness= Find("_RimSharpness", properties);
            MaterialProperty rimColor    = Find("_RimColor",     properties);

            // ── Thickness ──
            MaterialProperty useThickness      = Find("_UseThickness",      properties);
            MaterialProperty thicknessMap      = Find("_ThicknessMap",      properties);
            MaterialProperty thicknessStrength = Find("_ThicknessStrength", properties);
            MaterialProperty thicknessColor    = Find("_ThicknessColor",    properties);

            // ── MatCap ──
            MaterialProperty useMatCap      = Find("_UseMatCap",      properties);
            MaterialProperty matCapMap      = Find("_MatCapMap",       properties);
            MaterialProperty matCapStrength = Find("_MatCapStrength",  properties);
            MaterialProperty matCapBlend    = Find("_MatCapBlend",     properties);

            // ── Base Colors / Textures ──
            MaterialProperty baseColor  = Find("_BaseColor", properties);
            MaterialProperty baseMap    = Find("_BaseMap",   properties);

            MaterialProperty toonColor2 = Find("_ToonColor2", properties);
            MaterialProperty toonColor3 = Find("_ToonColor3", properties);
            MaterialProperty toonColor4 = Find("_ToonColor4", properties);
            MaterialProperty toonColor5 = Find("_ToonColor5", properties);
            MaterialProperty toonColor6 = Find("_ToonColor6", properties);
            MaterialProperty toonColor7 = Find("_ToonColor7", properties);

            MaterialProperty toonMap2 = Find("_ToonMap2", properties);
            MaterialProperty toonMap3 = Find("_ToonMap3", properties);
            MaterialProperty toonMap4 = Find("_ToonMap4", properties);
            MaterialProperty toonMap5 = Find("_ToonMap5", properties);
            MaterialProperty toonMap6 = Find("_ToonMap6", properties);
            MaterialProperty toonMap7 = Find("_ToonMap7", properties);

            // ── Surface ──
            MaterialProperty surfaceMode  = Find("_SurfaceMode", properties);
            MaterialProperty opacityMap    = Find("_OpacityMap",    properties);
            MaterialProperty invertOpacity = Find("_InvertOpacity", properties);
            MaterialProperty alphaClip     = Find("_AlphaClip",     properties);
            MaterialProperty opacityLevel = Find("_OpacityLevel", properties);

            EditorGUI.BeginChangeCheck();

            EditorGUILayout.LabelField("SP Toon URP", EditorStyles.boldLabel);

            // ────────────────────────────
            //  Lighting
            // ────────────────────────────
            EditorGUILayout.Space(4);
            EditorGUILayout.LabelField("Lighting", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useHDR, "HDR Enabled");
            bool hdrEnabled = useHDR != null && useHDR.floatValue > 0.5f;

            if (hdrEnabled)
            {
                DrawProperty(materialEditor, hdrStrength, "HDR Ambient Strength");
                EditorGUILayout.HelpBox(
                    "HDR Enabled uses each Unity light's direct N dot L, "
                    + "so the light/shadow boundary matches a normally lit "
                    + "sphere more closely. Point and Spot attenuation and "
                    + "shadows are included. HDR Ambient Strength adds only "
                    + "an optional Skybox/HDRI offset. HDR Disabled uses "
                    + "only the manual Light Position.",
                    MessageType.Info);
            }

            using (new EditorGUI.DisabledScope(hdrEnabled))
            {
                if (lightPosition != null)
                {
                    EditorGUILayout.Space(2);
                    EditorGUILayout.LabelField("Light Position", EditorStyles.miniBoldLabel);

                    Vector4 current = lightPosition.vectorValue;
                    Vector3 numericValue = new Vector3(current.x, current.y, current.z);

                    EditorGUI.BeginChangeCheck();
                    numericValue = EditorGUILayout.Vector3Field("Numeric", numericValue);

                    float sliderX = EditorGUILayout.Slider("X Slider", numericValue.x, -20f, 20f);
                    float sliderY = EditorGUILayout.Slider("Y Slider", numericValue.y, -20f, 20f);
                    float sliderZ = EditorGUILayout.Slider("Z Slider", numericValue.z, -20f, 20f);

                    if (EditorGUI.EndChangeCheck())
                    {
                        lightPosition.vectorValue = new Vector4(
                            sliderX, sliderY, sliderZ, current.w);
                    }
                }
            }

            // ────────────────────────────
            //  Hull Outline (Inverted Hull)
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Hull Outline (Inverted Hull)", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useHullOutline, "Use Hull Outline");
            bool hullEnabled = useHullOutline != null && useHullOutline.floatValue > 0.5f;

            using (new EditorGUI.DisabledScope(!hullEnabled))
            {
                DrawProperty(materialEditor, hullOutlineWidth, "Width");
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                EditorGUILayout.LabelField("Hull Outline Color / Texture", EditorStyles.miniBoldLabel);
                EditorGUI.indentLevel++;
                if (hullOutlineColor != null)
                    materialEditor.ColorProperty(hullOutlineColor, "Color");
                DrawTextureOnly(materialEditor, hullOutlineMap, "Texture");
                EditorGUI.indentLevel--;
                EditorGUILayout.EndVertical();
                DrawProperty(materialEditor, hullNoiseStrength, "Noise Strength");
                DrawProperty(materialEditor, hullNoiseScale,    "Noise Scale");
            }

            // ────────────────────────────
            //  Outline
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Outline", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useOutline);
            DrawProperty(materialEditor, reverseOutline);
            DrawProperty(materialEditor, outlineThickness);
            DrawProperty(materialEditor, outlineBlur);
            DrawTextureColor(materialEditor, outlineMap, outlineColor, "Outline Color / Texture");

            // ────────────────────────────
            //  Inline
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Inline", EditorStyles.boldLabel);

            DrawProperty(materialEditor, inlineThickness);
            DrawProperty(materialEditor, inlineBlur);
            DrawProperty(materialEditor, inlineOnTop, "Inline on Top");
            DrawTextureColor(materialEditor, inlineMap, inlineColor, "Inline Color / Texture");
            DrawTextureOnly(materialEditor, curvatureMap, "Inline Curvature Map");
            DrawProperty(materialEditor, invertCurvature);

            // ────────────────────────────
            //  Toon Gradation
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Toon Gradation", EditorStyles.boldLabel);

            DrawProperty(materialEditor, toonParam2);
            DrawProperty(materialEditor, toonParam3);
            DrawProperty(materialEditor, toonParam4);
            DrawProperty(materialEditor, toonParam5);
            DrawProperty(materialEditor, toonParam6);
            DrawProperty(materialEditor, toonParam7);
            DrawProperty(materialEditor, toonBlur);

            // ────────────────────────────
            //  Normal Map
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Normal Map", EditorStyles.boldLabel);

            DrawTextureOnly(materialEditor, normalMap, "Normal Map");
            DrawProperty(materialEditor, normalStrength, "Strength");

            // ────────────────────────────
            //  Ambient Occlusion
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Ambient Occlusion", EditorStyles.boldLabel);

            DrawTextureOnly(materialEditor, aoMap, "AO Map");
            DrawProperty(materialEditor, aoStrength, "Strength");
            if (aoColor != null)
                materialEditor.ColorProperty(aoColor, "AO Color (shadow tint)");

            // ────────────────────────────
            //  Rim Light
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Rim Light", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useRim, "Use Rim Light");
            bool rimEnabled = useRim != null && useRim.floatValue > 0.5f;
            using (new EditorGUI.DisabledScope(!rimEnabled))
            {
                DrawProperty(materialEditor, rimStrength,  "Strength");
                DrawProperty(materialEditor, rimSharpness, "Sharpness");
                if (rimColor != null)
                    materialEditor.ColorProperty(rimColor, "Rim Color");
            }

            // ────────────────────────────
            //  Thickness SSS
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Thickness (SSS)", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useThickness, "Use Thickness");
            bool thickEnabled = useThickness != null && useThickness.floatValue > 0.5f;
            using (new EditorGUI.DisabledScope(!thickEnabled))
            {
                DrawTextureOnly(materialEditor, thicknessMap, "Thickness Map");
                DrawProperty(materialEditor, thicknessStrength, "Strength");
                if (thicknessColor != null)
                    materialEditor.ColorProperty(thicknessColor, "Thickness Color");
            }

            // ────────────────────────────
            //  MatCap
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("MatCap (World Space Normals)", EditorStyles.boldLabel);

            DrawProperty(materialEditor, useMatCap, "Use MatCap");
            bool matCapEnabled = useMatCap != null && useMatCap.floatValue > 0.5f;
            using (new EditorGUI.DisabledScope(!matCapEnabled))
            {
                DrawTextureOnly(materialEditor, matCapMap, "MatCap Texture");
                DrawProperty(materialEditor, matCapStrength, "Strength");
                DrawProperty(materialEditor, matCapBlend,    "Blend Mode (Add / Multiply)");
            }

            // ────────────────────────────
            //  Colors / Textures
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Colors / Textures", EditorStyles.boldLabel);

            DrawTextureColor(materialEditor, baseMap,  baseColor,  "Base Color / Texture");
            DrawTextureColor(materialEditor, toonMap2, toonColor2, "Toon Color 2 / Texture");
            DrawTextureColor(materialEditor, toonMap3, toonColor3, "Toon Color 3 / Texture");
            DrawTextureColor(materialEditor, toonMap4, toonColor4, "Toon Color 4 / Texture");
            DrawTextureColor(materialEditor, toonMap5, toonColor5, "Toon Color 5 / Texture");
            DrawTextureColor(materialEditor, toonMap6, toonColor6, "Toon Color 6 / Texture");
            DrawTextureColor(materialEditor, toonMap7, toonColor7, "Toon Color 7 / Texture");

            if (baseMap != null)
            {
                EditorGUILayout.BeginVertical(EditorStyles.helpBox);
                EditorGUILayout.LabelField("Base Texture Mapping", EditorStyles.miniBoldLabel);
                materialEditor.TextureScaleOffsetProperty(baseMap);
                EditorGUILayout.EndVertical();
            }

            // ────────────────────────────
            //  Surface
            // ────────────────────────────
            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("Surface", EditorStyles.boldLabel);

            // ── Surface Mode dropdown ──
            int currentMode = surfaceMode != null ? (int)surfaceMode.floatValue : 0;
            string[] modeNames = new string[]
            {
                "Opaque",
                "Cutout",
                "Transparent",
                "Cutout Both Sides",
                "Transparent Both Sides"
            };
            EditorGUI.BeginChangeCheck();
            int selectedMode = EditorGUILayout.Popup("Surface Mode", currentMode, modeNames);
            if (EditorGUI.EndChangeCheck())
            {
                if (surfaceMode != null)
                    surfaceMode.floatValue = (float)selectedMode;
            }
            DrawTextureOnly(materialEditor, opacityMap, "Opacity Map");
            DrawProperty(materialEditor, invertOpacity, "Invert Opacity Map");
            bool isCutoutMode = (currentMode == 1 || currentMode == 3);
            using (new EditorGUI.DisabledScope(!isCutoutMode))
            {
                DrawProperty(materialEditor, alphaClip, "Alpha Clip (0/1)");
            }
            bool alphaClipEnabled = alphaClip != null && alphaClip.floatValue > 0.5f;
            using (new EditorGUI.DisabledScope(!alphaClipEnabled))
            {
                DrawProperty(materialEditor, opacityLevel, "Opacity Level");
            }


            if (EditorGUI.EndChangeCheck())
            {
                foreach (Object target in materialEditor.targets)
                {
                    if (target is not Material material) continue;
                    material.SetFloat("_UseHDR", hdrEnabled ? 1.0f : 0.0f);

                    int mode = (int)material.GetFloat("_SurfaceMode");
                    // Cull: 0=Off(両面) 2=Back(片面)
                    // ZWrite: 0=Off 1=On
                    // Blend: SrcBlend/DstBlend
                    //   One/Zero = 不透明
                    //   SrcAlpha/OneMinusSrcAlpha = 半透明
                    switch (mode)
                    {
                        case 0: // Opaque
                            material.SetFloat("_SurfaceCull",      2); // Back
                            material.SetFloat("_SurfaceZWrite",    1);
                            material.SetFloat("_SurfaceSrcBlend",  1); // One
                            material.SetFloat("_SurfaceDstBlend",  0); // Zero
                            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Geometry;
                            break;
                        case 1: // Cutout
                            material.SetFloat("_SurfaceCull",      2); // Back
                            material.SetFloat("_SurfaceZWrite",    1);
                            material.SetFloat("_SurfaceSrcBlend",  1); // One
                            material.SetFloat("_SurfaceDstBlend",  0); // Zero
                            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
                            break;
                        case 2: // Transparent
                            material.SetFloat("_SurfaceCull",      2); // Back
                            material.SetFloat("_SurfaceZWrite",    0);
                            material.SetFloat("_SurfaceSrcBlend",  5); // SrcAlpha
                            material.SetFloat("_SurfaceDstBlend",  10); // OneMinusSrcAlpha
                            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
                            break;
                        case 3: // Cutout Both Sides
                            material.SetFloat("_SurfaceCull",      0); // Off
                            material.SetFloat("_SurfaceZWrite",    1);
                            material.SetFloat("_SurfaceSrcBlend",  1); // One
                            material.SetFloat("_SurfaceDstBlend",  0); // Zero
                            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
                            break;
                        case 4: // Transparent Both Sides
                            material.SetFloat("_SurfaceCull",      0); // Off
                            material.SetFloat("_SurfaceZWrite",    0);
                            material.SetFloat("_SurfaceSrcBlend",  5); // SrcAlpha
                            material.SetFloat("_SurfaceDstBlend",  10); // OneMinusSrcAlpha
                            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
                            break;
                    }
                    EditorUtility.SetDirty(material);
                }
            }
        }
    }
}
