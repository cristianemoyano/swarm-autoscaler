"""Centralized constants for labels, metrics, enums, and other string literals."""
from enum import Enum, auto

# Metrics
# Use an enum for internal logic and provide helpers to map to/from strings

# Service labels
LABEL_AUTOSCALE = "swarm.autoscale"
LABEL_MAX_REPLICAS = "swarm.autoscale.max"
LABEL_MIN_REPLICAS = "swarm.autoscale.min"
LABEL_DISABLE_MANUAL_REPLICAS = "swarm.autoscale.disable-manual-replicas"
LABEL_PERCENTAGE_MAX = "swarm.autoscale.percentage-max"
LABEL_PERCENTAGE_MIN = "swarm.autoscale.percentage-min"
LABEL_DECREASE_MODE = "swarm.autoscale.decrease-mode"
LABEL_METRIC = "swarm.autoscale.metric"


class MetricEnum(Enum):
    CPU = auto()
    MEMORY = auto()

# Defaults for replicas when labels are missing
DEFAULT_MIN_REPLICAS = 2
DEFAULT_MAX_REPLICAS = 15

# Mapping helpers
_METRIC_TO_STR = {
    MetricEnum.CPU: "cpu",
    MetricEnum.MEMORY: "memory",
}
SUPPORTED_METRIC_STRINGS = tuple(_METRIC_TO_STR.values())

def metric_to_str(metric: MetricEnum) -> str:
    return _METRIC_TO_STR[metric]

def parse_metric(metric_value: str | None) -> MetricEnum:
    if not metric_value:
        return MetricEnum.CPU
    value = str(metric_value).strip().lower()
    if value == "memory":
        return MetricEnum.MEMORY
    return MetricEnum.CPU


