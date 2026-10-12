using System;
using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Thistletide.Presentation;

// Phase and weather lighting rig.
public partial class RenderWorld
{
    // Phase is native truth; the rig table in Palette is presentation. A new
    // phase blends in over PhaseBlendMs instead of snapping (spec §9); the
    // proof settles it at once with SettlePhase.
    private const float PhaseBlendMs = 3000;

    private readonly record struct Lit(Color Sun, float SunEnergy, Vector3 SunPos, Color Zenith,
        Color Horizon, Color Ground, Color Fog, Color Fill, float FillEnergy, float Exposure, float FogDensity, Color Veil)
    {
        public static Lit Of(Palette.PhaseRig r) => new(new Color(r.SunColor), r.Sun,
            new Vector3(r.SunX, r.SunY, r.SunZ), new Color(r.Zenith), new Color(r.Horizon), new Color(r.Ground),
            new Color(r.Fog), new Color(r.FillColor), r.Fill, r.Exposure, r.FogDensity, new Color(r.Veil));

        public static Lit Mix(Lit a, Lit b, float t) => new(a.Sun.Lerp(b.Sun, t),
            Mathf.Lerp(a.SunEnergy, b.SunEnergy, t), a.SunPos.Lerp(b.SunPos, t), a.Zenith.Lerp(b.Zenith, t),
            a.Horizon.Lerp(b.Horizon, t), a.Ground.Lerp(b.Ground, t), a.Fog.Lerp(b.Fog, t), a.Fill.Lerp(b.Fill, t),
            Mathf.Lerp(a.FillEnergy, b.FillEnergy, t), Mathf.Lerp(a.Exposure, b.Exposure, t),
            Mathf.Lerp(a.FogDensity, b.FogDensity, t), a.Veil.Lerp(b.Veil, t));

        // This phase's light under [w]'s sky: clouds pull every colour
        // toward the overcast grey at its own brightness, a heavy sky
        // darkens, the sun dims behind cloud, and fog thickens.
        public Lit Under(Palette.WeatherRig w)
        {
            Color cloud = new(w.Cloud);
            Color Grey(Color c, float share) =>
                c.Lerp(Color.FromHsv(cloud.H, cloud.S, c.V, c.A), share);
            Color Sky(Color c) => Grey(c, w.Overcast).Darkened(1 - w.Gloom);
            return new Lit(Grey(Sun, w.Overcast * 0.5f), SunEnergy * w.Sun, SunPos, Sky(Zenith),
                Sky(Horizon), Sky(Ground), Sky(Fog), Grey(Fill, w.Overcast), FillEnergy * w.Fill, Exposure,
                FogDensity * w.Fog, Sky(Veil));
        }
    }

    private Lit _lit;
    private Lit _litFrom;
    private Lit _litTo;
    private ulong _litStart;
    private bool _litSet;

    public LookTuning Look => _look.Tuning;

    // Re-applies the look (LookTuning) to the light now, so a changed layer shows at once.
    public void ApplyLook(LookTuning tuning)
    {
        _look.Apply(tuning);
        if (_litSet) Light(_lit);
    }

    // Jump the light to the current phase's rig, skipping the blend.
    public void SettlePhase()
    {
        _lit = _litTo;
        Light(_lit);
    }

    // Advance the phase blend; a no-op once the light has arrived.
    private void BlendPhase()
    {
        if (!_litSet || _lit == _litTo) return;
        float t = Math.Clamp((Time.GetTicksMsec() - _litStart) / PhaseBlendMs, 0f, 1f);
        _lit = t >= 1 ? _litTo : Lit.Mix(_litFrom, _litTo, t * t * (3 - 2 * t));
        Light(_lit);
    }

    private void Light(Lit lit)
    {
        _sun.LightColor = lit.Sun;
        _sun.LightEnergy = lit.SunEnergy * _look.Tuning.Sun.Strength;
        _sun.ShadowOpacity = CharacterKit.IllustratedBody ? 0.65f : 1f;
        _sun.ShadowBlur = CharacterKit.IllustratedBody ? 2f : 1f;
        _sun.Position = lit.SunPos;
        _sun.LookAt(Vector3.Zero); // A direction, independent of the pawn's map coordinates.
        _terrain.SetUnknownVeil(lit.Veil, lit.Sun);
        // Dusk keys at 0.5 and night at 0.3: the rim turns moonlit as the key fades.
        PawnAppearance.SetMoonlight((0.5f - lit.SunEnergy) / 0.2f);
        _sky.SkyTopColor = lit.Zenith;
        _sky.SkyHorizonColor = lit.Horizon;
        _sky.GroundBottomColor = lit.Ground;
        _sky.GroundHorizonColor = lit.Horizon;
        _atmosphere.AmbientLightColor = lit.Fill;
        // The illustrated study keeps the phase/weather fill, with a softer key/fill ratio.
        _atmosphere.AmbientLightEnergy = lit.FillEnergy * (CharacterKit.IllustratedBody ? 1.6f : 1f);
        _atmosphere.TonemapExposure = lit.Exposure;
        _atmosphere.FogLightColor = _look.FogColour(lit.Fog);
        _atmosphere.FogDensity = _look.FogDensity(lit.FogDensity);
    }

    // Phase and weather both re-key the light: a new day's sky blends in
    // over the same PhaseBlendMs as a new phase.
    private void ApplyLight(float phase, string weather)
    {
        int ordinal = (int)MathF.Round(phase);
        if (ordinal < 0 || ordinal > 3) ordinal = 3;
        if (ordinal == _appliedPhase && weather == _appliedWeather) return;
        _appliedPhase = ordinal;
        _appliedWeather = weather;
        Palette.WeatherRig sky = Palette.Sky(weather);
        _weather.Present(sky);
        _litTo = Lit.Of(Palette.Rig(ordinal)).Under(sky);
        _litFrom = _litSet ? _lit : _litTo;
        _litStart = Time.GetTicksMsec();
        if (!_litSet)
        {
            _litSet = true;
            SettlePhase();
        }
        // Night sheen, ported from the reference Pawn.svelte emissive floor:
        // full at night/unset (which reads night), off otherwise, so
        // dark-albedo figures read instead of rendering as silhouettes. The
        // channel stays enabled with zero energy by day to avoid shader
        // recompiles on phase change.
        _sheen = ordinal == 3 ? 1 : 0;
        foreach (StandardMaterial3D sheen in _sheenMaterials)
            sheen.EmissionEnergyMultiplier = _sheen;
        foreach (HallVisual hall in _halls.Values) hall.SetPhase(ordinal);
        foreach (var structure in _structures.Values)
            if (structure.Knowledge == Knowledge.Visible && structure.Root is HallVisual shelter)
                shelter.SetPhase(ordinal);
    }

}
