# ArduPlane Takeoff Analysis — Performance Evidence and Metric Contract

**Scope:** conventional fixed-wing ArduPlane TAKEOFF mode and AUTO mission
`NAV_TAKEOFF` in stable Plane 4.7.x

**Primary source basis:** Plane-4.7.0

**Stable log basis:** `Logs/log_0.bin`, ArduPlane V4.7.0 (`1511f271`)

**Status:** TAKEOFF-mode execution, event-led phase evidence, and bounded
performance metrics are implemented and validated on the stable reference log;
deferred follow-ups are recorded below

## 1. Purpose and limits

This document defines the DataFlash evidence and temporal rules for a first,
bounded takeoff-performance implementation. The execution and state semantics
in `firmware_semantics.md` remain authoritative and are not redefined here.

The analysis describes logged firmware demand, estimated aircraft state, and
commanded output. It does not infer physical hand release, wheel rotation,
liftoff, physical actuator position, motor response, thrust, or flight quality.
It does not assign safe/unsafe or good/bad scores.

Plane-4.7.0 source is the semantic authority. Observations from `log_0.bin`
confirm availability and resolution only; metric definitions must not be tuned
to its three normal launch executions.

## 2. Current APT exposure and stable-log inventory

`FlightReader` retains the message names configured in `Config/landing.yaml`
and always adds `MISE`, `PARM`, and `STAT`. The normal reader therefore already
exposes `ATT`, `CTUN`, `ARSP`, `GPS`, `BARO`, `STAT`, and `XKF1` from the stable
log. The BIN also contains `POS`, `TECS`, `AETR`, `RCOU`, and `AOA`, but the
current normal configuration does not retain them.

Rates below are observed medians from `log_0.bin`, not guaranteed logger
contracts. Actual rates depend on logging configuration and scheduler load.

| Message | Normal reader | Relevant fields | Observed interval/rate | Evidence class and units |
|---|---:|---|---:|---|
| `ATT` | yes | `DesRoll`, `Roll`, `DesPitch`, `Pitch` | about 40 ms / 25 Hz | Navigation attitude targets and AHRS-estimated attitude, degrees |
| `CTUN` | yes | `NavRoll`, `Roll`, `NavPitch`, `Pitch`, `ThO`, `ThD`, `As`, `AsT` | about 40 ms / 25 Hz | Co-sampled navigation demand, AHRS response, normalized throttle command/demand in percent, and equivalent-airspeed estimate in m/s |
| `ARSP` | yes | `I`, `Airspeed`, `U`, `H`, `Hp`, `TR`, `Pri` | about 100 ms / 10 Hz | Per-sensor raw airspeed result and health/use evidence; `Airspeed` is m/s |
| `GPS` | yes | `I`, `Status`, `Spd`, `VZ`, `U` | about 200 ms / 5 Hz | Receiver-measured ground velocity; `Spd` and `VZ` are m/s |
| `BARO` | yes | `I`, `Alt`, `AltAMSL`, `CRt`, `H` | about 100 ms / 10 Hz | Per-sensor calculated altitude and derived primary-barometer climb rate; metres and m/s |
| `STAT` | yes | `Stage`, `Sup`, `Armed` | about 200 ms / 5 Hz, plus immediate state writes | Firmware state observations; unitless enums/booleans |
| `XKF1` | yes | `C`, `VN`, `VE`, `VD`, `PD` | about 40 ms / 25 Hz | Per-EKF-core estimated NED state; velocity in m/s and position in m |
| `POS` | no | `Alt`, `RelHomeAlt`, `RelOriginAlt` | about 40 ms / 25 Hz | Canonical AHRS vehicle position; metres |
| `TECS` | no | `h`, `dh`, `hin`, `hdem`, `dhdem`, `spdem`, `sp`, `th`, `ph` | about 100 ms / 10 Hz while TECS logs | TECS internal estimated state and outputs; height m, rates/speeds m/s, throttle fraction, pitch radians |
| `AETR` | no | `Ail`, `Elev`, `Thr`, `Rudd`, `Flap`, `Steer` | about 40 ms / 25 Hz | Normalized pre-mixer servo-function commands; surfaces -4500..4500 and throttle -100..100 |
| `RCOU` | no | `C1` through `C14` | about 40 ms / 25 Hz | Values read from hardware output channels, PWM microseconds; command evidence, not feedback |
| `AOA` | no | `AOA`, `SSA` | about 100 ms / 10 Hz | AHRS-estimated angle of attack and sideslip, degrees; not needed for the first metric slice |

The primary source definitions are Plane's
[`Log.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Log.cpp),
[`Attitude.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Attitude.cpp),
[`takeoff.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/takeoff.cpp),
[`servos.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/servos.cpp),
and the library log structures for
[`ATT`/`POS`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_AHRS/LogStructure.h),
[`GPS`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_GPS/LogStructure.h),
and
[`BARO`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_Baro/LogStructure.h).

## 3. Pitch demand and response

### 3.1 Source semantics

Plane constructs both `ATT.DesPitch` and `CTUN.NavPitch` from
`nav_pitch_cd`. `ATT.Pitch` is the AHRS pitch attitude. `CTUN.Pitch` is
`ahrs.pitch_sensor - PTCH_TRIM_DEG * 100`, so it is expressed in the same
trim-relative convention described for `CTUN.NavPitch`.

The fixed-wing pitch controller's final demanded pitch is:

```text
nav_pitch_cd
  + PTCH_TRIM_DEG * 100
  + scaled_throttle_output * KFF_THR2PTCH
```

No single `ATT` or `CTUN` field logs that final expression. Consequently:

- `ATT.DesPitch` and `ATT.Pitch` are not directly comparable when
  `PTCH_TRIM_DEG` is nonzero;
- `CTUN.NavPitch` and `CTUN.Pitch` are co-sampled and directly comparable in
  the trim-relative navigation-demand frame;
- their difference is not the exact controller pitch error when
  `KFF_THR2PTCH` is nonzero.

### 3.2 Selected evidence

Use `CTUN.NavPitch` as **navigation demanded pitch** and `CTUN.Pitch` as
**trim-relative achieved pitch**, both in degrees. This is the preferred first
pair because the fields share a timestamp and reference convention.

Do not label `CTUN.NavPitch` as the final attitude-controller demand. A pitch
tracking-error metric is valid without reconstruction only when event-time
`KFF_THR2PTCH == 0` and post-launch TECS-demand freshness is established as
specified in section 17. Reconstruction for nonzero feed-forward is deferred
because the exact controller-cycle throttle value is not logged as part of the
same CTUN pitch observation.

## 4. Roll demand and response

Plane logs `nav_roll_cd` as both `ATT.DesRoll` and `CTUN.NavRoll`; achieved
roll is the AHRS roll estimate. Unlike pitch, the normal fixed-wing roll
controller compares `nav_roll_cd` directly with `ahrs.roll_sensor` and has no
corresponding trim or throttle-to-pitch term.

Use the co-sampled `CTUN.NavRoll` and `CTUN.Roll` fields, in degrees. They are
the preferred directly comparable demanded/achieved pair. During TAKEOFF,
`takeoff_calc_roll()` applies the source-defined level-altitude and rotation
limits before assigning `nav_roll_cd`; the logged demand is therefore the
post-limit navigation roll demand. System-identification or VTOL controller
paths remain outside this fixed-wing contract.

## 5. Throttle evidence hierarchy

Throttle evidence must retain these distinctions:

1. `Triggered AUTO` is the launch-check acceptance event.
2. `STAT.Sup` changing to zero is the observed suppression-release event.
3. `CTUN.ThD` is `AP_TECS::get_throttle_demand()`: the speed/height
   controller demand in percent, normally 0..100 but capable of negative
   values where reverse thrust is configured.
