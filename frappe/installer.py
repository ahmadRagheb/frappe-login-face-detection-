# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# called from wnf.py
# lib/wnf.py --install [rootpassword] [dbname] [source]

from __future__ import unicode_literals, print_function

import os, json, sys, subprocess, shutil
import frappe
import frappe.database
import getpass
import importlib
from frappe import _
from frappe.model.db_schema import DbManager
from frappe.model.sync import sync_for
from frappe.utils.fixtures import sync_fixtures
from frappe.website import render
from frappe.desk.doctype.desktop_icon.desktop_icon import sync_from_app
from frappe.utils.password import create_auth_table
from frappe.utils.global_search import setup_global_search_table
from frappe.modules.utils import sync_customizations

def install_db(root_login="root", root_password=None, db_name=None, source_sql=None,
	admin_password=None, verbose=True, force=0, site_config=None, reinstall=False):
	make_conf(db_name, site_config=site_config)
	frappe.flags.in_install_db = True
	if reinstall:
		frappe.connect(db_name=db_name)
		dbman = DbManager(frappe.local.db)
		dbman.create_database(db_name)

	else:
		frappe.local.db = get_root_connection(root_login, root_password)
		frappe.local.session = frappe._dict({'user':'Administrator'})
		create_database_and_user(force, verbose)

	frappe.conf.admin_password = frappe.conf.admin_password or admin_password

	frappe.connect(db_name=db_name)
	check_if_ready_for_barracuda()
	import_db_from_sql(source_sql, verbose)
	if not 'tabDefaultValue' in frappe.db.get_tables():
		print('''Database not installed, this can due to lack of permission, or that the database name exists.
Check your mysql root password, or use --force to reinstall''')
		sys.exit(1)

	remove_missing_apps()

	create_auth_table()
	setup_global_search_table()
	create_user_settings_table()

	frappe.flags.in_install_db = False


def create_database_and_user(force, verbose):
	db_name = frappe.local.conf.db_name
	dbman = DbManager(frappe.local.db)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name)
		dbman.drop_database(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, frappe.conf.db_password)
	if verbose: print("Created user %s" % db_name)

	dbman.create_database(db_name)
	if verbose: print("Created database %s" % db_name)

	dbman.grant_all_privileges(db_name, db_name)
	dbman.flush_privileges()
	if verbose: print("Granted privileges to user %s and database %s" % (db_name, db_name))

	# close root connection
	frappe.db.close()

