FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DEBUG=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# chave só para o build (collectstatic); em produção vale a SECRET_KEY do .env
RUN SECRET_KEY=chave-apenas-para-o-build-nao-usar-em-producao python manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /media \
 && chown -R appuser:appuser /app /media
USER appuser
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 3 --access-logfile -"]
