# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
import json
import random
from frappe.model.document import Document
from six import iteritems, string_types


class DesktopIcon(Document):
	def validate(self):
		if not self.label:
			self.label = self.module_name

	def on_trash(self):
		clear_desktop_icons_cache()

def after_doctype_insert():
	frappe.db.add_unique('Desktop Icon', ('module_name', 'owner', 'standard'))

def get_desktop_icons(user=None):
	'''Return desktop icons for user'''
	if not user:
		user = frappe.session.user

	user_icons = frappe.cache().hget('desktop_icons', user)

	if not user_icons:
		fields = ['module_name', 'hidden', 'label', 'link', 'type', 'icon', 'color',
			'_doctype', '_report', 'idx', 'force_show', 'reverse', 'custom', 'standard', 'blocked']

		active_domains = frappe.get_active_domains()

		blocked_doctypes = frappe.get_all("DocType", filters={
			"ifnull(restrict_to_domain, '')": ("not in", ",".join(active_domains))
		}, fields=["name"])

		blocked_doctypes = [ d.get("name") for d in blocked_doctypes ]

		standard_icons = frappe.db.get_all('Desktop Icon',
			fields=fields, filters={'standard': 1})

		standard_map = {}
		for icon in standard_icons:
			if icon._doctype in blocked_doctypes:
				icon.blocked = 1
			standard_map[icon.module_name] = icon

		user_icons = frappe.db.get_all('Desktop Icon', fields=fields,
			filters={'standard': 0, 'owner': user})

		# update hidden property
		for icon in user_icons:
			standard_icon = standard_map.get(icon.module_name, None)

			if icon._doctype in blocked_doctypes:
				icon.blocked = 1

			# override properties from standard icon
			if standard_icon:
				for key in ('route', 'label', 'color', 'icon', 'link'):
					if standard_icon.get(key):
						icon[key] = standard_icon.get(key)


				if standard_icon.blocked:
					icon.hidden = 1

					# flag for modules_setup page
					icon.hidden_in_standard = 1

				elif standard_icon.force_show:
					icon.hidden = 0

		# add missing standard icons (added via new install apps?)
		user_icon_names = [icon.module_name for icon in user_icons]
		for standard_icon in standard_icons:
			if standard_icon.module_name not in user_icon_names:

				# if blocked, hidden too!
				if standard_icon.blocked:
					standard_icon.hidden = 1
					standard_icon.hidden_in_standard = 1

				user_icons.append(standard_icon)

		user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()
		for icon in user_icons:
			if icon.module_name in user_blocked_modules:
				icon.hidden = 1

		# sort by idx
		user_icons.sort(lambda a, b: 1 if a.idx > b.idx else -1)

		# translate
		for d in user_icons:
			if d.label: d.label = _(d.label)

		frappe.cache().hset('desktop_icons', user, user_icons)

	return user_icons

@frappe.whitelist()
def add_user_icon(_doctype, _report=None, label=None, link=None, type='link', standard=0):
	'''Add a new user desktop icon to the desktop'''

	if not label: label = _doctype or _report
	if not link: link = 'List/{0}'.format(_doctype)

	# find if a standard icon exists
	icon_name = frappe.db.exists('Desktop Icon', {'standard': standard, 'link': link,
		'owner': frappe.session.user})

	if icon_name:
		if frappe.db.get_value('Desktop Icon', icon_name, 'hidden'):
			# if it is hidden, unhide it
			frappe.db.set_value('Desktop Icon', icon_name, 'hidden', 0)
			clear_desktop_icons_cache()

	else:
		idx = frappe.db.sql('select max(idx) from `tabDesktop Icon` where owner=%s',
			frappe.session.user)[0][0] or \
			frappe.db.sql('select count(*) from `tabDesktop Icon` where standard=1')[0][0]

		module = frappe.db.get_value('DocType', _doctype, 'module')
		module_icon = frappe.get_value('Desktop Icon', {'standard':1, 'module_name':module},
			['name', 'icon', 'color', 'reverse'], as_dict=True)

		if not frappe.db.get_value("Report", _report):
			_report = None

		if not module_icon:
			module_icon = frappe._dict()
			opts = random.choice(palette)
			module_icon.color = opts[0]
			module_icon.reverse = 0 if (len(opts) > 1) else 1

		try:
			new_icon = frappe.get_doc({
				'doctype': 'Desktop Icon',
				'label': label,
				'module_name': label,
				'link': link,
				'type': type,
				'_doctype': _doctype,
				'_report': _report,
				'icon': module_icon.icon,
				'color': module_icon.color,
				'reverse': module_icon.reverse,
				'idx': idx + 1,
				'custom': 1,
				'standard': standard
			}).insert(ignore_permissions=True)
			clear_desktop_icons_cache()

			icon_name = new_icon.name

		except frappe.UniqueValidationError as e:
			frappe.throw(_('Desktop Icon already exists'))
		except Exception as e:
			raise e

	return icon_name


