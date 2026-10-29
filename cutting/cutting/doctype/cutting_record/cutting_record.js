frappe.ui.form.on("Cutting Record", {
  refresh(frm) {
    cutting_app.load_texts().then((t) => {
      if (frm.is_new()) return;
      frm.add_custom_button(t("ui.history"), () => frappe.set_route("List", "Cutting History", { cutting_record: frm.doc.name }));
      const manager = frappe.session.user === "Administrator" || frappe.user_roles.some((role) => ["System Manager", "Cutting Manager"].includes(role));
      if (frm.doc.is_deleted) frm.disable_save();
      else if (manager) frm.enable_save();
      if (!manager) return;
      const deleted = Boolean(frm.doc.is_deleted);
      for (const field of ["product", "color", "market", "product_code_identifier", "quantity", "company", "note"]) frm.set_df_property(field, "read_only", deleted ? 1 : 0);
      frm.add_custom_button(t(deleted ? "ui.restore" : "ui.delete"), () => {
        frappe.confirm(t(deleted ? "ui.confirm_restore" : "ui.confirm_delete"), () => {
          frappe.call({ method: deleted ? "cutting.api.restore" : "cutting.api.soft_delete", args: { name: frm.doc.name }, freeze: true })
            .then((result) => { frappe.show_alert({ message: result.message.notice, indicator: "green" }); frm.reload_doc(); });
        });
      });
    });
  },
});
