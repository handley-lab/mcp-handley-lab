"""
Mathematica Kernel Manager for persistent REPL sessions.

This module manages a long-running Wolfram kernel session that persists
across multiple MCP tool calls, enabling true REPL behavior where LLMs
can build on previous calculations and use history references.
"""

import logging
import threading
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from pathlib import Path

from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr


logger = logging.getLogger(__name__)


class MathematicaKernelManager:
    """
    Manages a persistent Wolfram kernel session for MCP tools.
    
    Features:
    - Single long-running WolframLanguageSession
    - Thread-safe access with locking
    - Automatic session recovery on failure
    - Configurable output formatting
    - Session history and context tracking
    - File-based state backup for resilience
    """
    
    def __init__(
        self,
        kernel_path: str = '/usr/bin/WolframKernel',
        default_format: str = 'OutputForm',
        state_backup_path: Optional[str] = None
    ):
        self.kernel_path = kernel_path
        self.default_format = default_format
        self.state_backup_path = state_backup_path or "/tmp/mathematica_mcp_state.mx"
        
        self._session: Optional[WolframLanguageSession] = None
        self._lock = threading.RLock()
        self._evaluation_count = 0
        self._session_context: Dict[str, Any] = {}
        
        logger.info(f"Initialized MathematicaKernelManager with kernel: {kernel_path}")
    
    def start_session(self) -> bool:
        """Start the Wolfram kernel session."""
        with self._lock:
            if self._session is not None:
                logger.warning("Session already started")
                return True
            
            try:
                logger.info("Starting Wolfram kernel session...")
                self._session = WolframLanguageSession(self.kernel_path)
                
                # Initialize session with useful settings
                self._session.evaluate(wlexpr('$HistoryLength = 100'))  # Keep evaluation history
                self._session.evaluate(wlexpr('SetOptions[$Output, PageWidth -> Infinity]'))  # No line wrapping
                
                # Load any existing state backup
                self._load_state_backup()
                
                self._evaluation_count = 0
                logger.info("✅ Wolfram kernel session started successfully")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to start Wolfram session: {e}")
                self._session = None
                return False
    
    def stop_session(self) -> None:
        """Stop the Wolfram kernel session."""
        with self._lock:
            if self._session is None:
                return
            
            try:
                # Save state before closing
                self._save_state_backup()
                
                self._session.terminate()
                logger.info("✅ Wolfram kernel session stopped")
            except Exception as e:
                logger.error(f"Error stopping session: {e}")
            finally:
                self._session = None
                self._evaluation_count = 0
    
    def is_active(self) -> bool:
        """Check if the kernel session is active."""
        with self._lock:
            return self._session is not None
    
    def evaluate(
        self, 
        expression: str, 
        output_format: Optional[str] = None,
        store_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a Wolfram expression in the persistent session.
        
        Args:
            expression: Wolfram Language expression to evaluate
            output_format: Format for output ('OutputForm', 'InputForm', 'TeXForm', etc.)
            store_context: Optional key to store result in session context
        
        Returns:
            Dict with 'result', 'formatted', 'evaluation_count', and metadata
        """
        with self._lock:
            if not self._ensure_session():
                raise RuntimeError("Could not establish Wolfram session")
            
            try:
                logger.debug(f"Evaluating: {expression}")
                
                # Evaluate the expression
                raw_result = self._session.evaluate(wlexpr(expression))
                self._evaluation_count += 1
                
                # Format the result directly without using history references
                format_to_use = output_format or self.default_format
                if format_to_use and format_to_use != 'Raw':
                    try:
                        # Format the raw result directly using ToString
                        formatted_result = str(raw_result)
                        # If it's a simple value, ToString in Python is often sufficient
                        # For complex expressions, we could implement more sophisticated formatting
                    except Exception as e:
                        logger.warning(f"Formatting failed with {format_to_use}: {e}")
                        formatted_result = str(raw_result)
                else:
                    formatted_result = str(raw_result)
                
                # Store in context if requested
                if store_context:
                    self._session_context[store_context] = raw_result
                
                result = {
                    'result': raw_result,
                    'formatted': formatted_result,
                    'evaluation_count': self._evaluation_count,
                    'expression': expression,
                    'format_used': format_to_use,
                    'success': True
                }
                
                logger.debug(f"✅ Evaluation successful: {formatted_result}")
                return result
                
            except Exception as e:
                logger.error(f"❌ Evaluation failed: {e}")
                return {
                    'result': None,
                    'formatted': f"Error: {str(e)}",
                    'evaluation_count': self._evaluation_count,
                    'expression': expression,
                    'format_used': output_format,
                    'success': False,
                    'error': str(e)
                }
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session."""
        with self._lock:
            if not self._session:
                return {'active': False}
            
            try:
                # Get session details
                version = self._session.evaluate(wlexpr('ToString[$Version]'))
                memory_used = self._session.evaluate(wlexpr('ToString[MemoryInUse[]]'))
                kernel_id = self._session.evaluate(wlexpr('ToString[$KernelID]'))
                
                return {
                    'active': True,
                    'evaluation_count': self._evaluation_count,
                    'version': str(version),
                    'memory_used': str(memory_used),
                    'kernel_id': str(kernel_id),
                    'context_keys': list(self._session_context.keys()),
                    'kernel_path': self.kernel_path,
                    'default_format': self.default_format
                }
            except Exception as e:
                return {
                    'active': True,
                    'error': str(e),
                    'evaluation_count': self._evaluation_count
                }
    
    def clear_session(self, keep_builtin: bool = True) -> bool:
        """
        Clear session variables and history.
        
        Args:
            keep_builtin: If True, preserve built-in Wolfram functions
        
        Returns:
            True if successful
        """
        with self._lock:
            if not self._ensure_session():
                return False
            
            try:
                if keep_builtin:
                    # Clear only user-defined symbols
                    self._session.evaluate(wlexpr('ClearAll[Evaluate[Names["Global`*"]]]'))
                    logger.info("Cleared user-defined symbols")
                else:
                    # Nuclear option - clear everything
                    self._session.evaluate(wlexpr('ClearAll["Global`*"]'))
                    self._session.evaluate(wlexpr('$HistoryLength = 100'))
                    logger.info("Cleared all symbols and reset session")
                
                self._session_context.clear()
                return True
                
            except Exception as e:
                logger.error(f"Failed to clear session: {e}")
                return False
    
    def _ensure_session(self) -> bool:
        """Ensure session is active, restart if necessary."""
        if self._session is None:
            return self.start_session()
        
        try:
            # Test if session is responsive
            self._session.evaluate(wlexpr('1 + 1'))
            return True
        except Exception as e:
            logger.warning(f"Session unresponsive, restarting: {e}")
            self.stop_session()
            return self.start_session()
    
    def _save_state_backup(self) -> None:
        """Save critical session state to file."""
        if not self._session:
            return
        
        try:
            # Save user-defined symbols to backup file
            self._session.evaluate(wlexpr(f'DumpSave["{self.state_backup_path}", Names["Global`*"]]'))
            logger.debug(f"State backed up to {self.state_backup_path}")
        except Exception as e:
            logger.warning(f"Failed to save state backup: {e}")
    
    def _load_state_backup(self) -> None:
        """Load session state from backup file."""
        backup_path = Path(self.state_backup_path)
        if not backup_path.exists():
            return
        
        try:
            self._session.evaluate(wlexpr(f'Get["{self.state_backup_path}"]'))
            logger.info("✅ Loaded state from backup")
        except Exception as e:
            logger.warning(f"Failed to load state backup: {e}")
    
    @contextmanager
    def session_context(self):
        """Context manager for safe session access."""
        with self._lock:
            if not self._ensure_session():
                raise RuntimeError("Could not establish Wolfram session")
            yield self._session


# Global kernel manager instance
_kernel_manager: Optional[MathematicaKernelManager] = None


def get_kernel_manager() -> MathematicaKernelManager:
    """Get the global kernel manager instance."""
    global _kernel_manager
    if _kernel_manager is None:
        _kernel_manager = MathematicaKernelManager()
    return _kernel_manager


def initialize_kernel(kernel_path: str = '/usr/bin/WolframKernel') -> bool:
    """Initialize the global kernel manager."""
    global _kernel_manager
    _kernel_manager = MathematicaKernelManager(kernel_path=kernel_path)
    return _kernel_manager.start_session()


def shutdown_kernel() -> None:
    """Shutdown the global kernel manager."""
    global _kernel_manager
    if _kernel_manager:
        _kernel_manager.stop_session()
        _kernel_manager = None