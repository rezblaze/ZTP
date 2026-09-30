import asyncio
import logging
import os
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_offline import FastAPIOffline
from uvicorn import Config, Server

from app.config import config
from app.logger import bmi_api_logging as bmi_logging
from app.logger import logging_middleware
from app.routes import (
    abort_routes,
    admin_routes,
    baseline_routes,
    bmo_routes,
    build_routes,
    health_routes,
    status_routes,
    useful_routes,
)
from app.service.kafka_service import setup_faust_app
from app.service.splunk_service import api_data_to_spunk

# Load settings and version
settings = config.get_setting()
os.environ["PYTHONASYNCIODEBUG"] = "1"
try:
    with open("version.text", "r") as f:
        BMIAPI_VERSION = f.read().split("=")[1].strip()
except Exception:
    raise Exception("version file not found")

# Setup logging
bmi_logging.setup_logging()
logger = logging.getLogger(__name__)

# UI URL for description
ui = f"https://{settings.bmi_env}/static/index.html"
# Main app description
DISCRIPTION = f"""
**B**are **M**etal **I**maging **API** *powered by* **ZTP**
[Documentation](https://github.example.com/example-org/ztp)
[Issues](https://github.example.com/example-org/ztp/issues)
[Dashboard](https://monitoring.example.com/en-US/app/company_bmi_app/company_bmi_dashboard)
[BMI User Interface]({ui})
"""
# Admin sub-API description
ADMIN_DESCRIPTION = """
Admin Portal
[http://bmi-stage.example.com:2812](http://bmi-stage.example.com:2812)
[http://bmi-prod.example.com:2812](http://bmi-prod.example.com:2812)
"""


# Lifespan context manager for Faust and Splunk
@asynccontextmanager
async def lifespan(app: FastAPIOffline):
    logger.info("fn: lifespan starting faust")
    faust_app = setup_faust_app(asyncio.get_running_loop())
    await faust_app.start()
    if settings.bmi_env in ["bmi-stage.example.com", "bmi-prod.example.com"]:
        logger.info("fn:lifespan creating new thread for api_data_to_spunk")
        api_data_thrd = Thread(target=api_data_to_spunk)
        api_data_thrd.start()
    yield
    logger.info("fn:lifespan stopping faust")
    await faust_app.stop()
    logger.info("fn:lifespan End of lifespan")


# Main FastAPI app
app = FastAPIOffline(
    title="BMI API",
    description=DISCRIPTION,
    version=f"{BMIAPI_VERSION}",
    docs_url="/",
    openapi_url="/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

# Mount static files
script_dir = os.path.dirname(__file__)
static_dir = os.path.join(script_dir, "static")
if not os.path.exists(static_dir):
    logger.error(f"Static directory does not exist: {static_dir}")
    raise Exception(f"Static directory not found: {static_dir}")
logger.info(f"Mounting static_dir: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

# CORS middleware for main app
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers for main app
app.include_router(build_routes.router)
app.include_router(baseline_routes.router)
app.include_router(status_routes.router)
app.include_router(abort_routes.router)
app.include_router(useful_routes.router)
app.include_router(health_routes.router)

# BMO sub-API
bmo_api = FastAPIOffline(
    title="BMO API",
    description="Bare Metal Operations",
    version=f"{BMIAPI_VERSION}",
    docs_url="/",
    openapi_url="/openapi.json",
    redoc_url=None,
)
bmo_api.include_router(bmo_routes.router)
bmo_api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin sub-API
admin_api = FastAPIOffline(
    title="Admin sub API",
    description=ADMIN_DESCRIPTION,
    version=f"{BMIAPI_VERSION}",
    docs_url="/",
    openapi_url="/openapi.json",
    redoc_url=None,
)
admin_api.include_router(admin_routes.router)
admin_api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount sub-APIs
app.mount(path="/bmo", app=bmo_api)
app.mount(path="/admin", app=admin_api)

# Uvicorn server configuration
uvicorn_config = Config(app=app, host="0.0.0.0", port=8080)
uvicorn_server = Server(uvicorn_config)


# Custom logging middleware
@app.middleware("http")
async def log_request(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await logging_middleware.log_request(request, call_next)
        logger.info(f"Response status: {response.status_code} for {request.url}")
        return response
    except Exception as e:
        logger.error(f"Error in middleware for {request.url}: {str(e)}")
        raise


if __name__ == "__main__":
    logger.info("Starting server")
    uvicorn_server.run()
