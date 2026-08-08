import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)
        
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str = "mingli-agent") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())
    
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logger()