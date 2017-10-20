# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe
from frappe.model.document import Document
from frappe.utils import cint, has_gravatar, format_datetime, now_datetime, get_formatted_email
from frappe import throw, msgprint, _
from frappe.utils.password import update_password as _update_password
from frappe.desk.notifications import clear_notifications
from frappe.utils.user import get_system_managers
import frappe.permissions
import frappe.share
import re
from frappe.limits import get_limits
from frappe.website.utils import is_signup_enabled
from frappe.utils.background_jobs import enqueue

STANDARD_USERS = ("Guest", "Administrator")

class MaxUsersReachedError(frappe.ValidationError): pass

class User(Document):
	__new_password = None

	def __setup__(self):
		# because it is handled separately
		self.flags.ignore_save_passwords = True

	def autoname(self):
		"""set name as Email Address"""
		if self.get("is_admin") or self.get("is_guest"):
			self.name = self.first_name
		else:
			self.email = self.email.strip()
			self.name = self.email

	def onload(self):
		self.set_onload('all_modules',
			[m.module_name for m in frappe.db.get_all('Desktop Icon',
				fields=['module_name'], filters={'standard': 1}, order_by="module_name")])

	def before_insert(self):
		self.flags.in_insert = True

	def validate(self):
		self.check_demo()

		# clear new password
		self.__new_password = self.new_password
		self.new_password = ""

		if not frappe.flags.in_test:
			self.password_strength_test()

		if self.name not in STANDARD_USERS:
			self.validate_email_type(self.email)
			self.validate_email_type(self.name)
		self.add_system_manager_role()
		self.set_system_user()
		self.set_full_name()
		self.check_enable_disable()
		self.ensure_unique_roles()
		self.remove_all_roles_for_guest()
		self.validate_username()
		self.remove_disabled_roles()
		self.validate_user_email_inbox()
		ask_pass_update()

		if self.language == "Loading...":
			self.language = None

		if (self.name not in ["Administrator", "Guest"]) and (not self.frappe_userid):
			self.frappe_userid = frappe.generate_hash(length=39)

	def on_update(self):
		# clear new password
		self.validate_user_limit()
		self.share_with_self()
		clear_notifications(user=self.name)
		frappe.clear_cache(user=self.name)
		self.send_password_notification(self.__new_password)
		if self.name not in ('Administrator', 'Guest') and not self.user_image:
			frappe.enqueue('frappe.core.doctype.user.user.update_gravatar', name=self.name)

	def has_website_permission(self, ptype, verbose=False):
		"""Returns true if current user is the session user"""
		return self.name == frappe.session.user

	def check_demo(self):
		if frappe.session.user == 'demo@erpnext.com':
			frappe.throw(_('Cannot change user details in demo. Please signup for a new account at https://erpnext.com'), title=_('Not Allowed'))

	def set_full_name(self):
		self.full_name = " ".join(filter(None, [self.first_name, self.last_name]))

	def check_enable_disable(self):
		# do not allow disabling administrator/guest
		if not cint(self.enabled) and self.name in STANDARD_USERS:
			frappe.throw(_("User {0} cannot be disabled").format(self.name))

		if not cint(self.enabled):
			self.a_system_manager_should_exist()

		# clear sessions if disabled
		if not cint(self.enabled) and getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

	def add_system_manager_role(self):
		# if adding system manager, do nothing
		if not cint(self.enabled) or ("System Manager" in [user_role.role for user_role in
				self.get("roles")]):
			return

		if self.name not in STANDARD_USERS and self.user_type == "System User" and not self.get_other_system_managers():
			msgprint(_("Adding System Manager to this User as there must be atleast one System Manager"))
			self.append("roles", {
				"doctype": "Has Role",
				"role": "System Manager"
			})

		if self.name == 'Administrator':
			# Administrator should always have System Manager Role
			self.extend("roles", [
				{
					"doctype": "Has Role",
					"role": "System Manager"
				},
				{
					"doctype": "Has Role",
					"role": "Administrator"
				}
			])

	def email_new_password(self, new_password=None):
		if new_password and not self.flags.in_insert:
			_update_password(self.name, new_password)

			if self.send_password_update_notification:
				self.password_update_mail(new_password)
				frappe.msgprint(_("New password emailed"))

	def set_system_user(self):
		'''Set as System User if any of the given roles has desk_access'''
		if self.has_desk_access() or self.name == 'Administrator':
			self.user_type = 'System User'
		else:
			self.user_type = 'Website User'

	def has_desk_access(self):
		'''Return true if any of the set roles has desk access'''
		if not self.roles:
			return False

		return len(frappe.db.sql("""select name
			from `tabRole` where desk_access=1
				and name in ({0}) limit 1""".format(', '.join(['%s'] * len(self.roles))),
				[d.role for d in self.roles]))


	def share_with_self(self):
		if self.user_type=="System User":
			frappe.share.add(self.doctype, self.name, self.name, write=1, share=1,
				flags={"ignore_share_permission": True})
		else:
			frappe.share.remove(self.doctype, self.name, self.name,
				flags={"ignore_share_permission": True, "ignore_permissions": True})

	def validate_share(self, docshare):
		if docshare.user == self.name:
			if self.user_type=="System User":
				if docshare.share != 1:
					frappe.throw(_("Sorry! User should have complete access to their own record."))
			else:
				frappe.throw(_("Sorry! Sharing with Website User is prohibited."))

	def send_password_notification(self, new_password):
		try:
			if self.flags.in_insert:
				if self.name not in STANDARD_USERS:
					if new_password:
						# new password given, no email required
						_update_password(self.name, new_password)

					if not self.flags.no_welcome_mail and self.send_welcome_email:
						self.send_welcome_mail_to_user()
						self.flags.email_sent = 1
						if frappe.session.user != 'Guest':
							msgprint(_("Welcome email sent"))
						return
			else:
				self.email_new_password(new_password)

		except frappe.OutgoingEmailError:
			print(frappe.get_traceback())
			pass # email server not set, don't send email

	@Document.hook
	def validate_reset_password(self):
		pass

	def reset_password(self, send_email=False):
		from frappe.utils import random_string, get_url

		key = random_string(32)
		self.db_set("reset_password_key", key)
		link = get_url("/update-password?key=" + key)

		if send_email:
			self.password_reset_mail(link)

		return link

	def get_other_system_managers(self):
		return frappe.db.sql("""select distinct user.name from `tabHas Role` user_role, tabUser user
			where user_role.role='System Manager'
				and user.docstatus<2
				and user.enabled=1
				and user_role.parent = user.name
			and user_role.parent not in ('Administrator', %s) limit 1""", (self.name,))

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.first_name or '') + \
			(self.first_name and " " or '') + (self.last_name or '')

	def password_reset_mail(self, link):
		self.send_login_mail(_("Password Reset"),
			"password_reset", {"link": link}, now=True)

	def password_update_mail(self, password):
		self.send_login_mail(_("Password Update"),
			"password_update", {"new_password": password}, now=True)

	def send_welcome_mail_to_user(self):
		from frappe.utils import get_url

		link = self.reset_password()
		app_title = None

		method = frappe.get_hooks('get_site_info')
		if method:
			get_site_info = frappe.get_attr(method[0])
			site_info = get_site_info({})
			app_title = site_info.get('company', None)

		if app_title:
			subject = _("Welcome to {0}").format(app_title)
		else:
			subject = _("Complete Registration")

		self.send_login_mail(subject, "new_user",
				dict(
					link=link,
					site_url=get_url(),
				))

	def send_login_mail(self, subject, template, add_args, now=None):
		"""send mail with login details"""
		from frappe.utils.user import get_user_fullname
		from frappe.utils import get_url

		mail_titles = frappe.get_hooks().get("login_mail_title", [])
		title = frappe.db.get_default('company') or (mail_titles and mail_titles[0]) or ""

		full_name = get_user_fullname(frappe.session['user'])
		if full_name == "Guest":
			full_name = "Administrator"

		args = {
			'first_name': self.first_name or self.last_name or "user",
			'user': self.name,
			'title': title,
			'login_url': get_url(),
			'user_fullname': full_name
		}

		args.update(add_args)

		sender = frappe.session.user not in STANDARD_USERS and get_formatted_email(frappe.session.user) or None

		frappe.sendmail(recipients=self.email, sender=sender, subject=subject,
			template=template, args=args, header=[subject, "green"],
			delayed=(not now) if now!=None else self.flags.delay_emails, retry=3)

	def a_system_manager_should_exist(self):
		if not self.get_other_system_managers():
			throw(_("There should remain at least one System Manager"))

	def on_trash(self):
		frappe.clear_cache(user=self.name)
		if self.name in STANDARD_USERS:
			throw(_("User {0} cannot be deleted").format(self.name))

		self.a_system_manager_should_exist()

		# disable the user and log him/her out
		self.enabled = 0
		if getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

		# delete todos
		frappe.db.sql("""delete from `tabToDo` where owner=%s""", (self.name,))
		frappe.db.sql("""update tabToDo set assigned_by=null where assigned_by=%s""",
			(self.name,))

		# delete events
		frappe.db.sql("""delete from `tabEvent` where owner=%s
			and event_type='Private'""", (self.name,))

		# delete shares
		frappe.db.sql("""delete from `tabDocShare` where user=%s""", self.name)

		# delete messages
		frappe.db.sql("""delete from `tabCommunication`
			where communication_type in ('Chat', 'Notification')
			and reference_doctype='User'
			and (reference_name=%s or owner=%s)""", (self.name, self.name))

	def before_rename(self, old_name, new_name, merge=False):
		self.check_demo()
		frappe.clear_cache(user=old_name)
		self.validate_rename(old_name, new_name)

	def validate_rename(self, old_name, new_name):
		# do not allow renaming administrator and guest
		if old_name in STANDARD_USERS:
			throw(_("User {0} cannot be renamed").format(self.name))

		self.validate_email_type(new_name)

	def validate_email_type(self, email):
		from frappe.utils import validate_email_add
		validate_email_add(email.strip(), True)

	def after_rename(self, old_name, new_name, merge=False):
		tables = frappe.db.sql("show tables")
		for tab in tables:
			desc = frappe.db.sql("desc `%s`" % tab[0], as_dict=1)
			has_fields = []
			for d in desc:
				if d.get('Field') in ['owner', 'modified_by']:
					has_fields.append(d.get('Field'))
			for field in has_fields:
				frappe.db.sql("""\
					update `%s` set `%s`=%s
					where `%s`=%s""" % \
					(tab[0], field, '%s', field, '%s'), (new_name, old_name))

		# set email
		frappe.db.sql("""\
			update `tabUser` set email=%s
			where name=%s""", (new_name, new_name))

	def append_roles(self, *roles):
		"""Add roles to user"""
		current_roles = [d.role for d in self.get("roles")]
		for role in roles:
			if role in current_roles:
				continue
			self.append("roles", {"role": role})

	def add_roles(self, *roles):
		"""Add roles to user and save"""
		self.append_roles(*roles)
		self.save()

	def remove_roles(self, *roles):
		existing_roles = dict((d.role, d) for d in self.get("roles"))
		for role in roles:
			if role in existing_roles:
				self.get("roles").remove(existing_roles[role])

		self.save()

	def remove_all_roles_for_guest(self):
		if self.name == "Guest":
			self.set("roles", list(set(d for d in self.get("roles") if d.role == "Guest")))

	def remove_disabled_roles(self):
		disabled_roles = [d.name for d in frappe.get_all("Role", filters={"disabled":1})]
		for role in list(self.get('roles')):
			if role.role in disabled_roles:
				self.get('roles').remove(role)

	def ensure_unique_roles(self):
		exists = []
		for i, d in enumerate(self.get("roles")):
			if (not d.role) or (d.role in exists):
				self.get("roles").remove(d)
			else:
				exists.append(d.role)

	def validate_username(self):
		if not self.username and self.is_new() and self.first_name:
			self.username = frappe.scrub(self.first_name)

		if not self.username:
			return

		# strip space and @
		self.username = self.username.strip(" @")

		if self.username_exists():
			if self.user_type == 'System User':
				frappe.msgprint(_("Username {0} already exists").format(self.username))
				self.suggest_username()

			self.username = ""

	def password_strength_test(self):
		""" test password strength """
		if self.__new_password:
			user_data = (self.first_name, self.middle_name, self.last_name, self.email, self.birth_date)
			result = test_password_strength(self.__new_password, '', None, user_data)
			feedback = result.get("feedback", None)

			if feedback and not feedback.get('password_policy_validation_passed', False):
				handle_password_test_fail(result)

	def suggest_username(self):
		def _check_suggestion(suggestion):
			if self.username != suggestion and not self.username_exists(suggestion):
				return suggestion

			return None

		# @firstname
		username = _check_suggestion(frappe.scrub(self.first_name))

		if not username:
			# @firstname_last_name
			username = _check_suggestion(frappe.scrub("{0} {1}".format(self.first_name, self.last_name or "")))

		if username:
			frappe.msgprint(_("Suggested Username: {0}").format(username))

		return username

	def username_exists(self, username=None):
		return frappe.db.get_value("User", {"username": username or self.username, "name": ("!=", self.name)})

	def get_blocked_modules(self):
		"""Returns list of modules blocked for that user"""
		return [d.module for d in self.block_modules] if self.block_modules else []

	def validate_user_limit(self):
		'''
			Validate if user limit has been reached for System Users
			Checked in 'Validate' event as we don't want welcome email sent if max users are exceeded.
		'''

		if self.user_type == "Website User":
			return

		if not self.enabled:
			# don't validate max users when saving a disabled user
			return

		limits = get_limits()
		if not limits.users:
			# no limits defined
			return

		total_users = get_total_users()
		if self.is_new():
			# get_total_users gets existing users in database
			# a new record isn't inserted yet, so adding 1
			total_users += 1

		if total_users > limits.users:
			frappe.throw(_("Sorry. You have reached the maximum user limit for your subscription. You can either disable an existing user or buy a higher subscription plan."),
				MaxUsersReachedError)

	def validate_user_email_inbox(self):
		""" check if same email account added in User Emails twice """

		email_accounts = [ user_email.email_account for user_email in self.user_emails ]
		if len(email_accounts) != len(set(email_accounts)):
			frappe.throw(_("Email Account added multiple times"))

