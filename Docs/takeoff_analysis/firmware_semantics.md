# ArduPlane Takeoff Analysis — Firmware Semantics Contract

**Scope:** conventional fixed-wing ArduPlane TAKEOFF mode and AUTO mission
`NAV_TAKEOFF` in stable Plane 4.7.x

**Primary source basis:** Plane-4.7.0

**Compatibility check:** the relevant Plane-4.7.1 source is unchanged

**Status:** stable 4.7.x ownership/event semantics established and implemented
in the current TAKEOFF-mode analyser; remaining surface-phase and
already-airborne presentation work is explicitly deferred

## 1. Purpose and decisions

This document defines the firmware ownership, event, and evidence semantics
that APT may use for fixed-wing takeoff analysis. It deliberately stops before
performance metrics, threshold tuning, or safety judgments.

The primary operational entry context is ArduPlane **TAKEOFF mode**
(`ModeNum=13`). The contract is not specific to hand launch. It covers
conventional rolling/surface and non-surface launches wherever Plane 4.7.x
uses the same TAKEOFF-mode machinery. QuadPlane/VTOL and other vehicle takeoff
implementations are outside this contract. Tow/winch, air-drop, and carrier
launches are also excluded because this bounded audit found no dedicated
stable-4.7.0 conventional TAKEOFF-mode state that would justify separate
semantics for them.

AUTO mission `MAV_CMD_NAV_TAKEOFF` remains a second, separately owned entry
context. It shares substantial launch and controller code with TAKEOFF mode,
but its start, target, completion, and outer ownership are different.

The analysis concerns **firmware behavior**. It does not infer physical hand
release, launcher release, wheel rotation, wheel liftoff, or physical thrust.

### 1.1 Two boundaries are required for TAKEOFF mode

| Boundary | Definition | Intended analytical use |
|---|---|---|
| Outer execution | Successful logged transition into `MODE=13` through the first authoritative transition to `MODE!=13` (or log end) | Ownership and context |
| Inner automatic takeoff-control phase | The source-defined TAKEOFF-stage control interval, interpreted with launch/suppression context, through a defensible `FlightStage::TAKEOFF -> NORMAL` transition | Later firmware-response measurements |

The boundaries need not coincide. After the inner stage becomes `NORMAL`,
TAKEOFF mode continues to own navigation and normally loiters at its target
until another mode is selected.

### 1.2 Causality is mandatory

An observation may affect an execution only while that execution owns it.
Mode exit closes the outer TAKEOFF-mode window. A later re-entry creates a new
window. No later observation may repair, extend, or rewrite a closed window,
and any persistence requirement must complete before ownership ends.

APT does not retain a universal raw order across different DataFlash message
types at equal `TimeUS`. Unsupported same-timestamp cross-stream ordering must
remain ambiguous unless firmware control flow establishes the relationship.

## 2. Firmware and corpus scope

### 2.1 Stable source target

Plane-4.7.0 is authoritative for this project. `Logs/log_0.bin` identifies
itself as `ArduPlane V4.7.0 (1511f271)` and is the stable real-log reference.

A bounded comparison found the relevant Plane-4.7.0 and Plane-4.7.1 files
byte-for-byte identical: `mode_takeoff.cpp`, `takeoff.cpp`, `servos.cpp`,
`Log.cpp`, `Plane.cpp`, `mode.cpp`, `system.cpp`, `mode.h`, `Plane.h`,
`Parameters.cpp`, `Parameters.h`, `Attitude.cpp`, `commands_logic.cpp`,
`mode_auto.cpp`, and `AP_FixedWing.h`. The ownership, launch check, rotation,
suppression, flight-stage, completion, mode-transition, and STAT semantics in
this contract are therefore stable across those two tags. This is not a
claim about unrelated Plane subsystems or later firmware.

### 2.2 Available real-log evidence

The five available logs contain 13 operational launch sequences. All 13:

- have `Armed AUTO` and `Triggered AUTO` messages;
- have those messages while the latest established mode is `MODE=13`;
- later leave TAKEOFF mode, usually for FBWA;
- contain no runtime `MISE MAV_CMD_NAV_TAKEOFF`.

The corpus therefore represents TAKEOFF-mode execution, not AUTO mission
takeoff. In particular, `AUTO` in `Armed AUTO` and `Triggered AUTO` names the
shared automatic launch-check mechanism; it does **not** prove that flight mode
AUTO (`ModeNum=10`) owned the event.

`log_0.bin` is the design-reference log. The other four logs identify as
custom Plane 4.7.0 beta builds: beta4 (`log_11`), beta7 (`log_17` and
`log_19`), and beta8 (`log_26`). They are later compatibility evidence, not
alternative design targets.

## 3. TAKEOFF-mode outer ownership

### 3.1 Successful entry and the logged start

