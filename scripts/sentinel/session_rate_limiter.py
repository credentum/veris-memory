#!/usr/bin/env python3
"""
Session Rate Limiter for Phase 3 Emergency Sessions

Prevents runaway automation by implementing comprehensive rate limiting,
session tracking, and emergency brake mechanisms for Claude Code sessions.

Author: Claude Code Integration - Phase 3 Security  
Date: 2025-08-21
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import fcntl
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SessionRateLimiter:
    """
    Rate limiter for Claude Code emergency sessions with comprehensive controls.
    
    Features:
    - Sessions per hour/day limits
    - Concurrent session limits
    - Emergency brake mechanism
    - Session tracking and history
    - Automatic cleanup of old sessions
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize session rate limiter."""
        self.config = config
        
        # Use persistent storage directory with fallback to /tmp
        persistent_dir = config.get('persistent_dir', '/var/lib/veris-memory')
        if not os.path.exists(persistent_dir):
            try:
                os.makedirs(persistent_dir, mode=0o755, exist_ok=True)
                logger.info(f"Created persistent directory: {persistent_dir}")
            except (OSError, PermissionError):
                logger.warning(f"Cannot create persistent directory {persistent_dir}, falling back to /tmp")
                persistent_dir = '/tmp'
        
        self.state_file = config.get('state_file', os.path.join(persistent_dir, 'claude_sessions_state.json'))
        self.lock_file = config.get('lock_file', os.path.join(persistent_dir, 'claude_sessions.lock'))
        
        # Rate limiting configuration
        self.max_sessions_per_hour = config.get('max_sessions_per_hour', 5)
        self.max_sessions_per_day = config.get('max_sessions_per_day', 20)
        self.max_concurrent_sessions = config.get('max_concurrent_sessions', 2)
        self.max_session_duration_minutes = config.get('max_session_duration', 30)
        
        # Emergency brake settings
        self.emergency_brake_enabled = config.get('emergency_brake_enabled', True)
        self.failure_threshold = config.get('failure_threshold', 3)
        self.failure_window_minutes = config.get('failure_window_minutes', 15)
        
        # Thread lock for concurrent access
        self._lock = threading.Lock()
        
        logger.info("Session Rate Limiter initialized")

    def _load_session_state(self) -> Dict[str, Any]:
        """Load session state from persistent storage."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Clean up old sessions
                    state = self._cleanup_old_sessions(state)
                    return state
            else:
                return {
                    'sessions': [],
                    'active_sessions': {},
                    'failure_count': 0,
                    'last_failure': None,
                    'emergency_brake_active': False
                }
        except Exception as e:
            logger.error(f"Error loading session state: {e}")
            return {
                'sessions': [],
                'active_sessions': {},
                'failure_count': 0,
                'last_failure': None,
                'emergency_brake_active': False
            }

    def _save_session_state(self, state: Dict[str, Any]):
        """Save session state to persistent storage."""
        try:
            # Use file locking to prevent race conditions
            with open(self.lock_file, 'w') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
                
        except Exception as e:
            logger.error(f"Error saving session state: {e}")

    def _cleanup_old_sessions(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old session records."""
        current_time = datetime.now()
        
        # Remove sessions older than 24 hours
        cutoff_time = current_time - timedelta(hours=24)
        
        cleaned_sessions = []
        for session in state.get('sessions', []):
            session_time = datetime.fromisoformat(session['start_time'])
            if session_time > cutoff_time:
                cleaned_sessions.append(session)
        
        state['sessions'] = cleaned_sessions
        
        # Clean up stale active sessions
        cleaned_active = {}
        for session_id, session_info in state.get('active_sessions', {}).items():
            session_time = datetime.fromisoformat(session_info['start_time'])
            max_duration = timedelta(minutes=self.max_session_duration_minutes)
            
            if current_time - session_time < max_duration:
                cleaned_active[session_id] = session_info
            else:
                logger.warning(f"Cleaning up stale session: {session_id}")
        
        state['active_sessions'] = cleaned_active
        
        return state

    def _check_hourly_limit(self, state: Dict[str, Any], custom_limit: Optional[int] = None) -> bool:
        """Check if hourly session limit is exceeded."""
        current_time = datetime.now()
        hour_ago = current_time - timedelta(hours=1)
        
        recent_sessions = [
            s for s in state['sessions']
            if datetime.fromisoformat(s['start_time']) > hour_ago
        ]
        
        limit = custom_limit if custom_limit is not None else self.max_sessions_per_hour
        return len(recent_sessions) < limit

    def _check_daily_limit(self, state: Dict[str, Any], custom_limit: Optional[int] = None) -> bool:
        """Check if daily session limit is exceeded."""
        current_time = datetime.now()
        day_ago = current_time - timedelta(days=1)
        
        recent_sessions = [
            s for s in state['sessions']
            if datetime.fromisoformat(s['start_time']) > day_ago
        ]
        
        limit = custom_limit if custom_limit is not None else self.max_sessions_per_day
        return len(recent_sessions) < limit

    def _check_concurrent_limit(self, state: Dict[str, Any]) -> bool:
        """Check if concurrent session limit is exceeded."""
        return len(state['active_sessions']) < self.max_concurrent_sessions

    def _check_emergency_brake(self, state: Dict[str, Any]) -> bool:
        """Check if emergency brake should be activated."""
        if not self.emergency_brake_enabled:
            return False
        
        # Check for recent failures
        current_time = datetime.now()
        failure_window = timedelta(minutes=self.failure_window_minutes)
        
        if state.get('last_failure'):
            last_failure_time = datetime.fromisoformat(state['last_failure'])
            if current_time - last_failure_time < failure_window:
                if state.get('failure_count', 0) >= self.failure_threshold:
                    logger.warning("Emergency brake activated due to recent failures")
                    state['emergency_brake_active'] = True
                    return True
        
        return state.get('emergency_brake_active', False)

    def can_start_session(self, alert_context: Dict[str, Any], emergency_mode: bool = False) -> Dict[str, bool]:
        """
        Check if a new session can be started based on rate limits.
        
        Args:
            alert_context: Alert context for the session
            emergency_mode: Whether this is an emergency session (relaxes some limits)
            
        Returns:
            Dict with validation results and reasons
        """
        with self._lock:
            state = self._load_session_state()
            
            # Basic checks that apply even in emergency mode
            checks = {
                'concurrent_limit_ok': self._check_concurrent_limit(state),
                'emergency_brake_ok': not self._check_emergency_brake(state),
                'can_start': False
            }
            
            # In emergency mode, we relax but don't eliminate rate limits
            if emergency_mode:
                # Emergency mode gets higher limits but still has limits
                emergency_hourly_limit = min(self.max_sessions_per_hour * 2, 10)  # Max 10/hour even in emergency
                emergency_daily_limit = min(self.max_sessions_per_day * 2, 40)    # Max 40/day even in emergency
                
                checks['hourly_limit_ok'] = self._check_hourly_limit(state, emergency_hourly_limit)
                checks['daily_limit_ok'] = self._check_daily_limit(state, emergency_daily_limit)
                checks['emergency_mode'] = True
                
                # Emergency mode still requires basic safety checks
                checks['can_start'] = all([
                    checks['concurrent_limit_ok'],      # Always respect concurrent limits
                    checks['emergency_brake_ok'],       # Always respect emergency brake
                    checks['hourly_limit_ok'],          # Relaxed but still limited
                    checks['daily_limit_ok']            # Relaxed but still limited
                ])
            else:
                # Normal mode uses standard limits
                checks['hourly_limit_ok'] = self._check_hourly_limit(state)
                checks['daily_limit_ok'] = self._check_daily_limit(state)
                checks['emergency_mode'] = False
                
                checks['can_start'] = all([
                    checks['hourly_limit_ok'],
                    checks['daily_limit_ok'],
                    checks['concurrent_limit_ok'],
                    checks['emergency_brake_ok']
                ])
            
            # Log rate limit status
            if not checks['can_start']:
                reasons = []
                if not checks['hourly_limit_ok']:
                    limit = emergency_hourly_limit if emergency_mode else self.max_sessions_per_hour
                    reasons.append(f"hourly limit ({limit}/hour)")
                if not checks['daily_limit_ok']:
                    limit = emergency_daily_limit if emergency_mode else self.max_sessions_per_day
                    reasons.append(f"daily limit ({limit}/day)")
                if not checks['concurrent_limit_ok']:
                    reasons.append(f"concurrent limit ({self.max_concurrent_sessions})")
                if not checks['emergency_brake_ok']:
                    reasons.append("emergency brake active")
                
                mode_str = "emergency mode" if emergency_mode else "normal mode"
                logger.warning(f"Session start blocked ({mode_str}): {', '.join(reasons)}")
            
            return checks

    def start_session(self, session_id: str, alert_context: Dict[str, Any]) -> bool:
        """
        Start a new session and update tracking.
        
        Args:
            session_id: Unique session identifier
            alert_context: Alert context for the session
            
        Returns:
            True if session was started successfully
        """
        with self._lock:
            # Check if session can be started
            can_start_result = self.can_start_session(alert_context)
            if not can_start_result['can_start']:
                return False
            
            state = self._load_session_state()
            
            # Record new session
            session_record = {
                'session_id': session_id,
                'start_time': datetime.now().isoformat(),
                'alert_context': alert_context,
                'status': 'active'
            }
            
            state['sessions'].append(session_record)
            state['active_sessions'][session_id] = session_record
            
            # Reset emergency brake if it was active and we're allowing the session
            if state.get('emergency_brake_active'):
                logger.info("Emergency brake deactivated - allowing session")
                state['emergency_brake_active'] = False
            
            self._save_session_state(state)
            
            logger.info(f"Session started: {session_id}")
            return True

    def end_session(self, session_id: str, success: bool = True, error: Optional[str] = None):
        """
        End a session and update tracking.
        
        Args:
            session_id: Session identifier
            success: Whether session completed successfully
            error: Error message if session failed
        """
        with self._lock:
            state = self._load_session_state()
            
            # Update session record
            if session_id in state['active_sessions']:
                session_record = state['active_sessions'][session_id]
                session_record['end_time'] = datetime.now().isoformat()
                session_record['status'] = 'completed' if success else 'failed'
                session_record['success'] = success
                
                if error:
                    session_record['error'] = error
                
                # Update session in history
                for i, session in enumerate(state['sessions']):
                    if session['session_id'] == session_id:
                        state['sessions'][i] = session_record
                        break
                
                # Remove from active sessions
                del state['active_sessions'][session_id]
                
                # Handle failures for emergency brake
                if not success:
                    state['failure_count'] = state.get('failure_count', 0) + 1
                    state['last_failure'] = datetime.now().isoformat()
                    
                    if state['failure_count'] >= self.failure_threshold:
                        logger.warning(f"Failure threshold reached: {state['failure_count']}")
                        state['emergency_brake_active'] = True
                else:
                    # Reset failure count on success
                    state['failure_count'] = 0
                
                self._save_session_state(state)
                
                status = "completed successfully" if success else f"failed: {error}"
                logger.info(f"Session ended: {session_id} - {status}")
            
            else:
                logger.warning(f"Attempted to end unknown session: {session_id}")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get comprehensive session statistics."""
        with self._lock:
            state = self._load_session_state()
            
            current_time = datetime.now()
            hour_ago = current_time - timedelta(hours=1)
            day_ago = current_time - timedelta(days=1)
            
            sessions_last_hour = [
                s for s in state['sessions']
                if datetime.fromisoformat(s['start_time']) > hour_ago
            ]
            
            sessions_last_day = [
                s for s in state['sessions']
                if datetime.fromisoformat(s['start_time']) > day_ago
            ]
            
            successful_sessions = [s for s in state['sessions'] if s.get('success', True)]
            failed_sessions = [s for s in state['sessions'] if not s.get('success', True)]
            
            return {
                'current_time': current_time.isoformat(),
                'active_sessions': len(state['active_sessions']),
                'sessions_last_hour': len(sessions_last_hour),
                'sessions_last_day': len(sessions_last_day),
                'total_sessions': len(state['sessions']),
                'successful_sessions': len(successful_sessions),
                'failed_sessions': len(failed_sessions),
                'failure_count': state.get('failure_count', 0),
                'emergency_brake_active': state.get('emergency_brake_active', False),
                'rate_limits': {
                    'max_sessions_per_hour': self.max_sessions_per_hour,
                    'max_sessions_per_day': self.max_sessions_per_day,
                    'max_concurrent_sessions': self.max_concurrent_sessions
                }
            }

    def reset_emergency_brake(self):
        """Reset the emergency brake (admin function)."""
        with self._lock:
            state = self._load_session_state()
            state['emergency_brake_active'] = False
            state['failure_count'] = 0
            state['last_failure'] = None
            self._save_session_state(state)
            
            logger.info("Emergency brake reset by administrator")


# Example usage and testing
if __name__ == '__main__':
    # Example configuration
    config = {
        'max_sessions_per_hour': 3,
        'max_sessions_per_day': 10,
        'max_concurrent_sessions': 1,
        'emergency_brake_enabled': True,
        'failure_threshold': 2
    }
    
    # Initialize rate limiter
    rate_limiter = SessionRateLimiter(config)
    
    # Test alert context
    test_alert = {
        'alert_id': 'test-123',
        'severity': 'critical',
        'check_id': 'S1-health'
    }
    
    print("Testing Session Rate Limiter")
    print("=" * 40)
    
    # Test session limits
    for i in range(5):
        session_id = f"test-session-{i+1}"
        
        can_start = rate_limiter.can_start_session(test_alert)
        print(f"\nSession {i+1}:")
        print(f"  Can start: {can_start['can_start']}")
        
        if can_start['can_start']:
            success = rate_limiter.start_session(session_id, test_alert)
            print(f"  Started: {success}")
            
            # Simulate session end
            import random
            session_success = random.choice([True, False])
            error = "Simulated error" if not session_success else None
            rate_limiter.end_session(session_id, session_success, error)
            print(f"  Ended: {'Success' if session_success else 'Failed'}")
        
        time.sleep(0.1)  # Small delay
    
    # Show final stats
    stats = rate_limiter.get_session_stats()
    print(f"\nFinal Statistics:")
    for key, value in stats.items():
        if key != 'rate_limits':
            print(f"  {key}: {value}")