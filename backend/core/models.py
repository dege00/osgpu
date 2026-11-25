import os
import re
import secrets
import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Max
from django.db.models.functions import Lower
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .imagens import reduzir_imagem


def gerar_token():
    return secrets.token_urlsafe(8)


def _extensao_segura(filename, padrao=".jpg"):
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in {".jpg", ".jpeg", ".png", ".webp"} else padrao


def caminho_foto(instance, filename):
    """Nome aleatório: dificulta a enumeração de fotos de outras lojas."""
    return f"fotos/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{_extensao_segura(filename)}"


def caminho_assinatura(instance, filename):
    return f"assinaturas/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.png"


def caminho_tema(instance, filename):
    return f"tema/{uuid.uuid4().hex}{_extensao_segura(filename)}"


def caminho_tema_video(instance, filename):
    extensao = os.path.splitext(filename or "")[1].lower()
    return f"tema/{uuid.uuid4().hex}{extensao if extensao in {'.mp4', '.webm', '.ogv'} else '.mp4'}"


def caminho_logo(instance, filename):
    return f"logos/{uuid.uuid4().hex}{_extensao_segura(filename)}"


class Loja(models.Model):
    """Cada assistência técnica = 1 loja (multiempresa / SaaS)."""
    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=20, blank=True)
    documento = models.CharField("CNPJ/CPF", max_length=20, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    termo_garantia = models.TextField(blank=True, default="Garantia de 90 dias sobre o serviço executado. Não cobre mau uso, queda ou contato com líquidos.")
    checklist_padrao_criado = models.BooleanField(default=False)
    logo = models.ImageField(upload_to=caminho_logo, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Usuario(AbstractUser):
    class Cargo(models.TextChoices):
        ADMIN = "admin", "Administrador"
        ATENDENTE = "atendente", "Atendente"
        TECNICO = "tecnico", "Técnico"

    loja = models.ForeignKey(Loja, null=True, blank=True, on_delete=models.CASCADE, related_name="usuarios")
    cargo = models.CharField(max_length=12, choices=Cargo.choices, default=Cargo.ADMIN)
    telefone = models.CharField(max_length=20, blank=True)

    @property
    def eh_admin(self):
        return self.cargo == self.Cargo.ADMIN or self.is_superuser


class PorLoja(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, related_name="+")

    class Meta:
        abstract = True


class Cliente(PorLoja):
    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    documento = models.CharField("CPF/CNPJ", max_length=20, blank=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Peca(PorLoja):
    nome = models.CharField(max_length=120)
    sku = models.CharField("Código / código de barras", max_length=60, blank=True)
    custo = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    quantidade = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    minimo = models.IntegerField("Estoque mínimo", default=1, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class OrdemServico(PorLoja):
    class Status(models.TextChoices):
        ORCAMENTO = "orcamento", "Orçamento"
        EM_ANALISE = "em_analise", "Em análise"
        AGUARDANDO_PECA = "aguardando_peca", "Aguardando peça"
        EM_SERVICO = "em_servico", "Em serviço"
        FINALIZADO = "finalizado", "Finalizado"
        PAGO = "pago", "Pago"
        CANCELADO = "cancelado", "Cancelado"

    class Categoria(models.TextChoices):
        CELULAR = "celular", "Celular"
        OUTRO = "outro", "Outro"

    numero = models.PositiveIntegerField(editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ordens")
    tecnico = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    categoria = models.CharField(max_length=10, choices=Categoria.choices, default=Categoria.OUTRO)
    tipo_aparelho = models.CharField(max_length=40, default="")
    marca = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    numero_serie = models.CharField("Nº de série", max_length=40, blank=True)
    imei = models.CharField("IMEI", max_length=40, blank=True)
    senha_aparelho = models.CharField(max_length=60, blank=True)
    acessorios = models.CharField(max_length=200, blank=True)
    defeito = models.TextField("Defeito relatado")
    laudo = models.TextField("Laudo técnico", blank=True)
    checklist = models.TextField("Estado do aparelho na entrada / checklist", blank=True)
    checklist_itens = models.JSONField("Respostas do checklist na entrada", default=list, blank=True)
    observacao_entrada = models.TextField("Observações da entrada", blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EM_ANALISE)
    token = models.CharField(max_length=16, default=gerar_token, unique=True, editable=False)
    assinatura = models.ImageField(upload_to=caminho_assinatura, blank=True, null=True)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    garantia_dias = models.PositiveIntegerField(default=90)
    previsao_entrega = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    entregue_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        unique_together = [("loja", "numero")]

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                Loja.objects.select_for_update().get(pk=self.loja_id)  # serializa a numeração por loja
                ultimo = OrdemServico.objects.filter(loja=self.loja).aggregate(m=Max("numero"))["m"] or 0
                self.numero = ultimo + 1
                super().save(*args, **kwargs)
                HistoricoStatus.objects.create(os=self, status=self.status)
            return
        super().save(*args, **kwargs)

    def mudar_status(self, novo):
        if novo == self.status:
            return
        self.status = novo
        if novo == self.Status.PAGO and not self.entregue_em:
            self.entregue_em = timezone.now()
        self.save()
        HistoricoStatus.objects.create(os=self, status=novo)

    @property
    def subtotal(self):
        return sum((i.subtotal for i in self.itens.all()), Decimal("0"))

    @property
    def total(self):
        return max(self.subtotal - self.desconto, Decimal("0"))

    @property
    def custo(self):
        return sum((i.custo_unitario * i.quantidade for i in self.itens.all()), Decimal("0"))

    @property
    def lucro(self):
        return self.total - self.custo

    @property
    def pago(self):
        return sum((p.valor for p in self.lancamentos.all() if p.tipo == "entrada"), Decimal("0"))

    def __str__(self):
        return f"OS #{self.numero} - {self.cliente}"


class ItemChecklist(PorLoja):
    categoria = models.CharField(max_length=10, choices=OrdemServico.Categoria.choices)
    nome = models.CharField(max_length=80)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(Lower("nome"), "loja", "categoria", name="uniq_checklist_loja_cat_nome"),
        ]

    def __str__(self):
        return self.nome


class HistoricoStatus(models.Model):
    os = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="historico")
    status = models.CharField(max_length=20, choices=OrdemServico.Status.choices)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]


class ItemOS(models.Model):
    class Tipo(models.TextChoices):
        PECA = "peca", "Peça"
        SERVICO = "servico", "Serviço"

    os = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="itens")
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.SERVICO)
    peca = models.ForeignKey(Peca, null=True, blank=True, on_delete=models.SET_NULL)
    descricao = models.CharField(max_length=160)
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    @property
    def subtotal(self):
        return self.valor_unitario * self.quantidade