4. `CTUN.ThO` is the current scaled throttle-function output in percent after
   the Plane output path has applied applicable suppression, battery
   compensation, and takeoff/normal throttle limits. `AETR.Thr` reads the same
   normalized throttle function at the pre-mixer presentation layer.
5. `RCOU.Cn` is the hardware output-channel command in PWM microseconds. The
   throttle channel must be resolved from event-time `SERVOx_FUNCTION`, and
   PWM interpretation requires that channel's min/max/trim/reversal and output
   configuration.
6. None of these is physical thrust, ESC telemetry, motor speed, or actuator
   feedback.

`CTUN.ThO` is the best already-retained evidence for final normalized throttle
command. `RCOU` is the best evidence of the value sent toward the configured
ESC/servo, but it requires one additional retained message family and
parameter-aware channel interpretation. `CTUN.ThD` is useful controller
context, not a substitute for post-suppression output.

Thresholds of 50% or 90% are arbitrary unless the question explicitly asks
for those fractions. “Time to commanded takeoff throttle” is potentially
useful later, but its target must be derived at event time from takeoff
throttle limits/options, the max-throttle timer, and slew behavior. The first
slice should report suppression timing and observed commands without claiming
time to useful throttle or thrust.

## 6. Airspeed and groundspeed

### 6.1 Airspeed

Use `CTUN.As`, in m/s, as the primary **controller airspeed estimate** and
retain `CTUN.AsT` with every value. Plane obtains it from `AHRS::airspeed_EAS`:

| `AsT` | Meaning |
|---:|---|
| 0 | no new/usable estimate |
| 1 | airspeed sensor |
| 2 | DCM synthetic estimate |
| 3 | EKF3 synthetic estimate |
| 4 | simulation |

This field is equivalent airspeed and may be measured or synthesized. Accept
only finite, nonnegative `As` values with `AsT != 0`; otherwise airspeed
evidence is unavailable.

`ARSP.Airspeed` is raw per-sensor evidence rather than the final controller
selection. If sensor-specific corroboration is later exposed, accept only the
row for the primary/used sensor (`I == Pri`, `U == 1`) with `H == 1` and a
finite, nonnegative value. Do not assume that a raw sensor row was accepted by
AHRS merely because it exists.

### 6.2 Groundspeed

Use `GPS.Spd`, in m/s. When `U` exists, only rows with `U == 1` are active;
otherwise retain the established APT compatibility behavior of using all GPS
rows. Require at least a 3D fix (`Status >= 3`) and a finite, nonnegative
speed. Preserve the selected receiver instance and sample timestamp.

The launch-check speed printed in `Triggered AUTO` is firmware event text,
whereas `GPS.Spd` is independently sampled receiver telemetry. They need not
match exactly. Do not interpolate GPS to force agreement with the event text
or with faster CTUN samples.

### 6.3 Configured-minimum airspeed event metrics

The authoritative `AIRSPEED_MIN` event is the existing first owned CTUN
observation whose usable controller airspeed satisfies the `AIRSPEED_MIN`
value effective at that CTUN row. Its `TimeUS`, `As`, `AsT`, and event-time
parameter value are shared by every metric below; do not run a second crossing
detector or substitute a nearby row.

**Trigger → AIRSPEED_MIN** is the duration from the firmware launch trigger to
that qualifying CTUN observation. This is the existing time-to-minimum metric
under a more explicit human-facing label; its analytical semantics do not
change.

**Altitude Δ at AIRSPEED_MIN** uses `POS.RelHomeAlt` and the same trigger
baseline as the other altitude-delta metrics. Select the latest finite POS
sample at or after the trigger and at or before the qualifying CTUN timestamp,
then subtract the latest valid owned POS baseline at or before the trigger.
The signed result is metres, and a negative result is valid evidence. If the
trigger baseline or the causal event-time POS sample is unavailable, the metric
is unavailable. Do not interpolate POS, substitute another altitude family,
or use a post-event sample.

**Throttle → AIRSPEED_MIN** is the qualifying CTUN `TimeUS` minus the observed
throttle-unsuppression event `TimeUS`, expressed in seconds. Both observations
must belong to the same TAKEOFF execution, and the qualifying airspeed
observation must be at or after unsuppression. Missing evidence or reversed
time order makes the metric unavailable; do not clamp a negative duration to
zero or interpolate either boundary.

Normal presentation renders these two event-to-event quantities as durations
without a leading plus sign. Event offsets in the execution timeline remain
trigger-relative and retain their existing leading-plus convention.

### 6.4 Event-led phase presentation

The detailed report separates firmware-owned phase evidence from configuration
and derived performance. `Armed AUTO, xaccel = ...` is observed
acceleration-gate evidence only when the event belongs to the execution and
the event-time `TKOFF_THR_MINACC` value enables that gate. It is not evidence of
a hand, bungee, catapult, rail, or other physical launch method. A configured
gate without an owned `Armed AUTO` event remains **Configured**, not Observed;
in that case configuration is evaluated at the trigger.

`Triggered AUTO. GPS speed = ...` remains the authoritative trigger event and
its printed speed is firmware-message evidence at that trigger. It is not a
rotation speed and does not prove a rolling or other surface takeoff. Throttle
release, the configured-minimum airspeed observation, and TAKEOFF-stage
completion reuse their existing owned event/state and metric semantics; the
phase presentation does not run parallel detectors.

Plane internally tracks `rotation_complete`, but current retained APT evidence
does not expose that state authoritatively. The report therefore shows rotation
completion as **Unavailable** rather than inferring it from
`TKOFF_ROTATE_SPD`, airspeed, pitch, or altitude. Tail hold, ground roll,
rotation, liftoff, and surface departure are likewise deferred until known
surface-takeoff logs and authoritative evidence support them.

Physical launch classification is deliberately deferred. Future high-level
families may distinguish externally launched from surface takeoff, but neither
configuration nor sensor traces establish those families in the current
analysis. An already-airborne TAKEOFF-mode entry is a separate execution
context, not a launch family.

The phase-report label is `TAKEOFF control`, with the existing values
`Completed` and `Mode exit before completion`. The label describes inner
automatic TAKEOFF-control completion rather than the outer Mode-13 execution;
detector and status semantics are unchanged.

Explicit owned `Above TKOFF alt - loitering` and `Climbing to TKOFF alt then
loitering` events identify the two firmware already-flying Mode-13 entry
branches. Their compact context report does not substitute Mode-13 entry for a
launch trigger, so trigger-dependent performance remains unavailable. Missing
`Triggered AUTO` alone is never already-airborne evidence.

## 7. Altitude and climb/sink evidence

### 7.1 Altitude

The preferred source is `POS.RelHomeAlt`, in metres. `POS` is the canonical
AHRS vehicle position, and `RelHomeAlt` is explicitly relative to home. It is
the closest logged representation of the position frame used by Plane's
takeoff navigation logic and is available at about 25 Hz in `log_0.bin`.

Use differences within `POS.RelHomeAlt` only:

- trigger baseline: the latest valid owned sample at or before the trigger;
- minimum relative altitude: the minimum valid strictly post-trigger sample
  minus that baseline;
- altitude at `AIRSPEED_MIN`: the latest valid sample at or after the trigger
  and at or before the qualifying CTUN observation, minus that baseline;
- endpoint gain: the latest valid owned sample at or before the endpoint minus
  the same baseline.

Do not mix `POS.RelHomeAlt`, `POS.Alt`, `BARO.Alt`, `BARO.AltAMSL`, or GPS
altitude in one delta. If `POS` is unavailable, the POS-based metric is
unavailable; a separately named BARO-derived result may be added later, but it
must not be a silent fallback.

