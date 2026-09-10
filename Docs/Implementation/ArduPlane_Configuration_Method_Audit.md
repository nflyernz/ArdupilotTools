# AMC ArduPlane Configuration Method — Read-Only Audit

> **Status:** COMPLETE — read-only configuration-method audit
> **Audit date:** 2026-09-11
> **AMC repository:** `~/MethodicConfigurator`
> **Audited baseline:** `c58eb9f8` (`master`)
> **Primary conclusion:** configuration content, not shared AMC infrastructure, is the immediate problem.
> **Next bounded implementation:** ArduPlane 4.7.x Step 66 — **Everyday use / RTL correctness**.

## Document role

This document freezes the repository evidence and conclusions from the
2026-09-11 read-only audit. It is an implementation-planning baseline, not a
replacement for ArduPlane firmware documentation or maintainer direction.
Future PRs should update this record only when repository evidence or accepted
design direction materially changes.

## 1. Executive summary

The current ArduPlane configuration method is not yet a coherent Plane-specific method.

The sequence engine and `.param` processing architecture are sufficient for narrow improvements. The principal problem is configuration content:

- The authoritative file is `configuration_steps_ArduPlane.json` (`ardupilot_methodic_configurator/configuration_steps_ArduPlane.json:1`). No file named `configuration_sequence_ArduPlane.json` exists.
- Its 63 step keys exactly match the ArduCopter sequence.
- Most step metadata is copied from Copter with only the blog URL changed.
- 26 of the 63 files shared by the two `empty_4.7.x` templates have identical parameter-name sets.
- Large sections configure Copter/QuadPlane controllers (`ATC_*`, `PSC_*`, `MOT_*`, VTOL QuickTune, multicopter SystemID and `PLND_*`) without fixed-wing applicability boundaries.
- Essential fixed-wing domains—airspeed, TECS, takeoff, landing, flaps, spoilers and fixed-wing navigation—lack canonical sequence ownership.
- Existing fixed-wing airspeed/rangefinder/landing content is concentrated in one undocumented mixed file:
  - `normal_plane/15_range_finder.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/normal_plane/15_range_finder.param:1`)
  - `empty_4.7.x/59_range_finder.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/empty_4.7.x/59_range_finder.param:1`)
- Neither filename has a matching entry in the Plane sequence JSON.
- The `normal_plane` template has two files with prefix 15, a condition explicitly marked as a known `xfail` in `test_vehicle_template_param_files.py` (`tests/test_vehicle_template_param_files.py:82`).
- In `empty_4.7.x`, throttle-failsafe, airspeed and landing settings appear at step 59—after multiple supposed flight and tuning phases.
- `66_everyday_use.param` uses Copter’s `RTL_ALT=3500`; current Plane 4.7 defaults expose `RTL_ALTITUDE`, whose canonical units and value semantics differ.

Verdict: improve the Plane method through small domain-specific PRs. No shared architecture rewrite is needed first.

## 2. Repository / branch / HEAD / worktree

``text
Repository: /Users/donaldsmith/MethodicConfigurator
Branch:     master
HEAD:       c58eb9f87b7a5a298ef20df4f2a3d710eb6ceddc
            c58eb9f8 chore(translations): apply AI translations and compile .mo files
``

Final checks:

``text
git status --short   <empty>
git diff --stat      <empty>
git diff --check     PASS
``

## 3. AMC configuration-sequence architecture

### Observed AMC behavior

The sequence is driven by numbered `.param` files in the selected vehicle directory, not solely by the JSON map.

- `LocalFilesystem.read_params_from_files()` (`ardupilot_methodic_configurator/backend_filesystem.py:335`) loads every `NN_*.param` file lexicographically, excluding `00_default.param` and `01_ignore_readonly.param`.
- Consequently, a `.param` file without JSON metadata still appears as a step.
- A JSON step without a corresponding template file does not appear in that template’s actual navigation sequence.
- `compound_params()` (`ardupilot_methodic_configurator/backend_filesystem.py:361`) applies files in sequence; later occurrences of a parameter replace earlier values through `ParDict.append()`.
- The last successfully uploaded filename is persisted by `write_last_uploaded_filename()` (`ardupilot_methodic_configurator/backend_filesystem.py:738`). Resumption starts at the following file.
- Progress is positional: selecting or uploading a file advances the displayed phase progress. It is not a per-step dependency/completion graph.

### JSON loading and authoring contract

`ConfigurationSteps.re_init()` (`ardupilot_methodic_configurator/backend_filesystem_configuration_steps.py:73`):

1. Looks for `configuration_steps_<vehicle>.json` in the vehicle project.
2. Falls back to the installed application file.
3. Validates it against `configuration_steps_schema.json` (`ardupilot_methodic_configurator/configuration_steps_schema.json:1`).
4. Retains ordered `steps` and `phases`.

The documented authoring contract is in `CUSTOMIZING_CONFIGURATION_STEPS.md` (`CUSTOMIZING_CONFIGURATION_STEPS.md:48`):

- `.param` syntax accepts comma, space or tab separators.
- Full-line and trailing `#` comments are supported.
- Values must parse as finite floats.
- Duplicate names within one file are rejected.
- `forced_parameters` compute non-editable values.
- `derived_parameters` evaluate expressions from component data and current FC parameters.
- `add_parameters` add an editable parameter without replacing an existing file value.
- `delete_parameters` remove parameters conditionally.
- `autoimport_nondefault_regexp` imports matching non-default FC values.
- `jump_possible` offers a manual skip.
- `old_filenames` supplies migration history.
- `plugin`, `download_file`, `upload_file`, `instructions_popup` and `related_bin_messages` provide optional step behavior.

