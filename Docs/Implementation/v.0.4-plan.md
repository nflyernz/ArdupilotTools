> **Archived roadmap**
>
> Retained as a historical development record.

# v0.4 — Landing Detection Implementation Plan

## Purpose

This document defines the implementation plan for:

**v0.4 — Landing Detection**

The objective is to replace the bounded development `LandingWindow` used
through v0.3 with objective detection of real ArduPlane AUTO-landing
attempts inside each `FlightWindow`.

A continuous flight may contain:

- no AUTO-landing attempts;
- one AUTO-landing attempt;
- multiple AUTO-landing attempts;
- aborted AUTO-landing approaches;
- go-arounds;
- restarted AUTO-landing sequences;
- a completed AUTO landing.

v0.4 must identify those attempts without splitting the parent
`FlightWindow`.

Manual approaches and manual landings outside the ArduPlane AUTO landing
sequence are not `LandingWindow` objects in v0.4.

This is an implementation plan.

Architectural authority remains:

```text
Docs/Architecture.md


## Core Flight-State Sources

LandingWindow detection may rely on the following core flight-state
sensors and systems:

- GPS
- Barometer
- IMU / AHRS attitude

These are the core flight-state sources considered available to the
AUTO-landing analysis.

The following are optional and must not be required for LandingWindow
detection:

- Airspeed sensor
- Rangefinder

Optional sensor data may enrich subsequent landing analysis when
available, but its absence must not prevent detection of an AUTO-landing
attempt.

In particular, rangefinder data must never define the start or end of a
LandingWindow.

### Firmware Version Guard

Before interpreting `LAND.stage` or other landing-controller evidence,
the analysis must verify that the log is from a supported ArduPlane
firmware version.

For v0.4, the initial landing-state investigation is restricted to
ArduPlane 4.7.x.

If the firmware version is available in the BIN log, the analysis should
detect a pre-4.7 log and **error immediately when the log is read**, rather
than allowing incompatible data to proceed through the landing analysis.

If firmware version is not exposed in the BIN log, determine how the
reader can reliably establish the firmware version.

Add support for pre-4.7 landing behaviour as a separate investigation
after the 4.7.x implementation has been validated.

- [ ] Determine whether ArduPlane firmware version is exposed in the BIN
      log and available through FlightReader.
- [ ] Add an early version guard for pre-4.7 logs if the version can be
      determined from the BIN.
- [ ] Investigate pre-4.7 LAND.stage / landing-controller behaviour
      separately.
      
      
      - [ ] Add configurable landing-window end speed, default 3.0 m/s
- [ ] Add configurable landing-window end persistence, default 2.0 s
- [ ] Validate GPS-only landing-window termination across the four 4.7 logs
      
      ## v0.4 Final Cleanup — Descriptive Module Names

- [ ] Review all modules under `Scripts/core/`
- [ ] Rename modules whose filenames do not clearly describe their purpose
- [ ] Use descriptive names that make the module's role obvious without opening it
- [ ] Identify and replace historical, abbreviated, or overly generic names
- [ ] Review `model.py` in particular — replace with a name that describes what it provides
- [ ] Update all imports and references
- [ ] Update test/development harnesses
- [ ] Update documentation and roadmap references
- [ ] Run `python -m compileall -q Scripts`
- [ ] Run the v0.4 regression tests
- [ ] Commit the naming cleanup separately

### v0.4 — Final Validation / Hardening

- [ ] Fix landing-attempt abort handling so an aborted/go-around attempt returns a bounded window with an explicit `ABORT` termination reason rather than being silently discarded.
- [ ] Make landing-window termination event-driven so `DISARM`, mode change, abort, GPS persistence, and flight-window end are evaluated independently of GPS sample timing.
- [ ] Fix event-timeline mode decoding to use the same `ModeNum` field as production landing-window logic.
- [ ] Confirm and enforce the intended ArduPlane firmware scope for v0.4; implementation is validated against ArduPlane 4.7.x.
- [ ] Add assertive regression checks for all four representative 4.7 logs, including `log_11.bin` abort/go-around cases.
- [ ] Retain the human-readable unified event timeline as a validation and diagnostic tool.
- [ ] Re-run compile, diagnostic timeline, and regression tests after the above changes.
- [ ] Run a final read-only Codex sanity check before committing the v0.4 checkpoint.

### v0.4 — Analyse Deliverable

- [ ] Add **Landing Analysis** to the Analyse menu.
- [ ] Present a structured landing-attempt timeline for each flight.
- [ ] Show landing-window start and end times.
- [ ] Show landing outcome: completed, aborted/go-around, disarmed, or unresolved.
- [ ] Show landing-window termination reason: GPS groundspeed, disarm, mode change, abort, or flight-window end.
- [ ] Show `LAND.stage` transitions alongside the landing timeline.
- [ ] Show key landing events including rangefinder engagement, flare, and landing aborts.
- [ ] Provide timestamps and measurements so each detected landing can be independently validated against the flight log.
- [ ] Use the structured landing-window data as the foundation for progressively richer landing analysis in future versions.

### v0.4 — Final Cleanup

- [ ] Audit module usage and identify genuinely unused modules before renaming or removing anything.
- [ ] Rename modules to more descriptive names where their current names obscure their purpose.
- [ ] Re-run the full regression suite after module cleanup.
- [ ] Commit the completed v0.4 checkpoint.

- [ ] Restrict v0.4 firmware acceptance to ArduPlane 4.7.x.
- [ ] Require AUTO landing context before accepting LAND.stage 1 as a landing-window start.
- [ ] Make the regression harness assert all four expected 4.7 logs were processed and none were skipped.
- [ ] Remove unused imports from landing_window_detector.py.
- [ ] Remove the no-op LAND.stage 0 scan.
- [ ] Re-run compileall and event-timeline regression.
- [ ] Run one final read-only sanity check.
- [ ] Commit v0.4.