@frappe.whitelist()
def set_order(new_order, user=None):
	'''set new order by duplicating user icons (if user is set) or set global order'''
	if isinstance(new_order, string_types):
		new_order = json.loads(new_order)
	for i, module_name in enumerate(new_order):
		if module_name not in ('Explore',):
			if user:
				icon = get_user_copy(module_name, user)
			else:
				name = frappe.db.get_value('Desktop Icon',
					{'standard': 1, 'module_name': module_name})
				if name:
					icon = frappe.get_doc('Desktop Icon', name)
				else:
					# standard icon missing, create one for DocType
					name = add_user_icon(module_name, standard=1)
					icon = frappe.get_doc('Desktop Icon', name)

			icon.db_set('idx', i)

	clear_desktop_icons_cache()

def set_desktop_icons(visible_list, ignore_duplicate=True):
	'''Resets all lists and makes only the given one standard,
	if the desktop icon does not exist and the name is a DocType, then will create
	an icon for the doctype'''

	# clear all custom
	frappe.db.sql('delete from `tabDesktop Icon` where standard=0')

	# set all as blocked
	frappe.db.sql('update `tabDesktop Icon` set blocked=0, hidden=1')

	# set as visible if present, or add icon
	for module_name in visible_list:
		name = frappe.db.get_value('Desktop Icon', {'module_name': module_name})
		if name:
			frappe.db.set_value('Desktop Icon', name, 'hidden', 0)
		else:
			if frappe.db.exists('DocType', module_name):
				try:
					add_user_icon(module_name, standard=1)
				except frappe.UniqueValidationError as e:
					if not ignore_duplicate:
						raise e
					else:
						visible_list.remove(module_name)
						if frappe.message_log:
							frappe.message_log.pop()

	# set the order
	set_order(visible_list)

	clear_desktop_icons_cache()

def set_hidden_list(hidden_list, user=None):
	'''Sets property `hidden`=1 in **Desktop Icon** for given user.
	If user is None then it will set global values.
	It will also set the rest of the icons as shown (`hidden` = 0)'''
	if isinstance(hidden_list, string_types):
		hidden_list = json.loads(hidden_list)

	# set as hidden
	for module_name in hidden_list:
		set_hidden(module_name, user, 1)

	# set as seen
	for module_name in list(set(get_all_icons()) - set(hidden_list)):
		set_hidden(module_name, user, 0)

	if user:
		clear_desktop_icons_cache()
	else:
		frappe.clear_cache()

def set_hidden(module_name, user=None, hidden=1):
	'''Set module hidden property for given user. If user is not specified,
		hide/unhide it globally'''
	if user:
		icon = get_user_copy(module_name, user)

		if hidden and icon.custom:
			frappe.delete_doc(icon.doctype, icon.name, ignore_permissions=True)
			return

		# hidden by user
		icon.db_set('hidden', hidden)
	else:
		icon = frappe.get_doc('Desktop Icon', {'standard': 1, 'module_name': module_name})

		# blocked is globally hidden
		icon.db_set('blocked', hidden)

def get_all_icons():
	return [d.module_name for d in frappe.get_all('Desktop Icon',
		filters={'standard': 1}, fields=['module_name'])]

def clear_desktop_icons_cache(user=None):
	frappe.cache().hdel('desktop_icons', user or frappe.session.user)
	frappe.cache().hdel('bootinfo', user or frappe.session.user)

