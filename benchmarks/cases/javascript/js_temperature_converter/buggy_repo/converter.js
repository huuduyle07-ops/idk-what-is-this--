const { SUPPORTED_UNITS } = require("./units");

function convertCelsius(celsius, toUnit) {
  // BUG: accepts values below absolute zero and unknown target units.
  if (toUnit === "F") {
    return celsius * 9 / 5 + 32;
  }
  if (toUnit === "K") {
    return celsius + 273.15;
  }
  return celsius;
}

module.exports = { convertCelsius };
