<<<<<<< HEAD
frappe.provide("frappe.wiz");
frappe.provide("frappe.setup.events");
=======
frappe.provide("frappe.setup");
frappe.provide("frappe.setup.events");
frappe.provide("frappe.ui");
>>>>>>> 176d241496ede1357a309fa44a037b757a252581

frappe.setup = {
	slides: [],
	events: {},
	data: {},
	utils: {},

<<<<<<< HEAD
	remove_app_slides: [],
=======
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
	on: function(event, fn) {
		if(!frappe.setup.events[event]) {
			frappe.setup.events[event] = [];
		}
		frappe.setup.events[event].push(fn);
	},
	add_slide: function(slide) {
		frappe.setup.slides.push(slide);
	},

	run_event: function(event) {
		$.each(frappe.setup.events[event] || [], function(i, fn) {
			fn();
		});
	}
}

frappe.pages['setup-wizard'].on_page_load = function(wrapper) {
	// setup page ui
	$(".navbar:first").toggle(false);

<<<<<<< HEAD
	var requires = ["/assets/frappe/css/animate.min.css"].concat(frappe.boot.setup_wizard_requires || []);

	frappe.require(requires, function() {
		frappe.setup.run_event("before_load");

		var wizard_settings = {
			page_name: "setup-wizard",
			parent: wrapper,
			slides: frappe.setup.slides,
			title: __("Welcome")
		}

		frappe.wizard = new frappe.setup.Wizard(wizard_settings);
		frappe.setup.run_event("after_load");

		// frappe.wizard.values = test_values_edu;

		var route = frappe.get_route();
		if(route) {
			frappe.wizard.show(route[1]);
		}
	});
}

frappe.pages['setup-wizard'].on_page_show = function(wrapper) {
	if(frappe.get_route()[1]) {
		frappe.wizard && frappe.wizard.show(frappe.get_route()[1]);
	}
}

frappe.setup.Wizard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.slides;
		this.slide_dict = {};
		this.values = {};
		this.welcomed = true;
		frappe.set_route("setup-wizard/0");
	},
	make: function() {
		this.parent = $('<div class="setup-wizard-wrapper">').appendTo(this.parent);
	},
	get_message: function(html) {
		return $(repl('<div data-state="setup-complete">\
			<div style="padding: 40px;" class="text-center">%(html)s</div>\
		</div>', {html:html}))
	},
	show_working: function() {
		this.hide_current_slide();
		frappe.set_route(this.page_name);
		this.current_slide = {"$wrapper": this.get_message(this.working_html()).appendTo(this.parent)};
	},
	show_complete: function() {
		this.hide_current_slide();
		this.current_slide = {"$wrapper": this.get_message(this.complete_html()).appendTo(this.parent)};
	},
	show: function(id) {
		if(!this.welcomed) {
			frappe.set_route(this.page_name);
			return;
		}
		id = cint(id);
		if(this.current_slide && this.current_slide.id===id) {
			return;
		}

		this.update_values();

		if(!this.slide_dict[id]) {
			this.slide_dict[id] = new frappe.setup.WizardSlide($.extend(this.slides[id], {wiz:this, id:id}));
			this.slide_dict[id].make();
		}

		this.hide_current_slide();

		this.current_slide = this.slide_dict[id];
		this.current_slide.$wrapper.removeClass("hidden");
	},
	hide_current_slide: function() {
		if(this.current_slide) {
			this.current_slide.$wrapper.addClass("hidden");
			this.current_slide = null;
		}
	},
	get_values: function() {
		var values = {};
		$.each(this.slide_dict, function(id, slide) {
			if(slide.values) {
				$.extend(values, slide.values);
			}
		});
		return values;
	},
	working_html: function() {
		var msg = $(frappe.render_template("setup_wizard_message", {
			image: "/assets/frappe/images/ui/bubble-tea-smile.svg",
			title: __("Setting Up"),
			message: __('Sit tight while your system is being setup. This may take a few moments.')
		}));
		msg.find(".setup-wizard-message-image").addClass("animated infinite bounce");
		return msg.html();
	},

	complete_html: function() {
		return frappe.render_template("setup_wizard_message", {
			image: "/assets/frappe/images/ui/bubble-tea-happy.svg",
			title: __('Setup Complete'),
			message: ""
		});
	},

	on_complete: function() {
		var me = this;
		this.update_values();
		this.show_working();
		return frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: {args: this.values},
			callback: function(r) {
				me.show_complete();
=======
	var requires = ["/assets/frappe/css/animate.min.css"].concat(
		frappe.boot.setup_wizard_requires || []);

	frappe.require(requires, function() {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.load_languages",
			freeze: true,
			callback: function(r) {
				frappe.setup.data.lang = r.message;
				
				frappe.setup.run_event("before_load");
				var wizard_settings = {
					parent: wrapper,
					slides: frappe.setup.slides,
					slide_class: frappe.setup.SetupWizardSlide,
					unidirectional: 1,
					before_load: ($footer) => {
						$footer.find('.next-btn').removeClass('btn-default')
							.addClass('btn-primary');
						$footer.find('.text-right').prepend(
							$(`<a class="complete-btn btn btn-sm primary">
						${__("Complete Setup")}</a>`));

					}
				}
				frappe.wizard = new frappe.setup.SetupWizard(wizard_settings);
				frappe.setup.run_event("after_load");
				// frappe.wizard.values = test_values_edu;
				let route = frappe.get_route();
				if(route) {
					frappe.wizard.show_slide(route[1]);
				}
			}
		});
	});
};

