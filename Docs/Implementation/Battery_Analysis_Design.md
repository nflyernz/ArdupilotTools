# Battery Analysis Design

## 1. Purpose


This document defines the requirements and implementation boundaries for Battery
Analysis, persistent physical-pack identity, and future longitudinal physical-pack
history in ArduPilotTools (APT).

APT Battery Analysis measures the electrical behaviour of the propulsion battery
as experienced by the aircraft during real flight.

It is an evidence and longitudinal-comparison system.

It is not a battery chemistry diagnostic system, charger analysis tool, or
battery-health scoring system.

APT is the Plane research, prototyping, and real-log-validation environment.
New Battery Analysis functionality should be validated against real logs before
any consideration of migration into ArduPilot Methodic Configurator (AMC).

The bounded load-event implementation is complete in APT and committed as
`4e83b46` (`feat(battery): add bounded load-event analysis`). The implemented
scope covers embedded-PARM session configuration, AUTO Takeoff Load Events,
Sustained Load Events, common bounded-event battery evidence, and optional Pack
ID at the session/presentation boundary.

Persistent physical-pack identity is also implemented. APT can now associate
multiple source BIN logs with the same user-defined physical Pack ID, remember an
explicit decision not to track a log, rename an existing Pack ID, and correct the
Pack ID assignment of an individual source log without changing Battery Analysis
calculations.

Persistent physical-pack identity is intentionally narrower than longitudinal
Pack History. APT currently persists identity and source-log association only.
It does not yet persist Battery Analysis observations, event results, trends, or
health conclusions.

Manual takeoff detection and longitudinal physical-pack evidence history remain
deferred.

## 2. Core Design Principle

APT analyses the battery pack as a complete electrical source connected to the
aircraft.

The aircraft log provides the battery evidence and relevant battery-monitor
configuration.

The user provides only an optional physical Pack ID.

Therefore:

    User input:
        Pack ID, optional

    Flight log:
        voltage
        current
        consumed capacity
        consumed energy where available
        battery-monitor configuration
        configured capacity where available
        LOW voltage threshold where available
        CRITICAL voltage threshold where available
        throttle and flight context

APT must not require the user to describe the battery's chemistry, cells, or
construction in order to perform Battery Analysis.


## 3. Design Principles

Battery Analysis follows these principles:

1. Preserve evidence available in the flight log.
2. Evaluate the complete battery pack as experienced by the aircraft.
3. Keep measured values distinct from derived values.
4. Do not guess unavailable evidence.
5. Use logged aircraft configuration where configuration is required.
6. Require no battery metadata from the user other than optional Pack ID.
7. Do not perform cell-level evaluation.
8. Do not calculate inferred internal resistance.
9. Do not assign battery health scores.
10. Do not make battery replacement recommendations.
11. Keep per-log analysis separate from longitudinal physical-pack history.
12. Preserve provenance back to the source log.
13. Use configurable detector thresholds where appropriate.
14. Validate detector behaviour against varied real-world logs.
15. Add complexity only when real evidence demonstrates that it is required.


## 4. Existing Battery Analysis

APT already contains chemistry-neutral Battery Analysis based on flight-log
telemetry.

Existing evidence includes:

- flight-scoped pack voltage;
- flight-scoped current;
- average current;
- consumed capacity where available;
- consumed energy where available;
- highest-current evidence;
- voltage sag;
- five-second voltage recovery where measurable.

New functionality extends this existing evidence model rather than replacing it.

The legacy single-sample `BatteryLoadEvent` remains unchanged. New bounded load
events use their own explicit event-boundary semantics and must not inherit the
legacy peak-row sag baseline, peak-time recovery anchor, or `sag_per_ampere`
semantics.


## 5. Pack Identification


Physical battery identity is optional user-supplied metadata.

The only battery information APT should request from the user is:

    Pack ID

Examples:

    Pack 1
    Pack 2
    LiPo-A

Pack ID identifies a physical battery so observations from different source logs
can be associated with that same physical pack.

Pack ID:

- is optional;
- must not be inferred from telemetry;
- need not be numeric;
- applies to the battery installation represented by the complete source BIN;
- must not be required for ordinary per-log Battery Analysis;
- remains metadata only and must not affect Battery Analysis calculations.

