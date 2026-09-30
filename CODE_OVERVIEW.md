# ZTP Repository Overview

## What this repository does

This repository is a Bare Metal Imaging / Zero Touch Provisioning (ZTP) project for HPE and Dell servers.

It is composed of three main parts:

1. `ZTP/` - core Python library and device automation modules for server provisioning, hardware control, and health checks.
2. `ZTP-api/` - a FastAPI-based service that exposes provisioning APIs and queues build requests.
3. `ZTP-builder/` - a builder service that consumes Kafka build requests and executes provisioning workflows.

---

## Technologies used

- Python 3.8+ compatible
- FastAPI for HTTP API routing and documentation
- `fastapi_offline` for the API server wrapper
- Uvicorn for serving ASGI apps
- Kafka for build queueing
- Faust streaming integration for asynchronous Kafka handling
- `requests`, `httpx`, `aiohttp` for HTTP/REST interactions
- `pydantic-settings`, `python-dotenv` for configuration
- `uvicorn`, `jinja2`, `psutil`, `cryptography`, `validators`
- Redfish / iDRAC / HPE iLO automation via REST APIs
- Static UI file mounting for dashboard assets

---

## Main components

### `ZTP/` core package

This package contains server automation functionality and hardware-specific drivers.

Key modules:

- `action.py` - central `Actions` class that performs lifecycle operations such as firmware checks, configuration, OS deployment, secure boot, power control, and post-provisioning steps.
- `dell.py` - Dell server automation and Redfish/iDRAC helpers, including power, virtual media, BIOS configuration, RAID, firmware, encryption, and job tracking.
- `hphpe.py` - HPE server and iLO automation for power control, BIOS, firmware, deployment, secure boot, and HPE-specific baseline operations.
- `ilo.py` / `idrac.py` - HPE iLO and Dell iDRAC action classes for specialized management flows.
- `networkdata.py` - utilities for network discovery and server inventory data.
- `sanitycheck.py` - DNS, ping, and power-state validations used before triggering builds.
- `serverhealth.py` - ESXi/RHEL server health checks.
- `secrets.py` - credential retrieval for management interfaces.
- `immutable.py` - helper utilities for immutable objects and payload handling.

`ZTP/__init__.py` exposes the primary library classes and functions for external use.

---

### `ZTP-api/` service

This is the public API service for the BMI/ZTP platform.

Key elements:

- `app/main.py` - startup logic and FastAPI application configuration.
  - Creates the main API app plus mounted sub-apps for `/bmo` and `/admin`.
  - Sets up CORS and static file serving.
  - Uses a lifespan manager to start Faust and optionally Spin up Splunk logging threads.

- `app/routes/` - HTTP endpoints organized by capability:
  - `build_routes.py` - create Linux, Windows, ESXi build requests.
  - `status_routes.py` - query build status and event streams.
  - `abort_routes.py` - abort active builds.
  - `baseline_routes.py` - invoke baseline/prep and firmware operations.
  - `health_routes.py` - health checks and service status.
  - `admin_routes.py` / `bmo_routes.py` / `useful_routes.py` - admin and operational convenience endpoints.

- `app/service/` - core business logic:
  - `build_service.py` - validates builds, checks server readiness, creates build events, and queues builds to Kafka.
  - `status_service.py` - stores and retrieves build lifecycle events.
  - `kafka_service.py` - interfaces with Kafka and publishes build requests/events.
  - `loran_service.py` - publishes host build metadata to an external service.
  - `splunk_service.py` - forwards analytics and logging events to Splunk.

- `app/config/` - environment-specific configuration and settings management.
- `app/logger/` - logging middleware and request/response logging.
- `app/dto/` - Pydantic DTOs for build request payloads and status responses.
- `app/common/` - domain definitions for build types, statuses, and sanity rules.

---

### `ZTP-builder/` service

This component consumes build jobs from Kafka and executes the provisioning workflows.

Key flow:

- `app/main.py` - starts the builder by launching `message_consumer.start_consumer()`.
- `app/message_consumer.py` - subscribes to the `server_builds` Kafka topic and spawns a separate process for each incoming build.
- `app/builders/build_runner.py` - orchestrates build execution and maps build types to builder workflows.
  - Supports Linux, Windows, ESXi, test builds, and HPE/Dell baseline flows.
  - Emits build events for status transitions: QUEUED, PROCESSING, COMPLETE, ERROR, ABORTING, ABORTED.
  - Handles abort logic with process termination and server power-off via ZTP actions.

Builder modules under `app/builders/` implement platform-specific build steps:

- `linux_builder.py`
- `windows_builder.py`
- `esxi_builder.py`
- `baseline_hpe.py`
- `baseline_dell.py`
- `test_builder.py`

---

## How it works together

1. API client submits a build request to `ZTP-api`.
2. `build_service.create_build()` validates the request, verifies network/server metadata, and checks current status.
3. Approved builds are queued into Kafka via `kafka_service.queue_build()`.
4. `ZTP-builder` consumes Kafka messages and executes the selected provisioning workflow.
5. Build progress is persisted through status events and available via `/builds/status/{build_id}` and `/builds/events/{build_id}`.
6. Abort handling can stop queued or running builds and optionally power off the target server.

---

## Key capabilities

- Bare metal provisioning for Linux, Windows, and VMware ESXi
- HPE and Dell hardware management through iLO and iDRAC
- BIOS and firmware baseline enforcement
- Secure boot and TPM readiness validation
- Build lifecycle tracking and abort support
- Kafka-based asynchronous build orchestration
- FastAPI-based REST API with OpenAPI docs

---

## Notes

- `ZTP-api/requirements.txt` defines API dependencies.
- `ZTP-builder/requirements.txt` defines builder/runtime dependencies.
- The repository appears to be designed for enterprise bare-metal operations with environment-specific configuration and external service integrations.

If you want, I can also create a shorter `README.md` replacement for the root of the repo that summarizes just the primary workflow and commands.