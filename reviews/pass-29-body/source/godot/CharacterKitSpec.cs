using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace Thistletide.Presentation;

// What the character kit offers, read from the same file the kit builder
// builds from (assets/characters/kit/character_kit.spec.json), and what one
// look asks of it: which parts are worn and how far each shape key is
// pushed. Pure C#, so EntryGuard checks it without Godot; CharacterKit.cs
// applies the result to a loaded kit.
public sealed class CharacterKitSpec
{
    public float GameScale { get; }
    public IReadOnlyList<string> Bases { get; }
    public IReadOnlyList<string> Sliders { get; }
    // Part name -> colour channel ("skin", "hair", "shirt", ...). Body is
    // always skin.
    public IReadOnlyDictionary<string, string> PartColours { get; }
    public IReadOnlyDictionary<string, string> DefaultColours { get; }
    public IReadOnlySet<string> Always { get; }
    // Parts drawn with the dark rim: the body and the opaque clothes, not
    // the hair cards or the small face pieces.
    public IReadOnlySet<string> Outlined { get; }
    public IReadOnlyCollection<string> Races => _races.Keys;
    public IReadOnlySet<string> FittedParts => _fittedParts;
    public IReadOnlyList<GarmentCorrection> GarmentCorrectives => _correctives;
    public IReadOnlyCollection<string> Bodies => _bodies.Keys;
    public sealed record GarmentCorrection(string Name, string[] Drivers);

    private readonly Dictionary<string, Dictionary<string, string[]>> _slots;
    private readonly Dictionary<string, RaceTraits> _races;
    private readonly Dictionary<string, Dictionary<string, Dictionary<string, float>>> _faces = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Dictionary<string, float>> _bodies = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string[]> _savedHair = new(StringComparer.Ordinal);
    private readonly HashSet<string> _fittedParts = new(StringComparer.Ordinal);
    private readonly List<GarmentCorrection> _correctives = new();
    private string[] _beards = Array.Empty<string>();

    // What a race adds to every look of that race: slider values, parts
    // (an orc's tusks) and colours (green skin, a vampire's red eyes).
    private sealed record RaceTraits(Dictionary<string, float> Sliders, string[] Parts, Dictionary<string, string> Colours);

    private CharacterKitSpec(float scale, string[] bases, string[] sliders, Dictionary<string, string> colours,
        Dictionary<string, string> defaults, HashSet<string> always, HashSet<string> outlined,
        Dictionary<string, Dictionary<string, string[]>> slots, Dictionary<string, RaceTraits> races)
    {
        GameScale = scale;
        Bases = bases;
        Sliders = sliders;
        PartColours = colours;
        DefaultColours = defaults;
        Always = always;
        Outlined = outlined;
        _slots = slots;
        _races = races;
    }

    public IReadOnlyCollection<string> Choices(string slot) => SlotOf(slot).Keys;
    public IReadOnlyCollection<string> Faces(string body) => _faces[body].Keys;
    public IReadOnlyDictionary<string, float> Face(string body, string name) => _faces[body][name];
    public IReadOnlyDictionary<string, float> Body(string name) => _bodies[name];
    public IReadOnlyList<string> HairFamily(string saved) => _savedHair[saved];

    // These are subdivisions of the saved cut, not a new lifetime identity.
    // Their authored order and the pawn's stable id make reloads reproducible.
    public string HairFor(string saved, ulong id) => _savedHair.TryGetValue(saved, out string[]? family)
        ? family[(int)(Physique.Mix(id) % (ulong)family.Length)]
        : throw new InvalidOperationException($"Unknown hairstyle '{saved}'.");
    public string BeardFor(ulong id) => _beards[(int)(Physique.Mix(id) % (ulong)_beards.Length)];

