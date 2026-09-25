# APT ArduPlane Autotune Analysis

## Firmware Semantics and Evidence Contract

**Status:** Frozen firmware-semantics reference for initial implementation
**Scope:** ArduPlane 4.7.x fixed-wing AUTOTUNE
**Repository:** `~/ArduPilotTools`

Related design document:

```text
Implementation/Autotune_detector_design.md
```

---

# 1. Purpose

This document defines the ArduPlane fixed-wing AUTOTUNE firmware semantics that APT may rely on when analysing DataFlash BIN logs.

It separates:

1. explicit firmware events;
2. selected tuning configuration;
3. actual tuner activity;
4. per-axis completion milestones;
5. runtime gain changes;
6. firmware save requests;
7. observed parameter-save processing;
8. restore behaviour;
9. measured aircraft response;
10. derived APT interpretation.

The purpose is to prevent APT from claiming more than the firmware and log evidence support.

Unavailable evidence must remain unavailable.

---

# 2. Supported Firmware Scope

Initial implementation scope:

```text
ArduPlane 4.7.x
```

The primary released-firmware audit covered:

```text
Plane-4.7.0
Plane-4.7.1
```

No relevant fixed-wing AUTOTUNE semantic difference was found between those releases.

Primary source areas include:

```text
ArduPlane/control_modes.cpp
ArduPlane/mode_autotune.cpp
ArduPlane/mode.cpp
ArduPlane/Parameters.cpp
ArduPlane/Log.cpp

libraries/APM_Control/AP_AutoTune.cpp
libraries/APM_Control/AP_AutoTune.h
libraries/APM_Control/AP_FW_Controller.cpp
libraries/APM_Control/AP_YawController.cpp
```

Beta firmware must be checked at its producing commit before stable-release semantics are applied.

---

# 3. Real-Log Validation Basis

The firmware contract has been checked against two real logs.

## 3.1 `log_17.bin`

Firmware:

```text
ArduPlane 4.7.0-beta7
97775f82
```

This log provides:

* multiple AUTOTUNE sessions;
* roll and pitch completion;
* later partial roll tuning;
* selected but inactive yaw;
* runtime gain continuity between sessions;
* incomplete-axis restore behaviour;
* time-local parameter-save records.

Relevant AUTOTUNE behaviour was checked at commit `97775f82`.

## 3.2 `log_0.bin`

Firmware:

```text
ArduPlane V4.7.0
1511f271
```

This provides released-4.7.0 validation including:

* roll and pitch tuner activity;
* selected but inactive yaw;
* repeated gain-limit events;
* pitch completion;
* two roll `Finished` milestones in one session;
* gain revision after a prior `Finished`;
* time-local `PARM` records following save operations.

---

# 4. AUTOTUNE Activation Paths

Fixed-wing AUTOTUNE can be activated through multiple firmware paths.

## 4.1 AUTOTUNE flight mode

Entering AUTOTUNE mode invokes the fixed-wing AUTOTUNE start path.

AUTOTUNE mode otherwise provides FBWA-like attitude-demand behaviour.

## 4.2 RC auxiliary option

Plane RC option:

```text
FW_AUTOTUNE = 107
```

can enable and disable AUTOTUNE in supported modes.

Supported modes include firmware contexts such as:

```text
AUTO
AUTOTUNE
LOITER
FBWA
FBWB
```

subject to the 4.7.x implementation.

## 4.3 MAVLink or mission command

Fixed-wing AUTOTUNE can also be controlled using:

```text
MAV_CMD_DO_AUTOTUNE_ENABLE
```

through direct MAVLink or mission execution.

---

# 5. MODE Is Not the Universal Session Detector

Because fixed-wing AUTOTUNE may run outside AUTOTUNE flight mode:

```text
MODE == AUTOTUNE
```

is neither necessary nor sufficient as the universal tuning-session detector.

MODE is contextual evidence.

The authoritative session events are the firmware AUTOTUNE start and stop messages.

---

# 6. Global AUTOTUNE Start

`Plane::autotune_start()` performs the global start operation.

Important behaviour includes:

* sampling the configured AUTOTUNE axis mask;
* starting the selected axis tuners;
* setting the Plane AUTOTUNE-running state;
* emitting:

```text
Started autotune
```

* emitting a selected-axis message such as:

```text
Autotuning roll pitch yaw
```

---

# 7. Per-Axis Start Behaviour

Each selected `AP_AutoTune` instance begins a fresh session-local tuner state.

Important state reset includes:

* runtime tuner state;
* P limit;
* D limit;
* FF sampling state;
* event counters;
* completion counter;
* restore snapshot;
* last-save snapshot;
* filters and related transient state.

A new AUTOTUNE start therefore creates a new logical tuner session even when it begins from gain values retained from an earlier session.

