# ArduPlane Analyzer Roadmap

## Vision

Build a modular engineering tool for objectively analysing ArduPilot fixed-wing flight logs.

The objective is to explain observed aircraft behaviour from logged telemetry, beginning with landing analysis, while providing a reusable framework for future analyses such as TECS, cruise performance, RTL, power systems, and autotune.

---

# Design Principles

- `FlightLog` is the sole owner of decoded telemetry, parameters, events, and mode segments.
- `FlightWindow` represents one continuous flight within a log.
- Every analysis operates within a selected `FlightWindow`.
- `FlightWindow` remains a lightweight time-bound object and does not own telemetry.
- Processors and detectors receive the `FlightLog` and selected `FlightWindow` when flight scope is required.
- Analysis-specific windows such as `SensorHealthWindow` and `LandingWindow` are derived within a parent `FlightWindow`.
- The analysis orchestrator is responsible for selecting flights and coordinating processors, detectors, and results.
- Firmware-specific parameter names and units are normalised by `ParameterReader`.
- Detectors and analysers operate only on the normalised parameter interface.
- Internal calculations use `TimeUS`.
- Human-readable output uses `MM:SS.mmm`.

---

# Objective Analysis Principle

The toolkit derives its conclusions solely from telemetry contained within the flight log.

```text
Flight Log
    │
    ▼
Processors
    │
    ▼
Analysers
    │
    ▼
Report
```

---

# Current Architecture

```text
BIN log
    │
    ▼
FlightReader
    │
    ▼
FlightLog
    ├── Messages
    ├── Parameters
    ├── Events
    ├── Mode Segments
    ├── Metadata
    │
    └── FlightWindow(s)
             │
             ├── SensorHealthWindow
             ├── LandingWindow(s)
             ├── CruiseWindow(s)
             ├── AutotuneWindow(s)
             ├── RTLWindow(s)
             └── ...
```

---

# v0.1 — Core Framework ✅

## Log Reader

- [x] Read BIN logs
- [x] Decode configured MAVLink/DataFlash messages
- [x] Load matching parameter files
- [x] Build `FlightLog`
- [x] Store telemetry as pandas DataFrames

## Parameter Framework

- [x] Load configured parameters
- [x] Support exact parameter names
- [x] Support wildcard parameter groups
- [x] Normalise firmware-specific parameter names
- [x] Normalise firmware-specific parameter units
- [x] Support ArduPlane 4.6 `RNGFND1_MAX_CM`
- [x] Present firmware-independent parameter interface to detectors

## Segmentation

- [x] Decode MODE records
- [x] Generate mode segments
- [x] Store log-wide mode timeline

## Sensor Framework

- [x] Airspeed processor
- [x] GPS processor
- [x] Barometer processor
- [x] Sensor health window
- [x] Rangefinder event processing

## Event Framework

- [x] Load firmware `MSG` records
- [x] Represent firmware messages as timeline events
- [x] Load `LAND` telemetry
- [x] Load `ARM` telemetry
- [x] Build chronological landing timeline

---

# v0.2 — FlightWindow Integration ✅

## Objective

Complete the transition from whole-log analysis to independently scoped flight analysis.

A single BIN log may contain multiple flights. Each flight must be analysed independently without moving telemetry ownership out of `FlightLog`.

---

## Flight Detection

- [x] Introduce `FlightWindow`
- [x] Add `FlightLog.flights`
- [x] Implement `FlightWindowDetector`
- [x] Populate flight windows during log loading
- [x] GPS groundspeed based flight detection
- [x] Default flight speed threshold of 5 m/s
- [x] Allow flight speed threshold to be configured
- [x] Support `AIRSPEED_STALL` in FlightWindow threshold calculation when available
- [ ] Enable `AIRSPEED_STALL` parameter loading only after explicit FlightWindow regression validation- [x] Require above-threshold state to persist for 2 seconds
- [x] Require extended ground period before separating flights
- [x] Support multiple flights within one log
- [x] Keep go-arounds within the same continuous `FlightWindow`

---

## Sensor Health Scoping

- [x] Refactor `SensorHealthWindowDetector` for flight-scoped operation
- [x] Input includes `FlightLog` and selected `FlightWindow`
- [x] Validate that the `FlightWindow` belongs to the supplied `FlightLog`
- [x] Derive sensor-health bounds within the parent flight
- [x] Restrict airspeed health analysis to the selected flight's health window