    public static CharacterKitSpec Parse(string json)
    {
        using var document = JsonDocument.Parse(json);
        JsonElement root = document.RootElement;
        if (root.GetProperty("schema").GetInt32() != 1)
            throw new InvalidOperationException("Unsupported character kit spec version.");
        string[] bases = root.GetProperty("bases").EnumerateObject().Select(p => p.Name).ToArray();
        string[] sliders = root.GetProperty("sliders").EnumerateArray()
            .Select(s => s.GetProperty("name").GetString() ?? throw new InvalidOperationException("Unnamed slider.")).ToArray();
        var colours = new Dictionary<string, string>(StringComparer.Ordinal) { ["Body"] = "skin" };
        var outlined = new HashSet<string>(StringComparer.Ordinal) { "Body" };
        foreach (JsonProperty part in root.GetProperty("parts").EnumerateObject())
        {
            colours[part.Name] = part.Value.GetProperty("colour").GetString()
                ?? throw new InvalidOperationException($"Part {part.Name} has no colour channel.");
            if (part.Value.TryGetProperty("outline", out JsonElement outline) && outline.GetBoolean())
                outlined.Add(part.Name);
        }
        var defaults = Hexes(root.GetProperty("default_colours"));
        foreach (string channel in colours.Values.Distinct())
            if (!defaults.ContainsKey(channel))
                throw new InvalidOperationException($"Colour channel {channel} has no default colour.");
        var always = Names(root.GetProperty("always")).ToHashSet(StringComparer.Ordinal);
        var slots = new Dictionary<string, Dictionary<string, string[]>>(StringComparer.Ordinal);
        foreach (JsonProperty slot in root.GetProperty("slots").EnumerateObject())
            slots[slot.Name] = slot.Value.EnumerateObject().ToDictionary(c => c.Name, c => Names(c.Value), StringComparer.Ordinal);
        var races = new Dictionary<string, RaceTraits>(StringComparer.Ordinal);
        foreach (JsonProperty race in root.GetProperty("races").EnumerateObject())
            races[race.Name] = new RaceTraits(Values(race.Value.GetProperty("sliders")), Names(race.Value.GetProperty("parts")),
                Hexes(race.Value.GetProperty("colours")));
        var spec = new CharacterKitSpec(root.GetProperty("game_scale").GetSingle(), bases, sliders, colours, defaults,
            always, outlined, slots, races);
        foreach (JsonProperty body in root.GetProperty("face_archetypes").EnumerateObject())
            spec._faces[body.Name] = body.Value.EnumerateObject().ToDictionary(p => p.Name, p => Values(p.Value), StringComparer.Ordinal);
        foreach (string body in bases)
        {
            if (!spec._faces.TryGetValue(body, out var recipes) || recipes.Count == 0)
                throw new InvalidOperationException($"Character kit has no face recipes for {body}.");
            foreach (var recipe in recipes.Values) spec.CheckSliders(recipe);
        }
        foreach (JsonProperty body in root.GetProperty("body_archetypes").EnumerateObject())
        {
            var recipe = Values(body.Value);
            spec.CheckSliders(recipe);
            spec._bodies[body.Name] = recipe;
        }
        foreach (JsonProperty hair in root.GetProperty("saved_hair_families").EnumerateObject())
        {
            string[] family = Names(hair.Value);
            if (family.Length == 0) throw new InvalidOperationException($"Empty hairstyle family {hair.Name}.");
            foreach (string choice in family) _ = spec.Slot("hair", choice);
            spec._savedHair[hair.Name] = family;
        }
        spec._beards = Names(root.GetProperty("saved_beard_family"));
        if (spec._beards.Length == 0) throw new InvalidOperationException("Empty beard family.");
        foreach (string beard in spec._beards) _ = spec.Slot("beard", beard);
        foreach (JsonProperty part in root.GetProperty("parts").EnumerateObject())
            if (part.Value.TryGetProperty("fit", out JsonElement fit))
            {
                string[] supports = Names(fit.GetProperty("under"));
                if (supports.Length == 0 || supports.Distinct().Count() != supports.Length
                    || supports.Any(s => s == part.Name || !colours.ContainsKey(s)))
                    throw new InvalidOperationException($"Part {part.Name} has invalid supporting layers [{string.Join(", ", supports)}].");
                spec._fittedParts.Add(part.Name);
            }
        foreach (JsonElement correction in root.GetProperty("garment_correctives").EnumerateArray())
        {
            string name = correction.GetProperty("name").GetString()!;
            string[] drivers = Names(correction.GetProperty("drivers"));
            if (drivers.Length != 2 || drivers.Distinct().Count() != 2
                || drivers.Any(d => d.Length < 2 || d[^1] is not ('+' or '-') || !sliders.Contains(d[..^1])))
                throw new InvalidOperationException($"Invalid garment drivers for {name}.");
            spec._correctives.Add(new GarmentCorrection(name, drivers));
        }
        // Every name a look can reach must be a part the kit builds.
        foreach (string part in always.Concat(slots.Values.SelectMany(s => s.Values.SelectMany(p => p)))
                     .Concat(races.Values.SelectMany(r => r.Parts)))
            if (!colours.ContainsKey(part))
                throw new InvalidOperationException($"Character kit names unknown part {part}.");
        foreach (RaceTraits race in races.Values)
        {
            spec.CheckSliders(race.Sliders);
            spec.CheckChannels(race.Colours);
        }
        return spec;
    }

    // The parts one look wears and every shape key value it sets. Unknown
    // names fail: a look naming a slider or style the kit lacks is a broken
    // look, not a default.
    public (IReadOnlySet<string> Worn, IReadOnlyDictionary<string, float> Shapes) Dress(CharacterLook look)
    {
        if (!Bases.Contains(look.Base)) throw new InvalidOperationException($"Look {look.Name}: no base '{look.Base}'.");
        RaceTraits race = RaceOf(look);
        CheckSliders(look.Sliders);
        CheckChannels(look.Colours);
        var worn = new HashSet<string>(Always, StringComparer.Ordinal);
        worn.UnionWith(Slot("hair", look.Hair));
        worn.UnionWith(Slot("outfit", look.Outfit));
        worn.UnionWith(Slot("headwear", look.Headwear));
        worn.UnionWith(Slot("beard", look.Beard));
        worn.UnionWith(Slot("neckwear", look.Neckwear));
        worn.UnionWith(race.Parts);
        var values = new Dictionary<string, float>(race.Sliders, StringComparer.Ordinal);
        if (look.Face != "none")
            foreach ((string slider, float value) in Face(look.Base, look.Face))
                values[slider] = values.GetValueOrDefault(slider) + value;
        foreach ((string slider, float value) in look.Sliders)
            values[slider] = values.GetValueOrDefault(slider) + value;
        var shapes = new Dictionary<string, float>(StringComparer.Ordinal);
        foreach ((string slider, float value) in values)
            if (value != 0) shapes[slider + (value > 0 ? "+" : "-")] = Math.Abs(Math.Clamp(value, -1f, 1f));
        foreach (GarmentCorrection correction in _correctives)
        {
            float weight = correction.Drivers.Aggregate(1f, (v, driver) => v * shapes.GetValueOrDefault(driver));
            if (weight > 0) shapes[correction.Name] = weight;
        }
        shapes["Hide." + look.Outfit] = 1;
        return (worn, shapes);
    }

