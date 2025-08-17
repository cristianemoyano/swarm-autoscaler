import os
import sys
import subprocess

ROLE = os.getenv("ROLE", "service-registry").lower()
PORT = os.getenv("PORT")

# Default ports per role (can be overridden by PORT env)
DEFAULT_PORTS = {
    "service-registry": "5001",
    "autoscaler": "5003",
    "docker-service": "5004",
    "ui": "5005",
}

MODULES = {
    "service-registry": "services.service_registry.app:app",
    "autoscaler": "services.autoscaler.app:app",
    "docker-service": "services.docker_service.app:app",
    "ui": "services.ui.app:app",
}

if ROLE not in MODULES:
    print(f"Unknown ROLE '{ROLE}'. Must be one of: {', '.join(MODULES.keys())}", file=sys.stderr)
    sys.exit(1)

module = MODULES[ROLE]
port = PORT or DEFAULT_PORTS[ROLE]

cmd = [
    "gunicorn",
    "-w", "1",
    "-b", f"0.0.0.0:{port}",
    module,
]

# Replace the current process with gunicorn
os.execvp(cmd[0], cmd)
