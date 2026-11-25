from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Count, F, Max, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .estoque import baixar_estoque, baixar_itens, devolver_estoque, devolver_itens
from .exportacao import exportar_clientes, exportar_pecas, resposta_xlsx
from .imagens import processar_assinatura
from .models import Cliente, FotoOS, ItemChecklist, ItemOS, Lancamento, Loja, OrdemServico, Peca, Usuario
from .permissoes import ordens_visiveis
from .pdf import gerar_pdf_os
from .serializers import (ClienteSerializer, FotoSerializer, ItemChecklistSerializer, ItemOSSerializer,
                          LancamentoSerializer, LojaSerializer, OSListaSerializer, OSSerializer, PecaSerializer,
                          UsuarioSerializer)
from .sessoes import invalidar_tokens

FORMAS_PAGAMENTO = {"dinheiro", "pix", "debito", "credito", "outro"}
CHECKLIST_PADRAO = {
    OrdemServico.Categoria.CELULAR: ["Liga", "Tela sem danos", "Touch funciona", "Câmeras funcionam", "Carrega", "Áudio funciona"],
    OrdemServico.Categoria.OUTRO: ["Liga", "Liga mas não dá vídeo", "Tem danos visíveis"],
}


def exigir_pagamento_para_pago(os_, novo):
    """Só vira 'Pago' quem tem pagamentos registrados cobrindo o total (use a ação 'pagar')."""
    if novo == OrdemServico.Status.PAGO and os_.pago < os_.total:
        raise ValidationError({"detail": "Registre o pagamento da OS para marcá-la como Paga."})


class TemLoja(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.loja_id)


class SoAdmin(TemLoja):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.eh_admin


class LojaViewSet(viewsets.ModelViewSet):
    """Isola os dados: cada usuário só enxerga/grava na própria loja."""
    permission_classes = [TemLoja]

    def get_queryset(self):
        return super().get_queryset().filter(loja=self.request.user.loja)

    def perform_create(self, serializer):
        serializer.save(loja=self.request.user.loja)


