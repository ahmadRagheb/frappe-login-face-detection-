# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import re, copy, os
import MySQLdb
import frappe
from frappe import _

from frappe.utils import now, cint
from frappe.model import no_value_fields, default_fields
from frappe.model.document import Document
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.notifications import delete_notification_count_for
from frappe.modules import make_boilerplate
from frappe.model.db_schema import validate_column_name, validate_column_length
import frappe.website.render

class InvalidFieldNameError(frappe.ValidationError): pass

form_grid_templates = {
	"fields": "templates/form_grid/fields.html"
}

class DocType(Document):
	def get_feed(self):
		return self.name

	def validate(self):
		"""Validate DocType before saving.

		- Check if developer mode is set.
		- Validate series
		- Check fieldnames (duplication etc)
		- Clear permission table for child tables
		- Add `amended_from` and `amended_by` if Amendable"""

		self.check_developer_mode()

		self.validate_name()

		if self.issingle:
			self.allow_import = 0
			self.is_submittable = 0
			self.istable = 0

		elif self.istable:
			self.allow_import = 0
			self.permissions = []

		self.scrub_field_names()
		self.set_default_in_list_view()
		self.validate_series()
		self.validate_document_type()
		validate_fields(self)

		if self.istable:
			# no permission records for child table
			self.permissions = []
		else:
			validate_permissions(self)

		self.make_amendable()
		self.validate_website()

		if not self.is_new():
			self.before_update = frappe.get_doc('DocType', self.name)

		if not self.is_new():
			self.setup_fields_to_fetch()

		if self.default_print_format and not self.custom:
			frappe.throw(_('Standard DocType cannot have default print format, use Customize Form'))

	def set_default_in_list_view(self):
		'''Set default in-list-view for first 4 mandatory fields'''
		if not [d.fieldname for d in self.fields if d.in_list_view]:
			cnt = 0
			for d in self.fields:
				if d.reqd and not d.hidden and not d.fieldtype == "Table":
					d.in_list_view = 1
					cnt += 1
					if cnt == 4: break

	def check_developer_mode(self):
		"""Throw exception if not developer mode or via patch"""
		if frappe.flags.in_patch or frappe.flags.in_test:
			return

		if not frappe.conf.get("developer_mode") and not self.custom:
			frappe.throw(_("Not in Developer Mode! Set in site_config.json or make 'Custom' DocType."))

	def setup_fields_to_fetch(self):
		'''Setup query to update values for newly set fetch values'''
		try:
			old_meta = frappe.get_meta(frappe.get_doc('DocType', self.name), cached=False)
			old_fields_to_fetch = [df.fieldname for df in old_meta.get_fields_to_fetch()]
		except frappe.DoesNotExistError:
			old_fields_to_fetch = []

		new_meta = frappe.get_meta(self, cached=False)

		self.flags.update_fields_to_fetch_queries = []

		if set(old_fields_to_fetch) != set([df.fieldname for df in new_meta.get_fields_to_fetch()]):
			for df in new_meta.get_fields_to_fetch():
				if df.fieldname not in old_fields_to_fetch:
					link_fieldname, source_fieldname = df.options.split('.', 1)
					link_df = new_meta.get_field(link_fieldname)

					self.flags.update_fields_to_fetch_queries.append('''update
							`tab{link_doctype}` source,
							`tab{doctype}` target
						set
							target.`{fieldname}` = source.`{source_fieldname}`
						where
							target.`{link_fieldname}` = source.name
							and ifnull(target.`{fieldname}`, '')="" '''.format(
								link_doctype = link_df.options,
								source_fieldname = source_fieldname,
								doctype = self.name,
								fieldname = df.fieldname,
								link_fieldname = link_fieldname
					))

	def update_fields_to_fetch(self):
		'''Update fetch values based on queries setup'''
		if self.flags.update_fields_to_fetch_queries:
			for query in self.flags.update_fields_to_fetch_queries:
				frappe.db.sql(query)

	def validate_document_type(self):
		if self.document_type=="Transaction":
			self.document_type = "Document"
		if self.document_type=="Master":
			self.document_type = "Setup"

	def validate_website(self):
		"""Ensure that website generator has field 'route'"""
		if self.has_web_view:
			# route field must be present
			if not 'route' in [d.fieldname for d in self.fields]:
				frappe.throw('Field "route" is mandatory for Web Views', title='Missing Field')

			# clear website cache
			frappe.website.render.clear_cache()

	def change_modified_of_parent(self):
		"""Change the timestamp of parent DocType if the current one is a child to clear caches."""
		if frappe.flags.in_import:
			return
		parent_list = frappe.db.sql("""SELECT parent
			from tabDocField where fieldtype="Table" and options=%s""", self.name)
		for p in parent_list:
			frappe.db.sql('UPDATE tabDocType SET modified=%s WHERE `name`=%s', (now(), p[0]))

	def scrub_field_names(self):
		"""Sluggify fieldnames if not set from Label."""
		restricted = ('name','parent','creation','modified','modified_by',
			'parentfield','parenttype','file_list', 'flags', 'docstatus')
		for d in self.get("fields"):
			if d.fieldtype:
				if (not getattr(d, "fieldname", None)):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(' ','_')
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + '1'
					else:
						d.fieldname = d.fieldtype.lower().replace(" ","_") + "_" + str(d.idx)

				# fieldnames should be lowercase
				d.fieldname = d.fieldname.lower()

	def validate_series(self, autoname=None, name=None):
		"""Validate if `autoname` property is correctly set."""
		if not autoname: autoname = self.autoname
		if not name: name = self.name

		if not autoname and self.get("fields", {"fieldname":"naming_series"}):
			self.autoname = "naming_series:"

		# validate field name if autoname field:fieldname is used

		if autoname and autoname.startswith('field:'):
			field = autoname.split(":")[1]
			if not field or field not in [ df.fieldname for df in self.fields ]:
				frappe.throw(_("Invalid fieldname '{0}' in autoname".format(field)))

		if autoname and (not autoname.startswith('field:')) \
			and (not autoname.startswith('eval:')) \
			and (not autoname.lower() in ('prompt', 'hash')) \
			and (not autoname.startswith('naming_series:')):

			prefix = autoname.split('.')[0]
			used_in = frappe.db.sql('select name from tabDocType where substring_index(autoname, ".", 1) = %s and name!=%s', (prefix, name))
			if used_in:
				frappe.throw(_("Series {0} already used in {1}").format(prefix, used_in[0][0]))

	def on_update(self):
		"""Update database schema, make controller templates if `custom` is not set and clear cache."""
		from frappe.model.db_schema import updatedb
		updatedb(self.name, self)

		self.change_modified_of_parent()
		make_module_and_roles(self)

		self.update_fields_to_fetch()

		from frappe import conf
		if not self.custom and not (frappe.flags.in_import or frappe.flags.in_test) and conf.get('developer_mode'):
			self.export_doc()
			self.make_controller_template()

			if self.has_web_view:
				self.set_base_class_for_controller()

		# update index
		if not self.custom:
			self.run_module_method("on_doctype_update")
			if self.flags.in_insert:
				self.run_module_method("after_doctype_insert")

		delete_notification_count_for(doctype=self.name)
		frappe.clear_cache(doctype=self.name)

		if not frappe.flags.in_install and hasattr(self, 'before_update'):
			self.sync_global_search()

		# clear from local cache
		if self.name in frappe.local.meta_cache:
			del frappe.local.meta_cache[self.name]

	def sync_global_search(self):
		'''If global search settings are changed, rebuild search properties for this table'''
		global_search_fields_before_update = [d.fieldname for d in
			self.before_update.fields if d.in_global_search]
		if self.before_update.show_name_in_global_search:
			global_search_fields_before_update.append('name')

		global_search_fields_after_update = [d.fieldname for d in
			self.fields if d.in_global_search]
		if self.show_name_in_global_search:
			global_search_fields_after_update.append('name')

		if set(global_search_fields_before_update) != set(global_search_fields_after_update):
			now = (not frappe.request) or frappe.flags.in_test or frappe.flags.in_install
			frappe.enqueue('frappe.utils.global_search.rebuild_for_doctype',
				now=now, doctype=self.name)

	def set_base_class_for_controller(self):
		'''Updates the controller class to subclass from `WebsiteGenertor`,
		if it is a subclass of `Document`'''
		controller_path = frappe.get_module_path(frappe.scrub(self.module),
			'doctype', frappe.scrub(self.name), frappe.scrub(self.name) + '.py')

		with open(controller_path, 'r') as f:
			code = f.read()

		class_string = '\nclass {0}(Document)'.format(self.name.replace(' ', ''))
		if '\nfrom frappe.model.document import Document' in code and class_string in code:
			code = code.replace('from frappe.model.document import Document',
				'from frappe.website.website_generator import WebsiteGenerator')
			code = code.replace('class {0}(Document)'.format(self.name.replace(' ', '')),
				'class {0}(WebsiteGenerator)'.format(self.name.replace(' ', '')))

		with open(controller_path, 'w') as f:
			f.write(code)


	def run_module_method(self, method):
		from frappe.modules import load_doctype_module
		module = load_doctype_module(self.name, self.module)
		if hasattr(module, method):
			getattr(module, method)()

	def before_rename(self, old, new, merge=False):
		"""Throw exception if merge. DocTypes cannot be merged."""
		if not self.custom and frappe.session.user != "Administrator":
			frappe.throw(_("DocType can only be renamed by Administrator"))

		self.check_developer_mode()

		self.validate_name(new)

		if merge:
			frappe.throw(_("DocType can not be merged"))

	def after_rename(self, old, new, merge=False):
		"""Change table name using `RENAME TABLE` if table exists. Or update
		`doctype` property for Single type."""
		if self.issingle:
			frappe.db.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
		else:
			frappe.db.sql("rename table `tab%s` to `tab%s`" % (old, new))

	def before_reload(self):
		"""Preserve naming series changes in Property Setter."""
		if not (self.issingle and self.istable):
			self.preserve_naming_series_options_in_property_setter()

	def preserve_naming_series_options_in_property_setter(self):
		"""Preserve naming_series as property setter if it does not exist"""
		naming_series = self.get("fields", {"fieldname": "naming_series"})

		if not naming_series:
			return

		# check if atleast 1 record exists
		if not (frappe.db.table_exists(self.name) and frappe.db.sql("select name from `tab{}` limit 1".format(self.name))):
			return

		existing_property_setter = frappe.db.get_value("Property Setter", {"doc_type": self.name,
			"property": "options", "field_name": "naming_series"})

		if not existing_property_setter:
			make_property_setter(self.name, "naming_series", "options", naming_series[0].options, "Text", validate_fields_for_doctype=False)
			if naming_series[0].default:
				make_property_setter(self.name, "naming_series", "default", naming_series[0].default, "Text", validate_fields_for_doctype=False)

	def export_doc(self):
		"""Export to standard folder `[module]/doctype/[name]/[name].json`."""
		from frappe.modules.export_file import export_to_files
		export_to_files(record_list=[['DocType', self.name]])

	def import_doc(self):
		"""Import from standard folder `[module]/doctype/[name]/[name].json`."""
		from frappe.modules.import_module import import_from_files
		import_from_files(record_list=[[self.module, 'doctype', self.name]])

	def make_controller_template(self):
		"""Make boilerplate controller template."""
		make_boilerplate("controller._py", self)

		if not (self.istable or self.issingle):
			make_boilerplate("test_controller._py", self.as_dict())

		if not self.istable:
			make_boilerplate("controller.js", self.as_dict())
			#make_boilerplate("controller_list.js", self.as_dict())
			if not os.path.exists(frappe.get_module_path(frappe.scrub(self.module),
				'doctype', frappe.scrub(self.name), 'tests')):
				make_boilerplate("test_controller.js", self.as_dict())

		if self.has_web_view:
			templates_path = frappe.get_module_path(frappe.scrub(self.module), 'doctype', frappe.scrub(self.name), 'templates')
			if not os.path.exists(templates_path):
				os.makedirs(templates_path)
			make_boilerplate('templates/controller.html', self.as_dict())
			make_boilerplate('templates/controller_row.html', self.as_dict())

	def make_amendable(self):
		"""If is_submittable is set, add amended_from docfields."""
		if self.is_submittable:
			if not frappe.db.sql("""select name from tabDocField
				where fieldname = 'amended_from' and parent = %s""", self.name):
					self.append("fields", {
						"label": "Amended From",
						"fieldtype": "Link",
						"fieldname": "amended_from",
						"options": self.name,
						"read_only": 1,
						"print_hide": 1,
						"no_copy": 1
					})

	def get_max_idx(self):
		"""Returns the highest `idx`"""
		max_idx = frappe.db.sql("""select max(idx) from `tabDocField` where parent = %s""",
			self.name)
		return max_idx and max_idx[0][0] or 0

	def validate_name(self, name=None):
		if not name:
			name = self.name

		# a DocType's name should not start with a number or underscore
		# and should only contain letters, numbers and underscore
		is_a_valid_name = re.match("^(?![\W])[^\d_\s][\w -]+$", name, re.UNICODE)
		if not is_a_valid_name:
			frappe.throw(_("DocType's name should start with a letter and it can only consist of letters, numbers, spaces and underscores"), frappe.NameError)

