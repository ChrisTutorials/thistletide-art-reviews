# Independent adversarial body pixel review C — current A-clean/B/C

**Finding:** HOLD body art acceptance. B/C actual rest shoulders are smooth, but normal posed detail/Walk/PickUp still forms triangular shoulder caps. C adds some softer dimensional body shading, yet very dark hard self-shadow shapes dominate several poses. The illustrated weathered frontier finish is not established at gameplay scale. This is exploratory critique; no code/art approval granted.

**Changed:** This note only; no source edits, builds, tests or renders.
**Verified:** Python Path.glob and Pillow image.size: A-clean,B,C each12 originals, all1280×720. Actually opened27 original PNGs through view_image (nine pervariant), exact filenames below. A-clean used as baseline; stale A/A-rest/diagnostic folders not treated as evidence. Source/geometry identity between B/C supplied by coordinator, not independently checked.

## Re-derived observations

1. **Posed shoulder anatomy remains the first blocker.** In B/C rest0 andrest90 shoulder-to-upper-arm contour is continuous. In detail0 and45 the lateral shoulders become triangular ledges over a narrow upper-arm attachment, stronger on male but present on female. Walk retains the same cap; PickUp's bent upper arm meets a sharp shelf/indent. A-clean already shows related deformation. Therefore smooth bind/rest proves the rest shape only, not pose quality. C material changes soften edges but leave the silhouette defect. Fix pose/deformation ownership before judging more anatomy paint.
2. **B adult proportions remain coherent but the stylization is subtle.** Ribcage/waist/pelvis and thigh/calf transitions remain identifiable; hands/feet readable and grounded in rest/detail. Male taper and female pelvic fullness give adult body structure. B changes are small enough that z9day/dusk silhouettes remain essentially the same visual category. The female's larger head-to-body visual relationship still reads younger than the male; no face recipe tuning proposed. There is no measured anatomy-ratio claim in this note.
3. **C dark shapes are real; paint ownership is not proven.** Rest90 shows a distinct finger-shaped dark silhouette across hip/upper thigh on both bodies. Detail90 has a dark arm-adjacent hip strip; Walk has a hard dark mass beneath the forward hand/forearm; PickUp has nearly black torso/hip shapes and bands across thighs/knees. These read as strong hard cast/self shadows, with finger shapes especially indicating a scene-light contribution (inference from pixels). I agree with B that they look stain-like and hurt the softly illustrated finish; I do not establish them as anatomical paint defects without a shadow/material diagnostic.
4. **C is dimensional, not yet convincingly painted/weathered.** Chest/waist shading is softer and linework reduced versus B, so it has some directional improvement. Smooth warm fields still dominate most exposed body; no convincing broad hue planes, handled/worn finish or deliberately painted anatomical modeling is readable atz9. Dusk keeps two adult silhouettes but darkens internal anatomy; day gain is mainly lighter/softer value and reduced outlines. Hard nearly black shadows oppose the requested soft finish.
5. **Two next actions:** First repair the posed deltoid/clavicle contour with body/rig ownership and recheck detail0/45,Walk,PickUp. Then isolate scene-light self-shadow from UV2paint and lift/soften the black shadow shapes; judge broad warm-light/cool-shadow anatomical planes only after that separation. Wardrobe and face changes remain paused peruser direction.

## Agreement / challenge

C independently confirms B's posed shoulder shelf finding and hard dark hip/thigh shapes. C challenges treating those shapes as paint stains: visible finger-shaped shadows strongly suggest hard scene-light self-shadow involvement. Exact cause NOT RUN. C agrees that z9 style gain is modest, but “mostly brightness” is a visual description, not a measured luminance result. Neither same-geometry nor actual shader contracts were inspected.

## Exact originals viewed (27)

Base:/home/chris/tmp/agent-tmp/body-first-20261012/

- A-clean/body_rest_0.png
- A-clean/body_rest_90.png
- A-clean/body_detail_0.png
- B/body_rest_0.png
- B/body_rest_90.png
- B/body_detail_0.png
- C/body_rest_0.png
- C/body_rest_90.png
- C/body_detail_0.png
- A-clean/body_detail_45.png
- A-clean/body_detail_90.png
- A-clean/body_Walk.png
- A-clean/body_PickUp.png
- B/body_detail_45.png
- B/body_detail_90.png
- B/body_Walk.png
- B/body_PickUp.png
- C/body_detail_45.png
- C/body_detail_90.png
- C/body_Walk.png
- C/body_PickUp.png
- A-clean/body_day_z9.png
- A-clean/body_dusk_z9.png
- B/body_day_z9.png
- B/body_dusk_z9.png
- C/body_day_z9.png
- C/body_dusk_z9.png

**Remaining:** Root pose-deformation investigation, light/shadow separation and corrected body-only comparison.
**Blockers:** Posed shoulder silhouette defect; hard dark self-shadow shapes prevent a convincing soft body finish.
**NOT RUN:** Code/tests/builds, hardware/performance, animation playback, remaining9 PNGs(detail180,z5day,z5dusk eachvariant), scenario completion/status validation, geometry hash comparison, UV2/material/shadow diagnostic, numeric anatomy or luminance metrics, owner art approval. File counts/resolutions verified; unrun checks are not PASS.