---

# 8. Start-Time Parameter Adjustments

Per-axis start can make immediate runtime adjustments required by the tuner.

Examples include:

* adjusting RMAX or time constant according to AUTOTUNE level;
* constraining IMAX;
* ensuring minimum usable FF;
* initializing or setting `RATE_SMAX` where required.

Some start-time parameter operations may themselves use persistent parameter-save paths.

These must not be confused with the later P/D tuning-completion save semantics.

---

# 9. Repeated Start While Already Running

The fixed-wing start path does not provide a universal guard that makes a second start impossible.

Therefore a new:

```text
Started autotune
```

can occur while a logical AUTOTUNE session is already active.

A new start resets important per-axis tuner state.

### Evidence consequence

APT must treat a later `Started autotune` as a new logical session boundary.

The previous logical interval ends as:

```text
RESTARTED
```

This is an analyser termination category describing the observed repeated start.

It is not a firmware text message.

---

# 10. Global AUTOTUNE Stop

The fixed-wing stop path invokes each axis tuner's stop behaviour.

When the Plane global AUTOTUNE state is active, firmware emits:

```text
Stopped autotune
```

This is the authoritative normal session-stop event.

---

# 11. Normal Stop Paths

Important stop paths include:

* leaving AUTOTUNE flight mode for a mode which does not retain tuning;
* RC AUTOTUNE disable;
* MAVLink AUTOTUNE disable;
* mission AUTOTUNE disable;
* failsafe behaviour which causes a mode transition through the stop path.

The exact activation context is separate from the meaning of the stop event.

---

# 12. Disarm Is Not an AUTOTUNE Stop

Disarm by itself is not a dedicated fixed-wing AUTOTUNE stop operation.

Therefore:

```text
DISARM
```

must not be treated as an authoritative AUTOTUNE session boundary.

If disarm causes another firmware action which actually invokes AUTOTUNE stop, the resulting stop event remains authoritative.

---

# 13. GPS Motion Is Not an AUTOTUNE Stop

Loss of flight-like GPS groundspeed is not a firmware AUTOTUNE stop condition.

Therefore an APT:

```text
FlightWindow
```

boundary is analysis context only.

It must not redefine the firmware AUTOTUNE session lifetime.

---

# 14. Log End Is Not Normal Firmware Stop

If the log ends while AUTOTUNE is still logically open:

* normal stop was not observed;
* normal save/restore stop semantics cannot automatically be assumed;
* log end is censoring of evidence, not proof of firmware completion.

---

# 15. Axis Selection

`AUTOTUNE_AXES` is a bitmask.

For the relevant 4.7.x implementation:

```text
Roll  = 1
Pitch = 2
Yaw   = 4
```

The configured mask is sampled at AUTOTUNE start.

---

# 16. Explicit Selected-Axis Message

Firmware reports selected axes with text such as:

```text
Autotuning roll pitch yaw
```

This is the strongest session-specific evidence of what the start path selected.

It means:

> this axis was selected by the AUTOTUNE start configuration.

It does not mean:

> the corresponding per-axis tuner subsequently produced activity.

---

# 17. Selected and Active Are Different

Both real validation logs demonstrate:

```text
AUTOTUNE_AXES = 7
```

and:

```text
Autotuning roll pitch yaw
```

while yaw produces no ATRP activity.

In those logs:

```text
YAW_RATE_ENABLE = 0
```

Therefore APT must distinguish:

```text
Selected axis
```

from:

```text
Observed active tuner axis
```

---

# 18. Yaw Availability

Yaw tuner allocation/activity depends on yaw-rate-controller configuration in addition to `AUTOTUNE_AXES`.

Therefore:

```text
yaw selected
```

does not itself prove:

```text
yaw tuner executed
```

ATRP or equivalent runtime activity evidence is required.

---

# 19. Independent Axis Tuners

Roll, pitch, and yaw AUTOTUNE state is maintained independently.

Each axis has its own:

* state;
* gain limits;
* FF sampling;
* completion counter;
* restore snapshot;
* save state.

One axis may complete while another remains incomplete.

---

# 20. No Global Firmware Completion State

There is no authoritative fixed-wing firmware variable or message equivalent to:

```text
AUTOTUNE COMPLETE
```

for all axes.

Completion exists as a per-axis milestone.

APT must not invent a global firmware success state.

---

# 21. Per-Axis Runtime States

The relevant `AP_AutoTune` runtime states are:

```text
IDLE
DEMAND_POS
DEMAND_NEG
```

There is no persistent:

```text
FINISHED
```

runtime state.

`Finished` is an emitted milestone event.

---

# 22. Excitation Source

Fixed-wing AUTOTUNE does not inject a private excitation manoeuvre independent of normal aircraft control.

