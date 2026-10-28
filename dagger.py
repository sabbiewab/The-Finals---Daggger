"""Parametric THE FINALS dagger prop, "Recoilless Blade" skin.

The skin pairs a slim dagger blade with a recoilless-rifle themed handle:
  - blade serrated on both edges near the guard, then twisting half a turn to the tip,
    with two through-slots along the centerline that spiral with the twist
  - round tube handle with flared front and rear flanges, recessed windows,
    a ring that marks out the red band, and a ribbed venturi nozzle as the pommel

Proportions were measured from in-game skin showcase images and scaled to a ~214 mm prop.

Coordinates: X runs along the knife (guard face at x = 0, tip at +X, pommel at -X),
Y is the blade width direction, Z is the blade thickness direction. Units are mm.

Run:  python3 dagger.py            -> writes stl/dagger_full.stl, stl/dagger_blade.stl, stl/dagger_handle.stl
"""

import os

import numpy as np
import shapely
import trimesh
from manifold3d import CrossSection, Manifold, Mesh, OpType
from shapely.geometry import LineString, Polygon

# Overall scale (1.0 = ~214 mm overall)
SCALE = 1.0

# Blade
BLADE_LENGTH = 105.0          # guard face to tip
BLADE_WIDTH = 18.0            # width of the straight section near the guard
BLADE_THICKNESS = 4.0         # spine thickness (thicker than a real knife so the twist prints strong)
EDGE_THICKNESS = 1.0          # blunt edge for a safe, non-brittle resin prop
GRIND_HALF_ANGLE = 10.0       # degrees, flat grind from edge to full thickness
TIP_RADIUS = 1.0              # rounds the point in plan view

# Twist of the front section
TWIST_START = 40.0            # distance from guard where the twist begins
TWIST_ANGLE = 180.0           # degrees of twist from TWIST_START to the tip

# Through-slots along the centerline, as (start, end) distances from the guard
BLADE_SLOTS = [(31.0, 52.0), (64.0, 80.0)]
SLOT_WIDTH = 3.0

# Serrations on both edges near the guard
SERRATION_START = 12.0
SERRATION_END = 46.0
SERRATION_PITCH = 2.6
SERRATION_RADIUS = 1.3

# Handle (all positions are distances back from the guard face)
GRIP_RADIUS = 13.0
FLANGE_RADIUS = 22.0
WINDOW_DEPTH = 2.0
WINDOW_WIDTH = 4.5
# Window rows around the tube, alternating B/A, as (start, end) spans
WINDOW_COUNT = 6
WINDOW_ROW_A = [(27.5, 46.0), (54.0, 58.0), (64.5, 69.5)]
WINDOW_ROW_B = [(30.5, 46.0), (54.0, 69.5)]
BAND_START = 48.0             # red band, marked by two paint-guide grooves
BAND_END = 53.0
BAIL_HOLE_RADIUS = 0.8        # holes through the rear flange for a wire lanyard bail

# Tang that joins the separate blade and handle prints
TANG_LENGTH = 55.0
TANG_WIDTH = 12.0
TANG_CLEARANCE = 0.15         # per side, tune for your resin's shrinkage

MESH_EDGE_LENGTH = 0.6        # refinement for the blade grind and twist
REVOLVE_SEGMENTS = 128
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


