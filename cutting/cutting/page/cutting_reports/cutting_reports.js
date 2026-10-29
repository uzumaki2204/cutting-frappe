frappe.pages["cutting-reports"].on_page_load = function (wrapper) {
  cutting_app.load_texts().then((t) => {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: t("ui.reports"), single_column: true });
    const controls = {};
    const add = (fieldname, label, fieldtype, options, value) => {
      controls[fieldname] = page.add_field({ fieldname, label: t(label), fieldtype, options, default: value });
      controls[fieldname].$input?.attr("aria-label", t(label));
    };
    add("mode", "ui.mode", "Select", [t("ui.summary"), t("ui.detail"), t("ui.admin_summary")].join("\n"), t("ui.summary"));
    add("group_by", "ui.group_by", "Select", [t("ui.date"), t("ui.product"), t("ui.color"), t("ui.market")].join("\n"), t("ui.date"));
    add("from_date", "ui.from", "Date", null, frappe.datetime.get_today());
    add("to_date", "ui.to", "Date", null, frappe.datetime.get_today());
    add("company", "ui.company", "Link", "Company");
    add("device", "ui.device", "Link", "Factory Device");
    add("product", "ui.product", "Link", "Product");
    add("color", "ui.color", "Link", "Color");
    add("market", "ui.market", "Link", "Market");
    const body = document.createElement("div"); body.className = "p-3"; page.main[0].append(body);
    let exportRows = [], exportColumns = [];

    function table(columns, rows) {
      exportColumns = columns; exportRows = rows;
      body.replaceChildren();
      if (!rows.length) { const p = document.createElement("p"); p.className = "text-muted"; p.textContent = t("ui.no_data"); body.append(p); return; }
      const container = document.createElement("div"); container.className = "table-responsive";
      const el = document.createElement("table"); el.className = "table table-bordered";
      const head = document.createElement("thead"), header = document.createElement("tr");
      for (const column of columns) { const th = document.createElement("th"); th.scope = "col"; th.textContent = column.label; header.append(th); }
      head.append(header); el.append(head);
      const tbody = document.createElement("tbody");
      for (const row of rows) {
        const tr = document.createElement("tr");
        for (const column of columns) { const td = document.createElement("td"); td.textContent = row[column.key] ?? ""; tr.append(td); }
        tbody.append(tr);
      }
      el.append(tbody); container.append(el); body.append(container);
    }

    async function refresh() {
      body.textContent = t("ui.loading");
      const filters = Object.fromEntries(["company", "device", "product", "color", "market"].map((key) => [key, controls[key].get_value()]).filter(([, value]) => value));
      const mode = controls.mode.get_value();
      const args = { filters, from_date: controls.from_date.get_value(), to_date: controls.to_date.get_value() };
      let method = "cutting.reporting.report_summary";
      if (mode === t("ui.detail")) method = "cutting.reporting.report_detail";
      if (mode === t("ui.admin_summary")) {
        method = "cutting.reporting.admin_summary";
        args.created_from = args.from_date; args.created_to = args.to_date;
        delete args.from_date; delete args.to_date;
      }
      try {
        const response = await frappe.call({ method, args, type: "GET" });
        const data = response.message;
        if (mode === t("ui.detail")) {
          table([
            { key: "occurred_at", label: t("ui.date") }, { key: "company_code", label: t("ui.company") },
            { key: "device_name", label: t("ui.device") }, { key: "product_code", label: t("ui.product") },
            { key: "market_code", label: t("ui.market") }, { key: "color_code", label: t("ui.color") },
            { key: "product_code_identifier", label: t("ui.plan") }, { key: "quantity", label: t("ui.quantity") },
          ], data);
        } else if (mode === t("ui.admin_summary")) {
          const group = controls.group_by.get_value();
          const dimension = group === t("ui.product") ? "byProduct" : group === t("ui.color") ? "byColor" : group === t("ui.market") ? "byMarket" : "byCreatedDate";
          table([{ key: "label", label: group }, { key: "count", label: t("ui.total_records") }, { key: "quantity", label: t("ui.total_quantity") }], data[dimension]);
          const totals = document.createElement("p"); totals.textContent = `${t("ui.total_records")}: ${data.totalRecords} · ${t("ui.total_quantity")}: ${data.totalQuantity}`; body.prepend(totals);
        } else table(data.columns, data.rows);
      } catch (_) { body.textContent = t("ui.report_error"); }
    }

    function exportCsv() {
      const cell = (value) => {
        let text = String(value ?? ""); if (/^[=+@-]/.test(text)) text = `'${text}`;
        return `"${text.replaceAll('"', '""')}"`;
      };
      const csv = [exportColumns.map((c) => cell(c.label)).join(","), ...exportRows.map((r) => exportColumns.map((c) => cell(r[c.key])).join(","))].join("\r\n");
      const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a"); link.href = url; link.download = "cutting.csv"; link.click(); URL.revokeObjectURL(url);
    }
    page.set_primary_action(t("ui.refresh"), refresh);
    page.add_inner_button(t("ui.export"), exportCsv);
    refresh();
  });
};
