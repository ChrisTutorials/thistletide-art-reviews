using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Godot;

namespace Thistletide.Presentation;

// The character kit in the game: the CC0 MakeHuman bodies that
// scripts/asset_pipeline/build_character_kit.py writes to
// assets/characters/kit/kit_<base>.glb, turned into one person per
// CharacterLook (assets/characters/kit/looks/*.json).
//
// A look picks the base (male or female), race, hair and outfit, sets
// sliders and colours. Build applies it to a copy of the kit:
//
// * worn parts stay, every other part is removed;
// * every slider is a pair of blend shapes ("Height+", "Height-") on the
//   body and on every part, so clothes and hair change shape with the body;
// * the skeleton's joints move with the sliders (kit_<base>.bones.json), so
//   a longer leg bends at its own knee, and each figure gets its own skin
//   binding for its own joints;
// * the outfit's "Hide.<outfit>" shape pulls covered skin under the cloth;
// * colours tint each part by channel (skin, hair, shirt, ...).
//
// Presentation only: nothing here decides what a person does or wears in the
// game. The models are read at runtime with GltfDocument, not imported, and a
// kit that does not match the spec fails loudly when it is loaded.
public static class CharacterKit
{
    private const string Folder = "assets/characters/kit";
    private const string SpecAsset = Folder + "/character_kit.spec.json";
    // Clips every kit carries. They only turn bones, so they fit every body
    // the sliders make.
    private static readonly string[] Clips = { FigureClips.Idle, FigureClips.Walk };
    private static readonly string[] Expressions = { "Blink", "Smile", "MouthOpen" };
    // The dark rim, in screen pixels (shaders/creature_outline.gdshader).
    private const float OutlinePixels = 1.5f;

    // One built person: its root (kit scale, facing +Z), clips and face.
    public sealed class Figure
    {
        public required Node3D Root { get; init; }
        public required AnimationPlayer Clips { get; init; }
        public required CharacterLook Look { get; init; }
        public required KitFootContact Ground { get; init; }
        internal List<(MeshInstance3D Mesh, int Blink, int Smile, int Open)> Face { get; } = new();

        public void Express(Expression look)
        {
            foreach (var (mesh, blink, smile, open) in Face)
            {
                mesh.SetBlendShapeValue(blink, look.Blink);
                mesh.SetBlendShapeValue(smile, look.Smile);
                mesh.SetBlendShapeValue(open, look.MouthOpen);
            }
        }

        // Holds the clip still at [seconds] in, for a still frame.
        public void Hold(string clip, float seconds)
        {
            Clips.Play(clip);
            Clips.Seek(seconds, true);
            Clips.Pause();
            Ground.Apply();
        }
    }

    // One base as loaded: the scene every figure copies, and how far each
    // slider end moves each joint (glTF axes, the skeleton's own space).
    private sealed record Kit(Node3D Scene, Dictionary<string, Vector3[]> JointKeys);

    private static CharacterKitSpec? _spec;
    private static readonly Dictionary<string, Kit> Kits = new(StringComparer.Ordinal);
    private static readonly Dictionary<(string, Texture2D?, bool, bool, bool, bool), StandardMaterial3D> Materials = new();
    private static readonly Dictionary<string, ShaderMaterial> PaintedBodies = new(StringComparer.Ordinal);
    private static ShaderMaterial? _paintedBody;
    private static ImageTexture? _bodyPigment;
    public static bool IllustratedBody => System.Environment.GetEnvironmentVariable("TT_KIT_BODY_FINISH") == "painted";
    private static ShaderMaterial? _outline;
    private static StandardMaterial3D? _surface;
    private static StandardMaterial3D? _stubble;

    public static CharacterKitSpec Spec => _spec ??= CharacterKitSpec.Parse(File.ReadAllText(AssetPath(SpecAsset)));

    // An authored look by file name (looks/<name>.json).
    public static CharacterLook Look(string name) =>
        CharacterLook.Parse(File.ReadAllText(AssetPath($"{Folder}/looks/{name}.json")));

