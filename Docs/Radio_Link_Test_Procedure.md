⚠️ PROP OFF FOR BENCH TESTING.
Remove the propeller before performing the transmitter-off bench test. Do not rely on failsafe behaviour to make the propulsion system safe.

# Controlled Radio Link Test Procedure

This procedure defines a repeatable method for collecting ArduPlane
DataFlash BIN evidence and, optionally, EdgeTX telemetry CSV evidence
for APT Radio Link analysis.

## Preparation

1.  Make the aircraft safe for a deliberate RC-link-loss test. For a
    bench test, **remove the propeller or otherwise make propulsion
    physically safe**.
2.  Ensure aircraft DataFlash logging is enabled for the test.
3.  If collecting EdgeTX telemetry, enable CSV telemetry logging and set
    the **EdgeTX date and time reasonably correctly**. Exact clock
    synchronization with the flight controller is not required.
4.  For a controlled ELRS walk test, select and record:
    -   fixed transmitter power;
    -   packet rate;
    -   dynamic power state.
5.  Record the relevant ArduPlane failsafe configuration, particularly
    `RC_FS_TIMEOUT` and `FS_LONG_TIMEOUT`. These should not be changed
    merely to suit the analyser.
6.  The deliberate link-loss period must comfortably exceed the
    configured time required to reach long failsafe. **Use at least 5
    seconds of additional margin** beyond the applicable configured
    failsafe timing.

## Bench Transmitter-Off Test

1.  **Power-cycle the transmitter.**
2.  **Power-cycle the aircraft.**
3.  Allow the aircraft to boot fully and establish a fresh RC link.
4.  Arm the aircraft.
5.  Turn the transmitter completely off.
6.  Keep it off for the configured failsafe period **plus at least 5
    seconds margin**, so that both short and long failsafe behaviour can
    be observed.
7.  Turn the transmitter back on.
8.  Allow the RC link to recover.
9.  Select the desired flight mode if required after recovery.
10. Disarm the aircraft.
11. Power down the aircraft.
12. Retain the resulting aircraft BIN as the log for **this test only**,
    together with its EdgeTX CSV if recorded.

## Walk / Link-Loss Test

1.  Position and safely secure the aircraft at the test location.
2.  **Power-cycle the transmitter.**
3.  **Power-cycle the aircraft.**
4.  Allow the aircraft to boot fully and establish a fresh RC link.
5.  Verify the intended fixed ELRS power, packet rate and dynamic-power
    setting.
6.  Arm the aircraft when safe to do so.
7.  Walk away with the transmitter until the RC link is clearly lost.
8.  Continue far enough beyond the marginal-link region to avoid
    deliberately hovering at the threshold.
9.  Remain beyond usable link for the configured failsafe period **plus
    at least 5 seconds margin** if testing long-failsafe behaviour.
10. Walk back toward the aircraft and allow the RC link to recover.
11. Select the desired flight mode if required after recovery.
12. Disarm the aircraft.
13. Power down the aircraft.
14. Retain the resulting aircraft BIN as the log for **this test only**,
    together with its EdgeTX CSV if recorded.

## Evidence and Interpretation

Each power-cycle/test sequence is treated as a separate controlled
session.

The aircraft BIN is authoritative for **what ArduPlane detected and
did**. EdgeTX CSV evidence, when available, describes transmitter-side
RF/telemetry behaviour and is correlated with --- but does not redefine
--- the aircraft's failsafe episodes.

`RXLQ` alone must not be interpreted as proof that the RC link was alive
because a logged value may remain stale during loss.

Commanded throttle/PWM evidence does **not** prove physical motor
operation.

The walk test does not establish RF range in metres unless
transmitter-to-aircraft distance is independently measured.

## Analysis Note

Future parameter-aware analysis may read `RC_FS_TIMEOUT`,
`FS_LONG_TIMEOUT`, and other applicable parameters from the BIN and
compare configured failsafe behaviour with observed transitions.

The exact timer semantics should be established from the applicable
ArduPlane source before defining expected transition timing
mathematically. The test procedure therefore deliberately does not
assume a specific formula relating these parameters.
