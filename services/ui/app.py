import os
from typing import Any, Dict

from flask import Flask, render_template, request, jsonify
import requests
from services.common.logging_config import configure_logging, get_logger


def create_app() -> Flask:
    app = Flask(__name__, static_folder='static')

    configure_logging()
    role = os.getenv("ROLE", "ui")
    logger = get_logger(role, name="ui")

    docker_service_url = os.getenv("DOCKER_SERVICE_URL", "http://docker-service:5004")

    @app.get("/")
    def index() -> Any:
        return render_template("index.html")

    @app.get("/api/events")
    def api_events() -> Any:
        """Proxy events API calls to docker-service."""
        try:
            # Forward all query parameters to the docker-service
            params = request.args.to_dict()
            resp = requests.get(f"{docker_service_url}/api/events", params=params, timeout=10)
            resp.raise_for_status()
            return jsonify(resp.json())
        except Exception as e:
            logger.warning(f"fetch events failed: {e}")
            return jsonify([])

    @app.get("/api/services")
    def api_services() -> Any:
        """Proxy services API calls to docker-service."""
        try:
            resp = requests.get(f"{docker_service_url}/api/services", timeout=10)
            resp.raise_for_status()
            return jsonify(resp.json())
        except Exception as e:
            logger.warning(f"fetch services failed: {e}")
            return jsonify([])

    @app.get("/api/stats")
    def api_stats() -> Any:
        """Proxy stats API calls to docker-service."""
        try:
            resp = requests.get(f"{docker_service_url}/api/stats", timeout=10)
            resp.raise_for_status()
            return jsonify(resp.json())
        except Exception as e:
            logger.warning(f"fetch stats failed: {e}")
            return jsonify({"error": str(e)})

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5005")))
