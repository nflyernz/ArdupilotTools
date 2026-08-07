# v0.4 — Landing Detection Implementation Plan

## Purpose

This document defines the implementation plan for:

**v0.4 — Landing Detection**

The objective is to replace the bounded development `LandingWindow` used through v0.3 with objective detection of real ArduPlane AUTO-landing attempts inside each `FlightWindow`.

A continuous flight may contain:

- no AUTO-landing attempts;
- one AUTO-landing attempt;
- multiple AUTO-landing attempts;
- aborted AUTO-landing approaches;
- go-arounds;
- restarted AUTO-landing sequences;
- a completed AUTO landing.

v0.4 must identify those attempts without splitting the parent `FlightWindow`.

Manual approaches and landings outside the ArduPlane AUTO landing sequence are not `LandingWindow` objects in v0.4.

This is an implementation plan.

Architectural authority remains:

```text
Docs/Architecture.md
```

Milestone scope and status remain:

```text
Docs/Roadmap.md
```

Verified behaviour and landing-event observations remain:

```text
Docs/Validation.md
```

---

# Architectural Baseline

v0.3 completed the FlightWindow-based analysis framework.

The established hierarchy is:

```text
FlightLog
    │
    └── FlightWindow
            │
            ├── SensorHealthWindow
            │
            └── LandingWindow(s)
```

The following rules remain authoritative:

- `FlightLog` owns decoded telemetry.
- `FlightWindow` defines one continuous flight.
- `FlightWindow` does not own telemetry.
- `LandingWindow` is a child scope of a `FlightWindow`.
- every `LandingWindow` must lie completely within its parent `FlightWindow`;
- processors receive explicit parent scope;
- telemetry filtering uses shared scope utilities;
- internal time uses integer `TimeUS`;
- analysis must remain objective and reproducible.

v0.4 must preserve these rules.

---

# v0.4 Objective

Implement:

```text
FlightLog
    +
FlightWindow
        │
        ▼
LandingWindowDetector
        │
        ├── LandingWindow
        ├── LandingWindow
        └── ...
```

The detector must return:

```python
list[LandingWindow]
```

for exactly one selected `FlightWindow`.

The number of returned windows may be:

```text
0       no AUTO-landing attempts
1       one AUTO-landing attempt
many    multiple AUTO-landing attempts
```

A go-around must not create a new `FlightWindow`.

Instead, where supported by validated evidence, it terminates one AUTO-landing attempt and allows a later AUTO-landing attempt to begin within the same parent flight.

---

# Primary v0.4 Principle

## Evidence Before Semantics

Do not begin by assigning assumed meanings to:

```text
LAND.stage = 0
LAND.stage = 1
LAND.stage = 2
LAND.stage = 3
```

Do not assume that a firmware `MSG` string is by itself authoritative.

Do not assume that rangefinder engagement means touchdown.

Do not assume that disarm means touchdown.

Do not assume that Yaapu's audible:

```text
Landing complete
```

corresponds to an ArduPlane `MSG` or MAVLink `STATUSTEXT` containing those words.

v0.4 begins by establishing what the available evidence actually represents.

Detector rules are implemented only after the relevant sequences have been compared across representative AUTO-landing attempts.

---

# Current Evidence

## log_17.bin

`log_17.bin` remains the existing regression and development log.

It contains four validated FlightWindows.

Flight 2 is particularly important because it contains multiple AUTO-landing attempts and go-arounds while remaining one continuous `FlightWindow`.

Observed firmware messages include:

```text
Mission: 1 LandStart
Mission: 2 LoitAltitude
Loiter to alt complete
Mission: 3 Land
Landing approach start at 19.1m
Landing glide slope 4.7 degrees
Flare 5.2m sink=1.76 speed=11.2 dist=25.9
Landing aborted via throttle
Landing aborted, climbing to 30m
Restarted landing via DO_LAND_START: 1
```

A later attempt contains:

```text
Landing approach start at 18.9m
Landing glide slope 4.7 degrees
Flare 6.6m sink=2.21 speed=15.9 dist=60.6
Rangefinder engaged at 5.66m
Landing aborted via throttle
Landing aborted, climbing to 30m
```

