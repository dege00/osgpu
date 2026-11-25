import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .fields import RelativeImageField
from .imagens import MAX_IMAGEM_BYTES, erro_imagem, reduzir_imagem, validar_imagem
from .permissoes import ordens_visiveis
from .models import Cliente, FotoOS, HistoricoStatus, ItemOS, Lancamento, Loja, OrdemServico, Peca, Servico, Usuario


class ImagemLimitada(RelativeImageField):
    """Checa o tamanho antes de tentar decodificar a imagem."""

    def to_internal_value(self, data):
        if getattr(data, "size", 0) > MAX_IMAGEM_BYTES:
            raise serializers.ValidationError("A imagem deve ter no máximo 20 MB.")
        try:
            return super().to_internal_value(data)
        except (serializers.ValidationError, DjangoValidationError):
            raise serializers.ValidationError(erro_imagem(data)) from None


class LojaSerializer(serializers.ModelSerializer):
    logo = ImagemLimitada(required=False, allow_null=True)

    class Meta:
        model = Loja
        fields = ["id", "nome", "telefone", "documento", "endereco", "termo_garantia", "logo"]

    def validate_logo(self, arquivo):
        validar_imagem(arquivo)
        return arquivo

    def _processar_logo(self, validated_data):
        if validated_data.get("logo"):
            validated_data["logo"] = reduzir_imagem(validated_data["logo"], max_largura=600)
        return validated_data

    def create(self, validated_data):
        return super().create(self._processar_logo(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._processar_logo(validated_data))


class UsuarioSerializer(serializers.ModelSerializer):
    loja = LojaSerializer(read_only=True)
    senha = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = Usuario
        fields = ["id", "username", "first_name", "email", "cargo", "telefone", "loja", "senha", "is_active"]

    def validate(self, data):
        request = self.context.get("request")
        if self.instance and request and self.instance.pk == request.user.pk:
            if data.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "Você não pode desativar o próprio usuário."})
            if data.get("cargo") and data["cargo"] != Usuario.Cargo.ADMIN:
                raise serializers.ValidationError({"cargo": "Você não pode remover seu próprio acesso de administrador."})
        senha = data.get("senha")
        if senha:
            validate_password(senha, self.instance)
        return data

    def create(self, data):
        senha = data.pop("senha", None)
        if not senha:
            raise serializers.ValidationError({"senha": "Informe uma senha inicial."})
        u = Usuario(**data)
        u.set_password(senha)
        u.save()
        return u

    def update(self, instance, data):
        senha = data.pop("senha", None)
        u = super().update(instance, data)
        if senha:
            u.set_password(senha)
            u.save(update_fields=["password"])
        return u


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ["id", "nome", "telefone", "email", "documento", "observacoes", "criado_em"]


class PecaSerializer(serializers.ModelSerializer):
    estoque_baixo = serializers.SerializerMethodField()

    class Meta:
        model = Peca
        fields = ["id", "nome", "sku", "custo", "preco", "quantidade", "minimo", "estoque_baixo"]

    def get_estoque_baixo(self, o):
        return o.quantidade <= o.minimo

    def validate(self, data):
        r = self.context.get("request")
        if r and not r.user.eh_admin:
            data.pop("custo", None)
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        r = self.context.get("request")
        if not (r and r.user.eh_admin):
            data.pop("custo", None)
        return data


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = ["id", "nome", "preco", "ativo"]

    def validate_nome(self, valor):
        nome = valor.strip()
        if not nome:
            raise serializers.ValidationError("Informe o nome do serviço.")
        request = self.context.get("request")
        if request and request.user.loja_id:
            iguais = Servico.objects.filter(loja_id=request.user.loja_id, nome__iexact=nome)
            if self.instance:
                iguais = iguais.exclude(pk=self.instance.pk)
            if iguais.exists():
                raise serializers.ValidationError("Já existe um serviço com esse nome nesta loja.")
        return nome


class ItemOSSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ItemOS
        fields = ["id", "os", "tipo", "peca", "servico", "descricao", "quantidade", "valor_unitario", "custo_unitario", "subtotal"]
        extra_kwargs = {"descricao": {"required": False}, "valor_unitario": {"required": False},
                        "custo_unitario": {"required": False}, "quantidade": {"min_value": 1}}

    def validate(self, d):
        request = self.context["request"]
        loja = request.user.loja
        if not request.user.eh_admin:
            d.pop("custo_unitario", None)
        os_ = d.get("os") or getattr(self.instance, "os", None)
        if not os_ or not ordens_visiveis(request.user).filter(pk=os_.pk).exists():
            raise serializers.ValidationError("OS inválida.")
        tipo = d.get("tipo") or getattr(self.instance, "tipo", None)
        peca = d.get("peca") or getattr(self.instance, "peca", None)
        servico = d.get("servico") or getattr(self.instance, "servico", None)
        if tipo == "peca" and not peca:
            raise serializers.ValidationError({"peca": "Escolha a peça."})
        if peca:
            if peca.loja_id != loja.id:
                raise serializers.ValidationError("Peça inválida.")
            d.setdefault("descricao", peca.nome)
            if not self.instance:
                d.setdefault("valor_unitario", peca.preco)
                d.setdefault("custo_unitario", peca.custo)
        if servico:
            if tipo != ItemOS.Tipo.SERVICO:
                raise serializers.ValidationError({"servico": "Serviço só pode ser usado no tipo serviço."})
            if servico.loja_id != loja.id or not servico.ativo:
                raise serializers.ValidationError("Serviço inválido.")
            d.setdefault("descricao", servico.nome)
            if not self.instance:
                d.setdefault("valor_unitario", servico.preco)
        if not (d.get("descricao") or getattr(self.instance, "descricao", None)):
            raise serializers.ValidationError({"descricao": "Informe a descrição."})
        return d

    def to_representation(self, instance):
        data = super().to_representation(instance)
        r = self.context.get("request")
        if not (r and r.user.eh_admin):
            data.pop("custo_unitario", None)
        return data


