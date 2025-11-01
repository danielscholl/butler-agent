"""Unit tests for activity tracking."""

import pytest

from butler.activity import ActivityTracker


class TestActivityTracker:
    """Test ActivityTracker class."""

    def test_default_state(self):
        """Test tracker starts in idle state."""
        tracker = ActivityTracker()
        assert tracker.current_activity == "Idle"

    def test_set_activity(self):
        """Test setting current activity."""
        tracker = ActivityTracker()
        tracker.set_activity("Running tests")
        assert tracker.current_activity == "Running tests"

    def test_reset(self):
        """Test resetting activity."""
        tracker = ActivityTracker()
        tracker.set_activity("Running tests")
        tracker.reset()
        assert tracker.current_activity == "Idle"

    def test_get_status(self):
        """Test getting current status."""
        tracker = ActivityTracker()
        assert tracker.get_status() == "Idle"
        
        tracker.set_activity("Processing")
        assert tracker.get_status() == "Processing"
