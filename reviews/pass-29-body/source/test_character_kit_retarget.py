"""The kit's clip and socket bridge still describes the two real rigs.

This runs without Blender (no bpy, no mathutils) and reads the shipped assets,
so a rebuilt folk rig, a renamed kit bone or a kit GLB built without its clips
fails here rather than as a pawn that does not move.

The carried clips are read back out of both GLBs and checked against each
other: a bone has to point the way the folk's does in every clip and keep its
own bone's length. That is what a mangled copy looks like when it goes wrong --
a skeleton that comes apart into joints sitting away from their bones -- and it
is invisible in a clip count.
"""

from __future__ import annotations

import math
import re
import struct
import unittest
from pathlib import Path

import runpy
from character_kit_glb import accessor, glb_chunks

ROOT = Path(__file__).resolve().parents[2]
RETARGET = runpy.run_path(str(ROOT / "scripts/asset_pipeline/kit_retarget.py"))
FOLK = ROOT / "assets" / "characters" / "frontier_folk" / "frontier_folk.glb"
KIT = ROOT / "assets" / "characters" / "kit"


class RetargetPlanTests(unittest.TestCase):
    def test_the_map_matches_both_real_rigs(self):
        RETARGET["plan_check"](RETARGET["bone_names"](FOLK),
                               self.kit_bones(), RETARGET["folk_clip_names"](FOLK))

    def test_the_folk_carry_exactly_the_clips_the_client_asks_for(self):
        self.assertEqual(sorted(RETARGET["CLIPS"]), sorted(RETARGET["folk_clip_names"](FOLK)))

    def test_the_client_still_names_those_clips(self):
        named = set(re.findall(r'public const string \w+ = "([^"]+)"',
                               (ROOT / "clients/godot-csharp/FigureClips.cs").read_text()))
        # An animal's one action clip is not a person's clip.
        self.assertEqual(sorted(RETARGET["CLIPS"]), sorted(named - {"Action"}))

    def test_a_renamed_kit_bone_is_rejected(self):
        bones = self.kit_bones() - {"hand_r"}
        with self.assertRaises(ValueError):
            RETARGET["plan_check"](RETARGET["bone_names"](FOLK), bones, RETARGET["folk_clip_names"](FOLK))

    def test_a_dropped_folk_bone_is_rejected(self):
        with self.assertRaises(ValueError):
            RETARGET["plan_check"](RETARGET["bone_names"](FOLK) | {"Elbow.L"},
                                   self.kit_bones(), RETARGET["folk_clip_names"](FOLK))

    def test_two_folk_bones_on_one_kit_bone_is_rejected(self):
        original = RETARGET["BONE_MAP"]
        try:
            RETARGET["BONE_MAP"]["Neck"] = ("head",)
            with self.assertRaises(ValueError):
                RETARGET["plan_check"](RETARGET["bone_names"](FOLK), self.kit_bones(),
                                       RETARGET["folk_clip_names"](FOLK))
        finally:
            RETARGET["BONE_MAP"].clear()
            RETARGET["BONE_MAP"].update(original)

    def test_a_missing_clip_is_rejected(self):
        with self.assertRaises(ValueError):
            RETARGET["plan_check"](RETARGET["bone_names"](FOLK), self.kit_bones(),
                                   [name for name in RETARGET["folk_clip_names"](FOLK) if name != "Sleep"])

    def test_the_built_kits_carry_every_clip_and_socket(self):
        """The bridge's own output: until both bases are rebuilt with it, a
        pawn built from the kit would ask for clips the kit does not have."""
        wanted = sorted(RETARGET["CLIPS"])
        sockets = sorted(RETARGET["SOCKETS"])
        for base in ("male", "female"):
            glb = KIT / f"kit_{base}.glb"
            document = RETARGET["gltf_json"](glb)
            self.assertEqual(wanted, sorted(animation["name"] for animation in document["animations"]),
                             f"{glb.name} does not carry the client's clips")
            names = {node.get("name") for node in document["nodes"]}
            for socket in sockets:
                self.assertIn(socket, names, f"{glb.name} has no {socket} socket")

    def test_the_kit_sockets_hang_off_the_kits_own_bones(self):
        document = RETARGET["gltf_json"](KIT / "kit_male.glb")
        parent = {child: node.get("name") for node in document["nodes"]
                  for child in node.get("children", [])}
        for socket, (kit_bone, _how) in RETARGET["SOCKETS"].items():
            index = [i for i, node in enumerate(document["nodes"]) if node.get("name") == socket]
            self.assertEqual(1, len(index), f"{KIT / 'kit_male.glb'} has no single {socket} node")
            self.assertEqual(kit_bone, parent[index[0]], f"{socket} does not ride {kit_bone}")

    def test_a_tool_sits_in_the_hand_and_the_loads_on_the_body(self):
        """The client hangs a held tool at the grip and a hauled load at the
        shoulder and the belly, in figure units, so the sockets must be there
        rather than merely somewhere on the asset."""
        document = RETARGET["gltf_json"](KIT / "kit_male.glb")
        body = next(mesh for mesh in document["meshes"] if mesh["name"] == "Body")
        accessor = document["accessors"][body["primitives"][0]["attributes"]["POSITION"]]
        height = accessor["max"][1] - accessor["min"][1]
        base = accessor["min"][1]
        where = {socket: place(document, socket) for socket in ("Grip", "Shoulder", "Hug")}
        # glTF is Y-up, facing +Z: [0] is the figure's own right, [1] its height.
        # A tool is gripped in the right hand, at chest height.
        self.assertLess(where["Grip"][0], -0.2, "the grip is not on the right hand")
        self.assertLess(where["Grip"][1], base + height * 0.8)
        self.assertGreater(where["Grip"][1], base + height * 0.4)
        # A load rides the right shoulder, above the belly load, both on the body.
        self.assertGreater(where["Shoulder"][1], base + height * 0.8)
        self.assertGreater(where["Hug"][1], base + height * 0.5)
        self.assertLess(where["Hug"][1], where["Shoulder"][1])
        for socket, at in where.items():
            self.assertTrue(base - 0.05 < at[1] < base + height + 0.05, f"{socket} is off the body")

    def test_the_kit_stands_at_the_height_the_client_measures_in(self):
        """HeldSizes draws every held shape and CarriedLoad every load in
        figure units, so the kit's own root scale must put its body at that
        same standing height; otherwise a kit pawn's axe is the wrong size."""
        import json
        import re
        figure_height = float(re.search(r"FigureHeight = ([\d.]+)f",
                                        (ROOT / "clients/godot-csharp/HeldSizes.cs").read_text()).group(1))
        scale = json.loads((KIT / "character_kit.spec.json").read_text())["game_scale"]
        document = RETARGET["gltf_json"](KIT / "kit_male.glb")
        body = next(mesh for mesh in document["meshes"] if mesh["name"] == "Body")
        accessor = document["accessors"][body["primitives"][0]["attributes"]["POSITION"]]
        self.assertAlmostEqual(figure_height, accessor["max"][1] * scale, delta=0.02)

    def test_the_kit_carries_the_bone_manifest_every_slider_needs(self):
        import json
        bones = RETARGET["bone_names"](KIT / "kit_male.glb")
        manifest = json.loads((KIT / "kit_male.bones.json").read_text())
        self.assertEqual(sorted(manifest["bones"]), sorted(bones))
        self.assertEqual(sorted(manifest["bones"]), sorted(self.kit_bones()))

    def test_every_clip_aims_the_kit_the_way_the_folk_aim_it(self):
        """The point of the retarget: in every clip the kit's limbs point where
        the folk's point, frame for frame. The clip's own two rigs differ in
        proportion, so this is a direction and not a position, and the tolerance
        is the difference the two stances already have (about 11 degrees here).
        """
        for clip in RETARGET["CLIPS"]:
            folk = Pose(FOLK, clip)
            kit = Pose(KIT / "kit_male.glb", clip)
            for folk_bone, kit_bone, folk_child, kit_child in LIMBS:
                worst = 0.0
                for at in folk.times():
                    apart = apart_by(folk.way(at, folk_bone, folk_child),
                                     kit.way(at, kit_bone, kit_child))
                    worst = max(worst, apart)
                self.assertLess(worst, 25.0,
                                f"{clip}: {kit_bone} points {worst:.0f} degrees away from {folk_bone}")

    def test_no_clip_pulls_a_joint_off_its_bone(self):
        """A joint only leaves its bone's length where the transfer says it may
        travel: the folk's own body shift, hip shift and shoulder shrug, carried
        onto a bone whose parents play the same part of the body. Everything else
        stays put, which is what keeps the kit's own skeleton. Without this rule
        the copy tore: a hand sat 0.46 body heights off its wrist.
        """
        folk_parents = bone_parents(RETARGET["gltf_json"](FOLK))
        for base in ("male", "female"):
            glb = KIT / f"kit_{base}.glb"
            kit_parents = bone_parents(RETARGET["gltf_json"](glb))
            for clip in RETARGET["CLIPS"]:
                pose = Pose(glb, clip)
                for joint in pose.joints:
                    drift = pose.drift(joint) / pose.height
                    if carries_shift(folk_parents, kit_parents, joint):
                        self.assertLess(drift, 0.25, f"{base}/{clip}: {joint} travels {drift:.2f} body heights")
                    else:
                        self.assertLess(drift, 0.005,
                                        f"{base}/{clip}: {joint} left its own bone by {drift:.3f} body heights")

    def test_the_kit_stands_on_the_ground_in_every_grounded_clip(self):
        """A foot has to reach the ground in the clips that stand on it: a
        figure that hovers, or sinks, is the first thing a player sees. The
        clips left out are the ones that leave the ground by design -- Sleep,
        Sprawl, a lunging Punch or sword swing -- and a foot sliding across the
        ground while it is planted reads as skating, so the kit is held to the
        clip it was copied from.
        """
        grounded = ("Idle", "Walk", "Run", "Talk", "Craft", "Eat", "Chop", "Mine",
                    "Shoot", "RecieveHit", "PickUp", "HugIdle", "HugWalk",
                    "ShoulderIdle", "ShoulderWalk")
        for clip in grounded:
            pose = Pose(KIT / "kit_male.glb", clip)
            # The shoe, not an ankle or ball joint inside it, touches the floor.
            lowest = min(pose.skin_points("Boots", at)[1][:, 1].min() for at in pose.times())
            self.assertLess(lowest - pose.ground, 0.05 * pose.height,
                            f"{clip} leaves every foot {lowest - pose.ground:.3f} off the ground")
            self.assertGreater(lowest - pose.ground, -0.03 * pose.height,
                               f"{clip} pushes a foot {lowest - pose.ground:.3f} through the ground")
            if clip not in ("Walk", "Run", "HugWalk", "ShoulderWalk"):
                continue
            theirs = Pose(FOLK, clip)
            for folk_bone, kit_bone in (("Foot.L", "ball_l"), ("Foot.R", "ball_r")):
                self.assertLess(pose.slip(kit_bone), 2 * theirs.slip(folk_bone),
                                f"{clip}: {kit_bone} slides twice as far as the folk's {folk_bone}")

    def test_idle_does_not_carry_the_folk_arm_roll_into_makehuman_skin(self):
        # The relaxed reference lowers an A-pose arm; it must not wind the
        # upper arm around its length and fold the deltoid into a sleeve edge.
        for base in ("male", "female"):
            pose = Pose(KIT / f"kit_{base}.glb", "Idle")
            tracks = pose.tracks
            for bone in ("upperarm_l", "upperarm_r"):
                pose.tracks = tracks
                _at, spin, _scale = pose.transform(0, bone)
                pose.tracks = {}
                _at, rest, _scale = pose.transform(0, bone)
                axis = turned(rest, (0, 1, 0))
                inverse = (*(-v for v in rest[:3]), rest[3])
                delta = multiplied(spin, inverse)
                along = sum(a * b for a, b in zip(delta[:3], axis))
                twist = normalized((*[along * a for a in axis], delta[3]))
                angle = math.degrees(2 * math.acos(min(1, abs(twist[3]))))
                self.assertLess(angle, 1, (base, bone, angle))

    def kit_bones(self):
        import json
        return set(json.loads((KIT / "kit_male.bones.json").read_text())["bones"])


