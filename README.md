# THE FINALS Dagger Prop: Recoilless Blade

A parametric, 3D-printable prop of the THE FINALS dagger in its **Recoilless Blade** skin. Every dimension was measured off the in-game skin showcase image, at 0.405 mm per image pixel.

![Render](images/render.png)

The comparison below puts the cosmetic image (top) at the same scale as the model:

![Comparison with the cosmetic](images/compare.png)

## Features

- **Blade:** 108 mm long, 13.8 mm wide and 3.5 mm thick. It stays nearly full width for about two-thirds of its length, then tapers to the point.
  - Both edges are serrated from 12 to 50 mm out from the guard.
  - The twist runs along the whole blade. It's a gentle 40° real twist plus spiral lobe lines carved into both faces, which keeps the top-down outline full width like the cosmetic.
  - Two slots run through the centerline.
- **Handle:** a slim recoilless-rifle tube, 116 mm long with a 19.4 mm grip.
  - Concave bells flare out to the front flange (34 mm across) and the rear flange (32 mm).
  - Eight recessed windows sit in alternating rows, and two grooves mark out the red band.
  - A domed cap and a ribbed venturi nozzle form the pommel.
- **Lanyard bail:** two small holes through the rear flange take a bent wire loop, like the one on the in-game skin.
- **Overall length:** about 222 mm. Change `SCALE` in `dagger.py` to resize the whole prop.

## Safety

This is a **prop**. The edges are modelled blunt (`EDGE_THICKNESS = 1.0` mm) and the tip is rounded (`TIP_RADIUS`). Keep it that way. Check your local rules before carrying it to events.

## Files

- `stl/dagger_full.stl` prints in one piece.
- `stl/dagger_blade.stl` is the blade with a 50 x 9 x 3.5 mm tang.
- `stl/dagger_handle.stl` is the handle, with a tang slot (0.15 mm clearance per side). Print the two parts separately to make painting easier, then glue them together.
- `dagger.py` is the parametric model. Edit the ALL_CAPS constants at the top and re-run it.
- `render_preview.py` writes a quick matplotlib preview to `images/preview.png`.

```bash
pip install -r requirements.txt
python3 dagger.py
python3 render_preview.py
```

## Painting (to match the skin)

- **Blade:** gunmetal or dark chrome. Use a metallic silver drybrush on the serrations and slot edges.
- **Handle:** satin black. Paint red on the band between the two grooves and on the edges of both flanges. A dark red ring on each nozzle rib adds depth.
- **Decals:** add THE FINALS triangle logo on the front bell, and diagonal black stripes over the red band, as decals or masked paint.

## Printing (Anycubic Photon M3 Max)

- Every part fits the M3 Max build volume (298 x 164 x 300 mm).
- **Handle:** print it standing on the nozzle end, tilted about 10-15°. The grip is slim, so print it solid (about 37 cm³ of resin), or hollow it with a wall of at least 3 mm.
- **Blade:** print it tip-up at 15-30°. Put supports on the tang, and use light supports along the spine, keeping them off the twisted faces.
- **Resin:** the twisted tip and the narrow strips beside the slots are the most fragile parts, so use a tough or ABS-like resin for the blade.
- **Tang fit:** test-fit the tang in the slot. If it's too tight or too loose for your resin, change `TANG_CLEARANCE`.

## Notes

See `docs/handoff.md` for the original research notes and the resin printer ventilation plan.
