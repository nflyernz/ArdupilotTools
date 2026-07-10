from dataclasses import dataclass


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
    Find all arm/disarm cycles in a flight.
    """

    def __init__(self, flight):

        self.flight = flight

    def find(self):

        arm = self.flight.get("ARM")

        if arm.empty:
            return []

        cycles = []

        current = None

        previous = None

        for index, row in arm.iterrows():

            state = int(row.ArmState)

            #
            # Arm transition
            #
            if previous == 0 and state == 1:

                current = ArmCycle(
                    arm_us=int(row.TimeUS),
                    arm_index=index,
                )

            #
            # Disarm transition
            #
            elif (
                current is not None
                and previous == 1
                and state == 0
            ):

                current.disarm_us = int(row.TimeUS)

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
        # Still armed when log ended
        #
        if current is not None:

            current.disarm_us = int(arm.iloc[-1].TimeUS)

            current.disarm_index = arm.index[-1]

            current.duration_s = (
                current.disarm_us
                - current.arm_us
            ) / 1e6

            current.closed = False

            cycles.append(current)

        return cycles
