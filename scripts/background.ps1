param([ValidateSet('install', 'uninstall', 'start', 'stop', 'status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $appRoot '.venv\Scripts\pythonw.exe'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'ECO Native Studio.lnk'

function Get-AppProcess {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" | Where-Object {
        $_.ExecutablePath -eq $python -and $_.CommandLine -match '-m\s+backend\.background(?:\s|$)'
    }
}

switch ($Action) {
    'install' {
        if (!(Test-Path $python) -or !(Test-Path (Join-Path $appRoot 'dist\frontend\index.html'))) {
            throw 'Instale as dependencias e execute npm run build:frontend primeiro.'
        }
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $python
        $shortcut.Arguments = '-m backend.background'
        $shortcut.WorkingDirectory = $appRoot
        $shortcut.Description = 'Servidor local ECO Native Studio em segundo plano'
        $shortcut.Save()
        & $PSCommandPath -Action start
        Write-Output 'Inicio automatico configurado para o login deste usuario no Windows.'
    }
    'uninstall' {
        if (Test-Path $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
        Write-Output 'Inicio automatico removido. Use stop para parar o servidor atual.'
    }
    'start' {
        if (!(Get-AppProcess)) {
            Start-Process -FilePath $python -ArgumentList '-m backend.background' -WorkingDirectory $appRoot -WindowStyle Hidden
        }
        Write-Output 'Servidor iniciado em segundo plano: http://127.0.0.1:18765'
    }
    'stop' {
        Get-AppProcess | ForEach-Object { Stop-Process -Id $_.ProcessId }
        Write-Output 'Servidor em segundo plano parado.'
    }
    'status' {
        [pscustomobject]@{ Autostart = (Test-Path $shortcutPath); ProcessIds = @(Get-AppProcess | ForEach-Object { $_.ProcessId }) }
    }
}
