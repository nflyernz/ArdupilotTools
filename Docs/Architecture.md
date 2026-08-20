# ArduPlane Analyzer Architecture

## Mission

ArduPlane Analyzer is an engineering analysis tool for ArduPlane flight logs.

It does not replace UAV Log Viewer, Mission Planner, or QGroundControl.

Its purpose is to explain **why** the aircraft behaved as it did using objective measurements derived from the flight log.

---

# Philosophy

The analyser shall:

- Measure
- Compare
- Quantify
- Explain

The analyser shall not:

- Tune aircraft
- Recommend parameter values
- Optimise PID gains
- Override pilot judgement

---

# Core Principles

## Evidence Before Opinion

Every statement shall be supported by measurable evidence.

Example:

> Average approach speed was 10.4 m/s.

Not:

> Landing speed was too slow.

---

## Behaviour Before Parameters

Aircraft behaviour is analysed.

Parameters provide context only.

Example:

```text
LAND_ARSPD = 11 m/s
Measured IAS = 10.2 m/s
Difference = -0.8 m/s
```

No recommendation is made.

---

## Every Graph Answers a Question

Graphs are never included simply because the data exists.

Every graph must answer a specific engineering question.

---

## Every Metric Has a Purpose

Each metric must answer one question.

Examples:

**Glide slope**

Did the aircraft follow the intended approach?

**Pitch tracking**

Did the aircraft achieve commanded pitch?

**Throttle**

Was energy management stable?

---

## Pilot Remains Responsible

The software highlights observations.

The pilot decides whether configuration changes are appropriate.

---

# Core Architecture

The central architecture is:

```text
BIN Log
    │
    ▼
FlightReader
    │
    ▼
FlightLog
    │
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

A BIN log may contain zero, one, or multiple flights.

`FlightReader` decodes the log once and constructs one `FlightLog`.

`FlightWindowDetector` identifies the individual flights contained within that log.

Analyses then operate independently on each selected `FlightWindow`.

---

# FlightLog

`FlightLog` is the sole owner of decoded log-level data.

It owns:

- telemetry messages
- parameters
- firmware events
- mode segments
- metadata
- detected `FlightWindow` objects

`FlightLog` remains the telemetry source throughout analysis.

Telemetry ownership is **not** transferred into individual windows.

Conceptually:

```text
FlightLog
    ├── GPS
    ├── ARSP
    ├── BARO
    ├── LAND
    ├── MSG
    ├── ARM
    ├── MODE
    ├── Parameters
    ├── Events
    ├── Segments
    └── Flights
```

Processors and detectors obtain telemetry from `FlightLog` and constrain that telemetry using the selected analysis scope.

---

# FlightWindow

`FlightWindow` represents one continuous flight within a `FlightLog`.

It is intentionally lightweight.

Its core contract is:

```text
FlightWindow
    ├── start_us
    └── end_us
```

A `FlightWindow` does **not**:

- own telemetry
- own parameters
- duplicate message DataFrames
- own mode segments
- own firmware events

It defines **scope**, not data ownership.

---

# Flight Detection

`FlightWindowDetector` identifies continuous flights using GPS groundspeed.

The current detection model:

- uses a configurable groundspeed threshold
- defaults to 5 m/s
- may raise the effective threshold using normalised `AIRSPEED_STALL`
- requires the above-threshold state to persist for 2 seconds
- requires an extended ground period before separating flights

A go-around does not create a new `FlightWindow` unless the aircraft satisfies the ground-separation rule.

Therefore:

```text
Takeoff
   │
   ▼
Approach
   │
   ▼
Go-around
   │
   ▼
Approach
   │
   ▼
Landing

= one FlightWindow
```

A single BIN log may therefore contain:

```text
FlightLog
    ├── FlightWindow 1
    ├── FlightWindow 2
    ├── FlightWindow 3
    └── FlightWindow 4
```

Each is analysed independently.

---

# Analysis Scope

The analysis orchestrator selects one `FlightWindow` from the `FlightLog`.

The standard architecture is:

```text
FlightLog
    +
FlightWindow
    │
    ▼
Processor / Detector
    │
    ▼
Scoped Result
```

Where flight scope is required, processors and detectors receive:

```text
FlightLog + FlightWindow
```

`FlightLog` supplies the data.

`FlightWindow` supplies the allowed time bounds.

No processor or detector performing per-flight analysis should use telemetry outside the selected `FlightWindow`.

---

# Analysis-Specific Windows

Some analyses require narrower windows within a flight.

Examples include:

- `SensorHealthWindow`
- `LandingWindow`
- future `CruiseWindow`
- future `AutotuneWindow`
- future `RTLWindow`

These are child scopes of a `FlightWindow`.

Conceptually:

```text
FlightWindow
    │
    ├── SensorHealthWindow
    │
    ├── LandingWindow 1
    ├── LandingWindow 2
    └── LandingWindow 3
