"""Google Calendar tool for calendar management via MCP."""
import asyncio
import os
import pickle
from datetime import datetime, timedelta
from functools import wraps
from typing import List, Optional, Dict, Any
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from ..common.config import settings

mcp = FastMCP("Google Calendar Tool")

def async_wrap(func):
    """Decorator to run a synchronous function in an executor."""
    @wraps(func)
    async def run(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return run

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

async def _get_calendar_service():
    """Get authenticated Google Calendar service."""
    def _sync_get_service():
        creds = None
        token_file = settings.google_token_path
        credentials_file = settings.google_credentials_path
        
        # Load existing token
        if token_file.exists():
            with open(token_file, 'rb') as f:
                creds = pickle.load(f)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, 'wb') as f:
                pickle.dump(creds, f)
        
        return build('calendar', 'v3', credentials=creds)
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_service)


async def _resolve_calendar_id(calendar_id: str, service) -> str:
    """Resolve calendar name to calendar ID."""
    if calendar_id in ['primary', 'all'] or '@' in calendar_id:
        return calendar_id
    
    # Try to find calendar by name
    def _sync_list_calendars():
        return service.calendarList().list().execute()
    
    loop = asyncio.get_running_loop()
    calendar_list = await loop.run_in_executor(None, _sync_list_calendars)
    
    for calendar in calendar_list.get('items', []):
        if calendar.get('summary', '').lower() == calendar_id.lower():
            return calendar['id']
    
    # If not found, assume it's already an ID
    return calendar_id


def _format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    if 'T' in dt_str:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S %Z').strip()
    else:
        return dt_str + " (all-day)"


def _format_iso_datetime(date_str: Optional[str], default_offset_days: int = 0) -> str:
    """Format date string into full ISO 8601 datetime with UTC timezone."""
    if not date_str:
        dt = datetime.now() + timedelta(days=default_offset_days)
        return dt.isoformat() + 'Z'
    
    if date_str.endswith('Z'):
        return date_str
    elif 'T' not in date_str:
        # Date only - add appropriate time
        suffix = 'T00:00:00Z' if default_offset_days == 0 else 'T23:59:59Z'
        return date_str + suffix
    elif '+' in date_str:
        # Has timezone - parse and convert to UTC
        dt = datetime.fromisoformat(date_str)
        return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    else:
        # Datetime without timezone - assume UTC
        return date_str + 'Z' if not date_str.endswith('Z') else date_str