class ClienteViewSet(LojaViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    search_fields = ["nome", "telefone", "documento"]


class PecaViewSet(LojaViewSet):
    queryset = Peca.objects.all()
    serializer_class = PecaSerializer
    search_fields = ["nome", "sku"]

    @action(detail=False)
    def por_codigo(self, request):
        p = self.get_queryset().filter(sku=request.query_params.get("codigo", "")).first()
        return Response(PecaSerializer(p, context={"request": request}).data) if p else Response(status=404)


class ChecklistItemViewSet(LojaViewSet):
    queryset = ItemChecklist.objects.all()
    serializer_class = ItemChecklistSerializer
    filterset_fields = ["categoria"]
    pagination_class = None

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [TemLoja()]
        return [SoAdmin()]

    def get_queryset(self):
        return super().get_queryset().order_by("ordem", "id")

    def _garantir_padrao(self, loja):
        if loja.checklist_padrao_criado:
            return
        with transaction.atomic():
            bloqueada = Loja.objects.select_for_update().get(pk=loja.pk)
            if bloqueada.checklist_padrao_criado:
                return
            existentes = {
                (categoria, nome.lower())
                for categoria, nome in ItemChecklist.objects.filter(loja=bloqueada).values_list("categoria", "nome")
            }
            for categoria, nomes in CHECKLIST_PADRAO.items():
                for ordem, nome in enumerate(nomes, start=1):
                    if (categoria, nome.lower()) not in existentes:
                        ItemChecklist.objects.create(loja=bloqueada, categoria=categoria, nome=nome, ordem=ordem)
            bloqueada.checklist_padrao_criado = True
            bloqueada.save(update_fields=["checklist_padrao_criado"])

    def list(self, request, *args, **kwargs):
        self._garantir_padrao(request.user.loja)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        loja = self.request.user.loja
        categoria = serializer.validated_data["categoria"]
        ultimo = ItemChecklist.objects.filter(loja=loja, categoria=categoria).aggregate(m=Max("ordem"))["m"] or 0
        serializer.save(loja=loja, ordem=ultimo + 1)

    @action(detail=False, methods=["post"])
    def reordenar(self, request):
        categoria = request.data.get("categoria")
        ids = request.data.get("ids")
        if categoria not in OrdemServico.Categoria.values:
            raise ValidationError("Categoria inválida.")
        if not isinstance(ids, list) or not ids or len(ids) > 40 or any(type(i) is not int for i in ids):
            raise ValidationError("Lista de ids inválida.")
        if len(set(ids)) != len(ids):
            raise ValidationError("Ids repetidos não são permitidos.")
        itens = {i.id: i for i in self.get_queryset().filter(categoria=categoria, id__in=ids)}
        if len(itens) != len(ids):
            raise ValidationError("Itens inválidos para esta loja e categoria.")
        with transaction.atomic():
            for ordem, item_id in enumerate(ids, start=1):
                ItemChecklist.objects.filter(pk=item_id).update(ordem=ordem)
        return Response({"ok": True})


class OSViewSet(LojaViewSet):
    queryset = OrdemServico.objects.all()
    serializer_class = OSSerializer
    filterset_fields = ["status", "cliente"]
    search_fields = ["numero", "cliente__nome", "modelo", "marca", "numero_serie", "imei", "tipo_aparelho"]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        qs = ordens_visiveis(self.request.user).select_related("cliente")
        if self.action == "list":
            return qs.prefetch_related("itens", "lancamentos")
        return qs.prefetch_related("itens", "fotos", "historico", "lancamentos")

    def get_serializer_class(self):
        return OSListaSerializer if self.action == "list" else OSSerializer

    def perform_create(self, serializer):
        serializer.save(loja=self.request.user.loja)

    @staticmethod
    def _transicionar_estoque(os_, novo):
        if novo == os_.status:
            return
        itens = list(os_.itens.select_related("peca"))
        if novo == OrdemServico.Status.CANCELADO and os_.status != OrdemServico.Status.CANCELADO:
            devolver_itens(itens)
        elif os_.status == OrdemServico.Status.CANCELADO and novo != OrdemServico.Status.CANCELADO:
            baixar_itens(itens)

    def perform_update(self, serializer):
        with transaction.atomic():
            OrdemServico.objects.select_for_update().filter(pk=serializer.instance.pk).first()
            antigo = serializer.instance.status
            novo = serializer.validated_data.get("status", antigo)
            if novo != antigo:
                exigir_pagamento_para_pago(serializer.instance, novo)
            self._transicionar_estoque(serializer.instance, novo)
            os_ = serializer.save()
            if os_.status != antigo:
                os_.historico.create(status=os_.status)

    def perform_destroy(self, inst):
        if not self.request.user.eh_admin:
            raise PermissionDenied("Só administradores podem excluir OS.")
        with transaction.atomic():
            if inst.status != OrdemServico.Status.CANCELADO:
                devolver_itens(list(inst.itens.select_related("peca")))
            inst.delete()

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        novo = request.data.get("status")
        if novo not in OrdemServico.Status.values:
            return Response({"detail": "Status inválido."}, status=400)
        with transaction.atomic():
            os_ = OrdemServico.objects.select_for_update().filter(pk=self.get_object().pk).first()
            if novo != os_.status:
                exigir_pagamento_para_pago(os_, novo)
            self._transicionar_estoque(os_, novo)
            os_.mudar_status(novo)
        return Response(OSSerializer(os_, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def assinar(self, request, pk=None):
        """Recebe a assinatura como data URL (canvas) e salva como PNG."""
        os_ = self.get_object()
        os_.assinatura.save("assinatura.png", processar_assinatura(request.data.get("assinatura", "")))
        return Response(OSSerializer(os_, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def pagar(self, request, pk=None):
        with transaction.atomic():
            os_ = OrdemServico.objects.select_for_update().filter(pk=self.get_object().pk).first()
            if os_.status == OrdemServico.Status.CANCELADO:
                return Response({"detail": "OS cancelada não recebe pagamento. Reabra a OS primeiro."}, status=400)
            restante = os_.total - os_.pago
            if restante <= 0:
                return Response({"detail": "Esta OS já está quitada."}, status=400)
            bruto = request.data.get("valor")
            try:
                valor = Decimal(str(bruto)) if bruto not in (None, "") else restante
            except (ArithmeticError, TypeError, ValueError):
                return Response({"detail": "Informe um valor de pagamento válido."}, status=400)
            if not valor.is_finite():
                return Response({"detail": "Informe um valor de pagamento válido."}, status=400)
            forma = request.data.get("forma", "dinheiro")
            if forma not in FORMAS_PAGAMENTO:
                return Response({"detail": "Forma de pagamento inválida."}, status=400)
            valor = valor.quantize(Decimal("0.01"))
            if valor <= 0:
                return Response({"detail": "O valor do pagamento deve ser maior que zero."}, status=400)
            if valor > restante:
                return Response({"detail": f"O valor máximo para esta OS é R$ {restante:.2f}.".replace(".", ",")},
                                status=400)
            Lancamento.objects.create(loja=os_.loja, tipo="entrada", descricao=f"OS #{os_.numero} - {os_.cliente.nome}",
                                      valor=valor, forma=forma, os=os_)
            os_.refresh_from_db()
            if os_.pago >= os_.total:
                os_.mudar_status(OrdemServico.Status.PAGO)
        return Response(OSSerializer(os_, context={"request": request}).data)

    @action(detail=True)
    def whatsapp(self, request, pk=None):
        os_ = self.get_object()
        base = settings.FRONTEND_URL or request.build_absolute_uri("/").rstrip("/")
        link = f"{base}/r/{os_.token}"
        if os_.status == "orcamento":
            msg = (f"Olá, {os_.cliente.nome}! Segue o orçamento do seu {os_.marca} {os_.modelo} na {os_.loja.nome}: "
                   f"*R$ {os_.total:.2f}*. Acompanhe e veja os detalhes: {link}")
        else:
            msg = (f"Olá, {os_.cliente.nome}! Sua OS #{os_.numero} ({os_.marca} {os_.modelo}) está: "
                   f"*{os_.get_status_display()}*. Acompanhe em tempo real: {link}")
        fone = "".join(c for c in os_.cliente.telefone if c.isdigit())
        if fone and not fone.startswith("55"):
            fone = "55" + fone
        return Response({"url": f"https://wa.me/{fone}?text={quote(msg)}", "mensagem": msg})

    @action(detail=True)
    def pdf(self, request, pk=None):
        os_ = self.get_object()
        r = HttpResponse(gerar_pdf_os(os_), content_type="application/pdf")
        r["Content-Disposition"] = f'inline; filename="os-{os_.numero}.pdf"'
        return r


class ItemOSViewSet(viewsets.ModelViewSet):
    """Adicionar/editar/remover peça dá baixa/devolve automaticamente no estoque."""
    permission_classes = [TemLoja]
    serializer_class = ItemOSSerializer
    filterset_fields = ["os"]

    def get_queryset(self):
        return ItemOS.objects.filter(os__in=ordens_visiveis(self.request.user)).order_by("id")

    @staticmethod
    def _os_editavel(os_):
        if os_.status == OrdemServico.Status.CANCELADO:
            raise ValidationError({"detail": "OS cancelada. Reabra a OS antes de alterar itens."})

    def perform_create(self, serializer):
        with transaction.atomic():
            os_ = OrdemServico.objects.select_for_update().get(pk=serializer.validated_data["os"].pk)
            self._os_editavel(os_)
            item = serializer.save()
            if item.peca_id:
                baixar_estoque(item.peca_id, item.quantidade)

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            inst = ItemOS.objects.select_for_update().get(pk=self.get_object().pk)
            os_ = OrdemServico.objects.select_for_update().get(pk=inst.os_id)
            self._os_editavel(os_)
            dados = {k: v for k, v in request.data.items()
                     if k in {"quantidade", "valor_unitario", "descricao"}}
            serializer = self.get_serializer(inst, data=dados, partial=True)
            serializer.is_valid(raise_exception=True)
            nova = serializer.validated_data.get("quantidade", inst.quantidade)
            diferenca = nova - inst.quantidade
            if inst.peca_id and diferenca:
                if diferenca > 0:
                    baixar_estoque(inst.peca_id, diferenca)
                else:
                    devolver_estoque(inst.peca_id, -diferenca)
            item = serializer.save()
            return Response(self.get_serializer(item).data)

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            inst = ItemOS.objects.select_for_update().get(pk=self.get_object().pk)
            os_ = OrdemServico.objects.select_for_update().get(pk=inst.os_id)
            self._os_editavel(os_)
            if inst.peca_id:
                devolver_estoque(inst.peca_id, inst.quantidade)
            inst.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class FotoViewSet(viewsets.ModelViewSet):
    permission_classes = [TemLoja]
    serializer_class = FotoSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["os"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        return FotoOS.objects.filter(os__in=ordens_visiveis(self.request.user)).order_by("id")

    def perform_create(self, serializer):
        if not ordens_visiveis(self.request.user).filter(pk=serializer.validated_data["os"].pk).exists():
            raise PermissionDenied()
        serializer.save()

    def update(self, request, *args, **kwargs):
        inst = self.get_object()
        dados = {k: v for k, v in request.data.items() if k in {"legenda", "visivel_cliente", "tipo"}}
        serializer = self.get_serializer(inst, data=dados, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LancamentoViewSet(LojaViewSet):
    permission_classes = [SoAdmin]
    queryset = Lancamento.objects.all()
    serializer_class = LancamentoSerializer
    filterset_fields = ["tipo", "data"]
    search_fields = ["descricao"]

    def get_queryset(self):
        qs = super().get_queryset()
        de, ate = self.request.query_params.get("de"), self.request.query_params.get("ate")
        if de:
            qs = qs.filter(data__gte=de)
        if ate:
            qs = qs.filter(data__lte=ate)
        return qs

    def perform_update(self, serializer):
        if serializer.instance.os_id:
            raise ValidationError({"detail": "Pagamento de OS não pode ser editado. Exclua e registre de novo."})
        serializer.save()

    def perform_destroy(self, inst):
        with transaction.atomic():
            os_ = inst.os
            inst.delete()
            if os_ and os_.status == OrdemServico.Status.PAGO:
                os_ = OrdemServico.objects.prefetch_related("itens", "lancamentos").get(pk=os_.pk)
                if os_.pago < os_.total:
                    os_.mudar_status(OrdemServico.Status.FINALIZADO)

    @action(detail=False)
    def resumo(self, request):
        qs = self.filter_queryset(self.get_queryset())

        def soma(tipo):
            return qs.filter(tipo=tipo).aggregate(s=Sum("valor"))["s"] or Decimal("0")

        e, s = soma("entrada"), soma("saida")
        return Response({"entradas": e, "saidas": s, "saldo": e - s})


class UsuarioViewSet(viewsets.ModelViewSet):
    permission_classes = [SoAdmin]
    serializer_class = UsuarioSerializer

    def get_queryset(self):
        return Usuario.objects.filter(loja=self.request.user.loja).order_by("username")

    def perform_create(self, serializer):
        serializer.save(loja=self.request.user.loja)

    def perform_update(self, serializer):
        # Ao desativar um usuário, encerra as sessões dele (refresh tokens na blacklist).
        ativo_antes = serializer.instance.is_active
        usuario = serializer.save()
        if ativo_antes and not usuario.is_active:
            invalidar_tokens(usuario)

    def perform_destroy(self, inst):
        if inst.pk == self.request.user.pk:
            raise ValidationError({"detail": "Você não pode excluir o próprio usuário."})
        inst.delete()


class Login(TokenObtainPairView):
    """Login com limite de tentativas por IP (o cadastro público não existe mais)."""
    throttle_scope = "auth"


class Refresh(TokenRefreshView):
    """Renovação de token: limite próprio, mais folgado que o do login."""
    throttle_scope = "refresh"


class TrocarSenha(APIView):
    """Troca a própria senha exigindo a senha atual (usada no primeiro acesso)."""

    throttle_scope = "senha"

    def post(self, request):
        atual = request.data.get("senha_atual", "")
        nova = request.data.get("nova_senha", "")
        if not request.user.check_password(atual):
            return Response({"detail": "Senha atual incorreta."}, status=400)
        try:
            validate_password(nova, request.user)
        except DjangoValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=400)
        request.user.set_password(nova)
        request.user.save(update_fields=["password"])
        # Encerra as sessões antigas e devolve um par novo para a sessão atual seguir logada.
        invalidar_tokens(request.user)
        novo_refresh = RefreshToken.for_user(request.user)
        return Response({
            "detail": "Senha alterada com sucesso.",
            "access": str(novo_refresh.access_token),
            "refresh": str(novo_refresh),
        })


class ExportarClientes(APIView):
    permission_classes = [SoAdmin]

    def get(self, request):
        wb = exportar_clientes(request.user.loja)
        return resposta_xlsx(wb, f"clientes-{timezone.localdate():%Y-%m-%d}.xlsx")


class ExportarPecas(APIView):
    permission_classes = [SoAdmin]

    def get(self, request):
        wb = exportar_pecas(request.user.loja)
        return resposta_xlsx(wb, f"pecas-{timezone.localdate():%Y-%m-%d}.xlsx")


class Eu(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        return Response(UsuarioSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        if not request.user.eh_admin or not request.user.loja:
            return Response(status=403)
        s = LojaSerializer(request.user.loja, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response(UsuarioSerializer(request.user, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([TemLoja])
def dashboard(request):
    loja = request.user.loja
    ordens = ordens_visiveis(request.user)
    contagem = dict(ordens.values_list("status").annotate(n=Count("id")))
    por_status = {s: contagem.get(s, 0) for s in OrdemServico.Status.values}
    out = {"por_status": por_status, "abertas": sum(n for s, n in por_status.items() if s not in ("pago", "cancelado")),
           "estoque_baixo": Peca.objects.filter(loja=loja, quantidade__lte=F("minimo")).count()}
    if request.user.eh_admin:
        ini = timezone.localdate().replace(day=1)
        l = Lancamento.objects.filter(loja=loja, data__gte=ini)  # noqa: E741
        e = l.filter(tipo="entrada").aggregate(s=Sum("valor"))["s"] or 0
        saidas = l.filter(tipo="saida").aggregate(s=Sum("valor"))["s"] or 0
        finalizadas = ordens.filter(status="finalizado").prefetch_related("itens", "lancamentos")
        receber = sum((o.total - o.pago for o in finalizadas), Decimal("0"))
        out.update(entradas_mes=e, saidas_mes=saidas, saldo_mes=e - saidas, a_receber=receber)
    return Response(out)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def saude(request):
    """Checagem de saúde para o UptimeRobot: confirma a conexão com o banco sem expor dados."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return Response({"status": "erro"}, status=503)
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@throttle_classes([ScopedRateThrottle])
def acompanhar(request, token):
    """Link público (sem login) para o cliente ver a etapa do conserto."""
    os_ = get_object_or_404(OrdemServico.objects.select_related("loja", "cliente"), token=token)
    return Response({
        "loja": os_.loja.nome, "loja_telefone": os_.loja.telefone, "numero": os_.numero,
        "cliente": os_.cliente.nome.split()[0], "aparelho": f"{os_.marca} {os_.modelo}".strip() or os_.tipo_aparelho,
        "defeito": os_.defeito, "status": os_.status, "status_label": os_.get_status_display(),
        "previsao_entrega": os_.previsao_entrega, "total": os_.total if os_.status != "em_analise" else None,
        "itens": [{"descricao": i.descricao, "quantidade": i.quantidade, "subtotal": i.subtotal} for i in os_.itens.all()],
        "historico": [{"status": h.status, "label": h.get_status_display(), "em": h.criado_em} for h in os_.historico.all()],
        "fotos": [{"url": f.imagem.url if f.imagem else None, "legenda": f.legenda, "tipo": f.tipo, "criado_em": f.criado_em}
                  for f in os_.fotos.filter(visivel_cliente=True).order_by("criado_em")],
        "garantia_dias": os_.garantia_dias,
    })
acompanhar.cls.throttle_scope = "publico"
