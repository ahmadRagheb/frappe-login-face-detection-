# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import urllib
import frappe
from frappe.utils import get_request_site_address, get_datetime, nowdate
from frappe.website.router import get_pages, get_all_page_context_from_doctypes
from six import iteritems
<<<<<<< HEAD
from six.moves.urllib.parse import quote
=======
from six.moves.urllib.parse import quote, urljoin
>>>>>>> 176d241496ede1357a309fa44a037b757a252581

no_cache = 1
no_sitemap = 1
base_template_path = "templates/www/sitemap.xml"

def get_context(context):
	"""generate the sitemap XML"""
	host = get_request_site_address()
	links = []
	for route, page in iteritems(get_pages()):
		if not page.no_sitemap:
			links.append({
<<<<<<< HEAD
				"loc": urllib.basejoin(host, quote(page.name.encode("utf-8"))),
=======
				"loc": urljoin(host, quote(page.name.encode("utf-8"))),
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
				"lastmod": nowdate()
			})

	for route, data in iteritems(get_all_page_context_from_doctypes()):
		links.append({
<<<<<<< HEAD
			"loc": urllib.basejoin(host, quote((route or "").encode("utf-8"))),
=======
			"loc": urljoin(host, quote((route or "").encode("utf-8"))),
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
			"lastmod": get_datetime(data.get("modified")).strftime("%Y-%m-%d")
		})

	return {"links":links}
