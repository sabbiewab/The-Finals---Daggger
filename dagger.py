"""Parametric THE FINALS dagger prop, based on the Fox Knives FX-647 S (Elementum dagger).

Reference specs (retailer listings, e.g. Knivesandtools FOFX-647S):
  blade length 100 mm, overall ~200-206 mm, handle ~100 mm,
  blade height 30 mm, blade thickness 3 mm, partially serrated edge.

Coordinates: X runs along the knife (guard face at x = 0, tip at +X, pommel at -X),
Y is the blade width direction, Z is the blade thickness direction. Units are mm.

Run:  python3 dagger.py            -> writes stl/dagger_full.stl, stl/dagger_blade.stl, stl/dagger_handle.stl
"""

import os

import numpy as np
import shapely
import trimesh
from manifold3d import CrossSection, Manifold, Mesh, OpType
from shapely.geometry import Polygon

# Overall scale (1.0 = real FX-647 S size)
SCALE = 1.0

# Blade
BLADE_LENGTH = 100.0          # guard face to tip
BLADE_WIDTH = 28.0            # max width (spec lists 30 mm blade height incl. guard overlap)
BLADE_THICKNESS = 3.0         # spine / flat thickness
EDGE_THICKNESS = 1.0          # blunt edge for a safe, non-brittle resin prop
GRIND_HALF_ANGLE = 8.0        # degrees, flat grind from edge to full thickness
TIP_RADIUS = 1.0              # rounds the point in plan view

# Serrations on one edge, near the guard
SERRATION_START = 6.0
SERRATION_END = 40.0
SERRATION_PITCH = 4.5
SERRATION_RADIUS = 2.0

# Handle
HANDLE_LENGTH = 103.0
LANYARD_HOLE_RADIUS = 3.0
LANYARD_HOLE_POS = 92.0       # distance from guard face

# Tang that joins the separate blade and handle prints
TANG_LENGTH = 60.0
TANG_WIDTH = 12.0
TANG_CLEARANCE = 0.15         # per side, tune for your resin's shrinkage

MESH_EDGE_LENGTH = 0.6        # refinement for the blade grind surface
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


def bladeHalfWidth(x):
    """Half width of the blade at distance x from the guard face."""
    halfWidth = BLADE_WIDTH / 2.0
    baseHalfWidth = halfWidth - 1.0
    bellyStart = 18.0
    x = np.asarray(x, dtype=float)
    # Slight swell from the guard to the belly, then a curved spear-point taper.
    swell = baseHalfWidth + (halfWidth - baseHalfWidth) * np.clip(x / bellyStart, 0, 1)
    taperPos = np.clip((x - bellyStart) / (BLADE_LENGTH - bellyStart), 0, 1)
    return swell * (1.0 - taperPos ** 1.8)


def bladeOutline():
    """Plan-view outline of the blade as a shapely polygon (rounded tip)."""
    xs = np.linspace(-0.5, BLADE_LENGTH, 400)
    hw = bladeHalfWidth(np.clip(xs, 0, None))
    upper = np.column_stack([xs, hw])
    lower = np.column_stack([xs[::-1], -hw[::-1]])
    outline = Polygon(np.vstack([upper, lower[1:-1]]))
    # Morphological opening rounds the convex point without changing the rest.
    return outline.buffer(-TIP_RADIUS, quad_segs=16).buffer(TIP_RADIUS, quad_segs=16)


def polygonToCrossSection(poly):
    coords = np.asarray(poly.exterior.coords)[:-1]
    if not poly.exterior.is_ccw:
        coords = coords[::-1]
    return CrossSection([coords.tolist()])


def makeBladeBody():
    """Blade with a flat grind, built by warping a refined slab by distance-to-edge."""
    outline = bladeOutline()
    slab = Manifold.extrude(polygonToCrossSection(outline), 1.0).translate((0, 0, -0.5))
    slab = slab.refine_to_length(MESH_EDGE_LENGTH)
    boundary = outline.exterior
    # The heel (x < 0.5) is hidden in the guard; keep it full thickness there.
    edgeOnly = shapely.difference(boundary, shapely.box(-10, -50, 0.5, 50))
    slope = 2.0 * np.tan(np.radians(GRIND_HALF_ANGLE))

    def warpBatch(verts):
        verts = np.array(verts, dtype=float)
        dist = shapely.distance(shapely.points(verts[:, 0], verts[:, 1]), edgeOnly)
        thick = np.minimum(BLADE_THICKNESS, EDGE_THICKNESS + slope * dist)
        # Slab spans z = -0.5..0.5; scale linearly so refined side-wall vertices stay in order.
        verts[:, 2] = verts[:, 2] * thick
        return verts

    return slab.warp_batch(warpBatch)