`BARO.Alt` is usable sensor-relative corroboration when restricted to one
healthy instance, and `BARO.AltAMSL` is an AMSL estimate. Neither is the
canonical fused takeoff navigation height. CTUN has no altitude field.

The implemented POS-based metrics therefore retain `POS.RelHomeAlt` as their
authoritative altitude family. Do not silently replace that evidence with a
rangefinder result.

#### 7.1.1 Deferred rangefinder AGL comparison

A future low-altitude takeoff metric should investigate Plane's `RFNS.HE`
(`rangefinder_state.height_estimate`) as optional height-above-ground evidence.
Plane 4.7.0 logs `RFNS.HE` directly, and its rangefinder update path derives
`height_estimate` from a range measurement corrected for sensor orientation and
aircraft attitude before any applicable terrain correction.

This work is deliberately deferred and must not change the meaning of the
existing **Altitude Δ at AIRSPEED_MIN** metric. The first implementation should
prefer a separately named comparison such as **AGL at AIRSPEED_MIN** or
**AGL Δ at AIRSPEED_MIN**, then validate it against `POS.RelHomeAlt` on real
takeoffs.

Before implementation, define and test:

- whether the metric is absolute `RFNS.HE` at the authoritative AIRSPEED_MIN
  event or a delta from an owned pre/at-trigger rangefinder baseline;
- which `RFNS.InRng` / source-validity evidence is required, especially when
  the aircraft begins stationary close to the ground;
- causal sample selection at or before the AIRSPEED_MIN event, with no future
  sample and no interpolation;
- behavior when RFNS is absent, not in range, points away from the ground, or
  leaves range before AIRSPEED_MIN;
- the effect of sloping/uneven terrain: RFNS describes the surface below the
  aircraft, whereas `POS.RelHomeAlt` is home-relative vehicle position;
- sensor mounting-height implications for an absolute AGL reading.

Do not use raw `RFND.Dist` as a silent substitute when the Plane-owned
attitude-corrected `RFNS.HE` evidence is available. Preserve both sources and
their different meanings if both are later reported.

Source basis:
[`ArduPlane/Log.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Log.cpp)
and
[`ArduPlane/altitude.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/altitude.cpp).

### 7.2 Climb and sink

`TECS.dh`, in m/s, is the preferred controller-context climb-rate evidence.
TECS uses EKF NED vertical velocity when available and otherwise a
barometer/inertial complementary filter. It is an estimate used by the energy
controller, not a direct sensor measurement. `TECS` must be retained before
using this field.

`BARO.CRt` is a directly logged but derived primary-barometer climb rate in
m/s and is already retained. `GPS.VZ` is lower-rate receiver evidence whose
NED/down sign convention is unsuitable for silent substitution. `XKF1.VD`
is per-core NED down velocity; selecting the owning EKF lane robustly is more
work than this first slice warrants.

Do not differentiate raw altitude samples to manufacture climb rate. That
would amplify noise and require an arbitrary filter/window. Defer climb-rate
extrema and summaries until `TECS` retention and robust aggregation semantics
are deliberately added. Initial decrease/increase is already answered more
defensibly by the POS altitude-delta metrics.

## 8. Performance intervals

There is no universal takeoff-performance window.

### 8.1 Launch-response interval

```text
Triggered AUTO -> target/course finalization
```

Use this interval for immediate response: launch timing, demanded/achieved
attitude, roll excursion, initial speed development, and initial altitude
movement. If either boundary is missing, these interval metrics are
unavailable.

### 8.2 Automatic takeoff-control interval

```text
Triggered AUTO -> TAKEOFF-control completion
```

Use this interval when the inner `FlightStage::TAKEOFF -> NORMAL` completion
is available. It owns takeoff-controller response and normal completion gain.

### 8.3 Censored automatic-control interval

When no inner completion is observed before the outer Mode-13 exit:

```text
Triggered AUTO -> outer Mode-13 exit
```

This is a censored observed-control interval. Report its censoring and end
reason. It may support “observed before exit” extrema and an explicitly
censored altitude delta, but must not be called time/gain to completion.

### 8.4 Pre-trigger context

A later implementation may define a short context interval ending at the
trigger for baselines. Pre-trigger samples may establish a causal event-time
baseline but may never participate in post-trigger minima, maxima, response
times, or persistence.

## 9. Sampling and ownership rules

All timestamps are absolute DataFlash `TimeUS` microseconds.

Apply these rules per signal family rather than searching for a globally
nearest row:

1. **Event-time state:** use the latest valid sample at or before the event,
   constrained to the owning execution. Preserve its timestamp and report or
   retain sample age. If no owned prior sample exists, the value is
   unavailable. A future sample must not rewrite event-time state.
2. **First observed response:** where a metric is explicitly defined this way,
   use the first valid sample at or after the causal event and before the next
   ownership boundary. Its own sample timestamp is the observation time; do
   not backdate it to the event.
3. **Interval extrema/aggregates:** use only valid samples strictly after the
   start and strictly before a cross-message end boundary. Equal-timestamp
   cross-stream order is not retained by APT and must not be invented.
4. **Endpoint state:** use the latest valid owned sample at or before the
   endpoint. Preserve sample time and age. Do not use a post-end sample.
5. **Same-row comparisons:** prefer co-sampled fields, notably the CTUN
   demand/response pairs. Do not nearest-neighbor join independent streams and
   present the result as simultaneous.
6. **No first-pass interpolation:** do not interpolate ATT/CTUN, GPS, airspeed,
   altitude, throttle, or state transitions. Sampling resolution is part of
   the evidence and must remain visible.
7. **Validity:** timestamps and numeric values must be finite and rows must
   meet the family-specific health/instance rules above. Missing or unusable
   evidence yields unavailable, not zero.
8. **Boundary clipping first:** filter to the owning execution and metric
   interval before selecting samples or calculating extrema. Later samples
   cannot affect a finalized execution.

A stale-value limit should not be invented from `log_0.bin`. If implementation
requires a maximum event-time sample age, it must be a documented,
message-specific evidence rule derived from the configured/observed logging
cadence, and the actual age must still be retained.

## 10. Candidate metric disposition

### 10.1 Recommended first implementation

| Metric family | Definition |
|---|---|
| Phase timing | Trigger timestamp; trigger-to-observed-suppression-release; trigger-to-target-finalization; trigger-to-inner-completion when present; otherwise a separately labelled censored trigger-to-mode-exit duration |
| Trigger context | Causal event-time `CTUN.NavPitch`, `CTUN.Pitch`, `CTUN.NavRoll`, `CTUN.Roll`, `CTUN.As`/`AsT`, and valid active `GPS.Spd`, each with its source timestamp/age |
| Immediate roll excursion | Maximum absolute `CTUN.Roll` in the launch-response interval, with timestamp; retain co-sampled `NavRoll` as context |
| Altitude response | Minimum `POS.RelHomeAlt` relative to the trigger baseline over the automatic-control interval; altitude gain to inner completion, or a separately labelled censored delta to mode exit |
| Speed envelope | Independent minimum and maximum valid `CTUN.As` and active `GPS.Spd` over the automatic-control or censored interval, with source type/timestamps; do not imply simultaneous air/ground-speed pairs |

These families use strong evidence, avoid arbitrary performance thresholds,
and directly answer phase duration, attitude at launch, roll excursion, speed
development, and initial altitude loss/gain. A first implementation may ship
them incrementally, but must retain the window and censoring labels.

### 10.2 Useful later

