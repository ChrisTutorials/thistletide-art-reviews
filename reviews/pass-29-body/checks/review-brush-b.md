# Incremental body finish review

## Changed

- **Best finish: C-brush-light.** Its irregularity stays mostly in the lit value transition, so skin color and anatomical planes remain readable. On Aldric's chest and side torso in `body_detail_45.png`, the transition is less airbrushed than C-final without the all-over blotches of C-pigment-fixed. Wren's skin remains coherent across the same views.
- C-pigment-fixed is visibly more textured, but the mottling appears on broad chest, abdomen and legs regardless of the form; in `body_detail_45.png` and `body_Walk.png` it reads closer to bruising/dirt than brushwork. C-final is cleanest but also smoothest. C-brush-light is a modest refinement, not a large style jump.

## Verified

- Viewed **18 original PNGs**, six per directory (`C-final`, `C-pigment-fixed`, `C-brush-light`): `body_detail_45.png`, `body_detail_90.png`, `body_Walk.png`, `body_PickUp.png`, `body_day_z9.png`, `body_dusk_z9.png`. All three directories contain 18 PNGs; all sampled images measured **1280×720 px**. Each `scenario.json` reports `ok: true`, `rendered: true` and 18 artifacts. Latest `C-brush-light` reports clean checkout `ffce2b623f63`.
- Native 1× gameplay day/dusk z9: the three finishes are nearly indistinguishable on the small figures. The added brush light neither harms readability nor makes Weathered Folklore materially clearer at that scale.
- Geometry review, source/shader audit, builds and tests for this incremental pass: **NOT RUN**. This review only compares the finish pixels; faces and wardrobe remain outside scope.

## Remaining / blockers

- `C-brush-light/body_detail_90.png` still has dark finger-shaped hand shadows on the outer thighs, and `body_Walk.png` still shows a dark patch at the hip under the forward hand. Their edges and contrast are reduced compared with the previous C capture, but they can read as stains at close range. This is a finish refinement, not a reproduced joint or coverage defect.
- The skin still reads as fairly smooth, evenly cared-for material: minimal irregular warm/cool variation beyond broad light fields, little sign of weathering or manual brush placement at clavicle/ribs/knees/shins. That is the main gap to the stated Weathered Folklore direction. At gameplay z9, silhouette and clothing will carry the style more than this body-only light texture.

## Verdict

**C-brush-light is ready to put before the owner for the cloth-free body foundation decision.** I found no new visual blocker in these six views, and the finish is preferable to both alternatives. This is a recommendation to request the owner's body review, **not production art PASS**; the owner may still require stronger weathered painterly treatment. Keep C-pigment-fixed as a rejected experiment rather than the selected finish.
