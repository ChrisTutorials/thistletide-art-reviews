"""Fit clothing morphs to their supporting layer, preserving authored ease.

Shape keys carry the re-fit; Godot only applies their authored driver products.
Buttons and buckles are rigid pieces so a larger waist cannot enlarge them.
"""

from __future__ import annotations

import math
import numpy as np
import bmesh
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

CLOTH_BONES = ("cloth_front", "cloth_back")


def add_cloth_bones(builder):
    """Hanging panels bend over legs without copying anatomical twist or splay."""
    hip = (builder.shape.bones["thigh_l"][0] + builder.shape.bones["thigh_r"][0]) / 2
    for name in CLOTH_BONES:
        builder.rig[name] = {**builder.rig["pelvis"], "parent": "pelvis", "roll": 0}
        builder.shape.bones[name] = (hip.copy(), hip + (0, 0, -0.3))
        for moves in builder.shape.bone_keys.values():
            shift = (moves["thigh_l"][0] + moves["thigh_r"][0]) / 2
            moves[name] = (shift.copy(), shift.copy())


def pose_cloth(carrier, moved):
    hip_turn = moved["pelvis"].to_quaternion() @ carrier.reference["pelvis"].to_quaternion().inverted()
    legs = [hip_turn.inverted() @ carrier._way(moved[f"thigh_{side}"]) for side in ("l", "r")]
    pitch = [math.atan2(leg.y, -leg.z) for leg in legs]
    for name, angle in zip(CLOTH_BONES, (min(0, *pitch), max(0, *pitch))):
        rest = carrier.armature.data.bones[name].matrix_local.to_quaternion()
        rotation = hip_turn @ Quaternion(Vector((1, 0, 0)), angle) @ rest
        moved[name] = Matrix.Translation(moved[name].to_translation()) @ rotation.to_matrix().to_4x4()


def positions(key):
    co = np.empty(len(key.data) * 3, dtype=np.float32)
    key.data.foreach_get("co", co)
    return co.reshape(-1, 3).astype(float)


def islands(mesh):
    neighbours = [set() for _ in mesh.vertices]
    for edge in mesh.edges:
        a, b = edge.vertices
        neighbours[a].add(b)
        neighbours[b].add(a)
    unseen = set(range(len(neighbours)))
    while unseen:
        stack = [unseen.pop()]
        found = []
        while stack:
            at = stack.pop()
            found.append(at)
            more = neighbours[at] & unseen
            unseen.difference_update(more)
            stack.extend(sorted(more))
        yield np.array(sorted(found))


