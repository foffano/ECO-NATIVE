param(
    [string]$Version = "0.1.36",
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
- Variacoes de cor manuais: adicione uma cor enviando a foto (nome livre, ex.: Azul Bebe) alem das geradas por IA
- Variacoes genericas (ex.: Tamanho) criadas manualmente com SKU proprio e foto por variacao
- Remocao de variacoes de cor/atributo direto pela aba do produto, limpando SKUs e arquivos locais
- Correcao do upload para o bucket Cloudflare R2: o app sempre republica a imagem (force) antes de usar o link, evitando enviar a IA ou exportar um link quebrado/desatualizado quando o objeto sumiu do bucket

## Test plan
- [ ] Adicionar uma cor manual enviando uma foto e confirmar que aparece nas variacoes de cor
- [ ] Criar uma variacao de Tamanho e enviar uma foto para ela
- [ ] Remover uma variacao e confirmar que SKU e arquivo somem
- [ ] Gerar imagem por IA e confirmar que o link enviado aponta para o objeto atual no R2
- [ ] Exportar a planilha e confirmar que as imagens abrem
- [ ] Atualizar via auto-update de 0.1.35 para 0.1.36
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
