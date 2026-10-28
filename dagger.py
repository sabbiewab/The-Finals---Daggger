"""Parametric THE FINALS dagger prop, "Recoilless Blade" skin.

Every dimension below was measured off the in-game skin showcase image (side view, knife
rotated level) at 0.405 mm per image pixel, which puts the prop at ~224 mm overall.

  - slim blade: a flat section serrated on both edges near the guard, which splits into
    three fins that twist a full turn like a corkscrew out to the tip
  - slim round tube handle with flared bells into front and rear flanges, eight recessed
    windows, a ring marking out the red band, and a ribbed venturi nozzle as the pommel

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

# Overall scale (1.0 = ~224 mm overall, as measured)
SCALE = 1.0

# Flat serrated section next to the guard: (distance from guard, half width), measured from the skin image
FLAT_PROFILE = [(0.0, 6.9), (13.0, 6.5), (29.0, 6.2), (40.3, 6.2)]
BLADE_THICKNESS = 3.5         # spine thickness
EDGE_THICKNESS = 1.0          # blunt edge for a safe, non-brittle resin prop
GRIND_HALF_ANGLE = 12.0       # degrees, flat grind from edge to full thickness

# Serrations on both edges of the flat section
SERRATION_START = 12.0
SERRATION_END = 39.0
SERRATION_PITCH = 2.6
SERRATION_RADIUS = 1.25

# Corkscrew section: the flat blade splits into three fins that twist like a corkscrew to the tip
CORKSCREW_START = 40.0
CORKSCREW_SPLIT = 8.0         # length over which the third fin grows and the fins spread to 120 degrees
CORKSCREW_TWIST = 220.0       # degrees of twist from CORKSCREW_START to the tip (eased in and out)
# (distance from guard, fin radius from the blade axis); the three fins project ~1.6x this wide
FIN_PROFILE = [(40.0, 6.2), (48.0, 7.8), (60.0, 8.6), (72.0, 8.2), (87.0, 5.8),
               (98.0, 3.6), (104.0, 2.2), (108.0, 0.6)]
FIN_ROOT_THICKNESS = (3.5, 1.2)   # at the corkscrew start and at the tip
FIN_EDGE_THICKNESS = 1.0
CORKSCREW_STATION = 0.3       # mm between lofted cross-sections
CORKSCREW_RAYS = 720          # boundary samples per cross-section
BLADE_LENGTH = FIN_PROFILE[-1][0]

# Handle (all positions are distances back from the guard face)
GRIP_RADIUS = 9.7
FRONT_FLANGE = (0.0, 4.0, 17.2)       # (start, end, radius)
FRONT_BELL_END = 25.0                 # bell flares from the front flange down to the grip
REAR_BELL_START = 80.0                # bell flares from the grip up to the rear flange
REAR_FLANGE = (90.7, 94.8, 15.8)
CAP_END = 99.0                        # domed cap behind the rear flange
NECK = (99.0, 101.3, 5.5)
NOZZLE = (101.3, 116.2, 6.5, 9.1)     # (start, end, start radius, end radius)
NOZZLE_RIBS = 6
NOZZLE_RECESS = (6.5, 5.0)            # (radius, depth) of the venturi opening
WINDOW_DEPTH = 1.5
WINDOW_WIDTH = 4.6
WINDOW_COUNT = 8              # around the tube, alternating row B (facing the blade flat) and row A
WINDOW_ROW_A = [(32.0, 52.6), (60.7, 66.8), (71.3, 77.0)]
WINDOW_ROW_B = [(34.4, 52.6), (60.7, 77.0)]
BAND_START = 54.7             # red band, marked by two paint-guide grooves
BAND_END = 58.3
BAIL_HOLE_RADIUS = 0.7        # holes through the rear flange for a wire lanyard bail

# Tang that joins the separate blade and handle prints
TANG_LENGTH = 50.0
TANG_WIDTH = 9.0
TANG_CLEARANCE = 0.15         # per side, tune for your resin's shrinkage

MESH_EDGE_LENGTH = 0.35       # refinement for the blade grind and twist
REVOLVE_SEGMENTS = 128
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


def smoothCurve(points, values, samples):
    raw = np.interp(samples, points, values)
    kernel = np.exp(-0.5 * (np.linspace(-3, 3, 13) ** 2))
    kernel /= kernel.sum()
    padded = np.pad(raw, 6, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def flatHalfWidth(x):
    """Half width of the flat section at distance x from the guard face."""
    controlX, controlHalfWidth = zip(*FLAT_PROFILE)
    return np.interp(x, controlX, controlHalfWidth)


def flatOutline():
    """Plan-view outline of the flat section, from just inside the guard to the corkscrew."""
    xs = np.linspace(-0.5, FLAT_PROFILE[-1][0], 200)
    hw = smoothCurve(xs, flatHalfWidth(np.clip(xs, 0, None)), xs)
    return Polygon(np.vstack([np.column_stack([xs, hw]), np.column_stack([xs[::-1], -hw[::-1]])]))


def polygonToCrossSection(poly):
    """Shapely polygon (holes allowed) to a manifold CrossSection: outer ring CCW, holes CW."""
    rings = []
    for ring, wantCcw in [(poly.exterior, True)] + [(hole, False) for hole in poly.interiors]:
        coords = np.asarray(ring.coords)[:-1]
        if ring.is_ccw != wantCcw:
            coords = coords[::-1]
        rings.append(coords.tolist())
    return CrossSection(rings)


def serratedOutline(outline):
    """Outline with the serration scallops cut into both edges."""
    cuts = []
    x = SERRATION_START + SERRATION_PITCH / 2.0
    while x + SERRATION_PITCH / 2.0 <= SERRATION_END:
        edgeY = outline.intersection(LineString([(x, 0), (x, 50)])).bounds[3]
        for side in (1, -1):
            y = side * (edgeY + SERRATION_RADIUS * 0.15)
            cuts.append(shapely.Point(x, y).buffer(SERRATION_RADIUS, quad_segs=8))
        x += SERRATION_PITCH
    return outline.difference(shapely.union_all(cuts))


def makeFlatSection():
    """Flat serrated blade, built by warping a refined slab by distance to the smooth edge."""
    smoothOutline = flatOutline()
    slab = Manifold.extrude(polygonToCrossSection(serratedOutline(smoothOutline)), 1.0)
    slab = slab.translate((0, 0, -0.5)).refine_to_length(MESH_EDGE_LENGTH)
    # Grind toward the smooth side edges only: the heel hides in the guard and the far end
    # is buried in the corkscrew, so both stay full thickness.
    sideEdges = shapely.difference(smoothOutline.exterior, shapely.box(-10, -50, 0.5, 50))
    sideEdges = shapely.difference(sideEdges, shapely.box(FLAT_PROFILE[-1][0] - 0.5, -50, 200, 50))
    slope = 2.0 * np.tan(np.radians(GRIND_HALF_ANGLE))

    def warpBatch(verts):
        verts = np.array(verts, dtype=float)
        dist = shapely.distance(shapely.points(verts[:, 0], verts[:, 1]), sideEdges)
        thick = np.minimum(BLADE_THICKNESS, EDGE_THICKNESS + slope * dist)
        # Slab spans z = -0.5..0.5; scale linearly so refined side-wall vertices stay in order.
        verts[:, 2] = verts[:, 2] * thick
        return verts

    return slab.warp_batch(warpBatch)


def finCrossSection(u):
    """Three-fin star cross-section at distance u from the guard, before twisting.

    Fin directions are angles in the YZ plane (y = sin, z = cos). At the corkscrew start two
    fins point along +/-Y like the flat blade; over CORKSCREW_SPLIT they spread to 120 degrees
    apart while the third fin grows out of the +Z face.
    """
    split = np.clip((u - CORKSCREW_START) / CORKSCREW_SPLIT, 0, 1)
    split = split * split * (3 - 2 * split)
    controlU, controlRadius = zip(*FIN_PROFILE)
    radius = float(np.interp(u, controlU, controlRadius))
    along = np.clip((u - CORKSCREW_START) / (BLADE_LENGTH - CORKSCREW_START), 0, 1)
    rootHalf = (FIN_ROOT_THICKNESS[0] + (FIN_ROOT_THICKNESS[1] - FIN_ROOT_THICKNESS[0]) * along) / 2.0
    edgeHalf = min(FIN_EDGE_THICKNESS / 2.0, rootHalf)
    fins = [(90.0 + 30.0 * split, radius), (270.0 - 30.0 * split, radius), (0.0, radius * split)]
    shapes = [shapely.Point(0, 0).buffer(rootHalf, quad_segs=16)]
    for angle, finRadius in fins:
        reach = finRadius - edgeHalf
        if reach <= rootHalf:
            continue
        a = np.radians(angle)
        tip = shapely.Point(reach * np.sin(a), reach * np.cos(a)).buffer(edgeHalf, quad_segs=16)
        shapes.append(shapely.union_all([shapes[0], tip]).convex_hull)
    # Closing adds small fillets where the fins meet the core.
    return shapely.union_all(shapes).buffer(0.4, quad_segs=8).buffer(-0.4, quad_segs=8)


def makeCorkscrew():
    """Loft the twisted three-fin section from inside the flat blade out to the tip."""
    stations = np.arange(CORKSCREW_START - 0.5, BLADE_LENGTH, CORKSCREW_STATION)
    stations = np.append(stations, BLADE_LENGTH)
    rayAngles = np.linspace(0, 2 * np.pi, CORKSCREW_RAYS, endpoint=False)
    rays = [LineString([(0, 0), (30 * np.sin(a), 30 * np.cos(a))]) for a in rayAngles]
    rings = []
    for u in stations:
        # The star is convex along every ray from the axis, so the hit length is the boundary radius.
        reach = shapely.length(shapely.intersection(rays, finCrossSection(u)))
        t = np.clip((u - CORKSCREW_START) / (BLADE_LENGTH - CORKSCREW_START), 0, 1)
        twist = np.radians(CORKSCREW_TWIST) * t * t * (3 - 2 * t)
        rings.append(np.column_stack([np.full(CORKSCREW_RAYS, u),
                                      reach * np.sin(rayAngles + twist), reach * np.cos(rayAngles + twist)]))
    return loftRings(rings)


def loftRings(rings):
    """Closed solid through equal-size rings of points, capped at both ends."""
    count = len(rings[0])
    verts = np.vstack(rings + [rings[0].mean(axis=0, keepdims=True), rings[-1].mean(axis=0, keepdims=True)])
    firstCenter, lastCenter = len(rings) * count, len(rings) * count + 1
    faces = []
    for r in range(len(rings) - 1):
        for i in range(count):
            a, b = r * count + i, r * count + (i + 1) % count
            faces += [[a, b, a + count], [b, b + count, a + count]]
    last = (len(rings) - 1) * count
    for i in range(count):
        faces.append([firstCenter, (i + 1) % count, i])
        faces.append([lastCenter, last + i, last + (i + 1) % count])
    mesh = trimesh.Trimesh(verts, np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return Manifold(Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                         tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


def makeBlade():
    return makeFlatSection() + makeCorkscrew()


def makeTang(clearance=0.0):
    length = TANG_LENGTH + clearance
    width = TANG_WIDTH + 2 * clearance
    thick = BLADE_THICKNESS + 2 * clearance
    return Manifold.cube((length + 1.0, width, thick)).translate(
        (-length, -width / 2.0, -thick / 2.0))


def flangeRim(start, end, radius):
    """Flange rim with 0.8 mm chamfers on both faces."""
    return [(radius - 0.8, start), (radius, start + 0.8), (radius, end - 0.8), (radius - 0.8, end)]


def handleProfile():
    """(radius, distance from guard face) outline of the revolved handle, front to back."""
    frontStart, frontEnd, frontRadius = FRONT_FLANGE
    rearStart, rearEnd, rearRadius = REAR_FLANGE
    profile = [(0.0, frontStart)] + flangeRim(*FRONT_FLANGE)
    # Concave bell from the front flange down into the grip
    bellDrop = frontRadius - 1.0 - GRIP_RADIUS
    for t in np.linspace(0, 1, 32)[1:]:
        profile.append((GRIP_RADIUS + bellDrop * (1 - t) ** 2.2, frontEnd + (FRONT_BELL_END - frontEnd) * t))
    # Grip tube with two paint-guide grooves around the red band
    for u in np.arange(FRONT_BELL_END + 0.5, REAR_BELL_START, 0.5):
        r = GRIP_RADIUS
        if abs(u - BAND_START) < 0.5 or abs(u - BAND_END) < 0.5:
            r -= 0.4
        profile.append((r, u))
    # Concave bell out to the rear flange
    bellRise = rearRadius - 1.0 - GRIP_RADIUS
    for t in np.linspace(0, 1, 24):
        profile.append((GRIP_RADIUS + bellRise * t ** 2.2, REAR_BELL_START + (rearStart - REAR_BELL_START) * t))
    profile += flangeRim(*REAR_FLANGE)
    # Domed cap behind the rear flange, closing down to the nozzle neck
    neckStart, neckEnd, neckRadius = NECK
    capRadius = rearRadius - 4.0
    for t in np.linspace(0, 1, 12):
        profile.append((neckRadius + (capRadius - neckRadius) * np.sqrt(1 - t * t), rearEnd + (CAP_END - rearEnd) * t))
    profile.append((neckRadius, neckEnd))
    # Ribbed venturi nozzle widening toward the end
    nozzleStart, nozzleEnd, startRadius, endRadius = NOZZLE
    ribLength = (nozzleEnd - nozzleStart) / NOZZLE_RIBS
    for i in range(NOZZLE_RIBS):
        u0 = nozzleStart + i * ribLength
        r = startRadius + (endRadius - startRadius) * (i + 1) / NOZZLE_RIBS
        profile += [(r - 0.7, u0 + 0.15), (r, u0 + 0.6), (r, u0 + ribLength - 0.6), (r - 0.7, u0 + ribLength - 0.15)]
    recessRadius, recessDepth = NOZZLE_RECESS
    profile += [(endRadius - 0.3, nozzleEnd), (recessRadius, nozzleEnd),
                (recessRadius - 1.0, nozzleEnd - recessDepth), (0.0, nozzleEnd - recessDepth)]
    return profile


def makeWindowCutters():
    cutters = []
    for k in range(WINDOW_COUNT):
        row = WINDOW_ROW_B if k % 2 == 0 else WINDOW_ROW_A
        for start, end in row:
            stadium = LineString([(-start, 0), (-end, 0)]).buffer(WINDOW_WIDTH / 2.0, quad_segs=12)
            pocket = Manifold.extrude(polygonToCrossSection(stadium), 10.0)
            pocket = pocket.translate((0.5, 0, GRIP_RADIUS - WINDOW_DEPTH))
            cutters.append(pocket.rotate((360.0 * k / WINDOW_COUNT, 0, 0)))
    return Manifold.batch_boolean(cutters, OpType.Add)


def makeBailHoles():
    rearStart, rearEnd, rearRadius = REAR_FLANGE
    holes = []
    for angle in (-20.0, 20.0):
        pin = Manifold.cylinder(10.0, BAIL_HOLE_RADIUS, BAIL_HOLE_RADIUS, 16)
        pin = pin.rotate((0, 90, 0)).translate((-rearEnd - 2.0, 0, -(rearRadius - 2.0)))
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
