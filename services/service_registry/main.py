"""
Service Registry Main Application

This is the main entry point for the Service Registry microservice.
It bootstraps all components and runs the HTTP/2 server.
"""

import os
import signal
import sys
import threading
import time
from typing import Any

from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio

from services.common.logging_config import configure_logging, get_logger
from .docker_adapter import DockerSwarmAdapter
from .cache_manager import CacheManager
from .publisher import Publisher
from .api import create_api_app


class ServiceRegistry:
    """Main Service Registry application."""
    
    def __init__(self):
        # Configure logging first
        configure_logging()
        self.logger = get_logger("service-registry", name="main")
        
        # Configuration
        self.port = int(os.getenv("PORT", "5001"))
        self.host = os.getenv("HOST", "0.0.0.0")
        self.refresh_interval = int(os.getenv("REFRESH_INTERVAL_SEC", "30"))
        self.metrics_refresh_interval = int(os.getenv("METRICS_REFRESH_INTERVAL_SEC", "60"))
        
        # Initialize components
        self.docker_adapter = DockerSwarmAdapter()
        self.cache_manager = CacheManager(self.docker_adapter, self.refresh_interval)
        self.publisher = Publisher()
        
        # Create Flask app
        self.app = create_api_app(self.cache_manager, self.publisher)
        
        # Server state
        self.server = None
        self.running = False
        
        self.logger.info("service registry initialized")
    
    def setup_event_handlers(self) -> None:
        """Setup event handlers and callbacks."""
        # Set up services changed callback
        self.cache_manager.set_services_changed_callback(self._on_services_changed)
        
        # Set up Docker events handler
        def docker_event_handler(action: str, service_id: str) -> None:
            self.cache_manager.handle_docker_event(action, service_id)
        
        # Start Docker events watcher in background
        docker_events_thread = threading.Thread(
            target=self.docker_adapter.watch_events,
            args=(docker_event_handler,),
            daemon=True,
            name="docker-events"
        )
        docker_events_thread.start()
        
        self.logger.info("event handlers configured")
    
    def _on_services_changed(self, services: list) -> None:
        """Handle services changed event."""
        try:
            if self.publisher.enabled:
                self.publisher.publish_services_updated(services)
                self.logger.info(f"published services.updated event for {len(services)} services")
        except Exception as e:
            self.logger.error(f"error publishing services changed event: {e}")
    
    def start_background_tasks(self) -> None:
        """Start background tasks."""
        # Start cache refresh loop
        self.cache_manager.start_background_refresh()
        
        # Start metrics refresh loop
        def metrics_refresh_loop():
            self.logger.info("starting background metrics refresh loop")
            while self.running:
                try:
                    time.sleep(self.metrics_refresh_interval)
                    if self.running:
                        self.cache_manager.refresh_metrics()
                except Exception as e:
                    self.logger.error(f"error in metrics refresh loop: {e}")
                    time.sleep(5)
        
        metrics_thread = threading.Thread(
            target=metrics_refresh_loop,
            daemon=True,
            name="metrics-refresh"
        )
        metrics_thread.start()
        
        # Start health check publisher
        def health_check_loop():
            self.logger.info("starting health check publisher loop")
            while self.running:
                try:
                    time.sleep(300)  # Every 5 minutes
                    if self.running and self.publisher.enabled:
                        self.publisher.publish_health_check()
                except Exception as e:
                    self.logger.error(f"error in health check loop: {e}")
                    time.sleep(60)
        
        health_thread = threading.Thread(
            target=health_check_loop,
            daemon=True,
            name="health-check"
        )
        health_thread.start()
        
        self.logger.info("background tasks started")
    
    async def start_server(self) -> None:
        """Start the HTTP/2 server."""
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.worker_class = "asyncio"
        config.workers = 1  # Single worker for this service
        config.access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
        config.access_logger = self.logger.logger
        
        self.logger.info(f"starting server on {self.host}:{self.port}")
        self.server = await serve(self.app, config)
    
    def stop_server(self) -> None:
        """Stop the server and cleanup."""
        self.logger.info("stopping service registry")
        self.running = False
        
        # Close publisher connection
        if self.publisher:
            self.publisher.close()
        
        self.logger.info("service registry stopped")
    
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum: int, frame: Any) -> None:
            self.logger.info(f"received signal {signum}, shutting down gracefully")
            self.stop_server()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self) -> None:
        """Run the service registry."""
        try:
            self.running = True
            
            # Setup components
            self.setup_event_handlers()
            self.setup_signal_handlers()
            self.start_background_tasks()
            
            # Initial cache refresh
            self.logger.info("performing initial cache refresh")
            self.cache_manager.refresh_services()
            
            # Start server
            await self.start_server()
            
        except Exception as e:
            self.logger.error(f"error starting service registry: {e}")
            self.stop_server()
            raise


def main() -> None:
    """Main entry point."""
    try:
        registry = ServiceRegistry()
        asyncio.run(registry.run())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