A further attempt contains:

```text
Landing approach start at 20.9m
Landing glide slope 5.1 degrees
Flare 6.3m sink=2.11 speed=11.0 dist=27.1
Rangefinder engaged at 5.85m
```

Other flights show different landing geometry.

Examples include:

```text
Landing glide slope 3.8 degrees
Flare 4.5m sink=1.56 speed=12.9 dist=38.9
Rangefinder engaged at 5.47m
```

and:

```text
Landing glide slope 3.8 degrees
Flare 4.4m sink=1.50 speed=10.6 dist=47.3
Rangefinder engaged at 5.47m
```

These are observations only.

They do not yet establish detector semantics.

---

# New Landing Evidence Log

A new landing log is available for v0.4 validation.

It contains:

- multiple AUTO-landing attempts;
- multiple go-arounds;
- completed AUTO-landing behaviour;
- different glide-slope configurations;
- apparently inconsistent flare behaviour.

This log should become a second primary v0.4 evidence source.

The first task is not to explain or tune the flare.

The first task is to extract the AUTO-landing sequences objectively and compare them with the existing evidence from `log_17.bin`.

The matching parameter file should be used when interpreting configuration-dependent behaviour.

---

# Flare Investigation

The new log raises a specific question:

> Why does flare behaviour appear inconsistent between AUTO-landing attempts?

This is an investigation target, not yet a detector rule.

For each AUTO-landing attempt, collect at minimum:

```text
Approach start
Glide-slope declaration
LAND.stage transitions
Airspeed
Groundspeed
Barometric altitude
Vertical speed / sink rate
Pitch
Throttle
Flare MSG
Rangefinder engagement
Abort/restart events
Disarm
Landing-completion evidence
```

Where available, also retain:

```text
distance from LAND point
mission state
mode transitions
GPS position
rangefinder height
```

---

# Glide-Slope Comparison

The available logs contain different declared glide slopes.

This provides useful comparative evidence.

For each AUTO-landing attempt, record:

```text
declared glide slope
approach-start altitude
approach geometry
airspeed approaching flare
sink rate approaching flare
firmware flare-message time
LAND.stage transition time
barometric altitude at flare
rangefinder altitude at flare
rangefinder engagement time
pitch response
throttle response
abort/completion outcome
```

The purpose is to determine whether observed flare differences correlate with:

- glide slope;
- sink rate;
- airspeed;
- approach geometry;
- rangefinder state;
- configured flare parameters;
- another logged state.

Do not alter landing parameters as part of v0.4 detection development.

Parameter tuning is outside this milestone.

---

# Yaapu "Landing Complete" Observation

During a completed AUTO landing in the new evidence log, the TX16S running the Yaapu telemetry widget produced an audible:

```text
Landing complete
```

The same text was not observed in the MAVLink message stream.

This is important evidence.

Do not assume Yaapu received an ArduPlane text message containing:

```text
Landing complete
```

The announcement may instead be generated locally by Yaapu from telemetry state.

Possible underlying evidence may include:

```text
armed/disarmed state
flight mode
landing state
mission state
MAVLink extended state
landed-state telemetry
another ArduPilot telemetry field
a combination of telemetry states
```

This must be investigated before being used by the detector.

---

# Yaapu Investigation

Determine what telemetry condition causes Yaapu to announce:

```text
Landing complete
```

The investigation should answer:

1. Is the phrase received from ArduPilot or generated by Yaapu?
2. If generated locally, what telemetry field or state transition triggers it?
3. Is the underlying state represented in the BIN log?
4. If represented, which DataFlash record corresponds to it?
5. At what time does that state occur relative to:
   - flare;
   - rangefinder engagement;
   - LAND.stage transitions;
   - touchdown evidence;
   - throttle;
   - disarm?
6. Does the same state occur consistently across successful AUTO landings?
7. Does it remain absent during aborted AUTO-landing attempts?

The Yaapu phrase itself is not a detector input.

The underlying ArduPilot state may become a detector input if it is available in the BIN log and validated across representative AUTO landings.

---

# Landing Evidence Model

Before implementing final detection, establish a common chronological evidence representation.

Conceptually:

```text
LandingEvidence
    │
    ├── MSG events
    ├── LAND.stage transitions
    ├── MODE transitions
    ├── ARM transitions
    ├── Rangefinder events
    ├── GPS state
    ├── Airspeed state
    ├── Barometer state
    └── other validated landing-state evidence
```

This does not necessarily require a permanent new model class.

Repository inspection should determine whether the existing `LandingTimeline` and `TimelineEvent` architecture already provides the correct representation.

Avoid introducing a duplicate event model if the existing timeline architecture is sufficient.

---

# AUTO-Landing Attempt Semantics

The detector ultimately needs objective definitions for the following states.

## Attempt Start

Determine what constitutes sufficient evidence that an ArduPlane AUTO-landing attempt has begun.

Potential evidence includes:

```text
Mission: 3 Land
Landing approach start
LAND.stage transition
AUTO mode
mission navigation state
```

The final rule must be validated against multiple AUTO-landing attempts.

Manual approaches and landings outside the ArduPlane AUTO landing sequence are not `LandingWindow` objects in v0.4.

---

## Flare

Determine how flare is represented.

Potential evidence includes:

```text
Flare MSG
LAND.stage transition
pitch response
sink-rate change
rangefinder state
```

The firmware flare message may be strong evidence, but its relationship to the actual control-state transition must be established.

Flare detection is useful for AUTO-landing semantics, but flare metrics themselves belong primarily to v0.5.

---

## Abort / Go-Around

Existing evidence includes explicit messages:

```text
Landing aborted via throttle
Landing aborted, climbing to 30m
```

and:

```text
Restarted landing via DO_LAND_START: 1
```

Determine the corresponding LAND, MODE, mission, throttle, and altitude behaviour.

The detector must terminate an aborted AUTO-landing attempt without terminating the parent `FlightWindow`.

A later AUTO approach within the same flight must be capable of creating another `LandingWindow`.

---

## Restart

Determine what marks the beginning of a new AUTO-landing attempt following an abort.

Do not automatically treat:

```text
Restarted landing via DO_LAND_START
```

as the new `LandingWindow` start until its relationship to the subsequent AUTO approach has been validated.

The actual AUTO-landing attempt may begin later.

---

## Touchdown

Touchdown requires particular care.

Potential evidence includes:

```text
rangefinder height
vertical motion
groundspeed
airspeed
barometric altitude
LAND state
mission state
disarm
landing-complete state
```

No individual source should initially be assumed to provide authoritative touchdown time.

v0.4 may establish a defensible touchdown indicator if the logs support one.

If exact touchdown cannot be determined reliably, the detector should represent that uncertainty rather than manufacture a precise timestamp.

---

## Landing Complete

Determine whether a reliable logged state exists that represents successful completion of an AUTO landing.

The Yaapu observation is specifically relevant here.

Potential completion evidence may include:

```text
landed state
disarm
groundspeed persistence
rangefinder persistence
mission completion
LAND state
```

A completed `LandingWindow` must have a defensible end boundary.

---

# LandingWindow Semantics

By the end of v0.4, `LandingWindow` must represent one detected ArduPlane AUTO-landing attempt.

At minimum it must contain:

```text
start_us
end_us
```

Its boundaries must have explicit documented meanings.

Possible future metadata such as:

```text
outcome
abort reason
touchdown time
flare time
confidence
```

should not be added automatically during the initial detector implementation.

Add fields only if they are required by the validated v0.4 contract.

Avoid turning `LandingWindow` into a general landing-analysis result object.

Detailed landing measurements belong to v0.5.

---

# Detection Confidence

Some evidence may be stronger than other evidence.

The detector should prefer direct logged state over inferred physical behaviour where possible.

Conceptually:

```text
explicit firmware state
        ↓
validated state transition
        ↓
correlated physical telemetry
        ↓
heuristic inference
```

However, explicit firmware text must still be validated before being treated as semantic truth.

If multiple evidence sources disagree, retain the disagreement during investigation rather than forcing an early rule.

---

# Explicitly Deferred

The following remain outside v0.4 unless directly required to establish AUTO-landing boundaries:

- manual landing detection;
- landing-quality scoring;
- tuning recommendations;
- parameter recommendations;
- flare-quality scoring;
- ideal flare-height calculation;
- ideal glide-slope calculation;
- landing performance grading;
- detailed landing metrics;
- plots intended for end users;
- HTML reporting;
- PDF reporting;
- JSON reporting;
- public-release packaging.

These belong to v0.5 or later where applicable.

v0.4 may create diagnostic harness output and temporary engineering plots where required to understand AUTO-landing event behaviour.

---

# Regression Requirements

v0.4 must preserve all completed v0.3 architecture and regression behaviour.

In particular:

- `FlightLog` remains telemetry owner;
- `AnalysisResult` does not own telemetry;
- existing four `log_17.bin` FlightWindows remain unchanged;
- Flight 2 remains one continuous `FlightWindow`;
- sensor-health results remain unchanged;
- processor APIs remain unchanged unless a concrete v0.4 requirement demands modification;
- existing event scoping remains intact;
- framework errors remain isolated per flight.

Flight detection must not be modified merely to simplify AUTO-landing detection.

---

# Commit 1 — Landing Evidence Harness

## Purpose

Build a diagnostic harness that presents all potentially relevant AUTO-landing evidence chronologically for one selected `FlightWindow`.

This commit does **not** implement real `LandingWindow` detection.

## Likely Files

New:

```text
Scripts/test_landing_evidence.py
```

Modify only if required:

```text
Scripts/core/timeline.py
Scripts/core/event_extractor.py
```

Do not change detector semantics.

## Output

For a selected `FlightWindow`, display chronological evidence including:

```text
MSG
LAND.stage
MODE
ARM
rangefinder events
```

and timestamps needed to correlate continuous telemetry.

Where useful, include sampled values for:

```text
airspeed
groundspeed
barometric altitude
sink rate
pitch
throttle
rangefinder
```

The output should be concise enough to compare multiple AUTO-landing attempts.

## Validation

Run against:

```text
log_17.bin
```

especially Flight 2.

Then run against the new landing evidence log.

Record significant sequences in:

```text
Docs/Validation.md
```

## Difficulty

Medium

---

# Commit 2 — Catalogue AUTO-Landing Attempt Sequences

## Purpose

Use the evidence harness to establish observed AUTO-landing state sequences before writing detector rules.

This is primarily validation work.

## Required Cases

Catalogue at minimum:

- successful AUTO landing;
- aborted AUTO landing;
- go-around;
- restarted AUTO landing;
- multiple AUTO-landing attempts within one `FlightWindow`;
- different glide slopes;
- different apparent flare behaviour;
- a flight containing no AUTO-landing attempts, where a representative case is available.

Use both:

```text
log_17.bin
```

and the new landing log.

## Record

For each AUTO-landing attempt record:

```text
FlightWindow
approach-start evidence
LAND.stage sequence
firmware MSG sequence
glide slope
flare evidence
rangefinder engagement
abort evidence
restart evidence
completion evidence
```

Record uncertainty explicitly.

For a flight with no AUTO-landing attempt, confirm that candidate landing evidence does not cause a false positive.

## Documentation

Update:

```text
Docs/Validation.md
```

No detector rule should be committed merely because it works on one attempt.

## Difficulty

Medium

---

# Commit 3 — Investigate Landing Completion State

## Purpose

Determine the source of the Yaapu:

```text
Landing complete
```

announcement and identify whether the underlying state can be recovered from the BIN log.

## Investigation

Inspect Yaapu behaviour and relevant ArduPilot telemetry definitions.

Determine whether the announcement is:

```text
received text
```

or:

```text
locally generated telemetry interpretation
```

If locally generated, identify the triggering telemetry state.

Then determine whether the corresponding state is logged in DataFlash.

## Outcome

Document one of:

```text
A. Reliable logged landing-complete state identified.
B. State exists in MAVLink but is not represented in the BIN log.
C. Yaapu derives completion heuristically.
D. Source remains unresolved.
```

Only case A should directly influence BIN-log AUTO-landing detection without additional inference.

## Documentation

Update:

```text
Docs/Validation.md
```

## Difficulty

Medium

---

# Commit 4 — Define LandingWindow Boundary Rules

