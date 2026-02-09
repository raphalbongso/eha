"""Leave time / travel advisory tasks — v2 stub.

This module will integrate with the RouteProvider to calculate
optimal departure times and send "time to leave" notifications.
"""

from celery import shared_task


@shared_task(name="app.tasks.leave_time_tasks.calculate_leave_time")
def calculate_leave_time(user_id: str, event_id: str):
    """Calculate when user should leave for an event.

    v2 implementation will:
    1. Fetch event details (location, start time)
    2. Fetch user preferences (home/work address, transport mode)
    3. Query RouteProvider for travel time
    4. Schedule a push notification at (start_time - travel_time - buffer)
    """
    raise NotImplementedError("v2: Leave time calculation not yet implemented")
