# ArduPilotTools

ArduPilotTools is a Python toolkit for evidence-based analysis of ArduPilot
fixed-wing flight logs.

The project is currently focused on ArduPlane landing analysis. It reads
DataFlash BIN logs, identifies individual flights and AUTO landing attempts,
and reports measured and logged evidence associated with each attempt.

The longer-term goal is a modular flight-analysis framework that can support
additional analyses such as cruise performance, TECS behaviour, power systems,
RTL and autotune.

## Current Status

The project is under active development.

The current primary user-facing analysis is **Landing Analysis**.

The framework also contains an Event Timeline, Battery Analysis, sensor
processors and development/regression tools used to validate the underlying
analysis architecture.

Landing Analysis has been regression-tested against a set of development
ArduPlane 4.7 flight logs containing successful landings, aborted approaches,
multiple landing attempts, missing flare evidence and different landing
termination cases.

Raw development flight logs and aircraft parameter files are intentionally
not included in the public repository.

## Design Philosophy

The analyzer is intended to report what the flight log supports rather than
judge the quality of the flight.

The current landing analysis therefore concentrates on measured or logged
evidence such as:

- landing-attempt boundaries
- approach altitude
- glide slope
- preflare timing and height
- airspeed
- GPS groundspeed
- sink rate
- flare timing and height
- distance from the mission landing target
- rangefinder acquisition
- GPS rollout-stop evidence
- landing termination reason

Missing or ambiguous evidence is reported as unavailable rather than inferred.

Unusual telemetry is preserved as evidence rather than automatically
reinterpreted as pilot error, aircraft error or firmware error.

## Requirements

The project currently uses Python 3 and the packages listed in
`requirements.txt`.

A Python virtual environment is recommended.

Example:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Landing Analysis Input

Landing Analysis accepts either a single ArduPilot DataFlash BIN log or an
entire directory of BIN logs.

Single log:

```text
Log file or directory: Logs/log_19.bin
```

Entire directory:

```text
Log file or directory: Logs/
```

When a directory is supplied, Landing Analysis processes all `.bin` and `.BIN`
files in that directory in sequence. A log may contain multiple detected
flights, and each flight is analysed independently for landing attempts.

This allows the same analysis workflow to be used for an individual flight log
or for batch analysis of a collection of logs.

