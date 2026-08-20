import math

from core.config import Config
from core.events import EventType
from core.event_extractor import EventExtractor
from core.landing_attempt import LandingAttempt
from core.landing_attempt_analysis import (
    LandingAttemptAnalysis,
)
from core.landing_window import LandingWindow
from core.rangefinder import RangefinderEvents
from core.scope import (
    filter_telemetry,
    validate_child_window,
    validate_flight_window,
)


class LandingAttemptProcessor:
    """
    Build measured evidence for one bounded landing attempt.

    The processor does not determine whether a landing was good,
    bad, successful, or unsuccessful.

    It collects measured and logged evidence associated with the
    attempt and returns a LandingAttemptAnalysis.
    """

    APPROACH_CONTEXT_US = 1_000_000

    #
    # Local barometric-rate window centred on preflare.
    #
    BARO_RATE_HALF_WINDOW_US = 500_000

    def __init__(
        self,
        flight_log,
        flight_window,
        landing_window: LandingWindow,
        attempt: LandingAttempt,
        config,
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        validate_child_window(
            flight_window,
            landing_window,
        )

        validate_child_window(
            landing_window,
            attempt,
        )

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.landing_window = landing_window
        self.attempt = attempt
        self.config = config

        self.landing_config = Config(
            "Config/landing.yaml"
        )

    def build(self) -> LandingAttemptAnalysis:

        duration_s = (
            self.attempt.end_us
            - self.attempt.start_us
        ) / 1_000_000

        events = EventExtractor().extract(
            self.flight_log,
            self.attempt,
        )

        #
        # Immediately preceding firmware context.
        #
        approach_start_altitude = (
            self._approach_start_altitude()
        )

        glide_slope_degrees = None

        preflare_time_us = None
        preflare_altitude = None

        flare_time_us = None
        flare_altitude = None

        preflare_sink_rate = None
        preflare_airspeed = None
        preflare_gps_speed = None

        flare_sink_rate = None
        flare_airspeed = None
        flare_gps_speed = None
        flare_distance = None

        #
        # LandingWindowDetector owns both the boundary and reason.
        #
        end_reason = self.landing_window.end_reason

        #
        # Event evidence contained inside the attempt.
        #
        for event in events:

            if (
                event.event == EventType.MSG
                and event.detail.startswith(
                    "Landing approach start at "
                )
                and approach_start_altitude is None
            ):

                approach_start_altitude = (
                    self._extract_value(
                        event.detail,
                        "Landing approach start at ",
                        "m",
                    )
                )

            elif (
                event.event == EventType.MSG
                and event.detail.startswith(
                    "Landing glide slope "
                )
                and glide_slope_degrees is None
            ):

                glide_slope_degrees = (
                    self._extract_value(
                        event.detail,
                        "Landing glide slope ",
                        " degrees",
                    )
                )

            elif (
                event.event == EventType.LAND_STAGE
                and event.detail.startswith("2 ")
                and preflare_time_us is None
            ):

                preflare_time_us = event.time_us

                preflare_altitude = (
                    self._extract_fh(
                        event.detail
                    )
                )

            elif (
                event.event == EventType.LAND_STAGE
                and event.detail.startswith("3 ")
                and flare_time_us is None
            ):

                flare_time_us = event.time_us

                flare_altitude = (
                    self._extract_fh(
                        event.detail
                    )
                )

            elif (
                event.event == EventType.MSG
                and event.detail.startswith("Flare ")
            ):

                if flare_time_us is None:

                    flare_time_us = event.time_us

                if flare_altitude is None:

                    flare_altitude = (
                        self._extract_value(
                            event.detail,
                            "Flare ",
                            "m",
                        )
                    )

                if flare_sink_rate is None:

                    flare_sink_rate = (
                        self._extract_named_value(
                            event.detail,
                            "sink=",
                        )
                    )

                if flare_airspeed is None:

                    flare_airspeed = (
                        self._extract_named_value(
                            event.detail,
                            "speed=",
                        )
                    )

                if flare_distance is None:

                    flare_distance = (
                        self._extract_named_value(
                            event.detail,
                            "dist=",
                        )
                    )

        #
        # Point-in-time preflare measurements.
        #
        if preflare_time_us is not None:

            preflare_sink_rate = (
                self._barometric_sink_rate(
                    preflare_time_us
                )
            )

            preflare_airspeed = (
                self._nearest_telemetry_value(
                    "ARSP",
                    "Airspeed",
                    preflare_time_us,
                )
            )

            preflare_gps_speed = (
                self._nearest_telemetry_value(
                    "GPS",
                    "Spd",
                    preflare_time_us,
                )
            )

        #
        # Point-in-time flare measurements.
        #
        if flare_time_us is not None:

            #
            # Prefer the airspeed explicitly logged in the firmware
            # flare message. Use raw ARSP only if it is unavailable.
            #
            if flare_airspeed is None:

                flare_airspeed = (
                    self._nearest_telemetry_value(
                        "ARSP",
                        "Airspeed",
                        flare_time_us,
                    )
                )

            flare_gps_speed = (
                self._nearest_telemetry_value(
                    "GPS",
                    "Spd",
                    flare_time_us,
                )
            )

        #
        # Rangefinder evidence.
        #
        rangefinder_events = RangefinderEvents(
            self.flight_log,
            self.flight_window,
            self.attempt,
            self.config,
        ).build()

        (
            rangefinder_first_nonzero_time_us,
            rangefinder_first_nonzero_distance,
            rangefinder_first_in_range_time_us,
            rangefinder_first_in_range_distance,
            rangefinder_continuous_time_us,
            rangefinder_continuous_samples,
            rangefinder_disengage_events,
            rangefinder_last_disengage_time_us,
            rangefinder_last_disengage_distance,
        ) = self._process_rangefinder_events(
            rangefinder_events
        )

        #
        # GPS landing / rollout completion evidence.
        #
        (
            gps_stop_time_us,
            gps_stop_speed_limit,
            gps_stop_persistence_s,
            flare_to_gps_stop_s,
        ) = self._gps_stop_evidence(
            flare_time_us
        )

        #
        # Final position relative to the intended LAND target.
        #
        landing_end_target_distance_m = (
            self._landing_end_target_distance(
                gps_stop_time_us
            )
        )

        return LandingAttemptAnalysis(
            attempt=self.attempt,
            duration_s=duration_s,

            approach_start_altitude=(
                approach_start_altitude
            ),
            glide_slope_degrees=(
                glide_slope_degrees
            ),

            preflare_time_us=preflare_time_us,
            preflare_altitude=preflare_altitude,

            flare_time_us=flare_time_us,
            flare_altitude=flare_altitude,

            preflare_sink_rate=preflare_sink_rate,
            preflare_airspeed=preflare_airspeed,
            preflare_gps_speed=preflare_gps_speed,

            flare_sink_rate=flare_sink_rate,
            flare_airspeed=flare_airspeed,
            flare_gps_speed=flare_gps_speed,
            flare_distance=flare_distance,

            rangefinder_first_nonzero_time_us=(
                rangefinder_first_nonzero_time_us
            ),
            rangefinder_first_nonzero_distance=(
                rangefinder_first_nonzero_distance
            ),

            rangefinder_first_in_range_time_us=(
                rangefinder_first_in_range_time_us
            ),
            rangefinder_first_in_range_distance=(
                rangefinder_first_in_range_distance
            ),

            rangefinder_continuous_time_us=(
                rangefinder_continuous_time_us
            ),
            rangefinder_continuous_samples=(
                rangefinder_continuous_samples
            ),

            rangefinder_disengage_events=(
                rangefinder_disengage_events
            ),

            rangefinder_last_disengage_time_us=(
                rangefinder_last_disengage_time_us
            ),
            rangefinder_last_disengage_distance=(
                rangefinder_last_disengage_distance
            ),

            gps_stop_time_us=gps_stop_time_us,
            gps_stop_speed_limit=(
                gps_stop_speed_limit
            ),
            gps_stop_persistence_s=(
                gps_stop_persistence_s
            ),
            flare_to_gps_stop_s=(
                flare_to_gps_stop_s
            ),
            landing_end_target_distance_m=(
                landing_end_target_distance_m
            ),

            end_reason=end_reason,
        )

    def _gps_stop_evidence(
        self,
        flare_time_us,
    ):
        """
        Return authoritative GPS-stop evidence when GPS stop was the
        LandingWindow termination.

        LandingWindowDetector has already confirmed the configured
        persistence interval. The LandingWindow end timestamp is the
        beginning of that sustained low-groundspeed run.

        GPS stop is not interpreted as touchdown.
        """

        if (
            self.landing_window.end_reason
            != "gps"
        ):
            return (
                None,
                None,
                None,
                None,
            )

        speed_limit = float(
            self.landing_config.get(
                "landing_window.end_speed",
                3.0,
            )
        )

        persistence_s = float(
            self.landing_config.get(
                "landing_window.end_speed_seconds",
                2.0,
            )
        )

        gps_stop_time_us = int(
            self.landing_window.end_us
        )

        flare_to_gps_stop_s = None

        if flare_time_us is not None:

            delta_us = (
                gps_stop_time_us
                - flare_time_us
            )

            if delta_us >= 0:

                flare_to_gps_stop_s = (
                    delta_us
                    / 1_000_000
                )

        return (
            gps_stop_time_us,
            speed_limit,
            persistence_s,
            flare_to_gps_stop_s,
        )

    def _landing_end_target_distance(
        self,
        gps_stop_time_us,
    ):
        """
        Return horizontal distance from the aircraft position at the
        authoritative GPS-stop boundary to the applicable LAND
        mission target.

        This represents final landing / rollout position relative to
        the intended LAND point. It is not touchdown accuracy.
        """

        if gps_stop_time_us is None:
            return None

        target = self._land_target()

        if target is None:
            return None

        target_lat, target_lng = target

        gps = self.flight_log.get("GPS")

        if gps is None or gps.empty:
            return None

        if not {
            "TimeUS",
            "Lat",
            "Lng",
        }.issubset(
            gps.columns
        ):
            return None

        valid = gps[
            gps["Lat"].notna()
            & gps["Lng"].notna()
        ]

        if valid.empty:
            return None

        offsets = (
            valid["TimeUS"]
            - gps_stop_time_us
        ).abs()

        index = offsets.idxmin()

        try:

            aircraft_lat = float(
                valid.loc[
                    index,
                    "Lat",
                ]
            )

            aircraft_lng = float(
                valid.loc[
                    index,
                    "Lng",
                ]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        return self._horizontal_distance(
            target_lat,
            target_lng,
            aircraft_lat,
            aircraft_lng,
        )

    def _land_target(
        self,
    ):
        """
        Return the LAND target applicable to this landing attempt.

        CMD records may contain multiple mission snapshots during a
        log. Use the latest MAV_CMD_NAV_LAND command present at or
        before the attempt start.
        """

        cmd = self.flight_log.get("CMD")

        if cmd is None or cmd.empty:
            return None

        if not {
            "TimeUS",
            "CId",
            "Lat",
            "Lng",
        }.issubset(
            cmd.columns
        ):
            return None

        land_rows = cmd[
            (cmd["CId"] == 21)
            & (
                cmd["TimeUS"]
                <= self.attempt.start_us
            )
        ]

        if land_rows.empty:
            return None

        row = land_rows.sort_values(
            "TimeUS"
        ).iloc[-1]

        try:

            lat = float(
                row["Lat"]
            )

            lng = float(
                row["Lng"]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if (
            lat == 0.0
            and lng == 0.0
        ):
            return None

        return (
            lat,
            lng,
        )

    def _horizontal_distance(
        self,
        lat1,
        lng1,
        lat2,
        lng2,
    ):
        """
        Return great-circle horizontal distance in metres.
        """

        earth_radius_m = 6_371_000.0

        lat1_rad = math.radians(
            lat1
        )

        lat2_rad = math.radians(
            lat2
        )

        delta_lat = math.radians(
            lat2 - lat1
        )

        delta_lng = math.radians(
            lng2 - lng1
        )

        a = (
            math.sin(
                delta_lat / 2.0
            ) ** 2
            + math.cos(
                lat1_rad
            )
            * math.cos(
                lat2_rad
            )
            * math.sin(
                delta_lng / 2.0
            ) ** 2
        )

        c = 2.0 * math.atan2(
            math.sqrt(a),
            math.sqrt(
                1.0 - a
            ),
        )

        return (
            earth_radius_m
            * c
        )

    def _barometric_sink_rate(
        self,
        target_time_us,
    ):
        """
        Estimate local sink rate from raw BARO altitude over a
        one-second window centred on the target time.

        Returned sink rate is positive when descending, matching
        the sign convention of ArduPlane's flare sink value.
        """

        baro = filter_telemetry(
            self.flight_log.get("BARO"),
            self.attempt,
        )

        if baro is None or baro.empty:
            return None

        if (
            "TimeUS" not in baro.columns
            or "Alt" not in baro.columns
        ):
            return None

        start_us = max(
            self.attempt.start_us,
            (
                target_time_us
                - self.BARO_RATE_HALF_WINDOW_US
            ),
        )

        end_us = min(
            self.attempt.end_us,
            (
                target_time_us
                + self.BARO_RATE_HALF_WINDOW_US
            ),
        )

        rows = baro[
            (baro["TimeUS"] >= start_us)
            & (baro["TimeUS"] <= end_us)
            & baro["Alt"].notna()
        ]

        if len(rows) < 2:
            return None

        first = rows.iloc[0]
        last = rows.iloc[-1]

        elapsed_s = (
            int(last["TimeUS"])
            - int(first["TimeUS"])
        ) / 1_000_000

        if elapsed_s <= 0:
            return None

        altitude_rate = (
            float(last["Alt"])
            - float(first["Alt"])
        ) / elapsed_s

        return -altitude_rate

    def _approach_start_altitude(
        self,
    ):
        """
        Return the latest firmware approach-start altitude emitted
        immediately before the landing attempt begins.
        """

        msg = self.flight_log.get("MSG")

        if msg is None or msg.empty:
            return None

        if (
            "TimeUS" not in msg.columns
            or "Message" not in msg.columns
        ):
            return None

        context_start = max(
            self.flight_window.start_us,
            (
                self.attempt.start_us
                - self.APPROACH_CONTEXT_US
            ),
        )

        rows = msg[
            (msg["TimeUS"] >= context_start)
            & (
                msg["TimeUS"]
                <= self.attempt.start_us
            )
        ]

        if rows.empty:
            return None

        matches = rows[
            rows["Message"].astype(str).str.startswith(
                "Landing approach start at "
            )
        ]

        if matches.empty:
            return None

        row = matches.iloc[-1]

        return self._extract_value(
            str(row["Message"]),
            "Landing approach start at ",
            "m",
        )

    def _nearest_telemetry_value(
        self,
        message_name,
        field_name,
        target_time_us,
    ):
        """
        Return the nearest scoped telemetry value to the target time.
        """

        telemetry = filter_telemetry(
            self.flight_log.get(message_name),
            self.attempt,
        )

        if telemetry is None or telemetry.empty:
            return None

        if (
            "TimeUS" not in telemetry.columns
            or field_name not in telemetry.columns
        ):
            return None

        valid = telemetry[
            telemetry[field_name].notna()
        ]

        if valid.empty:
            return None

        offsets = (
            valid["TimeUS"]
            - target_time_us
        ).abs()

        index = offsets.idxmin()

        try:

            return float(
                valid.loc[
                    index,
                    field_name,
                ]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    def _process_rangefinder_events(
        self,
        events,
    ):

        first_nonzero_time_us = None
        first_nonzero_distance = None

        first_in_range_time_us = None
        first_in_range_distance = None

        continuous_time_us = None
        continuous_samples = None

        disengage_events = 0
        last_disengage_time_us = None
        last_disengage_distance = None

        for event in events:

            if (
                event.event
                == EventType.RFND_FIRST_NONZERO
            ):

                if first_nonzero_time_us is None:

                    first_nonzero_time_us = (
                        event.time_us
                    )

                    first_nonzero_distance = (
                        self._extract_value(
                            event.detail,
                            "",
                            " m",
                        )
                    )

            elif (
                event.event
                == EventType.RFND_FIRST_IN_RANGE
            ):

                if first_in_range_time_us is None:

                    first_in_range_time_us = (
                        event.time_us
                    )

                    first_in_range_distance = (
                        self._extract_value(
                            event.detail,
                            "",
                            " /",
                        )
                    )

            elif (
                event.event
                == EventType.RFND_CONTINUOUS
            ):

                if continuous_time_us is None:

                    continuous_time_us = (
                        event.time_us
                    )

                    continuous_samples = (
                        self._extract_value(
                            event.detail,
                            "",
                            " samples",
                        )
                    )

                    if continuous_samples is not None:

                        continuous_samples = int(
                            continuous_samples
                        )

            elif (
                event.event
                == EventType.RFND_DISENGAGED
            ):

                disengage_events += 1

                last_disengage_time_us = (
                    event.time_us
                )

                last_disengage_distance = (
                    self._extract_value(
                        event.detail,
                        "",
                        " m",
                    )
                )

        return (
            first_nonzero_time_us,
            first_nonzero_distance,
            first_in_range_time_us,
            first_in_range_distance,
            continuous_time_us,
            continuous_samples,
            disengage_events,
            last_disengage_time_us,
            last_disengage_distance,
        )

    def _extract_value(
        self,
        text,
        prefix,
        suffix,
    ):

        if prefix:

            if not text.startswith(prefix):
                return None

            text = text[len(prefix):]

        if suffix:

            index = text.find(suffix)

            if index < 0:
                return None

            text = text[:index]

        try:

            return float(
                text.strip()
            )

        except ValueError:

            return None

    def _extract_named_value(
        self,
        text,
        name,
    ):

        index = text.find(name)

        if index < 0:
            return None

        value = text[
            index + len(name):
        ].split()[0]

        try:

            return float(value)

        except ValueError:

            return None

    def _extract_fh(
        self,
        detail,
    ):

        marker = "fh="

        index = detail.find(marker)

        if index < 0:
            return None

        value = detail[
            index + len(marker):
        ]

        value = value.split(",")[0]

        try:

            return float(value)

        except ValueError:

            return None