---

## Analysis Orchestration

- [x] Iterate `FlightLog.flights`
- [x] Execute analysis independently for each `FlightWindow`
- [x] Produce one `AnalysisResult` per `FlightWindow`
- [x] Preserve `FlightLog` as the telemetry owner
- [x] Distinguish analysis failures from framework failures
- [x] Validate multi-flight execution through the main CLI

---

## Analysis Model

- [x] `AnalysisResult` explicitly references its parent `FlightWindow`
- [x] Consolidate duplicate `LandingWindow` models
- [x] Remove legacy `landwindow.py`
- [x] Validate parent/child window relationships where required

---

## Flight-Scoped Processing

- [x] Scope LAND processing to `FlightWindow`
- [x] Scope MSG event extraction to `FlightWindow`
- [x] Scope landing timeline event sources to `FlightWindow`
- [x] Scope mode-segment selection to `FlightWindow`
- [x] Keep log-wide telemetry and segment ownership in `FlightLog`

---

## Landing Framework Preparation

- [x] Refactor `LandingWindowDetector`
- [x] Accept `FlightLog + FlightWindow`
- [x] Validate parent `FlightWindow`
- [x] Remove fixed absolute development interval
- [x] Return a bounded development `LandingWindow`
- [x] Establish support for multiple `LandingWindow` results
- [x] Validate LAND and MSG telemetry within individual flights

Real landing-attempt detection is intentionally deferred to v0.4.

---

## Development Harnesses

- [x] Update reader harness for FlightWindow API
- [x] Update LAND-stage harness for flight scoping
- [x] Update MSG harness for flight scoping
- [x] Update rangefinder harness for canonical `LandingWindow`
- [x] Update timeline harness for parent `FlightWindow`
- [x] Remove remaining runtime dependencies on legacy `LandingWindows`
- [x] Validate `log_17.bin` as a multi-flight regression case

---

## v0.2 Validation

Validated against `log_17.bin`:

- [x] Four independent flights detected
- [x] Flight boundaries agree with previously validated boundaries
- [x] Changing flight-start qualification from five samples to two seconds did not alter the four detected flight boundaries
- [x] Multiple go-arounds remain within one continuous flight
- [x] LAND records are correctly scoped to individual flights
- [x] MSG records are correctly scoped to individual flights
- [x] Landing timeline events remain within the selected flight
- [x] Main landing-analysis CLI produces four `AnalysisResult` objects
- [x] Main landing-analysis CLI completes with zero framework errors

---

# v0.3 — Analysis Framework ✅

## Objective

Standardise processors, detectors, analyses, and result models around consistent flight-scoped contracts.

The purpose of this milestone is API consistency rather than new landing-detection behaviour.

---

## Analysis API

- [x] Define standard processor interface
- [x] Define standard detector interface
- [x] Define standard analysis interface
- [x] Standardise result models
- [x] Define common parent/child window validation

The established per-flight contract is:

```text
FlightLog
    +
FlightWindow
    ↓
Processor / Detector / Analysis
    ↓
Scoped Result
```

`LandingAnalysis` now exposes the reusable per-flight entry point:

```python
LandingAnalysis.analyse(
    flight_log,
    flight_window,
) -> AnalysisResult
```

The interactive `LandingAnalysis.run()` remains responsible for orchestration and presentation.

---

## Sensor Processors

- [x] Refactor `AirspeedProcessor`
- [x] Refactor `GPSProcessor`
- [x] Refactor `BarometerProcessor`
- [x] Refactor rangefinder processing

Established pattern:

```text
Processor
    │
    ├── FlightLog
    ├── FlightWindow
    └── optional analysis-specific sub-window
```

Processors must never read telemetry outside the selected parent flight.

The airspeed native-rate result was also corrected so that the result contains the calculated numeric sample rate rather than the function object.

Existing airspeed validation behaviour was preserved.

---

## Event Processors

- [x] Refactor `EventExtractor`
- [x] Refactor `ArmCycleFinder`
- [x] Refactor `LandingTimeline`
- [x] Standardise event filtering helpers
- [x] Standardise event ownership and storage

