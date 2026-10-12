using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Thistletide.Presentation;

public partial class ProofRun
{
    // Adult anatomy study requested by the owner after pass28. Proof-only:
    // no saved equipment changes, nudity mode or alternative generation stack.
    private void UndressKitStudy(CharacterKit.Figure figure)
    {
        var kept = CharacterKit.Spec.Always.ToHashSet();
        kept.UnionWith(CharacterKit.Spec.Slot("hair", figure.Look.Hair));
        foreach (var mesh in figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>())
            if (!kept.Contains(mesh.Name))
            {
                mesh.GetParent().RemoveChild(mesh);
                mesh.Free();
            }
        var body = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false)
            .Cast<MeshInstance3D>().Single(m => m.Name == "Body");
        var meshData = (ArrayMesh)body.Mesh;
        for (int i = 0; i < meshData.GetBlendShapeCount(); i++)
            if (meshData.GetBlendShapeName(i).ToString().StartsWith("Hide.", StringComparison.Ordinal))
                body.SetBlendShapeValue(i, 0);
        var skeleton = figure.Root.FindChildren("*", nameof(Skeleton3D), true, false).Cast<Skeleton3D>().Single();
        figure.Ground.Bind(skeleton, figure.Clips, figure.Root.GetChild<Node3D>(0), body);
    }

    private async Task KitBodyReviewAsync(Node3D studio, Vector3 centre, Vector2 toward, ViewFrame meadow, ulong self)
    {
        CharacterLook[] pair = { CharacterKit.Look("aldric"), CharacterKit.Look("wren") };
        var right = new Vector3(-toward.Y, 0, toward.X);
        Host.World.SetFree(true);
        Host.World.Pan(centre.X - meadow.Player.X, centre.Z - meadow.Player.Z);
        float before = Host.World.ZoomLevel;
        foreach (float zoom in new[] { WorldCamera.DefaultZoom, WorldCamera.NearestZoom })
        {
            Host.World.Zoom((int)(zoom - Host.World.ZoomLevel));
            foreach (float phase in new[] { 1f, 2f })
            {
                ClearStudio(studio);
                foreach (var (look, i) in pair.Select((look, i) => (look, i)))
                {
                    var figure = KitFigure(studio, look, centre + right * (i - 0.5f) * 0.85f, toward, 0);
                    UndressKitStudy(figure);
                    figure.Hold(FigureClips.Idle, 0);
                }
                Host.World.Present(meadow with { Phase = phase }, self);
                Host.World.SettlePhase();
                await DrawFrames(4);
                await Capture($"body_{(phase == 1 ? "day" : "dusk")}_z{zoom}.png");
            }
        }
        ClearStudio(studio);
        Host.World.Zoom((int)(before - Host.World.ZoomLevel));
        Host.World.Present(meadow, self);
        Host.World.SettlePhase();
        var camera = new Camera3D { Projection = Camera3D.ProjectionType.Orthogonal, Near = 0.05f, Far = 120 };
        studio.AddChild(camera);
        Camera3D game = GetViewport().GetCamera3D()!;
        camera.MakeCurrent();
        var strip = new KitStrip(this, studio, camera, centre, toward);
        try
        {
            foreach (int turn in new[] { 0, 90 })
                await strip.Shoot($"body_rest_{turn}.png", 0.7f,
                    pair.Select(look => new KitShot(look, turn, look.Name) { BodyOnly = true, RestPose = true }));
            foreach (int turn in new[] { 0, 45, 90, 180 })
                await strip.Shoot($"body_detail_{turn}.png", 0.7f,
                    pair.Select(look => new KitShot(look, turn, look.Name) { BodyOnly = true }));
            foreach (var pose in new[] { (FigureClips.Walk, 0.27f), (FigureClips.PickUp, 0.625f) })
                await strip.Shoot($"body_{pose.Item1}.png", 0.7f,
                    pair.Select(look => new KitShot(look, 25, look.Name) { BodyOnly = true, Clip = pose.Item1, At = pose.Item2 }));
            foreach (CharacterLook look in pair)
                foreach (var pose in new[] { (FigureClips.Idle, 0f), (FigureClips.Walk, 0.27f), (FigureClips.PickUp, 0.625f) })
                    await strip.Shoot($"body_fit_{look.Base}_{pose.Item1}.png", 0.56f,
                        CharacterKit.Spec.Bodies.Select(shape => new KitShot(look with
                        {
                            Sliders = new Dictionary<string, float>(CharacterKit.Spec.Body(shape))
                        }, 20, shape) { BodyOnly = true, Clip = pose.Item1, At = pose.Item2 }));
        }
        finally { game.MakeCurrent(); }
        ClearStudio(studio);
        Record("character_kit", new { shot = "body_study", staged = true, pair,
            finish = CharacterKit.IllustratedBody ? "painted" : "baseline",
            clothingApproval = "paused until owner approves bodies", humanArtApproval = false });
    }
}