## Purpose

Convert validated evidence into explicit AUTO-landing detector semantics.

Before implementation, document:

```text
LandingWindow start =
    ...

LandingWindow end on abort =
    ...

LandingWindow end on successful AUTO landing =
    ...

New AUTO-landing attempt after go-around =
    ...
```

Also document how the detector behaves when evidence is incomplete.

Examples:

```text
no AUTO-landing evidence
    → []

AUTO approach + abort
    → one LandingWindow

AUTO approach + abort + new AUTO approach + completion
    → two LandingWindows
```

The rules must work with both primary evidence logs.

A flight that contains manual flying or a manual landing but no ArduPlane AUTO-landing sequence must return:

```text
[]
```

## Documentation

Update:

```text
Docs/Validation.md
Docs/implementation/v0.4-plan.md
```

with the validated semantics before detector implementation.

## Difficulty

Large

---

# Commit 5 — Real LandingWindowDetector

## Purpose

Replace the v0.3 bounded development implementation with real AUTO-landing-attempt detection.

## Files

Modify:

```text
Scripts/core/landing_window_detector.py
Scripts/core/landing_window.py
```

Modify other core files only where required by the validated design.

## Contract

Retain:

```python
detect(
    flight_log,
    flight_window,
) -> list[LandingWindow]
```

## Requirements

The detector must:

1. validate the parent `FlightWindow`;
2. inspect only evidence within that `FlightWindow`;
3. detect zero or more AUTO-landing attempts;
4. produce one `LandingWindow` per detected AUTO-landing attempt;
5. keep every `LandingWindow` inside its parent `FlightWindow`;
6. separate AUTO-landing attempts across go-arounds;
7. avoid splitting the parent `FlightWindow`;
8. return no `LandingWindow` for flights containing no AUTO-landing attempt;
9. behave deterministically;
10. avoid relying on unvalidated `LAND.stage` semantics;
11. avoid silently manufacturing boundaries when evidence is insufficient;
12. not classify manual landings as AUTO-landing attempts.

## Difficulty

Large

---

# Commit 6 — Landing Analysis Integration

## Purpose

Integrate real `LandingWindow` detection into the reusable landing-analysis API.

## Files

Modify:

```text
Scripts/analyses/landing.py
Scripts/analyses/result.py
Scripts/test_landing_analysis.py
Scripts/analyse.py
```

## Behaviour

`LandingAnalysis.analyse()` must now return:

```text
AnalysisResult
    ├── FlightWindow
    ├── SensorHealthWindow
    ├── sensor health
    └── LandingWindow(s)
```

where `LandingWindow` objects represent actual detected AUTO-landing attempts rather than the v0.3 development placeholder.

A `FlightWindow` may legitimately contain:

```text
LandingWindows : 0     # no AUTO-landing attempts
LandingWindows : 1     # one AUTO-landing attempt
LandingWindows : many  # multiple AUTO-landing attempts
```

The CLI should display detected AUTO-landing attempts clearly without yet performing v0.5 landing-quality analysis.

## Difficulty

Medium

---

# Commit 7 — v0.4 Regression Validation

## Purpose

Validate the real detector against all established evidence and ensure no v0.3 regression.

## Run

```text
python -m compileall -q Scripts

python Scripts/test_reader.py
python Scripts/test_landwindow.py
python Scripts/test_landstages.py
python Scripts/test_msg.py
python Scripts/test_armcycle.py
python Scripts/test_rangefinder.py
python Scripts/test_timeline.py
python Scripts/test_airspeed.py
python Scripts/test_gps.py
python Scripts/test_barometer.py
python Scripts/test_landing_analysis.py
```

Run the new evidence harness against both primary landing logs.

Then run:

```text
python Scripts/analyse.py
```

against both logs.

## Confirm

For `log_17.bin`:

- exactly four `FlightWindow` objects remain;
- all four `FlightWindow` boundaries remain unchanged;
- Flight 2 remains one continuous `FlightWindow`;
- Flight 2 produces multiple `LandingWindow` objects corresponding to validated AUTO-landing attempts;
- other flights produce the expected detected AUTO-landing attempts;
- sensor-health results remain unchanged;
- framework errors remain zero.

