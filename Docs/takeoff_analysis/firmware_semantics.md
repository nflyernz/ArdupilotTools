# ArduPlane Takeoff Analysis — Firmware Semantics and Initial Analysis Contract

**Scope:** ArduPlane 4.7.x / APT research project  
**Source audit basis:** Plane-4.7.1  
**Status:** Source semantics established; execution-window semantics ready for prototype

## 1. Purpose and decision

**Purpose.** Define what an evidence-first APT takeoff analysis is allowed to call a takeoff execution, which firmware events own that execution, how the execution ends, and which DataFlash observations can be used to evaluate ArduPlane response. This document deliberately stops before performance-threshold tuning or real-log-specific detector tuning.

**Primary decision.** The analysis is about firmware behaviour, not reconstructing the physical act of hand release. Physical hand release is therefore not an analysis boundary and no release-time inference is required for the initial model. The central response anchor is the firmware AUTO launch trigger, and the analysis remains owned by the active AUTO `NAV_TAKEOFF` execution only while that execution remains in control.

**Hard ownership rule.** A takeoff execution window ends when the active AUTO `NAV_TAKEOFF` execution ends. A mode change away from AUTO is a hard end boundary even if the mission is later resumed. Re-entry to AUTO starts a new analysis execution window; the old window is never reopened or extended with later observations.

| Boundary | Meaning for analysis | Classification |
|---|---|---|
| `NAV_TAKEOFF` command start | AUTO mission takeoff command is active and its state has been initialized. | Firmware ownership start |
| `Triggered AUTO` | Launch detector accepts configured trigger conditions; post-trigger takeoff response begins. | Strong firmware event |
| `Takeoff complete` | Firmware verifier completes `NAV_TAKEOFF` and allows mission progression. | Normal firmware termination |
| Mode change away from AUTO | AUTO stops owning the running takeoff sequence; subsequent observations no longer belong to this execution. | Hard analysis termination |
| Takeoff timeout / disarm | Configured post-trigger timeout or another disarm has ended the execution. | Abnormal firmware termination |
| Log end / missing terminal evidence | Ownership cannot be proven beyond available observations. | Incomplete / censored termination |

## 2. Scope

This source audit applies to fixed-wing ArduPlane AUTO mission takeoff using `MAV_CMD_NAV_TAKEOFF` in Plane 4.7.x. Source references in this document are pinned to the Plane-4.7.1 tag unless stated otherwise.

- Research environment: APT (`~/ArduPilotTools`).
- Operational context: Volantex Ranger 2000, hand launch, AUTO takeoff, SpeedyBee F405 Wing.
- The aircraft has recently become lighter; historical speed assumptions are context only and are not analytical truth.
- This document does not modify AMC, `configuration_steps_ArduPlane.json`, Plane template parameter files, or `TUNING_GUIDE_ArduPlane.md`.
- This document does not define safe/unsafe thresholds or scoring.

**Out of scope for the initial model:** physical hand-release timing, physical liftoff timing, actual propeller thrust, and any inferred “stable climb” state. Those can only be added later with separate, explicit evidence semantics if they prove operationally useful.

For this aircraft, a real repeat hand launch is expected to involve a fresh arm/re-arm cycle. Repeated `NAV_TAKEOFF` execution while continuously armed is therefore an edge case for robustness testing, not a design-driving operational case.

## 3. Event ownership and causality contract

This section is normative for the first APT implementation. It carries forward the event-ownership and causality rule established during the earlier landing-analysis review: **an observation can only influence an event or metric while it is owned by the execution window that is still causally active.**

### 3.1 Ownership is established before evidence is interpreted

APT must first determine the enclosing AUTO `NAV_TAKEOFF` execution window. Only then may observations be selected for event detection, state interpretation, or derived metrics.

The intended order is:

```text
establish execution ownership
    -> identify firmware events inside that ownership
    -> select measured observations
    -> determine observation validity/usability
    -> calculate derived metrics
```

A convenient signal must not be allowed to define ownership merely because it appears near a takeoff.

### 3.2 First valid termination closes the window

The first authoritative terminating event ends the execution window. Examples include:

- firmware `Takeoff complete`;
- mode change away from AUTO;
- explicit `TKOFF_TIMEOUT` termination/disarm;
- another disarm that removes takeoff ownership;
- log end when no stronger terminal event is observable.

