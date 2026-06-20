param(
    [string]$Version = "0.1.29",
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
- Corrige bug de URL no Cloudflare R2: a imagem enviada para a IA podia apontar para um objeto que nao existia mais (bucket esvaziado), fazendo a geracao receber uma URL sem imagem
- asset_public_url agora re-publica a imagem a partir do arquivo local; o re-upload so acontece se o objeto tiver sumido do bucket (head_object antes)
- Esvaziar o bucket (purge-bucket) agora limpa os public_url gravados no store para o estado persistido nao apontar para objetos inexistentes

## Test plan
- [ ] Gerar imagens/variacoes de cor normalmente com o bucket populado
- [ ] Esvaziar o bucket R2 e gerar variacoes de cor: a imagem base deve ser reenviada automaticamente e a IA receber uma URL valida
- [ ] Conferir que apos o purge os assets ficam sem public_url no store
- [ ] Atualizar via auto-update de 0.1.28 para 0.1.29
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
