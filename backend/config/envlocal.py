import os


def carregar_env_local(caminho):
    try:
        if not caminho.exists():
            return
        with open(caminho, encoding="utf-8") as arquivo:
            for linha in arquivo.read().splitlines():
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                    valor = valor[1:-1]
                os.environ.setdefault(chave, valor)
    except (OSError, UnicodeError):
        return