`Plane::set_mode()` selects the prospective mode and calls `Mode::enter()`.
The generic entry path resets shared navigation/takeoff state, including
highest airspeed and `rotation_complete`. `ModeTakeoff::_enter()` then does
only two mode-local operations:

- sets `takeoff_mode_setup=false`;
- sets `have_autoenabled_fences=false`.

After `_enter()` succeeds, generic `Mode::enter()` sets
`throttle_suppressed=true` because TAKEOFF mode uses automatic throttle, and
updates the flight stage. `Plane::set_mode()` then exits the old mode and
writes the new `MODE` record.

Consequently, a valid `MODE=13` record is direct evidence that TAKEOFF-mode
entry succeeded. It occurs after `_enter()` but before the first necessarily
observable `ModeTakeoff::update()` setup. It is the strongest ordinary
DataFlash start boundary for the **outer** TAKEOFF execution. There is no
stronger dedicated “TAKEOFF mode setup started” log event.

### 3.2 First update and setup

`update_control_mode()` is a fast task and calls `ModeTakeoff::update()`.
Setup is deferred until position and home are valid. Without them, the mode
calculates normal navigation attitude, commands zero throttle at that point,
and returns without establishing the takeoff target or TAKEOFF stage.

For the normal not-already-flying path, the first usable update:

1. stores the configured `TKOFF_ALT` as the relative takeoff altitude;
2. captures the current location as the start and initial waypoint context;
3. constructs a target `TKOFF_DIST` ahead at `TKOFF_ALT`;
4. clears crash state;
5. stores `TKOFF_LVL_PITCH` as takeoff pitch;
6. sets `FlightStage::TAKEOFF`.

This is controller setup, not launch acceptance. The mode remains
`takeoff_mode_setup=false` until suppression has ended and groundspeed is high
enough to establish a useful course.

### 3.3 Outer end

TAKEOFF mode has no mode-specific `_exit()` cleanup. Nevertheless, once
`Plane::set_mode()` successfully changes to another mode, `control_mode` no
longer points to `mode_takeoff`; the new mode owns subsequent control and the
old mode's `update()` is no longer called.

The first authoritative `MODE` transition from 13 to another mode is therefore
the outer ownership end. A later `MODE=13` is a new execution. At log end,
an otherwise active window is censored; log end is not proof of normal inner
completion.

One logging-order detail matters: the new mode's `enter()` calls
`update_flight_stage()` before `Plane::set_mode()` writes the new `MODE`
record. A `STAT.Stage=NORMAL` immediately before a `MODE!=13` record can thus
be an effect of the mode change rather than independent evidence that TAKEOFF
mode completed its inner stage. Analysis must not classify that ordering by
timestamp proximity alone.

## 4. Shared automatic launch check

### 4.1 Call path in TAKEOFF mode

TAKEOFF mode does not call `auto_takeoff_check()` directly. The stable 4.7.0
path is:

```text
ModeTakeoff (automatic throttle)
  -> servo/output cycle
  -> Plane::set_throttle()
  -> Plane::suppress_throttle()
  -> special mode_takeoff branch
  -> Plane::auto_takeoff_check()
```

This shared function is why TAKEOFF mode emits messages containing `AUTO`.
The string is historical/shared mechanism wording, not a mode identifier.

### 4.2 Trigger gates

For a normal fresh launch, `auto_takeoff_check()` applies these executable
conditions:

| Gate/state | Stable 4.7.0 behavior |
|---|---|
| Armed and safety off | Otherwise all takeoff state is reset and the check fails. |
| Continuous servicing | A gap greater than 200 ms resets launch-check state (while preserving the conditional autoland direction state). |
| Rudder neutral | After rudder arming, the check waits for neutral and periodically reports that wait. |
| GPS | At least a 3D fix is required. |
| Acceleration | If `TKOFF_THR_MINACC` is nonzero, longitudinal TECS acceleration must meet it. `TKOFF_ACCEL_CNT` can require alternating positive/negative events; a gap over 500 ms resets their count. |
| Timer arm | The accepted acceleration state starts the launch timer and may emit `Armed AUTO`. With `TKOFF_THR_MINACC=0`, this arming step is reached without an acceleration gate. |
| Delay/expiry | Groundspeed acceptance waits `TKOFF_THR_DELAY * 100 ms`. The candidate expires strictly after that delay plus 100 ms, emits `Timeout AUTO` subject to report throttling, and resets. |
| Attitude | Unless disabled by the relevant flight option, pitch must be greater than -30 degrees and less than 45 degrees; non-inverted roll magnitude must not exceed 30 degrees. Rejection emits `Bad launch AUTO` and resets the candidate. |
| Groundspeed | GPS groundspeed must exceed `TKOFF_THR_MINSPD`, unless that parameter is zero. |