Expressions have access to vehicle components, parameter metadata and current FC values. They do not directly traverse earlier `.param` files. Earlier changes are visible only after reaching the FC or through the existing file contents.

### Re-entry behavior

Returning to an earlier step:

- recomputes that step’s forced/derived/add/delete operations;
- can change the FC and that step’s file;
- does not mark later steps stale;
- does not automatically re-run or invalidate dependent steps.

AMC warns about files affected by component-editor-derived changes, but it has no general downstream dependency graph.

### Frontend presentation

The frontend displays:

- current numbered file;
- phase/progress;
- `why`/`why_now` as a tooltip;
- blog/wiki/tool links;
- mandatory percentage;
- step parameters and change reasons;
- optional plugin or instructions popup.

Relevant implementation is in:

- `frontend_tkinter_parameter_editor_documentation_frame.py` (`ardupilot_methodic_configurator/frontend_tkinter_parameter_editor_documentation_frame.py:114`)
- `frontend_tkinter_parameter_editor.py` (`ardupilot_methodic_configurator/frontend_tkinter_parameter_editor.py:1320`)
- `data_model_configuration_step.py` (`ardupilot_methodic_configurator/data_model_configuration_step.py:65`)

## 4. Complete ArduPlane step inventory

Legend:

- `F`, `D`, `A`: forced, derived or automatically added by JSON.
- `External`: values are expected from another tool or firmware operation.
- `N missing`: absent from `normal_plane` although defined in JSON.
- “Copter/VTOL” means the repository content uses multicopter controller parameters; it is not being assumed correct for fixed-wing Plane.

