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