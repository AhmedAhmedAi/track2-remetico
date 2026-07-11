FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Track 2 rules: no key is injected by the harness — we ship our own
# (dedicated hackathon key, rotated after the event).
ARG FIREWORKS_API_KEY=""
ENV FIREWORKS_API_KEY=${FIREWORKS_API_KEY}
# Gemma 4 31B IT (Google DeepMind) served via a dedicated Fireworks deployment;
# serverless kimi as emergency fallback if the deployment is scaled to zero.
ARG MODEL_PRIMARY="accounts/ahmodu2892003-qzswoh/deployments/jsq0qa4l"
ARG MODEL_FALLBACK="accounts/fireworks/models/kimi-k2p6"
ENV MODEL_PRIMARY=${MODEL_PRIMARY} MODEL_FALLBACK=${MODEL_FALLBACK}

ENTRYPOINT ["python", "-m", "app.main"]
