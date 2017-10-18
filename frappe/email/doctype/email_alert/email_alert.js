frappe.email_alert = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if(!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			var get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
			}

			var fields = frappe.get_doc("DocType", frm.doc.document_type).fields;

			var options = $.map(fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : get_select_options(d); });

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));

			// set date changed options
			frm.set_df_property("date_changed", "options", $.map(fields,
				function(d) { return (d.fieldtype=="Date" || d.fieldtype=="Datetime") ?
					get_select_options(d) : null; }));

			var email_fields = $.map(fields,
				function(d) { return (d.options == "Email" ||
					(d.options=='User' && d.fieldtype=='Link')) ?
					get_select_options(d) : null; });

			// set email recipient options
			frappe.meta.get_docfield("Email Alert Recipient", "email_by_document_field",
				// set first option as blank to allow email alert not to be defaulted to the owner
				frm.doc.name).options = [""].concat(["owner"].concat(email_fields));

			frm.fields_dict.recipients.grid.refresh();
		});
	}
}

frappe.ui.form.on("Email Alert", {
	onload: function(frm) {
		frm.set_query("document_type", function() {
			return {
				"filters": {
					"istable": 0
				}
			}
		})
	},
	refresh: function(frm) {
		frappe.email_alert.setup_fieldname_select(frm);
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.trigger('event');
	},
	document_type: function(frm) {
		frappe.email_alert.setup_fieldname_select(frm);
	},
	view_properties: function(frm) {
		frappe.route_options = {doc_type:frm.doc.document_type};
		frappe.set_route("Form", "Customize Form");
	},
	event: function(frm) {
		if(in_list(['Days Before', 'Days After'], frm.doc.event)) {
			frm.add_custom_button(__('Get Alerts for Today'), function() {
				frappe.call({
					method: 'frappe.email.doctype.email_alert.email_alert.get_documents_for_today',
					args: {
						email_alert: frm.doc.name
					},
					callback: function(r) {
						if(r.message) {
							frappe.msgprint(r.message);
						} else {
							frappe.msgprint(__('No alerts for today'));
						}
					}
				});
			});
		}
	}
});
