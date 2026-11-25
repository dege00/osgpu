import getpass
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from core.senhas import erros_de_senha


class Command(BaseCommand):
    help = "Gera o hash da senha do painel de personalização (tema)."

    def add_arguments(self, parser):
        parser.add_argument("--gravar-env", action="store_true", help="Grava o hash em backend/.env.local.")

    def handle(self, *args, **options):
        try:
            senha = getpass.getpass("Senha do painel de tema: ")
        except (EOFError, KeyboardInterrupt):
            senha = ""
        if not senha:
            try:
                senha = input("Senha do painel de tema: ")
            except (EOFError, KeyboardInterrupt):
                senha = ""
        senha = (senha or "").strip()
        if not senha:
            self.stderr.write("Informe uma senha.")
            return
        erros = erros_de_senha(senha)
        if erros:
            self.stderr.write("Senha fraca: " + "; ".join(erros))
            return
        h = make_password(senha)

        linha = f"PAINEL_TEMA_SENHA_HASH={h}"
        self.stdout.write(linha)
        if options.get("gravar_env"):
            caminho = Path(settings.BASE_DIR) / ".env.local"
            linhas = []
            if caminho.exists():
                conteudo = caminho.read_text(encoding="utf-8")
                linhas = conteudo.splitlines()
            achou = False
            novas = []
            for atual in linhas:
                if atual.startswith("PAINEL_TEMA_SENHA_HASH="):
                    novas.append(linha)
                    achou = True
                else:
                    novas.append(atual)
            if not achou:
                novas.append(linha)
            caminho.write_text("\n".join(novas) + "\n", encoding="utf-8")
