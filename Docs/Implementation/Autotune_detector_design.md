# APT ArduPlane AUTOTUNE Detector Design

> **Status:** Implementation contract  
> **Target:** ArduPlane 4.7.x DataFlash BIN logs  
> **Repository:** ArduPilotTools (APT)  
> **Updated:** 2026-09-26  
> **Implementation branch:** `autotune-analysis`

---

## 1. Purpose

This document defines the implementation contract for fixed-wing ArduPlane AUTOTUNE analysis in APT.

The analyser must answer factual questions supported by firmware and log evidence:

- Was AUTOTUNE entered?
- How many AUTOTUNE sessions occurred?
- Which axes were selected?
- Which axes actually showed tuning activity?
- How long did each session last?
- How much demanded-motion activity was observed?
- Which gain-limit events occurred?
- Which per-axis completion milestones occurred?
- Were completion milestones repeated?
- What runtime gains were observed?
- Was a firmware save requested?
- Were time-local parameter-save records observed?
- Was a restore path inferred?
- Did runtime gains carry into a later session?
- Did the session stop normally, restart, or run to the end of available log evidence?
- Is any required evidence unavailable or contradictory?

The analyser must not manufacture an overall tune-quality score or generic success/failure verdict.

---

## 2. Design principles

The implementation must preserve five distinct evidence classes:

1. firmware state and explicit firmware events;
2. parameter/configuration state;
3. measured runtime response;
4. derived metrics;
5. interpretation and warnings.

These classes must not be collapsed into one another.

Examples:

- `Roll: Finished` is a firmware milestone.
- `RLL_RATE_P = ...` in a time-local raw `PARM` record is parameter-save evidence.
- ATRP gain values are observed runtime values.
- demand-period count is a derived metric.
- `Restore path inferred` is an interpretation from a defined evidence set.

Unavailable evidence must remain unavailable.

Historical interpretation must use timestamp-aware parameter state rather than silently applying the final or current configuration to earlier sessions.

---

## 3. Initial scope

Initial implementation scope:

- ArduPlane 4.7.x;
- fixed-wing AUTOTUNE;
- DataFlash BIN logs;
- multiple AUTOTUNE sessions per log;
- roll, pitch and yaw;
- firmware lifecycle events;
- ATRP activity;
- gain-limit events;
- per-axis completion events;
- timestamp-aware parameters;
- conservative persistence/save evidence;
- flight association;
- command-line presentation.

Deferred:

- PIDR/PIDP/PIDY response-quality analysis;
- demanded-vs-observed dynamic-response scoring;
- oscillation grading;
- gain recommendations;
- automatic parameter recommendations;
- parameter writes;
- Copter AUTOTUNE;
- generic aircraft stability scoring;
- global AUTOTUNE pass/fail scoring.

---

## 4. Repository baseline

The AUTOTUNE implementation is based on the consolidated APT `main` after integration of the existing TAKEOFF prototype.

Relevant existing infrastructure includes:

```text
Scripts/core/log_reader.py
Scripts/core/flight_data.py
Scripts/core/params.py
Scripts/core/flight_window.py
Scripts/core/flight_window_detector.py

Scripts/core/takeoff_execution.py
Scripts/core/takeoff_execution_detector.py
Scripts/core/takeoff_performance.py

Scripts/analyses/log_selector.py
Scripts/analyses/takeoff.py
Scripts/analyse.py