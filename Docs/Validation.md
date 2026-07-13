# Validation

## FlightReader

### MODE

Status: PASS

Validated against UAV Log Viewer.

The decoded MODE messages and resulting mode segments agree with UAV Log Viewer.

---

## LAND Message

Status: IN PROGRESS

### Observations

- `LAND.stage` is present in the DataFlash logs.
- No `LAND.Ev` field is present in the logs tested (ArduPlane 4.7 beta).
- `LAND.stage` transitions:
  - 0 → 1 approximately 10 m AGL, before the rangefinder becomes valid.
  - 1 → 2 later during final approach.
  - 2 → 3 near the flare.
- `LAND.stage` does not indicate physical touchdown.
- The landing state machine remains active after touchdown.
- `LAND.stage` returns to 0 only after leaving AUTO.
- QGroundControl reports "In landing sequence" until another flight mode is selected.

### Outstanding Questions

- What triggers each `LAND.stage` transition internally?
- Which sensors (baro, rangefinder, airspeed, etc.) are used?


### 2026-07-13

- Verified compatibility with ArduPlane 4.6.3 parameter export.
- Added normalization of `RNGFND1_MAX_CM` to `RNGFND1_MAX`.
