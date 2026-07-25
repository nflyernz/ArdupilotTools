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