namespace App;

public static class ScoreReport
{
    // BUG: deferred LINQ query — reflects mutations to scores made after this call
    public static IEnumerable<int> GetPassing(List<int> scores, int threshold) =>
        scores.Where(s => s >= threshold);
}