@frappe.whitelist()
def get_timezones():
	import pytz
	return {
		"timezones": pytz.all_timezones
	}

@frappe.whitelist()
def get_all_roles(arg=None):
	"""return all roles"""
	active_domains = frappe.get_active_domains()

	roles = frappe.get_all("Role", filters={
		"name": ("not in", "Administrator,Guest,All"),
		"disabled": 0
	}, or_filters={
		"ifnull(restrict_to_domain, '')": "",
		"restrict_to_domain": ("in", active_domains)
	}, order_by="name")

	return [ role.get("name") for role in roles ]

@frappe.whitelist()
def get_roles(arg=None):
	"""get roles for a user"""
	return frappe.get_roles(frappe.form_dict['uid'])

@frappe.whitelist()
def get_perm_info(role):
	"""get permission info"""
	from frappe.permissions import get_all_perms
	return get_all_perms(role)

@frappe.whitelist(allow_guest=True)
def update_password(new_password, key=None, old_password=None):
	result = test_password_strength(new_password, key, old_password)
	feedback = result.get("feedback", None)

	if feedback and not feedback.get('password_policy_validation_passed', False):
		handle_password_test_fail(result)

	res = _get_user_for_update_password(key, old_password)
	if res.get('message'):
		return res['message']
	else:
		user = res['user']

	_update_password(user, new_password)

	user_doc, redirect_url = reset_user_data(user)

	# get redirect url from cache
	redirect_to = frappe.cache().hget('redirect_after_login', user)
	if redirect_to:
		redirect_url = redirect_to
		frappe.cache().hdel('redirect_after_login', user)


	frappe.local.login_manager.login_as(user)

	if user_doc.user_type == "System User":
		return "/desk"
	else:
		return redirect_url if redirect_url else "/"

