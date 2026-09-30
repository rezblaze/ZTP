import logging
from uuid import uuid4

from fastapi import Request

from app.logger import request_context


async def log_request(request: Request, call_next):
    logger = logging.getLogger(__name__)
    request_id = request_context.set_request_id(str(uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_context.get_request_id()
    logger.info(f"{request.method}: {request.url.path} response_code={response.status_code}")
    request_context.reset_request_id(request_id)
    return response
