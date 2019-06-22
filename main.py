# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START app]
import json
import logging
import os.path
import random

# Monkey-patch requests to play nicely with GAE
import requests
from requests_toolbelt.adapters import appengine
appengine.monkeypatch()

# [START imports]
from google.appengine.api import users
from google.appengine.ext import db

from datetime import datetime, timedelta
from dateutil import parser, tz

import jinja2
import webapp2

import gcal
# [END imports]


TODOIST_API_KEY = "2c37b695034a1783aff802fd58d439d08c20e5a6"
from todoist.api import TodoistAPI


jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                                "templates")))

def get_todoist_api():
    if not hasattr(get_todoist_api, "api"):
        get_todoist_api.api = TodoistAPI(TODOIST_API_KEY, cache=False)
        get_todoist_api.api.sync()
    return get_todoist_api.api

# # [START models]
# class UserModel(db.Model):
#     gcal_credentials = CredentialsProperty()
# [END models]



# [START form]
class FormHandler(webapp2.RequestHandler):

    @gcal.oauth_decorator.oauth_required
    def get(self):
        api = get_todoist_api()

        projects = {p["id"]: p for p in api.state["projects"]}

        from pprint import pprint
        pprint(api.state["user"])
        timezone = tz.gettz(api.state["user"]["tz_info"]["timezone"])

        target_date = self.request.GET.get("date")
        if target_date is None:
            now = datetime.now(timezone)
            today = now.date()
            tomorrow = today + timedelta(days=1)
            target_date = today + timedelta(days=1)
        else:
            target_date = parser.parse(target_date)
        target_date = datetime.combine(target_date, datetime.min.time().replace(tzinfo=timezone))

        start, end = target_date, target_date + timedelta(days=2)

        utc_offset = datetime.now(timezone).strftime("%z")

        # Get todos due on target date.
        due_todos = []
        for item in api["items"]:
            if item["due_date_utc"] is not None:
                date = parser.parse(item["due_date_utc"]).astimezone(timezone)
                if date >= start and date <= end:
                    item["predictedTime"] = 1.0 # TODO
                    due_todos.append(item)

        gcal_events = gcal.fetch_all_calendar_events(timeMin=start.isoformat(),
                                                     timeMax=end.isoformat())
        # Sort by increasing date.
        gcal_events = sorted(gcal_events, key=lambda ev: ev["dt_start"])

        # preprocess todo data
        for due_todo in due_todos:
            due_todo["project"] = projects[due_todo["project_id"]]

        template = jinja.get_template("form.html")
        self.response.write(template.render(
            date=str(target_date), utcOffset=utc_offset,
            todos=due_todos, gcal_events=gcal_events))

    @gcal.oauth_decorator.oauth_required
    def post(self):
        todo_events = json.loads(self.request.body)
        gcal.add_todo_events(todo_events)
        self.response.write("thanx")


class TrainHandler(webapp2.RequestHandler):
    """
    Handler for retrieving post-hoc calendar data and training/updating user
    model.
    """

    @gcal.oauth_decorator.oauth_required
    def get(self):
        api = get_todoist_api()

        timeMin = "2019-01-01T00:00:00Z"
        events = gcal.fetch_all_calendar_events(
            timeMin=timeMin,
            calendars=["jon@gauthiers.net"],
            query="[t]")

        # Get just Todoist events; convert datetime to JSON-friendly value
        events = [{"id": event["id"],
                   "dt_created": str(event["dt_created"]),
                   "dt_updated": str(event["dt_updated"]),
                   "dt_start": str(event["dt_start"]),
                   "dt_end": str(event["dt_end"]),
                   "summary": event["summary"],
                   "description": event["description"],
                   "todoist_id": event["properties"]["todoistId"]}
                  for event in events
                  if event["summary"].startswith("[t]")
                  and "todoistId" in event["properties"]]

        self.response.headers["Content-Type"] = "application/json"
        self.response.out.write(json.dumps(events))


app = webapp2.WSGIApplication(
    [("/form", FormHandler),
     ("/train", TrainHandler),
     (gcal.oauth_decorator.callback_path, gcal.oauth_decorator.callback_handler()),
    ], debug=True)