def create_user_settings_table():
	frappe.db.sql_ddl("""create table if not exists __UserSettings (
		`user` VARCHAR(180) NOT NULL,
		`doctype` VARCHAR(180) NOT NULL,
		`data` TEXT,
		UNIQUE(user, doctype)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

def import_db_from_sql(source_sql, verbose):
	if verbose: print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(frappe.__file__), 'data', 'Framework.sql')
	DbManager(frappe.local.db).restore_database(db_name, source_sql, db_name, frappe.conf.db_password)
	if verbose: print("Imported from database %s" % source_sql)

def get_root_connection(root_login='root', root_password=None):
	if not frappe.local.flags.root_connection:
		if root_login:
			if not root_password:
				root_password = frappe.conf.get("root_password") or None

			if not root_password:
				root_password = getpass.getpass("MySQL root password: ")
		frappe.local.flags.root_connection = frappe.database.Database(user=root_login, password=root_password)

	return frappe.local.flags.root_connection

def install_app(name, verbose=False, set_as_patched=True):
	frappe.flags.in_install = name
	frappe.clear_cache()
	app_hooks = frappe.get_hooks(app_name=name)
	installed_apps = frappe.get_installed_apps()

	# install pre-requisites
	if app_hooks.required_apps:
		for app in app_hooks.required_apps:
			install_app(app)

	frappe.flags.in_install = name
	frappe.clear_cache()

	if name not in frappe.get_all_apps():
		raise Exception("App not in apps.txt")

	if name in installed_apps:
		frappe.msgprint(_("App {0} already installed").format(name))
		return

	print("\nInstalling {0}...".format(name))

	if name != "frappe":
		frappe.only_for("System Manager")

	for before_install in app_hooks.before_install or []:
		out = frappe.get_attr(before_install)()
		if out==False:
			return

	if name != "frappe":
		add_module_defs(name)

	sync_for(name, force=True, sync_everything=True, verbose=verbose, reset_permissions=True)

	sync_from_app(name)

	add_to_installed_apps(name)

	frappe.get_doc('Portal Settings', 'Portal Settings').sync_menu()

	if set_as_patched:
		set_all_patches_as_completed(name)

	for after_install in app_hooks.after_install or []:
		frappe.get_attr(after_install)()

	sync_fixtures(name)
	sync_customizations(name)

	frappe.flags.in_install = False

def add_to_installed_apps(app_name, rebuild_website=True):
	installed_apps = frappe.get_installed_apps()
	if not app_name in installed_apps:
		installed_apps.append(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
		post_install(rebuild_website)

def remove_from_installed_apps(app_name):
	installed_apps = frappe.get_installed_apps()
	if app_name in installed_apps:
		installed_apps.remove(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
		if frappe.flags.in_install:
			post_install()

def remove_app(app_name, dry_run=False, yes=False):
	"""Delete app and all linked to the app's module with the app."""

	if not dry_run and not yes:
		confirm = raw_input("All doctypes (including custom), modules related to this app will be deleted. Are you sure you want to continue (y/n) ? ")
		if confirm!="y":
			return

	from frappe.utils.backups import scheduled_backup
	print("Backing up...")
	scheduled_backup(ignore_files=True)

	drop_doctypes = []

	# remove modules, doctypes, roles
	for module_name in frappe.get_module_list(app_name):
		for doctype in frappe.get_list("DocType", filters={"module": module_name},
			fields=["name", "issingle"]):
			print("removing DocType {0}...".format(doctype.name))

			if not dry_run:
				frappe.delete_doc("DocType", doctype.name)

				if not doctype.issingle:
					drop_doctypes.append(doctype.name)

		# remove reports, pages and web forms
		for doctype in ("Report", "Page", "Web Form"):
			for record in frappe.get_list(doctype, filters={"module": module_name}):
				print("removing {0} {1}...".format(doctype, record.name))
				if not dry_run:
					frappe.delete_doc(doctype, record.name)

		print("removing Module {0}...".format(module_name))
		if not dry_run:
			frappe.delete_doc("Module Def", module_name)

	# delete desktop icons
	frappe.db.sql('delete from `tabDesktop Icon` where app=%s', app_name)

	remove_from_installed_apps(app_name)

	if not dry_run:
		# drop tables after a commit
		frappe.db.commit()

		for doctype in set(drop_doctypes):
			frappe.db.sql("drop table `tab{0}`".format(doctype))

def post_install(rebuild_website=False):
	if rebuild_website:
		render.clear_cache()

	init_singles()
	frappe.db.commit()
	frappe.clear_cache()

def set_all_patches_as_completed(app):
	patch_path = os.path.join(frappe.get_pymodule_path(app), "patches.txt")
	if os.path.exists(patch_path):
		for patch in frappe.get_file_items(patch_path):
			frappe.get_doc({
				"doctype": "Patch Log",
				"patch": patch
			}).insert(ignore_permissions=True)
		frappe.db.commit()

def init_singles():
	singles = [single['name'] for single in frappe.get_all("DocType", filters={'issingle': True})]
	for single in singles:
		if not frappe.db.get_singles_dict(single):
			doc = frappe.new_doc(single)
			doc.flags.ignore_mandatory=True
			doc.flags.ignore_validate=True
			doc.save()

def make_conf(db_name=None, db_password=None, site_config=None):
	site = frappe.local.site
	make_site_config(db_name, db_password, site_config)
	sites_path = frappe.local.sites_path
	frappe.destroy()
	frappe.init(site, sites_path=sites_path)

def make_site_config(db_name=None, db_password=None, site_config=None):
	frappe.create_folder(os.path.join(frappe.local.site_path))
	site_file = get_site_config_path()

	if not os.path.exists(site_file):
		if not (site_config and isinstance(site_config, dict)):
			site_config = get_conf_params(db_name, db_password)

		with open(site_file, "w") as f:
			f.write(json.dumps(site_config, indent=1, sort_keys=True))

def update_site_config(key, value, validate=True, site_config_path=None):
	"""Update a value in site_config"""
	if not site_config_path:
		site_config_path = get_site_config_path()

	with open(site_config_path, "r") as f:
		site_config = json.loads(f.read())

	# In case of non-int value
	if value in ('0', '1'):
		value = int(value)

	# boolean
	if value == 'false': value = False
	if value == 'true': value = True

	# remove key if value is None
	if value == "None":
		if key in site_config:
			del site_config[key]
	else:
		site_config[key] = value

	with open(site_config_path, "w") as f:
		f.write(json.dumps(site_config, indent=1, sort_keys=True))

	if frappe.local.conf:
		frappe.local.conf[key] = value

def get_site_config_path():
	return os.path.join(frappe.local.site_path, "site_config.json")

def get_conf_params(db_name=None, db_password=None):
	if not db_name:
		db_name = raw_input("Database Name: ")
		if not db_name:
			raise Exception("Database Name Required")

	if not db_password:
		from frappe.utils import random_string
		db_password = random_string(16)

	return {"db_name": db_name, "db_password": db_password}

def make_site_dirs():
	site_public_path = os.path.join(frappe.local.site_path, 'public')
	site_private_path = os.path.join(frappe.local.site_path, 'private')
	for dir_path in (
			os.path.join(site_private_path, 'backups'),
			os.path.join(site_public_path, 'files'),
			os.path.join(site_private_path, 'files'),
			os.path.join(frappe.local.site_path, 'task-logs')):
		if not os.path.exists(dir_path):
			os.makedirs(dir_path)
	locks_dir = frappe.get_site_path('locks')
	if not os.path.exists(locks_dir):
			os.makedirs(locks_dir)

def add_module_defs(app):
	modules = frappe.get_module_list(app)
	for module in modules:
		d = frappe.new_doc("Module Def")
		d.app_name = app
		d.module_name = module
		d.save(ignore_permissions=True)

def remove_missing_apps():
	apps = ('frappe_subscription', 'shopping_cart')
	installed_apps = json.loads(frappe.db.get_global("installed_apps") or "[]")
	for app in apps:
		if app in installed_apps:
			try:
				importlib.import_module(app)

			except ImportError:
				installed_apps.remove(app)
				frappe.db.set_global("installed_apps", json.dumps(installed_apps))

def check_if_ready_for_barracuda():
	mariadb_variables = frappe._dict(frappe.db.sql("""show variables"""))
	for key, value in {
			"innodb_file_format": "Barracuda",
			"innodb_file_per_table": "ON",
			"innodb_large_prefix": "ON",
			"character_set_server": "utf8mb4",
			"collation_server": "utf8mb4_unicode_ci"
		}.items():

		if mariadb_variables.get(key) != value:
			site = frappe.local.site
			msg = ("Creation of your site - {x} failed because MariaDB is not properly {sep}"
			       "configured to use the Barracuda storage engine. {sep}"
			       "Please add the settings below to MariaDB's my.cnf, restart MariaDB then {sep}"
			       "run `bench new-site {x}` again.{sep2}"
			       "").format(x=site, sep2="\n"*2, sep="\n")

			print_db_config(msg, expected_config_for_barracuda)
			raise frappe.exceptions.ImproperDBConfigurationError(
				reason="MariaDB default file format is not Barracuda"
			)


def print_db_config(explanation, config_text):
	print("="*80)
	print(explanation)
	print(config_text)
	print("="*80)


def extract_sql_gzip(sql_gz_path):
	try:
		subprocess.check_call(['gzip', '-d', '-v', '-f', sql_gz_path])
	except:
		raise

	return sql_gz_path[:-3]

def extract_tar_files(site_name, file_path, folder_name):
	# Need to do frappe.init to maintain the site locals
	frappe.init(site=site_name)
	abs_site_path = os.path.abspath(frappe.get_site_path())

	# Copy the files to the parent directory and extract
	shutil.copy2(os.path.abspath(file_path), abs_site_path)

	# Get the file name splitting the file path on
	tar_name = os.path.split(file_path)[1]
	tar_path = os.path.join(abs_site_path, tar_name)

	try:
		subprocess.check_output(['tar', 'xvf', tar_path, '--strip', '2'], cwd=abs_site_path)
	except:
		raise
	finally:
		frappe.destroy()

	return tar_path

expected_config_for_barracuda = """[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""