Once closed, the execution window is immutable.

### 3.3 No post-window evidence may rewrite the past

Observations after `termination_time` do not belong to the closed execution and must not:

- complete a persistence test that had not yet completed;
- establish a peak/minimum that occurred after ownership ended;
- replace an already selected termination reason;
- retroactively turn an incomplete event into a completed one;
- qualify a derived event that required future samples outside the window.

A later observation may only affect the earlier execution if ArduPlane firmware semantics explicitly define that later observation as completing the earlier firmware transition. No such exception is assumed by default.

This is the same causal principle that prevents a persistence detector from borrowing post-attempt samples to supersede an earlier valid termination.

### 3.4 Persistence and confirmation must finish inside ownership

If a future takeoff metric requires persistence—for example, groundspeed above a threshold for N milliseconds, pitch tracking settled for N samples, or climb rate remaining positive for a defined interval—the full confirmation interval must lie within the active execution window.

If the window terminates before confirmation completes, the condition is **unconfirmed**, not retrospectively true.

### 3.5 Event-time sampling must not cross the boundary

When reporting values “at” a firmware event, nearest-sample logic must respect ownership. A sample after a hard termination must not be borrowed to represent a value at the final event simply because it is temporally closer.

Each event-sampling rule must therefore define:

- source message/field;
- allowed time direction: previous-only, next-only, or nearest;
- maximum admissible time offset if required;
- whether the selected sample must lie strictly inside the execution window;
- missing-value behaviour.

### 3.6 Derived metrics inherit the ownership of their inputs

A derived metric is only valid if all required observations are valid and owned by the same execution window or by an explicitly defined event context.

Examples:

- trigger-to-termination duration belongs to one execution;
- maximum roll excursion uses only samples between trigger and termination;
- minimum airspeed after trigger cannot inspect samples after mode exit;
- parameter interpretation uses the value effective at the event/sample timestamp, not the final value in the log.

### 3.7 Re-entry to AUTO creates new ownership

If AUTO is exited and later re-entered, any subsequent `NAV_TAKEOFF` execution is a new analysis window. It must not be stitched to the previous window even if:

- the same mission item is resumed;
- the aircraft remains armed;
- the new command is only seconds later;
- the logs make the two intervals visually continuous.

Mode change is the causal break.

### 3.8 Missing evidence remains missing

DataFlash is an observation stream, not a full firmware execution trace. If a firmware message is absent, APT must not fabricate it from nearby values unless a separately defined inference method exists.

In particular:

- absence of `Triggered AUTO` text does not prove launch detection never triggered;
- absence of `Bad launch AUTO` does not prove attitude was never rejected;
- absence of `Timeout AUTO` does not prove the pre-trigger detector never reset;
- log end does not prove normal completion.

## 4. AUTO `NAV_TAKEOFF` firmware lifecycle

### 4.1 Command start

When `MAV_CMD_NAV_TAKEOFF` starts, `Plane::do_takeoff()` initializes the takeoff command state. It loads the mission pitch, substitutes 4 degrees when the mission pitch is zero or negative, calculates the relative takeoff target altitude, clears takeoff/rotation completion state, resets course-hold state, and records barometric takeoff altitude.

This is the correct firmware-level start of the mission takeoff command. It is not evidence that launch detection has fired.

```text
NAV_TAKEOFF start
  -> initialise takeoff pitch and target altitude
  -> clear takeoff_complete / rotation_complete
  -> reset takeoff course state
  -> record barometric takeoff reference
```

`AP_Mission` logs the starting mission item as `MISE` when the relevant mission-command logging is enabled. `MISE` is therefore strong evidence that a particular mission command execution has begun; the stored mission alone is only configuration.

### 4.2 Launch detection

`Plane::auto_takeoff_check()` performs the fixed-wing AUTO launch check. Its executable sequence in Plane-4.7.1 is: armed/safety state, continuity of the launch-check process, rudder-neutral handling where applicable, GPS 3D fix, optional longitudinal-acceleration trigger, configured delay, attitude validity gate, and GPS groundspeed threshold.

If accepted, firmware emits `Triggered AUTO. GPS speed = ...`, records the takeoff start timestamp used by the post-trigger timeout logic, starts the maximum-throttle timer, and returns `true`.

