from unittest import skipUnless

from .laudo import montar_laudo
from .models import HistoricoStatus, ItemOS, Lancamento, OrdemServico
from .tests import BaseTeste


class MontarLaudoTest(BaseTeste):
    def criar(self, **dados):
        base = {"loja": self.loja, "cliente": self.cliente, "defeito": "não liga"}
        base.update(dados)
        return OrdemServico.objects.create(**base)

    def test_os_basica(self):
        os_ = self.criar(tipo_aparelho="Celular")
        self.assertEqual(montar_laudo(os_),
                         "Aparelho: Celular.\nDefeito relatado pelo cliente: não liga.")

    def test_exemplo_completo(self):
        os_ = self.criar(tipo_aparelho="Celular", marca="Samsung", modelo="A12", status="finalizado",
                         checklist="Liga: Não\nCarrega: Sim\nTela sem danos: Sim")
        ItemOS.objects.create(os=os_, tipo="servico", descricao="Troca de conector de carga",
                              valor_unitario=120, custo_unitario=40)
        ItemOS.objects.create(os=os_, tipo="peca", descricao="Conector de carga",
                              valor_unitario=80, custo_unitario=30)
        self.assertEqual(montar_laudo(os_), "\n".join([
            "Aparelho: Celular Samsung A12.",
            "Defeito relatado pelo cliente: não liga.",
            "Estado na entrada: Liga: Não; Carrega: Sim; Tela sem danos: Sim.",
            "Serviços executados: Troca de conector de carga.",
            "Peças utilizadas: Conector de carga.",
        ]))

    def test_quantidade_maior_que_um(self):
        os_ = self.criar(tipo_aparelho="Celular", defeito="")
        ItemOS.objects.create(os=os_, tipo="servico", descricao="Limpeza", quantidade=2)
        ItemOS.objects.create(os=os_, tipo="peca", descricao="Tela", quantidade=3)
        texto = montar_laudo(os_)
        self.assertIn("Serviços previstos: Limpeza (x2).", texto)
        self.assertIn("Peças previstas: Tela (x3).", texto)

    def test_palavra_conforme_status(self):
        casos = [
            ("finalizado", "executados", "utilizadas"),
            ("pago", "executados", "utilizadas"),
            ("orcamento", "previstos", "previstas"),
            ("em_analise", "previstos", "previstas"),
            ("aguardando_peca", "previstos", "previstas"),
            ("em_servico", "previstos", "previstas"),
            ("cancelado", "previstos", "previstas"),
        ]
        for status, servico, peca in casos:
            with self.subTest(status=status):
                os_ = self.criar(defeito="", status=status)
                ItemOS.objects.create(os=os_, tipo="servico", descricao="Serviço A")
                ItemOS.objects.create(os=os_, tipo="peca", descricao="Peça A")
                texto = montar_laudo(os_)
                self.assertIn(f"Serviços {servico}: Serviço A.", texto)
                self.assertIn(f"Peças {peca}: Peça A.", texto)

    def test_nao_duplica_ponto_final(self):
        os_ = self.criar(tipo_aparelho="Celular!", defeito="não liga.", checklist="Liga: Não!")
        ItemOS.objects.create(os=os_, tipo="servico", descricao="Troca.")
        texto = montar_laudo(os_)
        self.assertIn("Aparelho: Celular!", texto)
        self.assertIn("Defeito relatado pelo cliente: não liga.", texto)
        self.assertIn("Estado na entrada: Liga: Não!", texto)
        self.assertIn("Serviços previstos: Troca.", texto)
        self.assertNotIn("..", texto)

    def test_checklist_antigo_ignora_rotulo_sem_valor(self):
        os_ = self.criar(defeito="", checklist="Liga: Não\nCarrega:\nTela: Sim\n\n")
        self.assertEqual(montar_laudo(os_), "Estado na entrada: Liga: Não; Tela: Sim.")

    def test_texto_nao_expoe_dados_sensiveis(self):
        self.cliente.nome = "Maria Segredo"
        self.cliente.telefone = "86999998888"
        self.cliente.documento = "11122233344"
        self.cliente.save()
        self.loja.termo_garantia = "Garantia de 90 dias sobre o serviço executado."
        self.loja.save()
        os_ = self.criar(tipo_aparelho="Celular", senha_aparelho="SENHA1234",
                         imei="123456789012345", numero_serie="SERIE777", desconto=99)
        ItemOS.objects.create(os=os_, tipo="peca", descricao="Tela", valor_unitario=500, custo_unitario=400)
        texto = montar_laudo(os_)
        for proibido in ("Maria Segredo", "86999998888", "11122233344", "SENHA1234",
                         "123456789012345", "SERIE777", "500", "400", "99", "R$",
                         "Garantia", "custo", "desconto", "total"):
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido, texto)


