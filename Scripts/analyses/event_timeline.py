from pathlib import Path

from core.event_extractor import EventExtractor
from core.log_reader import (
    FlightReader,
    UnsupportedFirmwareError,
)
from core.time import format_time


class EventTimelineAnalysis:
    """
    Present a chronological event timeline for a selected flight.
    """

    def run(self):

        log_path = self._select_log()

        if log_path is None:
            return

        try:
            flight_log = FlightReader(
                str(log_path)
            ).read()

        except UnsupportedFirmwareError as exc:
            print()
            print("Unsupported firmware.")
            print(exc)
            return

        if not flight_log.flights:
            print()
            print("No flights found.")
            return

        flight_window = self._select_flight(
            flight_log
        )

        if flight_window is None:
            return

        events = EventExtractor().extract(
            flight_log,
            flight_window,
        )

        self._print_timeline(
            log_path,
            flight_window,
            events,
        )

    def _select_log(self):

        log_paths = sorted(
            Path("Logs").glob("*.bin")
        )

        if not log_paths:
            print()
            print("No BIN logs found in Logs/")
            return None

        print()
        print("Available Logs")
        print("================")

        for index, log_path in enumerate(
            log_paths,
            start=1,
        ):
            print(
                f"{index}. {log_path.name}"
            )

        print("0. Cancel")

        while True:

            choice = input(
                "\nSelection: "
            ).strip()

            if choice == "0":
                return None

            try:
                index = int(choice)

                if (
                    1
                    <= index
                    <= len(log_paths)
                ):
                    return log_paths[index - 1]

            except ValueError:
                pass

            print("Invalid selection.")

    def _select_flight(
        self,
        flight_log,
    ):

        if len(flight_log.flights) == 1:
            return flight_log.flights[0]

        print()
        print("Available Flights")
        print("=================")

        for index, flight_window in enumerate(
            flight_log.flights,
            start=1,
        ):
            print(
                f"{index}. "
                f"{format_time(flight_window.start_us)}"
                f" -> "
                f"{format_time(flight_window.end_us)}"
            )

        print("0. Cancel")

        while True:

            choice = input(
                "\nSelection: "
            ).strip()

            if choice == "0":
                return None

            try:
                index = int(choice)

                if (
                    1
                    <= index
                    <= len(flight_log.flights)
                ):
                    return flight_log.flights[
                        index - 1
                    ]

            except ValueError:
                pass

            print("Invalid selection.")

    def _print_timeline(
        self,
        log_path,
        flight_window,
        events,
    ):

        print()
        print("Event Timeline")
        print("=" * 70)

        print(
            f"Log    : {log_path.name}"
        )

        print(
            f"Window : "
            f"{format_time(flight_window.start_us)}"
            f" -> "
            f"{format_time(flight_window.end_us)}"
        )

        print(
            f"Events : {len(events)}"
        )

        print()

        if not events:
            print("No events found.")
            return

        for event in events:

            print(
                f"{format_time(event.time_us)}  "
                f"{event.event.value:<14}"
                f"{event.detail}"
            )
