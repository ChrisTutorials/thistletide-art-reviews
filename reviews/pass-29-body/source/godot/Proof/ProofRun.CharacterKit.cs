using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;

namespace Thistletide.Presentation;

// The character kit in the game (CharacterKit.cs): people built at runtime
// from the CC0 MakeHuman bases, standing on cleared meadow in the live
// world's daylight. The kit pawn path remains opt-in (TT_KIT_PAWNS).
//
//   kit_lineup_z9.png, kit_lineup_z5.png  the authored looks (looks/*.json)
//                       through the game's own camera at the default and
//                       nearest zoom
//   kit_bases.png       the male and female base: front, three-quarter,
//                       side and back
//   kit_outfits.png     every outfit on both bases
//   kit_hair_<base>.png every hair style, head and shoulders
//   kit_body_<slider>.png  each body slider at -1, 0 and +1 on both bases
//   kit_face_<slider>.png  each face slider at -1 and +1 on both bases
//   kit_races.png, kit_races_face_<base>.png  human, goblin, orc, vampire
//   kit_walk.png        one walk clip on five very different bodies
//   kit_expressions_<base>.png  neutral, smile, blink, mouth open
//
// It asserts that every look builds with exactly the parts it asks for and
// that the joints follow the sliders; the captures are the evidence of how
// it looks. Run alone with `run.sh --scenario=character-kit`.
public partial class ProofRun
{
    // Strip framing in world units: the least height a whole-person strip
    // shows, how far below the feet it starts (room for the captions), and
    // the eye height every head is lifted to for head-and-shoulders strips.
    private const float KitWhole = 1.75f, KitFloor = 0.26f, KitHeadAim = 1.2f;

    private async Task ScenarioCharacterKitAsync()
    {
        ViewFrame live = Host.Frame;
        ulong self = live.Player.Id;
        Vector3 lens = Host.World.CamPos - Host.World.CamFocus;
        Vector2 toward = new Vector2(lens.X, lens.Z).Normalized();
        Vector2 player = new(live.Player.X, live.Player.Z);
        // Well to the side of the player, so the reader's own figure is out
        // of every shot.
        Vector2 stage = player + new Vector2(-toward.Y, toward.X) * 14;
        var cells = new List<TerrainCell>();
        for (int x = (int)MathF.Min(player.X, stage.X) - 24; x <= (int)MathF.Max(player.X, stage.X) + 24; x++)
            for (int z = (int)MathF.Min(player.Y, stage.Y) - 24; z <= (int)MathF.Max(player.Y, stage.Y) + 24; z++)
                cells.Add(new TerrainCell { X = x, Z = z, Kind = "grass", Knowledge = Knowledge.Visible, LastSeen = live.Tick });
        ViewFrame meadow = live with
        {
            Phase = 1, Weather = PresentationVocabulary.Weather.Clear,
            Cells = cells.ToArray(), Entities = Array.Empty<SeenEntity>(), Homes = Array.Empty<HomeState>(),
            Buildings = Array.Empty<BuildingState>(), Construction = Array.Empty<ConstructionSiteState>(),
            Projectiles = Array.Empty<ProjectileState>(), Context = Array.Empty<ContextAction>()
        };
        Host.Hud.Visible = false;
        Host.World.Present(meadow, self);
        Host.World.SettlePhase();
        var studio = new Node3D { Name = "KitStudio" };
        Host.World.AddChild(studio);
        var centre = new Vector3(stage.X, 0, stage.Y);
        try
        {
            // The clear sky stops new blown leaves, but a windy live day
            // leaves some in the air for their lifetime (3 s,
            // WeatherVisual.tscn); let them land before the first shot.
            await ToSignal(GetTree().CreateTimer(4), SceneTreeTimer.SignalName.Timeout);
            if (System.Environment.GetEnvironmentVariable("TT_KIT_BODY_REVIEW") == "1")
                await KitBodyReviewAsync(studio, centre, toward, meadow, self);
            else
            {
                await KitLineupAsync(studio, centre, toward, meadow, self);
                await KitCloseUpsAsync(studio, centre, toward);
            }
        }
        finally
        {
            studio.QueueFree();
            // Only this scenario loads the kits so far; free them with it.
            CharacterKit.Release();
            Host.Hud.Visible = true;
            Host.World.SetFree(false);
            Host.Refresh();
        }
        await DrawFrames(2);
    }