# The parts that play the same part of the body on both rigs, as a segment
# from a bone to the joint at its far end. The folk's shin is left out on
# purpose: their Foot bones hang off the root and are planted by IK, so the
# folk have no joint at the shin's far end to aim at.
LIMBS = (
    ("UpperArm.L", "upperarm_l", "LowerArm.L", "lowerarm_l"),
    ("UpperArm.R", "upperarm_r", "LowerArm.R", "lowerarm_r"),
    ("LowerArm.L", "lowerarm_l", "Fist.L", "hand_l"),
    ("LowerArm.R", "lowerarm_r", "Fist.R", "hand_r"),
    ("UpperLeg.L", "thigh_l", "LowerLeg.L", "calf_l"),
    ("UpperLeg.R", "thigh_r", "LowerLeg.R", "calf_r"),
    ("Torso", "spine_03", "Neck", "neck_01"),
)


def normalized(quaternion):
    size = math.sqrt(sum(value * value for value in quaternion)) or 1.0
    return tuple(value / size for value in quaternion)


def turned(quaternion, vector):
    """[vector] rotated by [quaternion]."""
    x, y, z, w = quaternion
    vx, vy, vz = vector
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def multiplied(first, second):
    """[first] then [second]."""
    ax, ay, az, aw = first
    bx, by, bz, bw = second
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def blended(times, values, at, spin):
    """A channel's value at time [at], between the keys around it. Rotations
    are mixed the short way round, or a key that flips its own sign would send
    the clip through a full turn between two frames."""
    when = [key[0] for key in times]
    if at <= when[0]:
        return tuple(values[0])
    if at >= when[-1]:
        return tuple(values[-1])
    for step in range(1, len(when)):
        if at <= when[step]:
            span = when[step] - when[step - 1]
            part = (at - when[step - 1]) / span if span else 0.0
            first, second = list(values[step - 1]), list(values[step])
            if spin and sum(a * b for a, b in zip(first, second)) < 0:
                second = [-value for value in second]
            mixed = [a + part * (b - a) for a, b in zip(first, second)]
            return normalized(mixed) if spin else tuple(mixed)
    return tuple(values[-1])


