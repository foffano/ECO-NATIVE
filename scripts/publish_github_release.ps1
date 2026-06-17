param(
    [string]$Version = "0.1.26",
    [string]$ReleaseDir = "$env:USERPROFILE\ECO-NATIVE-release"
)

if (-not $env:GH_TOKEN) {
    throw 'Defina GH_TOKEN com um Personal Access Token do GitHub (escopo repo).'
}

$tag = "v$Version"
$headers = @{
    Authorization              = "Bearer $env:GH_TOKEN"
    Accept                       = "application/vnd.github+json"
    "X-GitHub-Api-Version"       = "2022-11-28"
}

$releaseBody = @"
## Resumo
- Corrige erro ao abrir: stdio invalido ao iniciar a API local (v0.1.25)
- Mantem encerramento de processos eco-native-api orfaos e log em backend.log

## Test plan
- [ ] Abrir o app instalado e confirmar que a janela aparece
- [ ] Verificar health em http://127.0.0.1:8765/health
- [ ] Atualizar via auto-update de 0.1.25 para 0.1.26
"@

$releasePayload = @{
    tag_name = $tag
    name     = $Version
    body     = $releaseBody
    draft    = $false
    prerelease = $false
} | ConvertTo-Json

$release = $null
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/foffano/ECO-NATIVE/releases/tags/$tag" -Headers $headers -Method Get
    Write-Host "Release $tag ja existe (id $($release.id))."
} catch {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/foffano/ECO-NATIVE/releases" -Headers $headers -Method Post -Body $releasePayload -ContentType "application/json; charset=utf-8"
    Write-Host "Release $tag criada (id $($release.id))."
}

function Upload-ReleaseAsset {
    param(
        [object]$Release,
        [string]$FilePath
    )
    if (-not (Test-Path $FilePath)) {
        throw "Arquivo nao encontrado: $FilePath"
    }
    $name = [System.IO.Path]::GetFileName($FilePath)
    $existing = @($release.assets) | Where-Object { $_.name -eq $name }
    foreach ($asset in $existing) {
        Invoke-RestMethod -Uri "https://api.github.com/repos/foffano/ECO-NATIVE/releases/assets/$($asset.id)" -Headers $headers -Method Delete | Out-Null
        Write-Host "Asset antigo removido: $name"
    }
    $uploadUrl = "https://uploads.github.com/repos/foffano/ECO-NATIVE/releases/$($release.id)/assets?name=$name"
    Invoke-RestMethod -Uri $uploadUrl -Headers $headers -Method Post -InFile $FilePath -ContentType "application/octet-stream" | Out-Null
    Write-Host "Asset enviado: $name"
}

$files = @(
    Join-Path $ReleaseDir "ECO-Native-Studio-$Version-Windows-x64.exe"
    Join-Path $ReleaseDir "ECO-Native-Studio-$Version-Windows-x64.exe.blockmap"
    Join-Path $ReleaseDir "latest.yml"
)

foreach ($file in $files) {
    Upload-ReleaseAsset -Release $release -FilePath $file
}

Write-Host ""
Write-Host "Release publicada: $($release.html_url)"
