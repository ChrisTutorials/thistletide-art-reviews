# Independent finish review C — brush light

## Changed

Read-only incremental pixel critique. Saved this note outside the repository. No source or asset edits.
Latest source identifier supplied by coordinator: ffce2b623f63, reported clean. Geometry identity, unchanged albedo/UV2/tint, shader wiring and lighting parameters are coordinator provenance, not independently checked here.

## Verified

Direct filesystem/Pillow measurement: C-final, C-pigment-fixed and C-brush-light each contain 18 PNGs; all 54 are 1280 × 720. Read all three scenario.json files: each reports ok:true. This is report inspection, not a fresh scenario run.
Opened 18 distinct original images, six per finish. Judged at their original 1280 × 720 presentation, without a composite or resized comparison.

**Finish preference: C-brush-light narrowly ahead of C-final; C-pigment-fixed last.** The latest is a restrained improvement, not a substantial new painterly look.

- C-pigment-fixed introduces conspicuous irregular light/dark pigment across the male chest/abdomen and thighs in detail45 and Walk, and across the female legs. These marks compete with anatomy; they read as blotchy surface variation rather than deliberate painted form. PickUp also shows irregular skin shading on the limbs. I independently reproduce the mottling concern.
- C-brush-light preserves the broad warm light and cool/brown shadow fields of C-final. It avoids those conspicuous pigment blotches. Close detail45/profile show mildly less uniform transitions, but its separation from C-final is small at this scale. I would retain this version of the three, without presenting it as an obvious brush-painted transformation.
- Latest shoulders remain continuous in the two detail angles and Walk/PickUp. The adult body proportions and dimensional torso/limb volumes remain readable. No new obvious geometry collapse, shoulder ledge or surface discontinuity in these inspected stills.
- Day/dusk z9 preserve readable warm/cool lit bodies and scene-dependent shadow changes. I cannot distinguish a meaningful painterly upgrade at that zoom. The figures are roughly 70–85 pixels tall; their value grouping and silhouette dominate.
- Dark finger-shaped shadows remain conspicuous on the hip/upper thigh in Walk, particularly the male. Profile also retains hand-adjacent dark marks. They are softer than the old severe black-patch stage, but the latest brush treatment does not remove their visual emphasis. Their shape and placement suggest cast/self shadows; pixels alone do not prove the shading owner. PickUp still has a broad dark hip/outer-thigh shadow, which reads more coherently as volume than random pigment.

## Remaining

1. If another skin finish iteration is needed, favor sparse, anatomically directed changes in the light/shadow boundary over all-over pigment noise. The current finish remains largely smooth/airbrushed, though softly illustrated and dimensional; stronger weathered frontier paint identity is still modest.
2. Reduce the visual dominance of hand cast shadows on hips/thighs while keeping contact and body depth. The fingers currently stamp a more literal, darker pattern than the surrounding broad painted forms.

No face or wardrobe recommendations: those recipes are frozen under the body-first direction. This review covers only the listed stills, not all physiques or a full animation sweep.

## Blockers and approval

No new obvious development blocker found in inspected incremental stills. This is not production art approval. Explicit human owner BODY PASS remains required; no automatic ship decision follows from my finish preference.

Tests/builds: NOT RUN. Hardware/performance: NOT RUN. New rendering/scenario execution: NOT RUN. Source hashes, identical geometry and shader contracts: NOT independently verified. Full animation continuity and the 36-figure fit matrix in this latest set: NOT RUN.

## Exact original files opened

- C-final/body_detail_45.png
- C-final/body_detail_90.png
- C-pigment-fixed/body_detail_45.png
- C-pigment-fixed/body_detail_90.png
- C-brush-light/body_detail_45.png
- C-brush-light/body_detail_90.png
- C-brush-light/body_Walk.png
- C-brush-light/body_PickUp.png
- C-brush-light/body_day_z9.png
- C-brush-light/body_dusk_z9.png
- C-final/body_Walk.png
- C-final/body_PickUp.png
- C-final/body_day_z9.png
- C-final/body_dusk_z9.png
- C-pigment-fixed/body_Walk.png
- C-pigment-fixed/body_PickUp.png
- C-pigment-fixed/body_day_z9.png
- C-pigment-fixed/body_dusk_z9.png