| Step | Current content and automation | Dependency/action/status |
|---|---|---|
| 02 IMU temperature setup | Nine `BRD_HEAT/INS_TCAL/INS_RAW/LOG_*` values. F: `INS_TCAL1_ENABLE`, `LOG_BITMASK`, `LOG_DISARMED`, `INS_RAW_LOG_OPT`; D: TCAL2/3 enable; conditional heat target. | First optional experiment; leads to 03/04. Substantive common step. Useful comments. |
| 03 IMU temperature results | 63 `INS_TCAL{1..3}_{ACC*,GYR*,TMIN,TMAX,ENABLE}` records; conditional A/D for IMU2/3. | Requires 02; External results. Substantive common step but sparse comments. |
| 04 IMU temperature finish | `LOG_DISARMED`, `BRD_HEAT_TARG`, `BRD_HEAT_LOWMGN`; F disables disarmed logging. | Requires 03; prerequisite to routine operation. **N missing.** |
| 05 Board orientation | `AHRS_ORIENTATION`; D conditionally attempts `FRAME_CLASS` and `Q_FRAME_CLASS`; orientation plugin. | Precedes sensor calibration. Fixed-wing frame classification remains unclear; Q-centric derivation. |
| 06 RC receiver | `RC_OPTIONS`, `RC_PROTOCOLS`, `RSSI_TYPE`, serial protocol; D protocol and ExpressLRS `FLTMODE_CH`. | Prerequisite for 07–09, modes and failsafes. Substantive common step. |
| 07 RC controller | `ARMING_RUDDER`, `RC5–9_OPTION`; D ExpressLRS `RC5_OPTION`. | Requires 06; later RC calibration/modes depend on it. Partial Plane content. |
| 08 Telemetry | Three serial/RTSCTS parameters. | Depends on chosen connection/possibly RC. Substantive but example-specific and uncommented. |
| 09 ESC telemetry | Serial telemetry and `SERVO_BLH_TRATE`; D scripting, `MOT_PWM_TYPE`, serial protocols; ESC RPM plugin. | Depends on RC/telemetry/ESC component. Uses Copter `MOT_PWM_TYPE` rather than Plane/QuadPlane-specific ownership. |
| 10 Battery monitor | `BATT_MONITOR`; D monitor type/I²C; battery plugin. | Required before 11 and battery evidence. Substantive common step. |
| 11 Battery | Nine `BATT_*` thresholds/capacity/actions; F low/critical actions; D voltage/capacity and `MOT_BAT_VOLT_*`. | Requires 10. Battery thresholds are relevant; motor-voltage scaling is Copter/QuadPlane-specific. |
| 12 GNSS | Safety default, GNSS mode/type/position and serial protocol. | Required before navigation, compass flight and Remote ID. Substantive but normal template uses legacy `GPS_*` spellings versus 4.7 `GPS1_*`. |
| 13 Initial ATC | File contains only `INS_ACCEL_FILTER`, `INS_GYRO_FILTER`; JSON F/D contains extensive `ATC_*`, `MOT_THST_*` and propeller-derived multicopter values. | Intended before first flight. Actual fixed-wing controller initialization is missing. |
| 14 Mission Planner mandatory hardware | Accel/compass calibration, RC1–9 calibration, flight modes, fence, `SERVO1–4_FUNCTION/MIN/MAX/TRIM/REVERSED`, trims and filters. External Mission Planner import. | Depends on device drivers and RC/GNSS. Many later domains depend on it. Substantive but overly broad and aircraft-instance-specific. |
| 15 General configuration | RTC, IMU position/filter, scheduler rate, scripting. JSON deletes `ARMING_CHECK`. | Before safety/first flight. Weak catch-all; overwrites `INS_ACCEL_FILTER` from 13. |
| 16 Safety setup | `ARMING_CHECK`, `FENCE_TYPE`; F all arming checks. | Must precede flight. Present but incomplete: Plane throttle, GCS, RC and navigation failsafe ownership is elsewhere or absent. |
| 17 Remote ID | Four `DID_*` parameters. | Depends on GNSS/pressure; optional. Common content. |
| 18 OSD | 91 `OSD*` layout/display parameters. | Depends on telemetry/battery/sensors; optional. Substantive but uncommented. |
| 19 Motor | Only `SERVO_BLH_POLES`; D pole-count variants. | Supposed propulsion prerequisite. Skeletal and primarily multicopter-oriented. |
| 20 ESC | `MOT_SPIN_*`, `MOT_THST_EXPO`, DShot options and duplicated `SERVO1–4` endpoints; motor-test plugin. | Requires output assignment. Fixed-wing throttle/output ownership is incomplete; `MOT_*` is Copter/QuadPlane content. |
| 21 Motor notch setup | `INS_HNTCH_*`, sampling/rate; F enable; D frequency/mode. | Requires valid motor/ESC telemetry and precedes first logging flight. Generally reusable, but some generated parameter names are not visible with the current fixed-wing default state. |
| 22 Motor notch logging | Raw/batch/log settings; F logging plus `MOT_HOVER_LEARN`. | Requires 21; precedes first flight and 25. `MOT_HOVER_LEARN` is Copter-specific. |
| 23 Optional PID adjustment | `PTCH_RATE_*`, `PTCH2SRV_*`, `RLL_RATE_*`, `RLL2SRV_*`; instructions popup. | Requires mechanical outputs and flight envelope. This is the clearest substantive fixed-wing tuning step. |
| 24 Throttle controller | `ATC_THR_MIX_MAN`, `PSC_ACCZ_I/P`; D from `MOT_THST_HOVER`. | Explicitly Copter altitude-controller logic. Not a fixed-wing throttle/TECS step. |
| 25 Motor notch results | Six `INS_HNTCH_*` results. | Requires the logging flight from 22. Reusable concept, although template applicability needs validation. |
| 26 EKF configuration | `EK3_ACC_P_NSE`, `EK3_ALT_M_NSE`. | Requires calibrated sensors and flight evidence. Common but skeletal. |
| 27 PID-notch logging | Four logging parameters. | Requires a valid controller/tuning path. Common logging mechanism. |
| 28 PID-notch results | `ATC_RAT_*_NEF/NTF`, `PSC_ACCZ_*`. | Copter/QuadPlane controller targets; not fixed-wing `RLL_RATE/PTCH_RATE` ownership. |
| 29 QuickTune setup | `QUIK_*`, `SCR_ENABLE`; downloads `Copter-4.5/.../VTOL-quicktune.lua`. | Requires a hover-capable VTOL. No fixed-wing/QuadPlane applicability boundary. |
| 30 QuickTune results | Ten `ATC_RAT_*` parameters; External VTOL QuickTune result. | Requires 29. Copter/QuadPlane-only. |
| 31 in-flight MAGFit setup | `MAGH_*`, scripting; downloads `copter-magfit-helper.lua`. | Requires safe autonomous flight. Concept may be reusable, but helper and flight-path assumptions are explicitly Copter-derived. |
| 32 MAGFit results | Compass fit/offset/orientation data; External MAGFit. | Requires 31. Result storage is common; second-quicktune rationale is copied. |
| 33 Evaluate tune, FF disabled | `ATC_RATE_FF_ENAB=0` plus logging. | Copter/QuadPlane evaluation path. |
| 34 Evaluate tune, FF enabled | `ATC_RATE_FF_ENAB=1`. | Requires 33; Copter/QuadPlane path. |
| 35 Roll autotune setup | `AUTOTUNE_AGGR`, F `AUTOTUNE_AXES=1`. | AutoTune concept exists in Plane, but metadata and result parameter ownership are copied from Copter. |
| 36 Roll autotune results | `ATC_ACCEL_R_MAX`, `ATC_ANG_RLL_P`, `ATC_RAT_RLL_*`; External. | Wrong controller namespace for fixed-wing Plane. |
| 37 Pitch autotune setup | `AUTOTUNE_AGGR`, F `AUTOTUNE_AXES=2`. | Same applicability problem as 35. |
| 38 Pitch autotune results | `ATC_ACCEL_P_MAX`, `ATC_ANG_PIT_P`, `ATC_RAT_PIT_*`; External. | Wrong fixed-wing result namespace. |
| 39 Yaw autotune setup | `AUTOTUNE_AGGR`, axes and `ATC_RAT_YAW_FLTD`. | Copter/QuadPlane path. |
| 40 Yaw autotune results | Five `ATC_*YAW*` results; External. | Copter/QuadPlane path. |
| 41 Yaw-D autotune setup | `AUTOTUNE_AGGR`, `AUTOTUNE_AXES=8`, `AUTOTUNE_MIN_D`. | Copter/QuadPlane path. |
| 42 Yaw-D results | Five `ATC_*YAW*` results; External. | Copter/QuadPlane path. |
| 43 Roll/pitch retune setup | `AUTOTUNE_AGGR`, `AUTOTUNE_AXES=3`. | Copter/QuadPlane path. |
| 44 Roll/pitch retune results | Ten `ATC_*` results; External. | Copter/QuadPlane path. |
| 45 Autotune finish | `ATC_THR_MIX_MAX`; F same. | Copter/QuadPlane-only finish. |
| 46 PID derivative FF | Four `ATC_RAT_*_D_FF`/`PSC_ACCZ_D_FF`. | Copter/QuadPlane analytical tuning. |
| 47 Wind-speed estimation | `EK3_DRAG_*`, replay/disarmed logging. | Copter drag-coefficient method; not an airspeed-sensor calibration step. |
| 48 Barometer compensation | Seven `BARO1_WCF_*`. | Potentially common, but evidence-gathering instructions are Copter-based. |
| 49 Wind-speed finish | Restores replay/disarmed logging. | Requires 47/48. Common cleanup. |
| 50 SystemID input roll | `SID_*`, `ATC_*`, `ANGLE_MAX`, modes/tuning/logging. | Multicopter identification setup. |
| 51 SystemID input pitch | Same family, `SID_AXIS=2`. | Multicopter identification setup. |
| 52 SystemID input yaw | Same family, `SID_AXIS=3`. | Multicopter identification setup. |
| 53 SystemID mixer roll | Same family, `SID_AXIS=10`. | Multicopter identification setup. |
| 54 SystemID mixer pitch | `ATC_*`, `SID_*`, axis 11. | Multicopter identification setup. |
| 55 SystemID mixer yaw | `ATC_*`, `SID_*`, axis 12. | Multicopter identification setup. |
| 56 SystemID mixer thrust | `PSC/ATC/SID_*`, axis 13. | Multicopter thrust identification. |
| 57 Analytical PID optimization | `ARMING_CHECK`, `ATC_RATE_FF_ENAB`, `PSC_ACCZ_I`, `SID_AXIS`; F corresponding values. | Multicopter controller optimization, not fixed-wing Plane tuning. |
| 60 Position controller | `LOIT_*`, `PSC_*`, `WPNAV_*`, `ANGLE_MAX`; F logging. | Copter navigation controller content, not Plane L1/TECS/navigation ownership. |
| 61 Guided operation | `FS_GCS_ENABLE`, rally and `SYSID_MYGCS`. | Plane 4.7 exposes different names such as `FS_GCS_ENABL`; content is stale/Copter-derived. |
| 62 Precision landing | `PLND_*`, `LAND_ALT_LOW`, `LAND_SPEED`, `PSC_POSXY_P`, RC options. | Copter Precision Landing, not ArduPlane fixed-wing landing. |
| 63 Optical-flow setup | EKF source and `FLOW_*`; optional jump. | Optional/common concept but **N missing**. |
| 64 Optical-flow results | Flow scale/orientation results; External FlowCal. | Requires 63; **N missing**. |
| 65 Replace GNSS with optical flow | EKF source and RC options. | Requires 63/64; **N missing**. |
| 66 Everyday use | Battery failsafe actions, logging, `RTL_ALT`, `RTL_CLIMB_MIN`. | Final production configuration. Contains the concrete stale Plane `RTL_ALT` problem. |