@skipUnless(hasattr(OrdemServico, "checklist_itens"), "modelo sem checklist estruturado")
class ChecklistEstruturadoLaudoTest(BaseTeste):
    def test_apenas_itens_respondidos_e_observacao(self):
        os_ = self.criar_os()
        os_.checklist_itens = [
            {"nome": "Liga", "resposta": "nao"},
            {"nome": "Carrega", "resposta": "sim"},
            {"nome": "Sem resposta", "resposta": ""},
        ]
        if hasattr(os_, "observacao_entrada"):
            os_.observacao_entrada = "Queda antes do envio"
        os_.save()
        texto = montar_laudo(os_)
        self.assertIn("Estado na entrada: Liga: Não; Carrega: Sim.", texto)
        self.assertNotIn("Sem resposta", texto)
        if hasattr(os_, "observacao_entrada"):
            self.assertIn("Observações na entrada: Queda antes do envio.", texto)


class LaudoSugeridoAPITest(BaseTeste):
    def setUp(self):
        super().setUp()
        self.os = OrdemServico.objects.create(
            loja=self.loja, cliente=self.cliente, tecnico=self.tecnico, status="finalizado",
            tipo_aparelho="Celular", marca="Samsung", modelo="A12", defeito="não liga", laudo="Laudo antigo",
        )
        ItemOS.objects.create(os=self.os, tipo="servico", descricao="Troca de conector", valor_unitario=100)

    def url(self, os_id=None):
        return f"/api/os/{os_id or self.os.id}/laudo-sugerido/"

    def test_admin_atendente_e_tecnico_recebem_texto(self):
        for usuario in (self.admin, self.atendente, self.tecnico):
            with self.subTest(usuario=usuario.username):
                self.autenticar(usuario)
                r = self.client.get(self.url())
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(set(r.data), {"texto"})
                self.assertIn("Serviços executados: Troca de conector.", r.data["texto"])

    def test_outra_loja_recebe_404(self):
        os_b = self.criar_os(loja=self.outra_loja)
        self.autenticar(self.admin)
        self.assertEqual(self.client.get(self.url(os_b.id)).status_code, 404)

    def test_tecnico_fora_da_os_recebe_404(self):
        os_outro = self.criar_os(tecnico=self.tecnico2)
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get(self.url(os_outro.id)).status_code, 404)

    def test_sem_login_recebe_401(self):
        self.assertEqual(self.client.get(self.url()).status_code, 401)

    def test_post_nao_e_permitido(self):
        self.autenticar(self.admin)
        self.assertEqual(self.client.post(self.url()).status_code, 405)

    def test_chamar_endpoint_nao_grava_nada(self):
        self.autenticar(self.admin)
        antes = OrdemServico.objects.get(pk=self.os.pk)
        laudo_antes, atualizado_antes = antes.laudo, antes.atualizado_em
        historico_antes = list(HistoricoStatus.objects.filter(os=self.os).values_list("status", flat=True))
        itens_antes = list(ItemOS.objects.filter(os=self.os).values_list("id", "descricao", "quantidade"))
        lancamentos_antes = Lancamento.objects.count()

        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)

        depois = OrdemServico.objects.get(pk=self.os.pk)
        self.assertEqual(depois.laudo, laudo_antes)
        self.assertEqual(depois.atualizado_em, atualizado_antes)
        self.assertEqual(list(HistoricoStatus.objects.filter(os=self.os).values_list("status", flat=True)),
                         historico_antes)
        self.assertEqual(list(ItemOS.objects.filter(os=self.os).values_list("id", "descricao", "quantidade")),
                         itens_antes)
        self.assertEqual(Lancamento.objects.count(), lancamentos_antes)
