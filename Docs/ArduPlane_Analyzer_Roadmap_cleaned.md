# ArduPlane Analyzer Roadmap

## Vision

Build a modular engineering tool for objectively analysing ArduPilot fixed-wing
flight logs.

The initial focus is landing analysis. The framework must remain reusable for
future analyses such as TECS, cruise performance, RTL, power systems, autotune,
navigation and sensor diagnostics.

---

# Design Principles

- `FlightLog` owns decoded telemetry, parameters, events, mode segments and metadata.
- `FlightWindow` represents one continuous flight within a log.
- `FlightWindow` remains a lightweight time-bound object and does not own telemetry.
- Analysis operates within a selected `FlightWindow`.
- Analysis-specific windows are children of a `FlightWindow`.
- Processors, detectors and analyses receive the `FlightLog` and required scope.
- The analysis orchestrator selects flights and coordinates processors, detectors
  and results.
- Firmware-specific parameter names and units are normalised by `ParameterReader`.
- Detectors and analyses use the normalised parameter interface.
- Internal calculations use `TimeUS`.
- Human-readable times use `MM:SS.mmm`.
- Conclusions must be supported by telemetry and documented source behaviour,
  not inferred from isolated log values.
- Optional sensors must not become hidden prerequisites for defining analysis
  windows.

---

# Core Architecture

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
   └── FlightWindow(s)
          │
          ├── SensorHealthWindow
          ├── LandingWindow(s)
          ├── CruiseWindow(s)
          ├── AutotuneWindow(s)
          ├── RTLWindow(s)
          └── future analysis windows
```

Execution model:

```text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
Analysis-specific window
    │
    ▼
Processors / Detectors / Analysis
    │
    ▼
Result
    │
    ▼
