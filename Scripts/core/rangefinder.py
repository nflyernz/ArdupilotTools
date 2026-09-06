import math

from core.events import TimelineEvent, EventType
from core.flight_window import FlightWindow
from core.flight_data import FlightLog
from core.scope import (
    filter_telemetry,
    validate_child_window,
    validate_flight_window,
)


class RangefinderEvents:
    """
    Detect significant rangefinder events within a bounded child
    window of a selected FlightWindow.

    Published events

        RFND_FIRST_NONZERO

        RFND_FIRST_IN_RANGE

        RFND_CONTINUOUS

        RFND_DISENGAGED
    """

    def __init__(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
        window,
        config,
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        validate_child_window(
            flight_window,
            window,
        )

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.window = window
        self.config = config

    def publish(
        self,
        events,
        time_us,
        event,
        detail="",
    ):

        events.append(
            TimelineEvent(
                int(time_us),
                event,
                detail,
            )
        )

    def estimate_sample_rate(
        self,
        rfnd,
    ):

        if len(rfnd) < 2:
            return None

        dt = rfnd["TimeUS"].diff().dropna()

        if dt.empty:
            return None

        median_us = dt.median()

        if median_us <= 0:
            return None

        return 1e6 / median_us

    def build(self):

        events = []

        if not self.flight_log.has("RFND"):
            return events

        rfnd = filter_telemetry(
            self.flight_log.get("RFND"),
            self.window,
        )

        if rfnd is None or rfnd.empty:
            return events

        cfg = self.config.get(
            "rangefinder",
            {},
        )

        event_cfg = cfg.get(
            "events",
            {},
        )

        zero_threshold = event_cfg.get(
            "zero_threshold",
            0.05,
        )

        continuous_seconds = event_cfg.get(
            "continuous_seconds",
            1.0,
        )

        sample_rate = self.estimate_sample_rate(
            rfnd
        )

        if sample_rate is None:

            required_samples = 1

        else:

            required_samples = max(
                1,
                round(
                    sample_rate
                    * continuous_seconds
                ),
            )

        found_nonzero = False
        found_in_range = False
        found_continuous = False

        run_start_time = None
        run_samples = 0

        rangefinder_active = False

        for _, row in rfnd.iterrows():

            dist = float(row["Dist"])
            time_us = int(row["TimeUS"])

            #
            # Zero or invalid reading.
            #
            if dist <= zero_threshold:

                if rangefinder_active:

                    self.publish(
                        events,
                        time_us,
                        EventType.RFND_DISENGAGED,
                        f"{dist:.2f} m",
                    )

                    rangefinder_active = False

                run_samples = 0
                run_start_time = None

                continue

            #
            # Valid non-zero reading.
            #
            rangefinder_active = True

            #
            # First non-zero sample.
            #
            if not found_nonzero:

                found_nonzero = True

                self.publish(
                    events,
                    time_us,
                    EventType.RFND_FIRST_NONZERO,
                    f"{dist:.2f} m",
                )

            #
            # First sample inside configured maximum range.
            #
            if not found_in_range:

                max_range = (
                    self.flight_log
                    .parameter_history
                    .value_at(
                        "RNGFND1_MAX",
                        time_us,
                    )
                )

            if (
                not found_in_range
                and max_range is not None
                and math.isfinite(max_range)
                and max_range > 0
                and dist <= max_range
            ):

                found_in_range = True

                self.publish(
                    events,
                    time_us,
                    EventType.RFND_FIRST_IN_RANGE,
                    f"{dist:.2f} / {max_range:.2f} m",
                )

            #
            # Continuous valid measurements.
            #
            if run_samples == 0:

                run_start_time = time_us
                run_samples = 1

            else:

                run_samples += 1

            if (
                not found_continuous
                and run_samples >= required_samples
            ):

                found_continuous = True

                self.publish(
                    events,
                    run_start_time,
                    EventType.RFND_CONTINUOUS,
                    f"{run_samples} samples",
                )

        return events
