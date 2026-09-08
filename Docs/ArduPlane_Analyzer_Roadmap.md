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

# Current Project Role — 2026-09-07

ArduPilotTools (APT) is now retained as the **Plane log-analysis research,
development and validation environment**.

APT is not being retired after the AMC landing migration. Its purpose is to
provide a controlled place to:

- prototype new Plane-analysis ideas;
- inspect raw log evidence and ArduPilot semantics;
- define detector and evidence contracts;
- exercise synthetic edge cases;
- validate behaviour against representative real logs;
- build repeatable regression evidence before proposing upstream work.

The preferred development path is now:

``` text
Engineering question / observed anomaly
    │
    ▼
APT research and prototype
    │
    ▼
Real-log validation + explicit evidence semantics
    │
    ▼
Maintainer discussion where relevant
    │
    ▼
AMC-native implementation only if accepted/useful
```

APT behaviour is therefore **not automatically an AMC implementation plan**.
New APT work may remain APT-only when it is experimental, diagnostic, or not
yet justified for AMC.

The existing APT landing implementation remains a validated behavioural
reference, but AMC architecture and maintainer direction take precedence when
a feature is promoted upstream.

## Current AMC Status

The legacy APT landing-analysis migration to ArduPilot Methodic Configurator
(AMC) is complete from the APT side.

The Plane landing-analysis pull request remains open. The review response is
pushed and functional CI is green; code-owner review is pending:

``` text
ArduPilot/MethodicConfigurator PR #2024
```

The migration preserves the validated landing evidence semantics while using
AMC-native flight scoping, log-analysis models and flat `LogAnalysisResult`
presentation.

No further legacy APT-to-AMC landing migration work should be started unless
review identifies a specific gap.

After merge, representative AMC screenshots should be captured for the
maintainer's public announcement.

## Evidence Semantics Learned from AMC Review

The Plane landing review established durable principles for future log-analysis
research:

1. **DataFlash is an observation, not a complete execution trace.** Firmware
   may progress through multiple internal LAND states between log writes, so
   stage 1 may be absent. Detectors must use observable semantics validated
   against firmware behavior and real logs rather than assuming every internal
   transition is logged.
2. **Observation and firmware usability are different.** A current sensor
   observation can be useful evidence even when firmware rejects it for a
   particular control function. For example, RFND `Stat 3 OutOfRangeHigh`
   with `Dist 9.24 m` is current observation, but not usable as Plane
   landing-height evidence; it must not be relabeled unavailable.
3. **Preserve sensor status and provenance.** When interpretation depends on
   source selection or status, retain it. This includes RFND orientation and
   instance, RFND `Stat`, and ARSP primary/health state; instance 0 must not be
   assumed merely for convenience.
4. **Flight-control use is not measurement validity.** ARSP `U` indicates
   flight-control use, not general measurement validity. Observational evidence
   may still use a finite, healthy primary measurement when `U == 0`.
5. **Unavailable must mean unavailable.** Unavailable must mean unavailable. Treat evidence as unavailable only when it cannot itself be established conservatively.. Where defensible, keep the raw
   observation, explicit status/provenance, and derived usability or validity
   separate.
6. **Prefer direct evidence labels.** Use explicit firmware terms such as
   `OutOfRangeHigh (3)` instead of prematurely collapsing them into vague or
   evaluative labels such as “in range” or “invalid,” unless the derived
   interpretation is explicitly defined and justified.
7. **Reusable review question:** for every derived validity rule, ask whether
   rejected data is actually unavailable, or merely unusable for that
   particular derivation. This applies to future APT research beyond landing
   and RFND.

## Timestamped Parameter Evidence

APT now has embedded-BIN timestamped parameter history.

Completed commits:

``` text
e13fc73  feat(params): add timestamped parameter history
7bb0d26  refactor(rangefinder): use event-time parameter history
0b660ec  refactor(flight): use event-time stall speed
```

The public evidence API is:

