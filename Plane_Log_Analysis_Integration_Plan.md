# Plane Log Analysis Integration Plan

> **Updated:** 2026-09-11
> **Current AMC task:** Step 66 — ArduPlane 4.7.x Everyday use / RTL correctness
> **Configuration-method audit:** COMPLETE

## Purpose

Integrate the useful Plane-specific analysis logic from ArduPilotTools
(APT) into ArduPilot Methodic Configurator (AMC), using AMC's existing
log-analysis architecture and avoiding duplicate parser, parameter,
result, reporting, or GUI infrastructure.

This document is the active implementation plan for the AMC work. The
older APT → AMC task list remains useful as migration history, but this
file should track the work from the AMC side.

------------------------------------------------------------------------

## Current Repository State

AMC repository:

``` text
~/MethodicConfigurator
```

Remotes:

``` text
origin   = nflyernz/MethodicConfigurator
upstream = ArduPilot/MethodicConfigurator
```

The Plane landing-analysis migration is now merged upstream.

Final PR:

``` text
ArduPilot/MethodicConfigurator PR #2024
feat(log-analysis): add Plane landing analysis
MERGED 2026-09-10
```

Amílcar squashed the reviewed feature branch before merge, as requested for a
new feature. The final branch history shown by GitHub was reduced to one
feature commit:

``` text
7289471  feat(log-analysis): add ArduPlane landing attempt analysis
```

GitHub records the merge into `ArduPilot:master` as:

``` text
cf06392  merge of PR #2024 into ArduPilot:master
```

The last fully reviewed pre-squash implementation head was:

``` text
299e3797  fix(log-analysis): enforce Plane landing evidence locality
```

Tridge's final automated review at that head concluded:

``` text
APPROVE — no blockers. Everything I blocked on is fixed and properly pinned.
```

Amílcar also approved the changes before squashing and merging them.

Final local validation before merge included:

``` text
Focused Plane landing tests:  208 passed
Affected AMC tests:           305 passed
Reference logs:               4
Operational flights:          10
Landing attempts:             16
Historical APT boundaries:    15 / 16
APT landing regression:       PASS
APT event/timeline regression PASS
```

The sole intentional APT/AMC landing-boundary difference at merge was:

``` text
log_17.bin flight 4
APT: GPS_STOP 2848264090 us
AMC: DISARM   2848866277 us
```

This is the accepted causality correction: post-attempt GPS observations must
not retroactively qualify an earlier low-speed run after the attempt has
already terminated. APT now incorporates the same correction, so its current
`log_17.bin` flight 4 boundary is also DISARM at `2848866277 us` and current
four-log boundary parity is 16/16.

The final four-log AMC fingerprint remained:

``` text
8efe61136e30632afcf87e10ad2e22cdb02a1c015354df4972ef8c32ef1e53d0
```

Final PR CI had 16 successful checks. The remaining `Publish Tests Results`
failure was the repository-wide coverage gate (`88 < fail-under 89`) and was
also failing on `master`; it was not a Plane functional-test failure.

The old `plane-landing-analysis` review branch is historical. Local AMC
`master` was synchronized before the configuration-method audit. The read-only
audit ran on:

``` text
master @ c58eb9f8
```

with a clean worktree. That audit is now the baseline for the next Plane
configuration-method PR.

## PR #1989 Merge and Repository Synchronization

PR #1989 is now merged upstream. The accepted commits include:

``` text
79d8183f  feat(log-analysis): add Plane flight segmentation
c550980e  fix(log_analysis): Filter to U == 1 when that field exists in GPS
```

Amílcar added the GPS `U == 1` filtering fix during review. The accepted
upstream implementation is authoritative.

At the PR #1989 synchronization checkpoint, local `master`, `origin/master`,
and `upstream/master` were synchronized at `e8759fa6`. The obsolete `plane-flight-segment` branch
has been deleted locally and from the fork.

The flight-segmentation implementation remains authoritative shared
infrastructure for the next Plane landing-analysis phase.

# Maintainer Direction

Amílcar confirmed two architectural decisions.

## Reusable Flight Scope

AMC should gain a reusable flight-segment concept.

This should be AMC data-model infrastructure rather than something
hidden inside Plane landing analysis.

APT's existing flight-window implementation is reference behavior only.
It should not be copied into AMC unchanged.

## Initial Firmware Scope

Amílcar confirmed that the initial Plane landing-analysis scope may be
limited to **ArduPlane 4.7.x**. This is an explicit support boundary,
not a generic `>= 4.7` rule; future 4.8+ releases should not be admitted
until validated.

AMC's existing log-version mismatch dialogue does not centrally enforce
this range. The Plane landing availability model therefore owns the
4.7.x applicability check, while the paired analysis model does not
duplicate it.

## BARO Requirement

Amílcar confirmed that **BARO should be mandatory for Plane landing
analysis**. The Plane landing availability model therefore requires
non-empty BARO data with readable finite `TimeUS` and `Alt` fields.

The current availability contract is:

-   mandatory: GPS, LAND, MODE, BARO;
-   optional: ARSP, RFND, CMD, MSG;
-   vehicle: ArduPlane;
-   firmware: ArduPlane 4.7.x only.

A specific BARO-derived metric must still handle sparse or non-finite
samples conservatively; subsystem availability does not imply that every
individual metric can always be produced.

## Flat Analysis Results Initially

Plane landing results should initially use AMC's existing flat
`LogAnalysisResult` model.

A hierarchical per-flight/per-attempt result model should only be
introduced later if real implementation experience demonstrates that the
flat result is insufficient.

------------------------------------------------------------------------

# Maintainer Direction --- Configuration Method Integration

After PR #2024 merged, Amílcar clarified the intended destination for log
analysis inside AMC.

AMC is built around a **method / ordered configuration sequence**. Analysis is
not intended to become an independent tuning engine that invents arbitrary
parameter values. Instead, analysis should identify the earliest relevant
configuration step that addresses the user's observed problem and direct the
user back into the established method. Depending on dependencies, the user may
then need to repeat the following couple of steps as well.

Example principle from Amílcar:

``` text
problem concerns flap deflection
        ↓
identify the step where flap deflection is configured
        ↓
direct the user to repeat that step
        ↓
repeat subsequent dependent steps if required
```

The analysis should not send the user through unrelated configuration areas
(for example GPS configuration for a flap-deflection problem).

Amílcar specifically asked that the next Plane work first improve the
**ArduPlane configuration sequence and the respective `*.param` files**.

The repository audit established that the authoritative AMC metadata file is:

``` text
configuration_steps_ArduPlane.json
```

There is no repository file named `configuration_sequence_ArduPlane.json`.

Only once the ArduPlane method correctly describes a safe, coherent sequence
should Plane log-analysis findings be mapped to the appropriate `related_step`
or configuration process.

This makes the near-term architecture:

``` text
objective Plane log evidence
        ↓
identify configuration domain/problem
        ↓
earliest relevant ArduPlane sequence step
        ↓
AMC's existing step instructions / parameter method
        ↓
repeat dependent following steps where required
```

The configuration method owns the remedy. Plane landing analysis continues to
own the objective evidence and the defensible mapping to the relevant domain or
step.

------------------------------------------------------------------------

# ArduPlane Configuration-Method Audit — COMPLETE

A full read-only audit of the current AMC ArduPlane configuration method was
completed on 2026-09-11 and is preserved in:

``` text
Docs/Implementation/ArduPlane_Configuration_Method_Audit.md
```

Audit baseline:

``` text
Repository: ~/MethodicConfigurator
Branch:     master
HEAD:       c58eb9f8
Worktree:   clean
```

The audit found that AMC's configuration engine is already capable of
supporting narrow Plane improvements. The immediate deficiencies are primarily
**configuration content, ownership and ordering**, not missing shared
infrastructure.

Key findings:

- the 63 Plane step keys currently mirror the Copter sequence;
- substantial later sections still contain Copter/QuadPlane controller and
  workflow content without fixed-wing applicability boundaries;
- important fixed-wing domains lack canonical ownership, including airspeed,
  TECS, takeoff, landing, flaps/spoilers and fixed-wing navigation;
- `59_range_finder.param` is an undocumented mixed file containing airspeed,
  throttle-failsafe, landing, rangefinder, RTL and navigation settings;
- several preflight-critical Plane settings therefore appear after flight and
  tuning stages;
- Step 66 contains a concrete stale Copter-derived RTL setting:
  `RTL_ALT=3500`, while Plane 4.7 exposes `RTL_ALTITUDE` with different
  semantics/units.

The audit's recommended development strategy is **small domain-specific PRs**.
No shared architecture rewrite is required before those corrections.

## Next bounded PR — Step 66 Everyday use / RTL

The first implementation PR is intentionally narrow:

> Make ArduPlane 4.7.x Step 66 **Everyday use / RTL** technically correct and
> Plane-specific.

Include:

- validate exact ArduPlane 4.7.x `RTL_ALTITUDE` semantics and units;
- validate `RTL_CLIMB_MIN`;
- validate the battery-failsafe parameters already owned by Step 66;
- replace stale/wrong Copter-derived names, values or comments;
- update Step 66 Plane-specific `why` / `why_now` metadata as required;
- update both Plane templates consistently;
- add focused tests proving changed parameters exist in the targeted Plane
  metadata/default surface and that safety-relevant units are correct.

Explicitly exclude:

- whole-sequence redesign;
- Step 59 restructuring;
- airspeed, flaps, crow/spoilers, TECS, takeoff or landing redesign;
- `normal_plane` version migration;
- QuadPlane branching;
- log-analysis changes;
- dependency-graph infrastructure;
- Copter changes.

The review question for this PR is deliberately small:

> **Is ArduPlane's final Everyday use / RTL step technically correct for
> ArduPlane 4.7.x?**

------------------------------------------------------------------------

# Governing AMC Log-Analysis Architecture

Plane integration must follow AMC's `ARCHITECTURE_log_analysis.md` as
the default architectural authority.

In particular, new Plane functionality should follow AMC's documented
"Extending the Log Analysis System" path:

-   use the existing availability and analysis model architecture;
-   consume shared `LogData` and `LogAnalysisContext`;
-   add mature models to the existing analysis registry;
-   use existing `LogAvailabilityResult`, `LogAnalysisResult`, and
    `LogSummary` structures;
-   do not modify extraction when the required data is already available
    through `LogData`;
-   keep backend orchestration unaware of Plane subsystem implementation
    details;
-   use the existing frontend/report path rather than introducing a
    Plane-specific presentation pipeline.

This is the default constraint for implementation and for Codex prompts.

Shared backend, context, extraction, or other architectural changes are
not prohibited, but they should not be introduced merely for
convenience. If Plane implementation cannot be completed correctly
through the documented extension path, first identify and demonstrate
the missing architectural capability.

At that point, stop the Plane-specific implementation and review whether
a reusable AMC-native infrastructure change is justified before
modifying the shared architecture.

`FlightSegment` and timestamped parameter history are examples of such
shared requirements discovered during Plane integration. They should not
be treated as precedent for bypassing the documented extension path when
that path is sufficient.

------------------------------------------------------------------------

# Architecture Boundary

AMC already owns:

-   BIN/DataFlash parsing;
-   schema discovery;
-   scaling and units;
-   `LogData`;
-   firmware and vehicle identity;
-   logged parameter extraction;
-   parameter documentation;
-   analysis registration;
-   `LogAnalysisContext`;
-   `LogAnalysisResult`;
-   `LogSummary`;
-   frontend/report transport.

APT infrastructure that must **not** migrate includes:

-   `FlightReader`;
-   pandas telemetry ownership;
-   `FlightLog`;
-   companion `.params` parsing;
-   YAML message selection;
-   standalone CLI orchestration;
-   standalone console presentation;
-   generic APT result wrappers.

The useful migration target is Plane-specific business logic.

------------------------------------------------------------------------

## Configuration / YAML Migration Decision

APT used YAML configuration because the standalone application owned
message selection, parameter lists, parser behavior, detector
thresholds, and some presentation-related settings.

AMC already owns most of those responsibilities.

Therefore APT YAML files should not migrate as a configuration
subsystem.

Specifically:

-   APT message-selection lists are obsolete because AMC parses the
    available log messages into `LogData`.
-   APT parameter-selection lists are obsolete because AMC extracts
    logged `PARM` values into `LogAnalysisContext`.
-   APT parser/scaling configuration is obsolete because AMC owns
    extraction, schemas, scaling, and units.
-   APT presentation-oriented YAML settings should not migrate with
    data-model analysis work.
-   Plane detector heuristics that remain genuinely required should
    initially be explicit typed constants in the Plane detector rather
    than introducing a second YAML/configuration layer.

For the first flight-segment PR, inherited APT heuristics are:

``` text
minimum speed threshold       = 5.0 m/s
start persistence             = 2.0 s
ground/separation persistence = 30.0 s
stall-speed multiplier        = 0.5 × AIRSPEED_STALL
```

These values are migration/reference behavior, not universal ArduPlane
semantics.

If future AMC review determines that any of these values should be
configurable, they should move into an AMC-native configuration
mechanism rather than reintroducing APT YAML ownership.

# AMC Subsystem Integration Path

AMC's documented extension model gives the Plane work a clear eventual
integration point.

A new analysis subsystem should follow AMC's existing availability-model
and analysis-model architecture:

``` text
LogData + LogAnalysisContext
          │
          ▼
Plane landing availability model
          │
          ▼
Plane landing analysis model
          │
          ▼
LogAvailabilityResult + LogAnalysisResult
          │
          ▼
existing AMC result/report/frontend path
```

The availability model should determine whether the log contains
sufficient and appropriate evidence for the Plane landing analysis to
run. The analysis model should consume the shared `LogData` and
`LogAnalysisContext` rather than performing its own extraction or
configuration loading.

Once mature, the Plane availability and analysis models should be added
to AMC's existing analysis registry.

This has several architectural consequences:

-   the extraction backend should not be modified when the required
    messages are already available through `LogData`;
-   backend orchestration should remain unaware of Plane implementation
    details;
-   Plane analysis should not introduce a parallel entry point
    equivalent to APT's standalone `analyse.py`;
-   Plane analysis should return AMC-native `LogAvailabilityResult` and
    `LogAnalysisResult` structures;
-   the existing AMC frontend should consume those results without a
    Plane-specific presentation pipeline.

The reusable `FlightSegment` work sits below this subsystem boundary. It
is shared data-model infrastructure, not itself a registered analysis
subsystem.

The intended layering is therefore:

``` text
AMC extraction/backend
        │
        ├── LogData
        └── LogAnalysisContext
                │
                ▼
      reusable FlightSegment contract
                │
                ▼
      PlaneFlightSegmentDetector
                │
                ▼
      Plane landing availability model
                │
                ▼
      Plane landing analysis model
                │
                ▼
      AMC analysis registry/results
                │
                ▼
      existing AMC frontend/reporting
```

For that reason, the first flight-segment PR should remain below the
registry boundary. Analysis registration and frontend exposure belong
with the later Plane landing subsystem, after the reusable segment
infrastructure has been reviewed.

# Scope Hierarchy

APT's useful conceptual hierarchy is:

``` text
LogData
    ↓
FlightSegment
    ↓
Landing window / landing attempt
    ↓
Landing evidence
    ↓
AMC LogAnalysisResult
```

The exact APT classes do not need to survive.

A single operational flight may contain:

-   several AUTO landing attempts;
-   aborted approaches;
-   go-arounds;
-   restarted landings;
-   AUTO takeoffs;
-   extended armed time before launch or after landing.

For that reason, arm/disarm intervals are not an adequate Plane flight
scope.

------------------------------------------------------------------------

# Flight Segmentation

## Current APT Behavior

The implemented and regression-tested APT `FlightWindowDetector` uses:

-   `GPS.TimeUS`;
-   `GPS.Spd`;
-   optional `AIRSPEED_STALL`.

It does **not** currently use ARM, BARO, altitude, ARSP, MODE, or EV.

Default behavior:

``` text
effective speed threshold
    = max(5 m/s, 0.5 × AIRSPEED_STALL)

flight start
    = first GPS sample in a continuous > threshold run
      lasting at least 2 seconds

flight end
    = GPS sample immediately before a continuous <= threshold run
      lasting at least 30 seconds
```

A low-speed period shorter than 30 seconds does not split the flight, so
go-arounds remain inside one operational flight.

If a flight starts but the log ends before the 30-second ground
condition is confirmed, APT closes the window at the final GPS sample.

This is operational segmentation by heuristic, not an authoritative
ArduPlane takeoff/landing state machine.

## AMC Design Direction

Reusable AMC infrastructure should be limited to a generic immutable
segment contract.

Plane-specific GPS/stall-speed heuristics should remain in a Plane
detector.

Recommended split:

``` text
data_model_flight_segment.py
    FlightSegment
    FlightSegmentationResult

data_model_plane_flight_segment.py
    PlaneFlightSegmentDetector
```

Exact filenames remain subject to AMC naming/review conventions.

------------------------------------------------------------------------

# Proposed FlightSegment Contract

Minimum current requirement:

``` text
FlightSegment
    start_s: float
    end_s: float
    is_complete: bool
```

Semantics:

-   bounds are inclusive;
-   AMC data-model time is canonical seconds;
-   `start_s <= end_s`;
-   `is_complete=True` means end/separation evidence was observed;
-   `is_complete=False` means a flight start was detected but the log
    ended before the normal end condition was confirmed.

Do not store telemetry, parameters, vehicle identity, confidence, or
duplicate duration fields in the segment.

A derived `duration_s` property is acceptable.

A small segmentation result should distinguish:

``` text
segmentation unavailable
```

from:

``` text
segmentation succeeded but no flight was detected
```

------------------------------------------------------------------------

# Time Representation

APT uses integer microsecond `TimeUS` values internally.

AMC scaled message access exposes `TimeUS` in seconds.

For the AMC implementation:

-   use seconds internally;
-   use explicit `_s` suffixes;
-   persistence constants become `2.0` and `30.0`;
-   do not copy APT `_US` constants;
-   convert to microseconds only at an AMC result boundary that
    explicitly requires `timestamp_us`.

This avoids the primary million-fold unit-conversion risk identified in
the architecture audit.

------------------------------------------------------------------------

# First PR

## Objective

Add a reusable AMC flight-segment contract and the first AMC-native
Plane flight detector.

The first PR should be useful on its own but deliberately small.

## Include

-   immutable `FlightSegment`;
-   a small segmentation result contract;
-   Plane-specific detector using AMC-native `LogData`;
-   optional logged `AIRSPEED_STALL` adjustment;
-   existing APT persistence behavior expressed in AMC seconds;
-   incomplete-final-flight representation;
-   containment semantics needed by future child analyses;
-   focused AMC-native tests;
-   concise architecture/docstrings explaining generic versus
    Plane-specific ownership.

## Explicitly Exclude

-   landing-attempt detection;
-   landing metrics;
-   `LAND`, `MODE`, `MSG`, RFND or CMD migration;
-   ARM/EV redesign;
-   Copter or Rover segmentation;
-   generic detector protocol with only one implementation;
-   pandas;
-   APT `FlightLog`;
-   companion `.params`;
-   APT YAML/configuration loading;
-   parser changes;
-   parameter-default plumbing;
-   per-flight parameter reconstruction in PR #1989 (deferred to the
    separate parameter-history/time-resolution architecture decision);
-   filtered `LogData` copies;
-   frontend changes;
-   analysis registration;
-   reporting/JSON/plotting;
-   qualitative landing evaluation;
-   new thresholds not already represented by validated APT behavior.

------------------------------------------------------------------------

# First-PR Tests

Prefer small in-memory `LogData` fixtures.

Required tests:

-   [x] `FlightSegment` accepts valid inclusive bounds.
-   [x] Reversed bounds are rejected.
-   [x] Parent/child boundary containment is inclusive.
-   [x] One clear Plane flight is detected.
-   [x] Flight start is backdated to the first sample of the qualifying
    two-second speed run.
