"""Carry the frontier folk's clips and sockets onto the character kit's rig.

The folk (assets/characters/frontier_folk/) carry the nineteen clips the Godot
client asks for (FigureClips.cs) on a 32-bone rig. The kit
(assets/characters/kit/) stands on MakeHuman's 53-bone game rig with Idle and
Walk only and no sockets, so a real pawn cannot wear it yet (#4376).

Every folk clip is one pose per frame on every bone, so the kit copies the
motion instead of re-authoring nineteen clips:

* each kit bone takes the folk bone that plays the same part of the body
  (`BONE_MAP`), and receives that bone's own turn and shift measured against
  *its parent*, never against the world: a world delta carries every parent's
  movement a second time, and a skeleton transferred that way comes apart into
  joints that no longer sit at their bone's length;
* the movement is measured from each rig's own *standing* pose, never from its
  rest pose: MakeHuman stands in an A-pose and the folk in a near T-pose, so
  moving relative to rest would leave the arms out wide. The reference is the
  folk's Idle frame 0 against the kit's relaxed standing pose (Poser.relax);
* a bone's rest frame points a different way on each rig (different bone
  lengths, rolls and up axis), so each delta is carried through the rotation
  that maps the folk bone's rest frame onto the kit bone's (`Transporter.frame`).
  Without that, elbows and knees bend sideways;
* a shift is carried only between bones whose parents play the same part of the
  body (`Transporter.carries_shift`). The folk plant their feet with IK, so
  their `Foot` bones hang off the armature beside the trunk and one foot's shift
  is a whole leg's reach; copied onto the kit's foot -- a child of a calf -- it
  would pull the ankle off the leg. Foot rotation preserves the sole plane;
  the live kit still needs IK for horizontal planting on different physiques.

Two facts have to be true for the copy to be honest, and both are checked by
`test_character_kit_retarget.py` without Blender:

* every mapped name exists on the rig it names, no kit bone is mapped twice,
  and no folk bone is dropped without a written reason (`plan_check`);
* the folk asset carries exactly the clips the client asks for.

Sockets are carried the same way, from the shipped folk GLB rather than from
retyped numbers: the folk's `Grip`, `Shoulder` and `Hug` nodes are read out of
their own asset, moved onto the kit joint that plays the same part with the
same frame correction, and re-parented to it. A held tool and a hauled load
then hang where they hang on the folk.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLK_ASSET = ROOT / "assets" / "characters" / "frontier_folk" / "frontier_folk.glb"

# The folk clips were authored at 24 fps (Walk is 30 frames over 1.25 s), and
# the kit is built at the same rate so every frame lands on a whole key and a
# clip keeps its exact length. FigureClips paces strides, swings and
# acknowledgements by seconds, so the durations must not change.
FPS = 24

# Both rigs are brought to the same standing pose before any delta is taken:
# the folk's Idle frame 0 against the kit's Poser.relax().
REFERENCE_CLIP = "Idle"
REFERENCE_FRAME = 0

# Every clip the client can ask a person for (clients/godot-csharp/FigureClips.cs).
CLIPS = (
    "Idle", "Walk", "Run", "PickUp", "Punch", "RecieveHit", "Sword_Attack", "Chop",
    "Mine", "Craft", "Shoot", "Eat", "Talk", "Sleep", "Sprawl",
    "ShoulderWalk", "ShoulderIdle", "HugWalk", "HugIdle",
)

# folk bone -> the kit bone(s) that play the same part of the body. The folk
# fist is one bone with two phalanges; the kit has four fingers, so each
# phalanx drives all four.
BONE_MAP = {
    "Root": ("Root",),
    "Body": ("pelvis",),
    "Hips": ("spine_01",),
    "Abdomen": ("spine_02",),
    "Torso": ("spine_03",),
    "Neck": ("neck_01",),
    "Head": ("head",),
    "Shoulder.L": ("clavicle_l",),
    "Shoulder.R": ("clavicle_r",),
    "UpperArm.L": ("upperarm_l",),
    "UpperArm.R": ("upperarm_r",),
    "LowerArm.L": ("lowerarm_l",),
    "LowerArm.R": ("lowerarm_r",),
    "Fist.L": ("hand_l",),
    "Fist.R": ("hand_r",),
    "Fist1.L": ("index_01_l", "middle_01_l", "ring_01_l", "pinky_01_l"),
    "Fist1.R": ("index_01_r", "middle_01_r", "ring_01_r", "pinky_01_r"),
    "Fist2.L": ("index_02_l", "middle_02_l", "ring_02_l", "pinky_02_l"),
    "Fist2.R": ("index_02_r", "middle_02_r", "ring_02_r", "pinky_02_r"),
    "Thumb1.L": ("thumb_01_l",),
    "Thumb1.R": ("thumb_01_r",),
    "Thumb2.L": ("thumb_02_l",),
    "Thumb2.R": ("thumb_02_r",),
    "UpperLeg.L": ("thigh_l",),
    "UpperLeg.R": ("thigh_r",),
    "LowerLeg.L": ("calf_l",),
    "LowerLeg.R": ("calf_r",),
    "Foot.L": ("foot_l",),
    "Foot.R": ("foot_r",),
}

# Folk bones with no kit bone doing the same job. Named so a rig change that
# adds or renames a folk bone fails plan_check instead of dropping it quietly.
SKIPPED = {
    "Weapon.R": "the kit holds a tool through its Grip socket, not a weapon bone",
    "PoleTarget.L": "the folk rig's own IK helper; the kit's leg chain is plain FK",
    "PoleTarget.R": "the folk rig's own IK helper; the kit's leg chain is plain FK",
}

# name -> the kit bone a socket hangs off, and how its place on the body is
# read. A socket is a node the client hangs a held tool or a hauled load from,
# and the client's own code measures it in figure units, so it must sit in the
# hand and on the body, not near them.
#
#   hand  in the right fist, a little down the hand bone from the wrist
#   body  a place on the body, carried as a fraction of standing height
#
# The folk asset's own socket offsets cannot be copied across: Blender parents
# a node to the *tail* of a bone and the two assets record their offsets in
# their own rigs' frames, so a copied offset lands metres off the body. The
# body fractions below are the folk's own authored placement
# (LOAD_SOCKETS in build_frontier_folk.py) measured against their standing
# height: the right shoulder sits 88% up, 13% to the right and 2% forward; the
# hugged load 63% up, 2% right and 16% forward, in front of the belly.
SOCKETS = {
    "Grip": ("hand_r", "hand"),
    "Shoulder": ("spine_03", "body"),
    "Hug": ("spine_03", "body"),
}
BODY_SOCKETS = {
    # name: (up, right, forward) as fractions of standing height.
    "Shoulder": (0.878, -0.132, -0.019),
    "Hug": (0.627, -0.024, -0.163),
}
# How far down the hand bone a held tool is gripped, as a fraction of that
# bone's own length: in the middle of the fist, not at the wrist.
GRIP_IN_HAND = 0.5
# The tool's axes in the hand bone's own frame (Blender bone space, where +Y
# runs from the wrist to the fingers). The client's held meshes run their
# length up their own +Y and their working edge along their -Z, so the haft
# crosses the palm instead of running along the fingers and the edge faces
# away from the fist.
GRIP_BASIS = ((1, 0, 0), (0, 0, 1), (0, -1, 0))


def gltf_json(path: Path) -> dict:
    """The JSON chunk of a .glb, without reading the binary payload.

    A .glb is a 12-byte header, then chunks of (length, type, data); the first
    chunk is always the JSON document.
    """
    with path.open("rb") as handle:
        header = handle.read(12)
        if header[:4] != b"glTF":
            raise ValueError(f"{path} is not a binary glTF file")
        length, kind = struct.unpack("<I4s", handle.read(8))
        if kind != b"JSON":
            raise ValueError(f"{path} does not start with a JSON chunk")
        return json.loads(handle.read(length))


def folk_clip_names(path: Path = FOLK_ASSET) -> list:
    return [animation["name"] for animation in gltf_json(path).get("animations", [])]


def bone_names(path: Path) -> set:
    """The joint names of a .glb's (single) skin."""
    document = gltf_json(path)
    skin = document["skins"][0]
    return {document["nodes"][index]["name"] for index in skin["joints"]}