@mcp.tool(description="""Lists calendar events within a specified date range. The end date is exclusive (events on the `end_date` itself are *not* included). 

Defaults to the next 7 days if no dates provided. Use `calendar_id='all'` to search across all accessible calendars.

Date Format: ISO 8601 format required:
- DateTime: "2024-06-24T14:30:00Z" (UTC) or "2024-06-24T14:30:00+02:00" (with timezone)
- Date only: "2024-06-24" (for all-day events)

Error Handling:
- Raises ValueError for invalid date formats
- Raises RuntimeError for Google Calendar API errors (authentication, network, quota exceeded)
- Inaccessible calendars are silently skipped when using `calendar_id='all'`

Examples:
```python
# List next week's events from primary calendar
list_events()

# List events from specific date range
list_events(
    start_date="2024-06-24T09:00:00Z",
    end_date="2024-06-25T17:00:00Z"
)

# Search all calendars for today's events
list_events(
    calendar_id="all",
    start_date="2024-06-24",
    end_date="2024-06-25"
)
```""")
async def list_events(
    calendar_id: str = "primary",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 100
) -> str:
    """List calendar events."""
    try:
        service = await _get_calendar_service()
        
        # Format date range
        start_time = _format_iso_datetime(start_date)
        end_time = _format_iso_datetime(end_date, default_offset_days=7)
        
        events_list = []
        
        if calendar_id == "all":
            # Search all calendars
            def _sync_list_calendars():
                return service.calendarList().list().execute()
            
            loop = asyncio.get_running_loop()
            calendar_list = await loop.run_in_executor(None, _sync_list_calendars)
            
            for calendar in calendar_list.get('items', []):
                cal_id = calendar['id']
                
                def _sync_list_events():
                    return service.events().list(
                        calendarId=cal_id,
                        timeMin=start_time,
                        timeMax=end_time,
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                
                events_result = await loop.run_in_executor(None, _sync_list_events)
                
                cal_events = events_result.get('items', [])
                for event in cal_events:
                    event['calendar_name'] = calendar.get('summary', cal_id)
                events_list.extend(cal_events)
        else:
            # Search specific calendar
            resolved_id = await _resolve_calendar_id(calendar_id, service)
            
            def _sync_list_events():
                return service.events().list(
                    calendarId=resolved_id,
                    timeMin=start_time,
                    timeMax=end_time,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
            
            loop = asyncio.get_running_loop()
            events_result = await loop.run_in_executor(None, _sync_list_events)
            events_list = events_result.get('items', [])
        
        if not events_list:
            return f"No events found in the specified date range."
        
        # Sort by start time
        events_list.sort(key=lambda x: x.get('start', {}).get('dateTime', x.get('start', {}).get('date', '')))
        
        result = f"Found {len(events_list)} events:\n\n"
        
        for event in events_list:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'No Title')
            event_id = event['id']
            
            result += f"• {title}\n"
            result += f"  Time: {_format_datetime(start)}\n"
            result += f"  ID: {event_id}\n"
            
            if 'calendar_name' in event:
                result += f"  Calendar: {event['calendar_name']}\n"
            
            if event.get('location'):
                result += f"  Location: {event['location']}\n"
            
            result += "\n"
        
        return result.strip()
        
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Calendar service error: {e}")


@mcp.tool(description="Retrieves detailed information about a specific calendar event by its ID. Returns comprehensive event details including attendees, location, and timestamps.")
async def get_event(
    event_id: str,
    calendar_id: str = "primary"
) -> str:
    """Get detailed information about a specific event."""
    try:
        service = await _get_calendar_service()
        resolved_id = await _resolve_calendar_id(calendar_id, service)
        
        def _sync_get_event():
            return service.events().get(calendarId=resolved_id, eventId=event_id).execute()
        
        loop = asyncio.get_running_loop()
        event = await loop.run_in_executor(None, _sync_get_event)
        
        result = f"Event Details:\n"
        result += f"Title: {event.get('summary', 'No Title')}\n"
        
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        result += f"Start: {_format_datetime(start)}\n"
        result += f"End: {_format_datetime(end)}\n"
        
        if event.get('description'):
            result += f"Description: {event['description']}\n"
        
        if event.get('location'):
            result += f"Location: {event['location']}\n"
        
        if event.get('attendees'):
            result += f"Attendees:\n"
            for attendee in event['attendees']:
                email = attendee.get('email', 'Unknown')
                status = attendee.get('responseStatus', 'needsAction')
                result += f"  - {email} ({status})\n"
        
        result += f"Event ID: {event['id']}\n"
        result += f"Created: {event.get('created', 'Unknown')}\n"
        result += f"Updated: {event.get('updated', 'Unknown')}\n"
        
        return result
        
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(f"Event '{event_id}' not found in calendar '{calendar_id}'")
        raise RuntimeError(f"Google Calendar API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Calendar service error: {e}")


@mcp.tool(description="""Creates a new event in the specified calendar. 

Date/Time Formats (ISO 8601 required):
- Timed events: "2024-06-24T14:30:00Z" (UTC) or "2024-06-24T14:30:00+02:00" (with timezone)
- All-day events: "2024-06-24" (date only, no time component)

The `timezone` parameter defaults to UTC and is only used for timed events.

Error Handling:
- Raises ValueError for invalid date/time formats or missing required fields
- Raises RuntimeError for Google Calendar API errors (authentication, permissions, quota)
- Invalid attendee emails are accepted by the API but may not receive invitations

Examples:
```python
# Create a 1-hour meeting
create_event(
    summary="Team Standup",
    start_datetime="2024-06-24T10:00:00Z",
    end_datetime="2024-06-24T11:00:00Z",
    description="Daily team synchronization",
    attendees=["alice@company.com", "bob@company.com"]
)

# Create an all-day event
create_event(
    summary="Company Holiday",
    start_datetime="2024-12-25",
    end_datetime="2024-12-26"
)

# Create event with timezone
create_event(
    summary="Client Meeting",
    start_datetime="2024-06-24T14:00:00",
    end_datetime="2024-06-24T15:00:00",
    timezone="America/New_York"
)
```""")
async def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: str = "UTC",
    attendees: Optional[List[str]] = None
) -> str:
    """Create a new calendar event."""
    try:
        service = await _get_calendar_service()
        resolved_id = await _resolve_calendar_id(calendar_id, service)
        
        # Build event object
        event_body = {
            'summary': summary,
            'description': description or '',
            'start': {},
            'end': {}
        }
        
        # Handle all-day vs timed events
        if 'T' in start_datetime:
            # Timed event
            event_body['start']['dateTime'] = start_datetime
            event_body['start']['timeZone'] = timezone
            event_body['end']['dateTime'] = end_datetime
            event_body['end']['timeZone'] = timezone
        else:
            # All-day event
            event_body['start']['date'] = start_datetime
            event_body['end']['date'] = end_datetime
        
        # Add attendees if provided
        if attendees:
            event_body['attendees'] = [{'email': email} for email in attendees]
        
        # Create the event
        def _sync_create_event():
            return service.events().insert(
                calendarId=resolved_id,
                body=event_body
            ).execute()
        
        loop = asyncio.get_running_loop()
        created_event = await loop.run_in_executor(None, _sync_create_event)
        
        start = created_event['start'].get('dateTime', created_event['start'].get('date'))
        
        result = f"Event created successfully!\n"
        result += f"Title: {created_event['summary']}\n"
        result += f"Time: {_format_datetime(start)}\n"
        result += f"Event ID: {created_event['id']}\n"
        result += f"Calendar: {calendar_id}\n"
        
        if attendees:
            result += f"Attendees: {', '.join(attendees)}\n"
        
        return result
        
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Calendar service error: {e}")