-   [x] Flight end is the sample immediately before the qualifying
    30-second low-speed run.
-   [x] Long armed time before GPS movement does not alter the flight
    start.
-   [x] Remaining armed after landing does not alter the GPS-derived
    flight end.
-   [x] Two flights separated by sufficient low-speed time produce two
    segments.
-   [x] A short low-speed interval/go-around does not split a flight.
-   [x] Motion lasting less than two seconds does not create a flight.
-   [x] Candidate start persistence resets when speed drops to/below
    threshold.
-   [x] An open final flight returns `is_complete=False`.
-   [x] Missing GPS or required GPS fields produces segmentation
    unavailable.
-   [x] Missing `AIRSPEED_STALL` preserves the default 5 m/s threshold.
-   [x] `AIRSPEED_STALL=20` raises the effective threshold to 10 m/s.
-   [x] Speed exactly equal to threshold does not qualify as flight.
-   [x] Exactly 2 seconds qualifies for start.
-   [x] Exactly 30 seconds qualifies for end/separation.
-   [x] AMC `TimeUS` scaling is tested so returned bounds are seconds.

Two behavior questions should be kept explicit rather than silently
changed:

-   large GPS timestamp gaps currently count as elapsed persistence in
    APT;
-   non-finite GPS samples do not have a well-defined validated APT
    policy.

Do not change those semantics casually in the first PR.

------------------------------------------------------------------------

# Flight-Segment Implementation and Real-Log Validation

The first flight-segment implementation is complete and was merged
upstream in PR #1989.

Implemented files:

``` text
ardupilot_methodic_configurator/log_analysis/data_model_flight_segment.py
ardupilot_methodic_configurator/log_analysis/data_model_plane_flight_segment.py
tests/test_data_model_plane_flight_segment.py
```

The reusable contract contains `FlightSegment` and
`FlightSegmentationResult`. `PlaneFlightSegmentDetector` owns the
Plane-specific heuristic and consumes AMC-native scaled `LogData` plus
logged parameters.

## Real AMC BIN Smoke Test

`log_17.bin` was processed through AMC's normal production input path:
`extract_log()` → `LogData` → `analyze_log_data()` →
`LogAnalysisContext.parameters` → `PlaneFlightSegmentDetector`.

The log loaded as ArduPlane 4.7.0. AMC read `AIRSPEED_STALL=10.0 m/s`
from embedded PARM records, producing an effective threshold of 5.0 m/s.

``` text
1  start=656.723277 s   end=924.883724 s    duration=268.160447 s   complete=True
2  start=1095.783170 s  end=1680.743260 s   duration=584.960090 s   complete=True
3  start=1966.307340 s  end=2051.367266 s   duration=85.059926 s    complete=True
4  start=2573.683601 s  end=2863.678803 s   duration=289.995202 s   complete=False
```

AMC aggregate armed-duration metadata was 1338.905698 s. The final
segment demonstrates the purpose of `is_complete=False`: the GPS stream
ended without the normal 30-second separation evidence.

## APT / AMC Behavioural Parity

The same `log_17.bin` was independently processed through the existing
APT production path. Both systems detected exactly four operational
flights, with matching start/end boundaries and durations.

Maximum absolute numerical differences after unit normalization were:

``` text
start    4.547473508864641e-13 s
end      4.547473508864641e-13 s
duration 9.947598300641403e-14 s
```

These are floating-point representation only. Conclusion: **exact
behavioural parity**.

APT did not select `AIRSPEED_STALL` from its companion parameter file
and used the 5 m/s fallback. AMC independently obtained
`AIRSPEED_STALL=10.0` from the BIN, which also yields a 5 m/s effective
threshold.

------------------------------------------------------------------------

# Timestamped Parameter History --- RESOLVED / MERGED

The parameter-history architecture issue is now resolved upstream.

PR **#1995** (`feat(log-analysis): add timestamped parameter history`)
was merged by Amílcar into `ArduPilot/MethodicConfigurator`. During
review he explicitly confirmed that the feature aligned with his own
plans and that changing shared backend code was acceptable when
required. He then reworked the branch substantially before merge.

The final merged PR contained five commits, including:

``` text
fde99d9  feat(log-analysis): add timestamped parameter history
9cfbe4b  refactor(log-analysis): centralize and reuse binary log parsing
bfc6304  feat(bin-injection): correct progress_callback
ee19a9a  feat(config-sequence): add more quicktune parameters
4811705  feat(project-import): show progress while parsing binary logs
```

The important architectural conclusion is unchanged:

-   full timestamped `PARM` records belong to AMC-native shared log
    infrastructure;
-   Plane analysis must not implement AIRSPEED- or landing-specific PARM
    traversal;
-   time-scoped parameter lookup is a reusable capability, not Plane
    business logic;
-   the final upstream implementation is authoritative and must be used
    as merged rather than relying on the original local PR
    implementation.

The original temporal problem remains the reason this work was
necessary: final-value-only parameter dictionaries can incorrectly apply
a later parameter value to an earlier flight or landing attempt in the
same BIN. The merged timestamped history now provides the shared basis
for resolving parameter state at analysis time.

Before substantive landing implementation, the final merged API should
be used directly from current `master`; do not recreate the pre-review
helper API from memory.

------------------------------------------------------------------------

# Regression Harness Recovery and Four-Log Baseline --- COMPLETE

The established APT four-log regression workflow was recovered and run
successfully before further AMC migration work.

## Reference Baseline

``` text
APT commit: cf8d07d  Expand README landing analysis documentation

Logs/log_11.bin
Logs/log_17.bin
Logs/log_19.bin
Logs/log_26.bin
```

No replacement regression set or new harness is required.

## Recovered Regression Commands

With `~/ArduPilotTools/venv` active, from the APT repository root:

``` bash
PYTHONPATH=Scripts python Scripts/test_landing_regression.py
PYTHONPATH=Scripts python Scripts/test_event_timeline.py
```

`Scripts/test_landing_regression.py` result:

``` text
Landing analysis regression: PASS
```

This assertion-based harness covers all four logs, all established
termination paths (`abort`, `disarm`, `flight_window_end`, `gps`), a no-flare
case, known completed landing measurements, optional ARSP/RFND
unavailability, and incomplete CMD snapshot rejection.

Its corrected termination and completed-case references include:

``` text
log_17.bin  flight 4  DISARM   2848866277 us
log_19.bin  flight 1  GPS stop  743104000 us  flare→stop 6.70 s  target 19.1 m
log_26.bin  flight 4  GPS stop 2775037000 us  flare→stop 5.50 s  target 29.4 m
```

`Scripts/test_event_timeline.py` result:

``` text
Regression logs   : 4 / 4
Validated flights : 6
Validated cases   : 10
Skipped logs      : 0
STATUS             : PASS
```

The broader event/timeline harness preserves the established
landing-window and termination sequences, including multiple attempts,
aborts/restarts, flight-window termination, and GPS-stop completion.

Firmware represented by the run:

``` text
log_11.bin  ArduPlane V4.7.0-beta4
log_17.bin  ArduPlane V4.7.0-beta7
log_19.bin  ArduPlane V4.7.0-beta7
log_26.bin  ArduPlane V4.7.0-beta8
```

## Future Regression Gate

Before substantive Plane migration commits/PRs, normally run:

``` text
focused AMC tests
        +
full applicable AMC non-SITL suite
        +
APT landing regression
        +
APT event/timeline four-log regression
```

Any intentional behavior change must have its regression difference
reviewed and explained rather than silently replacing expected output.

## Definition of Done

-   [x] Exact four logs identified.
-   [x] Existing regression harnesses recovered.
-   [x] Harness behavior and production path understood for repeatable
    use.
-   [x] All four logs processed successfully.
-   [x] Existing deterministic assertions retained as the reference
    baseline.
-   [x] APT version/commit recorded (`cf8d07d`).
-   [x] Repeatable commands documented.
-   [x] Baseline reviewed before parameter-history implementation.

------------------------------------------------------------------------

# Plane Landing Analysis --- MERGED / COMPLETE

The final merged ParameterHistory API was audited and the AMC-native Plane
landing-analysis migration is complete. PR **#2024** was reviewed through
multiple mutation-backed hardening rounds, approved by Tridge and Amílcar,
squashed to one feature commit, and merged into `ArduPilot:master` on
2026-09-10.

Maintainer-confirmed firmware scope for the initial subsystem is
**ArduPlane 4.7.x only**. The Plane landing availability model owns that
gate. Amílcar also confirmed that **BARO is mandatory** for this
analysis.

Current availability contract:

-   GPS `TimeUS` / `Spd` mandatory;
-   LAND `TimeUS` / `stage` mandatory;
-   MODE `TimeUS` / `ModeNum` mandatory;
-   BARO `TimeUS` / `Alt` mandatory and finite/readable;
-   ARSP optional;
-   RFND optional;
-   CMD optional;
-   MSG optional;
-   at least one operational Plane `FlightSegment` under the current
    model.

The implementation continues to follow AMC's documented extension path
and returns flat objective `LogAnalysis` findings through the existing
registry and frontend/report path. No Plane-specific frontend,
hierarchical result model, qualitative scoring, or parameter
recommendation system has been introduced.

## Checkpointed Landing Slices

> **Historical parity note:** The slice-by-slice records below preserve the
> validation state at each implementation checkpoint. Several early slices
> therefore record 16/16 APT boundary parity and three GPS-stop target-distance
> cases. The final merged implementation intentionally differs on `log_17`
> flight 4: AMC now terminates that attempt by DISARM rather than allowing
> post-attempt GPS evidence to retroactively qualify GPS_STOP. Final merged
> boundary parity is 15/16, and the accepted current-state validation is recorded
> in the PR #2024 review-closure section above.

### Slice 1 --- Landing Attempt Detection

``` text
998ec2c0  feat(log-analysis): add Plane landing attempt analysis
```

Behavior preserved from APT:

-   normal stage 0 means no active LAND sequence is owned;
-   the first observed active stage `{1, 2, 3}` after normal/absence may
    open an attempt when FlightSegment and supported-mode gates hold;
-   LAND stage 1 is not guaranteed to appear in DataFlash because
    firmware can progress through multiple internal LAND states between
    log writes;
-   repeated active stages do not create duplicate attempts;
-   a later active-stage → stage-1 transition remains an explicit
    `STAGE_RESTART`;
-   mode exit terminates the active attempt, while mode re-entry does
    not fabricate a new attempt from a stale unchanged active LAND
    stage;
-   a scope beginning at stage 2 or 3 may produce a left-truncated
    attempt;
-   residual active stages do not fabricate repeated attempts;
-   attempts are children of an existing `FlightSegment`;
-   termination is the earliest of landing-aborted MSG,
    throttle-disarmed MSG, transition away from AUTO, sustained GPS
    stop, or parent segment boundary;
-   multiple attempts, abort/restart behavior, and go-arounds are
    preserved;
-   no touchdown inference is made;
-   GPS stop is landing/rollout completion evidence, not touchdown.

Direct four-log APT/AMC comparison found **16/16 landing-attempt
boundaries and termination reasons match** across 10 operational
flights:

``` text
log_11.bin  2 / 2
log_17.bin  6 / 6
log_19.bin  1 / 1
log_26.bin  7 / 7
TOTAL      16 / 16
```

### Slice 2 --- Preflare / Flare Stage Evidence

``` text
095c2ffa  feat(log-analysis): add Plane landing stage evidence
```

APT's validated **preflare event is `LAND.stage == 2`**. A focused APT
audit confirmed there is no distinct firmware preflare MSG concept to
migrate.

The first stage-2 and stage-3 transitions inside each attempt now
produce objective evidence including:

-   event timing;
-   LAND `fh` flight height;
-   nearest finite attempt-scoped ARSP `Airspeed` when available;
-   nearest finite attempt-scoped BARO `Alt`;
-   nearest finite attempt-scoped RFND `Dist` when available;
-   event-time parameters via `ParameterHistory.value_at(...)`:
    -   preflare: `LAND_PF_ALT`, `LAND_PF_SEC`;
    -   flare: `LAND_FLARE_ALT`, `LAND_FLARE_SEC`, `LAND_PITCH_DEG`.

The firmware `Flare ...` message is deliberately kept distinct from the
`LAND.stage == 3` controller transition.

For observational ARSP evidence, AMC selects the primary (`I == Pri`)
healthy sensor and requires a finite Airspeed value. `ARSP.U` is not
required because it expresses flight-control use, not measurement
validity. Firmware `Flare ... speed=` evidence is groundspeed, not
airspeed.

### BARO Availability Correction

``` text
dd2e50eb  fix(log-analysis): require BARO for Plane landing analysis
```

Following maintainer direction, BARO is mandatory at subsystem
availability level. The availability model requires non-empty BARO
records with finite, readable `TimeUS` and `Alt`. ARSP and RFND remain
optional.

### Slice 3 --- Quantitative Stage Evidence

``` text
0b1f6ce4  feat(log-analysis): add Plane landing quantitative evidence
```

Added APT-derived quantitative evidence:

-   nearest finite attempt-scoped GPS `Spd` at preflare;
-   nearest finite attempt-scoped GPS `Spd` at flare;
-   BARO-derived preflare sink rate using APT's centered ±0.5 s window,
    clipped to attempt boundaries, first-to-last finite BARO altitude
    samples, with positive values meaning descent;
-   flare-to-GPS-stop duration only for attempts that actually terminate
    via `GPS_STOP`.

Real-log comparison found exact agreement for all 14 comparable preflare
GPS and BARO sink-rate measurements, and all 14 flare cases selected the
same GPS sample as APT. The 16/16 attempt-boundary regression remained
unchanged.

### Slice 4 --- Firmware Landing Evidence

``` text
e975c054  feat(log-analysis): add Plane landing firmware evidence
```

AMC now parses the exact APT-supported firmware message forms:

``` text
Flare <altitude>m sink=<sink-rate> speed=<groundspeed> dist=<distance>
Landing glide slope <angle> degrees
```

All numeric fields must be finite; malformed or partial messages are
omitted. MSG remains optional at subsystem availability level.

Objective evidence added:

-   separate firmware flare timestamp;
-   firmware flare altitude;
-   firmware flare sink rate;
-   firmware flare groundspeed;
-   firmware flare distance to target;
-   firmware landing glide-slope timestamp and angle.

The four-log comparison found:

-   **14/14 firmware flare events match APT** for timestamp, altitude,
    sink rate, groundspeed, distance, and attempt association;
-   **16/16 glide-slope measurements match APT**;
-   the two attempts without APT flare evidence also omit it in AMC;
-   **16/16 attempt boundaries and termination reasons remain
    unchanged**.

A separate APT audit confirmed that there is **no firmware preflare
MSG**. `LAND.stage == 2` is the validated APT preflare event.

`Landing approach start at ...m` remains deliberately deferred because
all validated occurrences are approximately 0.1 s before the frozen
attempt boundary. The parent attempt/segment scope has not been widened
to capture it.

### Slice 5 --- Conservative Mission LAND Target Evidence

``` text
0881c5a8  feat(log-analysis): add Plane mission target evidence
```

CMD remains optional. AMC reproduces APT's conservative mission snapshot
rules:

-   required CMD fields: `TimeUS`, `CTot`, `CNum`, `CId`, `Lat`, `Lng`;
-   `CTot` positive and `0 <= CNum < CTot`;
-   `CNum == 0` starts/restarts a snapshot;
-   subsequent records must keep the same `CTot` and consecutive `CNum`;
-   only exactly complete `0..CTot-1` snapshots are candidates;
-   invalid/out-of-sequence rows discard only the current incomplete
    snapshot;
-   previously completed snapshots remain candidates if a later upload
    is incomplete;
-   for an attempt, choose the latest complete snapshot whose final
    record is at or before attempt start;
-   require exactly one `CId == 21` (`MAV_CMD_NAV_LAND`);
-   reject zero/zero LAND coordinates and non-finite coordinates.

For `GPS_STOP` attempts with valid mission target evidence, AMC
independently computes distance from the GPS-stop position to the
selected mission LAND coordinate using APT's haversine semantics and
Earth radius 6,371,000 m. Firmware `Flare ... dist=` remains a separate
measurement and is not reused as computed mission geometry.

Four-log comparison:

-   **16/16 mission LAND-target decisions match APT**;
-   **3/3 computed landing-end target distances match APT**:
    -   log_17 flight 4: 22.535686 m;
    -   log_19 flight 1: 19.051158 m;
    -   log_26 flight 4: 29.439547 m;
-   **16/16 attempt boundaries and termination reasons remain
    unchanged**.

## Slice 6 --- Rangefinder Lifecycle Evidence

``` text
66520182  feat(log-analysis): add Plane rangefinder evidence
```

This closed the final genuine objective-evidence gap identified by the
APT landing completeness audit. AMC now reproduces the validated APT
RFND lifecycle semantics inside each landing attempt, including first
nonzero acquisition, first in-range acquisition using event-time
`RNGFND1_MAX`, continuous-acquisition qualification, disengagement
count, and last disengagement evidence. RFND remains optional.

Across all 16 validated landing attempts, all nine comparable RFND
lifecycle fields matched APT exactly after unit normalization. Attempt
boundaries and termination reasons remained 16/16 unchanged.

### RFND Selection and Status Semantics

Landing RFND selection uses event-time `RNGFND_LND_ORNT`. The Plane 4.7
default is orientation 25, but it is not a universal hard-coded
selection. Where `Orient` is logged, AMC selects the matching configured
orientation and handles multiple matching sensors conservatively
according to the validated firmware-compatible selection behavior. RFND
instance 0 is not assumed to be the landing sensor. If `Orient` is
absent, the validated instance-0/ single-stream compatibility path is
retained.

The selected instance remains associated with its distance and status
evidence; event-time MAX mapping is:

``` text
instance 0 -> RNGFND1_MAX
instance 1 -> RNGFND2_MAX
...
instance 8 -> RNGFND9_MAX
instance 9 -> RNGFNDA_MAX
```

RFND status semantics are preserved explicitly:

``` text
0 NotConnected
1 NoData
2 OutOfRangeLow
3 OutOfRangeHigh
4 Good
```

Stat 0/1 retain status but suppress retained/stale `Dist` as a current
measurement. Stat 2/3 preserve a finite current distance plus explicit
status, but are not usable as Plane landing-height evidence. Stat 4 is a
current distance observation usable for landing-height evidence. Missing
`Stat` preserves the validated legacy distance-only behavior. Raw
observation, firmware usability, and derived in-range lifecycle
semantics remain distinct.

The final presentation correction restored nine Stat-3 finite
observations (9.240, 8.455, 9.280, 8.155, 9.635, 9.720, 6.820, 6.055,
and 7.460 m) and nine Stat-2 observations as explicitly labelled 0.000 m
readings. Stat 0/1 stale distances remain suppressed. These are
objective observations, not landing-quality judgments.

## PR #2024 Review Hardening and Merge Closure

The review cycle substantially expanded the synthetic edge-case coverage around
the original four-log validation set. The final reviewed implementation had
**208 focused Plane landing tests**, up from the initial migration slices, and
Tridge's final review explicitly concluded **APPROVE — no blockers**.

The individual review commits were intentionally squashed before merge. Their
historical value is in the evidence rules and regression tests, not in
preserving each intermediate commit upstream.

### Durable evidence rules established by review

1. **Causal ownership first.** Later evidence must not retroactively change or
   qualify an attempt after that attempt has terminated.
2. **Scope before selection.** Candidate telemetry must be restricted to the
   owning flight/attempt before nearest-sample selection. An out-of-scope row
   must not suppress valid in-scope evidence.
3. **Validity after selection.** Once the nearest/relevant in-scope observation
   is selected, decide whether that observation is finite, healthy, usable, or
   ambiguous. Do not search farther away merely to find a plausible value.
4. **State and observation are distinct.** Causally earlier configuration/state
   may seed interpretation (for example RFND orientation) without becoming an
   observation owned by the current attempt.
5. **Observation and firmware usability are distinct.** A current RFND status
   or distance can be valid observational evidence even when firmware would not
   use it as landing-height input.