The implemented ownership invariant is:

    one FC boot / one BIN log = one physical battery installation

A BIN may contain multiple `FlightWindow`s. All flights within that BIN inherit
the same physical Pack ID because Pack ID applies to the battery installation for
the complete FC boot/log session rather than to an individual flight.

Persistent Pack ID state is stored locally in:

    Data/battery_packs.json

`Data/` is local application state and is ignored by Git.

Source-log identity is based on SHA-256 of the BIN file contents rather than the
filename or path. Therefore:

- moving or renaming an otherwise identical BIN preserves its Pack ID association;
- a different BIN with the same filename does not inherit another log's Pack ID.

For a previously unseen source log, the user may:

    - associate the log with an existing physical Pack ID;
    - create a new physical Pack ID;
    - continue without Pack ID tracking.

Choosing to continue without Pack ID tracking does not create a synthetic,
"unknown", or placeholder physical pack.

The choice is remembered for that source-log fingerprint so repeated analysis
does not repeatedly prompt for Pack ID.

Persistent log association therefore has three conceptual states:

    unseen       — no Pack ID decision has yet been made;
    tracked      — associated with a physical Pack ID;
    not tracked  — the user explicitly chose not to track this log.

Known Pack IDs are retained in creation order. A Pack ID may be renamed through
Battery Pack Management. Renaming updates the Pack ID registry and every tracked
source-log association that refers to that physical pack in one atomic store
operation.

A rename to the existing normalized Pack ID is a no-op. Renaming to another
already-existing Pack ID is rejected rather than silently merging physical packs.

The current management surface supports:

- Pack ID rename;
- reassignment of one selected source BIN to an existing Pack ID;
- creation of a new Pack ID while reassigning the selected source BIN.

A reassignment changes only source-log ownership metadata. It does not modify the
BIN, historical battery configuration, or Battery Analysis calculations.

More extensive management operations should be added only when demonstrated user
need justifies them.

## 6. Battery Configuration

Battery configuration required by analysis should come from the flight log
where available.

APT should not ask the user to provide:

- battery chemistry;
- cell type;
- cell manufacturer or model;
- series/parallel configuration;
- cell count;
- nominal capacity.

Where a relevant ArduPilot battery-monitor parameter exists in embedded `PARM`
records, that logged configuration is the preferred evidence source.

For the implemented primary battery-monitor instance, the validated parameters
are:

- `BATT_CAPACITY` — configured capacity in mAh;
- `BATT_LOW_VOLT` — configured LOW voltage threshold in V;
- `BATT_CRT_VOLT` — configured CRITICAL voltage threshold in V;
- `BATT_FS_VOLTSRC` — failsafe voltage-source selection.

These names and semantics were established from the supported firmware/log
evidence rather than assumed. The current implementation does not generalize
primary `BATT_*` configuration onto non-zero BAT monitor instances; unsupported
non-zero instances leave the associated configuration and margins unavailable.

If required configuration is unavailable, the corresponding analysis should be
reported as unavailable rather than reconstructed from user memory or inferred
from pack voltage.


## 7. Whole-Pack Analysis Boundary

APT evaluates whole-pack electrical performance.

Relevant evidence includes:

- pack voltage;
- current;
- consumed capacity;
- consumed energy;
- voltage under load;
- voltage sag;
- voltage recovery;
- configured battery capacity where available;
- margin to configured aircraft voltage thresholds.

This provides direct evidence of how the battery performed in the aircraft.


## 8. Cell-Level Analysis Is Out of Scope

APT will not perform individual-cell evaluation.

It will not attempt to determine or diagnose:

- individual-cell voltage;
- cell imbalance;
- weak individual cells;
- cell degradation;
- cell internal resistance.

APT should not derive per-cell voltage by dividing pack voltage by an assumed or
configured cell count for battery-condition analysis.

If whole-pack flight evidence suggests that a physical pack warrants further
investigation, cell-level analysis belongs with appropriate charger or bench
equipment.


## 9. Internal Resistance Is Out of Scope

APT will not calculate or report inferred cell or whole-pack internal
resistance.

Flight-log voltage and current measurements are useful directly.

Converting them into inferred resistance introduces assumptions involving:

- voltage baseline;
- load transition timing;
- telemetry sample timing;
- wiring;
- connectors;
- battery dynamics.

