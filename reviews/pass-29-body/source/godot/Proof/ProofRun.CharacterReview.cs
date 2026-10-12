using System;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Thistletide.Presentation;

// A repeatable #4264 art-review study on the production PawnAppearance path.
// The six identities are explicitly staged from one seen human, not presented
// as people the controlled pawn observed in gameplay. Nothing writes to Sim.
// The existing appearance proof separately verifies real saved identity.
public partial class ProofRun
{
    private async Task ScenarioProductionCharacterReviewAsync(
        ViewFrame live, SeenEntity source, ulong self, Vector2 toward, Vector2 stand)
    {
        Require(source.Look is not null, "Production character study requires a human appearance.");
        Look original = source.Look!;
        // Keep the sample deliberately small: one soft/average adult, one tall,
        // one broad, one rounded, one hip-heavy, and one older/bearded silhouette.
        // Appearance has no authored sex/age bit, so the study does not claim
        // that those identities are simulated facts or already art-approved.
        var recipes = new[]
        {
            (Name: "soft", Hair: "crop", Head: "none", Beard: false, Mass: -0.25f, Frame: -0.3f, Height: 1.00f, Outer: 0),
            (Name: "tall", Hair: "long", Head: "none", Beard: false, Mass: -0.7f, Frame: -0.15f, Height: 1.07f, Outer: 1),
            (Name: "broad", Hair: "tail", Head: "none", Beard: false, Mass: 0.2f, Frame: 1.0f, Height: 1.03f, Outer: 2),
            (Name: "round", Hair: "bun", Head: "none", Beard: false, Mass: 1.0f, Frame: 0.0f, Height: 0.96f, Outer: 3),
            (Name: "hips", Hair: "long", Head: "cap", Beard: false, Mass: 0.5f, Frame: -1.0f, Height: 0.99f, Outer: 1),
            (Name: "older", Hair: "crop", Head: "brim", Beard: true, Mass: 0.6f, Frame: 0.8f, Height: 0.94f, Outer: 0)
        };
        Look[] looks = recipes.Select((r, i) => original with
        {
            Hair = r.Hair, Headwear = r.Head, Beard = r.Beard,
            Mass = r.Mass, Frame = r.Frame, Stature = r.Height,
            FaceWidth = new[] { -0.7f, -0.3f, 0.85f, 0.4f, -0.6f, 0.6f }[i],
            FaceLength = new[] { 0f, 0.6f, 0.2f, -0.4f, -0.2f, 0.4f }[i],
            Vest = r.Outer == 1, Apron = r.Outer == 2, Cloak = r.Outer == 3,
            Scarf = i == 4, Cloth = (original.Cloth + 29 * i) % 256,
            Skin = (original.Skin + 13 * i) % 256,
            HairTone = (original.HairTone + 31 * i) % 256
        }).ToArray();

        Vector2 across = new(-toward.Y, toward.X);
        Vector2[] spots = Enumerable.Range(0, 6)
            .Select(i => stand + across * ((i - 2.5f) * 0.85f)).ToArray();
        // The controlled pawn is slot 2; the other five are staging-only IDs.
        // Two faction values test palette/readability side by side, not diplomacy.
        int ownFaction = live.Player.Faction ?? 0;
        int otherFaction = (ownFaction + 1) % 3;
        SeenEntity[] actors = Enumerable.Range(0, 6).Where(i => i != 2).Select(i => source with
        {
            Id = (ulong)(900400 + i), Label = recipes[i].Name, Look = looks[i],
            Faction = i < 3 ? ownFaction : otherFaction,
            X = spots[i].X, Z = spots[i].Y, State = "idle",
            Equipped = "", Carried = "", Activity = null, Following = false
        }).ToArray();
        float forward = MathF.Atan2(toward.Y, toward.X);
        ViewFrame Study(float phase, float turn) => live with
        {
            Phase = phase, Weather = PresentationVocabulary.Weather.Clear,
            Player = live.Player with
            {
                X = spots[2].X, Z = spots[2].Y, Look = looks[2],
                State = "idle", Equipped = "", Carried = "", Activity = null
            },
            Entities = live.Entities.Where(e => e.Kind != PresentationVocabulary.EntityKind.Pawn)
                .Concat(actors.Select(a => a with { Heading = forward + Mathf.DegToRad(turn) }))
                .ToArray()
        };

        float previousZoom = Host.World.ZoomLevel;
        bool previousHud = Host.Hud.Visible;
        try
        {
            Host.Hud.Visible = false;
            // A staged Look is a new figure identity for this proof; rebuild
            // the controlled pawn just as the appearance proof does.
            Host.World.ResetRun();
            Host.World.Zoom((int)(WorldCamera.DefaultZoom - Host.World.ZoomLevel));
            ViewFrame day = Study(1, 0);
            Host.World.Present(day, self);
            Host.World.SettlePhase();
            await DrawFrames(40);
            foreach (SeenEntity actor in actors)
                ReadReviewHuman(actor.Id, actor.Look!, actor.Faction);
            ReadReviewHuman(self, looks[2], ownFaction);
            await Capture("folk_review_day_z9.png");

            Host.World.Present(Study(2, 0), self);
            Host.World.SettlePhase();
            await DrawFrames(6);
            await Capture("folk_review_dusk_z9.png");

            Host.World.Zoom((int)(WorldCamera.NearestZoom - Host.World.ZoomLevel));
            foreach ((string name, float angle) in new[]
                { ("front", 0f), ("threequarter", 45f), ("profile", 90f), ("rear", 180f) })
            {
                Host.World.Present(Study(1, angle), self);
                Host.World.SettlePhase();
                // The presentation eases headings; don't sample mid-turn.
                await DrawFrames(40);
                await Capture($"folk_review_{name}_z5.png");
            }
            // Same dye and cropped hair isolate body/face identity. The
            // difference must survive without six shirt colours or hats.
            Look[] savedLooks = looks;
            looks = savedLooks.Select(l => l with
            {
                Cloth = original.Cloth, Skin = original.Skin, HairTone = original.HairTone,
                Hair = "crop", Headwear = "none", Beard = false,
                Vest = false, Apron = false, Cloak = false, Scarf = false
            }).ToArray();
            actors = actors.Select(a => a with { Look = looks[(int)(a.Id - 900400)], Faction = ownFaction }).ToArray();
            Host.World.ResetRun();
            Host.World.Present(Study(1, 0), self);
            Host.World.SettlePhase();
            await DrawFrames(40);
            foreach (SeenEntity actor in actors) ReadReviewHuman(actor.Id, actor.Look!, actor.Faction);
            ReadReviewHuman(self, looks[2], ownFaction);
            var bodyMeasurements = Enumerable.Range(0, 6).Select(i =>
            {
                ulong id = i == 2 ? self : (ulong)(900400 + i);
                Node3D figure = Host.World.HumanFigure(id)!;
                var shirt = (MeshInstance3D)figure.FindChild("Shirt", true, false)!;
                using ArrayMesh baked = shirt.BakeMeshFromCurrentBlendShapeMix();
                Vector3[] vertices = baked.SurfaceGetArrays(0)[(int)Mesh.ArrayType.Vertex].AsVector3Array()
                    .Select(v => v * figure.Scale).ToArray();
                Vector3[] chest = vertices.Where(v => v.Y is > 0.70f and < 0.82f
                    && Math.Abs(v.X) < 0.3f).ToArray();
                return new { recipes[i].Name, width = chest.Max(v => v.X) - chest.Min(v => v.X),
                    scale = figure.Scale.X };
            }).ToArray();
            await Capture("folk_review_silhouettes_z5.png");
            Host.World.Zoom((int)(WorldCamera.DefaultZoom - Host.World.ZoomLevel));
            Host.World.Present(Study(1, 0), self);
            await DrawFrames(6);
            await Capture("folk_review_silhouettes_z9.png");
            // Moving poses use the production state-to-clip mapping. These
            // rows are staged read-only frames, not evidence of Sim orders.
            looks = savedLooks;
            actors = actors.Select(a => a with { Look = looks[(int)(a.Id - 900400)],
                Faction = a.Id < 900403 ? ownFaction : otherFaction }).ToArray();
            Host.World.ResetRun();
            int gaitFrames = 0;
            for (int i = 0; i < 60; i++)
            {
                ViewFrame moving = Study(1, 90);
                // Software-rendered frames take longer than live GPU frames.
                // Stage enough travel per batch to see a gait, then count the
                // actual clips during motion rather than after settling.
                float travel = (i / 6) * 0.4f;
                moving = moving with
                {
                    Entities = moving.Entities.Select(a => a.Kind == "pawn"
                        ? a with { State = "walking", X = a.X + across.X * travel,
                            Z = a.Z + across.Y * travel } : a).ToArray()
                };
                if (i % 6 == 0) Host.World.Present(moving, self);
                await DrawFrames(1);
                if (actors.All(a => Host.World.Clip(a.Id) is FigureClips.Walk or FigureClips.Run)) gaitFrames++;
                await Capture($"folk_review_walk_{i:D4}.png");
            }
            Require(gaitFrames > 0, "Staged walking review never draws all NPCs in a gait.");
            Record("folk_review", new
            {
                staged = true, source = KitPawnAppearance.Enabled
                    ? "CC0 MakeHuman kit via production KitPawnAppearance" : "production Frontier Folk via PawnAppearance",
                captured = new[] { "day_z9", "dusk_z9", "front_z5", "threequarter_z5", "profile_z5", "rear_z5" },
                profiles = recipes.Select((r, i) => new { r.Name, look = looks[i], faction = i < 3 ? ownFaction : otherFaction }).ToArray(),
                posesCaptured = "idle and staged walking", humanArtApproval = false,
                bodyMeasurements, gaitFrames,
                reviewAsset = KitPawnAppearance.Enabled ? "assets/characters/kit/kit_<base>.glb"
                    : System.Environment.GetEnvironmentVariable("TT_FOLK_REVIEW_ASSET") ?? PawnAppearance.FolkAsset
            });
        }
        finally
        {
            Host.World.ResetRun();
            Host.World.Present(live, self);
            Host.Hud.Present(live, self);
            Host.World.Zoom((int)(previousZoom - Host.World.ZoomLevel));
            Host.Hud.Visible = previousHud;
            Host.Refresh();
        }
    }

