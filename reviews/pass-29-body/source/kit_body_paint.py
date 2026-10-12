"""Broad anatomical paint fields, baked once and carried by the MakeHuman mesh."""
import numpy as np


def skin_coordinates(co, normals, neck, chest, waist, knee, ankle):
    x, y, z = co.T  # Blender: Z up, front is -Y
    wash = np.sin(x * 12 + z * 4.5) * np.cos(z * 3.1 + y * 8)
    front = np.clip(-normals[:, 1], 0, 1)
    torso = np.exp(-(x / 0.27) ** 4)
    collar = np.exp(-((z - (neck - 0.09 + np.abs(x) * 0.16)) / 0.025) ** 2) * front * torso
    ribs = np.exp(-((np.abs(x) - 0.12) / 0.055) ** 2) * np.exp(-((z - (chest - 0.10)) / 0.20) ** 2) * front
    waist_shadow = np.exp(-((z - waist) / 0.12) ** 2) * np.clip(np.abs(normals[:, 0]), 0, 1)
    sternum = np.exp(-(x / 0.055) ** 2) * np.exp(-((z - (chest + 0.10)) / 0.18) ** 2) * front
    knee_warmth = np.exp(-((z - knee) / 0.075) ** 2) * front
    shin = np.clip((z - ankle) / 0.10, 0, 1) * np.clip((knee - z) / 0.10, 0, 1) * front
    # Broad washes model the collar, ribcage and shin; warm joints interrupt
    # the uniform skin tint without inventing dirt, scars or character history.
    tone = (0.86 + 0.14 * wash + 0.08 * normals[:, 2] + 0.08 * sternum
            + 0.06 * shin - 0.22 * collar - 0.14 * ribs - 0.10 * waist_shadow)
    warmth = 0.50 + 0.36 * wash + 0.14 * normals[:, 2] + 0.18 * knee_warmth - 0.16 * ribs
    # Keep facial detail frozen: the body study changes broad form/material,
    # while the pre-existing lip/cheek paint remains its own vertex color.
    head = np.clip((z - neck) / 0.10, 0, 1)
    tone = tone * (1 - head) + (0.93 + 0.025 * wash) * head
    warmth = warmth * (1 - head) + (0.55 + 0.07 * wash) * head
    uv = np.column_stack((np.clip(tone, 0.60, 1.05), np.clip(warmth, 0.05, 0.95))).astype(np.float32)
    if not np.isfinite(uv).all(): raise ValueError('Body paint contains nonfinite coordinates')
    return uv


def bake_body_paint(builder):
    mesh = builder.objects['Body'].data
    mesh.update()
    co = np.array([tuple(v.co) for v in mesh.vertices])
    normals = np.array([tuple(v.normal) for v in mesh.vertices])
    uv = skin_coordinates(co, normals, builder.zNeck, builder.zChest, builder.zWaist, builder.zKnee, builder.zAnk)
    # Blender flips V on export; encode it so glTF carries warmth directly.
    uv[:, 1] = 1 - uv[:, 1]
    corners = np.array([loop.vertex_index for loop in mesh.loops])
    layer = mesh.uv_layers.new(name='BodyPaint')
    layer.data.foreach_set('uv', uv[corners].ravel())
    mesh.uv_layers.active_index = 0
