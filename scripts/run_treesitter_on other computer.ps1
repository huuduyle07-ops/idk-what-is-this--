param(
    [Parameter(Mandatory = $true)]
    [string]$Language,

    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [string]$EnvName = "ts_312"
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ParserScript = Join-Path $ProjectRoot "core\treesitter_parse.py"

if (!(Test-Path $ParserScript)) {
    Write-Error "Cannot find parser script: $ParserScript"
    exit 1
}

Push-Location $ProjectRoot

try {
    conda run -n $EnvName python $ParserScript $Language $FilePath
}
finally {
    Pop-Location
}