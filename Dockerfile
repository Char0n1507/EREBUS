FROM python:3.11-slim

# Install system dependencies (Tor, netcat for healthcheck, dos2unix)
run apt-get update && apt-get install -y \
    tor \
    netcat-openbsd \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Configure Tor Control Port
# We append to torrc to enable ControlPort and CookieAuthentication (or disable auth for local container)
RUN echo "ControlPort 9051" >> /etc/tor/torrc
RUN echo "CookieAuthentication 0" >> /etc/tor/torrc

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Fix line endings and make executable
RUN dos2unix entrypoint.sh && chmod +x entrypoint.sh

# Expose Streamlit port
EXPOSE 8501

# Entrypoint
ENTRYPOINT ["./entrypoint.sh"]

# Default command
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
