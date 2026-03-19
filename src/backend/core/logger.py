import logging
import queue
import datetime

class UIHandler(logging.Handler):
    """Custom logging handler to push log messages to a queue for real-time UI updates."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        log_entry = self.format(record)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put({
            "type": "log",
            "message": f"[{timestamp}] {log_entry}",
            "level": record.levelname
        })

def setup_logger(name: str, log_queue: queue.Queue = None):
    """Configures a logger with console and optional UI/Queue output."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        formatter = logging.Formatter('%(message)s')
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # UI Handler (Queue)
        if log_queue:
            ui_handler = UIHandler(log_queue)
            ui_handler.setFormatter(formatter)
            logger.addHandler(ui_handler)
            
    return logger
