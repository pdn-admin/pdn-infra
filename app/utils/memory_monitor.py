"""
Memory Monitoring Utility

This module provides memory monitoring and cleanup functionality to prevent
memory leaks and help identify memory usage patterns in the PDN Chat application.
"""

import gc
import logging
import os
import psutil
import threading
import time
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Memory monitoring and cleanup utility."""
    
    def __init__(self, cleanup_interval: int = 300):  # 5 minutes
        """
        Initialize memory monitor.
        
        Args:
            cleanup_interval: Seconds between cleanup runs
        """
        self.cleanup_interval = cleanup_interval
        self.process = psutil.Process(os.getpid())
        self.monitoring = False
        self._cleanup_thread = None
        
    def start_monitoring(self) -> None:
        """Start background memory monitoring."""
        if self.monitoring:
            return
            
        self.monitoring = True
        self._cleanup_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background memory monitoring."""
        self.monitoring = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring:
            try:
                self._log_memory_usage()
                self._cleanup_memory()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _log_memory_usage(self) -> None:
        """Log current memory usage."""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Log warning if memory usage is high
            if memory_mb > 400:  # 400MB threshold
                logger.warning(f"High memory usage: {memory_mb:.1f}MB")
            else:
                logger.info(f"Memory usage: {memory_mb:.1f}MB")
                
        except Exception as e:
            logger.error(f"Error logging memory usage: {e}")
    
    def _cleanup_memory(self) -> None:
        """Perform memory cleanup operations."""
        try:
            # Force garbage collection
            collected = gc.collect()
            if collected > 0:
                logger.info(f"Garbage collected {collected} objects")
                
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage statistics.
        
        Returns:
            Dictionary with memory usage information
        """
        try:
            memory_info = self.process.memory_info()
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': self.process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}
    
    def force_cleanup(self) -> int:
        """
        Force immediate memory cleanup.
        
        Returns:
            Number of objects collected
        """
        return gc.collect()


# Global memory monitor instance
_memory_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get or create the global memory monitor instance."""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


def start_memory_monitoring() -> None:
    """Start global memory monitoring."""
    monitor = get_memory_monitor()
    monitor.start_monitoring()


def stop_memory_monitoring() -> None:
    """Stop global memory monitoring."""
    global _memory_monitor
    if _memory_monitor:
        _memory_monitor.stop_monitoring()


def log_memory_usage() -> None:
    """Log current memory usage."""
    monitor = get_memory_monitor()
    monitor._log_memory_usage()


def force_memory_cleanup() -> int:
    """Force immediate memory cleanup."""
    monitor = get_memory_monitor()
    return monitor.force_cleanup()
