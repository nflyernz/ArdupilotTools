# ArduPlane Takeoff Analysis — Performance Evidence and Metric Contract

**Scope:** conventional fixed-wing ArduPlane TAKEOFF mode and AUTO mission
`NAV_TAKEOFF` in stable Plane 4.7.x

**Primary source basis:** Plane-4.7.0

**Stable log basis:** `Logs/log_0.bin`, ArduPlane V4.7.0 (`1511f271`)

**Status:** evidence and first-metric semantics established; no performance
metric implementation yet

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
`KFF_THR2PTCH == 0`. Reconstruction for nonzero feed-forward is deferred
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
- endpoint gain: the latest valid owned sample at or before the endpoint minus
  the same baseline.

Do not mix `POS.RelHomeAlt`, `POS.Alt`, `BARO.Alt`, `BARO.AltAMSL`, or GPS
altitude in one delta. If `POS` is unavailable, the POS-based metric is
unavailable; a separately named BARO-derived result may be added later, but it
must not be a silent fallback.

`BARO.Alt` is usable sensor-relative corroboration when restricted to one
healthy instance, and `BARO.AltAMSL` is an AMSL estimate. Neither is the
canonical fused takeoff navigation height. CTUN has no altitude field.

The first implementation will therefore need normal retention of `POS`. This
is a message-selection change only; the existing DataFlash reader already
preserves the needed raw fields.

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
