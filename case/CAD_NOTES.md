# Claw'd Desk Companion — CAD Notes

A pixel-mascot enclosure for the atech 14-port motherboard, with two Screen
modules mounted in the face as eyes.

Outer envelope **170 × 46 × 119 mm**. Pixel grid 17 mm/cell.

## Files

| File | What it is |
|---|---|
| `ClaudeDeskCompanion.FCStd` | FreeCAD source (both v1 and v2 objects) |
| `Clawd_Case_v2.stl` / `.step` | **Current** — use this |
| `Hull_Lower_v2.stl` / `Hull_Upper_v2.stl` | Current print split |
| `Clawd_Case.stl`, `Hull_*.stl` | v1 — superseded, kept because the films were rendered against it |

Object naming follows the house convention from `XWing.FCStd`:
`Board_14port` / `Mod_*` for hardware reference bodies, `<Name>_Solid` fused
sculpture, `<Name>_Case` after cuts, `Hull_Upper` / `Hull_Lower` for the split.

## v1 → v2 changes

Three defects found during render work, all fixed in v2:

1. **Board had no mount.** It floated 8.5 mm above `Hull_Lower` with nothing
   supporting it. Added support pillars, a continuous ledge, and side rails
   that locate the board in X and Y. Gap now **0.00 mm** — verified by probing
   real material, not bounding boxes.
2. **Board pocket was 6.5 mm; the real board is 7.00 mm.** The board would not
   have fitted. Widened to 7.0 mm.
3. **`modzone` clearance cut was on the wrong axis.** It assumed modules drop
   vertically onto the board. They do not — see below. Replaced with swept
   clearance outboard of each port column.

v2 adds 44 faces and removes 8,844 mm³. Outer envelope, interior void
(Z 37.25–116) and both eye apertures are unchanged.

## Mating is LATERAL, not vertical

This is the single most important fact and it is easy to get wrong.

Modules **slide inboard across the board face** into side-entry shrouds along
the long edges. They do **not** descend onto the board.

`presets.yaml` says modules "plug into the top (+Y) face". That describes the
**functional** face — where the LED emits, where the button is pressed, where
the cable enters. It is **not** the direction of travel during assembly.
Reading it as vertical produces geometry that cannot be built.

Authoritative source: `atech-artifacts/docs/MODULE_MATING_GEOMETRY.md`, which
supersedes the mating section of `CONNECTOR_SPEC.md`.

## The board mount prints with the UPPER hull, not the lower

Non-obvious and worth knowing before you print. The print split sits at Z 38.0:

| Part | Z range |
|---|---|
| `Hull_Lower_v2` | 0.0 – 38.0 (legs and base only) |
| `Hull_Upper_v2` | 38.0 – 119.0 (everything else) |

The board-mount ledge added in v2 sits at **Z 44.0 – 45.75**, above the split,
so it belongs to `Hull_Upper_v2`. The lower hull never reaches the board at all.

Two consequences:

- The upper half carries the board and all its support. The lower half is
  legs. Don't expect to seat the board in the lower shell.
- That ledge is what blocks downward clearance under the board. Measured by
  probing material: **39.5 mm above the board, 31.0 mm below**. The cavity is
  *not* symmetric, and below is the worse direction.

An arithmetic estimate that assumed a clear floor gave 53.5 mm below and
concluded the speaker fits. It does not — the ledge was invisible to the
calculation. Probe material; don't compute clearance from wall thicknesses.

## Open issue: the speaker does not fit

Not fixed in v2, because fixing it is a design decision rather than a defect.

- Speaker needs **50.59 mm** of reach from board centre
- Case offers **39.50 mm** above, **31.00 mm** below (measured by probing material)
- **Shortfall: 11.09 mm** above, ~19.6 mm below. Fails both ways.
- Resolution: the speaker is **tethered** — mounted in the head behind the
  board and wired to its 4 ports, consuming ports without needing reach.

Independently confirmed twice. Only 12.5 mm of headroom exists above the board
against the 20.6 mm the speaker's overhang requires.

Options: enlarge the case (breaks the mascot proportions), or leave the
speaker out. Every render so far omits it.

## Eye modules

Two Screen modules (39.5 × 19.5 × 9.6 mm) press into the face apertures at
X = ±34, Z = 94.5, and connect back to the board by ribbon cable rather than
plugging in directly.

The apertures are correct and open — a 35-point grid sample per aperture
confirms 35/35 clear at exactly the screen footprint. (An early analysis
reported them solid; that was a rectangle-merge artifact fusing the
triangulated fan into an apparent block.)

## Caveat on the films

`clawd_assembly.mp4` and the recut depict **v1** geometry — no board mount, old
modzone axis. Every constraint they rely on is identical in v2, and the v2
mount ledge (top at Z 45.75) sits 0.76–1.0 mm under where the films place the
board, so v2 corroborates the staging rather than contradicting it.

They are accurate as visuals. They are **not** build guides: the pocket
thickness and modzone fixes are not visible in them. Print from the v2 STLs.
