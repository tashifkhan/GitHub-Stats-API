import json
import os
from datetime import datetime
from typing import Dict, Optional
import httpx
from fastapi import HTTPException


class ProfileViewsService:
    def __init__(self, storage_file: str = "profile_views.json"):
        self.storage_file = storage_file
        self.views_data = self._load_views_data()

    def _load_views_data(self) -> Dict[str, int]:
        """Load profile views data from storage file."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_views_data(self):
        """Save profile views data to storage file."""
        try:
            with open(self.storage_file, "w") as f:
                json.dump(self.views_data, f, indent=2)
        except IOError as e:
            print(f"Error saving profile views data: {e}")

    def increment_views(self, username: str) -> int:
        """Increment profile views for a user and return the new count."""
        username_lower = username.lower()
        current_views = self.views_data.get(username_lower, 0)
        new_views = current_views + 1
        self.views_data[username_lower] = new_views
        self._save_views_data()
        return new_views

    def get_views(self, username: str) -> int:
        """Get current profile views count for a user."""
        username_lower = username.lower()
        return self.views_data.get(username_lower, 0)

    def set_base_views(self, username: str, base_count: int) -> int:
        """Set a base count for profile views (useful for migration from other services)."""
        username_lower = username.lower()
        self.views_data[username_lower] = base_count
        self._save_views_data()
        return base_count


# Global instance
profile_views_service = ProfileViewsService()


async def get_profile_views(username: str, base: Optional[int] = None) -> int:
    """
    Get profile views count for a user.

    Args:
        username: GitHub username
        base: Optional base count to add to existing views (for migration)

    Returns:
        Total profile views count
    """
    if base is not None:
        return profile_views_service.set_base_views(username, base)

    return profile_views_service.get_views(username)


async def increment_profile_views(username: str) -> int:
    """
    Increment profile views count for a user.

    Args:
        username: GitHub username

    Returns:
        New total profile views count
    """
    return profile_views_service.increment_views(username)