    public static Figure Build(CharacterLook look)
    {
        CharacterKitSpec spec = Spec;
        var (worn, shapes) = spec.Dress(look);
        Kit kit = Load(look.Base);
        var model = (Node3D)kit.Scene.Duplicate();
        model.Name = "Model";
        var root = new Node3D();
        root.AddChild(model);
        root.Name = look.Name;
        root.Scale = Vector3.One * spec.GameScale;
        var ground = new KitFootContact();
        root.AddChild(ground);
        var figure = new Figure { Root = root, Clips = One<AnimationPlayer>(root), Look = look, Ground = ground };
        var meshes = new List<MeshInstance3D>();
        foreach (MeshInstance3D mesh in root.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>())
        {
            string part = mesh.Name;
            if (!worn.Contains(part))
            {
                mesh.GetParent().RemoveChild(mesh);
                mesh.Free();
                continue;
            }
            // Load checked sliders and required outfit masks; other parts omit those masks.
            foreach ((string key, float value) in shapes)
                if (mesh.FindBlendShapeByName(key) is int index and >= 0) mesh.SetBlendShapeValue(index, value);
            mesh.MaterialOverride = Material(spec.Colour(look, part), mesh, spec.Outlined.Contains(part));
            if (mesh.FindBlendShapeByName(Expressions[0]) >= 0)
                figure.Face.Add((mesh, mesh.FindBlendShapeByName("Blink"), mesh.FindBlendShapeByName("Smile"),
                    mesh.FindBlendShapeByName("MouthOpen")));
            meshes.Add(mesh);
        }
        PlaceJoints(One<Skeleton3D>(root), figure.Clips, kit, shapes, meshes);
        MeshInstance3D footwear = meshes.Single(m => m.Name == (worn.Contains("Boots") ? "Boots" : "Shoes"));
        ground.Bind(One<Skeleton3D>(root), figure.Clips, model, footwear);
        figure.Clips.Play(FigureClips.Idle);
        return figure;
    }

    // Moves each joint by the sliders, keeping its rest orientation, then
    // binds this figure's own copy of the skin to the moved joints. The
    // blend shapes already put the skin where the moved joints expect it,
    // so at rest nothing moves; posed, each limb turns about its own joint.
    private static void PlaceJoints(Skeleton3D skeleton, AnimationPlayer clips, Kit kit, IReadOnlyDictionary<string, float> shapes,
        IEnumerable<MeshInstance3D> meshes)
    {
        int count = skeleton.GetBoneCount();
        var before = new Transform3D[count];
        var after = new Transform3D[count];
        for (int bone = 0; bone < count; bone++)
        {
            before[bone] = skeleton.GetBoneGlobalRest(bone);
            Vector3 head = before[bone].Origin;
            foreach ((string key, float value) in shapes)
                if (kit.JointKeys.TryGetValue(key, out Vector3[]? moves)) head += moves[bone] * value;
            after[bone] = new Transform3D(before[bone].Basis, head);
        }
        var shifts = new Vector3[count];
        for (int bone = 0; bone < count; bone++)
        {
            int parent = skeleton.GetBoneParent(bone);
            Transform3D rest = parent < 0 ? after[bone] : after[parent].AffineInverse() * after[bone];
            shifts[bone] = rest.Origin - skeleton.GetBoneRest(bone).Origin;
            skeleton.SetBoneRest(bone, rest);
        }
        // Imported position tracks are absolute local positions. They must
        // move with the new rests, or they undo the body's joint morphs.
        foreach (StringName name in clips.GetAnimationLibraryList())
        {
            AnimationLibrary shared = clips.GetAnimationLibrary(name);
            var library = new AnimationLibrary();
            foreach (StringName action in shared.GetAnimationList())
            {
                var animation = (Animation)shared.GetAnimation(action).Duplicate(true);
                float fullness = MathF.Max(shapes.GetValueOrDefault("Weight+"), shapes.GetValueOrDefault("Waist+"));
                for (int track = 0; track < animation.GetTrackCount(); track++)
                {
                    NodePath path = animation.TrackGetPath(track);
                    int bone = path.GetSubNameCount() == 1 ? skeleton.FindBone(path.GetSubName(0)) : -1;
                    if (animation.TrackGetType(track) == Animation.TrackType.Rotation3D
                        && (action.ToString() is FigureClips.HugIdle or FigureClips.HugWalk)
                        && bone >= 0 && (skeleton.GetBoneName(bone).ToString() is "upperarm_l" or "upperarm_r"))
                    {
                        // The kit's longer arms hold a load forward; fuller bodies hold it higher.
                        Vector3 axis = before[skeleton.GetBoneParent(bone)].Basis.Inverse() * Vector3.Right;
                        var turn = new Quaternion(axis.Normalized(), Mathf.DegToRad(-20 - 20 * fullness));
                        for (int key = 0; key < animation.TrackGetKeyCount(track); key++)
                            animation.TrackSetKeyValue(track, key, turn * animation.TrackGetKeyValue(track, key).AsQuaternion());
                    }
                    if (animation.TrackGetType(track) != Animation.TrackType.Position3D) continue;
                    if (bone < 0) throw new InvalidOperationException($"Kit position track {path} does not name a bone.");
                    for (int key = 0; key < animation.TrackGetKeyCount(track); key++)
                        animation.TrackSetKeyValue(track, key, animation.TrackGetKeyValue(track, key).AsVector3() + shifts[bone]);
                }
                if (library.AddAnimation(action, animation) != Error.Ok)
                    throw new InvalidOperationException($"Cannot bind shaped kit clip {action}.");
            }
            clips.RemoveAnimationLibrary(name);
            if (clips.AddAnimationLibrary(name, library) != Error.Ok)
                throw new InvalidOperationException($"Cannot bind shaped kit animation library {name}.");
        }
        skeleton.ResetBonePoses();
        var own = new Dictionary<Skin, Skin>();
        foreach (MeshInstance3D mesh in meshes)
        {
            Skin shared = mesh.Skin ?? throw new InvalidOperationException($"Kit part {mesh.Name} has no skin.");
            if (!own.TryGetValue(shared, out Skin? skin))
            {
                skin = (Skin)shared.Duplicate();
                for (int bind = 0; bind < skin.GetBindCount(); bind++)
                {
                    int bone = BoundBone(skeleton, skin, bind);
                    skin.SetBindPose(bind, after[bone].AffineInverse() * before[bone] * shared.GetBindPose(bind));
                }
                own.Add(shared, skin);
            }
            mesh.Skin = skin;
        }
    }