    // The authored looks through the game's own camera, panned from the
    // player to the stage.
    private async Task KitLineupAsync(Node3D studio, Vector3 centre, Vector2 toward, ViewFrame meadow, ulong self)
    {
        string[] names = { "aldric", "wren", "bram", "mira", "grub", "thokk", "vesna" };
        var right = new Vector3(-toward.Y, 0, toward.X);
        for (int i = 0; i < names.Length; i++)
            KitFigure(studio, CharacterKit.Look(names[i]), centre + right * (i - (names.Length - 1) / 2f) * 0.8f, toward, 0)
                .Clips.Play(FigureClips.Idle);
        Host.World.SetFree(true);
        Host.World.Pan(centre.X - meadow.Player.X, centre.Z - meadow.Player.Z);
        float before = Host.World.ZoomLevel;
        foreach (float zoom in new[] { WorldCamera.DefaultZoom, WorldCamera.NearestZoom })
        {
            Host.World.Zoom((int)(zoom - Host.World.ZoomLevel));
            Host.World.Present(meadow, self);
            Host.World.SettlePhase();
            await DrawFrames(6);
            await Capture($"kit_lineup_z{zoom}.png");
            Record("character_kit", new { shot = "lineup", zoom });
        }
        Host.World.Zoom((int)(before - Host.World.ZoomLevel));
        ClearStudio(studio);

        // The Sim generates and owns these identities; use the real projection
        // so this population cannot bypass the saved-pawn appearance mapping.
        var cohort = new List<object>();
        var community = new List<CharacterKit.Figure>();
        for (int i = 0; i < 30; i++)
        {
            ulong id = (ulong)i + 1;
            var saved = Thistletide.Sim.HumanAppearance.Generate(137, id);
            Look projected = ManagedSession.PresentAppearance(saved);
            CharacterLook look = KitLook.Of(projected, Race.Human, id, CharacterKit.Spec);
            Vector3 at = centre + right * ((i % 10) - 4.5f) * 0.75f
                - new Vector3(toward.X, 0, toward.Y) * (i / 10) * 1.65f;
            community.Add(KitFigure(studio, look, at, toward, 0));
            cohort.Add(new { id, look.Base, look.Face, look.Hair, look.Outfit, look.Headwear, look.Beard,
                look.Neckwear, saved = projected });
        }
        Host.World.Zoom((int)(WorldCamera.DefaultZoom - Host.World.ZoomLevel));
        Host.World.Pan(-toward.X * 1.65f, -toward.Y * 1.65f);
        Host.World.Present(meadow, self);
        Host.World.SettlePhase();
        await DrawFrames(6);
        Camera3D lens = GetViewport().GetCamera3D()!;
        Rect2 bounds = GetViewport().GetVisibleRect().Grow(-12);
        foreach (CharacterKit.Figure figure in community)
        {
            var skeleton = (Skeleton3D)figure.Root.FindChildren("*", nameof(Skeleton3D), true, false)[0];
            Vector3 crown = skeleton.GlobalTransform * skeleton.GetBoneGlobalPose(skeleton.FindBone("head")).Origin
                + Vector3.Up * 0.2f;
            Require(bounds.HasPoint(lens.UnprojectPosition(crown))
                && bounds.HasPoint(lens.UnprojectPosition(figure.Root.GlobalPosition)),
                $"Community camera crops {figure.Look.Name}.");
        }
        await Capture("kit_community_30.png");
        Record("character_kit", new { shot = "community", seed = 137, people = cohort });
        Host.World.Pan(toward.X * 1.65f, toward.Y * 1.65f);
        Host.World.Zoom((int)(before - Host.World.ZoomLevel));
        ClearStudio(studio);

        for (int i = 0; i < 3; i++)
        {
            ulong id = (ulong)i + 137;
            Look saved = ManagedSession.PresentAppearance(Thistletide.Sim.HumanAppearance.Generate(137, id));
            Vector3 at = centre + right * (i - 1) * 1.6f;
            var body = new Node3D();
            studio.AddChild(body);
            body.Position = at - right * 0.35f;
            PawnAppearance.Figure folk = PawnAppearance.Build(body, null, false, "human", saved);
            folk.Root.Rotation = new Vector3(0, MathF.Atan2(toward.X, toward.Y), 0);
            folk.Animator.Play(FigureClips.Idle);
            KitFigure(studio, KitLook.Of(saved, Race.Human, id, CharacterKit.Spec), at + right * 0.35f, toward, 0);
        }
        foreach (float zoom in new[] { WorldCamera.DefaultZoom, WorldCamera.NearestZoom })
        {
            Host.World.Zoom((int)(zoom - Host.World.ZoomLevel));
            Host.World.Present(meadow, self);
            Host.World.SettlePhase();
            await DrawFrames(6);
            await Capture($"kit_comparison_z{zoom}.png");
        }
        Host.World.Zoom((int)(before - Host.World.ZoomLevel));
        ClearStudio(studio);
    }

