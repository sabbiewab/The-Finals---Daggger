"""Parametric THE FINALS dagger prop, "Recoilless Blade" skin.

Every dimension below was measured off the in-game skin showcase image (side view, knife
rotated level) at 0.405 mm per image pixel, which puts the prop at ~224 mm overall.

  - three-edged corkscrew blade: three fins twisting from the guard out to the tip, with
    serrations cut into all three edges near the guard and staggered see-through windows
  - four-cornered front guard flaring into the grip
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

# Blade: three fins that twist like a corkscrew from the guard out to the tip.
# (distance from guard, fin radius from the blade axis); the three fins project ~1.6x this wide,
# so these radii reproduce the silhouette widths measured from the skin image
FIN_PROFILE = [(0.5, 8.0), (13.0, 7.8), (29.0, 7.6), (45.0, 7.9), (60.0, 8.6), (72.0, 8.2),
               (87.0, 5.8), (98.0, 3.6), (104.0, 2.2), (108.0, 0.6)]
FIN_ROOT_THICKNESS = (3.5, 1.2)   # at the guard and at the tip
FIN_EDGE_THICKNESS = 1.0          # blunt edges for a safe, non-brittle resin prop
CORKSCREW_TWIST = 330.0           # degrees of twist from the guard to the tip (eased in and out)
FIN_ANGLES = (90.0, 210.0, 330.0) # fin directions at the guard, in the YZ plane (y = sin, z = cos)
CORKSCREW_STATION = (0.15, 0.4)   # mm between lofted cross-sections: in the serrations, elsewhere
CORKSCREW_RAYS = 360              # boundary samples per cross-section
BLADE_START = FIN_PROFILE[0][0]   # flush with the handle's front face
BLADE_LENGTH = FIN_PROFILE[-1][0]

# Serrations cut into all three fin edges near the guard
SERRATION_START = 12.0
SERRATION_END = 45.0
SERRATION_PITCH = 2.6
SERRATION_RADIUS = 1.25
SERRATION_DEPTH = 0.95

# See-through windows in each fin, staggered from fin to fin as on the skin: (start, end) per fin
FIN_WINDOWS = [[(10.0, 30.0), (50.0, 72.0)],
               [(33.0, 57.0), (68.0, 84.0)],
               [(20.0, 44.0), (60.0, 80.0)]]
WINDOW_RAIL = 2.0             # solid rail left along each fin edge (inside the serrations)
WINDOW_CORE_GAP = 1.0         # solid web left between the core and each window

# Handle (all positions are distances back from the guard face)
GRIP_RADIUS = 9.7
FRONT_FLANGE = (0.0, 4.0, 17.2)       # (start, end, corner radius)
FRONT_BELL_END = 25.0                 # bell flares from the front flange down to the grip
FRONT_DIAMOND = 1.15                  # superellipse exponent of the four-cornered front guard (2 = round)
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
TANG_RADIUS = 6.0             # how far the key's three arms reach from the axis
TANG_CLEARANCE = 0.15         # per side, tune for your resin's shrinkage

REVOLVE_SEGMENTS = 128
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


def polygonToCrossSection(poly):
    """Shapely polygon (holes allowed) to a manifold CrossSection: outer ring CCW, holes CW."""
    rings = []
    for ring, wantCcw in [(poly.exterior, True)] + [(hole, False) for hole in poly.interiors]:
        coords = np.asarray(ring.coords)[:-1]
        if ring.is_ccw != wantCcw:
            coords = coords[::-1]
        rings.append(coords.tolist())
    return CrossSection(rings)


def serrationCut(u):
    """How far the scalloped serrations cut into the fin edges at distance u from the guard."""
    if u < SERRATION_START or u > SERRATION_END:
        return 0.0
    offset = (u - SERRATION_START) % SERRATION_PITCH - SERRATION_PITCH / 2.0
    return max(0.0, np.sqrt(max(SERRATION_RADIUS ** 2 - offset ** 2, 0.0)) - (SERRATION_RADIUS - SERRATION_DEPTH))


def finCrossSection(u):
    """Three-fin star cross-section at distance u from the guard, before twisting.

    Fins point 120 degrees apart in the YZ plane (y = sin, z = cos of the fin angle).
    """
    controlU, controlRadius = zip(*FIN_PROFILE)
    radius = float(np.interp(u, controlU, controlRadius)) - serrationCut(u)
    along = np.clip((u - BLADE_START) / (BLADE_LENGTH - BLADE_START), 0, 1)
    rootHalf = (FIN_ROOT_THICKNESS[0] + (FIN_ROOT_THICKNESS[1] - FIN_ROOT_THICKNESS[0]) * along) / 2.0
    edgeHalf = min(FIN_EDGE_THICKNESS / 2.0, rootHalf)
    core = shapely.Point(0, 0).buffer(rootHalf, quad_segs=16)
    shapes = [core]
    reach = radius - edgeHalf
    if reach > rootHalf:
        for angle in np.radians(FIN_ANGLES):
            tip = shapely.Point(reach * np.sin(angle), reach * np.cos(angle)).buffer(edgeHalf, quad_segs=16)
            shapes.append(shapely.union_all([core, tip]).convex_hull)
    # Closing adds small fillets where the fins meet the core.
    return shapely.union_all(shapes).buffer(0.4, quad_segs=8).buffer(-0.4, quad_segs=8)


def makeBlade():
    """Loft the twisted three-fin section from the guard face out to the tip."""
    fine, coarse = CORKSCREW_STATION
    stations = np.concatenate([np.arange(BLADE_START, SERRATION_START, coarse),
                               np.arange(SERRATION_START, SERRATION_END + fine, fine),
                               np.arange(SERRATION_END + coarse, BLADE_LENGTH, coarse), [BLADE_LENGTH]])
    rayAngles = np.linspace(0, 2 * np.pi, CORKSCREW_RAYS, endpoint=False)
    rays = [LineString([(0, 0), (30 * np.sin(a), 30 * np.cos(a))]) for a in rayAngles]
    rings = []
    for u in stations:
        # The star is convex along every ray from the axis, so the hit length is the boundary radius.
        reach = shapely.length(shapely.intersection(rays, finCrossSection(u)))
        twist = bladeTwist(u)
        rings.append(np.column_stack([np.full(CORKSCREW_RAYS, u),
                                      reach * np.sin(rayAngles + twist), reach * np.cos(rayAngles + twist)]))
    return loftRings(rings).simplify(0.01) - makeFinWindowCutters()


def bladeTwist(u):
    """Corkscrew twist in radians at distance u from the guard, eased in and out."""
    t = np.clip((u - BLADE_START) / (BLADE_LENGTH - BLADE_START), 0, 1)
    return np.radians(CORKSCREW_TWIST) * t * t * (3 - 2 * t)


def makeFinWindowCutters():
    """Twisted slot-shaped cutters that follow each fin, for the see-through windows."""
    controlU, controlRadius = zip(*FIN_PROFILE)
    cutters = []
    for finAngle, windows in zip(FIN_ANGLES, FIN_WINDOWS):
        for start, end in windows:
            rings = []
            for u in np.append(np.arange(start, end, CORKSCREW_STATION[1]), end):
                along = (u - BLADE_START) / (BLADE_LENGTH - BLADE_START)
                rootHalf = (FIN_ROOT_THICKNESS[0] + (FIN_ROOT_THICKNESS[1] - FIN_ROOT_THICKNESS[0]) * along) / 2.0
                inner = rootHalf + WINDOW_CORE_GAP
                outer = float(np.interp(u, controlU, controlRadius)) - WINDOW_RAIL
                if SERRATION_START <= u <= SERRATION_END:
                    outer -= SERRATION_DEPTH
                halfSpan = max((outer - inner) / 2.0, 0.05)
                # Round the window ends: the radial opening closes in a half circle.
                toEnd = min(u - start, end - u)
                half = halfSpan if toEnd >= halfSpan else np.sqrt(max(halfSpan ** 2 - (halfSpan - toEnd) ** 2, 0.0))
                half = max(half, 0.05)
                middle = (inner + outer) / 2.0
                phi = np.radians(finAngle) + bladeTwist(u)
                corners = [(middle - half, -3.0), (middle + half, -3.0), (middle + half, 3.0), (middle - half, 3.0)]
                rings.append(np.array([(u, r * np.sin(phi) + t * np.cos(phi), r * np.cos(phi) - t * np.sin(phi))
                                       for r, t in corners]))
            cutters.append(loftRings(rings))
    return Manifold.batch_boolean(cutters, OpType.Add)


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


def makeTang(clearance=0.0):
    """Y-shaped key tang: the blade's own base cross-section trimmed to TANG_RADIUS.

    It fits inside the blade at the guard, so nothing shows, and it can't spin in the handle.
    """
    key = finCrossSection(BLADE_START).intersection(shapely.Point(0, 0).buffer(TANG_RADIUS, quad_segs=32))
    key = key.buffer(clearance - 0.2, quad_segs=8)
    length = TANG_LENGTH + BLADE_START + 0.3 + clearance
    prism = Manifold.extrude(polygonToCrossSection(key), length)
    # Extrusion runs along Z with the key in XY; map (X, Y, Z) -> (y, z, x) so it runs along X.
    prism = prism.transform([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]])
    return prism.translate((-TANG_LENGTH - clearance, 0, 0))


def flangeRim(start, end, radius):
    """Flange rim with 0.8 mm chamfers on both faces."""
    return [(radius - 0.8, start), (radius, start + 0.8), (radius, end - 0.8), (radius - 0.8, end)]


def handleProfile():
    """(radius, distance from guard face) outline of the revolved handle, front to back."""
    rearStart, rearEnd, rearRadius = REAR_FLANGE
    # The front guard and bell are lofted separately (makeFrontGuard); start just inside the bell.
    # It sits 0.05 mm under the bell surface there, so the union has no coincident faces.
    profile = [(0.0, FRONT_BELL_END - 0.5), (GRIP_RADIUS - 0.05, FRONT_BELL_END - 0.5),
               (GRIP_RADIUS - 0.05, FRONT_BELL_END)]
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


def frontGuardRadius(u):
    """Corner radius of the front guard and bell at distance u back from its front face."""
    start, end, radius = FRONT_FLANGE
    if u <= end:
        # Flange rim with 0.8 mm chamfers on both faces
        return radius - max(0.0, 0.8 - (u - start), 0.8 - (end - u))
    t = min((u - end) / (FRONT_BELL_END - end), 1.0)
    return GRIP_RADIUS + (radius - 1.0 - GRIP_RADIUS) * (1 - t) ** 2.2


def makeFrontGuard():
    """Four-cornered front guard: a diamond-ish flange that flares down into the round grip."""
    start = FRONT_FLANGE[0]
    stations = np.concatenate([np.linspace(start, FRONT_FLANGE[1], 9),
                               np.linspace(FRONT_FLANGE[1], FRONT_BELL_END, 43)[1:]])
    # Offset half a segment from the revolved grip so no vertices coincide where they meet.
    angles = np.linspace(0, 2 * np.pi, REVOLVE_SEGMENTS, endpoint=False) + np.pi / REVOLVE_SEGMENTS
    rings = []
    for u in list(stations) + [FRONT_BELL_END + 0.3]:
        t = np.clip((u - FRONT_FLANGE[1]) / (FRONT_BELL_END - FRONT_FLANGE[1]), 0, 1)
        # Corners stay crisp down most of the bell, then round off into the grip.
        exponent = FRONT_DIAMOND + (2.0 - FRONT_DIAMOND) * t ** 2
        # Past the bell end the ring tucks just inside the grip.
        radius = frontGuardRadius(u) if u <= FRONT_BELL_END else GRIP_RADIUS - 0.3
        reach = radius / (np.abs(np.sin(angles)) ** exponent + np.abs(np.cos(angles)) ** exponent) ** (1 / exponent)
        rings.append(np.column_stack([np.full(len(angles), 0.5 - u), reach * np.sin(angles), reach * np.cos(angles)]))
    return loftRings(rings)


def makeHandle():
    profile = CrossSection([handleProfile()])
    # revolve() spins around Y and puts that axis on Z; turn Z (distance back) into -X.
    handle = Manifold.revolve(profile, REVOLVE_SEGMENTS).rotate((0, -90, 0)).translate((0.5, 0, 0))
    return handle + makeFrontGuard() - makeWindowCutters() - makeBailHoles()


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
