[![Autoscaller Build](https://github.com/AMEST/swarm-autoscaler/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/AMEST/swarm-autoscaler/actions/workflows/main.yml)
![hub.docker.com](https://img.shields.io/docker/pulls/eluki/swarm-service-autoscaler.svg)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/amest/swarm-autoscaler)
![GitHub](https://img.shields.io/github/license/amest/swarm-autoscaler)

# Swarm Service Autoscaler

## Links  

* **[Docker hub](https://hub.docker.com/r/eluki/swarm-service-autoscaler)**

***

## Description

The project is an application that implements the ability to dynamically change the number of service instances under high load. The application receives all services that have the `swarm.autoscale` label enabled, calculates the average value of the CPU utilization and, based on this, either increases the number of instances or decreases it.

Currently, both CPU and memory metrics are supported for autoscaling. By default, if the CPU load reaches 85%, the service will scale, if it reaches 25%, it will be scaled down.
But the minimum and maximum values ​​of CPU utilization can be changed through environment variables.

Also, for each service, you can set the maximum and minimum number of replicas to prevent a situation with an uncontrolled increase in the number of replicas (or too much decrease)

### Metrics Sources

The autoscaler supports two metrics sources:

1. **Docker API** (default): Uses Docker's stats API to collect metrics
2. **cAdvisor** (recommended): Uses cAdvisor for more efficient metric collection with minimal impact on the Docker daemon

For production environments, we recommend using cAdvisor as it provides better performance and scalability. See [CADVISOR_INTEGRATION.md](CADVISOR_INTEGRATION.md) for detailed setup instructions.

## Usage

1. Deploy Swarm Autoscaler using [`swarm-deploy.yml`](swarm-deploy.yml) from this repository
2. Add label `swarm.autoscale=true` for services you want to autoscale.

```yml
deploy:
  labels:
    - "swarm.autoscale=true"
```

For better resource management, it is recommended to add resource constraints to your service. Then it will definitely not eat more resources than necessary, and auto-scaling will work much better and will save resources in idle time.

```yml
deploy:
  resources:
    limits:
      cpus: '0.50'
      memory: '256M'
```

## Configuration

### Swarm Autoscaler configuration

_**The application is configured through environment variables**_

| Setting                     | Default Value      | Description                                                                             |
| --------------------------- | ------------------ | --------------------------------------------------------------------------------------- |
| `AUTOSCALER_MIN_PERCENTAGE` | 25                 | minimum service cpu utilization value in percent (0-100) for decrease replicas          |
| `AUTOSCALER_MAX_PERCENTAGE` | 85                 | maximum service cpu utilization value in percent (0-100) for increase replicas          |
| `AUTOSCALER_DNSNAME`        | `tasks.autoscaler` | swarm service name for in stack communication                                           |
| `AUTOSCALER_INTERVAL`       | 300                | interval between checks in seconds                                                      |
| `AUTOSCALER_DRYRUN`         | UNSET              | noop mode for check service functional without enable increment or decrement service replicas count. If environment variable set with any value - DryRun enabled. For disable need unset environment variable  |

### Services configuration

_**Services in docker swarm are configured via labels**_

| Setting                                   | Value   | Default                     | Description                                                                                                                                                                                |
| ----------------------------------------- | ------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `swarm.autoscale`                         | Boolean | `false`                     | Required. This enables autoscaling for a service. Anything other than `true` will not enable it                                                                                            |
| `swarm.autoscale.min`                     | Integer | `2`                         | Optional. This is the minimum number of replicas wanted for a service. The autoscaler will not downscale below this number                                                                 |
| `swarm.autoscale.max`                     | Integer | `15`                        | Optional. This is the maximum number of replicas wanted for a service. The autoscaler will not scale up past this number                                                                   |
| `swarm.autoscale.disable-manual-replicas` | Boolean | `false`                     | Optional. Disable manual control of replicas. It will no longer be possible to manually set the number of replicas more or less than the limit. Anything other than `true` will not enable |
| `swarm.autoscale.percentage-max`          | Integer | `AUTOSCALER_MAX_PERCENTAGE` | Optional. Custom maximum service cpu utilization for increase replicas                                                                                                                     |
| `swarm.autoscale.percentage-min`          | Integer | `AUTOSCALER_MIN_PERCENTAGE` | Optional. Custom minimum service cpu utilization for decrease replicas                                                                                                                     |
| `swarm.autoscale.decrease-mode`           | String  | `MEDIAN`                    | Optional. Service utilization calculation mode to decrease replicas. Modes: `MEDIAN`, `MAX`                                                                                                |
| `swarm.autoscale.metric`                  | String  | `cpu`                       | Optional. Metric used for autoscaling. Supported: `cpu`, `memory`                                                                                                                          |


## Local development

Run locally with Docker Swarm (recommended):

```bash
# Deploy the development stack
./samples/deploy.sh cpu
open http://localhost:8081
```

What this does:
- Uses the unified `clifford666/swarm-autoscaler-suite` image
- Runs all services (service-registry, autoscaler, docker-service, ui) with different roles
- Mounts the Docker socket so the autoscaler can talk to the local Docker daemon
- Runs in dry-run mode by default to avoid scaling actions during dev

Environment variables (as used in the swarm stack):

```yaml
services:
  autoscaler:
    environment:
      - ROLE=autoscaler
      - AUTOSCALER_DNSNAME=autoscaler
      - AUTOSCALER_INTERVAL=30
      - AUTOSCALER_DRYRUN=1   # remove to enable real scaling
      # - LOG_LEVEL=INFO      # optional, defaults to DEBUG
```

Stop and clean up:

```bash
./samples/down.sh cpu
```


## API

- GET `/`:
  - Health/status endpoint. Returns 200 with a short message.

- GET `/api/container/stats?id=<container_id>&cpuLimit=<limit>`:
  - Returns CPU usage percent for a container if it is running on this node.
  - `cpuLimit` is used to normalize CPU percentage according to service limits (e.g., 0.5).
  - Example:
    ```bash
    curl "http://localhost:8080/api/container/stats?id=<container_id>&cpuLimit=0.5"
    ```

- GET `/api/container/stats?id=<container_id>&metric=memory`:
  - Returns memory usage percent calculated from Docker stats (`usage/limit*100`).
  - Example:
    ```bash
    curl "http://localhost:8080/api/container/stats?id=<container_id>&metric=memory"
    ```


## Logging

Logging is configured via `src/logging_config.py`.

- Set the level with `LOG_LEVEL` env var (e.g., `INFO`, `DEBUG`, `WARNING`). Defaults to `DEBUG`.
- Noise from `urllib3`, `werkzeug`, and `docker` is reduced to `INFO` by default.


## Running without Docker Compose

Build and run the container directly:

```bash
docker build -t swarm-autoscaler:dev .
docker run -d \
  -p 8080:80 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e AUTOSCALER_DRYRUN=1 \
  --name swarm-autoscaler-dev \
  swarm-autoscaler:dev
```


## Deploy to Docker Swarm

Use the provided `swarm-deploy.yml` stack file. It runs the autoscaler in `global` mode on all nodes and mounts the Docker socket.

```bash
docker stack deploy -c swarm-deploy.yml autoscaler
```

Make sure target services you want to autoscale have labels set (see table above), for example:

```yaml
deploy:
  labels:
    - "swarm.autoscale=true"
    - "swarm.autoscale.metric=memory" # use memory metric instead of CPU
  resources:
    limits:
      cpus: '0.50'
      memory: '256M'
```


## Project layout

### Core Services
- `services/autoscaler/`: Main autoscaling service that evaluates and scales services
- `services/service-registry/`: Unified service discovery and caching
- `services/docker-service/`: Docker service operations and scaling logic
- `services/ui/`: Web interface for monitoring and management
- `services/common/`: Shared utilities and configurations



### Architecture Overview

The system uses a unified **Service Registry** that provides service discovery and caching:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Autoscaler    │    │ Service Registry │    │  Docker Service │
│                 │    │                 │    │                 │
│ - Evaluates     │◄──►│ - Discovery     │◄──►│ - Scaling       │
│   metrics       │    │ - Caching       │    │   operations    │
│ - Makes scaling │    │ - REST API      │    │ - Service mgmt  │
│   decisions     │    │ - Event pub     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Service Registry Features
- **Unified Discovery**: Automatically discovers Docker Swarm services with autoscaler labels
- **In-Memory Caching**: Maintains a constant pool of discovered services for low-latency access
- **HTTP/2 REST API**: Fast, modern API for querying services and metrics
- **Event Publishing**: Optional RabbitMQ integration for real-time updates
- **Metrics Collection**: Docker stats-based metrics collection

See `services/service-registry/README.md` for detailed documentation.

## Samples

Try ready-made Swarm stacks for CPU and memory autoscaling under `samples/`.

Prerequisites:
- Enable Swarm: `docker swarm init` (once per machine)

CPU sample (exposes port 8081):
```bash
./samples/deploy.sh cpu
# open http://localhost:8081
```

Memory sample (exposes port 8082):
```bash
./samples/deploy.sh memory
# open http://localhost:8082
```

Cleanup:
```bash
docker stack rm autoscale-cpu || true
docker stack rm autoscale-mem || true
```

Notes:
- The sample stacks reference the autoscaler image used in `samples/swarm-stack-*.yml` (currently `clifford666/swarm-autoscaler:latest`).
- Update the image there if you publish under a different Docker Hub user.

### Observe scaling

Watch the sample service tasks and overall service list:

```bash
# CPU sample
while true; do docker service ps autoscale-cpu_autoscaler; sleep 5; clear; done

# Memory sample
while true; do docker service ps autoscale-mem_sample; sleep 5; clear; done

# Also helpful
while true; do docker service ls; sleep 5; clear; done
```

View autoscaler logs:

```bash
# CPU sample autoscaler
docker service logs -f autoscale-cpu_autoscaler

# Memory sample autoscaler
docker service logs -f autoscale-mem_autoscaler
```

### Force a scale event

CPU sample (port 8081): generate concurrent requests to push CPU usage:

```bash
# Using hey (macOS: brew install hey)
hey -z 2m -c 200 http://localhost:8081/


hey -z 2m -c 200 http://localhost:8082/
```

Memory sample (port 8082): nginx is light on memory by default. You can temporarily stress memory to trigger scaling:


docker service rm autoscale-memory_sample

## Publish image to Docker Hub

Use the helper script to build and push your image under your Docker Hub user:

```bash
# Option A: With interactive login (you must be logged in already via `docker login`)
./scripts/publish.sh <your_dockerhub_user> [tag]

# Option B: Non-interactive login
DOCKERHUB_USER=<user> DOCKERHUB_TOKEN=<access_token> TAG=<tag> ./scripts/publish.sh

# Examples
./scripts/publish.sh myuser v0.1.0
./scripts/publish.sh myuser        # defaults to :latest
```

By default the image name is `swarm-autoscaler`. Change it with `IMAGE_NAME` if you prefer a different repo name:

```bash
IMAGE_NAME=my-swarm-autoscaler ./scripts/publish.sh myuser v0.1.0
```
