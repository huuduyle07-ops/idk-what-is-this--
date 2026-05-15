function topScores(scores, limit) {
  if (limit <= 0) {
    return [];
  }

  // BUG: Array.prototype.sort mutates the caller's scores array.
  return scores.sort((left, right) => right - left).slice(0, limit);
}

module.exports = { topScores };
