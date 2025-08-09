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

Currently, only the CPU is used for autoscaling in the project. By default, if the CPU load reaches 85%, the service will scale, if it reaches 25%, it will be scaled down.
But the minimum and maximum values ​​of CPU utilization can be changed through environment variables.

Also, for each service, you can set the maximum and minimum number of replicas to prevent a situation with an uncontrolled increase in the number of replicas (or too much decrease)

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

Run locally with Docker Compose (recommended):

```bash
docker compose build
docker compose up -d
open http://localhost:8080
```

What this does:
- Builds an image using Python 3.13 and installs dependencies with `uv`.
- Runs the app with Gunicorn on port 80 and maps it to `localhost:8080`.
- Mounts your source code (`./src`) into the container for quick edits (with `--reload`).
- Mounts the Docker socket so the autoscaler can talk to the local Docker daemon.
- Runs in dry-run mode by default to avoid scaling actions during dev.

Environment variables (as used in `docker-compose.yml`):

```yaml
services:
  autoscaler:
    environment:
      - AUTOSCALER_DNSNAME=autoscaler
      - AUTOSCALER_INTERVAL=30
      - AUTOSCALER_DRYRUN=1   # remove to enable real scaling
      # - LOG_LEVEL=INFO      # optional, defaults to DEBUG
```

Stop and clean up:

```bash
docker compose down
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

- `src/main.py`: App bootstrap and Flask app factory. Starts the autoscaler thread.
- `src/settings.py`: Centralized configuration from environment variables.
- `src/logging_config.py`: Logging setup with optional `LOG_LEVEL`.
- `src/docker_service.py`: Docker client operations and scaling logic.
- `src/autoscaler_service.py`: Autoscaling loop/thread.
- `src/discovery.py`: Cluster discovery and in-cluster requests.
- `src/container_controller.py`: Flask API endpoints.
- `docker-compose.yml`: Local development environment.
- `swarm-deploy.yml`: Swarm deployment manifest (global service).
- `Dockerfile`: Production-ready image using Gunicorn and `uv` for deps.
