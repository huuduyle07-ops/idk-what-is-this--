namespace App;

class Program
{
    static async Task Main()
    {
        var result = await DataService.SummarizeAsync();
        if (result != "Total: 42")
        {
            Console.Error.WriteLine($"FAIL: expected 'Total: 42', got '{result}'");
            Environment.Exit(1);
        }
        Console.WriteLine("OK");
    }
}