def plan_check(folk_bones, kit_bones, clips) -> None:
    """Fail loudly when the map no longer describes the two rigs.

    [folk_bones], [kit_bones] and [clips] come from the assets themselves, so a
    rebuilt or renamed rig cannot leave a clip half-transferred.
    """
    folk_bones, kit_bones, clips = set(folk_bones), set(kit_bones), set(clips)
    for name in CLIPS:
        if name not in clips:
            raise ValueError(f"the clip list names {name}, which the folk asset lacks")
    for name, targets in BONE_MAP.items():
        if name not in folk_bones:
            raise ValueError(f"BONE_MAP names folk bone {name}, which the folk rig lacks")
        for target in targets:
            if target not in kit_bones:
                raise ValueError(f"BONE_MAP sends {name} to kit bone {target}, which the kit lacks")
    carried = [target for targets in BONE_MAP.values() for target in targets]
    if len(carried) != len(set(carried)):
        raise ValueError("two folk bones drive the same kit bone")
    dropped = folk_bones - set(BONE_MAP) - set(SKIPPED)
    if dropped:
        raise ValueError(f"folk bones {sorted(dropped)} are neither mapped nor listed as skipped")
    if set(SKIPPED) & set(BONE_MAP):
        raise ValueError("a folk bone is both mapped and skipped")