class FotoOS(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SERVICO = "servico", "Serviço"

    os = models.ForeignKey(OrdemServico, on_delete=models.CASCADE, related_name="fotos")
    imagem = models.ImageField(upload_to=caminho_foto)
    legenda = models.CharField(max_length=120, blank=True)
    visivel_cliente = models.BooleanField(default=False)
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.ENTRADA)
    criado_em = models.DateTimeField(auto_now_add=True)


class Lancamento(PorLoja):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    tipo = models.CharField(max_length=8, choices=Tipo.choices)
    descricao = models.CharField(max_length=160)
    valor = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    forma = models.CharField(max_length=20, blank=True, default="dinheiro")
    os = models.ForeignKey(OrdemServico, null=True, blank=True, on_delete=models.SET_NULL, related_name="lancamentos")
    data = models.DateField(default=timezone.localdate)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data", "-criado_em"]


class Tema(models.Model):
    """Configuração visual global do sistema (singleton)."""

    class Fundo(models.TextChoices):
        COR = "cor", "Cor"
        IMAGEM = "imagem", "Imagem"
        VIDEO = "video", "Vídeo"

    class Vertical(models.TextChoices):
        TOPO = "topo", "Topo"
        MEIO = "meio", "Meio"
        BASE = "base", "Base"

    class Horizontal(models.TextChoices):
        ESQUERDA = "esquerda", "Esquerda"
        CENTRO = "centro", "Centro"
        DIREITA = "direita", "Direita"

    logo = models.ImageField(upload_to=caminho_tema, blank=True, null=True)
    cor_menu = models.CharField(max_length=7, default="#13201C")
    cor_destaque = models.CharField(max_length=7, default="#1F6F54")
    login_fundo_tipo = models.CharField(max_length=10, choices=Fundo.choices, default=Fundo.COR)
    login_cor = models.CharField(max_length=7, default="#F3F4EF")
    login_imagem = models.ImageField(upload_to=caminho_tema, blank=True, null=True)
    login_video = models.FileField(upload_to=caminho_tema_video, blank=True, null=True)
    caixa_vertical = models.CharField(max_length=10, choices=Vertical.choices, default=Vertical.MEIO)
    caixa_horizontal = models.CharField(max_length=10, choices=Horizontal.choices, default=Horizontal.CENTRO)
    caixa_opacidade = models.PositiveSmallIntegerField(default=100)

    _COR_RE = None

    @classmethod
    def _cor_re(cls):
        if cls._COR_RE is None:
            cls._COR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
        return cls._COR_RE

    @classmethod
    def carregar(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def para_dict(self, request=None):
        def midia(f):
            if not f:
                return ""
            try:
                url = f.url
            except Exception:
                return ""
            if isinstance(url, str) and url.startswith("/media/"):
                return url
            return ""

        return {
            "logo": midia(self.logo),
            "cor_menu": self.cor_menu,
            "cor_destaque": self.cor_destaque,
            "login_fundo_tipo": self.login_fundo_tipo,
            "login_cor": self.login_cor,
            "login_imagem": midia(self.login_imagem),
            "login_video": midia(self.login_video),
            "caixa_vertical": self.caixa_vertical,
            "caixa_horizontal": self.caixa_horizontal,
            "caixa_opacidade": self.caixa_opacidade,
        }

    def aplicar(self, data, files):
        erros = {}
        self._arquivos_antigos = []
        for campo in ("cor_menu", "cor_destaque", "login_cor"):
            if campo in data:
                valor = data.get(campo)
                if not self._cor_re().match(str(valor or "")):
                    erros[campo] = "Cor inválida."
                else:
                    setattr(self, campo, valor)

        if "login_fundo_tipo" in data:
            v = data.get("login_fundo_tipo")
            if v in {"cor", "imagem", "video"}:
                self.login_fundo_tipo = v
        if "caixa_vertical" in data and data.get("caixa_vertical") in {"topo", "meio", "base"}:
            self.caixa_vertical = data.get("caixa_vertical")
        if "caixa_horizontal" in data and data.get("caixa_horizontal") in {"esquerda", "centro", "direita"}:
            self.caixa_horizontal = data.get("caixa_horizontal")
        if "caixa_opacidade" in data:
            try:
                v = int(data.get("caixa_opacidade"))
                if 60 <= v <= 100:
                    self.caixa_opacidade = v
            except (TypeError, ValueError):
                pass

        for campo in ("logo", "login_imagem", "login_video"):
            if str(data.get(f"remover_{campo}", "")).strip() in {"1", "true", "True"}:
                arq = getattr(self, campo)
                if arq:
                    self._arquivos_antigos.append(arq)
                setattr(self, campo, None)

        limites = {"logo": 2, "login_imagem": 10, "login_video": 10}
        for campo in ("logo", "login_imagem"):
            arq = files.get(campo)
            if not arq:
                continue
            if getattr(arq, "size", 0) > limites[campo] * 1024 * 1024:
                erros[campo] = "Arquivo grande demais."
                continue
            try:
                arq = reduzir_imagem(arq, max_largura=1200 if campo == "logo" else 1920)
            except ValidationError as exc:
                detalhe = exc.detail.get("imagem") if isinstance(exc.detail, dict) else None
                erros[campo] = str(detalhe[0]) if detalhe else "Imagem inválida."
                continue
            atual = getattr(self, campo)
            if atual:
                self._arquivos_antigos.append(atual)
            setattr(self, campo, arq)

        video = files.get("login_video")
        if video:
            if getattr(video, "size", 0) > limites["login_video"] * 1024 * 1024:
                erros["login_video"] = "Arquivo grande demais."
            elif os.path.splitext(video.name or "")[1].lower() not in {".mp4", ".webm", ".ogv"}:
                erros["login_video"] = "Envie um vídeo MP4, WebM ou OGV."
            else:
                atual = self.login_video
                if atual:
                    self._arquivos_antigos.append(atual)
                self.login_video = video

        if self.login_fundo_tipo == "imagem" and not self.login_imagem:
            erros.setdefault("login_imagem", "Escolha uma imagem para usar como fundo.")
        if self.login_fundo_tipo == "video" and not self.login_video:
            erros.setdefault("login_video", "Escolha um vídeo para usar como fundo.")
        return erros

    def salvar_com_arquivos(self):
        """Salva antes de apagar os arquivos antigos: um erro nunca deixa o banco apontando para arquivos inexistentes."""
        self.save()
        for arq in getattr(self, "_arquivos_antigos", []):
            try:
                arq.delete(save=False)
            except Exception:
                pass
        self._arquivos_antigos = []

    def restaurar_padrao(self):
        self._arquivos_antigos = []
        for campo in ("logo", "login_imagem", "login_video"):
            arq = getattr(self, campo)
            if arq:
                self._arquivos_antigos.append(arq)
            setattr(self, campo, None)
        self.cor_menu = "#13201C"
        self.cor_destaque = "#1F6F54"
        self.login_fundo_tipo = "cor"
        self.login_cor = "#F3F4EF"
        self.caixa_vertical = "meio"
        self.caixa_horizontal = "centro"
        self.caixa_opacidade = 100