`EventExtractor` operates within the selected `FlightWindow`.

`ArmCycleFinder` is strictly FlightWindow-scoped and does not use pre-window ARM state to manufacture partial cycles.

`LandingTimeline` explicitly operates within its parent `FlightWindow` and child `LandingWindow`.

Rangefinder event processing uses the sensor configuration from `Config/sensors.yaml`.

---

## Shared Utilities

- [x] Consolidate human-readable time formatting
- [x] Implement shared `core.time.format_time_us()`
- [x] Remove duplicated time-formatting code
- [x] Standardise window containment helpers
- [x] Standardise segment filtering helpers
- [x] Standardise telemetry filtering helpers

Shared scope utilities provide common handling for:

- FlightWindow validation
- child-window containment
- telemetry filtering
- segment filtering

Internal calculations continue to use `TimeUS`.

---

## Common Conventions

- [x] `FlightLog` remains telemetry owner
- [x] `FlightWindow` defines parent analysis scope
- [x] Child windows are bounded by `FlightWindow`
- [x] Processors explicitly identify their parent flight
- [x] Health and analysis remain separate responsibilities
- [x] Validation responsibilities are consistent across processors
- [x] `AnalysisResult` does not claim telemetry ownership

The final telemetry ownership model is:

```text
FlightLog
    └── owns telemetry

AnalysisResult
    ├── references FlightWindow
    ├── references SensorHealthWindow
    ├── contains sensor-health results
    └── references LandingWindow(s)
```

---

## Analysis Result Model

- [x] `AnalysisResult` identifies its parent `FlightWindow`
- [x] `AnalysisResult` exposes the derived `SensorHealthWindow`
- [x] `AnalysisResult` exposes derived `LandingWindow` results
- [x] `AnalysisResult` carries analysis outputs without owning source telemetry
- [x] Remove the remaining telemetry reference from `AnalysisResult`

The result model therefore preserves the ownership boundary:

```text
FlightLog
    │
    └── source telemetry

AnalysisResult
    │
    ├── analysis scopes
    └── analytical results
```

---

## Rangefinder Configuration

- [x] Use `Config/sensors.yaml` for rangefinder event processing
- [x] Add explicit `rangefinder.events` configuration
- [x] Preserve existing rangefinder event behaviour
- [x] Validate rangefinder event output after configuration refactor

The configured rangefinder event settings are:

```yaml
rangefinder:

  events:

    zero_threshold: 0.05

    continuous_seconds: 1.0
```

The validated output remains:

```text
RFND_FIRST_NONZERO  1.97 m
RFND_CONTINUOUS     50 samples
```

---

## Development Harnesses

- [x] Migrate development harnesses to the public FlightWindow architecture
- [x] Remove obsolete processor API usage
- [x] Remove duplicated telemetry filtering where shared helpers apply
- [x] Remove duplicated segment filtering where shared helpers apply
- [x] Use shared time formatting
- [x] Add direct `LandingAnalysis.analyse()` harness
- [x] Validate sensor processors independently
- [x] Validate event processors independently
- [x] Validate rangefinder processing independently
- [x] Validate landing timeline independently

---

## v0.3 Validation

Validated against `log_17.bin`:

- [x] Python source tree compiles successfully
- [x] Exactly four `FlightWindow` objects are detected
- [x] Validated FlightWindow boundaries remain unchanged
- [x] Flight 2 remains one continuous flight through multiple landing attempts and go-arounds
- [x] LAND-stage telemetry remains correctly flight-scoped
- [x] MSG events remain correctly flight-scoped
- [x] ARM-cycle processing remains correctly flight-scoped
- [x] Rangefinder events remain correctly scoped
- [x] Landing timeline remains correctly scoped
- [x] Airspeed behaviour remains unchanged
- [x] GPS processor regression harness passes
- [x] Barometer processor regression harness passes
- [x] Direct `LandingAnalysis.analyse()` produces one result per FlightWindow
- [x] Each direct analysis result contains the expected `SensorHealthWindow`
- [x] Each direct analysis result contains one bounded development `LandingWindow`
- [x] Main landing-analysis CLI produces four flight results
- [x] Main landing-analysis CLI reports zero framework errors
- [x] Final source search confirms `AnalysisResult` no longer stores telemetry

