from core.events import TimelineEvent, EventType
from core.model import FlightLog
from core.scope import filter_telemetry


class EventExtractor:
    """
    Extract timeline events contained within a supplied time window.

    The window may be a FlightWindow or any child analysis window
    exposing start_us and end_us.

    Individual event sources are extracted independently then merged
    into a single chronological timeline.
    """

    def extract(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:
        """
        Extract all timeline events contained within the supplied window.

        Individual event sources are merged into a single chronological
        timeline.
        """

        if window is None:
            raise ValueError("window is required")

        if window.start_us > window.end_us:
            raise ValueError(
                "window start_us must not be after end_us"
            )

        events = []

        #
        # Firmware messages.
        #

        events.extend(
            self._extract_msg_events(
                flight_log,
                window,
            )
        )

        #
        # Landing controller state.
        #

        events.extend(
            self._extract_land_stage_events(
                flight_log,
                window,
            )
        )

        #
        # Future event sources.
        #

        # events.extend(
        #     self._extract_mode_events(
        #         flight_log,
        #         window,
        #     )
        # )

        # events.extend(
        #     self._extract_rangefinder_events(
        #         flight_log,
        #         window,
        #     )
        # )

        events.sort()

        return events

    def _extract_msg_events(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:
        """
        Extract firmware MSG events.
        """

        msg = filter_telemetry(
            flight_log.get("MSG"),
            window,
        )

        if msg is None or msg.empty:
            return []

        return [
            TimelineEvent(
                time_us=int(row["TimeUS"]),
                event=EventType.MSG,
                detail=row["Message"],
            )
            for _, row in msg.iterrows()
        ]

    def _extract_land_stage_events(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:
        """
        Extract LAND stage transitions.

        LAND telemetry is logged continuously. Only changes in the
        controller stage are emitted as timeline events.

        Diagnostic fields (currently fh and slope) are included to
        aid investigation of the landing controller.
        """

        land = filter_telemetry(
            flight_log.get("LAND"),
            window,
        )

        if land is None or land.empty:
            return []

        changes = land[
            land["stage"] != land["stage"].shift()
        ]

        return [
            TimelineEvent(
                time_us=int(row["TimeUS"]),
                event=EventType.LAND_STAGE,
                detail=(
                    f"{int(row['stage'])} "
                    f"(fh={row['fh']:.2f}, "
                    f"slope={row['slope']:.3f})"
                ),
            )
            for _, row in changes.iterrows()
        ]

    def _extract_mode_events(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:
        """
        Extract MODE change events.

        Placeholder for v0.4.
        """

        return []

    def _extract_rangefinder_events(
        self,
        flight_log: FlightLog,
        window,
    ) -> list[TimelineEvent]:
        """
        Extract derived rangefinder events.

        Placeholder for v0.4.
        """

        return []