Those assumptions are unnecessary for the intended whole-pack longitudinal
analysis.

Voltage, current, sag and recovery should be retained directly instead.

ArduPilot `BAT` messages may also contain derived fields such as `Res` and `SH`.
These are explicitly outside the current APT Battery Analysis evidence model:
they are not consumed, exposed, persisted, interpreted, or used to derive
resistance or state-of-health results.


## 10. Configured Battery Capacity

Where available, APT obtains configured battery capacity from `BATT_CAPACITY`
recorded in embedded BIN `PARM` evidence.

For the implemented primary monitor this value is in mAh and is resolved as
session-level configuration from `ParameterHistory`. Battery-instance and
temporal semantics were verified during implementation audit.

Configured capacity should normally be treated as session-level aircraft
configuration.

It may provide context for consumed-capacity evidence where appropriate.

APT must not:

- ask the user to enter nominal capacity merely because it is useful;
- infer capacity from flight duration or consumed energy;
- treat configured capacity as independently measured usable capacity;
- use configured capacity to create a battery-health score.

Configured capacity and measured consumed capacity are different evidence and
must remain distinguishable.


## 11. Configured Voltage Thresholds

Where available, Battery Analysis obtains the aircraft's configured LOW and
CRITICAL battery-voltage thresholds from embedded log parameter evidence using
`BATT_LOW_VOLT` and `BATT_CRT_VOLT`.

APT does not define its own battery LOW or CRITICAL thresholds. Voltage margins
are presented only when `BATT_FS_VOLTSRC == 0`, where comparing raw `BAT.Volt`
against the configured voltage thresholds is semantically supported by the
validated logs. Unsupported voltage-source selections leave margins unavailable.
A zero configured threshold is retained as disabled rather than treated as an
active 0 V threshold.

These values should normally be treated as session-level configuration and
displayed once in the Battery Analysis header.

For example:

    Battery Analysis
    Pack ID          : Pack 1
    Capacity         : 5000 mAh
    Low voltage      : 13.20 V
    Critical voltage : 12.80 V

Only fields supported by the log should be displayed.

If Pack ID was not supplied:

    Battery Analysis
    Capacity         : 5000 mAh
    Low voltage      : 13.20 V
    Critical voltage : 12.80 V

Individual flights and load events should not repeatedly display the configured
threshold values.

Instead, they should report their voltage margin to those thresholds.

For example:

    Minimum voltage : 13.77 V
    Margin to Low   : +0.57 V
    Margin to Crit  : +0.97 V

A threshold crossing naturally produces a negative margin:

    Minimum voltage : 13.05 V
    Margin to Low   : -0.15 V
    Margin to Crit  : +0.25 V

This is measured/derived operational evidence.

It is not an APT judgement about battery condition.


## 12. Session-Level Parameter Semantics

The implemented session configuration covers:

- `BATT_CAPACITY`;
- `BATT_LOW_VOLT`;
- `BATT_CRT_VOLT`;
- `BATT_FS_VOLTSRC`.

Values are resolved from embedded `ParameterHistory` at the beginning of the
first registered `FlightWindow`, with temporal provenance preserved.

This matters for logs such as `log_17.bin`, where the relevant battery
parameters first appear after log startup but before the flight session.

If a relevant parameter changes later during the analysed session, the affected
session configuration is treated as unavailable and a warning is emitted rather
than silently applying one value across inconsistent evidence.

Missing and non-finite values remain unavailable. Firmware defaults are not
substituted. Companion `.params` snapshots are not used as fallback evidence.

The current implementation treats these values as session-level configuration
rather than performing a separate lookup for every load event. If future
real-log evidence shows that mid-session changes need event-specific treatment,
that assumption can be revisited.


## 13. Load Events

Battery Analysis should identify repeatable periods of significant electrical
load.

These provide useful comparison points within a flight session and,
eventually, across the history of the same physical pack.

Two distinct event families are required:

1. Takeoff Load Events
2. Sustained Load Events

They serve different purposes and must not be collapsed into one generic
detector.


## 14. Takeoff Load Events

### 14.1 Purpose

Takeoff provides a naturally recurring propulsion load.

A Takeoff Load Event records battery behaviour during the launch period so
comparable evidence can be retained across flights and sessions.