    private async Task KitCloseUpsAsync(Node3D studio, Vector3 centre, Vector2 toward)
    {
        CharacterKitSpec spec = CharacterKit.Spec;
        var camera = new Camera3D { Projection = Camera3D.ProjectionType.Orthogonal, Near = 0.05f, Far = 120 };
        studio.AddChild(camera);
        Camera3D? game = GetViewport().GetCamera3D();
        camera.MakeCurrent();
        var strip = new KitStrip(this, studio, camera, centre, toward);
        try
        {
            static CharacterLook Plain(string body) => new(body == "male" ? "Male" : "Female", body, "human",
                body == "male" ? "short" : "long", "frontier",
                new Dictionary<string, float>(), new Dictionary<string, string>());
            string[] bases = spec.Bases.ToArray();
            RequireJointsFollow(studio, Plain("male"));

            string[] heroes = { "aldric", "wren", "bram" };
            foreach (float turn in new[] { 0, 45, 90, 180 })
                await strip.Shoot($"kit_heroes_{turn:0}.png", 0.65f,
                    heroes.Select(name => new KitShot(CharacterKit.Look(name), turn, name)));
            await strip.Shoot("kit_hero_faces.png", 0.35f,
                heroes.Select(name => new KitShot(CharacterKit.Look(name), 20, name)), heads: true);

            // The bases from four sides.
            float[] turns = { 0, 45, 90, 180 };
            await strip.Shoot("kit_bases.png", 0.5f,
                bases.SelectMany(b => turns.Select(t => new KitShot(Plain(b), t, $"{b} {t:0}°"))));

            // Every outfit, both bases.
            await strip.Shoot("kit_outfits.png", 0.5f,
                bases.SelectMany(b => spec.Choices("outfit").Select(o => new KitShot(Plain(b) with { Outfit = o }, 20, o))));

            // Every hair style, head and shoulders.
            foreach (string body in bases)
                await strip.Shoot($"kit_hair_{body}.png", 0.42f,
                    spec.Choices("hair").Select(h => new KitShot(Plain(body) with { Hair = h }, 25, h)), heads: true);

            foreach (float turn in turns)
                await strip.Shoot($"kit_hair_masculine_{turn:0}.png", 0.38f,
                    spec.HairFamily("crop").Distinct().Select(h => new KitShot(Plain("male") with { Hair = h }, turn, h)), heads: true);
            foreach (string body in bases)
                foreach (var expression in new[] { ("neutral", new Expression(0, 0, 0)), ("smile", new Expression(0, 0, 0.7f)),
                             ("open", new Expression(0, 0.6f, 0)) })
                    await strip.Shoot($"kit_archetypes_{body}_{expression.Item1}.png", 0.36f,
                        spec.Faces(body).Select(f => new KitShot(Plain(body) with { Face = f }, 20, f) { Face = expression.Item2 }), heads: true);

            // Same garment across combined body shapes, then posed. Single
            // slider sheets cannot catch a heavy waist plus broad shoulders.
            foreach (string body in bases)
                foreach (string outfit in new[] { "frontier_vest", "frontier_apron", "frontier_cloak" })
                    foreach (var pose in new[] { (FigureClips.Idle, 0f), (FigureClips.Walk, 0.27f),
                                 (FigureClips.PickUp, 0.625f), (FigureClips.Swing, 0.15f),
                                 (FigureClips.Chop, 0.3f), (FigureClips.Craft, 0.3f),
                                 (FigureClips.ShoulderWalk, 0.27f), (FigureClips.HugWalk, 0.27f),
                                 (FigureClips.Sleep, 0.4f) })
                    {
                        string[][] rows = pose.Item1 == FigureClips.Sleep ? spec.Bodies.Chunk(3).ToArray()
                            : new[] { spec.Bodies.ToArray() };
                        for (int row = 0; row < rows.Length; row++)
                            await strip.Shoot($"kit_fit_{body}_{outfit}_{pose.Item1}{(rows.Length > 1 ? "_" + row : "")}.png",
                                pose.Item1 == FigureClips.Sleep ? 1.6f : 0.56f,
                                rows[row].Select(f => new KitShot(Plain(body) with
                            {
                                Outfit = outfit, Sliders = new Dictionary<string, float>(spec.Body(f))
                            }, 20, f) { Clip = pose.Item1, At = pose.Item2 }));
                    }

            // Body sliders at -1, 0 and +1 (the first twelve are the body's).
            foreach (string slider in spec.Sliders.Take(12))
                await strip.Shoot($"kit_body_{slider}.png", 0.5f,
                    bases.SelectMany(b => new[] { -1f, 0f, 1f }.Select(v => new KitShot(Plain(b).With(slider, v),
                        slider is "Shoulders" or "Chest" or "Waist" or "Hips" ? 0 : 20, $"{slider} {v:+0;-0;0}"))));
            RequireHeldKitContactModes(Plain("male"));

            // Face sliders at -1 and +1, close up.
            foreach (string slider in spec.Sliders.Skip(12))
                await strip.Shoot($"kit_face_{slider}.png", 0.3f,
                    bases.SelectMany(b => new[] { -1f, 1f }.Select(v => new KitShot(Plain(b).With(slider, v), 30, $"{slider} {v:+0;-0}"))),
                    heads: true);

            // Races: whole body, then faces.
            await strip.Shoot("kit_races.png", 0.5f, bases.SelectMany(b =>
                spec.Races.Select(r => new KitShot(Plain(b) with { Race = r, Outfit = "frontier_vest" }, 20, r))));
            foreach (string body in bases)
                await strip.Shoot($"kit_races_face_{body}.png", 0.3f,
                    spec.Races.Select(r => new KitShot(Plain(body) with { Race = r }, 30, r)), heads: true);

            // One walk clip on very different bodies, mid stride, side on.
            await strip.Shoot("kit_walk.png", 0.62f, new[] { "grub", "mira", "bram", "thokk", "wren" }
                .Select(w => new KitShot(CharacterKit.Look(w), 90, w) { Clip = FigureClips.Walk, At = 0.27f }));

            // Expressions, close up.
            var faces = new (string Label, Expression Face)[]
            {
                ("neutral", new Expression(0, 0, 0)), ("smile", new Expression(0, 0, 1)),
                ("blink", new Expression(1, 0, 0)), ("mouth open", new Expression(0, 1, 0))
            };
            foreach (string body in bases)
                await strip.Shoot($"kit_expressions_{body}.png", 0.3f,
                    faces.Select(f => new KitShot(Plain(body), 20, f.Label) { Face = f.Face }), heads: true);
        }
        finally
        {
            game?.MakeCurrent();
        }
    }

