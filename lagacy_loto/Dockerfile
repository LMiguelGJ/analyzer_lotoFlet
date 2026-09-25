# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 loteka && \
    chown -R loteka:loteka /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p assets && \
    chown -R loteka:loteka /app && \
    chmod +x start.sh

# Switch to non-root user
USER loteka

# Expose port for Flet web interface
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLET_SERVER_PORT=8080
ENV FLET_SERVER_HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

# Run the startup script
CMD ["./start.sh"]