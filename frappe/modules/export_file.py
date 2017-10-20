# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, os, json
import frappe.model
from frappe.modules import scrub, get_module_path, lower_case_files_for, scrub_dt_dn

def export_doc(doc):
	export_to_files([[doc.doctype, doc.name]])

def export_to_files(record_list=None, record_module=None, verbose=0, create_init=None):
	"""
		Export record_list to files. record_list is a list of lists ([doctype],[docname] )  ,
	"""
	if frappe.flags.in_import:
		return

	if record_list:
		for record in record_list:
			write_document_file(frappe.get_doc(record[0], record[1]), record_module, create_init=create_init)

def write_document_file(doc, record_module=None, create_init=None):
	newdoc = doc.as_dict(no_nulls=True)

	# strip out default fields from children
	for df in doc.meta.get_table_fields():
		for d in newdoc.get(df.fieldname):
			for fieldname in frappe.model.default_fields:
				if fieldname in d:
					del d[fieldname]

	module = record_module or get_module_name(doc)
	if create_init is None:
		create_init = doc.doctype in lower_case_files_for

	# create folder
	folder = create_folder(module, doc.doctype, doc.name, create_init)

	# write the data file
	fname = (doc.doctype in lower_case_files_for and scrub(doc.name)) or doc.name
	with open(os.path.join(folder, fname +".json"),'w+') as txtfile:
		txtfile.write(frappe.as_json(newdoc))

def get_module_name(doc):
	if doc.doctype  == 'Module Def':
		module = doc.name
	elif doc.doctype=="Workflow":
		module = frappe.db.get_value("DocType", doc.document_type, "module")
	elif hasattr(doc, 'module'):
		module = doc.module
	else:
		module = frappe.db.get_value("DocType", doc.doctype, "module")

	return module

def create_folder(module, dt, dn, create_init):
	module_path = get_module_path(module)

	dt, dn = scrub_dt_dn(dt, dn)

	# create folder
	folder = os.path.join(module_path, dt, dn)

	frappe.create_folder(folder)

	# create init_py_files
	if create_init:
		create_init_py(module_path, dt, dn)

	return folder

def create_init_py(module_path, dt, dn):
	def create_if_not_exists(path):
		initpy = os.path.join(path, '__init__.py')
		if not os.path.exists(initpy):
			open(initpy, 'w').close()

	create_if_not_exists(os.path.join(module_path))
	create_if_not_exists(os.path.join(module_path, dt))
	create_if_not_exists(os.path.join(module_path, dt, dn))
