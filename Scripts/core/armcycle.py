from dataclasses import dataclass

from core.flight_window import FlightWindow
from core.model import FlightLog
from core.scope import (
    filter_telemetry,
    validate_flight_window,
)


@dataclass
class ArmCycle:
    """
    One arm/disarm cycle.
    """

    arm_us: int

    disarm_us: int = 0

    arm_index: int = 0

    disarm_index: int = 0

    duration_s: float = 0.0

    closed: bool = False


class ArmCycleFinder:
    """
    Find arm/disarm cycles within one FlightWindow.

    Only ARM transitions whose timestamps lie within the selected
    FlightWindow are considered.

    State before the FlightWindow is not used to synthesize a partial
    arm cycle at the flight boundary.
    """

    def __init__(
        self,
        flight_log: FlightLog,
        flight_window: FlightWindow,
    ):

        validate_flight_window(
            flight_log,
            flight_window,
        )

        self.flight_log = flight_log
        self.flight_window = flight_window

    def find(self) -> list[ArmCycle]:

        arm = filter_telemetry(
            self.flight_log.get("ARM"),
            self.flight_window,
        )

        if arm is None or arm.empty:
            return []

        cycles = []

        current = None
        previous = None

        for index, row in arm.iterrows():

            state = int(row.ArmState)

            #
            # Arm transition.
            #
            if previous == 0 and state == 1:

                current = ArmCycle(
                    arm_us=int(row.TimeUS),
                    arm_index=index,
                )

            #
            # Disarm transition.
            #
            elif (
                current is not None
                and previous == 1
                and state == 0
            ):

                current.disarm_us = int(
                    row.TimeUS
                )

                current.disarm_index = index

                current.duration_s = (
                    current.disarm_us
                    - current.arm_us
                ) / 1e6

                current.closed = True

                cycles.append(current)

                current = None

            previous = state

        #
        # An arm transition occurred inside the FlightWindow but no
        # matching disarm transition occurred before the window ended.
        #
        if current is not None:

            current.disarm_us = int(
                arm.iloc[-1].TimeUS
            )

            current.disarm_index = arm.index[-1]

            current.duration_s = (
                current.disarm_us
                - current.arm_us
            ) / 1e6

            current.closed = False

            cycles.append(current)

        return cycles