It observes controller response to demanded motion generated by:

* pilot input;
* FBWA-style attitude demand;
* navigation/controller demand in another supported mode.

Therefore successful progress depends on the aircraft actually receiving suitable demand excursions.

---

# 23. Demand-Entry Logic

AUTOTUNE begins tuning events when firmware demand/error thresholds are satisfied.

The 4.7.x implementation uses thresholds based on quantities including:

* desired rate;
* applicable RMAX;
* attitude limit;
* controller time constant;
* attitude error.

These are firmware gates.

APT need not reproduce them to establish basic session activity because ATRP exposes the resulting runtime state directly.

---

# 24. Event-End Hysteresis

Firmware uses a lower desired-rate threshold to leave a demand event than it uses to enter one.

Therefore AUTOTUNE demand periods are not simply samples above one fixed threshold.

ATRP state should be preferred when reconstructing observed demand periods.

---

# 25. Rejected Events

Firmware can reject or avoid using unsuitable excitation events.

Relevant conditions include:

* events too short to be useful;
* very low achieved rate;
* unsuitable controller response.

These conditions contribute to tuner progress but do not create one authoritative firmware:

```text
excitation quality percentage
```

---

# 26. No Firmware Excitation Score

Firmware does not expose a single percentage or pass/fail metric meaning:

```text
sufficient excitation = yes/no
```

APT may report factual evidence such as:

* demand-period count;
* positive/negative demand balance;
* demand duration;
* tuner action transitions.

Any later composite excitation metric would be APT-derived.

---

# 27. ATRP Logging

`ATRP` is the primary dedicated AUTOTUNE runtime log record.

Relevant fields include:

* axis;
* runtime state;
* surface output;
* P/D slew information;
* FF sampling;
* active FF;
* P;
* I;
* D;
* Action;
* RMAX;
* TAU.

Axis identifiers map to roll, pitch, and yaw.

---

# 28. ATRP as Activity Evidence

A valid ATRP record for an axis is strong positive evidence that the corresponding AUTOTUNE tuner update executed.

Therefore:

```text
ATRP present
```

supports:

```text
tuning activity observed
```

for that axis.

---

# 29. ATRP Absence Is Not Global Stop Evidence

No ATRP for an axis does not universally prove:

* AUTOTUNE was globally inactive;
* the selected axis was definitely disabled;
* the overall session did not exist.

Configuration or execution gating may explain the absence.

APT must report evidence absence conservatively.

---

# 30. ATRP Action Is Latched

Real-log validation shows:

```text
ATRP.Action
```

is a latched/current value.

It may be repeated across many ATRP records.

Therefore:

```text
one ATRP row
```

does not mean:

```text
one new Action event
```

---

# 31. Initial ATRP Action May Be Stale

Per-axis AUTOTUNE start resets important state but does not necessarily clear the previously stored `Action` value.

Real logs show the first Action in a later session may therefore reflect the previous session.

### Evidence consequence

APT must:

* treat the first Action value in a session as a baseline;
* detect later Action transitions;
* not automatically report the first value as a new event.

---

# 32. Gain-Limit Events

Firmware emits messages such as:

```text
RollD: 0.0125
RollP: 0.2336
PitchD: 0.0100
PitchP: 0.2621
```

when the corresponding tuning limit is established or revised.

These are explicit firmware progress events.

---

# 33. Gain-Limit Events Are Not Final Gains

A P or D limit message establishes:

```text
Gain limit observed
```

It does not establish:

* final session gain;
* final stored gain;
* completion;
* overall tune success.

The same limit type may later be revised.

---

# 34. Multiple Limit Events Are Valid

Real logs contain repeated P or D limit events.

For example, `log_0.bin` contains roll P-limit revision after an earlier completion milestone.

APT must retain all such events in sequence.

---

# 35. `Axis: Finished`

Firmware emits:

```text
Roll: Finished
Pitch: Finished
Yaw: Finished
```

when the corresponding axis reaches its completion milestone.

The milestone is per-axis.

---

# 36. Firmware Meaning of `Finished`

The firmware completion path increments a per-axis completion counter after the required tuning conditions have been established.

When the required count is reached, firmware emits:

```text
Axis: Finished
```

and calls the gain-save path.

Therefore an explicit `Finished` event authoritatively establishes:

1. the axis reached the firmware completion milestone at that instant;
2. firmware requested gain saving at that milestone.

---

# 37. `Finished` Does Not Stop Tuning

After `Finished`, the tuner remains active.

Firmware can continue to process later demand events.

Runtime gains may continue changing.

Therefore:

```text
Finished
```

does not mean:

```text
tuning stopped
```

---

# 38. `Finished` Does Not Make Values Immutable

