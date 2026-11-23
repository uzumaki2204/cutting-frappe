frappe.pages["cutting-reports"].on_page_load = function (wrapper) {
  cutting_app.load_texts().then((t) => {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: t("ui.reports"), single_column: true });
    const controls = {};
    const add = (fieldname, label, fieldtype, options, value) => {
      controls[fieldname] = page.add_field({ fieldname, label: t(label), fieldtype, options, default: value });
      controls[fieldname].$input?.attr("aria-label", t(label));
    };
    add("from_date", "ui.from", "Date", null, frappe.datetime.get_today());
    add("to_date", "ui.to", "Date", null, frappe.datetime.get_today());
    add("company", "ui.company", "Link", "Company");
    add("device", "ui.device", "Link", "Factory Device");
    add("product", "ui.product", "Link", "Product");
    add("color", "ui.color", "Link", "Product Color");
    add("market", "ui.market", "Link", "Market");
    const body = document.createElement("div"); body.className = "p-3"; page.main[0].append(body);
    let exportRows = [], exportColumns = [];
    let sortKey = null, sortDirection = 1;
    const numericColumns = new Set(["quantity", "sumOrderQty", "cuttingQtyM"]);
    const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

    function sortedRows(rows) {
      if (!sortKey) return rows;
      return [...rows].sort((left, right) => {
        const a = left[sortKey], b = right[sortKey];
        const aEmpty = a == null || a === "", bEmpty = b == null || b === "";
        if (aEmpty || bEmpty) return aEmpty === bEmpty ? 0 : aEmpty ? 1 : -1;
        const difference = numericColumns.has(sortKey) ? Number(a) - Number(b) : collator.compare(String(a), String(b));
        return difference * sortDirection;
      });
    }

    function table(columns, rows) {
      exportColumns = columns; exportRows = sortedRows(rows);
      body.replaceChildren();
      if (!exportRows.length) { const p = document.createElement("p"); p.className = "text-muted"; p.textContent = t("ui.no_data"); body.append(p); return; }
      const container = document.createElement("div"); container.className = "table-responsive";
      const el = document.createElement("table"); el.className = "table table-bordered";
      const head = document.createElement("thead"), header = document.createElement("tr");
      for (const column of columns) {
        const th = document.createElement("th"); th.scope = "col";
        const active = sortKey === column.key;
        th.setAttribute("aria-sort", active ? (sortDirection === 1 ? "ascending" : "descending") : "none");
        const button = document.createElement("button"); button.type = "button";
        button.className = "btn btn-link p-0 text-body text-decoration-none";
        button.textContent = column.label;
        const nextDirection = active && sortDirection === 1 ? -1 : 1;
        button.setAttribute("aria-label", `${column.label}: ${t(nextDirection === 1 ? "ui.sort_ascending" : "ui.sort_descending")}`);
        if (active) {
          const arrow = document.createElement("span"); arrow.setAttribute("aria-hidden", "true");
          arrow.textContent = sortDirection === 1 ? " ▲" : " ▼"; button.append(arrow);
        }
        button.addEventListener("click", () => { sortKey = column.key; sortDirection = nextDirection; table(columns, rows); });
        th.append(button); header.append(th);
      }
      head.append(header); el.append(head);
      const tbody = document.createElement("tbody");
      for (const row of exportRows) {
        const tr = document.createElement("tr");
        for (const column of columns) { const td = document.createElement("td"); td.textContent = row[column.key] ?? ""; tr.append(td); }
        tbody.append(tr);
      }
      el.append(tbody); container.append(el); body.append(container);
    }

    async function refresh() {
      body.textContent = t("ui.loading");
      const filters = Object.fromEntries(["company", "device", "product", "color", "market"].map((key) => [key, controls[key].get_value()]).filter(([, value]) => value));
      const args = { filters, from_date: controls.from_date.get_value(), to_date: controls.to_date.get_value() };
      try {
        const response = await frappe.call({ method: "cutting.reporting.report_summary", args, type: "GET" });
        table(response.message.columns, response.message.rows);
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
    if (frappe.session.user === "Administrator" || frappe.user_roles.some((role) => ["System Manager", "Cutting Manager"].includes(role))) {
      page.add_inner_button(t("ui.cutting_standard"), () => frappe.set_route("List", "Cutting Standard"));
    }
    refresh();
  });
};
