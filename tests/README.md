# Test Suite for Swarm Autoscaler

This directory contains comprehensive tests for the swarm-autoscaler project.

## Structure

```
tests/
├── unit/                    # Unit tests
│   ├── test_docker_adapter.py
│   └── ...
├── integration/             # Integration tests
│   ├── test_cadvisor_integration.py
│   ├── test_e2e_metrics_flow.py
│   └── ...
├── fixtures/                # Test fixtures and mock data
│   ├── cadvisor_responses.py
│   └── ...
├── requirements.txt         # Test dependencies
└── README.md               # This file
```

## Test Categories

### Unit Tests (`unit/`)
- Test individual components in isolation
- Use mocks to avoid external dependencies
- Fast execution
- Marked with `@pytest.mark.unit`

### Integration Tests (`integration/`)
- Test component interactions
- May require external services (cAdvisor, Docker)
- Slower execution
- Marked with `@pytest.mark.integration`

### Test Markers
- `unit`: Unit tests
- `integration`: Integration tests
- `cadvisor`: Tests requiring cAdvisor
- `docker`: Tests requiring Docker
- `slow`: Long-running tests

## Running Tests

### Quick Start
```bash
# Install dependencies and run unit tests
./run_tests.py --install --unit

# Run all tests
./run_tests.py --all

# Run integration tests only
./run_tests.py --integration

# Run cAdvisor-specific tests
./run_tests.py --cadvisor
```

### Manual Execution
```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/test_docker_adapter.py -v

# Run with specific markers
pytest -m "unit and not slow" -v
```

## Test Environment

### Prerequisites
- Python 3.11+
- Docker (for integration tests)
- cAdvisor (for cAdvisor tests)

### Environment Variables
- `CADVISOR_URL`: cAdvisor endpoint (default: http://localhost:8091)
- `SERVICE_REGISTRY_URL`: Service Registry endpoint (default: http://localhost:5001)

## Writing Tests

### Unit Tests
```python
import pytest
from unittest.mock import Mock, patch
from services.service_registry.docker_adapter import DockerSwarmAdapter

@pytest.mark.unit
class TestDockerAdapter:
    def test_something(self):
        # Test implementation
        pass
```

### Integration Tests
```python
import pytest
import requests

@pytest.mark.integration
@pytest.mark.cadvisor
class TestCadvisorIntegration:
    def test_cadvisor_connectivity(self):
        # Test with real cAdvisor
        pass
```

## Test Data

### Fixtures
- `cadvisor_responses.py`: Mock cAdvisor API responses
- Additional fixtures can be added as needed

### Mock Data
- Use realistic test data that matches production scenarios
- Include edge cases and error conditions
- Ensure data is consistent across tests

## Continuous Integration

Tests are designed to run in CI environments:
- Unit tests run without external dependencies
- Integration tests are marked and can be skipped in CI
- Tests provide clear pass/fail indicators

## Debugging Tests

### Verbose Output
```bash
pytest -v -s tests/unit/test_docker_adapter.py
```

### Debug Specific Test
```bash
pytest tests/unit/test_docker_adapter.py::TestDockerAdapter::test_specific_method -v -s
```

### Coverage Report
```bash
pytest --cov=services tests/unit/
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Test names should describe what they test
3. **Mocking**: Use mocks for external dependencies in unit tests
4. **Data**: Use fixtures for consistent test data
5. **Markers**: Use appropriate markers for test categorization
6. **Error Handling**: Test both success and failure scenarios