6. **Flight-control use is not measurement validity.** `ARSP.U` is not a gate
   for observational airspeed; primary/health/finiteness are the relevant
   evidence rules.
7. **One timestamp is one instant.** Duplicate RFND timestamps may be tolerated
   for cadence estimation, but equal-time rows must not count as distinct
   elapsed continuity samples.
8. **Unavailable means unavailable.** Missing, ambiguous, unhealthy, or
   non-finite event-local evidence is not replaced by a distant plausible
   observation.
9. **DataFlash is an observation, not a complete firmware execution trace.** A
   firmware state such as LAND stage 1 can legitimately be absent between log
   writes.
10. **Mutation tests are useful review evidence.** The final hardening rounds
    repeatedly reverted individual guards/ordering rules to prove the focused
    tests actually fail for the defect they are intended to prevent.

### Final validation record

``` text
Plane landing tests:          208 passed
Affected AMC tests:           305 passed
Reference logs:               4
Operational flights:          10
Landing attempts:             16
Historical APT parity:        15 / 16 boundaries
APT landing regression:       PASS
APT Event Timeline:           PASS (4/4 logs, 6 flights, 10 cases, 0 skipped)
Ruff:                         PASS
Ruff format:                  PASS
Scoped mypy:                  PASS
Pylint:                       10.00/10
Python compilation:           PASS
git diff --check:             PASS
```

The two unchanged reference GPS-stop boundaries remained:

``` text
log_19 flight 1:  743104011 us
log_26 flight 4: 2775037136 us
```

APT subsequently incorporated the same reviewed causality rule. Its current
`log_17` flight 4 boundary is DISARM at `2848866277 us`; the current APT/AMC
comparison therefore matches 16/16 attempt boundaries.

All 16 reference attempts retained dense RFND acquisition evidence (49 or 50
samples), and stage-local ARSP/BARO/GPS evidence in the reference logs remained
unchanged by the locality/validity corrections.

### Non-blocking review notes retained for future research

The merged implementation intentionally leaves several review notes as deferred
rather than inventing unsupported policy:

- GPS-stop persistence can bridge a large telemetry gap under the inherited
  sampled-state model; no defensible mandatory gap threshold has yet been
  established.
- A firmware flare before the first LAND row in a severely left-truncated log
  remains unassociated when no defensible bracketing evidence exists.
- An unusable RFND frame followed by NoData can leave the exact disengagement
  transition uncertain; the current result does not fabricate a precise event.
- Final review noted a non-blocking mutation-coverage gap around duplicate RFND
  rows occurring before continuity has qualified. Current shipped behavior was
  not identified as wrong, but additional mutation-pinning could be added if
  this area is revisited.

These are not incomplete migration slices. They are explicit future evidence
questions.

## APT Landing Migration Completeness --- COMPLETE

A read-only completeness audit accounted for all 30 fields/behaviours in
APT's validated `LandingAttemptAnalysis` surface. The only genuine
migration gap found was RFND lifecycle evidence, now implemented in
Slice 6.

Therefore no further existing APT landing-analysis feature slice is
currently required. Remaining items below are deliberate new
research/deferred capabilities, not incomplete migration.

# Explicit Deferred / Not Yet Implemented Scope

The following items are deliberately **deferred**. They are not
accidental omissions from the current Plane landing implementation and
should not be added without a specific validation or architecture
reason.

## GPS-STOP TERMINATION: DEFERRED --- NO CHANGE

The sustained GPS groundspeed `< 3 m/s` rule can theoretically terminate
an attempt while the aircraft remains airborne in a sufficiently strong
headwind. The three established real-log GPS-ended attempts had already
reached FINAL, had firmware flare evidence before GPS-stop, and remain
required by the validated APT regression. A FINAL gate would address a
pre-FINAL synthetic case but would not prove touchdown or ground
contact. Current GPS-stop behavior is therefore preserved pending a
better corroborated ground/landing termination design. GPS stop is
landing/rollout completion evidence, never a touchdown detector.

-   **Post-attempt / rollout evidence and widening of `FlightSegment`.**
    Current attempt and completed-flight boundaries remain frozen to
    validated APT behavior. Do not widen them merely to capture later
    evidence.
-   **Firmware `Distance from LAND point=...m` parsing.** A targeted APT
    audit found that APT does not parse or consume this message. All 9
    occurrences in the four reference logs are after the AMC attempt
    boundary; 6/9 are also outside completed `FlightSegment`s. It is
    therefore not an APT-parity gap.
-   **`Landing approach start at ...m` firmware evidence.** Validated
    occurrences are approximately 0.1 s before the frozen
    landing-attempt boundary. Capturing them would require a deliberate
    scope decision rather than silently reaching outside the attempt.
-   **Touchdown detection or touchdown evidence.** GPS stop remains
    landing / rollout completion evidence, not a touchdown detector.
-   **BARO flare sink-rate calculation.** APT has no equivalent
    calculated flare sink metric; the firmware `Flare ... sink=` value
    remains separate evidence.
-   **Non-GPS-ended mission-target distance.** APT only produces the
    independently computed landing-end target distance for GPS-stop
    cases.
-   **Standalone mission LAND-coordinate outcomes.** Mission coordinates
    are used internally for the validated computed target-distance
    evidence; they are not currently emitted as separate findings.
-   **Runway projection, along-track/cross-track geometry, or other new
    landing geometry.** These are not part of the validated APT
    migration baseline.
-   **Wind component on final approach.** A future landing-analysis
    phase may report the headwind/tailwind component along the
    final-approach track (and potentially crosswind separately), but
    this is not part of the validated APT migration baseline. Before
    implementation, define the authoritative wind source, final-track
    reference, sign convention, sensor/estimator availability, and
    behavior when airspeed or wind estimates are absent or unreliable.
    Do not infer a precise wind component from groundspeed alone.
-   **RC / telemetry range-check evaluation.** This is a potentially
    useful future log-analysis capability, but it is deliberately
    deferred because its scope is broader than Plane landing analysis
    and protocol/log-source assumptions matter. Before implementation,
    discuss the concept with the maintainer and determine whether it
    belongs as a reusable radio-link analysis subsystem. A useful design
    would need to define which logged evidence is authoritative (for
    example link quality/RSSI-style metrics, packet rate,
    telemetry/failsafe events and, where available, transmitter-power
    context), what constitutes a controlled range check, and how to
    avoid presenting environment-, antenna-, protocol-, or
    transmitter-specific observations as universal range predictions.
    Data that exists only on the transmitter/EdgeTX side must not be
    assumed to exist in the DataFlash log.
-   **Qualitative landing scoring or classification**, including
    good/poor, safe/unsafe, normal/abnormal labels.
-   **Parameter recommendations or automatic tuning advice.** These
    require a later evidence/validation phase using a broader body of
    logs and maintainer experience.
-   **Conventional Plane landing configuration-step metadata/frontend
    guidance.** AMC's generic analysis-to-configuration path already
    exists; Plane landing metadata should be reviewed separately after
    objective analysis is mature.
-   **Hierarchical per-flight/per-attempt result structures.** Continue
    using AMC's flat `LogAnalysisResult` unless implementation
    demonstrates a concrete need for hierarchy.
-   **Firmware support beyond ArduPlane 4.7.x.** Initial support remains
    the maintainer-confirmed 4.7.x boundary until later firmware is
    separately validated.
-   **Shared extraction/backend/context/result/frontend changes without
    a demonstrated missing architectural capability.** If a future
    feature cannot be implemented correctly through
    `ARCHITECTURE_log_analysis.md` extension points, stop and review the
    missing reusable hook before changing shared infrastructure.

This deferred list should be reviewed during the APT migration
completeness review. An item should move out of deferred scope only when
validated behavior, new log evidence, or maintainer direction provides a
concrete reason to do so.

------------------------------------------------------------------------

## Known Scope / Measurement Notes

### Completed-flight rollout scope

A completed `FlightSegment` ends immediately before the qualifying
30-second low-speed separation run. Consequently, terminal GPS-stop
evidence from that same run lies outside the completed segment. The
four-log APT/AMC comparison confirms this is inherited APT behavior
rather than an AMC regression: completed-flight terminal attempts end at
the flight/window boundary in both implementations, while GPS-stop
termination remains available where the evidence lies inside the parent
scope.

Do **not** widen `FlightSegment` merely to capture rollout evidence.
Revisit this only when a future metric demonstrably requires
post-segment evidence. This limitation does not block approach,
preflare, or flare analysis.

### Post-landing firmware distance message

ArduPlane 4.7.x logs may contain firmware messages such as:

``` text
Distance from LAND point=31.89m
```

APT does **not** parse or use this message for landing analysis. A
read-only audit of the four reference logs found nine occurrences:

``` text
log_11.bin  0
log_17.bin  4
log_19.bin  1
log_26.bin  4
```

All nine occur after the AMC landing-attempt boundary. Six of nine are
also outside completed `FlightSegment`s; the remaining three occur
inside incomplete final segments but still after the attempt boundary.

This message is therefore deliberately not migrated as an APT-parity
requirement. If adopted independently later, it would represent a
distinct post-landing firmware measurement and must not be conflated
with either:

-   firmware flare `dist=` evidence; or
-   independently computed CMD-LAND-target / GPS-stop distance.

### Nearest telemetry rule

ARSP, BARO, RFND, and GPS event measurements use the APT-derived rule of
selecting the nearest finite sample contained within the landing attempt
unless a specific APT metric defines a different algorithm.

This is suitable for objective evidence capture. If later analysis gives
these measurements stronger interpretation, review whether
sample-to-event time separation should also be exposed or bounded.

### LAND-stage versus firmware flare time

The LAND-controller flare transition (`LAND.stage == 3`) and firmware
`Flare ...` MSG are distinct evidence. On the validated logs the
firmware flare MSG precedes the LAND stage-3 transition by approximately
58--196 microseconds. This difference did not alter nearest GPS sample
selection, but the two event definitions should remain explicitly
separate.

