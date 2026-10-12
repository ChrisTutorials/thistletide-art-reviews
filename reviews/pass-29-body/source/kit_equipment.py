"""Frontier equipment the saved appearance can actually ask the kit to wear."""

import math

import bmesh
import numpy as np
from mathutils import Vector


def grid(rows):
    bm = bmesh.new()
    verts = [[bm.verts.new(tuple(p)) for p in row] for row in rows]
    for a, b in zip(verts, verts[1:]):
        for i in range(len(a) - 1):
            bm.faces.new((a[i], b[i], b[i + 1], a[i + 1]))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    return bm


def build_equipment(builder, head):
    b = builder
    # An apron hangs from its bib and waist rather than following each thigh.
    rows = []
    hang, _, _, _ = b.bvh_body.ray_cast(Vector((0, -0.7, b.zWaist)), Vector((0, 1, 0)), 1.4)
    if hang is None:
        raise RuntimeError("Apron waist has no body support")
    for z in np.linspace(b.zChest + 0.035, b.zHip - 0.24, 19):
        width = 0.115 + 0.085 * bstep(b.zWaist + 0.12, b.zWaist - 0.04, z)
        row = []
        for x in np.linspace(-width, width, 17):
            at, _, _, _ = b.bvh_body.ray_cast(Vector((x, -0.7, z)), Vector((0, 1, 0)), 1.4)
            y = min(at.y if at else hang.y, hang.y + max(0, b.zWaist - z) * 0.08) - 0.042
            y -= 0.030 * bstep(b.zWaist, b.zHip - 0.24, z)
            fold = 0.004 * math.cos(x / width * math.pi * 3) * bstep(b.zWaist, b.zHip, z)
            row.append((x, y + fold, z))
        rows.append(row)
    bm = grid(rows)
    # Faces look toward -Y.
    if bm.faces[0].normal.y > 0:
        for f in bm.faces:
            f.normal_flip()
    apron = b.finish("Apron", bm, 0.003, surface=False,
                     shade=lambda p: 0.84 + 0.12 * math.cos(p[0] / 0.20 * math.pi * 3) ** 2)
    hang_from_torso(b, apron, "spine_02")

    # A shoulder mantle opening at the chest, with a wider, scalloped hem.
    rows = []
    top, bottom = b.zNeck - 0.015, b.zKnee + 0.13
    for z in np.linspace(top, bottom, 23):
        down = bstep(top, b.zChest - 0.05, z)
        fall = bstep(b.zChest, bottom, z)
        width = 0.084 + 0.145 * down + 0.05 * fall
        depth = 0.071 + 0.095 * down + 0.04 * fall
        row = []
        for az in np.linspace(1.60, 2 * math.pi - 1.60, 41):
            pleat = 0.007 * fall * math.cos(az * 7)
            row.append(((width + pleat) * math.sin(az), b.yNeck + 0.016 - (depth + pleat) * math.cos(az),
                        z + 0.012 * fall ** 4 * math.cos(az * 3)))
        rows.append(row)
    bm = grid(rows)
    bm.faces.ensure_lookup_table()
    if bm.faces[0].normal.dot(bm.faces[0].calc_center_median() - Vector((0, b.yNeck, (top + bottom) / 2))) < 0:
        for f in bm.faces:
            f.normal_flip()
    b.conform(bm, 0.014, ("Body", "Shirt"), rounds=2)
    cloak = b.finish("Cloak", bm, 0.004, surface=False,
                     shade=lambda p: 0.88 + 0.10 * math.cos(math.atan2(p[0], b.yNeck - p[1]) * 7) ** 2)
    hang_from_torso(b, cloak, "spine_03")

    # Rolled neck cloth, low at the front so it clears the jaw.
    rows = []
    for az in np.linspace(0, 2 * math.pi, 33):
        row = []
        for cross in np.linspace(0, 2 * math.pi, 9):
            radius = 0.064 + 0.011 * math.cos(cross)
            row.append((math.sin(az) * radius, b.yNeck - math.cos(az) * radius,
                        b.zNeck + 0.003 + 0.012 * math.sin(cross) - 0.014 * max(0, math.cos(az))))
        rows.append(row)
    scarf = grid(rows)
    bmesh.ops.remove_doubles(scarf, verts=list(scarf.verts), dist=0.00001)
    b.finish("Scarf", scarf, 0, surface=False)

    # Felt crown and a brim with a slight upturn at its sides.
    for name in ("HatCap", "HatBrim"):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=20, radius=1)
        rim_z = head.eye[2] + 0.055
        centre_z = rim_z + 0.008
        height = head.top - centre_z + (0.055 if name == "HatBrim" else 0.035)
        for v in bm.verts:
            v.co = Vector((v.co.x * (head.radius + 0.016), head.centre[1] + v.co.y * (head.radius + 0.020),
                           centre_z + v.co.z * height))
        b.iso_clip(bm, lambda p: p.z - rim_z)
        b.thicken(bm, 0.003)
        if name == "HatBrim":
            rings = []
            for t in np.linspace(0, 1, 5):
                row = []
                for az in np.linspace(0, 2 * math.pi, 49):
                    r = head.radius + 0.012 + t * 0.068
                    row.append((r * math.sin(az), head.centre[1] - r * 1.06 * math.cos(az),
                                rim_z - 0.012 * t ** 2 + 0.003 * t * math.cos(az * 3)))
                rings.append(row)
            brim = grid(rings)
            if brim.faces[0].normal.z < 0:
                for face in brim.faces:
                    face.normal_flip()
            b.thicken(brim, 0.003)
            copied = {v: bm.verts.new(v.co) for v in brim.verts}
            for f in brim.faces:
                bm.faces.new([copied[v] for v in f.verts])
            brim.free()
        hat = b.finish(name, bm, 0, surface=False,
                       shade=lambda p: 0.66 if abs(p[2] - rim_z - 0.014) < 0.008 else 1.0)
        for group in list(hat.vertex_groups):
            hat.vertex_groups.remove(group)
        hat.vertex_groups.new(name="head").add(list(range(len(hat.data.vertices))), 1.0, "REPLACE")

    # Facial hair is an independent slot and follows expressions with the face.
    reach = np.linalg.norm(b.source.target("mouth/mouth-lowerlip-volume-incr")[:13380], axis=1)
    lip = b.shape.base[:13380][reach > reach.max() * 0.3]
    mouth = float(np.median(lip[:, 2]))
    for name, thickness in (("BeardStubble", 0.0007), ("BeardShort", 0.005),
                             ("BeardFull", 0.017), ("Moustache", 0.004)):
        low = mouth - 0.085
        if name == "BeardStubble":
            low = mouth - 0.055
        bm = b.body_bmesh(lambda p: low - 0.04 < p.z < mouth + 0.025 and p.y < head.eye[1] + 0.06)
        b.iso_clip(bm, lambda p: p.z - low)
        b.iso_clip(bm, lambda p: head.centre[1] + 0.005 - p.y)
        b.iso_clip(bm, lambda p: 0.082 - abs(p.x))
        if name == "Moustache":
            b.iso_clip(bm, lambda p: p.z - mouth + 0.004)
            b.iso_clip(bm, lambda p: mouth + 0.012 - p.z)
            b.iso_clip(bm, lambda p: 0.040 - abs(p.x))
        else:
            b.iso_clip(bm, lambda p: mouth + 0.014 * bstep(0.025, 0.065, abs(p.x)) - p.z)
            b.iso_clip(bm, lambda p: max(abs(p.x) - 0.027, mouth - 0.012 - p.z))
        edge = b.rim_distance(bm)
        b.offset(bm, thickness)
        if name != "BeardStubble":
            for v in bm.verts:
                flow = math.atan2(v.co.x, head.centre[1] - v.co.y)
                v.co.y -= thickness * 0.45 * math.cos(flow * 13) ** 2
        if name == "BeardFull":
            for v in bm.verts:
                v.co.z -= 0.040 * bstep(mouth - 0.025, low + 0.005, v.co.z) * (1 - bstep(0.02, 0.08, abs(v.co.x)))
        beard = b.finish(name, bm, 0 if name == "BeardStubble" else 0.001, surface=False,
                         shade=lambda p: 0.78 + 0.22 * math.cos(p[0] * 115) ** 2,
                         smooth_edges=name != "BeardStubble")
        if name == "BeardStubble":
            colors = beard.data.color_attributes["Color"].data
            for vertex in beard.data.vertices:
                rgb = colors[vertex.index].color
                colors[vertex.index].color = (*rgb[:3], bstep(0, 0.012, edge(vertex.co)))


def bstep(a, b, x):
    t = max(0, min(1, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def hang_from_torso(builder, obj, upper):
    """A hanging panel follows the torso, never individual arms or thighs."""
    weights = np.zeros((len(obj.data.vertices), len(builder.bone_names)), dtype=np.float32)
    for vertex in obj.data.vertices:
        rise = bstep(builder.zWaist - 0.04, builder.zChest, vertex.co.z)
        weights[vertex.index, builder.bone_names.index("pelvis")] = 1 - rise
        weights[vertex.index, builder.bone_names.index(upper)] = rise
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)
    builder.set_weights(obj, weights)