@frappe.whitelist(allow_guest=True)
def test_password_strength(new_password, key=None, old_password=None, user_data=[]):
	from frappe.utils.password_strength import test_password_strength as _test_password_strength

	password_policy = frappe.db.get_value("System Settings", None,
		["enable_password_policy", "minimum_password_score"], as_dict=True) or {}

	enable_password_policy = cint(password_policy.get("enable_password_policy", 0))
	minimum_password_score = cint(password_policy.get("minimum_password_score", 0))

	if not enable_password_policy:
		return {}

	if not user_data:
		user_data = frappe.db.get_value('User', frappe.session.user,
			['first_name', 'middle_name', 'last_name', 'email', 'birth_date'])

	if new_password:
		result = _test_password_strength(new_password, user_inputs=user_data)
		password_policy_validation_passed = False

		# score should be greater than 0 and minimum_password_score
		if result.get('score') and result.get('score') >= minimum_password_score:
			password_policy_validation_passed = True

		result['feedback']['password_policy_validation_passed'] = password_policy_validation_passed
		return result

#for login
@frappe.whitelist()
def has_email_account(email):
	return frappe.get_list("Email Account", filters={"email_id": email})

@frappe.whitelist(allow_guest=False)
def get_email_awaiting(user):
	waiting = frappe.db.sql("""select email_account,email_id
		from `tabUser Email`
		where awaiting_password = 1
		and parent = %(user)s""", {"user":user}, as_dict=1)
	if waiting:
		return waiting
	else:
		frappe.db.sql("""update `tabUser Email`
				set awaiting_password =0
				where parent = %(user)s""",{"user":user})
		return False

