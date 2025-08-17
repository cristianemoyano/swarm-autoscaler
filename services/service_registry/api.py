"""
REST API

This module provides the REST API endpoints for the Service Registry,
with HTTP/2 support using Hypercorn.
"""

import os
import time
from typing import Any, Dict, List, Optional
from flask import Flask, jsonify, request
from services.common.logging_config import get_logger


def create_api_app(cache_manager: Any, publisher: Any) -> Flask:
    """Create and configure the Flask API application."""
    app = Flask(__name__)
    
    logger = get_logger("service-registry", name="api")
    
    @app.route("/health", methods=["GET"])
    def health() -> Dict[str, Any]:
        """Health check endpoint."""
        cache_stats = cache_manager.get_cache_stats()
        
        health_status = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "service": "service-registry",
            "cache": cache_stats,
            "publisher": {
                "enabled": publisher.enabled,
                "connected": publisher.is_connected()
            }
        }
        
        # Determine overall health
        if cache_stats["services_count"] == 0 and cache_stats["last_refresh"] == 0:
            health_status["status"] = "degraded"
            health_status["warnings"] = ["no services discovered yet"]
        
        return jsonify(health_status)
    
    @app.route("/services", methods=["GET"])
    def get_services() -> Any:
        """Get all discovered services."""
        try:
            services = cache_manager.get_all_services()
            cache_stats = cache_manager.get_cache_stats()
            
            response = {
                "services": services,
                "metadata": {
                    "count": len(services),
                    "cache_version": cache_stats["cache_version"],
                    "last_refresh": cache_stats["last_refresh"],
                    "timestamp": int(time.time())
                }
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"error getting services: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/services/<service_name>", methods=["GET"])
    def get_service(service_name: str) -> Any:
        """Get a specific service by name."""
        try:
            service = cache_manager.get_service_by_name(service_name)
            
            if not service:
                return jsonify({"error": "service not found"}), 404
            
            return jsonify({
                "service": service,
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error getting service {service_name}: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/services/<service_name>/metrics", methods=["GET"])
    def get_service_metrics(service_name: str) -> Any:
        """Get metrics for a specific service."""
        try:
            # Check if service exists
            service = cache_manager.get_service_by_name(service_name)
            if not service:
                return jsonify({"error": "service not found"}), 404
            
            # Get cached metrics
            metrics = cache_manager.get_service_metrics(service_name)
            
            if not metrics:
                return jsonify({"error": "metrics not available"}), 404
            
            return jsonify({
                "service_name": service_name,
                "metrics": metrics,
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error getting metrics for {service_name}: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/services/<service_name>/metrics", methods=["POST"])
    def refresh_service_metrics(service_name: str) -> Any:
        """Force refresh metrics for a specific service."""
        try:
            # Check if service exists
            service = cache_manager.get_service_by_name(service_name)
            if not service:
                return jsonify({"error": "service not found"}), 404
            
            # Refresh metrics
            cache_manager.refresh_metrics([service_name])
            
            # Get updated metrics
            metrics = cache_manager.get_service_metrics(service_name)
            
            if metrics and publisher.enabled:
                publisher.publish_metrics_updated(service_name, metrics)
            
            return jsonify({
                "service_name": service_name,
                "metrics": metrics,
                "refreshed": True,
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error refreshing metrics for {service_name}: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/cache/refresh", methods=["POST"])
    def refresh_cache() -> Any:
        """Force refresh the services cache."""
        try:
            cache_manager.refresh_services()
            cache_stats = cache_manager.get_cache_stats()
            
            return jsonify({
                "message": "cache refreshed",
                "cache_stats": cache_stats,
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error refreshing cache: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/cache/stats", methods=["GET"])
    def get_cache_stats() -> Any:
        """Get cache statistics."""
        try:
            stats = cache_manager.get_cache_stats()
            return jsonify({
                "cache_stats": stats,
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error getting cache stats: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/cache/clear", methods=["POST"])
    def clear_cache() -> Any:
        """Clear the cache."""
        try:
            cache_manager.clear_cache()
            return jsonify({
                "message": "cache cleared",
                "timestamp": int(time.time())
            })
            
        except Exception as e:
            logger.error(f"error clearing cache: {e}")
            return jsonify({"error": "internal server error"}), 500
    
    @app.route("/events", methods=["GET"])
    def get_events_info() -> Any:
        """Get information about available events."""
        events_info = {
            "available_events": [
                "services.updated",
                "service.added", 
                "service.removed",
                "service.updated",
                "metrics.{service_name}",
                "health.check"
            ],
            "exchange": publisher.exchange_name if publisher.enabled else None,
            "enabled": publisher.enabled,
            "connected": publisher.is_connected()
        }
        
        return jsonify(events_info)
    
    @app.route("/", methods=["GET"])
    def root() -> Any:
        """Root endpoint with API information."""
        return jsonify({
            "service": "Service Registry",
            "version": "1.0.0",
            "description": "Unified service discovery and caching for Docker Swarm",
            "endpoints": {
                "health": "/health",
                "services": "/services",
                "service": "/services/{name}",
                "metrics": "/services/{name}/metrics",
                "cache": "/cache/*",
                "events": "/events"
            },
            "timestamp": int(time.time())
        })
    
    return app
