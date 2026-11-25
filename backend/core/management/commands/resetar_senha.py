from django.core.management.base import BaseCommand, CommandError

from core.models import Usuario
from core.senhas import erros_de_senha, gerar_senha
from core.sessoes import invalidar_tokens


class Command(BaseCommand):
    help = "Redefine a senha de um usuário existente (mesma regra do cadastro)."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", required=True, help="Login do usuário.")
        parser.add_argument("--senha", default=None, help="Nova senha (opcional; se faltar, é gerada).")

    def handle(self, *args, **options):
        try:
            usuario = Usuario.objects.get(username__iexact=options["usuario"])
        except Usuario.DoesNotExist:
            raise CommandError(f'O usuário "{options["usuario"]}" não existe.') from None

        gerada = options["senha"] is None
        senha = options["senha"] or gerar_senha()
        erros = erros_de_senha(senha, usuario)
        if erros:
            raise CommandError("Senha inválida: " + " ".join(erros))

        usuario.set_password(senha)
        usuario.save(update_fields=["password"])
        invalidar_tokens(usuario)
        self.stdout.write(self.style.SUCCESS(f'Senha de "{usuario.username}" redefinida.'))
        if gerada:
            self.stdout.write(self.style.WARNING(
                f"Senha gerada (anote agora, não será mostrada de novo): {senha}"))
