from contextvars import ContextVar, Token

CORRELATION_ID_CTX_KEY = "correlation_id"
REQUEST_ID_CTX_KEY = "request_id"
BUILD_ID_CTX_KEY = "build_id"
BUILD_HOST_CTX_KEY = "build_host"

_correlation_id_ctx_var: ContextVar[str] = ContextVar(CORRELATION_ID_CTX_KEY, default="")
_request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default="")
_build_id_ctx_var: ContextVar[str] = ContextVar(BUILD_ID_CTX_KEY, default="")
_build_host_ctx_var: ContextVar[str] = ContextVar(BUILD_HOST_CTX_KEY, default="")


def get_correlation_id() -> str:
    return _correlation_id_ctx_var.get()


def get_request_id() -> str:
    return _request_id_ctx_var.get()


def get_build_id() -> str:
    return _build_id_ctx_var.get()


def get_build_host() -> str:
    return _build_host_ctx_var.get()


def set_correlation_id(correlation_id) -> Token:
    return _correlation_id_ctx_var.set(correlation_id)


def set_request_id(request_id) -> Token:
    return _request_id_ctx_var.set(request_id)


def set_build_id(build_id) -> Token:
    return _build_id_ctx_var.set(build_id)


def set_build_host(build_host) -> Token:
    return _build_host_ctx_var.set(build_host)


def reset_request_id(request_id):
    return _request_id_ctx_var.reset(request_id)


def reset_correlation_id(correlation_id):
    return _correlation_id_ctx_var.reset(correlation_id)


def reset_build_id(build_id):
    return _build_id_ctx_var.reset(build_id)
