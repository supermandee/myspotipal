import logging
from logging.handlers import RotatingFileHandler
import os
import sys

def setup_logging():
    # Create log directory
    log_dir = '/var/log/myspotipal'
    os.makedirs(log_dir, exist_ok=True)

    # Configure formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(process)d] %(module)s: %(message)s'
    )

    # Create handlers
    handlers = {
        'app': RotatingFileHandler(f'{log_dir}/app.log', maxBytes=10485760, backupCount=5),
        'spotify': RotatingFileHandler(f'{log_dir}/spotify.log', maxBytes=10485760, backupCount=5),
        'llm': RotatingFileHandler(f'{log_dir}/llm.log', maxBytes=10485760, backupCount=5),
        'error': RotatingFileHandler(f'{log_dir}/error.log', maxBytes=10485760, backupCount=5),
        'console': logging.StreamHandler(sys.stdout)
    }

    # Set levels for handlers
    handlers['app'].setLevel(logging.INFO)  # Log INFO and above for the app
    handlers['spotify'].setLevel(logging.INFO)  # Log INFO and above for Spotify
    handlers['llm'].setLevel(logging.INFO)  # Log INFO and above for LLM
    handlers['error'].setLevel(logging.ERROR)  # Log only ERROR and above for error log
    handlers['console'].setLevel(logging.INFO)  # Log INFO and above to console

    # Add formatter to all handlers
    for handler in handlers.values():
        handler.setFormatter(formatter)

    # Create loggers
    loggers = {
        'app': logging.getLogger('app'),
        'spotify_client': logging.getLogger('spotify_client'),
        'llm_client': logging.getLogger('llm_client')
    }

    # Configure each logger
    for name, logger in loggers.items():
        logger.setLevel(logging.INFO)  # Suppress DEBUG logs
        logger.propagate = False  # Prevent propagation to root logger

        # Add appropriate handlers
        if name == 'app':
            logger.addHandler(handlers['app'])
        elif name == 'spotify_client':
            logger.addHandler(handlers['spotify'])
        elif name == 'llm_client':
            logger.addHandler(handlers['llm'])

        # Add console handler
        logger.addHandler(handlers['console'])

    # Configure root logger for global error logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)  # Log only errors and critical issues
    root_logger.addHandler(handlers['error'])  # Add error log handler

    # Set urllib3 and other verbose libraries to WARNING level
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return loggers
