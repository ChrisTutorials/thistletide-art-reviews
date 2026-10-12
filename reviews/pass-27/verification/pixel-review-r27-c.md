# Independent adversarial pixel review C — r27

**Verdict:** No development blocker found in the inspected stills. C independently agrees with B's r27 finding. Human production art approval remains pending and is not granted by this note.

**Changed:** This note only, outside repository. No source edits, tests, builds, renders, push or merge performed by C.
**Verified:** Current-session Python Path.glob counts: godot-r27-final117 PNGs, production-kit-r26 75 PNGs, production-kit-r27 75 PNGs. Read all three scenario.json files:ok:true/rendered:true. Clean matrix source supplied:7d8b28291ff5. Matrix artifact length117. Opened20 clean r27 originals,2 r26 matrix comparators and4 production comparison originals through view_image, exact filenames below.

## Pixel findings and measurement

1. **Cloak shape corrected without obvious exposure/collapse.** Both bases Idle/Walk/PickUp plus both Sleep panels inspected:10 sheets/48 displayed figures. Green panels remain continuous. Lower corners on stocky/heavy Walk are straighter and smoother than actual r26 same-sheet comparators; old angular projections are absent. PickUp trailing panels retain coherent strips with smooth ends; linen tunic/waist remains covered. No new obvious bare underlayer, open ground hole or collapsed panel found in these sampled poses.
2. **Apron repair holds.** Four Walk/HugWalk sheets, both bases×six physiques:24 figures manually inspected. Tan fronts continuous; no relocated cream/belt islands. Both hands visible on all12 HugWalk figures. Native1920×1080 Pillow thresholdR>230,G>225,B>165 repeated on femaleHugWalk:stockyROI(765,530)-(835,565)=0,heavyROI(1395,483)-(1500,525)=0. These match r26 and stay clear of measured r24 defects1474/2850; zero in two ROIs alone is not universal geometric proof.
3. **Production profile/rear appearance improved.** Opened r26 and r27 original profile/rear files. Pale third-NPC rear garment loses backward teeth in profile and jagged lower silhouette in rear; now reads as a single smooth hanging panel. Native1280×720 profileROI x530–565/y295–335 inclusive, pale thresholdR>225,G>220,B>150: r26 695 qualifying pixels,bbox(530,295)-(558,331); r27 573,bbox(530,295)-(545,335). Maximum pale extent retracts13pixels. This supports the visible shape change; it is not a world-space edge-stretch measurement.
4. **Framing/identity stable.** Heroes45/90/180 retain silhouettes and grounded boots; central cloak hangs as a continuous taper. Community manual count3rows×10=30, all heads/boots fully framed. Masculinehair front/back remains distinct atfront, but close_crop/side_part rear domes remain smooth/helmet-like. Dark triangular interruptions at rear tunic hem remain visible; earlier r23/r26 inspection established these predate r27.
5. **Production polish remains.** Sleep cloak still stands in a raised rigid plane rather than settling like soft cloth; PickUp trailing cloak similarly stiff. Grooming, smooth materials/weathering, face identity refinement and rear tunic hem appearance remain art concerns. These are not evidence of a new r27 development regression in the inspected sample.

## Production evidence limitation

production-kit-r27 is explicitly an exploratory dirty pre-commit capture of the exact final GLBs, as supplied by coordinator. It proves observed asset appearance through that staged runtime capture; it is **not a clean-source matched A/B claim** against production-kit-r26 and does not establish Sim emergence. Source/GLB match supplied by coordinator, not independently rehashed by C. Six actors remain framed in compared static profiles/rears; selected actor keeps its orientation while the other five rotate.

C did not run or re-derive the supplied17.4cm/2.5cm edge-test numbers. Those are author mechanical evidence, not C pixel measurements.

## Exact originals opened

Clean r27 folder:/home/chris/tmp/agent-tmp/kit-art-20261011/godot-r27-final (20):

- kit_fit_female_frontier_cloak_Idle.png
- kit_fit_female_frontier_cloak_Walk.png
- kit_fit_female_frontier_cloak_PickUp.png
- kit_fit_male_frontier_cloak_Idle.png
- kit_fit_male_frontier_cloak_Walk.png
- kit_fit_male_frontier_cloak_PickUp.png
- kit_fit_female_frontier_cloak_Sleep_0.png
- kit_fit_female_frontier_cloak_Sleep_1.png
- kit_fit_male_frontier_cloak_Sleep_0.png
- kit_fit_male_frontier_cloak_Sleep_1.png
- kit_fit_female_frontier_apron_Walk.png
- kit_fit_female_frontier_apron_HugWalk.png
- kit_fit_male_frontier_apron_Walk.png
- kit_fit_male_frontier_apron_HugWalk.png
- kit_heroes_45.png
- kit_heroes_90.png
- kit_heroes_180.png
- kit_hair_masculine_0.png
- kit_hair_masculine_180.png
- kit_community_30.png

r26 matrix comparators:/home/chris/tmp/agent-tmp/kit-art-20261011/godot-r26-final (2):

- kit_fit_female_frontier_cloak_Walk.png
- kit_fit_male_frontier_cloak_Walk.png

Production comparisons under /home/chris/tmp/agent-tmp/kit-art-20261011 (4):

- production-kit-r26/folk_review_profile_z5.png
- production-kit-r26/folk_review_rear_z5.png
- production-kit-r27/folk_review_profile_z5.png
- production-kit-r27/folk_review_rear_z5.png

**Remaining:** Separate human production art decision; cloth settling and grooming/material refinement.
**Blockers:** None found for opt-in development in this inspected sample. Coordinator reports PR4413 landed; this note neither performed merge nor claims owner art approval.
**NOT RUN:** Code/tests/builds, remaining97 clean matrix PNG pixels, full animation playback, clean-source r27 production A/B capture, GLB hash verification, hardware/performance. Stills cannot establish all times, cameras or variations are free of intersections.