On acceptance, firmware emits `Triggered AUTO. GPS speed = ...`, resets the
candidate timer, initializes takeoff and throttle-max timestamps and course
error, and returns `true`. The caller then releases throttle suppression.

`Armed AUTO`, `Timeout AUTO`, and `Bad launch AUTO` describe launch-check
observations or retries inside the same outer TAKEOFF-mode execution. They do
not create new execution windows. A missing message remains missing evidence;
message rate limiting and log loss prevent reasoning from absence alone.

## 5. Physical launch-method semantics

Plane 4.7.0 has no TAKEOFF-mode enum or state identifying “wheels”, “dolly”,
“skis”, “hand”, “catapult”, “rail”, or “bungee”. These physical methods share
the same outer mode, suppression/launch detector, flight stage, and controller
functions. Source-backed differences are parameter-driven.

APT therefore prefers owned firmware events and state transitions over
sensor-derived phase inference. An acceleration-gate message does not prove an
external launch, and the GPS speed printed by the trigger does not prove a
surface takeoff. Physical classification is deliberately deferred; possible
future high-level families are **externally launched** and **surface takeoff**.

### 5.1 Rolling or surface takeoff

Wheeled runway, dolly, and similar surface runs are analytically one firmware
family unless other evidence proves a different controller configuration.

The shared launch detector still controls suppression. A common rolling
configuration disables the acceleration gate (`TKOFF_THR_MINACC=0`) and uses
the configured delay and/or groundspeed gate; that is parameter behavior, not
a separate detector.

`TKOFF_ROTATE_SPD>0` enables the rolling rotation path in
`takeoff_calc_pitch()`:

- while `auto_state.highest_airspeed < TKOFF_ROTATE_SPD`, demanded pitch is
  fixed at `TKOFF_GND_PITCH`, and TECS pitch minimum and maximum are both set
  to that ground-run pitch;
- after rotate airspeed is reached, while GPS groundspeed is no greater than
  `AIRSPEED_CRUISE`, firmware scales from a minimum 5-degree climb demand
  toward the configured takeoff pitch;
- after that path is passed, firmware sets the internal
  `rotation_complete=true` and uses the normal takeoff pitch/TECS path.

`TKOFF_ROTATE_SPD` is an airspeed threshold inside command generation. It is
not logged as a dedicated rotation event and does not prove physical rotation
or liftoff. `rotation_complete` is not exposed in `STAT`.

Consequently, current APT presentation reports rotation completion as
**Unavailable**. It must not reconstruct that internal state from an airspeed
crossing, pitch or altitude response, or `TKOFF_ROTATE_SPD` configuration.
Tail-hold, ground-roll, rotation, liftoff, and surface-departure phases remain
deferred pending known real surface-takeoff logs and authoritative evidence.

Rolling control can additionally use:

- `TKOFF_TDRAG_ELEV` and `TKOFF_TDRAG_SPD1` for initial tail hold or wheel-load
  management;
- `GROUND_STEER_ALT`, steering configuration, and the ground-steering
  controller while close to the ground;
- `LEVEL_ROLL_LIMIT` before rotation and the altitude-scaled roll restriction
  after rotation;
- `TKOFF_THR_SLEW` to moderate acceleration.

During TAKEOFF stage, pilot rudder-rate input is suppressed in the ground-yaw
controller and heading/error control is used. Ordinary logs can show attitude,
desired attitude, steering, airspeed, groundspeed, and outputs, but none is a
firmware-authored wheel-liftoff event.

### 5.2 Hand launch

Hand launch uses the same detector. Parameter documentation recommends an
acceleration gate and, for pusher aircraft, a delay and suitable minimum
groundspeed to prevent premature motor engagement. `TKOFF_ROTATE_SPD=0`
bypasses the rolling rotation branch so the takeoff pitch path is used as soon
as takeoff control runs. Firmware does not log physical hand release, and APT
must not infer it.

### 5.3 Catapult or rail launch

Catapult/rail launch also has no separate firmware state. Acceleration,
groundspeed, and delay parameters can defer motor engagement until launcher
clearance. Parameter documentation prefers acceleration plus delay over sole
reliance on GPS speed because GPS velocity lags and can be noisy.
`TKOFF_ROTATE_SPD=0` is the documented catapult setting. Mechanical launcher
release is not directly logged.

### 5.4 Bungee launch

Bungee launch is another configuration of the same detector, not another
state machine. Parameter documentation specifically identifies a larger
`TKOFF_THR_DELAY` as a way to allow the bungee to release before motor start,
and identifies `TKOFF_THR_MINACC` as applicable. No distinct “bungee
released” event exists.

### 5.5 What may be classified

Later analysis may report the configured firmware behavior—for example,
“rotation-speed path enabled” or “acceleration-gated delayed launch.” It must
not infer a physical launcher class solely from that configuration because
multiple physical methods can use the same values.

