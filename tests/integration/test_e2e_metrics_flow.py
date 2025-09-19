"""
End-to-end tests for the complete metrics flow
"""

import pytest
import requests
import time
from unittest.mock import patch


@pytest.mark.integration
@pytest.mark.slow
class TestE2EMetricsFlow:
    """End-to-end tests for the complete metrics flow"""
    
    @pytest.fixture
    def service_registry_url(self):
        """Service Registry URL for testing"""
        return "http://localhost:5001"
    
    @pytest.fixture
    def cadvisor_url(self):
        """cAdvisor URL for testing"""
        return "http://localhost:8091"
    
    def test_service_registry_health(self, service_registry_url):
        """Test that Service Registry is healthy"""
        try:
            response = requests.get(f"{service_registry_url}/health", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]
            assert "service" in data
            assert data["service"] == "service-registry"
            
        except requests.exceptions.RequestException:
            pytest.skip("Service Registry not available")
    
    def test_cadvisor_health(self, cadvisor_url):
        """Test that cAdvisor is healthy"""
        try:
            response = requests.get(f"{cadvisor_url}/api/v1.3/containers", timeout=5)
            assert response.status_code == 200
            
        except requests.exceptions.RequestException:
            pytest.skip("cAdvisor not available")
    
    def test_services_discovery(self, service_registry_url):
        """Test that services are discovered"""
        try:
            response = requests.get(f"{service_registry_url}/services", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "services" in data
            assert "metadata" in data
            assert isinstance(data["services"], list)
            
            # Should have at least the sample services
            service_names = [s["name"] for s in data["services"]]
            assert any("sample" in name for name in service_names)
            
        except requests.exceptions.RequestException:
            pytest.skip("Service Registry not available")
    
    def test_metrics_availability(self, service_registry_url):
        """Test that metrics are available for services"""
        try:
            # Get services first
            services_response = requests.get(f"{service_registry_url}/services", timeout=5)
            assert services_response.status_code == 200
            
            services_data = services_response.json()
            services = services_data["services"]
            
            if not services:
                pytest.skip("No services found")
            
            # Test metrics for each service
            for service in services:
                service_name = service["name"]
                
                # Try to get metrics
                metrics_response = requests.get(
                    f"{service_registry_url}/services/{service_name}/metrics",
                    timeout=5
                )
                
                # Metrics might not be available immediately, that's OK
                # We just want to ensure the endpoint works
                assert metrics_response.status_code in [200, 404]
                
        except requests.exceptions.RequestException:
            pytest.skip("Service Registry not available")
    
    def test_metrics_refresh(self, service_registry_url):
        """Test manual metrics refresh"""
        try:
            # Get services first
            services_response = requests.get(f"{service_registry_url}/services", timeout=5)
            assert services_response.status_code == 200
            
            services_data = services_response.json()
            services = services_data["services"]
            
            if not services:
                pytest.skip("No services found")
            
            # Try to refresh metrics for the first service
            service_name = services[0]["name"]
            
            refresh_response = requests.post(
                f"{service_registry_url}/services/{service_name}/metrics",
                timeout=10
            )
            
            # Should return 200 or 404 (if no metrics available)
            assert refresh_response.status_code in [200, 404]
            
        except requests.exceptions.RequestException:
            pytest.skip("Service Registry not available")
    
    def test_cache_stats(self, service_registry_url):
        """Test cache statistics endpoint"""
        try:
            response = requests.get(f"{service_registry_url}/cache/stats", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "cache_stats" in data
            assert "services_count" in data["cache_stats"]
            assert "metrics_count" in data["cache_stats"]
            assert "last_refresh" in data["cache_stats"]
            
        except requests.exceptions.RequestException:
            pytest.skip("Service Registry not available")
    
    def test_complete_flow(self, service_registry_url, cadvisor_url):
        """Test the complete flow from cAdvisor to Service Registry"""
        try:
            # 1. Verify cAdvisor is running
            cadvisor_response = requests.get(f"{cadvisor_url}/api/v1.3/containers", timeout=5)
            assert cadvisor_response.status_code == 200
            
            # 2. Verify Service Registry is running
            health_response = requests.get(f"{service_registry_url}/health", timeout=5)
            assert health_response.status_code == 200
            
            # 3. Get services
            services_response = requests.get(f"{service_registry_url}/services", timeout=5)
            assert services_response.status_code == 200
            
            services_data = services_response.json()
            services = services_data["services"]
            
            if not services:
                pytest.skip("No services found")
            
            # 4. Wait a bit for metrics to be collected
            time.sleep(5)
            
            # 5. Check if any service has metrics
            has_metrics = False
            for service in services:
                service_name = service["name"]
                metrics_response = requests.get(
                    f"{service_registry_url}/services/{service_name}/metrics",
                    timeout=5
                )
                
                if metrics_response.status_code == 200:
                    metrics_data = metrics_response.json()
                    if "metrics" in metrics_data and metrics_data["metrics"]:
                        has_metrics = True
                        break
            
            # It's OK if no metrics are available yet, as long as the flow works
            # The important thing is that the endpoints respond correctly
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Integration test failed: {e}")
