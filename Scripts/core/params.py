import logging
import math
import re
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from numbers import Integral
from pathlib import Path
from types import MappingProxyType


PARAMETER_STARTUP_GAP_US = 110_000
PARAMETER_NAME_PATTERN = r"^[A-Z][A-Z_0-9]*$"
PARAMETER_NAME_MAX_LENGTH = 16


@dataclass(frozen=True)
class ParameterChange:
    """One effective parameter change after startup initialization."""

    time_us: int
    value: float


@dataclass(frozen=True)
class ParameterHistory:
    """Resolve logged parameter values at absolute BIN TimeUS timestamps."""

    initial_values: Mapping[str, float] = field(default_factory=dict)
    changes: Mapping[str, tuple[ParameterChange, ...]] = field(
        default_factory=dict
    )

    def __post_init__(self):
        """Freeze baseline values and stably sorted change sequences."""
        object.__setattr__(
            self,
            "initial_values",
            MappingProxyType(dict(self.initial_values)),
        )
        frozen_changes = {
            parameter_name: tuple(
                sorted(
                    parameter_changes,
                    key=lambda change: change.time_us,
                )
            )
            for parameter_name, parameter_changes in self.changes.items()
        }
        object.__setattr__(
            self,
            "changes",
            MappingProxyType(frozen_changes),
        )

    @property
    def latest_values(self):
        """Return the final logged value of every valid parameter."""
        latest_values = dict(self.initial_values)

        for parameter_name, parameter_changes in self.changes.items():
            if parameter_changes:
                latest_values[parameter_name] = parameter_changes[-1].value

        return latest_values

    def value_at(self, parameter_name, time_us):
        """Return the value applicable at time_us, or None when absent."""
        if not math.isfinite(time_us):
            raise ValueError("Parameter query time_us must be finite")

        parameter_changes = self.changes.get(parameter_name)

        if not parameter_changes:
            return self.initial_values.get(parameter_name)

        index = bisect_right(
            parameter_changes,
            time_us,
            key=lambda change: change.time_us,
        ) - 1

        if index < 0:
            return self.initial_values.get(parameter_name)

        return parameter_changes[index].value

    @classmethod
    def from_records(cls, records: Iterable[Mapping[str, object]]):
        """Build history from PARM dictionaries in decoded log order."""
        state = _ParameterHistoryState()

        for record in records:
            state.record(record)

        changes = {
            name: tuple(
                ParameterChange(
                    time_us=time_us,
                    value=value,
                )
                for time_us, value in parameter_changes
            )
            for name, parameter_changes in state.changes.items()
        }

        return cls(state.initial_values, changes)


class _ParameterHistoryState:
    """Classify decoded PARM records using absolute TimeUS timestamps."""

    def __init__(self):
        self.initial_values = {}
        self.current_values = {}
        self.changes = {}
        self.last_timestamp_us = None
        self.initialization_complete = False

    @staticmethod
    def _validate_name(name):
        if len(name) > PARAMETER_NAME_MAX_LENGTH:
            raise SystemExit(
                "Parameter name too long "
                f"(max {PARAMETER_NAME_MAX_LENGTH} characters): {name}"
            )

        if not re.match(PARAMETER_NAME_PATTERN, name):
            raise SystemExit(
                "Invalid parameter name format "
                "(must start with capital letter, contain only "
                f"A-Z, 0-9, _): {name}"
            )

    def record(self, payload):
        """Classify one raw PARM record using AMC's startup-gap rule."""
        name = payload.get("Name")
        value = payload.get("Value")

        if not isinstance(name, str) or not name or value is None:
            return

        self._validate_name(name)

        try:
            value = float(value)
        except (TypeError, ValueError) as error:
            raise SystemExit(
                f"Error converting {value} to float"
            ) from error

        timestamp_value = payload.get("TimeUS")
        timestamp_us = None

        if timestamp_value is not None:
            if isinstance(timestamp_value, Integral):
                timestamp_us = int(timestamp_value)
            else:
                try:
                    numeric_timestamp = float(timestamp_value)
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"PARM timestamp for {name} must be numeric"
                    ) from error

                if not math.isfinite(numeric_timestamp):
                    raise ValueError(
                        f"PARM timestamp for {name} must be finite"
                    )

                timestamp_us = int(numeric_timestamp)

            if (
                self.last_timestamp_us is not None
                and timestamp_us < self.last_timestamp_us
            ):
                raise ValueError(
                    f"PARM timestamps for {name} must be non-decreasing"
                )

            if (
                self.last_timestamp_us is not None
                and timestamp_us - self.last_timestamp_us
                > PARAMETER_STARTUP_GAP_US
            ):
                self.initialization_complete = True

            self.last_timestamp_us = timestamp_us

        if not self.initialization_complete:
            previous_value = self.current_values.get(name)

            if previous_value is not None and previous_value != value:
                logging.warning(
                    "Parameter %s changed from %s to %s "
                    "before boot process completed",
                    name,
                    previous_value,
                    value,
                )

            self.initial_values[name] = value
            self.current_values[name] = value
            return

        previous_value = self.current_values.get(name)
        self.current_values[name] = value

        if previous_value != value and timestamp_us is not None:
            self.changes.setdefault(name, []).append(
                (timestamp_us, value)
            )


class ParameterReader:

    def __init__(self, filename, config):

        self.filename = Path(filename)
        self.config = config

    def wanted_parameters(self):
        """
        Return the parameter patterns requested by the YAML configuration.
        """

        return set(self.config.get("parameters", []))

    def normalize_parameter(self, name, value):
        """
        Normalise firmware-specific parameter names and units so the rest
        of the framework sees a consistent parameter interface.
        """

        #
        # ArduPlane 4.6.x
        #

        if name == "RNGFND1_MAX_CM":
            name = "RNGFND1_MAX"
            value = value / 100.0

        return name, value

    @staticmethod
    def matches(name, patterns):
        """
        Return True if the parameter name matches any configured pattern.
        Supports both exact names and shell-style wildcards.
        """

        for pattern in patterns:
            if fnmatch(name, pattern):
                return True

        return False

    def read(self):
        """
        Read a MAVLink parameter export (.param/.params) and return only
        the parameters requested by the configuration.

        Firmware-specific parameter names and units are normalised before
        filtering so detectors always receive a consistent API.
        """

        patterns = self.wanted_parameters()

        params = {}

        with self.filename.open("r") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                parts = line.split()

                #
                # Expected format:
                # VehicleID ComponentID Name Value Type
                #

                if len(parts) < 5:
                    continue

                name = parts[2]

                try:
                    value = float(parts[3])
                except ValueError:
                    value = parts[3]

                #
                # Firmware compatibility
                #

                name, value = self.normalize_parameter(name, value)

                #
                # Configuration filtering
                #

                if self.matches(name, patterns):
                    params[name] = value

        return params
