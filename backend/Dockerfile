FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary için runtime yeterli; build araçları gerekmiyor
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

ENTRYPOINT ["./entrypoint.sh"]
CMD ["api"]