## 5. Complete associated `.param` inventory

### Templates

| Template | Default snapshot | Loaded step files | JSON-referenced present | Missing referenced files | Unreferenced files |
|---|---:|---:|---:|---|---|
| `ArduPlane/normal_plane` | 1,181 parameters; firmware metadata says ArduPlane 4.5.6 | 60 | 59/63 | 04, 63, 64, 65 | `15_range_finder.param` |
| `ArduPlane/empty_4.7.x` | 990 currently exposed parameters | 64 | 63/63 | None | `59_range_finder.param` |

All files parsed successfully. None was empty.

The complete referenced inventory is the 63 filenames in the table above. Both templates also use `00_default.param` indirectly for defaults and validation.

### Unreferenced mixed files

Both files contain the same 25 conceptual settings:

``text
ARSPD_BUS, ARSPD_DEVID, ARSPD_FBW_MAX, ARSPD_OFFSET, ARSPD_RATIO,
ARSPD_TYPE, ARSPD_USE, FBWB_CLIMB_RATE, LAND_ABORT_THR,
LAND_FLARE_ALT, LAND_FLARE_SEC, LIM_ROLL_CD, RNGFND_LANDING,
RNGFND1_MAX_CM, RNGFND1_MIN_CM, RNGFND1_TYPE, RSSI_TYPE,
RTL_AUTOLAND, SERIAL1_BAUD, SERIAL1_PROTOCOL, THR_FS_VALUE,
THR_MAX, TRIM_ARSPD_CM, TRIM_PITCH_CD, WP_RADIUS
``

This mixes at least seven ownership domains:

1. airspeed hardware/calibration;
2. flight-envelope speeds;
3. throttle failsafe/output;
4. landing flare;
5. rangefinder;
6. RTL/autoland;
7. general navigation limits.

It has no sequence metadata, no `why`, no `why_now`, no conditions and no comments.

### Documentation quality

- `normal_plane`: 60 non-default `.param` files, 652 parameter records; 13 files have no comments.
- `empty_4.7.x`: 64 files, 685 records; 44 files have no comments.
- Comments that exist are mostly trailing change reasons, not full authoring guidance.
- Sequence metadata provides `why`/`why_now` for every JSON step, but much of it describes Copter behavior rather than Plane behavior.

## 6. Current Plane dependency graph

The current declared sequence is effectively:

``text
IMU temperature
  02 → 03 → 04
             ↓
board/communications/power/sensors
  05 → 06 → 07 → 08 → 09
             10 → 11
             12
             13
               ↓
monolithic hardware calibration
             14
               ↓