## 6. Throttle suppression and release

Entering TAKEOFF mode starts with `throttle_suppressed=true`. In the TAKEOFF
branch of `suppress_throttle()` it remains true until either:

1. the already-flying escape conditions are satisfied; or
2. `auto_takeoff_check()` returns true.

On launch-check success, `suppress_throttle()` sets
`throttle_suppressed=false`, records barometric takeoff altitude, and returns
false to the output path. Before release, `set_throttle()` normally substitutes
zero throttle, or `TKOFF_THR_IDLE` during TAKEOFF stage; configured manual
pass-through and landing-specific cases are separate output rules.

The concepts must remain separate:

| Evidence/concept | What it means |
|---|---|
| `Triggered AUTO` | The shared launch check accepted its configured gates. |
| `STAT.Sup=0` after suppressed context | Logged firmware state showing suppression is no longer active by that sample. |
| CTUN/AETR/RCOU/servo value | A controller command or output observation. |
| Motor RPM/ESC telemetry | Additional motor behavior evidence when present. |
| Physical thrust | Not established by throttle command or suppression state. |

The message and suppression change occur in one firmware call path, but their
DataFlash timestamps come from different log writes. APT must not invent
cross-stream micro-ordering when timestamps tie or records are missing.

## 7. Meaning of `Takeoff to ...`

In normal fresh TAKEOFF-mode setup, firmware initially leaves
`takeoff_mode_setup=false`. On a later `ModeTakeoff::update()`, only after:

- throttle is no longer suppressed; and
- groundspeed exceeds `GPS_GND_CRS_MIN_SPD` (5 m/s),

it emits:

```text
Takeoff to <altitude>m for <distance>m heading <direction> deg
```

It then initializes/reinitializes takeoff timing, marks setup complete, and
locks the takeoff course from the current groundspeed direction. Thus this is
a firmware-originated **post-release course/target-finalization observation**.
It is not launch detection, physical launch, rotation, or automatic takeoff
completion. It should not replace `Triggered AUTO`; the two messages represent
different state changes.

The already-flying branches use `Above TKOFF alt - loitering` or `Climbing to
TKOFF alt then loitering` instead and do not require this normal setup message.

## 8. Inner `FlightStage::TAKEOFF` phase

### 8.1 Entry and pre-trigger behavior

For a fresh TAKEOFF-mode entry with valid position/home,
`ModeTakeoff::update()` sets `FlightStage::TAKEOFF` before launch detection has
necessarily succeeded. While suppression remains active, the separate 10 Hz
`update_flight_stage()` path falls back to `NORMAL`; the next fast TAKEOFF-mode
update can set TAKEOFF again because setup is still incomplete.

Accordingly, pre-trigger logs can alternate `STAT.Stage=1` and
`STAT.Stage=3`. A Stage=1 sample alone is not proof that launch was accepted,
that throttle was released, or that the aircraft was airborne. For a later
response interval, stage evidence must be interpreted with `Triggered AUTO`
and/or `STAT.Sup=0`, not as a free-standing launch detector.

While the current update sees TAKEOFF stage, it calls:

- `takeoff_calc_roll()`;
- `takeoff_calc_pitch()`;
- `takeoff_calc_throttle()`.

Pitch and roll demands can therefore be computed before launch acceptance,
while the later output path still suppresses throttle. The useful
post-trigger response interval must not be confused with initial controller
setup.

### 8.2 Normal and abnormal transitions to `NORMAL`

For TAKEOFF mode, `ModeTakeoff::update()` changes the stage from TAKEOFF to
NORMAL through these source-defined paths:

| Path | Stable 4.7.0 condition |
|---|---|
| Altitude | Height from the captured start location reaches `TKOFF_ALT * 100 - 200 cm` (two metres below the target). |
| Distance | Distance from the captured start location reaches `TKOFF_DIST`. |
| Post-trigger takeoff timeout | `TKOFF_TIMEOUT>0`, the timer is active, and groundspeed remains below 4 m/s beyond the configured duration; firmware emits the timeout message and disarms. TAKEOFF mode also clears setup. |
| Pitch level-off timeout | `TKOFF_PLIM_SEC` level-off timing has started and then expires. |
| Already flying above target | The already-flying entry branch selects NORMAL immediately. |

Crossing `TKOFF_LVL_ALT` or the target distance while course is not yet locked
can update the target bearing/course; that update is not independently a
completion event. The actual completion test is the altitude-or-distance test
above.

`FlightStage::TAKEOFF -> NORMAL`, when proven to have occurred under continuing
TAKEOFF-mode ownership rather than as a side effect of mode exit, is the
firmware definition of **automatic takeoff-control completion** for this entry
context. It is not a derived “stable climb” event.