def validate_fields_for_doctype(doctype):
	validate_fields(frappe.get_meta(doctype, cached=False))

# this is separate because it is also called via custom field
def validate_fields(meta):
	"""Validate doctype fields. Checks

	1. There are no illegal characters in fieldnames
	2. If fieldnames are unique.
	3. Validate column length.
	4. Fields that do have database columns are not mandatory.
	5. `Link` and `Table` options are valid.
	6. **Hidden** and **Mandatory** are not set simultaneously.
	7. `Check` type field has default as 0 or 1.
	8. `Dynamic Links` are correctly defined.
	9. Precision is set in numeric fields and is between 1 & 6.
	10. Fold is not at the end (if set).
	11. `search_fields` are valid.
	12. `title_field` and title field pattern are valid.
	13. `unique` check is only valid for Data, Link and Read Only fieldtypes.
	14. `unique` cannot be checked if there exist non-unique values.

	:param meta: `frappe.model.meta.Meta` object to check."""
	def check_illegal_characters(fieldname):
		validate_column_name(fieldname)

	def check_unique_fieldname(fieldname):
		duplicates = list(filter(None, map(lambda df: df.fieldname==fieldname and str(df.idx) or None, fields)))
		if len(duplicates) > 1:
			frappe.throw(_("Fieldname {0} appears multiple times in rows {1}").format(fieldname, ", ".join(duplicates)))

	def check_fieldname_length(fieldname):
		validate_column_length(fieldname)

	def check_illegal_mandatory(d):
		if (d.fieldtype in no_value_fields) and d.fieldtype!="Table" and d.reqd:
			frappe.throw(_("Field {0} of type {1} cannot be mandatory").format(d.label, d.fieldtype))

	def check_link_table_options(d):
		if d.fieldtype in ("Link", "Table"):
			if not d.options:
				frappe.throw(_("Options required for Link or Table type field {0} in row {1}").format(d.label, d.idx))
			if d.options=="[Select]" or d.options==d.parent:
				return
			if d.options != d.parent:
				options = frappe.db.get_value("DocType", d.options, "name")
				if not options:
					frappe.throw(_("Options must be a valid DocType for field {0} in row {1}").format(d.label, d.idx))
				else:
					# fix case
					d.options = options

	def check_hidden_and_mandatory(d):
		if d.hidden and d.reqd and not d.default:
			frappe.throw(_("Field {0} in row {1} cannot be hidden and mandatory without default").format(d.label, d.idx))

	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			frappe.throw(_("Max width for type Currency is 100px in row {0}").format(d.idx))

	def check_in_list_view(d):
		if d.in_list_view and (d.fieldtype in not_allowed_in_list_view):
			frappe.throw(_("'In List View' not allowed for type {0} in row {1}").format(d.fieldtype, d.idx))

	def check_in_global_search(d):
		if d.in_global_search and d.fieldtype in no_value_fields:
			frappe.throw(_("'In Global Search' not allowed for type {0} in row {1}")
				.format(d.fieldtype, d.idx))

	def check_dynamic_link_options(d):
		if d.fieldtype=="Dynamic Link":
			doctype_pointer = filter(lambda df: df.fieldname==d.options, fields)
			if not doctype_pointer or (doctype_pointer[0].fieldtype not in ("Link", "Select")) \
				or (doctype_pointer[0].fieldtype=="Link" and doctype_pointer[0].options!="DocType"):
				frappe.throw(_("Options 'Dynamic Link' type of field must point to another Link Field with options as 'DocType'"))

	def check_illegal_default(d):
		if d.fieldtype == "Check" and d.default and d.default not in ('0', '1'):
			frappe.throw(_("Default for 'Check' type of field must be either '0' or '1'"))
		if d.fieldtype == "Select" and d.default and (d.default not in d.options.split("\n")):
			frappe.throw(_("Default for {0} must be an option").format(d.fieldname))

	def check_precision(d):
		if d.fieldtype in ("Currency", "Float", "Percent") and d.precision is not None and not (1 <= cint(d.precision) <= 6):
			frappe.throw(_("Precision should be between 1 and 6"))

	def check_unique_and_text(d):
		if meta.issingle:
			d.unique = 0
			d.search_index = 0

		if getattr(d, "unique", False):
			if d.fieldtype not in ("Data", "Link", "Read Only"):
				frappe.throw(_("Fieldtype {0} for {1} cannot be unique").format(d.fieldtype, d.label))

			if not d.get("__islocal"):
				try:
					has_non_unique_values = frappe.db.sql("""select `{fieldname}`, count(*)
						from `tab{doctype}` where ifnull({fieldname}, '') != ''
						group by `{fieldname}` having count(*) > 1 limit 1""".format(
						doctype=d.parent, fieldname=d.fieldname))

				except MySQLdb.OperationalError as e:
					if e.args and e.args[0]==1054:
						# ignore if missing column, else raise
						# this happens in case of Custom Field
						pass
					else:
						raise

				else:
					# else of try block
					if has_non_unique_values and has_non_unique_values[0][0]:
						frappe.throw(_("Field '{0}' cannot be set as Unique as it has non-unique values").format(d.label))

		if d.search_index and d.fieldtype in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
			frappe.throw(_("Fieldtype {0} for {1} cannot be indexed").format(d.fieldtype, d.label))

	def check_fold(fields):
		fold_exists = False
		for i, f in enumerate(fields):
			if f.fieldtype=="Fold":
				if fold_exists:
					frappe.throw(_("There can be only one Fold in a form"))
				fold_exists = True
				if i < len(fields)-1:
					nxt = fields[i+1]
					if nxt.fieldtype != "Section Break":
						frappe.throw(_("Fold must come before a Section Break"))
				else:
					frappe.throw(_("Fold can not be at the end of the form"))

	def check_search_fields(meta, fields):
		"""Throw exception if `search_fields` don't contain valid fields."""
		if not meta.search_fields:
			return

		# No value fields should not be included in search field
		search_fields = [field.strip() for field in (meta.search_fields or "").split(",")]
		fieldtype_mapper = { field.fieldname: field.fieldtype \
			for field in filter(lambda field: field.fieldname in search_fields, fields) }

		for fieldname in search_fields:
			fieldname = fieldname.strip()
			if (fieldtype_mapper.get(fieldname) in no_value_fields) or \
				(fieldname not in fieldname_list):
				frappe.throw(_("Search field {0} is not valid").format(fieldname))

	def check_title_field(meta):
		"""Throw exception if `title_field` isn't a valid fieldname."""
		if not meta.get("title_field"):
			return

		if meta.title_field not in fieldname_list:
			frappe.throw(_("Title field must be a valid fieldname"), InvalidFieldNameError)

		def _validate_title_field_pattern(pattern):
			if not pattern:
				return

			for fieldname in re.findall("{(.*?)}", pattern, re.UNICODE):
				if fieldname.startswith("{"):
					# edge case when double curlies are used for escape
					continue

				if fieldname not in fieldname_list:
					frappe.throw(_("{{{0}}} is not a valid fieldname pattern. It should be {{field_name}}.").format(fieldname),
						InvalidFieldNameError)

		df = meta.get("fields", filters={"fieldname": meta.title_field})[0]
		if df:
			_validate_title_field_pattern(df.options)
			_validate_title_field_pattern(df.default)

	def check_image_field(meta):
		'''check image_field exists and is of type "Attach Image"'''
		if not meta.image_field:
			return

		df = meta.get("fields", {"fieldname": meta.image_field})
		if not df:
			frappe.throw(_("Image field must be a valid fieldname"), InvalidFieldNameError)
		if df[0].fieldtype != 'Attach Image':
			frappe.throw(_("Image field must be of type Attach Image"), InvalidFieldNameError)

	def check_is_published_field(meta):
		if not meta.is_published_field:
			return

		if meta.is_published_field not in fieldname_list:
			frappe.throw(_("Is Published Field must be a valid fieldname"), InvalidFieldNameError)

	def check_timeline_field(meta):
		if not meta.timeline_field:
			return

		if meta.timeline_field not in fieldname_list:
			frappe.throw(_("Timeline field must be a valid fieldname"), InvalidFieldNameError)

		df = meta.get("fields", {"fieldname": meta.timeline_field})[0]
		if df.fieldtype not in ("Link", "Dynamic Link"):
			frappe.throw(_("Timeline field must be a Link or Dynamic Link"), InvalidFieldNameError)

	def check_sort_field(meta):
		'''Validate that sort_field(s) is a valid field'''
		if meta.sort_field:
			sort_fields = [meta.sort_field]
			if ','  in meta.sort_field:
				sort_fields = [d.split()[0] for d in meta.sort_field.split(',')]

			for fieldname in sort_fields:
				if not fieldname in fieldname_list + list(default_fields):
					frappe.throw(_("Sort field {0} must be a valid fieldname").format(fieldname),
						InvalidFieldNameError)

	fields = meta.get("fields")
	fieldname_list = [d.fieldname for d in fields]

	not_allowed_in_list_view = list(copy.copy(no_value_fields))
	not_allowed_in_list_view.append("Attach Image")
	if meta.istable:
		not_allowed_in_list_view.remove('Button')

	for d in fields:
		if not d.permlevel: d.permlevel = 0
		if d.fieldtype != "Table": d.allow_bulk_edit = 0
		if not d.fieldname:
			frappe.throw(_("Fieldname is required in row {0}").format(d.idx))
		d.fieldname = d.fieldname.lower()
		check_illegal_characters(d.fieldname)
		check_unique_fieldname(d.fieldname)
		check_fieldname_length(d.fieldname)
		check_illegal_mandatory(d)
		check_link_table_options(d)
		check_dynamic_link_options(d)
		check_hidden_and_mandatory(d)
		check_in_list_view(d)
		check_in_global_search(d)
		check_illegal_default(d)
		check_unique_and_text(d)

	check_fold(fields)
	check_search_fields(meta, fields)
	check_title_field(meta)
	check_timeline_field(meta)
	check_is_published_field(meta)
	check_sort_field(meta)

