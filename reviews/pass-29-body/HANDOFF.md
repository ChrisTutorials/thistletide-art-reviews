# Thistletide body-first handoff — 2026-10-12

## 1. Current direction and ownership

The latest owner instruction supersedes the outfit-first reset: make the **unclothed adult bodies** appealing, believable and dimensional in the illustrated/painterly Weathered Folklore style. **Clothing, extra face recipes, hairstyle expansion, procedural population expansion and other visual work remain paused until explicit owner BODY PASS.** No production-default promotion has been approved.

Read updated direction in draft #4447 (`docs/visual/PAINTERLY-CHARACTER-RESET.md`), WEATHERED-FOLKLORE.md, WEATHERED-FOLKLORE-AB.md and issues #1946/#4264/#4268/#4269/#4270/#4267. Main already includes #4413/#4426/#4428; do not redo those. Keep MakeHuman -> Blender -> GLB -> Godot C#, existing saves/rig/equipment/morphs and TT_KIT_PAWNS=1.

- Own worktree: `/home/chris/gamedev/tt-character-art-wt`. Do not touch another session's original `/home/chris/gamedev/thistletide-gd`.
- Branch: `art/painterly-body-first-20261012`. Last pushed verified source: `ae29a2ed5499ce12a5fcbf559f4c78436554889b`. Parent main: `3e089e5ee`; last fetch found no newer main.
- Game draft: https://github.com/ChrisTutorials/thistletide-gd/pull/4453
- Earlier clothing experiment: https://github.com/ChrisTutorials/thistletide-gd/pull/4450 — pushed and paused, owner rejected pass28 as insufficiently different. Do not cherry-pick its rejected wardrobe polish into this body study.
- **During handoff, additional uncommitted edits appeared in this worktree. They are not part of the verified source. Reviewer C confirms they are not theirs. Ownership is unknown; leave them intact.** Observed: CharacterKit.cs, body shader, build_character_kit.py, kit_body_paint.py, test_kit_body_paint.py, new kit_shoulder.py/test_kit_shoulder.py, and regenerated male GLB/provenance. The changes include shoulder-weight smoothing and restored Body outline. Do not assume those changes passed or discard them; identify the active writer before continuing here.

## 2. Changed in the pushed body pass

- Existing character-kit proof now has `TT_KIT_BODY_REVIEW=1`. It removes clothing in the proof only, resets Body Hide.* keys and uses the real Body mesh for foot/contact measurements. Saved/equipped appearance is untouched. Two authored adult identities, Aldric/Wren, are staged; this is not autonomous Sim footage or a production nudity mode.
- Captures gameplay z9 first, day/dusk, closer game camera, diagnostic front/quarter/profile/back, actual bind rest, held Walk/PickUp, plus six existing physiques on each base under Idle/Walk/PickUp. Actual bind rest uses ResetBonePoses and checks global pose against global rest; local identity quaternions were an invalid earlier assumption.
- Adult proportions: house HeadSize .58, Muscle .25, Chest .12, TorsoLength .40, LegLength -.40, ArmLength -.12, NeckLength .08; female HeadSize .58 override. Baked bases measure male 6.46/female 6.30 heads tall. Detailed face recipes/features and hair geometry remain frozen.
- **Actual shoulder root cause fixed in kit_retarget.py:** shortest direction alignment was carrying the folk rig's standing roll into MakeHuman. Exported male upper-arm Idle twist measured 118.515° before correction. Preserve the target standing roll after carrying source direction; new Idle upper-arm twist is below 1°, without changing limb directions. This removed the visible shoulder shelves. A new real-GLB regression failed before and passes after. The speculative clavicle-lowering adjustment was removed.
- Body-only CharacterBodyPainted spatial shader uses original geometry normals, saved skin tint, original face vertex paint, anatomical UV2 tone/warmth and actual scene LIGHT/ATTENUATION. Other materials remain their existing families.
- One shared AI-generated neutral pigment PNG shapes soft light-value transitions. An albedo-wide experiment looked mottled and was rejected; the chosen C-brush-light confines it to light transitions. The image has exact prompt/hash/provenance, is loaded with Image.LoadFromFile through the existing kit runtime asset path, and gets shared mipmaps. Missing bitmap fails clearly. An unsupported hint/editor-import dependency in the first texture attempt was fixed.
- Painted-mode lighting keeps phase/weather colours and increases existing fill by 1.6, with sun shadow opacity .65 and blur 2. These remain default values when the painted finish is absent. The chosen pushed C has no Body outline pass.

Relevant files: `scripts/asset_pipeline/kit_retarget.py`, `kit_body_paint.py`, `build_character_kit.py`, `test_character_kit_retarget.py`, `test_character_kit_art.py`, `test_kit_body_paint.py`; `assets/characters/kit/character_kit.spec.json`, runtime GLBs/provenance, `body_brush_pigment-v1.png` and its provenance; `clients/godot-csharp/CharacterKit.cs`, `Proof/ProofRun.CharacterBody.cs`, `ProofRun.CharacterKit.cs`, `ProofRun.CharacterReview.cs`, `Render/RenderWorld.Lighting.cs`, `Render/CharacterBodyPainted.tres`, `shaders/character_body_painted.gdshader`.