```

A child window must be contained within its parent:

```text
flight_window.start_us
    <= child_window.start_us
    <= child_window.end_us
    <= flight_window.end_us
```

Child windows do not become telemetry owners.

---

# SensorHealthWindow

`SensorHealthWindow` defines the interval used to evaluate sensor quality for one flight.

It is derived from a selected `FlightWindow`.

The current implementation trims transient periods from the beginning and end of the parent flight.

Conceptually:

```text
FlightWindow
|------------------------------------------------|

  SensorHealthWindow
  |--------------------------------------------|
```

Sensor-health analysis must not extend outside the parent `FlightWindow`.

---

# LandingWindow

`LandingWindow` represents one landing attempt within a `FlightWindow`.

A flight may contain:

- no landing attempts
- one landing attempt
- multiple landing attempts

For example:

```text
FlightWindow
    │
    ├── LandingWindow 1
    │       └── aborted
    │
    ├── LandingWindow 2
    │       └── aborted
    │
    └── LandingWindow 3
            └── completed
```

Go-arounds therefore create additional landing attempts, not additional flights.

The canonical `LandingWindow` model is used throughout the repository.

`LandingWindowDetector` identifies landing activity within the selected
`FlightWindow`. A landing window may contain one or more bounded
`LandingAttempt` objects when go-arounds or aborts occur.

Landing attempts are derived from logged flight behaviour and firmware
events. Their boundaries are constrained to the parent `LandingWindow`
and `FlightWindow`.

Conceptually:

```text
FlightWindow
    │
    └── LandingWindow
            │
            ├── LandingAttempt 1 ──► aborted
            ├── LandingAttempt 2 ──► aborted
            └── LandingAttempt 3 ──► completed
```

`LandingAttemptProcessor` converts each bounded attempt into objective
landing evidence. It does not classify landing quality or recommend
configuration changes.

---

# Analysis Orchestration

The orchestrator is responsible for selecting flight scope.

For a log containing multiple flights:

```text
FlightReader
    │
    ▼
FlightLog
    │
    ├── FlightWindow 1 ──► Analysis ──► AnalysisResult 1
    │
    ├── FlightWindow 2 ──► Analysis ──► AnalysisResult 2
    │
    ├── FlightWindow 3 ──► Analysis ──► AnalysisResult 3
    │
    └── FlightWindow 4 ──► Analysis ──► AnalysisResult 4
```

Each flight is analysed independently.

A failure or observation in one flight must not contaminate another flight's result.

---

# AnalysisResult

`AnalysisResult` represents the result of analysing one selected `FlightWindow`.

Every result must explicitly identify its parent flight.

Conceptually:

```text
AnalysisResult
    ├── log_path
    ├── flight_window
    ├── sensor_health
    ├── analysis-specific results
    └── report
```

The result may refer to derived analysis windows and measurements.

It does not transfer telemetry ownership from `FlightLog`.

---

# Processor Architecture

Processors convert raw telemetry into engineering measurements or validation results.

Examples include:

- `AirspeedProcessor`
- `GPSProcessor`
- `BarometerProcessor`
- rangefinder processing

The target processor contract is:

```text
Processor
    │
    ├── FlightLog
    ├── FlightWindow
    └── optional analysis-specific sub-window
```

A processor:

1. obtains telemetry from `FlightLog`
2. constrains it to the parent `FlightWindow`
3. optionally constrains it further to an analysis-specific child window
4. produces measured or validated output

Processors do not make tuning recommendations.

---

# Detector Architecture

Detectors identify meaningful time windows or events.

Examples include:

- `FlightWindowDetector`
- `SensorHealthWindowDetector`
- `LandingWindowDetector`

A detector must clearly define:

- its telemetry source
- its parent scope
- its output scope
- its containment rules

Where a detector operates within a flight, the parent `FlightWindow` must be explicit.

---

# Event Architecture

Firmware events remain associated with the `FlightLog`.

Per-flight analysis extracts or filters events using the selected `FlightWindow`.

Examples include:

- firmware `MSG` records
- `LAND.stage` transitions
- ARM/disarm events
- MODE transitions
- rangefinder events

Conceptually:

```text
FlightLog Events
       │
       ▼
FlightWindow filter
       │
       ▼
Flight-scoped Events
       │
       ▼
LandingWindow filter
       │
       ▼
