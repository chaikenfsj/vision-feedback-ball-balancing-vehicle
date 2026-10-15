param([string]$ProjectRoot = (Split-Path $PSScriptRoot -Parent), [string]$Gcc = '')
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Gcc)) {
    if ($env:ARM_GCC_ROOT) {
        $Gcc = Join-Path $env:ARM_GCC_ROOT 'bin/arm-none-eabi-gcc.exe'
    } else {
        $Gcc = (Get-Command arm-none-eabi-gcc -ErrorAction Stop).Source
    }
}
Push-Location $ProjectRoot
try {
    $testElf = Join-Path $ProjectRoot 'tests/oled_test.elf'
    & $Gcc '-mcpu=cortex-m0plus' -mthumb -O0 -g '-std=c11' -Wall -Wextra -Werror `
        -ffunction-sections -fdata-sections -nostartfiles '-specs=nosys.specs' `
        '-Wl,-e,main,-Ttext=0x1000,-Tdata=0x20000000,--gc-sections' `
        -I tests/oled_stubs -I user tests/oled_test.c user/code/oled.c -lc -o $testElf
    if ($LASTEXITCODE -ne 0) { throw 'OLED test compilation failed' }
    python -B tests/run_q5_test.py $testElf
    if ($LASTEXITCODE -ne 0) { throw 'OLED regressions failed' }
} finally { Pop-Location }