If future implementation demonstrates that the documented AMC extension
path lacks a required shared capability, stop and report that missing
hook before changing extraction, backend orchestration, shared context,
result models, or frontend infrastructure.

------------------------------------------------------------------------

# ArduPlane Frontend / Configuration Audit --- COMPLETE

Current AMC master now contains a frontend-visible ArduPlane 4.7.x
template and a substantial configuration-step skeleton. Static audit of
commits `0fb3e29b` and `277beddb` classifies current support as:

**B. Frontend workflow exists with some usable Plane configuration.**

The template `vehicle_templates/ArduPlane/empty_4.7.x` is discoverable
by AMC's normal template-selection and project-creation path. It
contains:

-   a real ArduPlane 4.7.1-beta `00_default.param` snapshot;
-   64 numbered configuration `.param` files;
-   Plane component metadata;
-   a step-specific MagFit parameter-definition file.

The frontend therefore exposes a complete-looking Plane configuration
sequence. However, a significant portion of the later workflow is
inherited from Copter/QuadPlane and is not yet a coherent conventional
fixed-wing configuration procedure. Examples include multicopter
`ATC_*`/`MOT_*` workflow, VTOL QuickTune, multicopter
AutoTune/system-identification steps, and Copter-style
precision-landing/position-control pages.

## Plane landing configuration already present

The most relevant current Plane page is:

``` text
59_range_finder.param
```

It already contains genuine fixed-wing landing/rangefinder parameters,
including:

``` text
LAND_ABORT_THR
LAND_FLARE_ALT
LAND_FLARE_SEC
RNGFND_LANDING
RTL_AUTOLAND
```

`00_default.param` also contains the wider ArduPlane landing defaults,
including `LAND_PF_ALT`, `LAND_PF_SEC`, `LAND_FLARE_ALT`,
`LAND_FLARE_SEC`, `LAND_PITCH_DEG`, and `TECS_LAND_*`.

However, step 59 currently has no matching entry in
`configuration_steps_ArduPlane.json`. It therefore appears in the
frontend as a raw parameter page but lacks AMC's normal
configuration-step metadata, guidance, forced/derived rules, component
integration, log-message associations, and automatic parameter-to-step
mapping.

## Existing analysis-to-configuration bridge

AMC already has the generic architecture needed for future log-analysis
findings to connect to configuration:

``` text
Plane landing analysis
        │
        ▼
LogAnalysisResult / LogAnalysis findings
  param_name
  suggested_value
  related_step
        │
        ▼
existing AMC log-analysis frontend
        │
        ├── display finding
        ├── existing Fix/review path
        └── navigate to related configuration step
```

`BaseLogModel.step_for_parameter()` and
`find_configuration_step_for_parameter()` already provide
parameter-to-step lookup through configuration-step metadata.

Therefore the current limitation is **not** a missing log-analysis
architecture capability. The Plane configuration metadata simply does
not yet associate the principal fixed-wing landing parameters with a
documented step. In particular, there is currently no metadata rule for:

``` text
LAND_PF_ALT
LAND_PF_SEC
LAND_FLARE_ALT
LAND_FLARE_SEC
LAND_PITCH_DEG
```

This should not be repaired as part of the first landing-analysis PR.
The configuration workflow is a separate Plane-maturity concern. Once
objective landing analysis is established, the missing
conventional-Plane landing step/metadata can be discussed with Amílcar
using concrete analysis results and parameters.

Architectural implication:

-   landing analysis should produce AMC-native evidence/results first;
-   do not make log analysis directly manipulate template files;
-   do not create a Plane-specific recommendation framework;
-   later configuration guidance should use AMC's existing
    `param_name`/`suggested_value`/`related_step` path if and when such
    guidance is validated.

------------------------------------------------------------------------

# Landing Integration --- MERGED / COMPLETE

Plane landing integration was completed after the
parameter-history/time-resolution architecture issue was resolved
sufficiently for time-scoped analysis. PR #2024 is now merged upstream after
maintainer approval and squash.

Implemented flow:

``` text
LogData
    ↓
PlaneFlightSegmentDetector
    ↓
FlightSegment
    ↓
Plane landing detector
    ↓
one or more landing attempts
    ↓
objective landing evidence
    ↓
flat LogAnalysisResult
    ↓
existing AMC frontend
```

The landing window is a child of the parent flight segment.

The landing detector uses AMC-native access to:

-   `LAND`;
-   `MODE`;
-   `MSG`;
-   `GPS`;
-   optional `ARSP`;
-   mandatory `BARO`;
-   optional `RFND`;
-   optional `CMD`.

The landing result remains evidence-first.

The Plane landing availability and analysis models use AMC's existing
analysis registry and existing result/report/frontend path. No separate
Plane entry point or frontend pipeline has been introduced.

Do not classify landings as good, poor, safe, unsafe, normal, or
abnormal.

------------------------------------------------------------------------

# Landing Behavior to Preserve

Future changes to Plane landing analysis should retain the validated
baseline concepts:

-   AUTO + landing-stage evidence identifies landing attempts;
-   multiple landing attempts may exist in one flight;
-   aborted/restarted attempts remain represented;
-   go-arounds do not split the parent flight;
-   termination evidence is independent;
-   GPS stop means landing/rollout completion, not touchdown;
-   ARSP, RFND, CMD, and MSG remain optional; BARO is mandatory by
    maintainer direction;
-   missing or ambiguous evidence remains unavailable rather than
    guessed;
-   mission LAND target handling remains conservative;
-   no qualitative scoring without a validated later model.

------------------------------------------------------------------------

# Validation Strategy

During migration:

1.  use small AMC-native unit fixtures for detector semantics;
2.  preserve APT regression outputs as behavioral reference;
3.  compare AMC results against the same source logs where practical;
4.  add only a small number of BIN fixtures to AMC if repository policy
    and maintainer guidance support it;
5.  treat community logs as validation data, not threshold-tuning
    material.

The APT landing regression remains the frozen behavioural reference for
the migrated baseline. AMC has now demonstrated equivalent validated
behaviour for the defined migration scope; the APT harness remains
useful as an independent regression reference.

------------------------------------------------------------------------

# Post-Migration Development Model

After the existing mature APT functionality has been considered for AMC,
APT is no longer to be treated as a legacy implementation that AMC
should automatically reproduce.

**APT becomes the experimental/R&D environment for new flight-log
analysis concepts.**

Normal path for a substantial new idea:

``` text
idea
  ↓
separate research project
  ↓
APT prototype / experiment
  ↓
real-log validation and defined evidence semantics
  ↓
maintainer discussion where AMC direction is relevant
  ↓
AMC-native implementation only if accepted
```

New APT functionality does **not** imply an AMC migration requirement.
AMC implementation should begin only after the feature's meaning,
required evidence, limitations, and expected behaviour are sufficiently
established.

Future Codex work must distinguish between:

-   **APT research/prototyping:** experimentation is expected, but
    evidence, assumptions, units, test windows, and regression behaviour
    must remain explicit;
-   **AMC implementation:** follow `ARCHITECTURE_log_analysis.md`,
    current AMC extension points, maintainer direction, narrow scope,
    and the established review/test workflow.

Do not modify AMC merely to accommodate an unvalidated APT experiment.
Ideas discovered while implementing an AMC PR should normally be
recorded as research/deferred items rather than implemented in that PR
unless required for correctness.

This policy is intended to be copied into future Codex prompts when
switching between APT research and AMC production work.

------------------------------------------------------------------------

# Contribution Rules

AMC contribution requirements include:

-   Conventional Commit messages;
-   DCO signoff using `git commit --signoff`;
-   AMC type annotations and coding standards;
-   Ruff/Pylint/MyPy/Pyright/CI compliance;
-   automated tests;
-   backend → data_model → frontend separation;
-   no unnecessary dependencies;
-   new user-facing strings internationalized if/when frontend work is
    added.

Plane log-analysis work must adhere to `ARCHITECTURE_log_analysis.md`,
particularly the documented "Extending the Log Analysis System" path.

Unless a demonstrated architectural limitation requires otherwise:

-   new Plane functionality should use AMC's existing availability and
    analysis model architecture;
-   analysis should consume shared `LogData` and `LogAnalysisContext`;
-   required data already present in `LogData` must not cause extraction
    changes;
-   backend orchestration must remain unaware of Plane implementation
    details;
-   mature Plane models should use the existing registry;
-   results should use existing `LogAvailabilityResult`,
    `LogAnalysisResult`, and `LogSummary` structures;
-   the existing frontend/report path should be used.

If implementation exposes a missing shared capability, stop and review
the architectural requirement before modifying shared backend,
extraction, context, result, or frontend infrastructure. Any such change
should be reusable AMC-native infrastructure rather than a
Plane-specific workaround.

This rule should also be carried into Codex implementation prompts.

For future researched features, also follow Amílcar's
maintainer-confirmed two-commit workflow: one functionality commit
followed by one BDD-test commit. Use his supplied expert-role prompts
verbatim for the corresponding functionality/test audits; see
**Maintainer-Confirmed Implementation and Final-Audit Workflow** below.

Current Plane work should remain data-model only unless review requires
otherwise.

------------------------------------------------------------------------

# Maintainer-Confirmed Implementation and Final-Audit Workflow

Amílcar provided the following two prompts verbatim as the
review/testing workflow he uses:

``` text
As a python and ArduPlane expert review the last git commit. Take special notice of architecture meningfullness and testsability.
```

Then:

``` text
As a Python expert use the pytest-testing-instructions skill and write BDD tests for the functionality added in the last git commit
```

He also explicitly directed:

``` text
Keep it in two commits one for the functionality and a second one for the tests
```

These instructions should be preserved verbatim in this plan rather than
silently rewritten into equivalent wording. In particular, the role
framing ("As a python and ArduPlane expert" / "As a Python expert") is
part of the maintainer-provided audit method and should be used for the
corresponding Codex reviews.

## Default AMC Feature-Promotion Pattern

For future researched Plane analysis features, use this workflow unless
Amílcar gives different direction for a specific change:

