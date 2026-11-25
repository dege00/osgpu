from django.db import migrations, models


def migrar_dados(apps, schema_editor):
    OrdemServico = apps.get_model("core", "OrdemServico")
    for os_ in OrdemServico.objects.all().iterator():
        categoria = "celular" if (os_.tipo_aparelho or "").strip().lower() == "celular" else "outro"
        dados = {"categoria": categoria}

        if categoria == "celular":
            dados["imei"] = os_.numero_serie or ""

        checklist = os_.checklist
        if isinstance(checklist, dict):
            linhas = []
            for chave, valor in checklist.items():
                if valor is True:
                    texto = "ok"
                elif valor is False:
                    texto = "com defeito"
                else:
                    texto = str(valor)
                linhas.append(f"{chave}: {texto}")
            dados["checklist_texto"] = "\n".join(linhas)
        elif isinstance(checklist, str):
            dados["checklist_texto"] = checklist

        OrdemServico.objects.filter(pk=os_.pk).update(**dados)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_fotoos_tipo_fotoos_visivel_cliente"),
    ]

    operations = [
        migrations.RenameField(
            model_name="ordemservico",
            old_name="imei",
            new_name="numero_serie",
        ),
        migrations.AlterField(
            model_name="ordemservico",
            name="numero_serie",
            field=models.CharField(blank=True, max_length=40, verbose_name="Nº de série"),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="categoria",
            field=models.CharField(
                choices=[("celular", "Celular"), ("outro", "Outro")],
                default="outro",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="imei",
            field=models.CharField(blank=True, max_length=40, verbose_name="IMEI"),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="checklist_texto",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Estado do aparelho na entrada / checklist",
            ),
        ),
        migrations.RunPython(migrar_dados, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="ordemservico",
            name="checklist",
        ),
        migrations.RenameField(
            model_name="ordemservico",
            old_name="checklist_texto",
            new_name="checklist",
        ),
        migrations.AlterField(
            model_name="ordemservico",
            name="tipo_aparelho",
            field=models.CharField(default="", max_length=40),
        ),
    ]
