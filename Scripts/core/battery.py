"""
Flight-scoped battery telemetry processing.

BAT counters are cumulative across a log, so consumption values are
calculated as deltas from the selected FlightWindow baseline.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .flight_data import FlightLog
from .flight_window import FlightWindow
from .scope import filter_telemetry, validate_flight_window


@dataclass
class BatteryLoadEvent:
    """Measurements associated with the highest-current BAT sample."""

    time_us: int
    current: float
    voltage_before: Optional[float]
    minimum_voltage: Optional[float]
    voltage_sag: Optional[float]
    sag_per_ampere: Optional[float]
    voltage_after_recovery: Optional[float]
    voltage_recovery: Optional[float]


@dataclass
class BatteryAnalysis:
    """Battery measurements for one BAT instance and FlightWindow."""

    instance: int
    start_us: int
    end_us: int
    duration_s: Optional[float]
    start_voltage: Optional[float]
    final_voltage: Optional[float]
    minimum_voltage: Optional[float]
    maximum_current: Optional[float]
    average_current: Optional[float]
    maximum_power: Optional[float]
    consumed_mah: Optional[float]
    consumed_wh: Optional[float]
    mah_per_minute: Optional[float]
    load_event: Optional[BatteryLoadEvent]
    counter_warnings: list[str] = field(default_factory=list)


class BatteryProcessor:
    """
    Analyse one explicit ArduPilot BAT instance within one FlightWindow.

    The initial load-event definition is deliberately simple: the event is
    the single in-window BAT sample with the highest valid current. Its
    minimum voltage is therefore that sample's voltage.
    """

    RECOVERY_US = 5_000_000

    def __init__(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
        instance: int,
    ):
        validate_flight_window(flight_log, flight_window)

        self.flight_log = flight_log
        self.flight_window = flight_window
        self.instance = int(instance)

    def available_instances(self) -> list[int]:
        """Return BAT instances with valid instance identifiers."""
        bat = self.flight_log.get("BAT")

        if bat is None or bat.empty or "Inst" not in bat.columns:
            return []

        instances = pd.to_numeric(bat["Inst"], errors="coerce").dropna()
        return sorted({int(value) for value in instances})

    def analyse(self) -> Optional[BatteryAnalysis]:
        """Return measurements for the selected instance, or None if absent."""
        bat = self.flight_log.get("BAT")

        if (
            bat is None
            or bat.empty
            or not {"TimeUS", "Inst"}.issubset(bat.columns)
        ):
            return None

        all_instance = self._instance_rows(bat)

        if all_instance.empty:
            return None

        scoped = filter_telemetry(
            all_instance,
            self.flight_window,
        ).copy()

        if scoped.empty:
            return None

        scoped = scoped.sort_values("TimeUS")
        duration_s = self._duration_s()
        warnings: list[str] = []

        start_voltage = self._first_value(scoped, "Volt")
        final_voltage = self._last_value(scoped, "Volt")
        minimum_voltage = self._minimum_value(scoped, "Volt")
        maximum_current = self._maximum_value(scoped, "Curr")
        average_current = self._mean_value(scoped, "Curr")
        maximum_power = self._maximum_power(scoped)

        consumed_mah = self._counter_delta(
            all_instance,
            scoped,
            "CurrTot",
            warnings,
        )
        consumed_wh = self._counter_delta(
            all_instance,
            scoped,
            "EnrgTot",
            warnings,
        )

        mah_per_minute = None
        if (
            consumed_mah is not None
            and duration_s is not None
            and duration_s > 0
        ):
            mah_per_minute = consumed_mah / (duration_s / 60.0)

        return BatteryAnalysis(
            instance=self.instance,
            start_us=self.flight_window.start_us,
            end_us=self.flight_window.end_us,
            duration_s=duration_s,
            start_voltage=start_voltage,
            final_voltage=final_voltage,
            minimum_voltage=minimum_voltage,
            maximum_current=maximum_current,
            average_current=average_current,
            maximum_power=maximum_power,
            consumed_mah=consumed_mah,
            consumed_wh=consumed_wh,
            mah_per_minute=mah_per_minute,
            load_event=self._load_event(scoped),
            counter_warnings=warnings,
        )

    def _instance_rows(self, bat: pd.DataFrame) -> pd.DataFrame:
        instances = pd.to_numeric(bat["Inst"], errors="coerce")
        return bat.loc[instances == self.instance].copy()

    def _duration_s(self) -> Optional[float]:
        duration_s = (
            self.flight_window.end_us - self.flight_window.start_us
        ) / 1_000_000

        return duration_s if duration_s > 0 else None

    @staticmethod
    def _numeric(data: pd.DataFrame, column: str) -> pd.Series:
        if column not in data.columns:
            return pd.Series(dtype=float)

        return pd.to_numeric(
            data[column],
            errors="coerce",
        ).dropna()

    def _first_value(
        self,
        data: pd.DataFrame,
        column: str,
    ) -> Optional[float]:
        values = self._numeric(data, column)
        return float(values.iloc[0]) if not values.empty else None

    def _last_value(
        self,
        data: pd.DataFrame,
        column: str,
    ) -> Optional[float]:
        values = self._numeric(data, column)
        return float(values.iloc[-1]) if not values.empty else None

    def _minimum_value(
        self,
        data: pd.DataFrame,
        column: str,
    ) -> Optional[float]:
        values = self._numeric(data, column)
        return float(values.min()) if not values.empty else None

    def _maximum_value(
        self,
        data: pd.DataFrame,
        column: str,
    ) -> Optional[float]:
        values = self._numeric(data, column)
        return float(values.max()) if not values.empty else None

    def _mean_value(
        self,
        data: pd.DataFrame,
        column: str,
    ) -> Optional[float]:
        values = self._numeric(data, column)
        return float(values.mean()) if not values.empty else None

    def _maximum_power(
        self,
        data: pd.DataFrame,
    ) -> Optional[float]:
        if not {"Volt", "Curr"}.issubset(data.columns):
            return None

        voltage = pd.to_numeric(data["Volt"], errors="coerce")
        current = pd.to_numeric(data["Curr"], errors="coerce")

        power = (voltage * current).dropna()

        return float(power.max()) if not power.empty else None

    def _counter_delta(
        self,
        all_instance: pd.DataFrame,
        scoped: pd.DataFrame,
        column: str,
        warnings: list[str],
    ) -> Optional[float]:
        if column not in all_instance.columns:
            warnings.append(f"{column} is unavailable.")
            return None

        all_values = all_instance.copy()
        all_values["_counter"] = pd.to_numeric(
            all_values[column],
            errors="coerce",
        )

        all_values = (
            all_values
            .dropna(subset=["_counter"])
            .sort_values("TimeUS")
        )

        scoped_values = all_values[
            (
                all_values["TimeUS"]
                >= self.flight_window.start_us
            )
            &
            (
                all_values["TimeUS"]
                <= self.flight_window.end_us
            )
        ]

        if scoped_values.empty:
            warnings.append(
                f"{column} has no valid in-window samples."
            )
            return None

        # The counter baseline is the last valid sample strictly BEFORE
        # the FlightWindow. A sample exactly at the window start belongs
        # to the flight and must not be used as the baseline.
        baseline_rows = all_values[
            all_values["TimeUS"] < self.flight_window.start_us
        ]

        if baseline_rows.empty:
            baseline = float(
                scoped_values["_counter"].iloc[0]
            )

            warnings.append(
                f"{column} baseline unavailable before FlightWindow "
                "start; using first in-window sample."
            )
        else:
            baseline = float(
                baseline_rows["_counter"].iloc[-1]
            )

        counter_values = pd.concat(
            [
                pd.Series([baseline]),
                scoped_values["_counter"].reset_index(
                    drop=True
                ),
            ],
            ignore_index=True,
        )

        if (
            counter_values.diff().dropna() < 0
        ).any():
            warnings.append(
                f"{column} is non-monotonic or reset in "
                "FlightWindow."
            )
            return None

        return float(
            scoped_values["_counter"].iloc[-1] - baseline
        )

    def _load_event(
        self,
        scoped: pd.DataFrame,
    ) -> Optional[BatteryLoadEvent]:
        if "Curr" not in scoped.columns:
            return None

        current = pd.to_numeric(
            scoped["Curr"],
            errors="coerce",
        )

        if current.dropna().empty:
            return None

        peak_index = current.idxmax()
        peak = scoped.loc[peak_index]

        peak_time = int(peak["TimeUS"])
        peak_current = float(current.loc[peak_index])

        before = scoped[
            scoped["TimeUS"] < peak_time
        ]

        voltage_before = self._last_value(
            before,
            "Volt",
        )

        minimum_voltage = self._numeric(
            scoped.loc[[peak_index]],
            "Volt",
        )

        minimum_voltage = (
            float(minimum_voltage.iloc[0])
            if not minimum_voltage.empty
            else None
        )

        voltage_sag = None

        if (
            voltage_before is not None
            and minimum_voltage is not None
        ):
            voltage_sag = (
                voltage_before - minimum_voltage
            )

        sag_per_ampere = None

        if (
            voltage_sag is not None
            and peak_current > 0
        ):
            sag_per_ampere = (
                voltage_sag / peak_current
            )

        recovery_target = (
            peak_time + self.RECOVERY_US
        )

        recovery_rows = scoped[
            scoped["TimeUS"] >= recovery_target
        ]

        voltage_after_recovery = self._first_value(
            recovery_rows,
            "Volt",
        )

        voltage_recovery = None

        if (
            voltage_after_recovery is not None
            and minimum_voltage is not None
        ):
            voltage_recovery = (
                voltage_after_recovery - minimum_voltage
            )

        return BatteryLoadEvent(
            time_us=peak_time,
            current=peak_current,
            voltage_before=voltage_before,
            minimum_voltage=minimum_voltage,
            voltage_sag=voltage_sag,
            sag_per_ampere=sag_per_ampere,
            voltage_after_recovery=voltage_after_recovery,
            voltage_recovery=voltage_recovery,
        )