| Input / gate | Plane 4.7.1 behaviour | Analytical meaning |
|---|---|---|
| Armed + safety off | Disarmed state clears takeoff state and prevents trigger. | Prerequisite, not a launch event |
| GPS fix | At least 3D GPS fix is required. | Prerequisite |
| `TKOFF_THR_MINACC` | If non-zero, TECS longitudinal acceleration must satisfy configured event logic. | Trigger precursor |
| `TKOFF_ACCEL_CNT` | Can require multiple alternating acceleration events. | Trigger precursor |
| `TKOFF_THR_DELAY` | Delay after acceleration arming before groundspeed acceptance. | Timing gate |
| Attitude check | Rejects launch candidates outside permitted pitch/roll envelope unless disabled. | Validity gate |
| `TKOFF_THR_MINSPD` | GPS groundspeed must exceed threshold unless the parameter is zero. | Final trigger gate |
| `Triggered AUTO` | Launch conditions accepted; firmware proceeds with takeoff response. | Primary launch-response anchor |

**Key semantic result:** airspeed is not an input to the AUTO hand-launch detector. Pitch and roll are acceptance gates, not positive launch identifiers. Throttle is a response/output path rather than an input used to prove launch.

### 4.3 Pre-trigger retries are not separate completed takeoffs

The launch check can arm, reject, reset, and try again while the same `NAV_TAKEOFF` command remains active. If the delay window expires, firmware may report `Timeout AUTO`; if the attitude gate fails it reports `Bad launch AUTO`.

In both cases the internal launch timer is reset and another trigger opportunity may follow. These observations are pre-trigger events owned by the same execution window, not automatically independent takeoff attempts.

A source-code detail should be preserved: the introductory comment in `takeoff.cpp` still mentions a 2.5 s retry timeout, while executable Plane-4.7.1 code expires the candidate when elapsed time exceeds `TKOFF_THR_DELAY + 100 ms`. Executable code is authoritative for the model.

### 4.4 Takeoff response after trigger

Once the active `NAV_TAKEOFF` has triggered, `ModeAuto::update()` continues to call the takeoff-specific roll, pitch and throttle calculations while `NAV_TAKEOFF` remains the current navigation command.

This is the interval of primary operational interest: the firmware is commanding a takeoff and the log can be used to evaluate how the aircraft responded.

The pitch logic is not simply a fixed mission-pitch command. For hand launch, `TKOFF_ROTATE_SPD` is normally zero, after which the takeoff pitch path establishes a minimum takeoff pitch and, when an airspeed sensor is in use, allows normal pitch calculation subject to that minimum. Plane 4.7.1 also reduces pitch demand when roll error becomes large under stall-prevention logic, specifically to improve robustness of hand launches and cross-wind recovery.

This makes demanded-versus-achieved pitch and roll important paired observations rather than isolated attitude values.

### 4.5 Firmware completion

`Plane::verify_takeoff()` completes `NAV_TAKEOFF` when adjusted relative altitude exceeds the mission takeoff altitude, or when the configured pitch-level-off timeout path completes. Firmware emits `Takeoff complete at ...m`, sets `takeoff_complete`, releases takeoff course-hold state, and returns `true` so the mission can advance.

**Therefore `Takeoff complete` means mission-command completion, not physical liftoff and not an analytical declaration of stable climb.** If a future stable-climb metric is wanted, it must remain a separately derived concept with its own definition and ownership rules.

### 4.6 Post-trigger timeout

`TKOFF_TIMEOUT` creates an explicit abnormal termination path. If enabled, and GPS groundspeed has not reached 4 m/s within the configured time after `Triggered AUTO`, Plane emits a takeoff-timeout message, disarms using the `TAKEOFFTIMEOUT` arming method, and `verify_takeoff()` resets the mission.

This is qualitatively different from the pre-trigger `Timeout AUTO` retry event.

| Observed text / event | Stage | Meaning |
|---|---|---|
| `Armed AUTO` | Pre-trigger | Acceleration/event logic armed the launch timer; not launch completion. |
| `Timeout AUTO` | Pre-trigger | Current trigger candidate expired and detector reset; same execution may continue. |
| `Bad launch AUTO` | Pre-trigger | Attitude gate rejected candidate; same execution may continue. |
| `Triggered AUTO` | Trigger | Firmware accepted launch conditions. |
| Takeoff timeout `<4m/s` | Post-trigger | Configured abnormal takeoff termination; may disarm/reset mission. |
| `Takeoff complete` | Post-trigger | Normal `NAV_TAKEOFF` verifier completion. |