### 14.2 Takeoff types

The design ultimately supports:

- AUTO takeoff;
- manual takeoff.

AUTO takeoff is implemented and validated.

Manual takeoff detection is deliberately deferred because the current
validation set contains no genuine manual-takeoff example. A detector must not
be invented without real-log evidence.


### 14.3 AUTO classification and FlightWindow containment

A Takeoff Load Event is an actual flight-scoped departure event, not merely a
`Triggered AUTO` message and not merely high throttle.

Real aircraft use has demonstrated false `Triggered AUTO` events both on the
ground without launch and while already airborne. Therefore the message is
classification evidence only.

The validated AUTO association requires:

- the associated `FlightWindow`;
- the initial continuous TAKEOFF-mode sequence;
- exactly one associated `MSG` beginning `Triggered AUTO` before the
  `FlightWindow` starts;
- a valid transition away from the initial TAKEOFF sequence.

A ground trigger with no resulting `FlightWindow` produces no load event.
A post-start airborne trigger, repeated ambiguous markers, and later in-flight
TAKEOFF/retrigger sequences do not create additional takeoff events.

Existing validated `FlightWindow` behaviour must not be altered to create
Battery Analysis events.


### 14.4 AUTO event bounds

All bounded Battery Load Events are flight-scoped evidence.

For AUTO takeoff:

    event start = FlightWindow.start_us

    event end   = first transition away from the associated initial TAKEOFF
                  sequence, constrained to FlightWindow.end_us

Therefore every emitted AUTO event must satisfy:

    FlightWindow.start_us <= event.start_us <= event.end_us
    event.end_us <= FlightWindow.end_us

`Triggered AUTO` commonly occurs approximately 0.18–0.38 seconds before
`FlightWindow.start_us` in the current validation logs. That timing is retained
as classification evidence but does not move the battery event outside the
FlightWindow.


### 14.5 No minimum-duration rule

Takeoff Load Events do not use the Sustained Load Event minimum-duration rule.

A powered hand launch may produce a useful battery load for only a few seconds.
Such an event is retained even when shorter than eight seconds.


## 15. Sustained Load Events

### 15.1 Purpose

A Sustained Load Event identifies an extended high-throttle operating period
during flight.

It provides a load opportunity independent of takeoff.

Throttle describes the operating condition.

BAT current and voltage describe the electrical load and battery response
actually experienced by the pack.

APT must not assume that a given throttle percentage corresponds to a fixed
current.


### 15.2 Implemented detector

The implemented rule is:

    CTUN.ThO >= 90
    continuously for >= 8_000_000 us

Configuration is held in `Config/battery.yaml`:

    battery_analysis:
      sustained_load:
        throttle_min_pct: 90
        min_duration_s: 8.0

Semantics are exact:

- inclusive `>= 90`;
- duration measured from raw `TimeUS`;
- a below-threshold or non-finite `CTUN.ThO` sample terminates the run;
- no duration rounding;
- no hysteresis;
- no allowed gaps;
- no event merging;
- no smoothing.

Detection is performed within each `FlightWindow`, so an event cannot begin
before a flight, continue after a flight, bridge two flights, or incorporate
ground activity between flights.

The real `log_0.bin` contains a high-throttle run lasting `7.999973 s`; it is
correctly excluded by the exact eight-second boundary.

The 90% / 8 s rule remains a detector setting rather than a battery-condition
threshold and should be changed only if future real-log evidence justifies it.


## 16. Common Load-Event Evidence

Where supported by the source log, each load event should preserve the following
evidence.


### 16.1 Identity and context

- Pack ID, if supplied;
- source log;
- event type;
- event start time;
- event end time;
- event duration;
- relevant flight/mode context.


### 16.2 Battery state at event start

- consumed capacity at event start;
- pre-load pack voltage.


### 16.3 Throttle

- maximum throttle;
- average throttle.


### 16.4 Current

- peak current;
- average current;
- current at minimum pack voltage.

Peak current must be retained. Average current must not replace it.


### 16.5 Voltage

- minimum pack voltage;
- voltage sag from the defined pre-load baseline;
- margin to configured LOW threshold where available;
- margin to configured CRITICAL threshold where available.


### 16.6 Recovery

Where measurable:

- pack voltage after the defined recovery interval;
- voltage recovered relative to event minimum.

For bounded load events, five-second recovery is defined from the event end:
the first finite same-instance `BAT.Volt` sample at or after
`event.end_us + 5_000_000 us`, constrained to the associated `FlightWindow`.

All reported quantities must include explicit units.


## 17. Pre-Load Voltage and Sag

For bounded load events, pre-load voltage is:

    last finite same-instance BAT.Volt strictly before event.start_us

For an AUTO Takeoff Load Event, this baseline may lie immediately before
`FlightWindow.start_us`. That does not violate flight containment because the
baseline is supporting evidence, not part of the bounded event itself.

Voltage sag is:

    pre-load voltage - minimum event voltage

No interpolation, smoothing, or complex baseline estimation is used.


## 18. Current at Minimum Voltage

Battery Analysis should report both:

- peak current during the event;
- current associated with the minimum pack voltage.

These are not necessarily the same observation.

The validated `BAT` message contains voltage and current in the same timestamped
row. Current at minimum voltage is therefore taken from the exact same `BAT`
row selected for the minimum finite `BAT.Volt`.

APT does not interpolate current to the minimum-voltage timestamp.


## 19. Consumed Capacity

Where available, consumed capacity is preserved at the beginning of each load
event.

For bounded events:

    consumed at start =
        last valid same-instance BAT.CurrTot at or before event.start_us

The validation logs demonstrate that `CurrTot` can remain continuous across
multiple `FlightWindow`s in one BIN/session. It is therefore treated as
battery-session evidence rather than reset at every flight.

If a prior reset is observed such that the event-start value cannot be used
defensibly, consumed capacity at start is reported as unavailable rather than
reconstructed.


## 20. Flight and Session Evidence

Load-event analysis supplements rather than replaces whole-flight Battery
Analysis.

Battery Analysis should continue to preserve broader evidence such as:

- consumed capacity;
- consumed energy;
- average current;
- peak current;
- minimum pack voltage.

Where LOW and CRITICAL thresholds are available, flight/session evidence may
also report minimum voltage margin to those thresholds.

This prevents significant battery behaviour outside detected load events from
being hidden by event-focused reporting.


## 21. Measured and Derived Evidence

APT must distinguish directly logged evidence from derived evidence.

Examples of measured/logged evidence include:

- pack voltage;
- current;
- consumed capacity;
- throttle;
- logged battery configuration parameters.

Examples of derived evidence include:

- event duration;
- average current over an event;
- voltage sag;
- voltage recovery;
- margin to configured voltage threshold.

Derived evidence must have clear and reproducible definitions.

Unavailable evidence remains unavailable.


## 22. Battery-Monitor Instances

The initial target is one aircraft with one primary propulsion battery.

ArduPilot may log multiple battery-monitor instances, so Battery Analysis
preserves and filters BAT instance identity rather than combining instances.

The validated logs currently use `BAT Inst=0`. Session configuration from the
primary `BATT_*` parameter set is therefore applied only to the primary
instance. A selected non-zero BAT instance does not silently receive instance-0
capacity, thresholds, voltage-source semantics, or margins.

Generalized `BATT2_*`, `BATT3_*`, and wider multi-monitor mapping remains
outside the current implementation until real evidence requires it.


## 23. Parameter Evidence

Battery configuration required by Battery Analysis should be obtained from
embedded BIN parameter evidence where available.

APT's timestamped `ParameterHistory` should be used where temporal parameter
semantics matter.

Session-level battery configuration does not require repeated event-time lookup
when the design explicitly treats the parameter as constant for the session.

Companion `.params` snapshots must not be introduced as event-time fallback
evidence.

`Config/landing.yaml` parameter filters must not be expanded merely to expose
battery parameters.

The implemented required parameters are `BATT_CAPACITY`, `BATT_LOW_VOLT`,
`BATT_CRT_VOLT`, and `BATT_FS_VOLTSRC`.

`Config/landing.yaml` remains unchanged; battery-specific BIN message
requirements and detector settings live in `Config/battery.yaml`.


## 24. Longitudinal Physical-Pack History


Persistent physical-pack identity is implemented as a separate layer from
per-log Battery Analysis.

