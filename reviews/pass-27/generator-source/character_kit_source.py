"""The CC0 MakeHuman body, its shape targets and its game rig, as numpy arrays.

Everything here reads files fetched by fetch_mpfb2_cc0.py and needs only
numpy (Blender ships it), so the character kit builder and its tests share
one reader. Positions stay in MakeHuman units (decimetres, +Y up, the body
facing +Z) until a caller converts them.

A target is a list of "vertex dx dy dz" moves. A slider is a weighted sum of
targets; its result moves every vertex of the full base mesh, including the
helper shells (hair cap, tights, eye balls) and the small joint cubes that
place the rig's bones. So one slider value moves the skin, the clothes bound
to it and the skeleton together.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

# The CC0 example GLBs (#4300) were exported with the body lifted by this
# much (metres), so their feet stand on y=0. Using the same lift makes their
# clothes, hair and face parts line up with the body built here exactly.
EXAMPLE_LIFT = 0.817742859

BODY_VERTS = 13380  # vertices 0..13379 are the skin; the rest are helpers


class Source:
    """The base mesh plus a cache of the targets read so far."""

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.coords, self.faces, self.face_groups, self.uvs, self.face_uvs = _load_obj(
            self.dir / "3dobjs" / "base.obj")
        groups = json.loads((self.dir / "mesh_metadata" / "basemesh_vertex_groups.json").read_text())
        self.groups = {name: np.concatenate([np.arange(a, b + 1) for a, b in ranges])
                       for name, ranges in groups.items()}
        self._targets: dict[str, np.ndarray] = {}

    def target(self, rel: str) -> np.ndarray:
        if rel not in self._targets:
            delta = np.zeros_like(self.coords)
            path = self.dir / "targets" / f"{rel}.target.gz"
            with gzip.open(path, "rt") as handle:
                for line in handle:
                    if line.startswith("#") or not line.strip():
                        continue
                    index, x, y, z = line.split()
                    delta[int(index)] = (float(x), float(y), float(z))
            self._targets[rel] = delta
        return self._targets[rel]

    def combo(self, pairs, gender: str) -> np.ndarray:
        """Weighted sum of targets; '{g}' in a path becomes the gender."""
        total = np.zeros_like(self.coords)
        for rel, weight in pairs:
            total += weight * self.target(rel.replace("{g}", gender))
        return total

    def body_faces(self) -> tuple[list[list[int]], list[list[int]]]:
        """Skin faces (vertex indices) and their UV indices."""
        keep = [i for i, group in enumerate(self.face_groups) if group == "body"]
        return [self.faces[i] for i in keep], [self.face_uvs[i] for i in keep]

    def cage(self) -> np.ndarray:
        """Indices of every surface clothes may be bound to: skin and helper
        shells, without the joint cubes buried inside the body."""
        cubes = np.concatenate([v for k, v in self.groups.items() if k.startswith("joint-")])
        keep = np.ones(len(self.coords), dtype=bool)
        keep[cubes] = False
        return np.nonzero(keep)[0]


def joints(source: Source, shape: np.ndarray, rig: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Head and tail of every bone for one body shape, placed the way MPFB
    places them: the mean of a joint cube, or of listed vertices."""

    def place(end: dict) -> np.ndarray:
        if end["strategy"] == "CUBE":
            return shape[source.groups[end["cube_name"]]].mean(axis=0)
        if end["strategy"] == "MEAN":
            return shape[end["vertex_indices"]].mean(axis=0)
        if end["strategy"] == "VERTEX":
            return shape[end["vertex_index"]]
        raise ValueError(f"unknown joint strategy {end['strategy']}")

    return {name: (place(bone["head"]), place(bone["tail"])) for name, bone in rig.items()}


def to_blender(points: np.ndarray) -> np.ndarray:
    """MakeHuman decimetres (+Y up, facing +Z) to Blender metres (+Z up,
    facing -Y). Moves only: add EXAMPLE_LIFT to a position."""
    p = np.asarray(points) * 0.1
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], axis=-1)


class KitShape:
    """One base (male or female) as the kit builds it, in Blender space.

    * raw: MakeHuman's own body for this gender, exactly as the CC0 example
      GLB (#4300) was exported, so its clothes and hair fit it.
    * base: raw plus the house style (spec "house_style", then the base's
      own "style" slider values and fixed "targets"), feet on z=0. This is
      the shape every kit character starts from.
    * keys: what each slider end ("Height+", "Height-") adds to base, for
      every vertex of the full mesh, helpers included. Body sliders keep the
      soles on the ground, so a taller person still stands on the floor.
    * expressions: what Blink, Smile and MouthOpen add.
    * bones: head and tail of every rig bone on base; bone_keys: how far
      each slider end moves each bone's head and tail.
    """

    def __init__(self, source: Source, spec: dict, rig: dict, gender: str):
        self.gender = gender
        macro = [(rel, spec["macro_weight"]) for rel in spec["bases"][gender]["macro"]]
        mh_raw = source.coords + source.combo(macro, gender)
        mh_keys = {}
        for slider in spec["sliders"]:
            for sign, end in (("+", "plus"), ("-", "minus")):
                mh_keys[slider["name"] + sign] = source.combo(slider[end], gender)
        style = dict(spec["house_style"])
        style.update(spec["bases"][gender].get("style", {}))
        mh_base = mh_raw.copy()
        for name, value in style.items():
            mh_base += abs(value) * mh_keys[name + ("+" if value > 0 else "-")]
        # Shaping no slider offers (a softer jaw, more open eyes), baked in.
        mh_base += source.combo(spec["bases"][gender].get("targets", []), gender)

        lift = np.array([0.0, 0.0, EXAMPLE_LIFT])
        self.raw = to_blender(mh_raw) + lift
        base = to_blender(mh_base) + lift
        ground = np.array([0.0, 0.0, -base[:BODY_VERTS, 2].min()])
        self.base = base + ground
        self.style = style

        rest = joints(source, mh_base, rig)
        self.bones = {name: (to_blender(h) + lift + ground, to_blender(t) + lift + ground)
                      for name, (h, t) in rest.items()}
        soles = self.base[:BODY_VERTS, 2] < 0.012
        self.keys: dict[str, np.ndarray] = {}
        self.bone_keys: dict[str, dict[str, np.ndarray]] = {}
        for name, mh_delta in mh_keys.items():
            delta = to_blender(mh_delta)
            settle = np.array([0.0, 0.0, delta[:BODY_VERTS][soles, 2].mean()])
            self.keys[name] = delta - settle
            moved = joints(source, mh_base + mh_delta, rig)
            self.bone_keys[name] = {bone: (to_blender(moved[bone][0] - rest[bone][0]) - settle,
                                           to_blender(moved[bone][1] - rest[bone][1]) - settle)
                                    for bone in rest}
        self.expressions = {e["name"]: to_blender(source.combo(e["targets"], gender))
                            for e in spec["expressions"]}


def _load_obj(path: Path):
    coords, uvs, faces, face_uvs, groups = [], [], [], [], []
    group = None
    with path.open() as handle:
        for line in handle:
            if line.startswith("v "):
                coords.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                group = line.split()[1]
            elif line.startswith("f "):
                corners = [token.split("/") for token in line.split()[1:]]
                faces.append([int(c[0]) - 1 for c in corners])
                face_uvs.append([int(c[1]) - 1 for c in corners])
                groups.append(group)
    return np.array(coords), faces, groups, np.array(uvs), face_uvs
