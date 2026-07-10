from core.reader import FlightReader
from core.armcycle import ArmCycleFinder

flight = FlightReader(
    "Logs/log_19_2026-7-5-09-43-10.bin"
).read()

cycles = ArmCycleFinder(flight).find()

print()

print("Arm Cycles")
print("-" * 70)

for i, c in enumerate(cycles, start=1):

    print(f"Cycle {i}")

    print(f"  Arm      : {c.arm_us / 1e6:.3f} s")

    print(f"  Disarm   : {c.disarm_us / 1e6:.3f} s")

    print(f"  Duration : {c.duration_s:.2f} s")

    print(f"  Closed   : {c.closed}")

    print()
