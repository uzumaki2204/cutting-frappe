frappe.listview_settings["Cutting Record"] = {
  filters: [["is_deleted", "=", 0]],
  onload(listview) {
    cutting_app.load_texts().then((t) => {
      listview.page.add_inner_button(t("ui.trash"), () => listview.filter_area.set([["Cutting Record", "is_deleted", "=", 1]]));
      listview.page.add_inner_button(t("ui.active_records"), () => listview.filter_area.set([["Cutting Record", "is_deleted", "=", 0]]));
      listview.page.add_inner_button(t("ui.reports"), () => frappe.set_route("cutting-reports"));
    });
  },
};
