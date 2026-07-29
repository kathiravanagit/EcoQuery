"""
Temporal Shifter — delays non-urgent tasks to low-carbon hours.
Google-style carbon-aware scheduling: shift workloads to when the grid is greenest.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable
from carbon_collector import collector

logger = logging.getLogger("EcoQuery.temporal_shifter")


class TemporalShifter:
    """Delays tasks to low-carbon hours when possible."""

    def __init__(self):
        # Max delay for non-urgent tasks (in minutes)
        self.max_delay_minutes = int(os.getenv("CARBON_MAX_DELAY", "120"))
        # Carbon intensity threshold — only delay if above this
        self.delay_threshold = int(os.getenv("CARBON_DELAY_THRESHOLD", "300"))
        # Hours considered "green" (grid is clean)
        self.green_hours = [2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 22, 23]

    def should_delay(self, zone: str, current_intensity: float) -> bool:
        """Check if task should be delayed based on current intensity."""
        if current_intensity <= self.delay_threshold:
            return False  # Already green enough

        current_hour = datetime.now(timezone.utc).hour
        if current_hour in self.green_hours:
            return False  # Already in green window

        return True

    def get_next_green_hour(self, zone: str) -> datetime:
        """Find the next green hour from now."""
        now = datetime.now(timezone.utc)
        current_hour = now.hour

        # Check next 24 hours
        for offset in range(1, 25):
            next_hour = (current_hour + offset) % 24
            if next_hour in self.green_hours:
                next_green = now.replace(
                    hour=next_hour, minute=0, second=0, microsecond=0
                )
                if next_green <= now:
                    next_green += timedelta(days=1)
                return next_green

        # Fallback: 2 hours from now
        return now + timedelta(hours=2)

    async def delay_if_needed(
        self,
        zone: str,
        task_id: str,
        urgency: str = "normal",
    ) -> dict:
        """Delay task if appropriate.

        Returns:
            {
                "delayed": bool,
                "delay_minutes": int,
                "scheduled_for": str,
                "current_intensity": float,
                "expected_intensity": float,
                "reason": str,
            }
        """
        # Urgent tasks are never delayed
        if urgency == "urgent":
            return {
                "delayed": False,
                "delay_minutes": 0,
                "scheduled_for": datetime.now(timezone.utc).isoformat(),
                "current_intensity": 0,
                "expected_intensity": 0,
                "reason": "urgent — executing now",
            }

        # Get current intensity
        intensity_data = await collector.get_intensity(zone)
        current_intensity = intensity_data["intensity"]

        # Check if delay is needed
        if not self.should_delay(zone, current_intensity):
            return {
                "delayed": False,
                "delay_minutes": 0,
                "scheduled_for": datetime.now(timezone.utc).isoformat(),
                "current_intensity": current_intensity,
                "expected_intensity": current_intensity,
                "reason": "current grid is green enough",
            }

        # Calculate delay
        next_green = self.get_next_green_hour(zone)
        now = datetime.now(timezone.utc)
        delay_minutes = min(
            int((next_green - now).total_seconds() / 60),
            self.max_delay_minutes,
        )

        if delay_minutes <= 5:
            return {
                "delayed": False,
                "delay_minutes": 0,
                "scheduled_for": now.isoformat(),
                "current_intensity": current_intensity,
                "expected_intensity": current_intensity,
                "reason": "delay too short — executing now",
            }

        # Estimate green hour intensity
        green_hour_data = await collector.get_intensity(zone)
        expected_intensity = green_hour_data["intensity"]

        logger.info(
            f"Task {task_id} delayed {delay_minutes}min "
            f"({current_intensity} → {expected_intensity} g CO₂/kWh)"
        )

        return {
            "delayed": True,
            "delay_minutes": delay_minutes,
            "scheduled_for": next_green.isoformat(),
            "current_intensity": current_intensity,
            "expected_intensity": expected_intensity,
            "reason": (
                f"delaying {delay_minutes}min to green hour "
                f"(saving ~{current_intensity - expected_intensity} g CO₂/kWh)"
            ),
        }

    async def run_at_greenest(
        self,
        zone: str,
        task: Callable,
        *args,
        **kwargs,
    ):
        """Run a task at the greenest time.

        If current time is green, runs immediately.
        Otherwise, waits until next green hour.
        """
        result = await self.delay_if_needed(zone, task.__name__)

        if result["delayed"]:
            delay_seconds = result["delay_minutes"] * 60
            logger.info(f"Waiting {delay_seconds}s for green hour...")
            await asyncio.sleep(delay_seconds)

        return await task(*args, **kwargs)

    def get_carbon_schedule(self, zone: str, hours: int = 24) -> list:
        """Get carbon intensity forecast for next N hours."""
        schedule = []
        now = datetime.now(timezone.utc)

        for offset in range(hours):
            hour = (now.hour + offset) % 24
            is_green = hour in self.green_hours

            schedule.append({
                "hour": hour,
                "utc_time": (now + timedelta(hours=offset)).isoformat(),
                "is_green_window": is_green,
                "recommendation": "run" if is_green else "delay",
            })

        return schedule

    def estimate_savings(self, zone: str, current_intensity: float) -> dict:
        """Estimate carbon savings from temporal shifting."""
        # Average green hour intensity (varies by region)
        green_hour_intensities = {
            "eu-north-1": 10,   # Nuclear/hydro
            "eu-west-3": 40,    # Nuclear
            "eu-central-1": 150, # Wind
            "eu-west-1": 25,    # Wind/hydro
            "us-west-2": 60,    # Hydro
        }

        green_intensity = green_hour_intensities.get(zone, 200)
        savings_per_hour = current_intensity - green_intensity

        return {
            "current_intensity": current_intensity,
            "green_hour_intensity": green_intensity,
            "savings_per_hour": max(0, savings_per_hour),
            "savings_percentage": round(
                (max(0, savings_per_hour) / max(1, current_intensity)) * 100, 1
            ),
        }


shifter = TemporalShifter()
