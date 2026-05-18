const STOCK = {
  keyboard: 3,
  mouse: 10,
};

async function hasEnoughStock(itemId, quantity) {
  await new Promise((resolve) => setTimeout(resolve, 1));
  return (STOCK[itemId] || 0) >= quantity;
}

module.exports = { hasEnoughStock };
