"""Hair the character kit builds itself (build_character_kit.py).

The CC0 MakeHuman hair meshes are photo-strand cards. Under the game's toon
shading they read as a flat helmet or a spiky mop, so the kit builds its
own hair instead, as sculpted illustrated forms:

1. a cap: the scalp pushed out by the hair's volume and cut along a
   hairline (forehead, temples, over the ears, nape), thin at its edge so it
   hugs the skin there;
2. locks: tapered ribbons rooted inside the cap. Each grows from its root
   along the way the hair is combed, then hangs under gravity, sliding over
   the cap, the face and the body instead of passing through them, and ends
   in a point;
3. a painted shade per vertex (darker roots and undersides, a sheen band
   round the crown) that the game multiplies into the hair colour, so the
   locks read apart even in flat light.

A style is a short recipe of lock groups (fringe, crown, hanging locks, bun,
braid) placed by angle round the head, so the same recipe fits every body
the kit makes. Positions are Blender metres, +Z up, the body facing -Y.
"""

from __future__ import annotations

import math

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

BODY_VERTS = 13380
SIDES = 6  # vertices round each lock


def sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def curve(knots, x):
    """Smooth (cosine-eased) interpolation through (x, y) knots."""
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + (y1 - y0) * (1 - math.cos(math.pi * t)) / 2
    return knots[-1][1]


class Head:
    """The head as hair sees it: a centre, the scalp's distance from it in
    every direction, and where the hairline runs."""

    def __init__(self, co, faces, groups, bones, ear_verts):
        body = co[:BODY_VERTS]
        self.skin = BVHTree.FromPolygons([tuple(p) for p in body], faces)
        eyes = [co[groups[f"helper-{s}-eye"]].mean(axis=0) for s in "lr"]
        self.eye = (eyes[0] + eyes[1]) / 2
        self.eye_gap = abs(eyes[0][0] - eyes[1][0])
        self.top = float(body[:, 2].max())
        self.neck = float(bones["head"][0][2])
        # The skull: a sphere fitted to the scalp behind and above the eyes.
        skull = body[(body[:, 2] > self.eye[2] - 0.01) & (body[:, 1] > self.eye[1] + 0.04)]
        a = np.c_[2 * skull, np.ones(len(skull))]
        b = (skull ** 2).sum(axis=1)
        x, *_ = np.linalg.lstsq(a, b, rcond=None)
        self.centre = np.array([0.0, x[1], x[2]])
        self.radius = float(math.sqrt(x[3] + (x[:3] ** 2).sum()))
        # The scalp's distance from the centre, on an (azimuth, elevation)
        # grid: azimuth 0 faces forward, +pi/2 is the body's +X side.
        self.az = np.linspace(-math.pi, math.pi, 145)
        self.el = np.linspace(-1.3, math.pi / 2, 73)
        # A steep ray past the neck can miss it and end on the shoulders;
        # cap the reach there so the scalp stays a head.
        self.reach = np.zeros((len(self.az), len(self.el)))
        for i, az in enumerate(self.az):
            for j, el in enumerate(self.el):
                hit = self.skin.ray_cast(Vector(self.centre), Vector(self.direction(az, el)), 0.4)[0]
                self.reach[i, j] = min((hit - Vector(self.centre)).length, self.radius * 1.35) if hit else self.radius
        ear = body[ear_verts]
        self.ear_top, self.ear_mid = float(ear[:, 2].max()), float(ear[:, 2].mean())
        self.ear_low = float(ear[:, 2].min())
        self.ear_az = self.angles(np.array([ear[:, 0].mean(), ear[:, 1].mean(), self.ear_mid]))[0]

    @staticmethod
    def direction(az, el):
        return np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])

    def angles(self, p):
        d = np.asarray(p, dtype=float) - self.centre
        return math.atan2(d[0], -d[1]), math.atan2(d[2], math.hypot(d[0], d[1]))

    def scalp(self, az, el):
        """Distance from the centre to the scalp (bilinear on the grid)."""
        az = (az + math.pi) % (2 * math.pi) - math.pi
        fi = (az - self.az[0]) / (self.az[1] - self.az[0])
        fj = (min(max(el, self.el[0]), self.el[-1]) - self.el[0]) / (self.el[1] - self.el[0])
        i, j = min(int(fi), len(self.az) - 2), min(int(fj), len(self.el) - 2)
        u, v = fi - i, fj - j
        r = self.reach
        return float((r[i, j] * (1 - u) + r[i + 1, j] * u) * (1 - v) + (r[i, j + 1] * (1 - u) + r[i + 1, j + 1] * u) * v)

    def elevation_at(self, z, az):
        """Elevation of the scalp point at height [z] and azimuth [az]
        (bisection: the scalp's height rises with elevation)."""
        lo, hi = -1.0, 1.4
        for _ in range(30):
            mid = (lo + hi) / 2
            if self.centre[2] + math.sin(mid) * self.scalp(az, mid) < z:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


