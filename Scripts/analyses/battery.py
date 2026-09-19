from analyses.log_selector import select_log_input
from core.battery import (
    BatteryAnalysis,
    BatteryLoadEventType,
    BatteryProcessor,
)
from core.battery_pack_store import (
    BatteryPackStore,
    BatteryPackStoreError,
    LogPackState,
    fingerprint_log,
)
from core.config import Config
from core.log_reader import (
    FlightReader,
    UnsupportedFirmwareError,
)
from core.time import format_time, format_time_us


def _format_value(value, suffix="", decimals=2):
    """Format an optional numeric measurement."""

    if value is None:
        return "Unavailable"

    return f"{value:.{decimals}f}{suffix}"


def _format_duration(seconds):
    """Format an optional duration as mm:ss."""

    if seconds is None:
        return "Unavailable"

    total_seconds = int(round(seconds))
    minutes, seconds = divmod(total_seconds, 60)

    return f"{minutes:02d}:{seconds:02d}"


class BatteryAnalysisPresentation:
    """
    Present battery analysis for a selected flight and battery instance.
    """

    def __init__(self, pack_id=None, config=None, pack_store=None):
        self.pack_id = pack_id
        self.config = config or Config("Config/battery.yaml")
        self.pack_store = pack_store

    def run(self):

        selected_logs = select_log_input()

        if selected_logs is None:
            return
        log_path = selected_logs[0]

        pack_id = self.pack_id
        if pack_id is None:
            continue_analysis, pack_id = self._resolve_pack_id(log_path)
            if not continue_analysis:
                return

        try:
            flight_log = FlightReader(
                str(log_path),
                config=self.config,
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

        processor = BatteryProcessor(
            flight_log,
            flight_window,
            0,
        )

        instances = processor.available_instances()

        if not instances:
            print()
            print(
                "No battery telemetry is available "
                "for this flight."
            )
            return

        instance = self._select_instance(
            instances
        )

        if instance is None:
            return

        analysis = BatteryProcessor(
            flight_log,
            flight_window,
            instance,
            config=self.config,
        ).analyse()

        self._print_report(
            log_path,
            flight_window,
            analysis,
            pack_id,
        )

    def _resolve_pack_id(self, log_path):
        """Resolve optional Pack ID metadata for one content-identified BIN."""
        try:
            store = self.pack_store or BatteryPackStore()
            fingerprint = fingerprint_log(log_path)
            association = store.association_for(fingerprint)
        except (BatteryPackStoreError, OSError) as exc:
            print()
            print(f"Battery pack tracking unavailable: {exc}")
            print("Persistent pack data was not changed. Continuing without Pack ID.")
            return True, None

        if association.state is LogPackState.TRACKED:
            return True, association.pack_id
        if association.state is LogPackState.NOT_TRACKED:
            return True, None
        return self._select_pack_decision(store, fingerprint)

    def _select_pack_decision(self, store, fingerprint):
        """Prompt once for an unseen source-log fingerprint."""
        while True:
            print()
            print("Battery Pack")
            print("============")
            print()
            if store.pack_ids:
                print("1. Select existing pack")
                print("2. Create new pack")
                print("3. Continue without pack tracking")
            else:
                print("No existing Pack IDs.")
                print("1. Create new pack")
                print("2. Continue without pack tracking")
            print("0. Cancel")

            choice = input("\nSelection: ").strip()
            if choice == "0":
                return False, None
            if store.pack_ids and choice == "1":
                pack_id = self._select_existing_pack(store.pack_ids)
                if pack_id is None:
                    continue
                if self._save_pack_decision(
                    lambda selected_pack_id=pack_id: store.associate(
                        fingerprint,
                        selected_pack_id,
                    )
                ):
                    return True, pack_id
                return True, None
            if choice == ("2" if store.pack_ids else "1"):
                pack_id = input("\nNew Pack ID: ").strip()
                try:
                    store.create_and_associate(fingerprint, pack_id)
                except BatteryPackStoreError as exc:
                    print(exc)
                    continue
                except OSError as exc:
                    self._print_save_error(exc)
                    return True, None
                return True, pack_id
            if choice == ("3" if store.pack_ids else "2"):
                if self._save_pack_decision(
                    lambda: store.mark_not_tracked(fingerprint)
                ):
                    return True, None
                return True, None
            print("Invalid selection.")

    @staticmethod
    def _select_existing_pack(pack_ids):
        """Select one known physical Pack ID, or return to the decision menu."""
        print()
        print("Existing Battery Packs")
        print("======================")
        for index, pack_id in enumerate(pack_ids, start=1):
            print(f"{index}. {pack_id}")
        print("0. Back")

        while True:
            choice = input("\nSelection: ").strip()
            if choice == "0":
                return None
            try:
                index = int(choice)
            except ValueError:
                index = 0
            if 1 <= index <= len(pack_ids):
                return pack_ids[index - 1]
            print("Invalid selection.")

    def _save_pack_decision(self, save):
        """Persist one optional tracking decision without blocking analysis."""
        try:
            save()
        except OSError as exc:
            self._print_save_error(exc)
            return False
        return True

    @staticmethod
    def _print_save_error(exc):
        print(f"Unable to save battery pack decision: {exc}")
        print("Continuing without Pack ID; persistent data was not changed.")

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

    def _select_instance(
        self,
        instances,
    ):

        if len(instances) == 1:
            return instances[0]

        print()
        print("Available Battery Instances")
        print("===========================")

        for index, instance in enumerate(
            instances,
            start=1,
        ):
            print(
                f"{index}. Battery {instance}"
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
                    <= len(instances)
                ):
                    return instances[
                        index - 1
                    ]

            except ValueError:
                pass

            print("Invalid selection.")

    def _print_report(
        self,
        log_path,
        flight_window,
        analysis: BatteryAnalysis | None,
        pack_id=None,
    ):

        print()
        print("BATTERY ANALYSIS")
        print("=" * 70)

        print(
            f"Log    : {log_path.name}"
        )

        print(
            "Window : "
            f"{format_time(flight_window.start_us)}"
            " -> "
            f"{format_time(flight_window.end_us)}"
        )

        if analysis is None:
            print()
            print(
                "No valid battery analysis is available."
            )
            return

        print(
            f"Battery instance : {analysis.instance}"
        )

        configuration = analysis.session_configuration

        display_pack_id = pack_id if pack_id is not None else self.pack_id
        if display_pack_id is not None:
            print(f"Pack ID          : {display_pack_id}")

        if configuration is not None:
            print(
                "Capacity         : "
                f"{_format_value(
                    configuration.capacity_mah,
                    ' mAh',
                    0,
                )}"
            )
            print(
                "Low voltage      : "
                f"{self._format_threshold(
                    configuration.low_voltage
                )}"
            )
            print(
                "Critical voltage : "
                f"{self._format_threshold(
                    configuration.critical_voltage
                )}"
            )

        print()
        print(
            "Flight duration       "
            f"{_format_duration(analysis.duration_s)}"
        )
        print(
            "Start voltage         "
            f"{_format_value(analysis.start_voltage, ' V')}"
        )
        print(
            "Final voltage         "
            f"{_format_value(analysis.final_voltage, ' V')}"
        )
        print(
            "Minimum voltage       "
            f"{_format_value(analysis.minimum_voltage, ' V')}"
        )

        print()
        print(
            "Maximum current       "
            f"{_format_value(analysis.maximum_current, ' A')}"
        )
        print(
            "Average current       "
            f"{_format_value(analysis.average_current, ' A')}"
        )
        print(
            "Maximum power         "
            f"{_format_value(analysis.maximum_power, ' W')}"
        )
        print(
            "Energy consumed       "
            f"{_format_value(analysis.consumed_wh, ' Wh')}"
        )
        print(
            "Capacity consumed     "
            f"{_format_value(analysis.consumed_mah, ' mAh')}"
        )
        print(
            "Consumption rate      "
            f"{_format_value(analysis.mah_per_minute, ' mAh/min')}"
        )

        print()
        print("HIGHEST-LOAD EVENT")

        event = analysis.load_event

        if event is None:
            print()
            print("No valid load event is available.")

        else:
            print()
            print(
                f"Time                  "
                f"{format_time_us(event.time_us)}"
            )
            print(
                "Current               "
                f"{_format_value(event.current, ' A')}"
            )
            print(
                "Voltage before        "
                f"{_format_value(event.voltage_before, ' V')}"
            )
            print(
                "Minimum voltage       "
                f"{_format_value(event.minimum_voltage, ' V')}"
            )
            print(
                "Voltage sag           "
                f"{_format_value(event.voltage_sag, ' V')}"
            )
            print(
                "Sag per ampere        "
                f"{_format_value(event.sag_per_ampere, ' V/A')}"
            )
            print(
                "Voltage after 5 s     "
                f"{_format_value(
                    event.voltage_after_recovery,
                    ' V',
                )}"
            )
            print(
                "Voltage recovery      "
                f"{_format_value(
                    event.voltage_recovery,
                    ' V',
                )}"
            )

        if analysis.counter_warnings:
            print()
            print("COUNTER WARNINGS")

            for warning in analysis.counter_warnings:
                print()
                print(f"- {warning}")

        self._print_bounded_load_events(
            analysis.bounded_load_events
        )

        if (
            configuration is not None
            and configuration.warnings
        ):
            print()
            print("CONFIGURATION WARNINGS")

            for warning in configuration.warnings:
                print()
                print(f"- {warning}")

    @staticmethod
    def _format_threshold(value):
        if value is None:
            return "Unavailable"
        if value == 0:
            return "Disabled"
        return f"{value:.2f} V"

    @staticmethod
    def _print_bounded_load_events(events):
        print()
        print("BOUNDED LOAD EVENTS")

        if not events:
            print()
            print("No bounded load events detected.")
            return

        for index, event in enumerate(events, start=1):
            print()
            print(
                f"{index}. {event.event_type.value}"
            )

            if (
                event.event_type == BatteryLoadEventType.TAKEOFF
                and event.takeoff_type is not None
            ):
                print(
                    f"   Context              "
                    f"{event.takeoff_type.value}"
                )

            print(
                "   Time                 "
                f"{format_time_us(event.start_us)} -> "
                f"{format_time_us(event.end_us)}"
            )
            print(
                "   Duration             "
                f"{_format_value(event.duration_s, ' s', 3)}"
            )
            print(
                "   Consumed at start    "
                f"{_format_value(
                    event.consumed_mah_at_start,
                    ' mAh',
                )}"
            )
            print(
                "   Maximum throttle     "
                f"{_format_value(event.maximum_throttle, ' %')}"
            )
            print(
                "   Average throttle     "
                f"{_format_value(event.average_throttle, ' %')}"
            )
            print(
                "   Pre-load voltage     "
                f"{_format_value(event.pre_load_voltage, ' V')}"
            )
            print(
                "   Minimum voltage      "
                f"{_format_value(event.minimum_voltage, ' V')}"
            )
            print(
                "   Voltage sag          "
                f"{_format_value(event.voltage_sag, ' V')}"
            )
            print(
                "   Peak current         "
                f"{_format_value(event.peak_current, ' A')}"
            )
            print(
                "   Average current      "
                f"{_format_value(event.average_current, ' A')}"
            )
            print(
                "   Current at min V     "
                f"{_format_value(
                    event.current_at_minimum_voltage,
                    ' A',
                )}"
            )
            print(
                "   Voltage after 5 s    "
                f"{_format_value(
                    event.voltage_after_recovery,
                    ' V',
                )}"
            )
            print(
                "   Voltage recovery     "
                f"{_format_value(event.voltage_recovery, ' V')}"
            )
            print(
                "   Margin to LOW        "
                f"{_format_value(event.low_voltage_margin, ' V')}"
            )
            print(
                "   Margin to CRITICAL   "
                f"{_format_value(
                    event.critical_voltage_margin,
                    ' V',
                )}"
            )