# ------------------------------------------------------------------ Blender

def retarget(kit, poser, *, folk_glb: Path = FOLK_ASSET, fps: int = FPS, log=print):
    """Give the built kit its clips and sockets, from the shipped folk asset.

    [poser] is the kit's Poser holding its standing pose (Poser.relax): that is
    what the folk's Idle frame 0 maps onto. Runs inside the kit build, where the
    kit's armature and meshes exist.
    """
    import bpy  # noqa: PLC0415 - Blender-only module

    plan_check(bone_names(folk_glb), [b.name for b in kit.armature.data.bones],
               folk_clip_names(folk_glb))

    bpy.context.scene.render.fps = fps
    before_objects, before_actions = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=str(folk_glb))
    imported = [obj for obj in bpy.data.objects if obj not in before_objects]
    try:
        folk_armature = next(obj for obj in imported if obj.type == "ARMATURE")
        carrier = Transporter(kit, poser, folk_armature)
        # Read every clip out of the folk rig first. The kit's own actions are
        # written after the folk rig is gone: two actions cannot share a name,
        # and the client asks for these by name.
        sampled = [carrier.sample(name, clip_action(name)) for name in CLIPS]
        longest = max(frames for _name, frames, _keys in sampled)
        log(f"KIT retarget: {len(sampled)} clips from {folk_glb.name}, longest {longest} frames")
    finally:
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
        for action in [a for a in bpy.data.actions if a not in before_actions]:
            bpy.data.actions.remove(action)
    for name, _frames, keys in sampled:
        carrier.write(name, keys)
    for name, (kit_bone, how) in SOCKETS.items():
        at = carrier.socket(name, kit_bone, how)
        log(f"KIT socket {name} on {kit_bone} at {tuple(round(x, 3) for x in at)}")


def clip_action(name: str):
    """The imported folk action for [name]. The glTF importer names each
    animation after the clip, sometimes prefixed with the armature."""
    import bpy  # noqa: PLC0415
    matches = [action for action in bpy.data.actions
               if action.name == name or action.name.split("|")[-1] == name]
    if len(matches) != 1:
        raise ValueError(f"the imported folk asset gave {len(matches)} actions named {name}")
    return matches[0]


