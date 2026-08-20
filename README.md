# Plane Log Analysis

A Python toolkit for objective analysis of **ArduPilot fixed-wing
(ArduPlane) DataFlash logs**.

The project turns flight logs into scoped engineering evidence.
Individual flights are detected within a log, analyses operate inside
those flight boundaries, and missing or ambiguous evidence is reported
as unavailable rather than guessed.

The current development focus has been landing analysis, supported by
event, sensor and battery analysis infrastructure.

## Current Status

The core analysis framework and initial landing-analysis workflow are
implemented.

Current capabilities include:

-   detecting multiple flights within one `.bin` log;
-   detecting AUTO landing attempts within each flight;
-   representing aborted and restarted landing attempts;
-   reporting approach, preflare and final-flare evidence;
-   reporting optional rangefinder evidence;
-   detecting landing/rollout completion from persistent low GPS speed;
-   reporting final GPS-stop distance from the applicable LAND mission
    target;
-   Event Timeline analysis;
-   Battery Analysis;
-   assertion-based landing regression testing.

Landing output is intentionally **measurement-focused**. It reports
logged and derived evidence without automatically judging whether a
landing was good, bad, correctly tuned or incorrectly tuned.

See `Docs/Roadmap.md` for current development direction.

## Requirements

-   Python **3.13.13**
-   ArduPilot DataFlash `.bin` logs
-   dependencies listed in `requirements.txt`

The current landing-analysis implementation has been developed and
regression-tested against **ArduPlane 4.7.x** logs.

## Installation

From the repository root:

``` bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

From the repository root:

``` bash
python Scripts/analyse.py
```

The Analyse menu currently presents:

``` text
Flight Analysis
================

1. Landing Analysis
2. Event Timeline
3. Battery Analysis
4. Cruise Analysis
5. Autotune Review
6. Sensor Diagnostics
7. Log Summary
0. Exit
```

Landing Analysis, Event Timeline and Battery Analysis are established
analysis workflows. Other menu entries may be at earlier stages of
development.

## Logs and Parameters

Logs are normally stored under:

``` text
Logs/
```

For example:

``` text
Logs/log_19.bin
```

Companion parameter files are stored under:

``` text
Params/
```

The parameter filename is expected to match the log stem:

``` text
Logs/log_19.bin
Params/log_19.params
```

If a companion parameter file is absent, parameter-dependent features
may be unavailable. The analyzer does not invent missing parameter
values.

Landing configuration is stored in:

``` text
Config/landing.yaml
```

Configuration paths are resolved relative to the repository rather than
the process working directory.

## Flight Scope

A DataFlash log may contain more than one flight.

``` text
FlightLog
    |
    +-- FlightWindow
    |       |
    |       +-- analysis-specific windows
    |
    +-- FlightWindow
```

A `FlightWindow` represents one continuous flight. Go-arounds and
restarted landing attempts remain inside the same flight when flight
continuity is maintained.

Analyses operate independently on each detected flight.

# Landing Analysis

Select:

``` text
1. Landing Analysis
```

Then enter either a `.bin` file or a directory containing logs.

Example:

``` text
Log file or directory: Logs/log_19.bin
```

Landing Analysis detects landing attempts and reports evidence within
each attempt.

## Landing Window

Reports the landing-window bounds and duration.

``` text
Landing window              11:57.705 -> 12:23.104
Landing duration            25.4 s
```

## Approach

Currently reports:

-   approach altitude;
-   glide slope.

``` text
APPROACH

Approach altitude           20.5 m
Glide slope                 3.9 deg
```

## Preflare

Currently reports:

-   preflare time;
-   preflare height;
-   airspeed, where available;
-   GPS groundspeed;
-   sink rate.

``` text
PREFLARE

Time                        12:15.904
Preflare height             4.9 m
Airspeed                    11.0 m/s
GPS groundspeed             11.1 m/s
Sink rate                   1.5 m/s
```

## Flare

Currently reports:

-   final-flare time;
-   flare-timing height;
-   sink rate;
-   airspeed, where available;
-   GPS groundspeed;
-   logged flare distance to target.

``` text
FLARE

Time                        12:16.404
Flare-timing height         4.6 m
Sink rate                   1.6 m/s
Airspeed                    11.5 m/s
GPS groundspeed             11.5 m/s
Flare distance to target    45.8 m
```

`Flare-timing height` represents the ArduPilot landing-controller
evidence recorded in the log. It is not an independently detected
physical touchdown height.

## Rangefinder

Where RFND data exists, Landing Analysis reports acquisition evidence
such as:

``` text
RANGEFINDER

