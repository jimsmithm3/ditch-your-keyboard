# Probe: does Windows speech recognize the gspraudio command grammar from the default mic?
#
# Usage (from the project folder):
#   .\.venv\Scripts\python.exe -m app.wsapi_grammar --out $env:TEMP\gspraudio_commands.srgs.xml
#   powershell -ExecutionPolicy Bypass -File scripts\wsapi_probe.ps1 -Grammar $env:TEMP\gspraudio_commands.srgs.xml
#
# Speak a phrase from the list (for example "eight iron"). Each recognized phrase prints
# with its confidence. Recognize() returns nothing on timeout, so silence prints nothing.

param(
    [Parameter(Mandatory = $true)] [string] $Grammar,
    [int] $Seconds = 30
)

Add-Type -AssemblyName System.Speech
$culture = [System.Globalization.CultureInfo]::new("en-US")
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine $culture
try {
    $engine.LoadGrammar((New-Object System.Speech.Recognition.Grammar $Grammar))
    $engine.SetInputToDefaultAudioDevice()
    Write-Host "Listening for $Seconds seconds. Speak a phrase from the list."
    $end = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $end) {
        $result = $engine.Recognize([TimeSpan]::FromSeconds(2))
        if ($result) {
            "{0}  (confidence {1:N2})" -f $result.Text, $result.Confidence
        }
    }
    Write-Host "Done."
}
finally {
    $engine.Dispose()
}