For the new landing log:

- `FlightWindow` boundaries are sensible and independently validated;
- multiple go-arounds do not split the continuous flight incorrectly;
- AUTO-landing attempts agree with the manually validated event sequences;
- different glide slopes do not break detection;
- different flare behaviour does not incorrectly determine attempt boundaries;
- successful AUTO-landing completion is bounded using validated evidence.

For a representative flight with no AUTO-landing attempt:

- the parent `FlightWindow` is still detected normally;
- `LandingWindowDetector` returns `[]`;
- manual flying does not generate false AUTO-landing attempts;
- manual landing behaviour does not generate a false AUTO-landing attempt.

## Difficulty

Medium

---

# Recommended Commit Order

```text
1. Landing evidence harness
2. Catalogue AUTO-landing attempt sequences
3. Investigate Yaapu / landing-completion state
4. Define validated LandingWindow boundary rules
5. Implement real LandingWindowDetector
6. Integrate real LandingWindows into LandingAnalysis
7. Full v0.4 regression validation
```

The important sequencing rule is:

> **Do not implement Commit 5 until Commits 1–4 have established defensible AUTO-landing boundary semantics.**

---

# Expected Development Workflow

v0.4 intentionally contains an evidence phase before its implementation phase.

The expected workflow is:

```text
New landing log
        +
log_17.bin
        │
        ▼
Extract AUTO-landing evidence
        │
        ▼
Compare attempts
        │
        ▼
Understand flare / abort / restart / completion states
        │
        ▼
Document validated semantics
        │
        ▼
Implement LandingWindowDetector
        │
        ▼
Regression test
```

This is preferable to implementing a detector from assumptions and then changing its semantics repeatedly as new logs expose exceptions.

---

# v0.4 Completion Criteria

v0.4 is complete when all of the following are true:

- [ ] AUTO-landing event sequences have been catalogued across at least the existing and new evidence logs.
- [ ] Successful AUTO-landing behaviour has been validated.
- [ ] Aborted AUTO-landing behaviour has been validated.
- [ ] Restarted AUTO-landing behaviour has been validated.
- [ ] Multiple AUTO-landing attempts within one `FlightWindow` have been validated.
- [ ] A no-AUTO-landing case has been validated against false-positive detection.
- [ ] Different glide-slope cases have been compared.
- [ ] Flare-related evidence has been compared across representative AUTO-landing attempts.
- [ ] The Yaapu `Landing complete` observation has been investigated.
- [ ] The source of usable AUTO-landing-completion evidence is documented.
- [ ] `LandingWindow` start semantics are documented.
- [ ] `LandingWindow` abort-end semantics are documented.
- [ ] `LandingWindow` successful-end semantics are documented.
- [ ] Go-around/restart semantics are documented.
- [ ] `LandingWindowDetector` returns zero or more detected AUTO-landing attempts.
- [ ] Flights containing no AUTO-landing attempt return zero `LandingWindow` objects.
- [ ] Manual landings are not classified as AUTO-landing attempts.
- [ ] Every `LandingWindow` is contained within its parent `FlightWindow`.
- [ ] Multiple AUTO-landing attempts do not split the parent `FlightWindow`.
- [ ] Flight 2 of `log_17.bin` produces the expected multiple AUTO-landing attempts.
- [ ] The new landing log produces the expected multiple AUTO-landing attempts.
- [ ] `LandingAnalysis` uses the real detected `LandingWindow` objects.
- [ ] Existing `FlightWindow` regression boundaries remain unchanged.
- [ ] Existing sensor-health behaviour remains unchanged.
- [ ] Main CLI completes with zero framework errors on the regression logs.
- [ ] No manual-landing detector has been introduced.
- [ ] No landing-quality scoring or tuning recommendations have been introduced.

---

# v0.4 Status

**v0.4 — Landing Detection: PLANNED**

The first task is:

**Commit 1 — Landing Evidence Harness**

The detector itself must not be implemented until the available AUTO-landing evidence, including the new multiple-go-around log, different glide slopes, apparently inconsistent flare behaviour, and the Yaapu landing-completion observation, has been examined and documented.