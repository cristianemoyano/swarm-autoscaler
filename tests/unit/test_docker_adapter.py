"""
Unit tests for DockerSwarmAdapter
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from services.service_registry.docker_adapter import DockerSwarmAdapter
from tests.fixtures.cadvisor_responses import (
    get_cadvisor_containers_response,
    get_cadvisor_containers_response_with_service_containers
)


@pytest.mark.unit
class TestDockerSwarmAdapter:
    """Test cases for DockerSwarmAdapter"""
    
    @pytest.fixture
    def adapter(self):
        """Create a DockerSwarmAdapter instance for testing"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            adapter.cadvisor_url = "http://localhost:8091"
            adapter.use_cadvisor = True
            return adapter
    
    def test_init_with_cadvisor(self):
        """Test adapter initialization with cAdvisor enabled"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            adapter.cadvisor_url = "http://localhost:8091"
            adapter.metrics_source = "cadvisor"
            adapter.use_cadvisor = True
            
            assert adapter.use_cadvisor is True
            assert adapter.cadvisor_url == "http://localhost:8091"
    
    def test_init_with_docker_api(self):
        """Test adapter initialization with Docker API"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            adapter.metrics_source = "docker"
            adapter.use_cadvisor = False
            
            assert adapter.use_cadvisor is False
    
    @patch('requests.get')
    def test_get_metrics_from_cadvisor_success(self, mock_get, adapter):
        """Test successful metrics retrieval from cAdvisor"""
        # Mock cAdvisor response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = get_cadvisor_containers_response_with_service_containers()
        mock_get.return_value = mock_response
        
        # Test metrics retrieval
        result = adapter.get_metrics_from_cadvisor("autoscale-cpu_sample_1")
        
        assert result is not None
        assert "cpu_pct" in result
        assert "memory_bytes" in result
        assert "source" in result
        assert result["source"] == "cadvisor"
        assert result["cpu_pct"] > 0  # Should have some CPU usage
        assert result["memory_bytes"] > 0  # Should have some memory usage
    
    @patch('requests.get')
    def test_get_metrics_from_cadvisor_no_containers(self, mock_get, adapter):
        """Test metrics retrieval when no containers found"""
        # Mock empty cAdvisor response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "/", "name": "/", "subcontainers": []}
        mock_get.return_value = mock_response
        
        result = adapter.get_metrics_from_cadvisor("nonexistent_service")
        
        assert result is None
    
    @patch('requests.get')
    def test_get_metrics_from_cadvisor_http_error(self, mock_get, adapter):
        """Test metrics retrieval with HTTP error"""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = adapter.get_metrics_from_cadvisor("test_service")
        
        assert result is None
    
    @patch('requests.get')
    def test_get_metrics_from_cadvisor_insufficient_stats(self, mock_get, adapter):
        """Test metrics retrieval with insufficient stats"""
        # Mock response with only one stat (need at least 2 for delta calculation)
        mock_response = Mock()
        mock_response.status_code = 200
        response_data = get_cadvisor_containers_response_with_service_containers()
        # Remove one stat from each container
        for container in response_data["subcontainers"][0]["subcontainers"]:
            container["stats"] = container["stats"][:1]
        mock_response.json.return_value = response_data
        mock_get.return_value = mock_response
        
        result = adapter.get_metrics_from_cadvisor("autoscale-cpu_sample_1")
        
        assert result is None
    
    def test_get_service_metrics_with_cadvisor(self, adapter):
        """Test get_service_metrics method with cAdvisor"""
        with patch.object(adapter, 'get_metrics_from_cadvisor') as mock_cadvisor:
            mock_cadvisor.return_value = {"cpu_pct": 50.0, "memory_bytes": 1000000}
            
            result = adapter.get_service_metrics("test_service")
            
            assert result == {"cpu_pct": 50.0, "memory_bytes": 1000000}
            mock_cadvisor.assert_called_once_with("test_service")
    
    def test_get_service_metrics_with_docker_api(self, adapter):
        """Test get_service_metrics method with Docker API"""
        adapter.use_cadvisor = False
        
        with patch.object(adapter, 'get_metrics_from_docker') as mock_docker:
            mock_docker.return_value = {"cpu_pct": 30.0, "memory_bytes": 500000}
            
            result = adapter.get_service_metrics("test_service")
            
            assert result == {"cpu_pct": 30.0, "memory_bytes": 500000}
            mock_docker.assert_called_once_with("test_service")
    
    def test_service_matches_labels_true(self, adapter):
        """Test service label matching when labels match"""
        mock_service = Mock()
        mock_service.attrs = {
            "Spec": {
                "Labels": {
                    "autoscaler.enabled": "true"
                }
            }
        }
        
        result = adapter.service_matches_labels(mock_service)
        
        assert result is True
    
    def test_service_matches_labels_false(self, adapter):
        """Test service label matching when labels don't match"""
        mock_service = Mock()
        mock_service.attrs = {
            "Spec": {
                "Labels": {
                    "autoscaler.enabled": "false"
                }
            }
        }
        
        result = adapter.service_matches_labels(mock_service)
        
        assert result is False
    
    def test_service_matches_labels_no_labels(self, adapter):
        """Test service label matching when no labels present"""
        mock_service = Mock()
        mock_service.attrs = {"Spec": {}}
        
        result = adapter.service_matches_labels(mock_service)
        
        assert result is False
    
    def test_build_service_entry(self, adapter):
        """Test service entry building"""
        mock_service = Mock()
        mock_service.id = "service123"
        mock_service.attrs = {
            "Spec": {
                "Name": "test-service",
                "Labels": {
                    "autoscaler.enabled": "true",
                    "autoscaler.metric": "cpu",
                    "autoscaler.cpu.threshold": "80",
                    "autoscaler.memory.threshold": "70",
                    "autoscaler.min": "1",
                    "autoscaler.max": "5"
                },
                "Mode": {
                    "Replicated": {
                        "Replicas": 3
                    }
                }
            },
            "CreatedAt": "2025-09-19T00:00:00Z",
            "UpdatedAt": "2025-09-19T00:00:00Z"
        }
        
        result = adapter.build_service_entry(mock_service)
        
        assert result is not None
        assert result["id"] == "service123"
        assert result["name"] == "test-service"
        assert result["current_replicas"] == 3
        assert result["metric"] == "cpu"
        assert result["thresholds"]["cpu"] == 80.0
        assert result["thresholds"]["memory"] == 70.0
        assert result["min_replicas"] == 1
        assert result["max_replicas"] == 5
