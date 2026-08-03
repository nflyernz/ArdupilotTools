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
...

## Current Architecture

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
...             
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
- [x] Use `AIRSPEED_STALL` where available when determining effective threshold
- [x] Require above-threshold state to persist for 2 seconds
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

# v0.3 — Analysis Framework

## Objective

Standardise processors, detectors, analyses, and result models around consistent flight-scoped contracts.

The purpose of this milestone is API consistency rather than new landing-detection behaviour.

---

## Analysis API

- [ ] Define standard processor interface
- [ ] Define standard detector interface
- [ ] Define standard analysis interface
- [ ] Standardise result models
- [ ] Define common parent/child window validation

---

## Sensor Processors

- [ ] Refactor `AirspeedProcessor`
- [ ] Refactor `GPSProcessor`
- [ ] Refactor `BarometerProcessor`
- [ ] Refactor rangefinder processing

Target pattern:

```text
Processor
    │
    ├── FlightLog
    ├── FlightWindow
    └── optional analysis-specific sub-window
...    

Processors must never read telemetry outside the selected parent flight.
    
## Event Processors

- [ ] Refactor `EventExtractor`
- [ ] Refactor `ArmCycleFinder`
- [ ] Refactor `LandingTimeline`
- [ ] Standardise event filtering helpers
- [ ] Standardise event ownership and storage
  
    
## Shared Utilities

- [ ] Consolidate human-readable time formatting
- [ ] Implement shared `core.time.format_time_us()`
- [ ] Remove duplicated time-formatting code
- [ ] Standardise window containment helpers
- [ ] Standardise segment filtering helpers
- [ ] Standardise telemetry filtering helpers

---

## Common Conventions

- [ ] `FlightLog` remains telemetry owner
- [ ] `FlightWindow` defines parent analysis scope
- [ ] Child windows are bounded by `FlightWindow`
- [ ] Processors explicitly identify their parent flight
- [ ] Health and analysis remain separate responsibilities
- [ ] Validation responsibilities are consistent across processors

---

# v0.4 — Landing Detection

## Objective

Detect real AUTO landing attempts objectively from logged telemetry.

A continuous `FlightWindow` may contain zero, one, or multiple landing attempts.

Go-arounds and aborted approaches must produce separate landing attempts without splitting the parent flight.

---

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
- [x] LAND processing is flight-scoped
- [x] MSG extraction is flight-scoped
- [x] Landing timeline sources are flight-scoped
- [x] Development harnesses use the current FlightWindow architecture
- [ ] Processor APIs are fully standardised
- [ ] Real landing attempts are detected
- [ ] Landing metrics are implemented
- [ ] Landing reports are implemented

---

# Current Development Target

## v0.3 — Analysis Framework

With FlightWindow integration complete, the next development task is to standardise processor and event-processing APIs around the established architecture:

```text
FlightLog
    +
FlightWindow
    ↓
Processor / Detector
    ↓
Scoped Result
```

Real landing-attempt detection begins after that API consolidation in **v0.4 — Landing Detection**.