# ArduPlane Analyzer Roadmap

## Vision

Build a modular engineering tool for objectively analysing ArduPilot
fixed-wing flight logs.

The analyzer should explain what occurred from logged telemetry,
preserve the distinction between evidence and interpretation, and
provide a reusable framework for analyses such as landing, TECS, cruise
performance, RTL, autotune, launch, power systems, navigation and sensor
diagnostics.

------------------------------------------------------------------------

# Design Principles

-   `FlightLog` is the source owner for decoded telemetry, parameters,
    mode segments and metadata.
-   `FlightWindow` represents one continuous flight within a log.
-   Every analysis operates within a selected `FlightWindow`.
-   Analysis-specific windows are derived within their parent
    `FlightWindow`.
-   Detectors own event and window boundaries.
-   Processors measure evidence inside established boundaries.
-   Analysis modules combine evidence into structured results.
-   Presentation does not silently change detector semantics.
-   Optional sensors remain optional.
-   Missing or ambiguous evidence produces `Unavailable`, not a guessed
    value.
-   Internal calculations use `TimeUS`.
-   Human-readable output uses `MM:SS.mmm`.
-   Metrics remain descriptive unless a later milestone explicitly
    introduces a validated interpretation layer.
-   No tuning recommendation should be generated merely because a
    parameter or measurement looks unusual.

The core rule is:

> **Processors provide evidence; analysis modules combine and present
> that evidence.**

------------------------------------------------------------------------

# Architecture

``` text
BIN log
    │
    ▼
FlightReader
    │
    ▼
FlightLog
    ├── telemetry
    ├── parameters
    ├── mode segments
    ├── metadata
    │
    └── FlightWindow(s)
             │
             ├── Event Timeline
             ├── Battery Analysis
             ├── LandingWindow(s)
             │       │
             │       ▼
             │  LandingAttempt
             │       │
             │       ▼
             │  LandingAttemptProcessor
             │       │
             │       ▼
             │  LandingAttemptAnalysis
             │
             └── future analysis-specific windows
```

General analysis pattern:

``` text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
Analysis-specific Window
    │
    ▼
Processors / Detectors
    │
    ▼
Analysis
    │
    ▼
Result
    │
    ▼
Presentation / Report
```

------------------------------------------------------------------------

# Completed Foundation

## v0.1 --- Core Framework ✅

Established:

-   [x] BIN log reading.
-   [x] Configured DataFlash/MAVLink message decoding.
-   [x] Companion parameter-file loading.
-   [x] `FlightLog`.
-   [x] pandas telemetry storage.
-   [x] Parameter normalisation framework.
-   [x] MODE segmentation.
-   [x] Airspeed processing.
-   [x] GPS processing.
-   [x] Barometer processing.
-   [x] Sensor-health processing.
-   [x] Rangefinder event processing.
-   [x] Firmware MSG processing.
-   [x] LAND and ARM telemetry support.

------------------------------------------------------------------------

## v0.2 --- FlightWindow Integration ✅

Established flight-scoped analysis.

-   [x] `FlightWindow`.
-   [x] `FlightLog.flights`.
-   [x] `FlightWindowDetector`.
-   [x] Multiple flights per BIN log.
-   [x] Go-arounds remain inside one continuous flight.
-   [x] Flight-scoped sensor health.
-   [x] Flight-scoped LAND processing.
-   [x] Flight-scoped MSG processing.
-   [x] Flight-scoped mode selection.
-   [x] One `AnalysisResult` per selected flight.
-   [x] Parent/child window validation.
-   [x] Multi-flight CLI operation.

The validated flight-window boundaries became part of the regression
baseline and are not to be casually changed by later analysis work.

------------------------------------------------------------------------

## v0.3 --- Analysis Framework ✅

Standardised the internal APIs and ownership model.

