"""
Docker Swarm Adapter

This module handles all interactions with Docker Swarm, including:
- Service discovery and filtering
- Service metadata extraction
- Docker events monitoring
- Metrics collection via Docker API or cAdvisor
"""

import os
import time
import requests
from typing import Any, Dict, List, Optional, Callable
import docker
from services.common.logging_config import get_logger


class DockerSwarmAdapter:
    """Adapter for Docker Swarm operations."""
    
    def __init__(self):
        self.logger = get_logger("service-registry", name="docker-adapter")
        
        # Configuration
        self.docker_base_url = os.getenv("DOCKER_BASE_URL", "unix:///var/run/docker.sock")
        self.autoscaler_label_enabled = os.getenv("AUTOSCALER_LABEL_ENABLED", "autoscaler.enabled")
        self.autoscaler_label_metric = os.getenv("AUTOSCALER_LABEL_METRIC", "autoscaler.metric")
        self.autoscaler_label_cpu_threshold = os.getenv("AUTOSCALER_LABEL_CPU_THRESHOLD", "autoscaler.cpu.threshold")
        self.autoscaler_label_mem_threshold = os.getenv("AUTOSCALER_LABEL_MEM_THRESHOLD", "autoscaler.memory.threshold")
        self.autoscaler_label_min = os.getenv("AUTOSCALER_LABEL_MIN", "autoscaler.min")
        self.autoscaler_label_max = os.getenv("AUTOSCALER_LABEL_MAX", "autoscaler.max")
        # cAdvisor configuration
        self.cadvisor_url = os.getenv("CADVISOR_URL", "")
        self.metrics_source = os.getenv("METRICS_SOURCE", "docker").lower()
        self.use_cadvisor = self.metrics_source == "cadvisor" and self.cadvisor_url
        # Initialize Docker client
        if self.docker_base_url.startswith("unix"):
            self.client = docker.from_env()
        else:
            self.client = docker.DockerClient(base_url=self.docker_base_url)
        if self.use_cadvisor:
            self.logger.info(f"using cAdvisor for metrics: {self.cadvisor_url}")
        else:
            self.logger.info(f"using Docker API for metrics: {self.docker_base_url}")
    
    def service_matches_labels(self, service: Any) -> bool:
        """Check if a service has autoscaler labels enabled."""
        try:
            labels = (service.attrs.get("Spec", {}).get("Labels") or {})
            return str(labels.get(self.autoscaler_label_enabled, "false")).lower() == "true"
        except Exception as e:
            self.logger.warning(f"error checking service labels: {e}")
            return False
    
    def build_service_entry(self, service: Any) -> Optional[Dict[str, Any]]:
        """Build a standardized service entry from Docker service object."""
        try:
            spec = service.attrs.get("Spec", {})
            labels = spec.get("Labels") or {}
            mode = spec.get("Mode", {})
            replicated = mode.get("Replicated", {})
            replicas = replicated.get("Replicas", 1)
            
            metric = labels.get(self.autoscaler_label_metric, "cpu")
            cpu_threshold = float(labels.get(self.autoscaler_label_cpu_threshold, 70))
            mem_threshold = float(labels.get(self.autoscaler_label_mem_threshold, 70))
            min_replicas = int(labels.get(self.autoscaler_label_min, 1))
            max_replicas = int(labels.get(self.autoscaler_label_max, max(2, replicas)))
            
            return {
                "id": service.id,
                "name": spec.get("Name"),
                "labels": labels,
                "current_replicas": replicas,
                "metric": metric,
                "thresholds": {
                    "cpu": cpu_threshold,
                    "memory": mem_threshold,
                },
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
                "created_at": service.attrs.get("CreatedAt"),
                "updated_at": service.attrs.get("UpdatedAt"),
            }
        except Exception as e:
            self.logger.warning(f"error building service entry: {e}")
            return None
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all services that match autoscaler criteria."""
        try:
            services = self.client.services.list()
            matching_services = []
            
            for service in services:
                try:
                    if self.service_matches_labels(service):
                        entry = self.build_service_entry(service)
                        if entry:
                            matching_services.append(entry)
                except Exception as e:
                    self.logger.warning(f"skip service due to error: {e}")
                    continue
            
            self.logger.info(f"discovered {len(matching_services)} autoscaler-enabled services")
            return matching_services
            
        except Exception as e:
            self.logger.error(f"failed to get services: {e}")
            return []
    
    def get_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific service by name."""
        try:
            services = self.client.services.list(filters={"name": service_name})
            if not services:
                return None
            
            service = services[0]
            if self.service_matches_labels(service):
                return self.build_service_entry(service)
            
            return None
            
        except Exception as e:
            self.logger.error(f"failed to get service {service_name}: {e}")
            return None
    
    def get_service_containers(self, service_name: str) -> List[str]:
        """Get container IDs for a service."""
        try:
            tasks = self.client.api.tasks(filters={"service": service_name, "desired-state": "running"})
            container_ids = []
            
            for task in tasks:
                status = task.get("Status", {})
                container_status = status.get("ContainerStatus", {})
                container_id = container_status.get("ContainerID")
                
                if container_id:
                    container_ids.append(container_id)
            
            return container_ids
            
        except Exception as e:
            self.logger.warning(f"failed to get containers for {service_name}: {e}")
            return []
    
    def get_metrics_from_cadvisor(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics from cAdvisor for a service."""
        try:
            # Get all containers from cAdvisor once
            resp = requests.get(f"{self.cadvisor_url}/api/v1.3/containers", timeout=5)
            if resp.status_code != 200:
                self.logger.warning(f"Failed to get containers from cAdvisor: {resp.status_code}")
                return None
            
            root_container = resp.json()
            
            # Find all Docker containers in the hierarchy
            def find_docker_containers(container_obj, containers=None):
                if containers is None:
                    containers = []
                
                if container_obj.get("name", "").startswith("/docker/"):
                    containers.append(container_obj)
                
                if "subcontainers" in container_obj:
                    for subcontainer in container_obj["subcontainers"]:
                        find_docker_containers(subcontainer, containers)
                
                return containers
            
            docker_containers = find_docker_containers(root_container)
            self.logger.debug(f"Found {len(docker_containers)} Docker containers in cAdvisor")
            
            if not docker_containers:
                return None
            
            # Filter containers by service name
            service_containers = []
            for container in docker_containers:
                container_name = container.get("name", "")
                # Check if this container belongs to our service
                if service_name in container_name or f"{service_name}." in container_name:
                    service_containers.append(container)
                    self.logger.debug(f"Found service container: {container_name}")
            
            if not service_containers:
                self.logger.debug(f"No containers found for service {service_name} in cAdvisor")
                return None
            
            cpu_pcts: List[float] = []
            mem_usages: List[int] = []
            
            for container in service_containers:
                try:
                    stats = container.get("stats", [])
                    if len(stats) < 2:
                        self.logger.debug(f"Not enough stats for container {container.get('name')} (got {len(stats)})")
                        continue
                    
                    # Use the last two stats for delta calculation
                    current = stats[-1]
                    previous = stats[-2]
                    
                    # Calculate CPU percentage (cAdvisor style)
                    current_cpu = current.get("cpu", {}).get("usage", {})
                    previous_cpu = previous.get("cpu", {}).get("usage", {})
                    
                    cpu_delta = current_cpu.get("total", 0) - previous_cpu.get("total", 0)
                    system_delta = current.get("cpu", {}).get("system_usage", 0) - previous.get("cpu", {}).get("system_usage", 0)
                    
                    perc = 0.0
                    if system_delta > 0 and cpu_delta > 0:
                        # Get number of CPUs
                        num_cpus = current.get("cpu", {}).get("num_cores", 1)
                        perc = (cpu_delta / system_delta) * num_cpus * 100.0
                    
                    # Get memory usage
                    memory_usage = current.get("memory", {}).get("usage", 0)
                    
                    cpu_pcts.append(float(perc))
                    mem_usages.append(int(memory_usage))
                    
                    self.logger.debug(f"Container {container.get('name')}: CPU={perc:.2f}%, Memory={memory_usage}")
                    
                except Exception as e:
                    self.logger.debug(f"failed to process container {container.get('name')}: {e}")
                    continue
            
            if not cpu_pcts and not mem_usages:
                return None
            
            cpu_avg = sum(cpu_pcts) / len(cpu_pcts) if cpu_pcts else 0.0
            mem_avg = sum(mem_usages) / len(mem_usages) if mem_usages else 0
            
            self.logger.debug(f"Service {service_name}: CPU={cpu_avg:.2f}%, Memory={mem_avg}")
            
            return {
                "cpu_pct": cpu_avg,
                "memory_bytes": mem_avg,
                "window_seconds": 60,
                "timestamp": int(time.time()),
                "source": "cadvisor"
            }
            
        except Exception as e:
            self.logger.warning(f"failed to get cAdvisor metrics for {service_name}: {e}")
            return None

    
    def get_metrics_from_docker(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get current metrics for a service via Docker stats."""
        try:
            # Get tasks for the service
            tasks = self.client.api.tasks(filters={"service": service_name, "desired-state": "running"})
            
            cpu_pcts: List[float] = []
            mem_usages: List[int] = []
            
            for task in tasks:
                status = task.get("Status", {})
                container_status = status.get("ContainerStatus", {})
                container_id = container_status.get("ContainerID")
                
                if not container_id:
                    continue
                
                try:
                    stats = self.client.api.stats(container_id, stream=False)
                except Exception:
                    continue
                
                # CPU percent calculation (Docker style)
                cpu_delta = (
                    stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - 
                    stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                )
                system_delta = (
                    stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - 
                    stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
                )
                
                perc = 0.0
                if system_delta > 0 and cpu_delta > 0:
                    online_cpus = (
                        stats.get("cpu_stats", {}).get("online_cpus") or 
                        len(stats.get("cpu_stats", {}).get("cpu_usage", {}).get("percpu_usage", []) or [1])
                    )
                    perc = (cpu_delta / system_delta) * online_cpus * 100.0
                
                mem_usage = stats.get("memory_stats", {}).get("usage", 0)
                cpu_pcts.append(float(perc))
                mem_usages.append(int(mem_usage))
            
            if not cpu_pcts and not mem_usages:
                return None
            
            cpu_avg = sum(cpu_pcts) / len(cpu_pcts) if cpu_pcts else 0.0
            mem_avg = sum(mem_usages) / len(mem_usages) if mem_usages else 0
            
            return {
                "cpu_pct": cpu_avg,
                "memory_bytes": mem_avg,
                "window_seconds": 60,
                "timestamp": int(time.time()),
                "source": "docker"
            }
            
        except Exception as e:
            self.logger.warning(f"failed to get Docker metrics for {service_name}: {e}")
            return None
    
    def get_service_metrics(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get current metrics for a service using the configured source."""
        self.logger.debug(f"Getting metrics for service: {service_name}")
        if self.use_cadvisor:
            result = self.get_metrics_from_cadvisor(service_name)
            self.logger.debug(f"cAdvisor metrics for {service_name}: {result is not None}")
            return result
        else:
            result = self.get_metrics_from_docker(service_name)
            self.logger.debug(f"Docker metrics for {service_name}: {result is not None}")
            return result
    
    def watch_events(self, callback: Callable[[str, str], None]) -> None:
        """Watch Docker events and call the callback when service events occur."""
        self.logger.info("starting docker events watcher")
        
        while True:
            try:
                for event in self.client.events(decode=True):
                    if not isinstance(event, dict):
                        continue
                    
                    if event.get("Type") != "service":
                        continue
                    
                    action = event.get("Action", "")
                    if action not in ("create", "update", "remove"):
                        continue
                    
                    service_id = event.get("Actor", {}).get("ID", "")
                    self.logger.info(f"service_event action={action} service_id={service_id}")
                    
                    # Call the callback with event details
                    callback(action, service_id)
                    
            except Exception as e:
                self.logger.warning(f"events stream error, retrying in 2s: {e}")
                time.sleep(2)
