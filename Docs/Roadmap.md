# Version 0.1

✓ Read BIN

✓ Extract messages

✓ Export CSV

✓ Dashboard

---

# Version 0.2

Landing segmentation

Landing metrics

Landing report

---

# Version 0.3

Landing scorecard

HTML report

PDF report

---

# Version 0.4

Parameter integration

Multiple aircraft profiles

---

# Version 0.5

Flight comparison

Parameter comparison

Firmware comparison

---

# Version 0.6

Launch module

---

# Version 1.0

Public release


## v0.2.1 – ArduPlane 4.6 Compatibility

### Investigate

- [ ] Parameter loading
  - Compare 4.6.3 and 4.7 `.params` formats.
  - Determine why 4.6 parameters are not loading.

- [ ] LAND messages
  - Compare LAND message sequences between 4.6.3 and 4.7.
  - Identify any behavioural changes.

- [ ] Landing window detection
  - Investigate oversized landing windows on 4.6.3 logs.
  - Verify behaviour with go-arounds and aborted approaches.

### Validation

- [ ] Run detector suite on all available logs.
- [ ] Record observations before modifying algorithms.
- [ ] Only change detectors when supported by multiple logs.


## Objective Analysis Principle

The toolkit shall derive its conclusions solely from telemetry contained within the flight log.

The processing chain is:

## Objective Analysis Principle

The toolkit shall derive its conclusions solely from telemetry contained within the flight log.

The processing chain is:

```text
Flight Log
    │
    ▼
Processors
    │
    ▼
Analyzers
    │
    ▼
Report
```

### Design Principle

The flight log is the only source of truth.

Processors and analyzers shall operate only on information contained within the telemetry. They shall not consume or depend upon:

- pilot notes
- flight journals
- developer annotations
- video recordings
- user input
- manually entered events

These sources may be used during development to validate the software, but they must never influence the analysis itself.

### Validation

Development follows an independent validation workflow:

```text
Flight Log
    │
    ▼
Analysis
    │
    ▼
Report
    │
    ├── UAV Log Viewer
    ├── Pilot observations
    ├── Flight video
    └── Engineering review
```

Validation exists only to answer one question:

> Did the software correctly interpret the telemetry?

If not, the algorithms are improved. The validation data is never incorporated into the runtime analysis.

### Architectural Guidance

When adding a new feature, ask:

1. Can this conclusion be reached directly from telemetry?
2. If not, can it be derived objectively from existing processor outputs?
3. If neither is possible, it does not belong in the analyzer.

This principle applies to every processor, analyzer and report.

### Expected Outcome

A completed analysis must be:

- deterministic
- repeatable
- objective
- independent of the operator
- suitable for unattended batch processing

Running the toolkit on the same log must always produce the same result, regardless of who performs the analysis or what they know about the flight.


✓ FlightReader

✓ BARO Processor

✓ GPS Processor

⬜ ARSP Processor

⬜ RFND Processor (redesign)

⬜ FC Processor

⬜ Landing Window Analyzer

⬜ Landing Analyzer

⬜ Landing Report


### Format Validation Event Times

Display validation event start/end times as MM:SS.sss instead of raw TimeUS values. Retain TimeUS internally for calculations and cross-referencing between sensors.

### Design Principle

### Adopt Analysis-Centric Architecture

The application will be organised around analysis workflows rather than individual sensor modules.

Each analysis (e.g. Landing Analysis, Cruise Analysis, Sensor Diagnostics) will orchestrate the required processing pipeline:

1. Select log(s)
2. Load telemetry
3. Determine the analysis window
4. Execute the required processors
5. Generate structured results
6. Present reports (CLI, regression runner, or GUI)

Sensor processors are independent, reusable components responsible only for analysing their own data and reporting results. They remain unaware of the calling workflow or presentation layer.

The same analysis engine will be shared by:
- Command-line interface
- Regression runner
- Future GUI

This ensures a single source of analysis logic while allowing multiple front ends.

### Transition to Analysis-Driven Execution

The current `test_<processor>.py` scripts are development harnesses used while implementing and debugging individual processors.