general/safety/optional displays
  15 → 16 → 17 → 18
               ↓
Copter/VTOL propulsion and first-flight path
  19 → 20 → 21 → 22 → first flight → 24/25/26
             ↘ 23 fixed-wing PID adjustment
               ↓
Copter/VTOL tuning campaign
  27 → 28 → 29 → 30 → 31 → 32 → 33 … 46
               ↓
Copter wind/SystemID/controller campaign
  47 → 48 → 49 → 50 … 57
               ↓
undocumented mixed Plane file
  59_range_finder
               ↓
Copter navigation/precision landing
  60 → 61 → 62
               ↓
optional optical flow
  63 → 64 → 65
               ↓
everyday use
  66
``

Concrete dependency defects:

- `empty_4.7.x/59_range_finder.param` configures airspeed, throttle failsafe and landing only after the method has already requested numerous test flights.
- Fixed-wing pitch/roll tuning in step 23 has no prior canonical ownership for flight-envelope speeds, airspeed calibration, control-surface geometry or output-direction verification.
- Plane landing depends on airspeed and potentially flaps/rangefinder, but those domains have no canonical prerequisite steps.
- Step 60 consumes Copter `LOIT/PSC/WPNAV` configuration instead of Plane navigation-controller configuration.
- Step 62 is Copter precision landing and cannot serve as fixed-wing landing ownership.
- Step 66 attempts routine RTL configuration using a Copter parameter name/unit.
- The normal template’s step 13 filter results are overwritten before flight:
  - `INS_ACCEL_FILTER`: 10 in step 13, 20 in step 15.
  - `INS_GYRO_FILTER`: 46 in step 13, 20 in step 14.
- Many transient duplicates are intentional—logging modes, AutoTune axes, result capture—but AMC stores no explicit reason that later steps invalidate or supersede earlier ones.

## 7. Configuration-domain coverage

| Domain | Classification | Evidence |
|---|---|---|
| Vehicle/frame basics | PRESENT BUT INCOMPLETE | Board orientation exists; frame derivation is primarily `FRAME_CLASS/Q_FRAME_CLASS`, with no substantive fixed-wing airframe/mixer method. |
| Servo/output assignment | PRESENT BUT QUESTIONABLE OWNERSHIP | Step 14 owns assignment/calibration; step 20 repeats endpoints. |
| RC input | PRESENT AND SUBSTANTIVE | Steps 06, 07 and RC calibration in 14. |
| Control surfaces | PRESENT BUT INCOMPLETE | Functions/reversal exist in example values; no explicit mechanical range, direction or movement-validation method. |
| Elevon/V-tail/tail type | ABSENT | No canonical ownership found. |
| Throttle/motor | PRESENT BUT INCOMPLETE | ESC telemetry and motor test exist, but configuration is predominantly `MOT_*` multicopter content. |
| Battery/power | PRESENT AND SUBSTANTIVE | Steps 10–11, subject to firmware-instance validation. |
| GNSS/navigation sensor | PRESENT BUT INCOMPLETE | Step 12 handles receiver basics; navigation-controller ownership is wrong later. |
| Compass | PRESENT BUT QUESTIONABLE ORDER/OWNERSHIP | Calibration in 14 and MAGFit in 31–32; MAGFit helper is Copter-specific. |
| Attitude/EKF prerequisites | PRESENT BUT INCOMPLETE | Orientation/calibration/EKF noise exist; fixed-wing controller prerequisites are incomplete. |
| Airspeed | PRESENT BUT QUESTIONABLE ORDER/OWNERSHIP | Only in unreferenced mixed step 15/59. |
| Flight modes | PRESENT BUT QUESTIONABLE OWNERSHIP | Embedded in Mission Planner step 14 rather than a dedicated operational/mode strategy. |
| Failsafes | PRESENT BUT INCOMPLETE | Battery and arming/fence are present; Plane throttle/GCS/RTL ownership is fragmented or stale. |
| Takeoff | ABSENT | No fixed-wing `TKOFF_*` method. `TKOFF_RPM_MIN` is a Copter-derived conditional. |
| Landing | PRESENT BUT INCOMPLETE | Two flare values in the unreferenced mixed file; most Plane landing parameters have no owner. |
| Flaps | ABSENT | No `LAND_FLAP_PERCNT`, flap output or deployment method. |
| Spoilers/crow | ABSENT | No ownership found. |
| TECS | ABSENT | No substantive `TECS_*` configuration. |
| Fixed-wing pitch/roll control | PRESENT BUT INCOMPLETE | Step 23 is substantive; surrounding setup/results are Copter `ATC_*`. |
| AutoTune | PRESENT BUT QUESTIONABLE | Setup names are potentially shared, but result capture and instructions are Copter-controller-specific. |
| RTL | PRESENT BUT INCORRECT | Mixed file has `RTL_AUTOLAND`; step 66 uses stale `RTL_ALT`. |
| Mission/navigation | PRESENT BUT INCORRECT | Step 60 is Copter position-controller content. |
| Rangefinder | PRESENT BUT QUESTIONABLE ORDER/OWNERSHIP | Unreferenced 15/59 mixed file. |
| Optical flow | PRESENT BUT INCOMPLETE | Generic steps exist in empty template but not normal template. |
| Remote ID/OSD | PRESENT AND SUBSTANTIVE | Steps 17–18. |

## 8. Landing-related configuration ownership map

