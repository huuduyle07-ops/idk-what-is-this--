const { topScores } = require("./leaderboard");


function assertDeepEqual(actual, expected, message) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    throw new Error(`${message}: expected ${expectedJson}, got ${actualJson}`);
  }
}


function main() {
  const scores = [12, 30, 18, 30, 5];
  const original = scores.slice();

  assertDeepEqual(topScores(scores, 3), [30, 30, 18], "top three scores should be sorted");
  assertDeepEqual(scores, original, "input scores should not be mutated");
  assertDeepEqual(topScores(scores, 10), [30, 30, 18, 12, 5], "large limit should return all scores");
  assertDeepEqual(topScores(scores, 0), [], "zero limit should return empty list");

  console.log("OK");
}


main();