Later tuner activity can revise gains after a completion milestone.

Therefore values observed at the first `Finished` event are not automatically the session's final runtime values.

---

# 39. Repeated `Finished` Is Real Firmware Behaviour

Stable `log_0.bin` demonstrates a complete real sequence of:

```text
RollD
RollP
Roll: Finished
...
RollP revised
...
Roll: Finished
```

within one session.

This confirms that repeated per-axis completion milestones are not merely theoretical.

---

# 40. Why Repeated `Finished` Can Occur

Subsequent tuning events may cause gain reduction or otherwise reset the completion-progress counter.

After later clean events, the axis can again satisfy the milestone condition and emit another:

```text
Axis: Finished
```

Each occurrence is a separate firmware event and save request.

---

# 41. Completion Must Be Event-Based

APT must retain:

```text
completion_events[]
```

rather than model completion solely as:

```text
finished = true
```

Presentation may summarize counts and first/last timestamps, but the evidence model must preserve repeated occurrences.

---

# 42. `Finished` Does Not Mean All Axes Finished

An explicit:

```text
Pitch: Finished
```

says nothing authoritative about whether:

* roll finished;
* yaw finished;
* another selected axis was active;
* all intended tuning work completed.

Each axis must be analysed independently.

---

# 43. Runtime Gain Changes

AUTOTUNE changes live controller parameters during tuning.

Relevant categories include:

* FF;
* P;
* I;
* D;
* controller filter values;
* RMAX;
* time constant;
* IMAX or slew-related values where firmware updates them.

These changes affect the live controller state.

---

# 44. Roll Parameter Family

Relevant roll parameters include, according to the audited implementation:

```text
RLL2SRV_TCONST
RLL2SRV_RMAX

RLL_RATE_FF
RLL_RATE_P
RLL_RATE_I
RLL_RATE_D
RLL_RATE_IMAX
RLL_RATE_FLTT
RLL_RATE_FLTE
RLL_RATE_FLTD
RLL_RATE_SMAX
```

The final implementation should encode the exact controlled set from the audited 4.7.x source.

---

# 45. Pitch Parameter Family

Relevant pitch parameters include:

```text
PTCH2SRV_TCONST
PTCH2SRV_RMAX_UP
PTCH2SRV_RMAX_DN

PTCH_RATE_FF
PTCH_RATE_P
PTCH_RATE_I
PTCH_RATE_D
PTCH_RATE_IMAX
PTCH_RATE_FLTT
PTCH_RATE_FLTE
PTCH_RATE_FLTD
PTCH_RATE_SMAX
```

Again, implementation should use the exact firmware-controlled list.

---

# 46. Yaw Parameter Family

Yaw analysis must use only the fixed-wing yaw-rate-controller parameters actually controlled by the audited 4.7.x AUTOTUNE implementation.

Do not infer a yaw parameter list from Copter AUTOTUNE or unrelated controllers.

---

# 47. Three Separate Persistence Concepts

The analyser must distinguish:

1. **runtime active value**;
2. **firmware save request / save processing**;
3. **physical persistent-media durability**.

These are not interchangeable.

---

# 48. Save Request at `Finished`

At every:

```text
Axis: Finished
```

firmware calls the corresponding gain-save path.

Therefore APT may safely state:

```text
Save requested by firmware milestone
```

for each observed completion event.

---

# 49. Stop-Path Save or Restore

On per-axis AUTOTUNE stop:

* if both required P and D limits have been established, firmware saves current gains;
* otherwise firmware restores the session-entry gain snapshot.

This is independent per axis.

---

# 50. An Axis Can Save Without `Finished`

Because stop checks the P/D-limit state directly, an axis can leave AUTOTUNE before reaching the explicit three-cycle completion milestone but still have both required limits established.

In that case stop requests a save.

Therefore:

```text
no Finished
```

does **not** imply:

```text
restored
```

---

# 51. An Incomplete Axis Can Restore

If the required P/D limit state has not been reached when normal stop occurs, the per-axis stop path restores the session-entry gain snapshot.

Where log evidence establishes that condition sufficiently, APT may report:

```text
Restore path inferred
```

---

# 52. Restore Is an Inference Unless Directly Corroborated

The internal P-limit and D-limit state is not logged as a dedicated pair of variables.

Therefore restore classification usually combines:

* firmware semantics;
* explicit gain-limit messages;
* completion events;
* ATRP progress;
* normal stop;
* parameter/runtime continuity;
* absence of contradictory evidence.

If evidence is incomplete:

```text
UNKNOWN
```

is required.

---

# 53. `log_17.bin` Session 2 Roll Restore Case

In the second AUTOTUNE session of `log_17.bin`:

