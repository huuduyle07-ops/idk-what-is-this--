const { checkout } = require("./orderService");


function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}


async function main() {
  const valid = await checkout("keyboard", 2);
  assertEqual(valid.ok, true, "sufficient stock should checkout");

  const invalid = await checkout("keyboard", 5);
  assertEqual(invalid.ok, false, "insufficient stock should fail");
  assertEqual(invalid.error, "insufficient stock", "should return stock error");

  const missing = await checkout("unknown-item", 1);
  assertEqual(missing.ok, false, "missing item should fail as insufficient stock");

  console.log("OK");
}


main().catch((err) => {
  console.error(err);
  process.exit(1);
});