    internal static int BoundBone(Skeleton3D skeleton, Skin skin, int bind)
    {
        string name = skin.GetBindName(bind);
        int bone = name.Length > 0 ? skeleton.FindBone(name) : skin.GetBindBone(bind);
        if (bone < 0) throw new InvalidOperationException($"Kit skin binds unknown bone '{name}'.");
        return bone;
    }

    // A part's look: the toon shading the folk use, tinted by its colour
    // channel. A part with a texture keeps it (grey detail the tint colours,
    // or cut-out hair cards); the irises carry their dark rim and pupil as
    // vertex shade. The rim line goes on the body and opaque clothes only.
    private static Godot.Material Material(string hex, MeshInstance3D mesh, bool outlined)
    {
        if (mesh.Name == "Body" && IllustratedBody)
        {
            if ((((ArrayMesh)mesh.Mesh).SurfaceGetFormat(0) & Mesh.ArrayFormat.FormatTexUV2) == 0)
                throw new InvalidOperationException("Body has no anatomical paint coordinates; rebuild the kit.");
            if (PaintedBodies.TryGetValue(hex, out ShaderMaterial? body)) return body;
            _paintedBody ??= GD.Load<ShaderMaterial>("res://Render/CharacterBodyPainted.tres")
                ?? throw new InvalidOperationException("Missing CharacterBodyPainted.tres.");
            body = (ShaderMaterial)_paintedBody.Duplicate();
            if (_bodyPigment is null)
            {
                using Image image = Image.LoadFromFile(AssetPath($"{Folder}/body_brush_pigment-v1.png"));
                if (image.IsEmpty()) throw new InvalidOperationException("Missing body brush pigment bitmap.");
                image.GenerateMipmaps();
                _bodyPigment = ImageTexture.CreateFromImage(image);
            }
            body.SetShaderParameter("brush_pigment", _bodyPigment);
            body.SetShaderParameter("skin_colour", new Color(hex));
            PaintedBodies.Add(hex, body);
            return body;
        }
        var imported = mesh.Mesh.SurfaceGetMaterial(0) as BaseMaterial3D;
        Texture2D? texture = imported?.AlbedoTexture;
        bool cutout = imported is not null && imported.Transparency != BaseMaterial3D.TransparencyEnum.Disabled;
        bool shaded = (((ArrayMesh)mesh.Mesh).SurfaceGetFormat(0) & Mesh.ArrayFormat.FormatColor) != 0;
        bool stubble = mesh.Name == "BeardStubble";
        var key = (hex, texture, cutout, shaded, outlined, stubble);
        if (Materials.TryGetValue(key, out StandardMaterial3D? material)) return material;
        _surface ??= GD.Load<StandardMaterial3D>("res://Render/CharacterKitSurface.tres")
            ?? throw new InvalidOperationException("Missing Render/CharacterKitSurface.tres.");
        _stubble ??= GD.Load<StandardMaterial3D>("res://Render/CharacterKitStubble.tres")
            ?? throw new InvalidOperationException("Missing Render/CharacterKitStubble.tres.");
        material = (StandardMaterial3D)(stubble ? _stubble : _surface).Duplicate();
        Color tint = new Color(hex);
        tint.A = material.AlbedoColor.A;
        material.AlbedoColor = tint;
        material.AlbedoTexture = texture;
        material.VertexColorUseAsAlbedo = shaded;
        if (cutout)
        {
            // Hair, brows and lashes are cards: cut out, seen from both
            // sides, and matte, or dark hair glints gold at its edges.
            material.Transparency = BaseMaterial3D.TransparencyEnum.AlphaScissor;
            material.AlphaScissorThreshold = 0.5f;
            material.CullMode = BaseMaterial3D.CullModeEnum.Disabled;
            material.RimEnabled = false;
            material.SpecularMode = BaseMaterial3D.SpecularModeEnum.Disabled;
        }
        if (outlined) material.NextPass = Outline();
        Materials.Add(key, material);
        return material;
    }