Report
```

---

# Sensor Model

## Core Flight Sensors

The current framework treats these as the core sensors for normal fixed-wing
analysis:

- GPS
- Barometer
- Gyro / attitude solution

These are fundamental to the flight model and should be handled as core inputs.

## Optional Sensors

Other sensors remain independent evidence sources.

In particular:

- Rangefinder is optional.
- Rangefinder must not define the existence or boundaries of a landing window.
- Rangefinder processing may be useful during landing and automatic takeoff.
- Sensor-specific events should remain available even when the sensor is absent.

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
- [x] Present a firmware-independent parameter interface to detectors
- [x] Load `RNGFND*` parameters
- [x] Expose `RNGFND1_MAX` as a normalised metre value

## Firmware Identification

- [x] Decode BIN `VER` records
- [x] Add `FlightLog.firmware_version()`
- [x] Expose numeric major/minor/patch values
- [x] Preserve the firmware string from `FWS`
- [x] Confirm `log_26.bin` reports ArduPlane 4.7.0-beta8

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

Complete the transition from whole-log analysis to independently scoped flight
analysis.

A single BIN log may contain multiple flights. Each flight is analysed
independently while `FlightLog` remains the telemetry owner.

## Flight Detection

- [x] Introduce `FlightWindow`
- [x] Add `FlightLog.flights`
- [x] Implement `FlightWindowDetector`
- [x] Populate flight windows during log loading
- [x] GPS groundspeed-based flight detection
- [x] Default flight speed threshold of 5 m/s
- [x] Allow flight speed threshold to be configured
- [x] Support `AIRSPEED_STALL` in threshold calculation when available
- [x] Require above-threshold state to persist for 2 seconds
- [x] Require an extended ground period before separating flights
- [x] Support multiple flights within one log
- [x] Keep go-arounds within the same continuous `FlightWindow`
- [ ] Enable `AIRSPEED_STALL` parameter loading only after explicit
      FlightWindow regression validation

## Sensor Health Scoping

- [x] Refactor `SensorHealthWindowDetector` for flight-scoped operation
- [x] Accept `FlightLog` and selected `FlightWindow`
- [x] Validate that the window belongs to the supplied `FlightLog`
- [x] Derive sensor-health bounds within the parent flight
- [x] Restrict airspeed health analysis to the selected flight health window

## Analysis Orchestration

- [x] Iterate `FlightLog.flights`
- [x] Execute analysis independently for each `FlightWindow`
- [x] Produce one `AnalysisResult` per `FlightWindow`
- [x] Preserve `FlightLog` as telemetry owner
- [x] Distinguish analysis failures from framework failures
- [x] Validate multi-flight execution through the main CLI

## Analysis Model

- [x] `AnalysisResult` explicitly references its parent `FlightWindow`
- [x] Consolidate duplicate `LandingWindow` models
- [x] Remove legacy `landwindow.py`
- [x] Validate parent/child window relationships where required

## Flight-Scoped Processing

- [x] Scope LAND processing to `FlightWindow`
- [x] Scope MSG extraction to `FlightWindow`
- [x] Scope landing timeline sources to `FlightWindow`
- [x] Scope mode-segment selection to `FlightWindow`
- [x] Keep log-wide telemetry and segment ownership in `FlightLog`

## Landing Framework Preparation

- [x] Refactor `LandingWindowDetector`
- [x] Accept `FlightLog + FlightWindow`
- [x] Validate parent `FlightWindow`
- [x] Remove fixed absolute development interval
- [x] Return a bounded development `LandingWindow`
- [x] Establish support for multiple `LandingWindow` results
- [x] Validate LAND and MSG telemetry within individual flights
- [x] Defer real landing-attempt detection to v0.4

## Development Harnesses

- [x] Update reader harness for FlightWindow API
- [x] Update LAND-stage harness for flight scoping
- [x] Update MSG harness for flight scoping
- [x] Update rangefinder harness for canonical `LandingWindow`
- [x] Update timeline harness for parent `FlightWindow`
- [x] Remove runtime dependencies on legacy `LandingWindows`
- [x] Validate `log_17.bin` as a multi-flight regression case

## v0.2 Validation

Validated against `log_17.bin`:

- [x] Four independent flights detected
- [x] Flight boundaries agree with previously validated boundaries
- [x] Changing flight-start qualification from five samples to two seconds did
      not alter the four detected boundaries
- [x] Multiple go-arounds remain within one continuous flight
- [x] LAND records are correctly flight-scoped
- [x] MSG records are correctly flight-scoped
- [x] Landing timeline events remain within the selected flight
- [x] Main landing-analysis CLI produces four `AnalysisResult` objects
- [x] Main landing-analysis CLI completes with zero framework errors

---

# v0.3 — Analysis Framework ✅

## Objective

Standardise processors, detectors, analyses and result models around consistent
flight-scoped contracts.

The purpose of this milestone is API consistency rather than new landing-detection
behaviour.

## Analysis API

- [x] Define standard processor interface
- [x] Define standard detector interface
- [x] Define standard analysis interface
- [x] Standardise result models
- [x] Define common parent/child window validation
- [x] Establish `LandingAnalysis.analyse(flight_log, flight_window)`
- [x] Keep interactive `LandingAnalysis.run()` responsible for orchestration
  and presentation

Established contract:

```text
FlightLog + FlightWindow
        │
        ▼
Processor / Detector / Analysis
        │
        ▼
Scoped Result
```

## Sensor Processors

- [x] Refactor `AirspeedProcessor`
- [x] Refactor `GPSProcessor`
- [x] Refactor `BarometerProcessor`
- [x] Refactor rangefinder processing
- [x] Preserve existing airspeed validation behaviour
- [x] Correct airspeed native-rate result to contain the calculated numeric
      sample rate

Processors never read telemetry outside the selected parent flight.

## Event Processors

- [x] Refactor `EventExtractor`
- [x] Refactor `ArmCycleFinder`
- [x] Refactor `LandingTimeline`
- [x] Standardise event filtering helpers
- [x] Standardise event ownership and storage
- [x] Keep `ArmCycleFinder` strictly FlightWindow-scoped
- [x] Prevent pre-window ARM state from manufacturing partial cycles

`EventExtractor` operates within the selected `FlightWindow`.

`LandingTimeline` operates within its parent `FlightWindow` and child
`LandingWindow`.

Rangefinder event processing uses `Config/sensors.yaml`.

## Shared Utilities

- [x] Consolidate human-readable time formatting
- [x] Implement shared `core.time.format_time_us()`
- [x] Remove duplicated time-formatting code
- [x] Standardise window containment helpers
- [x] Standardise segment filtering helpers
- [x] Standardise telemetry filtering helpers

## Result Model

- [x] `AnalysisResult` identifies its parent `FlightWindow`
- [x] `AnalysisResult` exposes `SensorHealthWindow`
- [x] `AnalysisResult` exposes derived `LandingWindow` results
- [x] `AnalysisResult` carries analysis outputs without owning source telemetry
- [x] Remove remaining telemetry references from `AnalysisResult`

Telemetry ownership:

```text
FlightLog
    └── source telemetry