-   [x] Standard processor interface.
-   [x] Standard detector interface.
-   [x] Standard analysis interface.
-   [x] Shared scope validation.
-   [x] Shared telemetry filtering.
-   [x] Shared segment filtering.
-   [x] Shared human-readable time formatting.
-   [x] Flight-scoped airspeed processor.
-   [x] Flight-scoped GPS processor.
-   [x] Flight-scoped barometer processor.
-   [x] Flight/landing-scoped rangefinder processing.
-   [x] Event extraction framework.
-   [x] ARM-cycle processing.
-   [x] Reusable `LandingAnalysis.analyse()` entry point.
-   [x] `AnalysisResult` references source scope without owning
    telemetry.

Established contract:

``` text
FlightLog
    +
FlightWindow
    ↓
Processor / Detector / Analysis
    ↓
Scoped Result
```

------------------------------------------------------------------------

## v0.4 --- Landing Detection and Evidence Framework ✅

Established objective AUTO landing-attempt detection.

-   [x] Source validation of ArduPilot landing-controller semantics.
-   [x] `LAND.stage` semantics established from source.
-   [x] `LAND.fh` retained as **flare-timing height**.
-   [x] Approach, preflare and final-flare events represented.
-   [x] Multiple landing attempts within one `FlightWindow`.
-   [x] Aborted landing detection.
-   [x] Restarted landing handling.
-   [x] Go-around support without splitting the parent flight.
-   [x] Independent termination evidence.
-   [x] GPS-stop detector with persistence ownership.
-   [x] Rangefinder retained as independent optional evidence.
-   [x] Parent/child containment validation.
-   [x] Event Timeline exposed through the Analyse workflow.
-   [x] Four-log event/landing regression baseline established.

Landing termination evidence remains independent:

``` text
abort
disarm
mode transition
GPS stop
flight-window end
```

GPS stop means **landing/rollout completion**, not touchdown.

------------------------------------------------------------------------

## v0.5 --- Analysis and Initial Presentation ✅

v0.5 converted the validated evidence framework into useful engineering
analysis.

### Event Timeline

-   [x] Available through `Scripts/analyse.py`.
-   [x] Flight-scoped.
-   [x] Structured event evidence displayed chronologically.

### Battery Analysis

-   [x] Standalone Analyse-menu analysis.
-   [x] Flight-scoped voltage/current evidence.
-   [x] Average current.
-   [x] mAh consumption where available.
-   [x] Wh consumption where available.
-   [x] Highest-current event.
-   [x] Voltage sag.
-   [x] Five-second voltage recovery where measurable.
-   [x] Chemistry-neutral measurement layer.

Battery Analysis remains separate from Landing Analysis.

### Landing Analysis

-   [x] User-facing Analyse-menu workflow.
-   [x] One result per selected flight.
-   [x] Multiple landing attempts represented.
-   [x] Landing-window duration.
-   [x] Approach altitude.
-   [x] Glide slope.
-   [x] Preflare time.
-   [x] Preflare flare-timing height.
-   [x] Preflare airspeed where available.
-   [x] Preflare GPS groundspeed.
-   [x] Preflare sink rate.
-   [x] Final-flare time where available.
-   [x] Final-flare flare-timing height.
-   [x] Final-flare sink rate.
-   [x] Final-flare airspeed where available.
-   [x] Final-flare GPS groundspeed.
-   [x] Logged flare distance to target.
-   [x] Rangefinder acquisition evidence.
-   [x] Rangefinder continuity evidence.
-   [x] GPS-stop landing/rollout completion.
-   [x] Flare-to-stop elapsed time.
-   [x] Final GPS-stop distance from applicable LAND target.
-   [x] Human-readable termination reason.
-   [x] `Unavailable` rather than guessed evidence.

### Architecture Hardening

-   [x] Repository-relative configuration paths.
-   [x] Shared landing configuration ownership.
-   [x] Configuration injection into landing workflow components.
-   [x] Conservative CMD mission-snapshot handling.
-   [x] LAND target accepted only from a complete applicable mission
    snapshot.
-   [x] Unexpected programming/framework exceptions are no longer
    swallowed as ordinary analysis errors.