Validated FlightWindow boundaries:

| Flight | Start TimeUS | End TimeUS |
|---|---:|---:|
| 1 | 656,723,277 | 924,883,724 |
| 2 | 1,095,783,170 | 1,680,743,260 |
| 3 | 1,966,307,340 | 2,051,367,266 |
| 4 | 2,573,683,601 | 2,863,678,803 |

Validated production result:

```text
Logs            : 1
Flight Results  : 4
Framework Errors: 0
```

---

# v0.4 — Landing Detection

## Objective

Detect real AUTO landing attempts objectively from logged telemetry.

A continuous `FlightWindow` may contain zero, one, or multiple landing attempts.

Go-arounds and aborted approaches must produce separate landing attempts without splitting the parent flight.

---

### Implementation Notes

During implementation it became clear that `EventExtractor`
currently extracts only `MSG` events.

Before `LandingAttemptExtractor` is implemented,
`EventExtractor` will become the authoritative source of
time-ordered timeline events.

It will publish a unified event stream including:

- MSG
- LAND.stage
- MODE
- Rangefinder events

Subsequent components (`LandingTimeline`,
`LandingAttemptExtractor`, and future landing analysis)
will consume this common event stream rather than
duplicating event extraction logic.

This preserves a single authoritative event model
throughout the framework.

## Landing Event Validation

Before finalising detection rules:

- [ ] Catalogue LAND sequences across available logs
- [ ] Catalogue firmware MSG landing sequences
- [ ] Compare ArduPlane 4.6 and 4.7 behaviour
- [ ] Validate aborted approaches
- [ ] Validate restarted landings
- [ ] Validate successful landings
- [ ] Record observations in `Docs/Validation.md`

Detector rules must be supported by multiple representative logs before being treated as authoritative.

---

## Landing Detection

- [ ] Detect landing approach start
- [ ] Detect flare
- [ ] Detect aborted landing
- [ ] Detect restarted landing
- [ ] Detect touchdown evidence
- [ ] Detect rollout where telemetry supports it
- [ ] Detect multiple landing attempts within one flight
- [ ] Support go-arounds
- [ ] Return zero or more `LandingWindow` objects per `FlightWindow`
- [ ] Guarantee every `LandingWindow` lies within its parent `FlightWindow`

---

## Detection Sources

Potential evidence includes:

- [ ] `LAND.stage`
- [ ] Firmware `MSG` events
- [ ] MODE transitions
- [ ] ARM/disarm events
- [ ] Rangefinder
- [ ] GPS
- [ ] Airspeed
- [ ] Barometer

No source should be assumed authoritative until validated against representative logs.

---

## Known Validation Evidence

Current logs show useful correspondence between firmware events and LAND stages.

Examples observed include:

```text
Mission: 3 Land
Landing approach start
Landing glide slope
Flare
Landing aborted via throttle
Restarted landing via DO_LAND_START
Throttle disarmed
```

Flight 2 of `log_17.bin` contains multiple landing attempts and is the primary current regression case for aborted/restarted landing detection.

These observations are validation evidence only. Final detector rules remain part of v0.4.

---

### Future Enhancement: Per-Flight Landing Parameters

The current framework associates a companion `.params` file with each log and assumes those values apply to all flights contained within that log.

This is sufficient for the initial landing analysis framework because parameter changes are typically made between flying sessions.

However, development and tuning flights may deliberately change landing parameters between flights within a single log (for example `RNGFND1_MAX`, `LAND_FLARE_ALT`, or `LAND_PF_ALT`). In these cases the companion `.params` file no longer accurately represents every flight.

A future enhancement should reconstruct the active parameter set for each `FlightWindow` using in-log `PARM` messages.

Until this is implemented:

- The companion `.params` file is treated as a log-level parameter snapshot.
- Reports should clearly indicate the parameter source.
- Landing analysis should not assume parameter values remained constant throughout the log.
- Comparative tuning flights are best recorded as separate logs whenever practical.

This enhancement is deferred until parameter-dependent landing analysis requires per-flight parameter reconstruction.

# v0.5 — Landing Analysis

## Objective

Measure what occurred during each detected landing attempt.

Analysis remains descriptive and evidence-based. It does not recommend parameter changes.

---