The implemented identity relationship is:

    Pack ID
       |
       +-- source BIN fingerprint A
       |
       +-- source BIN fingerprint B
       |
       +-- source BIN fingerprint C

This layer answers only which physical battery was installed for each source log.

It does not persist flight-analysis results.

Future longitudinal history will be built from validated per-log Battery Analysis
evidence associated through this identity layer.

Conceptually:

    Pack ID
       |
       +-- Session / Log A
       |      +-- Flight evidence
       |      +-- Takeoff Load Event
       |      +-- Sustained Load Event
       |
       +-- Session / Log B
       |      +-- Flight evidence
       |      +-- Takeoff Load Event
       |      +-- Sustained Load Event
       |
       +-- Session / Log C
              +-- ...

Pack ID provides the durable association between sessions.

APT does not require a persistent chemistry/cell specification for the physical
pack.

Relevant aircraft battery configuration remains provenance from each source
session/log. A Pack ID must not overwrite, normalize, or reinterpret historical
logged configuration such as `BATT_CAPACITY`, `BATT_LOW_VOLT`, or
`BATT_CRT_VOLT`.

## 25. Longitudinal Comparison

Longitudinal comparison should expose how the same physical pack behaved during
comparable real-flight conditions over time.

Useful comparison dimensions may include:

- event type;
- consumed capacity at event start;
- peak current;
- average current;
- current at minimum voltage;
- pre-load voltage;
- minimum loaded voltage;
- voltage sag;
- voltage recovery;
- margin to configured aircraft thresholds.

Comparisons should preserve the actual measurements rather than normalize them
into a battery-health score.

For example, the history may allow the user to observe that repeated takeoffs at
similar consumed capacity and current show increasing voltage sag over time.

APT presents that evidence.

It does not decide why it occurred.


## 26. Provenance


Every longitudinal observation must remain traceable to its source evidence.

The implemented physical-pack identity store deliberately persists only:

- schema version;
- known Pack IDs;
- source-log SHA-256 fingerprints;
- tracked / not-tracked association state;
- Pack ID for tracked source logs.

It does not persist Battery Analysis measurements or derived results.

The current store is:

    Data/battery_packs.json

The persistence schema is versioned. Writes are performed through a temporary
file in the destination directory followed by atomic replacement. In-memory state
is updated only after the replacement succeeds.

Future longitudinal evidence records should preserve enough provenance to
identify:

- Pack ID;
- source BIN/log;
- session/log date and time where available;
- flight;
- event;
- relevant logged battery configuration;
- measured and derived evidence.

The persistence format for future analytical/history observations remains a
separate design decision. It must not be conflated with the already-implemented
Pack ID association store.

## 27. Explicit Non-Goals

The following are outside the scope of APT Battery Analysis:

- requiring battery chemistry from the user;
- requiring cell model from the user;
- requiring cell count from the user;
- requiring series/parallel configuration from the user;
- requiring nominal capacity from the user when it exists in log configuration;
- individual-cell analysis;
- inferred per-cell voltage as a battery-condition metric;
- cell imbalance analysis;
- weak-cell identification;
- cell internal resistance;
- inferred whole-pack internal resistance;
- using or exposing `BAT.Res` as Battery Analysis evidence;
- using or exposing `BAT.SH` as Battery Analysis evidence;
- battery-health percentages;
- battery-health scores;
- automatic good/bad battery classification;
- automatic replacement recommendations;
- charger-style capacity testing;
- charge-cycle management;
- cell balancing analysis;
- inferring physical Pack ID from telemetry.

Cell-level investigation belongs with charger or bench equipment.


## 28. Validation Logs

Initial implementation and detector development should use real ArduPlane logs.

The primary Battery Analysis validation log is:

    Logs/log_0.bin

The physical battery used in this log is identified as:

    Pack ID : 50S-P1

No other battery construction metadata should be assumed from user input.

Relevant battery configuration should be independently obtained from the BIN
where available.

Additional repository regression/evidence logs include:

    Logs/log_11.bin
    Logs/log_17.bin
    Logs/log_19.bin
    Logs/log_26.bin

Validated bounded-event counts are:

| Log | AUTO | Sustained |
| --- | ---: | ---: |
| `log_0.bin` | 3 | 0 |
| `log_11.bin` | 1 | 1 |
| `log_17.bin` | 4 | 2 |
| `log_19.bin` | 1 | 0 |
| `log_26.bin` | 4 | 3 |