    public IEnumerable<string> Slot(string slot, string choice) =>
        SlotOf(slot).TryGetValue(choice, out string[]? parts)
            ? parts : throw new InvalidOperationException($"Character kit {slot} has no choice '{choice}'.");

    // A part's colour (hex): the look's own for its channel, else its
    // race's, else the kit default.
    public string Colour(CharacterLook look, string part)
    {
        string channel = PartColours[part];
        if (look.Colours.TryGetValue(channel, out string? hex)) return hex;
        return RaceOf(look).Colours.TryGetValue(channel, out hex) ? hex : DefaultColours[channel];
    }

    private RaceTraits RaceOf(CharacterLook look) => _races.TryGetValue(look.Race, out RaceTraits? race)
        ? race : throw new InvalidOperationException($"Look {look.Name}: no race '{look.Race}'.");

    private Dictionary<string, string[]> SlotOf(string slot) =>
        _slots.TryGetValue(slot, out var choices) ? choices : throw new InvalidOperationException($"Character kit has no slot '{slot}'.");

    private void CheckSliders(IReadOnlyDictionary<string, float> values)
    {
        foreach (string slider in values.Keys)
            if (!Sliders.Contains(slider)) throw new InvalidOperationException($"Character kit has no slider '{slider}'.");
    }

    private void CheckChannels(IReadOnlyDictionary<string, string> colours)
    {
        foreach (string channel in colours.Keys)
            if (!DefaultColours.ContainsKey(channel)) throw new InvalidOperationException($"Character kit has no colour channel '{channel}'.");
    }

    internal static Dictionary<string, string> Hexes(JsonElement map) => map.EnumerateObject().ToDictionary(p => p.Name,
        p => p.Value.GetString() is { Length: 6 } hex ? hex : throw new InvalidOperationException($"Colour {p.Name} is not a 6-digit hex."),
        StringComparer.Ordinal);

    internal static string[] Names(JsonElement array) => array.EnumerateArray()
        .Select(v => v.GetString() ?? throw new InvalidOperationException("Null name in character kit.")).ToArray();

    internal static Dictionary<string, float> Values(JsonElement map) =>
        map.EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetSingle(), StringComparer.Ordinal);
}

// One authored person: which base, race and styles, slider values on top of
// the race's, and colours by channel. Stored as JSON under
// assets/characters/kit/looks/.
public sealed record CharacterLook(string Name, string Base, string Race, string Hair, string Outfit,
    IReadOnlyDictionary<string, float> Sliders, IReadOnlyDictionary<string, string> Colours)
{
    public string Headwear { get; init; } = "none";
    public string Beard { get; init; } = "none";
    public string Neckwear { get; init; } = "none";
    public string Face { get; init; } = "none";
    public static CharacterLook Parse(string json)
    {
        using var document = JsonDocument.Parse(json);
        JsonElement root = document.RootElement;
        string Text(string key) => root.GetProperty(key).GetString() ?? throw new InvalidOperationException($"Look has no {key}.");
        return new CharacterLook(Text("name"), Text("base"), Text("race"), Text("hair"), Text("outfit"),
            root.TryGetProperty("sliders", out JsonElement sliders)
                ? CharacterKitSpec.Values(sliders) : new Dictionary<string, float>(StringComparer.Ordinal),
            root.TryGetProperty("colours", out JsonElement colours)
                ? CharacterKitSpec.Hexes(colours) : new Dictionary<string, string>(StringComparer.Ordinal))
        {
            Headwear = root.TryGetProperty("headwear", out JsonElement headwear) ? headwear.GetString()! : "none",
            Beard = root.TryGetProperty("beard", out JsonElement beard) ? beard.GetString()! : "none",
            Neckwear = root.TryGetProperty("neckwear", out JsonElement neckwear) ? neckwear.GetString()! : "none",
            Face = root.TryGetProperty("face", out JsonElement face) ? face.GetString()! : "none"
        };
    }

    public CharacterLook With(string slider, float value)
    {
        var sliders = new Dictionary<string, float>(Sliders, StringComparer.Ordinal) { [slider] = value };
        return this with { Sliders = sliders };
    }
}