First non-zero              12:08.925
First distance              11.7 m
First in range              12:09.023
In-range distance           5.8 m
Continuous from             12:12.184
```

Rangefinder data is optional. The analyzer preserves unusual rangefinder
behaviour as measured evidence rather than silently correcting it.

## Landing / Rollout Completion

Where persistent low GPS speed is detected:

``` text
LANDING / ROLLOUT COMPLETION

GPS stop                    12:23.104
Flare -> stop               6.7 s
Distance from target        19.1 m
End reason                  GPS stop
```

**GPS stop is not treated as touchdown.**

It represents the point at which the configured low-groundspeed
persistence condition establishes landing/rollout completion.

Likewise, `Distance from target` is the aircraft's distance from the
applicable LAND mission target at the detected GPS-stop point. It is not
automatically a touchdown-distance measurement.

## Aborted Attempts

Multiple landing attempts can occur within one flight.

An attempt may terminate with:

``` text
End reason                  Landing aborted
```

A subsequent attempt remains part of the same `FlightWindow` when the
aircraft remained continuously in flight.

## Missing Evidence

Optional or unavailable measurements are reported explicitly:

``` text
Unavailable
```

Examples include:

-   no usable ARSP evidence;
-   no RFND evidence;
-   no final-flare event;
-   no GPS-stop completion before the flight window ends;
-   no complete applicable mission snapshot from which a LAND target can
    be established.

Ambiguous evidence remains unavailable rather than being replaced with
an inferred value.

# Event Timeline

Select:

``` text
2. Event Timeline
```

The Event Timeline presents detected events chronologically within each
flight. It is useful for inspecting evidence underlying higher-level
analyses such as landing detection.

# Battery Analysis

Select:

``` text
3. Battery Analysis
```

Battery Analysis is a separate flight-scoped analysis.

Implemented measurements include, where available:

-   voltage;
-   current;
-   average current;
-   consumed mAh;
-   consumed Wh;
-   highest-current event;
-   voltage sag;
-   five-second voltage recovery.

The measurement layer is chemistry-neutral and does not automatically
infer battery health or suitability.

# Project Structure

Key project areas:

``` text
Config/
    landing.yaml

Docs/
    Roadmap.md
    Implementation/

Logs/
    *.bin

Params/
    *.params

Scripts/
    analyse.py

    analyses/
        landing.py
        ...

    core/
        flight_data.py
        flight_window.py
        flight_window_detector.py
        landing_window.py
        landing_window_detector.py
        landing_attempt.py
        landing_attempt_processor.py
        landing_attempt_analysis.py
        rangefinder.py
        gps_stop.py
        ...

    test_landing_regression.py
    ...
```

The architectural separation is deliberate:

``` text
Reader
  |
  v
FlightLog
  |
  v
FlightWindow
  |
  v
Detector / Processor
  |
  v
Analysis Result
  |
  v
Presentation
```

# Testing

Compile the Python source:

``` bash
python -m compileall -q Scripts
```

Run the landing regression:

``` bash
python Scripts/test_landing_regression.py
```

Expected result:

``` text
Landing analysis regression: PASS
```

Before committing changes:

``` bash
git status
git diff --check
```

# Development Principles

## Evidence before interpretation

Core processors and detectors report what the log establishes. They
should not silently convert unusual measurements into tuning
conclusions.

## Scope is explicit

Telemetry used by an analysis must belong to the applicable flight or
child window.

## Boundaries have owners

Detectors establish event and window boundaries. Processors measure
evidence within those boundaries.

## Optional sensors remain optional

Missing airspeed or rangefinder telemetry should not unnecessarily
prevent analysis of evidence that remains available.

## Ambiguity remains visible

If a LAND target, event or measurement cannot be established defensibly,
the result should be `Unavailable`.

## Regression protects semantics

Validated flight and landing boundaries should not change incidentally
during presentation, cleanup or unrelated feature work.

# Documentation

Project documentation is under:

``` text
Docs/
```

The current development roadmap is:

``` text
Docs/Roadmap.md
```

Implementation plans and older roadmaps may be retained as historical
development records. They describe earlier project states and should not
be assumed to represent the current implementation unless explicitly
marked current.

# Development Direction

The completed landing-analysis foundation is being prepared for user and
ArduPlane community review.

The planned sequence is:

1.  community review of existing landing evidence and terminology;
2.  stable structured result/report contract;
3.  machine-readable export;
4.  richer reporting and plotting where those outputs answer
    demonstrated engineering questions;
5.  broader regression coverage;
6.  additional flight analyses built on the same flight-scoped
    architecture.

See `Docs/Roadmap.md` for the current roadmap.
