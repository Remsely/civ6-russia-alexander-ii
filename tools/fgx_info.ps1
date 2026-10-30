# What a geometry .fgx holds, as JSON (what the Asset Editor writes into the .geo on import): the model name, its
# skeleton's bones in order, and per mesh the vertex, triangle and bound-bone counts and the triangle groups' materials.
# The Granny wrapper asks the Asset Editor's services for LOD settings while it opens a model; without the editor
# running they are null, so they are stubbed (empty answers: the wrapper then takes its defaults).
#
# powershell -STA -ExecutionPolicy Bypass -File tools\fgx_info.ps1 -Fgx <file.fgx> -Out <file.json>
param([Parameter(Mandatory = $true)][string]$Fgx, [Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = 'Stop'
$dir = "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK\AssetModTools\AssetEditor"
$Fgx = (Resolve-Path $Fgx).Path
$Out = [IO.Path]::GetFullPath($Out)
# the wrapper reads no path with an apostrophe ("Sid Meier's"): a copy in the temp folder
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("fgx_info_" + [IO.Path]::GetFileName($Fgx))
Copy-Item $Fgx $tmp -Force
Set-Location $dir
[Environment]::CurrentDirectory = $dir
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($s, $e)
    $p = Join-Path $dir ((New-Object Reflection.AssemblyName($e.Name)).Name + '.dll')
    if (Test-Path $p) { [Reflection.Assembly]::LoadFrom($p) } else { $null }
})
$ct = [Reflection.Assembly]::LoadFrom("$dir\Firaxis.CivTech.dll")
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.dll")
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.Impl.dll")
Add-Type -TypeDefinition @"
using System; using System.Reflection; using System.Linq.Expressions;
using System.Runtime.Remoting.Proxies; using System.Runtime.Remoting.Messaging;
public class FgxInfoStub : RealProxy {
  public FgxInfoStub(Type t) : base(t) {}
  public override IMessage Invoke(IMessage msg) {
    var m = (IMethodCallMessage)msg; var mi = (MethodInfo)m.MethodBase;
    if (mi.Name == "GetType") return new ReturnMessage(GetProxiedType(), null, 0, m.LogicalCallContext, m);
    object r = null; var rt = mi.ReturnType;
    if (rt.IsArray) r = Array.CreateInstance(rt.GetElementType(), 0);
    else if (rt.IsGenericType && rt.GetGenericTypeDefinition() == typeof(System.Collections.Generic.IEnumerable<>))
      r = Array.CreateInstance(rt.GetGenericArguments()[0], 0);
    else if (rt == typeof(string)) r = "";
    else if (rt.IsValueType && rt != typeof(void)) r = Activator.CreateInstance(rt);
    return new ReturnMessage(r, null, 0, m.LogicalCallContext, m);
  }
  public static void Install(Type reg) {
    foreach (var f in reg.GetFields(BindingFlags.NonPublic | BindingFlags.Static)) {
      if (!f.Name.StartsWith("s_")) continue;
      var iface = f.FieldType.GetGenericArguments()[0];
      object proxy = new FgxInfoStub(iface).GetTransparentProxy();
      var ft = typeof(Func<>).MakeGenericType(iface);
      var lam = Expression.Lambda(ft, Expression.Convert(Expression.Constant(proxy, typeof(object)), iface)).Compile();
      f.SetValue(null, Activator.CreateInstance(f.FieldType, new object[] { lam }));
    }
  }
}
"@
[FgxInfoStub]::Install($ct.GetType('Firaxis.CivTech.CivTechRegistry'))
$ctx = New-Object Firaxis.Granny.GrannyContext
# the first load in a process returns nothing (wrapper initialisation): warm up once
try { [void]$ctx.LoadGrannyFile($tmp) } catch {}
$g = $ctx.LoadGrannyFile($tmp)
$model = @($g.Models)[0]
$info = [ordered]@{
    model  = $model.Name
    bones  = @($model.Skeleton.Bones | ForEach-Object { $_.Name })
    # The file's mesh collection is NOT the model's binding order. The cooker builds
    # behavior_desc palettes from Model.MeshBindings, but render-node offsets from
    # the GEO/AST order. Using g.Meshes reversed all ten palettes in Alexander II.
    meshes = @($model.MeshBindings | ForEach-Object {
        [ordered]@{
            name        = $_.Name
            verts       = $_.VertexCount
            tris        = $_.IndexCount / 3
            bound_bones = @($_.BoneBindings).Count
            bound       = @($_.BoneBindings | ForEach-Object { "$_" })
            groups      = @($_.MaterialBindings | ForEach-Object { "$($_.Name)" })
        }
    })
}
[IO.File]::WriteAllText($Out, ($info | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
try { Remove-Item $tmp -ErrorAction Stop } catch {}  # the wrapper may still hold it; the temp folder keeps it
"fgx_info: $($info.model), $($info.bones.Count) bones, $($info.meshes.Count) meshes -> $Out"
