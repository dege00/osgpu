from .models import ItemOS, OrdemServico

_PONTUACAO_FINAL = ".!?"


def _com_ponto(texto):
    texto = (texto or "").strip()
    if not texto:
        return ""
    return texto if texto[-1] in _PONTUACAO_FINAL else texto + "."


def _itens_entrada(os_):
    estruturados = getattr(os_, "checklist_itens", None) or []
    if isinstance(estruturados, (list, tuple)):
        respondidos = []
        for item in estruturados:
            if not isinstance(item, dict):
                continue
            resposta = str(item.get("resposta", "")).strip().lower()
            if resposta not in ("sim", "nao"):
                continue
            nome = str(item.get("nome", "") or "").strip()
            if nome:
                respondidos.append(f"{nome}: {'Sim' if resposta == 'sim' else 'Não'}")
        if respondidos:
            return respondidos

    antigo = getattr(os_, "checklist", "") or ""
    linhas = []
    for linha in str(antigo).splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if ":" in linha:
            rotulo, valor = linha.split(":", 1)
            if not valor.strip():
                continue
            linha = f"{rotulo.strip()}: {valor.strip()}"
        linhas.append(linha)
    return linhas


def _itens_os(os_):
    relacao = getattr(os_, "itens", None)
    brutos = relacao.all() if hasattr(relacao, "all") else (relacao or [])
    return sorted(brutos, key=lambda i: getattr(i, "pk", None) or 0)


def _descricoes(itens, tipo):
    descricoes = []
    for item in itens:
        if getattr(item, "tipo", None) != tipo:
            continue
        descricao = str(getattr(item, "descricao", "") or "").strip()
        if not descricao:
            continue
        try:
            quantidade = int(getattr(item, "quantidade", 1) or 1)
        except (TypeError, ValueError):
            quantidade = 1
        if quantidade > 1:
            descricao += f" (x{quantidade})"
        descricoes.append(descricao)
    return "; ".join(descricoes)


def montar_laudo(os_):
    linhas = []

    partes = [str(getattr(os_, campo, "") or "").strip()
              for campo in ("tipo_aparelho", "marca", "modelo")]
    aparelho = " ".join(parte for parte in partes if parte)
    if aparelho:
        linhas.append(_com_ponto(f"Aparelho: {aparelho}"))

    defeito = str(getattr(os_, "defeito", "") or "").strip()
    if defeito:
        linhas.append(_com_ponto(f"Defeito relatado pelo cliente: {defeito}"))

    estado = "; ".join(_itens_entrada(os_))
    if estado:
        linhas.append(_com_ponto(f"Estado na entrada: {estado}"))

    observacao = str(getattr(os_, "observacao_entrada", "") or "").strip()
    if observacao:
        linhas.append(_com_ponto(f"Observações na entrada: {observacao}"))

    itens = _itens_os(os_)
    concluido = getattr(os_, "status", "") in (OrdemServico.Status.FINALIZADO, OrdemServico.Status.PAGO)

    servicos = _descricoes(itens, ItemOS.Tipo.SERVICO)
    if servicos:
        verbo = "executados" if concluido else "previstos"
        linhas.append(_com_ponto(f"Serviços {verbo}: {servicos}"))

    pecas = _descricoes(itens, ItemOS.Tipo.PECA)
    if pecas:
        verbo = "utilizadas" if concluido else "previstas"
        linhas.append(_com_ponto(f"Peças {verbo}: {pecas}"))

    return "\n".join(linhas)