For `log_0.bin`, embedded session configuration resolves to:

    BATT_CAPACITY   = 5000 mAh
    BATT_LOW_VOLT   = 13.20 V
    BATT_CRT_VOLT   = 12.80 V
    BATT_FS_VOLTSRC = 0

`log_0.bin` intentionally validates without a companion `.params` file.

Additional varied Plane logs should be incorporated as they become available.

Detector behaviour must not be tuned solely to log_0 or to one aircraft.


## 29. Validation Status and Requirements


The bounded-event implementation has established and regression-tested:

- BAT fields and units required by the feature;
- primary BAT instance handling;
- `CTUN.ThO` as the sustained-load throttle source;
- `BATT_CAPACITY`, `BATT_LOW_VOLT`, `BATT_CRT_VOLT`, and
  `BATT_FS_VOLTSRC` session semantics;
- consumed-capacity continuity across multiple flights in one BIN;
- AUTO takeoff classification evidence;
- FlightWindow-contained AUTO event boundaries;
- Sustained Load Event behaviour;
- pre-load voltage semantics;
- minimum pack voltage;
- peak current;
- average current;
- current at minimum voltage from the same BAT row;
- voltage sag;
- event-end-plus-five-second recovery constrained to the flight;
- voltage-margin calculations;
- missing-evidence behaviour;
- exact 90% throttle boundary;
- exact eight-second duration boundary;
- rejection of the real `7.999973 s` near-miss;
- non-zero BAT instance safety;
- Pack ID calculation independence.

Persistent physical-pack identity has additionally established and tested:

- SHA-256 content identity for source BIN logs;
- persistence across repeated analysis;
- preservation of association after moving or renaming an identical BIN;
- rejection of filename-only identity;
- explicit `unseen`, `tracked`, and `not tracked` states;
- creation and reuse of physical Pack IDs;
- multiple source BINs associated with one physical pack;
- distinct physical packs retained separately;
- no silent carry-over of an interactive Pack ID to another source log;
- malformed persistent data reported without being overwritten;
- failed writes leaving durable and in-memory state unchanged;
- atomic Pack ID rename;
- rename propagation to all matching source-log associations;
- rejection of rename onto another existing Pack ID;
- same-name rename as a no-op;
- individual source-log reassignment to an existing Pack ID;
- creation of a new Pack ID during source-log reassignment;
- failed reassignment leaving durable and in-memory ownership unchanged;
- constructor-supplied Pack ID compatibility.

Real-log validation established three distinct physical battery identities:

- `log_11.bin` was assigned to `LIPO-2600-01`, representing the earlier
  two-battery 2600 mAh installation;
- `log_17.bin`, `log_19.bin`, and `log_26.bin` were assigned to
  `LIPO-3900-01`, representing the later three-battery 3900 mAh installation;
- the separate Samsung 50S pack was assigned to `50S-P1`.

The real `505-P1` entry error was corrected through the implemented rename
workflow to `50S-P1`. The existing source-log association followed the rename,
unrelated associations remained unchanged, and repeated Battery Analysis resolved
the corrected Pack ID without prompting.

Real use then exposed an incorrect earlier association of `log_11.bin` with
`LIPO-3900-01`. The implemented source-log reassignment workflow was used to
create `LIPO-2600-01` and move only that BIN fingerprint to the correct physical
battery identity. The later 3900 mAh LiPo logs and `50S-P1` association remained
unchanged.

This also demonstrated why physical Pack ID must remain separate from logged
aircraft configuration. `log_11.bin` records `BATT_CAPACITY = 2600 mAh`, while
the later LiPo sessions record `3900 mAh`. APT preserves the configuration
actually recorded in each BIN rather than deriving it from Pack ID metadata.

Regression validation covers `log_0`, `log_11`, `log_17`, `log_19`, and
`log_26`, while existing Battery, FlightWindow, ParameterHistory, Rangefinder,
Landing, and Event Timeline regressions remain passing.

Manual takeoff evidence remains unresolved and is explicitly deferred until a
real manual-takeoff log is available.

## 30. Resolved Implementation Decisions and Remaining Questions


The implementation has resolved the following design questions:

