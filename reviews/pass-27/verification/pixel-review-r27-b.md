# Independent r27 pixel review B

## Changed

- Read-only inspection of the clean-source 1080p matrix `/home/chris/tmp/agent-tmp/kit-art-20261011/godot-r27-final` (source identified by owner as `7d8b28291ff5`), with targeted r26 and production-image comparisons. No repository files changed.

## Verified

- Recounted **117 PNGs** in the r27 matrix; its `scenario.json` reports `ok: true` and `rendered: true`. The exploratory `production-kit-r27` directory contains **75 PNGs**, also with scenario `ok: true` and `rendered: true`; it predates the commit and is used here only to inspect the exact final GLBs, not as a clean-source A/B proof.
- Opened **24 distinct r27 PNGs at original resolution**, plus **six r26 comparison PNGs** (exact list below). The ten r27 Cloak fit sheets cover both bases in Idle, Walk, PickUp, and both Sleep rows (six physiques per sheet, 60 displayed figures). There is no newly exposed body, large cloth hole, or severed panel in those stills.
- r26 Cloak Idle/Walk had several sharp, jagged lower-corner teeth, particularly the female stocky/heavy sheets and male stocky/broad Walk. The corresponding r27 sides and hems hang more continuously. In the production profile, the pale cloak on the third figure has a toothed trailing edge in r26 near image x530–550/y285–335; r27 presents a single straighter trailing edge. In the production rear, the same pale cloak's lower edge is smoother and rounder. These are visual location estimates, not measured geometry. The reported old 17.4 cm stretch and new edge assertion were **not independently measured or run** by reviewer B.
- r27 PickUp raises the Cloak panels behind the bent torso on both bases; the edges stay attached and do not intersect the arms in the sampled pose. Both Sleep rows still hold a long, near-horizontal panel above the upper leg, which reads stiff like a sail, but it has a continuous silhouette rather than a new tear. This is production art polish.
- Four r27 apron Walk/HugWalk sheets show intact tan fronts for all six physiques per base (**0/24 displayed figures with the former cream Shirt breakthrough**); the joined hands remain visible in HugWalk. Hero 45/90/180 and 30-community frames remain complete and framed. Front/back masculine hair still has readable variants, while close-crop/side-part backs remain smooth, rounded caps.
- Production-kit-r27 front/profile/rear and one gait still remain readable at gameplay zoom. The staged gait still has only five easily separable silhouettes as two red figures overlap near the selection ring, as in r26; it does not show a cape-only failure. The exploratory capture does not establish clean-source integration or owner art approval.

## Remaining / blockers

- **Development correctness blocker found:** none in the inspected stills. The cape tooth regression is visibly improved and the r26 apron coverage fix persists. This supports an opt-in development merge alongside separately executed mechanical checks.
- **Production art approval remains pending:** refine the rigid Sleep Cloak pose, cape drape/motion, smooth hair caps and ear joins, and weak face archetype differentiation with the owner.
- **NOT RUN by reviewer B:** build, automated edge check, numerical 17.4 cm remeasurement, full animation playback, hardware performance, source audit, or a clean-source r27 production A/B capture.

## Exact original PNGs opened

### r27 clean matrix (20)

1. `godot-r27-final/kit_fit_female_frontier_cloak_Idle.png`
2. `godot-r27-final/kit_fit_female_frontier_cloak_Walk.png`
3. `godot-r27-final/kit_fit_female_frontier_cloak_PickUp.png`
4. `godot-r27-final/kit_fit_female_frontier_cloak_Sleep_0.png`
5. `godot-r27-final/kit_fit_female_frontier_cloak_Sleep_1.png`
6. `godot-r27-final/kit_fit_male_frontier_cloak_Idle.png`
7. `godot-r27-final/kit_fit_male_frontier_cloak_Walk.png`
8. `godot-r27-final/kit_fit_male_frontier_cloak_PickUp.png`
9. `godot-r27-final/kit_fit_male_frontier_cloak_Sleep_0.png`
10. `godot-r27-final/kit_fit_male_frontier_cloak_Sleep_1.png`
11. `godot-r27-final/kit_fit_female_frontier_apron_Walk.png`
12. `godot-r27-final/kit_fit_female_frontier_apron_HugWalk.png`
13. `godot-r27-final/kit_fit_male_frontier_apron_Walk.png`
14. `godot-r27-final/kit_fit_male_frontier_apron_HugWalk.png`
15. `godot-r27-final/kit_heroes_45.png`
16. `godot-r27-final/kit_heroes_90.png`
17. `godot-r27-final/kit_heroes_180.png`
18. `godot-r27-final/kit_hair_masculine_0.png`
19. `godot-r27-final/kit_hair_masculine_180.png`
20. `godot-r27-final/kit_community_30.png`

### r27 exploratory production (4)

21. `production-kit-r27/folk_review_profile_z5.png`
22. `production-kit-r27/folk_review_rear_z5.png`
23. `production-kit-r27/folk_review_front_z5.png`
24. `production-kit-r27/folk_review_walk_0030.png`

### r26 comparison (6)

25. `godot-r26-final/kit_fit_female_frontier_cloak_Walk.png`
26. `godot-r26-final/kit_fit_male_frontier_cloak_Walk.png`
27. `godot-r26-final/kit_fit_female_frontier_cloak_Idle.png`
28. `godot-r26-final/kit_fit_male_frontier_cloak_Idle.png`
29. `production-kit-r26/folk_review_profile_z5.png`
30. `production-kit-r26/folk_review_rear_z5.png`