AnalysisResult
    ├── analysis scopes
    └── analytical results
```

## Rangefinder Configuration

- [x] Use `Config/sensors.yaml`
- [x] Add explicit `rangefinder.events` configuration
- [x] Preserve existing rangefinder event behaviour
- [x] Validate rangefinder event output after configuration refactor

Validated settings:

```yaml
rangefinder:
  events:
    zero_threshold: 0.05
    continuous_seconds: 1.0
```

Validated output:

```text
RFND_FIRST_NONZERO  1.97 m
RFND_CONTINUOUS     50 samples
```

## Development Harnesses

- [x] Migrate harnesses to public FlightWindow architecture
- [x] Remove obsolete processor API usage
- [x] Remove duplicated telemetry filtering
- [x] Remove duplicated segment filtering
- [x] Use shared time formatting
- [x] Add direct `LandingAnalysis.analyse()` harness
- [x] Validate sensor processors independently
- [x] Validate event processors independently
- [x] Validate rangefinder processing independently
- [x] Validate landing timeline independently

## v0.3 Validation

Validated against `log_17.bin`:

- [x] Python source tree compiles
- [x] Exactly four `FlightWindow` objects are detected
- [x] FlightWindow boundaries remain unchanged
- [x] Flight 2 remains one continuous flight through multiple landing attempts
- [x] LAND-stage telemetry remains flight-scoped
- [x] MSG events remain flight-scoped
- [x] ARM-cycle processing remains flight-scoped
- [x] Rangefinder events remain correctly scoped
- [x] Landing timeline remains correctly scoped
- [x] Airspeed behaviour remains unchanged
- [x] GPS processor regression harness passes
- [x] Barometer processor regression harness passes
- [x] Direct `LandingAnalysis.analyse()` produces one result per FlightWindow
- [x] Each result contains the expected `SensorHealthWindow`
- [x] Each result contains one bounded development `LandingWindow`
- [x] Main landing-analysis CLI produces four flight results
- [x] Main landing-analysis CLI reports zero framework errors
- [x] `AnalysisResult` no longer stores telemetry

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

# v0.4 — Landing Detection 🚧

## Objective

Detect real AUTO landing attempts objectively from logged telemetry.

A continuous `FlightWindow` may contain zero, one or multiple landing attempts.
Go-arounds and aborted approaches remain inside the parent flight while producing
separate landing attempts where supported by validated evidence.

## Event Model

The development timeline harness established a useful unified event stream.

`EventExtractor` is the authoritative source for time-ordered events and currently
combines:

- firmware `MSG`
- `LAND.stage`
- MODE

Rangefinder events remain an independent source and must not become a requirement
for defining a landing window.

Future landing detection should consume the common event model rather than
duplicating event extraction.

## Firmware and Parameter Context

The timeline header now records:

- firmware version from the BIN `VER` message
- `RNGFND1_MAX` from the verified parameter set

Example:

```text
Firmware : ArduPlane V4.7.0-beta8 (cb872be0)
RNGFND1_MAX : 6.0 m
```

The parameter reader already normalises:

```text
RNGFND1_MAX_CM → RNGFND1_MAX
```

with metres as the common unit.

## Current Four-Log Validation

Four ArduPlane 4.7 logs have been run through the timeline harness.

The purpose is to validate event evidence before implementing authoritative landing
attempt rules.

The comparison covers:

- landing-window boundaries
- `Mission: 1 LandStart`
- `Mission: 2 LoitAltitude`
- `Mission: 3 Land`
- `LAND.stage`
- `LAND.fh`
- `LAND.slope`
- `LAND.slopeInit`
- flare messages
- rangefinder timing
- aborted approaches
- restarted landings
- MODE transitions
- GPS / EKF / AHRS messages

The logs demonstrate that rangefinder timing varies independently of the landing
window and therefore must remain an optional evidence source.

## Landing Event Validation

- [ ] Catalogue LAND sequences across representative logs
- [ ] Catalogue firmware MSG landing sequences
- [ ] Validate aborted approaches
- [ ] Validate restarted landings
- [ ] Validate successful landings
- [ ] Validate multiple landing attempts within one flight
- [ ] Validate go-arounds
- [ ] Record validated observations in `Docs/Validation.md`
- [ ] Confirm the four 4.7 logs use compatible landing-controller behaviour

Detector rules must be supported by multiple representative logs before being
treated as authoritative.

## LAND Event Extraction

Source inspection has established the meaning of `LAND.stage`.

Use:

| Stage | Meaning |
|---:|---|
| 0 | NORMAL |
| 1 | APPROACH |
| 2 | PREFLARE |
| 3 | FINAL |

Raw LAND fields remain available:

```text
stage
fh
slope
slopeInit
altO
```

`fh` must be described as **flare-timing height**, not generic AGL or simply
rangefinder altitude.

- [ ] Use the confirmed stage meanings in `EventExtractor`
- [ ] Preserve raw `fh`
- [ ] Preserve raw `slope` and `slopeInit`
- [ ] Add validated stage details to timeline events
- [ ] Do not invent alternative stage thresholds

## Landing Attempt Detection

- [ ] Detect landing approach start
- [ ] Detect pre-flare evidence
- [ ] Detect final flare
- [ ] Detect aborted landing
- [ ] Detect restarted landing
- [ ] Detect touchdown evidence
- [ ] Detect rollout where telemetry supports it
- [ ] Detect multiple landing attempts within one flight
- [ ] Support go-arounds
- [ ] Return zero or more `LandingWindow` objects per `FlightWindow`
- [ ] Guarantee every `LandingWindow` lies within its parent `FlightWindow`

## Evidence Sources

Candidate evidence:

- `LAND.stage`
- firmware `MSG`
- MODE transitions
- GPS
- Airspeed
- Barometer
- Rangefinder

ARM/disarm is currently **not treated as a flight event**. The user commonly arms
and spins up in the pits before moving to the flight line, so ARM/DISARM can occur
outside the meaningful flight-event window. It may be used later if a specific
analysis requires it.

No source is authoritative until validated.

## Rangefinder

Rangefinder is optional and must remain independent of landing-window detection.

It has two known landing-analysis roles:

1. It can affect the height used for flare/pre-flare timing.
2. It can affect landing-slope correction.

It will also be relevant to future automatic-takeoff analysis.

Do not make rangefinder availability a condition for creating a `LandingWindow`.

## Parameter Snapshot Limitation

The framework currently associates one companion `.params` file with each BIN log.

That parameter set is therefore a log-level snapshot.

A future development flight may deliberately change landing parameters between
flights in the same BIN log. In that case the companion file cannot represent
every flight accurately.

Future enhancement:

- reconstruct active parameters from in-log `PARM` messages
- associate the reconstructed parameter state with each `FlightWindow`

Until then:

- companion `.params` is treated as the log-level parameter snapshot
- reports should identify the parameter source
- parameter-dependent analysis must not silently assume parameters were constant
- separate logs are preferable for comparative tuning flights

## Firmware Version Handling

The BIN `VER` message is available in current 4.7 logs and is now exposed through
`FlightLog.firmware_version()`.

The planned compatibility rule is:

- detect firmware version as early as possible
- reject unsupported pre-4.7 parameter formats as soon as they are read
- do not silently reinterpret a pre-4.7 parameter into a 4.7 analysis model
- use the version information in the BIN where available
- retain the parameter-file compatibility normalisation already implemented

A pre-4.7 log may not contain a usable `VER` record. That case must be handled
explicitly rather than guessed.

The v0.4 implementation now accepts only ArduPlane 4.7.x. Unsupported
firmware is rejected before parameters, flight windows or segments are built,
and the diagnostic harness reports unsupported logs as skipped rather than
crashing.

---

# v0.4 Validation / Current Status

The v0.4 landing-window implementation has now been validated against four
ArduPlane 4.7 regression logs.

## Completed v0.4 Implementation

- [x] Detect landing-window starts from `LAND.stage == 1`
- [x] Require AUTO mode at the landing-window start
- [x] Support multiple landing windows within a continuous `FlightWindow`
- [x] Bound aborted/go-around attempts instead of silently discarding them
- [x] Evaluate MSG, MODE, GPS persistence and flight-window-end termination
      independently of GPS sample timing
- [x] Select the earliest applicable termination boundary
- [x] Use GPS groundspeed below 3 m/s with 2 seconds persistence as the
      validated GPS termination rule
- [x] Keep `LAND.stage == 0` non-terminating
- [x] Restrict v0.4 firmware acceptance to ArduPlane 4.7.x
- [x] Handle unsupported firmware gracefully in the diagnostic harness
- [x] Keep the human-readable unified event timeline as a validation tool
- [x] Assert that all four regression logs are processed
- [x] Assert six validated flights and ten validated landing cases
- [x] Assert that no regression logs are skipped
- [x] Run compile and event-timeline regression successfully

Validated regression result:

```text
Regression logs  : 4 / 4
Validated flights : 6
Validated cases   : 10
Skipped logs      : 0

