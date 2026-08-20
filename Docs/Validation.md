
> This document records validation work accumulated during v0.1–v0.5.
> Some sections describe the implementation state at the time the validation
> was performed. For the current architecture and roadmap, see
> `Architecture.md` and `ArduPlane_Analyzer_Roadmap.md`.


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

## AIRSPEED_STALL FlightWindow Threshold

**Status: DEFERRED VALIDATION**

The parameter exports used by the current regression logs contain:

```text
AIRSPEED_STALL

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

---

# v0.4 — AUTO-Landing Detection Validation

## Status

**IN PROGRESS**

v0.4 introduces objective detection of ArduPlane AUTO-landing attempts within a parent `FlightWindow`.

A `FlightWindow` may contain:

```text
zero AUTO-landing attempts
one AUTO-landing attempt
multiple AUTO-landing attempts
```

Manual approaches and manual landings are outside the scope of v0.4 AUTO-landing detection.

The purpose of this validation work is to establish the observed telemetry semantics before those semantics are encoded in `LandingWindowDetector`.

---

# Validation Principle

Landing-detection rules must be derived from repeatable evidence across representative logs.

No individual source is currently assumed to be authoritative.

Candidate evidence includes:

```text
LAND.stage
firmware MSG events
MODE transitions
ARM/disarm events
rangefinder
GPS
airspeed
barometer
mission state
other logged landing-state information
```

The validation process must distinguish between:

```text
direct firmware state
validated state correspondence
physical telemetry evidence
heuristic inference
```

Where evidence is incomplete or contradictory, the uncertainty should be recorded rather than converted prematurely into a detector rule.

---

# Primary Evidence Logs

## log_17.bin

**Status: EXISTING VALIDATION LOG**

`log_17.bin` remains the primary regression log from v0.2 and v0.3.

It provides:

- four independently validated `FlightWindow` objects;
- multiple AUTO-landing attempts;
- aborted AUTO-landing attempts;
- go-arounds;
- restarted AUTO-landing sequences;
- different declared glide slopes;
- LAND stage transitions;
- firmware landing MSG events;
- rangefinder engagement;
- disarm evidence.

Flight 2 remains particularly important because multiple AUTO-landing attempts occur within one continuous `FlightWindow`.

Existing observations from this log are documented above.

---

## New Landing Evidence Log

**Status: PENDING ANALYSIS**

A new landing log has been recorded specifically for further landing investigation.

Observed during the flight:

- multiple AUTO-landing attempts;
- multiple go-arounds;
- completed AUTO landings;
- different glide slopes;
- apparently inconsistent flare behaviour.

This log will be used as the second primary evidence source for v0.4.

The matching parameter file must be considered when investigating configuration-dependent behaviour.

No detector semantics are inferred from this log until its telemetry has been extracted and compared with the existing validation evidence.

---

# AUTO-Landing Attempt Validation

For each identified AUTO-landing attempt, record the chronological relationship between:

```text
Mission / AUTO landing entry
Landing approach start
Landing glide-slope declaration
LAND.stage transitions
Flare MSG
Rangefinder engagement
Abort
Restart
Disarm
Landing-completion evidence
```

Where required to interpret these events, correlate:

```text
airspeed
groundspeed
barometric altitude
sink rate
pitch
throttle
rangefinder height
distance from LAND point
```

The purpose is to establish defensible meanings for:

```text
LandingWindow start
LandingWindow abort end
LandingWindow successful end
new attempt following go-around
```

---

# No AUTO-Landing Attempt Case

**Status: VALIDATION REQUIRED**

A representative `FlightWindow` containing no ArduPlane AUTO-landing attempt must be tested.

Expected detector result:

```text
[]
```

Manual flight, a manual approach, or a manual landing must not by itself create a `LandingWindow`.

This case is required to establish false-positive behaviour before v0.4 is considered complete.

---

# Flare Validation

## Status

**IN PROGRESS**

Existing logs already show that the firmware `Flare` message does not occur at one fixed reported height.

Examples from `log_17.bin` include:

```text
Flare 5.2m sink=1.76 speed=11.2 dist=25.9
Flare 6.6m sink=2.21 speed=15.9 dist=60.6
Flare 6.3m sink=2.11 speed=11.0 dist=27.1
Flare 4.5m sink=1.56 speed=12.9 dist=38.9
Flare 4.4m sink=1.50 speed=10.6 dist=47.3
```

The new landing log also appeared during flight to show differing flare behaviour.

This must be investigated rather than treated as an anomaly.

For each representative AUTO-landing attempt, compare:

```text
declared glide slope
configured landing parameters
approach airspeed
approach groundspeed
sink rate
barometric altitude
rangefinder height
LAND.stage transition
Flare MSG
pitch response
throttle response
abort/completion outcome
```

The objective is to establish what the logged flare events represent and what conditions correspond to them.

v0.4 does not attempt to determine whether the flare was good or bad.

Landing-quality analysis belongs to v0.5.

---

# Glide-Slope Validation

## Status

**IN PROGRESS**

Existing validation evidence contains multiple declared glide slopes, including:

```text
3.8 degrees
4.7 degrees
5.1 degrees
```

The new landing log contains additional approaches flown with different glide slopes.

These cases provide comparative evidence for determining whether glide-slope geometry affects observed flare timing, height, sink rate, or other landing-state transitions.

For each attempt record:

```text
declared glide slope
approach-start altitude
flare time
flare reported height
flare sink rate
flare airspeed
LAND.stage transitions
rangefinder engagement
abort/completion outcome
```

Different glide slopes must not themselves alter the semantic definition of an AUTO-landing attempt.

---

# Yaapu Landing-Complete Observation

## Status

**INVESTIGATION REQUIRED**

During a completed AUTO landing in the new evidence flight, the TX16S running the Yaapu telemetry widget produced the audible announcement:

```text
Landing complete
```

No equivalent text was observed in the MAVLink message stream at the time.

This raises the possibility that Yaapu generates the announcement locally from an ArduPilot telemetry state rather than receiving a `STATUSTEXT` containing those words.

The source of this announcement must be established before it is considered landing-completion evidence.

Questions to resolve:

1. Is `Landing complete` received from ArduPilot as text?
2. Is the announcement generated locally by Yaapu?
3. If generated locally, which telemetry state triggers it?
4. Is that underlying state represented in the DataFlash BIN log?
5. What is its timing relative to:
   - flare;
   - LAND.stage transitions;
   - rangefinder engagement;
   - touchdown evidence;
   - throttle;
   - disarm?
6. Does the state occur consistently after successful AUTO landings?
7. Is it absent during aborted AUTO-landing attempts?

The Yaapu announcement itself must not be used by `LandingWindowDetector`.

If the underlying ArduPilot state is available in the BIN log and proves repeatable, that state may become validated landing-completion evidence.

---

# v0.4 Boundary Questions

The following questions must be resolved before real AUTO-landing detection is considered validated.

## AUTO-Landing Start

- What event most reliably marks the beginning of an AUTO-landing attempt?
- What is the relationship between `Mission: 3 Land`, `Landing approach start`, `Landing glide slope`, and `LAND.stage 0 -> 1`?
- Which event provides the correct `LandingWindow.start_us`?

## Abort

- What event should terminate an aborted AUTO-landing attempt?
- How does the explicit firmware abort MSG relate to LAND state?
- Should the window end at abort declaration, state-machine reset, or another event?

## Restart

- What constitutes a new AUTO-landing attempt following a go-around?
- Does `Restarted landing via DO_LAND_START` mark a new attempt or preparation for the subsequent approach?
- How does LAND stage reset relate to the next approach?

## Successful End

- What evidence most reliably identifies completion of a successful AUTO landing?
- Is physical touchdown determinable from the available telemetry?
- Is disarm an appropriate boundary or merely supporting evidence?
- Does a logged landed state exist?
- Does the telemetry state responsible for Yaapu's `Landing complete` announcement exist in the BIN log?

These questions must be answered from evidence before final detector semantics are implemented.

---

# v0.4 Expected Validation Outcomes

Before v0.4 is complete, validation should establish:

- [ ] AUTO-landing attempt-start semantics.
- [ ] Aborted-attempt end semantics.
- [ ] Go-around/restart semantics.
- [ ] Successful AUTO-landing end semantics.
- [ ] Multiple AUTO-landing attempts within one `FlightWindow`.
- [ ] Zero AUTO-landing attempts within a valid `FlightWindow`.
- [ ] No false AUTO-landing detection from manual flight or manual landing.
- [ ] LAND-stage correspondence across representative attempts.
- [ ] Firmware MSG correspondence across representative attempts.
- [ ] Flare-event behaviour across different approaches.
- [ ] Glide-slope comparison across representative approaches.
- [ ] Rangefinder relationship to flare and landing completion.
- [ ] Yaapu `Landing complete` trigger investigated.
- [ ] Usable landing-completion evidence identified or explicitly documented as unavailable.
- [ ] Released ArduPlane 4.7 behaviour checked against the existing pre-release observations.

Until these items are validated, AUTO-landing boundary semantics remain **IN PROGRESS**.

### Supported Firmware

The initial release targets ArduPlane 4.7.x.

Firmware event messages and landing state transitions are
treated as part of the analysis API. Earlier firmware
versions (e.g. 4.6.x) are not regression targets and may
produce incomplete landing analysis.

Support for additional firmware versions may be added in a
future release if there is sufficient demand.

