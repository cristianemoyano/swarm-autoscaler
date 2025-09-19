"""
cAdvisor response fixtures for testing
"""

def get_cadvisor_containers_response():
    """Mock cAdvisor containers API response"""
    return {
        "id": "/",
        "name": "/",
        "subcontainers": [
            {
                "id": "/docker",
                "name": "/docker",
                "subcontainers": [
                    {
                        "id": "/docker/5dab53088c979dbc714774536e28f4da4f3ec9112c01555e9099f86df4d34e39",
                        "name": "/docker/5dab53088c979dbc714774536e28f4da4f3ec9112c01555e9099f86df4d34e39",
                        "stats": [
                            {
                                "timestamp": "2025-09-19T00:00:00.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 1000000000,
                                        "per_cpu_usage": [500000000, 500000000]
                                    },
                                    "system_usage": 2000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 50000000
                                }
                            },
                            {
                                "timestamp": "2025-09-19T00:00:10.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 2000000000,
                                        "per_cpu_usage": [1000000000, 1000000000]
                                    },
                                    "system_usage": 4000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 60000000
                                }
                            }
                        ]
                    },
                    {
                        "id": "/docker/898011fcb3f57c98b87bd0f25d8296146e1befe7170e063ff01ca18add480182",
                        "name": "/docker/898011fcb3f57c98b87bd0f25d8296146e1befe7170e063ff01ca18add480182",
                        "stats": [
                            {
                                "timestamp": "2025-09-19T00:00:00.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 800000000,
                                        "per_cpu_usage": [400000000, 400000000]
                                    },
                                    "system_usage": 2000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 40000000
                                }
                            },
                            {
                                "timestamp": "2025-09-19T00:00:10.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 1600000000,
                                        "per_cpu_usage": [800000000, 800000000]
                                    },
                                    "system_usage": 4000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 45000000
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

def get_cadvisor_containers_response_with_service_containers():
    """Mock cAdvisor response with service-specific containers"""
    return {
        "id": "/",
        "name": "/",
        "subcontainers": [
            {
                "id": "/docker",
                "name": "/docker",
                "subcontainers": [
                    {
                        "id": "/docker/autoscale-cpu_sample_1.1.abc123",
                        "name": "/docker/autoscale-cpu_sample_1.1.abc123",
                        "stats": [
                            {
                                "timestamp": "2025-09-19T00:00:00.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 1000000000,
                                        "per_cpu_usage": [500000000, 500000000]
                                    },
                                    "system_usage": 2000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 50000000
                                }
                            },
                            {
                                "timestamp": "2025-09-19T00:00:10.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 2000000000,
                                        "per_cpu_usage": [1000000000, 1000000000]
                                    },
                                    "system_usage": 4000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 60000000
                                }
                            }
                        ]
                    },
                    {
                        "id": "/docker/autoscale-cpu_sample_1.2.def456",
                        "name": "/docker/autoscale-cpu_sample_1.2.def456",
                        "stats": [
                            {
                                "timestamp": "2025-09-19T00:00:00.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 800000000,
                                        "per_cpu_usage": [400000000, 400000000]
                                    },
                                    "system_usage": 2000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 40000000
                                }
                            },
                            {
                                "timestamp": "2025-09-19T00:00:10.000000000Z",
                                "cpu": {
                                    "usage": {
                                        "total": 1600000000,
                                        "per_cpu_usage": [800000000, 800000000]
                                    },
                                    "system_usage": 4000000000,
                                    "num_cores": 2
                                },
                                "memory": {
                                    "usage": 45000000
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }
