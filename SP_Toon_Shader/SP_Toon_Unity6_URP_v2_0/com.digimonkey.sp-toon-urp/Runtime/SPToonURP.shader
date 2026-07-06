Shader "DiGiMonkey/SP Toon URP"
{
    Properties
    {
        [Header(Lighting)]
        [Toggle] _UseHDR ("HDR Enabled", Float) = 0
        _HDRStrength ("HDR Ambient Strength", Range(0, 5)) = 0
        _LightPosition ("Light Position", Vector) = (10, 10, 10, 0)

        [Header(Hull Outline)]
        [Toggle] _UseHullOutline ("Use Hull Outline", Float) = 1
        _HullOutlineWidth ("Hull Outline Width", Range(0, 0.1)) = 0.003
        _HullOutlineColor ("Hull Outline Color", Color) = (0, 0, 0, 1)
        [NoScaleOffset] _HullOutlineMap ("Hull Outline Texture", 2D) = "white" {}
        _HullNoiseStrength ("Hull Noise Strength", Range(0, 5)) = 0
        _HullNoiseScale ("Hull Noise Scale", Range(0.1, 200)) = 5

        [Header(Outline)]
        [Toggle] _UseOutline ("Use Outline", Float) = 1
        [Toggle] _ReverseOutline ("Reverse Outline", Float) = 0
        _OutlineThickness ("Outline Thickness", Range(0, 1)) = 0.6
        _OutlineBlur ("Outline Blur", Range(0, 5)) = 0
        _OutlineColor ("Outline Color", Color) = (0, 0.7608, 1, 1)
        [NoScaleOffset] _OutlineMap ("Outline Texture", 2D) = "white" {}

        [Header(Inline)]
        _InlineThickness ("Inline Thickness", Range(0, 1)) = 0.14
        _InlineBlur ("Inline Blur", Range(0, 5)) = 0
        _InlineOnTop ("Inline on Top", Range(0, 1)) = 1
        _InlineColor ("Inline Color", Color) = (0.4902, 0.0157, 0, 1)
        [NoScaleOffset] _InlineMap ("Inline Texture", 2D) = "white" {}
        [NoScaleOffset] _CurvatureMap ("Inline Curvature Map", 2D) = "white" {}
        [Toggle] _InvertCurvature ("Invert Curvature", Float) = 0

        [Header(Toon Gradation)]
        _ToonParam2 ("Toon Param 2", Range(-1, 1)) = 0
        _ToonParam3 ("Toon Param 3", Range(-1, 1)) = -0.5
        _ToonParam4 ("Toon Param 4", Range(-1, 1)) = -1
        _ToonParam5 ("Toon Param 5", Range(-1, 1)) = -1
        _ToonParam6 ("Toon Param 6", Range(-1, 1)) = -1
        _ToonParam7 ("Toon Param 7", Range(-1, 1)) = -1
        _ToonBlur ("Toon Blur", Range(0, 5)) = 0

        [Header(Normal Map)]
        [NoScaleOffset] _NormalMap ("Normal Map", 2D) = "bump" {}
        _NormalStrength ("Normal Strength", Range(-5, 5)) = 1

        [Header(Ambient Occlusion)]
        [NoScaleOffset] _AOMap ("AO Map", 2D) = "white" {}
        _AOStrength ("AO Strength", Range(0, 5)) = 1
        _AOColor ("AO Color", Color) = (0, 0, 0, 1)

        [Header(Rim Light)]
        [Toggle] _UseRim ("Use Rim Light", Float) = 0
        _RimStrength ("Rim Strength", Range(0, 20)) = 1
        _RimSharpness ("Rim Sharpness", Range(0, 50)) = 8
        _RimColor ("Rim Color", Color) = (1, 1, 1, 1)

        [Header(Thickness SSS)]
        [Toggle] _UseThickness ("Use Thickness", Float) = 0
        [NoScaleOffset] _ThicknessMap ("Thickness Map", 2D) = "white" {}
        _ThicknessStrength ("Thickness Strength", Range(0, 10)) = 1
        _ThicknessColor ("Thickness Color", Color) = (1, 0.5, 0.3, 1)

        [Header(MatCap)]
        [Toggle] _UseMatCap ("Use MatCap", Float) = 0
        [NoScaleOffset] _MatCapMap ("MatCap Texture", 2D) = "white" {}
        _MatCapStrength ("MatCap Strength", Range(0, 10)) = 1
        [KeywordEnum(Add, Multiply)] _MatCapBlend ("MatCap Blend Mode", Float) = 0

        [Header(Colors and Textures)]
        _BaseColor ("Base Color", Color) = (1, 1, 1, 1)
        _BaseMap ("Base Texture", 2D) = "white" {}

        _ToonColor2 ("Toon Color 2", Color) = (0.6824, 0.6824, 0.6824, 1)
        [NoScaleOffset] _ToonMap2 ("Toon Texture 2", 2D) = "white" {}

        _ToonColor3 ("Toon Color 3", Color) = (0.4941, 0.4941, 0.4941, 1)
        [NoScaleOffset] _ToonMap3 ("Toon Texture 3", 2D) = "white" {}

        _ToonColor4 ("Toon Color 4", Color) = (0.3490, 0.3490, 0.3490, 1)
        [NoScaleOffset] _ToonMap4 ("Toon Texture 4", 2D) = "white" {}

        _ToonColor5 ("Toon Color 5", Color) = (0.2627, 0.2627, 0.2627, 1)
        [NoScaleOffset] _ToonMap5 ("Toon Texture 5", 2D) = "white" {}

        _ToonColor6 ("Toon Color 6", Color) = (0.1961, 0.1961, 0.1961, 1)
        [NoScaleOffset] _ToonMap6 ("Toon Texture 6", 2D) = "white" {}

        _ToonColor7 ("Toon Color 7", Color) = (0.1490, 0.1490, 0.1490, 1)
        [NoScaleOffset] _ToonMap7 ("Toon Texture 7", 2D) = "white" {}

        [Header(Surface)]
        [NoScaleOffset] _OpacityMap ("Opacity Map", 2D) = "white" {}
        [Toggle] _InvertOpacity ("Invert Opacity Map", Float) = 0
        [Toggle] _AlphaClip ("Alpha Clip", Float) = 0
        _OpacityLevel ("Opacity Level", Range(0, 1)) = 1

        // 0=Opaque 1=Cutout 2=Transparent 3=CutoutBothSides 4=TransparentBothSides
        [HideInInspector] _SurfaceMode ("Surface Mode", Float) = 0
        [HideInInspector] _SurfaceCull ("Cull Mode", Float) = 2
        [HideInInspector] _SurfaceZWrite ("ZWrite", Float) = 1
        [HideInInspector] _SurfaceSrcBlend ("Src Blend", Float) = 1
        [HideInInspector] _SurfaceDstBlend ("Dst Blend", Float) = 0
        [HideInInspector] _QueueOffset ("Queue Offset", Float) = 0
    }

    SubShader
    {
        Tags
        {
            "RenderType" = "Transparent"
            "RenderPipeline" = "UniversalPipeline"
            "UniversalMaterialType" = "Unlit"
            "Queue" = "Transparent"
        }

        // ──────────────────────────────────────────
        //  Pass 0 : Hull Outline (Inverted Hull)
        // ──────────────────────────────────────────
        Pass
        {
            Name "HullOutline"
            // No LightMode tag: URP renders this pass unconditionally

            Cull Front
            ZWrite On
            ZTest LEqual
            Blend One Zero

            HLSLPROGRAM

            #pragma target 3.5
            #pragma vertex HullVert
            #pragma fragment HullFrag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct HullAttributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float2 uv         : TEXCOORD0;
            };

            struct HullVaryings
            {
                float4 positionCS : SV_POSITION;
                float2 uv         : TEXCOORD0;
            };

            TEXTURE2D(_HullOutlineMap);
            SAMPLER(sampler_HullOutlineMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;

                half4 _BaseColor;
                half4 _OutlineColor;
                half4 _InlineColor;
                half4 _ToonColor2;
                half4 _ToonColor3;
                half4 _ToonColor4;
                half4 _ToonColor5;
                half4 _ToonColor6;
                half4 _ToonColor7;
                half4 _AOColor;
                half4 _RimColor;
                half4 _ThicknessColor;
                half4 _HullOutlineColor;

                float4 _LightPosition;

                half _UseHDR;
                half _HDRStrength;

                half _UseHullOutline;
                half _HullOutlineWidth;
                half _HullNoiseStrength;
                half _HullNoiseScale;

                half _UseOutline;
                half _ReverseOutline;
                half _OutlineThickness;
                half _OutlineBlur;

                half _InlineThickness;
                half _InlineBlur;
                half _InlineOnTop;
                half _InvertCurvature;

                half _ToonParam2;
                half _ToonParam3;
                half _ToonParam4;
                half _ToonParam5;
                half _ToonParam6;
                half _ToonParam7;
                half _ToonBlur;

                half _NormalStrength;

                half _AOStrength;

                half _UseRim;
                half _RimStrength;
                half _RimSharpness;

                half _UseThickness;
                half _ThicknessStrength;

                half _UseMatCap;
                half _MatCapStrength;
                half _MatCapBlend;

                half _AlphaClip;
                half _OpacityLevel;
                half _InvertOpacity;
                half _SurfaceMode;
                half _SurfaceCull;
                half _SurfaceZWrite;
                half _SurfaceSrcBlend;
                half _SurfaceDstBlend;
            CBUFFER_END

            // ── Value Noise (3D, world-space stable) ──
            float3 NoiseFloor(float3 v) { return floor(v); }

            float NoiseHash(float3 p)
            {
                p = frac(p * float3(127.1, 311.7, 74.7));
                p += dot(p, p + 19.19);
                return frac(p.x * p.y * p.z);
            }

            float ValueNoise3D(float3 p)
            {
                float3 i = NoiseFloor(p);
                float3 f = frac(p);
                float3 u = f * f * (3.0 - 2.0 * f);

                return lerp(
                    lerp(
                        lerp(NoiseHash(i + float3(0,0,0)), NoiseHash(i + float3(1,0,0)), u.x),
                        lerp(NoiseHash(i + float3(0,1,0)), NoiseHash(i + float3(1,1,0)), u.x),
                        u.y),
                    lerp(
                        lerp(NoiseHash(i + float3(0,0,1)), NoiseHash(i + float3(1,0,1)), u.x),
                        lerp(NoiseHash(i + float3(0,1,1)), NoiseHash(i + float3(1,1,1)), u.x),
                        u.y),
                    u.z);
            }

            HullVaryings HullVert(HullAttributes input)
            {
                HullVaryings output;

                float3 positionWS =
                    TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS =
                    TransformObjectToWorldNormal(input.normalOS);

                float noise = ValueNoise3D(positionWS * _HullNoiseScale);
                float width = _HullOutlineWidth * lerp(1.0, noise, _HullNoiseStrength);
                positionWS += normalWS * width;

                output.positionCS = TransformWorldToHClip(positionWS);

                // UseHullOutline OFF: widthを0にしてCull Frontで不可視化
                // さらにpositionCSをNDC外に完全退避
                width *= step(0.5h, _UseHullOutline);
                if (_UseHullOutline < 0.5h)
                {
                    output.positionCS = float4(1e30, 1e30, 1e30, 1);
                    output.uv = 0;
                    return output;
                }
                output.uv = TRANSFORM_TEX(input.uv, _BaseMap);
                return output;
            }

            half4 HullFrag(HullVaryings input) : SV_Target
            {
                half3 col =
                    SAMPLE_TEXTURE2D(
                        _HullOutlineMap,
                        sampler_HullOutlineMap,
                        input.uv
                    ).rgb * _HullOutlineColor.rgb;

                return half4(col, 1.0h);
            }

            ENDHLSL
        }

        // ──────────────────────────────────────────
        //  Pass 1 : Forward (Toon)
        // ──────────────────────────────────────────
        Pass
        {
            Name "Forward"
            Tags { "LightMode" = "UniversalForward" }

            Cull [_SurfaceCull]
            ZWrite [_SurfaceZWrite]
            Blend [_SurfaceSrcBlend] [_SurfaceDstBlend]

            HLSLPROGRAM

            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment Frag

            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile _ _FORWARD_PLUS _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/CommonMaterial.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/RealtimeLights.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float4 tangentOS  : TANGENT;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS    : SV_POSITION;
                float3 positionWS    : TEXCOORD0;
                half3  normalWS      : TEXCOORD1;
                float2 uv            : TEXCOORD2;
                half3  viewDirectionWS : TEXCOORD3;
                half3  tangentWS     : TEXCOORD4;
                half3  bitangentWS   : TEXCOORD5;
            };

            TEXTURE2D(_BaseMap);        SAMPLER(sampler_BaseMap);
            TEXTURE2D(_NormalMap);      SAMPLER(sampler_NormalMap);
            TEXTURE2D(_AOMap);          SAMPLER(sampler_AOMap);
            TEXTURE2D(_ThicknessMap);   SAMPLER(sampler_ThicknessMap);
            TEXTURE2D(_MatCapMap);      SAMPLER(sampler_MatCapMap);
            TEXTURE2D(_OutlineMap);     SAMPLER(sampler_OutlineMap);
            TEXTURE2D(_InlineMap);      SAMPLER(sampler_InlineMap);
            TEXTURE2D(_CurvatureMap);   SAMPLER(sampler_CurvatureMap);
            TEXTURE2D(_ToonMap2);       SAMPLER(sampler_ToonMap2);
            TEXTURE2D(_ToonMap3);       SAMPLER(sampler_ToonMap3);
            TEXTURE2D(_ToonMap4);       SAMPLER(sampler_ToonMap4);
            TEXTURE2D(_ToonMap5);       SAMPLER(sampler_ToonMap5);
            TEXTURE2D(_ToonMap6);       SAMPLER(sampler_ToonMap6);
            TEXTURE2D(_ToonMap7);       SAMPLER(sampler_ToonMap7);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;

                half4 _BaseColor;
                half4 _OutlineColor;
                half4 _InlineColor;
                half4 _ToonColor2;
                half4 _ToonColor3;
                half4 _ToonColor4;
                half4 _ToonColor5;
                half4 _ToonColor6;
                half4 _ToonColor7;
                half4 _AOColor;
                half4 _RimColor;
                half4 _ThicknessColor;
                half4 _HullOutlineColor;

                float4 _LightPosition;

                half _UseHDR;
                half _HDRStrength;

                half _UseHullOutline;
                half _HullOutlineWidth;
                half _HullNoiseStrength;
                half _HullNoiseScale;

                half _UseOutline;
                half _ReverseOutline;
                half _OutlineThickness;
                half _OutlineBlur;

                half _InlineThickness;
                half _InlineBlur;
                half _InlineOnTop;
                half _InvertCurvature;

                half _ToonParam2;
                half _ToonParam3;
                half _ToonParam4;
                half _ToonParam5;
                half _ToonParam6;
                half _ToonParam7;
                half _ToonBlur;

                half _NormalStrength;

                half _AOStrength;

                half _UseRim;
                half _RimStrength;
                half _RimSharpness;

                half _UseThickness;
                half _ThicknessStrength;

                half _UseMatCap;
                half _MatCapStrength;
                half _MatCapBlend;

                half _AlphaClip;
                half _OpacityLevel;
                half _InvertOpacity;
                half _SurfaceMode;
                half _SurfaceCull;
                half _SurfaceZWrite;
                half _SurfaceSrcBlend;
                half _SurfaceDstBlend;
            CBUFFER_END

            TEXTURE2D(_OpacityMap); SAMPLER(sampler_OpacityMap);

            Varyings Vert(Attributes input)
            {
                Varyings output;

                VertexPositionInputs positionInputs =
                    GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs normalInputs =
                    GetVertexNormalInputs(input.normalOS, input.tangentOS);

                output.positionCS      = positionInputs.positionCS;
                output.positionWS      = positionInputs.positionWS;
                output.normalWS        = NormalizeNormalPerVertex(normalInputs.normalWS);
                output.tangentWS       = normalInputs.tangentWS;
                output.bitangentWS     = normalInputs.bitangentWS;
                output.viewDirectionWS =
                    GetWorldSpaceNormalizeViewDir(positionInputs.positionWS);
                output.uv = TRANSFORM_TEX(input.uv, _BaseMap);

                return output;
            }

            half InverseSmoothMask(half value, half threshold, half blur)
            {
                half safeBlur = max(blur, 0.00001h);
                return 1.0h - smoothstep(
                    threshold - safeBlur,
                    threshold + safeBlur,
                    value
                );
            }

            half LuminanceSP(half3 c)
            {
                return dot(c, half3(0.2126h, 0.7152h, 0.0722h));
            }

            half GetManualLightingValue(float3 positionWS, half3 normalWS)
            {
                half3 lightDirection = SafeNormalize(
                    _LightPosition.xyz - positionWS
                );
                return dot(normalWS, lightDirection);
            }

            half GetLightInfluence(Light light)
            {
                half colorIntensity = saturate(LuminanceSP(light.color));
                return saturate(
                    colorIntensity
                    * light.distanceAttenuation
                    * light.shadowAttenuation
                );
            }

            half EvaluateSPToonNdotL(half3 normalWS, Light light)
            {
                half rawNdotL = dot(normalWS, light.direction);
                half influence = GetLightInfluence(light);
                return lerp(-1.0h, rawNdotL, influence);
            }

            half GetSceneHDRLightingValue(InputData inputData)
            {
                half strongestNdotL = -1.0h;

                float4 shadowCoord =
                    TransformWorldToShadowCoord(inputData.positionWS);
                Light mainLight = GetMainLight(shadowCoord);

                strongestNdotL = max(
                    strongestNdotL,
                    EvaluateSPToonNdotL(inputData.normalWS, mainLight)
                );

                #if USE_FORWARD_PLUS || defined(_CLUSTER_LIGHT_LOOP)
                    UNITY_LOOP
                    for (
                        uint lightIndex = 0;
                        lightIndex < min(
                            URP_FP_DIRECTIONAL_LIGHTS_COUNT,
                            MAX_VISIBLE_LIGHTS
                        );
                        lightIndex++
                    )
                    {
                        Light additionalDirectional =
                            GetAdditionalLight(
                                lightIndex,
                                inputData.positionWS,
                                half4(1, 1, 1, 1)
                            );
                        strongestNdotL = max(
                            strongestNdotL,
                            EvaluateSPToonNdotL(
                                inputData.normalWS,
                                additionalDirectional
                            )
                        );
                    }
                #endif

                uint pixelLightCount = GetAdditionalLightsCount();

                LIGHT_LOOP_BEGIN(pixelLightCount)
                    Light additionalLight =
                        GetAdditionalLight(
                            lightIndex,
                            inputData.positionWS,
                            half4(1, 1, 1, 1)
                        );
                    strongestNdotL = max(
                        strongestNdotL,
                        EvaluateSPToonNdotL(inputData.normalWS, additionalLight)
                    );
                LIGHT_LOOP_END

                half3 hdrAmbient = max(SampleSH(inputData.normalWS), half3(0, 0, 0));
                half ambientOffset =
                    saturate(LuminanceSP(hdrAmbient)) * _HDRStrength;

                return clamp(strongestNdotL + ambientOffset, -1.0h, 1.0h);
            }

            // ── MatCap UV from camera-space normal ──
            float2 MatCapUV(half3 normalWS, half3 viewDirectionWS)
            {
                // Build camera-space normal
                half3 up     = half3(0, 1, 0);
                half3 right  = normalize(cross(up, viewDirectionWS));
                      up     = cross(viewDirectionWS, right);
                half2 capUV  = half2(dot(right, normalWS), dot(up, normalWS));
                return capUV * 0.5h + 0.5h;
            }

            half4 Frag(Varyings input) : SV_Target
            {
                // ── Normal Map ──
                half3 normalTS = UnpackNormalScale(
                    SAMPLE_TEXTURE2D(_NormalMap, sampler_NormalMap, input.uv),
                    _NormalStrength
                );
                half3x3 TBN = half3x3(
                    input.tangentWS,
                    input.bitangentWS,
                    input.normalWS
                );
                half3 normalWS = NormalizeNormalPerPixel(
                    mul(normalTS, TBN)
                );

                half3 viewDirectionWS = SafeNormalize(input.viewDirectionWS);

                InputData inputData = (InputData)0;
                inputData.positionWS             = input.positionWS;
                inputData.normalWS               = normalWS;
                inputData.viewDirectionWS         = viewDirectionWS;
                inputData.normalizedScreenSpaceUV =
                    GetNormalizedScreenSpaceUV(input.positionCS);
                inputData.shadowCoord =
                    TransformWorldToShadowCoord(input.positionWS);
                inputData.bakedGI   = SampleSH(normalWS);
                inputData.shadowMask = half4(1, 1, 1, 1);

                // ── Lighting value (NdL) ──
                half lightingValue;
                if (_UseHDR > 0.5h)
                    lightingValue = GetSceneHDRLightingValue(inputData);
                else
                    lightingValue = GetManualLightingValue(
                        input.positionWS, normalWS);

                // ── Base ──
                half4 baseSample =
                    SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, input.uv)
                    * _BaseColor;
                half3 result = baseSample.rgb;

                // ── Toon Gradation ──
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap2, sampler_ToonMap2, input.uv).rgb * _ToonColor2.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam2, _ToonBlur));
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap3, sampler_ToonMap3, input.uv).rgb * _ToonColor3.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam3, _ToonBlur));
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap4, sampler_ToonMap4, input.uv).rgb * _ToonColor4.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam4, _ToonBlur));
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap5, sampler_ToonMap5, input.uv).rgb * _ToonColor5.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam5, _ToonBlur));
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap6, sampler_ToonMap6, input.uv).rgb * _ToonColor6.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam6, _ToonBlur));
                result = lerp(result,
                    SAMPLE_TEXTURE2D(_ToonMap7, sampler_ToonMap7, input.uv).rgb * _ToonColor7.rgb,
                    InverseSmoothMask(lightingValue, _ToonParam7, _ToonBlur));

                // ── AO (乗算、AOColor で黒以外の色指定可) ──
                half aoSample =
                    SAMPLE_TEXTURE2D(_AOMap, sampler_AOMap, input.uv).r;
                half aoFactor = lerp(1.0h, aoSample, _AOStrength);
                // AOColorと乗算: 白=そのまま、黒=完全AO、任意色=色付きAO
                half3 aoTint  = lerp(half3(1, 1, 1), _AOColor.rgb, _AOStrength);
                half3 aoBlend = lerp(half3(1, 1, 1), aoTint, 1.0h - aoFactor);
                result *= aoBlend;

                // ── Rim Light ((1-NdV)^n × NdL、ライト側のみ) ──
                if (_UseRim > 0.5h)
                {
                    half NdV = saturate(dot(normalWS, viewDirectionWS));
                    half rim = pow(1.0h - NdV, _RimSharpness);
                    // lightingValueでライト方向側だけ光る (-1~1 → 0~1)
                    half rimLight = saturate((lightingValue + 1.0h) * 0.5h);
                    result += _RimColor.rgb * rim * rimLight * _RimStrength;
                }

                // ── Thickness SSS (加算、逆光透過感) ──
                if (_UseThickness > 0.5h)
                {
                    half thickSample =
                        SAMPLE_TEXTURE2D(_ThicknessMap, sampler_ThicknessMap, input.uv).r;
                    // 逆光(lightingValue < 0)で最大になるマスク
                    half backLight = saturate(-lightingValue);
                    half NdV = saturate(dot(normalWS, viewDirectionWS));
                    // エッジ側(NdV小)ほど透けやすく
                    half sssEdge = pow(1.0h - NdV, 2.0h);
                    half sss = thickSample * backLight * sssEdge * _ThicknessStrength;
                    result += _ThicknessColor.rgb * sss;
                }

                // ── MatCap ──
                if (_UseMatCap > 0.5h)
                {
                    float2 mcUV = MatCapUV(normalWS, viewDirectionWS);
                    half3 mcSample =
                        SAMPLE_TEXTURE2D(_MatCapMap, sampler_MatCapMap, mcUV).rgb
                        * _MatCapStrength;

                    if (_MatCapBlend < 0.5h)
                        result += mcSample;          // Add
                    else
                        result *= (1.0h + mcSample); // Multiply (brightens less harshly)
                }

                // ── Outline / Inline 合成 ──
                half facing = saturate(dot(normalWS, viewDirectionWS));

                half outlineMask = InverseSmoothMask(
                    facing, _OutlineThickness, _OutlineBlur);
                outlineMask = lerp(outlineMask, 1.0h - outlineMask,
                    saturate(_ReverseOutline));
                outlineMask *= saturate(_UseOutline);

                half3 outlineBlended =
                    SAMPLE_TEXTURE2D(_OutlineMap, sampler_OutlineMap, input.uv).rgb
                    * _OutlineColor.rgb;

                half curvature =
                    SAMPLE_TEXTURE2D(_CurvatureMap, sampler_CurvatureMap, input.uv).r;
                curvature = lerp(curvature, 1.0h - curvature,
                    saturate(_InvertCurvature));

                half inlineMask = InverseSmoothMask(
                    curvature, _InlineThickness, _InlineBlur);

                half3 inlineBlended =
                    SAMPLE_TEXTURE2D(_InlineMap, sampler_InlineMap, input.uv).rgb
                    * _InlineColor.rgb;

                half3 pathA = lerp(result, inlineBlended, inlineMask);
                      pathA = lerp(pathA,  outlineBlended, outlineMask);

                half3 pathB = lerp(result, outlineBlended, outlineMask);
                      pathB = lerp(pathB,  inlineBlended,  inlineMask);

                result = lerp(pathA, pathB, saturate(_InlineOnTop));

                // ── Alpha ──
                half opacitySample =
                    SAMPLE_TEXTURE2D(_OpacityMap, sampler_OpacityMap, input.uv).r;
                opacitySample = lerp(opacitySample, 1.0h - opacitySample,
                    saturate(_InvertOpacity));
                half alpha = opacitySample;
                if (_AlphaClip > 0.5h)
                    clip(alpha - _OpacityLevel);

                return half4(result, alpha);
            }

            ENDHLSL
        }

        // ──────────────────────────────────────────
        //  Pass 2 : Shadow Caster
        // ──────────────────────────────────────────
        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }

            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull [_SurfaceCull]

            HLSLPROGRAM

            #pragma target 3.5
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            struct ShadowAttributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float2 uv         : TEXCOORD0;
            };

            struct ShadowVaryings
            {
                float4 positionCS : SV_POSITION;
                float2 uv         : TEXCOORD0;
            };

            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;

                half4 _BaseColor;
                half4 _OutlineColor;
                half4 _InlineColor;
                half4 _ToonColor2;
                half4 _ToonColor3;
                half4 _ToonColor4;
                half4 _ToonColor5;
                half4 _ToonColor6;
                half4 _ToonColor7;
                half4 _AOColor;
                half4 _RimColor;
                half4 _ThicknessColor;
                half4 _HullOutlineColor;

                float4 _LightPosition;

                half _UseHDR;
                half _HDRStrength;

                half _UseHullOutline;
                half _HullOutlineWidth;
                half _HullNoiseStrength;
                half _HullNoiseScale;

                half _UseOutline;
                half _ReverseOutline;
                half _OutlineThickness;
                half _OutlineBlur;

                half _InlineThickness;
                half _InlineBlur;
                half _InlineOnTop;
                half _InvertCurvature;

                half _ToonParam2;
                half _ToonParam3;
                half _ToonParam4;
                half _ToonParam5;
                half _ToonParam6;
                half _ToonParam7;
                half _ToonBlur;

                half _NormalStrength;

                half _AOStrength;

                half _UseRim;
                half _RimStrength;
                half _RimSharpness;

                half _UseThickness;
                half _ThicknessStrength;

                half _UseMatCap;
                half _MatCapStrength;
                half _MatCapBlend;

                half _AlphaClip;
                half _OpacityLevel;
                half _InvertOpacity;
                half _SurfaceMode;
                half _SurfaceCull;
                half _SurfaceZWrite;
                half _SurfaceSrcBlend;
                half _SurfaceDstBlend;
            CBUFFER_END

            TEXTURE2D(_OpacityMap); SAMPLER(sampler_OpacityMap);

            float4 GetShadowPositionHClip(ShadowAttributes input)
            {
                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS   = TransformObjectToWorldNormal(input.normalOS);

                float4 positionCS = TransformWorldToHClip(
                    ApplyShadowBias(
                        positionWS,
                        normalWS,
                        _MainLightPosition.xyz
                    )
                );

                #if UNITY_REVERSED_Z
                    positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                    positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif

                return positionCS;
            }

            ShadowVaryings ShadowVert(ShadowAttributes input)
            {
                ShadowVaryings output;
                output.positionCS = GetShadowPositionHClip(input);
                output.uv = TRANSFORM_TEX(input.uv, _BaseMap);
                return output;
            }

            half4 ShadowFrag(ShadowVaryings input) : SV_Target
            {
                half alpha =
                    SAMPLE_TEXTURE2D(_OpacityMap, sampler_OpacityMap, input.uv).r;
                alpha = lerp(alpha, 1.0h - alpha, saturate(_InvertOpacity));
                if (_AlphaClip > 0.5h)
                    clip(alpha - _OpacityLevel);
                return 0;
            }

            ENDHLSL
        }
    }

    CustomEditor "DiGiMonkey.SPToonURPShaderGUI"
    FallBack Off
}
