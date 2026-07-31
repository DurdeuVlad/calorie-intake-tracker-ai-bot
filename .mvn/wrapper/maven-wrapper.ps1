param([Parameter(ValueFromRemainingArguments = $true)][string[]]$MavenArguments)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$properties = Get-Content (Join-Path $PSScriptRoot 'maven-wrapper.properties')
$url = ($properties | Where-Object { $_ -like 'distributionUrl=*' }).Substring('distributionUrl='.Length)
$sha512 = ($properties | Where-Object { $_ -like 'distributionSha512=*' }).Substring('distributionSha512='.Length)
$fileName = Split-Path $url -Leaf
$version = ($fileName -replace '^apache-maven-', '' -replace '-bin\.zip$', '')
$cache = Join-Path $env:USERPROFILE ('.m2\wrapper\dists\apache-maven-' + $version)
$mavenHome = Join-Path $cache ('apache-maven-' + $version)
if (-not (Test-Path (Join-Path $mavenHome 'bin\mvn.cmd'))) {
  New-Item -ItemType Directory -Force -Path $cache | Out-Null
  $zip = Join-Path $cache $fileName
  Invoke-WebRequest -Uri $url -OutFile $zip
  if ((Get-FileHash -Algorithm SHA512 -LiteralPath $zip).Hash.ToLowerInvariant() -ne $sha512.ToLowerInvariant()) { Remove-Item -LiteralPath $zip; throw 'Maven distribution checksum mismatch.' }
  Expand-Archive -Path $zip -DestinationPath $cache -Force
  Remove-Item -LiteralPath $zip
}
& (Join-Path $mavenHome 'bin\mvn.cmd') @MavenArguments
exit $LASTEXITCODE
