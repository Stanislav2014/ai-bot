FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -r -s /bin/false botuser && mkdir -p /app/data && chown botuser:botuser /app/data
COPY . .

USER botuser

CMD ["python", "-m", "app.main"]
