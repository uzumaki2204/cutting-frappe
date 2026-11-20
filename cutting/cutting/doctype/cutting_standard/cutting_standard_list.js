frappe.listview_settings["Cutting Standard"] = {
  onload(listview) {
    cutting_app.load_texts().then((t) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".xlsx";
      input.hidden = true;
      listview.page.main[0].append(input);
      let busy = false;
      const button = listview.page.add_inner_button(t("ui.import_standard_excel"), () => input.click());
      button.attr("title", t("ui.import_standard_hint"));
      input.addEventListener("change", async () => {
        const file = input.files[0];
        input.value = "";
        if (!file || busy) return;
        if (!file.name.toLowerCase().endsWith(".xlsx") || file.size > 5 * 1024 * 1024) {
          frappe.msgprint(t("ui.import_standard_invalid_file"));
          return;
        }
        busy = true;
        button.prop("disabled", true);
        try {
          const data = new FormData();
          data.append("file", file);
          data.append("is_private", "1");
          const upload = await fetch("/api/method/upload_file", {
            method: "POST", body: data, credentials: "same-origin",
            headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
          });
          const payload = await upload.json();
          if (!upload.ok || !payload.message?.name) throw new Error(t("ui.import_standard_invalid_file"));
          const response = await frappe.call({
            method: "cutting.standard_import.import_workbook",
            args: { file_id: payload.message.name }, type: "POST",
          });
          const result = response.message;
          frappe.msgprint(t("ui.import_standard_result")
            .replace("{created}", result.created).replace("{updated}", result.updated));
          listview.refresh();
        } catch (error) {
          frappe.msgprint(error.message || t("ui.import_standard_failed"));
        } finally {
          busy = false;
          button.prop("disabled", false);
        }
      });
    });
  },
};