def validate_permissions_for_doctype(doctype, for_remove=False):
	"""Validates if permissions are set correctly."""
	doctype = frappe.get_doc("DocType", doctype)
	validate_permissions(doctype, for_remove)

	# save permissions
	for perm in doctype.get("permissions"):
		perm.db_update()

	clear_permissions_cache(doctype.name)

def clear_permissions_cache(doctype):
	frappe.clear_cache(doctype=doctype)
	delete_notification_count_for(doctype)
	for user in frappe.db.sql_list("""select
			distinct `tabHas Role`.parent
		from
			`tabHas Role`,
		tabDocPerm
			where tabDocPerm.parent = %s
			and tabDocPerm.role = `tabHas Role`.role""", doctype):
		frappe.clear_cache(user=user)

def validate_permissions(doctype, for_remove=False):
	permissions = doctype.get("permissions")
	if not permissions:
		frappe.msgprint(_('No Permissions Specified'), alert=True, indicator='orange')
	issingle = issubmittable = isimportable = False
	if doctype:
		issingle = cint(doctype.issingle)
		issubmittable = cint(doctype.is_submittable)
		isimportable = cint(doctype.allow_import)

	def get_txt(d):
		return _("For {0} at level {1} in {2} in row {3}").format(d.role, d.permlevel, d.parent, d.idx)

	def check_atleast_one_set(d):
		if not d.read and not d.write and not d.submit and not d.cancel and not d.create:
			frappe.throw(_("{0}: No basic permissions set").format(get_txt(d)))

	def check_double(d):
		has_similar = False
		similar_because_of = ""
		for p in permissions:
			if p.role==d.role and p.permlevel==d.permlevel and p!=d:
				if p.apply_user_permissions==d.apply_user_permissions:
					has_similar = True
					similar_because_of = _("Apply User Permissions")
					break
				elif p.if_owner==d.if_owner:
					similar_because_of = _("If Owner")
					has_similar = True
					break

		if has_similar:
			frappe.throw(_("{0}: Only one rule allowed with the same Role, Level and {1}")\
				.format(get_txt(d),	similar_because_of))

	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role != 'All':
			has_zero_perm = False
			for p in permissions:
				if p.role==d.role and (p.permlevel or 0)==0 and p!=d:
					has_zero_perm = True
					break

			if not has_zero_perm:
				frappe.throw(_("{0}: Permission at level 0 must be set before higher levels are set").format(get_txt(d)))

			for invalid in ("create", "submit", "cancel", "amend"):
				if d.get(invalid): d.set(invalid, 0)

	def check_permission_dependency(d):
		if d.cancel and not d.submit:
			frappe.throw(_("{0}: Cannot set Cancel without Submit").format(get_txt(d)))

		if (d.submit or d.cancel or d.amend) and not d.write:
			frappe.throw(_("{0}: Cannot set Submit, Cancel, Amend without Write").format(get_txt(d)))
		if d.amend and not d.write:
			frappe.throw(_("{0}: Cannot set Amend without Cancel").format(get_txt(d)))
		if d.get("import") and not d.create:
			frappe.throw(_("{0}: Cannot set Import without Create").format(get_txt(d)))

	def remove_rights_for_single(d):
		if not issingle:
			return

		if d.report:
			frappe.msgprint(_("Report cannot be set for Single types"))
			d.report = 0
			d.set("import", 0)
			d.set("export", 0)

		for ptype, label in (
			("set_user_permissions", _("Set User Permissions")),
			("apply_user_permissions", _("Apply User Permissions"))):
			if d.get(ptype):
				d.set(ptype, 0)
				frappe.msgprint(_("{0} cannot be set for Single types").format(label))

	def check_if_submittable(d):
		if d.submit and not issubmittable:
			frappe.throw(_("{0}: Cannot set Assign Submit if not Submittable").format(get_txt(d)))
		elif d.amend and not issubmittable:
			frappe.throw(_("{0}: Cannot set Assign Amend if not Submittable").format(get_txt(d)))

	def check_if_importable(d):
		if d.get("import") and not isimportable:
			frappe.throw(_("{0}: Cannot set import as {1} is not importable").format(get_txt(d), doctype))

	for d in permissions:
		if not d.permlevel:
			d.permlevel=0
		check_atleast_one_set(d)
		if not for_remove:
			check_double(d)
			check_permission_dependency(d)
			check_if_submittable(d)
			check_if_importable(d)
		check_level_zero_is_set(d)
		remove_rights_for_single(d)