STATUS : PASS
```

## v0.4 Deferred Hardening

The following items were identified during the final read-only sanity review.
They are deliberately deferred rather than changing the validated v0.4
implementation.

- [ ] Add an explicit termination-reason field to `LandingWindow`, if the
      eventual analysis/result contract requires reason-bearing windows.
- [ ] Define handling for a new landing attempt that starts before the previous
      attempt has received an explicit termination event.
- [ ] Remove the no-op `LAND.stage == 0` scan from the detector.
- [ ] Remove unused imports from `landing_window_detector.py`.
- [ ] Consolidate duplicated LAND, MSG and MODE interpretation between the
      detector, event extractor and landing-attempt extractor.
- [ ] Add an independent diagnostic check proving the full GPS persistence
      interval rather than relying only on the detector's boundary.
- [ ] Resolve working-directory-dependent configuration paths if command-line
      execution from outside the repository root becomes a requirement.

These are cleanup, architecture or future-analysis concerns and are not required
to invalidate the current v0.4 regression result.

## v0.4 Analyse Deliverable

The unified event timeline is retained as a validation and diagnostic tool.
The eventual Analyse deliverable should consume the structured landing-window
and event data rather than the development harness directly.

- [ ] Add **Landing Analysis** to the Analyse menu.
- [ ] Present a structured landing-attempt timeline for each flight.
- [ ] Show landing-window start and end times.
- [ ] Show landing outcome: completed, aborted/go-around, disarmed, or unresolved.
- [ ] Show landing-window termination reason: GPS groundspeed, disarm, mode change,
      abort, or flight-window end.
- [ ] Show `LAND.stage` transitions alongside the landing timeline.
- [ ] Show key landing events including rangefinder engagement, flare, and
      landing aborts.
- [ ] Provide timestamps and measurements so each detected landing can be
      independently validated against the flight log.
- [ ] Use structured landing-window data as the foundation for progressively
      richer landing analysis in future versions.

## v0.4 Cleanup

- [ ] Audit module usage and identify genuinely unused modules before renaming
      or removing anything.
- [ ] Rename modules to more descriptive names where their current names obscure
      their purpose.
- [ ] Re-run the full regression suite after module cleanup.

# ArduPilot Landing Logic — Source Validation ✅

This investigation is complete and should be treated as the source of truth for
LAND-stage semantics.

## Confirmed Stage Definitions

| Stage | ArduPilot meaning |
|---:|---|
| 0 | NORMAL |
| 1 | APPROACH |
| 2 | PREFLARE |
| 3 | FINAL |

The logger records `stage` as progress through the landing sequence.

## Confirmed `LAND.fh` Meaning

`LAND.fh` is logged as:

```text
Height for flare timing
```

It is the `height` value supplied to the landing controller for flare and pre-flare
decisions.

It is **not** simply:

- rangefinder altitude
- barometric AGL
- generic height above ground

The analyzer should retain and label it as **flare-timing height**.

## Confirmed Pre-Flare Logic

Pre-flare is controlled by:

- `LAND_PF_ARSPD`
- `LAND_PF_ALT`
- `LAND_PF_SEC`

`LAND_PF_ARSPD > 0` enables the pre-flare stage.

The transition occurs when either:

```text
height <= LAND_PF_ALT
```

or the equivalent sink-rate/time condition is met:

```text
height <= sink_rate × LAND_PF_SEC
```

On entering PREFLARE, the landing controller targets `LAND_PF_ARSPD`.

Current aircraft settings:

```text
LAND_PF_ALT   = 4 m
LAND_PF_SEC   = 7 s
LAND_PF_ARSPD = 9 m/s
```

Therefore pre-flare is not necessarily a simple 4 m trigger.

## Confirmed Final Flare Logic

Final flare is controlled primarily by:

- `LAND_FLARE_ALT`
- `LAND_FLARE_SEC`

The altitude condition is:

```text
height <= LAND_FLARE_ALT
```

The time-based condition is based on:

```text
height <= sink_rate × LAND_FLARE_SEC
```

The time-based flare condition also requires sufficient progress along the landing
path, preventing an excessive flare setting from causing a premature flare while
the aircraft is still establishing the approach.

Additional final-stage conditions exist around passing the landing point and
rangefinder availability.

## Confirmed Rangefinder Interaction

Rangefinder data can affect:

1. the height used for landing flare/pre-flare timing
2. landing-slope correction

Therefore rangefinder remains an independent sensor/event source.

It is not a prerequisite for defining a landing window.

## Version Boundary

The relevant landing logic was already present in the 4.6.3 timeframe.

The 4.6.3 release notes contain landing/rangefinder fixes, including:

- landing flare when using a rangefinder
- landing slope when a rangefinder exists but is not in use

The 4.7 beta release notes do not identify a subsequent change to the relevant
landing state-machine logic.

For the four 4.7 logs being analysed, the relevant landing-controller behaviour
can therefore be treated as compatible for current analysis purposes.

There is no need to prove byte-for-byte identity between every 4.6.3 and 4.7 source
file.

## Source-Informed Analyzer Consequences

The analyzer does not need to infer LAND-stage semantics from flight data.

It can explicitly expose:

```text
0 = NORMAL
1 = APPROACH
2 = PREFLARE
3 = FINAL
```

It should retain:

```text
stage
fh
slope
slopeInit
altO
```

and label `fh` as flare-timing height.

Further landing analysis should use source-defined state transitions rather than
inventing thresholds from observed logs.

---

# v0.5 — Landing Analysis

## Objective

Measure what occurred during each detected landing attempt.

Analysis remains descriptive and evidence-based. It does not recommend parameter
changes.

## Geometry

- [ ] Approach geometry
- [ ] Glide slope
- [ ] Height profile
- [ ] Distance-to-landing-point profile
- [ ] Touchdown location where measurable

## Energy

- [ ] Airspeed profile
- [ ] Airspeed tracking
- [ ] Groundspeed profile
- [ ] Sink rate
- [ ] Throttle behaviour
- [ ] Energy-management observations

## Aircraft Response

- [ ] Pitch
- [ ] Roll
- [ ] Attitude tracking
- [ ] Control response where objectively measurable

## Flare

- [ ] Pre-flare timing
- [ ] Final flare timing
- [ ] Flare-timing height
- [ ] Flare airspeed
- [ ] Flare sink rate
- [ ] Flare duration
- [ ] Rangefinder evidence where available

## Touchdown

- [ ] Detect touchdown where telemetry permits
- [ ] Touchdown speed
- [ ] Touchdown sink rate
- [ ] Touchdown location
- [ ] Rollout measurements

## Sensor Validation

- [ ] GPS quality
- [ ] Barometer quality
- [ ] Gyro/attitude quality
- [ ] Airspeed quality
- [ ] Rangefinder quality where present
- [ ] Associate measurement confidence with source quality

## Metrics

Each metric must contain:

- measured value
- units
- source/evidence
- applicable time/window
- confidence or validity where appropriate

Metrics must not contain tuning recommendations.

---

# v0.6 — Reporting

## Objective

Present analysis results clearly while preserving the distinction between
measurement, evidence and interpretation.

## Report Structure

- [ ] Summary
- [ ] Measurements
- [ ] Evidence
- [ ] Observations
- [ ] Timeline
- [ ] Plots
- [ ] Appendix

## Console

- [ ] Landing summary
- [ ] Flight identification
- [ ] Landing-attempt identification
- [ ] Sensor-health summary
- [ ] Timeline
- [ ] Metrics

## Structured Output

- [ ] JSON export
- [ ] Stable result schema
- [ ] Machine-readable evidence references

## Rich Reports

- [ ] HTML report
- [ ] PDF report

## Plotting

Every plot must answer a specific engineering question.

Potential landing plots:

- [ ] approach geometry
- [ ] airspeed
- [ ] sink rate
- [ ] pitch
- [ ] throttle
- [ ] rangefinder
- [ ] pre-flare / flare detail

---

# v0.7 — Regression Framework

## Objective

Make analysis changes objectively testable against representative logs.

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
- [ ] ArduPlane 4.6 parameter format
- [ ] ArduPlane 4.7 parameter format
- [ ] Window containment
- [ ] Deterministic analysis results
- [ ] Deterministic report output

## Version Compatibility

- [ ] Confirm BIN firmware version handling
- [ ] Confirm behaviour when `VER` is absent
- [ ] Reject unsupported pre-4.7 parameter formats at read time
- [ ] Add explicit regression logs for supported firmware versions
- [ ] Record known firmware differences

## Validation Records

- [ ] Maintain representative flight-log catalogue
- [ ] Record expected flight boundaries
- [ ] Record expected landing-event sequences
- [ ] Record known firmware differences
- [ ] Record expected detector outputs

---

# Future Analyses

The architecture should support additional analyses without changing the core
flight framework.

Potential modules:

- TECS
- Cruise performance
- RTL
- Autotune
- Airspeed calibration
- Automatic takeoff
- Launch
- Power system
- Battery performance
- Wind estimation
- Navigation accuracy
- Mission analysis
- Sensor diagnostics

All future analyses should follow:

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
Processors / Analysis
    │
    ▼
Result
    │
    ▼
Report
```