## Geometry

- [ ] Approach geometry
- [ ] Glide slope
- [ ] Height profile
- [ ] Distance-to-landing-point profile
- [ ] Touchdown location where measurable

---

## Energy

- [ ] Airspeed profile
- [ ] Airspeed tracking
- [ ] Groundspeed profile
- [ ] Sink rate
- [ ] Throttle behaviour
- [ ] Energy-management observations

---

## Aircraft Response

- [ ] Pitch
- [ ] Roll
- [ ] Attitude tracking
- [ ] Control response where objectively measurable

---

## Flare

- [ ] Flare start
- [ ] Flare height
- [ ] Flare airspeed
- [ ] Flare sink rate
- [ ] Flare duration
- [ ] Rangefinder evidence

---

## Touchdown

- [ ] Detect touchdown where telemetry permits
- [ ] Touchdown speed
- [ ] Touchdown sink rate
- [ ] Touchdown location
- [ ] Rollout measurements

---

## Sensor Validation

- [ ] Airspeed quality
- [ ] GPS quality
- [ ] Barometer quality
- [ ] Rangefinder quality
- [ ] Associate measurement confidence with source quality

---

## Metrics

Each metric must contain:

- measured value
- units
- source/evidence
- applicable time/window
- confidence or validity where appropriate

Metrics must not contain tuning recommendations.

Public first release
+ user logs / feedback

---

# v0.6 — Reporting

## Objective

Present analysis results clearly while preserving the distinction between measurement, evidence, and interpretation.

---

## Report Structure

- [ ] Summary
- [ ] Measurements
- [ ] Evidence
- [ ] Observations
- [ ] Timeline
- [ ] Plots
- [ ] Appendix

---

## Console

- [ ] Landing summary
- [ ] Flight identification
- [ ] Landing-attempt identification
- [ ] Sensor-health summary
- [ ] Timeline
- [ ] Metrics

---

## Structured Output

- [ ] JSON export
- [ ] Stable result schema
- [ ] Machine-readable evidence references

---

## Rich Reports

- [ ] HTML report
- [ ] PDF report

---

## Plotting

Every plot must answer a specific engineering question.

Potential landing plots include:

- [ ] approach geometry
- [ ] airspeed
- [ ] sink rate
- [ ] pitch
- [ ] throttle
- [ ] rangefinder
- [ ] flare detail

---

# v0.7 — Regression Framework

## Objective

Make analysis changes objectively testable against representative logs.

---

## Automated Coverage

- [ ] Zero-flight log
- [ ] Single-flight log
- [ ] Multiple-flight log
- [ ] Flight with no AUTO landing
- [ ] Successful landing
- [ ] Aborted landing
- [ ] Multiple landing attempts
- [ ] Go-around
- [ ] Missing sensor data
- [ ] ArduPlane 4.6 parameters
- [ ] ArduPlane 4.7 parameters
- [ ] Window containment
- [ ] Deterministic analysis results
- [ ] Deterministic report output

---

## Validation Records

- [ ] Maintain representative flight-log catalogue
- [ ] Record expected flight boundaries
- [ ] Record expected landing-event sequences
- [ ] Record known firmware differences
- [ ] Record expected detector outputs

---

# Future Analyses

The architecture should support additional analyses without changing the core flight framework.

Potential modules include:

- TECS
- Cruise performance
- RTL
- Autotune
- Airspeed calibration
- Launch
- Power system
- Battery performance
- Wind estimation
- Navigation accuracy
- Mission analysis
- Sensor diagnostics

All future analyses should follow the same general execution pattern:

```text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
Analysis-specific Window
    │
    ▼
Processors / Analyser
    │
    ▼
Result
    │
    ▼
Report
```

---

# Architecture Status