* roll has substantial ATRP activity;
* no `RollD` event is observed;
* no `RollP` event is observed;
* no `Roll: Finished` event is observed;
* normal AUTOTUNE stop occurs;
* firmware reset P/D-limit state at session start.

This provides the initial validated example of:

```text
Roll tuning activity observed
Completion milestone not observed
Restore path inferred on exit
```

This is a firmware-path inference, not a tune-quality judgement.

---

# 54. `PARM` Is More Than a Startup Snapshot

Earlier analysis treated `PARM` too narrowly.

Real `log_17.bin` and `log_0.bin` demonstrate time-local `PARM` records emitted during AUTOTUNE save activity.

Therefore raw `PARM` contains useful persistence evidence beyond the startup parameter snapshot.

---

# 55. Firmware Parameter-Save Path

The relevant conceptual save path is:

```text
AUTOTUNE save_gains()
        |
        v
AP_Param save requested
        |
        v
asynchronous parameter-save processing
        |
        v
parameter value transmitted through parameter-report path
        |
        v
DataFlash PARM record
```

This is why time-local `PARM` records appear shortly after AUTOTUNE save-triggering events.

---

# 56. Real `log_0.bin` Save Evidence

Stable `log_0.bin` contains time-local `PARM` records following AUTOTUNE completion/save points.

For example, following a roll `Finished` milestone, roll rate-controller parameters are emitted as `PARM` records.

Later, after roll is retuned and reaches `Finished` again, revised parameters appear again.

Additional parameter-save records occur around normal AUTOTUNE stop.

This independently validates time-local save-processing evidence on stable 4.7.0.

---

# 57. Real `log_17.bin` Save Evidence

`log_17.bin` also contains time-local `PARM` activity following:

* pitch completion;
* roll completion;
* normal stop save operations.

Therefore the behaviour is not unique to one log.

---

# 58. Meaning of a Correlated Time-Local `PARM`

A conservatively correlated time-local `PARM` record supports:

```text
Parameter-save record observed
```

or:

```text
Save processing observed for this value
```

This is stronger than merely observing a runtime gain change.

---

# 59. `PARM` Does Not Guarantee Physical Durability

A DataFlash `PARM` record shows that the value passed through ArduPilot's parameter-save/reporting path.

APT should still not state:

```text
Guaranteed permanently committed to storage
```

because the BIN itself does not independently verify physical-media durability under every failure scenario.

---

# 60. Persistence Vocabulary

Use these distinctions:

```text
Save requested by firmware
Parameter-save record observed
Runtime value retained
Persistent-media durability not independently verified
```

The final qualification may normally remain documented rather than repeated throughout the CLI.

---

# 61. Not Every In-Session `PARM` Is AUTOTUNE

A raw `PARM` record occurring during an AUTOTUNE session is not automatically caused by AUTOTUNE.

Other parameter activity is possible.

Therefore AUTOTUNE attribution requires correlation using applicable evidence such as:

* known AUTOTUNE-controlled parameter name;
* save-triggering firmware event;
* timestamp;
* source order;
* expected runtime value;
* absence of a stronger competing cause.

---

# 62. `PARM` Absence Is Not Proof of No Save

Failure to find a correlated raw `PARM` record does not automatically establish:

```text
save did not happen
```

The safe interpretation is:

```text
corroborating PARM save record not observed
```

where relevant.

---

# 63. Raw `PARM` and Historical Parameter State Are Different

APT must use two distinct evidence products.

## Historical configuration

Use:

```text
FlightLog.parameter_history
```

for questions such as:

```text
What was AUTOTUNE_AXES at session start?
What was YAW_RATE_ENABLE at session start?
```

## Save-event evidence

Use the raw:

```text
flight_log.get("PARM")
```

records for time-local save correlation.

---

# 64. Why ParameterHistory Alone Is Insufficient for Save Evidence

Generic parameter history may suppress repeated records where the value did not change.

A repeated save of the same value can therefore be meaningful raw persistence evidence without creating a new historical transition.

Thus:

```text
ParameterHistory
```

must not replace raw `PARM` for save-event analysis.

---

# 65. AUTOTUNE Saves Naturally Affect Later Parameter History

Where an AUTOTUNE-generated `PARM` changes the effective parameter value, generic timestamp-aware parameter history should reflect that value from that point forward.

This is desirable.

It allows later sessions to be interpreted against the values actually active after earlier tuning.

---

# 66. Runtime Continuity Between Sessions

`log_17.bin` demonstrates that final observed active gains from one session can become the starting active gains of the next.

This provides:

```text
Runtime gain continuity observed
```

It does not, by itself, prove storage-media durability.

---

# 67. Session Re-entry Does Not Resume Old Tuner Progress

Although retained gains may become the next session's starting point, a new AUTOTUNE start resets session-local tuner progress.

