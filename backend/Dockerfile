FROM python:3.11-slim

# System deps for Camelot (ghostscript) + OpenCV runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
