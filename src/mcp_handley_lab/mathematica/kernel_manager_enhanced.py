"""
Enhanced Mathematica Kernel Manager

This module provides advanced kernel management capabilities for future enhancements.
Currently, the main tool.py uses a simpler approach, but this provides a foundation
for more sophisticated session management features.
"""

import logging
import threading
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from pathlib import Path

from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr

logger = logging.getLogger(__name__)


class EnhancedKernelManager:
    """
    Advanced Wolfram kernel session manager with enhanced features.
    
    Features:
    - Thread-safe session management
    - Automatic session recovery
    - Session health monitoring
    - Memory management and cleanup
    - State backup and restoration
    - Performance metrics
    """
    
    def __init__(
        self,
        kernel_path: str = '/usr/bin/WolframKernel',
        max_memory_mb: int = 1024,
        session_timeout: int = 3600,
        backup_interval: int = 300
    ):
        self.kernel_path = kernel_path
        self.max_memory_mb = max_memory_mb
        self.session_timeout = session_timeout
        self.backup_interval = backup_interval
        
        self._session: Optional[WolframLanguageSession] = None
        self._lock = threading.RLock()
        self._evaluation_count = 0
        self._session_start_time: Optional[float] = None
        self._last_backup_time: Optional[float] = None
        self._session_context: Dict[str, Any] = {}
        self._performance_metrics: Dict[str, Any] = {}
        
        logger.info(f"Enhanced kernel manager initialized: {kernel_path}")
    
    @property
    def is_active(self) -> bool:
        """Check if the kernel session is active."""
        with self._lock:
            return self._session is not None
    
    @property
    def evaluation_count(self) -> int:
        """Get the current evaluation count."""
        with self._lock:
            return self._evaluation_count
    
    @property
    def uptime_seconds(self) -> Optional[float]:
        """Get session uptime in seconds."""
        with self._lock:
            if self._session_start_time is None:
                return None
            return time.time() - self._session_start_time
    
    def start_session(self) -> bool:
        """Start a new Wolfram kernel session."""
        with self._lock:
            if self._session is not None:
                logger.warning("Session already active")
                return True
            
            try:
                logger.info("Starting enhanced Wolfram kernel session...")
                self._session = WolframLanguageSession(self.kernel_path)
                self._session_start_time = time.time()
                self._evaluation_count = 0
                
                # Initialize session with optimized settings
                self._initialize_session_settings()
                
                logger.info("✅ Enhanced Wolfram session started successfully")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to start enhanced Wolfram session: {e}")
                self._session = None
                self._session_start_time = None
                return False
    
    def stop_session(self) -> None:
        """Stop the current session and clean up resources."""
        with self._lock:
            if self._session is None:
                return
            
            try:
                # Backup session state before closing
                self._backup_session_state()
                
                # Terminate session
                self._session.terminate()
                logger.info("✅ Enhanced Wolfram session stopped")
                
            except Exception as e:
                logger.error(f"Error stopping enhanced session: {e}")
            finally:
                self._session = None
                self._session_start_time = None
                self._evaluation_count = 0
    
    def evaluate(
        self,
        expression: str,
        output_format: str = "Raw",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a Wolfram expression with enhanced error handling and monitoring.
        """
        with self._lock:
            if not self._ensure_session_healthy():
                raise RuntimeError("Could not establish healthy Wolfram session")
            
            start_time = time.time()
            
            try:
                logger.debug(f"Enhanced evaluation: {expression}")
                
                # Check memory usage before evaluation
                self._check_memory_usage()
                
                # Evaluate the expression
                raw_result = self._session.evaluate(wlexpr(expression))
                self._evaluation_count += 1
                
                # Format result based on requested format
                formatted_result = self._format_result(raw_result, output_format)
                
                # Update performance metrics
                evaluation_time = time.time() - start_time
                self._update_performance_metrics(evaluation_time)
                
                # Periodic backup
                self._maybe_backup_session()
                
                result = {
                    'result': raw_result,
                    'formatted': formatted_result,
                    'success': True,
                    'evaluation_count': self._evaluation_count,
                    'expression': expression,
                    'format_used': output_format,
                    'evaluation_time': evaluation_time
                }
                
                logger.debug(f"✅ Enhanced evaluation successful: {formatted_result}")
                return result
                
            except Exception as e:
                evaluation_time = time.time() - start_time
                logger.error(f"❌ Enhanced evaluation failed: {e}")
                
                return {
                    'result': None,
                    'formatted': f"Error: {str(e)}",
                    'success': False,
                    'evaluation_count': self._evaluation_count,
                    'expression': expression,
                    'format_used': output_format,
                    'error': str(e),
                    'evaluation_time': evaluation_time
                }
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information and metrics."""
        with self._lock:
            if not self._session:
                return {
                    'active': False,
                    'evaluation_count': self._evaluation_count,
                    'kernel_path': self.kernel_path
                }
            
            try:
                # Get Wolfram system information
                version = self._session.evaluate(wlexpr('$Version'))
                memory_used = self._session.evaluate(wlexpr('MemoryInUse[]'))
                process_id = self._session.evaluate(wlexpr('$ProcessID'))
                
                return {
                    'active': True,
                    'evaluation_count': self._evaluation_count,
                    'version': str(version),
                    'memory_used': str(memory_used),
                    'process_id': str(process_id),
                    'kernel_path': self.kernel_path,
                    'uptime_seconds': self.uptime_seconds,
                    'performance_metrics': self._performance_metrics.copy(),
                    'max_memory_mb': self.max_memory_mb,
                    'session_timeout': self.session_timeout
                }
                
            except Exception as e:
                return {
                    'active': False,
                    'error': str(e),
                    'evaluation_count': self._evaluation_count,
                    'kernel_path': self.kernel_path
                }
    
    def clear_session(self, keep_builtin: bool = True) -> bool:
        """Clear session variables with enhanced cleanup."""
        with self._lock:
            if not self._ensure_session_healthy():
                return False
            
            try:
                if keep_builtin:
                    # Clear only user-defined symbols
                    self._session.evaluate(wlexpr('ClearAll[Evaluate[Names["Global`*"]]]'))
                    logger.info("Enhanced clear: user-defined symbols")
                else:
                    # More comprehensive clearing
                    self._session.evaluate(wlexpr('ClearAll["Global`*"]'))
                    self._session.evaluate(wlexpr('$HistoryLength = 100'))
                    logger.info("Enhanced clear: all symbols and reset")
                
                # Reset internal state
                self._session_context.clear()
                
                return True
                
            except Exception as e:
                logger.error(f"Enhanced clear session failed: {e}")
                return False
    
    def _initialize_session_settings(self):
        """Initialize session with optimized settings."""
        try:
            # Set up history and output formatting
            self._session.evaluate(wlexpr('$HistoryLength = 100'))
            self._session.evaluate(wlexpr('SetOptions[$Output, PageWidth -> Infinity]'))
            
            # Memory management settings
            self._session.evaluate(wlexpr(f'$MemoryConstrained = {self.max_memory_mb * 1024 * 1024}'))
            
            # Performance monitoring
            self._session.evaluate(wlexpr('$TimeConstrained = 300'))  # 5 minute timeout
            
            logger.debug("Session settings initialized")
            
        except Exception as e:
            logger.warning(f"Could not initialize all session settings: {e}")
    
    def _ensure_session_healthy(self) -> bool:
        """Ensure session is healthy and restart if necessary."""
        if self._session is None:
            return self.start_session()
        
        try:
            # Test session responsiveness
            self._session.evaluate(wlexpr('1'))
            
            # Check session age
            if self.uptime_seconds and self.uptime_seconds > self.session_timeout:
                logger.info("Session timeout reached, restarting...")
                self.stop_session()
                return self.start_session()
            
            return True
            
        except Exception as e:
            logger.warning(f"Session health check failed, restarting: {e}")
            self.stop_session()
            return self.start_session()
    
    def _format_result(self, raw_result: Any, output_format: str) -> str:
        """Format result with enhanced error handling."""
        try:
            if output_format == "Raw":
                return str(raw_result)
            elif output_format == "InputForm":
                return str(self._session.evaluate(wlexpr(f'ToString[{raw_result}, InputForm]')))
            elif output_format == "OutputForm":
                return str(self._session.evaluate(wlexpr(f'ToString[{raw_result}, OutputForm]')))
            elif output_format == "TeXForm":
                return str(self._session.evaluate(wlexpr(f'ToString[TeXForm[{raw_result}]]')))
            else:
                return str(raw_result)
        except Exception as e:
            logger.warning(f"Formatting failed for {output_format}: {e}")
            return str(raw_result)
    
    def _check_memory_usage(self):
        """Monitor memory usage and take action if necessary."""
        try:
            memory_bytes = self._session.evaluate(wlexpr('MemoryInUse[]'))
            memory_mb = int(memory_bytes) / (1024 * 1024)
            
            if memory_mb > self.max_memory_mb * 0.8:  # 80% threshold
                logger.warning(f"High memory usage: {memory_mb:.1f}MB")
                
                if memory_mb > self.max_memory_mb:
                    logger.error("Memory limit exceeded, clearing session")
                    self.clear_session(keep_builtin=True)
                    
        except Exception as e:
            logger.debug(f"Could not check memory usage: {e}")
    
    def _update_performance_metrics(self, evaluation_time: float):
        """Update performance tracking metrics."""
        if 'total_evaluations' not in self._performance_metrics:
            self._performance_metrics = {
                'total_evaluations': 0,
                'total_time': 0.0,
                'average_time': 0.0,
                'max_time': 0.0,
                'min_time': float('inf')
            }
        
        metrics = self._performance_metrics
        metrics['total_evaluations'] += 1
        metrics['total_time'] += evaluation_time
        metrics['average_time'] = metrics['total_time'] / metrics['total_evaluations']
        metrics['max_time'] = max(metrics['max_time'], evaluation_time)
        metrics['min_time'] = min(metrics['min_time'], evaluation_time)
    
    def _backup_session_state(self):
        """Backup critical session state."""
        try:
            # This would implement state saving using DumpSave
            # For now, just log the attempt
            logger.debug("Session state backup requested")
        except Exception as e:
            logger.warning(f"Session backup failed: {e}")
    
    def _maybe_backup_session(self):
        """Perform periodic backup if needed."""
        current_time = time.time()
        if (self._last_backup_time is None or 
            current_time - self._last_backup_time > self.backup_interval):
            self._backup_session_state()
            self._last_backup_time = current_time
    
    @contextmanager
    def session_context(self):
        """Context manager for safe session access."""
        with self._lock:
            if not self._ensure_session_healthy():
                raise RuntimeError("Could not establish healthy Wolfram session")
            yield self._session


# Example usage and testing
if __name__ == "__main__":
    # This allows for standalone testing of the enhanced kernel manager
    logging.basicConfig(level=logging.INFO)
    
    manager = EnhancedKernelManager()
    
    # Test session startup
    if manager.start_session():
        print("✅ Enhanced kernel manager test successful")
        
        # Test evaluation
        result = manager.evaluate("2 + 2")
        print(f"2 + 2 = {result['formatted']}")
        
        # Test session info
        info = manager.get_session_info()
        print(f"Session info: {info}")
        
        manager.stop_session()
    else:
        print("❌ Enhanced kernel manager test failed")