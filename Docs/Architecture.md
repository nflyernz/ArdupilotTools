# ArduPlane Analyzer

## Mission

ArduPlane Analyzer is an engineering analysis tool for ArduPlane flight logs.

It does not replace UAV Log Viewer, Mission Planner or QGroundControl.

Its purpose is to explain **why** the aircraft behaved as it did using objective measurements derived from the flight log.

---

# Philosophy

The analyser shall:

- Measure
- Compare
- Quantify
- Explain

The analyser shall not:

- Tune aircraft
- Recommend parameter values
- Optimise PID gains
- Override pilot judgement

---

# Core Principles

## Evidence before opinion

Every statement shall be supported by measurable evidence.

Example:

"Average approach speed was 10.4 m/s."

not

"Landing speed was too slow."

---

## Behaviour before parameters

Aircraft behaviour is analysed.

Parameters provide context only.

Example

LAND_ARSPD = 11 m/s

Measured IAS = 10.2 m/s

Difference = -0.8 m/s

No recommendation is made.

---

## Every graph answers a question

Graphs are never included simply because the data exists.

Every graph must answer a specific engineering question.

---

## Every metric has a purpose

Each metric must answer one question.

Examples

Glide slope

Did the aircraft follow the intended approach?

Pitch tracking

Did the aircraft achieve commanded pitch?

Throttle

Was energy management stable?

---

## Pilot remains responsible

The software highlights observations.

The pilot decides whether configuration changes are appropriate.

---

# Scope

Version 1

Landing Analysis

Version 2

Launch Analysis

Future

FBWA

AUTO

RTL

Power

Sensors

Navigation

---

# Landing Analysis

The landing module will measure:

• Geometry

• Airspeed

• Pitch

• Roll

• Throttle

• TECS

• Flare

• Touchdown

• Rangefinder

---

# Report Structure

Summary

Measurements

Evidence

Observations

Plots

Appendix

---

# Coding Philosophy

Small modules.

Single responsibility.

No duplicated code.

Every function should be testable.

Every report should be reproducible.
