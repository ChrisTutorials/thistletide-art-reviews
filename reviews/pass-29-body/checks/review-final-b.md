# Independent final body review — A-clean / B-final / C-final

## Changed

- **Geometry/pose:** The old horizontal shoulder shelf is gone. In A-clean `body_detail_0.png` and `body_Walk.png`, both shoulders read as a short flat sleeve ending above the arms. In B-final and C-final the neck, shoulder and upper arm form a continuous outline in Idle and Walk. PickUp also retains a plausible rounded shoulder instead of the earlier angular flap. This is a substantial anatomical correction.
- **Form:** B-final has a clearer waist, ribcage and pelvis than A-clean; C-final keeps that geometry. The six physiques vary in height, width and mass without an obvious torn joint in the inspected Idle/Walk/PickUp sheets.
- **Finish:** C-final gives the skin a warmer, softer gradation and reduces the thick ink-like rim of B-final. The earlier near-black hip/thigh blotches are materially reduced in `C-final/body_PickUp.png` and the 90-degree view.

## Verified

- **32 original PNGs opened**, all **1280×720 px**. A-clean (6): `body_detail_0.png`, `body_detail_90.png`, `body_Walk.png`, `body_PickUp.png`, `body_day_z9.png`, `body_dusk_z9.png`. B-final (10): `body_rest_0.png`, `body_rest_90.png`, `body_detail_0.png`, `body_detail_45.png`, `body_detail_90.png`, `body_detail_180.png`, `body_Walk.png`, `body_PickUp.png`, `body_day_z9.png`, `body_dusk_z9.png`. C-final (16): those same ten plus `body_fit_male_Idle.png`, `body_fit_male_Walk.png`, `body_fit_male_PickUp.png`, `body_fit_female_Idle.png`, `body_fit_female_Walk.png`, `body_fit_female_PickUp.png`.
- Directory inventory: A-clean has 12 PNGs; B-final and C-final have 18 each. Resolution was measured from files; artistic findings are from original pixels. Builds, tests, source/shader inspection and animation sampling beyond these stills: **NOT RUN**.
- Read each `scenario.json`: `ok: true`, `rendered: true`, with 12/18/18 listed artifacts respectively. B-final and C-final both report clean checkout `d279d4ba4f5f`; these metadata checks do not count as aesthetic acceptance.

## Remaining

1. **Skin finish still lacks the intended weathered, painterly surface.** In C-final `body_detail_0.png` and `body_detail_180.png`, broad light and dark bands model the bodies, but most chest, abdomen, back and limbs are smooth gradients. At native `body_day_z9.png` and `body_dusk_z9.png`, the final work mostly changes brightness; anatomy paint is not legible. A restrained irregular warm/cool skin variation and more form-specific treatment at clavicle, ribcage, knee and shin would help. Do not spend this on eyes/brows or wardrobe.
2. **Some cast/self-shadow edges still look like dark markings.** `C-final/body_rest_90.png` shows finger-shaped dark shadows across Aldric's and Wren's upper outer thighs; `C-final/body_Walk.png` retains a dark hip patch under the forward hand on both. They are much less severe than the prior C capture and are not a geometry break, but remain conspicuous at detail scale. Keep the physical shadow while softening its edge/contrast for the painterly target.
3. **Form remains stylized and somewhat generic.** All six female sheets show a repeated simple bust-to-waist transition and all six male sheets show similarly smooth chest/abdomen planes. The physiology variants read mainly through scale and width rather than local anatomical character. This is a quality refinement, not a joint correctness defect.

## Blockers / recommendation

- **No reproduced merge-blocking body deformation** in the inspected final Idle, Walk or PickUp stills. The shoulder defect that blocked the prior review appears corrected across both named adults and six male/six female physique strips.
- **Recommendation for owner body-art gate: ITERATE.** The new body foundation is a substantial improvement and is technically plausible for moving to review, but C-final does not yet make the promised weathered painterly finish convincing at detail scale; the thigh/hip shadow pattern and smooth, uniform skin are the remaining visible issues. This is an independent recommendation, **not owner or production art PASS**. Faces and wardrobe remained outside scope.