### 4.7 Mode change away from AUTO

Mode exit is a hard analysis boundary. AUTO no longer owns the takeoff sequence after the mode change, so later aircraft behaviour must not be attributed to the closed takeoff execution.

For the first APT model:

```text
AUTO NAV_TAKEOFF active
    -> mode changes away from AUTO
    -> terminate execution at mode-change timestamp
    -> ignore all later observations for this execution
```

If AUTO is later re-entered and `NAV_TAKEOFF` runs again, APT creates a new execution window. No later samples may extend or repair the old one.

## 5. Evidence classification

The takeoff model must preserve the difference between firmware events, logged measurements, controller outputs, and derived metrics.

| Observation | Classification | What it can establish |
|---|---|---|
| Executed `MISE NAV_TAKEOFF` | Firmware-originated event | Mission takeoff command execution began, when logging is present. |
| `Armed AUTO` message | Firmware-originated observation | Launch acceleration/event logic armed at an observed reporting point. |
| `Bad launch AUTO` message | Firmware-originated event | Attitude gate rejected a trigger candidate. |
| `Timeout AUTO` message | Firmware-originated event | Pre-trigger candidate expired/reset. |
| `Triggered AUTO` message | Strong firmware event | `auto_takeoff_check()` accepted launch conditions. |
| `STAT.Stage` / `STAT.Sup` | Firmware state sample | Flight-stage and throttle-suppression context at sample time. |
| `ATT` | Logged target + attitude | Desired and achieved aircraft attitude. |
| `CTUN` | Controller/state sample | Navigation attitude targets, throttle values and related control context. |
| `ARSP` | Sensor-derived measurement | Airspeed-system observation when available and valid. |
| `GPS` | Sensor-derived measurement | Position, track and groundspeed. |
| `BARO` / altitude source | Sensor/state measurement | Altitude evidence subject to explicit source choice. |
| `AETR` / `RCOU` | Command/output | Surface/throttle outputs; not aerodynamic response or thrust. |
| `Takeoff timeout...` | Firmware event | Explicit post-trigger timeout path. |
| `Takeoff complete...` | Strong firmware event | Firmware verifier completed `NAV_TAKEOFF`. |
| Physical hand release | Unavailable directly | Outside initial analysis scope. |
| Physical liftoff | Unavailable directly | No direct ordinary DataFlash event. |
| Actual propeller thrust | Unavailable normally | Throttle/output does not prove physical thrust. |
| Pitch tracking error | Derived | Demand minus achieved pitch under defined signal conventions. |
| Distance / altitude gain / extrema | Derived | Requires explicit source and ownership window. |

`STAT.is_flying` is a firmware estimator, not a physical liftoff switch. It may be useful supporting context but must not be renamed as release/liftoff time.

## 6. Controller demand and response signals

### 6.1 Pitch and roll

For the first APT implementation, `ATT` should be the primary signal family for demanded-versus-achieved attitude because it provides final desired attitude and achieved attitude on a common log message.

Recommended interpretation:

- `ATT.DesPitch` versus `ATT.Pitch` for pitch demand/response;
- `ATT.DesRoll` versus `ATT.Roll` for roll demand/response;
- `CTUN` as a controller cross-check when investigating takeoff control behaviour;
- `PIDP` / `PIDR` only when deeper control-loop diagnosis is required.

Any metric comparing demand and response must state its sample-alignment method and must not pair samples across the execution boundary.

### 6.2 Throttle

The analysis may use throttle demand/output messages appropriate to the specific log and logging configuration. These are controller/output observations. They do not prove actual propeller thrust.

If RPM or ESC telemetry exists it can add evidence, but even RPM is not direct thrust measurement. Metric names should therefore describe command/output behaviour rather than claim physical thrust.

### 6.3 Airspeed, groundspeed and wind

Airspeed during the takeoff window is operationally important even though it is not a launch-trigger input. Groundspeed and airspeed should be presented independently.

Their scalar difference is not generally wind. Wind should only be reported from a defensible logged estimate or an explicit vector calculation with defined validity conditions.

