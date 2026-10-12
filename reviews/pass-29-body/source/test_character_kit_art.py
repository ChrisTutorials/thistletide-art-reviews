"""Check rebuilt art geometry and provenance; aesthetics still require pixel review."""

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from character_kit_glb import accessor, glb_chunks
from test_character_kit_retarget import Pose, turned

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "assets/characters/kit"


class KitArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((KIT / "character_kit.spec.json").read_text())
        cls.kits = {base: glb_chunks(KIT / f"kit_{base}.glb") for base in cls.spec["bases"]}

    def mesh(self, base, name):
        doc, blob = self.kits[base]
        mesh = next(m for m in doc["meshes"] if m["name"] == name)
        primitive = mesh["primitives"][0]
        co = np.array(accessor(doc, blob, primitive["attributes"]["POSITION"]), dtype=float)
        keys = {name: np.array(accessor(doc, blob, target["POSITION"]), dtype=float)
                if "POSITION" in target else np.zeros_like(co)
                for name, target in zip(mesh["extras"]["targetNames"], primitive["targets"])}
        return doc, blob, primitive, co, keys

    def shaped(self, co, keys, recipe):
        drivers = {n + ("+" if v > 0 else "-"): abs(v) for n, v in recipe.items() if v}
        target = co + sum((keys[d] * v for d, v in drivers.items()), np.zeros_like(co))
        for correction in self.spec["garment_correctives"]:
            x, y = correction["drivers"]
            target += keys[correction["name"]] * drivers.get(x, 0) * drivers.get(y, 0)
        return target

    def test_all_parts_are_skinned_and_all_fit_keys_have_real_geometry(self):
        for base in self.kits:
            doc, _ = self.kits[base]
            expected = set(self.spec["parts"]) | {"Body"}
            self.assertEqual(expected, {m["name"] for m in doc["meshes"]})
            for name in expected:
                _, _, primitive, co, keys = self.mesh(base, name)
                self.assertGreater(len(co), 0, (base, name))
                self.assertIn("WEIGHTS_0", primitive["attributes"])
                weights = np.array(accessor(doc, self.kits[base][1], primitive["attributes"]["WEIGHTS_0"]))
                self.assertTrue(np.allclose(weights.sum(axis=1), 1, atol=0.001), (base, name))
                self.assertTrue(np.isfinite(co).all(), (base, name))
                for delta in keys.values(): self.assertTrue(np.isfinite(delta).all(), (base, name))
                if name != "Body" and "fit" in self.spec["parts"][name]:
                    for correction in self.spec["garment_correctives"]:
                        self.assertIn(correction["name"], keys, (base, name))
            # A name with a zero delta is not evidence of a working correction.
            keys = self.mesh(base, "Vest")[4]
            self.assertGreater(np.linalg.norm(keys["Fit.Weight+.Waist+"], axis=1).max(), 0.0001)

    def test_anatomical_paint_survives_export_beside_original_uvs(self):
        for base in self.kits:
            doc, blob, primitive, co, _keys = self.mesh(base, "Body")
            self.assertIn("TEXCOORD_0", primitive["attributes"])
            paint = np.array(accessor(doc, blob, primitive["attributes"]["TEXCOORD_1"]))
            self.assertEqual((len(co), 2), paint.shape)
            self.assertTrue(np.isfinite(paint).all())
            self.assertTrue(((paint[:, 0] >= .60) & (paint[:, 0] <= 1.05)).all())
            self.assertTrue(((paint[:, 1] >= .05) & (paint[:, 1] <= .95)).all())
            self.assertGreater(np.ptp(paint[:, 0]), .15)
            self.assertGreater(np.ptp(paint[:, 1]), .25)

    def test_buttons_and_buckle_do_not_stretch_with_a_heavy_or_broad_body(self):
        for base in self.kits:
            for name in ("Buckle", "VestButtons"):
                doc, blob, primitive, co, keys = self.mesh(base, name)
                triangles = np.array(accessor(doc, blob, primitive["indices"])).ravel().reshape(-1, 3)
                a, b = triangles[:, 0], triangles[:, 1]
                before = np.linalg.norm(co[a] - co[b], axis=1)
                recipes = [s for s in self.spec["body_archetypes"].values()] + [{"Weight": 1, "Waist": 1}]
                for recipe in recipes:
                    after = self.shaped(co, keys, recipe)
                    measured = np.linalg.norm(after[a] - after[b], axis=1)
                    self.assertLess(np.max(np.abs(measured - before)), 0.00001, (base, name, recipe))

    def test_frontier_cloth_has_the_three_motion_shapes_the_live_rig_reads(self):
        for base in self.kits:
            for part in ("Shirt", "Apron", "Cloak"):
                keys = self.mesh(base, part)[4]
                for name in ("ClothBack", "ClothLeft", "ClothRight"):
                    self.assertGreater(np.linalg.norm(keys[name], axis=1).max(), 0.001, (base, part, name))
                    self.assertLess(np.linalg.norm(keys[name], axis=1).max(), 0.03, (base, part, name))

    def test_face_controls_do_not_undo_garment_fitting(self):
        for base in self.kits:
            for part in ("Shirt", "Vest", "Apron", "Cloak", "Trousers", "Boots"):
                keys = self.mesh(base, part)[4]
                for slider in ("NoseSize", "EyeSize", "JawWidth"):
                    for sign in ("+", "-"):
                        self.assertLess(np.linalg.norm(keys[slider + sign], axis=1).max(), 0.00001,
                                        (base, part, slider + sign))

    def test_idle_and_bending_keep_both_heel_and_toe_on_the_same_plane(self):
        for base in self.kits:
            for clip in ("Idle", "PickUp"):
                pose = Pose(KIT / f"kit_{base}.glb", clip)
                for at in pose.times(8):
                    for part in ("Boots", "Shoes"):
                        rest, moved = pose.skin_points(part, at)
                        sole = rest[:, 1] < rest[:, 1].min() + 0.015
                        reach = np.ptp(rest[sole, 2])
                        back = rest[sole, 2].min()
                        for side in (-1, 1):
                            heel = sole & (rest[:, 0] * side > 0) & (rest[:, 2] < back + reach * 0.35)
                            toe = sole & (rest[:, 0] * side > 0) & (rest[:, 2] > back + reach * 0.65)
                            self.assertTrue(heel.any() and toe.any(), (base, part, side))
                            self.assertLess(abs(moved[heel, 1].min() - moved[toe, 1].min()), 0.02,
                                            (base, part, clip, at, side))

    def test_stubble_fades_at_the_hairline(self):
        for base in self.kits:
            doc, blob, primitive, _co, _keys = self.mesh(base, "BeardStubble")
            alpha = np.array(accessor(doc, blob, primitive["attributes"]["COLOR_0"]))[:, 3]
            self.assertLess(alpha.min(), 0.05)
            self.assertGreater(alpha.max(), 0.95)

    def test_run_reaches_the_ground_and_retains_a_flight_phase(self):
        for base in self.kits:
            pose = Pose(KIT / f"kit_{base}.glb", "Run")
            floors = [pose.skin_points("Boots", at)[1][:, 1].min() for at in pose.times(32)]
            self.assertLess(abs(min(floors)), 0.02, base)
            self.assertGreater(max(floors) - min(floors), 0.05, base)

    def test_hanging_garments_follow_the_torso_and_independent_cloth_controls(self):
        for base in self.kits:
            for part in ("Vest", "Apron", "Cloak"):
                doc, blob, primitive, _co, _keys = self.mesh(base, part)
                mesh_id = next(i for i, m in enumerate(doc["meshes"]) if m["name"] == part)
                node = next(n for n in doc["nodes"] if n.get("mesh") == mesh_id)
                joints = [doc["nodes"][i]["name"] for i in doc["skins"][node["skin"]]["joints"]]
                weights = np.array(accessor(doc, blob, primitive["attributes"]["WEIGHTS_0"]))
                bones = np.array(accessor(doc, blob, primitive["attributes"]["JOINTS_0"]))
                used = {joints[i] for i in bones[weights > 0.001]}
                allowed = {"pelvis", "spine_01", "spine_02", "spine_03", "neck_01"}
                if part in ("Apron", "Cloak"):
                    allowed |= {"cloth_front", "cloth_back"}
                    self.assertTrue(used & {"cloth_front", "cloth_back"}, (base, part, used))
                if part == "Apron":
                    manifest = json.loads((KIT / f"kit_{base}.bones.json").read_text())
                    hip = dict(zip(manifest["bones"], manifest["rest_heads"]))["thigh_l"][1]
                    lower = _co[:, 1] < hip
                    carried = (weights * (bones == joints.index("cloth_front"))).sum(axis=1)
                    self.assertGreater(carried[lower].min(), 0.999, base)
                self.assertTrue(used <= allowed,
                                (base, part, used))

    def test_tunics_conceal_the_trousers_beneath_them(self):
        for base in self.kits:
            _doc, _blob, _primitive, co, keys = self.mesh(base, "Trousers")
            upper = co[:, 1] > np.quantile(co[:, 1], 0.8)
            for outfit, parts in self.spec["slots"]["outfit"].items():
                if "Shirt" in parts and "Trousers" in parts:
                    masked = co + keys["Hide." + outfit]
                    self.assertLess(np.linalg.norm(masked[upper][:, [0, 2]], axis=1).mean(),
                                    np.linalg.norm(co[upper][:, [0, 2]], axis=1).mean() * 0.4)

    def test_tunic_conceals_the_skin_at_the_underarm_seam(self):
        for base in self.kits:
            doc, blob, primitive, co, keys = self.mesh(base, "Body")
            mesh_id = next(i for i, m in enumerate(doc["meshes"]) if m["name"] == "Body")
            node = next(n for n in doc["nodes"] if n.get("mesh") == mesh_id)
            joints = [doc["nodes"][i]["name"] for i in doc["skins"][node["skin"]]["joints"]]
            weights = np.array(accessor(doc, blob, primitive["attributes"]["WEIGHTS_0"]))
            bones = np.array(accessor(doc, blob, primitive["attributes"]["JOINTS_0"]))
            bound = np.array([joints[i].startswith("upperarm_") for i in bones.ravel()]).reshape(bones.shape)
            manifest = json.loads((KIT / f"kit_{base}.bones.json").read_text())
            heads = dict(zip(manifest["bones"], manifest["rest_heads"]))
            underarm = ((weights * bound).sum(axis=1) > 0.35) & (co[:, 1] > heads["lowerarm_l"][1] + 0.08) \
                & (co[:, 1] < heads["neck_01"][1] - 0.055)
            self.assertTrue(underarm.any(), base)
            self.assertGreater(np.linalg.norm(keys["Hide.frontier"][underarm], axis=1).min(), 0.01, base)

    def test_apron_hem_keeps_its_width_instead_of_wrapping_each_thigh(self):
        for base in self.kits:
            for clip in ("Idle", "Walk", "PickUp", "HugWalk", "Sleep"):
                rest, posed = Pose(KIT / f"kit_{base}.glb", clip).skin_points("Apron", 0.27)
                hem = posed[rest[:, 1] < np.quantile(rest[:, 1], 0.1)]
                self.assertGreater(np.ptp(hem[:, 0]), np.ptp(posed[:, 0]) * 0.7, (base, clip))

    def test_cloak_hanging_panel_does_not_grow_teeth_between_adjacent_rows(self):
        for base in self.kits:
            doc, blob, primitive, co, keys = self.mesh(base, "Cloak")
            manifest = json.loads((KIT / f"kit_{base}.bones.json").read_text())
            hip = dict(zip(manifest["bones"], manifest["rest_heads"]))["thigh_l"][1]
            faces = np.array(accessor(doc, blob, primitive["indices"])).reshape(-1, 3)
            edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
            edges = edges[np.all(co[edges, 1] < hip + 0.04, axis=1)]
            self.assertGreater(len(edges), 0, base)
            for name, recipe in self.spec["body_archetypes"].items():
                delta = self.shaped(co, keys, recipe) - co
                stretch = (delta[edges[:, 1]] - delta[edges[:, 0]])[:, [0, 2]]
                self.assertLess(np.linalg.norm(stretch, axis=1).max(), 0.025, (base, name))

    def test_apron_stays_in_front_of_the_tunic_hem_and_trousers_in_real_poses(self):
        for base in self.kits:
            hip = json.loads((KIT / f"kit_{base}.bones.json").read_text())
            hip = dict(zip(hip["bones"], hip["rest_heads"]))["thigh_l"][1]
            for clip in ("Idle", "Walk", "PickUp", "HugWalk", "Sleep"):
                pose = Pose(KIT / f"kit_{base}.glb", clip)
                doc, blob = self.kits[base]
                skin = doc["skins"][0]
                joint = next(i for i, node in enumerate(skin["joints"]) if doc["nodes"][node]["name"] == "cloth_front")
                inverse = np.array(accessor(doc, blob, skin["inverseBindMatrices"])[joint]).reshape(4, 4).T
                for at in pose.times(4):
                    rest, apron = pose.skin_points("Apron", at)
                    _origin, spin, size = pose.transform(at, "cloth_front")
                    frame = np.array([turned(spin, axis) for axis in np.eye(3)]).T * size @ inverse[:3, :3]
                    # Clearance is along the panel's posed normal, including recumbent poses.
                    points = apron[rest[:, 1] < hip] @ frame
                    for part in ("Shirt", "Trousers"):
                        doc, blob, primitive, co, keys = self.mesh(base, part)
                        masked = co + keys["Hide.frontier_apron"]
                        moved = pose.skin_points(part, at, masked)[1]
                        faces = np.array(accessor(doc, blob, primitive["indices"])).reshape(-1, 3)
                        if part == "Shirt":
                            faces = faces[np.all(co[faces, 1] < hip + 0.08, axis=1)]
                        clearance = front_clearance(points, moved[faces] @ frame)
                        if len(clearance):
                            self.assertGreater(clearance.min(), 0.001,
                                               (base, clip, at, part, float(clearance.min())))

    def test_apron_mask_preserves_the_tunic_shell_over_the_waist(self):
        for base in self.kits:
            _doc, _blob, _primitive, co, keys = self.mesh(base, "Shirt")
            manifest = json.loads((KIT / f"kit_{base}.bones.json").read_text())
            hip = dict(zip(manifest["bones"], manifest["rest_heads"]))["thigh_l"][1]
            shell = co[:, 1] > hip + 0.045
            self.assertLess(np.linalg.norm(keys["Hide.frontier_apron"][shell], axis=1).max(), 0.00001, base)

    def test_rebuilt_assets_name_and_hash_every_input_in_this_checkout(self):
        for base in self.kits:
            manifest = json.loads((KIT / f"kit_{base}.glb.provenance.json").read_text())
            self.assertIn("pending owner", manifest["approval"])
            for name, expected in manifest["inputs_sha256"].items():
                self.assertEqual(expected, hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), (base, name))


def front_clearance(points, triangles):
    """Front depth against the actual triangles whose XY projection contains each point."""
    a, b, c = (triangles[:, i] for i in range(3))
    denom = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    valid = abs(denom) > 1e-10
    a, b, c, denom = a[valid], b[valid], c[valid], denom[valid]
    x, y = points[:, 0, None], points[:, 1, None]
    u = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / denom
    v = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / denom
    inside = (u >= 0) & (v >= 0) & (u + v <= 1)
    depth = np.where(inside, u * a[:, 2] + v * b[:, 2] + (1 - u - v) * c[:, 2], -np.inf).max(axis=1)
    return points[np.isfinite(depth), 2] - depth[np.isfinite(depth)]


if __name__ == "__main__":
    unittest.main()