``` python
flight_log.parameter_history.value_at(parameter_name, time_us)
```

APT uses absolute raw `TimeUS` microseconds.

### Rangefinder

`RangefinderEvents` now evaluates `RNGFND1_MAX` at each candidate RFND sample
using embedded parameter history.

The companion `.params` snapshot is not used as historical fallback for this
consumer.

### Flight detection

`FlightWindowDetector` now evaluates `AIRSPEED_STALL` at each GPS sample.

For a finite positive logged stall speed:

``` text
effective_threshold = max(5.0 m/s, 0.5 × AIRSPEED_STALL)
```

More generally the configured detector floor is used instead of 5.0 m/s.

If event-time stall evidence is missing, non-finite, zero or negative, the
detector uses its configured minimum-speed heuristic directly. It does **not**
invent a 10 m/s stall-speed value.

The four validated logs retain their exact pre-migration flight boundaries.

### Companion `.params`

The companion parameter reader remains in APT.

It must **not** be removed merely because current Landing Analysis is now
byte-identical with and without companion `.params` for:

``` text
log_11
log_17
log_19
log_26
```

That result establishes independence for the currently exercised Landing
Analysis path, not repository-wide redundancy.

Before any deprecation/removal decision:

1. audit every remaining `FlightLog.param()`, `has_param()` and
   `parameters` consumer;
2. classify whether each consumer requires historical parameter evidence,
   current/snapshot configuration, or neither;
3. migrate only where embedded event-time evidence is the correct semantic
   source;
4. validate against real logs and synthetic edge cases;
5. retain companion-only information where it remains materially useful.

### Repository-wide companion-parameter audit

The repository-wide consumer audit is complete.

No current production analysis consumes values from
`FlightLog.parameters`, `FlightLog.param()` or `FlightLog.has_param()`.

Landing Analysis, Event Timeline, Battery Analysis, flight detection and
rangefinder evidence now obtain their required evidence from telemetry or
embedded timestamped `ParameterHistory`.

`ParameterReader` is therefore **probably redundant for normal production
analysis**, but removal is deliberately deferred.

Removal requires a separate deprecation/design decision covering:

- `FlightLog.parameters`;
- `FlightLog.param()`;
- `FlightLog.has_param()`;
- companion parameter metadata;
- remaining diagnostic/test tooling;
- legacy `RNGFND1_MAX_CM` normalisation;
- the possible future value of genuinely external configuration snapshots.

Companion snapshots must not be reintroduced as fallback evidence for an
event-time parameter lookup.

The absence of current production consumers is evidence that the companion
system is not presently required by analysis. It is not, by itself, a reason
to remove the API or external-snapshot capability without a deliberate
cleanup decision.

### `Config/landing.yaml` parameter filters

Keep `Config/landing.yaml` and its existing parameter configuration unchanged.

The YAML has responsibilities beyond companion parameter loading and must not
be treated as obsolete merely because production analysis no longer consumes
the filtered companion snapshot.

Its companion-parameter filter section currently retains parameter families
such as:

    AHRS_*
    ARSPD_*
    EK3_*
    LAND_*
    RNGFND*
    TECS_*

Those filters are now legacy infrastructure associated with
`ParameterReader`, because no current production analysis consumes the
resulting filtered `FlightLog.parameters` dictionary.

Do **not** remove or simplify these filters opportunistically.

Reconsider the companion-parameter filter section only as part of a deliberate
`ParameterReader` deprecation/removal task, with its own architecture review
and regression validation.

In particular, future Battery Analysis / battery-pack history work must not
modify these filters merely to obtain `BATT_*` parameters. If battery
parameter evidence is required, determine the correct evidence source and
time semantics independently.

## Immediate APT Research Priorities

### 1. Rangefinder acquisition / `LAND.fh` anomaly

A previously observed landing anomaly is now a dedicated bug-reproduction
research item:

- on rangefinder acquisition, RFND has sometimes shown a brief drop to about
  5 m;
- at the same time `LAND.fh` has reportedly excursioned to about `-167`.

Treat this as a suspected ArduPilot firmware bug until reproduced and traced.

The next step is **read-only evidence audit and reproduction**, not a generic
sensor-health score.

Required evidence should include synchronized:

- RFND acquisition state and raw distance samples;
- `LAND.fh`;
- LAND stage;
- BARO altitude and other relevant altitude evidence;
- event-time rangefinder parameters;
- exact timestamps and transient duration;
- repeatability across attempts/logs.

Do not infer the cause before source/log evidence establishes it.

### 2. Battery pack identity and longitudinal history

APT Battery Analysis already provides objective per-flight measurements.

Planned research is to add optional physical-pack identity (for example
Pack 1 / Pack 2 / Pack 3) and a separate longitudinal persistence layer.

The analyzer should continue to report measurements such as voltage, current,
consumed capacity, sag and recovery without inventing a battery-health score.

### 3. Remaining companion-parameter consumer audit

Continue auditing remaining uses of the legacy companion parameter API before
deciding whether `ParameterReader` is redundant in APT.

This is a cleanup/evidence task, not a mandate to remove the reader.

## Working Rules for New APT Work

For new analysis or diagnostic work:

- begin with a concrete engineering question;
- inspect current code and log evidence before implementation;
- define units and time semantics explicitly;
- preserve measured versus derived evidence;
- use `Unavailable` rather than guessed values;
- avoid score/health/tuning judgements until validated;
- use real logs plus synthetic edge cases;
- keep production changes narrow;
- do not combine unrelated cleanup with semantic changes;
- do not assume an APT prototype should migrate to AMC.


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
    ├── parameter_history
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

------------------------------------------------------------------------

# Proposed Broader Analysis --- Radio Link Health / RC Failsafe

## Objective

Add a flight-scoped analysis for objectively examining RC-link degradation,
RC failsafe entry/recovery, and the aircraft response to loss of the control
link.

The analysis should preserve the project-wide distinction between RF/link
evidence and ArduPilot's response. It should not infer transmitter-side
behaviour that is not present in the flight log.

Engineering questions include:

-   At what recorded link conditions did packet loss become significant?
-   When did ArduPilot declare RC failsafe?
-   How long did each RC failsafe last?
-   What flight-mode or failsafe response followed?
-   When was RC control recovered?
-   What link evidence was available immediately before loss and after recovery?

## Candidate Evidence

Subject to validation against representative logs:

-   [ ] RC receiver RSSI / RSSI dBm where logged.
-   [ ] Receiver link quality (`RQLY` / LQ) where logged.
-   [ ] RF mode / packet-rate evidence where logged.
-   [ ] RC channel validity and loss.
-   [ ] ArduPilot RC failsafe events/state.
-   [ ] Flight-mode transitions associated with failsafe.
-   [ ] Failsafe entry and recovery timestamps.
-   [ ] Duration of each failsafe interval.
-   [ ] Last valid link measurements before failsafe.
-   [ ] First valid link measurements after recovery.
-   [ ] Transmitter-power evidence only if actually present in the log; do not
    infer Dynamic Power behaviour from receiver metrics.

## Proposed Analysis Pattern

``` text
FlightLog
    │
    ▼
FlightWindow
    │
    ▼
RC Link / Failsafe Window(s)
    │
    ├── Link Evidence Processor
    ├── RC Failsafe Detector
    └── Mode / Response Evidence
             │
             ▼
      RadioLinkAnalysis
             │
             ▼
      Structured Result
```

Failsafe boundaries should be owned by a detector using explicit ArduPilot
evidence rather than an arbitrary RSSI or LQ threshold.

## Candidate Presentation

-   [ ] Minimum recorded RSSI and/or LQ.
-   [ ] Chronological link/failsafe event timeline.
-   [ ] Failsafe duration and recovery.
-   [ ] Mode before, during and after failsafe.
-   [ ] Link-quality/RSSI plot with failsafe and mode-change markers.
-   [ ] Explicit `Unavailable` for RF metrics not present in the BIN log.

