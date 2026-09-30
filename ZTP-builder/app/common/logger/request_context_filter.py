import logging

import app.common.logger.request_context as request_context


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = request_context.get_correlation_id()
        record.request_id = request_context.get_request_id()
        record.build_id = request_context.get_build_id()
        record.build_host = request_context.get_build_host()
        return True
