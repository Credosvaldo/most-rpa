FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "gunicorn -w 1 -k gthread --threads 4 -b 0.0.0.0:${PORT:-8000} main:app"]