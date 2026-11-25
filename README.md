# Assistec — base de sistema para assistência técnica

Stack: **Django + DRF + PostgreSQL** (API) · **Vue 3 + Vite** (PWA instalável no celular).

## O que já funciona
- Multiempresa (cada loja só vê os próprios dados) e login JWT com limite de tentativas por IP; o acesso do cliente é criado pelo comando `criar_loja`
- Cargos: administrador, atendente, técnico (financeiro, custo e lucro só para admin)
- Clientes
- Ordem de serviço: checklist de entrada, fotos pela câmera, assinatura na tela, laudo, status e histórico
- Orçamento (OS com status "Orçamento") com envio por WhatsApp (link `wa.me` com mensagem pronta)
- Link público de acompanhamento `/r/<codigo>` (sem login), com fotos marcadas como visíveis ao cliente
- Fotos com legenda e tipo (entrada/serviço); o PDF da OS inclui todas as fotos de entrada em miniaturas
- Peças e serviços na OS com **baixa/devolução automática de estoque**; alerta de estoque mínimo
- Leitura de código de barras pela câmera (Chrome/Android)
- Financeiro: entradas, saídas, saldo por período; pagamento da OS lança no caixa; custo e lucro por OS
- PDF da OS/orçamento (ReportLab)
- Exportação de clientes e produtos para Excel `.xlsx` pelo administrador (`/api/exportar/clientes/` e `/api/exportar/pecas/`), usando **openpyxl** — biblioteca madura que gera o arquivo direto, sem depender do Microsoft Office nem de conversores externos
- Painel inicial, PWA (vite-plugin-pwa)

## Etapa 1 — operação diária
- Permissões por cargo: técnico vê só as OS atribuídas a ele (ou sem técnico); atendente não vê custo, lucro nem financeiro
- Pagamento parcial da OS, com bloqueio de valor acima do restante; a OS só vira **Pago** ao quitar
- Edição e remoção de itens com ajuste automático do estoque (inclusive quando a quantidade muda)
- Cancelamento devolve as peças ao estoque; reabrir dá baixa novamente (bloqueia se não houver estoque)
- Fotos comprimidas no navegador para até 1600 px (JPEG, qualidade 0.8); servidor aceita até 20 MB, valida com Pillow e reduz novamente; assinatura e logo também são reduzidos
- Gestão de usuários (criar, editar cargo, ativar/desativar, redefinir senha) e configurações da assistência com logo
- Impressão de recibo em 58 mm ou 80 mm direto pelo navegador

## Rodar em desenvolvimento
```bash
# terminal 1 - API (usa SQLite se não houver POSTGRES_DB)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # opcional, para /admin
# para testar o link do WhatsApp no celular, use o IP do PC na rede:
# bash:       export FRONTEND_URL=http://192.168.1.110:5173
# PowerShell: $env:FRONTEND_URL="http://192.168.1.110:5173"
python manage.py runserver 0.0.0.0:8000

# terminal 2 - frontend
cd frontend
npm install
npm run dev     # http://<ip-do-pc>:5173 (proxy para a API em :8000)
```
O alvo padrão do proxy de desenvolvimento fica em `frontend/.env.example` (`API_PROXY`); para trocar, crie `frontend/.env.development` com o novo valor.
Se `FRONTEND_URL` não for definida, o link do WhatsApp usa o endereço pelo qual o sistema foi acessado. No celular do cliente, `localhost` não abre: acesse pelo IP do PC (ex.: `http://192.168.1.110:5173`) ou defina `FRONTEND_URL`.
Abra o app e entre com o usuário e senha do administrador (veja "Como criar o acesso de um cliente"). Testes: `python manage.py test core`.

## Produção (VPS)
```bash
cp .env.example .env   # edite os valores (SECRET_KEY, POSTGRES_PASSWORD, DOMINIO...)
docker compose up -d --build
```
O compose sobe PostgreSQL (com healthcheck), API (Gunicorn), frontend (Nginx) e **Caddy**, que emite o HTTPS
automaticamente para o `DOMINIO` do `.env` (o DNS precisa apontar para a VPS; câmera e PWA exigem HTTPS).
Sem `DOMINIO`, sobe em `https://localhost` com certificado local, só para testar.
O container da API roda sempre com `DEBUG=0`, mesmo que o `.env` esqueça a variável; com isso o boot falha se a
`SECRET_KEY` for a padrão ou tiver menos de 32 caracteres. Use `https://` em `CSRF_TRUSTED_ORIGINS` e `FRONTEND_URL`:
o Caddy publica HTTPS, e origins em `http://` fazem o CSRF falhar e os links do WhatsApp apontarem para o endereço errado.

