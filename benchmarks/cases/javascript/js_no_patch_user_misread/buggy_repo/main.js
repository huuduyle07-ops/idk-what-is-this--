const { formatTemperature } = require('./formatter');

function assertEqual(actual, expected, msg) {
    if (actual !== expected) {
        throw new Error(msg + ': expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual));
    }
}

assertEqual(formatTemperature(0), "0.0°C", "zero celsius");
assertEqual(formatTemperature(100), "100.0°C", "boiling point");
assertEqual(formatTemperature(36.6), "36.6°C", "body temperature");
assertEqual(formatTemperature(-10), "-10.0°C", "sub-zero");

console.log("OK");
