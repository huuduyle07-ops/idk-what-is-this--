const { getDisplayName } = require("./profile");


function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}


function main() {
  assertEqual(
    getDisplayName({ profile: { name: " Ada Lovelace " } }),
    "Ada Lovelace",
    "profile name should be trimmed",
  );
  assertEqual(getDisplayName(null), "Guest", "null user should be guest");
  assertEqual(getDisplayName(undefined), "Guest", "undefined user should be guest");
  assertEqual(getDisplayName({}), "Guest", "missing profile should be guest");
  assertEqual(getDisplayName({ profile: {} }), "Guest", "missing name should be guest");
  assertEqual(getDisplayName({ profile: { name: "   " } }), "Guest", "blank name should be guest");

  console.log("OK");
}


main();
