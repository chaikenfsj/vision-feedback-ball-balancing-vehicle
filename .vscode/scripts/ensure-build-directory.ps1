param(
    [Parameter(Mandatory = $true)][string]$WorkspaceFolder,
    [string]$CMake = 'cmake'
)
$ErrorActionPreference = 'Stop'
$workspacePath = (Resolve-Path -LiteralPath $WorkspaceFolder).ProviderPath.TrimEnd('\', '/')
$buildPath = Join-Path $workspacePath 'build'
$cachePath = Join-Path $buildPath 'CMakeCache.txt'

if (Test-Path -LiteralPath $cachePath) {
    $cacheHome = Select-String -LiteralPath $cachePath -Pattern '^CMAKE_HOME_DIRECTORY:INTERNAL=(.*)$'
    $cacheBuild = Select-String -LiteralPath $cachePath -Pattern '^CMAKE_CACHEFILE_DIR:INTERNAL=(.*)$'
    $sourceMatches = $cacheHome -and
        ($cacheHome.Matches[0].Groups[1].Value.Replace('/', '\').TrimEnd('\') -ieq $workspacePath)
    $buildMatches = $cacheBuild -and
        ($cacheBuild.Matches[0].Groups[1].Value.Replace('/', '\').TrimEnd('\') -ieq $buildPath)
    if (-not $sourceMatches -or -not $buildMatches) {
        Write-Host 'Project moved: regenerating CMake metadata; keeping other build files.'
        # Delete only generated metadata; keep build/testdeps and repair backups.
        $buildItem = Get-Item -LiteralPath $buildPath
        if ($buildItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing to clean a linked build directory: $buildPath"
        }
        foreach ($metadataName in @('CMakeCache.txt', 'CMakeFiles')) {
            $metadataPath = Join-Path $buildPath $metadataName
            if (Test-Path -LiteralPath $metadataPath) {
                $metadataItem = Get-Item -LiteralPath $metadataPath
                if ($metadataItem.FullName -ine $metadataPath -or
                    ($metadataItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                    throw "Unexpected CMake metadata path: $metadataPath"
                }
                Remove-Item -LiteralPath $metadataPath -Recurse -Force
            }
        }
    }
}

# Configure each time to apply changes to CMakeLists/presets.
& $CMake --preset debug-armgcc -S $workspacePath
exit $LASTEXITCODE