## 7. Parameter context

Takeoff interpretation must use event-time parameter values from the existing APT `ParameterHistory`. Final parameter values in a log must never be used to explain an earlier takeoff if a parameter was changed later.

Parameter lookup itself follows causality: the effective value at time `t` is the most recent applicable parameter state at or before `t` according to established `ParameterHistory` semantics; later parameter changes cannot alter earlier interpretation.

| Parameter / input | Role in Plane 4.7.x takeoff analysis |
|---|---|
| `NAV_TAKEOFF p1` | Mission takeoff pitch; firmware substitutes 4 degrees when `<= 0`. |
| `NAV_TAKEOFF altitude` | Normal firmware completion altitude target. |
| `TKOFF_THR_MINACC` | Forward acceleration threshold for launch-check arming; zero disables this test. |
| `TKOFF_ACCEL_CNT` | Number/pattern of acceleration events required. |
| `TKOFF_THR_DELAY` | Delay between acceleration arming and final groundspeed acceptance. |
| `TKOFF_THR_MINSPD` | GPS groundspeed threshold used before throttle is unsuppressed; zero disables speed requirement. |
| `TKOFF_TIMEOUT` | Post-trigger timeout if 4 m/s GPS groundspeed is not achieved. |
| `TKOFF_THR_MAX` / `TKOFF_THR_MAX_T` | Takeoff maximum-throttle limit and forced-maximum interval. |
| `TKOFF_THR_MIN` / `TKOFF_OPTIONS` | Takeoff throttle range behaviour. |
| `TKOFF_THR_IDLE` | Idle throttle before takeoff. |
| `TKOFF_THR_SLEW` | Takeoff throttle slew behaviour. |
| `TKOFF_ROTATE_SPD` | Ground-takeoff rotation path; zero is the hand-launch configuration. |
| `TKOFF_PLIM_SEC` | Pitch-minimum level-off reduction and timeout path near takeoff target altitude. |
| `TKOFF_LVL_ALT` / `LEVEL_ROLL_LIMIT` | Takeoff roll limiting with altitude. |
| Flight option disabling takeoff attitude check | Changes whether pitch/roll can reject a launch candidate. |

## 8. Initial APT execution-window model

The first implementation should remain narrow. It should model one firmware-owned AUTO `NAV_TAKEOFF` execution and attach observations to that window. It should not invent physical launch phases before the evidence requires them.

| Field / concept | Initial semantics |
|---|---|
| `command_start` | Timestamp and mission identity for executed `NAV_TAKEOFF`. |
| `parameter_context` | Relevant `ParameterHistory` values at command start and event/sample times. |
| `pretrigger_events` | Observed `Armed AUTO` / `Timeout AUTO` / `Bad launch AUTO` / rudder-wait evidence; explicitly incomplete if logging omits messages. |
| `launch_trigger` | `Triggered AUTO` timestamp when directly observed. |
| `post_trigger_response` | Timeseries evidence from trigger until execution termination. |
| `termination_time` | First authoritative end of the firmware-owned execution window. |
| `termination_reason` | `completed` / `mode_change` / `takeoff_timeout` / `disarm` / `log_end` / other evidence-based reason. |
| `completion` | Firmware `NAV_TAKEOFF` completion evidence where present. |
| `timeseries` | ATT, CTUN, ARSP, GPS, altitude and throttle/output sources selected by explicit rules. |
| `derived_metrics` | Only metrics with explicit definitions, windows, source fields and validity conditions. |

**No `physical_release` field is required.** The operational question is how the firmware behaves while it owns the takeoff sequence and especially after it declares `Triggered AUTO`. Inferring the instant the aircraft left the launcher’s hand would add uncertainty without improving that evaluation.

### 8.1 Execution finalization rule

An execution may be finalized as soon as its first authoritative termination is known. After finalization:

- its time bounds do not move;
- its termination reason does not change because of later samples;
- its derived metrics cannot consume later samples;
- a later AUTO entry creates a new execution object.

This is the key guard against retroactive causality.

## 9. Candidate first metrics

The first useful metrics should be limited to quantities with clean event and ownership semantics. This is a research target, not yet an implementation requirement.