### 8.3 Behavior after inner completion

While stage is TAKEOFF, the takeoff-specific controllers above run. Once stage
is NORMAL, `ModeTakeoff::update()` auto-enables the applicable fences once,
uses ordinary navigation roll/pitch/throttle calculation, handles a deferred
long failsafe, and `navigate()` continues loiter navigation. Mode 13 remains
the outer owner until an actual mode transition.

## 9. `STAT` evidence and timestamp limits

Stable 4.7.0 defines `STAT` fields:

```text
TimeUS,isFlying,isFlyProb,Armed,Safety,Crash,Still,Stage,Hit,Sup
```

For this contract:

- `Stage=1` is `FlightStage::TAKEOFF`;
- `Stage=3` is `FlightStage::NORMAL`;
- `Sup=1` means throttle suppression is active;
- `Sup=0` means it is not active at the logged sample.

`Log_Write_Status()` copies the current firmware stage and suppression flag.
It is called by the 5 Hz `update_is_flying_5Hz()` task and immediately after
`set_flight_stage()` changes the stage. The immediate write makes STAT strong
state-transition evidence when retained, but the logged `TimeUS` is taken
after the in-memory assignment, and a record can be absent or dropped. The
first retained Stage=3 sample proves NORMAL state **by that sample**; it must
not be described as the exact internal transition instruction's microsecond.

Three qualifications are essential:

1. pre-trigger Stage 1/3 alternation is expected from the two firmware update
   paths described above;
2. a Stage=3 observation immediately associated with `MODE!=13` may have been
   generated by new-mode entry, so it does not independently prove inner
   completion;
3. if the relevant STAT record is absent, inner completion time remains
   unavailable rather than being invented from altitude or distance telemetry.

Altitude/distance can later corroborate or explain the transition, but using
them to manufacture a missing firmware stage event would be a separate,
explicitly derived rule.

`STAT.isFlying` is a probabilistic estimator, not physical liftoff. No normal
DataFlash field directly exposes `rotation_complete`, hand/launcher release,
wheel liftoff, or thrust.

## 10. Already-flying TAKEOFF-mode entry

Before normal fresh setup, TAKEOFF mode checks whether Plane already considers
itself flying, has done so for more than 10 seconds, and has groundspeed above
3 m/s.

- If already at or above `TKOFF_ALT`, firmware emits `Above TKOFF alt -
  loitering`, sets the loiter target to current location, completes setup, and
  selects NORMAL stage.
- If below `TKOFF_ALT`, it emits `Climbing to TKOFF alt then loitering`, builds
  a climb/loiter target from current position, completes setup, and selects
  TAKEOFF stage.

Separately, `suppress_throttle()` has an already-flying escape that can release
suppression without `Triggered AUTO`. It requires the aircraft to be considered
flying for more than the larger of five seconds or `TKOFF_THR_DELAY + 2 s`, to
be more than 5 m above the adjusted reference, to have absolute pitch below
30 degrees, and to have GPS movement (at least 2D fix and 5 m/s groundspeed).
Therefore `Triggered AUTO` is not mandatory evidence for the already-flying
path.

This is an edge case for entering Mode 13 in flight, not a physical launch
method. It must be represented separately and must not redefine the normal
fresh-arm/surface-or-non-surface execution model.

Current APT note: the stable reference log contains an
`Above TKOFF alt - loitering` observation in an already-airborne Mode-13
window, but the current execution model does not yet promote that message into
an owned already-airborne event for normal detailed phase output. That support
is a bounded deferred event-model task. Until then, APT must not manufacture
already-airborne status from missing trigger evidence or sensor inference.

## 11. AUTO mission `NAV_TAKEOFF` as a separate context

AUTO mission takeoff shares the following with TAKEOFF mode:

- `suppress_throttle()` and `auto_takeoff_check()`;
- the `Armed AUTO`, `Timeout AUTO`, `Bad launch AUTO`, and `Triggered AUTO`
  messages;
- takeoff roll, pitch, throttle, rotation, tail-hold, roll-limit, suppression,
  and post-trigger timeout machinery;
- relevant shared takeoff parameters.

Its ownership and completion differ:

| Concern | TAKEOFF mode | AUTO mission `NAV_TAKEOFF` |
|---|---|---|
| Direct start evidence | Successful `MODE=13` | Runtime `MISE CId=22` under established AUTO ownership, when retained |
| Target altitude/pitch | `TKOFF_ALT` and `TKOFF_LVL_PITCH` | Mission item altitude and `p1` pitch; nonpositive pitch becomes 4 degrees |
| Course/target message | `Takeoff to ...` after suppression release and >5 m/s | `Holding course ...` may establish mission course |
| Normal completion | TAKEOFF stage becomes NORMAL at altitude-minus-2 m or distance; mode continues | `verify_takeoff()` exceeds mission altitude or completes pitch-level-off timeout, emits `Takeoff complete`, and allows mission advance |
| Outer ownership end | First transition away from Mode 13 | First loss of AUTO/NAV_TAKEOFF ownership: mission advance/restart, mode exit, applicable timeout/disarm, or log end |