| Candidate | Reason to defer |
|---|---|
| Pitch tracking error over an interval | Valid directly from CTUN only when event-time `KFF_THR2PTCH == 0`; nonzero feed-forward needs an explicitly validated reconstruction or a qualified metric |
| Time to commanded takeoff throttle | Requires event-time throttle limits/options, timer state, slew policy, and an exact target/tolerance definition |
| RCOU throttle-output timing | Requires `RCOU` retention plus event-time servo-function/channel calibration; remains command, not thrust |
| Climb/sink extrema or average | Prefer `TECS.dh`; requires TECS retention and a robust aggregation definition |
| Airspeed-minus-groundspeed | Independent streams and different rates require a declared pairing/window statistic; it is also wind-sensitive and must not be described as wind by itself |
| Demand/response summaries beyond extrema | Need an explicit time-weighted versus sample-weighted aggregation rule |
| ARSP sensor corroboration | Useful for diagnosing controller source/health, but CTUN already states the selected estimate type for the primary metric |
| Rangefinder AGL at/near `AIRSPEED_MIN` | Investigate optional Plane `RFNS.HE` as a separately named low-altitude AGL result; define validity/baseline semantics and validate against real takeoffs before considering any preference over `POS.RelHomeAlt` |

### 10.3 Reject for this scope

- time to arbitrary 50% or 90% throttle;
- “useful throttle” without a parameter-aware definition;
- physical hand release, rotation, liftoff, thrust, motor speed, or actuator
  position inferred from commands;
- raw-altitude finite-difference climb rate;
- stored mission definitions as runtime execution evidence;
- safe/unsafe, pass/fail, good/bad, scoring, or recommendations.

## 11. Rolling versus non-surface interpretation

Do not infer a launch method. Use event-time parameter context only.

When `TKOFF_ROTATE_SPD > 0`, firmware holds `TKOFF_GND_PITCH` before the
configured rotation condition and then follows the takeoff pitch path. Early
pitch demand/response and altitude loss therefore describe a rolling/surface
rotation configuration.

When `TKOFF_ROTATE_SPD == 0`, that rotation-speed gate is absent. The same
metrics describe a non-surface-compatible controller path, but still do not
prove a hand launch. Trigger airspeed/groundspeed, early altitude delta, and
time-to-speed metrics have materially different operational interpretation
between the two configurations and must carry the parameter context.

## 12. Parameter context required later

Use the existing timestamped `ParameterHistory` at the takeoff event; do not
introduce a second parameter mechanism.

Relevant context includes:

- launch/rotation: `TKOFF_ROTATE_SPD`, `TKOFF_GND_PITCH`,
  `TKOFF_LVL_PITCH`, `TKOFF_LVL_ALT`, `TKOFF_ALT`, `TKOFF_DIST`,
  `LEVEL_ROLL_LIMIT`, `ROLL_LIMIT_DEG`, `STALL_PREVENTION`;
- pitch reference: `PTCH_TRIM_DEG`, `KFF_THR2PTCH`;
- throttle: `TKOFF_THR_MAX`, `TKOFF_THR_MIN`, `TKOFF_THR_MAX_T`,
  `TKOFF_THR_SLEW`, `TKOFF_OPTIONS`, `THR_MAX`, `THR_MIN`,
  `TRIM_THROTTLE`, `THR_SLEWRATE`;
- airspeed: `ARSPD_USE`, `ARSPD_PRIMARY`, relevant `ARSPDn_TYPE`,
  `AIRSPEED_MIN`, `AIRSPEED_CRUISE`;
- hardware output, if added: matching `SERVOx_FUNCTION`, `SERVOx_MIN`,
  `SERVOx_MAX`, `SERVOx_TRIM`, and `SERVOx_REVERSED`.

Non-finite or missing event-time values are unavailable. Do not substitute a
later companion-parameter snapshot.

## 13. Stable-log sanity result

The stable log contains three normal launch executions with trigger,
suppression-release, and target-finalization evidence. One has an inner
TAKEOFF-to-NORMAL completion; two end their observed automatic-control
interval by Mode-13 exit and are therefore censored.

All proposed primary signal families exist. Across the three launch-response
intervals, the raw BIN contains:

- 3, 6, and 9 CTUN/ATT/POS-class samples at about 25 Hz;
- 1, 3, and 3 ARSP/BARO/TECS-class samples at about 10 Hz;
- 1, 1, and 2 GPS samples at about 5 Hz.

Across the corresponding completed or censored control intervals, CTUN and
POS contain 133, 182, and 196 samples; ARSP/BARO/TECS contain 53, 73, and 78;
GPS contains 27, 36, and 39. This is adequate to verify the proposed evidence
paths, but the short first launch-response interval illustrates why sampling
timestamps and no-interpolation semantics matter.

During all three intervals:

- `CTUN.AsT == 1`, identifying sensor-derived controller airspeed;
- ARSP instance 0 is used, healthy, and primary;
- the active GPS is instance 0 with 3D-or-better fixes;
- BARO instance 0 is healthy.

`POS`, `TECS`, `AETR`, and `RCOU` are present in the BIN at the expected
observed rates but absent from the normal `FlightReader` result. TECS begins
only after the controller is active (about 41--61 ms after these triggers), so
it cannot provide a universal pre-trigger baseline. The observed units and
scales agree with the Plane-4.7.0 log definitions. No performance comparison
or threshold tuning was performed.

## 14. Beta compatibility closure

Execution/state compatibility is closed for the available beta corpus:
beta4, beta7, and beta8 were validated and no ownership/state incompatibility
was found. Beta-specific performance analysis is deferred. Logger sampling
and scheduling differences may later change measurement resolution without
changing execution ownership semantics.

## 15. Smallest future implementation boundary

The first metric implementation can reuse the frozen execution detector,
existing `FlightLog` dataframes, and `ParameterHistory`. No parser architecture
change is required.

Add `POS` to normal message retention for the preferred altitude evidence.
Retaining `TECS` and `RCOU` is optional and should wait for the deferred climb
and hardware-output metrics. Keep metric calculation in a takeoff-specific
processor/model layered over the generic reader; do not add takeoff-specific
DataFlash parsing or traverse raw PARM rows inside the metric code.

## 16. Event-time parameter interpretation audit

This section records the bounded Plane-4.7.0 source and `log_0.bin` parameter
audit performed after the first performance-evidence slice was implemented.
It interprets existing evidence; it does not add metrics or change the
execution contract.

### 16.1 Method and event-time values

Every value below was obtained with
`flight_log.parameter_history.value_at(name, trigger_time_us)`. Times are
absolute DataFlash `TimeUS` microseconds. All listed values are startup
baseline values and none has an effective `ParameterChange` between the three
triggers.

| Execution | Trigger `TimeUS` | `PTCH_TRIM_DEG` | `KFF_THR2PTCH` | `PTCH_LIM_MAX_DEG` / `MIN` | `TECS_PITCH_MAX` / `MIN` |
|---:|---:|---:|---:|---:|---:|
| 1 | 736323444 | 0 deg | 0 deg | 45 / -40 deg | 20 / -12 deg |
| 2 | 1557443368 | 0 deg | 0 deg | 45 / -40 deg | 20 / -12 deg |
| 3 | 2356143377 | 0 deg | 0 deg | 45 / -40 deg | 20 / -12 deg |

| Execution | `TKOFF_ROTATE_SPD` | `TKOFF_GND_PITCH` | `TKOFF_LVL_PITCH` | `TKOFF_ALT` | `TKOFF_DIST` | `TKOFF_LVL_ALT` | `TKOFF_PLIM_SEC` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 m/s | 5 deg | 18 deg | 30 m | 75 m | 10 m | 2 s |
| 2 | 0 m/s | 5 deg | 18 deg | 30 m | 75 m | 10 m | 2 s |
| 3 | 0 m/s | 5 deg | 18 deg | 30 m | 75 m | 10 m | 2 s |

