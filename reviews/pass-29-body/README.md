# Thistletide — body-first pass29

**Owner BODY PASS / ITERATE / REJECT pending. Clothing and other visual work are paused.**

Implementation: [draft #4453](https://github.com/ChrisTutorials/thistletide-gd/pull/4453). Updated direction: [draft #4447](https://github.com/ChrisTutorials/thistletide-gd/pull/4447). Earlier clothing experiment #4450 remains paused.

## Compare the actual Godot bodies

Open `index.html` after downloading this directory for the native-resolution offline gallery. Original gameplay 1× shots come first. Raw PNGs can also be inspected directly here.

| Candidate | Evidence | Meaning |
|---|---|---|
| A |12 original 1280×720 PNGs|Merged MakeHuman anatomy/material, stripped in the proof only|
| B |18 original 1280×720 PNGs|New proportions and corrected retarget roll under the existing material|
| C |18 original 1280×720 PNGs|Identical B GLBs with anatomical paint, brushed light transitions and controlled lighting|

**Original anatomy renders contain nonsexual adult nudity.** [Open the original body diagnostic](C/body_detail_45.png).

Seed 137; authored Aldric/Wren identities; identical common poses/cameras. The extra B/C sheets use the existing six physiques, each under Idle, Walk and PickUp. These are staged studies and held animation samples, **not moving simulation footage**. `source-identity.json` and launcher logs record the source heads. A was captured at 7db79e9503bd; B at d279d4ba4f5f; latest C at ffce2b623f63. Current branch head adds documentation only.

## Changed

- Adult body defaults: HeadSize .58, Muscle .25, Chest .12, TorsoLength .40, LegLength -.40, ArmLength -.12, NeckLength .08. Base measurements: male 6.46 and female 6.30 heads tall. Detailed facial recipes and hairstyles remain frozen.
- Retarget direction alignment had copied approximately 119° of unwanted upper-arm roll from the folk rig into MakeHuman Idle. Restoring target standing roll keeps limb directions while removing the shoulder shelves. The new exported upper-arm Idle twist is below 1°.
- Body-only spatial shader retains actual geometry normals, saved skin colour, existing face vertex paint and real scene LIGHT/ATTENUATION. UV2 carries broad anatomical tone/warmth. A shared AI-generated grayscale bitmap breaks soft light-value transitions; it is not painted dirt. Exact prompt/hash/provenance are beside the runtime PNG.
- C uses the existing phase/weather fill ×1.6, sun shadow opacity .65 and blur 2. Other material families retain their materials. Defaults remain unchanged unless `TT_KIT_BODY_FINISH=painted`; MakeHuman pawns still require `TT_KIT_PAWNS=1`. Bare bodies exist only in the proof.

## Verified / failures

- C# build: zero warnings/errors; 2,037 EntryGuard tests passed.
- Art/export 16 tests; retarget 16; body-paint/provenance 3: passed.
- A/B/C original image captures passed their real skinned-camera/contact assertions. Full character-kit headless regression passed, launcher exit 0, after the final shader integration. Headless regression has no pixels.
- **Additional live projection proof FAILED before reaching appearance review:** player 13, stature .94, held axe measured .652 of body height; assertion expects .45. See `checks/live-projection-final/`. Whether this is newly introduced or a pre-existing kit-path assumption is **not diagnosed**. Do not claim live projection acceptance or merge readiness.
- Hardware performance, real moving simulation footage and owner body approval: **NOT RUN / pending**.

## Visual critique

Independent reviews confirm continuous shoulders across the pair and the six physique strips. C-brush-light is the strongest finish in reviewer B's incremental comparison: full albedo brush modulation looked mottled, so the chosen version confines brush breakup to illustrated light transitions. Skin still has some airbrushed forms and visible finger-shaped thigh shadows; surface differences barely register at native z9. This is body foundation evidence for owner review, **not production art acceptance**.

## Cost and provenance

55 skin joints and 19 clips retained. Each Body has 14,517 exported vertices and 26,756 triangles. UV2 adds 116,136 bytes of coordinates per base. Current male/female GLBs are 201,912/298,864 bytes larger than A; exact hashes/sizes are in `checks/asset-cost.json`. One shared 1254×1254 pigment texture is 1,874,841 source bytes with mipmaps generated at runtime. The shader adds one texture sample per body fragment and drops the Body outline pass. These are asset/material measurements, **not a hardware timing claim**.

`original-assets/`, `candidate-assets/`, `source/` and `checks/` contain assets, provenance, source snapshots and actual logs. `exploratory/` retains earlier comparisons and the failed first texture load; those are clearly historical experiments. All matched PNGs are unedited originals. No hosted CI, merge, release or default promotion occurred.
