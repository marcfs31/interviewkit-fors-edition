FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

WORKDIR /app

ENV FLASK_APP="app:create_app()"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

RUN useradd --system --no-create-home --shell /usr/sbin/nologin app

COPY --chown=app:app . .

USER app

EXPOSE 8080

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120"]
