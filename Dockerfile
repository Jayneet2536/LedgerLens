FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NLTK_DATA=/usr/local/share/nltk_data

# PDF extraction, OCR and layout inference dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libmagic1 libgomp1 poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# CPU wheels avoid downloading several GB of unused CUDA libraries.
RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements-runtime.txt ./
COPY docker/constraints.txt /tmp/constraints.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --upgrade pip \
    && pip install --timeout 120 -c /tmp/constraints.txt -r requirements-runtime.txt \
    && python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab averaged_perceptron_tagger_eng

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/documents /home/app/.cache \
    && chown -R app:app /home/app/.cache

COPY config.py main.py retrieval_main.py ./
COPY api ./api
COPY chunking ./chunking
COPY embeddings ./embeddings
COPY retrieval ./retrieval
COPY vectorstore ./vectorstore
COPY docker ./docker

USER app
EXPOSE 8000
# One worker: the index/reindex state is held in memory.
CMD ["python", "docker/start.py"]
