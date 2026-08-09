def _extract_land_stage_events(
    self,
    flight_log: FlightLog,
    window,
) -> list[TimelineEvent]:
    """
    Extract LAND stage transitions.

    LAND telemetry is logged continuously. Only changes in the
    controller stage are emitted as timeline events.
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
