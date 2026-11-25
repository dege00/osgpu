from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Loja, Usuario
from core.senhas import erros_de_senha, gerar_senha


class Command(BaseCommand):
    help = "Cria uma loja e o usuário administrador dela (acesso do cliente no SaaS)."

    def add_arguments(self, parser):
        parser.add_argument("--nome-loja", required=True, help="Nome da assistência técnica.")
        parser.add_argument("--usuario", required=True, help="Login do administrador.")
        parser.add_argument("--nome", required=True, help="Nome da pessoa (primeiro nome).")
        parser.add_argument("--telefone", default="", help="Telefone/WhatsApp da loja (opcional).")
        parser.add_argument("--senha", default=None, help="Senha inicial (opcional; se faltar, é gerada).")

    def handle(self, *args, **options):
        username = options["usuario"]
        if Usuario.objects.filter(username__iexact=username).exists():
            raise CommandError(f'O usuário "{username}" já existe.')

        gerada = options["senha"] is None
        senha = options["senha"] or gerar_senha()
        erros = erros_de_senha(senha)
        if erros:
            raise CommandError("Senha inválida: " + " ".join(erros))

        with transaction.atomic():
            loja = Loja.objects.create(nome=options["nome_loja"], telefone=options["telefone"])
            usuario = Usuario(username=username, first_name=options["nome"], loja=loja,
                              cargo=Usuario.Cargo.ADMIN, telefone=options["telefone"])
            usuario.set_password(senha)
            usuario.save()

        self.stdout.write(self.style.SUCCESS(
            f'Loja "{loja.nome}" criada com o administrador "{username}".'))
        if gerada:
            self.stdout.write(self.style.WARNING(
                f"Senha gerada (anote agora, não será mostrada de novo): {senha}"))
