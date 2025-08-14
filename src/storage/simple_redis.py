#!/usr/bin/env python3
"""
simple_redis.py: Direct Redis client for scratchpad operations

This module provides a simple, direct Redis interface that bypasses
the complex ContextKV inheritance chain to ensure reliable scratchpad operations.
"""

import os
from typing import Optional
import redis
import logging

logger = logging.getLogger(__name__)


class SimpleRedisClient:
    """Simple, direct Redis client for reliable scratchpad operations."""
    
    def __init__(self):
        """Initialize Redis client with environment configuration."""
        self.client: Optional[redis.Redis] = None
        self.is_connected = False
        
    def connect(self, redis_password: Optional[str] = None) -> bool:
        """
        Connect to Redis with minimal complexity.
        
        Args:
            redis_password: Optional Redis password
            
        Returns:
            bool: True if connected successfully
        """
        try:
            # Get Redis configuration from environment
            host = os.getenv("REDIS_HOST", "redis")
            port = int(os.getenv("REDIS_PORT", "6379"))
            db = int(os.getenv("REDIS_DB", "0"))
            
            # Create connection parameters
            connection_params = {
                "host": host,
                "port": port,
                "db": db,
                "decode_responses": True,  # Return strings instead of bytes
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "connection_pool_kwargs": {
                    "max_connections": 10,
                    "retry_on_timeout": True
                }
            }
            
            # Add password if provided
            if redis_password:
                connection_params["password"] = redis_password
            
            # Create Redis client
            self.client = redis.Redis(**connection_params)
            
            # Test connection
            self.client.ping()
            self.is_connected = True
            
            logger.info(f"✅ SimpleRedisClient connected to {host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ SimpleRedisClient connection failed: {e}")
            self.client = None
            self.is_connected = False
            return False
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Set a key-value pair in Redis with optional TTL.
        
        Args:
            key: Redis key
            value: Value to store
            ex: TTL in seconds (optional)
            
        Returns:
            bool: True if successful
        """
        try:
            if not self.is_connected or not self.client:
                logger.warning("Redis not connected, attempting reconnection...")
                if not self.connect():
                    return False
            
            # Perform Redis SET operation
            if ex:
                result = self.client.set(key, value, ex=ex)
            else:
                result = self.client.set(key, value)
            
            return bool(result)
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in set(): {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in set(): {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis by key.
        
        Args:
            key: Redis key
            
        Returns:
            str: Retrieved value or None
        """
        try:
            if not self.is_connected or not self.client:
                logger.warning("Redis not connected, attempting reconnection...")
                if not self.connect():
                    return None
            
            # Perform Redis GET operation
            result = self.client.get(key)
            return result  # Already decoded to string due to decode_responses=True
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in get(): {e}")
            self.is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get(): {e}")
            return None
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.
        
        Args:
            key: Redis key
            
        Returns:
            bool: True if key exists
        """
        try:
            if not self.is_connected or not self.client:
                logger.warning("Redis not connected, attempting reconnection...")
                if not self.connect():
                    return False
            
            # Perform Redis EXISTS operation
            result = self.client.exists(key)
            return bool(result)
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in exists(): {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in exists(): {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.
        
        Args:
            key: Redis key
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            if not self.is_connected or not self.client:
                logger.warning("Redis not connected, attempting reconnection...")
                if not self.connect():
                    return False
            
            # Perform Redis DELETE operation
            result = self.client.delete(key)
            return bool(result)
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in delete(): {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in delete(): {e}")
            return False
    
    def keys(self, pattern: str = "*") -> list:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (default: "*")
            
        Returns:
            list: List of matching keys
        """
        try:
            if not self.is_connected or not self.client:
                logger.warning("Redis not connected, attempting reconnection...")
                if not self.connect():
                    return []
            
            # Perform Redis KEYS operation
            result = self.client.keys(pattern)
            return result  # Already decoded to strings
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error in keys(): {e}")
            self.is_connected = False
            return []
        except Exception as e:
            logger.error(f"Unexpected error in keys(): {e}")
            return []
    
    def close(self):
        """Close Redis connection."""
        if self.client:
            try:
                self.client.close()
                logger.info("SimpleRedisClient connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.client = None
                self.is_connected = False