| Landing domain | Current owner | Current content | Assessment |
|---|---|---|---|
| Landing airspeed | No JSON owner | Mixed file has `TRIM_ARSPD_CM`, `ARSPD_FBW_MAX`; no `LAND_PF_ARSPD` | No defensible destination for landing analysis. |
| Preflare | No JSON owner | No `LAND_PF_ALT` or `LAND_PF_SEC` | Missing. |
| Flare | No JSON owner | Mixed file has `LAND_FLARE_ALT`, `LAND_FLARE_SEC` | Content exists, ownership absent. |
| Flaps | None | No `LAND_FLAP_PERCNT`; servo assignment only in 14 | Missing. |
| Spoiler/crow | None | None found | Missing. |
| Landing pitch | No JSON owner | Mixed file has legacy `TRIM_PITCH_CD`; no `LAND_PITCH_DEG` | Missing landing-specific ownership. |
| Geometry/slope | No JSON owner | `WP_RADIUS` and `RTL_AUTOLAND` mixed in; no coherent `LAND_*` geometry step | Incomplete. |
| Rangefinder | No JSON owner | `RNGFND_LANDING`, type and min/max in mixed file | Usable content but wrong structure and unclear 4.7 names/units. |
| Airspeed hardware/calibration | No JSON owner | Seven `ARSPD_*` fields in mixed file | Must precede airspeed-dependent landing work. |
| Copter precision landing | Step 62 | `PLND_*`, `LAND_SPEED`, `PSC_POSXY_P` | Not a fixed-wing landing destination. |

A defensible future dependency chain is:

``text
airspeed hardware/calibration
    + output/control-surface assignment
    + flight envelope
    + optional rangefinder setup
        → flaps/spoilers
        → landing geometry/preflare/flare/pitch
        → RTL/autoland and mission validation
``

That is a trace of ownership requirements, not a recommendation for numerical values.

## 9. Existing log-analysis → configuration-step capability

`LogAnalysis` (`ardupilot_methodic_configurator/log_analysis/data_model_log_analysis_result.py:16`) already supports:

``text
related_step
param_name
suggested_value
timestamp_us
value
``

`LogAnalysisResult` also has an overall `related_step`.

Therefore:

- An analysis can already point to a sequence step without backend changes.
- Different outcomes in one analysis can point to different steps.
- “First relevant correction step” can be represented by setting the outcome’s `related_step` to the canonical owner.
- `find_configuration_step_for_parameter()` can resolve an owner from `forced_parameters`, `derived_parameters` or `add_parameters`.

However:

- `find_configuration_step_for_parameter()` (`ardupilot_methodic_configurator/log_analysis/utils.py:40`) raises when a parameter has multiple JSON owners.
- The Plane JSON currently has many multiple owners, including `ARMING_CHECK`, `LOG_BITMASK`, `AUTOTUNE_AXES`, `ATC_RATE_FF_ENAB` and `SID_AXIS`.
- Downstream dependencies are not represented.
- Landing observational outcomes currently do not assign `param_name`, `suggested_value` or `related_step`.

The first relevant-step workflow therefore needs canonical sequence ownership, not new log-analysis infrastructure. Automatic “repeat these downstream steps” behavior would require future dependency metadata, but that is not required to start directing users to a correct first step.

## 10. Comparison with mature AMC methods

### Reusable Copter patterns

ArduCopter demonstrates useful method structure:

- mechanical/component data before tuning;
- setup/result pairs for experiments;
- temporary logging settings followed by cleanup;
- explicit `why` and `why_now`;
- derived values from component specifications;
- external-tool/result steps;
- optional phase jumps;
- plugins for complex calibration/test operations;
- progressive setup → first flight → evidence-based tuning → everyday configuration.

### Copter-specific patterns that must not be copied

The following must be validated or replaced for Plane:

- `MOT_SPIN_*`, `MOT_THST_*`, `MOT_HOVER_LEARN`;
- `ATC_ANG_*`, `ATC_RAT_*`, `ATC_THR_MIX_*`;
- `PSC_ACCZ_*`, `PSC_POSXY_*`;
- VTOL QuickTune;
- multicopter SystemID input/mixer axes;
- `ANGLE_MAX`, `LOIT_*`, Copter `WPNAV_*`;
- `PLND_*` precision landing;
- Copter `RTL_ALT` naming and centimetre convention;
- Copter-specific MAGFit flight helper and tuning flight assumptions.

The Plane JSON’s ordered keys are identical to Copter’s, and most metadata differs only in blog URLs. That is repository evidence of scaffolding reuse, not evidence that the behavior is appropriate for Plane.

## 11. Findings

### P0 — configuration correctness / safety ordering

| Finding | Exact files/current behavior | Smallest likely correction | Prerequisite and tests |
|---|---|---|---|
| P0-1: stale Plane RTL altitude setting | Both `normal_plane/66_everyday_use.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/normal_plane/66_everyday_use.param:1`) and `empty_4.7.x/66_everyday_use.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/empty_4.7.x/66_everyday_use.param:1`) set `RTL_ALT=3500`. Plane 4.7 defaults expose `RTL_ALTITUDE`, not `RTL_ALT`. The comment claims a 35 m clearance, so blindly renaming would also be unsafe because Plane’s unit/value contract differs. | Validate current Plane 4.7 source metadata, then replace the stale name/value/comment with the correct Plane parameter and canonical unit. Do not mechanically rename `3500`. | ArduPlane source/docs validation required. Test that the parameter exists in Plane metadata and its value/comment use the documented unit. |
| P0-2: preflight-critical domains placed after flight campaign | `empty_4.7.x/59_range_finder.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/empty_4.7.x/59_range_finder.param:1`) places `THR_FS_VALUE`, airspeed configuration, flight-envelope values and landing setup after steps 21–57. | Establish canonical earlier owners for throttle failsafe, airspeed and landing prerequisites; leave step 59 rangefinder-only or move it according to validated sensor dependencies. | Requires Plane-domain review. Add order assertions: throttle failsafe/flight envelope/airspeed must precede first-flight and dependent tuning steps. |