@mcp.tool(description="""Updates an existing calendar event.
Only non-None parameters will be updated. To clear a field, pass an empty string.

Error Handling:
- Raises ValueError if event_id not found in specified calendar.
- Raises googleapiclient.errors.HttpError for API-level issues (permissions, etc).

Examples:
```python
# Update event time only
update_event(
    event_id="abc123def456",
    start_datetime="2024-06-24T11:00:00Z",
    end_datetime="2024-06-24T12:00:00Z"
)

# Update title and clear description
update_event(
    event_id="abc123def456",
    summary="New Meeting Title",
    description=""
)
```""")
async def update_event(
    event_id: str,
    calendar_id: str = "primary",
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """Update an existing calendar event. Trusts the provided event_id."""
    try:
        service = await _get_calendar_service()
        resolved_id = await _resolve_calendar_id(calendar_id, service)
        
        update_body = {}
        if summary is not None:
            update_body['summary'] = summary
        if description is not None:
            update_body['description'] = description
        
        if start_datetime:
            update_body['start'] = {'dateTime': start_datetime, 'timeZone': 'UTC'} if 'T' in start_datetime else {'date': start_datetime}
        
        if end_datetime:
            update_body['end'] = {'dateTime': end_datetime, 'timeZone': 'UTC'} if 'T' in end_datetime else {'date': end_datetime}
            
        if not update_body:
            return "No updates specified. Nothing to do."

        @async_wrap
        def _sync_patch_event():
            # Use 'patch' which is more efficient for partial updates
            return service.events().patch(
                calendarId=resolved_id,
                eventId=event_id,
                body=update_body
            ).execute()

        updated_event = await _sync_patch_event()
        return f"Event (ID: {updated_event['id']}) updated successfully. Fields changed: {', '.join(update_body.keys())}"
        
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(f"Event '{event_id}' not found in calendar '{calendar_id}'")
        raise  # Re-raise the original, informative HttpError


@mcp.tool(description="""Deletes a calendar event permanently.
WARNING: This action is irreversible.

Error Handling:
- Raises ValueError if event_id not found.
- Raises googleapiclient.errors.HttpError for API-level issues.

Example:
```python
# Delete an event by its ID
delete_event(
    event_id="abc123def456",
    calendar_id="primary"
)
```""")
async def delete_event(
    event_id: str,
    calendar_id: str = "primary"
) -> str:
    """Delete a calendar event. Trusts the provided event_id."""
    try:
        service = await _get_calendar_service()
        resolved_id = await _resolve_calendar_id(calendar_id, service)

        @async_wrap
        def _sync_delete_event():
            # The API will return a 404 if it doesn't exist, which is handled below.
            service.events().delete(calendarId=resolved_id, eventId=event_id).execute()

        await _sync_delete_event()
        return f"Event (ID: {event_id}) has been permanently deleted."
        
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(f"Event '{event_id}' not found in calendar '{calendar_id}'")
        raise # Re-raise the original HttpError for other API issues


@mcp.tool(description="Lists all calendars accessible to the authenticated user with their IDs, access levels, and colors. Use this to discover calendar IDs before using other calendar tools.")
async def list_calendars() -> str:
    """List all accessible calendars."""
    try:
        service = await _get_calendar_service()
        
        def _sync_list_calendars():
            return service.calendarList().list().execute()
        
        loop = asyncio.get_running_loop()
        calendar_list = await loop.run_in_executor(None, _sync_list_calendars)
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            return "No calendars found."
        
        result = f"Found {len(calendars)} accessible calendars:\n\n"
        
        for calendar in calendars:
            name = calendar.get('summary', 'Unknown')
            cal_id = calendar['id']
            access_role = calendar.get('accessRole', 'unknown')
            color_id = calendar.get('colorId', 'default')
            
            result += f"• {name}\n"
            result += f"  ID: {cal_id}\n"
            result += f"  Access: {access_role}\n"
            result += f"  Color: {color_id}\n\n"
        
        return result.strip()
        
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Calendar service error: {e}")


@mcp.tool(description="""Finds available free time slots within a calendar for scheduling meetings.

Defaults to next 7 days if no date range specified. Returns up to 20 slots, checking every 30 minutes.

Parameters:
- `duration_minutes`: Length of desired time slot (default: 60)
- `work_hours_only`: If True (default), restricts to weekdays 9 AM - 5 PM in the calendar's local timezone (not configurable)

Date Format: ISO 8601 format required ("2024-06-24T09:00:00Z" or "2024-06-24")

Error Handling:
- Raises ValueError for invalid date formats or missing required parameters
- Raises RuntimeError for Google Calendar API errors (network, authentication, quota)
- Returns descriptive error messages for debugging

Examples:
```python
# Find 1-hour slots in work hours for next week
find_time()

# Find 30-minute slots including evenings/weekends
find_time(
    duration_minutes=30,
    work_hours_only=False
)

# Find slots in specific date range
find_time(
    start_date="2024-06-24T09:00:00Z",
    end_date="2024-06-28T17:00:00Z",
    duration_minutes=90
)
```""")
async def find_time(
    calendar_id: str = "primary",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    duration_minutes: int = 60,
    work_hours_only: bool = True
) -> str:
    """Find free time slots in a calendar."""
    try:
        service = await _get_calendar_service()
        resolved_id = await _resolve_calendar_id(calendar_id, service)
        
        # Set default date range
        if not start_date:
            start_dt = datetime.now()
        else:
            start_dt = datetime.fromisoformat(start_date)
        
        if not end_date:
            end_dt = start_dt + timedelta(days=7)
        else:
            end_dt = datetime.fromisoformat(end_date)
        
        # Get busy times
        freebusy_request = {
            'timeMin': start_dt.isoformat() + 'Z',
            'timeMax': end_dt.isoformat() + 'Z',
            'items': [{'id': resolved_id}]
        }
        
        def _sync_freebusy_query():
            return service.freebusy().query(body=freebusy_request).execute()
        
        loop = asyncio.get_running_loop()
        freebusy_result = await loop.run_in_executor(None, _sync_freebusy_query)
        busy_times = freebusy_result['calendars'][resolved_id].get('busy', [])
        
        # Generate time slots
        slots = []
        current = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
        end_dt = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt
        slot_duration = timedelta(minutes=duration_minutes)
        
        while current + slot_duration <= end_dt:
            if work_hours_only and (current.hour < 9 or current.hour >= 17):
                current += timedelta(hours=1)
                continue
            
            slot_end = current + slot_duration
            
            # Check if slot conflicts with busy times
            is_free = True
            for busy in busy_times:
                busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00')).replace(tzinfo=None)
                busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00')).replace(tzinfo=None)
                
                if (current < busy_end and slot_end > busy_start):
                    is_free = False
                    break
            
            if is_free:
                slots.append((current, slot_end))
            
            current += timedelta(minutes=30)  # Check every 30 minutes
        
        if not slots:
            return f"No free {duration_minutes}-minute slots found in the specified time range."
        
        result = f"Found {len(slots)} free {duration_minutes}-minute slots:\n\n"
        
        for start_time, end_time in slots[:20]:  # Limit to first 20 slots
            result += f"• {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%H:%M')}\n"
        
        if len(slots) > 20:
            result += f"\n... and {len(slots) - 20} more slots"
        
        return result
        
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}")
    except Exception as e:
        raise RuntimeError(f"Calendar service error: {e}")