frappe.pages['setup-wizard'].on_page_show = function(wrapper) {
	if(frappe.get_route()[1]) {
		frappe.wizard && frappe.wizard.show_slide(frappe.get_route()[1]);
	}
};

frappe.setup.on("before_load", function() {
	// load slides
	frappe.setup.slides_settings.map(frappe.setup.add_slide);
});

frappe.setup.SetupWizard = class SetupWizard extends frappe.ui.Slides {
	constructor(args = {}) {
		super(args);
		$.extend(this, args);

		this.welcomed = true;
		this.page_name = "setup-wizard";
		frappe.set_route("setup-wizard/0");
	}

	make() {
		super.make();
		this.container.addClass("container setup-wizard-slide with-form");
		this.$next_btn.addClass('action');
		this.$complete_btn = this.$footer.find('.complete-btn').addClass('action');
		this.setup_keyboard_nav();
	}

	setup_keyboard_nav() {
		this.container.on('keydown',  (e) => {
			if(e.which === 13) {
				var $target = $(e.target);
				if($target.hasClass('prev-btn')) {
					$target.trigger('click');
				} else {
					this.container.find('.next-btn').trigger('click');
					e.preventDefault();
				}
			}
		});
	}

	before_show_slide() {
		if(!this.welcomed) {
			frappe.set_route(this.page_name);
			return false;
		}
		return true;
	}

	show_slide(id) {
		super.show_slide(id);
		frappe.set_route(this.page_name, id + "");
	}

	show_hide_prev_next(id) {
		super.show_hide_prev_next(id);
		if (id + 1 === this.slides.length){
			this.$next_btn.removeClass("btn-primary").hide();
			this.$complete_btn.addClass("btn-primary").show()
				.on('click', this.action_on_complete.bind(this));

		} else {
			this.$next_btn.addClass("btn-primary").show();
			this.$complete_btn.removeClass("btn-primary").hide();
		}
	}

	refresh_slides() {
		// For Translations, etc.
		if(this.in_refresh_slides || !this.current_slide.set_values()) {
			return;
		}
		this.in_refresh_slides = true;

		this.update_values();
		frappe.setup.slides = [];
		frappe.setup.run_event("before_load");

		frappe.setup.slides = this.get_setup_slides_filtered_by_domain();

		this.slides = frappe.setup.slides;
		frappe.setup.run_event("after_load");

		// re-render all slide, only remake made slides
		$.each(this.slide_dict, (id, slide) => {
			if(slide.made) {
				this.made_slide_ids.push(id);
			}
		});
		this.made_slide_ids.push(this.current_id);
		this.setup();

		this.show_slide(this.current_id);
		setTimeout(() => {
			this.container.find('.form-control').first().focus();
		}, 200);
		this.in_refresh_slides = false;
	}

	action_on_complete() {
		var me = this;
		if (!this.current_slide.set_values()) return;
		this.update_values();
		this.show_working_state();
		return frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: {args: this.values},
			callback: function() {
				me.show_setup_complete_state();
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
				if(frappe.setup.welcome_page) {
					localStorage.setItem("session_last_route", frappe.setup.welcome_page);
				}
				setTimeout(function() {
<<<<<<< HEAD
					window.location = "/desk";
				}, 2000);
			},
			error: function(r) {
				var d = frappe.msgprint(__("There were errors."));
				d.custom_onhide = function() {
=======
					// frappe.ui.toolbar.clear_cache();
					window.location = "/desk";
				}, 2000);
				setTimeout(()=> {
					$('body').removeClass('setup-state');
				}, 20000);
			},
			error: function() {
				var d = frappe.msgprint(__("There were errors."));
				d.custom_onhide = function() {
					$(me.parent).find('.page-card-container').remove();
					$('body').removeClass('setup-state');
					me.container.show();
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
					frappe.set_route(me.page_name, me.slides.length - 1);
				};
			}
		});