### P1 — major missing or structurally weak Plane content

| Finding | Evidence | Smallest likely correction |
|---|---|---|
| P1-1: sequence is substantially a Copter method | All 63 step keys match Copter; 26 empty-template files have identical parameter-name sets; steps 24 and 28–62 prominently use Copter controller domains and documentation. | Replace one domain at a time, beginning with safety/RTL and preflight fixed-wing ownership. Do not rewrite all 63 steps at once. |
| P1-2: fixed-wing preflight foundation is incomplete | No canonical steps for airspeed, fixed-wing flight envelope, TECS, takeoff, flap/spoiler configuration or landing prerequisites. | Introduce explicit ownership in dependency order with firmware-validated parameter sets. |
| P1-3: control-surface method is not explicit | Servo functions/calibration are buried in step 14; motor/ESC step 20 repeats endpoints; no explicit direction/range/mixer validation exists. | Split conceptual ownership between output assignment, control-surface mechanics and propulsion validation. |
| P1-4: fixed-wing tuning path breaks after step 23 | Step 23 uses Plane `RLL_RATE/PTCH_RATE`; steps 24 and 28–57 revert to `MOT/ATC/PSC/SID` multicopter content. | Design a fixed-wing tuning sequence around Plane rate controllers, AutoTune outputs and TECS. Keep QuadPlane tuning conditional or template-specific. |
| P1-5: navigation and landing tail is the wrong vehicle domain | Steps 60–62 are Copter position control, Guided and Precision Landing. | Replace with Plane navigation/L1/RTL/mission/landing domains after source validation. |
| P1-6: template and metadata inventories disagree | Normal lacks 04/63/64/65 and has duplicate prefix 15; both rangefinder files lack JSON entries. | Reconcile file presence and JSON entries, with `old_filenames` migration and a template/sequence consistency test. |

### P2 — ownership/dependency/order improvements

| Finding | Evidence | Smallest likely correction |
|---|---|---|
| P2-1: initial filter derivation is overwritten | `INS_ACCEL_FILTER` 10→20 at 13→15; `INS_GYRO_FILTER` 46→20 at 13→14. | Assign one canonical owner or explicitly document the temporary-to-final transition. |
| P2-2: Mission Planner step is overly broad | Step 14 mixes accel, compass, RC, modes, fence and servo outputs. | Split only when each extracted domain has a validated prerequisite and owner. |
| P2-3: mixed rangefinder file has ambiguous ownership | It mixes 25 parameters across seven domains and has no metadata. | Separate rangefinder from airspeed, landing, throttle and navigation. |
| P2-4: no downstream invalidation model | Returning to an earlier step does not identify later steps that should be repeated. | Initially document downstream repeats in `why_now`/instructions. Consider dependency metadata only after multiple concrete consumers exist. |
| P2-5: log-analysis owner lookup requires uniqueness | Multiple JSON owners cause `find_configuration_step_for_parameter()` to raise. | Ensure each durable parameter has one canonical correction step. Treat temporary experiment settings explicitly rather than as competing owners. |
| P2-6: `normal_plane` is version-stale | Component metadata reports ArduPlane 4.5.6 while the maintained empty method targets 4.7.x. | Decide whether it remains a historical example or regenerate/migrate it deliberately. |

### P3 — documentation/usability

- Numerous Plane steps retain Copter wiki pages, Copter scripts and Copter-specific wording.
- `why`/`why_now` frequently describe hover, AltHold or multicopter dynamics.
- The unreferenced rangefinder files have no comments.
- Forty-four `empty_4.7.x` step files contain no parameter comments.
- Several titles hide mixed responsibility, especially steps 14, 15, 20, 31, 60 and 62.
- Typographical issues remain, such as “It con only be done” in optical-flow metadata.

### DEFER

- Automatic downstream-step invalidation.
- General dependency-graph UI.
- Whole-step conditional expressions.
- Plane tuning-report visualization; `_update_tuning_report()` is currently hard-coded to Copter `ATC_*` parameters.
- Landing-analysis recommendation/scoring logic.
- Wiring landing outcomes to steps before canonical Plane ownership exists.
- Separate longitudinal configuration history beyond the existing files/tuning report.

## 12. Configuration content vs infrastructure

### Configuration content

This is the dominant problem:

- wrong vehicle-domain steps;
- missing fixed-wing domains;
- unsafe ordering of preflight parameters;
- stale parameter names/units;
- ambiguous ownership and overwrites;
- missing metadata for actual files;
- inconsistent template inventories;
- copied or misleading instructions.

### AMC method infrastructure

Existing infrastructure is sufficient for the first several corrections.

Genuine limitations are:

1. No explicit prerequisite/dependent-step graph.
2. No automatic stale/downstream-repeat state.
3. No whole-step `if` condition.
4. Parameter-to-step lookup demands unique ownership.
5. The tuning report is Copter-specific.

None requires a shared architecture change before correcting Plane sequence content.

### Log-analysis integration

