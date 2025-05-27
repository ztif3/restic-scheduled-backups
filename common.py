import logging
from logging.config import dictConfig
from multiprocessing_logging import install_mp_handler

print(__name__)

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "style": "{",
                "format": "[{asctime}] - {levelname} - {filename}:{lineno:d}: {message}",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": "log",
                "formatter": "default",
                "when":"midnight",
                "interval": 1,
                "backupCount": 7
            }
        },
        "root": {
            "level": "DEBUG", 
            "handlers": ["console", "file"]
        }
    }
)

install_mp_handler()