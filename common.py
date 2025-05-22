import logging
from logging.config import dictConfig

def setup_logging():
    """ Sets up logging """
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)d: %(message)s",
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
                    "when":"midnight",
                    "interval": 1,
                    "backupCount": 7
                }
            },
            "root": {
                "level": "INFO", 
                "handlers": ["console", "file"]
            }
        }
    )