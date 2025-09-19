import os
import time
import threading
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
import requests
from services.common.logging_config import configure_logging, get_logger


def create_app() -> Flask:
    app = Flask(__name__)

    configure_logging()
    role = os.getenv("ROLE", "autoscaler")
    logger = get_logger(role, name="autoscaler")

    # Configuration
    docker_service_url = os.getenv("DOCKER_SERVICE_URL", "http://docker-service:5004")
    service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://service-registry:5001")
    cooldown_sec = int(os.getenv("SCALE_COOLDOWN_SEC", "60"))
    poll_interval_sec = int(os.getenv("POLL_INTERVAL_SEC", "30"))
    async_scale = os.getenv("ASYNC_SCALE", "true").lower() in ("1", "true", "yes")

    last_scaled_at: Dict[str, float] = {}
    running = True

    def should_scale(service_name: str) -> bool:
        now = time.time()
        ts = last_scaled_at.get(service_name, 0)
        return (now - ts) >= cooldown_sec

    def record_scaled(service_name: str) -> None:
        last_scaled_at[service_name] = time.time()

    def _do_scale_request(scale_payload: Dict[str, Any]) -> None:
        service_name = scale_payload.get("service_name", "")
        try:
            resp = requests.post(f"{docker_service_url}/scale", json=scale_payload, timeout=15)
            resp.raise_for_status()
            logger.info(
                f"scaled (async) service={service_name} to={scale_payload.get('to_replicas')} reason='{scale_payload.get('reason')}'"
            )
        except Exception as e:
            logger.error(f"async scale request failed service={service_name} error={e}")

    def evaluate_service(service: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        """Evaluate a single service for scaling decisions."""
        service_name = service.get("name")
        current_replicas = int(service.get("current_replicas", 1))
        thresholds = service.get("thresholds", {"cpu": 70.0, "memory": 70.0})
        metric_type = service.get("metric", "cpu")
        min_replicas = int(service.get("min_replicas", 1))
        max_replicas = int(service.get("max_replicas", max(2, current_replicas)))

        if not service_name:
            logger.warning("service missing name, skipping evaluation")
            return

        # Compute percent values
        cpu_pct = float(metrics.get("cpu_pct", 0.0))
        mem_bytes = float(metrics.get("memory_bytes", 0.0))
        mem_pct = 0.0
        mem_limit = 0.0
        try:
            # Get memory limit from labels
            mem_limit = float(service.get("labels", {}).get("autoscaler.memory.limit_bytes", 0))
            if mem_limit > 0:
                mem_pct = (mem_bytes / mem_limit) * 100.0
            elif metric_type == "memory":
                logger.warning(
                    f"service {service_name} uses memory metric but has no memory limit configured "
                    f"(autoscaler.memory.limit_bytes=0), memory percentage will be 0%"
                )
        except Exception as e:
            logger.warning(f"error calculating memory percentage for {service_name}: {e}")
            mem_pct = 0.0

        # Log service configuration and current metrics
        logger.info(
            f"evaluating service={service_name} metric={metric_type} replicas={current_replicas} "
            f"cpu={cpu_pct:.1f}% mem={mem_bytes/1024/1024:.1f}MB/{mem_limit/1024/1024:.1f}MB "
            f"mem_pct={mem_pct:.1f}% threshold={thresholds.get(metric_type, 70.0)}%"
        )

        desired = current_replicas
        reason = "no-op"

        if metric_type == "cpu":
            if cpu_pct > float(thresholds.get("cpu", 70.0)):
                desired = min(current_replicas + 1, max_replicas)
                reason = f"cpu {cpu_pct:.1f}% > {thresholds.get('cpu')}%"
            elif cpu_pct < float(thresholds.get("cpu", 70.0)) * 0.5:
                desired = max(current_replicas - 1, min_replicas)
                reason = f"cpu {cpu_pct:.1f}% < half threshold"
        elif metric_type == "memory" and mem_pct > 0:
            if mem_pct > float(thresholds.get("memory", 70.0)):
                desired = min(current_replicas + 1, max_replicas)
                reason = f"mem {mem_pct:.1f}% > {thresholds.get('memory')}%"
            elif mem_pct < float(thresholds.get("memory", 70.0)) * 0.5:
                desired = max(current_replicas - 1, min_replicas)
                reason = f"mem {mem_pct:.1f}% < half threshold"

        if desired == current_replicas:
            if metric_type == "memory":
                logger.debug(
                    f"no-op service={service_name} replicas={current_replicas} "
                    f"mem={mem_pct:.1f}% threshold={thresholds.get('memory')}% "
                    f"half_threshold={float(thresholds.get('memory', 70.0)) * 0.5:.1f}%"
                )
            else:
                logger.debug(
                    f"no-op service={service_name} replicas={current_replicas} "
                    f"cpu={cpu_pct:.1f}% threshold={thresholds.get('cpu')}% "
                    f"half_threshold={float(thresholds.get('cpu', 70.0)) * 0.5:.1f}%"
                )
            return

        if not should_scale(service_name):
            logger.debug(f"cooldown service={service_name} replicas={current_replicas}")
            return

        scale_payload = {
            "service_name": service_name,
            "from_replicas": current_replicas,
            "to_replicas": desired,
            "reason": reason,
        }

        if async_scale:
            # Optimistically set cooldown to avoid bursts while the request is in flight
            record_scaled(service_name)
            threading.Thread(target=_do_scale_request, args=(scale_payload,), daemon=True).start()
            logger.info(f"enqueued scale service={service_name} from={current_replicas} to={desired} reason='{reason}'")
        else:
            try:
                resp = requests.post(f"{docker_service_url}/scale", json=scale_payload, timeout=15)
                resp.raise_for_status()
                record_scaled(service_name)
                logger.info(f"scaled service={service_name} from={current_replicas} to={desired} reason='{reason}'")
            except Exception as e:
                logger.error(f"scale request failed service={service_name} error={e}")

    def autoscaler_polling_loop() -> None:
        """Background loop that polls Service Registry and evaluates services."""
        logger.info(f"starting autoscaler polling loop with interval={poll_interval_sec}s")
        logger.info(f"autoscaler configuration: cooldown={cooldown_sec}s async_scale={async_scale}")
        
        while running:
            try:
                # Get all services from Service Registry
                services_resp = requests.get(f"{service_registry_url}/services", timeout=10)
                services_resp.raise_for_status()
                services_data = services_resp.json()
                
                services = services_data.get("services", [])
                logger.debug(f"polling {len(services)} services from service registry")
                
                # Evaluate each service
                for service in services:
                    try:
                        service_name = service.get("name")
                        if not service_name:
                            continue
                            
                        # Get metrics for this service
                        metrics_resp = requests.get(f"{service_registry_url}/services/{service_name}/metrics", timeout=10)
                        if metrics_resp.status_code == 200:
                            metrics_data = metrics_resp.json()
                            metrics = metrics_data.get("metrics", {})
                            
                            # Log metrics source and values
                            source = metrics.get("source", "unknown")
                            cpu_pct = metrics.get("cpu_pct", 0.0)
                            mem_bytes = metrics.get("memory_bytes", 0.0)
                            logger.debug(
                                f"metrics for {service_name}: source={source} "
                                f"cpu={cpu_pct:.1f}% mem={mem_bytes/1024/1024:.1f}MB"
                            )
                            
                            # Evaluate the service
                            evaluate_service(service, metrics)
                        else:
                            logger.warning(f"failed to get metrics for {service_name}: {metrics_resp.status_code}")
                            
                    except Exception as e:
                        logger.error(f"error evaluating service {service.get('name', 'unknown')}: {e}")
                        continue
                
                # Wait for next poll
                time.sleep(poll_interval_sec)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"service registry polling error: {e}")
                time.sleep(min(poll_interval_sec * 2, 60))  # Exponential backoff, max 60s
            except Exception as e:
                logger.error(f"autoscaler polling loop error: {e}")
                time.sleep(min(poll_interval_sec * 2, 60))

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    def status() -> Dict[str, Any]:
        """Get autoscaler status and configuration."""
        return {
            "status": "running",
            "service_registry_url": service_registry_url,
            "docker_service_url": docker_service_url,
            "poll_interval_sec": poll_interval_sec,
            "cooldown_sec": cooldown_sec,
            "async_scale": async_scale,
            "last_scaled_services": list(last_scaled_at.keys()),
            "timestamp": int(time.time())
        }

    @app.post("/evaluate")
    def evaluate() -> Any:
        """Manual evaluation endpoint (for testing)."""
        data = request.get_json(silent=True) or {}
        service = data.get("service") or {}
        metrics = data.get("metrics") or {}
        
        evaluate_service(service, metrics)
        
        return jsonify({
            "status": "evaluated",
            "service": service.get("name"),
            "timestamp": int(time.time())
        })

    # Start background polling loop
    polling_thread = threading.Thread(target=autoscaler_polling_loop, daemon=True, name="autoscaler-polling")
    polling_thread.start()
    logger.info("autoscaler background polling started")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5003")))
