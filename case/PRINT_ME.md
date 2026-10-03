# Claw'd — Print Instructions

**Print it as ONE piece.** `Clawd_Case_v2.stl` — confirmed working in practice.

| File | Bed footprint | Height | Material |
|---|---|---|---|
| `Clawd_Case_v2.stl` | 170 × 46 mm | 119 mm | 236.5 cm³ ≈ 293 g PLA |

Watertight, zero bad edges, zero degenerate triangles. Sits flat on Z=0 on the
leg bottoms — no rotation needed.

The split halves (`Hull_Lower_v2.stl` / `Hull_Upper_v2.stl`) are still in this
directory but are **not** the recommended route. They were a hedge against the
119 mm height and the internal overhangs; printing whole turned out fine, and
one piece avoids a seam across the face and any alignment fuss.

## Orientation

Already oriented correctly — **do not rotate**. It stands on the leg bottoms
at Z=0, which is also the correct print orientation: the face and eye apertures
end up vertical, so they print cleanly without bridging.

## Suggested settings

| Setting | Value | Why |
|---|---|---|
| Layer height | 0.2 mm | Fine enough for the pixel steps |
| Walls | 3 | Structural, and the eye apertures need clean edges |
| Infill | 15 % gyroid | It's a hollow shell; more is wasted |
| Supports | **Check the board ledge** | Z 44–45.75 is the only real overhang; pixel steps are self-supporting |
| Brim | 5 mm | 119 mm tall on a 46 mm footprint — worth the adhesion |
| Nozzle | 0.4 mm | Standard |

**Colour:** Claw'd is the orange mascot — roughly Pantone 173 / hex `#D97757`.
Any warm orange PLA reads right. The eye apertures stay unpainted; the screen
modules fill them.

## After printing

1. Test-fit the board on its mount ledge (Z 44–45.75, reachable through the
   open back).
2. Two screen modules press into the face apertures (39.5 × 19.5 mm each).
3. Speaker and screens are cable-tethered; only the mic seats on the board.

See `CAD_NOTES.md` for the measured clearances and the known speaker issue.
