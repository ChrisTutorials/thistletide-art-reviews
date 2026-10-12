"""Build the character kit: CC0 MakeHuman bodies that the game can reshape,
restyle and dress at runtime.

It writes, for each base (male, female):

* assets/characters/kit/kit_<base>.glb: the body on MakeHuman's game rig,
  two hanging-cloth controls, every part a look can ask for (eyes, brows, lashes, hair styles,
  outfits, orc tusks), the nineteen clips the client asks for and the three
  sockets a held tool and a hauled load hang from (kit_retarget.py carries
  them over from the folk rig);
* assets/characters/kit/kit_<base>.bones.json: how far each slider moves
  each bone, so the game can move the skeleton with the body.

How a part follows the body:

1. The body is MakeHuman's male or female shape plus the house style
   (character_kit.spec.json "house_style"), built from the CC0 base mesh
   and shape targets that fetch_mpfb2_cc0.py downloads.
2. Every slider end ("Height+", "Height-", "NoseSize+", ...) is a shape key
   on the body.
3. Every other part is tied to the body: each of its vertices follows the
   eight nearest body vertices (inverse-distance weights). The parts made
   for the CC0 example GLBs (#4300) ride from the example body onto the kit
   body this way, even onto the other gender; then every slider key is
   copied onto them the same way. The frontier clothes are cut from the
   body surface here and tied the same way.
4. Each outfit gets a "Hide.<outfit>" key that pulls the skin it covers
   into the body, so skin cannot poke through cloth.
5. Clips only turn bones (kit_retarget.py), so they fit every body shape.

Run from the repo root (either form; the first needs `pip install bpy`):
    python3 scripts/asset_pipeline/build_character_kit.py [--only male] [--preview DIR]
    blender --background --python scripts/asset_pipeline/build_character_kit.py -- [args]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy  # first: the bpy module makes bmesh and mathutils importable
import bmesh
import numpy as np
from mathutils import Quaternion, Vector, kdtree
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from character_kit_source import BODY_VERTS, EXAMPLE_LIFT, KitShape, Source, to_blender  # noqa: E402
from fetch_mpfb2_cc0 import fetch  # noqa: E402
from kit_hair import STYLES, HairBuilder, Head  # noqa: E402
from kit_garments import add_cloth_bones, cloth_folds, fit_garments, positions  # noqa: E402
from kit_equipment import build_equipment  # noqa: E402
from kit_retarget import FOLK_ASSET, retarget  # noqa: E402

ROOT = HERE.parents[1]
KIT = ROOT / "assets" / "characters" / "kit"
SPEC = KIT / "character_kit.spec.json"
TEXTURE_SIZE = 512
NEAREST = 8          # body vertices each part vertex follows
SOFTEN = 0.002       # metres; keeps a part vertex on a body vertex from taking all the weight
IRIS_SPREAD = 0.72   # radians from the eye's forward axis to the iris edge
GAZE_DOWN = 0.05     # radians; a slightly lowered gaze leaves no white under the iris


# ------------------------------------------------------------------ small helpers

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def ssteps(a, b, x):
    """sstep over an array."""
    t = np.clip((np.asarray(x) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


class Anchors:
    """Each point's NEAREST cage vertices and inverse-distance weights.
    follow(delta) moves the points the way the cage moved."""

    def __init__(self, points, cage_points, cage_index, nearest=NEAREST):
        tree = kdtree.KDTree(len(cage_points))
        for i, p in enumerate(cage_points):
            tree.insert(p, i)
        tree.balance()
        self.index = np.zeros((len(points), nearest), dtype=np.int64)
        self.weight = np.zeros((len(points), nearest))
        for i, p in enumerate(points):
            for j, (_co, k, dist) in enumerate(tree.find_n(p, nearest)):
                self.index[i, j] = cage_index[k]
                self.weight[i, j] = 1.0 / (dist + SOFTEN) ** 2
        self.weight /= self.weight.sum(axis=1, keepdims=True)

    def follow(self, delta):
        return (delta[self.index] * self.weight[..., None]).sum(axis=1)


class Part:
    """A mesh before it becomes a Blender object: positions, faces, one UV
    per face corner, bone weights per vertex and an optional texture."""

    def __init__(self, co, faces, uv=None, weights=None, image=None, colors=None):
        self.co = np.asarray(co, dtype=float)
        self.faces = [tuple(f) for f in faces]
        self.uv = uv
        self.weights = weights
        self.image = image
        self.colors = colors


# ------------------------------------------------------------------ CC0 example parts

def read_example(path: Path) -> tuple[dict[str, Part], np.ndarray]:
    """Every mesh of a #4300 example GLB as a Part, plus the positions of its
    body vertices (to tell which skin its clothes deleted)."""
    reset_scene()
    bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=False, disable_bone_shape=True)
    parts, body = {}, None
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.data.materials:
            continue
        me = obj.data
        world = obj.matrix_world
        co = np.array([tuple(world @ v.co) for v in me.vertices])
        if me.materials and me.materials[0].name == "Human.body":
            body = co
            continue
        faces = [tuple(p.vertices) for p in me.polygons]
        uv = np.zeros(len(me.loops) * 2)
        me.uv_layers.active.data.foreach_get("uv", uv)
        names = [g.name for g in obj.vertex_groups]
        weights = [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in me.vertices]
        parts[me.name] = Part(co, faces, uv.reshape(-1, 2), weights, base_color_pixels(me.materials[0]))
    if body is None:
        raise RuntimeError(f"{path} has no Human.body mesh")
    return parts, body


def base_color_pixels(material):
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            links = node.inputs["Base Color"].links
            if links and links[0].from_node.type == "TEX_IMAGE":
                image = links[0].from_node.image
                pixels = np.zeros(image.size[0] * image.size[1] * 4, dtype=np.float32)
                image.pixels.foreach_get(pixels)
                return pixels.reshape(image.size[1], image.size[0], 4)
    return None


def shell(part: Part, which: str) -> Part:
    """One garment of an example mesh that holds two (the CC0 casual suit is
    a T-shirt and jeans in one mesh), so each takes its own colour: "top" is
    the connected piece whose middle is highest, "bottom" the lowest.
    Vertices split along a UV seam count as one, so a sleeve stays with its
    shirt."""
    _, weld = np.unique(np.round(part.co, 5), axis=0, return_inverse=True)
    weld = weld.ravel()
    root = list(range(int(weld.max()) + 1))

    def find(a):
        while root[a] != a:
            root[a] = root[root[a]]
            a = root[a]
        return a
    for face in part.faces:
        first = find(weld[face[0]])
        for i in face[1:]:
            root[find(weld[i])] = first
    piece = [find(weld[face[0]]) for face in part.faces]
    heights: dict[int, list[float]] = {}
    for face, p in zip(part.faces, piece):
        heights.setdefault(p, []).append(float(part.co[list(face), 2].mean()))
    if len(heights) < 2:
        raise RuntimeError(f"shell {which!r} asked of a mesh in one piece")
    middle = {p: np.mean(h) for p, h in heights.items()}
    pick = (max if which == "top" else min)(middle, key=middle.get)
    return subset(part, [p == pick for p in piece])


def subset(part: Part, keep) -> Part:
    """The faces of [part] where [keep] is true, with only the vertices
    they use."""
    faces, corners, corner = [], [], 0
    for face, k in zip(part.faces, keep):
        if k:
            faces.append(face)
            corners.extend(range(corner, corner + len(face)))
        corner += len(face)
    used = sorted({i for face in faces for i in face})
    index = {old: new for new, old in enumerate(used)}
    return Part(part.co[used], [tuple(index[i] for i in face) for face in faces],
                None if part.uv is None else np.asarray(part.uv)[corners],
                None if part.weights is None else [part.weights[i] for i in used], part.image)


def lid_shade(co):
    """Vertex shade for the eye whites: darker under the upper lid and
    toward the corners, so each eye sits in its socket instead of
    glaring white."""
    shade = np.ones(len(co))
    for sign in (1, -1):
        side = co[:, 0] * sign > 0
        centre = co[side].mean(axis=0)
        radius = np.linalg.norm(co[side] - centre, axis=1).max()
        up = (co[side, 2] - centre[2]) / radius
        across = np.abs(co[side, 0] - centre[0]) / radius
        shade[side] = (1 - 0.35 * ssteps(0.05, 0.5, up)) * (1 - 0.2 * ssteps(0.45, 0.9, across))
    return [(v, v, v, 1.0) for v in shade]


def tintable(pixels, covered=None, thicken=0):
    """A texture the game can tint: light grey detail (median 0.85) with the
    original alpha, shrunk to TEXTURE_SIZE. Fully clear pixels take the
    median grey so shrinking leaves no dark fringe on hair and lashes.
    [covered] (cloth only: the texels its faces use) also takes printed
    marks off the fabric and fills the unused texels with plain cloth, so
    no background colour bleeds into a seam. [thicken] widens the cut-out
    by that many texels, so fine strands (lashes, brows) stay solid strokes
    after shrinking instead of breaking up."""
    rgb, alpha = pixels[..., :3], pixels[..., 3]
    luma = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = np.dstack([luma, luma, luma, alpha]).astype(np.float32)
    while out.shape[0] > TEXTURE_SIZE:
        h, w = out.shape[0] // 2, out.shape[1] // 2
        out = out[:h * 2, :w * 2].reshape(h, 2, w, 2, 4).mean(axis=(1, 3))
    luma, alpha = out[..., 0], out[..., 3]
    solid = alpha > 0.5
    if covered is not None:
        solid = covered(luma.shape[0])
        luma = np.where(solid, luma, np.median(luma[solid]))
        luma = unprint(luma)
    middle = float(np.median(luma[solid])) if solid.any() else 1.0
    grey = np.clip(luma * (0.85 / max(middle, 1e-3)), 0.0, 1.0)
    grey[alpha < 0.02] = 0.85
    if thicken:
        alpha = window(alpha, np.max, thicken)
    return np.dstack([grey, grey, grey, alpha]).astype(np.float32)


def window(image, pick, reach):
    """[pick] (np.min, np.max, np.mean) over the square of side 2*reach+1
    around each pixel."""
    from numpy.lib.stride_tricks import sliding_window_view  # noqa: PLC0415
    padded = np.pad(image, reach, mode="edge")
    return pick(sliding_window_view(padded, (2 * reach + 1, 2 * reach + 1)), axis=(2, 3))


def unprint(luma):
    """Fabric shading without print: thin light marks (the MakeHuman logo on
    the CC0 casual shirt) and thin dark ones (stitching) are filled from the
    cloth around them: a grey opening (smallest then largest value nearby)
    takes out light lines before they can merge, a closing takes out dark
    ones, then a soft blur rounds off the square patches both leave. Broad
    tones, like a shirt against trousers or faded denim, stay."""
    opened = window(window(luma, np.min, 6), np.max, 6)
    closed = window(window(opened, np.max, 4), np.min, 4)
    return window(window(closed, np.mean, 4), np.mean, 4)


def uv_cover(part: "Part"):
    """A function giving, at a texture size, which texels the part's faces
    cover (rows bottom-up, like Blender's pixels)."""
    def covered(size):
        mask = np.zeros((size, size), dtype=bool)
        uv = np.asarray(part.uv, dtype=float) * size
        corner = 0
        for face in part.faces:
            pts = uv[corner:corner + len(face)]
            corner += len(face)
            for k in range(1, len(face) - 1):
                a, b, c = pts[0], pts[k], pts[k + 1]
                lo = np.clip(np.floor(np.minimum(np.minimum(a, b), c)).astype(int) - 1, 0, size - 1)
                hi = np.clip(np.ceil(np.maximum(np.maximum(a, b), c)).astype(int) + 1, 0, size - 1)
                xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1) + 0.5, np.arange(lo[1], hi[1] + 1) + 0.5)
                d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(d) < 1e-12:
                    continue
                l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
                l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
                inside = (l1 > -0.02) & (l2 > -0.02) & (1 - l1 - l2 > -0.02)
                mask[ys[inside].astype(int), xs[inside].astype(int)] = True
        return mask
    return covered


