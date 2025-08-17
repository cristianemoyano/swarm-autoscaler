import os
import pathlib
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import docker
from services.common.logging_config import configure_logging, get_logger


db = SQLAlchemy()


class ScalingEvent(db.Model):  # type: ignore
    __tablename__ = "scaling_events"

    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(255), nullable=False)
    from_replicas = db.Column(db.Integer, nullable=False)
    to_replicas = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging()
    role = os.getenv("ROLE", "docker-service")
    logger = get_logger(role, name="docker_service")

    database_url = os.getenv("DATABASE_URL", "sqlite:////data/events.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Ensure data dir exists for sqlite
    if database_url.startswith("sqlite"):
        pathlib.Path("/data").mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    docker_base_url = os.getenv("DOCKER_BASE_URL", "unix:///var/run/docker.sock")
    client = docker.from_env() if docker_base_url.startswith("unix") else docker.DockerClient(base_url=docker_base_url)

    def scale_service(service_name: str, to_replicas: int) -> None:
        service = client.services.get(service_name)
        try:
            # Prefer scale() if available
            service.scale(to_replicas)  # type: ignore[attr-defined]
        except Exception:
            # Fallback to update spec
            spec = service.attrs.get("Spec", {})
            spec.setdefault("Mode", {}).setdefault("Replicated", {})["Replicas"] = to_replicas
            service.update(**spec)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/scale")
    def scale() -> Any:
        body = request.get_json(silent=True) or {}
        service_name = body.get("service_name")
        from_replicas = int(body.get("from_replicas", 0))
        to_replicas = int(body.get("to_replicas", 0))
        reason = body.get("reason", "")
        if not service_name or to_replicas <= 0:
            return jsonify({"error": "invalid payload"}), 400
        try:
            scale_service(service_name, to_replicas)
            event = ScalingEvent(
                service_name=service_name,
                from_replicas=from_replicas,
                to_replicas=to_replicas,
                reason=reason,
            )
            db.session.add(event)
            db.session.commit()
            logger.info(f"scaled service={service_name} to={to_replicas} reason='{reason}'")
            return jsonify({"status": "ok", "service": service_name, "to": to_replicas})
        except Exception as e:
            db.session.rollback()
            logger.error(f"scale error service={service_name} error={e}")
            return jsonify({"error": str(e)}), 500

    @app.get("/events")
    def list_events() -> Any:
        rows: List[ScalingEvent] = (
            ScalingEvent.query.order_by(ScalingEvent.created_at.desc()).limit(500).all()
        )
        return jsonify([
            {
                "id": r.id,
                "service_name": r.service_name,
                "from_replicas": r.from_replicas,
                "to_replicas": r.to_replicas,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() + "Z",
            }
            for r in rows
        ])

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5004")))
