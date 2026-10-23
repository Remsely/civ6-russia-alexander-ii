# Convert FBX to Granny .fgx (+ .wig for geometry) with the Asset Editor's own FBX importer, without the Asset Editor.
# The Asset Editor's import of FBX *animations* writes the .fgx and then crashes (FiraxisGeometryExporter treats the
# animation as geometry in ParseWigFiles); calling the importer directly avoids that and needs no restarts.
#
# powershell -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <file.fbx> -Out <folder> -Name <fgx name> -Mode Animation [-Node <root node>]
# powershell -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <file.fbx> -Out <folder> -Name <fgx name> -Mode Geometry -Node <root node>
# powershell -ExecutionPolicy Bypass -File tools\fbx_to_fgx.ps1 -Fbx <file.fbx> -Mode List
param(
    [Parameter(Mandatory = $true)][string]$Fbx,
    [ValidateSet('Animation', 'Geometry', 'List')][string]$Mode = 'List',
    [string]$Out,
    [string]$Name,
    [string]$Node
)
$ErrorActionPreference = 'Stop'
$dir = "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK\AssetModTools\AssetEditor"
$Fbx = (Resolve-Path $Fbx).Path
if ($Out) { New-Item -ItemType Directory -Force $Out | Out-Null; $Out = (Resolve-Path $Out).Path }
Set-Location $dir
[Environment]::CurrentDirectory = $dir
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($s, $e)
    $p = Join-Path $dir ((New-Object Reflection.AssemblyName($e.Name)).Name + '.dll')
    if (Test-Path $p) { [Reflection.Assembly]::LoadFrom($p) } else { $null }
})
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.CivTech.dll")
$impl = [Reflection.Assembly]::LoadFrom("$dir\Firaxis.CivTech.Impl.dll")
$fbxi = [Activator]::CreateInstance($impl.GetType('Firaxis.CivTech.Autodesk_FBXInterface'))
# The exporters parent a progress dialog to the first visible form (FindFirstVisibleForm) and crash without one.
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = 'fbx_to_fgx'; $form.ShowInTaskbar = $false; $form.StartPosition = 'Manual'
$form.Location = New-Object System.Drawing.Point(-2000, -2000); $form.Size = New-Object System.Drawing.Size(10, 10)
$form.Show()

switch ($Mode) {
    'List' {
        "root models: $(@($fbxi.GetRootModels($Fbx)) -join ', ')"
        "meshes:      $(@($fbxi.GetMeshes($Fbx)) -join ', ')"
        "animations:  $(@($fbxi.GetAnimations($Fbx)) -join ', ')"
    }
    'Animation' {
        # -Node is the root model, not the take: with the take name the .fgx gets no track groups and nothing moves.
        # The track group is named after the root; it must match the body geometry's model name (Peter: Root/Root).
        if (-not $Node) { $Node = @($fbxi.GetRootModels($Fbx))[0] }
        $r = $fbxi.ExportAnimation($Fbx, $Out, $Node, $Name)  # the importer appends .fgx itself
        "ExportAnimation '$Node' -> $Out\$Name.fgx : $r"
    }
    'Geometry' {
        $r = $fbxi.ExportGeometry($Fbx, $Out, $Node, $Name)
        "ExportGeometry '$Node' -> $Out\$Name.fgx : $r"
        $r = $fbxi.ExportWIG($Fbx, $Out, $Node, $Name)
        "ExportWIG '$Node' -> $Out\$Name.wig : $r"
    }
}