    // One person in a strip: the look, how far it turns from facing the
    // camera (degrees; 90 is side on), its caption, and optionally a clip
    // held at a moment and a face.
    private sealed record KitShot(CharacterLook Look, float Turn, string Label)
    {
        public bool BodyOnly { get; init; }
        public bool RestPose { get; init; }
        public string Clip { get; init; } = FigureClips.Idle;
        public float At { get; init; }
        public Expression? Face { get; init; }
    }

    // People side by side, filmed square on by an orthographic camera from
    // the lens's side of the stage, a touch from above so the meadow is the
    // backdrop. Each strip is cleared after its capture.
    private sealed class KitStrip(ProofRun proof, Node3D studio, Camera3D camera, Vector3 centre, Vector2 toward)
    {
        public async Task Shoot(string shot, float spacing, IEnumerable<KitShot> people, bool heads = false)
        {
            KitShot[] row = people.ToArray();
            Vector2 view = proof.GetViewport().GetVisibleRect().Size;
            float aspect = view.X / view.Y;
            // Square on, a touch from above, so the meadow is the backdrop.
            Vector3 back = new Vector3(toward.X, 0.08f, toward.Y).Normalized();
            Vector3 right = Vector3.Up.Cross(back).Normalized();
            Vector3 up = back.Cross(right).Normalized();
            var spots = new List<Vector3>();
            var bodies = new List<Vector3[]>();
            var figures = new List<CharacterKit.Figure>();
            for (int i = 0; i < row.Length; i++)
            {
                KitShot person = row[i];
                Vector3 at = centre + right * (i - (row.Length - 1) / 2f) * spacing;
                CharacterKit.Figure figure = proof.KitFigure(studio, person.Look, at, toward, person.Turn);
                if (person.BodyOnly) proof.UndressKitStudy(figure);
                figures.Add(figure);
                var skeleton = (Skeleton3D)figure.Root.FindChildren("*", nameof(Skeleton3D), true, false)[0];
                float head = skeleton.GetBoneGlobalRest(skeleton.FindBone("head")).Origin.Y * figure.Root.Scale.Y;
                // Lift each person so their eyes meet the camera, however
                // tall their sliders made them.
                if (heads) figure.Root.Position += Vector3.Up * (KitHeadAim - head - 0.066f);
                if (person.Clip == FigureClips.Sleep)
                {
                    // Sleep's clip is local; production tips the actor's body onto its side.
                    var body = new Node3D { Position = at,
                        Rotation = new Vector3(0, figure.Root.Rotation.Y, MathF.PI / 2) };
                    studio.RemoveChild(figure.Root);
                    studio.AddChild(body);
                    body.AddChild(figure.Root);
                    figure.Root.Position = new Vector3(ActorPerformance.LieLift, 0, 0);
                    figure.Root.Rotation = Vector3.Zero;
                }
                if (person.RestPose)
                {
                    figure.Clips.Stop();
                    skeleton.ResetBonePoses();
                    proof.Require(Enumerable.Range(0, skeleton.GetBoneCount()).All(bone =>
                        skeleton.GetBoneGlobalPose(bone).IsEqualApprox(skeleton.GetBoneGlobalRest(bone))),
                        "Body rest study retained a posed bone.");
                    figure.Ground.Apply();
                }
                else figure.Hold(person.Clip, person.At);
                if (person.Clip == FigureClips.Sleep) figure.Express(new Expression(1, 0, 0));
                if (person.Face is Expression face) figure.Express(face);
                if (!heads)
                {
                    var body = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false)
                        .Cast<MeshInstance3D>().Single(m => m.Name == "Body");
                    bodies.Add(PosedKitMesh(body, skeleton).Posed.Select(p => skeleton.GlobalTransform * p).ToArray());
                }
                spots.Add(at);
            }
            float frame = MathF.Max(heads ? 0.5f : KitWhole, row.Length * spacing / aspect);
            Vector3 aim = centre + Vector3.Up * (heads ? KitHeadAim : frame / 2 - KitFloor);
            float bottom = 0;
            if (!heads)
            {
                var points = bodies.SelectMany(p => p).ToArray();
                float left = points.Min(p => (p - centre).Dot(right)), reach = points.Max(p => (p - centre).Dot(right));
                bottom = points.Min(p => (p - centre).Dot(up));
                float top = points.Max(p => (p - centre).Dot(up));
                frame = MathF.Max(frame, MathF.Max(top - bottom + 0.32f, (reach - left + 0.16f) / aspect));
                aim = centre + right * ((left + reach) / 2) + up * ((bottom + top) / 2 - 0.08f);
            }
            camera.Size = frame;
            // Every orthographic ray must start above the meadow, even in wide sleep strips.
            camera.Position = aim + back * MathF.Max(10, (frame / 2 - aim.Y + 0.2f) / back.Y);
            camera.LookAt(aim);
            for (int i = 0; i < row.Length; i++)
                studio.AddChild(new Label3D
                {
                    Text = row[i].Label, Position = heads
                        ? spots[i] + Vector3.Up * (aim.Y - centre.Y - frame * 0.44f)
                        : centre + right * ((bodies[i].Min(p => (p - centre).Dot(right))
                            + bodies[i].Max(p => (p - centre).Dot(right))) / 2) + up * (bottom - 0.13f),
                    Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, NoDepthTest = true, FontSize = 32,
                    PixelSize = frame / view.Y * 15 / 32, OutlineSize = 8,
                    OutlineModulate = new Color(Palette.World.LabelOutline)
                });
            await proof.DrawFrames(4);
            if (!heads)
            {
                Rect2 bounds = proof.GetViewport().GetVisibleRect().Grow(-8);
                foreach (Vector3[] body in bodies)
                    proof.Require(body.All(p => bounds.HasPoint(camera.UnprojectPosition(p))), $"Kit camera crops a posed body in {shot}.");
            }
            if (!heads)
                for (int i = 0; i < figures.Count; i++)
                {
                    CharacterKit.Figure figure = figures[i];
                    if (figure.Clips.AssignedAnimation != FigureClips.Sleep) proof.ReadKitSoles(figure, row[i].BodyOnly);
                    if (!row[i].BodyOnly && figure.Clips.AssignedAnimation == FigureClips.HugWalk) proof.ReadKitCarryHands(figure);
                    if (!row[i].BodyOnly && (figure.Clips.AssignedAnimation == FigureClips.Walk || figure.Clips.AssignedAnimation == FigureClips.HugWalk))
                        proof.ReadKitApronLayer(figure);
                }
            await proof.Capture(shot);
            proof.Record("character_kit", new { shot, people = row.Length,
                profiles = row.Select(r => new { r.Look.Base, r.Look.Name, r.Look.Outfit, r.Look.Face, r.Look.Sliders,
                    clip = r.RestPose ? "bind-rest" : r.Clip, at = r.At, turn = r.Turn, r.BodyOnly }) });
            ClearStudio(studio);
        }
    }

    private static (Vector3[] Base, Vector3[] Posed) PosedKitMesh(MeshInstance3D mesh, Skeleton3D skeleton)
    {
        using ArrayMesh shaped = mesh.BakeMeshFromCurrentBlendShapeMix();
        Vector3[] vertices = shaped.SurfaceGetArrays(0)[(int)Mesh.ArrayType.Vertex].AsVector3Array();
        var arrays = mesh.Mesh.SurfaceGetArrays(0);
        int[] bones = arrays[(int)Mesh.ArrayType.Bones].AsInt32Array();
        float[] weights = arrays[(int)Mesh.ArrayType.Weights].AsFloat32Array();
        Skin skin = mesh.Skin!;
        var transforms = new Transform3D[skin.GetBindCount()];
        for (int bind = 0; bind < transforms.Length; bind++)
            transforms[bind] = skeleton.GetBoneGlobalPose(CharacterKit.BoundBone(skeleton, skin, bind)) * skin.GetBindPose(bind);
        var posed = new Vector3[vertices.Length];
        for (int i = 0; i < vertices.Length; i++)
            for (int k = 0; k < 4; k++) posed[i] += (transforms[bones[i * 4 + k]] * vertices[i]) * weights[i * 4 + k];
        return (vertices, posed);
    }

    private static (Vector3[] Points, int[] Indices, bool[] Arm) KitTorsoSurface(MeshInstance3D mesh, Skeleton3D skeleton)
    {
        var (_, posed) = PosedKitMesh(mesh, skeleton);
        var arrays = mesh.Mesh.SurfaceGetArrays(0);
        int[] bones = arrays[(int)Mesh.ArrayType.Bones].AsInt32Array();
        float[] weights = arrays[(int)Mesh.ArrayType.Weights].AsFloat32Array();
        bool[] arm = Enumerable.Range(0, posed.Length).Select(i => Enumerable.Range(0, 4).Any(k =>
        {
            string bone = skeleton.GetBoneName(CharacterKit.BoundBone(skeleton, mesh.Skin!, bones[i * 4 + k]));
            return weights[i * 4 + k] > 0.1f && (bone.StartsWith("upperarm_") || bone.StartsWith("lowerarm_"));
        })).ToArray();
        return (posed, arrays[(int)Mesh.ArrayType.Index].AsInt32Array(), arm);
    }

    private static float KitSurfaceFront(Vector3 at, (Vector3[] Points, int[] Indices, bool[] Arm) surface)
    {
        var (posed, indices, arm) = surface;
        float front = float.NegativeInfinity;
        for (int i = 0; i < indices.Length; i += 3)
        {
            int a = indices[i], b = indices[i + 1], c = indices[i + 2];
            if (arm[a] || arm[b] || arm[c]) continue;
            Vector2 edge = new(posed[b].X - posed[a].X, posed[b].Y - posed[a].Y);
            Vector2 side = new(posed[c].X - posed[a].X, posed[c].Y - posed[a].Y);
            Vector2 point = new(at.X - posed[a].X, at.Y - posed[a].Y);
            float area = edge.Cross(side);
            if (Math.Abs(area) < 0.0000001f) continue;
            float u = point.Cross(side) / area, v = edge.Cross(point) / area;
            if (u < 0 || v < 0 || u + v > 1) continue;
            front = MathF.Max(front, posed[a].Z + u * (posed[b].Z - posed[a].Z) + v * (posed[c].Z - posed[a].Z));
        }
        return front;
    }

    private void ReadKitCarryHands(CharacterKit.Figure figure)
    {
        var skeleton = figure.Root.FindChildren("*", nameof(Skeleton3D), true, false).Cast<Skeleton3D>().Single();
        var meshes = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>().ToArray();
        var surfaces = meshes.Where(m => m.Name.ToString() is "Shirt" or "Vest" or "Apron")
            .Select(m => KitTorsoSurface(m, skeleton)).ToArray();
        foreach (string hand in new[] { "hand_l", "hand_r" })
        {
            Vector3 at = skeleton.GetBoneGlobalPose(skeleton.FindBone(hand)).Origin;
            float front = surfaces.Max(surface => KitSurfaceFront(at, surface));
            // A wrist beside the torso has no projected cloth in front of it.
            float? clearance = float.IsFinite(front) ? at.Z - front : null;
            Require(!clearance.HasValue || clearance > 0.008f,
                $"Kit {figure.Look.Name}/{figure.Look.Outfit}/{hand}: carrying wrist penetrates cloth by {-clearance:0.000}.");
            Record("character_kit", new { shot = "carry_contact", figure.Look.Name, figure.Look.Base,
                figure.Look.Outfit, figure.Look.Sliders, hand, clearance, outside_projection = !clearance.HasValue });
        }
    }

    private void ReadKitApronLayer(CharacterKit.Figure figure)
    {
        var meshes = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>().ToArray();
        MeshInstance3D? apron = meshes.SingleOrDefault(m => m.Name == "Apron");
        if (apron is null) return;
        var skeleton = figure.Root.FindChildren("*", nameof(Skeleton3D), true, false).Cast<Skeleton3D>().Single();
        var shirt = KitTorsoSurface(meshes.Single(m => m.Name == "Shirt"), skeleton);
        var (rest, posed) = PosedKitMesh(apron, skeleton);
        int[] indices = apron.Mesh.SurfaceGetArrays(0)[(int)Mesh.ArrayType.Index].AsInt32Array();
        float clearance = float.PositiveInfinity;
        int samples = 0;
        for (int i = 0; i < indices.Length; i += 3)
        {
            int a = indices[i], b = indices[i + 1], c = indices[i + 2];
            if ((rest[b] - rest[a]).Cross(rest[c] - rest[a]).Z <= 0) continue;
            Vector3 at = (posed[a] + posed[b] + posed[c]) / 3;
            float front = KitSurfaceFront(at, shirt);
            if (!float.IsFinite(front)) continue;
            clearance = MathF.Min(clearance, at.Z - front);
            samples++;
        }
        Require(samples > 0, $"Kit {figure.Look.Name}: apron check found no supporting tunic surface.");
        Require(clearance > -0.004f,
            $"Kit {figure.Look.Name}/{figure.Clips.AssignedAnimation}: tunic pierces apron by {-clearance:0.000}.");
        Record("character_kit", new { shot = "apron_layer", figure.Look.Name, figure.Look.Base,
            figure.Look.Sliders, clip = figure.Clips.AssignedAnimation.ToString(), samples, clearance });
    }

    // Re-derive from every posed footwear vertex, independently of the cached
    // footwear inputs used by KitFootContact. Rest joint heights cannot prove this.
    private void ReadKitSoles(CharacterKit.Figure figure, bool bodyOnly = false)
    {
        var skeleton = figure.Root.FindChildren("*", nameof(Skeleton3D), true, false).Cast<Skeleton3D>().Single();
        MeshInstance3D mesh = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false)
            .Cast<MeshInstance3D>().Single(m => bodyOnly ? m.Name == "Body" : m.Name == "Boots" || m.Name == "Shoes");
        var (vertices, posed) = PosedKitMesh(mesh, skeleton);
        float floor = float.PositiveInfinity;
        float restFloor = vertices.Min(v => v.Y);
        Vector3[] sole = vertices.Where(v => v.Y < restFloor + 0.015f).ToArray();
        float back = sole.Min(v => v.Z), reach = sole.Max(v => v.Z) - back;
        float[] contacts = Enumerable.Repeat(float.PositiveInfinity, 4).ToArray();
        Transform3D toWorld = skeleton.GlobalTransform;
        for (int i = 0; i < vertices.Length; i++)
        {
            float height = (toWorld * posed[i]).Y;
            floor = MathF.Min(floor, height);
            if (vertices[i].Y < restFloor + 0.015f)
            {
                int side = vertices[i].X < 0 ? 0 : 2;
                if (vertices[i].Z < back + reach * 0.35f) contacts[side] = MathF.Min(contacts[side], height);
                if (vertices[i].Z > back + reach * 0.65f) contacts[side + 1] = MathF.Min(contacts[side + 1], height);
            }
        }
        Require(Math.Abs(floor) < 0.018f, $"Kit {figure.Look.Name}/{figure.Clips.AssignedAnimation}: posed sole at {floor:0.000}.");
        if (figure.Clips.AssignedAnimation == FigureClips.Idle || figure.Clips.AssignedAnimation == FigureClips.PickUp)
            Require(contacts.All(v => Math.Abs(v) < 0.02f),
                $"Kit {figure.Look.Name}/{figure.Clips.AssignedAnimation}: raised heel or toe [{string.Join(", ", contacts.Select(v => v.ToString("0.000")))}].");
        Record("character_kit", new { shot = "sole_contact", figure.Look.Name,
            clip = figure.Clips.AssignedAnimation.ToString(), floor, heels_and_toes = contacts });
    }

    private void RequireHeldKitContactModes(CharacterLook look)
    {
        CharacterKit.Figure figure = CharacterKit.Build(look.With("Height", -0.5f));
        try
        {
            foreach (string clip in new[] { FigureClips.Run, FigureClips.Sleep, FigureClips.Sprawl })
            {
                figure.Hold(FigureClips.Idle, 0);
                figure.Hold(clip, 0.25f);
                Require(figure.Clips.AssignedAnimation == clip,
                    $"Held kit pose lost its assigned clip {clip} after Pause.");
                Require(figure.Ground.Offset == 0, $"Kit settles the intentionally ungrounded {clip} pose.");
                Record("character_kit", new { shot = "contact_mode", clip, offset = figure.Ground.Offset });
            }
        }
        finally { figure.Root.Free(); }
    }

    // A kit person standing at [at], facing the camera's side of the stage
    // turned by [turn] degrees, wearing exactly what its look asks for.
    private CharacterKit.Figure KitFigure(Node3D studio, CharacterLook look, Vector3 at, Vector2 toward, float turn)
    {
        CharacterKit.Figure figure = CharacterKit.Build(look);
        studio.AddChild(figure.Root);
        figure.Root.Position = at;
        // The kit faces +Z; turn that toward the lens.
        figure.Root.Rotation = new Vector3(0, MathF.Atan2(toward.X, toward.Y) + Mathf.DegToRad(turn), 0);
        var (worn, _) = CharacterKit.Spec.Dress(look);
        var drawn = figure.Root.FindChildren("*", nameof(MeshInstance3D), true, false).Select(n => n.Name.ToString()).ToHashSet();
        Require(drawn.SetEquals(worn),
            $"Look {look.Name} draws [{string.Join(", ", drawn.Order())}], not [{string.Join(", ", worn.Order())}].");
        return figure;
    }

    // A taller body carries its joints with it: the head and knee joints of
    // Height -1, 0 and +1 rise in that order.
    private void RequireJointsFollow(Node3D studio, CharacterLook look)
    {
        float Joint(float height, string bone)
        {
            CharacterKit.Figure figure = CharacterKit.Build(look.With("Height", height));
            studio.AddChild(figure.Root);
            figure.Hold(FigureClips.Idle, 0);
            var skeleton = (Skeleton3D)figure.Root.FindChildren("*", nameof(Skeleton3D), true, false)[0];
            float y = skeleton.GetBoneGlobalPose(skeleton.FindBone(bone)).Origin.Y;
            figure.Root.Free();
            return y;
        }
        foreach (string bone in new[] { "head", "calf_l" })
        {
            float low = Joint(-1, bone), mid = Joint(0, bone), high = Joint(1, bone);
            Require(low < mid && mid < high, $"Joint {bone} does not follow Height: {low:0.000}, {mid:0.000}, {high:0.000}.");
            Require(Math.Abs(Joint(0, bone) - mid) < 0.00001f, $"Joint {bone} leaked a different body's clip offsets.");
            Record("character_kit", new { joint = bone, low, mid, high });
        }
    }

    private static void ClearStudio(Node3D studio)
    {
        foreach (Node child in studio.GetChildren())
            if (child is not Camera3D)
            {
                studio.RemoveChild(child);
                child.QueueFree();
            }
    }
}
