from core.log_reader import FlightReader
from core.armcycle import ArmCycleFinder
from core.time import format_time_us


LOG = "Logs/log_19.bin"


flight_log = FlightReader(
    LOG
).read()


print()
print("Flight-scoped Arm Cycles")
print("-" * 70)


if not flight_log.flights:

    print("No FlightWindows detected.")
    raise SystemExit


for flight_number, flight_window in enumerate(
    flight_log.flights,
    start=1,
):

    cycles = ArmCycleFinder(
        flight_log,
        flight_window,
    ).find()

    print()
    print(f"Flight {flight_number}")

    print(
        f"  Window : "
        f"{format_time_us(flight_window.start_us)}"
        f" -> "
        f"{format_time_us(flight_window.end_us)}"
    )

    print(
        f"  Cycles : {len(cycles)}"
    )

    for i, cycle in enumerate(
        cycles,
        start=1,
    ):

        print()
        print(f"  Cycle {i}")

        print(
            f"    Arm      : "
            f"{format_time_us(cycle.arm_us)}"
        )

        print(
            f"    Disarm   : "
            f"{format_time_us(cycle.disarm_us)}"
        )

        print(
            f"    Duration : "
            f"{cycle.duration_s:.2f} s"
        )

        print(
            f"    Closed   : "
            f"{cycle.closed}"
        )