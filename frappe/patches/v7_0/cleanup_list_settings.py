import frappe, json

def execute():
	if frappe.db.table_exists("__ListSettings"):	
		list_settings = frappe.db.sql("select user, doctype, data from __ListSettings", as_dict=1)
		for ls in list_settings:
			if ls and ls.data:
				data = json.loads(ls.data)
<<<<<<< HEAD
				if not data.has_key("fields"):
=======
				if "fields" not in data:
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
					continue
				fields = data["fields"]
				for field in fields:
					if "name as" in field:
						fields.remove(field)
				data["fields"] = fields
			
				frappe.db.sql("update __ListSettings set data = %s where user=%s and doctype=%s", 
					(json.dumps(data), ls.user, ls.doctype))					
		
