# Character kit

MakeHuman provides the body, morphs, rig and skin weights. Thistletide authors
faces, sculpted hair masses, late-medieval garments and their fitting rules in
`character_kit.spec.json`. Both the generator and the Godot client read it.

The kit remains a candidate behind `TT_KIT_PAWNS=1`. Mechanical checks and
rendered sheets do not grant production art approval.

## Design and saved identity

- Three references: Aldric (rugged ranger), Wren (soft face, bob and travel
  cloak), Bram (mature, heavy worker with an apron and short beard).
- Six short hair silhouettes: textured crop, close crop, swept, side part,
  waves and curls. Bob, long hair, bun and braid work on either base.
- Twelve face recipes: soft, rugged, square, narrow, round and mature on each
  base. Saved face controls layer onto the recipe; race anatomy stays distinct.
- Six body review families: lean, average, stocky, broad, heavy and wiry.
  Live bodies still express their saved stature, mass and frame.
- Apron, cloak, scarf, cap, brimmed hat and facial hair are real independent
  parts. The kit reads the saved appearance projection, never hidden inventory.

`KitLook` translates the committed `HumanAppearance` through the same
`ManagedSession.PresentAppearance` that live pawns use. Detail within the saved
haircut and face family is selected by stable pawn id and authored recipe order.
It remains identical across reloads for the same spec. Changing recipes is an
art revision and may change those presentation details; saved identity controls
and palette indices are preserved.

## Clothing and motion

The setting is pre-firearms, with a rough 1500–1600 village feel: long-sleeved
linen tunics, simple wool or leather jerkins, work aprons, cloaks and leather
footwear. Modern casual tops, jeans and work suits are removed. The `frontier*`
outfit ids identify the existing kit slots, not an American frontier style.

The jerkin uses a continuous panel pattern rather than cut skin. Each clothing
layer is fitted to the smoothed body or the garment below it, preserving its
rest clearance, hems and thickness. An apron or cloak uses both body and tunic
support so the fit remains valid below the tunic hem. Fitting preserves unrelated
face morphs; nose and jaw controls cannot undo a garment's fitted base.
Pairwise body corrections add only the
residual fitting move after both ordinary morphs. `Dress` evaluates their
positive driver products and clamps combined race/body sliders to the built range.
Buttons and buckles keep their dimensions and one bone per rigid piece.
Tunic coverage comes from the same cut as its geometry. Lower panels blend from
the pelvis onto two cloth controls that follow leg flex without anatomical
twist or splay. The same generated clips animate those controls. Hanging hair
is built against the finished wardrobe.
Outfit masks retract the tunic panel covered by an apron, just as legwear
conceals skin and the tunic conceals the trouser waist.
The apron bib shares the supporting tunic's spine weights; its free skirt
changes to the front cloth control below the hip. The Godot matrix measures
posed apron/tunic clearance on all six builds during walking and carrying.
The lower cape follows the waist rather than fitting each row to a leg;
an exported-mesh check rejects neighboring rows stretched into projecting teeth.

Shirt, apron and cloak carry `ClothBack`, `ClothLeft`, `ClothRight` shapes for the
existing `ClothMotion`. Their reach is deliberately small.

The kit carries every clip in `FigureClips`, plus Grip, Shoulder and Hug sockets.
`KitFootContact` reads the cached shaped footwear vertices and settles the model within
the pawn's figure for grounded poses. Run retains its flight phase; Sleep and
Sprawl use the existing recumbent presentation. Horizontal foot planting and
full leg IK still need work. Body settling moves tools and sockets with the
figure, never the simulation position.
Position tracks follow each body's moved joints. Hugging poses hold the arms
forward and lift them on fuller bodies; attachment scales keep tools and loads
in the game's units despite the kit's different authored scale.

## Rebuild and check

From the repo root, with the installed Blender:

```bash
blender --background --threads 2 --python-exit-code 1 \
  --python scripts/asset_pipeline/build_character_kit.py --
python3 scripts/asset_pipeline/test_character_kit_art.py
python3 scripts/asset_pipeline/test_character_kit_retarget.py
scripts/test_entryguard.sh --filter Kit
```

Inputs are pinned CC0 MakeHuman data fetched by `fetch_mpfb2_cc0.py`. Every
rebuild writes its Blender version, input hashes, date, scope and pending owner
approval into `kit_<base>.glb.provenance.json`. The two GLBs and bone manifests
are intentional runtime assets; captures and scratch output stay outside git.

## Review in Godot

```bash
TT_SHOTS=full TT_TIMEOUT=900 TT_PROOF_DIR="$HOME/tmp/agent-tmp/kit-review" \
  bash clients/godot-csharp/run.sh --scenario=character-kit --viewport=1920x1080
dotnet run --project clients/godot-csharp/review -- \
  --proof-dir="$HOME/tmp/agent-tmp/kit-review" --out="$HOME/tmp/agent-tmp/kit-gallery"
```

Start with `kit_heroes_45.png` and `kit_hero_faces.png`, then inspect the four
hair angles, twelve face identities with expressions, and the fit sheets across
six bodies, three outerwear cuts and nine poses. Sleep sheets apply the same
body rotation as production and split the six bodies into readable rows.
`kit_community_30.png` uses
30 seeded Sim identities through the live mapping. `kit_comparison_z*.png`
pairs the existing folk and candidate for the same saved looks at gameplay zoom.
The proof also measures every posed footwear vertex; a rest-bone assertion cannot
hide hovering feet.

The launcher captures off-screen with muted audio. Software GL supports shape
review; hardware lighting, frame pacing and human artistic acceptance require
their own evidence.
