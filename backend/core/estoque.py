from rest_framework.exceptions import ValidationError

from .models import Peca


def baixar_estoque(peca_id, quantidade):
    """Baixa estoque com bloqueio de linha, impedindo negativo e corrida."""
    if not peca_id or not quantidade:
        return
    peca = Peca.objects.select_for_update().get(pk=peca_id)
    if peca.quantidade < quantidade:
        raise ValidationError(
            {"quantidade": f"Estoque insuficiente de {peca.nome} ({peca.quantidade} disponível)."}
        )
    peca.quantidade -= quantidade
    peca.save(update_fields=["quantidade"])


def devolver_estoque(peca_id, quantidade):
    """Devolve peças ao estoque com bloqueio de linha."""
    if not peca_id or not quantidade:
        return
    peca = Peca.objects.select_for_update().get(pk=peca_id)
    peca.quantidade += quantidade
    peca.save(update_fields=["quantidade"])


def baixar_itens(itens):
    """Baixa todas as peças de uma OS. Recebe itens já materializados."""
    for item in sorted((i for i in itens if i.peca_id), key=lambda i: i.peca_id):
        baixar_estoque(item.peca_id, item.quantidade)


def devolver_itens(itens):
    for item in sorted((i for i in itens if i.peca_id), key=lambda i: i.peca_id):
        devolver_estoque(item.peca_id, item.quantidade)
