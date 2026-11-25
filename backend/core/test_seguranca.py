"""Testes de regressão da revisão de segurança e qualidade."""
import io
from urllib.parse import quote

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from .models import FotoOS, ItemOS, Lancamento, OrdemServico, Servico
from .tests import BaseTeste


def jpeg_com_rotacao(largura=400, altura=200, orientacao=6):
    img = Image.new("RGB", (largura, altura), "red")
    exif = img.getexif()
    exif[274] = orientacao
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return SimpleUploadedFile("f.jpg", buf.getvalue(), "image/jpeg")


class TecnicoSoMexeNasPropriasOS(BaseTeste):
    def setUp(self):
        super().setUp()
        self.os_outro = self.criar_os(tecnico=self.tecnico2)
        self.os_minha = self.criar_os(tecnico=self.tecnico)
        OrdemServico.objects.update(tipo_aparelho="Placa de vídeo")

    def test_nao_adiciona_item_em_os_de_outro_tecnico(self):
        self.autenticar(self.tecnico)
        self.assertEqual(self.adicionar_item(self.os_outro.id).status_code, 400)
        self.assertEqual(self.adicionar_item(self.os_minha.id).status_code, 201)

    def test_nao_lista_nem_cria_foto_de_os_de_outro(self):
        FotoOS.objects.create(os=self.os_outro, imagem="fotos/x.jpg")
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.get("/api/fotos/").data["count"], 0)
        r = self.client.post("/api/fotos/", {"os": self.os_outro.id, "imagem": jpeg_com_rotacao()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_nao_remove_item_de_os_de_outro(self):
        item = ItemOS.objects.create(os=self.os_outro, tipo="servico", descricao="s", valor_unitario=10)
        self.autenticar(self.tecnico)
        self.assertEqual(self.client.delete(f"/api/itens/{item.id}/").status_code, 404)

    def test_tecnico_nao_altera_desconto_mas_salva_laudo(self):
        self.autenticar(self.tecnico)
        r = self.client.patch(f"/api/os/{self.os_minha.id}/", {"desconto": "10"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f"/api/os/{self.os_minha.id}/", {"laudo": "ok", "desconto": "0"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_atendente_aplica_desconto(self):
        self.autenticar(self.atendente)
        self.adicionar_item(self.os_minha.id)
        r = self.client.patch(f"/api/os/{self.os_minha.id}/", {"desconto": "10"}, format="json")
        self.assertEqual(r.status_code, 200)


class ValoresNaoNegativos(BaseTeste):
    def test_rejeita_valores_negativos(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/pecas/", {"nome": "p", "custo": "-1", "preco": "5", "quantidade": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/pecas/", {"nome": "p", "custo": "1", "preco": "5", "quantidade": -3}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/lancamentos/", {"tipo": "entrada", "descricao": "x", "valor": "-100"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/lancamentos/", {"tipo": "entrada", "descricao": "x", "valor": "0"}, format="json")
        self.assertEqual(r.status_code, 400)
        os_ = self.criar_os()
        r = self.client.patch(f"/api/os/{os_.id}/", {"desconto": "-50"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.adicionar_item(os_.id, valor_unitario="-5").status_code, 400)

    def test_aceita_valores_validos(self):
        self.autenticar(self.admin)
        r = self.client.post("/api/lancamentos/", {"tipo": "saida", "descricao": "luz", "valor": "80.50"}, format="json")
        self.assertEqual(r.status_code, 201)


class PagoExigePagamento(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.os = self.criar_os()
        self.adicionar_item(self.os.id, valor_unitario="100")

    def test_nao_marca_pago_sem_pagamento(self):
        r = self.client.post(f"/api/os/{self.os.id}/status/", {"status": "pago"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f"/api/os/{self.os.id}/", {"status": "pago"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.os.refresh_from_db()
        self.assertNotEqual(self.os.status, "pago")

    def test_pagar_quita_e_marca_pago(self):
        r = self.client.post(f"/api/os/{self.os.id}/pagar/", {"forma": "pix"}, format="json")
        self.assertEqual(r.data["status"], "pago")

    def test_excluir_pagamento_reabre_a_os(self):
        self.client.post(f"/api/os/{self.os.id}/pagar/", {"forma": "pix"}, format="json")
        lanc = Lancamento.objects.get(os=self.os)
        self.assertEqual(self.client.delete(f"/api/lancamentos/{lanc.id}/").status_code, 204)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, "finalizado")

    def test_pagamento_de_os_nao_e_editavel(self):
        self.client.post(f"/api/os/{self.os.id}/pagar/", {"forma": "pix"}, format="json")
        lanc = Lancamento.objects.get(os=self.os)
        r = self.client.patch(f"/api/lancamentos/{lanc.id}/", {"valor": "1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_forma_de_pagamento_invalida(self):
        r = self.client.post(f"/api/os/{self.os.id}/pagar/", {"forma": "x" * 40, "valor": "10"}, format="json")
        self.assertEqual(r.status_code, 400)


class PdfEFotos(BaseTeste):
    def test_pdf_aceita_caracteres_especiais(self):
        self.autenticar(self.admin)
        self.loja.nome = "Tec <Nova> & Cia"
        self.loja.save()
        os_ = OrdemServico.objects.create(loja=self.loja, cliente=self.cliente, defeito="tela <b quebrada & riscada",
                                          tipo_aparelho="Placa")
        r = self.client.get(f"/api/os/{os_.id}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_foto_respeita_rotacao_exif(self):
        self.autenticar(self.admin)
        os_ = self.criar_os()
        r = self.client.post("/api/fotos/", {"os": os_.id, "imagem": jpeg_com_rotacao()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        img = Image.open(FotoOS.objects.get().imagem.path)
        self.assertEqual(img.size, (200, 400))  # 400x200 com rotação 6 vira retrato


class LinkWhatsapp(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.os = self.criar_os()

    @override_settings(FRONTEND_URL="")
    def test_link_usa_endereco_de_acesso_sem_frontend_url(self):
        r = self.client.get(f"/api/os/{self.os.id}/whatsapp/")
        link = f"http://testserver/r/{self.os.token}"
        self.assertEqual(r.status_code, 200)
        self.assertIn(link, r.data["mensagem"])
        self.assertNotIn("em tempo real: /r/", r.data["mensagem"])
        self.assertTrue(r.data["url"].startswith("https://wa.me/55"))
        self.assertIn(quote(link), r.data["url"])

    @override_settings(FRONTEND_URL="https://exemplo.com.br")
    def test_frontend_url_tem_prioridade(self):
        r = self.client.get(f"/api/os/{self.os.id}/whatsapp/")
        self.assertIn(f"https://exemplo.com.br/r/{self.os.token}", r.data["mensagem"])

    @override_settings(FRONTEND_URL="")
    def test_orcamento_usa_link_completo(self):
        os_ = self.criar_os(status="orcamento")
        r = self.client.get(f"/api/os/{os_.id}/whatsapp/")
        link = f"http://testserver/r/{os_.token}"
        self.assertEqual(r.status_code, 200)
        self.assertIn(link, r.data["mensagem"])
        self.assertTrue(r.data["url"].startswith("https://wa.me/55"))
        self.assertIn(quote(link), r.data["url"])


class Desempenho(BaseTeste):
    def test_listagem_nao_faz_consulta_por_os(self):
        self.autenticar(self.admin)
        for _ in range(25):
            os_ = self.criar_os()
            ItemOS.objects.create(os=os_, tipo="servico", descricao="s", valor_unitario=10)
        with self.assertNumQueries(4):  # contagem, OS+cliente, itens, lançamentos
            r = self.client.get("/api/os/")
        self.assertEqual(r.data["count"], 25)
        self.assertNotIn("fotos", r.data["results"][0])

    def test_numeracao_sequencial_por_loja(self):
        a, b = self.criar_os(), self.criar_os()
        self.assertEqual((a.numero, b.numero), (1, 2))
        outra = self.criar_os(loja=self.outra_loja)
        self.assertEqual(outra.numero, 1)


class Servicos(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.servico = Servico.objects.create(loja=self.loja, nome="Troca de tela", preco="120.00")
        self.servico_b = Servico.objects.create(loja=self.outra_loja, nome="Serviço da loja B", preco="90.00")

    def adicionar_servico(self, os_id, servico_id):
        return self.client.post("/api/itens/", {
            "os": os_id, "tipo": "servico", "servico": servico_id, "quantidade": 2,
        }, format="json")

    def test_crud(self):
        r = self.client.post("/api/servicos/", {"nome": "Limpeza", "preco": "50.00"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data["id"]
        self.assertTrue(r.data["ativo"])
        self.assertEqual(self.client.get("/api/servicos/").data["count"], 2)
        self.assertEqual(self.client.get(f"/api/servicos/{sid}/").data["nome"], "Limpeza")
        r = self.client.patch(f"/api/servicos/{sid}/", {"nome": "Limpeza completa", "preco": "60.00"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.servico.refresh_from_db()
        self.assertEqual(Servico.objects.get(pk=sid).nome, "Limpeza completa")
        self.assertEqual(self.client.delete(f"/api/servicos/{sid}/").status_code, 204)
        self.assertFalse(Servico.objects.filter(pk=sid).exists())

    def test_busca_e_filtro_por_ativo(self):
        self.servico.ativo = False
        self.servico.save()
        self.assertEqual(self.client.get("/api/servicos/?ativo=true").data["count"], 0)
        self.assertEqual(self.client.get("/api/servicos/?ativo=false").data["count"], 1)
        self.assertEqual(self.client.get("/api/servicos/?search=Serviço da loja").data["count"], 0)
        self.assertEqual(self.client.get("/api/servicos/?search=troca").data["count"], 1)

    def test_isolamento_entre_lojas(self):
        self.autenticar(self.admin_b)
        self.assertEqual(self.client.get("/api/servicos/").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/servicos/{self.servico.id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/servicos/{self.servico.id}/", {"preco": "1"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/servicos/{self.servico.id}/").status_code, 404)
        os_b = self.criar_os(loja=self.outra_loja)
        r = self.adicionar_servico(os_b.id, self.servico.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Serviço inválido.", str(r.data))

    def test_atendente_e_tecnico_listam_mas_nao_escrevem(self):
        for usuario in (self.atendente, self.tecnico):
            self.autenticar(usuario)
            self.assertEqual(self.client.get("/api/servicos/").status_code, 200)
            self.assertEqual(self.client.get("/api/servicos/").data["count"], 1)
            self.assertEqual(self.client.post("/api/servicos/", {"nome": "Novo", "preco": "1"}, format="json").status_code, 403)
            self.assertEqual(self.client.patch(f"/api/servicos/{self.servico.id}/", {"preco": "1"}, format="json").status_code, 403)
            self.assertEqual(self.client.delete(f"/api/servicos/{self.servico.id}/").status_code, 403)

    def test_preco_negativo_recusado(self):
        r = self.client.post("/api/servicos/", {"nome": "Negativo", "preco": "-1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nome_duplicado_na_mesma_loja_recusado(self):
        r = self.client.post("/api/servicos/", {"nome": "  troca DE tela  ", "preco": "10"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Já existe um serviço com esse nome nesta loja.", str(r.data))
        self.assertEqual(self.client.patch(f"/api/servicos/{self.servico.id}/", {"nome": "TROCA DE TELA"}, format="json").status_code, 200)
        self.autenticar(self.admin_b)
        self.assertEqual(self.client.post("/api/servicos/", {"nome": "Troca de tela", "preco": "10"}, format="json").status_code, 201)

    def test_item_com_servico_copia_nome_e_valor(self):
        os_ = self.criar_os()
        r = self.adicionar_servico(os_.id, self.servico.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["descricao"], "Troca de tela")
        self.assertEqual(float(r.data["valor_unitario"]), 120.0)
        self.assertEqual(float(r.data["subtotal"]), 240.0)

    def test_alterar_preco_ou_excluir_servico_nao_muda_os_criada(self):
        os_ = self.criar_os()
        item_id = self.adicionar_servico(os_.id, self.servico.id).data["id"]
        self.servico.preco = "999.00"
        self.servico.save()
        self.servico.delete()
        item = ItemOS.objects.get(pk=item_id)
        self.assertEqual(item.descricao, "Troca de tela")
        self.assertEqual(float(item.valor_unitario), 120.0)
        os_.refresh_from_db()
        self.assertEqual(float(os_.total), 240.0)

    def test_servico_inativo_recusado_na_os(self):
        self.servico.ativo = False
        self.servico.save()
        r = self.adicionar_servico(self.criar_os().id, self.servico.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Serviço inválido.", str(r.data))

    def test_servico_so_no_tipo_servico(self):
        r = self.client.post("/api/itens/", {
            "os": self.criar_os().id, "tipo": "peca", "peca": self.peca.id,
            "servico": self.servico.id, "quantidade": 1,
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Serviço só pode ser usado no tipo serviço.", str(r.data))

    def test_os_cancelada_continua_bloqueando_itens(self):
        os_ = self.criar_os(status="cancelado")
        r = self.adicionar_servico(os_.id, self.servico.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("OS cancelada", str(r.data))

    def test_servico_avulso_continua_funcionando(self):
        r = self.adicionar_item(self.criar_os().id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["descricao"], "Mão de obra")
