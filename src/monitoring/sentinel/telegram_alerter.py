#!/usr/bin/env python3
"""
Telegram Alerter for Veris Sentinel

This module provides Telegram bot integration for sending alerts from the
Veris Memory Sentinel monitoring system.

Author: Workspace 002
Date: 2025-08-19
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import aiohttp
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"


@dataclass
class TelegramMessage:
    """Structured Telegram message."""
    text: str
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True
    disable_notification: bool = False


class TelegramAlerter:
    """
    Telegram bot alerter for Sentinel monitoring.
    
    Handles sending alerts to Telegram with rate limiting,
    formatting, and error handling.
    """
    
    # Emoji mappings for severity levels
    SEVERITY_EMOJIS = {
        AlertSeverity.CRITICAL: "🚨",
        AlertSeverity.HIGH: "⚠️",
        AlertSeverity.WARNING: "⚡",
        AlertSeverity.INFO: "ℹ️"
    }
    
    # Status emojis
    STATUS_EMOJIS = {
        "pass": "✅",
        "fail": "❌",
        "error": "🔥",
        "timeout": "⏱️",
        "unknown": "❓"
    }
    
    def __init__(self, bot_token: str, chat_id: str, rate_limit: int = 30):
        """
        Initialize Telegram alerter.
        
        Args:
            bot_token: Telegram bot API token
            chat_id: Target chat/channel ID
            rate_limit: Max messages per minute (default: 30)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.rate_limit = rate_limit
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Rate limiting
        self.message_times: List[datetime] = []
        self.rate_limit_lock = asyncio.Lock()
        
        # Message queue for batching
        self.message_queue: List[TelegramMessage] = []
        self.queue_lock = asyncio.Lock()
        
        logger.info(f"Telegram alerter initialized for chat {chat_id}")
    
    async def send_alert(
        self,
        check_id: str,
        status: str,
        message: str,
        severity: AlertSeverity,
        details: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None
    ) -> bool:
        """
        Send an alert to Telegram.
        
        Args:
            check_id: Check identifier (e.g., "S1-health-probes")
            status: Check status (pass/fail/error/timeout)
            message: Alert message
            severity: Alert severity level
            details: Additional details dictionary
            latency_ms: Check latency in milliseconds
        
        Returns:
            True if message sent successfully
        """
        formatted_message = self._format_alert(
            check_id, status, message, severity, details, latency_ms
        )
        
        # Disable notifications for info level
        disable_notification = severity == AlertSeverity.INFO
        
        telegram_msg = TelegramMessage(
            text=formatted_message,
            disable_notification=disable_notification
        )
        
        return await self._send_message(telegram_msg)
    
    async def send_summary(
        self,
        period_hours: int,
        total_checks: int,
        passed_checks: int,
        failed_checks: int,
        top_failures: List[Dict[str, Any]],
        avg_latency_ms: float,
        uptime_percent: float
    ) -> bool:
        """
        Send a periodic summary to Telegram.
        
        Args:
            period_hours: Summary period in hours
            total_checks: Total checks executed
            passed_checks: Number of passed checks
            failed_checks: Number of failed checks
            top_failures: List of top failure details
            avg_latency_ms: Average check latency
            uptime_percent: System uptime percentage
        
        Returns:
            True if message sent successfully
        """
        formatted_message = self._format_summary(
            period_hours, total_checks, passed_checks, failed_checks,
            top_failures, avg_latency_ms, uptime_percent
        )
        
        telegram_msg = TelegramMessage(
            text=formatted_message,
            disable_notification=True  # Summaries are non-urgent
        )
        
        return await self._send_message(telegram_msg)
    
    def _format_alert(
        self,
        check_id: str,
        status: str,
        message: str,
        severity: AlertSeverity,
        details: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None
    ) -> str:
        """Format an alert message for Telegram."""
        severity_emoji = self.SEVERITY_EMOJIS.get(severity, "")
        status_emoji = self.STATUS_EMOJIS.get(status, "❓")
        
        # Build header
        header = f"<b>{severity_emoji} {severity.value.upper()}: Veris Memory Alert</b>"
        
        # Build body
        lines = [
            header,
            "━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Check:</b> {check_id}",
            f"<b>Status:</b> {status.upper()} {status_emoji}",
            f"<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        ]
        
        if latency_ms:
            lines.append(f"<b>Latency:</b> {latency_ms:.1f}ms")
        
        lines.append("")
        lines.append(f"<b>Message:</b>\n{self._escape_html(message)}")
        
        # Add details if provided
        if details:
            lines.append("")
            lines.append("<b>Details:</b>")
            for key, value in details.items():
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, indent=2)
                lines.append(f"• {self._escape_html(str(key))}: {self._escape_html(str(value))}")
        
        # Add action required for critical/high severity
        if severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            lines.append("")
            lines.append("<b>Action Required:</b> Immediate investigation")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        
        return "\n".join(lines)
    
    def _format_summary(
        self,
        period_hours: int,
        total_checks: int,
        passed_checks: int,
        failed_checks: int,
        top_failures: List[Dict[str, Any]],
        avg_latency_ms: float,
        uptime_percent: float
    ) -> str:
        """Format a summary message for Telegram."""
        period_text = f"{period_hours} hours" if period_hours != 24 else "24 hours"
        pass_percent = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        lines = [
            "<b>📊 Veris Sentinel Report</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Period:</b> Last {period_text}",
            f"<b>Total Checks:</b> {total_checks:,}",
            f"✅ <b>Passed:</b> {passed_checks:,} ({pass_percent:.1f}%)",
            f"❌ <b>Failed:</b> {failed_checks:,} ({100-pass_percent:.1f}%)"
        ]
        
        if top_failures:
            lines.append("")
            lines.append("<b>Top Issues:</b>")
            for i, failure in enumerate(top_failures[:5], 1):
                check_id = failure.get('check_id', 'Unknown')
                count = failure.get('count', 0)
                lines.append(f"{i}. {check_id}: {count} failures")
        
        lines.extend([
            "",
            f"<b>Avg Response Time:</b> {avg_latency_ms:.1f}ms",
            f"<b>Uptime:</b> {uptime_percent:.1f}%",
            "━━━━━━━━━━━━━━━━━━━━━"
        ])
        
        return "\n".join(lines)
    
    async def _send_message(self, message: TelegramMessage) -> bool:
        """
        Send a message to Telegram with rate limiting.
        
        Args:
            message: TelegramMessage object
        
        Returns:
            True if sent successfully
        """
        # Check rate limit
        if not await self._check_rate_limit():
            logger.warning("Rate limit exceeded, queuing message")
            async with self.queue_lock:
                self.message_queue.append(message)
            return False
        
        # Send via Telegram API
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": message.text,
                    "parse_mode": message.parse_mode,
                    "disable_web_page_preview": message.disable_web_page_preview,
                    "disable_notification": message.disable_notification
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            logger.info("Telegram message sent successfully")
                            return True
                        else:
                            logger.error(f"Telegram API error: {result.get('description')}")
                            return False
                    else:
                        logger.error(f"Telegram HTTP error: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limit."""
        async with self.rate_limit_lock:
            now = datetime.utcnow()
            cutoff = now - timedelta(minutes=1)
            
            # Remove old timestamps
            self.message_times = [t for t in self.message_times if t > cutoff]
            
            # Check if we can send
            if len(self.message_times) < self.rate_limit:
                self.message_times.append(now)
                return True
            
            return False
    
    async def process_queue(self) -> int:
        """
        Process queued messages.
        
        Returns:
            Number of messages sent from queue
        """
        sent_count = 0
        
        async with self.queue_lock:
            while self.message_queue and await self._check_rate_limit():
                message = self.message_queue.pop(0)
                if await self._send_message(message):
                    sent_count += 1
                await asyncio.sleep(0.1)  # Small delay between messages
        
        if sent_count > 0:
            logger.info(f"Processed {sent_count} queued messages")
        
        return sent_count
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
    
    async def test_connection(self) -> bool:
        """
        Test Telegram bot connection.
        
        Returns:
            True if bot is accessible and configured correctly
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/getMe"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            bot_info = result.get("result", {})
                            logger.info(f"Connected to Telegram bot: @{bot_info.get('username')}")
                            return True
                        else:
                            logger.error(f"Telegram bot error: {result.get('description')}")
                            return False
                    else:
                        logger.error(f"Telegram connection failed: HTTP {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to test Telegram connection: {e}")
            return False