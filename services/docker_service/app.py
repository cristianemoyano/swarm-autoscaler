import os
import pathlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

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

    def get_time_range_filter(time_range: str) -> Optional[datetime]:
        """Convert time range string to datetime filter."""
        now = datetime.utcnow()
        
        if time_range == '5m':
            return now - timedelta(minutes=5)
        elif time_range == '15m':
            return now - timedelta(minutes=15)
        elif time_range == '1h':
            return now - timedelta(hours=1)
        elif time_range == '6h':
            return now - timedelta(hours=6)
        elif time_range == '1d':
            return now - timedelta(days=1)
        elif time_range == '7d':
            return now - timedelta(days=7)
        else:
            return None

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/status")
    def api_status() -> Dict[str, Any]:
        """Get API status and statistics."""
        try:
            total_events = ScalingEvent.query.count()
            recent_events = ScalingEvent.query.filter(
                ScalingEvent.created_at >= datetime.utcnow() - timedelta(hours=1)
            ).count()
            
            # Get unique services
            services = db.session.query(ScalingEvent.service_name).distinct().all()
            unique_services = [s[0] for s in services]
            
            return {
                "status": "ok",
                "total_events": total_events,
                "recent_events_1h": recent_events,
                "unique_services": unique_services,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        except Exception as e:
            logger.error(f"Error getting API status: {e}")
            return {"status": "error", "message": str(e)}

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
        """Enhanced events endpoint with filtering and pagination."""
        try:
            # Get query parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 50, type=int)
            service_name = request.args.get('service')
            time_range = request.args.get('range')
            start_date = request.args.get('start')
            end_date = request.args.get('end')
            sort_by = request.args.get('sort_by', 'created_at')
            sort_order = request.args.get('sort_order', 'desc')
            
            # Validate pagination
            page = max(1, page)
            per_page = min(100, max(1, per_page))  # Limit to 100 per page
            
            # Build query
            query = ScalingEvent.query
            
            # Apply service filter
            if service_name:
                query = query.filter(ScalingEvent.service_name == service_name)
            
            # Apply time range filter
            if time_range:
                time_filter = get_time_range_filter(time_range)
                if time_filter:
                    query = query.filter(ScalingEvent.created_at >= time_filter)
            
            # Apply custom date range
            if start_date and end_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(
                        ScalingEvent.created_at >= start_dt,
                        ScalingEvent.created_at <= end_dt
                    )
                except ValueError:
                    pass  # Invalid date format, ignore filter
            
            # Apply sorting
            if sort_by == 'id':
                order_column = ScalingEvent.id
            elif sort_by == 'service_name':
                order_column = ScalingEvent.service_name
            elif sort_by == 'from_replicas':
                order_column = ScalingEvent.from_replicas
            elif sort_by == 'to_replicas':
                order_column = ScalingEvent.to_replicas
            elif sort_by == 'reason':
                order_column = ScalingEvent.reason
            else:
                order_column = ScalingEvent.created_at
            
            if sort_order == 'asc':
                query = query.order_by(order_column.asc())
            else:
                query = query.order_by(order_column.desc())
            
            # Get total count for pagination
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            events = query.offset(offset).limit(per_page).all()
            
            # Format response
            events_data = [
                {
                    "id": event.id,
                    "service_name": event.service_name,
                    "from_replicas": event.from_replicas,
                    "to_replicas": event.to_replicas,
                    "reason": event.reason,
                    "created_at": event.created_at.isoformat() + "Z",
                }
                for event in events
            ]
            
            return jsonify({
                "events": events_data,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_count,
                    "pages": (total_count + per_page - 1) // per_page
                },
                "filters": {
                    "service": service_name,
                    "time_range": time_range,
                    "start_date": start_date,
                    "end_date": end_date,
                    "sort_by": sort_by,
                    "sort_order": sort_order
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/events")
    def api_events() -> Any:
        """API endpoint for the UI - returns events in the format expected by the frontend."""
        try:
            # Get query parameters
            time_range = request.args.get('range', '1d')
            start_date = request.args.get('start')
            end_date = request.args.get('end')
            service_name = request.args.get('service')
            
            # Build query
            query = ScalingEvent.query
            
            # Apply service filter
            if service_name:
                query = query.filter(ScalingEvent.service_name == service_name)
            
            # Apply time range filter
            if start_date and end_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    query = query.filter(
                        ScalingEvent.created_at >= start_dt,
                        ScalingEvent.created_at <= end_dt
                    )
                except ValueError:
                    pass
            elif time_range:
                time_filter = get_time_range_filter(time_range)
                if time_filter:
                    query = query.filter(ScalingEvent.created_at >= time_filter)
            
            # Get events ordered by most recent
            events = query.order_by(ScalingEvent.created_at.desc()).limit(1000).all()
            
            # Format response for frontend
            events_data = [
                {
                    "id": event.id,
                    "service_name": event.service_name,
                    "from_replicas": event.from_replicas,
                    "to_replicas": event.to_replicas,
                    "reason": event.reason,
                    "created_at": event.created_at.isoformat() + "Z",
                }
                for event in events
            ]
            
            return jsonify(events_data)
            
        except Exception as e:
            logger.error(f"Error fetching events for API: {e}")
            return jsonify([])

    @app.get("/api/services")
    def api_services() -> Any:
        """Get list of unique services that have scaling events."""
        try:
            services = db.session.query(ScalingEvent.service_name).distinct().all()
            return jsonify([s[0] for s in services])
        except Exception as e:
            logger.error(f"Error fetching services: {e}")
            return jsonify([])

    @app.get("/api/stats")
    def api_stats() -> Any:
        """Get scaling statistics."""
        try:
            # Total events
            total_events = ScalingEvent.query.count()
            
            # Events in last 24 hours
            last_24h = ScalingEvent.query.filter(
                ScalingEvent.created_at >= datetime.utcnow() - timedelta(days=1)
            ).count()
            
            # Events in last hour
            last_1h = ScalingEvent.query.filter(
                ScalingEvent.created_at >= datetime.utcnow() - timedelta(hours=1)
            ).count()
            
            # Unique services
            unique_services = db.session.query(ScalingEvent.service_name).distinct().count()
            
            # Most active service
            most_active = db.session.query(
                ScalingEvent.service_name,
                db.func.count(ScalingEvent.id).label('count')
            ).group_by(ScalingEvent.service_name).order_by(
                db.func.count(ScalingEvent.id).desc()
            ).first()
            
            return jsonify({
                "total_events": total_events,
                "events_24h": last_24h,
                "events_1h": last_1h,
                "unique_services": unique_services,
                "most_active_service": {
                    "name": most_active[0] if most_active else None,
                    "events": most_active[1] if most_active else 0
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return jsonify({"error": str(e)}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5004")))
