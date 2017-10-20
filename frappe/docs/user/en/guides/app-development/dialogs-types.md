# Dialogs Types

<<<<<<< HEAD
Frappé provide a group of standard dialogs that are very usefull while coding.

## Alert Dialog

<img class="screenshot" src="/docs/assets/img/app-development/show_alert.png">

Is helpfull for show a non-obstructive message.

This dialog have 2 parameters `txt`that is the message and `seconds` that is the time that the message will be showed for the user, the standard is `3 seconds`.
=======
Frappé provides a group of standard dialogs that are very useful while coding.

## Alert Dialog

<img class="screenshot" src="/docs/assets/img/app-development/show-alert.png">

Alert Dialog is used for showing non-obstructive messages.

It has 2 parameters:

- **txt:** The message to be shown in the `Alert Dialog`
- **seconds:** The duration that the message will be displayed. The default is `3 seconds`.
>>>>>>> 176d241496ede1357a309fa44a037b757a252581

### Example

	show_alert('Hi, do you have a new message', 5);

---

## Prompt Dialog

<img class="screenshot" src="/docs/assets/img/app-development/prompt.png">

<<<<<<< HEAD
Is helpful for ask a value for the user

This dialog have 4 parameters, they are:

- **fields:** a list with the fields objects
- **callback:** the function that manage the received values
=======
Prompt Dialog is used for collecting data from users.

It has 4 parameters:

- **fields:** a list with the fields objects
- **callback:** a function to process the data in the dialog
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
- **title:** the title of the dialog
- **primary_label:** the label of the primary button

### Example

	frappe.prompt([
		{'fieldname': 'birth', 'fieldtype': 'Date', 'label': 'Birth Date', 'reqd': 1}  
	],
	function(values){
		show_alert(values, 5);
	},
	'Age verification',
	'Subscribe me'
	)

---
## Confirm Dialog

<img class="screenshot" src="/docs/assets/img/app-development/confirm-dialog.png">

<<<<<<< HEAD
Usefull to get a confirmation from the user before do an action

This dialog have 3 arguments, they are:

- **mesage:**  The message content
=======
Confirm Dialog is used to get a confirmation from the user before executing an action.

It has 3 arguments:

- **mesage:**  The message to display in the dialog
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
- **onyes:** The callback on positive confirmation
- **oncancel:** The callback on negative confirmation

### Example

	frappe.confirm(
		'Are you sure to leave this page?',
		function(){
			window.close();
		},
		function(){
			show_alert('Thanks for continue here!')
		}
	)

---

## Message Print

<img class="screenshot" src="/docs/assets/img/app-development/msgprint.png">

<<<<<<< HEAD
Is helpfull for show a informational dialog for the user;

This dialog have 2 arguments, they are:

- **message:** The message content, can be a HTML string too
=======
Message Print is used for showing information to users.

It has 2 arguments:

- **message:** The message to display. It can be a HTML string
>>>>>>> 176d241496ede1357a309fa44a037b757a252581
- **title:** The title of the dialog

### Example

	msgprint("<b>Server Status</b>"
		+ "<hr>"
		+ "<ul>"
    			+ "<li><b>28%</b> Memory</li>"
    			+ "<li><b>12%</b> Processor</li>"
    			+ "<li><b>0.3%</b> Disk</li>"
		+ "</ul>", 'Server Info')

---

### Custom Dialog

<img class="screenshot" src="/docs/assets/img/app-development/dialog.png">

<<<<<<< HEAD
Frappé provide too a `Class` that you can extend and build your own custom dialogs

`frappe.ui.Dialog`
=======
You can extend and build your own custom dialogs using `frappe.ui.Dialog`
>>>>>>> 176d241496ede1357a309fa44a037b757a252581

### Example

	var d = new frappe.ui.Dialog({
		'fields': [
			{'fieldname': 'ht', 'fieldtype': 'HTML'},
			{'fieldname': 'today', 'fieldtype': 'Date', 'default': frappe.datetime.nowdate()}
		],
		primary_action: function(){
			d.hide();
			show_alert(d.get_values());
		}
	});
	d.fields_dict.ht.$wrapper.html('Hello World');
	d.show();




<!-- markdown -->
