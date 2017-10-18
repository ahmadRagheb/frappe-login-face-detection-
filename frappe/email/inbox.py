import frappe
import json

def get_email_accounts(user=None):
	if not user:
		user = frappe.session.user

	email_accounts = []

	accounts = frappe.get_all("User Email", filters={ "parent": user },
		fields=["email_account", "email_id", "enable_outgoing"],
		distinct=True, order_by="idx")

	if not accounts:
		return {
			"email_accounts": [],
			"all_accounts": ""
		}

	all_accounts = ",".join([ account.get("email_account") for account in accounts ])
	if len(accounts) > 1:
		email_accounts.append({
			"email_account": all_accounts,
			"email_id": "All Accounts"
		})
	email_accounts.extend(accounts)

	email_accounts.extend([
		{
			"email_account": "Sent",
			"email_id": "Sent Mail"
		},
		{
			"email_account": "Spam",
			"email_id": "Spam"
		},
		{
			"email_account": "Trash",
			"email_id": "Trash"
		}
	])

	return {
		"email_accounts": email_accounts,
		"all_accounts": all_accounts
	}

@frappe.whitelist()
def create_email_flag_queue(names, action, flag="(\\Seen)"):
	""" create email flag queue to mark email either as read or unread """
	class Found(Exception):
		pass

	if not all([names, action, flag]):
		return

	for name in json.loads(names or []):
		uid, seen_status, email_account = frappe.db.get_value("Communication", name, 
			["ifnull(uid, -1)", "ifnull(seen, 0)", "email_account"])

		if not uid or uid == -1:
			continue

		seen = 1 if action == "Read" else 0
		# check if states are correct
		if (action =='Read' and seen_status == 0) or (action =='Unread' and seen_status == 1):
			try:
				queue = frappe.db.sql("""select name, action, flag from `tabEmail Flag Queue`
					where communication = %(name)s""", {"name":name}, as_dict=True)
				for q in queue:
					# is same email with same flag
					if q.flag == flag:
						# to prevent flag local and server states being out of sync
						if q.action != action:
							frappe.delete_doc("Email Flag Queue", q.name)
						raise Found

				flag_queue = frappe.get_doc({
					"uid": uid,
					"flag": flag,
					"action": action,
					"communication": name,
					"doctype": "Email Flag Queue",
					"email_account": email_account
				})
				flag_queue.save(ignore_permissions=True);
				frappe.db.set_value("Communication", name, "seen", seen, 
					update_modified=False)
			except Found:
				pass

@frappe.whitelist()
def mark_as_trash(communication):
	"""set email status to trash"""
	frappe.db.set_value("Communication", communication, "email_status", "Trash")

@frappe.whitelist()
def mark_as_spam(communication, sender):
	""" set email status to spam """
	email_rule = frappe.db.get_value("Email Rule", { "email_id": sender })
	if not email_rule:
		frappe.get_doc({
			"doctype": "Email Rule",
			"email_id": sender,
			"is_spam": 1	
		}).insert(ignore_permissions=True)
	frappe.db.set_value("Communication", communication, "email_status", "Spam")

def link_communication_to_document(doc, reference_doctype, reference_name, ignore_communication_links):
	if not ignore_communication_links:
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.status = "Linked"
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def make_issue_from_communication(communication, ignore_communication_links=False):
	""" raise a issue from email """

	doc = frappe.get_doc("Communication", communication)
	issue = frappe.get_doc({
		"doctype": "Issue",
		"subject": doc.subject,
		"raised_by": doc.sender	
	}).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Issue", issue.name, ignore_communication_links)

	return issue.name

@frappe.whitelist()
def make_lead_from_communication(communication, ignore_communication_links=False):
	""" raise a issue from email """

	doc = frappe.get_doc("Communication", communication)
	frappe.errprint(doc.sender_full_name)
	lead_name = frappe.db.get_value("Lead", {"email_id": doc.sender})
	if not lead_name:
		lead = frappe.get_doc({
			"doctype": "Lead",
			"lead_name": doc.sender_full_name,
			"email_id": doc.sender	
		})
		lead.flags.ignore_mandatory = True
		lead.flags.ignore_permissions = True
		lead.insert()

		lead_name = lead.name

	link_communication_to_document(doc, "Lead", lead_name, ignore_communication_links)
	return lead_name

@frappe.whitelist()
def make_opportunity_from_communication(communication, ignore_communication_links=False):
	doc = frappe.get_doc("Communication", communication)

	lead = doc.reference_name if doc.reference_doctype == "Lead" else None
	if not lead:
		lead = make_lead_from_communication(communication, ignore_communication_links=True)

	enquiry_from = "Lead"

	opportunity = frappe.get_doc({
		"doctype": "Opportunity",
		"enquiry_from": enquiry_from,
		"lead": lead
	}).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Opportunity", opportunity.name, ignore_communication_links)

	return opportunity.name
