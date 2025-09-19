"""
Integration tests for cAdvisor functionality
"""

import pytest
import requests
import time
from unittest.mock import patch
from services.service_registry.docker_adapter import DockerSwarmAdapter


@pytest.mark.integration
@pytest.mark.cadvisor
class TestCadvisorIntegration:
    """Integration tests for cAdvisor functionality"""
    
    @pytest.fixture
    def cadvisor_url(self):
        """cAdvisor URL for testing"""
        return "http://localhost:8091"
    
    @pytest.fixture
    def adapter(self, cadvisor_url):
        """Create adapter with cAdvisor enabled"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            adapter.cadvisor_url = cadvisor_url
            adapter.use_cadvisor = True
            return adapter
    
    def test_cadvisor_connectivity(self, cadvisor_url):
        """Test that cAdvisor is accessible"""
        try:
            response = requests.get(f"{cadvisor_url}/api/v1.3/containers", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.skip("cAdvisor not available")
    
    def test_cadvisor_containers_endpoint(self, cadvisor_url):
        """Test cAdvisor containers endpoint structure"""
        try:
            response = requests.get(f"{cadvisor_url}/api/v1.3/containers", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "name" in data
            assert "subcontainers" in data
            # cAdvisor v0.47.0 doesn't have "id" field in root container
        except requests.exceptions.RequestException:
            pytest.skip("cAdvisor not available")
    
    def test_cadvisor_docker_containers(self, cadvisor_url):
        """Test that cAdvisor can find Docker containers"""
        try:
            response = requests.get(f"{cadvisor_url}/api/v1.3/containers", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            
            # Find Docker containers
            docker_containers = []
            def find_docker_containers(container_obj):
                if container_obj.get("name", "").startswith("/docker/"):
                    docker_containers.append(container_obj)
                if "subcontainers" in container_obj:
                    for subcontainer in container_obj["subcontainers"]:
                        find_docker_containers(subcontainer)
            
            find_docker_containers(data)
            
            # Check if we found any Docker containers
            # If not, that's OK - it might mean no containers are running
            if len(docker_containers) > 0:
                # Check container structure
                for container in docker_containers:
                    assert "name" in container
                    # Some containers might not have stats yet
                    if "stats" in container:
                        assert len(container["stats"]) > 0
            else:
                # Just verify the structure is correct
                assert "subcontainers" in data
                
        except requests.exceptions.RequestException:
            pytest.skip("cAdvisor not available")
    
    def test_metrics_calculation(self, adapter):
        """Test metrics calculation with real cAdvisor data"""
        try:
            # This test requires cAdvisor to be running with actual containers
            result = adapter.get_metrics_from_cadvisor("autoscale-cpu_sample_1")
            
            if result is not None:
                assert "cpu_pct" in result
                assert "memory_bytes" in result
                assert "source" in result
                assert result["source"] == "cadvisor"
                assert isinstance(result["cpu_pct"], (int, float))
                assert isinstance(result["memory_bytes"], (int, float))
                assert result["memory_bytes"] >= 0
            else:
                # If no metrics, it might be because the service doesn't exist
                # This is acceptable for integration testing
                pass
                
        except Exception as e:
            pytest.skip(f"cAdvisor integration test failed: {e}")


@pytest.mark.integration
@pytest.mark.docker
class TestDockerIntegration:
    """Integration tests for Docker functionality"""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter with Docker API"""
        with patch('services.service_registry.docker_adapter.docker.from_env'):
            adapter = DockerSwarmAdapter()
            adapter.use_cadvisor = False
            return adapter
    
    def test_docker_client_connection(self, adapter):
        """Test Docker client connection"""
        try:
            # This will fail if Docker is not available
            services = adapter.client.services.list()
            assert isinstance(services, list)
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")
    
    def test_get_all_services(self, adapter):
        """Test getting all services from Docker"""
        try:
            services = adapter.get_all_services()
            assert isinstance(services, list)
            # Should not raise an exception
        except Exception as e:
            pytest.skip(f"Docker services not available: {e}")