### Landing Regression

-   [x] Assertion-based `Scripts/test_landing_regression.py`.
-   [x] Established four-log regression set.
-   [x] Aborted-attempt coverage.
-   [x] Multiple-attempt coverage.
-   [x] No-flare coverage.
-   [x] Optional ARSP absence coverage.
-   [x] Optional RFND absence coverage.
-   [x] GPS-stop timing coverage.
-   [x] Target-distance coverage.
-   [x] Incomplete CMD snapshot coverage.
-   [x] Deterministic regression result.

Current result:

``` text
Landing analysis regression: PASS
```

### v0.5 Baseline

``` text
6556780  Harden landing analysis architecture and regressions
ccaf123  Polish landing analysis presentation
```

The landing foundation is now deliberately stable pending user/developer
feedback.

------------------------------------------------------------------------

# Current Development Position

## Community Review / First Public Feedback

The immediate next task is **not to add more landing metrics**.

The current Landing Analysis should first be reviewed by ArduPlane users
and developers.

Review should establish:

-   whether the current measurements are understandable;
-   whether labels are technically precise;
-   whether any displayed evidence is unnecessary;
-   whether important evidence is missing;
-   whether the flare versus landing/rollout-completion distinction is
    clear;
-   whether final distance from target is clearly distinguished from
    touchdown accuracy;
-   whether the rangefinder section is useful;
-   which plots would answer real engineering questions;
-   which additional measurements would be useful in actual diagnosis.

New landing metrics should be driven by a concrete engineering question
rather than telemetry availability alone.

------------------------------------------------------------------------

# v0.6 --- Reporting and Structured Output

## Objective

Turn analysis results into a stable reporting layer without changing the
underlying detector semantics.

The existing console Landing Analysis is the presentation baseline.

v0.6 should separate:

``` text
Analysis
    │
    ▼
Structured Result
    │
    ├── Console presentation
    ├── Machine-readable export
    └── Rich report
```

------------------------------------------------------------------------

## 1. Result Contract

-   [ ] Audit current result objects for reportability.
-   [ ] Define stable field names.
-   [ ] Define units explicitly.
-   [ ] Preserve source/evidence provenance where useful.
-   [ ] Preserve applicable `FlightWindow` / `LandingAttempt`.
-   [ ] Preserve `Unavailable` distinctly from numeric zero.
-   [ ] Preserve termination reason.
-   [ ] Avoid presentation-only strings inside core measurement objects
    where practical.
-   [ ] Define versioning strategy for machine-readable output.

The structured result must not require re-running detector logic.

------------------------------------------------------------------------

## 2. JSON Export

-   [ ] Add JSON export for analysis results.
-   [ ] Include log identity.
-   [ ] Include flight identity and bounds.
-   [ ] Include landing-attempt identity and bounds.
-   [ ] Include measurements and units.
-   [ ] Include unavailable/null measurements explicitly.
-   [ ] Include termination reason.
-   [ ] Include firmware/parameter provenance where available.
-   [ ] Keep output deterministic.
-   [ ] Add regression fixtures for JSON output.

JSON is the first rich-output target because it establishes the result
contract before HTML/PDF presentation.

------------------------------------------------------------------------

## 3. Console Presentation Consolidation

The current Landing Analysis console output is already usable.

v0.6 should consolidate presentation rather than redesign it without
evidence.

-   [ ] Retain current concise landing report as baseline.
-   [ ] Standardise common headings and field formatting across
    analyses.
-   [ ] Standardise `Unavailable`.
-   [ ] Standardise flight/log summaries.
-   [ ] Keep optional sections conditional.
-   [ ] Avoid dumping internal diagnostic fields into normal output.
-   [ ] Consider a separate verbose/diagnostic presentation mode only if
    user feedback demonstrates a need.

------------------------------------------------------------------------

## 4. Rich Engineering Report

After the result schema is stable:

-   [ ] HTML report.
-   [ ] PDF report if useful to users.
-   [ ] One report may contain multiple flights from one log.
-   [ ] Clearly separate measured evidence from observations.
-   [ ] Retain raw log/flight/attempt identity.
-   [ ] Include parameter provenance.
-   [ ] Make missing evidence explicit.

A rich report must not introduce analysis semantics that do not exist in
the structured result.

------------------------------------------------------------------------

## 5. Plotting

Every plot must answer a specific engineering question.

Candidate landing plots are deferred until community feedback identifies
which are useful.

Possible plots include:

-   [ ] approach geometry;
-   [ ] flare detail;
-   [ ] airspeed through the landing attempt;
-   [ ] GPS groundspeed;
-   [ ] sink rate;
-   [ ] rangefinder evidence;
-   [ ] distance to LAND target;
-   [ ] pitch or throttle only where a defined engineering question
    justifies them.

Plotting should consume the same scoped evidence as the numerical
analysis.

------------------------------------------------------------------------

## v0.6 Completion Criteria

v0.6 is complete when:

-   [ ] structured result/export contract is documented;
-   [ ] JSON output is stable and deterministic;
-   [ ] console presentation uses shared formatting conventions;
-   [ ] rich report generation can consume the structured result without
    re-analysis;
-   [ ] report output clearly distinguishes evidence, measurement and
    unavailable data;
-   [ ] report regressions protect the result schema;
-   [ ] existing landing detector and analysis regressions remain green.

------------------------------------------------------------------------

# v0.7 --- Regression and Validation Expansion

## Objective

Extend the existing landing regression work into a broader project-wide
regression framework.

v0.7 is no longer starting regression from zero: v0.4/v0.5 already
established event and landing regression harnesses.

The task is to generalise and expand them.

------------------------------------------------------------------------

## Regression Catalogue

Maintain a documented set of representative logs.

For each regression log record:

-   [ ] firmware version;
-   [ ] parameter source;
-   [ ] number of expected flights;
-   [ ] expected flight boundaries;
-   [ ] expected landing attempts;
-   [ ] expected termination reasons;
-   [ ] expected optional-sensor availability;
-   [ ] known unusual but valid telemetry;
-   [ ] purpose of the log in the regression set.

------------------------------------------------------------------------

## Automated Coverage

Expand coverage to include:

-   [ ] zero-flight log;
-   [ ] single-flight log;
-   [x] multiple-flight log;
-   [ ] flight with no AUTO landing;
-   [x] completed landing;
-   [x] aborted landing;
-   [x] multiple landing attempts;
-   [x] go-around/restarted landing evidence;
-   [x] missing optional sensor evidence;
-   [ ] missing companion parameter file;
-   [ ] malformed/unreadable log;
-   [ ] unsupported firmware;
-   [ ] supported ArduPlane 4.6 case where appropriate;
-   [x] supported ArduPlane 4.7 cases;
-   [x] window containment;
-   [x] deterministic landing-analysis results;
-   [ ] deterministic JSON/report output.

------------------------------------------------------------------------

## Test Layers

Formalise separate regression layers:

``` text
Core parsing
    │
    ▼
Flight detection
    │
    ▼
Event extraction
    │
    ▼
Landing detection
    │
    ▼
Landing analysis
    │
    ▼
Presentation / export
```

A failure should identify the layer that changed rather than merely
showing a different final report.

------------------------------------------------------------------------

## Validation Records

-   [ ] Maintain expected flight-boundary records.
-   [ ] Maintain expected event sequences.
-   [ ] Maintain expected landing-attempt records.
-   [ ] Maintain known firmware differences.
-   [ ] Maintain expected analysis measurements where sufficiently
    stable.
-   [ ] Document deliberate regression-baseline changes.
-   [ ] Require explanation when a validated boundary changes.

------------------------------------------------------------------------

## v0.7 Completion Criteria

-   [ ] Representative regression catalogue exists.
-   [ ] Core layers have assertion-based tests.
-   [ ] Supported firmware cases are explicit.
-   [ ] Expected unsupported cases are explicit.
-   [ ] Deterministic report/export tests exist.
-   [ ] Regression commands are documented.
-   [ ] A developer can identify which architectural layer failed from
    the regression output.

