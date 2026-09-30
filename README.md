# ZTP

A bare-metal provisioning repository for HPE and Dell servers.

## What this repo contains

- `ZTP/` — core Python library for hardware automation, server sanity checks, Redfish/iLO/iDRAC operations, and provisioning helpers.
- `ZTP-api/` — FastAPI-based HTTP service that validates build requests and queues them into Kafka.
- `ZTP-builder/` — Kafka consumer and builder runtime that executes Linux, Windows, ESXi, and hardware baseline workflows.

## Primary workflow

1. Client submits a build request to the `ZTP-api` service.
2. API validates the request, confirms server metadata and readiness, and creates a build event.
3. Build requests are queued to Kafka.
4. `ZTP-builder` consumes the request and runs the appropriate provisioning workflow.
5. Build progress and status are tracked through lifecycle events.

## Quick start

Install dependencies for the API and builder:

```bash
pip install -r ZTP-api/requirements.txt
pip install -r ZTP-builder/requirements.txt
```

Start the API service:

```bash
python ZTP-api/app/main.py
```

Start the builder service:

```bash
python ZTP-builder/app/main.py
```

## Notes

- The API exposes endpoints for Linux, Windows, and ESXi builds, status polling, aborts, and hardware baselines.
- The builder spawns worker processes for each Kafka build message and updates status events.
- `ZTP-api` uses FastAPI, Uvicorn, Kafka, Faust streaming, and environment-driven configuration.
- `ZTP-builder` uses Kafka, process isolation, and the `ZTP` core library to manage hardware workloads.
 