def fit_garments(builder, anchors_type):
    # Imported example outfits keep their upstream tailoring. Frontier layers
    # are fitted in order so a vest follows the corrected shirt beneath it.
    body_keys = [s["name"] + sign for s in builder.spec["sliders"] if s["group"] == "body"
                 for sign in ("+", "-")]
    corrections = builder.spec["garment_correctives"]
    fitted = {}

    def bound_weights(obj):
        weights = np.zeros((len(obj.data.vertices), len(builder.bone_names)), dtype=np.float32)
        names = [builder.bone_names.index(g.name) for g in obj.vertex_groups]
        for vertex in obj.data.vertices:
            for group in vertex.groups:
                weights[vertex.index, names[group.group]] = group.weight
        return weights

    def shaped(name, drivers):
        if name in fitted and tuple(drivers) in fitted[name]:
            return fitted[name][tuple(drivers)]
        keys = builder.objects[name].data.shape_keys.key_blocks
        base = positions(keys["Basis"])
        co = base + sum((positions(keys[d]) - base for d in drivers), np.zeros_like(base))
        if name == "Body":
            # Cloth rests on the large forms, not individual toes and nipples.
            bm = bmesh.new()
            bm.from_mesh(builder.objects[name].data)
            bm.verts.ensure_lookup_table()
            for vertex, point in zip(bm.verts, co):
                vertex.co = Vector(point)
            builder.smooth(bm, 8)
            builder.smooth(bm, 30, lambda p: p.z < builder.zAnk + 0.07)
            co = np.array([tuple(v.co) for v in bm.verts])
            bm.free()
            fitted.setdefault(name, {})[tuple(drivers)] = co
        return co

    for name, part in builder.spec["parts"].items():
        if "fit" not in part:
            continue
        config = part["fit"]
        parents = config["under"]
        obj = builder.objects[name]
        base = positions(obj.data.shape_keys.key_blocks["Basis"])
        rest = np.concatenate([shaped(parent, ()) for parent in parents])
        faces, offset = [], 0
        for parent in parents:
            support = builder.objects[parent]
            faces.extend(tuple(v + offset for v in support.data.polygons[i].vertices)
                         for i in builder.fit_surfaces[parent][0])
            offset += len(support.data.vertices)
        pairs = builder.fit_surfaces[name][1]
        outer_faces = [obj.data.polygons[i] for i in builder.fit_surfaces[name][0]]
        surface_vertices = sorted({i for face in outer_faces for i in face.vertices})
        shirt_hem = shaped("Shirt", ())[:, 2].min() if name == "Apron" else 0
        tree = BVHTree.FromPolygons(rest.tolist(), faces)
        # Rest distance includes blousing, the shaped hem and cloth thickness.
        # It is preserved on larger bodies instead of fitting every vertex tight.
        gap = []
        for p in base:
            at, normal, _, _ = tree.find_nearest(Vector(p))
            if at is None:
                raise RuntimeError(f"{name}: no supporting surface on {parents}")
            gap.append(max(config["gap"], (Vector(p) - at).dot(normal)))
        gap = np.array(gap)
        def refit(target, surface):
            for i in surface_vertices:
                if name in ("Boots", "Shoes") and base[i, 2] < builder.zAnk + 0.035:
                    continue  # The authored toe box bridges toes, which are hidden.
                if name in ("Shirt", "Cloak") and base[i, 2] < builder.shirt_join:
                    continue  # Hanging panels bridge both legs, rather than wrapping each thigh.
                if name == "Apron" and base[i, 2] < shirt_hem:
                    continue  # The upper panel still needs clearance from the tunic beneath it.
                p = target[i]
                at, normal, _, _ = surface.find_nearest(Vector(p))
                if at is None:
                    raise RuntimeError(f"{name}: morphed {parents} have no surface")
                target[i] += np.array(normal) * (gap[i] - (Vector(p) - at).dot(normal))
            for inner, outer in pairs:
                target[inner] = target[outer] + base[inner] - base[outer]

        if not config["rigid"]:
            target = base.copy()
            refit(target, tree)
            # Moving Basis must preserve unrelated morph deltas, including face keys.
            for key in obj.data.shape_keys.key_blocks:
                if key.name != "Basis":
                    key.data.foreach_set("co", (positions(key) + target - base).astype(np.float32).ravel())
            base = target
            obj.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", base.astype(np.float32).ravel())
            obj.data.vertices.foreach_set("co", base.astype(np.float32).ravel())
            obj.data.update()
        anchors = anchors_type(base, rest, np.arange(len(rest)))
        hanging = base[:, 2] < builder.shirt_join if name in ("Shirt", "Apron", "Cloak") else np.zeros(len(base), dtype=bool)
        waist_points = base.copy()
        waist_points[hanging, 2] = builder.zHip + 0.08
        waist_anchors = anchors_type(waist_points, rest, np.arange(len(rest))) if hanging.any() else None
        pieces = list(islands(obj.data)) if config["rigid"] else None
        if pieces is not None:
            original = bound_weights(obj)
            weights = np.zeros_like(original)
            for piece in pieces:
                carried = original[piece].sum(axis=0)
                if carried.sum() <= 0:
                    raise RuntimeError(f"{name}: rigid trim has no bone binding")
                weights[piece, int(carried.argmax())] = 1
            for group in list(obj.vertex_groups):
                obj.vertex_groups.remove(group)
            builder.set_weights(obj, weights)
        else:
            # Hanging garments own their rig binding; nearest legs are not supports.
            weights = bound_weights(obj)
            if name == "Apron":
                shirt = shaped("Shirt", ())
                weights = anchors_type(base, shirt, np.arange(len(shirt))).follow(bound_weights(builder.objects["Shirt"]))
                # The bib borrows the tunic's spine blend without anatomical leg twist.
                thighs = [builder.bone_names.index("thigh_" + side) for side in ("l", "r")]
                weights[:, builder.bone_names.index("pelvis")] += weights[:, thighs].sum(axis=1)
                weights[:, thighs] = 0
            if name in ("Shirt", "Apron", "Cloak"):
                # Independent panel controls keep the rest drape through the A-pose transition.
                leg = np.clip((builder.zHip + 0.12 - base[:, 2]) / 0.28, 0, 1)
                if name == "Apron":
                    # The bib follows its tunic; only the concealed skirt changes to the free panel.
                    leg = np.clip((builder.shirt_join - base[:, 2]) / (builder.shirt_join - builder.zHip), 0, 1)
                leg = leg * leg * (3 - 2 * leg)
                front = np.ones(len(base)) if name == "Apron" else np.clip((builder.yNeck - base[:, 1]) / 0.10 + 0.5, 0, 1)
                front = front * front * (3 - 2 * front)
                weights *= (1 - leg[:, None])
                weights[:, builder.bone_names.index(CLOTH_BONES[0])] += leg * front
                weights[:, builder.bone_names.index(CLOTH_BONES[1])] += leg * (1 - front)
            for inner, outer in pairs: weights[inner] = weights[outer]
            for group in list(obj.vertex_groups): obj.vertex_groups.remove(group)
            builder.set_weights(obj, weights)
        fitted[name] = {(): base}
        for drivers in [(k,) for k in body_keys] + [tuple(c["drivers"]) for c in corrections]:
            moved = np.concatenate([shaped(parent, drivers) for parent in parents])
            target = base + anchors.follow(moved - rest)
            if waist_anchors is not None:
                target[hanging, :2] = (base + waist_anchors.follow(moved - rest))[hanging, :2]
            surface = BVHTree.FromPolygons(moved.tolist(), faces)
            if pieces is not None:
                for piece in pieces:
                    shift = (target[piece] - base[piece]).mean(axis=0)
                    # shortcut: trim translates; use a rigid socket when a future cut needs large rotations.
                    target[piece] = base[piece] + shift
            else:
                refit(target, surface)
            if not np.isfinite(target).all():
                raise RuntimeError(f"{name}: nonfinite garment fit for {drivers}")
            fitted[name][drivers] = target
            if len(drivers) == 1:
                obj.data.shape_keys.key_blocks[drivers[0]].data.foreach_set("co", target.astype(np.float32).ravel())
            else:
                # Residual only: the two ordinary morphs already applied their moves.
                added = sum((fitted[name][(d,)] - base for d in drivers), np.zeros_like(base))
                correction = next(c for c in corrections if tuple(c["drivers"]) == drivers)
                builder.add_key(obj, correction["name"], target - added)


def cloth_folds(builder):
    """Small hem motion for the existing ClothMotion, anchored at the waist."""
    for name in ("Shirt", "Apron", "Cloak"):
        obj = builder.objects[name]
        base = positions(obj.data.shape_keys.key_blocks["Basis"])
        waist = builder.zWaist
        hem = np.clip((waist + 0.04 - base[:, 2]) / 0.3, 0, 1) ** 2
        if name == "Cloak":
            hem = np.clip((builder.zChest - base[:, 2]) / 0.5, 0, 1) ** 2
        for key, direction in (("ClothBack", (0, 0.025, 0)), ("ClothLeft", (-0.018, 0, 0)),
                               ("ClothRight", (0.018, 0, 0))):
            builder.add_key(obj, key, base + hem[:, None] * np.array(direction))