Landing Timeline
```

Events are filtered by scope rather than copied into `FlightWindow`.

---

# Mode Segments

Mode segments are generated at log scope and stored by `FlightLog`.

Analyses select only segments overlapping their chosen `FlightWindow`.

This preserves one authoritative mode timeline while preventing cross-flight analysis.

---

# Parameter Architecture

The framework presents a normalised parameter interface to processors and detectors.

Firmware-specific parameter names and units are resolved in `ParameterReader`.

Example:

| Firmware | Native Parameter | Normalised |
|----------|------------------|------------|
| 4.6.x | `RNGFND1_MAX_CM` (cm) | `RNGFND1_MAX` (m) |
| 4.7.x | `RNGFND1_MAX` (m) | `RNGFND1_MAX` (m) |

Processors and detectors always request:

```python
flight_log.param("RNGFND1_MAX")
```

They are never responsible for firmware compatibility.

Firmware compatibility therefore remains isolated:

```text
Firmware Parameters
        │
        ▼
ParameterReader
        │
        ▼
Normalised Parameters
        │
        ▼
FlightLog
        │
        ▼
Processors / Detectors
```

---

# Time Architecture

Internal calculations use integer microsecond timestamps:

```text
TimeUS
```

Time comparisons, window boundaries, event ordering, and calculations remain in `TimeUS`.

Human-readable output uses:

```text
MM:SS.mmm
```

Time formatting is a presentation concern and must not affect internal calculations.

---

# Landing Analysis

Landing analysis operates on one selected `FlightWindow` at a time.

The current architecture is:

```text
FlightLog
    +
FlightWindow
    │
    ▼
LandingWindowDetector
    │
    ▼
LandingWindow(s)
    │
    ▼
LandingAttemptExtractor
    │
    ▼
LandingAttempt(s)
    │
    ▼
LandingAttemptProcessor
    │
    ▼
LandingAttemptAnalysis
    │
    ▼
Presentation
```

`LandingAnalysis` is the workflow and presentation layer. It owns the
landing configuration for the analysis run and supplies that configuration
to the reader, detectors, and processors that require it.

The landing pipeline currently reports objective evidence including:

- landing-window timing and duration
- approach altitude
- glide slope
- preflare timing and height
- airspeed and GPS groundspeed at preflare
- sink rate at preflare
- flare timing and flare-timing height
- airspeed and GPS groundspeed at flare
- sink rate at flare
- flare distance to the mission LAND target when a valid target is available
- rangefinder acquisition evidence
- GPS-stop timing when detected
- flare-to-stop elapsed time
- final distance from the mission LAND target when available
- attempt termination reason

A mission LAND target is used only when the applicable `CMD` records form
a complete, consecutive mission snapshot and contain exactly one usable
`MAV_CMD_NAV_LAND` command. Missing, incomplete, invalid, or ambiguous
mission evidence produces an unavailable measurement rather than a guessed
target.

Optional telemetry remains non-fatal. For example, unavailable airspeed,
rangefinder, flare, GPS-stop, or target evidence is represented as
unavailable where appropriate rather than causing the landing analysis to
invent a value.

Sensor-health analysis is a separate concern. It may use the same
`FlightLog` and parent `FlightWindow`, but it is not a prerequisite stage
inside the landing-attempt measurement pipeline.

Additional landing metrics such as pitch tracking, roll behaviour,
throttle behaviour, TECS behaviour, and richer touchdown analysis are not
part of the current landing report. They may be added later when each
metric has a defined engineering purpose and validated evidence model.

Landing analysis describes what occurred.

It does not prescribe parameter changes.

# Report Structure

Reports are structured around evidence.

Expected sections include:

- Summary
- Measurements
- Evidence
- Observations
- Timeline
- Plots
- Appendix

The distinction between measurement and interpretation must remain explicit.

---

# Coding Philosophy

Modules should be small and have a single responsibility.

Avoid duplicated logic.

Public contracts should be explicit.

Every function should be testable.

Every report should be reproducible.

Common operations such as:

- time formatting
- window containment
- telemetry filtering
- segment filtering

should have shared implementations rather than being independently recreated by individual processors.

---

# Reproducibility

Analysis is derived only from telemetry and parameters contained in the flight data.

External development material may be used to validate implementation behaviour, but it must not influence runtime results.

Therefore:

```text
Same Log
   +
Same Analyzer Version
   =
Same Analysis Result
```

This requirement applies to:

- flight detection
- landing detection
- sensor validation
- metrics
- timelines
- reports

---

# Architectural Contract

The authoritative model is:

1. `FlightReader` decodes one log into one `FlightLog`.
2. `FlightLog` owns decoded telemetry, parameters, events, segments, metadata, and detected flights.
3. `FlightWindow` represents one continuous flight and contains only flight scope.
4. Analyses select one `FlightWindow` at a time.
5. Flight-scoped processors and detectors use `FlightLog + FlightWindow`.
6. Analysis-specific child windows must remain within their parent `FlightWindow`.
7. Telemetry ownership remains with `FlightLog`.
8. Firmware compatibility remains within `ParameterReader`.
9. Internal time remains `TimeUS`.
10. Analysis output remains objective and reproducible.