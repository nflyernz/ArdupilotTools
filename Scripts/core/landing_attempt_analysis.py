from dataclasses import dataclass

from .landing_attempt import LandingAttempt


@dataclass(slots=True)
class LandingAttemptAnalysis:
    """
    Measured evidence describing one landing attempt.

    This class does not determine whether the landing was good,
    bad, successful, or unsuccessful. It records what occurred
    during the attempt so that interpretation can be performed
    by a later presentation or review layer.
    """

    attempt: LandingAttempt

    # ------------------------------------------------------------------
    # Temporal scope
    # ------------------------------------------------------------------

    duration_s: float | None

    # ------------------------------------------------------------------
    # Landing geometry
    # ------------------------------------------------------------------

    approach_start_altitude: float | None
    glide_slope_degrees: float | None

    # ------------------------------------------------------------------
    # Landing stages
    # ------------------------------------------------------------------

    preflare_time_us: int | None
    preflare_altitude: float | None

    flare_time_us: int | None
    flare_altitude: float | None

    # ------------------------------------------------------------------
    # Aircraft state at preflare
    # ------------------------------------------------------------------

    preflare_sink_rate: float | None
    preflare_airspeed: float | None
    preflare_gps_speed: float | None

    # ------------------------------------------------------------------
    # Aircraft state at flare
    # ------------------------------------------------------------------

    flare_sink_rate: float | None
    flare_airspeed: float | None
    flare_gps_speed: float | None
    flare_distance: float | None

    # ------------------------------------------------------------------
    # Rangefinder
    #
    # These fields preserve observed rangefinder acquisition and
    # continuity evidence. A zero or invalid reading may occur
    # intermittently during acquisition, so rangefinder behaviour
    # is not represented as a simple engaged/disengaged state.
    # ------------------------------------------------------------------

    rangefinder_first_nonzero_time_us: int | None
    rangefinder_first_nonzero_distance: float | None

    rangefinder_first_in_range_time_us: int | None
    rangefinder_first_in_range_distance: float | None

    rangefinder_continuous_time_us: int | None
    rangefinder_continuous_samples: int | None

    rangefinder_disengage_events: int

    rangefinder_last_disengage_time_us: int | None
    rangefinder_last_disengage_distance: float | None

    # ------------------------------------------------------------------
    # Landing / rollout completion
    #
    # GPS stop is the beginning of a sustained low-groundspeed run.
    # It is not interpreted as the touchdown instant.
    # ------------------------------------------------------------------

    gps_stop_time_us: int | None
    gps_stop_speed_limit: float | None
    gps_stop_persistence_s: float | None

    flare_to_gps_stop_s: float | None

    # ------------------------------------------------------------------
    # Attempt termination
    # ------------------------------------------------------------------

    end_reason: str | None