from pathlib import Path
import sys

sys.path.insert(0, "Scripts")

from core.reader import FlightReader


targets = {
    "log_17.bin": 4,
    "log_19.bin": 1,
    "log_26.bin": 4,
}


for filename, flight_number in targets.items():

    log = FlightReader(
        str(Path("Logs") / filename)
    ).read()

    fw = log.flights[flight_number - 1]
    land = log.get("LAND")
    gps = log.get("GPS")
    msg = log.get("MSG")

    land = land[
        (land["TimeUS"] >= fw.start_us)
        & (land["TimeUS"] <= fw.end_us)
    ]

    # Detect the actual transition INTO stage 1.
    prev = land["stage"].shift()
    stage1 = land[
        (land["stage"] == 1)
        & (prev != 1)
    ]

    # Use the final landing attempt.
    start = int(stage1["TimeUS"].iloc[-1])

    # Actual transition INTO stage 3.
    after_start = land[land["TimeUS"] >= start]
    prev = after_start["stage"].shift()
    stage3 = after_start[
        (after_start["stage"] == 3)
        & (prev != 3)
    ]

    stage3_time = (
        int(stage3["TimeUS"].iloc[0])
        if not stage3.empty
        else None
    )

    # First disarm message after stage 1.
    disarm = msg[
        (msg["TimeUS"] >= start)
        & (msg["TimeUS"] <= fw.end_us)
        & msg["Message"].astype(str).str.contains(
            "Throttle disarmed",
            case=False,
            na=False,
        )
    ]

    disarm_time = (
        int(disarm["TimeUS"].iloc[0])
        if not disarm.empty
        else fw.end_us
    )

    data = gps[
        (gps["TimeUS"] >= start)
        & (gps["TimeUS"] <= disarm_time)
    ][["TimeUS", "Spd"]].copy()

    data["sec"] = (
        data["TimeUS"] - start
    ) / 1_000_000

    print()
    print("=" * 60)
    print(filename, "Flight", flight_number)
    print("stage 1:", start)
    print("stage 3:", stage3_time)
    print("disarm :", disarm_time)
    print()
    print(
        data[["sec", "Spd"]].to_string(
            index=False,
            formatters={
                "sec": "{:.2f}".format,
                "Spd": "{:.2f}".format,
            },
        )
    )