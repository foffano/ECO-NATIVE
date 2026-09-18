# ECO Native Studio Web

Aplicação web local para coletar produtos, gerar anúncios e imagens com IA e exportar para marketplaces.

**Stack:** React · Vite · FastAPI · Cloudflare Tunnel (opcional)

## VPS Linux / Docker Compose

Veja o [guia de implantação na VPS](docs/VPS-LINUX.md) para instalação, HTTPS,
migração do Windows, backups e a imagem opcional com Codex CLI. A imagem Linux
mantém Chromium com `headless=False` usando Xvfb e controle pelo painel web.

```bash
docker compose build
docker compose run --rm --no-deps app python -m backend.smoke_browser
docker compose up -d
```

O acesso publicado fica em `127.0.0.1:18765` da VPS. O guia explica o primeiro
acesso por SSH e a publicação HTTPS. Dados permanecem no volume `eco-data`.
Use apenas uma instância/worker; tarefas interrompidas por reinício são marcadas
como falhas para revisão, sem repetir automaticamente cobranças de IA.

As instruções abaixo descrevem a execução local no Windows.

O frontend, a API, o banco JSON, imagens, modelos 3D, Playwright e todos os processamentos rodam neste computador. O Cloudflare Tunnel apenas encaminha HTTPS para a porta HTTP local.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
npm install
npm run build:playwright
```

## Executar

```powershell
npm start
```

Abra `http://127.0.0.1:18765`. Na primeira abertura, crie uma conta administradora sem vínculo com loja e um login para cada loja já existente. A conta administrativa configura integrações, cadastra lojas e controla cotas mensais de coleta, texto, imagem e custo de IA. Cada acesso de loja enxerga somente sua loja e nunca recebe as chaves globais.

Ao abrir pela primeira vez uma instalação que já utilizou o formato provisório anterior, o antigo login administrador é separado automaticamente da loja. A conta administrativa mantém o login original; a loja correspondente recebe um login com sufixo `-loja` e a mesma senha. Uma cópia do arquivo de autenticação anterior é preservada antes da migração.

A antiga gestão de impressoras, placas e agenda de impressão foi retirada da versão web. Custos de produção e filamentos continuam disponíveis. Registros antigos dessa área permanecem inertes no banco e nos backups para evitar perda irreversível durante a migração.

Para desenvolvimento com recarga automática, use `npm run dev`. O frontend fica em `http://127.0.0.1:5173` e a API em `http://127.0.0.1:18765`.

## Dados locais e migração

O servidor reutiliza automaticamente o banco do aplicativo Electron em `%APPDATA%\eco-native-studio`. Antes da primeira inicialização web, cria uma cópia única em `%APPDATA%\eco-native-studio\exports\pre_web_migration`.

Para escolher outro diretório sem mover os dados:

```powershell
$env:ECO_NATIVE_DATA_DIR = "D:\ECO Native\dados"
npm start
```

## Publicar com Cloudflare Tunnel

Mantenha o app ouvindo somente em `127.0.0.1:18765`. No painel Cloudflare, crie um Tunnel, instale o conector indicado para Windows e publique um hostname apontando para:

```text
http://127.0.0.1:18765
```

O comando fornecido pelo painel contém um token: trate-o como segredo e não o salve no repositório. Para maior proteção, adicione também uma política do Cloudflare Access ao hostname, criando uma segunda barreira antes do login do ECO Native.

### Sessão MakerWorld

Cada loja mantém um perfil de navegador MakerWorld separado. Use **Configurar login MakerWorld** tanto pelo endereço local quanto pelo endereço público: a interface transmite a página do Chromium para um painel remoto, com suporte a clique, teclado, colagem e rolagem. O botão **Tela de login** abre direto o login da Bambu Lab, que retorna ao MakerWorld já autenticado; **Voltar**, **Recarregar** e **Início** ajudam a sair de páginas travadas. Se a Cloudflare exibir a verificação “Verify you are human”, marque a caixa pelo painel e aguarde. Ao iniciar uma coleta, o mesmo painel mostra o navegador da coleta; se o MakerWorld pedir uma verificação ou puzzle, a coleta espera até 3 minutos e o aviso pede para resolvê-la ali, com clique ou arrastando. Cada produto é salvo assim que é capturado, e links que falharem não viram produto: podem ser coletados de novo. Ao concluir, cookies e armazenamento ficam somente no perfil local daquela loja. No modo `background:install` ou `background:start`, o servidor e seus navegadores rodam em um desktop separado do Windows, que não é exibido no monitor. O Chromium continua com interface (`headless=False`), incluindo nas coletas. Use o painel para interagir; diálogos nativos do Windows não são transmitidos. Nos modos `npm start` e `npm run dev`, as janelas continuam visíveis.

Documentação oficial: [criar Tunnel pelo painel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) e [instalar cloudflared no Windows](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/).

## Segundo plano e inicio com o Windows

Depois de instalar as dependencias e executar `npm run build:frontend`, execute `npm run background:install`. O servidor inicia sem terminal e volta a iniciar automaticamente quando este usuario entra no Windows. Fechar o navegador nao encerra o servidor. Acesse http://127.0.0.1:18765.

- `npm run background:status`: mostra o processo e a configuracao de inicio automatico.
- `npm run background:start`: inicia manualmente sem terminal.
- `npm run background:stop`: encerra o servidor (interrompe trabalhos em andamento).
- `npm run background:uninstall`: remove o inicio automatico.

Os logs ficam na pasta `logs` do diretorio de dados, incluindo `server.log` com rotacao. O atalho usa esta pasta de instalacao; execute novamente a instalacao do inicio automatico se mover o projeto. O inicio ocorre ao entrar na conta, nao antes do login, para permitir as sessoes interativas do MakerWorld. Nao execute `npm start` ou `npm run dev` na mesma porta enquanto o servidor em segundo plano estiver ativo.