| Metric | Proposed window / anchor | Status |
|---|---|---|
| Command duration | `command_start -> termination_time` | Straightforward once boundaries are resolved |
| Trigger-to-termination time | `launch_trigger -> termination_time` | Straightforward when trigger exists |
| Airspeed at trigger / termination | Explicit event-sampling rule using valid ARSP observation | Measured/sampled; validity required |
| Groundspeed at trigger / termination | Explicit event-sampling rule using GPS observation | Measured/sampled |
| Pitch demand / achieved at trigger | ATT desired/actual pitch near event | Measured/sampled |
| Maximum pitch tracking error | Post-trigger firmware-owned window only | Derived; define sample alignment |
| Maximum absolute roll / roll error | Post-trigger firmware-owned window only | Derived; distinguish attitude from tracking error |
| Minimum altitude after trigger | `launch_trigger -> termination_time` | Derived; choose altitude source explicitly |
| Altitude gain to termination | Event-defined altitude difference | Derived |
| Throttle rise after trigger | `launch_trigger -> defined output threshold`, inside window | Derived from command/output, not thrust |
| Minimum airspeed after trigger | Trigger to termination or narrower validated critical window | Derived; no safety score yet |

Deferred until separately justified: physical release time, liftoff time, stable-climb time, wind-effect scoring, airspeed safety margin, and any good/bad assessment.

No persistence-based metric should be added without an explicit rule that its confirmation interval must complete before the execution terminates.

## 10. Synthetic cases required before real-log validation

Synthetic tests should freeze ownership, causality and event semantics before expectations are taken from the Ranger logs.

At minimum:

1. Normal `NAV_TAKEOFF` command start -> `Triggered AUTO` -> `Takeoff complete`.
2. Pre-trigger acceleration arm followed by `Timeout AUTO`, then a successful trigger within the same command execution.
3. Bad-launch attitude rejection followed by a later successful trigger.
4. Command starts but mode changes away from AUTO before `Triggered AUTO`.
5. Mode changes away from AUTO after `Triggered AUTO` but before firmware completion.
6. AUTO is later re-entered and `NAV_TAKEOFF` runs again; this must create a new execution window.
7. A post-window sample would satisfy a candidate persistence rule; test must prove it is rejected.
8. A post-window sample is temporally nearest to termination; test must prove event sampling does not cross the hard boundary unless the sampling contract explicitly allows it.
9. `TKOFF_TIMEOUT` causes post-trigger disarm and mission reset.
10. Disarm for another reason while `NAV_TAKEOFF` remains active.
11. Takeoff completion is observed but `Triggered AUTO` text is missing from the log.
12. Log ends during an active takeoff execution; result remains incomplete rather than inferred.
13. Parameter changes between separate takeoff executions in one log; each execution receives event-time values.
14. Later observations contradict or extend a finalized execution; test must prove they cannot rewrite its bounds, termination, or metrics.
15. Multiple real-style hand launches in one log separated by disarm/re-arm create independent execution windows.
16. Continuously armed repeated `NAV_TAKEOFF` execution is handled without corrupting ownership, but remains an edge case rather than the normal operational model.

## 11. Real-log validation plan

Only after the synthetic semantics pass should the first Li-ion flight log with multiple AUTO takeoffs be used. The objective of the first real-log pass is not to tune thresholds; it is to verify that source-defined ownership windows and firmware events can be recovered from ordinary DataFlash evidence without special-casing that log.

1. Enumerate AUTO `NAV_TAKEOFF` execution windows from mission/mode evidence.
2. Confirm each window ends at the first authoritative completion, mode exit, timeout/disarm, or unavailable/log-end evidence.
3. Confirm no sample after termination is consumed by that execution.
4. Locate `Triggered AUTO` where present and inspect the transition from suppressed/pre-trigger behaviour to takeoff response.
5. Plot ATT pitch/roll demand versus achieved response inside each firmware-owned window.
6. Add CTUN throttle demand/output, ARSP airspeed, GPS groundspeed and altitude evidence using event-time parameters.
7. Compare repeated takeoff executions for consistency without declaring thresholds good/bad.
8. Record any mismatch between source-predicted state transitions and what normal DataFlash exposes; adjust evidence semantics before adding metrics.
9. Explicitly test whether each derived metric can be finalized causally at or before the execution termination.

## 12. What the source audit establishes — and what it does not