<<<<<<< HEAD
	},

	update_values: function() {
		this.values = $.extend(this.values, this.get_values());
	},

	refresh_slides: function() {
		// reset all slides so that labels are translated
		var me = this;
		if(this.in_refresh_slides) {
			return;
		}
		this.in_refresh_slides = true;

		if(!this.current_slide.set_values()) {
			return;
		}

		this.update_values();

		frappe.setup.slides = [];
		frappe.setup.run_event("before_load");

		// remove slides listed in remove_app_slides
		var new_slides = [];
=======
	}

	get_setup_slides_filtered_by_domain() {
		var filtered_slides = [];
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		frappe.setup.slides.forEach(function(slide) {
			if(frappe.setup.domain) {
				var domains = slide.domains;
				if (domains.indexOf('all') !== -1 ||
					domains.indexOf(frappe.setup.domain.toLowerCase()) !== -1) {
<<<<<<< HEAD
					new_slides.push(slide);
				}
			} else {
				new_slides.push(slide);
			}
		})

		frappe.setup.slides = new_slides;

		this.slides = frappe.setup.slides;
		frappe.setup.run_event("after_load");

		// re-render all slides
		this.slide_dict = {};

		var current_id = this.current_slide.id;
		this.current_slide.destroy();

		this.show(current_id);
		this.in_refresh_slides = false;
	}
});

