param(
    [string]$Version = "0.1.31",
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
- Geracao em lote de anuncios e imagens agora roda em paralelo (dispara todos os produtos de uma vez), em vez de uma fila sequencial
- Novo limitador de taxa global thread-safe (janela deslizante) protege as APIs externas: Kie limitado a 18 novas geracoes/10s (margem do limite de 20) e OpenRouter a 20/10s
- O limitador da Kie cobre todas as chamadas createTask (imagens base, variacoes de cor e regeneracoes); removidos os sleeps fixos de 3s entre imagens
- Confirmacoes de regeneracao resolvidas uma unica vez antes do disparo, evitando varios dialogos simultaneos
- Gravacao no store continua segura em paralelo (lock + merge por id); erros sao coletados por produto sem derrubar o lote

## Test plan
- [ ] Selecionar varios produtos e gerar anuncios em lote: requisicoes em paralelo e progresso atualizado conforme concluem
- [ ] Selecionar varios produtos e gerar imagens base em lote: nao estourar o rate limit da Kie (sem 429)
- [ ] Confirmar que a confirmacao de regeneracao aparece uma unica vez no inicio do lote
- [ ] Forcar falha em um produto e verificar que os demais concluem e o erro e reportado
- [ ] Atualizar via auto-update de 0.1.30 para 0.1.31
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
