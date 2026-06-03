namespace App;

public static class DataService
{
    public static Task<int> GetCountAsync() => Task.FromResult(42);

    public static async Task<string> SummarizeAsync()
    {
        // BUG: missing await — count is Task<int>, not int
        var count = GetCountAsync();
        return $"Total: {count}";
    }
}