Stored `CMD` mission definitions are configuration, not runtime execution
evidence. The five current logs have no `MISE NAV_TAKEOFF`, so this AUTO entry
context does not describe their 13 launches.

This document does not prescribe whether later code should use shared base
classes or separate detectors. It only records which firmware semantics are
common and which ownership rules are not.

## 12. Parameter classification

All interpretation must use APT `ParameterHistory.value_at(name, time_us)` so
later parameter changes cannot rewrite earlier behavior. This table classifies
firmware applicability; it does not recommend values.

| Parameter/input | Classification | Firmware role |
|---|---|---|
| `TKOFF_THR_MINACC` | Shared launch detector; especially non-surface configuration | Longitudinal acceleration gate; zero disables it. |
| `TKOFF_ACCEL_CNT` | Shared launch detector; especially non-surface configuration | Count/polarity sequence of acceleration events used to arm the timer. |
| `TKOFF_THR_DELAY` | Shared launch detector; especially non-surface configuration | Delay in deciseconds before speed acceptance; hand/catapult/bungee can use it for clearance. |
| `TKOFF_THR_MINSPD` | Shared launch detector | GPS groundspeed gate for suppression release; zero disables the speed threshold. |
| takeoff-attitude-check flight option | Shared launch detector | Enables/disables pitch/roll rejection. |
| `TKOFF_TIMEOUT` | Shared by TAKEOFF mode and AUTO mission | Post-trigger failure to reach 4 m/s can emit timeout and disarm. |
| `TKOFF_THR_IDLE` | Shared by both entry contexts | Optional throttle output while TAKEOFF stage remains suppressed. |
| `TKOFF_THR_MIN`, `TKOFF_THR_MAX`, `TKOFF_OPTIONS` | Shared by both entry contexts | Takeoff throttle limits/range behavior. |
| `TKOFF_THR_MAX_T` | Shared by both entry contexts | Duration for forcing the takeoff maximum after its timer starts. |
| `TKOFF_THR_SLEW` | Shared by both entry contexts; often material to rolling performance | Takeoff throttle slew; zero uses normal slew and -1 disables limiting. |
| `TKOFF_ROTATE_SPD` | Shared controller; rolling/surface behavior | Enables airspeed-based ground-pitch/rotation path when nonzero. |
| `TKOFF_GND_PITCH` | Shared controller; rolling/surface behavior | Pitch demand below rotate speed. Despite its `TKOFF_` mode group location, shared `takeoff_calc_pitch()` uses it in both contexts. |
| `TKOFF_TDRAG_ELEV`, `TKOFF_TDRAG_SPD1` | Shared rolling/surface behavior | Tail hold/wheel-load behavior before the configured airspeed. |
| `GROUND_STEER_ALT`, `GROUND_STEER_DPS` and steering configuration | Shared rolling/surface behavior | Availability and response of ground steering; not a liftoff detector. |
| `TKOFF_PLIM_SEC` | Shared controller, with context-specific completion effect | Reduces pitch minimum near target and supplies a level-off timeout. TAKEOFF mode selects NORMAL; AUTO verification completes the mission item. |
| `TKOFF_LVL_ALT`, `LEVEL_ROLL_LIMIT`, normal roll limit | Shared by both entry contexts | Level/altitude-scaled roll restriction during automatic takeoff. |
| `TKOFF_ALT` | TAKEOFF-mode target/completion; also used by the shared roll limiter | Mode target altitude and one completion threshold; also caps the altitude over which `takeoff_calc_roll()` transitions from `LEVEL_ROLL_LIMIT` toward the normal roll limit in both entry contexts. |
| `TKOFF_DIST` | TAKEOFF-mode-specific | Mode loiter distance, course/target placement, and one completion threshold. |
| `TKOFF_LVL_PITCH` | TAKEOFF-mode-specific | Mode takeoff pitch stored in `auto_state.takeoff_pitch_cd`. |
| Mission `NAV_TAKEOFF` altitude and `p1` | AUTO-mission-specific | Mission completion altitude and takeoff pitch. |

Physical launch type must not be inferred solely from this table. For example,
an acceleration-gated delayed configuration can serve hand, rail, or bungee
launches.

## 13. Evidence and ownership contract

APT must establish the entry context and outer owner before interpreting
events or extracting future metrics:

```text
establish outer ownership
  -> identify firmware events and stage/suppression state
  -> establish a defensible inner response interval
  -> select valid observations within that interval
  -> calculate explicitly defined derived metrics
```

