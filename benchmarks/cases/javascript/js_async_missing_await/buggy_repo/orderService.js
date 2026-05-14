const { hasEnoughStock } = require("./inventoryApi");

async function checkout(itemId, quantity) {
  // BUG: missing await, so Promise is treated as truthy.
  const ok = hasEnoughStock(itemId, quantity);

  if (!ok) {
    return { ok: false, error: "insufficient stock" };
  }

  return { ok: true, itemId, quantity };
}

module.exports = { checkout };