The analysis should distinguish:

``` text
RF signal strength          -> available link-margin evidence
Link quality / packet loss  -> successful packet-reception evidence
RC failsafe                 -> ArduPilot failsafe state
Flight-mode response        -> aircraft/autopilot response
```

## Validation

Initial validation should include a deliberate ground-test log in which the
ELRS link is progressively degraded until an actual RC failsafe occurs, with
independent observation of aircraft behaviour where practical.

This module belongs under **v0.8 Broader Flight Analyses** unless earlier logs
or community feedback establish a stronger development priority. It should not
displace the current Community Review -> v0.6 Reporting sequence.


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

## Timestamped Parameter Reconstruction ✅

This work is now complete.

APT reads in-log `PARM` records into `FlightLog.parameter_history` and exposes
event-time lookup in raw absolute `TimeUS` microseconds.

Established semantics include:

- startup baseline reconstruction;
- timestamped post-startup changes;
- exact-timestamp changes effective at that timestamp;
- stable duplicate-timestamp ordering;
- late first occurrence remaining unavailable before first evidence;
- explicit rejection of invalid/non-finite timestamps;
- no interpolation between parameter changes.

Event-time parameter history is already used by:

- `RangefinderEvents` for `RNGFND1_MAX`;
- `FlightWindowDetector` for `AIRSPEED_STALL`.

The companion `.params` reader remains available as a separate untimestamped
snapshot source until a repository-wide consumer audit demonstrates whether
it is still required.

Do not reintroduce a per-`FlightWindow` reconstructed parameter dictionary
unless a concrete consumer requires one. Prefer direct event-time lookup from
the shared log-level history.

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
-   [x] `FlightLog` owns timestamped embedded parameter history.
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

# Historical Development Target

The former `Community review → v0.6 Reporting` sequence below is retained only
as project history.

It is **not** the current instruction for Codex and should not be used to pick
the next task.

Standalone reporting, JSON, HTML/PDF and broad analysis expansion remain
possible future work, but only when a concrete engineering need or the AMC
integration direction justifies them.

The authoritative current direction is the
**Current Project Role — 2026-09-07** section near the top of this roadmap.

------------------------------------------------------------------------

# Direction Update — AMC Collaboration

The project direction changed after discussion with the ArduPilot Methodic
Configurator (AMC) project about collaborating and potentially moving this
work into the AMC repository.

This changes the near-term priority of standalone ArduPilotTools development.

## Immediate Priority

The current v0.5 landing-analysis baseline should remain stable while the
proposed AMC collaboration is explored.

Near-term work should focus on:

- presenting the existing landing analysis to the ArduPilot community;
- collecting feedback on its usefulness, terminology and assumptions;
- exposing the current implementation to logs from other aircraft and users;
- understanding how the analysis framework could fit into AMC;
- identifying which parts of ArduPilotTools should be reused, adapted or
  reorganised for that environment;
- avoiding substantial standalone architecture work that may immediately
  need to be reworked during integration.

The existing Landing Analysis, Event Timeline and Battery Analysis remain
useful working capabilities and provide concrete code and behaviour for
collaboration.

## Sensor Diagnostics Deferred

An audit of the existing Sensor Diagnostics work found useful underlying
sensor-processing infrastructure, but not a nearly complete user-facing
analysis.

In particular:

- airspeed has the most developed validation support;
- GPS and barometer currently provide useful descriptive processing but not
  a complete health-validation model;
- rangefinder processing is primarily landing evidence rather than generic
  sensor-health assessment;
- `SensorHealthWindow` and other sensor primitives exist but are not wired
  into a complete Sensor Diagnostics analysis;
- menu option 6 remains unimplemented.

The audit also identified some bounded cleanup and validation work in the
existing sensor code.