def deleted_skin(example_body: np.ndarray, neutral: np.ndarray) -> np.ndarray:
    """Skin vertices the example's clothes deleted: body vertices of the
    neutral mesh with no vertex of the exported example body on them."""
    tree = kdtree.KDTree(len(example_body))
    for i, p in enumerate(example_body):
        tree.insert(p, i)
    tree.balance()
    kept = np.array([tree.find(p)[2] < 1e-4 for p in neutral[:BODY_VERTS]])
    return np.nonzero(~kept)[0]


# ------------------------------------------------------------------ the kit for one base

class KitBuilder:
    def __init__(self, source: Source, spec: dict, rig: dict, weights: dict, shapes: dict, examples: dict,
                 gender: str):
        self.source, self.spec, self.rig = source, spec, dict(rig)
        self.shape: KitShape = shapes[gender]
        self.shapes, self.examples, self.gender = shapes, examples, gender
        self.cage = source.cage()
        add_cloth_bones(self)
        self.bone_names = list(self.rig)
        self.weights = np.zeros((len(source.coords), len(self.bone_names)), dtype=np.float32)
        for j, bone in enumerate(rig):
            for vertex, w in weights[bone]:
                self.weights[vertex, j] = w
        self.objects: dict[str, bpy.types.Object] = {}
        self.anchors: dict[str, Anchors] = {}
        self.hides: dict[str, np.ndarray] = {}
        self.fit_surfaces: dict[str, tuple[list[int], list[tuple[int, int]]]] = {}

    # -- skeleton and body

    def build(self):
        reset_scene()
        self.armature = self.make_armature()
        body = self.make_body()
        self.landmarks()
        self.bvh_body = self.smoothed_body()
        for name, part in self.spec["parts"].items():
            if part["source"] == "built":
                continue
            self.add_example_part(name, part)
        self.surfaces = [("Body", self.bvh_body, 0.0)]
        self.build_irises()
        self.build_tusks()
        self.hair_head = self.make_hair_head()
        self.build_shirt()
        self.build_trousers()
        self.build_boots()
        self.build_shoes()
        self.build_belt()
        self.build_vest()
        build_equipment(self, self.hair_head)
        fit_garments(self, Anchors)
        self.build_hair()
        cloth_folds(self)
        self.add_hide_keys(body)
        self.make_clips()
        return self

    def smoothed_body(self):
        """The body with small bumps (nipples, knuckles, toes) smoothed
        away. Clothes rest on this, so cloth bridges over them instead of
        clinging; the skin under cloth is hidden anyway (add_hide_keys)."""
        bm = bmesh.new()
        bm.from_mesh(self.objects["Body"].data)
        self.smooth(bm, 8)
        self.taubin(bm, 60, self.chest)
        tree = BVHTree.FromBMesh(bm)
        bm.free()
        return tree

    def make_armature(self):
        data = bpy.data.armatures.new("Kit")
        obj = link(bpy.data.objects.new("Kit", data))
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        for name, bone in self.rig.items():
            edit = data.edit_bones.new(name)
            edit.head, edit.tail = (Vector(p) for p in self.shape.bones[name])
            edit.roll = bone["roll"]
            edit.use_connect = False
            edit.use_inherit_rotation = bone["use_inherit_rotation"]
            edit.use_local_location = bone["use_local_location"]
            edit.inherit_scale = bone["inherit_scale"]
        for name, bone in self.rig.items():
            if bone["parent"]:
                data.edit_bones[name].parent = data.edit_bones[bone["parent"]]
        bpy.ops.object.mode_set(mode="OBJECT")
        return obj

    def make_body(self):
        faces, face_uvs = self.source.body_faces()
        uv = self.source.uvs[[i for f in face_uvs for i in f]]
        part = Part(self.shape.base[:BODY_VERTS], faces, uv)
        obj = self.make_object("Body", part, None, self.face_paint())
        self.set_weights(obj, self.weights[:BODY_VERTS])
        obj.shape_key_add(name="Basis", from_mix=False)
        for key, delta in self.shape.keys.items():
            self.add_key(obj, key, part.co + delta[:BODY_VERTS])
        for key, delta in self.shape.expressions.items():
            self.add_key(obj, key, part.co + delta[:BODY_VERTS])
        return obj

    def face_paint(self):
        """Vertex shade that colours the lips and warms the cheeks, as
        multipliers of the skin tint (spec bases.<base>.paint), so it suits
        every skin colour. MakeHuman's lip shapes find the lips: a vertex
        either lip target moves far is lip. The blush is a soft oval on
        each cheek, below the pupil."""
        paint = self.spec["bases"][self.gender].get("paint", {})
        body = self.shape.base[:BODY_VERTS]
        masks = {}
        if "lips" in paint:
            reach = [np.linalg.norm(self.source.target(t)[:BODY_VERTS], axis=1)
                     for t in ("mouth/mouth-upperlip-volume-incr", "mouth/mouth-lowerlip-volume-incr")]
            masks["lips"] = np.max([ssteps(0.25, 0.7, r / r.max()) for r in reach], axis=0)
        if "blush" in paint:
            masks["blush"] = np.zeros(BODY_VERTS)
            for side in ("l", "r"):
                eye = self.shape.base[self.source.groups[f"helper-{side}-eye"]]
                centre = eye.mean(axis=0)
                radius = float(np.abs(eye[:, 0] - centre[0]).max())
                aim = np.array([centre[0] * 1.08, centre[2] - 2.6 * radius])
                front = body[:, 1] < centre[1] + 2 * radius
                near = np.argmin(np.where(front, np.hypot(body[:, 0] - aim[0], body[:, 2] - aim[1]), np.inf))
                d = (body - body[near]) / np.array([2.3 * radius, 1.8 * radius, 1.6 * radius])
                masks["blush"] = np.maximum(masks["blush"], 1 - ssteps(0.0, 1.0, np.linalg.norm(d, axis=1)))
        shade = np.ones((BODY_VERTS, 3))
        for region, tint in paint.items():
            shade *= 1 - masks[region][:, None] * (1 - np.asarray(tint, dtype=float))
        return [(*rgb, 1.0) for rgb in shade]

    def make_object(self, name, part: Part, image, colors=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(part.co.tolist(), [], part.faces)
        self.fit_surfaces[name] = (list(range(len(part.faces))), [])
        if part.uv is not None:
            layer = me.uv_layers.new(name="UVMap")
            layer.data.foreach_set("uv", np.asarray(part.uv, dtype=np.float32).ravel())
        if colors is not None:
            attr = me.color_attributes.new("Color", "FLOAT_COLOR", "POINT")
            attr.data.foreach_set("color", np.asarray(colors, dtype=np.float32).ravel())
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
        me.materials.append(self.material(name, image))
        obj = link(bpy.data.objects.new(name, me))
        obj.parent = self.armature
        obj.modifiers.new("Armature", "ARMATURE").object = self.armature
        self.objects[name] = obj
        return obj

    def material(self, name, image):
        mat = bpy.data.materials.new(name)
        # A new material has no node tree unless nodes are switched on; some
        # Blender builds (4.5 LTS here) default to the old fixed pipeline.
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.9
        if image is not None:
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            img = bpy.data.images.new(f"{self.gender}_{name}", image.shape[1], image.shape[0], alpha=True)
            img.pixels.foreach_set(image.ravel())
            img.file_format = "PNG"
            img.pack()
            tex.image = img
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if (image[..., 3] < 0.99).any():
                clip = mat.node_tree.nodes.new("ShaderNodeMath")
                clip.operation = "ROUND"
                mat.node_tree.links.new(tex.outputs["Alpha"], clip.inputs[0])
                mat.node_tree.links.new(clip.outputs[0], bsdf.inputs["Alpha"])
        return mat

    def set_weights(self, obj, weights: np.ndarray):
        """[weights] is (vertices, bones). Each vertex keeps its four
        strongest bones, renormalised."""
        groups = [obj.vertex_groups.new(name=b) for b in self.bone_names]
        top = np.argsort(-weights, axis=1)[:, :4]
        for i, row in enumerate(top):
            w = weights[i, row]
            total = w.sum()
            if total <= 0: raise RuntimeError(f"{obj.name}: vertex {i} has no skin binding")
            for j, value in zip(row, w):
                if value > 1e-4:
                    groups[j].add([i], float(value / total), "REPLACE")

    def add_key(self, obj, name, co):
        key = obj.shape_key_add(name=name, from_mix=False)
        key.data.foreach_set("co", np.asarray(co, dtype=np.float32).ravel())
        key.value = 0.0  # exported as the shape's default weight: off until a look sets it

    def tie(self, name, co, nearest=NEAREST):
        """Tie a part (positions on the kit body) to the body: anchors, the
        slider keys and, for face parts, the expressions."""
        anchors = Anchors(co, self.shape.base[self.cage], self.cage, nearest)
        self.anchors[name] = anchors
        return anchors

    def add_part_keys(self, obj, name, co, face=False):
        anchors = self.anchors[name]
        obj.shape_key_add(name="Basis", from_mix=False)
        for key, delta in self.shape.keys.items():
            self.add_key(obj, key, co + anchors.follow(delta))
        if face:
            for key, delta in self.shape.expressions.items():
                self.add_key(obj, key, co + anchors.follow(delta))

    # -- parts from the CC0 examples

    def add_example_part(self, name, spec_part):
        source = self.gender if spec_part["source"] == "example" else spec_part["source"]
        parts, example_body = self.examples[source]
        found = parts[spec_part["mesh"]]
        texture = spec_part.get("texture")
        image = None
        if texture and found.image is not None:
            # The image belongs to the whole mesh, before a shell is taken.
            image = tintable(found.image, uv_cover(found) if texture == "detail" else None,
                             spec_part.get("thicken", 0))
        if "shell" in spec_part:
            found = shell(found, spec_part["shell"])
        raw = self.shapes[source].raw
        # Onto the kit body: follow how the kit body differs from the
        # example body it was made for (gender, house style, grounding).
        carry = Anchors(found.co, raw[self.cage], self.cage)
        co = found.co + carry.follow(self.shape.base - raw)
        part = Part(co, found.faces, found.uv, found.weights)
        if spec_part.get("keep") == "upper":
            # Upper lashes only: at game size the lower ones read as dark
            # spikes under the eye.
            centres = {np.sign(c[0]): c for c, _ in self.eyes()}
            part = subset(part, [p[2] > centres[np.sign(p[0])][2]
                                 for p in (part.co[list(f)].mean(axis=0) for f in part.faces)])
            co = part.co
        obj = self.make_object(name, part, image, lid_shade(co) if spec_part.get("lid_shade") else None)
        groups = {b: obj.vertex_groups.new(name=b) for b in self.bone_names}
        for i, w in enumerate(part.weights):
            for bone, value in w.items():
                groups[bone].add([i], value, "REPLACE")
        self.tie(name, co)
        self.add_part_keys(obj, name, co, face=name in ("Eyes", "Brows", "Lashes"))
        if spec_part.get("hides"):
            # The example GLB stores its body unshaped (MakeHuman's neutral
            # mesh, with the gender as morph targets), so match against that.
            neutral = to_blender(self.source.coords) + np.array([0.0, 0.0, EXAMPLE_LIFT])
            self.hides[name] = deleted_skin(example_body, neutral)

    # -- landmarks for cutting clothes

    def landmarks(self):
        b = self.shape.bones
        head = lambda n: Vector(b[n][0])  # noqa: E731
        self.zAnk, self.zKnee, self.zHip = head("foot_l").z, head("calf_l").z, head("thigh_l").z
        self.zPelvis, self.zChest, self.zNeck = head("pelvis").z, head("spine_03").z, head("neck_01").z
        self.yNeck = head("neck_01").y
        body = self.shape.base[:BODY_VERTS]
        trunk = (np.abs(body[:, 0]) < 0.24) & (np.abs(body[:, 1]) < 0.2)
        best = None
        for z in np.arange(self.zHip + 0.04, self.zChest, 0.005):
            ring = body[trunk & (np.abs(body[:, 2] - z) < 0.006)]
            if len(ring) > 8:
                width = ring[:, 0].max() - ring[:, 0].min()
                if best is None or width < best[0]:
                    best = (width, z)
        self.zWaist = float(best[1])
        self.arm = {s: (head(f"upperarm_{s}"), head(f"lowerarm_{s}"), head(f"hand_{s}"), head(f"middle_01_{s}"))
                    for s in "lr"}
        a, e, w, _k = self.arm["l"]
        self.upper, self.fore, self.xShoulder = (e - a).length, (w - e).length, a.x
        self.front = lambda p: sstep(0.0, 0.05, self.yNeck - p.y)  # noqa: E731

    def chest(self, p):
        """The front of the ribcage, where cloth hangs over the chest
        instead of following it."""
        return self.zWaist < p.z < self.zNeck - 0.03 and abs(p.x) < self.xShoulder

    def arm_at(self, p):
        """Distance from [p] to its arm and how far down the arm it is (0 at
        the shoulder joint)."""
        a, b, c, d = self.arm["l" if p.x >= 0 else "r"]
        best, along = (1e9, 0.0), 0.0
        for u, v in ((a, b), (b, c), (c, d)):
            seg = v - u
            t = max(0.0, min(1.0, (p - u).dot(seg) / seg.length_squared))
            dist = (p - (u + seg * t)).length
            if dist < best[0]:
                best = (dist, along + t * seg.length)
            along += seg.length
        return best

    def in_arm(self, p):
        dist, along = self.arm_at(p)
        return dist < 0.15 and abs(p.x) > self.xShoulder * 0.85, along

    # -- cutting clothes from the body surface

    def body_bmesh(self, pick):
        bm = bmesh.new()
        bm.from_mesh(self.objects["Body"].data)
        for layer in list(bm.verts.layers.shape):
            bm.verts.layers.shape.remove(layer)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not any(pick(v.co) for v in f.verts)], context="FACES")
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)
        return bm

    @staticmethod
    def iso_clip(bm, field):
        """Keep where field(p) > 0, cutting edges exactly where it is 0."""
        layer = bm.verts.layers.float.get("s") or bm.verts.layers.float.new("s")
        for v in bm.verts:
            s = field(v.co)
            v[layer] = s if abs(s) > 1e-7 else 1e-7
        cut = set()
        for e in list(bm.edges):
            a, b = e.verts
            sa, sb = a[layer], b[layer]
            if (sa > 0) != (sb > 0):
                _e, v = bmesh.utils.edge_split(e, a, sa / (sa - sb))
                v[layer] = 0.0
                cut.add(v)
        for f in list(bm.faces):
            on = [v for v in f.verts if v in cut]
            if len(on) == 2:
                try:
                    bmesh.utils.face_split(f, on[0], on[1])
                except ValueError:
                    pass
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if sum(v[layer] for v in f.verts) <= 1e-9], context="FACES")
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.001)

    @staticmethod
    def drop_islands(bm, keep=200):
        seen, kill = set(), []
        for f in bm.faces:
            if f in seen:
                continue
            stack, island = [f], []
            seen.add(f)
            while stack:
                g = stack.pop()
                island.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h not in seen:
                            seen.add(h)
                            stack.append(h)
            if len(island) < keep:
                kill += island
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)

    @staticmethod
    def offset(bm, amount):
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * (amount(v.co) if callable(amount) else amount)

    @staticmethod
    def smooth(bm, rounds, pick=None, factor=0.5):
        verts = [v for v in bm.verts if pick is None or pick(v.co)]
        for _ in range(rounds):
            bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)

    @staticmethod
    def taubin(bm, rounds, pick=None):
        """Smooth without shrinking: each round smooths, then pushes back
        out a little more than it pulled in (Taubin smoothing). Takes small
        bumps (nipples, ribs) out of cloth without pulling it into the body."""
        verts = [v for v in bm.verts if pick is None or pick(v.co)]
        for _ in range(rounds):
            for factor in (0.5, -0.53):
                bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)

    def conform(self, bm, gap, under, rounds=3):
        """Push every vertex out of the layers under it, keeping [gap]."""
        for r in range(rounds):
            for v in bm.verts:
                for name, tree, thick in self.surfaces:
                    if name not in under:
                        continue
                    loc, normal, _i, _d = tree.find_nearest(v.co, 0.08)
                    if loc is None:
                        continue
                    dv = v.co - loc
                    s = dv.dot(normal)
                    if (dv - normal * s).length > 0.004 or s < -0.05:
                        continue
                    if s < thick + gap:
                        v.co += normal * (thick + gap - s)
            if r < rounds - 1:
                self.smooth(bm, 1, factor=0.35)

    def finish(self, name, bm, thick, surface=True, shade=None, smooth_edges=True):
        """Turn a cut shell into a skinned, slider-keyed part, its edges
        smoothed into clean lines. [shade] (position to 0..1) paints a vertex
        shade the game multiplies into the part's colour."""
        if smooth_edges:
            self.smooth_rims(bm)
        for _ in range(3):
            for v in bm.verts:
                around = [e.other_vert(v) for e in v.link_edges]
                if len(around) < 2:
                    continue
                mid = sum((u.co for u in around), Vector()) / len(around)
                spread = sum((u.co - mid).length for u in around) / len(around) + 1e-6
                if (v.co - mid).length > 3 * spread and (v.co - mid).length > 0.004:
                    v.co = mid
        bm.normal_update()
        if surface:
            self.surfaces.append((name, BVHTree.FromBMesh(bm), thick))
        outer, pairs = self.thicken(bm, thick) if thick else (list(bm.faces), [])
        bm.faces.index_update()
        bm.verts.index_update()
        support_faces = [f.index for f in outer]
        thickness_pairs = [(a.index, b.index) for a, b in pairs]
        co = np.array([tuple(v.co) for v in bm.verts])
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        deform = bm.verts.layers.deform.active
        weights = np.array([[v[deform].get(j, 0) for j in range(len(self.bone_names))] for v in bm.verts]) \
            if deform is not None else None
        bm.free()
        colors = None if shade is None else [(s, s, s, 1.0) for s in map(shade, co)]
        obj = self.add_built(name, Part(co, faces), colors, bone_weights=weights)
        self.fit_surfaces[name] = (support_faces, thickness_pairs)
        return obj

    @staticmethod
    def smooth_rims(bm, rounds=6):
        """A cut leaves its edge zigzagging between the body's vertices;
        smooth each edge as a curve (toward the middle of its two edge
        neighbours, then back out a little more, so a cuff or neckline
        keeps its size) so hems and necklines run as clean lines."""
        rims = {}
        for v in bm.verts:
            rim = [e.other_vert(v) for e in v.link_edges if len(e.link_faces) == 1]
            if len(rim) == 2:
                rims[v] = rim
        for _ in range(rounds):
            for factor in (0.5, -0.53):
                mids = {v: (a.co + b.co) / 2 for v, (a, b) in rims.items()}
                for v, mid in mids.items():
                    v.co = v.co.lerp(mid, factor)

    @staticmethod
    def thicken(bm, thick):
        """Give a shell cloth thickness: an outer copy along the vertex
        normals plus a rim along every open edge. Plain normals, not even
        thickness, which shoots spikes out of tight creases."""
        bm.normal_update()
        faces = list(bm.faces)
        outer = {v: bm.verts.new(v.co + v.normal * thick) for v in list(bm.verts)}
        deform = bm.verts.layers.deform.active
        if deform is not None:
            for inner, copy in outer.items():
                for bone, weight in inner[deform].items(): copy[deform][bone] = weight
        rims = []
        for f in faces:
            for loop in f.loops:
                if len(loop.edge.link_faces) == 1:
                    rims.append((loop.vert, loop.link_loop_next.vert))
        outside = []
        for f in faces:
            outside.append(bm.faces.new([outer[v] for v in f.verts]))
            f.normal_flip()
        for a, b in rims:
            bm.faces.new((a, b, outer[b], outer[a]))
        bm.normal_update()
        return outside, list(outer.items())

    def add_built(self, name, part: Part, colors=None, nearest=NEAREST, bone_weights=None):
        obj = self.make_object(name, part, None, colors)
        anchors = self.tie(name, part.co, nearest)
        weights = bone_weights if bone_weights is not None else (
            self.weights[anchors.index] * anchors.weight[..., None]).sum(axis=1)
        self.set_weights(obj, weights)
        self.add_part_keys(obj, name, part.co, face=name in ("Irises", "EyeShine", "Tusks")
                           or self.spec["parts"][name].get("face", False))
        return obj

    # -- face pieces built here

    def eyes(self):
        """Each eyeball's centre and radius."""
        eye_co = np.array([tuple(v.co) for v in self.objects["Eyes"].data.vertices])
        balls = (eye_co[eye_co[:, 0] * sign > 0] for sign in (1, -1))
        return [(b.mean(axis=0), float(np.linalg.norm(b - b.mean(axis=0), axis=1).max())) for b in balls]

    def build_irises(self):
        """An iris and pupil on the front of each eyeball, coloured per
        person by the game (the vertex colour shades the tint): a dark
        pupil, the iris brightest low down and in the shadow of the upper
        lid at the top, and a dark rim. The iris is drawn a little larger
        than life and the gaze a little low, so no white shows under it.
        Then a small catch light on each, on the same side of both eyes, so
        the eyes read as wet and alive. Each disc vertex sits just outside
        the eye mesh in its direction."""
        eye_co = np.array([tuple(v.co) for v in self.objects["Eyes"].data.vertices])
        spread = IRIS_SPREAD
        down = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(GAZE_DOWN), -math.sin(GAZE_DOWN)],
                         [0.0, math.sin(GAZE_DOWN), math.cos(GAZE_DOWN)]])
        co, faces, colors = [], [], []
        shine, shine_faces = [], []
        for sign in (1, -1):
            ball = eye_co[eye_co[:, 0] * sign > 0]
            centre = ball.mean(axis=0)

            def on_ball(d, lift):
                d = down @ (d / np.linalg.norm(d))
                return tuple(centre + d * (float(((ball - centre) @ d).max()) + lift))

            def shade(r, up):
                tone = 0.05 if r < 0.32 else 0.82 if r < 0.45 else 1.0 if r < 0.75 else 0.62 if r < 0.92 else 0.3
                return tone * (1 - 0.5 * sstep(-0.2, 0.9, up) * sstep(0.25, 0.5, r))
            self.disc(co, faces, colors, 10, 24, lambda angle, turn: on_ball(np.array(
                [math.sin(angle) * math.cos(turn), -math.cos(angle), math.sin(angle) * math.sin(turn)]), 0.0004),
                spread, shade)
            # The catch light: up and to the viewer's right of the pupil.
            aim = np.array([math.sin(0.4 * spread), -1.0, math.sin(0.42 * spread)])
            aim /= np.linalg.norm(aim)
            side = np.cross(aim, (0.0, 0.0, 1.0))
            side /= np.linalg.norm(side)
            up = np.cross(side, aim)
            self.disc(shine, shine_faces, None, 2, 10, lambda angle, turn: on_ball(
                aim + (side * math.cos(turn) + up * math.sin(turn)) * math.tan(angle), 0.0007), 0.16 * spread)
        head = np.zeros((len(co), len(self.bone_names)), dtype=np.float32)
        head[:, self.bone_names.index("head")] = 1
        self.add_built("Irises", Part(co, self.facing_front(co, faces)), colors, bone_weights=head)
        self.add_built("EyeShine", Part(shine, self.facing_front(shine, shine_faces)),
                       bone_weights=head[:len(shine)])

    @staticmethod
    def disc(co, faces, colors, rings, segments, at, spread, shade=None):
        """A round patch: [at](angle, turn) places each vertex, ring by ring
        out to [spread]; [shade](r, up) gives its vertex shade."""
        start = len(co)
        for ring in range(rings + 1):
            angle = spread * ring / rings
            for seg in range(segments if ring else 1):
                turn = 2 * math.pi * seg / segments
                co.append(at(angle, turn))
                if colors is not None:
                    s = shade(ring / rings, math.sin(turn) if ring else 0.0)
                    colors.append((s, s, s, 1.0))
        for seg in range(segments):
            faces.append((start, start + 1 + (seg + 1) % segments, start + 1 + seg))
        for ring in range(1, rings):
            a, b = start + 1 + (ring - 1) * segments, start + 1 + ring * segments
            for seg in range(segments):
                n = (seg + 1) % segments
                faces.append((a + seg, a + n, b + n, b + seg))

    @staticmethod
    def facing_front(co, faces):
        """Faces wound so the patches face forward (-Y)."""
        a, b, c = (np.array(co[i]) for i in faces[0])
        return [tuple(reversed(f)) for f in faces] if np.cross(b - a, c - a)[1] > 0 else faces

    def build_tusks(self):
        """An orc's two lower tusks, rising from the jaw beside the mouth."""
        teeth = self.shape.base[self.source.groups["helper-lower-teeth"]]
        top, front = teeth[:, 2].max(), teeth[:, 1].min()
        co, faces = [], []
        for sign in (1, -1):
            base = Vector((sign * 0.019, front + 0.001, top - 0.006))
            tip = base + Vector((sign * 0.007, -0.004, 0.027))
            start = len(co)
            for ring, (t, radius) in enumerate(((0.0, 0.0058), (0.5, 0.0042), (0.85, 0.0022))):
                c = base.lerp(tip, t) + Vector((0, -0.002 * math.sin(math.pi * t), 0))
                for seg in range(8):
                    a = 2 * math.pi * seg / 8
                    co.append(tuple(c + Vector((math.cos(a) * radius, math.sin(a) * radius, 0))))
            co.append(tuple(tip))
            for ring in range(2):
                for seg in range(8):
                    n = (seg + 1) % 8
                    a, b = start + ring * 8, start + (ring + 1) * 8
                    faces.append((a + seg, a + n, b + n, b + seg))
            for seg in range(8):
                faces.append((start + 16 + seg, start + 16 + (seg + 1) % 8, start + 24))
        head = np.zeros((len(co), len(self.bone_names)), dtype=np.float32)
        head[:, self.bone_names.index("head")] = 1
        self.add_built("Tusks", Part(co, faces), bone_weights=head)

    # -- hair

    def make_hair_head(self):
        ear = np.linalg.norm(self.source.target("ears/l-ear-scale-incr")[:BODY_VERTS], axis=1)
        return Head(self.shape.base, self.source.body_faces()[0], self.source.groups, self.shape.bones,
                    np.nonzero(ear > ear.max() * 0.3)[0])

    def build_hair(self):
        """Hair rests on finished clothing; long tips follow the torso."""
        head = self.hair_head
        points, faces = [], []
        for name in ("Body", "Shirt", "Vest", "Apron", "Cloak"):
            obj = self.objects[name]
            offset = len(points)
            points.extend(positions(obj.data.shape_keys.key_blocks["Basis"]).tolist())
            faces.extend(tuple(i + offset for i in obj.data.polygons[f].vertices)
                         for f in self.fit_surfaces[name][0])
        hair = HairBuilder(head, BVHTree.FromPolygons(points, faces), self.spec["bases"][self.gender]["hairline"])
        for name, part in self.spec["parts"].items():
            if "style" not in part:
                continue
            co, faces, shade = hair.style(STYLES[part["style"]], self)
            anchors = Anchors(co, self.shape.base[self.cage], self.cage)
            under = (self.weights[anchors.index] * anchors.weight[..., None]).sum(axis=1)
            rides = np.zeros_like(under)
            rides[:, self.bone_names.index("head")] = 1
            low = np.array([sstep(head.neck + 0.03, head.neck - 0.06, z) for z in co[:, 2]])[:, None]
            self.add_built(name, Part(co, faces), [(s, s, s, 1.0) for s in shade],
                           bone_weights=rides * (1 - low) + under * low)

    # -- frontier clothes

    def build_shirt(self):
        """A long-sleeved linen tunic with a short neck slit and free skirt."""
        self.shirt_join = self.zHip + 0.06
        hem, cuff = self.shirt_join, self.upper + 0.94 * self.fore
        def neck(p):
            dip = 0.014 * self.front(p)
            round_neck = (p.x / 0.064) ** 2 + ((p.z - (self.zNeck - 0.008 - dip)) / 0.038) ** 2 - 1
            slit = max(abs(p.x) - 0.008, p.z - self.zNeck, self.zNeck - 0.12 - p.z) if self.front(p) > 0.5 else 1
            return min(round_neck, slit)
        def sleeve(p):
            inside, along = self.in_arm(p)
            return (cuff - along) if inside else 1.0
        fields = (lambda p: max((self.zNeck - 0.005) - p.z, abs(p.x) - 0.10),
                  neck, lambda p: p.z - hem, sleeve)
        bm = self.body_bmesh(lambda p: hem - 0.05 < p.z < self.zNeck + 0.08)
        for field in fields: self.iso_clip(bm, field)
        # The same cut owns skin coverage; rays miss the concave underarm seam.
        self.hides["Shirt"] = np.array([i for i, co in enumerate(self.shape.base[:BODY_VERTS])
            if hem < co[2] < self.zNeck + 0.08 and all(field(Vector(co)) > 0 for field in fields)], dtype=np.int64)
        self.drop_islands(bm)
        ring = []
        for edge in bm.edges:
            if len(edge.link_faces) == 1 and all(abs(v.co.z - hem) < 0.006 for v in edge.verts):
                loop = next(loop for loop in edge.link_faces[0].loops if loop.edge == edge)
                ring.append((loop.vert, loop.link_loop_next.vert))
        if not ring: raise RuntimeError("Tunic has no continuous lower edge")
        # Cloth never shows the nipples: smooth them out of the cut skin
        # before it is pushed out (an offset along the normals would only
        # make a bump bigger).
        self.taubin(bm, 60, self.chest)

        def loose(p):
            inside, along = self.in_arm(p)
            if inside:
                gather = 0.005 * math.sin(math.pi * sstep(cuff - 0.06, cuff, along))
                return 0.008 + 0.012 * sstep(0.0, self.upper, along) - 0.010 * sstep(cuff - 0.06, cuff, along) + gather
            blouse = 0.010 * sstep(self.zWaist + 0.12, self.zWaist, p.z)
            collar = 0.006 * sstep(self.zNeck - 0.08, self.zNeck, p.z) * self.front(p)
            return 0.006 + 0.004 * sstep(self.zChest + 0.1, self.zWaist, p.z) + blouse + collar
        self.offset(bm, loose)
        self.smooth(bm, 3)
        self.taubin(bm, 20, self.chest)
        self.drape(bm, self.chest)
        self.conform(bm, 0.004, ("Body",))
        previous = {v: v for pair in ring for v in pair}
        for t in np.linspace(0.16, 1, 7):
            row = {}
            for vertex in previous:
                p = vertex.co
                pleat = 0.004 * t * math.cos(math.atan2(p.x, self.yNeck - p.y) * 8)
                row[vertex] = bm.verts.new((p.x * (1 + 0.12 * t), self.yNeck + (p.y - self.yNeck) * (1 + 0.12 * t) + pleat,
                                           hem + (self.zHip - 0.12 - hem) * t))
                deform = bm.verts.layers.deform.active
                for bone, weight in vertex[deform].items(): row[vertex][deform][bone] = weight
            for a, b in ring:
                bm.faces.new((previous[b], previous[a], row[a], row[b]))
            previous = row
        edge = self.rim_distance(bm)
        shirt = self.finish("Shirt", bm, 0.003, shade=lambda p: 0.85 if edge(p) < 0.007 else 1.0)
        indices = [v.index for v in shirt.data.vertices if v.co.z < hem + 0.003]
        for group in shirt.vertex_groups: group.remove(indices)
        shirt.vertex_groups["pelvis"].add(indices, 1, "REPLACE")

    def build_trousers(self):
        top, boot = self.zWaist + 0.015, self.zAnk + 0.55 * (self.zKnee - self.zAnk)
        self.zBoot = boot
        bm = self.body_bmesh(lambda p: self.zAnk - 0.02 < p.z < top + 0.05 and abs(p.x) < 0.3)
        self.iso_clip(bm, lambda p: top - p.z)
        self.iso_clip(bm, lambda p: p.z - (boot - 0.06))
        self.drop_islands(bm)

        def loose(p):
            bag = sstep(self.zKnee + 0.25, self.zKnee - 0.05, p.z) * 0.010
            return 0.007 + 0.004 * sstep(self.zHip, self.zKnee, p.z) + bag
        self.offset(bm, loose)
        self.smooth(bm, 2)
        self.conform(bm, 0.003, ("Body", "Shirt"))
        self.finish("Trousers", bm, 0.003)

    def build_boots(self, name="Boots", top=None, under=("Body", "Trousers")):
        """A rounded toe box, welt and shaft, independent of toe anatomy."""
        from kit_equipment import grid
        top = self.zBoot if top is None else top
        bm = bmesh.new()
        body = self.shape.base[:BODY_VERTS]
        for side, sign in (("l", 1), ("r", -1)):
            ankle = Vector(self.shape.bones[f"foot_{side}"][0])
            knee = Vector(self.shape.bones[f"calf_{side}"][0])
            foot = body[(body[:, 0] * sign > 0) & (body[:, 2] < self.zAnk + 0.02)]
            front, back = float(foot[:, 1].min()) - 0.014, float(foot[:, 1].max()) + 0.012
            width = float(np.ptp(foot[:, 0])) / 2 + 0.009
            levels = [(-0.006, width, front, back), (0.009, width, front, back),
                      (0.032, width * 0.94, front + 0.010, back - 0.004),
                      (self.zAnk + 0.012, width * 0.83, front + 0.055, back - 0.008)]
            for z in np.linspace(self.zAnk + 0.047, top, 8):
                ring = body[(body[:, 0] * sign > 0) & (np.abs(body[:, 2] - z) < 0.025)]
                radius = max(0.035, float(np.ptp(ring[:, 0])) / 2) + 0.009
                centre_y = float(np.median(ring[:, 1]))
                levels.append((z, radius, centre_y - radius - 0.008, centre_y + radius))
            rows = []
            for z, half, near, far in levels:
                t = max(0, min(1, (z - ankle.z) / (knee.z - ankle.z)))
                centre_x = ankle.x + (knee.x - ankle.x) * t
                centre_y, depth = (near + far) / 2, (far - near) / 2
                rows.append([(centre_x + half * math.sin(az), centre_y - depth * math.cos(az), z)
                             for az in np.linspace(0, 2 * math.pi, 41)])
            shell = grid(rows)
            bmesh.ops.remove_doubles(shell, verts=list(shell.verts), dist=0.00001)
            shell.verts.ensure_lookup_table()
            bottom = sorted([v for v in shell.verts if abs(v.co.z + 0.006) < 0.00001],
                            key=lambda v: math.atan2(v.co.x - ankle.x, v.co.y - (front + back) / 2))
            sole = shell.faces.new(bottom)
            if sole.normal.z > 0: sole.normal_flip()
            shell.normal_update()
            for face in shell.faces:
                if face is sole: continue
                at = face.calc_center_median()
                centre = ankle.lerp(knee, max(0, min(1, (at.z - ankle.z) / (knee.z - ankle.z))))
                if face.normal.dot(Vector((at.x - centre.x, at.y - centre.y, 0))) < 0: face.normal_flip()
            copied = {v: bm.verts.new(v.co) for v in shell.verts}
            for face in shell.faces: bm.faces.new([copied[v] for v in face.verts])
            shell.free()
        self.conform(bm, 0.004, under, rounds=1)
        self.finish(name, bm, 0.003, shade=lambda p: 0.55 if p[2] < 0.012 else 1.0)

    def build_shoes(self):
        self.build_boots("Shoes", self.zAnk + 0.05, ("Body",))

    def build_belt(self):
        z, half = self.zWaist - 0.005, 0.02
        bm = self.body_bmesh(lambda p: abs(p.z - z) < 0.08 and abs(p.x) < 0.3)
        self.iso_clip(bm, lambda p: half - abs(p.z - z))
        self.drop_islands(bm, keep=40)
        self.offset(bm, 0.004)
        self.smooth(bm, 3)
        self.conform(bm, 0.002, ("Body", "Shirt", "Trousers"), rounds=4)
        front = min((v.co.y for v in bm.verts if abs(v.co.x) < 0.01), default=-0.12)
        self.finish("Belt", bm, 0.004)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * 0.046, v.co.y * 0.008, v.co.z * 0.038)) + Vector((0, front - 0.007, z))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.003, segments=2, affect="EDGES")
        self.finish("Buckle", bm, 0.0, surface=False)

    def build_vest(self):
        """A sleeveless wool/leather jerkin with a higher, practical closure."""
        from kit_equipment import grid
        from kit_hair import curve
        body = self.shape.base[:BODY_VERTS]
        strongest = np.argmax(self.weights[:BODY_VERTS], axis=1)
        trunk_bones = [j for j, n in enumerate(self.bone_names) if n in
                       ("pelvis", "spine_01", "spine_02", "spine_03", "neck_01")]
        trunk = body[np.isin(strongest, trunk_bones)]
        top_button, bottom_button = self.zChest + 0.13, self.zWaist + 0.03
        outline = [(0.0, top_button), (0.67, self.zNeck - 0.028), (0.84, self.zNeck - 0.03),
                   (1.25, self.zNeck - 0.20), (math.pi / 2, self.zNeck - 0.23),
                   (1.90, self.zNeck - 0.20), (2.30, self.zNeck - 0.03),
                   (2.48, self.zNeck - 0.028), (math.pi, self.zNeck - 0.070)]
        bm = bmesh.new()
        for side in (1, -1):
            rows = []
            for v in np.linspace(0, 1, 23):
                row = []
                for az in np.linspace(0, math.pi, 37):
                    hem = self.zWaist - 0.052 - 0.045 * math.exp(-((az - 0.28) / 0.3) ** 2)
                    z = hem + (curve(outline, az) - hem) * v
                    ring = trunk[np.abs(trunk[:, 2] - z) < 0.016]
                    if len(ring) < 4:
                        ring = trunk[np.argsort(np.abs(trunk[:, 2] - z))[:40]]
                    half_x = max(0.055, float(np.abs(ring[:, 0]).max())) + 0.019
                    front, back = float(ring[:, 1].min()) - 0.024, float(ring[:, 1].max()) + 0.018
                    centre, depth = (front + back) / 2, (back - front) / 2
                    opening = 0.043 * sstep(bottom_button, self.zWaist - 0.05, z) - 0.003
                    x = side * (math.sin(az) * half_x + opening * (1 - sstep(0, 0.25, az)))
                    row.append((x, centre - depth * math.cos(az), z))
                rows.append(row)
            panel = grid(rows)
            for face in panel.faces:
                centre = face.calc_center_median()
                if face.normal.dot(Vector((centre.x, centre.y - self.yNeck, 0))) < 0:
                    face.normal_flip()
            copied = {vertex: bm.verts.new(vertex.co) for vertex in panel.verts}
            for face in panel.faces:
                bm.faces.new([copied[vertex] for vertex in face.verts])
            panel.free()
        self.taubin(bm, 12, lambda p: abs(p.x) > 0.022)
        self.conform(bm, 0.015, ("Body", "Shirt", "Belt", "Trousers"), rounds=2)
        edge = self.rim_distance(bm)
        def shade(p):
            tone = 0.86 if p[1] > self.yNeck + 0.01 else 1.0
            return tone * (0.78 if edge(p) < 0.006 else 1.0)
        vest = self.finish("Vest", bm, 0.004, surface=False, shade=shade)
        from kit_equipment import hang_from_torso
        hang_from_torso(self, vest, "spine_03")
        self.build_buttons(vest, bottom_button, top_button)

    def build_buttons(self, vest, low, high, count=3):
        """Leather-covered toggles down the jerkin's overlapping front."""
        tree = BVHTree.FromPolygons([tuple(v.co) for v in vest.data.vertices],
                                    [tuple(p.vertices) for p in vest.data.polygons])
        bm = bmesh.new()
        for k in range(count):
            z = high - 0.008 - (high - low - 0.012) * k / (count - 1)
            hit, normal, _i, _d = tree.ray_cast(Vector((0.008, -0.5, z)), Vector((0.0, 1.0, 0.0)), 1.0)
            if hit is None:
                raise RuntimeError(f"no vest in front of button {k} at z={z:.3f}")
            dome = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
            side = normal.cross(Vector((0.0, 0.0, 1.0))).normalized()
            up = side.cross(normal).normalized()
            for v in dome["verts"]:
                c = v.co.copy()
                v.co = hit + normal * (0.002 + 0.003 * c.z) + side * c.x * 0.012 + up * c.y * 0.004
        self.finish("VestButtons", bm, 0.0, surface=False)

    def keep_largest(self, bm):
        """Drop every piece but the biggest (an arm cut off by the armhole)."""
        sizes = []
        seen = set()
        for f in bm.faces:
            if f in seen:
                continue
            stack, island = [f], []
            seen.add(f)
            while stack:
                g = stack.pop()
                island.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h not in seen:
                            seen.add(h)
                            stack.append(h)
            sizes.append(island)
        sizes.sort(key=len)
        bmesh.ops.delete(bm, geom=[f for island in sizes[:-1] for f in island], context="FACES")
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)

    def drape(self, bm, pick, bend=0.15, slope=0.8):
        """Cloth over the chest spans hollows instead of sinking into them:
        across each height the front between the two most forward points
        (the breasts, or a broad chest) is pulled out to their depth, and
        down each column the cloth falls away from what is above it along a
        curve that starts straight down and steepens to [slope] (a shirt
        hangs from the bust, it does not tuck under it). Cloth just under
        the bust that faced the ground went past the toon light's edge in
        the game's high sun and drew two dark spots."""
        def fall(drop):
            return drop * drop / (2 * bend) if drop < bend * slope else slope * (drop - bend * slope / 2)
        front = [v for v in bm.verts if pick(v.co) and self.front(v.co) > 0.3]
        rows: dict[int, list] = {}
        for v in front:
            rows.setdefault(round(v.co.z / 0.008), []).append(v)
        for row in rows.values():
            for sign in (1, -1):
                side = [v for v in row if v.co.x * sign >= 0]
                if side:
                    peak = min(side, key=lambda v: v.co.y)
                    for v in side:
                        if abs(v.co.x) < abs(peak.co.x):
                            v.co.y = min(v.co.y, peak.co.y)
        columns: dict[int, list] = {}
        for v in front:
            columns.setdefault(round(v.co.x / 0.01), []).append(v)
        for column in columns.values():
            column.sort(key=lambda v: -v.co.z)
            hang, at = None, None
            for v in column:
                if hang is not None:
                    v.co.y = min(v.co.y, hang + fall(at - v.co.z))
                if hang is None or v.co.y < hang + fall(at - v.co.z):
                    hang, at = v.co.y, v.co.z
        self.taubin(bm, 30, lambda p: pick(p) and self.front(p) > 0.3)

    @staticmethod
    def rim_distance(bm):
        """A function giving how far a point is from the shell's nearest
        open edge."""
        rim = {v for e in bm.edges if len(e.link_faces) == 1 for v in e.verts}
        tree = kdtree.KDTree(max(len(rim), 1))
        for i, v in enumerate(rim):
            tree.insert(v.co, i)
        tree.balance()
        return lambda p: tree.find(Vector(tuple(p)))[2] if rim else 1.0

    # -- skin under clothes

    def covered(self, name):
        """Skin vertices under a built piece: a ray out along the vertex
        normal meets the piece within 6 cm, or the skin pokes out through it
        by up to 2 cm (a ray in meets it). Legwear also takes all the leg
        skin it spans, so no stray bump shows through. One ring is taken
        off the edge so skin still shows right up to each hem. A tunic hides
        its full covered surface so bent shoulders cannot expose skin."""
        me = self.objects["Body"].data
        obj = self.objects[name]
        tree = BVHTree.FromPolygons([tuple(v.co) for v in obj.data.vertices],
                                    [tuple(p.vertices) for p in obj.data.polygons])
        hidden = {v.index for v in me.vertices
                  if tree.ray_cast(v.co + v.normal * 0.001, v.normal, 0.06)[0] is not None
                  or tree.ray_cast(v.co, -v.normal, 0.02)[0] is not None}
        z = self.shape.base[:BODY_VERTS, 2]
        if name in ("Boots", "Shoes"):  # the whole foot and shaft, toes included
            top = self.zBoot if name == "Boots" else self.zAnk + 0.05
            hidden |= set(np.nonzero(z < top - 0.01)[0].tolist())
        if name == "Trousers":
            legs = [j for j, b in enumerate(self.bone_names) if b.startswith(("thigh_", "calf_", "pelvis"))]
            strongest = np.argmax(self.weights[:BODY_VERTS], axis=1)
            span = (z > self.zBoot - 0.05) & (z < self.zWaist + 0.005)
            hidden |= set(np.nonzero(span & np.isin(strongest, legs))[0].tolist())
        around = {i: set() for i in range(len(me.vertices))}
        for e in me.edges:
            a, b = e.vertices
            around[a].add(b)
            around[b].add(a)
        for _ in range(0 if name == "Shirt" else 1):
            hidden = {i for i in hidden if around[i] <= hidden}
        return np.array(sorted(hidden), dtype=np.int64)

    def add_hide_keys(self, body):
        """Hide.<outfit>: the skin its clothes cover moves most of the way
        to the bone inside it, out of sight under the cloth. Toes go to the
        ball of the foot, so a boot's toe cap never shows them."""
        for name, part in self.spec["parts"].items():
            if part["source"] == "built" and part.get("hides") and name not in self.hides:
                self.hides[name] = self.covered(name)
        base = self.shape.base[:BODY_VERTS]
        strongest = np.argmax(self.weights[:BODY_VERTS], axis=1)
        for outfit, parts in self.spec["slots"]["outfit"].items():
            sets = [self.hides[p] for p in parts if p in self.hides]
            if not sets:
                continue
            co = base.copy()
            for i in np.unique(np.concatenate(sets)):
                bone = self.bone_names[strongest[i]]
                head, tail = (Vector(p) for p in self.shape.bones[bone])
                p = Vector(base[i])
                if bone.startswith("ball_"):
                    core = head
                else:
                    seg = tail - head
                    t = max(0.0, min(1.0, (p - head).dot(seg) / max(seg.length_squared, 1e-9)))
                    core = head + seg * t
                co[i] = tuple(p.lerp(core, 0.75))
            self.add_key(body, f"Hide.{outfit}", co)
            if "Shirt" in parts and "Trousers" in parts:
                trousers = self.objects["Trousers"]
                co = np.array([tuple(v.co) for v in trousers.data.vertices])
                covered = np.clip((co[:, 2] - (self.zHip - 0.10)) / 0.055, 0, 1)
                co[:, :2] *= 1 - 0.85 * covered[:, None]
                self.add_key(trousers, f"Hide.{outfit}", co)
            if "Shirt" in parts and "Apron" in parts:
                shirt = self.objects["Shirt"]
                co = positions(shirt.data.shape_keys.key_blocks["Basis"])
                apron = self.objects["Apron"].data
                tree = BVHTree.FromPolygons([tuple(v.co) for v in apron.vertices],
                                           [tuple(p.vertices) for p in apron.polygons])
                # Covered underlayers retract inside; their moving hems cannot pierce the apron.
                for i, p in enumerate(co):
                    if p[2] < self.shirt_join - 0.02 and p[1] < self.yNeck \
                            and tree.ray_cast(Vector(p), Vector((0, -1, 0)), 0.3)[0] is not None:
                        co[i, 1] = self.yNeck + (p[1] - self.yNeck) * 0.15
                self.add_key(shirt, f"Hide.{outfit}", co)

    # -- clips

    def make_clips(self):
        """Every clip the client asks for, and the sockets it hangs a tool and
        a hauled load from, carried from the folk rig (kit_retarget.py). This
        used to author Idle and Walk here; a real pawn needs all nineteen, and
        the folk already carry them, paced to FigureClips' own constants."""
        poser = Poser(self.armature)
        poser.relax()
        retarget(self, poser)

    # -- output

    def export(self, out: Path):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.export_scene.gltf(
            filepath=str(out), export_format="GLB", export_animation_mode="ACTIONS",
            export_force_sampling=True, export_frame_step=1, export_yup=True, export_apply=False,
            export_skins=True, export_morph=True, export_morph_normal=False, export_try_sparse_sk=True,
            export_try_omit_sparse_sk=True, export_cameras=False, export_lights=False, export_extras=False,
            export_vertex_color="ACTIVE", export_image_format="AUTO", export_def_bones=False,
            export_optimize_animation_size=True, export_optimize_animation_keep_anim_armature=False,
            export_reset_pose_bones=True)

    def bone_manifest(self) -> dict:
        """Bone heads (glTF axes: +Y up, facing +Z) and how far each slider
        end moves them."""
        def gltf(p):
            return [round(float(p[0]), 5), round(float(p[2]), 5), round(float(-p[1]), 5)]
        return {
            "bones": self.bone_names,
            "rest_heads": [gltf(self.shape.bones[b][0]) for b in self.bone_names],
            "keys": {key: [gltf(moved[b][0]) for b in self.bone_names] for key, moved in self.shape.bone_keys.items()},
        }


