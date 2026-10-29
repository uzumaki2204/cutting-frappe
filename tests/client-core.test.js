const test = require("node:test");
const assert = require("node:assert/strict");
const queue = require("../cutting/public/js/client-core.js");

const event = (id, quantity = 1) => ({ local_event_id: id, product: "P", color: "C", market: "M", product_code_identifier: "PLAN", quantity, occurred_at: "2026-10-29T01:00:00Z" });

test("editing an unsent create keeps one create", () => {
  const state = queue.empty(); queue.add(state, event("a")); queue.edit(state, event("a", 2));
  assert.equal(state.records.length, 1); assert.equal(state.records[0].quantity, 2); assert.equal(state.updates.length, 0);
});

test("canceling an unsent create does not send a server delete", () => {
  const state = queue.empty(); queue.add(state, event("a")); queue.remove(state, "a");
  assert.equal(state.records.length, 0); assert.equal(state.deletes.length, 0);
});

test("acknowledging a snapshot preserves later creates", () => {
  const state = queue.empty(); queue.add(state, event("a")); const sent = queue.copy(state); queue.add(state, event("b"));
  queue.acknowledge(state, sent, { accepted_local_event_ids: ["a"] });
  assert.deepEqual(state.records.map((row) => row.local_event_id), ["b"]);
  assert.equal(state.saved.find((row) => row.local_event_id === "a").synced, true);
});

test("an edit during an in-flight create becomes an update after acknowledgement", () => {
  const state = queue.empty(); queue.add(state, event("a")); const sent = queue.copy(state); queue.edit(state, event("a", 3));
  queue.acknowledge(state, sent, { accepted_local_event_ids: ["a"] });
  assert.equal(state.records.length, 0); assert.equal(state.updates[0].quantity, 3); assert.equal(state.saved[0].synced, false);
});

test("a delete during an in-flight create is sent after acknowledgement", () => {
  const state = queue.empty(); queue.add(state, event("a")); const sent = queue.copy(state); queue.remove(state, "a");
  queue.acknowledge(state, sent, { accepted_local_event_ids: ["a"] });
  assert.deepEqual(state.deletes, [{ local_event_id: "a" }]);
});

test("an acknowledgement does not clear a newer pending update", () => {
  const state = queue.empty(); state.saved = [{ ...event("a"), synced: true }]; queue.edit(state, event("a", 2));
  const sent = queue.copy(state); queue.edit(state, event("a", 4));
  queue.acknowledge(state, sent, { accepted_update_local_event_ids: ["a"] });
  assert.equal(state.updates[0].quantity, 4);
});

test("server refresh does not overwrite unsynced edits or resurrect pending deletes", () => {
  const state = queue.empty(); state.saved = [{ ...event("a"), synced: true }, { ...event("b"), synced: true }];
  queue.edit(state, event("a", 7)); queue.remove(state, "b"); queue.mergeServer(state, [event("a"), event("b")]);
  assert.equal(state.saved[0].quantity, 7); assert.equal(state.saved.some((row) => row.local_event_id === "b"), false);
});