1. Existing `BatteryProcessor` / `BatteryAnalysis` structures are extended rather
   than replaced.
2. Bounded events use common battery-evidence evaluation while preserving the
   legacy single-sample `BatteryLoadEvent`.
3. `BAT` supplies `Volt`, `Curr`, `CurrTot`, and related whole-pack evidence.
4. `CTUN.ThO` supplies sustained-load throttle evidence.
5. Embedded `ParameterHistory` supplies session battery configuration.
6. AUTO classification uses the initial TAKEOFF sequence plus unique associated
   `Triggered AUTO` evidence.
7. `FlightWindow` is the hard temporal boundary for all bounded load events.
8. AUTO event start is `FlightWindow.start_us`; the pre-window trigger is not
   part of the bounded battery event.
9. Pre-load voltage is the last finite same-instance BAT voltage strictly before
   the event.
10. Recovery is anchored at event end + 5 seconds and constrained to the flight.
11. Voltage and current at minimum voltage come from the same BAT row.
12. Pack ID enters at the Battery Analysis session/presentation boundary and has
    no effect on calculations.
13. Battery-specific detector configuration lives in `Config/battery.yaml`.
14. One FC boot / one BIN log represents one physical battery installation for
    Pack ID purposes.
15. Source-log Pack ID ownership uses SHA-256 BIN-content identity rather than
    filename or path.
16. Local physical-pack identity is persisted in
    `Data/battery_packs.json`.
17. Explicit `not tracked` state is persisted without creating a placeholder
    physical pack.
18. Physical Pack ID persistence is separate from analytical-result persistence.
19. Pack IDs can be renamed atomically without altering per-log Battery Analysis
    evidence.
20. A selected source BIN can be reassigned to another existing or newly created
    Pack ID without altering analytical evidence.
21. Historical logged configuration remains provenance of each source BIN and is
    not replaced by physical-pack metadata.

Remaining questions are intentionally narrower:

- What real-log evidence should define manual takeoff?
- When sufficient repeated-pack evidence exists, what longitudinal observation
  schema and comparison presentation best fit APT?
- Do future non-primary battery-monitor logs justify generalized `BATT2_*` /
  `BATT3_*` configuration mapping?
- Does future real-log evidence justify any refinement of the 90% / 8 s
  sustained-load detector?
- Does future demonstrated user need justify additional Pack ID management
  operations beyond rename and individual source-log reassignment?

## 31. Implementation Sequence


Completed:

    requirements
        |
        v
    read-only architecture and real-log evidence audit
        |
        v
    narrow per-log bounded load-event implementation
        |
        v
    log_0 validation
        |
        v
    five-log regression validation
        |
        v
    optional Pack ID integration
        |
        v
    APT persistence architecture audit
        |
        v
    persistent physical Pack ID + source-log association
        |
        v
    automated persistence hardening
        |
        v
    real-log repeated-pack validation
        |
        v
    Pack ID management / atomic rename
        |
        v
    rename hardening and real-user acceptance validation
        |
        v
    source-log Pack ID reassignment
        |
        v
    reassignment hardening and real-log correction

The bounded load-event implementation is committed as:

    4e83b46  feat(battery): add bounded load-event analysis

Persistent physical-pack identity and management are committed as:

    df825e8  feat(battery): persist physical pack identity
    917df75  test(battery): harden pack identity persistence
    f645550  feat(battery): manage physical pack identity
    6563017  test(battery): harden pack identity management
    54d0c54  feat(battery): support log pack reassignment
    b74323f  test(battery): harden log pack reassignment

The current deferred paths are separate.

Manual takeoff:

    acquire genuine manual-takeoff evidence
        |
        v
    design/validate manual takeoff detector

Longitudinal physical-pack evidence:

    accumulate repeated sessions for identified physical packs
        |
        v
    define longitudinal observation/provenance schema
        |
        v
    implement evidence persistence or reproducible aggregation
        |
        v
    longitudinal comparison presentation

Persistent physical Pack ID is no longer deferred. It is implemented and remains
a metadata layer separate from per-log Battery Analysis calculations.

What remains deferred is persistence and presentation of longitudinal analytical
observations across those identified physical packs.

New complexity should continue to be introduced only when real-log evidence
demonstrates that the simpler design is insufficient.
