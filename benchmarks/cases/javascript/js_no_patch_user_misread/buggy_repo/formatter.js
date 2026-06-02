function formatTemperature(celsius) {
    // Returns temperature with exactly one decimal place, e.g. "36.6°C".
    return celsius.toFixed(1) + "°C";
}

module.exports = { formatTemperature };
