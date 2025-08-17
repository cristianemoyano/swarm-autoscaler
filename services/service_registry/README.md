# Service Registry

A unified microservice that provides service discovery and caching functionality for Docker Swarm environments.

## Overview

The Service Registry provides:
- **Service Discovery**: Automatically discovers Docker Swarm services with autoscaler labels
- **In-Memory Caching**: Maintains a constant pool of discovered services for low-latency access
- **REST API**: HTTP/2 enabled API for querying services and metrics
- **Event Publishing**: Optional RabbitMQ integration for real-time service updates
- **Metrics Collection**: Docker stats-based metrics collection for services

## Architecture

The service is built with a modular architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DockerSwarm   │    │   CacheManager  │    │    Publisher    │
│    Adapter      │    │                 │    │                 │
│                 │    │                 │    │                 │
│ - Service       │◄──►│ - In-memory     │◄──►│ - RabbitMQ      │
│   discovery     │    │   cache         │    │   events        │
│ - Docker events │    │ - Refresh logic │    │ - Health checks │
│ - Metrics       │    │ - Change detect │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   REST API      │
                       │                 │
                       │ - HTTP/2        │
                       │ - Service query │
                       │ - Metrics       │
                       │ - Cache mgmt    │
                       └─────────────────┘
```

## Features

### Service Discovery
- Automatically discovers Docker Swarm services with `autoscaler.enabled=true` label
- Real-time monitoring of service changes via Docker events
- Configurable label-based filtering

### Caching
- In-memory cache with thread-safe access
- Periodic background refresh (configurable interval)
- Change detection to avoid unnecessary updates
- Cache statistics and management endpoints

### REST API
- HTTP/2 support via Hypercorn
- Comprehensive service querying
- Metrics retrieval
- Cache management operations
- Health checks with detailed status

### Event Publishing
- Optional RabbitMQ integration
- Real-time service change notifications
- Metrics update events
- Health check events

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5001` | HTTP server port |
| `HOST` | `0.0.0.0` | HTTP server host |
| `REFRESH_INTERVAL_SEC` | `30` | Service cache refresh interval |
| `METRICS_REFRESH_INTERVAL_SEC` | `60` | Metrics refresh interval |
| `DOCKER_BASE_URL` | `unix:///var/run/docker.sock` | Docker daemon URL |
| `RABBITMQ_URL` | `` | RabbitMQ connection URL (optional) |
| `RABBITMQ_EXCHANGE` | `service-registry` | RabbitMQ exchange name |
| `LOG_LEVEL` | `INFO` | Logging level |

### Docker Labels

The service looks for these labels on Docker Swarm services:

| Label | Default | Description |
|-------|---------|-------------|
| `autoscaler.enabled` | `false` | Enable autoscaling for this service |
| `autoscaler.metric` | `cpu` | Primary metric type (`cpu` or `memory`) |
| `autoscaler.cpu.threshold` | `70` | CPU usage threshold percentage |
| `autoscaler.memory.threshold` | `70` | Memory usage threshold percentage |
| `autoscaler.min` | `1` | Minimum replica count |
| `autoscaler.max` | `2` | Maximum replica count |

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status including cache and publisher status.

### Services
```
GET /services
```
Returns all discovered services with metadata.

```
GET /services/{service_name}
```
Returns a specific service by name.

### Metrics
```
GET /services/{service_name}/metrics
```
Returns cached metrics for a service.

```
POST /services/{service_name}/metrics
```
Force refresh metrics for a service.

### Cache Management
```
GET /cache/stats
```
Returns cache statistics.

```
POST /cache/refresh
```
Force refresh the services cache.

```
POST /cache/clear
```
Clear all cached data.

### Events
```
GET /events
```
Returns information about available events and RabbitMQ status.

## RabbitMQ Events

When RabbitMQ is configured, the service publishes these events:

| Event | Routing Key | Description |
|-------|-------------|-------------|
| `services.updated` | `services.updated` | All services updated |
| `service.added` | `service.added` | New service discovered |
| `service.removed` | `service.removed` | Service removed |
| `service.updated` | `service.updated` | Service configuration changed |
| `metrics.{service_name}` | `metrics.{service_name}` | Service metrics updated |
| `health.check` | `health.check` | Periodic health check |

## Usage Examples

### Basic Service Query
```bash
curl http://localhost:5001/services
```

### Get Specific Service
```bash
curl http://localhost:5001/services/my-app
```

### Get Service Metrics
```bash
curl http://localhost:5001/services/my-app/metrics
```

### Force Refresh Cache
```bash
curl -X POST http://localhost:5001/cache/refresh
```

### Health Check
```bash
curl http://localhost:5001/health
```

## Docker Swarm Deployment

### Using the Suite Image
The Service Registry is deployed as part of the unified `swarm-autoscaler-suite` image using the `ROLE=service-registry` environment variable.

### Deploy with Swarm Stack
```bash
# Deploy using the samples (recommended for testing)
./samples/deploy.sh cpu

# Or deploy with custom image/tag
./samples/deploy.sh cpu my-registry/swarm-autoscaler-suite v1.0.0
```

### Environment Variables
The service uses the same `clifford666/swarm-autoscaler-suite` image as other services:
- `ROLE=service-registry` - Identifies this as the service registry
- `SUITE_IMAGE` - Override the default image (optional)
- `SUITE_TAG` - Override the default tag (optional)

## Integration with Autoscaler

The Service Registry is designed to work seamlessly with the Autoscaler service:

```python
# Configuration
service_registry_url = "http://service-registry:5001"
```

### Swarm Stack Integration
When deploying the complete autoscaler suite, the Service Registry will be available to other services via the `autoscaler_net` overlay network.



## Monitoring

### Health Checks
The service provides comprehensive health checks at `/health` that include:
- Service status
- Cache statistics
- Publisher connection status
- Last refresh timestamp

### Logging
Structured logging with role-based formatting:
```
2024-01-15T10:30:00+00:00 INFO role=service-registry logger=main service registry initialized
```

### Metrics
Cache statistics are available via the `/cache/stats` endpoint:
- Services count
- Metrics count
- Cache version
- Last refresh time

## Troubleshooting

### Common Issues

1. **No services discovered**
   - Check Docker labels: `autoscaler.enabled=true`
   - Verify Docker socket access
   - Check service logs for discovery errors

2. **RabbitMQ connection issues**
   - Verify `RABBITMQ_URL` format
   - Check network connectivity
   - Review RabbitMQ logs

3. **High memory usage**
   - Adjust refresh intervals
   - Monitor cache size
   - Consider service limits

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
```

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

### Testing
```bash
# Health check
curl http://localhost:5001/health

# List services
curl http://localhost:5001/services

# Cache stats
curl http://localhost:5001/cache/stats
```

### Swarm Testing
```bash
# Deploy to swarm for testing using samples
./samples/deploy.sh cpu

# Test endpoints
curl http://localhost:5001/health

# Remove test deployment
./samples/down.sh cpu
```

## Contributing

1. Follow the modular architecture
2. Add comprehensive logging
3. Include error handling
4. Update documentation
5. Add tests for new features

## License

This project is part of the Swarm Autoscaler system. See the main LICENSE file for details.