As the project matures, all execution paths will converge on the analysis engine. The test scripts will become lightweight wrappers that invoke the same analysis classes used by the regression runner and future GUI.

Target architecture:

    test_*.py
         │
    regression.py
         │
        GUI
         │
         ▼
    Analysis Engine
         │
         ▼
    Sensor Processors
         │
         ▼
    Analysis Results

This establishes a single execution path for all processing. New functionality is implemented once in the analysis engine and is immediately available to developer tests, regression testing, command-line execution, and the GUI without duplication.

Status: Planned
Priority: High

### Structure

Analyse/
│
├── analyse.py          ← application entry point
│
├── analyses/
│   ├── landing.py
│   ├── cruise.py
│   ├── diagnostics.py
│   └── summary.py
│
├── core/
│   ├── reader.py
│   ├── airspeed.py
│   ├── gps.py
│   └── barometer.py
│
└── tests/
    ├── test_airspeed.py
    ├── test_gps.py
    └── ...
    
    ### Output Formatting

Consolidate all human-readable time formatting into a shared utility.

Current status:
- Time formatting exists in multiple locations (e.g. landing.py, test scripts).
- Internal processing uses TimeUS (microseconds).
- User-facing reports should consistently display MM:SS.mmm.

Planned:
- Create a shared `core.time.format_time_us()` helper.
- Use it throughout all analyses, reports, diagnostics, and tests.
- Keep all internal calculations in TimeUS and only format at presentation time.

Benefit:
- Single implementation.
- Consistent output across CLI, regression tests, and future GUI.
- Avoid duplicated formatting logic.





## Sensor Health vs Analysis

The first implementation of `AirspeedProcessor.health()` demonstrated that not all existing validation rules are appropriate for sensor health.

### Sensor Health

Health answers:

> "Can this sensor be trusted?"

Typical rules:

- Missing sensor
- Missing values
- Timestamp ordering
- Sample gaps
- Impossible values
- Corrupt data

Health is normally evaluated over the entire flight.

### Analysis

Analysis answers:

> "What happened during this phase of flight?"

Typical rules:

- Low airspeed
- Excessive airspeed change
- Landing performance
- Flare behaviour
- Sink rate
- Energy management

Analysis is performed over a selected flight window.

### Design Principle

Health and analysis are separate responsibilities.

A processor may expose both:

```python
processor.health()
processor.analyse(window)



## Next Refactor: Sensor Health Window

The first implementation of sensor health highlighted that evaluating health over the entire flight log produces false positives. Examples include low airspeed before takeoff and after landing, and possible logging artefacts while the aircraft is stationary.

The next refactor will introduce a common **Sensor Health Window** that defines the period over which sensor health is evaluated.

### Sensor Health Window

The window will be derived from GPS groundspeed.

Preconditions:

- GPS data must be present.
- GPS quality (HDOP) must be within the configured limit.
- If either condition fails, sensor health analysis is aborted.

Window definition:

- Start when:

      groundspeed > max(0.5 × AIRSPEED_STALL, 5 m/s)

- End when groundspeed falls below the same threshold.

If `AIRSPEED_STALL` is unavailable, a default threshold of **5 m/s** is used.

### Benefits

- Evaluates sensors only during meaningful flight.
- Removes expected false positives while stationary.
- Uses GPS as an independent reference.
- Provides a common evaluation window for multiple sensor processors.

### Scope

This refactor changes **where** health is evaluated, not **how** individual validation rules work.

Existing airspeed validation rules will remain unchanged until they are re-evaluated using the new Sensor Health Window.

# Sensor health window

Support multiple sensor health windows for logs containing multiple flights or touch-and-go operations.

## Sensor Health Window

### Completed

- GPS-speed based detector
- Sensor validation restricted to the health window
- Eliminated pre-flight and post-flight false positives

### Remaining

- Support multiple `SensorHealthWindow`s within a log by splitting flights after extended ground periods.
- Split windows after an extended ground period.
- Continue using the existing GPS speed threshold.
- Add configurable minimum ground time before ending a window.
- Return multiple `SensorHealthWindow` objects rather than a single longest window.

---

## Landing Analysis Window

### Planned

Create a separate `LandingWindow` for AUTO landings.

Derived from firmware `MSG` events:

Start:
- Landing approach start
  (or `Mission: 3 Land`)

End:
- Throttle disarmed
- Landing aborted via throttle

The landing analyser will operate on `LandingWindow`, not `SensorHealthWindow`.

Multiple landing windows are supported naturally for aborted landings and retries.

Manual takeoffs and manual landings are intentionally out of scope.

## Flight Windows

### ✓ Completed

- GPS-based `SensorHealthWindow`
- Sensor validation restricted to the health window
- False positives from pre-flight and post-flight largely eliminated

---

## Event Timeline

### ✓ Completed

- `MSG` records successfully loaded from BIN logs.
- `TimelineEvent` extended to support `EventType.MSG`.
- Firmware messages exposed as timestamped events.

This exposes information not available in UAV Log Viewer, including:

- AUTO trigger
- Takeoff
- Landing approach
- Glide slope
- Flare
- Landing abort
- Autotune
- Airspeed warnings
- Mission progress

---

## Sensor Health Window

Purpose:

Determine when sensor validation is meaningful.

Current implementation:

- GPS-speed based
- Single continuous window
- Independent of flight mode

This window is used only for sensor health validation.

---

## Landing Analysis Window

Purpose:

Define the period over which AUTO landing analysis is performed.

Unlike the Sensor Health Window, this window is firmware-driven.

Candidate boundaries:

Start:
- `Mission: 3 Land`
  or
- `Landing approach start`

End:
- `Throttle disarmed`
- `Landing aborted via throttle`

This allows multiple landing windows within a single flight (go-arounds).

Only AUTO landings will be analysed.

Manual takeoffs and manual landings are intentionally outside the scope of landing analysis.

---

## Planned

### EventExtractor

Extract `TimelineEvent`s from `MSG`.

### LandingWindowDetector

Construct one or more `LandingWindow`s from firmware events.

### Landing Analysis

Operate on `LandingWindow` rather than `SensorHealthWindow`.

### Future

Integrate derived events (touchdown, rangefinder, GPS stop) with firmware events into a single chronological timeline.

### architectural target

FlightReader
    │
    ▼
FlightLog
    ├── Messages
    ├── Parameters
    ├── Events
    └── FlightWindow(s)
             │
             ├── SensorHealthWindow
             ├── LandingWindow(s)
             ├── CruiseWindow(s)
             ├── AutotuneWindow(s)
             ├── RTLWindow(s)
             └── ...
             
 Architecture

FlightReader is responsible only for decoding the log into a FlightLog. Analysis-specific window detectors progressively enrich each FlightWindow, allowing new analyses to be added without modifying the reader. This provides a scalable framework supporting multiple flights and multiple analysis windows per flight.

## Flight Framework

### Objective

Introduce `FlightWindow` as the primary organisational unit within a flight log. All analysis-specific windows will be scoped to an individual flight, allowing multiple flights to be represented within a single log.

### Planned

- Add `FlightWindow` to the core model.
- Add `flight.flights` to `FlightLog`.
- Implement `FlightWindowDetector`.
- Populate `FlightLog.flights` during log loading.
- Refactor `SensorHealthWindowDetector` to operate on a `FlightWindow`.
- Refactor `LandingWindowDetector` to operate on a `FlightWindow`.

### Target Architecture

```text
reader.py
    │
    ▼
FlightLog
    ├── Messages
    ├── Parameters
    ├── Events
    ├── Segments
    └── FlightWindow(s)
             │
             ├── SensorHealthWindow
             ├── LandingWindow(s)
             ├── CruiseWindow(s)
             ├── AutotuneWindow(s)
             ├── RTLWindow(s)
             └── ...
```

### Notes

- `reader.py` remains responsible solely for decoding the log into a `FlightLog`.
- `FlightWindowDetector` identifies individual flights within the log.
- Analysis-specific window detectors progressively enrich each `FlightWindow`.
- This architecture supports multiple flights per log and multiple analysis windows per flight while keeping responsibilities clearly separated.