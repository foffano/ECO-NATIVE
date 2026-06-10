# ECO Native Studio

Plataforma React + FastAPI + Electron para organizar e automatizar a criacao de anuncios de e-commerce com IA.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
npm.cmd install
npm.cmd run dev
```

Frontend: http://127.0.0.1:5173  
Backend: http://127.0.0.1:8765/health

Para abrir no Electron durante o desenvolvimento:

```powershell
npm.cmd run dev:desktop
```

## Gerar instalador Windows

O pacote Windows usa:

- React/Vite compilado em `dist/frontend`.
- API FastAPI empacotada com PyInstaller em `dist/backend/eco-native-api.exe`.
- Chromium do Playwright em `dist/playwright-browsers`, usado pela coleta MakerWorld.
- Electron Builder para gerar o instalador NSIS.

Comando principal:

```powershell
npm.cmd run dist:win
```

Por padrao, o instalador final e gerado fora do OneDrive em:

```text
C:\Users\<seu usuario>\ECO-NATIVE-release
```

Isso evita erros de bloqueio de arquivo do OneDrive durante o empacotamento.

Arquivos importantes da release:

- `ECO Native Studio-0.1.0-Windows-x64.exe`: instalador.
- `latest.yml`: metadados usados pelo auto-update.
- `.exe.blockmap`: mapa usado para atualizacao diferencial.
- `win-unpacked`: versao desempacotada para teste local.

## macOS

O macOS deve ser gerado em uma maquina macOS:

```bash
npm run dist:mac
```

Para distribuicao publica no macOS, sera necessario configurar assinatura e notarizacao da Apple.

## Atualizacao automatica

O app usa `electron-updater`.

No app instalado, a aba **Ajustes > Aplicativo** tem o botao **Verificar atualizacoes**. Ele consulta o GitHub Releases, baixa a nova versao e instala ao fechar/reabrir o app.

Para publicar uma release Windows automaticamente:

```powershell
$env:GH_TOKEN="seu_token_do_github"
npm.cmd run publish:win
```

Antes de publicar, confira em `package.json` se o campo `repository.url` aponta para o repositorio GitHub correto. Hoje ele esta configurado como:

```text
https://github.com/marlo/ECO-NATIVE.git
```

## Dados locais do app instalado

No desenvolvimento, os dados ficam em `data/` dentro do projeto.

No app instalado, o Electron define:

- `ECO_NATIVE_DATA_DIR`: pasta de dados do usuario do Electron.
- `ECO_NATIVE_ENV_PATH`: `.env` dentro da pasta de dados do usuario.
- `PLAYWRIGHT_BROWSERS_PATH`: navegadores empacotados junto ao app.

Assim, chaves de API, produtos, backups e arquivos gerados nao ficam dentro do executavel.

## Variaveis

As chaves podem ser configuradas pela interface em **Ajustes > Integracoes**. Tambem e possivel usar `.env`:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/qwen3.5-flash-02-23
OPENROUTER_EST_INPUT_USD_PER_1M=0.065
OPENROUTER_EST_OUTPUT_USD_PER_1M=0.26
KIE_API_KEY=
KIE_IMAGE_MODEL=qwen/image-edit
KIE_IMAGE_COST_USD=0.01
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_R2_BUCKET_NAME=
CLOUDFLARE_R2_ACCESS_KEY=
CLOUDFLARE_R2_SECRET_KEY=
CLOUDFLARE_R2_PUBLIC_URL=
```

Custos usados por padrao:

- OpenRouter Qwen: US$ 0,065 por 1M tokens de entrada e US$ 0,26 por 1M tokens de saida.
- Kie.ai/Qwen imagem: US$ 5 compra 1000 creditos; cada imagem usa 2 creditos; custo estimado por imagem = US$ 0,01.