## 3. Verified and failed — do not conflate them

**Actually passed:**

- Last relevant C# build: zero warnings/errors; 2,037 EntryGuard tests passed.
- Art/export 16 tests; retarget 16 tests; paint/bitmap provenance 3 tests passed.
- A12 / B18 / C18 original rendered PNGs, all 1280×720, seed 137, passed real camera/skinned-contact assertions. B/C use identical final candidate GLBs. Latest C is clean source ffce2b623f63; subsequent pushed commit ae29a2ed changes documentation only.
- Full character-kit **headless** regression passed after final shader integration. `full-regression-final.exit` is 0, scenario ok:true, cleanup exit 0/no orphans. This verifies geometry/poses/kit assertions, not pixels. An earlier wrapper exited 143 despite a completed report; the final isolated rerun completed cleanly.
- Source push ran 46 static guards successfully.

**Unresolved failure:**

```
TT_KIT_PAWNS=1 TT_KIT_BODY_FINISH=painted \
TT_PROOF_DIR=/home/chris/tmp/agent-tmp/body-first-20261012/live-projection-final \
TT_TIMEOUT=180 timeout 200 setsid bash clients/godot-csharp/run.sh \
  --no-build --no-render --scenario=character-review --seed=137
```

This FAILED **before appearance review**, in `ScenarioCommittedActivityAsync`, `clients/godot-csharp/Proof/ProofRun.Interaction.cs:409`:

> Axe held by 13 (stature 0.94) is 0.652 of their height, not 0.45.

Whether the failure is introduced by this pass or is an existing kit-path assumption is **NOT DIAGNOSED**. Do not weaken the assertion, claim live projection acceptance, or merge before diagnosis. Baseline comparison on original kit assets/current main is the next engineering check after resolving write ownership.

**NOT RUN:** hardware GPU/frame pacing/performance, full moving simulation footage, release certification. Full horizontal foot planting IK remains an older limitation. Owner art approval is pending.

## 4. Evidence, critique and costs

- Public artifact draft: https://github.com/ChrisTutorials/thistletide-art-reviews/pull/2
- Public review directory: https://github.com/ChrisTutorials/thistletide-art-reviews/tree/review/body-first-pass-29/reviews/pass-29-body
- Native offline gallery: `/home/chris/review/character-art-20261012/pass-29-body/index.html`. It has been updated to C-brush-light; opening this new body gallery in the browser has NOT RUN in this handoff.
- Scratch/checks: `/home/chris/tmp/agent-tmp/body-first-20261012/`.
- Artifact repo checkout: `/home/chris/tmp/agent-tmp/thistletide-art-reviews`, branch `review/body-first-pass-29`. Original assets, current verified assets, source snapshots, unedited PNGs, earlier experiments, failures and SHA256 manifest are published. Do not repack from the now-dirty source tree without separating the unknown edits.
- Correct baseline is **A-clean**; latest geometry B-final; chosen material C-brush-light. **Do not use A-rest as true bind rest or failed C-pigment as a candidate.**

Independent reviewers B/C confirm the repaired shoulders across the pair and physique strips. Both incremental reviews opened 18 originals across C-final/C-pigment-fixed/C-brush-light and favour C-brush-light. They do not grant owner or production PASS. Remaining visual weaknesses: some airbrushed anatomy, conspicuous finger-shaped thigh/hip shadows, and little material difference at native z9. The albedo-wide C-pigment-fixed looks mottled/bruised; keep it historical. Latest notes: review-brush-b.md and review-brush-c.md; broader reviews review-final-b.md/review-final-c.md. Reviewers were read-only and did not run builds/tests.

55 joints and 19 clips remain. Each Body has 14,517 exported vertices and 26,756 triangles. UV2 is 116,136 bytes per base. Male/female GLB deltas from A: 201,912/298,864 bytes; exact hashes in asset-cost.json. Shared PNG is 1254×1254, 1,874,841 bytes, one shader sample per body fragment with shared runtime mipmaps. These are actual file/material counts, not hardware timing.

## 5. Remaining and next action

1. Identify the writer of the new dirty edits; preserve them and use the pushed ae29a2ed source/evidence as the last verified boundary.
2. Diagnose the axe/body scale assertion against the original kit baseline; repair its owning presentation/scaling code if this pass caused it. Do not raise limits or mask the check. Rerun the focused live proof.
3. Bring the strongest actual Godot bare-body candidate to the owner for **BODY PASS / ITERATE / REJECT**. Do not declare the Weathered Folklore style complete from passing tests.
4. Only after BODY PASS resume one 1500–1600/pre-firearms frontier hero outfit and matching pair. Keep default promotion behind the later full-character owner approval.
5. UI icon intake and other visual improvements stay paused. Owner icon source remains `/home/chris/Pictures/thistletide_weathered_folklore_icons.png`; its prepared scratch intake was not landed and is stale against main's newly appended farm/fish cells. Earlier complete pass27 evidence remains artifact repo PR1; old outfit draft #4450 and pass28 gallery remain historical.

No source merge, production default change, release, hosted CI, or artistic PASS occurred.
