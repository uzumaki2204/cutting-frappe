window.cutting_app = window.cutting_app || {};
window.cutting_app.load_texts = function () {
  if (!this.texts_promise) {
    this.texts_promise = frappe.call({ method: "cutting.api.translations", args: { lang: frappe.boot.lang || "vi" }, type: "GET" })
      .then((response) => {
        const texts = response.message;
        this.t = (key) => texts[key] || texts["error.unexpected"];
        return this.t;
      }).catch((error) => { this.texts_promise = null; throw error; });
  }
  return this.texts_promise;
};
