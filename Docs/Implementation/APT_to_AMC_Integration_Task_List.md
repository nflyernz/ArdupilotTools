# APT → AMC Integration Record and Current Backlog

The August integration plan below is retained as an engineering record.
Phases 1–3 describe decisions made before implementation; Phases 4–7 record
the resulting AMC work. The final sections distinguish current APT work from
possible future AMC contributions.

## Original goal

Move the useful ArduPlane analysis work from ArduPilotTools into the ArduPilot Methodic Configurator (`small_fixes` branch), using AMC's existing log and parameter pipeline and following its backend → data_model → frontend architecture.

The first objective is **not** to add new analysis features or make qualitative judgements about landing quality. It is to understand the integration boundary, preserve the existing measurable analysis, and produce a small, reviewable first Pull Request.

## Phase 1 — Prepare the Development Environment

- [x] Fork `ArduPilot/MethodicConfigurator` on GitHub.
- [x] Clone the fork locally.
- [x] Add the official ArduPilot repository as the upstream remote.
- [x] Check out / create the working branch from AMC `small_fixes`.
- [x] Follow AMC's development setup instructions in `CONTRIBUTING.md`.
- [x] Run AMC's existing tests and linting locally before making changes.
- [x] Confirm the unmodified `small_fixes` branch passes locally, subject to the pre-commit tooling exception documented below.


### Phase 1 Baseline Status

Local AMC baseline:

```text
Repository   : ~/MethodicConfigurator
Branch       : small_fixes
Baseline     : ee46bced  fix(lint): fix linter issues
Origin       : nflyernz/MethodicConfigurator
Upstream     : ArduPilot/MethodicConfigurator
Python       : 3.13.15
uv           : 0.12.5
Working tree : clean before baseline checks
```

`origin/small_fixes` and `upstream/small_fixes` were confirmed identical before starting integration work.

The AMC developer environment was created successfully, but two issues were encountered on the unmodified branch:

- `SetupDeveloperPC.sh` uses `${response,,}`, which fails under Apple's older `/bin/bash`. Running the script explicitly with the newer Homebrew Bash avoids that problem.
- The script requests the Homebrew formula `uv@0.10.9`, which was unavailable. Installing the current Homebrew `uv` first allowed environment creation and dependency installation to continue.

These are development-environment observations only. No AMC source code was changed.

#### Pytest baseline

The first untouched `small_fixes` test run terminated with a native Tkinter
segmentation fault while exercising the Component Editor GUI integration test.
At approximately the same time, multiple AMC GUI windows were being opened and
macOS requested Screen & System Audio Recording permission for Terminal.

After granting Terminal the required screen-recording permission, the complete
non-SITL suite was rerun:

```bash
uv run pytest -m "not sitl"
```

Result:

```text
4767 passed, 6 skipped, 53 deselected, 4 xfailed
308.58s (0:05:08)
```

The untouched AMC `small_fixes` pytest baseline therefore **passes locally on
macOS with Python 3.13.15**.

The earlier Tkinter segmentation fault is retained here as an environment
observation. The successful rerun strongly indicates that it was associated
with the macOS GUI/screen-recording environment rather than an AMC source-code
failure or APT migration regression.

#### Pre-commit baseline exception

The untouched branch was also checked with:

```bash
pre-commit run --all-files
```

Pre-commit environment creation stopped while installing the `markdownlint-cli` hook because npm refused the local Git package source:

```text
npm error EALLOWGIT
npm error Fetching non-root packages of type "git" have been disabled
```

This is recorded as a local tooling/environment baseline exception. It occurred before any APT → AMC code changes.

#### Phase 1 conclusion

Phase 1 environment preparation is complete and the untouched AMC pytest baseline passes locally.

The only remaining baseline exception is the pre-commit environment-installation failure for `markdownlint-cli` caused by npm `EALLOWGIT`. This occurred before any APT → AMC code changes and must remain distinguished from failures introduced by Plane integration work.

Phase 2 — the no-code architecture audit — can now begin.

Reference starting point:

```text
small_fixes @ ee46bced
No APT migration code applied
```

## Phase 2 — Architecture Audit — No Code Changes

Give Codex both repositories and explicitly instruct it to **analyse only**.

Map the current APT landing-analysis architecture against AMC's `log_analysis` architecture.

For every relevant APT module/function, classify it as:

- [x] Replaced by AMC backend functionality.
- [x] Replaced by AMC parameter infrastructure.
- [x] Requires adaptation to AMC `LogData` / analysis context.
- [x] Genuine Plane business logic worth migrating.
- [x] Reporting/frontend functionality to defer.
- [x] Obsolete or unnecessary after integration.

