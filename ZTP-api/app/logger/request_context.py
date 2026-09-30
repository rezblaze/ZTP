import logging
from contextvars import ContextVar, Token

REQUEST_ID_CTX_KEY = "request_id"
_request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


def set_request_id(request_id) -> Token:
    return _request_id_ctx_var.set(request_id)


def reset_request_id(request_id):
    return _request_id_ctx_var.reset(request_id)


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True