# ------------------------------------------------------------------ posing

class Poser:
    """Poses the rig by turning bones in armature space and keys only
    rotations, so a clip fits every body shape the sliders make."""

    def __init__(self, armature):
        self.armature = armature
        self.bones = armature.data.bones
        self.order = [b.name for b in self.bones]
        self.rest = {b.name: b.matrix_local.to_quaternion() for b in self.bones}
        self.basis = {}
        self.reset()

    def reset(self):
        self.basis = {n: Quaternion() for n in self.order}

    def world(self, name):
        """Posed armature-space rotation of a bone."""
        bone = self.bones[name]
        if bone.parent is None:
            return self.rest[name] @ self.basis[name]
        parent = bone.parent.name
        return self.world(parent) @ self.rest[parent].inverted() @ self.rest[name] @ self.basis[name]

    def turn(self, name, axis, angle):
        """Turn a bone about an armature-space axis (in its parent's posed
        frame)."""
        r = self.rest[name]
        self.basis[name] = (r.inverted() @ Quaternion(Vector(axis), angle) @ r) @ self.basis[name]

    def aim(self, name, direction):
        """Point a bone (head to tail) along an armature-space direction."""
        g = self.world(name)
        now = g @ Vector((0, 1, 0))
        delta = now.rotation_difference(Vector(direction).normalized())
        self.basis[name] = self.basis[name] @ (g.inverted() @ delta @ g)

    def relax(self):
        """From MakeHuman's A-pose (arms out, forearms forward, legs apart)
        to standing at ease."""
        for s, x in (("l", 1), ("r", -1)):
            foot = self.world(f"foot_{s}") @ Vector((0, 1, 0))
            self.aim(f"upperarm_{s}", (0.2 * x, 0.03, -1))
            self.aim(f"lowerarm_{s}", (0.07 * x, -0.2, -1))
            self.aim(f"hand_{s}", (0.02 * x, -0.12, -1))
            self.aim(f"thigh_{s}", (0.04 * x, 0.0, -1))
            self.aim(f"calf_{s}", (0.03 * x, 0.02, -1))
            self.aim(f"foot_{s}", foot)

    def walk(self, phase):
        for s, shift, x in (("l", 0.0, 1), ("r", math.pi, -1)):
            p = phase + shift
            swing = math.radians(24) * math.sin(p)
            bend = math.radians(6 + 50 * max(0.0, math.cos(p)) ** 2)
            self.turn(f"thigh_{s}", (1, 0, 0), -swing)
            self.turn(f"calf_{s}", (1, 0, 0), bend)
            self.turn(f"foot_{s}", (1, 0, 0), 0.7 * (swing - bend))
            self.turn(f"upperarm_{s}", (1, 0, 0), math.radians(16) * math.sin(p))
            self.turn(f"lowerarm_{s}", (1, 0, 0), -math.radians(8) * (1 - math.sin(p)))
        twist = math.radians(4) * math.sin(phase)
        self.turn("pelvis", (0, 0, 1), twist)
        self.turn("spine_02", (0, 0, 1), -1.6 * twist)
        self.turn("spine_03", (1, 0, 0), math.radians(-2))

    def snapshot(self):
        return dict(self.basis)

    def clip(self, name, keys):
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        self.armature.animation_data_create()
        self.armature.animation_data.action = action
        for frame, basis in keys:
            for bone in self.armature.pose.bones:
                bone.rotation_mode = "QUATERNION"
                bone.rotation_quaternion = basis[bone.name]
                bone.keyframe_insert("rotation_quaternion", frame=frame)
        self.armature.animation_data.action = None
        for bone in self.armature.pose.bones:
            bone.rotation_quaternion = Quaternion()


# ------------------------------------------------------------------ main

def heads_tall(shape: KitShape) -> float:
    """Standing height over the crown-to-chin length."""
    body = shape.base[:BODY_VERTS]
    head, neck = shape.bones["head"][0], shape.bones["neck_01"][0]
    middle = (np.abs(body[:, 0]) < 0.01) & (body[:, 1] < head[1] - 0.06) & (body[:, 2] > neck[2])
    crown = body[:, 2].max()
    return float(crown / (crown - body[middle, 2].min()))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Build the CC0 character kit GLBs.")
    parser.add_argument("--only", choices=("male", "female"))
    parser.add_argument("--out", default=str(KIT))
    parser.add_argument("--preview", help="also render review stills into this folder")
    args = parser.parse_args(argv)

    data = fetch() / "src" / "mpfb" / "data"
    spec = json.loads(SPEC.read_text())
    rig = json.loads((data / "rigs" / "standard" / "rig.game_engine.json").read_text())
    weights = json.loads((data / "rigs" / "standard" / "weights.game_engine.json").read_text())["weights"]
    source = Source(data)
    shapes = {g: KitShape(source, spec, rig, g) for g in spec["bases"]}
    examples = {g: read_example(ROOT / spec["bases"][g]["example"]) for g in spec["bases"]}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for gender in spec["bases"]:
        if args.only and gender != args.only:
            continue
        kit = KitBuilder(source, spec, rig, weights, shapes, examples, gender).build()
        glb = out / f"kit_{gender}.glb"
        kit.export(glb)
        manifest = kit.bone_manifest()
        (out / f"kit_{gender}.bones.json").write_text(json.dumps(manifest, separators=(",", ":")) + "\n")
        provenance = {
            "producer": "build_character_kit.py", "blender": bpy.app.version_string,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "mpfb2_commit": json.loads((HERE / "mpfb2_cc0_sources.json").read_text())["commit"],
            "inputs_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (
                SPEC, Path(__file__).resolve(), HERE / "character_kit_source.py", HERE / "kit_hair.py",
                HERE / "kit_retarget.py", HERE / "kit_garments.py", HERE / "kit_equipment.py",
                HERE / "mpfb2_cc0_sources.json", FOLK_ASSET,
                ROOT / spec["bases"]["male"]["example"], ROOT / spec["bases"]["female"]["example"])},
            "house_style": shapes[gender].style,
            "art_direction": "stylized late-medieval village dress, rough 1500-1600 feel; pre-firearms; owner direction 2026-10-11",
            "approval": "pending owner visual review; TT_KIT_PAWNS remains opt-in",
            "scope": "Thistletide character kit candidate, generated in Blender from CC0 MakeHuman inputs",
        }
        (out / f"kit_{gender}.glb.provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        print(f"wrote {glb} ({glb.stat().st_size // 1024} KiB); {heads_tall(kit.shape):.2f} heads tall")
        if args.preview:
            import kit_preview  # noqa: PLC0415 - dev-only review renders
            kit_preview.render(kit, Path(args.preview))
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    raise SystemExit(main(argv))
