# VPS Linux com Docker Compose

O app usa um container Linux com FastAPI, frontend compilado, Chromium e Xvfb.
O Chromium permanece **headed (`headless=False`)**. O painel do app transmite a
página e envia cliques/teclado; não é necessário instalar desktop ou VNC na VPS.

## Primeira instalação

Pré-requisitos: Docker Engine e plugin Docker Compose funcionando na VPS,
saída HTTPS para os provedores, espaço para imagens/modelos e DNS para o domínio.
Comece com uma única instância. O limite padrão é dois navegadores e um trabalho
por vez; dimensione RAM e disco medindo o uso real.

Na pasta do repositório:

```bash
docker compose build
docker compose run --rm --no-deps app python -m backend.smoke_browser
ECO_NATIVE_SECURE_COOKIES=false docker compose up -d
docker compose ps
docker compose logs --tail=100 app
```

O smoke test abre Chromium **com interface**, captura um quadro, envia texto pelo
controle remoto e verifica a mudança do quadro. Não acessa MakerWorld nem usa os
perfis reais. Execute na arquitetura final da VPS.

A porta fica publicada apenas em `127.0.0.1:18765` da VPS. Para configurar o
primeiro administrador antes de publicar o domínio, abra um túnel SSH no seu PC:

```bash
ssh -L 18765:127.0.0.1:18765 usuario@SUA_VPS
```

Acesse `http://127.0.0.1:18765` no PC e configure os acessos. Depois habilite HTTPS
e recrie o serviço com o padrão de cookies seguros:

```bash
docker compose up -d --force-recreate
```

Não coloque chaves de API na imagem. Cadastre-as no painel; serão gravadas em
`/data/.env` no volume persistente. O arquivo `.env` do Compose, se usado, configura
o deployment e não é automaticamente o arquivo de integrações dentro do container.

## HTTPS por Cloudflare Tunnel

Na VPS `prod-01`, que já tem Tunnel e rede `edge`, use `deploy/compose.yml`.
Esse arquivo segue a estrutura `/srv/apps/eco-native`, não publica portas,
usa `./data` como diretório persistente e limita o app a 2 CPUs/4 GB de RAM.
O destino do hostname no Tunnel é `http://eco-native:18765`.
`IMAGE` e `IMAGE_TAG` ficam em `.env`; `app.env` contém configurações de ambiente.
O diretório `data` deve pertencer ao UID/GID 1000 do container.

Enquanto não houver runner, o primeiro deploy pode ser feito manualmente:
construa a imagem a partir do código de uma release em diretório temporário,
execute `backend.smoke_browser` na imagem, copie apenas o Compose da release
para a pasta do app e rode `docker compose up -d --pull never --wait`.
Guarde a tag no `.env` e registre o resultado em `deploys.log`. Não altere o
código no servidor. O fluxo automatizado de `/srv/infra/scripts/deploy.sh`
requer imagem publicada em registry e runner previamente configurados.

O arquivo opcional `compose.tunnel.yaml` adiciona o conector. Configure um hostname
no painel Cloudflare com destino **`http://app:18765`**. `127.0.0.1` dentro do
conector apontaria para o próprio conector.

Salve `TUNNEL_TOKEN` no `.env` local da VPS, fora do Git, com permissão `600`.
Depois:

```bash
docker compose -f compose.yaml -f compose.tunnel.yaml up -d
```

Use os mesmos arquivos `-f` nos próximos comandos de atualização. O serviço
permanece acessível por loopback para diagnóstico. Se usar um proxy HTTPS próprio,
preserve `Host`, sobrescreva `X-Forwarded-Host`/`X-Forwarded-Proto` com os valores
corretos e não exponha a porta da API diretamente na internet. Com o frontend e a
API na mesma origem, não é necessário liberar CORS para qualquer origem.

## Dados, concorrência e reinício

- `eco-data` monta `/data`: banco JSON, autenticação, segredo de sessão, projetos,
  imagens, modelos, logos, configurações e perfis de navegador por loja.
- Não use `docker compose down -v`: `-v` remove o volume de dados.
- O app roda com UID/GID `1000`, sem usuário root. Bind mounts precisam permitir
  escrita para esse UID. O volume nomeado novo já recebe a propriedade da imagem.
- Não use múltiplas réplicas nem `uvicorn --workers`. O lock do diretório rejeita
  um segundo processo Linux; o banco JSON ainda não é um banco distribuído.
- A fila responde `202` com o trabalho e executa uma operação por vez. O frontend
  consulta seu andamento. Fechar a página não cancela o trabalho no servidor.
- A fila aceita até 32 trabalhos aguardando; o excedente recebe `429`.
- Após reinício, trabalhos pendentes/em execução são marcados como interrompidos.
  Eles **não são repetidos automaticamente**, para evitar duplicar cobranças de
  IA. Revise os arquivos já gerados antes de repetir a operação.
- Login e coleta não podem abrir o mesmo perfil simultaneamente. Feche a sessão
  de login pelo botão do painel antes de coletar; conflitos retornam erro claro.
- A transmissão mostra páginas e popups web do login. Não transmite diálogos
  nativos nem os contextos separados das coletas.
- O healthcheck verifica HTTP; não autentica no MakerWorld nem valida APIs de IA.
  Um container marcado unhealthy não é reiniciado automaticamente pelo Compose;
  `restart: unless-stopped` cobre a saída do processo.

## Backup operacional e restauração

O backup do painel continua restrito à loja. Para recuperar toda a instalação,
use o comando **offline** abaixo. Ele inclui `auth.json`, `.session-secret`, `.env`,
perfis Chromium e todos os arquivos regulares de `/data`. Symlinks e locks de
processos não são transportados. O ZIP contém credenciais: mantenha-o privado e
guarde uma cópia fora da VPS.

