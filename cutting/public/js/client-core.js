(function (root) {
  "use strict";
  const key = (item) => item.local_event_id;
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const upsert = (items, item) => [...items.filter((row) => key(row) !== key(item)), copy(item)];
  const empty = () => ({ records: [], updates: [], deletes: [], saved: [] });

  function add(state, item) {
    state.records = upsert(state.records, item);
    state.saved = upsert(state.saved, { ...item, synced: false });
  }

  function edit(state, item) {
    if (state.records.some((row) => key(row) === key(item))) {
      state.records = upsert(state.records, item);
    } else {
      state.updates = upsert(state.updates, item);
    }
    state.saved = upsert(state.saved, { ...item, synced: false });
  }

  function remove(state, id) {
    const pending = state.records.some((row) => key(row) === id);
    state.records = state.records.filter((row) => key(row) !== id);
    state.updates = state.updates.filter((row) => key(row) !== id);
    if (!pending) state.deletes = upsert(state.deletes, { local_event_id: id });
    state.saved = state.saved.filter((row) => key(row) !== id);
  }

  function acknowledge(state, sent, result) {
    for (const id of result.accepted_local_event_ids || []) {
      const original = sent.records.find((row) => key(row) === id);
      const current = state.records.find((row) => key(row) === id);
      state.records = state.records.filter((row) => key(row) !== id);
      if (!state.saved.some((row) => key(row) === id)) {
        state.deletes = upsert(state.deletes, { local_event_id: id });
      } else if (current && JSON.stringify(current) !== JSON.stringify(original)) {
        state.updates = upsert(state.updates, current);
      }
    }
    for (const id of result.accepted_update_local_event_ids || []) {
      const original = sent.updates.find((row) => key(row) === id);
      state.updates = state.updates.filter((row) => key(row) !== id || JSON.stringify(row) !== JSON.stringify(original));
    }
    const deleted = new Set(result.accepted_delete_local_event_ids || []);
    state.deletes = state.deletes.filter((row) => !deleted.has(key(row)));
    const pending = new Set([...state.records, ...state.updates, ...state.deletes].map(key));
    state.saved = state.saved.map((row) => ({ ...row, synced: !pending.has(key(row)) }));
    const synced = state.saved.filter((row) => row.synced).sort((a, b) => String(b.occurred_at).localeCompare(String(a.occurred_at))).slice(0, 200);
    state.saved = [...state.saved.filter((row) => !row.synced), ...synced];
    return state;
  }

  function mergeServer(state, rows) {
    const pending = new Set([...state.records, ...state.updates, ...state.deletes].map(key));
    const hidden = new Set(state.deletes.map(key));
    for (const row of rows) {
      if (!pending.has(key(row)) && !hidden.has(key(row))) state.saved = upsert(state.saved, { ...row, synced: true });
    }
    const synced = state.saved.filter((row) => row.synced).sort((a, b) => String(b.occurred_at).localeCompare(String(a.occurred_at))).slice(0, 200);
    state.saved = [...state.saved.filter((row) => !row.synced), ...synced];
    return state;
  }

  const api = { empty, add, edit, remove, acknowledge, mergeServer, copy };
  root.CuttingQueue = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window === "undefined" ? globalThis : window);
