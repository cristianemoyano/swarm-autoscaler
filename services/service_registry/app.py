"""
Service Registry Flask App

Flask app wrapper for the Service Registry to be compatible with the entrypoint system.
This provides the full Service Registry functionality using all components.
"""

import os
import threading
import time
from typing import Any

from flask import Flask, jsonify
from services.common.logging_config import configure_logging, get_logger
from .docker_adapter import DockerSwarmAdapter
from .cache_manager import CacheManager
from .publisher import Publisher
from .api import create_api_app


def create_app() -> Flask:
    """Create the Service Registry Flask application."""
    # Configure logging
    configure_logging()
    logger = get_logger("service-registry", name="app")
    
    # Initialize components
    docker_adapter = DockerSwarmAdapter()
    refresh_interval = int(os.getenv("REFRESH_INTERVAL_SEC", "30"))
    metrics_refresh_interval = int(os.getenv("METRICS_REFRESH_INTERVAL_SEC", "60"))
    cache_manager = CacheManager(docker_adapter, refresh_interval)
    publisher = Publisher()
    
    # Create the API app
    app = create_api_app(cache_manager, publisher)
    
    # Setup background tasks
    def start_background_tasks():
        """Start background tasks in a separate thread."""
        try:
            # Set up services changed callback
            cache_manager.set_services_changed_callback(_on_services_changed)
            
            # Set up Docker events handler
            def docker_event_handler(action: str, service_id: str) -> None:
                cache_manager.handle_docker_event(action, service_id)
            
            # Start Docker events watcher in background
            docker_events_thread = threading.Thread(
                target=docker_adapter.watch_events,
                args=(docker_event_handler,),
                daemon=True,
                name="docker-events"
            )
            docker_events_thread.start()
            
            # Start cache refresh loop
            cache_manager.start_background_refresh()
            
            # Start metrics refresh loop
            def metrics_refresh_loop():
                while True:
                    try:
                        time.sleep(metrics_refresh_interval)  # Refresh metrics based on env var
                        cache_manager.refresh_metrics()
                    except Exception as e:
                        logger.error(f"error in metrics refresh loop: {e}")
                        time.sleep(5)
            
            metrics_thread = threading.Thread(
                target=metrics_refresh_loop,
                daemon=True,
                name="metrics-refresh"
            )
            metrics_thread.start()
            
            # Start health check publisher
            def health_check_loop():
                while True:
                    try:
                        time.sleep(300)  # Every 5 minutes
                        if publisher.enabled:
                            publisher.publish_health_check()
                    except Exception as e:
                        logger.error(f"error in health check loop: {e}")
                        time.sleep(60)
            
            health_thread = threading.Thread(
                target=health_check_loop,
                daemon=True,
                name="health-check"
            )
            health_thread.start()
            
            # Initial cache refresh
            logger.info("performing initial cache refresh")
            cache_manager.refresh_services()
            
            logger.info("background tasks started")
            
        except Exception as e:
            logger.error(f"error starting background tasks: {e}")
    
    def _on_services_changed(services: list) -> None:
        """Handle services changed event."""
        try:
            if publisher.enabled:
                publisher.publish_services_updated(services)
                logger.info(f"published services.updated event for {len(services)} services")
        except Exception as e:
            logger.error(f"error publishing services changed event: {e}")
    
    # Start background tasks in a separate thread
    background_thread = threading.Thread(target=start_background_tasks, daemon=True)
    background_thread.start()
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