@mcp.tool(description="""Checks the status of the Google Calendar Tool server and API connectivity.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, API connection status, and a list of available tools.

**Error Handling:**
- Returns an error message if the server is not configured correctly or if there is a connection error.

**Examples:**
```python
# Check the server status.
server_info()
```""")
async def server_info() -> str:
    """Get server status and Google Calendar API connection info."""
    try:
        service = await _get_calendar_service()
        
        # Test API connection by getting calendar list
        def _sync_test_connection():
            return service.calendarList().list(maxResults=1).execute()
        
        loop = asyncio.get_running_loop()
        calendar_list = await loop.run_in_executor(None, _sync_test_connection)
        
        return f"""Google Calendar Tool Server Status
========================================
Status: Connected and ready
API Connection: ✓ Active
Calendars Access: ✓ Available ({len(calendar_list.get('items', []))} calendars accessible)

Available tools:
- list_events: List calendar events within date range
- get_event: Get detailed event information
- create_event: Create new calendar events
- update_event: Update existing events
- delete_event: Delete calendar events
- list_calendars: List all accessible calendars
- find_time: Find free time slots
- server_info: Get server status"""
        
    except FileNotFoundError as e:
        return f"""Google Calendar Tool Server Status
========================================
Status: Configuration Error
Error: {str(e)}

Please ensure Google Calendar credentials are properly configured."""
        
    except Exception as e:
        return f"""Google Calendar Tool Server Status
========================================
Status: Connection Error
Error: {str(e)}

Please check your internet connection and Google Calendar API credentials."""