def get_user_copy(module_name, user=None):
	'''Return user copy (Desktop Icon) of the given module_name. If user copy does not exist, create one.

	:param module_name: Name of the module
	:param user: User for which the copy is required (optional)
	'''
	if not user:
		user = frappe.session.user

	desktop_icon_name = frappe.db.get_value('Desktop Icon',
		{'module_name': module_name, 'owner': user, 'standard': 0})

	if desktop_icon_name:
		return frappe.get_doc('Desktop Icon', desktop_icon_name)
	else:
		return make_user_copy(module_name, user)

def make_user_copy(module_name, user):
	'''Insert and return the user copy of a standard Desktop Icon'''
	standard_name = frappe.db.get_value('Desktop Icon', {'module_name': module_name, 'standard': 1})

	if not standard_name:
		frappe.throw(_('{0} not found').format(module_name), frappe.DoesNotExistError)

	original = frappe.get_doc('Desktop Icon', standard_name)

	desktop_icon = frappe.get_doc({
		'doctype': 'Desktop Icon',
		'standard': 0,
		'owner': user,
		'module_name': module_name
	})

	for key in ('app', 'label', 'route', 'type', '_doctype', 'idx', 'reverse', 'force_show'):
		if original.get(key):
			desktop_icon.set(key, original.get(key))

	desktop_icon.insert(ignore_permissions=True)

	return desktop_icon

def sync_desktop_icons():
	'''Sync desktop icons from all apps'''
	for app in frappe.get_installed_apps():
		sync_from_app(app)

def sync_from_app(app):
	'''Sync desktop icons from app. To be called during install'''
	try:
		modules = frappe.get_attr(app + '.config.desktop.get_data')() or {}
	except ImportError:
		return []

	if isinstance(modules, dict):
		modules_list = []
		for m, desktop_icon in iteritems(modules):
			desktop_icon['module_name'] = m
			modules_list.append(desktop_icon)
	else:
		modules_list = modules

	for i, m in enumerate(modules_list):
		desktop_icon_name = frappe.db.get_value('Desktop Icon',
			{'module_name': m['module_name'], 'app': app, 'standard': 1})
		if desktop_icon_name:
			desktop_icon = frappe.get_doc('Desktop Icon', desktop_icon_name)
		else:
			# new icon
			desktop_icon = frappe.get_doc({
				'doctype': 'Desktop Icon',
				'idx': i,
				'standard': 1,
				'app': app,
				'owner': 'Administrator'
			})

		if 'doctype' in m:
			m['_doctype'] = m.pop('doctype')

		desktop_icon.update(m)
		desktop_icon.save()

	return modules_list

palette = (
	('#FFC4C4',),
	('#FFE8CD',),
	('#FFD2C2',),
	('#FF8989',),
	('#FFD19C',),
	('#FFA685',),
	('#FF4D4D', 1),
	('#FFB868',),
	('#FF7846', 1),
	('#A83333', 1),
	('#A87945', 1),
	('#A84F2E', 1),
	('#D2D2FF',),
	('#F8D4F8',),
	('#DAC7FF',),
	('#A3A3FF',),
	('#F3AAF0',),
	('#B592FF',),
	('#7575FF', 1),
	('#EC7DEA', 1),
	('#8E58FF', 1),
	('#4D4DA8', 1),
	('#934F92', 1),
	('#5E3AA8', 1),
	('#EBF8CC',),
	('#FFD7D7',),
	('#D2F8ED',),
	('#D9F399',),
	('#FFB1B1',),
	('#A4F3DD',),
	('#C5EC63',),
	('#FF8989', 1),
	('#77ECCA',),
	('#7B933D', 1),
	('#A85B5B', 1),
	('#49937E', 1),
	('#FFFACD',),
	('#D2F1FF',),
	('#CEF6D1',),
	('#FFF69C',),
	('#A6E4FF',),
	('#9DECA2',),
	('#FFF168',),
	('#78D6FF',),
	('#6BE273',),
	('#A89F45', 1),
	('#4F8EA8', 1),
	('#428B46', 1)
)
