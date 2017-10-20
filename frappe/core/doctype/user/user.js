frappe.ui.form.on('User', {
	before_load: function(frm) {
		var update_tz_select = function(user_language) {
			frm.set_df_property("time_zone", "options", [""].concat(frappe.all_timezones));
		}

		if(!frappe.all_timezones) {
			frappe.call({
				method: "frappe.core.doctype.user.user.get_timezones",
				callback: function(r) {
					frappe.all_timezones = r.message.timezones;
					update_tz_select();
				}
			});
		} else {
			update_tz_select();
		}

	},
	onload: function(frm) {
		if(has_common(frappe.user_roles, ["Administrator", "System Manager"]) && !frm.doc.__islocal) {
			if(!frm.roles_editor) {
				var role_area = $('<div style="min-height: 300px">')
					.appendTo(frm.fields_dict.roles_html.wrapper);
				frm.roles_editor = new frappe.RoleEditor(role_area, frm);

				var module_area = $('<div style="min-height: 300px">')
					.appendTo(frm.fields_dict.modules_html.wrapper);
				frm.module_editor = new frappe.ModuleEditor(frm, module_area)
			} else {
				frm.roles_editor.show();
			}
		}
	},
	refresh: function(frm) {
		var doc = frm.doc;

		if(doc.name===frappe.session.user && !doc.__unsaved
			&& frappe.all_timezones
			&& (doc.language || frappe.boot.user.language)
			&& doc.language !== frappe.boot.user.language) {
			frappe.msgprint(__("Refreshing..."));
			window.location.reload();
		}

		frm.toggle_display(['sb1', 'sb3', 'modules_access'], false);

		if(!doc.__islocal){
			frm.add_custom_button(__("Set Desktop Icons"), function() {
				frappe.route_options = {
					"user": doc.name
				};
				frappe.set_route("modules_setup");
			}, null, "btn-default")

			if(has_common(frappe.user_roles, ["Administrator", "System Manager"])) {

				frm.add_custom_button(__("Set User Permissions"), function() {
					frappe.route_options = {
						"user": doc.name
					};
					frappe.set_route('List', 'User Permission');
				}, __("Permissions"))

				frm.add_custom_button(__('View Permitted Documents'),
					() => frappe.set_route('query-report', 'Permitted Documents For User',
						{user: frm.doc.name}), __("Permissions"));

				frm.toggle_display(['sb1', 'sb3', 'modules_access'], true);
			}

			frm.add_custom_button(__("Reset Password"), function() {
				frappe.call({
					method: "frappe.core.doctype.user.user.reset_password",
					args: {
						"user": frm.doc.name
					}
				})
			}, __("Password"));

			frm.add_custom_button(__("Reset OTP Secret"), function() {
				frappe.call({
					method: "frappe.core.doctype.user.user.reset_otp_secret",
					args: {
						"user": frm.doc.name
					}
				})
			}, __("Password"));

			frm.trigger('enabled');

			frm.roles_editor && frm.roles_editor.show();
			frm.module_editor && frm.module_editor.refresh();

			if(frappe.session.user==doc.name) {
				// update display settings
				if(doc.user_image) {
					frappe.boot.user_info[frappe.session.user].image = frappe.utils.get_file_link(doc.user_image);
				}
			}
		}
		if (frm.doc.user_emails){
			var found =0;
			for (var i = 0;i<frm.doc.user_emails.length;i++){
				if (frm.doc.email==frm.doc.user_emails[i].email_id){
					found = 1;
				}
			}
			if (!found){
				frm.add_custom_button(__("Create User Email"), function() {
					frm.events.create_user_email(frm)
				})
			}
		}

		if (frappe.route_flags.unsaved===1){
			delete frappe.route_flags.unsaved;
			for ( var i=0;i<frm.doc.user_emails.length;i++) {
				frm.doc.user_emails[i].idx=frm.doc.user_emails[i].idx+1;
			}
			cur_frm.dirty();
		}

	},
	validate: function(frm) {
		if(frm.roles_editor) {
			frm.roles_editor.set_roles_in_table()
		}
	},
	enabled: function(frm) {
		var doc = frm.doc;
		if(!doc.__islocal && has_common(frappe.user_roles, ["Administrator", "System Manager"])) {
			frm.toggle_display(['sb1', 'sb3', 'modules_access'], doc.enabled);
			frm.set_df_property('enabled', 'read_only', 0);
		}

		if(frappe.session.user!=="Administrator") {
			frm.toggle_enable('email', doc.__islocal);
		}
	},
	create_user_email:function(frm) {
		frappe.call({
			method: 'frappe.core.doctype.user.user.has_email_account',
			args: {
				email: frm.doc.email
			},
			callback: function(r) {
				if (r.message == undefined) {
					frappe.route_options = {
						"email_id": frm.doc.email,
						"awaiting_password": 1,
						"enable_incoming": 1
					};
					frappe.model.with_doctype("Email Account", function (doc) {
						var doc = frappe.model.get_new_doc("Email Account");
						frappe.route_flags.linked_user = frm.doc.name;
						frappe.route_flags.delete_user_from_locals = true;
						frappe.set_route("Form", "Email Account", doc.name);
					})
				} else {
					frappe.route_flags.create_user_account = frm.doc.name;
					frappe.set_route("Form", "Email Account", r.message[0]["name"]);
				}
			}
		})
	}
})


frappe.ModuleEditor = Class.extend({
	init: function(frm, wrapper) {
		this.wrapper = $('<div class="row module-block-list"></div>').appendTo(wrapper);
		this.frm = frm;
		this.make();
	},
	make: function() {
		var me = this;
		this.frm.doc.__onload.all_modules.forEach(function(m) {
			$(repl('<div class="col-sm-6"><div class="checkbox">\
				<label><input type="checkbox" class="block-module-check" data-module="%(module)s">\
				%(module)s</label></div></div>', {module: m})).appendTo(me.wrapper);
		});
		this.bind();
	},
	refresh: function() {
		var me = this;
		this.wrapper.find(".block-module-check").prop("checked", true);
		$.each(this.frm.doc.block_modules, function(i, d) {
			me.wrapper.find(".block-module-check[data-module='"+ d.module +"']").prop("checked", false);
		});
	},
	bind: function() {
		var me = this;
		this.wrapper.on("change", ".block-module-check", function() {
			var module = $(this).attr('data-module');
			if($(this).prop("checked")) {
				// remove from block_modules
				me.frm.doc.block_modules = $.map(me.frm.doc.block_modules || [], function(d) { if(d.module != module){ return d } });
			} else {
				me.frm.add_child("block_modules", {"module": module});
			}
		});
	}
})