class HairBuilder:
    """Builds each hair style the spec lists as one mesh with vertex shade
    and bone weights."""

    def __init__(self, head: Head, body_tree: BVHTree, hairline: dict):
        self.head, self.body = head, body_tree
        self.profile = {}
        h = head
        front = h.elevation_at(h.eye[2] + hairline["forehead"], 0.0)
        # Forehead, temple, the sideburn down in front of the ear, up over
        # the ear's root, down behind it and across the nape.
        knots = [(h.ear_az - 0.32, h.ear_mid + hairline["sideburn"]), (h.ear_az - 0.15, h.ear_top + 0.010),
                 (h.ear_az + 0.15, h.ear_top + 0.010), (h.ear_az + 0.42, h.ear_mid),
                 (2.4, h.neck + hairline["nape"] - 0.01), (math.pi, h.neck + hairline["nape"])]
        self.hairline = [(0.0, front), (0.55, front - 0.05)] + [(az, h.elevation_at(z, az)) for az, z in knots]

    def line(self, az):
        return curve(self.hairline, abs(az)) + self.profile.get("nape_trim", 0) * sstep(2.0, 2.8, abs(az))

    # -- the cap

    def cap(self, volume, builder):
        """The hair's base shell: the scalp pushed out by [volume] (metres at
        the crown, thinning to the hairline) and cut along the hairline."""
        h = self.head
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
        for v in bm.verts:
            d = np.array(tuple(v.co))
            d /= np.linalg.norm(d)
            az, el = math.atan2(d[0], -d[1]), math.asin(max(-1.0, min(1.0, d[2])))
            v.co = Vector(h.centre + d * (h.scalp(az, el) + self.thickness(az, el, volume)))
        builder.iso_clip(bm, lambda p: (lambda a: a[1] - self.line(a[0]))(h.angles(tuple(p))))
        builder.drop_islands(bm, keep=50)
        builder.smooth(bm, 2, factor=0.3)
        builder.thicken(bm, 0.0025)
        bm.verts.index_update()
        co = np.array([tuple(v.co) for v in bm.verts])
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        return co, faces

    def thickness(self, az, el, volume):
        above = el - self.line(az)
        profile = self.profile
        crown = sstep(0.2, 1.2, el)
        mass = profile.get("sides", 1.0) * (1 - crown) + profile.get("crown", 1.0) * crown
        mass *= 1 + profile.get("front", 0.0) * max(0.0, math.cos(az)) * crown
        if "part" in profile:
            mass *= 1 - 0.35 * math.exp(-((az - profile["part"]) / 0.12) ** 2)
        clump = profile.get("sculpt", 0.0) * (0.5 + 0.5 * math.cos(az * 7 - el * 2))
        return 0.002 + (volume * mass + clump) * sstep(0.0, 0.55, above)

    def surface(self, az, el, volume, out=0.0):
        """A point [out] metres above the cap."""
        h = self.head
        return h.centre + h.direction(az, el) * (h.scalp(az, el) + self.thickness(az, el, volume) + out)

    # -- locks

    def grow(self, az, el, comb, length, volume, step=0.012, stiff=0.05, drop=1.0, lean=(0.0, 0.0, 0.0),
             lift=0.004, tip_lift=0.0, gap=0.024, floor=None, hug=False, past=None):
        """A lock's centre line: from inside the cap at (az, el), first along
        [comb] (radians from straight down the scalp, + toward +azimuth),
        then bending under gravity once past [stiff] metres. While over the
        upper head (or everywhere, if [hug]: combed-back hair) it lies on the
        cap, [lift] above it (rising by [tip_lift] toward its tip); below
        that it hangs free, [gap] off the skin. It stops at [length], at
        height [floor], or [past] metres after it crosses the hairline."""
        h = self.head
        p = self.surface(az, el, volume, -0.004)
        d = h.direction(az, el)
        down = np.array([0.0, 0.0, -1.0])
        tangent_down = down - d * (d @ down)
        if np.linalg.norm(tangent_down) < 1e-6:
            tangent_down = h.direction(az, el - 0.5) - d
        tangent_down /= np.linalg.norm(tangent_down)
        across = np.cross(d, tangent_down)
        v = tangent_down * math.cos(comb) + across * math.sin(comb)
        path, travelled, below = [p], 0.0, 0.0
        lean = np.asarray(lean, dtype=float)
        while travelled < length and (past is None or below < past):
            pull = drop * sstep(stiff * 0.4, stiff * 1.6, travelled)
            # Lean steers hair hanging past the ears in front of or behind
            # the shoulders (never draped over them), then eases off.
            steer = sstep(h.ear_mid, h.neck - 0.04, p[2]) * (1 - sstep(h.neck - 0.1, h.neck - 0.18, p[2]))
            v = v + down * pull * 0.35 + lean * 0.3 * steer
            v /= np.linalg.norm(v)
            rise = tip_lift * sstep(0.55, 1.0, travelled / length)
            target = p + v * step
            q = self.collide(target, volume, lift + rise, gap, hug)
            if floor is not None and q[2] < floor:
                break
            # Slide: a push off the head or body takes away only the part
            # of the lock's heading that ran into it, so a lock that brushes
            # an ear keeps falling instead of flying out from it.
            push = q - target
            if np.linalg.norm(push) > 1e-9:
                n = push / np.linalg.norm(push)
                v = v - n * min(0.0, float(v @ n))
                v /= np.linalg.norm(v)
            p = q
            path.append(p)
            travelled += step
            q_az, q_el = h.angles(p)
            if q_el < self.line(q_az):
                below += step
        return np.array(path)

    def collide(self, q, volume, lift, gap, hug=False):
        """Keep a lock point on the cap over the upper head (where hair
        lies on the head), and off the cap, face and body elsewhere."""
        h = self.head
        az, el = h.angles(q)
        r = float(np.linalg.norm(q - h.centre))
        if el > -0.9:
            shell = h.scalp(az, el) + self.thickness(az, el, volume) + lift
            # Over an ear, hanging hair lies on the head only above the ear;
            # held to the scalp lower down it would slip in behind the ear
            # and hook out under the lobe.
            ear = abs(abs(az) - h.ear_az) < 0.35 and q[2] < h.ear_top + 0.006
            lies = hug or (el > max(self.line(az) - 0.1, -0.05) and not ear)
            if r < shell or (lies and r < shell + 0.03):
                q = h.centre + (q - h.centre) * (shell / r)
        loc, normal, _i, _d = self.body.find_nearest(Vector(q), 0.2)
        if loc is not None:
            # Round the head (ears included) hair lies close; below the ears
            # it rests on clothes, so keep the full gap there.
            need = gap * sstep(h.ear_low, h.ear_low - 0.06, q[2]) + lift
            s = (Vector(q) - loc).dot(normal)
            if s < need:
                q = np.array(tuple(Vector(q) + normal * (need - s)))
        return q

    def lock(self, path, width, thick=0.32, taper=0.7, blunt=2.2, tip=0.0):
        """A ribbon round [path]: [width] wide at the root, flattened to
        [thick] of its width, tapering to a point ([tip] of its width
        left there, for a blunt cut). The flat faces out from the head (or
        body)."""
        h = self.head
        n = len(path)
        co, shade, faces = [], [], []
        for i, p in enumerate(path[:-1]):
            t = i / (n - 1)
            w = width * (0.45 + 0.55 * sstep(0.0, 0.3, t)) * max((1 - t ** blunt) ** taper, tip)
            tangent = path[i + 1] - path[max(i - 1, 0)]
            tangent /= np.linalg.norm(tangent)
            out = p - h.centre
            if p[2] < h.neck:
                loc, normal, _i, _d = self.body.find_nearest(Vector(p), 0.3)
                if loc is not None:
                    out = np.array(tuple(normal))
            out = out - tangent * (out @ tangent)
            out /= max(np.linalg.norm(out), 1e-9)
            side = np.cross(tangent, out)
            for k in range(SIDES):
                a = 2 * math.pi * k / SIDES
                co.append(p + side * math.cos(a) * w / 2 + out * math.sin(a) * w * thick / 2)
                shade.append(self.paint(p, math.sin(a), t))
        rings = len(co) // SIDES
        co.append(path[-1])
        shade.append(self.paint(path[-1], 0.0, 1.0))
        tip = len(co) - 1
        for r in range(rings - 1):
            for k in range(SIDES):
                a, b = r * SIDES + k, r * SIDES + (k + 1) % SIDES
                faces.append((a, b, b + SIDES, a + SIDES))
        last = (rings - 1) * SIDES
        for k in range(SIDES):
            faces.append((last + k, last + (k + 1) % SIDES, tip))
        root = len(co)
        co.append(path[0] - (path[1] - path[0]) * 0.5)
        shade.append(0.5)
        for k in range(SIDES):
            faces.append(((k + 1) % SIDES, k, root))
        return np.array(co), faces, shade

    def paint(self, p, facing, t):
        """Vertex shade: dark underside and root, a sheen band on the crown."""
        h = self.head
        _az, el = h.angles(p)
        near = np.linalg.norm(p - h.centre) < h.radius + 0.06
        sheen = math.exp(-((el - 0.62) / 0.16) ** 2) if near else 0.0
        tone = 0.62 + 0.24 * max(0.0, facing) + 0.14 * sheen * max(0.0, facing)
        return min(1.0, tone * (0.86 + 0.14 * sstep(0.0, 0.2, t)))

    # -- styles

    def style(self, recipe, builder):
        """One style: its cap plus every lock group of [recipe]."""
        volume = recipe["volume"]
        self.profile = recipe.get("profile", {})
        meshes = []
        co, faces = self.cap(volume, builder)
        shade = [0.55 + 0.3 * math.exp(-((self.head.angles(p)[1] - 0.62) / 0.2) ** 2) for p in co]
        meshes.append((co, faces, shade))
        for group in recipe["locks"]:
            paths = list(self.paths(group, volume))
            for path, width in paths:
                meshes.append(self.lock(path, width, group.get("thick", 0.32), blunt=group.get("blunt", 2.2),
                                        tip=group.get("tip", 0.0)))
            if group.get("sheet"):
                meshes.append(self.sheet([path for path, _w in paths], builder))
        if recipe.get("bun"):
            meshes.extend(self.bun(volume))
        if recipe.get("braid"):
            meshes.extend(self.braid(volume))
        if recipe.get("curls"):
            meshes.extend(self.curls(volume))
        return merge(meshes)

    def curls(self, volume):
        """Broad overlapping coils, with a rounded outer silhouette."""
        meshes = []
        for row, el in enumerate((0.22, 0.68, 1.13)):
            count = 12 if row < 2 else 7
            for i in range(count):
                az = 2 * math.pi * (i + 0.45 * (row % 2)) / count
                rise = max(el, self.line(az) + 0.18)
                path = np.array([self.surface(az + 0.12 * math.sin(t), rise + 0.09 * math.cos(t),
                                             volume, 0.004 + 0.003 * math.sin(t / 2))
                                 for t in np.linspace(0, math.pi * 1.75, 14)])
                meshes.append(self.lock(path, 0.052, thick=0.65, taper=0.15, tip=0.65))
        return meshes

    def sheet(self, paths, builder, reach=0.8, points=24):
        """The mass under a group of hanging locks: a thin sheet joining
        each lock's centre line to its neighbour's, a little under them and
        stopping short of their tips, so the hair reads as one body with
        locks on it, never as separate strands with gaps."""
        h = self.head
        rows = []
        for path in paths:
            run = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
            at = np.linspace(0.0, run[-1] * reach, points)
            row = np.stack([np.interp(at, run, path[:, j]) for j in range(3)], axis=1)
            for k, p in enumerate(row):
                out = p - h.centre
                if p[2] < h.neck:
                    loc, normal, _i, _d = self.body.find_nearest(Vector(p), 0.3)
                    if loc is not None:
                        out = np.array(tuple(normal))
                row[k] = p - out / max(np.linalg.norm(out), 1e-9) * 0.003
            rows.append(row)
        bm = bmesh.new()
        verts = [[bm.verts.new(tuple(p)) for p in row] for row in rows]
        for a, b in zip(verts, verts[1:]):
            for k in range(points - 1):
                bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        f = bm.faces[0]
        mid = f.calc_center_median()
        if f.normal.dot(mid - Vector(h.centre)) < 0:
            for face in bm.faces:
                face.normal_flip()
        builder.thicken(bm, 0.002)
        bm.verts.index_update()
        co = np.array([tuple(v.co) for v in bm.verts])
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        return co, faces, [0.6] * len(co)

    def bun(self, volume):
        """A knot of hair high on the back of the head: a round core wound
        with three locks."""
        h = self.head
        az, el = math.pi, 0.62
        normal = h.direction(az, el)
        centre = self.surface(az, el, volume, 0.028)
        side = np.cross(normal, (0.0, 0.0, 1.0))
        side /= np.linalg.norm(side)
        up = np.cross(side, normal)
        meshes = []
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1.0)
        co = []
        for v in bm.verts:
            d = np.array(tuple(v.co))
            co.append(centre + side * d[0] * 0.034 + up * d[1] * 0.031 + normal * d[2] * 0.024)
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        meshes.append((np.array(co), faces, [self.paint(p, 1.0, 0.5) * 0.85 for p in co]))
        for k in range(3):
            start = 2 * math.pi * k / 3
            path = []
            for i in range(22):
                t = i / 21
                a = start + t * 2 * math.pi * 0.85
                r = 0.03 * (1 - 0.35 * t)
                path.append(centre + (side * math.cos(a) + up * math.sin(a)) * r + normal * (0.012 - 0.01 * t))
            meshes.append(self.lock(np.array(path), 0.026, 0.5, 0.5))
        return meshes

    def braid(self, volume):
        """One plait from the nape down the back: overlapping bulbs leaning
        left and right in turn, then a small tuft."""
        h = self.head
        el = self.line(math.pi) + 0.12
        spine = self.grow(math.pi, el, 0.0, 0.36, volume, step=0.01, stiff=0.02, lift=0.006, gap=0.03)
        meshes = []
        steps = np.cumsum(np.r_[0.0, np.linalg.norm(np.diff(spine, axis=0), axis=1)])
        pitch = 0.03
        for k, s in enumerate(np.arange(0.0, steps[-1] - 0.05, pitch)):
            a = np.array([np.interp(s, steps, spine[:, j]) for j in range(3)])
            b = np.array([np.interp(s + pitch * 1.5, steps, spine[:, j]) for j in range(3)])
            along = b - a
            along /= np.linalg.norm(along)
            side = np.cross(along, (0.0, 1.0, 0.0))
            if np.linalg.norm(side) < 0.3:
                side = np.array([1.0, 0.0, 0.0])
            side /= np.linalg.norm(side)
            lean = side * (0.009 if k % 2 else -0.009)
            fade = 1 - 0.4 * s / steps[-1]
            path = np.array([a - lean, (a + b) / 2 + lean * 0.4, b + lean])
            path = np.array([path[0] + (path[1] - path[0]) * t if t <= 1 else path[1] + (path[2] - path[1]) * (t - 1)
                             for t in np.linspace(0, 2, 7)])
            meshes.append(self.lock(path, 0.034 * fade, 0.6, 0.35))
        end = int(np.searchsorted(steps, steps[-1] - 0.06))
        tuft = spine[end:]
        if len(tuft) >= 3:
            meshes.append(self.lock(tuft, 0.03, 0.5, 0.6))
        return meshes

    def paths(self, group, volume):
        """The centre lines of one lock group: [count] locks spread evenly
        over azimuths [arc] (radians, 0 = front, + = the body's +X side),
        rooted [rise] radians above the hairline."""
        h = self.head
        lo, hi = group["arc"]
        count = group["count"]
        for i in range(count):
            t = (i + 0.5) / count
            az = lo + (hi - lo) * t
            el = group["root_el"] if "root_el" in group else min(self.line(az) + group["rise"], 1.45)
            sway = group.get("sway", 0.0) * math.sin(7.3 * i)
            length = group["length"] * (1 + group.get("ragged", 0.08) * math.sin(5.1 * i + 1.3))
            comb = group.get("comb", 0.0) + sway
            if "comb_by_side" in group:
                comb += group["comb_by_side"] * math.copysign(1.0, az) if abs(az) > 1e-3 else 0.0
            lean = np.array(group.get("lean", (0.0, 0.0, 0.0)), dtype=float)
            if "lean_out" in group:
                lean = lean + group["lean_out"] * np.array([math.sin(az), -math.cos(az), 0.0])
            floor = h.eye[2] + group["stop_above_eyes"] if "stop_above_eyes" in group else None
            if "down_to" in group:
                floor = h.eye[2] + group["down_to"]
            # Neighbours lie at slightly different heights, so overlapping
            # locks layer instead of cutting through each other.
            lift = group.get("lift", 0.004) + 0.0015 * (i % 3)
            path = self.grow(az, el, comb, length, volume, stiff=group.get("stiff", 0.05),
                             drop=group.get("drop", 1.0), lean=lean, lift=lift,
                             tip_lift=group.get("tip_lift", 0.0), floor=floor, hug=group.get("drop", 1.0) == 0.0,
                             past=group.get("past"))
            if "wave" in group:
                for k, p in enumerate(path[1:], 1):
                    angle, elevation = h.angles(p)
                    angle += group["wave"] * math.sin(k / max(len(path) - 1, 1) * math.pi * 2)
                    radius = np.linalg.norm(p - h.centre)
                    path[k] = self.collide(h.centre + h.direction(angle, elevation) * radius,
                                           volume, lift, 0.024)
            if len(path) >= 3:
                yield path, group["width"] * (1 + 0.12 * math.sin(3.7 * i))


