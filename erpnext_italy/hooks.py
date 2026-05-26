from . import __version__ as app_version

app_name = "erpnext_italy"
app_title = "ERPNext Italy"
app_publisher = "Frappe Technologies"
app_description = "App to hold regional code for KItaly, built on top of ERPNext."
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "contact@frappe.io"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_italy/css/erpnext_italy.css"
# app_include_js = "/assets/erpnext_italy/js/erpnext_italy.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_italy/css/erpnext_italy.css"
# web_include_js = "/assets/erpnext_italy/js/erpnext_italy.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_italy/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"Sales Order": "public/js/sales_order.js",
	"Quotation": "public/js/quotation.js",
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erpnext_italy.utils.jinja_methods",
# 	"filters": "erpnext_italy.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "erpnext_italy.install.before_install"
# after_install = "erpnext_italy.install.after_install"

after_install = "erpnext_italy.install.after_install"
before_uninstall = "erpnext_italy.install.before_uninstall"
after_migrate = "erpnext_italy.install.after_migrate"

# Uninstallation
# ------------

# after_uninstall = "erpnext_italy.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_italy.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

doc_events = {
	"Sales Invoice": {
		"on_submit": "erpnext_italy.utils.sales_invoice_on_submit",
		"on_cancel": "erpnext_italy.utils.sales_invoice_on_cancel",
	},
	'Address': {
		'validate': 'erpnext_italy.utils.set_state_code',
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		# Poll inbound invoices from active SDI providers every 30 min on weekdays
		"*/30 7-20 * * 1-5": [
			"erpnext_italy.sdi_providers.tasks.poll_inbound_invoices"
		],
	},
# 	"all": [
# 		"erpnext_italy.tasks.all"
# 	],
# 	"daily": [
# 		"erpnext_italy.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnext_italy.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erpnext_italy.tasks.weekly"
# 	],
# 	"monthly": [
# 		"erpnext_italy.tasks.monthly"
# 	],
}

# Testing
# -------

# before_tests = "erpnext_italy.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_italy.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnext_italy.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnext_italy.auth.validate"
# ]

regional_overrides = {
	'Italy': {
		'erpnext.controllers.taxes_and_totals.update_itemised_tax_data': 'erpnext_italy.utils.update_itemised_tax_data',
		'erpnext.controllers.accounts_controller.validate_regional': 'erpnext_italy.utils.sales_invoice_validate',
	}
}