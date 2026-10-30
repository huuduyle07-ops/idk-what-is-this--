param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][ValidateRange(1, 300)][int]$SlideIndex,
    [ValidateRange(1, 1800)][int]$MaxEdge = 1800
)

# This helper receives only a preflighted temporary OOXML copy from Python.
# Do not attach to, close, save, or quit a user's Office presentation/application.
$ErrorActionPreference = 'Stop'
# Creating a COM object can attach to a user's existing PowerPoint server.
# Refuse before touching its settings, including when a previous render hangs.
# A preceding owned server may still be exiting just after its helper ends.
# Wait read-only for at most one second; never attach to or stop that process.
for ($waitAttempt = 0; $waitAttempt -lt 10; $waitAttempt++) {
    if (-not (Get-Process -Name POWERPNT -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 100
}
if (Get-Process -Name POWERPNT -ErrorAction SilentlyContinue) { exit 3 }
$presentation = $null
$application = $null
$slide = $null
$previousSecurity = $null
$sharedApplication = $false
$ownedApplication = $false
$resultCode = 1
try {
    $application = New-Object -ComObject PowerPoint.Application
    if ($application.Visible -ne 0 -or $application.Presentations.Count -ne 0) {
        $sharedApplication = $true
        throw 'PowerPoint is already in use.'
    }
    $ownedApplication = $true
    $previousSecurity = $application.AutomationSecurity
    $application.AutomationSecurity = 3 # msoAutomationSecurityForceDisable
    # ReadOnly=true, Untitled=false, WithWindow=false. Source is a temporary copy.
    $presentation = $application.Presentations.Open($InputPath, -1, 0, 0)
    if ($SlideIndex -gt $presentation.Slides.Count) { throw 'Invalid slide index.' }
    $slide = $presentation.Slides.Item($SlideIndex)
    $slideWidth = [double]$presentation.PageSetup.SlideWidth
    $slideHeight = [double]$presentation.PageSetup.SlideHeight
    if ($slideWidth -le 0 -or $slideHeight -le 0) { throw 'Invalid slide dimensions.' }
    $ratio = $MaxEdge / [math]::Max($slideWidth, $slideHeight)
    $renderWidth = [math]::Max(1, [int][math]::Round($slideWidth * $ratio))
    $renderHeight = [math]::Max(1, [int][math]::Round($slideHeight * $ratio))
    $slide.Export($OutputPath, 'PNG', $renderWidth, $renderHeight)
    if (-not [System.IO.File]::Exists($OutputPath)) { throw 'No exported slide.' }
    $resultCode = 0
}
catch {
    # Renderer internals and local paths must not appear in the web response.
    if ($null -eq $application -or $sharedApplication) { $resultCode = 3 } else { $resultCode = 1 }
}
finally {
    if ($null -ne $slide) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($slide) }
    if ($null -ne $presentation) {
        try { $presentation.Close() } catch {}
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
    }
    if ($null -ne $application) {
        # A user may have opened a file while our export ran. Never quit that app.
        if ($null -ne $previousSecurity) { try { $application.AutomationSecurity = $previousSecurity } catch {} }
        if ($ownedApplication) {
            try {
                if ($application.Visible -eq 0 -and $application.Presentations.Count -eq 0) {
                    $application.Quit()
                }
            } catch {}
        }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($application)
    }
    $slide = $null
    $presentation = $null
    $application = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
exit $resultCode