- [x] `FlightLog` owns decoded telemetry
- [x] `FlightLog` owns parameters
- [x] `FlightLog` owns mode segments
- [x] `FlightWindow` defines individual flight scope
- [x] Multiple flights per log are supported
- [x] Analysis orchestrator executes independently per `FlightWindow`
- [x] `AnalysisResult` identifies its parent `FlightWindow`
- [x] `AnalysisResult` does not own telemetry
- [x] LAND processing is flight-scoped
- [x] MSG extraction is flight-scoped
- [x] ARM-cycle processing is flight-scoped
- [x] Rangefinder processing is flight/landing-scoped
- [x] Landing timeline sources are flight/landing-scoped
- [x] Development harnesses use the current FlightWindow architecture
- [x] Processor APIs are standardised around explicit parent scope
- [x] Detector APIs are standardised according to their required scope
- [x] Reusable per-flight landing-analysis API is established
- [x] Shared telemetry filtering is established
- [x] Shared segment filtering is established
- [x] Shared window containment validation is established
- [x] Shared human-readable time formatting is established
- [ ] Real landing attempts are detected
- [ ] Landing metrics are implemented
- [ ] Landing reports are implemented

---

# Current Development Target

## v0.4 — Landing Detection

With FlightWindow integration and analysis-framework consolidation complete, the next development task is to detect real AUTO landing attempts within each continuous flight.

The established architecture is:

```text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
Landing Detection
    │
    ├── LandingWindow
    ├── LandingWindow
    └── ...
```

A single `FlightWindow` may contain:

```text
zero landing attempts
one landing attempt
multiple landing attempts
```

Go-arounds and aborted approaches must remain within the same parent `FlightWindow` while producing separate landing attempts where supported by validated telemetry evidence.

The first v0.4 task is **landing-event validation**, not implementation of assumed detector semantics.

LAND stages, firmware MSG events, MODE transitions, ARM/disarm events, rangefinder, GPS, airspeed, and barometer are candidate evidence sources.

No source is authoritative until its behaviour has been validated against representative logs.

Flight 2 of `log_17.bin`, containing multiple aborted/restarted landing sequences, remains the primary current regression case.

The validated evidence will define the rules used by the real `LandingWindowDetector`.

## ArduPilot Landing Logic Source Validation

Before adding further interpretation of `LAND.stage`, `LAND.fh`, pre-flare, or flare
events, inspect the actual ArduPilot landing implementation used by the 4.7 series.

The four 4.7 logs show behaviour that should not be interpreted purely from observed
log values. In particular, `LAND.fh` is documented by ArduPilot as height used for
flare timing, rather than simply height above ground, and `LAND.stage` represents
internal landing-controller state.

### Objective

Use the ArduPilot source code to establish the actual meaning and transitions of:

- `LAND.stage`
- `LAND.fh`
- `LAND.slope`
- `LAND.slopeInit`
- pre-flare
- final flare
- rangefinder altitude correction
- `LAND_PF_ALT`
- `LAND_PF_SEC`
- `LAND_PF_ARSPD`
- `LAND_FLARE_ALT`
- `LAND_FLARE_SEC`

### Version boundary

Determine whether the relevant precision-autoland implementation changed at the
4.6.3 → 4.7 boundary.

The 4.7 beta release notes do not show a major precision-autoland implementation
change during the beta series. This suggests the relevant work may have entered
the 4.7 development cycle earlier, but this must be confirmed from the source rather
than inferred from release notes.

### Required source inspection

Inspect the ArduPlane 4.7 implementation, particularly:

- `AP_Landing_Slope.cpp`
- `AP_Landing.cpp`
- associated landing headers
- calculation of the logged flare-height value
- assignments to the landing stage
- pre-flare transition logic
- flare transition logic
- rangefinder correction used by the landing controller

Compare against 4.6.3 only where necessary to establish the version boundary.

### Evidence status

**Observed**
- Four 4.7 logs contain `LAND.stage` and `LAND.fh`.
- Stage transitions and `fh` values are not always intuitive from the logs alone.
- Pre-flare and flare are distinct controller states.
- Rangefinder use occurs independently of the landing-window definition.

**Validated**
- `LAND.fh` is logged by ArduPilot as height used for flare timing.
- Precision autoland includes explicit pre-flare parameters.

**To validate**
- Exact meaning of each `LAND.stage` value.
- Exact calculation and meaning of `LAND.fh`.
- Conditions causing stage 1 → stage 2 → stage 3.
- Relationship between pre-flare parameters and `LAND.stage`.
- Relationship between rangefinder correction and `LAND.fh`.
- Whether any relevant implementation changed between 4.6.3 and 4.7.

### Outcome

Use the source-derived behaviour to determine what the analyzer should call and
extract in a later landing-analysis milestone. Do not add inferred landing-state
semantics to the analyzer until this validation is complete.


