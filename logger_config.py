import logging
from logging.handlers import RotatingFileHandler
import os
import sys
def setup_logging():
    # Create log directory
    os.makedirs('/var/log/myspotipal', exist_ok=True)

    # Configure formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(process)d] %(module)s: %(message)s'
    )

    # Create filter to ignore connectionpool logs
    class IgnoreConnectionPoolFilter(logging.Filter):
        def filter(self, record):
            return not record.name.startswith('urllib3.connectionpool')

    # Create handlers
    handlers = {
        'app': RotatingFileHandler('/var/log/myspotipal/app.log', maxBytes=10485760, backupCount=5),
        'spotify': RotatingFileHandler('/var/log/myspotipal/spotify.log', maxBytes=10485760, backupCount=5),
        'llm': RotatingFileHandler('/var/log/myspotipal/llm.log', maxBytes=10485760, backupCount=5),
        'error': RotatingFileHandler('/var/log/myspotipal/error.log', maxBytes=10485760, backupCount=5),
        'console': logging.StreamHandler(sys.stdout)
    }

    # Configure handlers
    for name, handler in handlers.items():
        handler.setFormatter(formatter)
        handler.addFilter(IgnoreConnectionPoolFilter())

    # Set levels for handlers
    handlers['app'].setLevel(logging.DEBUG)
    handlers['spotify'].setLevel(logging.DEBUG)
    handlers['llm'].setLevel(logging.DEBUG)
    handlers['error'].setLevel(logging.ERROR)  # Only log errors
    handlers['console'].setLevel(logging.INFO)

    # Create loggers
    loggers = {
        'app': logging.getLogger('app'),
        'spotify_client': logging.getLogger('spotify_client'),
        'llm_client': logging.getLogger('llm_client')
    }

    # Configure each logger
    for name, logger in loggers.items():
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger

        # Add only the appropriate handlers
        if name == 'app':
            logger.addHandler(handlers['app'])
        elif name == 'spotify_client':
            logger.addHandler(handlers['spotify'])
        elif name == 'llm_client':
            logger.addHandler(handlers['llm'])

        # Add console handler
        logger.addHandler(handlers['console'])

    # Configure root logger to handle errors globally
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    root_logger.addHandler(handlers['error'])

    # Set urllib3 to WARNING level
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return loggers
