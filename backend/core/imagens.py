import base64
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    register_heif_opener = None

MAX_IMAGEM_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 100_000_000  # recusa imagens gigantes antes de decodificar (evita estourar a memória)
ERROS_IMAGEM = (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)
FORMATOS = {"JPEG", "PNG", "WEBP"}
EXTENSOES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
MARCAS_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}


def parece_heic(arquivo):
    if not arquivo or not hasattr(arquivo, "seek"):
        return False
    final = (getattr(arquivo, "name", "") or "").lower()
    if final.endswith((".heic", ".heif")):
        return True
    try:
        arquivo.seek(0)
        cabecalho = arquivo.read(32)
    finally:
        arquivo.seek(0)
    return cabecalho[4:8] == b"ftyp" and cabecalho[8:12] in MARCAS_HEIC


def erro_imagem(arquivo):
    if parece_heic(arquivo):
        return "Formato HEIC/HEIF não suportado aqui. No iPhone, use Ajustes > Câmera > Formatos > Mais compatível, ou envie JPEG, PNG ou WebP."
    return "Envie uma imagem válida (JPEG, PNG ou WebP)."


def validar_imagem(arquivo):
    """Valida tamanho e se o conteúdo é realmente uma imagem suportada."""
    if not arquivo:
        raise ValidationError({"imagem": "Envie uma imagem."})
    if arquivo.size > MAX_IMAGEM_BYTES:
        raise ValidationError({"imagem": "A imagem deve ter no máximo 20 MB."})
    try:
        arquivo.seek(0)
        with Image.open(arquivo) as img:
            if img.width * img.height > MAX_PIXELS:
                raise ValidationError({"imagem": "A imagem tem resolução alta demais. Reduza-a e tente de novo."})
            img.verify()
    except ERROS_IMAGEM:
        raise ValidationError({"imagem": erro_imagem(arquivo)}) from None
    finally:
        arquivo.seek(0)


def reduzir_imagem(arquivo, max_largura=1600, qualidade=85):
    """Redimensiona a imagem para no máximo `max_largura` px de largura."""
    validar_imagem(arquivo)
    arquivo.seek(0)
    img = Image.open(arquivo)
    formato = (img.format or "JPEG").upper()
    if formato not in FORMATOS:
        formato = "JPEG"
    img = ImageOps.exif_transpose(img)  # aplica a rotação da câmera antes de salvar (o EXIF é descartado)
    if img.width > max_largura:
        altura = max(1, round(img.height * max_largura / img.width))
        img = img.resize((max_largura, altura), Image.LANCZOS)
    if formato == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    salvar = {"format": formato}
    if formato in ("JPEG", "WEBP"):
        salvar.update(quality=qualidade, optimize=True)
    img.save(buf, **salvar)
    return ContentFile(buf.getvalue(), name=f"imagem{EXTENSOES.get(formato, '.jpg')}")


def processar_assinatura(data_url):
    """Valida a assinatura em data URL e devolve PNG normalizado."""
    if not data_url or "base64," not in data_url:
        raise ValidationError({"assinatura": "Assinatura inválida."})
    bruto = data_url.split("base64,", 1)[1]
    try:
        conteudo = base64.b64decode(bruto, validate=False)
    except (ValueError, TypeError):
        raise ValidationError({"assinatura": "Assinatura inválida."}) from None
    if len(conteudo) > MAX_IMAGEM_BYTES:
        raise ValidationError({"assinatura": "A assinatura deve ter no máximo 20 MB."})
    try:
        with Image.open(BytesIO(conteudo)) as img:
            img.verify()
    except ERROS_IMAGEM:
        raise ValidationError({"assinatura": "Assinatura inválida."}) from None
    img = Image.open(BytesIO(conteudo)).convert("RGBA")
    if img.width > 1200:
        altura = max(1, round(img.height * 1200 / img.width))
        img = img.resize((1200, altura), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return ContentFile(buf.getvalue(), name="assinatura.png")