@frappe.whitelist(allow_guest=False)
def set_email_password(email_account, user, password):
	account = frappe.get_doc("Email Account", email_account)
	if account.awaiting_password:
		account.awaiting_password = 0
		account.password = password
		try:
			account.save(ignore_permissions=True)
		except Exception:
			frappe.db.rollback()
			return False

	return True

def setup_user_email_inbox(email_account, awaiting_password, email_id, enable_outgoing):
	""" setup email inbox for user """
	def add_user_email(user):
		user = frappe.get_doc("User", user)
		row = user.append("user_emails", {})

		row.email_id = email_id
		row.email_account = email_account
		row.awaiting_password = awaiting_password or 0
		row.enable_outgoing = enable_outgoing or 0

		user.save(ignore_permissions=True)

	udpate_user_email_settings = False
	if not all([email_account, email_id]):
		return

	user_names = frappe.db.get_values("User", { "email": email_id }, as_dict=True)
	if not user_names:
		return

	for user in user_names:
		user_name = user.get("name")

		# check if inbox is alreay configured
		user_inbox = frappe.db.get_value("User Email", {
			"email_account": email_account,
			"parent": user_name
		}, ["name"]) or None

		if not user_inbox:
			add_user_email(user_name)
		else:
			# update awaiting password for email account
			udpate_user_email_settings = True

	if udpate_user_email_settings:
		frappe.db.sql("""UPDATE `tabUser Email` SET awaiting_password = %(awaiting_password)s,
			enable_outgoing = %(enable_outgoing)s WHERE email_account = %(email_account)s""", {
				"email_account": email_account,
				"enable_outgoing": enable_outgoing,
				"awaiting_password": awaiting_password or 0
			})
	else:
		frappe.msgprint(_("Enabled email inbox for user {users}".format(
			users=" and ".join([frappe.bold(user.get("name")) for user in user_names])
		)))

	ask_pass_update()