This work is now deliberately deferred. It should not be expanded simply to
complete the standalone Analyse menu before the AMC integration direction is
clear.

Sensor Diagnostics remains a valid future analysis, but its implementation
should be reconsidered in the context of the eventual AMC architecture and
user interface.

## Reporting Milestones Reconsidered

The previously planned sequence:

``` text
Community Review
    ↓
v0.6 Reporting + Structured Output
    ↓
v0.7 Regression + Validation Expansion
    ↓
v0.8 Broader Flight Analyses
```

should no longer be treated as the immediate implementation schedule.

The concepts remain useful, particularly structured results, regression
coverage and evidence-first reporting, but their implementation order may
change as part of AMC collaboration.

In particular, avoid building a substantial standalone HTML/PDF reporting
layer until it is clear how results will be presented and consumed within
AMC.

## Current Working Sequence

``` text
v0.5 Landing Analysis baseline           COMPLETE
    │
    ▼
Public ArduPilot review                  CURRENT
    │
    ├── test against additional user logs
    ├── collect technical feedback
    └── identify incorrect assumptions
    │
    ▼
AMC collaboration / integration design  NEXT
    │
    ├── determine code ownership and repository structure
    ├── identify reusable ArduPilotTools components
    ├── determine AMC presentation requirements
    ├── preserve evidence-first analysis semantics
    └── establish validation / CI expectations
    │
    ▼
Implementation priorities reassessed
```

Until that integration direction is established, new standalone analyses
should be added only where there is a strong immediate engineering need.

## Preservation Rule

The current project remains valuable as a tested reference implementation.

Any migration or integration work should preserve:

- the validated landing-attempt semantics;
- `FlightLog` / `FlightWindow` scoping principles where applicable;
- separation of detectors, processors, analysis and presentation;
- explicit handling of unavailable evidence;
- optional-sensor behaviour;
- the landing regression baseline;
- the distinction between measurement and interpretation.

Integration into a larger project is not a reason to silently change validated
analysis behaviour.

Where AMC architecture requires a different implementation structure, changes
should be made deliberately and checked against the existing regression
behaviour.

## Roadmap Status

The earlier v0.6-v0.8 sections are retained as design history and a catalogue
of useful future work. They are not a commitment to implementation order.

The AMC integration path has now been established and the legacy Plane landing
migration is complete from the APT side. AMC PR #2024 has its review response
pushed and functional CI green; code-owner review is pending.

The current development model is:

> **Keep APT as the Plane research/validation environment; promote only
> validated and accepted functionality into AMC using AMC-native architecture.**

Near-term APT work should therefore be selected by evidence and engineering
need, currently including the rangefinder-acquisition / `LAND.fh` bug
reproduction, battery-pack longitudinal history, and completion of the
remaining companion-parameter consumer audit.


Battery Analysis / Pack History — extend the existing chemistry-neutral per-log analysis with takeoff and sustained-load evidence, optional physical Pack ID, configured voltage-threshold margins, and longitudinal whole-pack history. Cell-level diagnosis, inferred IR, and battery-health scoring are explicitly out of scope. See Docs/Implementation/Battery_Analysis_Design.md.

### Parameter evidence direction

New APT analysis should, where practical, operate directly from the `.bin` log
and use embedded `PARM` records / `ParameterHistory` for logged parameter
evidence.

New analysis should not introduce a dependency on companion `.params` snapshots
when the required evidence is already available in the BIN.

If an analysis genuinely requires parameter evidence that is not available from
the BIN, that requirement should be identified explicitly and its appropriate
source and semantics designed before implementation rather than silently using a
companion snapshot as fallback.

Existing companion `.params` support remains legacy infrastructure. Its eventual
deprecation or continued role is a separate architectural decision.

This APT direction does not imply that external/current parameter sets are
unnecessary in AMC, where Methodic Configurator's configuration workflow may
legitimately provide parameter evidence that is distinct from historical values
recorded in a flight log.
