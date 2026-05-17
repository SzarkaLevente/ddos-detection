FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY ddos-data-2024/ ./ddos-data-2024/
COPY models/ ./models/
COPY outputs/ ./outputs/

# Generate dummy data if needed
RUN python -m src.generate_dummy_data || true

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Run inference by default
CMD ["python", "-m", "src.inference"]
