#!/usr/bin/env python3
"""
Test script for Service Registry

This script tests the basic functionality of the Service Registry service.
Run this after starting the Service Registry to verify it's working correctly.
"""

import requests
import time
import json
import sys
from typing import Dict, Any


def test_health(base_url: str) -> bool:
    """Test the health endpoint."""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Health check passed: {data['status']}")
        print(f"   Cache: {data['cache']['services_count']} services")
        print(f"   Publisher: {'enabled' if data['publisher']['enabled'] else 'disabled'}")
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_services(base_url: str) -> bool:
    """Test the services endpoint."""
    print("\nTesting services endpoint...")
    try:
        response = requests.get(f"{base_url}/services", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        services = data.get("services", [])
        metadata = data.get("metadata", {})
        
        print(f"✅ Services endpoint working: {len(services)} services found")
        print(f"   Cache version: {metadata.get('cache_version', 'N/A')}")
        print(f"   Last refresh: {metadata.get('last_refresh', 'N/A')}")
        
        if services:
            print("   Sample services:")
            for service in services[:3]:  # Show first 3 services
                print(f"     - {service.get('name', 'N/A')} (replicas: {service.get('current_replicas', 'N/A')})")
        
        return True
        
    except Exception as e:
        print(f"❌ Services endpoint failed: {e}")
        return False


def test_cache_stats(base_url: str) -> bool:
    """Test the cache stats endpoint."""
    print("\nTesting cache stats endpoint...")
    try:
        response = requests.get(f"{base_url}/cache/stats", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stats = data.get("cache_stats", {})
        print(f"✅ Cache stats working:")
        print(f"   Services count: {stats.get('services_count', 'N/A')}")
        print(f"   Metrics count: {stats.get('metrics_count', 'N/A')}")
        print(f"   Cache version: {stats.get('cache_version', 'N/A')}")
        print(f"   Refresh interval: {stats.get('refresh_interval_sec', 'N/A')}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache stats failed: {e}")
        return False


def test_cache_refresh(base_url: str) -> bool:
    """Test the cache refresh endpoint."""
    print("\nTesting cache refresh endpoint...")
    try:
        response = requests.post(f"{base_url}/cache/refresh", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Cache refresh working: {data.get('message', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ Cache refresh failed: {e}")
        return False


def test_events_info(base_url: str) -> bool:
    """Test the events info endpoint."""
    print("\nTesting events info endpoint...")
    try:
        response = requests.get(f"{base_url}/events", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Events info working:")
        print(f"   Publisher enabled: {data.get('enabled', 'N/A')}")
        print(f"   Publisher connected: {data.get('connected', 'N/A')}")
        print(f"   Available events: {len(data.get('available_events', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Events info failed: {e}")
        return False


def test_root_endpoint(base_url: str) -> bool:
    """Test the root endpoint."""
    print("\nTesting root endpoint...")
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Root endpoint working: {data.get('service', 'N/A')} v{data.get('version', 'N/A')}")
        print(f"   Description: {data.get('description', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return False


def main():
    """Main test function."""
    base_url = "http://localhost:5001"
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"Testing Service Registry at: {base_url}")
    print("=" * 50)
    
    tests = [
        test_health,
        test_services,
        test_cache_stats,
        test_cache_refresh,
        test_events_info,
        test_root_endpoint,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test(base_url):
            passed += 1
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Service Registry is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the Service Registry logs for issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
