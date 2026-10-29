const test = require("node:test");
const assert = require("node:assert/strict");
const { parseId, clearStorage } = require("../cutting/public/js/device-core.js");

const ID = "72A618ED-61A7-4AC1-8A9F-1C1072400000";

test("QR parser accepts UUID, Admin JSON and URL forms", () => {
  for (const input of [
    ID,
    JSON.stringify({ id: ID, deviceName: "Tablet" }),
    JSON.stringify({ deviceId: ID }),
    `https://example.invalid/device?id=${ID}`,
    `https://example.invalid/device?deviceId=${ID}`,
  ]) assert.equal(parseId(input), ID.toLowerCase());
  for (const input of ["", "Test", "{bad", "https://example.invalid/device?id=bad"])
    assert.equal(parseId(input), "");
});

test("clear cache removes Cutting data, including queues, and preserves other apps", () => {
  const data = new Map([
    ["cutting.device", ID], ["cutting.queue." + ID, "unsynced"],
    ["cutting.catalog." + ID, "catalog"], ["factory_management.device", "keep"],
  ]);
  const storage = {
    get length() { return data.size; },
    key(index) { return [...data.keys()][index]; },
    removeItem(key) { data.delete(key); },
  };
  assert.equal(clearStorage(storage).length, 3);
  assert.deepEqual([...data.entries()], [["factory_management.device", "keep"]]);
});
