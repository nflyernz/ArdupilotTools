# Validation

This document records observations used to validate ArduPlane Analyzer against known flight logs and external log-viewing tools.

Validation evidence may be used to confirm that the software interprets telemetry correctly.

It must not influence runtime analysis results.

---

# FlightReader

## MODE

**Status: PASS**

Validated against UAV Log Viewer.

The decoded MODE messages and resulting mode segments agree with UAV Log Viewer.

---

# FlightWindow Detection

## log_17.bin

**Status: PASS**

`log_17.bin` contains four independently detected flights.

Expected windows:

| Flight | Start TimeUS | End TimeUS | Duration |
|---|---:|---:|---:|
| 1 | 656,723,277 | 924,883,724 | 268.2 s |
| 2 | 1,095,783,170 | 1,680,743,260 | 585.0 s |
| 3 | 1,966,307,340 | 2,051,367,266 | 85.1 s |
| 4 | 2,573,683,601 | 2,863,678,803 | 290.0 s |

These boundaries were checked against the flight structure visible in UAV Log Viewer.

---

## Flight Start Persistence

The original detector qualified flight start using five consecutive GPS samples above the speed threshold.

This was replaced with a time-based rule requiring groundspeed to remain above the effective threshold continuously for at least 2 seconds.

After this change, `log_17.bin` still produced exactly the same four FlightWindow boundaries.

**Result: PASS**

This confirms that the 2-second persistence rule removes dependence on GPS sample count without changing the validated flight segmentation in this regression log.

---

## Multiple Landing Attempts

Flight 2 contains multiple landing attempts and go-arounds.

Despite these landing sequences, the detector produces one continuous FlightWindow:

```text
1,095,783,170 -> 1,680,743,260
```

The go-arounds do not incorrectly split the flight into separate FlightWindows.

**Result: PASS**

---

# Flight-Scoped Analysis

## Main Analysis CLI

Command:

```text
python Scripts/analyse.py
```

Test log:

```text
Logs/log_17.bin
```

Observed result:

```text
Logs            : 1
Flight Results  : 4
Framework Errors: 0
```

Each detected FlightWindow was processed independently.

**Result: PASS**

---

## SensorHealthWindow

Each FlightWindow produced its own SensorHealthWindow.

Observed windows:

| Flight | Flight Start | Flight End | Health Start | Health End |
|---|---:|---:|---:|---:|
| 1 | 656.723 s | 924.884 s | 658.723 s | 922.884 s |
| 2 | 1095.783 s | 1680.743 s | 1097.783 s | 1678.743 s |
| 3 | 1966.307 s | 2051.367 s | 1968.307 s | 2049.367 s |
| 4 | 2573.684 s | 2863.679 s | 2575.684 s | 2861.679 s |

The current implementation trims 2 seconds from each end of the parent FlightWindow.

**Result: PASS**

---

# LAND Message

## General Behaviour

**Status: IN PROGRESS**

### Observations

- `LAND.stage` is present in the DataFlash logs.
- No `LAND.Ev` field is present in the logs tested with ArduPlane 4.7 beta.
- `LAND.stage` does not directly indicate physical touchdown.
- The landing state machine may remain active after touchdown.
- QGroundControl may report `In landing sequence` until the landing state is cleared.
- LAND behaviour must not yet be treated as a complete landing-attempt detector.

The exact firmware meaning of each stage remains subject to validation.

---

# Flight-Scoped LAND Validation

## log_17.bin

LAND records were filtered independently to each FlightWindow.

### Flight 1

```text
662.302 s   None -> 0
901.423 s   0 -> 1
915.623 s   1 -> 2
915.923 s   2 -> 3
```

LAND records in flight: **241**

---

### Flight 2

```text
1102.102 s   None -> 0
1519.423 s   0 -> 1
1535.023 s   1 -> 2
1535.523 s   2 -> 3
1540.163 s   3 -> 0
1589.223 s   0 -> 1
1600.823 s   1 -> 2
1601.723 s   2 -> 3
1656.524 s   3 -> 0
1656.623 s   0 -> 1
1667.223 s   1 -> 2
1672.223 s   2 -> 3
```

LAND records in flight: **735**

This flight is particularly useful because it contains multiple landing attempts.

The returns:

```text
3 -> 0
```

occur in association with aborted/restarted landing sequences.

---