| Established from Plane 4.7.x source / project causality rules | Not established / not assumed |
|---|---|
| `NAV_TAKEOFF` has a distinct command-init path and verifier. | Physical hand release time. |
| Launch detection can depend on acceleration, delay, attitude and GPS groundspeed. | Physical liftoff time. |
| Airspeed is not a launch-trigger input. | Actual thrust from throttle output alone. |
| `Triggered AUTO` is a strong firmware event and starts post-trigger timeout timing. | A universal safe airspeed margin. |
| Pre-trigger timeout/bad-attitude events reset and may retry within the same execution. | That every retry message is logged. |
| Takeoff completion is altitude/level-off-verifier based. | That completion equals stable climb. |
| Mode exit from AUTO ends analysis ownership. | That observations after mode exit still belong to the earlier takeoff. |
| Re-entry to AUTO creates new analysis ownership. | That a resumed mission should be stitched to the previous window. |
| Post-trigger `TKOFF_TIMEOUT` can disarm and reset mission. | That all takeoff failures use the same abort mechanism. |
| First authoritative termination closes the execution. | That future samples may supersede a completed termination. |
| Persistence confirmation must complete while the execution is active. | That post-window samples may be borrowed to finish a condition. |
| Event-time parameter values explain event-time behaviour. | That final log parameter values explain earlier takeoffs. |

## 13. Implementation guardrails

The first detector/model implementation must satisfy these rules before performance metrics are added:

- ownership is determined before metric extraction;
- every execution has explicit start and termination semantics;
- mode exit is a hard boundary;
- the first authoritative termination wins;
- finalized executions are immutable;
- no observation after termination can affect the closed execution unless a specific firmware rule explicitly requires it;
- persistence conditions must complete inside ownership;
- missing evidence remains missing;
- parameter lookup uses established `ParameterHistory` semantics;
- measured, firmware-originated and derived values remain labelled separately;
- no physical-release inference is needed;
- no safety/good/bad judgement is encoded.

These are stronger requirements than simply producing plausible takeoff windows. The implementation must be causally defensible.

## 14. Recommended next step

The next APT task should be a bounded implementation of the execution-window and event model only, backed by synthetic tests. It should not yet calculate every candidate performance metric.

The first implementation should prove that APT can reliably identify:

- AUTO `NAV_TAKEOFF` command start;
- pre-trigger event observations without over-interpreting missing messages;
- `Triggered AUTO` when available;
- hard termination on mode change;
- firmware completion;
- explicit takeoff timeout/disarm;
- new execution ownership if AUTO later resumes/re-enters;
- event-time parameter context;
- causal finalization with no post-window evidence leakage.

Only after those boundaries are stable should pitch/roll tracking, airspeed/groundspeed growth, altitude behaviour and throttle-response metrics be layered onto the window.

## 15. Source references

**ArduPlane Plane-4.7.1: `takeoff.cpp`**  
https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.1/ArduPlane/takeoff.cpp  
`auto_takeoff_check()`, `takeoff_calc_roll()`, `takeoff_calc_pitch()`, `takeoff_calc_throttle()`, `check_takeoff_timeout()`.

**ArduPlane Plane-4.7.1: `commands_logic.cpp`**  
https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.1/ArduPlane/commands_logic.cpp  
`do_takeoff()`, `verify_takeoff()`, mission callbacks.

**ArduPlane Plane-4.7.1: `mode_auto.cpp`**  
https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.1/ArduPlane/mode_auto.cpp  
AUTO entry/exit, mission stop/resume, takeoff-specific controller update path.

**AP_Mission Plane-4.7.1: `AP_Mission.cpp`**  
https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.1/libraries/AP_Mission/AP_Mission.cpp  
`MISE` logging, `stop()`, `resume()`, `start_or_resume()`, command re-initialisation.

**ArduPlane Plane-4.7.1: `Log.cpp`**  
https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.1/ArduPlane/Log.cpp  
CTUN, STAT and AETR definitions.

**AP_AHRS log structure**  
https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_AHRS/LogStructure.h  
ATT desired/achieved attitude fields.

*Research note: source semantics are pinned to Plane-4.7.1 for this audit. Before migrating the model to materially different ArduPlane versions, re-check the relevant functions rather than assuming the state machine is unchanged.*
