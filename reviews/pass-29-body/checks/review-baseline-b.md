# Independent body baseline critique (read-only)

## Changed

- No art or code changed. This is a baseline review for the body-first gate.

## Verified

- Opened **11 original PNGs**: `A/body_detail_0.png`, `body_detail_45.png`, `body_detail_90.png`, `body_detail_180.png`, `body_Walk.png`, `body_PickUp.png`, `body_day_z9.png`; and `A-clean/body_rest_0.png`, `body_rest_90.png`, `body_detail_0.png`, `body_detail_90.png`.
- `A-clean/scenario.json` says `ok: true`, `rendered: true` and includes both rest captures. That only validates completion; the observations below come from pixels. Tests/build: **NOT RUN**.
- Rest versus animation: in `A-clean/body_rest_0.png`, both shoulders slope more naturally into the arms. In the matching Idle `body_detail_0.png`, both become nearly horizontal triangular shelves with abrupt lateral corners and dark wedges below them (Aldric around x429–586,y157–220; Wren around x739–853,y222–280). `A/body_Walk.png` retains the shelf, and `A/body_PickUp.png` exaggerates the angular shoulder/upper-arm join. This strongly implicates pose deformation or shoulder skinning in the most conspicuous defect; it does not prove a specific weight or bone is wrong.

## Remaining: anatomical priorities

1. **Repair shoulder deformation first.** The Idle shoulder reads like a short cape or cut-off sleeve, not a deltoid flowing into upper arm and clavicle. In profile (`A/body_detail_90.png`), Aldric has a sharp backward scapular projection and dark vertical crease at the shoulder (roughly x465–485,y151–201). Wren has a similar pinched upper-arm root. Keep the continuous rest-pose shoulder silhouette through Idle, Walk, and PickUp, with a smooth front armpit and rear deltoid transition. This is the current body-approval blocker.
2. **Add torso mass and surface structure once the joint is stable.** From front (`A/body_detail_0.png`), Aldric's chest/abdomen is a smooth taper with little pectoral, ribcage, or pelvic landmark; the arms and legs are similarly tube-like. At 90°, his upper back/ribcage is nearly flat and abdomen projects as a rounded bulge, giving a thin board-plus-belly profile. Wren's side torso is also very flat above the breast, with a sharp hip-to-buttock change. A modest ribcage/lat/oblique and pelvic transition would make them read as dimensional adults without adding face detail or extreme muscle definition.
- At native `body_day_z9.png`, both figures are tiny (roughly 80 px tall) and anatomical details cannot be judged reliably. The broad human silhouette remains readable; approval should use detail and movement views.

## Blockers / limits

- **Body art gate: not yet approved.** The animated shoulder shelf is a visible correctness defect in both figures and multiple poses. The flat torso forms remain a quality limitation, distinct from that deformation.
- Rest/animation attribution is based only on the corrected `A-clean` capture and paired pixels. Earlier `A-rest` and `A-rest-actual` were excluded because their pose capture/assertion was invalid. No technical cause was claimed beyond the visible pose dependency. Faces and wardrobe were out of scope.