The tail-dragger override parameters are also zero at every trigger:
`TKOFF_TDRAG_ELEV=0` and `TKOFF_TDRAG_SPD1=0`. Launch-check context is
`TKOFF_THR_MINACC=6 m/s/s`, `TKOFF_THR_MINSPD=0 m/s`,
`TKOFF_THR_DELAY=0 ds`, and `TKOFF_ACCEL_CNT=1` at all three triggers.

| Execution | `LEVEL_ROLL_LIMIT` | `ROLL_LIMIT_DEG` | `STALL_PREVENTION` |
|---:|---:|---:|---:|
| 1 | 5 deg | 60 deg | 1 |
| 2 | 5 deg | 60 deg | 1 |
| 3 | 5 deg | 60 deg | 1 |

| Execution | `TKOFF_THR_MIN` / `IDLE` / `MAX` | `TKOFF_THR_MAX_T` | `TKOFF_THR_SLEW` | `TKOFF_OPTIONS` | `THR_MIN` / `MAX` | `TRIM_THROTTLE` | `THR_SLEWRATE` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 / 0 / 100% | 0.5 s | 110 %/s | 0 | 0 / 100% | 45% | 100 %/s |
| 2 | 0 / 0 / 100% | 0.5 s | 110 %/s | 0 | 0 / 100% | 45% | 100 %/s |
| 3 | 0 / 0 / 100% | 0.5 s | 110 %/s | 0 | 0 / 100% | 45% | 100 %/s |

Forward-throttle battery compensation and cutoff are disabled at every
trigger: `FWD_BAT_VOLT_MIN=0`, `FWD_BAT_VOLT_MAX=0`, and
`FWD_BAT_THR_CUT=0`. No `BATT_WATT_MAX` parameter exists in this log's PARM
history, so this audit does not infer a watt-limiter state from a missing
value.

| Execution | `AIRSPEED_MIN` | `AIRSPEED_CRUISE` | `ARSPD_USE` | `ARSPD_PRIMARY` | `ARSPD_TYPE` | `ARSPD2_TYPE` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11 m/s | 13 m/s | 1 | 0 | 9 | 0 |
| 2 | 11 m/s | 13 m/s | 1 | 0 | 9 | 0 |
| 3 | 11 m/s | 13 m/s | 1 | 0 | 9 | 0 |

The numeric airspeed type is retained as evidence rather than being inferred
from a companion parameter file. More importantly for these observations,
all three trigger CTUN rows report `AsT=1`, so the controller estimate is
sensor-derived at those sample times. Parameters express configuration and
selection policy; they do not by themselves prove sensor health or acceptance
at a particular event.

### 16.2 Pitch demand and the two 45-degree observations

The relevant Plane source path is:

1. `ModeTakeoff::update()` calls `takeoff_calc_pitch()` while the inner flight
   stage is TAKEOFF.
2. With `TKOFF_ROTATE_SPD > 0`, `takeoff_calc_pitch()` uses
   `TKOFF_GND_PITCH` below rotate speed, then ramps toward the takeoff pitch
   using groundspeed until cruise speed. With `TKOFF_ROTATE_SPD == 0`, both
   pre-rotation branches are skipped and rotation is marked complete
   immediately.
3. Because these launches have a usable airspeed sensor, the post-rotation
   path calls `calc_nav_pitch()`, takes the current TECS pitch demand, applies
   the global `PTCH_LIM_MIN_DEG` / `PTCH_LIM_MAX_DEG` clamp, and then enforces
   the takeoff minimum pitch. `TKOFF_LVL_PITCH` is a minimum, not the sole
   demanded pitch. `TECS_PITCH_MAX` / `MIN` apply when TECS updates its demand;
   `TKOFF_PLIM_SEC` can reduce the takeoff minimum near level-off.
4. With `STALL_PREVENTION=1`, large roll tracking error can subsequently
   reduce takeoff pitch demand by the source-defined cosine-squared factor.

The trigger-context lookup is causal, not interpolated. Executions 2 and 3
therefore report the latest CTUN rows 18,810 us and 39,426 us before their
firmware trigger messages. Both rows contain `NavPitch=45 deg`; they are not
measurements taken exactly at the message timestamp.

Those pre-trigger rows still contain retained TECS state because throttle
suppression gates off `update_pitch_throttle()`. That fact does not, however,
explain the fresh post-trigger 45-degree demands. A second Plane-4.7.0 state
lifecycle is decisive:

1. At `740784189 us`, execution 1 emits `Takeoff level-off starting at 10m`
   and assigns its current remaining height to
   `auto_state.height_below_takeoff_to_level_off_cm`.
2. The nearest logged `POS.RelHomeAlt` and `TECS.h` are 19.104 m for a
   30 m TAKEOFF target. They provide an approximately 10.896 m proxy for the
   stored value; the integer firmware message itself establishes only that
   the remaining height was at least 10 m and less than 11 m.
3. `ModeTakeoff::_enter()`, its normal setup, mode exit, disarm and re-arm do
   not clear that `auto_state` field. Disarm clears the separately owned
   `takeoff_state`, including `level_off_start_time_ms`, but not the retained
   height. The later Mode-13 executions can therefore reuse execution 1's
   reference.
4. The lowest observed `POS.RelHomeAlt` values before the later triggers are
   -0.03 m and -0.04 m, giving approximate remaining heights of 30.03 m and
   30.04 m. With the logged-altitude proxy above, the source formula
   `18 deg * remaining_height / retained_height` gives 49.61 deg and
   49.63 deg. Their first fresh TECS records report `pmin=pmax=49.53 deg`
   and `49.51 deg`, respectively. The small difference is consistent with
   the logged fields being sampled proxies for the internal values, not a
   reason to tune the retained reference to force exact agreement.

Before the first post-trigger TECS solution, repeated `takeoff_calc_pitch()`
calls can also accumulate the largest external TECS minimum through
`set_pitch_min()`. TECS consumes and resets that external limit when
`update_pitch_throttle()` next runs. This accounts for the first fresh limit
reflecting the near-ground remaining height rather than only the altitude at
the TECS record.

The TECS ordering permits `pmax` to exceed `TECS_PITCH_MAX=20 deg`. TECS first
selects the configured maximum, replaces its minimum with the TAKEOFF minimum,
applies accumulated external limits, converts the limits to radians, and then
forces `pmax = max(pmax, pmin)`. Its rate-limited `ph` can initially remain far
below those newly raised limits. On the next Plane control iteration,
`calc_nav_pitch()` clamps `ph` to `PTCH_LIM_MAX_DEG=45`, after which
`takeoff_calc_pitch()` again enforces the TAKEOFF minimum and may then reduce
the result for roll error. `CTUN.NavPitch=45 deg` is consequently a
combination of the retained TAKEOFF minimum, TECS limit ordering, Plane's
global navigation-pitch clamp and per-sample stall-prevention adjustment. It
is not simply the raw TECS `ph`, not `TKOFF_GND_PITCH`, and not evidence of a
physical rotation.

The same Mode-13 reset gap is present in Plane 4.7.1 and current master as
audited at `de411b3818bd9ccabab90151c22f4bb3bb367353`. AUTO mission
`NAV_TAKEOFF` does not have this gap: `do_takeoff()` explicitly resets
`height_below_takeoff_to_level_off_cm` when starting each mission item.

