# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt, cstr, fmt_money
import unittest

class TestFmtMoney(unittest.TestCase):
	def test_standard(self):
		frappe.db.set_default("number_format", "#,###.##")
		self.assertEquals(fmt_money(100), "100.00")
		self.assertEquals(fmt_money(1000), "1,000.00")
		self.assertEquals(fmt_money(10000), "10,000.00")
		self.assertEquals(fmt_money(100000), "100,000.00")
		self.assertEquals(fmt_money(1000000), "1,000,000.00")
		self.assertEquals(fmt_money(10000000), "10,000,000.00")
		self.assertEquals(fmt_money(100000000), "100,000,000.00")
		self.assertEquals(fmt_money(1000000000), "1,000,000,000.00")

	def test_negative(self):
		frappe.db.set_default("number_format", "#,###.##")
		self.assertEquals(fmt_money(-100), "-100.00")
		self.assertEquals(fmt_money(-1000), "-1,000.00")
		self.assertEquals(fmt_money(-10000), "-10,000.00")
		self.assertEquals(fmt_money(-100000), "-100,000.00")
		self.assertEquals(fmt_money(-1000000), "-1,000,000.00")
		self.assertEquals(fmt_money(-10000000), "-10,000,000.00")
		self.assertEquals(fmt_money(-100000000), "-100,000,000.00")
		self.assertEquals(fmt_money(-1000000000), "-1,000,000,000.00")

	def test_decimal(self):
		frappe.db.set_default("number_format", "#.###,##")
		self.assertEquals(fmt_money(-100), "-100,00")
		self.assertEquals(fmt_money(-1000), "-1.000,00")
		self.assertEquals(fmt_money(-10000), "-10.000,00")
		self.assertEquals(fmt_money(-100000), "-100.000,00")
		self.assertEquals(fmt_money(-1000000), "-1.000.000,00")
		self.assertEquals(fmt_money(-10000000), "-10.000.000,00")
		self.assertEquals(fmt_money(-100000000), "-100.000.000,00")
		self.assertEquals(fmt_money(-1000000000), "-1.000.000.000,00")


	def test_lacs(self):
		frappe.db.set_default("number_format", "#,##,###.##")
		self.assertEquals(fmt_money(100), "100.00")
		self.assertEquals(fmt_money(1000), "1,000.00")
		self.assertEquals(fmt_money(10000), "10,000.00")
		self.assertEquals(fmt_money(100000), "1,00,000.00")
		self.assertEquals(fmt_money(1000000), "10,00,000.00")
		self.assertEquals(fmt_money(10000000), "1,00,00,000.00")
		self.assertEquals(fmt_money(100000000), "10,00,00,000.00")
		self.assertEquals(fmt_money(1000000000), "1,00,00,00,000.00")

	def test_no_precision(self):
		frappe.db.set_default("number_format", "#,###")
		self.assertEquals(fmt_money(0.3), "0")
		self.assertEquals(fmt_money(100.3), "100")
		self.assertEquals(fmt_money(1000.3), "1,000")
		self.assertEquals(fmt_money(10000.3), "10,000")
		self.assertEquals(fmt_money(-0.3), "0")
		self.assertEquals(fmt_money(-100.3), "-100")
		self.assertEquals(fmt_money(-1000.3), "-1,000")

	def test_currency_precision(self):
		frappe.db.set_default("currency_precision", "4")
		frappe.db.set_default("number_format", "#,###.##")
		self.assertEquals(fmt_money(100), "100.00")
		self.assertEquals(fmt_money(1000), "1,000.00")
		self.assertEquals(fmt_money(10000), "10,000.00")
		self.assertEquals(fmt_money(100000), "100,000.00")
		self.assertEquals(fmt_money(1000000), "1,000,000.00")
		self.assertEquals(fmt_money(10000000), "10,000,000.00")
		self.assertEquals(fmt_money(100000000), "100,000,000.00")
		self.assertEquals(fmt_money(1000000000), "1,000,000,000.00")
		self.assertEquals(fmt_money(100.23), "100.23")
		self.assertEquals(fmt_money(1000.456), "1,000.456")
		self.assertEquals(fmt_money(10000.7890), "10,000.789")
		self.assertEquals(fmt_money(100000.1234), "100,000.1234")
		self.assertEquals(fmt_money(1000000.3456), "1,000,000.3456")
		self.assertEquals(fmt_money(10000000.3344567), "10,000,000.3345")
		self.assertEquals(fmt_money(100000000.37827268), "100,000,000.378")
		self.assertEquals(fmt_money(1000000000.2718272637), "1,000,000,000.27")
		frappe.db.set_default("currency_precision", "")

if __name__=="__main__":
	frappe.connect()
	unittest.main()