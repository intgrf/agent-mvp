import time
import grpc
from grpc import UnaryUnaryClientInterceptor

class LoggingUnaryClientInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, logger, mask_keys=frozenset({"authorization"}), max_body=8_192):
        self.logger = logger
        self.mask_keys = {k.lower() for k in mask_keys}
        self.max_body = max_body

    def intercept_unary_unary(self, continuation, client_call_details, request):
        t0 = time.perf_counter()

        md = list(client_call_details.metadata or [])
        md_sanitized = [
            (k, "***" if k.lower() in self.mask_keys else v)
            for k, v in md
        ]

        self.logger.info("rqMessage: METHOD=%s METADATA=%s BODY=%s",
                         client_call_details.method, md_sanitized, safe_proto(request, self.max_body))

        try:
            response = continuation(client_call_details, request)

            dt_ms = (time.perf_counter() - t0) * 1000
            # unary: first_byte_time почти равно execution_time (если не используете with_call / future)
            self.logger.info("rsMessage: STATUS_CODE=OK IS_COMPLETE=True EXECUTION_TIME=%.0f FIRST_BYTE_TIME=%.0f BODY=%s",
                             dt_ms, dt_ms, safe_proto(response, self.max_body))
            return response

        except grpc.RpcError as e:
            dt_ms = (time.perf_counter() - t0) * 1000
            code = e.code()
            details = e.details()
            self.logger.warning("rsMessage: STATUS_CODE=%s IS_COMPLETE=True EXECUTION_TIME=%.0f DETAILS=%r",
                                code, dt_ms, details)
            raise

def safe_proto(msg, max_body):
    # В реальности обычно: MessageToJson / MessageToDict (google.protobuf.json_format)
    s = str(msg)
    return s if len(s) <= max_body else s[:max_body] + "...<truncated>"