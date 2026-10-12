# Independent A-clean / B / C body art review

## Changed

- **B vs A-clean:** The torso and hip shapes are modestly fuller and more articulated. Aldric's front has a clearer pectoral and waist transition; Wren's bust, waist and pelvis have more volume. Side profile has slightly better ribcage/abdomen form. These are visible at detail scale, much less so at gameplay z9.
- **C vs B:** The same shapes render with warmer, softer, less outlined skin and more modeled light/dark planes. This gives a more dimensional impression in frontal close views. C also creates large, hard, very dark shadow shapes over hips and thighs in side and action views.

## Verified

- Inspected **30 original PNGs**, 10 each in `A-clean`, `B`, `C`: `body_rest_0.png`, `body_rest_90.png`, `body_detail_0.png`, `body_detail_45.png`, `body_detail_90.png`, `body_Walk.png`, `body_PickUp.png`, `body_day_z9.png`, `body_dusk_z9.png`, `body_day_z5.png`. All **36 PNGs present** across the three directories, 12 each. All measured **1280×720 px**. No resized images used for the native-size judgment. `body_detail_180.png` and `body_dusk_z5.png` were not opened in this review.
- Tests, builds, source inspection, shader measurements: **NOT RUN**. Faces and wardrobe were out of scope.

## Remaining / blockers

1. **Body approval blocker: posed shoulder shelf still reads as a sleeve.** Both bodies have a continuous sloping shoulder at rest in B/C. In `C/body_detail_0.png`, Aldric's shoulder ends in a straight lateral ledge around x433–583,y178–209 and Wren's around x739–848,y246–281, with a dark abrupt arm-root crease beneath. `C/body_detail_45.png` and `C/body_Walk.png` keep that cut-off edge; `C/body_PickUp.png` shows the shoulders as angular flaps while bent. The B geometry/aim pass did not resolve it; C's paint makes the ledge more conspicuous by giving it a broad, uniform highlight. The rest/pose difference is visible, but the images alone do not prove a particular bone, weight or shader cause. Priority: preserve the shoulder-to-deltoid continuity through Idle, Walk and PickUp.
2. **C finish blocker: hard moving shadows read like painted black patches.** In `C/body_rest_90.png`, each figure has a sharply edged dark shape from hip over upper thigh (Aldric near x450–507,y315–414; Wren near x730–780,y348–418). The patches recur in `C/body_detail_90.png` and move into different thigh positions in `C/body_Walk.png` and `C/body_PickUp.png`. They dominate the body paint and break the intended soft, dimensional finish. B side/action views do not have patches of comparable contrast. Investigate the light/shadow response at the same pose and camera before adding more painted anatomy.
3. **Quality refinement after those fixes:** B/C improves broad form, but the ribcage, upper back, knees and calves still read as fairly smooth tubes at close range. C's warm paint is subtle; at native z9 day/dusk it changes body brightness more than anatomical read. More small UV2 markings would not compensate for the two visible shape/light defects.

## Verdict

The change is **substantial at close range in material response, moderate in geometry, and limited at gameplay z9**. It does not yet reach a convincing painterly dimensional adult-body finish because the posed shoulder shelf persists and C's side/action shadows look like dark stains. Body art approval remains with the owner; this review recommends keeping the body-first gate closed while these visible defects remain.