The source basis is Plane-4.7.0
[`ModeTakeoff::update()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/mode_takeoff.cpp),
[`takeoff_calc_pitch()` and `get_takeoff_pitch_min_cd()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/takeoff.cpp),
[`calc_nav_pitch()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Attitude.cpp),
[`update_speed_height()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Plane.cpp),
[`do_takeoff()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/commands_logic.cpp),
and
[`AP_TECS` pitch-limit handling](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_TECS/AP_TECS.cpp).
The lifecycle comparison used the corresponding
[Plane-4.7.1](https://github.com/ArduPilot/ardupilot/tree/Plane-4.7.1/ArduPlane)
and
[current-master](https://github.com/ArduPilot/ardupilot/tree/de411b3818bd9ccabab90151c22f4bb3bb367353/ArduPlane)
sources.

### 16.3 Exact pitch-tracking qualification

For the conventional fixed-wing pitch-controller path, define:

- `N = CTUN.NavPitch`, degrees;
- `P = CTUN.Pitch`, degrees, equal to actual pitch minus
  `PTCH_TRIM_DEG`;
- `K = KFF_THR2PTCH`, degrees added at 100% throttle;
- `u =` scaled throttle output, percent, at the instant
  `stabilize_pitch_get_pitch_out()` reads it.

The final controller demand and angular error are:

```text
final demand deg = N + PTCH_TRIM_DEG + u * K / 100
controller error deg = N - P + u * K / 100
```

Thus `CTUN.NavPitch - CTUN.Pitch` is a defensible co-sampled tracking residual
when event-time `KFF_THR2PTCH == 0` and the normal fixed-wing pitch controller
is actually active. A tail-hold elevator override would bypass that controller;
the stable log excludes it with `TKOFF_TDRAG_ELEV=0`. VTOL and system-ID paths
remain outside this contract.

When `KFF_THR2PTCH != 0`, the correction requires the throttle-function value
read by `stabilize_pitch_get_pitch_out()` in that control iteration. Although
`CTUN.ThO` has the required percent scale, it is logged later from the current
scaled output after the servo path can apply battery compensation, throttle
limits, suppression, and slew limiting. It is therefore not guaranteed to be
the exact earlier value used by the pitch controller. Normal DataFlash does
not log the final pitch-demand expression or that controller-input throttle
atomically. Exact reconstruction is unavailable in the general nonzero-KFF
case; nearest-sample substitution must not be presented as exact.

This follows Plane-4.7.0
[`stabilize_pitch_get_pitch_out()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Attitude.cpp),
the `KFF_THR2PTCH` parameter definition in
[`Parameters.cpp`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Parameters.cpp),
and CTUN construction in
[`Log_Write_Control_Tuning()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Log.cpp).

### 16.4 TAKEOFF roll-limit interpretation

`takeoff_calc_roll()` first obtains the normal navigation roll demand. Before
a nonzero rotate speed is reached, it clamps that demand to
`LEVEL_ROLL_LIMIT`. Thereafter it applies a height-dependent limit:

- through `TKOFF_LVL_ALT` above the captured barometric takeoff altitude:
  `LEVEL_ROLL_LIMIT`;
- from that height to the lower of `3 * TKOFF_LVL_ALT` and `TKOFF_ALT`:
  linear expansion toward `ROLL_LIMIT_DEG`;
- above the upper bound: `ROLL_LIMIT_DEG`.

For this configuration, the demand limit is therefore 5 degrees initially,
expands between 10 m and 30 m, and reaches 60 degrees at the upper bound.
`TKOFF_ROTATE_SPD=0` removes the pre-rotate condition but does not remove this
altitude-dependent limit. The already implemented maximum achieved-roll is
aircraft response, not commanded roll, so achieved roll can exceed the demand
cap. A later configured-margin result would need to reconstruct the dynamic
cap and its captured barometric takeoff reference; subtracting achieved roll
from the static 5-degree parameter would not be a controller-limit margin.

### 16.5 Throttle path and the observed early commands

The Plane-4.7.0 path is:

1. launch acceptance emits `Triggered AUTO`, starts the max-throttle timer,
   and permits suppression to clear;
2. `takeoff_calc_throttle()` selects the takeoff maximum as
   `TKOFF_THR_MAX` when nonzero, otherwise `THR_MAX`;
3. it initially selects the takeoff minimum as `TKOFF_THR_MIN` when nonzero,
   otherwise `TRIM_THROTTLE`;
4. an active `TKOFF_THR_MAX_T` timer raises the minimum to the maximum;
5. unset `TKOFF_OPTIONS` bit 0, absence of an airspeed sensor, or remaining
   below `TKOFF_LVL_ALT` also raises the minimum to the maximum;
6. TECS supplies the controller demand, and
   `apply_throttle_limits()` applies the takeoff min/max plus enabled battery
   compensation and power limiting;
7. suppression substitutes `TKOFF_THR_IDLE` when positive, otherwise zero;
8. `throttle_slew_limit()` uses nonzero `TKOFF_THR_SLEW` during TAKEOFF,
   otherwise `THR_SLEWRATE`; the servo-function layer rate-limits the scaled
   command before CTUN logs `ThO`.

Here, `TKOFF_THR_MAX=100` is the configured takeoff maximum. Although the
zero takeoff minimum initially falls back to `TRIM_THROTTLE=45`,
`TKOFF_OPTIONS=0` forces the takeoff minimum equal to the maximum throughout
the TAKEOFF stage; the 0.5-second max timer independently does the same while
active. The target/course-finalization path restarts that timer. Forward
battery compensation and cutoff are disabled. `TKOFF_THR_SLEW=110 %/s`
overrides `THR_SLEWRATE=100 %/s`.

The existing observations are consistent with that path:

| Execution | Trigger `ThO` | Suppression-release `ThO` | Target-finalization `ThO` |
|---:|---:|---:|---:|
| 1 | 0.0% | 8.8% | 13.2% |
| 2 | 0.0% | 17.6% | 26.4% |
| 3 | 0.0% | 6.6% | 37.4% |

The trigger contexts use CTUN samples 19.393 ms, 18.810 ms, and 39.426 ms
before the corresponding messages, while suppression is still effective.
The suppression-release lookups use samples only 243 us, 152 us, and 157 us
before their STAT observations. The different values therefore principally
reflect how many control-loop slew increments have occurred by each logger
sample. At the observed roughly 40 ms CTUN cadence, 110 %/s permits about 4.4
percentage points per full sample interval; the rows surrounding the events
show that progression. TECS demand changes from its pre-trigger state toward
99--100%, but `ThO` remains the slew-limited, post-suppression command. The
three values are not three different configured throttle targets.

The source basis is Plane-4.7.0
[`auto_takeoff_check()` and `takeoff_calc_throttle()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/takeoff.cpp),
[`ModeTakeoff::update()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/mode_takeoff.cpp),
and
[`suppress_throttle()`, `apply_throttle_limits()`, `set_throttle()`, and
`throttle_slew_limit()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/servos.cpp).

### 16.6 Propulsion response to configured minimum airspeed

When both suppression release and the first owned CTUN observation satisfying
event-time `As >= AIRSPEED_MIN` are available, define the propulsion-build
interval as the inclusive observed interval between those two timestamps. Do
not substitute the trigger or another boundary when suppression-release
evidence is missing. The interval must remain inside the owning TAKEOFF
execution and must not extend beyond the first qualifying airspeed row.

Within that interval, report the maximum finite observed `CTUN.ThO` as
**peak throttle**. If the maximum occurs more than once, its source timestamp
is the earliest matching CTUN sample. **Throttle ramp to peak** is the elapsed
duration from observed suppression release to that first maximum sample. It is an
observed sample-to-sample duration with no interpolation, not an observed slew
rate and not a comparison with an idealized ramp.

**Time at peak throttle** is available only when every finite `CTUN.ThO`
observation from the first peak sample through the qualifying AIRSPEED_MIN
sample equals that peak exactly, including the qualifying sample itself. It is
the duration from the first peak timestamp to the AIRSPEED_MIN timestamp,
without interpolation or tolerance. A valid below-peak observation breaks the
continuous hold; separated peak periods are not summed. This duration is
distinct from **throttle ramp to peak**, which starts at suppression release.

