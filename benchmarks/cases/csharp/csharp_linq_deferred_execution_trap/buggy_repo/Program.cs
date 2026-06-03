namespace App;

class Program
{
    static void Main()
    {
        var scores = new List<int> { 50, 60, 70, 80 };
        var passing = ScoreReport.GetPassing(scores, 60);

        // Mutate the source after calling GetPassing
        scores.Add(100);

        // Deferred execution: if not materialized, reflects the mutation → count = 4
        var count = passing.Count();
        if (count != 3)
        {
            Console.Error.WriteLine($"FAIL: expected 3 passing scores, got {count}");
            Environment.Exit(1);
        }
        Console.WriteLine("OK");
    }
}
