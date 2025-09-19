"""
Cache Manager

This module handles in-memory caching of discovered services and provides
periodic refresh functionality to keep the cache up-to-date.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Callable
from services.common.logging_config import get_logger


class CacheManager:
    """Manages in-memory cache of discovered services."""
    
    def __init__(self, docker_adapter: Any, refresh_interval_sec: int = 30):
        self.logger = get_logger("service-registry", name="cache-manager")
        self.docker_adapter = docker_adapter
        self.refresh_interval_sec = refresh_interval_sec
        
        # Cache state
        self._cache_lock = threading.RLock()
        self._services_cache: List[Dict[str, Any]] = []
        self._metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._last_refresh = 0.0
        self._cache_version = 0
        
        # Event callbacks
        self._on_services_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None
        
        self.logger.info(f"initialized cache manager with refresh_interval={refresh_interval_sec}s")
    
    def set_services_changed_callback(self, callback: Callable[[List[Dict[str, Any]]], None]) -> None:
        """Set callback to be called when services change."""
        self._on_services_changed = callback
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all cached services."""
        with self._cache_lock:
            return self._services_cache.copy()
    
    def get_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific service by name from cache."""
        with self._cache_lock:
            for service in self._services_cache:
                if service.get("name") == service_name:
                    return service.copy()
        return None
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get cached metrics for a service."""
        with self._cache_lock:
            return self._metrics_cache.get(service_name)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                "services_count": len(self._services_cache),
                "metrics_count": len(self._metrics_cache),
                "last_refresh": self._last_refresh,
                "cache_version": self._cache_version,
                "refresh_interval_sec": self.refresh_interval_sec
            }
    
    def refresh_services(self) -> None:
        """Refresh the services cache from Docker Swarm."""
        try:
            new_services = self.docker_adapter.get_all_services()
            
            with self._cache_lock:
                # Check if services have actually changed
                services_changed = self._services_have_changed(new_services)
                
                if services_changed:
                    self._services_cache = new_services
                    self._cache_version += 1
                    self._last_refresh = time.time()
                    
                    self.logger.info(
                        f"services cache refreshed: {len(new_services)} services, "
                        f"version={self._cache_version}"
                    )
                    
                    # Notify callback if set
                    if self._on_services_changed:
                        try:
                            self._on_services_changed(new_services)
                        except Exception as e:
                            self.logger.error(f"error in services changed callback: {e}")
                else:
                    self.logger.debug("services cache unchanged, skipping update")
                    
        except Exception as e:
            self.logger.error(f"failed to refresh services cache: {e}")
    
    def refresh_metrics(self, service_names: Optional[List[str]] = None) -> None:
        """Refresh metrics for specified services or all services."""
        try:
            services_to_update = service_names or [s.get("name") for s in self._services_cache]
            updated_count = 0
            
            for service_name in services_to_update:
                if not service_name:
                    continue
                
                metrics = self.docker_adapter.get_service_metrics(service_name)
                if metrics:
                    with self._cache_lock:
                        self._metrics_cache[service_name] = metrics
                        updated_count += 1
                        
                        # Log memory metrics if available
                        if "memory_bytes" in metrics:
                            mem_bytes = metrics.get("memory_bytes", 0)
                            cpu_pct = metrics.get("cpu_pct", 0.0)
                            self.logger.debug(
                                f"cached metrics for {service_name}: "
                                f"cpu={cpu_pct:.1f}% mem={mem_bytes/1024/1024:.1f}MB"
                            )
            
            self.logger.debug(f"refreshed metrics for {updated_count}/{len(services_to_update)} services")
            
        except Exception as e:
            self.logger.error(f"failed to refresh metrics: {e}")
    
    def _services_have_changed(self, new_services: List[Dict[str, Any]]) -> bool:
        """Check if the new services list differs from the cached one."""
        if len(new_services) != len(self._services_cache):
            return True
        
        # Create a set of service IDs for comparison
        current_ids = {s.get("id") for s in self._services_cache}
        new_ids = {s.get("id") for s in new_services}
        
        if current_ids != new_ids:
            return True
        
        # Check for changes in replica counts or other important fields
        current_by_id = {s.get("id"): s for s in self._services_cache}
        new_by_id = {s.get("id"): s for s in new_services}
        
        for service_id in current_ids:
            current = current_by_id.get(service_id, {})
            new = new_by_id.get(service_id, {})
            
            # Compare important fields
            if (current.get("current_replicas") != new.get("current_replicas") or
                current.get("updated_at") != new.get("updated_at")):
                return True
        
        return False
    
    def start_background_refresh(self) -> None:
        """Start background thread for periodic cache refresh."""
        def refresh_loop():
            self.logger.info("starting background cache refresh loop")
            while True:
                try:
                    self.refresh_services()
                    time.sleep(self.refresh_interval_sec)
                except Exception as e:
                    self.logger.error(f"error in refresh loop: {e}")
                    time.sleep(5)  # Shorter sleep on error
        
        thread = threading.Thread(target=refresh_loop, daemon=True, name="cache-refresh")
        thread.start()
        self.logger.info("background cache refresh started")
    
    def handle_docker_event(self, action: str, service_id: str) -> None:
        """Handle Docker events to trigger immediate cache refresh."""
        self.logger.info(f"docker event received: {action} for service {service_id}")
        
        # Trigger immediate refresh for service events
        if action in ("create", "update", "remove"):
            self.refresh_services()
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        with self._cache_lock:
            self._services_cache.clear()
            self._metrics_cache.clear()
            self._cache_version += 1
            self._last_refresh = time.time()
        
        self.logger.info("cache cleared")