class FotoSerializer(serializers.ModelSerializer):
    imagem = ImagemLimitada()
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = FotoOS
        fields = ["id", "os", "imagem", "legenda", "visivel_cliente", "tipo", "tipo_label", "criado_em"]

    def validate_imagem(self, arquivo):
        validar_imagem(arquivo)
        return arquivo

    def create(self, validated_data):
        validated_data["imagem"] = reduzir_imagem(validated_data["imagem"], max_largura=1600)
        return super().create(validated_data)


class HistoricoSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = HistoricoStatus
        fields = ["status", "status_label", "criado_em"]


class OSSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    cliente_telefone = serializers.CharField(source="cliente.telefone", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    assinatura = RelativeImageField(read_only=True)
    itens = ItemOSSerializer(many=True, read_only=True)
    fotos = FotoSerializer(many=True, read_only=True)
    historico = HistoricoSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    custo = serializers.SerializerMethodField()
    lucro = serializers.SerializerMethodField()
    pago = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrdemServico
        fields = ["id", "numero", "cliente", "cliente_nome", "cliente_telefone", "tecnico", "categoria", "tipo_aparelho",
                  "marca", "modelo", "numero_serie", "imei", "senha_aparelho", "acessorios", "defeito", "laudo",
                  "checklist", "status",
                  "status_label", "token", "assinatura", "desconto", "garantia_dias", "previsao_entrega",
                  "criado_em", "atualizado_em", "entregue_em", "itens", "fotos", "historico", "subtotal", "total",
                  "custo", "lucro", "pago"]
        read_only_fields = ["numero", "token", "assinatura", "entregue_em"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            fields["tecnico"].queryset = Usuario.objects.filter(loja_id=request.user.loja_id)
        return fields

    # custo/lucro só para administradores
    def _admin(self):
        r = self.context.get("request")
        return bool(r and r.user.eh_admin)

    def get_custo(self, o):
        return o.custo if self._admin() else None

    def get_lucro(self, o):
        return o.lucro if self._admin() else None

    def validate_cliente(self, c):
        if c.loja_id != self.context["request"].user.loja_id:
            raise serializers.ValidationError("Cliente inválido.")
        return c

    def validate_desconto(self, valor):
        r = self.context.get("request")
        atual = self.instance.desconto if self.instance else 0
        if r and r.user.cargo == Usuario.Cargo.TECNICO and not r.user.eh_admin and valor != atual:
            raise serializers.ValidationError("Só administrador ou atendente aplica desconto.")
        return valor

    def validate(self, data):
        categoria = data.get(
            "categoria", getattr(self.instance, "categoria", OrdemServico.Categoria.OUTRO)
        )
        if categoria == OrdemServico.Categoria.CELULAR:
            data["tipo_aparelho"] = "Celular"
            imei = (data.get("imei", getattr(self.instance, "imei", "")) or "").strip()
            if imei and not re.fullmatch(r"\d{14,17}", imei):
                raise serializers.ValidationError({"imei": "O IMEI deve ter de 14 a 17 dígitos."})
            data["imei"] = imei
        else:
            descricao = (
                data.get("tipo_aparelho", getattr(self.instance, "tipo_aparelho", "")) or ""
            ).strip()
            if not descricao:
                raise serializers.ValidationError(
                    {"tipo_aparelho": "Informe o que é o aparelho."}
                )
            data["tipo_aparelho"] = descricao
            data["imei"] = ""
        return data

    def validate_status(self, s):
        return s


class OSListaSerializer(serializers.ModelSerializer):
    """Versão enxuta para a listagem (sem fotos, histórico e itens aninhados)."""
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    cliente_telefone = serializers.CharField(source="cliente.telefone", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    pago = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrdemServico
        fields = ["id", "numero", "cliente", "cliente_nome", "cliente_telefone", "categoria", "tipo_aparelho", "marca",
                  "modelo", "defeito", "status", "status_label", "previsao_entrega", "criado_em", "total", "pago"]


class LancamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lancamento
        fields = ["id", "tipo", "descricao", "valor", "forma", "os", "data"]

    def validate_os(self, os_):
        request = self.context.get("request")
        if os_ and request and os_.loja_id != request.user.loja_id:
            raise serializers.ValidationError("OS inválida.")
        return os_