def remove_user_email_inbox(email_account):
	""" remove user email inbox settings if email account is deleted """
	if not email_account:
		return

	users = frappe.get_all("User Email", filters={
		"email_account": email_account
	}, fields=["parent as name"])

	for user in users:
		doc = frappe.get_doc("User", user.get("name"))
		to_remove = [ row for row in doc.user_emails if row.email_account == email_account ]
		[ doc.remove(row) for row in to_remove ]

		doc.save(ignore_permissions=True)

def ask_pass_update():
	# update the sys defaults as to awaiting users
	from frappe.utils import set_default

	users = frappe.db.sql("""SELECT DISTINCT(parent) as user FROM `tabUser Email`
		WHERE awaiting_password = 1""", as_dict=True)

	password_list = [ user.get("user") for user in users ]
	set_default("email_user_password", u','.join(password_list))

def _get_user_for_update_password(key, old_password):
	# verify old password
	if key:
		user = frappe.db.get_value("User", {"reset_password_key": key})
		if not user:
			return {
				'message': _("Cannot Update: Incorrect / Expired Link.")
			}

	elif old_password:
		# verify old password
		frappe.local.login_manager.check_password(frappe.session.user, old_password)
		user = frappe.session.user

	else:
		return

	return {
		'user': user
	}

def reset_user_data(user):
	user_doc = frappe.get_doc("User", user)
	redirect_url = user_doc.redirect_url
	user_doc.reset_password_key = ''
	user_doc.redirect_url = ''
	user_doc.save(ignore_permissions=True)

	return user_doc, redirect_url

@frappe.whitelist()
def verify_password(password):
	frappe.local.login_manager.check_password(frappe.session.user, password)

