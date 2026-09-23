"""
Structured application logging for FASHORA Agent 1.
Logs request ID, endpoints, processing stages, and execution timings without leaking sensitive data.
"""

import logging
import json
import sys
import time
from typing import Optional, Dict, Any


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Attach context attributes if present
        for key in ["request_id", "endpoint", "processing_stage", "duration_ms", "user_id", "status_code", "error_code"]:
            if hasattr(record, key):
                val = getattr(record, key)
                # Ensure no secrets leak
                if key in ["password", "token", "secret", "api_key"]:
                    continue
                log_obj[key] = val
                
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)


def get_logger(name: str = "fashora.agent1") -> logging.Logger:
    """Returns a configured logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger()
