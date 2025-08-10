import os

# Defaults
DEFAULT_MIN_PERCENTAGE = 25.0
DEFAULT_MAX_PERCENTAGE = 85.0
DEFAULT_DISCOVERY_DNSNAME = "tasks.autoscaler"
DEFAULT_CHECK_INTERVAL = 60 * 5  # 5 minutes

# Public settings loaded from environment
MIN_PERCENTAGE = float(os.getenv("AUTOSCALER_MIN_PERCENTAGE", DEFAULT_MIN_PERCENTAGE))
MAX_PERCENTAGE = float(os.getenv("AUTOSCALER_MAX_PERCENTAGE", DEFAULT_MAX_PERCENTAGE))
DISCOVERY_DNSNAME = os.getenv("AUTOSCALER_DNSNAME", DEFAULT_DISCOVERY_DNSNAME)
CHECK_INTERVAL = int(os.getenv("AUTOSCALER_INTERVAL", DEFAULT_CHECK_INTERVAL))

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "on"):  # truthy
        return True
    if s in ("0", "false", "no", "off", ""):  # falsy
        return False
    return default

# Dry run is enabled only for explicit truthy values
DRY_RUN = _env_bool("AUTOSCALER_DRYRUN", False)