---

# Future Enhancement — Per-Flight Parameters

The current companion `.params` model is log-wide.

If future tuning flights change parameters within one BIN log, the analyzer will
need to reconstruct active parameter state from in-log `PARM` messages.

This is deferred until parameter-dependent analysis requires it.

Potential implementation:

```text
BIN
 │
 ├── PARM changes
 │
 ▼
Parameter timeline
 │
 ▼
Parameter state for each FlightWindow
 │
 ▼
Analysis
```

---

# Architecture Status

## Completed

- [x] `FlightLog` owns decoded telemetry
- [x] `FlightLog` owns parameters
- [x] `FlightLog` owns mode segments
- [x] `FlightWindow` defines flight scope
- [x] Multiple flights per log are supported
- [x] Analysis orchestrator executes independently per flight
- [x] `AnalysisResult` identifies its parent `FlightWindow`
- [x] `AnalysisResult` does not own telemetry
- [x] LAND processing is flight-scoped
- [x] MSG extraction is flight-scoped
- [x] ARM-cycle processing is flight-scoped
- [x] Rangefinder processing is flight-scoped/landing-scoped
- [x] Landing timeline sources are flight-scoped
- [x] Processor APIs are standardised
- [x] Detector APIs are standardised
- [x] Reusable per-flight landing-analysis API is established
- [x] Shared telemetry filtering is established
- [x] Shared segment filtering is established
- [x] Shared window containment validation is established
- [x] Shared human-readable time formatting is established
- [x] BIN firmware version extraction is established
- [x] Normalised `RNGFND1_MAX` parameter access is established
- [x] Four 4.7 logs have been processed by the event-timeline harness
- [x] ArduPilot LAND-stage semantics have been verified from source

