// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.ui');

frappe.ui.FieldGroup = frappe.ui.form.Layout.extend({
	init: function(opts) {
		$.extend(this, opts);
		this._super();
		$.each(this.fields || [], function(i, f) {
			if(!f.fieldname && f.label) {
				f.fieldname = f.label.replace(/ /g, "_").toLowerCase();
			}
		})
		if(this.values) {
			this.set_values(this.values);
		}
	},
	make: function() {
		var me = this;
		if(this.fields) {
			this._super();
			this.refresh();
			// set default
			$.each(this.fields_list, function(i, field) {
				if(field.df["default"]) {
					field.set_input(field.df["default"]);
				}
			})

			if(!this.no_submit_on_enter) {
				this.catch_enter_as_submit();
			}

			$(this.body).find('input').on('change', function() {
				me.refresh_dependency();
			})

			$(this.body).find('select').on("change", function() {
				me.refresh_dependency();
			})
		}
	},
	add_fields: function(fields) {
		this.render(fields);
		this.refresh_fields(fields);
	},
	refresh_fields: function(fields) {
		let fieldnames = fields.map((field) => {
			if(field.fieldname) return field.fieldname;
		});

		this.fields_list.map(fieldobj => {
			if(fieldnames.includes(fieldobj.df.fieldname)) {
				fieldobj.refresh();
				if(fieldobj.df["default"]) {
					fieldobj.set_input(fieldobj.df["default"]);
				}
			}
		});
	},
	first_button: false,
	catch_enter_as_submit: function() {
		var me = this;
		$(this.body).find('input[type="text"], input[type="password"]').keypress(function(e) {
			if(e.which==13) {
				if(me.has_primary_action) {
					e.preventDefault();
					me.get_primary_btn().trigger("click");
				}
			}
		});
	},
	get_input: function(fieldname) {
		var field = this.fields_dict[fieldname];
		return $(field.txt ? field.txt : field.input);
	},
	get_field: function(fieldname) {
		return this.fields_dict[fieldname];
	},
	get_values: function(ignore_errors) {
		var ret = {};
		var errors = [];
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			if(f.get_value) {
				var v = f.get_value();
				if(f.df.reqd && is_null(v))
					errors.push(__(f.df.label));

				if(!is_null(v)) ret[f.df.fieldname] = v;
			}
		}
		if(errors.length && !ignore_errors) {
			frappe.msgprint({
				title: __('Missing Values Required'),
				message: __('Following fields have missing values:') +
					'<br><br><ul><li>' + errors.join('<li>') + '</ul>',
				indicator: 'orange'
			});
			return null;
		}
		return ret;
	},
	get_value: function(key) {
		var f = this.fields_dict[key];
		return f && (f.get_value ? f.get_value() : null);
	},
	set_value: function(key, val){
		return new Promise(resolve => {
			var f = this.fields_dict[key];
			if(f) {
				f.set_value(val).then(() => {
					f.set_input(val);
					this.refresh_dependency();
					resolve();
				});
			} else {
				resolve();
			}
		});
	},
	set_input: function(key, val) {
		return this.set_value(key, val);
	},
	set_values: function(dict) {
		for(var key in dict) {
			if(this.fields_dict[key]) {
				this.set_value(key, dict[key]);
			}
		}
	},
	clear: function() {
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			if(f && f.set_input) {
				f.set_input(f.df['default'] || '');
			}
		}
	},
});
