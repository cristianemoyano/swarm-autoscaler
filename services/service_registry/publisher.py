"""
Publisher

This module handles RabbitMQ integration for publishing service updates
and events to subscribers.
"""

import os
import json
import threading
import time
from typing import Any, Dict, List, Optional
import pika
from services.common.logging_config import get_logger


class Publisher:
    """Handles RabbitMQ publishing for service events."""
    
    def __init__(self):
        self.logger = get_logger("service-registry", name="publisher")
        
        # Configuration
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "")
        self.exchange_name = os.getenv("RABBITMQ_EXCHANGE", "service-registry")
        self.enabled = bool(self.rabbitmq_url)
        
        # Connection state
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._lock = threading.RLock()
        self._connected = False
        
        if self.enabled:
            self.logger.info(f"publisher initialized with exchange={self.exchange_name}")
        else:
            self.logger.info("publisher disabled (no RABBITMQ_URL)")
    
    def _ensure_connection(self) -> bool:
        """Ensure RabbitMQ connection is established."""
        if not self.enabled:
            return False
        
        with self._lock:
            if self._connected and self._connection and not self._connection.is_closed:
                return True
            
            try:
                # Parse connection parameters
                params = pika.URLParameters(self.rabbitmq_url)
                
                # Establish connection
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()
                
                # Declare exchange
                self._channel.exchange_declare(
                    exchange=self.exchange_name,
                    exchange_type='topic',
                    durable=True
                )
                
                self._connected = True
                self.logger.info("rabbitmq connection established")
                return True
                
            except Exception as e:
                self.logger.error(f"failed to establish rabbitmq connection: {e}")
                self._connected = False
                return False
    
    def _publish_message(self, routing_key: str, message: Dict[str, Any]) -> bool:
        """Publish a message to RabbitMQ."""
        if not self.enabled:
            return False
        
        if not self._ensure_connection():
            return False
        
        try:
            with self._lock:
                if not self._channel or self._channel.is_closed:
                    return False
                
                # Serialize message
                body = json.dumps(message, default=str)
                
                # Publish with persistent delivery
                self._channel.basic_publish(
                    exchange=self.exchange_name,
                    routing_key=routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # persistent
                        content_type='application/json',
                        timestamp=int(time.time())
                    )
                )
                
                self.logger.debug(f"published message: {routing_key}")
                return True
                
        except Exception as e:
            self.logger.error(f"failed to publish message: {e}")
            self._connected = False
            return False
    
    def publish_services_updated(self, services: List[Dict[str, Any]]) -> None:
        """Publish services updated event."""
        message = {
            "event": "services.updated",
            "timestamp": int(time.time()),
            "services_count": len(services),
            "services": services
        }
        
        self._publish_message("services.updated", message)
    
    def publish_service_added(self, service: Dict[str, Any]) -> None:
        """Publish service added event."""
        message = {
            "event": "service.added",
            "timestamp": int(time.time()),
            "service": service
        }
        
        self._publish_message("service.added", message)
    
    def publish_service_removed(self, service_id: str, service_name: str) -> None:
        """Publish service removed event."""
        message = {
            "event": "service.removed",
            "timestamp": int(time.time()),
            "service_id": service_id,
            "service_name": service_name
        }
        
        self._publish_message("service.removed", message)
    
    def publish_service_updated(self, service: Dict[str, Any]) -> None:
        """Publish service updated event."""
        message = {
            "event": "service.updated",
            "timestamp": int(time.time()),
            "service": service
        }
        
        self._publish_message("service.updated", message)
    
    def publish_metrics_updated(self, service_name: str, metrics: Dict[str, Any]) -> None:
        """Publish metrics updated event."""
        message = {
            "event": "metrics.updated",
            "timestamp": int(time.time()),
            "service_name": service_name,
            "metrics": metrics
        }
        
        self._publish_message(f"metrics.{service_name}", message)
    
    def publish_health_check(self) -> None:
        """Publish health check event."""
        message = {
            "event": "health.check",
            "timestamp": int(time.time()),
            "service": "service-registry"
        }
        
        self._publish_message("health.check", message)
    
    def close(self) -> None:
        """Close RabbitMQ connection."""
        if not self.enabled:
            return
        
        with self._lock:
            try:
                if self._channel and not self._channel.is_closed:
                    self._channel.close()
                if self._connection and not self._connection.is_closed:
                    self._connection.close()
                
                self._connected = False
                self.logger.info("rabbitmq connection closed")
                
            except Exception as e:
                self.logger.error(f"error closing rabbitmq connection: {e}")
    
    def is_connected(self) -> bool:
        """Check if RabbitMQ connection is active."""
        if not self.enabled:
            return False
        
        with self._lock:
            return (self._connected and 
                   self._connection and 
                   not self._connection.is_closed and
                   self._channel and 
                   not self._channel.is_closed)
