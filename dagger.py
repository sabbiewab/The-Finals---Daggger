"""Parametric THE FINALS dagger prop, "Recoilless Blade" skin.

Every dimension below was measured off the in-game skin showcase image (side view, knife
rotated level) at 0.405 mm per image pixel, which puts the prop at ~224 mm overall.

  - slim blade, serrated on both edges near the guard, twisting along its whole length
    (a gentle real twist plus carved spiral lobe lines), with two through-slots
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
from manifold3d import CrossSection, Manifold, OpType
from shapely.geometry import LineString, Polygon

# Overall scale (1.0 = ~224 mm overall, as measured)
SCALE = 1.0

# Blade outline: (distance from guard, half width) measured from the skin image
BLADE_PROFILE = [(0.0, 6.9), (13.0, 6.5), (29.0, 6.2), (45.0, 6.2), (60.0, 6.6),
                 (70.0, 6.6), (80.0, 5.9), (90.0, 4.6), (98.0, 3.2), (104.0, 1.8), (108.0, 0.0)]
BLADE_LENGTH = BLADE_PROFILE[-1][0]
BLADE_THICKNESS = 3.5         # spine thickness
EDGE_THICKNESS = 1.0          # blunt edge for a safe, non-brittle resin prop
GRIND_HALF_ANGLE = 12.0       # degrees, flat grind from edge to full thickness
TIP_RADIUS = 0.8              # rounds the point in plan view

# Twist runs along the whole blade
TWIST_START = 8.0             # distance from guard where the twist begins
TWIST_ANGLE = 40.0            # degrees of real twist from TWIST_START to the tip

# Spiral lobe lines carved into both faces: they trace the edges of a half-turn twisted
# ribbon (y = +/- halfWidth * cos(phase)), which gives the skin's corkscrew look while
# keeping the top-down outline full width
SPIRAL_START = 18.0           # distance from guard where the lines leave the edges
SPIRAL_PHASE = (40.0, 180.0)  # degrees of phase at SPIRAL_START and at the tip
SPIRAL_DEPTH = 0.7
SPIRAL_WIDTH = 1.1            # gaussian half width of the groove

# Through-slots along the centerline, as (start, end) distances from the guard
BLADE_SLOTS = [(33.0, 57.5), (70.0, 84.0)]
SLOT_WIDTH = 2.4

# Serrations on both edges near the guard
SERRATION_START = 12.0
SERRATION_END = 50.0
SERRATION_PITCH = 2.6
SERRATION_RADIUS = 1.25

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


def bladeHalfWidth(x):
    """Half width of the blade at distance x from the guard face."""
    controlX, controlHalfWidth = zip(*BLADE_PROFILE)
    return np.interp(x, controlX, controlHalfWidth)


def bladeOutline():
    """Plan-view outline of the blade as a shapely polygon (rounded tip)."""
    xs = np.linspace(-0.5, BLADE_LENGTH, 500)
    hw = smoothCurve(xs, bladeHalfWidth(np.clip(xs, 0, None)), xs)
    hw[-1] = 0.0
    upper = np.column_stack([xs, hw])
    lower = np.column_stack([xs[::-1], -hw[::-1]])
    outline = Polygon(np.vstack([upper, lower[1:-1]]))
    # Morphological opening rounds the convex point without changing the rest.
    return outline.buffer(-TIP_RADIUS, quad_segs=16).buffer(TIP_RADIUS, quad_segs=16)


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
    """Blade outline with the serration scallops and through-slots cut in 2D."""
    cuts = []
    x = SERRATION_START + SERRATION_PITCH / 2.0
    while x + SERRATION_PITCH / 2.0 <= SERRATION_END:
        edgeY = outline.intersection(LineString([(x, 0), (x, 50)])).bounds[3]
        for side in (1, -1):
            y = side * (edgeY + SERRATION_RADIUS * 0.15)
            cuts.append(shapely.Point(x, y).buffer(SERRATION_RADIUS, quad_segs=8))
        x += SERRATION_PITCH
    for start, end in BLADE_SLOTS:
        cuts.append(LineString([(start, 0), (end, 0)]).buffer(SLOT_WIDTH / 2.0, quad_segs=12))
    return outline.difference(shapely.union_all(cuts))


def spiralGrooveDepth(x, y, thick):
    """Depth of the spiral lobe grooves on each face at blade points (x, y)."""
    t = np.clip((x - SPIRAL_START) / (BLADE_LENGTH - SPIRAL_START), 0, 1)
    phase = np.radians(SPIRAL_PHASE[0] + (SPIRAL_PHASE[1] - SPIRAL_PHASE[0]) * t)
    lineY = bladeHalfWidth(x) * np.cos(phase)
    groove = np.maximum(np.exp(-((y - lineY) / SPIRAL_WIDTH) ** 2),
                        np.exp(-((y + lineY) / SPIRAL_WIDTH) ** 2))
    # Fade in from the start, and fade out over the edge bevels so the edges stay clean
    fade = np.clip((x - SPIRAL_START) / 6.0, 0, 1) * np.clip((thick - 2.0) / 1.0, 0, 1)
    return SPIRAL_DEPTH * groove * fade


def twistAngle(x):
    """Real twist about the X axis, ramping in smoothly after TWIST_START."""
    t = np.clip((x - TWIST_START) / (BLADE_LENGTH - TWIST_START), 0, 1)
    return np.radians(TWIST_ANGLE) * t * t * (2 - t)


def makeBlade():
    """Refined slab of the 2D outline, warped into the grind, spiral grooves and twist."""
    smoothOutline = bladeOutline()
    outline = serratedOutline(smoothOutline)
    slab = Manifold.extrude(polygonToCrossSection(outline), 1.0).translate((0, 0, -0.5))
    slab = slab.refine_to_length(MESH_EDGE_LENGTH)
    # Grind toward the smooth outer edge, so the serrations cut through a clean bevel and the
    # slots stay full thickness. The heel (x < 0.5) is hidden in the guard and stays full too.
    edgeOnly = shapely.difference(smoothOutline.exterior, shapely.box(-10, -50, 0.5, 50))
    slope = 2.0 * np.tan(np.radians(GRIND_HALF_ANGLE))

    def warpBatch(verts):
        verts = np.array(verts, dtype=float)
        x, y = verts[:, 0], verts[:, 1]
        dist = shapely.distance(shapely.points(x, y), edgeOnly)
        thick = np.minimum(BLADE_THICKNESS, EDGE_THICKNESS + slope * dist)
        thick -= 2.0 * spiralGrooveDepth(x, y, thick)
        # Slab spans z = -0.5..0.5; scale linearly so refined side-wall vertices stay in order.
        z = verts[:, 2] * thick
        theta = twistAngle(x)
        verts[:, 1] = y * np.cos(theta) - z * np.sin(theta)
        verts[:, 2] = y * np.sin(theta) + z * np.cos(theta)
        return verts

    return slab.warp_batch(warpBatch)


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