frappe.setup.WizardSlide = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.$wrapper = $('<div class="slide-wrapper hidden"></div>')
			.appendTo(this.wiz.parent)
			.attr("data-slide-id", this.id);
	},
	make: function() {
		var me = this;
		if(this.$body) this.$body.remove();

		var fields = JSON.parse(JSON.stringify(this.fields));

		if(this.add_more) {
			this.count = 1;
			fields = fields.map((field, i) => {
				if(field.fieldname) {
					field.fieldname += '_1';
				}
				if(i === 1 && this.mandatory_entry) {
					field.reqd = 1;
				}
				if(!field.static) {
					if(field.label) field.label += ' 1';
				}
				return field;
			});
		}

		if(this.before_load) {
			this.before_load(this);
		}

		this.$body = $(frappe.render_template("setup_wizard_page", {
			help: __(this.help),
			title:__(this.title),
			main_title:__(this.wiz.title),
			step: this.id + 1,
			name: this.name,
			slides_count: this.wiz.slides.length
		})).appendTo(this.$wrapper);

		this.body = this.$body.find(".form")[0];

		if(this.fields) {
			this.form = new frappe.ui.FieldGroup({
				fields: fields,
				body: this.body,
				no_submit_on_enter: true
			});
			this.form.make();
		} else {
			$(this.body).html(this.html);
		}

		this.set_reqd_fields();
		this.set_init_values();
		this.make_prev_next_buttons();
		if(this.add_more) this.bind_more_button();

		var $primary_btn = this.$next ? this.$next : this.$complete;

		this.bind_fields_to_next($primary_btn);

		if(this.onload) {
			this.onload(this);
		}
		this.set_reqd_fields();
		this.bind_fields_to_next($primary_btn);

		this.reset_next($primary_btn);
		this.focus_first_input();
	},
	set_reqd_fields: function() {
		var dict = this.form.fields_dict;
		this.reqd_fields = [];
		Object.keys(dict).map(key => {
			if(dict[key].df.reqd) {
				this.reqd_fields.push(dict[key]);
			}
		});
	},
	set_init_values: function() {
=======
					filtered_slides.push(slide);
				}
			} else {
				filtered_slides.push(slide);
			}
		})
		return filtered_slides;
	}

	show_working_state() {
		this.container.hide();
		$('body').addClass('setup-state');
		frappe.set_route(this.page_name);

		this.working_state_message = this.get_message(
			__("Setting Up"),
			__("Sit tight while your system is being setup. This may take a few moments."),
			true
		).appendTo(this.parent);

		this.current_id = this.slides.length;
		this.current_slide = null;
		this.completed_state_message = this.get_message(
			__("Setup Complete"),
			__("You're all set!")
		);
	}

	show_setup_complete_state() {
		this.working_state_message.hide();
		this.completed_state_message.appendTo(this.parent);
	}

	get_message(title, message="", loading=false) {
		return $(`<div class="page-card-container" data-state="setup">
			<div class="page-card">
				<div class="page-card-head">
					<span class="indicator blue">
						${title}</span>
				</div>
				<p>${message}</p>
				<div class="state-icon-container">
				${loading
					? '<div style="width:100%;height:100%" class="lds-rolling state-icon"><div></div></div>'
					: `<div style="width:100%;height:100%" class="state-icon"><i class="fa fa-check-circle text-extra-muted"
						style="font-size: 64px; margin-top: -8px;">
					</i></div>`
				}
				</div>
			</div>
		</div>`);
	}
};

