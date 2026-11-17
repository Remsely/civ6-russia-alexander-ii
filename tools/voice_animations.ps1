# Build speech-length clips from the existing idle without retiming its curves.
param([string]$Root = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath($Root)
$dir="C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI SDK\AssetModTools\AssetEditor"
Set-Location -LiteralPath $dir
[Environment]::CurrentDirectory=$dir
[AppDomain]::CurrentDomain.add_AssemblyResolve({param($s,$e) $p=Join-Path $dir ((New-Object Reflection.AssemblyName($e.Name)).Name+'.dll');if(Test-Path -LiteralPath $p){[Reflection.Assembly]::LoadFrom($p)}})
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.dll")
[void][Reflection.Assembly]::LoadFrom("$dir\Firaxis.Granny.Impl.dll")
Add-Type -TypeDefinition @"
using System;
using System.Reflection;
using System.Runtime.InteropServices;
public static class VoiceClip {
 public static unsafe void Duration(object animation,float duration) {
  var field=animation.GetType().GetField("m_pkAnimation",BindingFlags.Instance|BindingFlags.NonPublic);
  IntPtr ptr=(IntPtr)Pointer.Unbox(field.GetValue(animation));
  float current=(float)animation.GetType().GetProperty("Duration").GetValue(animation,null);
  // SDK granny_animation packed x64: name pointer, duration, timestep.
  var bytes=new byte[4]; Marshal.Copy(ptr+8,bytes,0,4);
  if(BitConverter.ToSingle(bytes,0)!=current) throw new InvalidOperationException("Unexpected granny_animation layout");
  Marshal.Copy(BitConverter.GetBytes(duration),0,ptr+8,4);
 }
 public static double Compare(object a,object b,float end,float originalDuration) {
  var sample=a.GetType().GetMethod("Sample");double worst=0;
  for(int i=0;i<=120;i++) {
   float t=end*i/120;
   var av=(float[])sample.Invoke(a,new object[]{t,originalDuration,false,false,false});
   var bv=(float[])sample.Invoke(b,new object[]{t,end,false,false,false});
   for(int j=0;j<av.Length;j++) worst=Math.Max(worst,Math.Abs((double)av[j]-bv[j]));
  }
  return worst;
 }
}
"@ -CompilerParameters (New-Object CodeDom.Compiler.CompilerParameters -Property @{CompilerOptions='/unsafe'})
$ctx=New-Object Firaxis.Granny.GrannyContext
$token=[Guid]::NewGuid().ToString('N')
$baseFile=Join-Path ([IO.Path]::GetTempPath()) "voice_${token}_base.fgx"
$workFile=Join-Path ([IO.Path]::GetTempPath()) "voice_${token}_work.fgx"
Copy-Item -LiteralPath (Join-Path $Root 'mod/Animations/AlexanderII_Idle.fgx') -Destination $baseFile
Copy-Item -LiteralPath $baseFile -Destination $workFile
try {
 try{[void]$ctx.LoadGrannyFile($baseFile)}catch{}
 $base=$ctx.LoadGrannyFile($baseFile)
 if($base.Animations.Count -ne 1 -or $base.Animations[0].Duration -ne 16){throw 'Expected original 16-second idle'}
 foreach($description in Get-ChildItem -LiteralPath (Join-Path $Root 'mod/Animations') -Filter 'AlexanderII_Voice_*.anm') {
  [xml]$xml=Get-Content -LiteralPath $description.FullName
  $duration=[single]::Parse($xml.DocumentElement.m_fDuration,[Globalization.CultureInfo]::InvariantCulture)
  $file=$ctx.LoadGrannyFile($workFile)
  $animation=$file.Animations[0]
  [VoiceClip]::Duration($animation,$duration)
  $animation.Name=$description.BaseName
  $temporary=Join-Path ([IO.Path]::GetTempPath()) ("voice_${token}_"+$description.BaseName+'.fgx')
  $file.GetType().GetField('m_szFilename',[Reflection.BindingFlags]'Instance,NonPublic').SetValue($file,$temporary)
  if(-not $file.Save()){throw 'Granny Save failed'}
  $saved=$ctx.LoadGrannyFile($temporary)
  $a=$base.Animations[0];$b=$saved.Animations[0]
  if([Math]::Abs($b.Duration-$duration) -gt 0.00001 -or $a.TrackGroups.Count -ne $b.TrackGroups.Count){throw 'Clip metadata mismatch'}
  $worst=0.0
  for($g=0;$g -lt $a.TrackGroups.Count;$g++){
   $ag=$a.TrackGroups[$g];$bg=$b.TrackGroups[$g]
   if($ag.Name -ne $bg.Name -or $ag.TransformTracks.Count -ne $bg.TransformTracks.Count){throw 'Track group mismatch'}
   for($t=0;$t -lt $ag.TransformTracks.Count;$t++){
    $at=$ag.TransformTracks[$t];$bt=$bg.TransformTracks[$t]
    if($at.Name -ne $bt.Name){throw 'Track name mismatch'}
    foreach($curve in @('PositionCurve','OrientationCurve','ScaleShearCurve')){
     $worst=[Math]::Max($worst,[VoiceClip]::Compare($at.$curve,$bt.$curve,$duration,16))
    }
   }
  }
  if($worst -gt 0.00001){throw "Motion changed: $worst"}
  Copy-Item -LiteralPath $temporary -Destination (Join-Path $description.DirectoryName ($description.BaseName+'.fgx')) -Force
  Write-Output "$($description.BaseName): duration=$duration; original motion max error=$worst"
 }
}finally{
 $ctx.Dispose()
 # Exact temporary files created by this worker; no recursive deletion.
 Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Filter "voice_${token}_*.fgx" | Remove-Item -ErrorAction SilentlyContinue
}