@frappe.whitelist(allow_guest=True)
def sign_up(email, full_name, redirect_to):
	if not is_signup_enabled():
		frappe.throw(_('Sign Up is disabled'), title='Not Allowed')

	user = frappe.db.get("User", {"email": email})
	if user:
		if user.disabled:
			return 0, _("Registered but disabled")
		else:
			return 0, _("Already Registered")
	else:
		if frappe.db.sql("""select count(*) from tabUser where
			HOUR(TIMEDIFF(CURRENT_TIMESTAMP, TIMESTAMP(modified)))=1""")[0][0] > 300:

			frappe.respond_as_web_page(_('Temperorily Disabled'),
				_('Too many users signed up recently, so the registration is disabled. Please try back in an hour'),
				http_status_code=429)

		from frappe.utils import random_string
		user = frappe.get_doc({
			"doctype":"User",
			"email": email,
			"first_name": full_name,
			"enabled": 1,
			"new_password": random_string(10),
			"user_type": "Website User"
		})
		user.flags.ignore_permissions = True
		user.insert()

		if redirect_to:
			frappe.cache().hset('redirect_after_login', user.name, redirect_to)

		if user.flags.email_sent:
			return 1, _("Please check your email for verification")
		else:
			return 2, _("Please ask your administrator to verify your sign-up")

@frappe.whitelist(allow_guest=True)
def reset_password(user):
	if user=="Administrator":
		return 'not allowed'

	try:
		user = frappe.get_doc("User", user)
		user.validate_reset_password()
		user.reset_password(send_email=True)

		return frappe.msgprint(_("Password reset instructions have been sent to your email"))

	except frappe.DoesNotExistError:
		frappe.clear_messages()
		return 'not found'

def user_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond

	user_type_condition = "and user_type = 'System User'"
	if filters and filters.get('ignore_user_type'):
		user_type_condition = ''

	txt = "%{}%".format(txt)
	return frappe.db.sql("""select name, concat_ws(' ', first_name, middle_name, last_name)
		from `tabUser`
		where enabled=1
			{user_type_condition}
			and docstatus < 2
			and name not in ({standard_users})
			and ({key} like %(txt)s
				or concat_ws(' ', first_name, middle_name, last_name) like %(txt)s)
			{mcond}
		order by
			case when name like %(txt)s then 0 else 1 end,
			case when concat_ws(' ', first_name, middle_name, last_name) like %(txt)s
				then 0 else 1 end,
			name asc
		limit %(start)s, %(page_len)s""".format(
			user_type_condition = user_type_condition,
			standard_users=", ".join(["'{0}'".format(frappe.db.escape(u)) for u in STANDARD_USERS]),
			key=searchfield, mcond=get_match_cond(doctype)),
			dict(start=start, page_len=page_len, txt=txt))

def get_total_users():
	"""Returns total no. of system users"""
	return frappe.db.sql('''select sum(simultaneous_sessions) from `tabUser`
		where enabled=1 and user_type="System User"
		and name not in ({})'''.format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

def get_system_users(exclude_users=None, limit=None):
	if not exclude_users:
		exclude_users = []
	elif not isinstance(exclude_users, (list, tuple)):
		exclude_users = [exclude_users]

	limit_cond = ''
	if limit:
		limit_cond = 'limit {0}'.format(limit)

	exclude_users += list(STANDARD_USERS)

	system_users = frappe.db.sql_list("""select name from `tabUser`
		where enabled=1 and user_type != 'Website User'
		and name not in ({}) {}""".format(", ".join(["%s"]*len(exclude_users)), limit_cond),
		exclude_users)

	return system_users

def get_active_users():
	"""Returns No. of system users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type != 'Website User'
		and name not in ({})
		and hour(timediff(now(), last_active)) < 72""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS)[0][0]

def get_website_users():
	"""Returns total no. of website users"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'""")[0][0]

def get_active_website_users():
	"""Returns No. of website users who logged in, in the last 3 days"""
	return frappe.db.sql("""select count(*) from `tabUser`
		where enabled = 1 and user_type = 'Website User'
		and hour(timediff(now(), last_active)) < 72""")[0][0]

def get_permission_query_conditions(user):
	if user=="Administrator":
		return ""

	else:
		return """(`tabUser`.name not in ({standard_users}))""".format(
			standard_users='"' + '", "'.join(STANDARD_USERS) + '"')

def has_permission(doc, user):
	if (user != "Administrator") and (doc.name in STANDARD_USERS):
		# dont allow non Administrator user to view / edit Administrator user
		return False

