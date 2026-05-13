const { convertCelsius } = require("./converter");
const { ABSOLUTE_ZERO_C } = require("./units");

function assertClose(actual, expected, message) {
  if (Math.abs(actual - expected) > 1e-6) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function assertThrows(fn, message) {
  try {
    fn();
  } catch (e) {
    return;
  }
  throw new Error(message);
}

function main() {
  assertClose(convertCelsius(0, "F"), 32, "0C should be 32F");
  assertClose(convertCelsius(100, "F"), 212, "100C should be 212F");
  assertClose(convertCelsius(0, "K"), 273.15, "0C should be 273.15K");
  assertClose(convertCelsius(ABSOLUTE_ZERO_C, "K"), 0, "absolute zero in K");
  assertClose(convertCelsius(25, "C"), 25, "C -> C is identity");

  assertThrows(
    () => convertCelsius(-300, "F"),
    "below absolute zero should fail",
  );

  assertThrows(
    () => convertCelsius(0, "Q"),
    "unknown unit should fail",
  );

  console.log("OK");
}

main();