### 13.1 Direct versus derived evidence

| Observation | Classification | Defensible meaning |
|---|---|---|
| `MODE=13` | Firmware event | Successful TAKEOFF-mode entry / outer start. |
| `MODE!=13` following Mode 13 | Firmware event | Outer ownership ended. |
| Runtime `MISE NAV_TAKEOFF` | Firmware event | AUTO mission item began, subject to established AUTO ownership. |
| `Armed AUTO`, `Timeout AUTO`, `Bad launch AUTO` | Firmware observations | Shared launch-check arming/retry state. |
| `Triggered AUTO` | Strong firmware event | Shared launch check accepted configured gates. |
| `Takeoff to ...` | Firmware observation | TAKEOFF-mode course/target setup finalized after suppression release and sufficient groundspeed. |
| `STAT.Stage`, `STAT.Sup` | Firmware state observations | Stage and suppression state by the sample, with the qualifications in section 9. |
| `Takeoff complete ...` | Strong firmware event | AUTO mission verifier completed `NAV_TAKEOFF`; not TAKEOFF-mode completion. |
| ATT/CTUN/GPS/ARSP/BARO | Logged measurements/state | Aircraft/controller context subject to source validity and owned sampling. |
| AETR/RCOU/servo output | Command/output | Output behavior, not aerodynamic response or thrust. |
| Physical release, rotation, liftoff, thrust | Not directly available | Must not be asserted by this initial model. |

### 13.2 Finalization rules

- The first authoritative outer termination closes the execution.
- Mode exit is a hard boundary for TAKEOFF mode.
- Re-entry creates a new execution; windows are never stitched.
- Events at a shared boundary require source-supported ownership; timestamp
  equality alone supplies no order.
- A sample after termination cannot be borrowed for nearest-event lookup or to
  complete persistence.
- Log end is inclusive of the final retained observation but is a censored
  termination, not normal completion.
- Missing trigger, STAT, completion, or output evidence remains missing.
- All event-time parameter evidence uses absolute BIN `TimeUS` microseconds.

## 14. Stable and beta compatibility findings

### 14.1 Plane-4.7.0 to Plane-4.7.1

The relevant source files listed in section 2.1 are identical between the two
stable tags. No material change was found in:

- TAKEOFF-mode entry or exit ownership;
- shared launch detection and its messages;
- rolling rotation or ground-pitch behavior;
- throttle suppression/release;
- TAKEOFF-stage entry or completion;
- already-flying handling;
- `STAT.Stage` or `STAT.Sup` logging;
- AUTO mission takeoff behavior used by this contract.

These semantics may therefore be treated as the project's audited stable
Plane 4.7.x contract.

### 14.2 Corpus beta builds

The exact relevant files at the beta4 (`571e8c7b`), beta7 (`97775f82`), and
beta8 (`cb872be0`) commits recorded by the four beta logs were compared with
stable 4.7.0. `mode_takeoff.cpp`, `takeoff.cpp`, `servos.cpp`, `Log.cpp`,
`Parameters.cpp`, `mode.cpp`, `system.cpp`, and `Attitude.cpp` are identical.
Beta7 and beta8 also have the same audited `Plane.cpp`. Beta4 differs only in
the scheduler rate/budget for the logger periodic task (50 Hz/400 us there,
400 Hz/300 us in stable), not in `set_flight_stage()`, stage selection,
suppression, or launch ownership.

Plane 4.7 release history also records “Throttle slew fixed during first
takeoff” in beta2 (PR 32381). The fix ensures the slew limiter is allocated
even if initially disabled. It can change throttle-response measurements in
beta1 or earlier behavior, but it does not redefine Mode 13 ownership, launch
acceptance, suppression release, rotation state, or stage completion. Every
available beta corpus log is beta4 or later and therefore includes that fix.

Policy remains:

1. develop against stable 4.7.0 semantics;
2. validate first against `log_0.bin`;
3. run the same model unchanged across the four beta logs;
4. record any demonstrated incompatibility;
5. add no beta-specific logic otherwise.

Performance results must still retain the firmware identity. A logging-service
or throttle-slew implementation difference can affect sampling or measured
response without changing semantic ownership.

## 15. Historical prototype revision requirements — implemented

The requirements below were identified by the original firmware audit and have
since been incorporated into the current TAKEOFF-mode execution model. They are
retained as the historical semantic contract rather than as outstanding work:

- TAKEOFF-mode executions must be discoverable from Mode 13 entry/exit; they
  must not require AUTO mode or runtime `MISE NAV_TAKEOFF`.
- `Triggered AUTO` must be owned by the established entry context and must not
  itself imply Mode 10.
- the model must distinguish outer TAKEOFF-mode ownership from inner
  TAKEOFF-stage completion;
- `Takeoff complete` and mission advance are AUTO-mission completion evidence,
  not TAKEOFF-mode completion evidence;