------------------------------------------------------------------------

# v0.8 --- Broader Flight Analyses

## Objective

Use the proven flight-scoped architecture for analyses beyond landing.

Do not add all modules at once. Select the next analysis according to
engineering usefulness and available validation logs.

Candidate analyses:

-   TECS performance;
-   cruise performance;
-   RTL;
-   autotune review;
-   takeoff / launch;
-   airspeed calibration;
-   power-system performance;
-   battery/endurance;
-   wind estimation;
-   navigation accuracy;
-   mission analysis;
-   sensor diagnostics.

------------------------------------------------------------------------

## Analysis Selection Rule

Before starting a new module, define:

1.  the engineering question;
2.  the required telemetry;
3.  the analysis-specific window;
4.  the evidence owner for each measurement;
5.  optional versus required sensors;
6.  representative validation logs;
7.  objective completion criteria.

The new module should then follow:

``` text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
Analysis-specific Window
    │
    ▼
Processors / Detectors
    │
    ▼
Analysis Result
    │
    ▼
Presentation / Report
```

------------------------------------------------------------------------

# Deferred Landing Expansion

The current landing analysis intentionally does **not** attempt to
measure everything available in the log.

Possible future work includes:

## Geometry

-   [ ] full height profile;
-   [ ] distance-to-LAND-target profile;
-   [ ] along-track error;
-   [ ] cross-track error.

## Energy

-   [ ] full airspeed profile;
-   [ ] airspeed tracking;
-   [ ] groundspeed profile;
-   [ ] sink-rate profile;
-   [ ] throttle behaviour;
-   [ ] energy-management observations.

## Aircraft Response

-   [ ] pitch;
-   [ ] roll;
-   [ ] attitude tracking;
-   [ ] control response where objectively measurable.

## Flare

-   [ ] flare-duration model;
-   [ ] detailed preflare-to-final transition analysis.

## Touchdown

-   [ ] exact touchdown detection where defensible;
-   [ ] touchdown speed;
-   [ ] touchdown sink rate;
-   [ ] touchdown location;
-   [ ] touchdown-to-stop rollout measurements.

## Sensor Validation

-   [ ] GPS quality;
-   [ ] barometer quality;
-   [ ] gyro/attitude quality;
-   [ ] airspeed quality integration;
-   [ ] rangefinder quality;
-   [ ] measurement validity/confidence model.

These remain deferred until they answer a demonstrated engineering need.

------------------------------------------------------------------------

# Deferred Architecture Work

## Per-Flight Parameter Reconstruction

The current framework uses a companion `.params` file as a log-level
parameter snapshot.

Future tuning logs may change parameters between flights in one BIN log.

A future milestone should:

-   [ ] read in-log `PARM` changes;
-   [ ] reconstruct active parameter state for each `FlightWindow`;
-   [ ] expose parameter provenance;
-   [ ] preserve the companion `.params` file as an external snapshot;
-   [ ] prevent analysis from silently assuming one parameter state
    where the log proves otherwise.

This should be implemented when parameter-dependent comparative analysis
requires it.

------------------------------------------------------------------------

## Event-Layer Cleanup

Potential cleanup remains:

-   [ ] consolidate duplicated LAND/MSG/MODE interpretation where
    duplication still exists;
-   [ ] review whether identity/pass-through landing layers still
    provide useful architectural separation;
-   [ ] remove stale development-only classes only after confirming they
    are not useful public contracts;
-   [ ] keep detector ownership of validated boundaries intact during
    cleanup.

Cleanup must not be combined with semantic detector changes unless
separately justified and regression-tested.

------------------------------------------------------------------------

# Community and Public Release Strategy

The project should reach users incrementally rather than waiting for
every possible analysis.

## First Public Landing Release

Current v0.5 landing analysis is sufficient for initial review because
it already provides:

-   objective landing-attempt detection;
-   multiple-attempt handling;
-   approach geometry;
-   preflare and flare evidence;
-   optional rangefinder evidence;
-   landing/rollout completion;
-   final position relative to the LAND target;
-   explicit unavailable evidence;
-   regression coverage.

Initial public feedback should focus on usefulness and clarity.

## User Logs

Additional user logs are valuable primarily for:

-   validating assumptions across different aircraft;
-   finding firmware/logging variations;
-   finding missing-data cases;
-   finding unusual landing sequences;
-   expanding regression coverage.

User logs should not be used merely to tune detector thresholds until
the underlying event semantics are understood.

------------------------------------------------------------------------

# Project-Wide Definition of Done

A feature is not complete merely because it prints a plausible number.

For a new detector, processor, metric or analysis to be considered
complete:

-   [ ] its engineering purpose is defined;
-   [ ] its scope is explicit;
-   [ ] source telemetry is identified;
-   [ ] required and optional evidence are distinguished;
-   [ ] ambiguous evidence is handled explicitly;
-   [ ] units are defined;
-   [ ] output terminology is technically defensible;
-   [ ] representative logs have been checked;
-   [ ] regression coverage exists where practical;
-   [ ] existing validated boundaries remain unchanged unless
    deliberately revised;
-   [ ] documentation reflects the implementation;
-   [ ] presentation does not imply more certainty than the evidence
    supports.

------------------------------------------------------------------------

# Current Architecture Status

-   [x] `FlightLog` owns decoded telemetry.
-   [x] `FlightLog` owns parameters.
-   [x] `FlightLog` owns mode segments.
-   [x] `FlightWindow` defines individual flight scope.
-   [x] Multiple flights per log are supported.
-   [x] Go-arounds remain within continuous flights.
-   [x] Analysis executes independently per `FlightWindow`.
-   [x] Shared processor/detector scope conventions exist.
-   [x] Shared telemetry filtering exists.
-   [x] Shared segment filtering exists.
-   [x] Shared window-containment validation exists.
-   [x] Shared human-readable time formatting exists.
-   [x] Real landing attempts are detected.
-   [x] Multiple landing attempts are supported.
-   [x] Landing termination reasons are retained.
-   [x] GPS-stop persistence has a clear detector owner.
-   [x] Rangefinder remains optional.
-   [x] Airspeed remains optional where appropriate.
-   [x] Landing metrics are implemented.
-   [x] Landing console presentation is implemented.
-   [x] Battery Analysis is implemented separately.
-   [x] Event Timeline is implemented.
-   [x] Landing assertion regression exists.
-   [x] Configuration paths are repository-relative.
-   [x] Landing workflow has shared configuration ownership.
-   [x] LAND mission-target provenance is conservatively validated.
-   [ ] Stable machine-readable result schema.
-   [ ] JSON export.
-   [ ] Rich reports.
-   [ ] Project-wide regression catalogue.
-   [ ] Broader flight analyses.

------------------------------------------------------------------------

# Current Development Target

## Community review → v0.6 Reporting

The project has reached a useful transition point.

The landing detector and initial analysis are no longer the immediate
development target.

Current sequence:

``` text
v0.1  Core Framework                     COMPLETE
  │
v0.2  FlightWindow Integration           COMPLETE
  │
v0.3  Analysis Framework                 COMPLETE
  │
v0.4  Landing Detection                  COMPLETE
  │
v0.5  Analysis + Initial Presentation    COMPLETE
  │
  ▼
Community Review                         CURRENT
  │
  ▼
v0.6  Reporting + Structured Output
  │
  ▼
v0.7  Regression + Validation Expansion
  │
  ▼
v0.8  Broader Flight Analyses
```

The immediate objective is to preserve the `ccaf123` landing baseline,
collect feedback, and use that feedback to define the first stable
reporting contract.

Do not expand landing analysis simply to fill out the old metric list.

The next implementation milestone should begin with the **result/report
contract**, not another detector.