Therefore the new session does not resume:

* old demand-event count;
* old P/D limit state;
* old completion counter;
* old sampling phase.

It is a fresh tuner session around a potentially updated controller baseline.

---

# 68. MODE Logging Order

Entering AUTOTUNE flight mode can involve firmware start behaviour before the corresponding MODE record is written.

Therefore exact record ordering around:

```text
Started autotune
MODE AUTOTUNE
```

may not match a simplistic assumption that MODE must appear first.

APT must preserve source ordering and use the explicit start event as the session authority.

---

# 69. Cross-Message Source Ordering Matters

Several important evidence relationships may share identical or near-identical `TimeUS`.

Examples include:

* start and MODE;
* stop and MODE;
* completion and subsequent `PARM`;
* repeated start boundaries;
* ATRP around start or stop.

Timestamp alone may not resolve ownership.

The analyser therefore requires original DataFlash source order in addition to `TimeUS`.

---

# 70. Parameter Changes Alone Do Not Define Sessions

A change in an AUTOTUNE-controlled parameter is not sufficient evidence that:

* AUTOTUNE started;
* AUTOTUNE stopped;
* a session completed.

Explicit session and tuner evidence must remain authoritative.

---

# 71. Completion Does Not Equal Tune Quality

Firmware completion means that the tuner reached its own per-axis progression milestone.

It does not establish:

* ideal handling;
* absence of oscillation under all conditions;
* best possible gains;
* adequate control authority;
* stability margin under every operating condition.

APT must keep firmware completion separate from later measured-response analysis.

---

# 72. Measured Response Sources

Later analysis may use:

```text
PIDR
PIDP
PIDY
ATT
RCIN
RCOU
ARSP
```

These can describe:

* target versus actual rate;
* controller error;
* output limiting;
* actuator demand;
* aircraft response;
* airspeed context.

They do not redefine `Finished`.

---

# 73. No Generic Firmware Tune Score

ArduPlane fixed-wing AUTOTUNE does not expose a single authoritative:

```text
tune score
```

or:

```text
good / bad
```

result suitable for direct reporting.

APT must not invent one in the initial implementation.

---

# 74. Explicit Evidence Hierarchy

| Evidence              | Firmware meaning                           | Safe APT interpretation                      |
| --------------------- | ------------------------------------------ | -------------------------------------------- |
| `Started autotune`    | Global start path executed                 | Open new AUTOTUNE session                    |
| `Autotuning ...`      | Axes selected by start path                | Explicit selected axes                       |
| `ATRP`                | Per-axis tuner update executed             | Tuning activity observed                     |
| `AxisD` / `AxisP`     | Gain limit established or revised          | Gain-limit event                             |
| `Axis: Finished`      | Per-axis completion milestone reached      | Completion event + firmware save request     |
| `Stopped autotune`    | Global normal stop path executed           | Normal session end                           |
| raw time-local `PARM` | Parameter value emitted via parameter path | Possible correlated save-processing evidence |
| `MODE`                | Flight-mode state                          | Activation/stop context                      |
| `MAVC`                | MAVLink command activity                   | Possible activation context                  |
| `MISE`                | Mission runtime command activity           | Possible activation context                  |
| `ParameterHistory`    | Historical effective parameter values      | Configuration at timestamp                   |
| PID logs              | Controller target/response evidence        | Later response analysis                      |
| gain change alone     | Runtime parameter change                   | Not session/completion proof                 |

---

# 75. Session Evidence Hierarchy

Preferred authority for session lifecycle:

1. explicit `Started autotune`;
2. explicit later `Started autotune` for restart;
3. explicit `Stopped autotune`;
4. log end if no normal stop exists.

Do not replace this hierarchy with:

* mode boundaries;
* disarm;
* flight-window boundaries;
* gain changes.

---

# 76. Axis Evidence Hierarchy

Preferred authority for per-axis interpretation:

1. explicit selected-axis message;
2. ATRP activity;
3. explicit P/D limit events;
4. explicit `Finished`;
5. runtime gain values;
6. correlated raw `PARM`;
7. timestamp-aware configuration support.

No one lower-level signal should silently overwrite stronger explicit firmware evidence.

---

# 77. Selected-but-Inactive Real Validation

Both real logs support the same pattern:

```text
Selected : Roll, Pitch, Yaw
Active   : Roll, Pitch
```

with yaw-rate control disabled.

This pattern must remain a first-class supported outcome.

---

# 78. Partial-Axis Real Validation

`log_17.bin` session 2 supports:

```text
Pitch:
    activity observed
    Finished observed

Roll:
    activity observed
    Finished not observed
    restore path inferred

Yaw:
    selected
    no activity observed
```

This proves that one global AUTOTUNE result would lose essential information.

