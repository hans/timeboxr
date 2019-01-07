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
    "https://www.googleapis.com/auth/calendar.readonly")

service = build("calendar", "v3")


def fetch_all_calendar_events(timeMin=None, timeMax=None,
                              calendars=None, preferred_timezones=None):
    http = oauth_decorator.http()

    # fetch all calendars
    calendars = service.calendarList().list(maxResults=250).execute(http=http)
    # DEV: MIT classes calendar ID
    calendarID = "gauthiers.net_0n5kpl5nf2srmrkstbfefab1m8@group.calendar.google.com"

    # TODO do for all calendars
    # https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/calendar_v3.events.html#list
    all_events = []
    recurring_events = []
    events_req = service.events().list(calendarId=calendarID, maxResults=2500, # calendarId="primary",
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