class Pose:
    """One clip of a shipped .glb: where a joint sits and which way its bone
    points, with its parents applied, without Blender."""

    def __init__(self, asset: Path, clip: str):
        self.document, self.blob = glb_chunks(asset)
        self.nodes = self.document["nodes"]
        self.index = {node.get("name"): at for at, node in enumerate(self.nodes)}
        self.parent = {child: at for at, node in enumerate(self.nodes)
                       for child in node.get("children", [])}
        animation = next(one for one in self.document["animations"] if one["name"] == clip)
        self.tracks = {}
        for channel in animation["channels"]:
            sampler = animation["samplers"][channel["sampler"]]
            name = self.nodes[channel["target"]["node"]].get("name")
            self.tracks[(name, channel["target"]["path"])] = (
                accessor(self.document, self.blob, sampler["input"]),
                accessor(self.document, self.blob, sampler["output"]))
        starts = [times[0][0] for times, _ in self.tracks.values()]
        ends = [times[-1][0] for times, _ in self.tracks.values()]
        self.start, self.end = min(starts), max(ends)
        body = next(mesh for mesh in self.document["meshes"] if mesh["name"] == "Body")
        corner = self.document["accessors"][body["primitives"][0]["attributes"]["POSITION"]]
        self.ground, self.height = corner["min"][1], corner["max"][1] - corner["min"][1]
        self.joints = {node.get("name") for skin in self.document["skins"]
                       for node in [self.nodes[at] for at in skin["joints"]]}

    def times(self, count: int = 24) -> list:
        return [self.start + (self.end - self.start) * at / count for at in range(count + 1)]

    def at(self, name: str, path: str, when: float, fallback):
        track = self.tracks.get((name, path))
        if track is None:
            return tuple(fallback)
        return blended(track[0], track[1], when, path == "rotation")

    def chain(self, name: str) -> list:
        at = self.index[name]
        names = []
        while at is not None:
            names.append(self.nodes[at].get("name"))
            at = self.parent.get(at)
        return list(reversed(names))

    def transform(self, when: float, name: str):
        """Where [name]'s joint sits and which way its bone points. Both rigs
        were exported by the same tool, so a bone points along its own +Y on
        each, and a node's scale reaches its children's offsets."""
        place = [0.0, 0.0, 0.0]
        spin = (0.0, 0.0, 0.0, 1.0)
        size = 1.0
        for step in self.chain(name):
            node = self.nodes[self.index[step]]
            shift = self.at(step, "translation", when, node.get("translation", [0, 0, 0]))
            offset = turned(spin, [value * size for value in shift])
            place = [was + now for was, now in zip(place, offset)]
            scale = node.get("scale", [1, 1, 1])
            size *= sum(scale) / 3.0 if isinstance(scale, list) else scale
            spin = multiplied(spin, self.at(step, "rotation", when, node.get("rotation", [0, 0, 0, 1])))
        return place, spin, size

    def state(self, when: float, name: str):
        place, spin, _size = self.transform(when, name)
        return place, turned(spin, (0.0, 1.0, 0.0))

    def skin_points(self, part: str, when: float, positions=None):
        """Real mesh vertices through the clip's skin, including bind poses."""
        import numpy as np
        mesh_id = next(i for i, m in enumerate(self.document["meshes"]) if m["name"] == part)
        node = next(n for n in self.nodes if n.get("mesh") == mesh_id)
        primitive = self.document["meshes"][mesh_id]["primitives"][0]
        arrays = {name: np.array(accessor(self.document, self.blob, at))
                  for name, at in primitive["attributes"].items()}
        skin = self.document["skins"][node["skin"]]
        bind = np.array(accessor(self.document, self.blob, skin["inverseBindMatrices"]))
        matrices = []
        for joint, inverse in zip(skin["joints"], bind):
            place, spin, size = self.transform(when, self.nodes[joint]["name"])
            pose = np.eye(4)
            pose[:3, :3] = np.array([turned(spin, axis) for axis in np.eye(3)]).T * size
            pose[:3, 3] = place
            matrices.append(pose @ inverse.reshape(4, 4).T)
        matrices = np.array(matrices)
        vertices = np.c_[arrays["POSITION"] if positions is None else positions, np.ones(len(arrays["POSITION"]))]
        moved = np.zeros_like(arrays["POSITION"])
        for slot in range(4):
            moved += np.einsum("nij,nj->ni", matrices[arrays["JOINTS_0"][:, slot]], vertices)[:, :3] \
                * arrays["WEIGHTS_0"][:, slot, None]
        return arrays["POSITION"], moved

    def lowest(self, name: str, when: float = None) -> float:
        return min(self.state(at, name)[0][1] for at in (self.times() if when is None else [when]))

    def way(self, when: float, bone: str, child: str):
        """Which way the segment from [bone] to [child] points."""
        here = self.state(when, bone)[0]
        there = self.state(when, child)[0]
        span = [there[at] - here[at] for at in range(3)]
        size = math.sqrt(sum(value * value for value in span)) or 1.0
        return [value / size for value in span]

    def drift(self, name: str) -> float:
        """The furthest this joint's own offset from its parent travels from
        the offset it rests at."""
        track = self.tracks.get((name, "translation"))
        if track is None:
            return 0.0
        rest = self.nodes[self.index[name]].get("translation", [0, 0, 0])
        return max(max(abs(value[at] - rest[at]) for at in range(3))
                   for value in track[1])

    def slip(self, name: str) -> float:
        """How far [name] slides sideways while it is at its lowest, which is
        the stretch of the clip a player reads as a planted foot."""
        places = [(self.state(at, name)[0][1], self.state(at, name)[0]) for at in self.times(48)]
        floor = min(place[0] for place in places)
        touching = [place[1] for place in places if place[0] < floor + 0.02 * self.height]
        return sum(math.dist(first, last) for first, last in zip(touching, touching[1:]))