``` text
separate research project
        ↓
APT experimental/reference implementation
        ├── prototype in the smaller CLI environment
        ├── validate against real BIN logs
        └── freeze the behavioural contract
        ↓
AMC-native implementation
        ├── follow ARCHITECTURE_log_analysis.md
        ├── use existing AMC extension points
        └── COMMIT 1: functionality
        ↓
maintainer-style functionality audit
        └── use Amílcar's first prompt verbatim
        ↓
AMC BDD tests
        ├── use pytest-testing-instructions skill
        └── COMMIT 2: tests
        ↓
maintainer-style BDD/test audit
        └── use Amílcar's second prompt verbatim
        ↓
APT ↔ AMC real-log validation
        ↓
full AMC validation / final branch audit
        ↓
PR
```

APT is the experimental/reference implementation and regression harness
for Plane log-analysis research. AMC remains the production integration
target. Mature APT behaviour should normally be reimplemented using
AMC-native infrastructure rather than mechanically merging or
cherry-picking APT architecture into AMC.

## Commit Discipline

The normal unit of a researched AMC feature should be two commits:

1.  **Functionality commit** --- the smallest AMC-native implementation
    of the already-researched behaviour.
2.  **BDD tests commit** --- tests for that functionality, written after
    the functionality review using the repository's
    `pytest-testing-instructions` skill.

"Functionality first, tests second" does not mean testability is
deferred. Amílcar's first review prompt explicitly requires attention to
testability. The functionality commit should therefore be designed so
the following BDD test commit can exercise it cleanly without
architectural rework.

Small review corrections, CI-only fixes, DCO/history maintenance, or
maintainer-requested follow-ups do not need to be artificially forced
into a new functionality/tests pair when they are not a new researched
feature.

## Final Audits Before PR

For future feature promotions, the two maintainer prompts above should
also be explicit final audit gates rather than relying only on a broad
generic Codex review.

Recommended final sequence:

1.  Confirm APT/reference regression and real-log evidence are still
    valid.
2.  Run the first maintainer prompt verbatim against the functionality
    commit.
3.  Resolve concrete architecture/testability findings without
    broadening scope.
4.  Add the BDD test commit using the second maintainer prompt verbatim.
5.  Review the resulting tests for behavioural coverage and absence of
    speculative assertions.
6.  Run focused AMC tests and APT ↔ AMC real-log parity checks.
7.  Run the full applicable AMC non-SITL suite and repository static/CI
    checks.
8.  Perform a final branch-level architecture/scope/hygiene review only
    if it adds information not already covered by the two
    maintainer-directed audits.
9.  Open the PR without adding unrelated fixes discovered elsewhere in
    AMC.

This is intended to become a reusable template for promoting validated
research/APT prototypes into AMC while preserving AMC architecture and
independently established behavioural evidence.

------------------------------------------------------------------------

# Current Work Sequence

``` text
APT standalone landing analysis                  COMPLETE
        │
        ▼
APT → AMC architecture audit                     COMPLETE
        │
        ▼
Plane flight segmentation / PR #1989             MERGED
        │
        ▼
Timestamped ParameterHistory / PR #1995          MERGED
        │
        ▼
Plane landing analysis / PR #2024                MERGED
        ├── 208 focused Plane landing tests
        ├── mutation-backed review hardening
        ├── 16/16 current APT boundary parity
        ├── log_17 causality correction incorporated into APT
        ├── Tridge APPROVE — no blockers
        └── Amílcar squashed and merged
        │
        ▼
Local/fork synchronization                       COMPLETE
        │
        ▼
ArduPlane configuration-method audit             COMPLETE
        ├── configuration_steps_ArduPlane.json
        ├── all associated Plane *.param files
        ├── step ownership/dependency inventory
        ├── Copter/QuadPlane inheritance identified
        └── P0/P1/P2/P3 findings frozen in audit doc
        │
        ▼
PR 1 — Step 66 Everyday use / RTL                NEXT
        ├── validate Plane 4.7.x parameter semantics
        ├── correct stale RTL ownership/content
        ├── validate existing battery-failsafe content
        ├── update Plane-specific step metadata
        └── add focused configuration-content tests
        │
        ▼
Further Plane method PRs                         LATER
        ├── sequence/template conformance
        ├── fixed-wing frame/output foundation
        ├── propulsion/failsafes
        ├── airspeed/flight envelope
        ├── takeoff/landing/tuning/TECS/navigation
        └── QuadPlane applicability boundaries
        │
        ▼
Map log-analysis findings to configuration steps LATER
        ├── identify earliest relevant canonical owner
        ├── preserve evidence-first semantics
        └── let AMC's method own the corrective workflow
        │
        ▼
APT continues as Plane log-analysis R&D environment
```

## Immediate AMC Configuration-Method Sequence

The broad read-only configuration-method audit is complete. Do not repeat it
for each PR.

The immediate task is **PR 1 — Step 66 Everyday use / RTL correctness**:

1. Validate the exact ArduPlane 4.7.x firmware/source semantics for
   `RTL_ALTITUDE`, `RTL_CLIMB_MIN`, and the battery-failsafe parameters already
   present in Step 66.
2. Determine the smallest technically correct change to
   `66_everyday_use.param` in both Plane templates.
3. Update only the Step 66 Plane metadata needed to make its purpose and timing
   technically accurate.
4. Add focused tests for parameter existence and safety-relevant units/semantics
   using Plane metadata as the oracle.
5. Run the applicable AMC configuration/template tests and static checks.
6. Review the diff strictly against the bounded PR scope.
7. Obtain maintainer review before moving to the next method domain.

Do **not** use this PR to fix unrelated findings from the audit. Preserve those
as separately reviewable follow-up work.

The provisional follow-up order from the audit is:

``` text
PR 1  Everyday use / RTL correctness
  ↓
PR 2  Sequence / template conformance
  ↓
PR 3  Fixed-wing frame + output/control-surface foundation
  ↓
PR 4  Power / propulsion / failsafes
  ↓
PR 5  Airspeed + flight envelope
  ↓
later: takeoff / landing / attitude tuning / TECS / navigation / QuadPlane
```

Direct parameter-value recommendations from landing analysis remain out of
scope. First make the configuration method authoritative enough that analysis
can safely identify the relevant configuration step.

## Secondary APT R&D Sequence

APT ParameterHistory is complete and remains shared APT research infrastructure.
The bounded Battery Analysis extension is also complete in commit `4e83b46`.
These tasks are secondary while the maintainer-requested AMC Plane sequence work
is active:

1.  **Rangefinder acquisition / `LAND.fh` anomaly --- RESEARCH CANDIDATE.**
    Reproduce and trace the reported transient before inferring cause.
2.  **Persistent Pack History --- DEFERRED RESEARCH.** Accumulate repeated
    sessions for identified physical packs before choosing a persistence model.
3.  Present mature APT research such as Battery Analysis and Event Timeline when
    useful, but migrate only functionality that is accepted and fits AMC-native
    architecture.

# Historical Flight-Segment Definition of Done --- COMPLETE

PR #1989 is merged. The checklist below is retained as the historical
acceptance record for that infrastructure work:

-   [x] reusable segment ownership is clearly separated from Plane
    heuristics;
-   [x] no APT parser or data ownership has migrated;
-   [x] no APT YAML/configuration subsystem has migrated;
-   [x] all time values are correctly expressed in AMC seconds;
-   [x] Plane detector behavior is covered by focused tests;
-   [x] incomplete final flights are explicit;
-   [x] no frontend or analysis-registry changes are included;
-   [x] the full non-SITL pytest suite remains green;
-   [x] static checks applicable to the changed files pass;
-   [x] the diff contains only work necessary for the flight-segment
    feature;
-   [x] commits follow Conventional Commits and are DCO signed off;
-   [x] PR description states which thresholds are inherited APT
    heuristics and which infrastructure is reusable AMC behavior.

------------------------------------------------------------------------

# Phase 1 Closure

-   [x] PR #1989 merged upstream.
-   [x] Maintainer GPS `U == 1` fix incorporated.
-   [x] Local `master` synchronized with upstream.
-   [x] Fork `origin/master` synchronized.
-   [x] `plane-flight-segment` retired locally and remotely.
-   [x] Accepted upstream history is the baseline for future work.

# Phase 2 Definition of Done

-   [x] Re-audit current upstream parameter flow.
-   [x] Establish initial PARM-dump semantics for the reusable history
    API.
