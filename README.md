# THE FINALS Dagger Prop: Recoilless Blade

A parametric, 3D-printable prop of the THE FINALS dagger in its **Recoilless Blade** skin. The proportions were measured from in-game skin showcase images, so the details are close approximations.

![Render](images/render.png)

## Features

- **Blade:** 105 mm long, 18 mm wide and 4 mm thick. Both edges are serrated near the guard. The front section twists half a turn to the tip, and two slots run through the centerline and spiral with the twist.
- **Handle:** a round recoilless-rifle tube, 108 mm long with a 27 mm grip. It has flared front and rear flanges (44 mm across), six recessed windows, two grooves that mark out the red band, and a ribbed venturi-nozzle pommel.
- **Lanyard bail:** two small holes through the rear flange take a bent wire loop, like the one on the in-game skin.
- **Overall length:** about 211 mm. Change `SCALE` in `dagger.py` to resize the whole prop.

## Safety

This is a **prop**. The edges are modelled blunt (`EDGE_THICKNESS = 1.0` mm) and the tip is rounded (`TIP_RADIUS`). Keep it that way. Check your local rules before carrying it to events.

## Files

- `stl/dagger_full.stl` prints in one piece.
- `stl/dagger_blade.stl` is the blade with a 55 x 12 x 4 mm tang.
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
- **Handle:** print it standing on the nozzle end, tilted about 10-15°. Hollow it in the slicer (2.5-3 mm wall) to save resin, and add drain holes inside the tang slot.
- **Blade:** print it tip-up at 15-30°. Put supports on the tang, and use light supports along the spine, keeping them off the twisted faces.
- **Resin:** the twisted tip and the narrow strips beside the slots are the most fragile parts, so use a tough or ABS-like resin for the blade.
- **Tang fit:** test-fit the tang in the slot. If it's too tight or too loose for your resin, change `TANG_CLEARANCE`.

## Notes

See `docs/handoff.md` for the original research notes and the resin printer ventilation plan.