- the normal reader must retain `STAT` before direct stage/suppression evidence
  can be used (the current landing reader configuration does not request it);
- pre-trigger stage alternation and mode-exit-caused Stage=NORMAL observations
  need explicit tests;
- rolling rotation remains controller context, not a directly logged event;
- AUTO mission support and its strict `MISE`/AUTO ownership rules should remain
  available as the separate context described in section 11.

These requirements define semantics rather than a required public API or class
hierarchy. Future changes must preserve them unless a new firmware/source audit
justifies a deliberate revision.

## 16. Unresolved evidence limitations

- DataFlash has no direct physical release, launcher-release, rotation,
  liftoff, or thrust event for this conventional Plane path.
- `rotation_complete` is internal and absent from `STAT`.
- `Triggered AUTO` can be missing because of logging/reporting loss; absence is
  not proof that suppression never ended.
- `STAT` records can be absent or dropped, and their timestamp is an observed
  log time rather than the exact internal assignment instruction.
- Pre-trigger Stage 1/3 alternation prevents naive “first Stage=TAKEOFF” start
  detection.
- A Stage=NORMAL log emitted during a mode transition can be mistaken for
  inner completion unless the mode-transition call order is respected.
- Physical launch class cannot be recovered uniquely from parameters.
- The current real-log corpus has no AUTO mission `NAV_TAKEOFF`, no asserted
  rolling takeoff reference, and no direct evidence for validating physical
  rotation semantics.

These limitations do not block the current TAKEOFF-mode ownership/stage model.
They do constrain event naming and timing precision.

### 16.1 Explicit deferred analyser work

The following are intentionally deferred rather than inferred:

- **Already-airborne phase reporting:** promote the owned
  `Above TKOFF alt - loitering` / related already-flying firmware observation
  into the execution model before displaying that context in the normal phase
  report.
- **Rotation completion:** keep `Rotation complete = Unavailable` in normal
  phase evidence while `auto_state.rotation_complete` lacks authoritative
  retained log exposure. Do not reconstruct it from airspeed, pitch, altitude,
  or `TKOFF_ROTATE_SPD`.
- **Surface-specific phases:** tail hold, ground roll, rotation, liftoff, and
  surface departure wait for known surface-takeoff logs and source-backed
  authoritative evidence.
- **Physical launch family:** do not currently classify hand/bungee/catapult/
  rail versus wheeled/float/ski/dolly. Possible future high-level families are
  externally launched and surface takeoff, but classification requires a
  separate evidence contract.
- **Presentation wording:** a future presentation-only change may rename
  `Takeoff completion` to `TAKEOFF control` while preserving the existing
  completion semantics and values.

These deferred items must not weaken the primary rule: prefer owned firmware
events/state over sensor-derived phase assertions.

## 17. Source references

Primary Plane-4.7.0 sources:

- [`mode_takeoff.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/mode_takeoff.cpp): mode parameters, entry, setup, `Takeoff to ...`, stage completion, post-completion behavior, already-flying path.
- [`takeoff.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/takeoff.cpp): shared launch detector, roll/pitch/throttle control, rotation, tail hold, level-off and post-trigger timeouts.
- [`servos.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/servos.cpp): throttle slew, suppression, release, idle/output handling.
- [`mode.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/mode.cpp) and [`system.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/system.cpp): generic mode entry/exit and MODE logging order.
- [`Plane.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/Plane.cpp): scheduler, control-mode update, flight-stage selection, immediate STAT write on stage changes.
- [`Log.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/Log.cpp): STAT structure and field definitions.
- [`AP_FixedWing.h`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/libraries/AP_Vehicle/AP_FixedWing.h): numeric flight-stage definitions.
- [`Attitude.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/Attitude.cpp): conventional ground steering behavior.
- [`Parameters.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/Parameters.cpp): launch, rotation, throttle, taildragger, roll, and timeout parameter semantics.
- [`commands_logic.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/commands_logic.cpp) and [`mode_auto.cpp`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/mode_auto.cpp): separate AUTO mission `NAV_TAKEOFF` setup, control, and verification.
- [`ReleaseNotes.txt`](https://raw.githubusercontent.com/ArduPilot/ardupilot/Plane-4.7.0/ArduPlane/ReleaseNotes.txt): bounded beta compatibility history, including the beta2 first-takeoff throttle-slew fix.
- [PR 32381](https://github.com/ArduPilot/ardupilot/pull/32381): scope and mechanism of the beta2 first-takeoff slew-limiter allocation fix.

Stable compatibility reference:

- [Plane-4.7.1 tag](https://github.com/ArduPilot/ardupilot/tree/Plane-4.7.1)

Before applying this contract to another firmware family, re-audit these
functions rather than extrapolating from current `master`.
