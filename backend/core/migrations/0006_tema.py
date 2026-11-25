from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_valores_nao_negativos'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='tema/')),
                ('cor_menu', models.CharField(default='#13201C', max_length=7)),
                ('cor_destaque', models.CharField(default='#1F6F54', max_length=7)),
                ('login_fundo_tipo', models.CharField(choices=[('cor', 'Cor'), ('imagem', 'Imagem'), ('video', 'Vídeo')], default='cor', max_length=10)),
                ('login_cor', models.CharField(default='#F3F4EF', max_length=7)),
                ('login_imagem', models.ImageField(blank=True, null=True, upload_to='tema/')),
                ('login_video', models.FileField(blank=True, null=True, upload_to='tema/')),
                ('caixa_vertical', models.CharField(choices=[('topo', 'Topo'), ('meio', 'Meio'), ('base', 'Base')], default='meio', max_length=10)),
                ('caixa_horizontal', models.CharField(choices=[('esquerda', 'Esquerda'), ('centro', 'Centro'), ('direita', 'Direita')], default='centro', max_length=10)),
                ('caixa_opacidade', models.PositiveSmallIntegerField(default=100)),
            ],
        ),
    ]