Specifically identify:

- [x] How APT currently opens and parses `.bin` files.
- [x] How APT accesses DataFlash messages.
- [x] How APT handles message scaling.
- [x] How APT loads external `.param` files.
- [x] How APT obtains parameter values.
- [x] How APT uses parameter defaults.
- [x] How APT identifies firmware/version.
- [x] How APT identifies Plane flights.
- [x] How APT detects landing segments.
- [x] How approach, pre-flare, flare and touchdown are detected.
- [x] Which calculations are genuinely independent of the input/parser layer.
- [x] Which APT assumptions depend on particular messages being present.
- [x] Which calculations currently depend specifically on the available Ranger test data or current ArduPlane versions.


### Phase 2 Audit Outcome and Maintainer Guidance

The no-code APT → AMC architecture audit is complete.

The audit confirmed that AMC already owns most generic infrastructure that
standalone APT previously supplied, including log parsing/scaling, message
metadata, parameter access, firmware identity and the analysis framework.
Those components should not be duplicated during migration.

The main APT functionality worth carrying forward is the Plane-specific
business logic for operational flight scoping, landing-attempt detection and
objective landing evidence.

A core architectural difference was identified:

- APT was designed to analyse distinct operational stages within a log.
- It establishes a flight scope before deriving landing attempts and phases.
- APT flight bounds use arm state together with speed and altitude/motion
  evidence, with hysteresis, rather than treating the complete armed interval
  as the flight.
- This is particularly important for Plane because an aircraft may be armed
  well before launch and remain armed after landing.
- AMC is primarily configuration-oriented and currently tends to analyse the
  log as a whole.

This was raised with Amílcar before implementation.

Maintainer guidance received:

> "I had plans to add a flight segment concept at some point. So yes, I prefer
> a reusable flight-scope concept added to AMC.
>
> I guess a flattened log analysis results is easier to implement and just as
> useful. But I can be convinced otherwise."

Decisions resulting from that guidance:

1. **Flight segmentation will be designed as reusable AMC log-analysis
   infrastructure**, not hidden inside the Plane landing analysis.
2. APT's `FlightWindow` implementation is behavioural reference material; it
   should not be copied into AMC unchanged.
3. The new flight-scope facility should operate on AMC-native `LogData`.
4. Plane landing analysis will initially use AMC's existing **flat
   `LogAnalysisResult`** model.
5. A hierarchical/per-attempt result model will not be introduced unless
   implementation experience demonstrates a concrete need.
6. The first implementation boundary should be reconsidered around the
   reusable flight-segment facility before landing-analysis code is migrated.

### Phase 2 conclusion

Phase 2 is complete.

The principal architecture question discovered by the audit has been answered
by the AMC maintainer. Phase 3 interface mapping was also substantially
completed by the audit and is recorded below.

Before creating an implementation branch, perform a focused design
investigation for an AMC-native reusable flight-segment API and its tests.
This investigation should use APT's existing flight-window behaviour as
reference while respecting AMC's native message, time, result and data-model
conventions.


## Phase 3 — Map AMC Interfaces

Determine exactly what AMC already provides to Plane analysis through its log-analysis system.

Document:

- [x] Parsed/scaled message access.
- [x] `LogMessages` metadata.
- [x] Parameter values.
- [x] Parameter defaults.
- [x] Parameter documentation.
- [x] Vehicle and firmware information.
- [x] Time representation and synchronization between message types.
- [x] Handling of missing message types/fields.
- [x] Existing Copter analysis patterns that Plane should follow.
- [x] Result/data structures expected from analysis modules.
- [x] How analyses are registered/discovered.
- [x] How analysis results reach the frontend.

Do not design replacements for AMC functionality until this mapping is complete.

## Phase 4 — First PR Boundary: Decision and Outcome

The original candidate sequence was:

```text
AMC LogData → reusable flight scope → Plane landing analysis
            → flat LogAnalysisResult
```

The focused design work led to AMC-native `PlaneFlightSegmentDetector` and
`FlightSegment` models, followed by Plane landing-attempt detection and
evidence extraction within those segments. The implemented segment detector
uses persistent GPS groundspeed with an optional stall-speed threshold. The
earlier arm/speed/altitude discussion remains useful motivation for an
operational flight scope, but does not describe this detector's full input.

