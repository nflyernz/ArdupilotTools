# Version 0.1

✓ Read BIN

✓ Extract messages

✓ Export CSV

✓ Dashboard

---

# Version 0.2

Landing segmentation

Landing metrics

Landing report

---

# Version 0.3

Landing scorecard

HTML report

PDF report

---

# Version 0.4

Parameter integration

Multiple aircraft profiles

---

# Version 0.5

Flight comparison

Parameter comparison

Firmware comparison

---

# Version 0.6

Launch module

---

# Version 1.0

Public release


## v0.2.1 – ArduPlane 4.6 Compatibility

### Investigate

- [ ] Parameter loading
  - Compare 4.6.3 and 4.7 `.params` formats.
  - Determine why 4.6 parameters are not loading.

- [ ] LAND messages
  - Compare LAND message sequences between 4.6.3 and 4.7.
  - Identify any behavioural changes.

- [ ] Landing window detection
  - Investigate oversized landing windows on 4.6.3 logs.
  - Verify behaviour with go-arounds and aborted approaches.

### Validation

- [ ] Run detector suite on all available logs.
- [ ] Record observations before modifying algorithms.
- [ ] Only change detectors when supported by multiple logs.


## Objective Analysis Principle

The toolkit shall derive its conclusions solely from telemetry contained within the flight log.

The processing chain is:

## Objective Analysis Principle

The toolkit shall derive its conclusions solely from telemetry contained within the flight log.

The processing chain is:

```text
Flight Log
    │
    ▼
Processors
    │
    ▼
Analyzers
    │
    ▼
Report
```

### Design Principle

The flight log is the only source of truth.

Processors and analyzers shall operate only on information contained within the telemetry. They shall not consume or depend upon:

- pilot notes
- flight journals
- developer annotations
- video recordings
- user input
- manually entered events

These sources may be used during development to validate the software, but they must never influence the analysis itself.

### Validation

Development follows an independent validation workflow:

```text
Flight Log
    │
    ▼
Analysis
    │
    ▼
Report
    │
    ├── UAV Log Viewer
    ├── Pilot observations
    ├── Flight video
    └── Engineering review
```

Validation exists only to answer one question:

> Did the software correctly interpret the telemetry?

If not, the algorithms are improved. The validation data is never incorporated into the runtime analysis.

### Architectural Guidance

When adding a new feature, ask:

1. Can this conclusion be reached directly from telemetry?
2. If not, can it be derived objectively from existing processor outputs?
3. If neither is possible, it does not belong in the analyzer.

This principle applies to every processor, analyzer and report.

### Expected Outcome

A completed analysis must be:

- deterministic
- repeatable
- objective
- independent of the operator
- suitable for unattended batch processing

Running the toolkit on the same log must always produce the same result, regardless of who performs the analysis or what they know about the flight.


✓ FlightReader

✓ BARO Processor

✓ GPS Processor

⬜ ARSP Processor

⬜ RFND Processor (redesign)

⬜ FC Processor

⬜ Landing Window Analyzer

⬜ Landing Analyzer

⬜ Landing Report
