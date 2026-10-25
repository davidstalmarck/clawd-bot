# Clawd body — print and build

Three parts. All files are in millimetres and already oriented for printing:
load them into your slicer as they come, with no rotation.

| File | Part | Size (mm) | Notes |
|---|---|---|---|
| `clawd_body.stl` | Body shell | 160 × 120 × 70.5 | Prints open side up |
| `clawd_cover_knob.stl` | Trim plate for the knob | 44.6 × 44.6 × 2 | Round opening, Ø 30 |
| `clawd_cover_button.stl` | Trim plate for the button | 24.6 × 24.6 × 2 | Rounded-square opening, 15 × 15 |

![Clawd body](img/clawd_body_print_orientation.png)

## 1. Print the body

Our reference print:

| | |
|---|---|
| Printer | Bambu Lab H2S |
| Plate | Textured PEI |
| Material | PETG |
| Filament used | 260.7 g |
| Time | about 7 h 35 min |

- **Orientation:** as the file comes, flat on the bed, open side up.
- **Supports: on.** The body has overhangs away from the bed: the rounded upper
  edges and features inside the shell, up to about 65 mm high. Tree supports keep
  them easy to remove. Check the slicer preview before you print.
- **Bed adhesion:** the body sits on the bed with about 100 cm² of flat base, so it
  holds well on textured PEI. With PETG, use your usual PETG release (glue stick
  or the plate's own texture) so it comes off cleanly.

## 2. Print the two covers

- Flat 2 mm plates with no overhangs: no supports needed.
- Any material works. Matching the body's filament looks best.
- Both fit on one plate and print in a few minutes.

## 3. Assemble

1. Remove the supports from the body and clean up the openings.
2. Fit the electronics: an Atech board with its modules plugged into their ports.
3. Place the **knob cover** over the knob module so the knob comes through the
   round opening, and the **button cover** over the button module so the button
   comes through the square opening.
4. Dry-fit everything before you glue anything.

## Firmware

The Atech project for the Claw'd buddy is in [`firmware/`](../firmware/). See the
main [README](../README.md) for how to build and flash it.
