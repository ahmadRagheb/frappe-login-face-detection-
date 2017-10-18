# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from six.moves import range
from six import string_types
import frappe
import json

from frappe.utils import (getdate, cint, add_months, date_diff, add_days,
	nowdate, get_datetime_str, cstr, get_datetime, now_datetime, format_datetime)
from frappe.model.document import Document
from frappe.utils.user import get_enabled_system_users
from frappe.desk.reportview import get_filters_cond

weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

class Event(Document):
	def validate(self):
		if not self.starts_on:
			self.starts_on = now_datetime()

		if self.starts_on and self.ends_on and get_datetime(self.starts_on) > get_datetime(self.ends_on):
			frappe.msgprint(frappe._("Event end must be after start"), raise_exception=True)

		if self.starts_on == self.ends_on:
			# this scenario doesn't make sense i.e. it starts and ends at the same second!
			self.ends_on = None

		if getdate(self.starts_on) == getdate(self.ends_on) and self.repeat_on == "Every Day":
			frappe.msgprint(frappe._("Every day events should finish on the same day."), raise_exception=True)

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user
	return """(tabEvent.event_type='Public' or tabEvent.owner='%(user)s')""" % {
			"user": frappe.db.escape(user),
			"roles": "', '".join([frappe.db.escape(r) for r in frappe.get_roles(user)])
		}

def has_permission(doc, user):
	if doc.event_type=="Public" or doc.owner==user:
		return True

	return False


def send_event_digest():
	today = nowdate()
	for user in get_enabled_system_users():
		events = get_events(today, today, user.name, for_reminder=True)
		if events:
			frappe.set_user_lang(user.name, user.language)

			for e in events:
				e.starts_on = format_datetime(e.starts_on, 'hh:mm a')
				if e.all_day:
					e.starts_on = "All Day"

			frappe.sendmail(
				recipients=user.email,
				subject=frappe._("Upcoming Events for Today"),
				template="upcoming_events",
				args={
					'events': events,
				},
				header=[frappe._("Events in Today's Calendar"), 'blue']
			)

@frappe.whitelist()
def get_events(start, end, user=None, for_reminder=False, filters=None):
	if not user:
		user = frappe.session.user
	if isinstance(filters, string_types):
		filters = json.loads(filters)
	roles = frappe.get_roles(user)
	events = frappe.db.sql("""select name, subject, description, color,
		starts_on, ends_on, owner, all_day, event_type, repeat_this_event, repeat_on,repeat_till,
		monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from tabEvent where ((
			(date(starts_on) between date(%(start)s) and date(%(end)s))
			or (date(ends_on) between date(%(start)s) and date(%(end)s))
			or (date(starts_on) <= date(%(start)s) and date(ends_on) >= date(%(end)s))
		) or (
			date(starts_on) <= date(%(start)s) and repeat_this_event=1 and
			ifnull(repeat_till, "3000-01-01") > date(%(start)s)
		))
		{reminder_condition}
		{filter_condition}
		and (event_type='Public' or owner=%(user)s
		or exists(select name from `tabDocShare` where
			tabDocShare.share_doctype="Event" and `tabDocShare`.share_name=tabEvent.name
			and tabDocShare.user=%(user)s))
		order by starts_on""".format(
			filter_condition=get_filters_cond('Event', filters, []),
			reminder_condition="and ifnull(send_reminder,0)=1" if for_reminder else "",
			roles=", ".join('"{}"'.format(frappe.db.escape(r)) for r in roles)
		), {
			"start": start,
			"end": end,
			"user": user,
		}, as_dict=1)

	# process recurring events
	start = start.split(" ")[0]
	end = end.split(" ")[0]
	add_events = []
	remove_events = []

	def add_event(e, date):
		new_event = e.copy()

		enddate = add_days(date,int(date_diff(e.ends_on.split(" ")[0], e.starts_on.split(" ")[0]))) \
			if (e.starts_on and e.ends_on) else date
		new_event.starts_on = date + " " + e.starts_on.split(" ")[1]
		if e.ends_on:
			new_event.ends_on = enddate + " " + e.ends_on.split(" ")[1]
		add_events.append(new_event)

	for e in events:
		if e.repeat_this_event:
			e.starts_on = get_datetime_str(e.starts_on)
			if e.ends_on:
				e.ends_on = get_datetime_str(e.ends_on)

			event_start, time_str = get_datetime_str(e.starts_on).split(" ")
			if cstr(e.repeat_till) == "":
				repeat = "3000-01-01"
			else:
				repeat = e.repeat_till
			if e.repeat_on=="Every Year":
				start_year = cint(start.split("-")[0])
				end_year = cint(end.split("-")[0])
				event_start = "-".join(event_start.split("-")[1:])

				# repeat for all years in period
				for year in range(start_year, end_year+1):
					date = str(year) + "-" + event_start
					if getdate(date) >= getdate(start) and getdate(date) <= getdate(end) and getdate(date) <= getdate(repeat):
						add_event(e, date)

				remove_events.append(e)

			if e.repeat_on=="Every Month":
				date = start.split("-")[0] + "-" + start.split("-")[1] + "-" + event_start.split("-")[2]

				# last day of month issue, start from prev month!
				try:
					getdate(date)
				except ValueError:
					date = date.split("-")
					date = date[0] + "-" + str(cint(date[1]) - 1) + "-" + date[2]

				start_from = date
				for i in range(int(date_diff(end, start) / 30) + 3):
					if getdate(date) >= getdate(start) and getdate(date) <= getdate(end) \
						and getdate(date) <= getdate(repeat) and getdate(date) >= getdate(event_start):
						add_event(e, date)
					date = add_months(start_from, i+1)

				remove_events.append(e)

			if e.repeat_on=="Every Week":
				weekday = getdate(event_start).weekday()
				# monday is 0
				start_weekday = getdate(start).weekday()

				# start from nearest weeday after last monday
				date = add_days(start, weekday - start_weekday)

				for cnt in range(int(date_diff(end, start) / 7) + 3):
					if getdate(date) >= getdate(start) and getdate(date) <= getdate(end) \
						and getdate(date) <= getdate(repeat) and getdate(date) >= getdate(event_start):
						add_event(e, date)

					date = add_days(date, 7)

				remove_events.append(e)

			if e.repeat_on=="Every Day":
				for cnt in range(date_diff(end, start) + 1):
					date = add_days(start, cnt)
					if getdate(date) >= getdate(event_start) and getdate(date) <= getdate(end) \
						and getdate(date) <= getdate(repeat) and e[weekdays[getdate(date).weekday()]]:
						add_event(e, date)
				remove_events.append(e)

	for e in remove_events:
		events.remove(e)

	events = events + add_events

	for e in events:
		# remove weekday properties (to reduce message size)
		for w in weekdays:
			del e[w]

	return events
