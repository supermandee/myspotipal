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

    def log_traceloop_span(self, span):
        """
        Logs a Traceloop span into the traceloop_logs table.
        """
        attributes_json = json.dumps(span.attributes) if span.attributes else None
        span_entry = (
            span.start_time,
            span.context.span_id,
            span.context.trace_id,
            span.name,
            attributes_json,
            span.kind.name,
            span.status.status_code.name if span.status else "UNSET",
        )
        insert_sql = '''
            INSERT INTO traceloop_logs (
                timestamp, span_id, trace_id, span_name, attributes, kind, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        # Wrap only the database operations in the try block
        try:
            conn = sqlite3.connect(self.db)
            with conn:
                conn.execute(insert_sql, span_entry)
        except sqlite3.Error as db_error:
            logging.error(f"Database error while logging Traceloop span: {db_error}")
        except Exception as e:
            logging.error(f"Unexpected error while logging Traceloop span: {e}")
    
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