    private static ShaderMaterial Outline()
    {
        if (_outline is not null) return _outline;
        _outline = new ShaderMaterial
        {
            Shader = GD.Load<Shader>("res://shaders/creature_outline.gdshader")
                ?? throw new InvalidOperationException("res://shaders/creature_outline.gdshader is missing.")
        };
        _outline.SetShaderParameter("width", OutlinePixels);
        // Kit parts carry no vertex colour: the line is the ink alone.
        _outline.SetShaderParameter("ink_mix", 1f);
        var ink = new Color(Palette.World.Ink);
        _outline.SetShaderParameter("ink", new Vector3(ink.R, ink.G, ink.B));
        return _outline;
    }

    // The base's kit, read once. Everything a look can ask for is checked
    // here, so a kit rebuilt without a part, a slider key, a hide key or a
    // clip fails when it loads, not as a person drawn wrong.
    private static Kit Load(string name)
    {
        if (Kits.TryGetValue(name, out Kit? known)) return known;
        CharacterKitSpec spec = Spec;
        string path = AssetPath($"{Folder}/kit_{name}.glb");
        var document = new GltfDocument();
        var state = new GltfState();
        Error error = document.AppendFromFile(path, state);
        if (error != Error.Ok) throw new InvalidOperationException($"Could not load {path}: {error}.");
        var scene = (Node3D)document.GenerateScene(state);
        try
        {
            var meshes = scene.FindChildren("*", nameof(MeshInstance3D), true, false).Cast<MeshInstance3D>()
                .ToDictionary(mesh => mesh.Name.ToString(), StringComparer.Ordinal);
            foreach (string part in spec.PartColours.Keys)
            {
                if (!meshes.TryGetValue(part, out MeshInstance3D? mesh))
                    throw new InvalidOperationException($"{path} has no part {part}.");
                if (mesh.Mesh.GetSurfaceCount() != 1)
                    throw new InvalidOperationException($"{path} part {part} has {mesh.Mesh.GetSurfaceCount()} surfaces, not one.");
                foreach (string slider in spec.Sliders)
                    foreach (string end in new[] { "+", "-" })
                        if (mesh.FindBlendShapeByName(slider + end) < 0)
                            throw new InvalidOperationException($"{path} part {part} lacks slider shape {slider}{end}.");
                if (mesh.FindBlendShapeByName(Expressions[0]) >= 0 && Expressions.Any(e => mesh.FindBlendShapeByName(e) < 0))
                    throw new InvalidOperationException($"{path} part {part} has some face shapes but not all.");
                if (spec.FittedParts.Contains(part))
                    foreach (CharacterKitSpec.GarmentCorrection correction in spec.GarmentCorrectives)
                        if (mesh.FindBlendShapeByName(correction.Name) < 0)
                            throw new InvalidOperationException($"{path} part {part} lacks garment correction {correction.Name}.");
            }
            foreach (string outfit in spec.Choices("outfit"))
            {
                var parts = spec.Slot("outfit", outfit).ToHashSet();
                var masked = new List<string> { "Body" };
                if (parts.Contains("Shirt") && parts.Contains("Trousers")) masked.Add("Trousers");
                if (parts.Contains("Shirt") && parts.Contains("Apron")) masked.Add("Shirt");
                foreach (string part in masked)
                    if (meshes[part].FindBlendShapeByName("Hide." + outfit) < 0)
                        throw new InvalidOperationException($"{path} {part} lacks Hide.{outfit}.");
            }
            AnimationPlayer animator = One<AnimationPlayer>(scene);
            foreach (string clip in Clips)
            {
                if (!animator.HasAnimation(clip)) throw new InvalidOperationException($"{path} lacks clip {clip}.");
                animator.GetAnimation(clip).LoopMode = Animation.LoopModeEnum.Linear;
            }
            var kit = new Kit(scene, JointKeys(name, One<Skeleton3D>(scene), spec));
            Kits.Add(name, kit);
            return kit;
        }
        catch
        {
            scene.Free();
            throw;
        }
    }

