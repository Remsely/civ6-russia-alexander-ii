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

# Mesh settings set in the exporter's dialog for geometry (captions as the dialog shows them), so that the vertices come
# out as Peter's (LEAD_RUSS_Peter.fgx): Position, BoneWeights/BoneIndices x8, Normal, Tangent, Binormal, UV x3 floats.
# The game takes only such leader vertices: the 4-bone format with tangents left the package unloaded and the game
# crashing on exit (the 14.10 test's 4 bones without tangents loaded, but rendered black with a Leader material).
$MeshSettings = @('Always use skinned format', 'Include tangent vectors', 'Include binormal vectors',
                  'Bones per vertex=8', 'Elements per coord=3')
$GrannyDialog = @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text; using System.Threading;
public static class GrannyDialog {
  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint a, bool i, uint pid);
  [DllImport("kernel32.dll")] static extern IntPtr VirtualAllocEx(IntPtr p, IntPtr a, int s, uint t, uint pr);
  [DllImport("kernel32.dll")] static extern bool VirtualFreeEx(IntPtr p, IntPtr a, int s, uint t);
  [DllImport("kernel32.dll")] static extern bool WriteProcessMemory(IntPtr p, IntPtr a, byte[] b, int s, out IntPtr w);
  [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr p, IntPtr a, byte[] b, int s, out IntPtr r);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  public static string Log = "";
  static string Cls(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }
  static string Txt(IntPtr h) { var s = new StringBuilder(1024); GetWindowText(h, s, 1024); return s.ToString(); }
  static IntPtr TopWindow(uint pid, string cls) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { if (Cls(h) == cls) { found = h; return false; }
        EnumChildWindows(h, (c, l2) => { if (Cls(c) == cls) { found = c; return false; } return true; }, IntPtr.Zero);
        if (found != IntPtr.Zero) return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
  static List<IntPtr> Children(IntPtr w) { var r = new List<IntPtr>(); EnumChildWindows(w, (c, l) => { r.Add(c); return true; }, IntPtr.Zero); return r; }
  static IntPtr Child(IntPtr w, string cls, string text) {
    foreach (var c in Children(w)) if (Cls(c) == cls && (text == null || Txt(c) == text)) return c;
    return IntPtr.Zero;
  }
  // LVITEMW (x64): mask, iItem, iSubItem, state, stateMask, pad, pszText (8), cchTextMax ... 88 bytes
  static byte[] Item(int mask, int i, int state, int stateMask, long text, int cch) {
    var b = new byte[88];
    BitConverter.GetBytes(mask).CopyTo(b, 0); BitConverter.GetBytes(i).CopyTo(b, 4);
    BitConverter.GetBytes(state).CopyTo(b, 12); BitConverter.GetBytes(stateMask).CopyTo(b, 16);
    BitConverter.GetBytes(text).CopyTo(b, 24); BitConverter.GetBytes(cch).CopyTo(b, 32); return b;
  }
  static bool SelectItem(IntPtr lv, string name) {
    uint pid; GetWindowThreadProcessId(lv, out pid); var p = OpenProcess(0x1F0FFF, false, pid);
    var mem = VirtualAllocEx(p, IntPtr.Zero, 4096, 0x3000, 4); IntPtr n; bool ok = false;
    int count = (int)SendMessage(lv, 0x1004, IntPtr.Zero, IntPtr.Zero);  // LVM_GETITEMCOUNT
    for (int i = 0; i < count && !ok; i++) {
      var it = Item(1, i, 0, 0, mem.ToInt64() + 256, 512); WriteProcessMemory(p, mem, it, it.Length, out n);
      SendMessage(lv, 0x1073, (IntPtr)i, mem);  // LVM_GETITEMTEXTW
      var buf = new byte[1024]; ReadProcessMemory(p, mem + 256, buf, buf.Length, out n);
      var s = Encoding.Unicode.GetString(buf); s = s.Substring(0, s.IndexOf('\0'));
      if (s != name) continue;
      var sel = Item(8, i, 3, 3, 0, 0); WriteProcessMemory(p, mem, sel, sel.Length, out n);
      SendMessage(lv, 0x102B, (IntPtr)i, mem);  // LVM_SETITEMSTATE: selected | focused
      ok = true;
    }
    VirtualFreeEx(p, mem, 0, 0x8000); CloseHandle(p); return ok;
  }
  [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
  static void Slide(IntPtr w, string caption, int value) {
    IntPtr bar = IntPtr.Zero; bool after = false;
    foreach (var c in Children(w)) {
      if (Cls(c) == "Static" && Txt(c) == caption) after = true;
      else if (after && Cls(c) == "msctls_trackbar32") { bar = c; break; }
    }
    if (bar == IntPtr.Zero) { Log += "no '" + caption + "'; "; return; }
    SendMessage(bar, 0x405, (IntPtr)1, (IntPtr)value);  // TBM_SETPOS, redraw
    var parent = GetParent(bar);  // tell the dialog as a drag would: WM_HSCROLL, SB_THUMBPOSITION then SB_ENDSCROLL
    SendMessage(parent, 0x114, (IntPtr)(4 | (value << 16)), bar);
    SendMessage(parent, 0x114, (IntPtr)8, bar);
    Log += caption + "=" + (int)SendMessage(bar, 0x400, IntPtr.Zero, IntPtr.Zero) + "; ";  // TBM_GETPOS
  }
  static void Tick(IntPtr w, string caption) {
    var b = Child(w, "Button", caption);
    if (b == IntPtr.Zero) { Log += "no '" + caption + "'; "; return; }
    if ((int)SendMessage(b, 0xF0, IntPtr.Zero, IntPtr.Zero) != 1) SendMessage(b, 0xF5, IntPtr.Zero, IntPtr.Zero);  // BM_GETCHECK / BM_CLICK
    Log += caption + "=" + (int)SendMessage(b, 0xF0, IntPtr.Zero, IntPtr.Zero) + "; ";
  }
  public static void Start(int pid, string category, string[] on) {
    var t = new Thread(() => {
      try {
        IntPtr w = IntPtr.Zero;
        for (int k = 0; k < 600 && w == IntPtr.Zero; k++) { Thread.Sleep(100); w = TopWindow((uint)pid, "GrannyRootSettingsWindowClass"); }
        if (w == IntPtr.Zero) { Log += "no settings dialog"; return; }
        if (!SelectItem(Child(w, "SysListView32", null), category)) { Log += "no '" + category + "'; "; return; }
        Thread.Sleep(300);
        foreach (var c in on) { var kv = c.Split('='); if (kv.Length == 2) Slide(w, kv[0], int.Parse(kv[1])); else Tick(w, c); }
        Tick(w, "Close when complete");
        PostMessage(Child(w, "Button", "Export"), 0xF5, IntPtr.Zero, IntPtr.Zero);  // the export runs in the dialog's thread
        Log += "exported";
      } catch (Exception e) { Log += e.Message; }
    });
    t.IsBackground = true; t.Start();
  }
}
"@

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
        # ExportGeometry runs the exporter with its default mesh settings, which suit no leader: no tangents or binormals
        # (the Leader materials rendered black) and meshes with one bone written rigid (the whole leader package then
        # failed to load). Those settings exist only in the exporter's dialog, so the same native call is made with the
        # dialog shown and a helper thread ticks them in it (Meshes) and presses Export.
        $export = $impl.ManifestModule.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static') |
            Where-Object { $_.Name -eq 'ExportFBXScene' } | Select-Object -First 1
        Add-Type -TypeDefinition $GrannyDialog
        [GrannyDialog]::Start($PID, 'Meshes', [string[]]$MeshSettings)
        $ok = $export.Invoke($null, [object[]]@([string]$Fbx, [string]$Node, [IO.Path]::Combine($Out, "$Name.fgx"), $true, $true, $form.Handle))
        "ExportFBXScene '$Node' -> $Out\$Name.fgx : $ok; dialog: $([GrannyDialog]::Log)"
        if (-not $ok -or [GrannyDialog]::Log -notmatch 'exported') { throw "geometry export failed: $([GrannyDialog]::Log)" }
        $r = $fbxi.ExportWIG($Fbx, $Out, $Node, $Name)
        "ExportWIG '$Node' -> $Out\$Name.wig : $r"
    }
}
