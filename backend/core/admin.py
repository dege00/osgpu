from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Cliente, FotoOS, HistoricoStatus, ItemChecklist, ItemOS, Lancamento, Loja, OrdemServico, Peca, Usuario


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ["nome", "telefone", "documento", "criado_em"]
    search_fields = ["nome", "documento"]


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ["username", "first_name", "loja", "cargo", "is_active"]
    list_filter = ["loja", "cargo", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Assistência", {"fields": ("loja", "cargo", "telefone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Assistência", {"fields": ("loja", "cargo", "telefone")}),
    )


for m in (Cliente, Peca, ItemChecklist, OrdemServico, ItemOS, FotoOS, Lancamento, HistoricoStatus):
    admin.site.register(m)