-   [x] Define time-query semantics and edge cases.
-   [x] Implement reusable AMC-native timestamped parameter history.
-   [x] Avoid Plane-specific parameter-history workarounds.
-   [x] Add focused temporal-semantics tests.
-   [x] Validate against real logs containing parameter changes.
-   [x] Submit the reusable infrastructure PR (#1995).
-   [x] Obtain maintainer architectural confirmation.
-   [x] Merge maintainer-reworked implementation upstream.
-   [x] Synchronize local/fork master and retire obsolete feature
    branch.

# Phase 3 Definition of Done --- First Plane Landing Slice

-   [x] Audit the final merged ParameterHistory API on current `master`.
-   [x] Define the smallest landing-availability contract using existing
    AMC models.
-   [x] Preserve validated APT multi-attempt / abort / go-around
    behavior.
-   [x] Use `PlaneFlightSegmentDetector` as the parent
    operational-flight scope.
-   [x] Use timestamped parameter state where landing interpretation
    depends on parameters that may change within one BIN.
-   [x] Keep ARSP/RFND/CMD/MSG optional while making BARO mandatory per
    maintainer direction.
-   [x] Preserve conservative mission LAND-target handling.
-   [x] Emit objective AMC-native flat results only.
-   [x] Do not introduce qualitative good/poor/safe/unsafe scoring.
-   [x] Do not add Plane-specific frontend or recommendation
    infrastructure.
-   [x] Add APT-equivalent preflare/flare quantitative evidence.
-   [x] Add APT-equivalent firmware Flare and glide-slope message
    evidence.
-   [x] Confirm there is no distinct firmware preflare MSG in validated
    APT behavior.
-   [x] Reconstruct complete CMD mission snapshots conservatively and
    associate the correct LAND target per attempt.
-   [x] Match all 16/16 mission-target decisions and all 3/3 comparable
    computed target distances against APT.
-   [x] Keep post-attempt `Distance from LAND point=...` firmware
    messages deliberately outside APT-parity scope.
-   [x] Stop and review before any shared architecture change not
    already supported by `ARCHITECTURE_log_analysis.md`.
-   [x] Run focused AMC tests, applicable full AMC non-SITL tests, APT
    landing regression, and APT event/timeline regression before
    substantive PR.
-   [x] Complete the APT landing migration completeness audit and close
    the RFND lifecycle gap.
-   [x] Complete final branch-level review and correct
    active-GPS/non-finite-parameter findings.
-   [x] Open PR #2024 for maintainer review.
-   [x] Address maintainer review, obtain approval, squash, and merge PR #2024.
-   [x] Establish objective Plane landing analysis before configuration guidance.
-   [x] Obtain maintainer direction that analysis should point users to the
    earliest relevant configuration-sequence step rather than directly becoming
    a tuning engine.

------------------------------------------------------------------------

# Phase 4 Definition of Done --- ArduPlane Configuration Method

## Audit / planning baseline

-   [x] Synchronize local AMC `master` before the configuration-method audit.
-   [x] Audit `configuration_steps_ArduPlane.json` end to end before editing.
-   [x] Audit the respective Plane `*.param` files and identify ownership by step.
-   [x] Document step ordering and dependency/re-run implications.
-   [x] Identify Plane gaps, inherited Copter/QuadPlane assumptions, misplaced
    responsibilities and template inconsistencies.
-   [x] Establish that configuration content—not shared AMC architecture—is the
    first problem to solve.
-   [x] Preserve the full audit in
    `Docs/Implementation/ArduPlane_Configuration_Method_Audit.md`.
-   [x] Select the first bounded implementation task: Step 66 Everyday use / RTL.

## PR 1 — Step 66 Everyday use / RTL

-   [ ] Validate `RTL_ALTITUDE` semantics and units against ArduPlane 4.7.x
    source/metadata.
-   [ ] Validate `RTL_CLIMB_MIN` for the same firmware scope.
-   [ ] Validate existing Step 66 battery-failsafe parameters for Plane 4.7.x.
-   [ ] Correct stale/wrong Plane Step 66 parameter content without mechanically
    translating Copter values or units.
-   [ ] Update Step 66 Plane-specific rationale/documentation as required.
-   [ ] Keep both Plane templates consistent.
-   [ ] Add focused tests for changed Plane configuration content.
-   [ ] Run applicable configuration-step/template tests and static checks.
-   [ ] Keep the PR free of unrelated sequence, landing-analysis or architecture
    changes.
-   [ ] Obtain maintainer review.

## Later method work

-   [ ] Resolve sequence/template conformance issues as a separate PR.
-   [ ] Establish fixed-wing frame, mixer, servo/output and control-surface
    foundations.
-   [ ] Validate Plane propulsion and failsafe ownership.
-   [ ] Establish canonical airspeed and flight-envelope ownership before
    dependent flight/tuning stages.
-   [ ] Add coherent Plane takeoff, landing, attitude-tuning, TECS and navigation
    paths incrementally.
-   [ ] Establish explicit QuadPlane applicability boundaries.
-   [ ] Only after canonical ownership exists, map Plane log-analysis findings to
    the earliest relevant configuration step through AMC's existing result path.

------------------------------------------------------------------------

# APT ParameterHistory R&D --- COMPLETE

## Objective and Outcome

Reusable timestamped parameter history is implemented in APT as research
and analysis infrastructure. The work preserved APT's native absolute
`TimeUS` microsecond convention while adopting the validated temporal
semantics needed for event-time parameter evidence.

Completed commits:

``` text
e13fc73  feat(params): add timestamped parameter history
7bb0d26  refactor(rangefinder): use event-time parameter history
0b660ec  refactor(flight): use event-time stall speed
```

This work is complete. It must not appear in future task sequences as an
unimplemented port, pending validation task, or uncommitted working-tree
change.

## Implemented APT Contract

APT retains embedded `PARM` records as core log metadata and exposes
reusable history through `FlightLog.parameter_history`.

Public evidence API:

``` text
ParameterChange.time_us: int

flight_log.parameter_history.value_at(
    parameter_name,
    time_us,
)

flight_log.parameter_history.latest_values
```

Time semantics:

-   timestamps use absolute raw BIN `TimeUS` microseconds;
-   no conversion to seconds;
-   no rebasing to first message, first PARM, flight start, or another
    epoch;
-   event-time consumers query the shared log-level history directly.

The implementation preserves the validated startup/change semantics
established during the APT/AMC comparison, including startup-baseline
reconstruction, timestamped post-startup changes, exact-timestamp
effectiveness, stable duplicate-timestamp ordering with last logged
value winning, late first occurrence remaining unavailable before first
evidence, and explicit rejection of invalid/non-finite timestamps.

The `log_17.bin` early-PARM-gap case was retained as evidence for the
strict startup semantics rather than being silently "improved."

## Implemented Consumers

### Rangefinder

`RangefinderEvents` uses event-time parameter history for `RNGFND1_MAX`.

The companion `.params` snapshot is not used as historical fallback for
this consumer.

### Flight detection

`FlightWindowDetector` uses event-time `AIRSPEED_STALL`.

For a finite positive logged stall speed:

``` text
effective_threshold = max(configured minimum-speed floor,
                          0.5 * AIRSPEED_STALL)
```

If event-time stall evidence is missing, non-finite, zero, or negative,
the detector uses its configured minimum-speed heuristic rather than
inventing a stall-speed value.

The validated flight-boundary regression remained unchanged.

## Companion `.params` Boundary

The companion parameter reader remains legacy infrastructure and is
separate from embedded timestamped history.

New APT analysis should not introduce a dependency on companion
`.params` snapshots when the required evidence is already available from
BIN `PARM` records. Companion snapshots must not be silently used as
fallback for event-time parameter evidence.

A repository-wide audit found no current production analysis consuming
`FlightLog.parameters`, `FlightLog.param()`, or `FlightLog.has_param()`.
That makes the companion reader probably redundant for normal production
analysis, but removal remains a separate deprecation/design decision
because the API, diagnostic/test tooling, legacy normalization, and
possible external snapshot use must be considered deliberately.

`Config/landing.yaml` parameter filters must not be opportunistically
changed as part of new analysis work.

## Validation Status

The ParameterHistory implementation was validated before commit and its
consumers were regression-tested. The established APT landing and
event/timeline regressions remained passing, and subsequent Battery
Analysis work successfully uses embedded ParameterHistory for session
configuration without companion `.params` fallback.

ParameterHistory is therefore **completed infrastructure**, not a
current R&D implementation task.

------------------------------------------------------------------------

# Battery Analysis / Pack History Status

The first bounded Battery Analysis extension is complete in APT:

``` text
4e83b46  feat(battery): add bounded load-event analysis
```

Implemented scope includes:

-   embedded-`PARM` session configuration for the primary BAT monitor:
    `BATT_CAPACITY`, `BATT_LOW_VOLT`, `BATT_CRT_VOLT`,
    `BATT_FS_VOLTSRC`;
-   AUTO Takeoff Load Events bounded by validated `FlightWindow`
    semantics;
-   Sustained Load Events using the exact configured `CTUN.ThO >= 90`
    for `>= 8.0 s` rule;
-   common bounded-event evidence including pre-load voltage, minimum
    voltage, peak/average current, current at minimum voltage, sag,
    five-second recovery, consumed capacity at event start, and
    configured-threshold margins where semantically supported;
-   optional user-supplied Pack ID at the session/presentation boundary;
-   five-log regression validation including `log_0.bin`;
-   independence from companion `.params` for the implemented battery
    configuration path.

The battery model remains whole-pack and chemistry-neutral. It does not
infer cell condition, internal resistance, state of health, or
replacement advice.

Deferred battery work is deliberately narrower:

-   genuine manual-takeoff evidence and a validated manual-takeoff
    detector;
-   persistent longitudinal Pack History after enough repeated
    identified-pack sessions exist;
-   persistence-format selection only after auditing APT persistence
    options;
-   generalized non-primary BAT monitor parameter mapping only if real
    logs demonstrate a need;
-   any change to the 90% / 8 s sustained-load detector only if broader
    real-log evidence justifies it.

Persistent Pack History must remain separate from per-log Battery
Analysis until the evidence and persistence model are sufficiently
established.

------------------------------------------------------------------------

# Current Project Checkpoint

``` text
APT timestamped ParameterHistory                 COMPLETE
        │
        ▼
APT bounded Battery Analysis                     COMPLETE (4e83b46)
        │
        ▼
AMC Plane infrastructure
        ├── Flight segmentation / PR #1989       MERGED
        ├── ParameterHistory / PR #1995          MERGED
        └── Plane landing / PR #2024             MERGED
                ├── 208 focused Plane tests
                ├── Tridge APPROVE
                ├── Amílcar APPROVE
                └── squash/merge complete
        │
        ▼
ArduPlane configuration-method audit             COMPLETE
        ├── master @ c58eb9f8
        ├── configuration_steps_ArduPlane.json
        ├── Plane *.param inventory
        ├── ownership/dependency map
        └── prioritized P0/P1/P2/P3 findings
        │
        ▼
Step 66 Everyday use / RTL                       NEXT PR
        ├── validate Plane 4.7.x RTL semantics
        ├── correct stale RTL content
        ├── validate battery-failsafe ownership
        └── focused configuration-content tests
        │
        ▼
Remaining Plane method domains                   LATER / SMALL PRs
        │
        ▼
Analysis → configuration-step mapping            LATER
        │
        ▼
APT continues as Plane log-analysis R&D environment
```

The active AMC task is now a bounded correction of ArduPlane Step 66, not
another broad configuration audit and not another landing-analysis metric.

The complete configuration-method audit is preserved at:

``` text
Docs/Implementation/ArduPlane_Configuration_Method_Audit.md
```

Future method work should consume that audit as the baseline and address its
findings through small reviewable PRs. New APT research should continue to
start from a concrete engineering question, establish evidence semantics and
real-log validation, and only then be considered for AMC-native implementation.