frappe.setup.SetupWizardSlide = class SetupWizardSlide extends frappe.ui.Slide {
	constructor(slide = null) {
		super(slide);
	}

	make() {
		super.make();
		this.set_init_values();
		this.reset_action_button_state();
	}

	set_init_values () {
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		var me = this;
		// set values from frappe.setup.values
		if(frappe.wizard.values && this.fields) {
			this.fields.forEach(function(f) {
				var value = frappe.wizard.values[f.fieldname];
				if(value) {
					me.get_field(f.fieldname).set_input(value);
				}
			});
		}
<<<<<<< HEAD
	},

	set_values: function() {
		this.values = this.form.get_values();
		if(this.values===null) {
			return false;
		}
		if(this.validate && !this.validate()) {
			return false;
		}
		return true;
	},

	bind_more_button: function() {
		this.$more = this.$body.find('.more-btn');
		this.$more.removeClass('hide')
			.on('click', () => {
				this.count++;
				var fields = JSON.parse(JSON.stringify(this.fields));
				this.form.add_fields(fields.map(field => {
					if(field.fieldname) field.fieldname += '_' + this.count;
					if(!field.static) {
						if(field.label) field.label += ' ' + this.count;
					}
					return field;
				}));
				if(this.count === this.max_count) {
					this.$more.addClass('hide');
				}
			});
	},

	make_prev_next_buttons: function() {
		var me = this;

		// prev
		if(this.id > 0) {
			this.$prev = this.$body.find('.prev-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(function() {
					me.prev();
				})
				.css({"margin-right": "10px"});
		}

		// next or complete
		if(this.id+1 < this.wiz.slides.length) {
			this.$next = this.$body.find('.next-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.next_or_complete.bind(this));
		} else {
			this.$complete = this.$body.find('.complete-btn')
				.removeClass("hide")
				.attr('tabIndex', 0)
				.click(this.next_or_complete.bind(this));
		}

		// setup mousefree navigation
		this.$body.on('keypress', function(e) {
			if(e.which === 13) {
				var $target = $(e.target);
				if($target.hasClass('prev-btn')) {
					me.prev();
				} else if($target.hasClass('btn-attach')) {
					//do nothing
				} else {
					me.next_or_complete();
					e.preventDefault();
				}
			}
		});
	},
	bind_fields_to_next: function($primary_btn) {
		var me = this;
		this.reqd_fields.map((field) => {
			field.$wrapper.on('change input', () => {
				me.reset_next($primary_btn);
			});
		});
	},
	next_or_complete: function() {
		if(this.set_values()) {
			if(this.id+1 < this.wiz.slides.length) {
				this.next();
			} else {
				this.wiz.on_complete(this.wiz);
			}
		}
	},
	reset_next: function($primary_btn) {
		var empty_fields = this.reqd_fields.filter((field) => {
			return !field.get_value();
		})

		if(empty_fields.length) {
			$primary_btn.addClass('disabled');
		} else {
			$primary_btn.removeClass('disabled');
		}
	},
	focus_first_input: function() {
		setTimeout(function() {
			this.$body.find('.form-control').first().focus();
		}.bind(this), 0);
	},
	next: function() {
		frappe.set_route(this.wiz.page_name, this.id+1 + "");
	},
	prev: function() {
		frappe.set_route(this.wiz.page_name, this.id-1 + "");
	},
	get_input: function(fn) {
		return this.form.get_input(fn);
	},
	get_field: function(fn) {
		return this.form.get_field(fn);
	},
	destroy: function() {
		this.$body.remove();
		if(frappe.wizard.current_slide===this) {
			frappe.wizard.current_slide = null;
		}
	},
});

var frappe_slides = [
=======
	}

};

// Frappe slides settings
// ======================================================

