from cutting.i18n import catalog

app_name = "cutting"
app_title = "Cutting"
app_publisher = "Onichan"
app_description = catalog()["en"]["app.description"]
app_email = ""
app_license = "Proprietary"

required_apps = ["factory_management"]

add_to_apps_screen = [{
    "name": app_name,
    "title": app_title,
    "route": "/cutting",
    "has_permission": "cutting.access.can_open",
}]

before_install = "cutting.install.before_install"
before_migrate = "cutting.install.before_install"
after_install = "cutting.install.after_install"
after_migrate = "cutting.install.after_migrate"
app_include_js = ["/assets/cutting/js/i18n.js"]