Report **throttle at AIRSPEED_MIN** from the `ThO` field of the same CTUN row
that established the first qualifying airspeed; an invalid same-row value is
unavailable and must not be replaced by a nearby sample. These values are
normalized throttle-function commands in percent, not electrical power, motor
output, or thrust. The trigger-time `TKOFF_THR_SLEW` parameter remains separate
configuration context in `%/s`; no measured slew rate is derived from it.

`BAT.Curr` provides electrical battery current in amperes and `BAT.Inst`
identifies the monitor instance. Use finite current from primary instance zero
only and report the highest observed value in the same inclusive interval as
**peak battery current before AIRSPEED_MIN**. Missing instance-zero evidence is
unavailable; another instance must not silently replace it. Battery-current
absence does not invalidate otherwise usable throttle evidence. This metric
does not infer watts, efficiency, voltage sag, or physical thrust.

All selected CTUN and BAT values retain their source `TimeUS` internally. The
normal report presents values and trigger-relative timing only, without
absolute timestamps or interpolation.

### 16.7 Firmware-defined throttle target

A precise scalar is possible only for a qualified configuration. First derive
the configured takeoff maximum:

```text
configured max = TKOFF_THR_MAX if nonzero, else THR_MAX
```

When firmware forces the takeoff minimum to that maximum (active
`TKOFF_THR_MAX_T`, `TKOFF_OPTIONS` bit 0 unset, no accepted airspeed sensor,
or below `TKOFF_LVL_ALT`), and no runtime compensation or power limiter changes
the bound, a future metric may be named **time from observed suppression
release to first observed `CTUN.ThO` reaching the effective forced takeoff
maximum**. It must retain the CTUN sample timestamp and sampling latency. For
the stable configuration, that nominal parameter-derived maximum is 100%.

When throttle-range operation is enabled, an airspeed sensor is accepted, the
aircraft is above the level altitude, and the max timer has expired, TECS may
command anywhere within the takeoff bounds. There is then no single static
parameter target. Battery compensation and the runtime watt limiter can also
make the effective bound dynamic. In those cases, retain the existing
threshold-free `ThD`/`ThO` command context or expose their co-sampled trajectory
rather than inventing a 50%, 90%, or static-parameter target.

### 16.8 Airspeed context and next-metric disposition

`AIRSPEED_MIN=11 m/s` is the controller's configured minimum airspeed context,
not a measured stall speed and not proof of margin to stall.
`AIRSPEED_CRUISE=13 m/s` is the normal demand/reference and, when
`TKOFF_ROTATE_SPD > 0`, is also used by the post-rotate groundspeed ramp toward
the takeoff pitch. `ARSPD_USE=1`, `ARSPD_PRIMARY=0`, and `ARSPD_TYPE=9`
identify configured use and the selected sensor instance/type; event-time
`CTUN.AsT` and ARSP health remain necessary to establish actual usable
evidence.

**Recommended next, with explicit qualification:**

- maximum absolute co-sampled `CTUN.NavPitch - CTUN.Pitch` over a declared
  automatic-control interval only after the section 17 TECS-freshness boundary,
  when event-time `KFF_THR2PTCH == 0`, the normal fixed-wing pitch controller
  is active, and no tail-hold override is active;
- controller-airspeed delta from event-time `AIRSPEED_MIN`, explicitly named
  configured-minimum airspeed delta and never stall margin;
- time to the effective forced takeoff maximum only when the source conditions
  in section 16.7 prove a fixed target and dynamic modifiers are excluded or
  represented.

**Defer:**

- mean pitch tracking error until time-weighted versus sample-weighted
  aggregation is chosen;
- pitch tracking reconstruction when `KFF_THR2PTCH != 0`;
- an observed throttle slew/ramp-rate scalar, because sample-rate effects and
  aggregation choices are not yet specified (the configured slew rate may be
  reported as context);
- roll margin until the time-varying limit and captured barometric takeoff
  reference are reconstructable;
- any airspeed result labelled stall margin;
- rotation-specific response metrics until a `TKOFF_ROTATE_SPD > 0` corpus is
  available to validate evidence and sampling, without inferring physical
  wheel rotation or liftoff.

## 16.9 Current implementation checkpoint and deferred follow-ups

The current APT TAKEOFF report now has three deliberately separate layers:

1. **event-led phase evidence** — owned firmware events/state such as
   `Armed AUTO`, `Triggered AUTO`, throttle unsuppression, the authoritative
   AIRSPEED_MIN event, explicit rotation unavailability, and existing TAKEOFF
   completion status;
2. **derived performance evidence** — including `Trigger → AIRSPEED_MIN`,
   `Throttle → AIRSPEED_MIN`, and `Altitude Δ at AIRSPEED_MIN`;
3. **configuration context** — event-time takeoff, throttle, pitch/roll, and
   airspeed parameters from `ParameterHistory`.

Stable `log_0.bin` validation for the three triggered executions is:

| TAKEOFF | Trigger → AIRSPEED_MIN | Throttle → AIRSPEED_MIN | Altitude Δ at AIRSPEED_MIN | `Armed AUTO` x-accel | Trigger GPS speed |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.581 s | 1.519 s | +2.58 m | 6.5 m/s² | 2.5 m/s |
| 2 | 1.781 s | 1.639 s | +3.01 m | 6.6 m/s² | 2.0 m/s |
| 3 | 1.761 s | 1.718 s | +0.13 m | 7.3 m/s² | 1.8 m/s |

Current deferred work:

- rotation completion remains `Unavailable` until authoritative retained log
  evidence exists; do not derive it from `TKOFF_ROTATE_SPD` or sensor traces;
- tail-hold, ground-roll, rotation, liftoff, and surface-departure phases remain
  deferred pending authoritative evidence and known surface-takeoff logs;
- physical launch classification remains deferred; possible future high-level
  families are externally launched and surface takeoff, but current evidence
  does not justify assigning them;
- investigate a separately named `RFNS.HE`-based low-altitude AGL result as
  described in section 7.1.1; retain the existing POS-based altitude metric
  until that evidence contract is validated.

These are explicit deferred items, not reasons to weaken the current
event-first evidence rules.

## 17. Post-launch pitch-demand freshness and report presentation

This section closes the remaining freshness question for the proposed maximum
pitch-tracking residual and defines presentation contracts for a later human
report. It does not change execution ownership or metric calculations.

### 17.1 TECS scheduling and refresh semantics

Plane-4.7.0 has two materially different TECS calls:

1. `update_speed_height()` runs at 50 Hz and calls `AP_TECS::update_50hz()`
   even while throttle is suppressed. This updates TECS state needed for
   launch detection; it does not calculate a new pitch/throttle solution.
2. `update_alt()` runs at 10 Hz. Only when automatic throttle is active and
   `throttle_suppressed` is false does it call
   `AP_TECS::update_pitch_throttle()`. That call updates limits, speed and
   height demands, energies, `_pitch_dem`, and `_throttle_dem`.

`AP_TECS::update_pitch_throttle()` writes the `TECS` record from inside the
same call, after `_update_pitch()` and the throttle calculation. A valid TECS
row with a finite `TimeUS` and `ph` therefore directly proves that a TECS pitch
solution was recalculated in that invocation. `ph` is the resulting TECS
pitch output in radians. A change in `CTUN.NavPitch` is not equivalent proof:
TAKEOFF minimum-pitch and stall-prevention logic can change `nav_pitch_cd`
while the underlying TECS demand remains retained, and a refreshed solution
can produce the same final navigation demand after clamping.