def make_module_and_roles(doc, perm_fieldname="permissions"):
	"""Make `Module Def` and `Role` records if already not made. Called while installing."""
	try:
		if not frappe.db.exists("Module Def", doc.module):
			m = frappe.get_doc({"doctype": "Module Def", "module_name": doc.module})
			m.app_name = frappe.local.module_app[frappe.scrub(doc.module)]
			m.flags.ignore_mandatory = m.flags.ignore_permissions = True
			m.insert()

		default_roles = ["Administrator", "Guest", "All"]
		roles = [p.role for p in doc.get("permissions") or []] + default_roles

		for role in list(set(roles)):
			if not frappe.db.exists("Role", role):
				r = frappe.get_doc(dict(doctype= "Role", role_name=role, desk_access=1))
				r.flags.ignore_mandatory = r.flags.ignore_permissions = True
				r.insert()
	except frappe.DoesNotExistError as e:
		pass
	except frappe.SQLError as e:
		if e.args[0]==1146:
			pass
		else:
			raise

def init_list(doctype):
	"""Make boilerplate list views."""
	doc = frappe.get_meta(doctype)
	make_boilerplate("controller_list.js", doc)
	make_boilerplate("controller_list.html", doc)

def check_if_fieldname_conflicts_with_methods(doctype, fieldname):
	doc = frappe.get_doc({"doctype": doctype})
	method_list = [method for method in dir(doc) if isinstance(method, str) and callable(getattr(doc, method))]

	if fieldname in method_list:
		frappe.throw(_("Fieldname {0} conflicting with meta object").format(fieldname))
