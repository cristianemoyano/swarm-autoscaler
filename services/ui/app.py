import os
from typing import Any, Dict

from flask import Flask, render_template
import requests
from services.common.logging_config import configure_logging, get_logger


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging()
    role = os.getenv("ROLE", "ui")
    logger = get_logger(role, name="ui")

    docker_service_url = os.getenv("DOCKER_SERVICE_URL", "http://docker-service:5004")

    @app.get("/")
    def index() -> Any:
        try:
            resp = requests.get(f"{docker_service_url}/events", timeout=10)
            resp.raise_for_status()
            events = resp.json()
        except Exception as e:
            logger.warning(f"fetch events failed: {e}")
            events = []
        return render_template("index.html", events=events)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5005")))