def notify_admin_access_to_system_manager(login_manager=None):
	if (login_manager
		and login_manager.user == "Administrator"
		and frappe.local.conf.notify_admin_access_to_system_manager):

		site = '<a href="{0}" target="_blank">{0}</a>'.format(frappe.local.request.host_url)
		date_and_time = '<b>{0}</b>'.format(format_datetime(now_datetime(), format_string="medium"))
		ip_address = frappe.local.request_ip

		access_message = _('Administrator accessed {0} on {1} via IP Address {2}.').format(
			site, date_and_time, ip_address)

		frappe.sendmail(
			recipients=get_system_managers(),
			subject=_("Administrator Logged In"),
			template="administrator_logged_in",
			args={'access_message': access_message},
			header=['Access Notification', 'orange']
		)

def extract_mentions(txt):
	"""Find all instances of @username in the string.
	The mentions will be separated by non-word characters or may appear at the start of the string"""
	return re.findall(r'(?:[^\w]|^)@([\w]*)', txt)


def handle_password_test_fail(result):
	suggestions = result['feedback']['suggestions'][0] if result['feedback']['suggestions'] else ''
	warning = result['feedback']['warning'] if 'warning' in result['feedback'] else ''
	suggestions += "<br>" + _("Hint: Include symbols, numbers and capital letters in the password") + '<br>'
	frappe.throw(_('Invalid Password: ' + ' '.join([warning, suggestions])))

def update_gravatar(name):
	gravatar = has_gravatar(name)
	if gravatar:
		frappe.db.set_value('User', name, 'user_image', gravatar)

@frappe.whitelist(allow_guest=True)
def send_token_via_sms(tmp_id,phone_no=None,user=None):
	try:
		from frappe.core.doctype.sms_settings.sms_settings import send_request
	except:
		return False

	if not frappe.cache().ttl(tmp_id + '_token'):
		return False
	ss = frappe.get_doc('SMS Settings', 'SMS Settings')
	if not ss.sms_gateway_url:
		return False

	token = frappe.cache().get(tmp_id + '_token')
	args = {ss.message_parameter: 'verification code is {}'.format(token)}

	for d in ss.get("parameters"):
		args[d.parameter] = d.value

	if user:
		user_phone = frappe.db.get_value('User', user, ['phone','mobile_no'], as_dict=1)
		usr_phone = user_phone.mobile_no or user_phone.phone
		if not usr_phone:
			return False
	else:
		if phone_no:
			usr_phone = phone_no
		else:
			return False

	args[ss.receiver_parameter] = usr_phone
	status = send_request(ss.sms_gateway_url, args)

	if 200 <= status < 300:
		frappe.cache().delete(tmp_id + '_token')
		return True
	else:
		return False

@frappe.whitelist(allow_guest=True)
def send_token_via_email(tmp_id,token=None):
	import pyotp

	user = frappe.cache().get(tmp_id + '_user')
	count = token or frappe.cache().get(tmp_id + '_token')

	if ((not user) or (user == 'None') or (not count)):
		return False
	user_email = frappe.db.get_value('User',user, 'email')
	if not user_email:
		return False

	otpsecret = frappe.cache().get(tmp_id + '_otp_secret')
	hotp = pyotp.HOTP(otpsecret)

	frappe.sendmail(
		recipients=user_email, sender=None, subject='Verification Code',
		message='<p>Your verification code is {0}</p>'.format(hotp.at(int(count))),
		delayed=False, retry=3)

	return True

@frappe.whitelist(allow_guest=True)
def reset_otp_secret(user):
	otp_issuer = frappe.db.get_value('System Settings', 'System Settings', 'otp_issuer_name')
	user_email = frappe.db.get_value('User',user, 'email')
	if frappe.session.user in ["Administrator", user] :
		frappe.defaults.clear_default(user + '_otplogin')
		frappe.defaults.clear_default(user + '_otpsecret')
		email_args = {
			'recipients':user_email, 'sender':None, 'subject':'OTP Secret Reset - {}'.format(otp_issuer or "Frappe Framework"),
			'message':'<p>Your OTP secret on {} has been reset. If you did not perform this reset and did not request it, please contact your System Administrator immediately.</p>'.format(otp_issuer or "Frappe Framework"),
			'delayed':False,
			'retry':3
		}
		enqueue(method=frappe.sendmail, queue='short', timeout=300, event=None, async=True, job_name=None, now=False, **email_args)
		return frappe.msgprint(_("OTP Secret has been reset. Re-registration will be required on next login."))
	else:
		return frappe.throw(_("OTP secret can only be reset by the Administrator."))