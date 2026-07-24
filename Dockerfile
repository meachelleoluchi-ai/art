FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first — this layer is cached unless requirements.txt changes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# A key is only needed to let collectstatic import settings at build time.
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

# Run as an unprivileged user rather than root.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
