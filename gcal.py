"""
Google Calendar utilities.
"""
import os.path

from googleapiclient.discovery import build
from oauth2client import file, client, tools
from httplib2 import Http
from dateutil.parser import parse
from oauth2client.contrib.appengine import OAuth2DecoratorFromClientSecrets, CredentialsProperty, StorageByKeyName


oauth_decorator = OAuth2DecoratorFromClientSecrets(
    os.path.join(os.path.dirname(__file__), "gcal_credentials.json"),
    "https://www.googleapis.com/auth/calendar")

service = build("calendar", "v3")

INCLUDE = ["jon@gauthiers.net", "MIT classes", "MIT regulars"]


def fetch_all_calendar_events(timeMin=None, timeMax=None,
                              calendars=None, preferred_timezones=None):
    http = oauth_decorator.http()

    # fetch all calendars
    calendars = service.calendarList().list(maxResults=250).execute(http=http)
    calendarIDs = [c["id"] for c in calendars["items"] if c["summary"] in INCLUDE]

    # https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/calendar_v3.events.html#list
    all_events = []
    recurring_events = []
    for calendarID in calendarIDs:
        events_req = service.events().list(calendarId=calendarID, maxResults=2500,
                                           timeMin=timeMin, timeMax=timeMax)
        while events_req is not None:
            events_resp = events_req.execute(http=http)
            items = events_resp["items"]

            while items:
                item = items.pop()

                if "recurrence" in item:
                    # This is a recurring event. Add to the queue relevant instances today.
                    instances = service.events().instances(
                            calendarId=calendarID, eventId=item["id"],
                            maxResults=2500, timeMin=timeMin, timeMax=timeMax) \
                        .execute(http=http)
                    items.extend(instances["items"])
                else:
                    if item.get("status") == "cancelled":
                        continue
                    elif "dateTime" not in item["start"]:
                        # all-day event
                        continue

                    start = item.get("start", {})
                    end = item.get("end", {})

                    all_events.append({
                        "id": item["id"],
                        "dt_created": parse(item["created"]) if "created" in item else None,
                        "dt_updated": parse(item["updated"]) if "updated" in item else None,
                        "dt_start": parse(start["dateTime"] if "dateTime" in start else start.get("date")),
                        "dt_end": parse(end["dateTime"] if "dateTime" in end else end.get("date")),
                        "summary": item.get("summary"),
                        "description": item.get("description"),
                        "is_allday": "dateTime" not in start,
                    })

            events_req = service.events().list_next(events_req, events_resp)

    return all_events


def add_todo_events(events, calendar=None):
    """
    Add todo-events to the given calendar (or primary calendar, if none is given).
    """

    http = oauth_decorator.http()
    batch = service.new_batch_http_request()

    res = service.events()
    for event in events:
        gcal_event = {
            "summary": "[t] %s" % event["title"],
            "start": {"dateTime": event["start"]},
            "end": {"dateTime": event["end"]},
            "extendedProperties": {
                "private": {"todoistId": event["id"]}
            }
        }
        result = res.insert(calendarId=calendar or "primary",
                            body=gcal_event).execute(http=http)
        print(result)