def merge(meshes):
    co, faces, shade = [], [], []
    for c, f, s in meshes:
        base = len(co)
        co.extend(tuple(p) for p in c)
        faces.extend(tuple(i + base for i in face) for face in f)
        shade.extend(s)
    return np.array(co), faces, shade


# Lock groups per style. "arc" is azimuth (0 = front, pi = back), "rise"
# is radians above the hairline where the roots sit, "comb" is the root
# direction (radians from straight down the scalp; + toward +azimuth).
STYLES = {
    # Cropped: locks from the crown ending just past the hairline (by the
    # middle of the ear at the sides), textured tips, a fringe swept to one
    # side.
    "short": {"volume": 0.014, "profile": {"sides": 0.35, "crown": 1.1}, "locks": [
        {"arc": (-0.75, 0.55), "count": 5, "root_el": 0.95, "length": 0.12, "width": 0.066, "comb": -0.65,
         "drop": 0.3, "stop_above_eyes": 0.054, "lift": 0.004, "thick": 0.38, "ragged": 0.08},
        {"arc": (0.55, 2.3), "count": 7, "root_el": 1.15, "length": 0.25, "past": 0.012, "down_to": -0.026,
         "width": 0.052, "sway": 0.12, "drop": 0.3, "tip_lift": 0.004, "thick": 0.26, "ragged": 0.06},
        {"arc": (2.3, 3.98), "count": 7, "root_el": 1.15, "length": 0.25, "past": 0.012, "width": 0.052,
         "sway": 0.12, "drop": 0.3, "tip_lift": 0.004, "thick": 0.26, "ragged": 0.06},
        {"arc": (3.98, 5.53), "count": 7, "root_el": 1.15, "length": 0.25, "past": 0.012, "down_to": -0.026,
         "width": 0.052, "sway": 0.12, "drop": 0.3, "tip_lift": 0.004, "thick": 0.26, "ragged": 0.06},
    ]},
    "close_crop": {"volume": 0.004, "profile": {"sides": 0.3, "crown": 1.0, "sculpt": 0.0025, "nape_trim": 0.12}, "locks": [
        {"arc": (-0.9, 0.9), "count": 5, "root_el": 0.85, "length": 0.07, "width": 0.045,
         "comb": -0.25, "drop": 0.0, "lift": 0.001, "thick": 0.2, "tip": 0.4},
        {"arc": (1.35, 4.93), "count": 8, "rise": 0.28, "length": 0.055, "width": 0.048,
         "drop": 0.0, "lift": 0.004, "thick": 0.14, "tip": 0.65},
    ]},
    "swept": {"volume": 0.014, "profile": {"sides": 0.3, "crown": 1.05, "front": 0.1, "sculpt": 0.003}, "locks": [
        {"arc": (-0.85, 0.85), "count": 5, "rise": 0.04, "length": 0.27, "width": 0.065,
         "comb": math.pi, "drop": 0.0, "lift": 0.004, "thick": 0.28, "tip": 0.25},
        {"arc": (1.45, 4.83), "count": 6, "root_el": 0.85, "length": 0.14, "width": 0.066,
         "comb": 0.12, "drop": 0.3, "past": 0.009, "thick": 0.21},
    ]},
    "side_part": {"volume": 0.018, "profile": {"sides": 0.35, "crown": 1.1, "part": 0.4, "sculpt": 0.0025, "nape_trim": 0.06}, "locks": [
        {"arc": (-0.8, 0.2), "count": 4, "root_el": 1.1, "length": 0.20, "width": 0.070,
         "comb": -1.35, "drop": 0.0, "lift": 0.004, "stop_above_eyes": 0.052, "thick": 0.38},
        {"arc": (0.5, 1.0), "count": 2, "rise": 0.2, "length": 0.11, "width": 0.048,
         "comb": 1.0, "drop": 0.0, "lift": 0.002, "thick": 0.25},
        {"arc": (1.1, 5.3), "count": 10, "rise": 0.25, "length": 0.11, "width": 0.05,
         "drop": 0.3, "past": 0.004, "thick": 0.22},
    ]},
    "waves": {"volume": 0.022, "profile": {"sides": 0.7, "crown": 1.2, "front": 0.2}, "locks": [
        {"arc": (-0.8, 0.65), "count": 4, "root_el": 1.15, "length": 0.20, "width": 0.082,
         "comb": -0.9, "drop": 0.3, "wave": 0.18, "stop_above_eyes": 0.026,
         "thick": 0.4, "tip_lift": 0.009, "ragged": 0.12},
        {"arc": (0.85, 5.43), "count": 11, "root_el": 1.25, "length": 0.27, "width": 0.078,
         "wave": 0.16, "past": 0.018, "down_to": -0.04, "thick": 0.4, "tip_lift": 0.008},
    ]},
    "curls": {"volume": 0.023, "profile": {"sides": 0.75, "crown": 1.5}, "curls": True, "locks": []},
    # Chin-length all round, with a full fringe.
    "bob": {"volume": 0.012, "locks": [
        {"arc": (-0.75, 0.75), "count": 9, "root_el": 0.95, "length": 0.16, "width": 0.042, "comb": -0.2,
         "drop": 0.5, "stop_above_eyes": 0.02, "lift": 0.003, "thick": 0.24, "ragged": 0.03},
        # Starts behind the temples: a lock rooted further forward hangs
        # in front of the cheekbone and hooks across the cheek.
        {"arc": (0.95, 5.33), "count": 20, "root_el": 1.15, "length": 0.4, "down_to": -0.095, "width": 0.064,
         "ragged": 0.02, "sheet": True, "thick": 0.22, "blunt": 4.0, "tip": 0.45},
    ]},
    # Past the shoulders: side-swept fringe, face-framing locks in front of
    # the shoulders, the rest down the back.
    "long": {"volume": 0.012, "locks": [
        {"arc": (-0.7, 0.5), "count": 8, "root_el": 0.95, "length": 0.17, "width": 0.042, "comb": -0.7,
         "drop": 0.5, "stop_above_eyes": 0.03, "lift": 0.003, "thick": 0.24, "ragged": 0.04},
        {"arc": (0.85, 1.45), "count": 4, "root_el": 1.15, "length": 0.6, "down_to": -0.36, "width": 0.062,
         "comb_by_side": 0.35, "lean": (0.0, -0.6, 0.0), "sheet": True, "thick": 0.22, "ragged": 0.04},
        {"arc": (-1.45, -0.85), "count": 4, "root_el": 1.15, "length": 0.6, "down_to": -0.36, "width": 0.062,
         "comb_by_side": 0.35, "lean": (0.0, -0.6, 0.0), "sheet": True, "thick": 0.22, "ragged": 0.04},
        {"arc": (1.65, 4.63), "count": 20, "root_el": 1.15, "length": 0.8, "down_to": -0.5, "width": 0.07,
         "ragged": 0.04, "lean": (0.0, 0.6, 0.0), "sheet": True, "thick": 0.22, "blunt": 3.0},
    ]},
    # Gathered into a bun high at the back, two loose strands at the temples.
    "bun": {"volume": 0.01, "bun": True, "locks": [
        {"arc": (-1.0, 1.0), "count": 9, "rise": 0.03, "length": 0.2, "width": 0.045, "comb": math.pi,
         "drop": 0.0, "lift": 0.002},
        {"arc": (1.05, 2.5), "count": 4, "rise": 0.04, "length": 0.13, "width": 0.045, "comb": math.pi,
         "comb_by_side": -0.6, "drop": 0.0, "lift": 0.002},
        {"arc": (-2.5, -1.05), "count": 4, "rise": 0.04, "length": 0.13, "width": 0.045, "comb": math.pi,
         "comb_by_side": -0.6, "drop": 0.0, "lift": 0.002},
        {"arc": (2.55, 3.73), "count": 4, "rise": 0.03, "length": 0.1, "width": 0.045, "comb": math.pi,
         "drop": 0.0, "lift": 0.002},
        {"arc": (-0.95, -0.75), "count": 1, "rise": 0.1, "length": 0.085, "width": 0.026, "stiff": 0.03,
         "comb_by_side": 0.3},
        {"arc": (0.75, 0.95), "count": 1, "rise": 0.1, "length": 0.085, "width": 0.026, "stiff": 0.03,
         "comb_by_side": 0.3},
    ]},
    # Combed back into one plait down the back.
    "braid": {"volume": 0.011, "braid": True, "locks": [
        {"arc": (-1.0, 1.0), "count": 9, "rise": 0.03, "length": 0.27, "width": 0.045, "comb": math.pi,
         "drop": 0.0, "lift": 0.002},
        # Short and rooted well above the ear: lower or longer locks curled
        # round its top.
        {"arc": (1.05, 2.6), "count": 4, "rise": 0.1, "length": 0.1, "width": 0.045, "comb": 0.0,
         "comb_by_side": 1.9, "drop": 0.0, "lift": 0.002},
        {"arc": (-2.6, -1.05), "count": 4, "rise": 0.1, "length": 0.1, "width": 0.045, "comb": 0.0,
         "comb_by_side": 1.9, "drop": 0.0, "lift": 0.002},
    ]},
}
