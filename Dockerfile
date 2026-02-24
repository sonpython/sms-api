FROM python:3.11-slim

WORKDIR /app

# Install bun
RUN apt-get update && apt-get install -y curl unzip && \
    curl -fsSL https://bun.sh/install | bash && \
    ln -s /root/.bun/bin/bun /usr/local/bin/bun && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build
COPY frontend/ frontend/
RUN cd frontend && bun install && bun run build

# App code
COPY *.py ./
COPY passkey.conf.example passkey.conf
COPY sms-data/ /var/spool/sms/

# Override SMS_BASE_DIR to default /var/spool/sms in container
RUN sed -i '/SMS_BASE_DIR/d' passkey.conf

COPY static/ static/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