### Flight 3

```text
1972.687 s   None -> 0
2025.687 s   0 -> 1
2042.988 s   1 -> 2
2043.388 s   2 -> 3
```

LAND records in flight: **263**

---

### Flight 4

```text
2580.483 s   None -> 0
2821.265 s   0 -> 1
2836.164 s   1 -> 2
2840.265 s   2 -> 3
```

LAND records in flight: **431**

---

## LAND Stage Questions

Still to be established across representative firmware versions and logs:

- What exact firmware condition causes stage 0 -> 1?
- What exact firmware condition causes stage 1 -> 2?
- What exact firmware condition causes stage 2 -> 3?
- Which stages are appropriate as landing-window boundaries?
- How consistent are these transitions across ArduPlane 4.6 and 4.7?
- What is the correct relationship between LAND state and physical touchdown?

These questions must be resolved before LAND stages are made authoritative landing-detection rules.

---

# Firmware MSG Events

## Flight-Scoped Extraction

**Status: PASS**

Firmware MSG records were successfully constrained to individual FlightWindows.

All extracted events in the validation run remained within their selected parent flight.

---

## Flight 1 Landing Sequence

Relevant observed messages:

```text
873.203  Mission: 1 LandStart
873.203  Mission: 2 LoitAltitude
901.323  Loiter to alt complete
901.323  Mission: 3 Land
901.323  Landing approach start at 19.5m
901.423  Landing glide slope 4.7 degrees
915.923  Flare 5.9m sink=1.97 speed=10.9 dist=55.9
917.384  Rangefinder engaged at 4.96m
```

LAND stage 1 begins at:

```text
901.423
```

This is approximately 0.1 seconds after:

```text
Mission: 3 Land
Landing approach start
```

and coincides with the `Landing glide slope` message.

---

## Flight 2 Landing Sequences

Flight 2 contains multiple landing attempts.

### Attempt 1

```text
1470.723  Mission: 1 LandStart
1470.723  Mission: 2 LoitAltitude
1519.323  Loiter to alt complete
1519.323  Mission: 3 Land
1519.323  Landing approach start at 19.1m
1519.423  Landing glide slope 4.7 degrees
1535.523  Flare 5.2m sink=1.76 speed=11.2 dist=25.9
1536.723  Landing aborted via throttle
1536.723  Landing aborted, climbing to 30m
1540.163  Restarted landing via DO_LAND_START: 1
```

Associated LAND transitions include:

```text
1519.423   0 -> 1
1535.023   1 -> 2
1535.523   2 -> 3
1540.163   3 -> 0
```

---

### Attempt 2

```text
1552.063  Mission: 1 LandStart
1552.063  Mission: 2 LoitAltitude
1589.123  Loiter to alt complete
1589.123  Mission: 3 Land
1589.123  Landing approach start at 18.9m
1589.223  Landing glide slope 4.7 degrees
1601.723  Flare 6.6m sink=2.21 speed=15.9 dist=60.6
1605.563  Rangefinder engaged at 5.66m
1607.924  Landing aborted via throttle
1607.925  Landing aborted, climbing to 30m
1615.023  Restarted landing via DO_LAND_START: 1
```

Associated LAND transitions include:

```text
1589.223   0 -> 1
1600.823   1 -> 2
1601.723   2 -> 3
```

---

### Attempt 3

```text
1615.023  Mission: 1 LandStart
1615.023  Mission: 2 LoitAltitude
1625.703  Mission: 2 LoitAltitude
1656.524  Loiter to alt complete
1656.524  Mission: 3 Land
1656.524  Landing approach start at 20.9m
1656.623  Landing glide slope 5.1 degrees
1672.223  Flare 6.3m sink=2.11 speed=11.0 dist=27.1
1675.043  Rangefinder engaged at 5.85m
```

Associated LAND transitions include:

```text
1656.524   3 -> 0
1656.623   0 -> 1
1667.223   1 -> 2
1672.223   2 -> 3
```

Flight 2 is therefore the primary current regression case for multiple landing attempts, aborts, and landing restarts.

---

## Flight 3 Landing Sequence

```text
1993.307  Mission: 1 LandStart
1993.307  Mission: 2 LoitAltitude
2025.587  Loiter to alt complete
2025.587  Mission: 3 Land
2025.587  Landing approach start at 19.8m
2025.688  Landing glide slope 3.8 degrees
2043.388  Flare 4.5m sink=1.56 speed=12.9 dist=38.9
2043.628  Rangefinder engaged at 5.47m
```

