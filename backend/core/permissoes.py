from django.db.models import Q

from .models import OrdemServico, Usuario


def ordens_visiveis(user):
    """OS que o usuário pode acessar: da loja dele; técnico só as suas ou sem técnico."""
    qs = OrdemServico.objects.filter(loja_id=user.loja_id)
    if not user.eh_admin and user.cargo == Usuario.Cargo.TECNICO:
        qs = qs.filter(Q(tecnico=user) | Q(tecnico__isnull=True))
    return qs
