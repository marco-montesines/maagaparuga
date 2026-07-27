# syntax=docker/dockerfile:1
# MaagapAruga assessment service — FastAPI scoring (NEWS2, DASS-21, fuzzy risk).
#
# Illustrative computation over fictitious data only — not a medical device.

FROM python:3.14-slim AS build
WORKDIR /app
# Install into an isolated venv so it copies cleanly into the runtime stage.
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM python:3.14-slim
# Non-root runtime (least privilege).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
USER app
EXPOSE 8000
# Uvicorn serves the FastAPI app; /healthz is the probe endpoint.
CMD ["uvicorn", "assessment.api:app", "--host", "0.0.0.0", "--port", "8000"]
