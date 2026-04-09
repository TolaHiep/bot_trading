"""NTP Time Synchronization Module

This module handles NTP time synchronization to ensure accurate timestamps
for trading operations.
"""

import asyncio
import logging
import ntplib
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class NTPSync:
    """NTP time synchronization manager"""
    
    def __init__(self, ntp_server: str = "pool.ntp.org", sync_interval: int = 3600):
        """Initialize NTP sync manager
        
        Args:
            ntp_server: NTP server address
            sync_interval: Sync interval in seconds (default: 1 hour)
        """
        self.ntp_server = ntp_server
        self.sync_interval = sync_interval
        self.ntp_client = ntplib.NTPClient()
        self.time_offset: Optional[float] = None
        self.last_sync: Optional[datetime] = None
        self._sync_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start periodic NTP synchronization"""
        logger.info(f"Starting NTP sync with server: {self.ntp_server}")
        await self.sync_time()
        self._sync_task = asyncio.create_task(self._periodic_sync())
        
    async def stop(self) -> None:
        """Stop NTP synchronization"""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("NTP sync stopped")
        
    async def _periodic_sync(self) -> None:
        """Periodically sync time with NTP server"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self.sync_time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic NTP sync: {e}")
                
    async def sync_time(self) -> None:
        """Synchronize time with NTP server"""
        try:
            # Run NTP query in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.ntp_client.request,
                self.ntp_server,
                version=3
            )
            
            # Calculate time offset
            self.time_offset = response.offset
            self.last_sync = datetime.now()
            
            # Check if drift exceeds 1 second
            if abs(self.time_offset) > 1.0:
                logger.warning(
                    f"Time drift warning: System time differs from NTP by "
                    f"{self.time_offset:.3f} seconds"
                )
            else:
                logger.info(
                    f"NTP sync successful. Offset: {self.time_offset:.3f}s"
                )
                
        except Exception as e:
            logger.error(f"Failed to sync with NTP server: {e}")
            
    def get_corrected_time(self) -> datetime:
        """Get current time corrected with NTP offset
        
        Returns:
            Corrected datetime
        """
        now = datetime.now()
        if self.time_offset is not None:
            # Apply offset correction
            from datetime import timedelta
            corrected = now + timedelta(seconds=self.time_offset)
            return corrected
        return now
        
    def get_time_drift(self) -> Optional[Decimal]:
        """Get current time drift in seconds
        
        Returns:
            Time drift in seconds, or None if not synced yet
        """
        if self.time_offset is not None:
            return Decimal(str(abs(self.time_offset)))
        return None