## Current

- [x] Real landing-window attempts are detected
- [x] Landing attempt detection rules are validated across four representative
      ArduPlane 4.7 logs
- [x] Firmware compatibility gate is implemented for ArduPlane 4.7.x
- [x] Unified event timeline provides validated LAND-stage, MSG and MODE evidence
- [ ] Landing metrics are implemented
- [ ] Analyse-menu landing deliverable is implemented

## Later

- [ ] Landing analysis
- [ ] Reporting
- [ ] GUI
- [ ] Automated regression framework
- [ ] Additional flight analyses


Landing-window termination — open question: investigate whether IMU/attitude data provides useful evidence for identifying the end of a landing attempt, particularly after flare/touchdown. Compare against airspeed, GPS, altitude and LAND-stage behaviour. Do not use ARM/DISARM or rangefinder as mandatory termination criteria.

## Architecture Reference — Current Analysis Flow

The project architecture is based on a common decoded `FlightLog` with
specialised processors providing different views of the same flight data.
These processors are intentionally parallel rather than forming one linear
processing chain. The analysis layer combines their outputs into an
analysis result.

```text
                     ┌─────────────────┐
                     │    BIN LOG      │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  log_reader.py  │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │ flight_data.py  │
                     │   FlightLog     │
                     └────────┬────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
 FlightWindowDetector   flight_segmenter   EventExtractor
          │                   │                   │
          ▼                   ▼                   ▼
   FlightWindow(s)      FlightSegment(s)    Event(s)
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                     ┌────────┴────────┐
                     │                │
                     ▼                ▼
          LandingWindowDetector   other processors
                     │
                     ▼
              LandingWindow(s)
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
    Airspeed data         Sensor health
          │                     │
          └──────────┬──────────┘
                     ▼
              analyses/landing.py
                     │
                     ▼
              analyses/result.py
                     │
                     ▼
                  analyse.py
```

