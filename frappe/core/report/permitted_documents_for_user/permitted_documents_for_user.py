# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, throw
import frappe.utils.user
from frappe.permissions import check_admin_or_system_manager
from frappe.model.db_schema import type_map

def execute(filters=None):
	user, doctype, show_permissions = filters.get("user"), filters.get("doctype"), filters.get("show_permissions")
	validate(user, doctype)

	columns, fields = get_columns_and_fields(doctype)
	data = frappe.get_list(doctype, fields=fields, as_list=True, user=user)

	if show_permissions:
		columns = columns + ["Read", "Write", "Create", "Delete", "Submit", "Cancel", "Amend", "Print", "Email",
		                     "Report", "Import", "Export", "Share"]
		data = list(data)
		for i,item in enumerate(data):
			temp = frappe.permissions.get_doc_permissions(frappe.get_doc(doctype, item[0]), False,user)
			data[i] = item+(temp.get("read"),temp.get("write"),temp.get("create"),temp.get("delete"),temp.get("submit"),temp.get("cancel"),temp.get("amend"),temp.get("print"),temp.get("email"),temp.get("report"),temp.get("import"),temp.get("export"),temp.get("share"),)

	return columns, data

def validate(user, doctype):
	# check if current user is System Manager
	check_admin_or_system_manager()

	if not user:
		throw(_("Please specify user"))

	if not doctype:
		throw(_("Please specify doctype"))

def get_columns_and_fields(doctype):
	columns = ["Name:Link/{}:200".format(doctype)]
	fields = ["`name`"]
	for df in frappe.get_meta(doctype).fields:
		if df.in_list_view and df.fieldtype in type_map:
			fields.append("`{0}`".format(df.fieldname))
			fieldtype = "Link/{}".format(df.options) if df.fieldtype=="Link" else df.fieldtype
			columns.append("{label}:{fieldtype}:{width}".format(label=df.label, fieldtype=fieldtype, width=df.width or 100))

	return columns, fields

def query_doctypes(doctype, txt, searchfield, start, page_len, filters):
	user = filters.get("user")
	user_perms = frappe.utils.user.UserPermissions(user)
	user_perms.build_permissions()
	can_read = user_perms.can_read

	single_doctypes = [d[0] for d in frappe.db.get_values("DocType", {"issingle": 1})]

	out = []
	for dt in can_read:
		if txt.lower().replace("%", "") in dt.lower() and dt not in single_doctypes:
			out.append([dt])

	return out
