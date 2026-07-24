# syntax=docker/dockerfile:1
# MaagapAruga media service — mock imaging/AV intake, transcription, hybrid search.
#
# One image, three roles (media api | worker | simulate). Illustrative processing
# over fictitious data only — not a medical device.

FROM python:3.13-slim AS build
WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
# CPU-only torch first (from the CPU wheel index) so sentence-transformers pulls
# it in already-satisfied — avoids the multi-GB CUDA build on a CPU-only demo.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM python:3.13-slim
# Runtime system deps: ffmpeg (audio normalization), espeak-ng (simulator TTS),
# libgomp1 (OpenMP, needed by CTranslate2/torch).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --from=build /opt/venv /opt/venv
# Model cache (whisper + MiniLM). Mounted from a PVC on-cluster so weights
# download once and survive pod restarts.
ENV WHISPER_CACHE_DIR=/models HF_HOME=/models
RUN mkdir -p /models && chown app:app /models
WORKDIR /app
USER app
EXPOSE 8000 9091
# ENTRYPOINT is the CLI; the Deployment passes the role as args (api|worker|simulate).
ENTRYPOINT ["media"]
CMD ["api"]