frappe.setup.slides_settings = [
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
	{
		// Welcome (language) slide
		name: "welcome",
		domains: ["all"],
		title: __("Hello!"),
		icon: "fa fa-world",
<<<<<<< HEAD
		help: __("Let's prepare the system for first use."),
=======
		// help: __("Let's prepare the system for first use."),
>>>>>>> 176d241496ede1357a309fa44a037b757a252581

		fields: [
			{ fieldname: "language", label: __("Your Language"),
				fieldtype: "Select", reqd: 1}
		],

		onload: function(slide) {
<<<<<<< HEAD
			if (frappe.setup.data.lang) {
				this.setup_fields(slide);
			} else {
				utils.load_languages(slide, this.setup_fields);
			}
		},

		setup_fields: function(slide) {
			utils.setup_language_field(slide);
			utils.bind_language_events(slide);
=======
			this.setup_fields(slide);

			var language_field = slide.get_field("language");

			language_field.set_input(frappe.setup.data.default_language || "English");

			if (!frappe.setup._from_load_messages) {
				language_field.$input.trigger("change");
			}
			delete frappe.setup._from_load_messages;
			moment.locale("en");
		},

		setup_fields: function(slide) {
			frappe.setup.utils.setup_language_field(slide);
			frappe.setup.utils.bind_language_events(slide);
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		},
	},

	{
		// Region slide
		name: 'region',
		domains: ["all"],
		title: __("Select Your Region"),
		icon: "fa fa-flag",
<<<<<<< HEAD
		help: __("Select your Country, Time Zone and Currency"),
=======
		// help: __("Select your Country, Time Zone and Currency"),
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		fields: [
			{ fieldname: "country", label: __("Your Country"), reqd:1,
				fieldtype: "Select" },
			{ fieldtype: "Section Break" },
			{ fieldname: "timezone", label: __("Time Zone"), reqd:1,
				fieldtype: "Select" },
			{ fieldtype: "Column Break" },
			{ fieldname: "currency", label: __("Currency"), reqd:1,
				fieldtype: "Select" }
		],

		onload: function(slide) {
			if(frappe.setup.data.regional_data) {
				this.setup_fields(slide);
			} else {
<<<<<<< HEAD
				utils.load_regional_data(slide, this.setup_fields);
=======
				frappe.setup.utils.load_regional_data(slide, this.setup_fields);
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
			}
		},

		setup_fields: function(slide) {
<<<<<<< HEAD
			utils.setup_region_fields(slide);
			utils.bind_region_events(slide);
=======
			frappe.setup.utils.setup_region_fields(slide);
			frappe.setup.utils.bind_region_events(slide);
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		}
	},

	{
		// Profile slide
		name: 'user',
		domains: ["all"],
		title: __("The First User: You"),
		icon: "fa fa-user",
		fields: [
			{ "fieldtype":"Attach Image", "fieldname":"attach_user_image",
				label: __("Attach Your Picture"), is_private: 0, align: 'center'},
			{ "fieldname": "full_name", "label": __("Full Name"), "fieldtype": "Data",
				reqd:1},
			{ "fieldname": "email", "label": __("Email Address") + ' (' + __("Will be your login ID") + ')',
				"fieldtype": "Data", "options":"Email"},
			{ "fieldname": "password", "label": __("Password"), "fieldtype": "Password" }
		],
<<<<<<< HEAD
		help: __('The first user will become the System Manager (you can change this later).'),
=======
		// help: __('The first user will become the System Manager (you can change this later).'),
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
		onload: function(slide) {
			if(frappe.session.user!=="Administrator") {
				slide.form.fields_dict.email.$wrapper.toggle(false);
				slide.form.fields_dict.password.$wrapper.toggle(false);

				// remove password field
				delete slide.form.fields_dict.password;

				if(frappe.boot.user.first_name || frappe.boot.user.last_name) {
					slide.form.fields_dict.full_name.set_input(
						[frappe.boot.user.first_name, frappe.boot.user.last_name].join(' ').trim());
				}

				var user_image = frappe.get_cookie("user_image");
				var $attach_user_image = slide.form.fields_dict.attach_user_image.$wrapper;

				if(user_image) {
					$attach_user_image.find(".missing-image").toggle(false);
					$attach_user_image.find("img").attr("src", decodeURIComponent(user_image));
					$attach_user_image.find(".img-container").toggle(true);
				}
				delete slide.form.fields_dict.email;

			} else {
				slide.form.fields_dict.email.df.reqd = 1;
				slide.form.fields_dict.email.refresh();
				slide.form.fields_dict.password.df.reqd = 1;
				slide.form.fields_dict.password.refresh();

<<<<<<< HEAD
				utils.load_user_details(slide, this.setup_fields);
=======
				frappe.setup.utils.load_user_details(slide, this.setup_fields);
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
			}
		},

		setup_fields: function(slide) {
			if(frappe.setup.data.full_name) {
				slide.form.fields_dict.full_name.set_input(frappe.setup.data.full_name);
			}
			if(frappe.setup.data.email) {
				let email = frappe.setup.data.email;
				slide.form.fields_dict.email.set_input(email);
				if (frappe.get_gravatar(email, 200)) {
					var $attach_user_image = slide.form.fields_dict.attach_user_image.$wrapper;
					$attach_user_image.find(".missing-image").toggle(false);
					$attach_user_image.find("img").attr("src", frappe.get_gravatar(email, 200));
					$attach_user_image.find(".img-container").toggle(true);
				}
			}
		},
	}
];

<<<<<<< HEAD
var utils = {
	load_languages: function(slide, callback) {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.load_languages",
			freeze: true,
			callback: function(r) {
				frappe.setup.data.lang = r.message;
				callback(slide);

				var language_field = slide.get_field("language");

				language_field.set_input(frappe.setup.data.default_language || "English");

				if (!frappe.setup._from_load_messages) {
					language_field.$input.trigger("change");
				}
				delete frappe.setup._from_load_messages;
				moment.locale("en");
			}
		});
	},