class Transporter:
    """Moves the folk rig's motion and sockets onto the kit's rig.

    Motion is carried one bone at a time, in the frame that bone is posed in:

    * the delta is read between the bone's frame under its *posed* parent and
      the same frame in the standing pose, so it holds that bone's own turn and
      shift and not its parents' as well;
    * the delta is turned onto the kit bone's own frame, because two bones that
      play the same part still point their local axes differently;
    * both rigs start from the same standing pose, and everything below is
      measured in an armature's own space, which is the space its bones are
      posed in. The two rigs were built by different tools at different
      scales, and a parent-relative delta survives that.
    """

    def __init__(self, kit, poser, folk_armature):
        import bpy  # noqa: PLC0415
        self.bpy = bpy
        self.kit = kit
        self.armature = kit.armature
        self.folk_armature = folk_armature
        self.order = self._parents_first()
        self.kit_local = {name: self._local(self.armature.data.bones[name])
                          for name in self.order}
        self.standing = {name: poser.basis[name].to_matrix().to_4x4() for name in self.order}
        self.kit_world = self.armature.matrix_world
        # How many kit metres stand in for one folk metre, so a step the folk
        # takes lands the same distance from the hips on a taller body.
        self.reach = self._heights(kit, folk_armature)
        # The kit's standing pose, and the folk's.
        self.reference = self._reference(poser)
        if self.folk_armature.animation_data is None:
            self.folk_armature.animation_data_create()
        self.source_reference = self._folk_pose(REFERENCE_CLIP, REFERENCE_FRAME)
        self.folk_world = folk_armature.matrix_world
        self.folk_parents = {bone.name: None if bone.parent is None else bone.parent.name
                             for bone in self.folk_armature.data.bones}
        # Each folk bone's standing frame in its parent's frame: what every
        # clip's delta is measured against.
        self.folk_standing = {name: self._standing(self.source_reference, name)
                              for name in self.folk_parents}

    # -- rig facts

    def _parents_first(self) -> list:
        """Every kit bone, a parent before its children. Blender promises no
        order over a rig's bones, and a bone posed before its parent would take
        its delta against a frame that had not moved yet."""
        order = []

        def walk(bone):
            order.append(bone.name)
            for child in bone.children:
                walk(child)

        for bone in self.armature.data.bones:
            if bone.parent is None:
                walk(bone)
        return order

    def _local(self, bone):
        """A bone's rest matrix against its parent's: the frame the rig poses
        that bone in, and the frame a delta for it is read in."""
        rest = bone.matrix_local
        return rest if bone.parent is None else bone.parent.matrix_local.inverted() @ rest

    def _standing(self, pose: dict, name: str):
        """One bone's matrix in a posed rig, read against its posed parent the
        same way _local reads a rest matrix."""
        parent = self.folk_parents[name]
        return pose[name] if parent is None else pose[parent].inverted() @ pose[name]

    def carries_shift(self, folk_bone: str, kit_bone: str) -> bool:
        """Whether [folk_bone]'s own shift belongs on [kit_bone].

        It does when the two hang off the same part of the body: the shift is
        then that joint moving against a frame that moved the same way on both
        rigs. The folk's feet fail that test: their `Foot` bones hang off the
        armature rather than off a shin, because the folk plant them with IK,
        while the kit's foot is a calf's child. The folk's IK pole targets fail
        it too, and no kit bone plays them at all.
        """
        folk_parent = self.folk_parents[folk_bone]
        kit_parent = self.armature.data.bones[kit_bone].parent
        if folk_parent is None or kit_parent is None:
            return folk_parent is None and kit_parent is None
        return kit_parent.name in BONE_MAP.get(folk_parent, ())

    # -- frames

    def _heights(self, kit, folk_armature) -> float:
        """How many kit metres stand in for one folk metre, measured in each
        body's own armature space: that is where the shifts below live.

        The kit's standing height in the scene is kept too, because a hauled
        load is placed against it.
        """
        from mathutils import Matrix, Vector  # noqa: PLC0415

        def height(obj, into=None):
            space = into or Matrix.Identity(4)
            corners = [space @ obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            return max(corner.z for corner in corners) - min(corner.z for corner in corners)

        folk_body = next(obj for obj in folk_armature.children_recursive if obj.name.startswith("Body"))
        kit_body = kit.objects["Body"]
        self.kit_height = height(kit_body)
        folk_arm = height(folk_body, folk_armature.matrix_world.inverted())
        kit_arm = height(kit_body, self.kit_world.inverted())
        reach = kit_arm / folk_arm
        if not 0.2 < reach < 5:
            raise ValueError(f"the folk and kit bodies differ by {reach:.2f}x, which is not a size difference")
        return reach

    def _reference(self, poser) -> dict:
        """The kit's standing pose, in the armature's own space: each bone's
        rest offset under its parent's, turned by the Poser's own basis."""
        out = {}
        for name in self.order:
            bone = self.armature.data.bones[name]
            local = self.kit_local[name] @ self.standing[name]
            out[name] = local if bone.parent is None else out[bone.parent.name] @ local
        return out

    def _folk_pose(self, clip: str, frame: int) -> dict:
        """Every folk bone's posed matrix in [clip] at [frame]. A pose bone's
        matrix is already in its armature's own space, which is the space its
        parent's frame is read in."""
        action = self.bpy.data.actions[clip] if clip in {a.name for a in self.bpy.data.actions} \
            else clip_action(clip)
        animation = self.folk_armature.animation_data
        animation.action = action
        # Blender 4.4+ actions carry slots; without one the rig does not move.
        if action.slots:
            animation.action_slot = action.slots[0]
        self.bpy.context.scene.frame_set(frame)
        self.bpy.context.view_layer.update()
        return {bone.name: bone.matrix.copy() for bone in self.folk_armature.pose.bones}

    def frame(self, folk_bone: str, kit_bone: str):
        """The rotation carrying [folk_bone]'s *standing* direction onto
        [kit_bone]'s, the shortest way round: a kit bone's orientation for a
        frame is the folk bone's own, turned through this.

        The standing poses are the pair the clips are measured between, so the
        two bones start out pointing the same way. The shortest way round
        between two directions keeps no roll of its own, which matters: the two
        rigs roll their bones differently (MakeHuman's arms are rolled unlike
        the folk's source rig's), and a roll difference carried onto a posed
        arm swings it out of the plane the folk swung it in.
        """
        folk_way = self._way(self.folk_world @ self.source_reference[folk_bone])
        kit_way = self._way(self.kit_world @ self.reference[kit_bone])
        if folk_bone in ("Foot.L", "Foot.R"):
            # An IK foot carries its sole plane as well as its direction.
            return ((self.kit_world @ self.reference[kit_bone]).to_quaternion()
                    @ (self.folk_world @ self.source_reference[folk_bone]).to_quaternion().inverted())
        return folk_way.rotation_difference(kit_way)

    def _way(self, matrix):
        """Which way a posed bone points, in the scene: a Blender bone runs
        from its head to its tail along its own +Y."""
        from mathutils import Vector  # noqa: PLC0415
        return (matrix.to_quaternion() @ Vector((0.0, 1.0, 0.0))).normalized()

    # -- clips

    def sample(self, name: str, action):
        """Read one folk clip into the kit's own key values, one key per folk
        frame, so the clip keeps its exact length and every pose is the
        folk's own. Nothing is written to the kit until the folk rig is gone.

        A bone takes the folk bone's orientation for that frame, so the two
        rigs' clips mean the same thing frame by frame. Its place comes from
        its own parent, which is what keeps the kit's skeleton at its own bone
        lengths, and only a joint whose parents play the same part of the body
        also takes the folk's shift (`carries_shift`).
        """
        from mathutils import Matrix, Vector  # noqa: PLC0415
        from kit_garments import pose_cloth
        frames = int(round(action.frame_range[1]))
        source = {kit: folk for folk, targets in BONE_MAP.items() for kit in targets}
        correction = {(folk, kit): self.frame(folk, kit)
                      for folk, targets in BONE_MAP.items() for kit in targets}
        # Match the kit's standing roll as well as its direction. A swing-only
        # correction otherwise imports the folk's ~120 degree arm roll into skin.
        roll = {(folk, kit):
                (correction[(folk, kit)] @ (self.folk_world @ self.source_reference[folk]).to_quaternion()).inverted()
                @ (self.kit_world @ self.reference[kit]).to_quaternion()
                for folk, targets in BONE_MAP.items() for kit in targets}
        keys = []
        for frame in range(frames + 1):
            pose = self._folk_pose(name, frame)
            moved = {}
            for kit_bone in self.order:
                bone = self.armature.data.bones[kit_bone]
                # A kit bone the folk have no counterpart for (a fingertip, the
                # ball of a foot) keeps the standing pose it was built with: the
                # clip has nothing to say about it, and leaving it out would
                # collapse it.
                local = self.kit_local[kit_bone] @ self.standing[kit_bone]
                anchor = local if bone.parent is None else moved[bone.parent.name] @ local
                folk_bone = source.get(kit_bone)
                if folk_bone is None:
                    moved[kit_bone] = anchor
                    continue
                orientation = (correction[(folk_bone, kit_bone)]
                               @ (self.folk_world @ pose[folk_bone]).to_quaternion()
                               @ roll[(folk_bone, kit_bone)]).normalized()
                moved[kit_bone] = (Matrix.Translation(anchor.to_translation()
                                                      + self._shift(folk_bone, kit_bone, pose))
                                   @ orientation.to_matrix().to_4x4())
            pose_cloth(self, moved)
            keys.append((frame, moved))
        if name == "Run":
            self._settle_run(keys)
        return name, frames, keys

    def _settle_run(self, keys):
        """Put the lowest run contact on the floor without erasing airtime."""
        from mathutils import Matrix, Vector
        footwear = self.kit.objects["Boots"]
        inverse = {bone.name: bone.matrix_local.inverted() for bone in self.armature.data.bones}
        sole = [(vertex.co.copy(), [(footwear.vertex_groups[g.group].name, g.weight)
                                    for g in vertex.groups]) for vertex in footwear.data.vertices
                if vertex.co.z < 0.035]
        if not sole:
            raise ValueError("Run has no footwear sole to measure")
        floor = min(sum(((pose[bone] @ inverse[bone] @ point) * weight for bone, weight in weights), Vector()).z
                    for _frame, pose in keys for point, weights in sole)
        shift = Matrix.Translation(Vector((0, 0, -floor)))
        for _frame, pose in keys:
            for bone in pose: pose[bone] = shift @ pose[bone]

    def _shift(self, folk_bone: str, kit_bone: str, pose: dict):
        """The folk joint's own shift in this frame's pose, in the kit's own
        metres, or nothing at all where the kit bone may not take it."""
        from mathutils import Vector  # noqa: PLC0415
        if not self.carries_shift(folk_bone, kit_bone):
            return Vector()
        parent = self.folk_parents[folk_bone]
        posed = pose[folk_bone] if parent is None else pose[parent].inverted() @ pose[folk_bone]
        shift = (posed.to_translation()
                 - self.folk_standing[folk_bone].to_translation()) * self.reach
        if parent is None:
            return shift
        kit_parent = self.armature.data.bones[kit_bone].parent
        return (self.frame(parent, kit_parent.name) @ shift)

    def write(self, name: str, keys) -> None:
        """Key the sampled clip onto the kit, as the action the client asks
        for by [name].

        The keys go in through the pose bones, not by writing curves by hand:
        Blender 4.4+ binds an action to its target through a slot, and an
        action whose curves were built directly carries no slot, so the
exporter drops the clip without a word. Assigning the action first creates
        the slot, and every channel is set before it is keyed, so the rig's
        re-evaluation on insert cannot reach a value from anywhere else.
        """
        from mathutils import Quaternion, Vector  # noqa: PLC0415
        action = self.bpy.data.actions.new(name)
        action.use_fake_user = True
        self.armature.animation_data_create()
        self.armature.animation_data.action = action
        for frame, poses in keys:
            channels = self._channels(poses)
            for bone in self.armature.pose.bones:
                location, rotation, scale = channels[bone.name]
                bone.rotation_mode = "QUATERNION"
                bone.location, bone.rotation_quaternion, bone.scale = location, rotation, scale
                bone.keyframe_insert("location", frame=frame)
                bone.keyframe_insert("rotation_quaternion", frame=frame)
                bone.keyframe_insert("scale", frame=frame)
        self.armature.animation_data.action = None
        for bone in self.armature.pose.bones:
            bone.rotation_quaternion = Quaternion()
            bone.location = Vector()

    def _channels(self, poses: dict) -> dict:
        """One frame's pose as each bone's own channel values: where the bone
        sits, and which way it turns, relative to its rest under its parent."""
        channels = {}
        for name in self.order:
            bone = self.armature.data.bones[name]
            rest = self.kit_local[name]
            pose = poses[name]
            if bone.parent is None:
                basis = rest.inverted() @ pose
            else:
                basis = rest.inverted() @ poses[bone.parent.name].inverted() @ pose
            channels[name] = basis.decompose()
        return channels

    # -- sockets

    def socket(self, name: str, kit_bone: str, how: str):
        """Hang a socket on the kit's own body: in the fist for a tool, at a
        place on the body for a load (SOCKETS, BODY_SOCKETS).

        Its scale is the inverse of the kit's game scale, because the client
        draws a held shape and a hauled load in figure units: on the folk, a
        socket's global scale is 1 and the figure stands on its own root, so
        the kit must cancel its root scale the same way.
        """
        from mathutils import Matrix, Vector  # noqa: PLC0415
        import bpy  # noqa: PLC0415
        bone = self.armature.data.bones[kit_bone]
        rest = self.kit_world @ bone.matrix_local
        if how == "hand":
            where = rest @ Vector((0.0, bone.length * GRIP_IN_HAND, 0.0))
            rotation = rest.to_quaternion() @ Matrix(GRIP_BASIS).to_quaternion()
        else:
            up, right, forward = BODY_SOCKETS[name]
            where = Vector((right, forward, up)) * self.kit_height
            rotation = rest.to_quaternion()
        scale = 1 / self.kit.spec["game_scale"]
        at = Matrix.Translation(where) @ rotation.to_matrix().to_4x4() @ Matrix.Scale(scale, 4)
        body = self.kit.objects["Body"]
        corners = [body.matrix_world @ Matrix.Translation(tuple(v)) for v in body.bound_box]
        low = min(corner.translation.z for corner in corners)
        high = max(corner.translation.z for corner in corners)
        if not low - 0.05 < at.translation.z < high:
            raise ValueError(f"socket {name} landed at z={at.translation.z:.2f}, outside the body "
                             f"({low:.2f}..{high:.2f})")
        socket = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(socket)
        socket.parent = self.armature
        socket.parent_type = "BONE"
        socket.parent_bone = kit_bone
        self.armature.data.pose_position = "REST"
        bpy.context.view_layer.update()
        socket.matrix_world = at
        self.armature.data.pose_position = "POSE"
        bpy.context.view_layer.update()
        return socket.matrix_world.translation