AMC owns BIN parsing, scaled `LogData`, parameter/context infrastructure,
analysis registration, and the flat `LogAnalysisResult`. Plane-specific
logic lives in AMC's log-analysis data-model and availability/analysis
modules. The contribution did not copy APT's standalone parser or add an
external parameter-file reader. It uses automated tests and the existing
result path, keeping frontend work limited. This boundary let maintainer
review address flight scope and evidence semantics without migrating all of
APT.

## Phase 5 — Test Data and Baselines: Outcome

Representative ArduPlane 4.7.x logs were used to compare AMC against APT's
landing behavior. The [APT roadmap](../../ArduPlane_Analyzer_Roadmap.md)
records four reference logs, ten operational flights, and sixteen landing
attempts in final validation. It also records the one reviewed GPS-stop
causality correction: AMC bounded the attempt at disarm; APT later adopted
the same rule, bringing the reference boundaries into agreement.

AMC has focused synthetic/unit tests for flight segmentation, landing
attempts, approach/pre-flare/flare stages, sensor evidence, and missing or
malformed input. The analysis gates unsupported firmware and missing required
evidence conservatively. Outputs are event boundaries and measurements,
not a generic landing-quality judgement.

### Landing Evaluation Boundary

The initial integration deliberately did **not** classify landings as good,
poor, normal, abnormal, safe, unsafe, or assign another generic quality score.

The available test data is too limited to establish robust general rules across ArduPlane aircraft and configurations.

The continuing boundary is:

- Detect what happened.
- Measure what happened.
- Report relevant aircraft, controller and parameter behaviour.
- Preserve evidence from the log.
- Avoid interpreting those measurements as universal indicators of landing quality.

Qualitative evaluation should be developed later using:

- guidance from experienced ArduPilot/AMC developers;
- a wider variety of ArduPlane aircraft;
- more landing logs;
- different landing configurations and modes;
- known failure/problem cases;
- validation of assumptions against ArduPilot's actual controller behaviour.

## Phase 6 — AMC Implementation: Completed

AMC implemented reusable Plane flight segmentation over native scaled
`LogData`, timestamped `ParameterHistory` in its log-analysis context, and
Plane landing detection and objective evidence reporting. Landing analysis
uses event-time parameter history where applicable and emits flat AMC
results. Its data-model tests cover flight and attempt boundaries, landing
stages, sensor selection, and absent evidence. APT supplied behavioral
reference cases; AMC retained its own parser and analysis architecture.

## Phase 7 — Review and Pull Request: Completed

The [APT roadmap](../../ArduPlane_Analyzer_Roadmap.md) records AMC
ParameterHistory as merged in PR #1995 and Plane landing analysis as merged
in **PR #2024 on 2026-09-10**. The AMC history contains the timestamped
parameter-history and Plane landing commits. Maintainer review shaped the
reusable flight-scope design and corrected GPS-stop causality; APT then
backported that causality rule. The roadmap records 208 Plane landing tests
and 305 affected AMC tests passing before merge. The merged landing work
remained within AMC's backend/data-model/result infrastructure.

## Phase 8 — Current State and Possible Next Work

**Already in AMC:** reusable Plane flight segments, timestamped parameter
history, and Plane landing-attempt analysis. This established a native
integration pattern; it did not imply that every APT analysis should be
ported unchanged.

**Current standalone APT:** Landing Analysis, Event Timeline, Battery
Analysis, conventional Plane TAKEOFF analysis, and fixed-wing AUTOTUNE
review. Their implementations and focused tests are present in this
repository. APT has also continued report/presentation work.

APT production parameter evidence now follows:

```text
DataFlash BIN → raw PARM → ParameterHistory → timestamp-aware analysis
```

The Phase 2 external `.param` audit describes the former architecture. In the

current APT architecture, companion `.param/.params` production loading and the

untimestamped `FlightLog` snapshot API have been removed; analysis uses

parameter evidence from the same BIN being analysed.

**Possible future work, not commitments:** deeper landing measurements where
evidence supports them; more reusable Plane flight/phase infrastructure;
consideration of TAKEOFF or AUTOTUNE for AMC's native architecture; TECS;
objective radio-link/range-check analysis; and other Plane diagnostics.
Generic landing-quality scores still require wider evidence and expert
validation. Range Check is not implemented here.

## Current Development Rule

The first AMC Plane landing contribution has passed review and established
the integration pattern. Standalone APT can continue developing objective
Plane analyses, using BIN-owned evidence and timestamp-aware parameter
history, with real-log validation and focused automated tests. Work proposed
for AMC should use its native `LogData`, context, data-model, and result
infrastructure rather than duplicate parsing or parameter readers. Report
what the evidence shows without unsupported quality scores.