## ArduPilot Landing Logic — Source Validation

**Status: Source inspected — semantics confirmed**

Before adding further interpretation of `LAND.stage`, `LAND.fh`, pre-flare, or
flare events, the ArduPilot landing implementation was inspected directly.

The source confirms that these values should not be reverse-engineered from flight
logs.

### LAND.stage

The landing controller defines four progress states:

| Stage | ArduPilot meaning |
|---:|---|
| 0 | NORMAL |
| 1 | APPROACH |
| 2 | PREFLARE |
| 3 | FINAL |

The logger records `stage` as progress through the landing sequence.

The transitions are implemented explicitly in the landing controller.

### LAND.fh

`LAND.fh` is logged as:

> Height for flare timing

It is the `height` value supplied to the landing controller for its flare/pre-flare
decisions. It is **not simply rangefinder altitude** and should not be interpreted
as generic height above ground.

The height is derived from the landing-height calculation and is subsequently
terrain-corrected before being supplied to the landing controller.

The analyzer should therefore retain the raw `fh` value and describe it as
**flare-timing height**, rather than renaming or interpreting it as AGL.

### Pre-flare

The transition from APPROACH to PREFLARE is explicitly controlled by:

- `LAND_PF_ARSPD`
- `LAND_PF_ALT`
- `LAND_PF_SEC`

`LAND_PF_ARSPD > 0` enables the pre-flare stage.

Pre-flare occurs when either:

- height reaches `LAND_PF_ALT`, or
- height reaches the equivalent of `sink_rate × LAND_PF_SEC`.

On entering PREFLARE, the landing controller targets `LAND_PF_ARSPD`.

For the current aircraft:

    LAND_PF_ALT   = 4 m
    LAND_PF_SEC   = 7 s
    LAND_PF_ARSPD = 9 m/s

Therefore pre-flare is not simply "4 m above ground"; it can also be triggered by
the predicted time represented by the current sink rate.

### Final flare

The transition to FINAL is controlled primarily by:

- `LAND_FLARE_ALT`
- `LAND_FLARE_SEC`

The altitude condition is:

    height <= LAND_FLARE_ALT

The time-based condition is based on:

    height <= sink_rate × LAND_FLARE_SEC

The time-based flare condition also requires sufficient progress along the landing
path, preventing an excessively large flare setting from causing an early flare
while still establishing the approach.

There are additional final-stage conditions associated with passing the landing
point and rangefinder availability.

### Rangefinder

Rangefinder data has two distinct effects relevant to landing analysis:

1. It can affect the height used for landing flare/pre-flare timing.
2. It can affect landing-slope correction.

It is therefore an **independent sensor/event source**, not a prerequisite for
defining the landing window.

This remains important because rangefinder use is also relevant during automatic
takeoff.

### Version investigation

The relevant landing logic was already present in the 4.6.3 timeframe.

The 4.6.3 release notes contain landing/rangefinder fixes, including fixes for:

- landing flare when using a rangefinder
- landing slope when a rangefinder exists but is not in use

The 4.7 beta release notes do not identify a subsequent change to this landing
state-machine logic.

For the four 4.7 logs currently being analysed, the relevant landing-controller
implementation can therefore be treated as consistent for our purposes.

This does **not** require us to prove byte-for-byte identity between every 4.6.3
and 4.7 source file.

### Consequences for the analyzer

We no longer need to infer the meaning of `LAND.stage` from flight data.

The analyzer can explicitly expose:

    0 = NORMAL
    1 = APPROACH
    2 = PREFLARE
    3 = FINAL

The raw landing fields should remain available:

    stage
    fh
    slope
    slopeInit
    altO

`fh` should be presented as **flare-timing height**.

Further landing analysis should use the source-defined state transitions rather than
inventing thresholds from observed logs.

### Future work

- Use the confirmed stage meanings in the LAND event extractor.
- Preserve raw `fh` for diagnostic analysis.
- Correlate PREFLARE and FINAL transitions with the configured landing parameters.
- Keep rangefinder events independent of landing-window detection.
- Investigate the four existing 4.7 logs using the confirmed source semantics.
- Add version compatibility handling before accepting pre-4.7 logs.