from core.events import TimelineEvent, EventType


class RangefinderEvents:
    """
    Detect significant rangefinder events during the landing window.

    Published events

        RFND_FIRST_NONZERO

        RFND_FIRST_IN_RANGE

        RFND_CONTINUOUS
    """

    def __init__(self, flight, window, config):

        self.flight = flight
        self.window = window
        self.config = config

    def publish(self, events, time_us, event, detail=""):

        events.append(

            TimelineEvent(

                int(time_us),

                event,

                detail,

            )

        )

    def estimate_sample_rate(self, rfnd):

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

        if not self.flight.has("RFND"):

            return events

        rfnd = self.flight.get("RFND")

        rfnd = rfnd[
            (rfnd["TimeUS"] >= self.window.start_us)
            &
            (rfnd["TimeUS"] <= self.window.end_us)
        ]

        if rfnd.empty:

            return events

        cfg = self.config.get("rangefinder", {})

        zero_threshold = cfg.get("zero_threshold", 0.05)

        continuous_seconds = cfg.get("continuous_seconds", 1.0)

        sample_rate = self.estimate_sample_rate(rfnd)

        if sample_rate is None:

            required_samples = 1

        else:

            required_samples = max(

                1,

                round(sample_rate * continuous_seconds)

            )

        max_range = None

        if self.flight.has_param("RNGFND1_MAX"):

            max_range = self.flight.param("RNGFND1_MAX")

        found_nonzero = False

        found_in_range = False

        found_continuous = False

        run_start_time = None

        run_samples = 0

        for _, row in rfnd.iterrows():

            dist = float(row["Dist"])

            time_us = int(row["TimeUS"])

            #
            # Zero reading
            #

            if dist <= zero_threshold:

                run_samples = 0

                run_start_time = None

                continue

            #
            # First non-zero sample
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
            # First sample inside configured range
            #

            if (

                not found_in_range

                and max_range is not None

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
            # Continuous valid measurements
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
