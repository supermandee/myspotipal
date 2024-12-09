import logging
import sqlite3
import threading
import traceback 

class SQLiteHandler(logging.Handler):
    def __init__(self, db='app_logs.db'):
        super().__init__()
        self.db = db
        self.lock = threading.Lock()
        self._initialize_database()

    def _initialize_database(self):
        # Initialize the database schema
        conn = sqlite3.connect(self.db)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL,
                level TEXT,
                module TEXT,
                funcName TEXT,
                lineno INTEGER,
                message TEXT,
                args TEXT,
                exc_info TEXT,
                processName TEXT,
                threadName TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def formatException(self, exc_info):
        if exc_info:
            return ''.join(traceback.format_exception(*exc_info))
        return ''

    def emit(self, record):
        try:
            # Format the record to ensure message is ready
            self.format(record)
            log_entry = (
                record.created,
                record.levelname,
                record.module,
                record.funcName,
                record.lineno,
                record.getMessage(),
                str(record.args),
                self.formatException(record.exc_info) if record.exc_info else None,
                record.processName,
                record.threadName,
            )
            insert_sql = '''
                INSERT INTO logs (
                    created, level, module, funcName, lineno, message, args, exc_info, processName, threadName
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            # Create a new connection for this thread
            conn = sqlite3.connect(self.db)
            with conn:
                conn.execute(insert_sql, log_entry)
        except Exception:
            self.handleError(record)


def setup_logger(name=None, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding multiple handlers if the logger is already configured
    if not logger.handlers:
        sqlite_handler = SQLiteHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
        sqlite_handler.setFormatter(formatter)
        logger.addHandler(sqlite_handler)

    return logger