def apart_by(first, second):
    """The angle between two directions, in degrees."""
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(first, second))))
    return math.degrees(math.acos(dot))


def bone_parents(document):
    """Bone name -> the bone it hangs off, for the bones in a skin; None where
    it hangs off the armature instead, which is not a bone."""
    nodes = document["nodes"]
    joints = {nodes[at].get("name") for skin in document["skins"] for at in skin["joints"]}
    out = {}
    for node in nodes:
        for child in node.get("children", []):
            if nodes[child].get("name") in joints:
                upper = node.get("name")
                out[nodes[child].get("name")] = upper if upper in joints else None
    return out


def carries_shift(folk_parents, kit_parents, kit_bone: str) -> bool:
    """Whether the kit bone is one the transfer carries the folk's own shift
    onto: the two bones have to hang off the same part of the body.

    The folk's trunk root, their feet and their IK poles all hang off the
    armature itself, and their trunk root sits beside the armature's own root
    bone rather than under it, so that whole level counts as one.
    """
    folk_bone = next((folk for folk, targets in RETARGET["BONE_MAP"].items()
                      if kit_bone in targets), None)
    if folk_bone is None:
        return False
    folk_up = folk_parents.get(folk_bone)
    kit_up = kit_parents.get(kit_bone)
    if folk_up is None:
        return kit_up is None or kit_up == RETARGET["BONE_MAP"]["Root"][0]
    return kit_up in RETARGET["BONE_MAP"].get(folk_up, ())


def place(document, name):
    """Where a node sits in the asset, with its parents' transforms applied."""
    nodes = document["nodes"]
    parent = {child: index for index, node in enumerate(nodes) for child in node.get("children", [])}
    at = next(index for index, node in enumerate(nodes) if node.get("name") == name)
    chain = []
    while at is not None:
        chain.append(at)
        at = parent.get(at)
    rotation = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    shift = [0, 0, 0]
    for at in reversed(chain):
        local = local_matrix(nodes[at])
        shift = [shift[r] + sum(rotation[r][k] * local[1][k] for k in range(3)) for r in range(3)]
        rotation = [[sum(rotation[r][k] * local[0][k][c] for k in range(3)) for c in range(3)] for r in range(3)]
    return shift


def local_matrix(node):
    """A glTF node's own rotation and scale, and where it puts its origin."""
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    scale = node.get("scale", [1, 1, 1])
    columns = [
        [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)],
        [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)],
        [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)],
    ]
    return ([[columns[c][r] * scale[c] for c in range(3)] for r in range(3)],
            list(node.get("translation", [0, 0, 0])))


if __name__ == "__main__":
    unittest.main()
