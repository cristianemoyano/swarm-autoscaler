"""
Unit tests for DockerSwarmAdapter
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.service_registry.docker_adapter import DockerSwarmAdapter


@pytest.mark.unit
class TestDockerSwarmAdapter:
    """Test cases for DockerSwarmAdapter"""
    
    @pytest.fixture
    def adapter(self):
        """Create a DockerSwarmAdapter instance for testing"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            return adapter
    
    def test_init_with_docker_api(self):
        """Test adapter initialization with Docker API"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            
            # Should always use Docker API now
            assert hasattr(adapter, 'client')
    
    def test_get_service_metrics_with_docker_api(self, adapter):
        """Test get_service_metrics method with Docker API"""
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