The scheduler order creates one additional propagation boundary. Every main
loop runs `update_control_mode()` before scheduled `update_alt()` and
`update_logging25()`. `ModeTakeoff::update()` therefore copies the current
TECS demand through `takeoff_calc_pitch()` and `calc_nav_pitch()` before a TECS
refresh that occurs later in the same loop. If CTUN logging is also due in that
loop, the TECS row is written first and the later CTUN row can still contain
the navigation demand calculated before that refresh.

Consequently:

- the first valid post-trigger TECS row proves **TECS solution refresh**;
- the first CTUN row after that TECS row is ambiguous because it may be from
  the same scheduler loop;
- the second CTUN row strictly after that TECS row is the earliest
  source-provable CTUN observation that has passed through a subsequent
  `update_control_mode()` invocation and can contain the refreshed solution.

This rule uses scheduler call order and occurrence order, not a timing
threshold. If TECS logging is disabled, no valid post-trigger TECS row exists,
or fewer than two later owned CTUN rows exist, demand freshness is unavailable
and the pitch-residual metric must be unavailable. A missing TECS row does not
prove that firmware failed to update; it means the log cannot prove that it
did. Equal cross-message timestamps remain ambiguous and must not be ordered
by message type.

The source basis is Plane-4.7.0
[`scheduler_tasks`, `update_speed_height()`, and `update_alt()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Plane.cpp),
[`ModeTakeoff::update()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/mode_takeoff.cpp),
[`takeoff_calc_pitch()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/takeoff.cpp),
[`calc_nav_pitch()` and `stabilize_pitch_get_pitch_out()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Attitude.cpp),
[`Log_Write_Control_Tuning()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/ArduPlane/Log.cpp),
and
[`AP_TECS::update_pitch_throttle()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_TECS/AP_TECS.cpp).
The one-run-per-tick basis for the second-CTUN propagation rule comes from
[`AP_Scheduler::run()` and `loop()`](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.0/libraries/AP_Scheduler/AP_Scheduler.cpp).

### 17.2 Stable-log freshness evidence

The first `STAT.Sup=0` row is an observed state report, not the exact internal
microsecond at which suppression changed. In all three launches, the first
post-trigger TECS record precedes that STAT observation. `Takeoff to ...`
finalizes the target/course and restarts the maximum-throttle timer; it does
not cause or prove a TECS pitch refresh.

| Execution | Trigger | First TECS refresh | First later CTUN (ambiguous) | Earliest provably propagated CTUN | `STAT.Sup=0` | `Takeoff to ...` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 736323444 | 736384242 | 736385759 | 736424689 | 736386002 | 736443331 |
| 2 | 1557443368 | 1557484228 | 1557503896 | 1557544402 | 1557585341 | 1557703252 |
| 3 | 2356143377 | 2356184172 | 2356185378 | 2356224438 | 2356185535 | 2356483405 |

Normal `FlightReader` now retains `TECS`, and the production residual applies
the conservative propagation boundary above. The resulting maxima are:

| Execution | Residual | `NavPitch` | `Pitch` | Source `TimeUS` | Interval status |
|---:|---:|---:|---:|---:|---|
| 1 | +12.54 deg | 17.62 deg | 5.08 deg | 736424689 | censored by mode exit |
| 2 | +54.41 deg | 45.00 deg | -9.41 deg | 1557544402 | completed |
| 3 | +41.92 deg | 45.00 deg | 3.08 deg | 2356224438 | censored by mode exit |

Raw messages not currently retained by normal APT reading add useful context.
At the execution-2 and execution-3 maxima, `PIDP` has its output-limit flag
set, `AETR.Elev` is at its positive scaled endpoint of 4500, and the configured
elevator channel is at its 1900 us maximum. This establishes software command
saturation at those observations. It does not establish actual surface
position under aerodynamic load, mechanical binding, insufficient physical
pitch authority, or a tuning defect; the log has no actuator-position
feedback. Execution 1 also has the PID limit flag at its maximum residual, but
its achieved pitch rate already exceeds its desired rate and the logical
elevator command is negative rather than at the positive endpoint.

The maximum absolute residual is therefore an evidence locator, not a
standalone takeoff-quality score. In this log each maximum occurs near the
initial attitude step, at about 3.5--3.7 m/s airspeed and essentially zero
altitude gain, while throttle is still slewing and the attitude controller is
rate-limiting its response. Interpreting it requires the TAKEOFF-minimum and
TECS-limit provenance, response trajectory, roll interaction and available
controller/output-limit evidence. These observations do not establish tuning
thresholds, expected performance values or safety scores.

### 17.3 Configuration-header contract

A normal takeoff report should present one compact context header for each
triggered execution. The snapshot time is the exact `Triggered AUTO` `TimeUS`,
and every entry comes from `ParameterHistory.value_at(name, trigger_time_us)`.
Missing or non-finite parameters display as **unavailable**, never zero and
never a companion-file fallback. The snapshot explains the launch; an
interval metric must still query parameter history at each relevant sample or
parameter-change boundary.

Use these groups and units:

| Group | Event-time values |
|---|---|
| Launch detection | `TKOFF_THR_MINACC` m/s/s; `TKOFF_ACCEL_CNT` count; `TKOFF_THR_DELAY` converted from deciseconds to seconds for display; `TKOFF_THR_MINSPD` m/s |
| Takeoff geometry/control | `TKOFF_ROTATE_SPD` m/s; `TKOFF_GND_PITCH` and `TKOFF_LVL_PITCH` degrees; `TKOFF_ALT` and `TKOFF_LVL_ALT` metres; `TKOFF_DIST` metres |
| Throttle | `TKOFF_THR_MAX` percent; `TKOFF_THR_MAX_T` seconds; `TKOFF_THR_SLEW` percent/second; numeric and decoded `TKOFF_OPTIONS`; `THR_MAX` when `TKOFF_THR_MAX=0` or useful for explaining the fallback |
| Pitch/roll | `PTCH_TRIM_DEG`, `KFF_THR2PTCH`, `PTCH_LIM_MAX_DEG`, `LEVEL_ROLL_LIMIT`, and `ROLL_LIMIT_DEG`, all in degrees |
| Airspeed | `AIRSPEED_MIN` and `AIRSPEED_CRUISE` m/s; numeric/decoded `ARSPD_USE`; zero-based `ARSPD_PRIMARY` instance |

In Plane 4.7.x, `TKOFF_OPTIONS` is an `AP_Int32` bitmask with one defined
option: bit 0 permits TECS to use the configured minimum-to-maximum throttle
range when its firmware conditions apply. Normal output retains the numeric
mask, decodes bit 0, and identifies every other set bit as unknown.

Preserve the underlying raw values in evidence/debug models. Human labels may
explain source-backed branches, for example `TKOFF_THR_MAX=0 (uses THR_MAX)`
or `TKOFF_OPTIONS bit 0 unset (fixed-maximum path)`, but must not infer a
physical launch method or imply that trigger-time parameters remained
unchanged throughout the interval.

### 17.4 Relative-time presentation contract

All analysis and evidence models retain exact absolute integer `TimeUS`.
Normal human-readable output uses the trigger as its local origin:

```text
Triggered AUTO                 0.000 s
Throttle unsuppressed         +0.142 s
Target/course finalized       +0.260 s
TAKEOFF control complete      +7.280 s
TAKEOFF mode exited           +8.100 s
```

Calculate each displayed offset as
`(event_time_us - trigger_time_us) / 1_000_000` without changing stored
timestamps or analytical precision. Display milliseconds by default. If the
source evidence is inherently coarser, the report may reduce displayed
precision rather than imply resolution the evidence lacks. Missing events are
shown as unavailable. Absolute `TimeUS`, source-row time, and sample age remain
available in debug/evidence-detail output but do not appear in the normal
human report.