---

# 79. Repeated-Completion Real Validation

`log_0.bin` supports:

```text
Roll:
    Finished observed
    later P-limit revision
    Finished observed again
```

The implementation must preserve both completion events.

---

# 80. Save-Processing Real Validation

Both validation logs provide raw time-local `PARM` evidence associated with firmware save operations.

Therefore save processing is an observable evidence category in the initial implementation.

---

# 81. What the BIN Cannot Always Reveal

Even with `ATRP`, MSG, `PARM`, and parameter history, a BIN may not conclusively reveal:

* every internal P/D-limit state when messages are missing;
* exact physical-media durability at the instant of unexpected power removal;
* unlogged controller activity;
* why a selected axis failed to generate activity if supporting configuration is unavailable;
* global tune quality;
* aircraft stability under unobserved conditions.

These limitations must remain explicit.

---

# 82. Safe Reporting Vocabulary

Preferred phrases include:

```text
AUTOTUNE session started
AUTOTUNE session stopped
Selected axis
Tuning activity observed
Tuning activity not observed
Gain limit observed
Completion milestone observed
Completion milestone not observed
Save requested by firmware milestone
Save requested on exit
Parameter-save record observed
Restore path inferred
Runtime gain continuity observed
Evidence unavailable
Normal stop not observed
```

---

# 83. Unsafe or Misleading Initial Vocabulary

Avoid:

```text
AUTOTUNE succeeded
AUTOTUNE failed
Successful tune
Failed tune
Good tune
Bad tune
Perfect tune
Final gain
Guaranteed saved
Guaranteed persisted
Yaw failed
```

unless later explicitly defined analysis supports the term.

---

# 84. Firmware-Derived vs APT-Derived Results

Firmware-derived:

```text
Started autotune
Stopped autotune
Autotuning roll pitch yaw
RollD
PitchP
Roll: Finished
```

APT-derived:

```text
session duration
demand-period count
selected-but-inactive comparison
runtime continuity
flight association
restore-path inference
PARM correlation
```

The report must not present APT-derived conclusions as literal firmware states.

---

# 85. FlightWindow Relationship

APT `FlightWindow` is a useful analysis scope based on flight detection.

It may be used to report:

```text
Session associated with Flight 2
```

but it does not define firmware AUTOTUNE lifetime.

A session may:

* start outside a detected flight;
* continue beyond a detected flight;
* remain open after disarm if no stop path occurs.

Therefore flight association is contextual only.

---

# 86. Session Termination Categories for APT

Based on firmware evidence, the initial analyser may use:

```text
STOPPED
RESTARTED
LOG_END
```

Where:

* `STOPPED` corresponds to explicit `Stopped autotune`;
* `RESTARTED` is an APT logical boundary caused by another authoritative start;
* `LOG_END` means evidence ended before an explicit stop.

There is no:

```text
FLIGHT_END
```

AUTOTUNE termination category.

---

# 87. Orphan Evidence

Logging gaps may produce:

* ATRP without an observed start;
* gain-limit messages without an observed start;
* `Finished` without an observed start;
* stop without an observed start.

APT should preserve and warn about such evidence.

It must not fabricate authoritative session boundaries.

---

# 88. Source-Order Requirement

Where records have the same `TimeUS`, original DataFlash record order may determine:

* which session owns an ATRP sample;
* whether a PARM follows or precedes a save trigger;
* whether a message occurs before or after restart.

The reader must therefore preserve a generic source-order index.

This is an analysis requirement derived from firmware logging behaviour.

---

# 89. Initial Implementation Boundary

The first AUTOTUNE implementation should cover:

* log-wide session detection;
* restart handling;
* selected-axis evidence;
* timestamp-aware configuration;
* ATRP activity;
* demand periods;
* Action transitions;
* gain-limit events;
* repeated completion events;
* entry and final observed runtime gains;
* firmware save requests;
* raw-PARM save correlation;
* conservative save/restore interpretation;
* runtime continuity;
* flight association;
* evidence warnings.

---

# 90. Deferred Analysis

Do not initially implement:

* automatic retuning recommendations;
* parameter writes;
* tune-quality scoring;
* aircraft stability grading;
* automatic gain recommendations;
* Copter AUTOTUNE;
* PID-response pass/fail;
* oscillation severity ratings.

---

# 91. Later Response Analysis

A later phase may investigate:

* demanded vs achieved rate;
* overshoot;
* settling;
* oscillation;
* slew limiting;
* actuator output;
* airspeed dependence;
* response before and after tuning.

This later work must consume the firmware session model defined here.

It must not redefine session completion semantics.

---

# 92. Frozen Firmware Semantics

The following are frozen for the initial implementation unless new source or real-log evidence disproves them.

