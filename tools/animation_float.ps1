# Diagnostic alternative representation of an existing animation, not a change to its motion.
# Run in a fresh Windows PowerShell process (the SDK uses .NET Framework):
# powershell -NoProfile -File tools/animation_float.ps1 -Animation input.fgx -Out output.fgx
# Leaves constants/identities alone; expands animated curves to DaK32fC32f with the SAME knots,
# controls and degree. GrannyFile.CompressAnimations only handles keyframed input, not these splines.
param(
    [Parameter(Mandatory = $true)][string]$Animation,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$Animation = (Resolve-Path -LiteralPath $Animation).Path
$Out = [IO.Path]::GetFullPath($Out)
if ($Animation -eq $Out) { throw 'Use a separate output file; keep the original animation for comparison.' }
$dir = "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK\AssetModTools\AssetEditor"
Set-Location -LiteralPath $dir
[Environment]::CurrentDirectory = $dir
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($s, $e)
    $p = Join-Path $dir ((New-Object Reflection.AssemblyName($e.Name)).Name + '.dll')
    if (Test-Path -LiteralPath $p) { [Reflection.Assembly]::LoadFrom($p) } else { $null }
})
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.dll")
$impl = [Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.Impl.dll")
Add-Type -TypeDefinition @"
using System;
using System.Reflection;
using System.Runtime.InteropServices;
public static class AnimationFloat {
    // These allocations must outlive Granny's Save and validation. This short-lived worker owns them.
    static System.Collections.Generic.List<IntPtr> buffers = new System.Collections.Generic.List<IntPtr>();
    static IntPtr Alloc(int n) { var p = Marshal.AllocHGlobal(n); buffers.Add(p); return p; }
    static unsafe IntPtr CurvePointer(object c) {
        var f = c.GetType().GetField("m_pkCurve", BindingFlags.Instance | BindingFlags.NonPublic);
        return (IntPtr)Pointer.Unbox(f.GetValue(c));
    }
    static unsafe IntPtr FloatType(Module mod) {
        var f = mod.GetField("GrannyCurveDataDaK32fC32fType", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        return (IntPtr)Pointer.Unbox(f.GetValue(null));
    }
    static void CheckLayout(IntPtr type) {
        string[] expected = { "CurveDataHeader_DaK32fC32f", "Padding", "Knots", "Controls" };
        for (int i = 0; i < expected.Length; i++) {
            var d = type + 44 * i;
            string name = Marshal.PtrToStringAnsi(Marshal.ReadIntPtr(d, 4));
            if (name != expected[i]) throw new InvalidOperationException("Unsupported Granny curve layout: " + name);
        }
        if (Marshal.ReadInt32(type + 44 * 4) != 0) throw new InvalidOperationException("Unexpected Granny curve fields");
    }
    public static unsafe void Expand(object curve, Module mod, int count, int dim, int degree) {
        IntPtr cp = CurvePointer(curve), type = FloatType(mod);
        CheckLayout(type);
        MethodInfo extract = null;
        foreach (var m in mod.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            if (m.Name == "GrannyCurveExtractKnotValues") { extract = m; break; }
        if (extract == null) throw new MissingMethodException("GrannyCurveExtractKnotValues");
        IntPtr knots = Alloc(count * 4), controls = Alloc(count * dim * 4), identity = Alloc(dim * 4);
        float[] ident = new float[dim];
        if (dim == 4) ident[3] = 1;
        if (dim == 9) ident[0] = ident[4] = ident[8] = 1;
        Marshal.Copy(ident, 0, identity, dim);
        var pars = extract.GetParameters();
        extract.Invoke(null, new object[] {
            Pointer.Box(cp.ToPointer(), pars[0].ParameterType), 0, count,
            Pointer.Box(knots.ToPointer(), pars[3].ParameterType),
            Pointer.Box(controls.ToPointer(), pars[4].ParameterType),
            Pointer.Box(identity.ToPointer(), pars[5].ParameterType)
        });
        // SDK's packed layout: 2-byte header + 2-byte padding, then two count/pointer arrays.
        IntPtr data = Alloc(28);
        Marshal.WriteInt32(data, 0, 1 | (degree << 8)); // DaK32fC32f format = 1
        Marshal.WriteInt32(data, 4, count); Marshal.WriteIntPtr(data, 8, knots);
        Marshal.WriteInt32(data, 16, count * dim); Marshal.WriteIntPtr(data, 20, controls);
        Marshal.WriteIntPtr(cp, 0, type); Marshal.WriteIntPtr(cp, 8, data);
    }
    public static double Compare(object a, object b, float duration, int samples) {
        var ma = a.GetType().GetMethod("Sample"); var mb = b.GetType().GetMethod("Sample");
        double error = 0;
        for (int i = 0; i < samples; i++) {
            object[] args = { duration * i / (samples - 1), duration, false, false, false };
            var av = (float[])ma.Invoke(a, args); var bv = (float[])mb.Invoke(b, args);
            if (av.Length != bv.Length) throw new InvalidOperationException("Curve dimension changed");
            for (int j = 0; j < av.Length; j++) {
                if (float.IsNaN(bv[j]) || float.IsInfinity(bv[j])) throw new InvalidOperationException("Non-finite curve");
                error = Math.Max(error, Math.Abs((double)av[j] - bv[j]));
            }
        }
        return error;
    }
}
"@ -CompilerParameters (New-Object CodeDom.Compiler.CompilerParameters -Property @{CompilerOptions='/unsafe'})

$token = [Guid]::NewGuid().ToString('N')
$tmpIn = Join-Path ([IO.Path]::GetTempPath()) "animation_float_${token}_in.fgx"
$tmpOut = Join-Path ([IO.Path]::GetTempPath()) "animation_float_${token}_out.fgx"
Copy-Item -LiteralPath $Animation -Destination $tmpIn
$ctx = New-Object Firaxis.Granny.GrannyContext
try {
    try { [void]$ctx.LoadGrannyFile($tmpIn) } catch {} # wrapper's first load needs warm-up
    $file = $ctx.LoadGrannyFile($tmpIn)
    if (-not $file -or $file.Animations.Count -ne 1) { throw 'Expected exactly one animation' }
    $curves = @('PositionCurve', 'OrientationCurve', 'ScaleShearCurve')
    $converted = 0
    foreach ($group in $file.Animations[0].TrackGroups) {
        foreach ($track in $group.TransformTracks) {
            foreach ($name in $curves) {
                $c = $track.$name
                if ($c.KnotCount -gt 1) {
                    [AnimationFloat]::Expand($c, $impl.ManifestModule, $c.KnotCount, $c.Dimension, $c.Degree)
                    $converted++
                }
            }
        }
    }
    # Loading holds the input file open; Save must target a different file.
    $file.GetType().GetField('m_szFilename', [Reflection.BindingFlags]'Instance,NonPublic').SetValue($file, $tmpOut)
    if (-not $file.Save()) { throw 'Granny Save failed' }
    $original = $ctx.LoadGrannyFile($tmpIn)
    $saved = $ctx.LoadGrannyFile($tmpOut)
    $a = $original.Animations[0]; $b = $saved.Animations[0]
    if ($a.Duration -ne $b.Duration -or $a.TrackGroups.Count -ne $b.TrackGroups.Count) { throw 'Animation metadata changed' }
    $worst = 0.0; $tracks = 0; $samples = [int][Math]::Ceiling($a.Duration * 60) + 1
    for ($g = 0; $g -lt $a.TrackGroups.Count; $g++) {
        $ag = $a.TrackGroups[$g]; $bg = $b.TrackGroups[$g]
        if ($ag.Name -ne $bg.Name -or $ag.TransformTracks.Count -ne $bg.TransformTracks.Count) { throw 'Track group changed' }
        for ($t = 0; $t -lt $ag.TransformTracks.Count; $t++) {
            $at = $ag.TransformTracks[$t]; $bt = $bg.TransformTracks[$t]; $tracks++
            if ($at.Name -ne $bt.Name) { throw 'Track name changed' }
            foreach ($name in $curves) {
                $worst = [Math]::Max($worst, [AnimationFloat]::Compare($at.$name, $bt.$name, $a.Duration, $samples))
            }
        }
    }
    if ($worst -gt 0.00001) { throw "Motion changed: max component error $worst" }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Out)) | Out-Null
    Copy-Item -LiteralPath $tmpOut -Destination $Out -Force
    "animation_float: $converted curves expanded, $tracks tracks checked at $samples times; max error $worst -> $Out"
} finally {
    $ctx.Dispose()
    foreach ($p in @($tmpIn, $tmpOut)) { Remove-Item -LiteralPath $p -ErrorAction SilentlyContinue }
}