Current result structures already support future mappings. The missing prerequisite is a stable, unique Plane owner for each configuration domain. Landing analysis should remain unchanged until that method content exists.

## 13. Recommended first implementation task

The highest-value, lowest-risk first PR is:

> Correct the Plane “Everyday use / RTL” safety step for ArduPlane 4.7.x.

Scope:

1. Validate the exact ArduPlane 4.7 `RTL_ALTITUDE` semantics and units.
2. Replace the stale Copter `RTL_ALT` entry in both Plane templates.
3. Validate `RTL_CLIMB_MIN` and battery-failsafe entries for Plane 4.7.
4. Update step 66’s Plane-specific rationale/documentation.
5. Add a focused test that all step-66 parameters exist in the applicable Plane metadata/default surface and that documented units agree.

This fixes a concrete operational error without requiring numbering changes or shared infrastructure.

## 14. Proposed small-PR implementation sequence

1. **Everyday-use/RTL safety:** correct step 66 names, units and Plane documentation.
2. **Sequence/template conformance:** resolve normal’s duplicate prefix 15, missing 04/63–65 files and undocumented 15/59 files; add consistency tests.
3. **Fixed-wing frame and output foundation:** define airframe type, servo functions, mixers, direction/range and motor-output validation.
4. **Power/propulsion/failsafes:** validate steps 09–11, 16, 19–20 for fixed-wing versus QuadPlane.
5. **Airspeed and flight envelope:** establish canonical sensor/calibration and `AIRSPEED_*`/`ARSPD_*` ownership before first flight.
6. **Fixed-wing takeoff:** add validated `TKOFF_*` ownership and prerequisites.
7. **Fixed-wing landing:** establish approach, preflare, flare, pitch, flaps/spoilers, optional rangefinder and autoland ownership.
8. **Fixed-wing attitude tuning:** retain useful step 23 content and replace copied `ATC_*` result paths with Plane controller semantics.
9. **TECS:** add altitude/speed-energy configuration after airspeed and basic attitude tuning.
10. **Plane navigation/RTL/mission:** replace steps 60–62 with appropriate Plane navigation domains.
11. **QuadPlane applicability:** retain VTOL-only steps only through explicit template or applicability boundaries.
12. **Log-analysis mappings:** once ownership is stable, map evidence to the first corrective step.
13. **Dependency UX:** only then evaluate whether explicit downstream-repeat metadata is justified.

## 15. Questions requiring Amílcar / ArduPlane developer input

1. Is the primary method intended for conventional fixed-wing Plane, QuadPlane, or both?
2. If both, should applicability be template-specific or should one sequence include explicit branching?
3. Is ArduPlane 4.7.x the intended minimum baseline for this work?
4. Should `normal_plane` remain a 4.5.6 historical example or be migrated?
5. Was step 59 intentionally reserved for rangefinder, and was `normal_plane/15_range_finder.param` intended to migrate there?
6. Which first-flight campaign should the Plane method prescribe before AutoTune/TECS work?
7. Which fixed-wing airspeed parameters are canonical for configured-sensor versus synthetic-airspeed vehicles?
8. Which control-surface layouts must the first method support: conventional, elevon, V-tail, flaperon, crow?
9. Should landing configuration be one step or separate airspeed, flap/spoiler, geometry and flare steps?
10. Which Plane AutoTune results should be imported, and at what point do they invalidate TECS or landing tuning?
11. Should the Copter MAGFit helper be replaced with a Plane flight path or omitted pending validation?
12. Should configuration steps with transient ownership be excluded from parameter-to-correction-step resolution?

## 16. Exact files likely involved in the first task

Expected first-task files:

- `configuration_steps_ArduPlane.json` (`ardupilot_methodic_configurator/configuration_steps_ArduPlane.json:1378`)
- `normal_plane/66_everyday_use.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/normal_plane/66_everyday_use.param:1`)
- `empty_4.7.x/66_everyday_use.param` (`ardupilot_methodic_configurator/vehicle_templates/ArduPlane/empty_4.7.x/66_everyday_use.param:1`)
- Focused additions to `test_vehicle_template_param_files.py` (`tests/test_vehicle_template_param_files.py:1`), or a new Plane-method content test if repository convention favors separation.

Generated translation files should only be updated if the JSON text changes and repository workflow requires it.

## 17. Test/validation strategy

For each small PR:

1. Validate JSON against `configuration_steps_schema.json`.
2. Parse every changed `.param` file through `ParDict`.
3. Verify changed parameters exist in the targeted Plane firmware metadata.
4. Assert units and scaling where safety-relevant.
5. Test template files and JSON entries correspond exactly, allowing only explicitly documented exceptions.
6. Test numeric prefixes are unique and ordered.
7. Test required prerequisites precede consumers.
8. Test each durable parameter has one canonical owner.
9. Permit explicitly documented temporary overrides only where setup/result/cleanup semantics require them.
10. Instantiate both `normal_plane` and `empty_4.7.x` projects and inspect the resulting ordered steps.
11. Exercise derived/forced expressions with fixed-wing and QuadPlane FC parameter surfaces.
12. Confirm later compounding gives the intended final value.
13. Run existing configuration-step, template, migration and parameter-editor tests.
14. Do not use Copter defaults as the oracle for Plane-specific parameters.

## 18. Git status / diff confirmation

``text
git status --short:
<empty>

git diff --stat:
<empty>

git diff --check:
PASS
``

## 19. READ-ONLY AUDIT — NO FILES CHANGED