### Architectural Principles

- `log_reader.py` converts the raw ArduPilot log into the common
  `FlightLog` representation.
- `flight_data.py` provides the shared flight-data model.
- `FlightWindowDetector`, `flight_segmenter`, `EventExtractor`, and
  `LandingWindowDetector` are specialised evidence/data processors.
- These processors operate from the common flight data and are not intended
  to form a single mandatory processing chain.
- `FlightWindow` identifies the bounds of an actual flight.
- `FlightSegment` describes meaningful phases or portions of a flight.
- `Event` provides discrete logged events and state transitions.
- `LandingWindow` identifies a specific landing attempt within a flight.
- Additional processors such as airspeed and sensor-health analysis provide
  specialised measurements or evidence.
- `analyses/landing.py` combines these independent sources into a landing
  analysis.
- `analyses/result.py` provides the structured analysis result.
- `analyse.py` is the application entry point and presentation layer.

### Design Rule

**Processors should provide evidence; analysis modules should interpret and
combine that evidence.**

Avoid moving analysis-specific interpretation into low-level processors unless
there is a clear reason for it to be reusable by multiple analyses.

This separation is intended to allow future analyses such as TECS, cruise
performance, RTL, power systems, and autotune to reuse the same underlying
flight-data and evidence-processing framework.