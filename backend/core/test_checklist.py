from .models import ItemChecklist, Loja, OrdemServico
from .tests import BaseTeste


class ItensChecklist(BaseTeste):
    def setUp(self):
        super().setUp()
        self.autenticar(self.admin)
        self.client.get("/api/checklist-itens/")

    def lista(self, categoria=None):
        url = "/api/checklist-itens/"
        if categoria:
            url += f"?categoria={categoria}"
        return self.client.get(url)

    def criar(self, **extra):
        dados = {"cliente": self.cliente.id, "defeito": "Não liga", "categoria": "celular",
                 "marca": "Samsung", "modelo": "A10"}
        dados.update(extra)
        return self.client.post("/api/os/", dados, format="json")

    def test_padrao_criado_uma_vez_e_nao_recriado(self):
        self.autenticar(self.atendente)
        r = self.lista()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 9)
        self.assertTrue(Loja.objects.get(pk=self.loja.pk).checklist_padrao_criado)
        ids = [i["id"] for i in r.data]
        self.autenticar(self.admin)
        for item_id in ids:
            self.assertEqual(self.client.delete(f"/api/checklist-itens/{item_id}/").status_code, 204)
        self.autenticar(self.atendente)
        self.assertEqual(len(self.lista().data), 0)
        self.assertTrue(Loja.objects.get(pk=self.loja.pk).checklist_padrao_criado)

    def test_itens_separados_por_categoria(self):
        self.assertEqual([i["nome"] for i in self.lista("celular").data],
                         ["Liga", "Tela sem danos", "Touch funciona", "Câmeras funcionam", "Carrega", "Áudio funciona"])
        self.assertEqual([i["nome"] for i in self.lista("outro").data],
                         ["Liga", "Liga mas não dá vídeo", "Tem danos visíveis"])

    def test_isolamento_entre_lojas(self):
        item_a = ItemChecklist.objects.filter(loja=self.loja).first()
        self.autenticar(self.admin_b)
        self.assertEqual(len(self.lista().data), 9)
        self.assertEqual(self.client.get(f"/api/checklist-itens/{item_a.id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/checklist-itens/{item_a.id}/", {"nome": "Alterado"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/checklist-itens/{item_a.id}/").status_code, 404)
        item_b = ItemChecklist.objects.filter(loja=self.outra_loja).first()
        r = self.client.post("/api/checklist-itens/reordenar/", {
            "categoria": item_a.categoria, "ids": [item_a.id, item_b.id],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_atendente_e_tecnico_listam_mas_nao_escrevem(self):
        item = ItemChecklist.objects.filter(loja=self.loja).first()
        for usuario in (self.atendente, self.tecnico):
            self.autenticar(usuario)
            self.assertEqual(self.lista().status_code, 200)
            self.assertEqual(self.client.post("/api/checklist-itens/", {"categoria": "celular", "nome": "Novo"}, format="json").status_code, 403)
            self.assertEqual(self.client.patch(f"/api/checklist-itens/{item.id}/", {"nome": "Novo"}, format="json").status_code, 403)
            self.assertEqual(self.client.delete(f"/api/checklist-itens/{item.id}/").status_code, 403)
            self.assertEqual(self.client.post("/api/checklist-itens/reordenar/", {
                "categoria": "celular", "ids": [item.id],
            }, format="json").status_code, 403)

    def test_nome_duplicado_com_maiusculas_diferentes(self):
        r = self.client.post("/api/checklist-itens/", {"categoria": "celular", "nome": "  lIgA  "}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Já existe um item com esse nome.", str(r.data))

    def test_limite_de_40_itens_por_categoria(self):
        for i in range(1, 38):
            r = self.client.post("/api/checklist-itens/", {"categoria": "outro", "nome": f"Item {i:02d}"}, format="json")
            self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post("/api/checklist-itens/", {"categoria": "outro", "nome": "Item 41"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Limite de 40 itens por categoria.", str(r.data))
        self.assertEqual(len(self.lista("outro").data), 40)

    def test_reordenar_atomico_e_recusa_ids_invalidos(self):
        ids = [i["id"] for i in self.lista("celular").data]
        r = self.client.post("/api/checklist-itens/reordenar/", {"categoria": "celular", "ids": list(reversed(ids))}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([i["id"] for i in self.lista("celular").data], list(reversed(ids)))

        antes = [i["id"] for i in self.lista("celular").data]
        outro = self.lista("outro").data[0]["id"]
        de_outra_loja = ItemChecklist.objects.create(loja=self.outra_loja, categoria="celular", nome="Externo")
        for ids_invalidos in ([outro], [de_outra_loja.id], [ids[0], ids[0]], ["1"], []):
            with self.subTest(ids=ids_invalidos):
                r = self.client.post("/api/checklist-itens/reordenar/", {
                    "categoria": "celular", "ids": ids_invalidos,
                }, format="json")
                self.assertEqual(r.status_code, 400)
                self.assertEqual([i["id"] for i in self.lista("celular").data], antes)

    def test_os_grava_itens_e_observacao(self):
        r = self.criar(checklist_itens=[{"nome": "Liga", "resposta": "sim"}, {"nome": "Carrega", "resposta": "nao"}],
                       observacao_entrada="  Tela riscada  ")
        self.assertEqual(r.status_code, 201, r.data)
        os_ = OrdemServico.objects.get(pk=r.data["id"])
        self.assertEqual(os_.checklist_itens, [{"nome": "Liga", "resposta": "sim"}, {"nome": "Carrega", "resposta": "nao"}])
        self.assertEqual(os_.observacao_entrada, "Tela riscada")
        self.assertEqual(os_.checklist, "")
        self.assertEqual(r.data["checklist_itens"], os_.checklist_itens)

    def test_renomear_excluir_item_nao_altera_os(self):
        r = self.criar(checklist_itens=[{"nome": "Liga", "resposta": "sim"}, {"nome": "Carrega", "resposta": "nao"}])
        self.assertEqual(r.status_code, 201, r.data)
        os_id = r.data["id"]
        liga = ItemChecklist.objects.get(loja=self.loja, categoria="celular", nome="Liga")
        self.assertEqual(self.client.patch(f"/api/checklist-itens/{liga.id}/", {"nome": "Liga (novo)"}, format="json").status_code, 200)
        carrega = ItemChecklist.objects.get(loja=self.loja, categoria="celular", nome="Carrega")
        self.assertEqual(self.client.delete(f"/api/checklist-itens/{carrega.id}/").status_code, 204)
        det = self.client.get(f"/api/os/{os_id}/").data
        self.assertEqual(det["checklist_itens"], [{"nome": "Liga", "resposta": "sim"}, {"nome": "Carrega", "resposta": "nao"}])

    def test_respostas_e_formatos_invalidos(self):
        casos = [
            {"checklist_itens": {"nome": "Liga", "resposta": "sim"}},
            {"checklist_itens": [{"nome": "Liga", "resposta": "tal"}]},
            {"checklist_itens": [{"nome": "", "resposta": "sim"}]},
            {"checklist_itens": [{"nome": "x" * 81, "resposta": "sim"}]},
            {"checklist_itens": [{"nome": "Liga", "resposta": "sim", "extra": 1}]},
            {"checklist_itens": ["Liga"]},
            {"checklist_itens": [{"nome": "Liga"}]},
            {"checklist_itens": [{"nome": f"I{i}", "resposta": "sim"} for i in range(61)]},
            {"observacao_entrada": "x" * 2001},
        ]
        for i, extra in enumerate(casos):
            with self.subTest(caso=i + 1):
                r = self.criar(**extra)
                self.assertEqual(r.status_code, 400)
                self.assertTrue(str(r.data))

    def test_patch_nao_altera_checklist_nem_observacao(self):
        r = self.criar(checklist_itens=[{"nome": "Liga", "resposta": "sim"}], observacao_entrada="Original")
        os_id = r.data["id"]
        r = self.client.patch(f"/api/os/{os_id}/", {
            "checklist_itens": [{"nome": "Liga", "resposta": "nao"}], "observacao_entrada": "Nova",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        det = self.client.get(f"/api/os/{os_id}/").data
        self.assertEqual(det["checklist_itens"], [{"nome": "Liga", "resposta": "sim"}])
        self.assertEqual(det["observacao_entrada"], "Original")

    def test_observacao_e_opcional(self):
        r = self.criar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["checklist_itens"], [])
        self.assertEqual(r.data["observacao_entrada"], "")

    def test_os_antiga_com_texto_continua_valida(self):
        texto = "Liga: ok\nTela: com defeito"
        r = self.criar(checklist=texto)
        self.assertEqual(r.status_code, 201, r.data)
        os_ = OrdemServico.objects.get(pk=r.data["id"])
        self.assertEqual(os_.checklist, texto)
        self.assertEqual(os_.checklist_itens, [])
        self.assertEqual(os_.observacao_entrada, "")
        self.assertEqual(self.client.get(f"/api/os/{os_.id}/pdf/").status_code, 200)

    def test_pdf_com_itens_e_texto_do_usuario(self):
        r = self.criar(checklist_itens=[{"nome": "Liga <b> &", "resposta": "sim"}],
                       observacao_entrada="Obs <x> & y")
        self.assertEqual(r.status_code, 201, r.data)
        pdf = self.client.get(f"/api/os/{r.data['id']}/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