O compose define `NUM_PROXIES=2` na API: como o tráfego passa pelo Caddy e pelo Nginx antes do Django, esse valor
faz o limite de tentativas de login usar o **IP real do cliente** em vez do IP do container do Nginx (sem ele, um
único atacante bloquearia o login de todos). Em desenvolvimento o padrão é `0`, pois não há proxy na frente.
Faça backup diário do volume `pgdata` (`pg_dump`) e do volume `media`.
Os logs dos containers são limitados (10 MB por arquivo, no máximo 3) para não encher o disco.

O passo a passo completo de uma VPS Ubuntu (usuário não-root, SSH por chave, `ufw`, Docker, DNS, `.env`,
backup, monitoramento e teste de restauração) está em **[docs/DEPLOY.md](docs/DEPLOY.md)**.

## Backup, restauração e monitoramento
Scripts em `scripts/` (rode na raiz do projeto, onde está o `docker-compose.yml`):
- `backup.sh`: `pg_dump` comprimido + `tar.gz` da mídia em `/var/backups/assistec/`, retenção de 14 dias.
- `enviar_backup.sh`: envia os arquivos novos para fora da VPS com `rclone` (ex.: Backblaze B2).
- `restaurar.sh <banco> <media>`: restaura em um banco/volume de **teste**; com `--producao` (e confirmação)
  sobrescreve produção.

Endpoint público `GET /api/saude/` (só checa o banco e responde `{"status": "ok"}`) para o UptimeRobot.
O agendamento no cron e a criação do `rclone.conf` estão em [docs/DEPLOY.md](docs/DEPLOY.md).


## Personalização do sistema (painel secreto)

O sistema tem um painel secreto para personalizar logo, cores e tela de login (aberto por três cliques rápidos na logo).

- Gere o hash da senha com `python manage.py gerar_senha_tema` (a senha precisa atender aos validadores do Django). Defina `PAINEL_TEMA_SENHA_HASH` no ambiente com o valor gerado; sem essa variável o painel fica desativado. Trocar o hash invalida imediatamente os tokens já emitidos.

- Docker (VPS/produção): gere com `docker compose exec backend python manage.py gerar_senha_tema`, cole `PAINEL_TEMA_SENHA_HASH=...` no `.env` da raiz (usado pelo compose) e reinicie o backend. O `.env` da raiz não é lido automaticamente pelo `runserver` em desenvolvimento.
- Sem Docker: `python manage.py gerar_senha_tema --gravar-env` grava a linha em `backend/.env.local` (arquivo só de desenvolvimento, fora do git), e depois `python manage.py migrate` e reinicie o `runserver`. O `runserver` não lê o `.env` da raiz.
## Como criar o acesso de um cliente
Não existe cadastro público: quem cria a loja e o usuário é você, pelo backend. Use o comando `criar_loja`
(rodando no servidor ou dentro do container):

```bash
# na VPS, via Docker (recomendado em produção)
docker compose exec backend python manage.py criar_loja \
  --nome-loja "TecnoPI Assistência" \
  --usuario ana --nome "Ana" --telefone "86999990000"

# ou em desenvolvimento, no venv do backend
cd backend
python manage.py criar_loja --nome-loja "TecnoPI" --usuario ana --nome "Ana"
```

Se `--senha` for omitida, o comando gera uma senha forte e a mostra **uma única vez** (anote e entregue ao
cliente). A senha é validada pelos validadores do Django e o comando recusa um usuário que já exista. A loja e o
administrador são criados na mesma transação.

Para redefinir a senha de alguém depois:

```bash
docker compose exec backend python manage.py resetar_senha --usuario ana
```

Entregue usuário e senha ao cliente; no primeiro acesso ele pode trocar a senha em **Ajustes → Minha senha**.
Também é possível criar lojas e usuários direto pelo `/admin` (com filtro por loja).

## Revisão de segurança e qualidade
Corrigido nesta revisão:
- **Técnico** só mexe (itens, fotos, desconto) nas OS que pode ver; antes conseguia adicionar itens em OS de outro técnico.
- **Valores negativos** recusados (peça, item, desconto, lançamento) no banco e na API.
- **OS só vira "Paga"** com pagamentos cobrindo o total (use "Registrar pagamento"). Excluir um pagamento reabre a OS
  (volta para Finalizado) e pagamentos ligados a OS não são editáveis. A forma de pagamento é validada.