Espere os trabalhos terminarem e pare o app antes do backup:

```bash
sudo install -d -m 0700 -o 1000 -g 1000 backups
docker compose stop app
docker compose run --rm --no-deps --entrypoint python \
  -v "$PWD/backups:/backups" app \
  -m backend.maintenance backup /backups/eco-operacional.zip
docker compose up -d app
```

Escolha um nome novo a cada backup. O comando recusa sobrescrever um arquivo.
Ele também recusa acesso ao volume enquanto a API mantém seu lock POSIX.

Para restaurar, use um volume vazio em uma instalação separada, preservando o
volume original para rollback. Exemplo com outro nome de projeto Compose:

```bash
docker compose stop app
docker compose -p eco-restore run --rm --no-deps --entrypoint python \
  -v "$PWD/backups:/backups:ro" app \
  -m backend.maintenance restore /backups/eco-operacional.zip
docker compose -p eco-restore up -d
```

Os caminhos do banco são convertidos para `/data` automaticamente. O comando
recusa restaurar sobre dados existentes. Use o nome `eco-restore` nos comandos
seguintes dessa instalação; a porta é a mesma, portanto mantenha a anterior parada.

## Migração do Windows

1. Pare o app Windows e faça uma cópia integral dos dados originais.
2. Com esta versão do backend e Python 3.12, execute no Windows:

   ```powershell
   $env:ECO_NATIVE_DATA_DIR = "$env:APPDATA\eco-native-studio"
   .\.venv\Scripts\python.exe -m backend.maintenance backup "D:\backups\eco-operacional.zip"
   ```

   Ajuste o caminho para o diretório realmente usado. No Windows o comando não
   verifica o lock POSIX: o servidor deve estar parado.
3. Transfira o ZIP à VPS, dê permissão de leitura ao UID 1000 e restaure em volume
   vazio conforme acima. Confira imagens, modelos, logos e exportações.
4. Refaça o login MakerWorld pelo painel. Um perfil copiado entre sistemas não
   garante reutilização dos cookies. Se o perfil Windows impedir a abertura,
   preserve o ZIP e remova apenas o perfil afetado em `/data/browser_data/makerworld`
   com o app parado; o próximo login criará um perfil Linux.

Se já copiou a pasta de dados manualmente, o utilitário também converte referências:

```bash
docker compose stop app
docker compose run --rm --no-deps --entrypoint python app \
  -m backend.maintenance migrate-paths 'C:\Users\SEU_USUARIO\AppData\Roaming\eco-native-studio'
docker compose up -d app
```

Uma cópia `studio.before-path-migration.json` é preservada. O backup operacional
é diferente do ZIP de loja e do antigo backup `full_app`; não misture os formatos.

## Integração opcional Codex CLI

A imagem padrão atende os provedores HTTP já existentes. Se usa geração de imagens
via Codex CLI, utilize `compose.codex.yaml` para instalar uma versão **explicitamente
selecionada** do CLI e persistir `/home/app/.codex` em volume separado.

Defina `CODEX_VERSION` no `.env` do Compose com a versão que irá validar; depois:

```bash
docker compose -f compose.yaml -f compose.codex.yaml build
docker compose -f compose.yaml -f compose.codex.yaml up -d
docker compose -f compose.yaml -f compose.codex.yaml exec app codex login --device-auth
docker compose -f compose.yaml -f compose.codex.yaml exec app codex login status
```

Siga o link/código exibido no seu navegador pessoal. A autenticação por dispositivo
pode exigir habilitação na conta/workspace. Referência:
[autenticação oficial do Codex](https://developers.openai.com/codex/auth/).

No painel, deixe `CODEX_BIN=codex`. Instalação e login **não garantem** que a versão,
conta e configuração escolhidas disponibilizem `image_gen`: valide uma geração real
antes de ativar esse provedor. Skills/configurações necessárias devem existir no
ambiente do CLI. O volume Codex não faz parte do backup de `/data`; preserve-o
separadamente ou refaça o login e a configuração após recuperar a instalação.

O modo de sandbox existente do Codex foi preservado. Não monte o socket Docker ou
diretórios do host no app. O sandbox do Chromium mantém o padrão anterior e pode
ser configurado por `ECO_NATIVE_CHROMIUM_SANDBOX=true` com as permissões de namespace
e seccomp adequadas; valide isso antes de alterar em produção.

## Atualizações e validação final

Faça backup, construa a nova imagem e execute o smoke test antes de atualizar:

```bash
docker compose build
docker compose run --rm --no-deps app python -m backend.smoke_browser
docker compose up -d
docker compose logs --tail=100 app
```

Valide no IP real da VPS: login MakerWorld, popup de login, persistência após
recriar o container, coleta por busca/URL, download de 3MF, geração de anúncio,
imagem, exportação e restauração de backup. O modo headed foi preservado, mas a
aceitação do IP e os desafios do MakerWorld dependem do serviço externo.

Os testes locais usam `python -m pytest tests` após instalar
`backend/requirements-dev.txt`. A automação em `.github/workflows/linux.yml` também
constrói a imagem e executa o smoke test em Linux quando enviada ao GitHub.

Na revisão das dependências, as correções compatíveis de `npm audit fix` foram
aplicadas ao lockfile. Restou um alerta baixo em esbuild relativo ao servidor de
desenvolvimento Windows (GHSA-g7r4-m6w7-qqqr). Esse servidor não é executado na
imagem de produção; não foi forçada uma troca incompatível de esbuild/Vite.
