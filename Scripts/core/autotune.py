"""Evidence models for the audited Plane 4.7.x fixed-wing AUTOTUNE paths."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class AutotuneAxis(IntEnum):
    ROLL = 0
    PITCH = 1
    YAW = 2


class AutotuneTerminationReason(Enum):
    STOPPED = "STOPPED"
    RESTARTED = "RESTARTED"
    LOG_END = "LOG_END"


class AutotuneExitOutcome(Enum):
    SAVE_REQUESTED = "SAVE_REQUESTED"
    RESTORE_INFERRED = "RESTORE_INFERRED"
    UNKNOWN = "UNKNOWN"


class SaveTriggerType(Enum):
    FINISHED_MILESTONE = "FINISHED_MILESTONE"
    SESSION_EXIT = "SESSION_EXIT"


class DemandState(IntEnum):
    IDLE = 0
    DEMAND_POS = 1
    DEMAND_NEG = 2


@dataclass(frozen=True, slots=True)
class EvidencePosition:
    time_us: int
    source_order: int | None

    @property
    def key(self):
        # Missing order never purports to recover original cross-message order.
        return self.time_us, self.source_order if self.source_order is not None else -1


@dataclass(frozen=True, slots=True)
class RuntimeGains:
    position: EvidencePosition
    ff: float | None
    p: float | None
    i: float | None
    d: float | None
    rmax: float | None
    tau: float | None

    @property
    def values(self):
        return self.ff, self.p, self.i, self.d, self.rmax, self.tau


@dataclass(frozen=True, slots=True)
class DemandPeriod:
    state: DemandState
    start: EvidencePosition
    end: EvidencePosition
    end_transition_observed: bool

    @property
    def duration_s(self):
        return (self.end.time_us - self.start.time_us) / 1e6


@dataclass(frozen=True, slots=True)
class ActionTransition:
    position: EvidencePosition
    previous: int
    current: int


@dataclass(frozen=True, slots=True)
class GainLimitEvent:
    position: EvidencePosition
    axis: AutotuneAxis
    kind: str
    value: float


@dataclass(frozen=True, slots=True)
class CompletionEvent:
    position: EvidencePosition
    axis: AutotuneAxis
    save_requested: bool = True


@dataclass(frozen=True, slots=True)
class SaveTrigger:
    position: EvidencePosition
    axis: AutotuneAxis
    trigger_type: SaveTriggerType


@dataclass(frozen=True, slots=True)
class ParameterSaveObservation:
    position: EvidencePosition
    name: str
    value: float
    trigger: SaveTrigger
    agreeing_runtime: EvidencePosition


@dataclass(slots=True)
class AxisPersistenceEvidence:
    save_requests: list[SaveTrigger] = field(default_factory=list)
    parameter_save_observations: list[ParameterSaveObservation] = field(
        default_factory=list
    )
    exit_outcome: AutotuneExitOutcome = AutotuneExitOutcome.UNKNOWN
    exit_basis: str = "Evidence unavailable"
    runtime_continuity_from_session: int | None = None
    # BIN evidence never independently verifies physical-media durability.
    physical_persistence_verified: bool = False


@dataclass(slots=True)
class AutotuneAxisResult:
    axis: AutotuneAxis
    atrp_count: int = 0
    entry_runtime_gains: RuntimeGains | None = None
    final_observed_runtime_gains: RuntimeGains | None = None
    demand_periods: list[DemandPeriod] = field(default_factory=list)
    action_baseline: int | None = None
    action_transitions: list[ActionTransition] = field(default_factory=list)
    gain_limit_events: list[GainLimitEvent] = field(default_factory=list)
    completion_events: list[CompletionEvent] = field(default_factory=list)
    persistence: AxisPersistenceEvidence = field(
        default_factory=AxisPersistenceEvidence
    )

    @property
    def active(self):
        return self.atrp_count > 0

    @property
    def positive_demand_periods(self):
        return sum(p.state is DemandState.DEMAND_POS for p in self.demand_periods)

    @property
    def negative_demand_periods(self):
        return sum(p.state is DemandState.DEMAND_NEG for p in self.demand_periods)

    @property
    def total_observed_demand_time_s(self):
        return sum(p.duration_s for p in self.demand_periods)

    @property
    def longest_observed_demand_period_s(self):
        return max((p.duration_s for p in self.demand_periods), default=0.0)


@dataclass(frozen=True, slots=True)
class AutotuneActivationContext:
    """Context observations, never an inferred activation cause."""

    mode_at_start: int | None = None
    mode_observations: tuple[tuple[EvidencePosition, int | None], ...] = ()
    command_observations: tuple[tuple[EvidencePosition, str, int | None], ...] = ()


@dataclass(frozen=True, slots=True)
class AutotuneFlightRelation:
    flight_number: int
    starts_before_flight: bool
    extends_beyond_flight: bool


@dataclass(frozen=True, slots=True)
class AutotuneWarning:
    code: str
    detail: str
    position: EvidencePosition | None = None
    session_number: int | None = None
    record: dict[str, object] | None = None


@dataclass(slots=True)
class AutotuneSessionResult:
    number: int
    start: EvidencePosition
    end: EvidencePosition | None = None
    termination_reason: AutotuneTerminationReason | None = None
    configuration: dict[str, float | None] = field(default_factory=dict)
    configured_axes: tuple[AutotuneAxis, ...] | None = None
    selected_axes: tuple[AutotuneAxis, ...] | None = None
    selection_events: list[tuple[EvidencePosition, tuple[AutotuneAxis, ...]]] = field(
        default_factory=list
    )
    axes: dict[AutotuneAxis, AutotuneAxisResult] = field(
        default_factory=lambda: {
            axis: AutotuneAxisResult(axis) for axis in AutotuneAxis
        }
    )
    activation_context: AutotuneActivationContext = field(
        default_factory=AutotuneActivationContext
    )
    flight_relations: list[AutotuneFlightRelation] = field(default_factory=list)

    @property
    def duration_s(self):
        return (self.end.time_us - self.start.time_us) / 1e6 if self.end else None

    @property
    def active_axes(self):
        return tuple(axis for axis, result in self.axes.items() if result.active)


@dataclass(slots=True)
class AutotuneAnalysisResult:
    firmware: str | None = None
    sessions: list[AutotuneSessionResult] = field(default_factory=list)
    warnings: list[AutotuneWarning] = field(default_factory=list)