- **PDF** não quebra mais com `<` ou `&` nos textos. **Fotos** respeitam a rotação da câmera (EXIF) e imagens gigantes são recusadas.
- Numeração da OS protegida contra duplicidade; listagem de OS usa um serializer enxuto (4 consultas, antes 1 por OS).
- Docker: `.dockerignore`, Dockerfile do frontend, Caddy com HTTPS, healthcheck do banco, `DEBUG=0` garantido.
- Testes: `core/test_seguranca.py` cobre essas regras; a suíte roda em poucos segundos.

Pendente / decisões conscientes:
- Cadastro público removido: a loja e o usuário do cliente são criados por você com `criar_loja` (ou pelo `/admin`).
- Login limitado a 10 tentativas por minuto por IP (`throttle_scope = "auth"`); a renovação de token tem limite próprio
  e mais folgado (`refresh`, 60/min) e a troca de senha tem o seu (`senha`, 5/min). A mensagem de erro continua genérica.
- `/media/` continua público por URL com nome UUID (veja "Decisões").
- Tokens JWT ficam no `localStorage` (access 60 min, refresh 14 dias, sem rotação de refresh). O access curto reduz o dano
  de um token vazado; a renovação é feita pelo refresh token. Trocar a própria senha, redefinir por comando
  (`resetar_senha`) ou **desativar** um usuário invalida na hora todos os refresh tokens já emitidos (blacklist), então as
  outras sessões caem no próximo refresh; a sessão atual recebe um par novo e continua logada. Limpe os tokens expirados de
  tempos em tempos com `docker compose exec backend python manage.py flushexpiredtokens` (veja o cron no `docs/DEPLOY.md`).
- Em desenvolvimento ainda há fallback para SQLite; o app `core` ainda não foi dividido por domínio.

## Decisões (Etapa 1)
- **Mídia:** fotos, assinaturas e logos ficam em `MEDIA_URL` com nomes UUID. A API devolve sempre caminho relativo (`/media/...`), nunca host/porta; o frontend ainda normaliza com `urlMidia` como defesa extra. Os arquivos são públicos por URL (sem endpoint autenticado), o que simplifica o PWA e a impressão; o UUID evita nomes previsíveis. `visivel_cliente` controla apenas o JSON do link público: quem tiver a URL direta do arquivo ainda consegue abri-lo, então a marcação não é um controle de acesso. Faça backup do volume `media`.
- **URL absoluta:** somente `FRONTEND_URL` (link do WhatsApp) vem do ambiente. Em desenvolvimento, defina-a com o IP do PC (ex.: `http://192.168.1.110:5173`) para o link abrir no celular.
- **Estoque:** baixa e devolução usam transação e `select_for_update`, efetivo no PostgreSQL de produção (os testes usam SQLite). Cancelar devolve as peças; reabrir dá baixa novamente e falha se faltar estoque.
- **Pagamento:** cada pagamento gera um lançamento no caixa. Não há estorno nesta etapa; a OS vira `pago` somente quando o total é atingido.
- **Exclusão de OS:** só administradores; OS já cancelada não devolve estoque uma segunda vez.
- **Custo/lucro:** ocultos para atendentes e técnicos também nas escritas (o campo é ignorado).
- **Senhas:** mínimo de 8 caracteres e validadores do Django; usuários antigos continuam podendo entrar, mas novas senhas precisam atender à regra.
- **Impressão:** recibo de 58/80 mm gerado no navegador com CSS de impressão; não há integração direta com impressora térmica nesta etapa.
- **Fotos (Etapa B):** a compressão no navegador usa `createImageBitmap` (respeitando EXIF) e canvas, evitando enviar 4–12 MB pelo celular. O servidor mantém o Pillow como rede de segurança, aceita até 20 MB brutos e valida o conteúdo real. HEIC/HEIF só é convertido se `pillow-heif` estiver instalado; sem ele, o usuário recebe uma mensagem clara para usar JPEG/PNG/WebP. Nginx aceita 25 MB e o proxy do Vite não impõe limite próprio.

## Próximos passos sugeridos
1. PDV de balcão e venda/compra de aparelhos (IMEI, termo de recebimento)
2. Crediário/carnê e comissões por técnico
3. Planos e cobrança (Stripe/Asaas/Mercado Pago) se for vender como SaaS
4. Nota fiscal via API de terceiros (Focus NFe, eNotas)
5. Troca do disco por storage S3/R2 para as fotos; política de privacidade (LGPD)