    private void ReadReviewHuman(ulong id, Look look, int? faction)
    {
        if (!KitPawnAppearance.Enabled)
        {
            ReadHuman(id, look);
            return;
        }
        Node3D? root = Host.World.HumanFigure(id);
        Require(root is not null, $"Kit human {id} has no production figure.");
        CharacterKitSpec spec = CharacterKit.Spec;
        CharacterLook projected = KitLook.Of(look, Race.Human, id, spec, faction);
        var (worn, shapes) = spec.Dress(projected);
        var meshes = root!.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>()
            .Where(m => m.Name != "Held" && m.GetParent()?.Name != "Held")
            .Where(m => m.Skin is not null).ToArray();
        Require(meshes.Select(m => m.Name.ToString()).ToHashSet().SetEquals(worn),
            $"Kit human {id} draws [{string.Join(", ", meshes.Select(m => m.Name))}], expected [{string.Join(", ", worn)}].");
        Require(root.Scale.IsEqualApprox(Vector3.One * spec.GameScale), $"Kit human {id} lost kit scale.");
        foreach (MeshInstance3D mesh in meshes)
        {
            foreach ((string key, float value) in shapes)
                if (mesh.FindBlendShapeByName(key) is int index and >= 0)
                    Require(Mathf.IsEqualApprox(mesh.GetBlendShapeValue(index), value),
                        $"Kit human {id}/{mesh.Name} lost {key}.");
            if (mesh.Name == "Body" && CharacterKit.IllustratedBody)
            {
                Require(mesh.MaterialOverride is ShaderMaterial, $"Kit human {id} lacks its painted body material.");
                var bodyMaterial = (ShaderMaterial)mesh.MaterialOverride;
                Require(bodyMaterial.GetShaderParameter("skin_colour").AsColor().IsEqualApprox(new Color(spec.Colour(projected, "Body"))),
                    $"Kit human {id} lost its saved skin palette.");
                continue;
            }
            var material = mesh.MaterialOverride as StandardMaterial3D;
            Require(material is not null, $"Kit human {id}/{mesh.Name} lacks its surface material.");
            Color expected = new(spec.Colour(projected, mesh.Name));
            expected.A = material!.AlbedoColor.A;
            Require(material.AlbedoColor.IsEqualApprox(expected),
                $"Kit human {id}/{mesh.Name} lost its saved palette or faction dye.");
            if (mesh.Name == "Brows" || mesh.Name == "Eyelashes")
                Require(material.NextPass is null && !material.RimEnabled,
                    $"Kit human {id}/{mesh.Name} draws a cosmetic outline.");
        }
    }
}