def smoothCurve(points, values, samples):
    raw = np.interp(samples, points, values)
    kernel = np.exp(-0.5 * (np.linspace(-3, 3, 13) ** 2))
    kernel /= kernel.sum()
    padded = np.pad(raw, 6, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def bladeHalfWidth(x):
    """Half width of the blade at distance x from the guard face (straight, then spear point)."""
    controlX = [0, TWIST_START, 60, 80, 95, BLADE_LENGTH]
    controlHalfWidth = np.array([1.0, 1.0, 0.95, 0.76, 0.42, 0.0]) * BLADE_WIDTH / 2.0
    return np.interp(x, controlX, controlHalfWidth)


def bladeOutline():
    """Plan-view outline of the blade as a shapely polygon (rounded tip)."""
    xs = np.linspace(-0.5, BLADE_LENGTH, 400)
    hw = smoothCurve(xs, bladeHalfWidth(np.clip(xs, 0, None)), xs)
    hw[-1] = 0.0
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


def makeBladeBody(outline):
    """Blade with a flat grind, built by warping a refined slab by distance-to-edge."""
    slab = Manifold.extrude(polygonToCrossSection(outline), 1.0).translate((0, 0, -0.5))
    slab = slab.refine_to_length(MESH_EDGE_LENGTH)
    # The heel (x < 0.5) is hidden in the guard; keep it full thickness there.
    edgeOnly = shapely.difference(outline.exterior, shapely.box(-10, -50, 0.5, 50))
    slope = 2.0 * np.tan(np.radians(GRIND_HALF_ANGLE))

    def warpBatch(verts):
        verts = np.array(verts, dtype=float)
        dist = shapely.distance(shapely.points(verts[:, 0], verts[:, 1]), edgeOnly)
        thick = np.minimum(BLADE_THICKNESS, EDGE_THICKNESS + slope * dist)
        # Slab spans z = -0.5..0.5; scale linearly so refined side-wall vertices stay in order.
        verts[:, 2] = verts[:, 2] * thick
        return verts

    return slab.warp_batch(warpBatch)


def makeSerrationCutters(outline):
    cutters = []
    x = SERRATION_START + SERRATION_PITCH / 2.0
    while x + SERRATION_PITCH / 2.0 <= SERRATION_END:
        edgeY = outline.intersection(LineString([(x, 0), (x, 50)])).bounds[3]
        for side in (1, -1):
            cyl = Manifold.cylinder(BLADE_THICKNESS * 4, SERRATION_RADIUS, SERRATION_RADIUS, 32)
            y = side * (edgeY + SERRATION_RADIUS * 0.2)
            cutters.append(cyl.translate((x, y, -BLADE_THICKNESS * 2)))
        x += SERRATION_PITCH
    return Manifold.batch_boolean(cutters, OpType.Add)


def makeSlotCutters():
    cutters = []
    for start, end in BLADE_SLOTS:
        slot = LineString([(start, 0), (end, 0)]).buffer(SLOT_WIDTH / 2.0, quad_segs=12)
        prism = Manifold.extrude(polygonToCrossSection(slot), BLADE_THICKNESS * 4)
        cutters.append(prism.translate((0, 0, -BLADE_THICKNESS * 2)))
    return Manifold.batch_boolean(cutters, OpType.Add)


def twistBlade(blade):
    """Twist the front of the blade about the X axis with a smooth ramp-in."""
    span = BLADE_LENGTH - TWIST_START

    def warpBatch(verts):
        verts = np.array(verts, dtype=float)
        t = np.clip((verts[:, 0] - TWIST_START) / span, 0, 1)
        theta = np.radians(TWIST_ANGLE) * t * t * (3 - 2 * t)
        y, z = verts[:, 1].copy(), verts[:, 2].copy()
        verts[:, 1] = y * np.cos(theta) - z * np.sin(theta)
        verts[:, 2] = y * np.sin(theta) + z * np.cos(theta)
        return verts

    return blade.refine_to_length(MESH_EDGE_LENGTH).warp_batch(warpBatch)


def makeBlade():
    outline = bladeOutline()
    blade = makeBladeBody(outline) - makeSerrationCutters(outline) - makeSlotCutters()
    return twistBlade(blade)


def makeTang(clearance=0.0):
    length = TANG_LENGTH + clearance
    width = TANG_WIDTH + 2 * clearance
    thick = BLADE_THICKNESS + 2 * clearance
    return Manifold.cube((length + 1.0, width, thick)).translate(
        (-length, -width / 2.0, -thick / 2.0))


def handleProfile():
    """(radius, distance from guard face) outline of the revolved handle, front to back."""
    profile = [(0.0, 0.0), (FLANGE_RADIUS - 1.0, 0.0), (FLANGE_RADIUS, 1.0), (FLANGE_RADIUS, 4.5)]
    # Concave bell flaring from the front flange rim down into the grip
    bellDrop = FLANGE_RADIUS - 0.5 - (GRIP_RADIUS + 0.5)
    for t in np.linspace(0, 1, 32)[1:]:
        profile.append((GRIP_RADIUS + 0.5 + bellDrop * (1 - t) ** 2.5, 4.5 + 13.0 * t))
    # Grip tube with a slight taper and two paint-guide grooves around the red band
    for u in np.arange(18.0, 72.0, 0.5):
        r = GRIP_RADIUS + 0.5 - 0.5 * (u - 17.5) / 54.5
        if abs(u - BAND_START) < 0.5 or abs(u - BAND_END) < 0.5:
            r -= 0.5
        profile.append((r, u))
    # Concave bell flaring out to the rear flange rim
    bellRise = FLANGE_RADIUS - 0.5 - GRIP_RADIUS
    for t in np.linspace(0, 1, 24):
        profile.append((GRIP_RADIUS + bellRise * t ** 2.5, 72.0 + 10.5 * t))
    profile += [(FLANGE_RADIUS, 83.0), (FLANGE_RADIUS, 85.5), (FLANGE_RADIUS - 1.0, 86.5)]
    # Domed cap behind the rear flange, then the nozzle neck
    for t in np.linspace(0, 1, 8):
        profile.append((16.0 - 3.0 * t ** 2, 86.5 + 2.5 * t))
    profile += [(6.5, 89.5), (6.5, 92.0)]
    # Ribbed venturi nozzle widening toward the end
    ribCount = 6
    nozzleLength = 16.0
    for i in range(ribCount):
        u0 = 92.0 + i * nozzleLength / ribCount
        u1 = u0 + nozzleLength / ribCount
        r = 7.5 + 2.0 * i / (ribCount - 1)
        profile += [(r, u0 + 0.3), (r + 0.8, u0 + 0.8), (r + 0.8, u1 - 0.8), (r, u1 - 0.3)]
    profile += [(9.5, 108.0), (7.0, 108.0), (5.5, 101.0), (0.0, 101.0)]
    return profile


def makeWindowCutters():
    cutters = []
    for k in range(WINDOW_COUNT):
        row = WINDOW_ROW_B if k % 2 == 0 else WINDOW_ROW_A
        for start, end in row:
            stadium = LineString([(-start, 0), (-end, 0)]).buffer(WINDOW_WIDTH / 2.0, quad_segs=12)
            pocket = Manifold.extrude(polygonToCrossSection(stadium), 10.0)
            pocket = pocket.translate((0, 0, GRIP_RADIUS + 0.5 - WINDOW_DEPTH))
            cutters.append(pocket.rotate((360.0 * k / WINDOW_COUNT, 0, 0)))
    return Manifold.batch_boolean(cutters, OpType.Add)


def makeBailHoles():
    holes = []
    for angle in (-20.0, 20.0):
        pin = Manifold.cylinder(10.0, BAIL_HOLE_RADIUS, BAIL_HOLE_RADIUS, 16)
        pin = pin.rotate((0, 90, 0)).translate((-88.0, 0, -(FLANGE_RADIUS - 2.5)))
        holes.append(pin.rotate((angle, 0, 0)))
    return Manifold.batch_boolean(holes, OpType.Add)


def makeHandle():
    profile = CrossSection([handleProfile()])
    # revolve() spins around Y and puts that axis on Z; turn Z (distance back) into -X.
    handle = Manifold.revolve(profile, REVOLVE_SEGMENTS).rotate((0, -90, 0)).translate((0.5, 0, 0))
    return handle - makeWindowCutters() - makeBailHoles()


def toTrimesh(solid):
    mesh = solid.scale((SCALE, SCALE, SCALE)).to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))


def buildParts():
    bladeWithTang = makeBlade() + makeTang()
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
