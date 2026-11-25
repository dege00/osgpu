# Requisitos para rodar o Assistec (OSGPU)

Existem dois jeitos de rodar. **O Docker só é necessário no segundo (produção).**

## 1. Desenvolvimento no seu computador — SEM Docker

Instale apenas:

| Ferramenta | Versão | Observação |
|---|---|---|
| Python | 3.12 (testado com 3.12.3) | O `Dockerfile` usa 3.12 |
| Node.js | 20 ou mais novo (testado com 22) | O `Dockerfile` do frontend usa 20 |
| npm | vem com o Node | |
| Git | qualquer versão atual | |

Não precisa instalar PostgreSQL: sem a variável `POSTGRES_DB`, o backend usa um arquivo SQLite (`backend/db.sqlite3`, ignorado pelo Git). Esse banco é **separado** do banco do cliente.

```bash
# Terminal 1 — API
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # opcional (acesso a /admin)
python manage.py runserver 0.0.0.0:8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev                        # http://localhost:5173 (usa proxy para a API em :8000)

# Testes do backend
cd backend && python manage.py test core
```

Para criar uma loja e um acesso de teste:
`python manage.py criar_loja --nome-loja "Loja Teste" --usuario teste --nome "Fulano" --telefone "86 99999-0000"`

> Em desenvolvimento o `.env` da raiz **não é lido**. Ele só vale para o Docker (produção).

## 2. Produção na VPS — COM Docker

Necessário na VPS: Ubuntu 22.04 ou 24.04, **Docker** e o plugin **Docker Compose**, domínio apontando para o IP da VPS, portas 80 e 443 liberadas. PostgreSQL, Python e Node **não** precisam ser instalados na VPS: tudo roda em containers (banco, API, frontend e Caddy para HTTPS).

```bash
cp .env.example .env     # preencha SECRET_KEY, DOMINIO, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, FRONTEND_URL e POSTGRES_PASSWORD
docker compose up -d --build
```

Passo a passo completo: `docs/DEPLOY.md`. **Faça `./scripts/backup.sh` antes de cada atualização**: as migrações rodam automaticamente quando o container da API sobe.

## Dependências do backend (`backend/requirements.txt`)

Instaladas automaticamente por `pip install -r requirements.txt`. Versões que funcionaram nos testes (105 testes passando):

| Pacote | Faixa exigida | Testado com |
|---|---|---|
| Django | >=5.0,<5.3 | 5.2.19 |
| djangorestframework | >=3.15 | 3.18.3 |
| djangorestframework-simplejwt | >=5.3 | 5.5.1 |
| django-filter | >=24.2 | 26.2 |
| Pillow | >=10.3 | 13.0.0 |
| reportlab | >=4.2 | 5.1.1 |
| openpyxl | >=3.1 | 3.1.5 |
| gunicorn | >=22.0 | 27.0.1 |
| psycopg2-binary | >=2.9 | 2.9.13 |
| whitenoise | >=6.6 | 6.12.0 |

## Dependências do frontend (`frontend/package.json`)

Instaladas por `npm install`: Vue 3, Vue Router, Vite 5, vite-plugin-pwa e @vitejs/plugin-vue.

## O que NÃO vai junto

O `.env` real (segredos), `node_modules`, `.venv`, `db.sqlite3`, `staticfiles` e `media`. Tudo isso é gerado ou fica só no servidor.
