# Dump models, bones (local transforms) and animation track names of Granny .fgx files via the Asset Editor's Granny wrapper.
# powershell -File tools\dump_fgx.ps1 <file.fgx> [<file.fgx> ...] [-Bones name1,name2]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Files, [string[]]$Bones = @())
$dir = "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK\AssetModTools\AssetEditor"
Set-Location $dir
[Environment]::CurrentDirectory = $dir
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($s, $e)
    $p = Join-Path $dir ((New-Object Reflection.AssemblyName($e.Name)).Name + '.dll')
    if (Test-Path $p) { [Reflection.Assembly]::LoadFrom($p) } else { $null }
})
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.dll")
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.Impl.dll")
$ctx = New-Object Firaxis.Granny.GrannyContext
# the first load in a process returns nothing (wrapper initialisation): warm up once
if ($Files.Count) { try { [void]$ctx.LoadGrannyFile($Files[0]) } catch {} }
function F($a) { if ($a) { ($a | ForEach-Object { '{0,8:N3}' -f $_ }) -join ' ' } }
foreach ($f in $Files) {
    "##### $f"
    $g = $ctx.LoadGrannyFile($f)
    if (-not $g) { "  (failed to load)"; continue }
    foreach ($m in $g.Models) {
        $ip = $m.InitialPlacement
        "  MODEL $($m.Name)  placement pos [$(F $ip.Position)] rot [$(F $ip.Orientation)]  meshes $($m.MeshBindings.Count)"
        $bs = $m.Skeleton.Bones
        "  skeleton $($m.Skeleton.Name): $($bs.Count) bones"
        for ($i = 0; $i -lt $bs.Count; $i++) {
            $b = $bs[$i]
            if ($Bones.Count -eq 0 -or $Bones -contains $b.Name -or $bs.Count -le 6) {
                $t = $b.LocalTransform
                "    [$i] $($b.Name) parent=$($b.ParentIndex) pos [$(F $t.Position)] rot [$(F $t.Orientation)] scale [$(F $t.ScaleShear[0]) $(F $t.ScaleShear[4]) $(F $t.ScaleShear[8])]"
                "         invWorld [$(F $b.InverseWorldTransform)]"
            }
        }
    }
    foreach ($a in $g.Animations) {
        "  ANIM $($a.Name) dur $($a.Duration)"
        foreach ($tg in $a.TrackGroups) { "    trackgroup $($tg.Name): $($tg.TransformTracks.Count) tracks: $((($tg.TransformTracks | Select-Object -First 8) | ForEach-Object { $_.Name }) -join ', ')" }
    }
}
