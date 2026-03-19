from abc import ABC, abstractmethod
from typing import List, Dict, Any
import queue

class BaseMiner(ABC):
    """Abstract base class for all marketplace miners."""
    def __init__(self, page, config: Dict[str, Any], log_queue: queue.Queue, 
                 progress_start: float, progress_end: float, stop_event=None):
        self.page = page
        self.config = config
        self.log_queue = log_queue
        self.ps = progress_start
        self.pe = progress_end
        self.stop_event = stop_event
        self.marketplace_name = self.__class__.__name__.replace("Miner", "")

    def log(self, message: str, progress: float = None):
        """Sends a log message to the log queue, with optional progress value."""
        data = {"message": message, "marketplace": self.marketplace_name}
        if progress is not None:
            # Scale progress to the specific miner's segment
            scaled_progress = self.ps + (self.pe - self.ps) * progress
            data["progress"] = min(scaled_progress, self.pe)
            
        self.log_queue.put({"type": "update", **data})

    def check_stop(self) -> bool:
        """Checks if a stop event has been triggered."""
        if self.stop_event and self.stop_event.is_set():
            self.log(f"🛑 {self.marketplace_name}: Interrupção solicitada pelo usuário.")
            return True
        return False

    @abstractmethod
    def run(self):
        """Main execution method for the miner, to be implemented by child classes."""
        pass