    // kit_<base>.bones.json: the rig's bone names, their rest heads and how
    // far each slider end moves each head. Its rest heads must be this
    // skeleton's, or the moves belong to some other build of the kit.
    private static Dictionary<string, Vector3[]> JointKeys(string name, Skeleton3D skeleton, CharacterKitSpec spec)
    {
        string path = AssetPath($"{Folder}/kit_{name}.bones.json");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
        JsonElement root = document.RootElement;
        string[] bones = CharacterKitSpec.Names(root.GetProperty("bones"));
        if (bones.Length != skeleton.GetBoneCount())
            throw new InvalidOperationException($"{path} names {bones.Length} bones; the skeleton has {skeleton.GetBoneCount()}.");
        // Manifest row -> skeleton bone.
        int[] order = bones.Select(bone => skeleton.FindBone(bone) is int i and >= 0
            ? i : throw new InvalidOperationException($"{path} names bone {bone} the skeleton lacks.")).ToArray();
        Vector3[] Rows(JsonElement rows)
        {
            var moves = new Vector3[bones.Length];
            int row = 0;
            foreach (JsonElement p in rows.EnumerateArray())
                moves[order[row++]] = new Vector3(p[0].GetSingle(), p[1].GetSingle(), p[2].GetSingle());
            if (row != bones.Length) throw new InvalidOperationException($"{path} has a row count unlike its bone count.");
            return moves;
        }
        Vector3[] heads = Rows(root.GetProperty("rest_heads"));
        for (int bone = 0; bone < heads.Length; bone++)
            if (heads[bone].DistanceTo(skeleton.GetBoneGlobalRest(bone).Origin) > 0.001f)
                throw new InvalidOperationException(
                    $"{path} puts {skeleton.GetBoneName(bone)} at {heads[bone]}; the kit's skeleton has it at {skeleton.GetBoneGlobalRest(bone).Origin}.");
        var keys = new Dictionary<string, Vector3[]>(StringComparer.Ordinal);
        foreach (JsonProperty key in root.GetProperty("keys").EnumerateObject())
            keys[key.Name] = Rows(key.Value);
        foreach (string slider in spec.Sliders)
            foreach (string end in new[] { "+", "-" })
                if (!keys.ContainsKey(slider + end))
                    throw new InvalidOperationException($"{path} has no joint moves for {slider}{end}.");
        return keys;
    }

    // Frees the loaded kits, so their meshes, skins and textures do not
    // outlive the renderer. Whoever builds people calls it when they go
    // (today only the character-kit proof scenario).
    public static void Release()
    {
        foreach (Kit kit in Kits.Values) kit.Scene.Free();
        Kits.Clear();
        Materials.Clear();
        PaintedBodies.Clear();
        _bodyPigment?.Dispose();
        _bodyPigment = null;
    }

    private static string AssetPath(string asset) =>
        Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "..", "..", asset));

    private static T One<T>(Node root) where T : Node
    {
        Godot.Collections.Array<Node> found = root.FindChildren("*", typeof(T).Name, true, false);
        if (found.Count != 1)
            throw new InvalidOperationException($"A character kit holds {found.Count} {typeof(T).Name} nodes, not one.");
        return (T)found[0];
    }
}