Associated LAND stage 1 begins at approximately:

```text
2025.687
```

---

## Flight 4 Landing Sequence

```text
2764.264  Mission: 1 LandStart
2764.264  Mission: 2 LoitAltitude
2821.164  Loiter to alt complete
2821.164  Mission: 3 Land
2821.164  Landing approach start at 19.9m
2821.265  Landing glide slope 3.8 degrees
2840.264  Flare 4.4m sink=1.50 speed=10.6 dist=47.3
2840.285  Rangefinder engaged at 5.47m
2848.866  Throttle disarmed
2848.883  EKF3 IMU0 stopped aiding
2848.883  AHRS: DCM active
2849.139  AHRS: EKF3 active
2849.140  Distance from LAND point=22.92m
2856.041  PreArm: In landing sequence
```

This sequence confirms that the firmware landing state can remain active after throttle disarm.

Therefore disarm and LAND state must be treated as distinct evidence when designing landing-window termination rules.

---

# LAND / MSG Correspondence

The current validation log shows a repeatable relationship:

```text
Mission: 3 Land
        │
Landing approach start
        │
        ▼
Landing glide slope
        │
        ▼
LAND stage 0 -> 1
        │
        ▼
LAND stage 1 -> 2
        │
        ▼
Flare
        │
        ▼
LAND stage 2 -> 3
```

The timestamps are closely aligned, but this is currently an observation rather than a formal detector rule.

Additional logs and firmware versions must be checked before finalising landing detection.

---

# Landing Timeline

## Flight 1

**Status: PASS**

Observed flight-scoped timeline:

```text
Flight Window : 656.723 -> 924.884 s

656.724  RFND_FIRST_NONZERO  1.97 m
656.724  RFND_CONTINUOUS     50 samples
662.302  LAND_STAGE          0
676.083  MODE                5
873.203  MODE                10
901.423  LAND_STAGE          1
915.623  LAND_STAGE          2
915.923  LAND_STAGE          3
```

Timeline sources remain constrained to the selected FlightWindow.

---

# Parameter Compatibility

## ArduPlane 4.6.3

**Status: PASS**

Validated on 2026-07-13.

ArduPlane 4.6.3 exports:

```text
RNGFND1_MAX_CM
```

in centimetres.

`ParameterReader` normalises this to:

```text
RNGFND1_MAX
```

in metres.

Processors and detectors therefore use the firmware-independent parameter name:

```python
flight_log.param("RNGFND1_MAX")
```

---

## ArduPlane 4.7

**Status: RELEASE VALIDATION PENDING**

ArduPlane 4.7 has now been released.

Existing validation logs were recorded using pre-release 4.7 firmware and demonstrate the LAND and MSG behaviour documented above.

The aircraft will be updated to the released ArduPlane 4.7 firmware. After the update, representative logs should be used to verify:

- parameter loading and normalisation
- FlightWindow detection
- LAND message structure and stage transitions
- firmware MSG landing events
- abort and restart behaviour
- ARM/disarm events
- landing timeline construction

Until this validation is complete, behaviour observed in the existing pre-release 4.7 logs should not automatically be assumed identical to the released firmware.

---

# Current Validation Conclusions

The following architectural behaviour is currently validated:

- `FlightReader` correctly decodes MODE data.
- Multiple flights can be detected within one BIN log.
- Flight detection is stable using the 2-second persistence rule on `log_17.bin`.
- Go-arounds remain inside the correct continuous FlightWindow.
- Sensor-health windows are derived independently for each flight.
- LAND telemetry can be scoped to individual FlightWindows.
- MSG events can be scoped to individual FlightWindows.
- Landing timeline sources can be constrained to a selected flight.
- One analysis result can be produced independently for each detected flight.
- ArduPlane 4.6.3 rangefinder parameter naming can be normalised to the common parameter interface.

The following behaviour is not yet considered fully validated:

- exact semantic meaning of every `LAND.stage`
- authoritative landing-attempt start boundary
- authoritative landing-attempt end boundary
- touchdown detection
- cross-version LAND behaviour
- cross-version MSG landing-event consistency

These remain validation targets for the landing-detection milestone.