def makeSerrationCutters():
    cutters = []
    x = SERRATION_START + SERRATION_PITCH / 2.0
    while x + SERRATION_PITCH / 2.0 <= SERRATION_END:
        y = float(bladeHalfWidth(x)) + SERRATION_RADIUS * 0.45
        cyl = Manifold.cylinder(BLADE_THICKNESS * 4, SERRATION_RADIUS, SERRATION_RADIUS, 48)
        cutters.append(cyl.translate((x, y, -BLADE_THICKNESS * 2)))
        x += SERRATION_PITCH
    return Manifold.batch_boolean(cutters, OpType.Add) if cutters else Manifold()


def makeTang(clearance=0.0):
    length = TANG_LENGTH + clearance
    width = TANG_WIDTH + 2 * clearance
    thick = BLADE_THICKNESS + 2 * clearance
    return Manifold.cube((length + 1.0, width, thick)).translate(
        (-length, -width / 2.0, -thick / 2.0))


def smoothCurve(points, values, samples):
    raw = np.interp(samples, points, values)
    kernel = np.exp(-0.5 * (np.linspace(-3, 3, 13) ** 2))
    kernel /= kernel.sum()
    padded = np.pad(raw, 6, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def makeHandle():
    """Lofted superellipse handle: integral guard, grooved grip, flared pommel."""
    controlU = [0, 5, 8, 14, 30, 55, 80, 92, 97, HANDLE_LENGTH]
    controlWidth = [34, 34, 30, 25, 24, 22.5, 24, 26, 25, 21]
    controlThick = [14, 15, 17, 19, 20, 20.5, 20, 19, 18, 15]
    uSamples = np.linspace(0, HANDLE_LENGTH, int(HANDLE_LENGTH * 2) + 1)
    widths = smoothCurve(controlU, controlWidth, uSamples)
    thicks = smoothCurve(controlU, controlThick, uSamples)

    # Shallow grip rings between the guard and the pommel swell
    groove = np.where((uSamples > 18) & (uSamples < 86),
                      0.5 * (1 - np.cos(2 * np.pi * (uSamples - 18) / 6.8)), 0.0)
    shrink = 1.0 - 0.6 * groove / (widths / 2.0)

    segments = 72
    theta = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    exponent = 2.6
    cosT, sinT = np.cos(theta), np.sin(theta)
    superX = np.sign(cosT) * np.abs(cosT) ** (2 / exponent)
    superY = np.sign(sinT) * np.abs(sinT) ** (2 / exponent)

    rings = []
    for u, w, t, s in zip(uSamples, widths, thicks, shrink):
        ring = np.column_stack([np.full(segments, -u + 0.5),
                                superX * w / 2 * s, superY * t / 2 * s])
        rings.append(ring)
    verts = np.vstack(rings + [[[0.5, 0, 0]], [[-HANDLE_LENGTH + 0.5, 0, 0]]])
    ringCount = len(rings)
    frontCenter, backCenter = ringCount * segments, ringCount * segments + 1

    faces = []
    for r in range(ringCount - 1):
        for i in range(segments):
            a = r * segments + i
            b = r * segments + (i + 1) % segments
            c = a + segments
            d = b + segments
            faces += [[a, c, b], [b, c, d]]
    for i in range(segments):
        faces.append([frontCenter, i, (i + 1) % segments])
        last = (ringCount - 1) * segments
        faces.append([backCenter, last + (i + 1) % segments, last + i])

    mesh = trimesh.Trimesh(verts, np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    handle = Manifold(Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                           tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))

    hole = Manifold.cylinder(40, LANYARD_HOLE_RADIUS, LANYARD_HOLE_RADIUS, 48)
    hole = hole.translate((-LANYARD_HOLE_POS + 0.5, 0, -20))
    return handle - hole


def toTrimesh(solid):
    mesh = solid.scale((SCALE, SCALE, SCALE)).to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))


def buildParts():
    blade = makeBladeBody() - makeSerrationCutters()
    bladeWithTang = blade + makeTang()
    handle = makeHandle()
    return {
        "dagger_full": bladeWithTang + handle,
        "dagger_blade": bladeWithTang,
        "dagger_handle": handle - makeTang(TANG_CLEARANCE),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, solid in buildParts().items():
        mesh = toTrimesh(solid)
        path = os.path.join(OUT_DIR, name + ".stl")
        mesh.export(path)
        size = mesh.bounds[1] - mesh.bounds[0]
        print(f"{name}: watertight={mesh.is_watertight} volume={mesh.volume / 1000:.1f} cm^3 "
              f"size={size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm -> {path}")


if __name__ == "__main__":
    main()
