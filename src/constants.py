"""Centralized constants for labels, metrics, and other string literals."""

# Metrics
METRIC_CPU = "cpu"
METRIC_MEMORY = "memory"
SUPPORTED_METRICS = (METRIC_CPU, METRIC_MEMORY)

# Service labels
LABEL_AUTOSCALE = "swarm.autoscale"
LABEL_MAX_REPLICAS = "swarm.autoscale.max"
LABEL_MIN_REPLICAS = "swarm.autoscale.min"
LABEL_DISABLE_MANUAL_REPLICAS = "swarm.autoscale.disable-manual-replicas"
LABEL_PERCENTAGE_MAX = "swarm.autoscale.percentage-max"
LABEL_PERCENTAGE_MIN = "swarm.autoscale.percentage-min"
LABEL_DECREASE_MODE = "swarm.autoscale.decrease-mode"
LABEL_METRIC = "swarm.autoscale.metric"