1. Fixed-wing AUTOTUNE has multiple activation paths.
2. AUTOTUNE flight mode is not the universal session detector.
3. `Started autotune` is authoritative start evidence.
4. `Stopped autotune` is authoritative normal stop evidence.
5. A repeated start resets important per-axis session state.
6. A repeated start therefore creates a new logical AUTOTUNE session.
7. Disarm alone is not an AUTOTUNE stop.
8. A GPS-flight boundary is not an AUTOTUNE stop.
9. Log end is not proof of normal stop.
10. Axis selection is sampled at AUTOTUNE start.
11. `Autotuning ...` is explicit selected-axis evidence.
12. Selected and active axes are different concepts.
13. Yaw selection does not guarantee yaw tuner activity.
14. Each axis has an independent tuner.
15. There is no global all-axis firmware completion state.
16. Runtime tuner states are IDLE, DEMAND_POS, and DEMAND_NEG.
17. Fixed-wing AUTOTUNE observes demanded movement rather than injecting a separate private excitation manoeuvre.
18. ATRP is primary per-axis runtime evidence.
19. ATRP presence proves observed tuner activity.
20. ATRP absence does not prove global AUTOTUNE inactivity.
21. ATRP Action is latched.
22. Initial Action in a new session may be stale.
23. Gain-limit messages are explicit progress events.
24. Multiple P/D limit events are valid.
25. `Axis: Finished` is a per-axis milestone.
26. `Finished` triggers a firmware gain-save request.
27. `Finished` does not stop tuning.
28. Gains may change after `Finished`.
29. An axis may emit `Finished` more than once in one session.
30. Repeated `Finished` is confirmed in stable `log_0.bin`.
31. Absence of `Finished` does not imply no save.
32. Normal stop saves an axis when required P/D limit state exists.
33. Otherwise the axis restores its session-entry gain snapshot.
34. Restore classification must remain evidence-based.
35. Runtime active values and persistent-save evidence are separate concepts.
36. Raw time-local `PARM` can provide positive evidence of save processing.
37. This behaviour is confirmed in both real validation logs.
38. Not every in-session `PARM` is necessarily caused by AUTOTUNE.
39. PARM attribution must be conservative.
40. A correlated `PARM` does not prove absolute physical-media durability.
41. Absence of a correlated `PARM` does not prove no save request occurred.
42. Raw `PARM` and `ParameterHistory` serve different evidence roles.
43. `ParameterHistory` is appropriate for historical configuration.
44. Raw `PARM` is required for time-local save correlation.
45. AUTOTUNE-generated parameter changes naturally affect later historical configuration.
46. Re-entry begins a fresh tuner session even when retained gains form the new baseline.
47. Runtime gain continuity between sessions is valid derived evidence.
48. Cross-message source order matters for exact event ownership.
49. MODE is supporting context, not lifecycle authority.
50. Firmware completion is not equivalent to tune quality.
51. PID response analysis is a separate later concern.
52. The initial implementation must not produce a global AUTOTUNE success/failure score.

---

# 93. Current Validation Status

The firmware contract has now been exercised against:

## Stable ArduPlane 4.7.0

Validated:

* selected axes;
* active axes;
* selected-but-inactive yaw;
* gain-limit revisions;
* repeated completion;
* tuning after completion;
* milestone saves;
* time-local parameter-save records;
* normal stop save activity.

## ArduPlane 4.7.0-beta7

Validated:

* multiple sessions;
* independent axis outcomes;
* roll and pitch completion;
* later incomplete roll tuning;
* restore-path inference;
* selected-but-inactive yaw;
* runtime continuity;
* time-local save evidence.

No current real-log evidence contradicts the firmware model defined here.

---

# 94. Implementation Contract

Production code must treat this document as the firmware-semantics boundary.

If implementation discovers evidence that appears inconsistent with this document:

1. do not silently alter the detector to fit the new log;
2. identify the exact contradiction;
3. check producing firmware version;
4. check source semantics;
5. determine whether the issue is:

   * reader loss;
   * ordering;
   * missing evidence;
   * beta/stable firmware difference;
   * genuinely new firmware behaviour;
6. update the documented contract before broadening implementation semantics.

---

# 95. Next Step

With this document and:

```text
Implementation/Autotune_detector_design.md
```

now aligned, firmware semantics and detector design are frozen for the initial functionality pass.

The next task is a single **Medium-reasoning Codex implementation pass** focused on:

* AUTOTUNE message configuration;
* generic source-order retention;
* AUTOTUNE domain model;
* log-wide session detector;
* per-axis evidence;
* persistence/PARM evidence;
* presentation;
* menu integration;
* real-log validation against `log_17.bin` and `log_0.bin`.

BDD/test hardening remains a separate subsequent pass.