=======
frappe.setup.utils = {
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
	load_regional_data: function(slide, callback) {
		frappe.call({
			method:"frappe.geo.country_info.get_country_timezone_info",
			callback: function(data) {
				frappe.setup.data.regional_data = data.message;
				callback(slide);
			}
		});
	},

	load_user_details: function(slide, callback) {
		frappe.call({
			method: "frappe.desk.page.setup_wizard.setup_wizard.load_user_details",
			freeze: true,
			callback: function(r) {
				frappe.setup.data.full_name = r.message.full_name;
				frappe.setup.data.email = r.message.email;
				callback(slide);
			}
		})
	},

	setup_language_field: function(slide) {
		var language_field = slide.get_field("language");
		language_field.df.options = frappe.setup.data.lang.languages;
		language_field.refresh();
	},

	setup_region_fields: function(slide) {
		/*
			Set a slide's country, timezone and currency fields
		*/
		var data = frappe.setup.data.regional_data;

		var country_field = slide.get_field('country');

		slide.get_input("country").empty()
			.add_options([""].concat(Object.keys(data.country_info).sort()));

		slide.get_input("currency").empty()
			.add_options(frappe.utils.unique([""].concat($.map(data.country_info,
				function(opts, country) { return opts.currency; }))).sort());

		slide.get_input("timezone").empty()
			.add_options([""].concat(data.all_timezones));

		// set values if present
		if(frappe.wizard.values.country) {
			country_field.set_input(frappe.wizard.values.country);
		} else if (data.default_country) {
			country_field.set_input(data.default_country);
		}

		if(frappe.wizard.values.currency) {
			slide.get_field("currency").set_input(frappe.wizard.values.currency);
		}

		if(frappe.wizard.values.timezone) {
			slide.get_field("timezone").set_input(frappe.wizard.values.timezone);
		}

	},

	bind_language_events: function(slide) {
		slide.get_input("language").unbind("change").on("change", function() {
			var lang = $(this).val() || "English";
			frappe._messages = {};
			frappe.call({
				method: "frappe.desk.page.setup_wizard.setup_wizard.load_messages",
				freeze: true,
				args: {
					language: lang
				},
				callback: function(r) {
					frappe.setup._from_load_messages = true;
					frappe.wizard.refresh_slides();
				}
			});
		});
	},

	bind_region_events: function(slide) {
		/*
			Bind a slide's country, timezone and currency fields
		*/
		slide.get_input("country").on("change", function() {
			var country = slide.get_input("country").val();
			var $timezone = slide.get_input("timezone");
			var data = frappe.setup.data.regional_data;

			$timezone.empty();

			// add country specific timezones first
			if(country) {
				var timezone_list = data.country_info[country].timezones || [];
				$timezone.add_options(timezone_list.sort());
				slide.get_field("currency").set_input(data.country_info[country].currency);
				slide.get_field("currency").$input.trigger("change");
			}

			// add all timezones at the end, so that user has the option to change it to any timezone
			$timezone.add_options([""].concat(data.all_timezones));

			slide.get_field("timezone").set_input($timezone.val());

			// temporarily set date format
			frappe.boot.sysdefaults.date_format = (data.country_info[country].date_format
				|| "dd-mm-yyyy");
		});

		slide.get_input("currency").on("change", function() {
			var currency = slide.get_input("currency").val();
			if (!currency) return;
			frappe.model.with_doc("Currency", currency, function() {
				frappe.provide("locals.:Currency." + currency);
				var currency_doc = frappe.model.get_doc("Currency", currency);
				var number_format = currency_doc.number_format;
				if (number_format==="#.###") {
					number_format = "#.###,##";
				} else if (number_format==="#,###") {
					number_format = "#,###.##"
				}

				frappe.boot.sysdefaults.number_format = number_format;
				locals[":Currency"][currency] = $.extend({}, currency_doc);
			});
		});
	},
<<<<<<< HEAD

}

frappe.setup.on("before_load", function() {
	// load slides
	frappe_slides.map(frappe.setup.add_slide);
});
=======
};
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
