FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Track 2 rules: no key is injected by the harness — we ship our own
# (dedicated hackathon key, rotated after the event). Baked as a file, not
# just ENV, so a runtime-injected FIREWORKS_API_KEY cannot override it.
ARG FIREWORKS_API_KEY=""
ENV FIREWORKS_API_KEY=${FIREWORKS_API_KEY}
RUN printf '%s' "${FIREWORKS_API_KEY}" > ./app/fw_key.txt
# DIAGNOSTIC BUILD: serverless Minimax M3 as primary (no GPU deployment cost).
# For the final Gemma-prize build set MODEL_PRIMARY back to the dedicated
# deployment: accounts/ahmodu2892003-qzswoh/deployments/jsq0qa4l
ARG MODEL_PRIMARY="accounts/fireworks/models/minimax-m3"
ARG MODEL_FALLBACK="accounts/fireworks/models/kimi-k2p6"
ARG MODEL_VISION_FALLBACK="accounts/fireworks/models/qwen3p7-plus"
ARG MODEL_HUMOR_2="accounts/fireworks/models/kimi-k2p6"
ARG MODEL_FACT_CHECK="accounts/fireworks/models/qwen3p7-plus"
ENV MODEL_PRIMARY=${MODEL_PRIMARY} MODEL_FALLBACK=${MODEL_FALLBACK} \
    MODEL_VISION_FALLBACK=${MODEL_VISION_FALLBACK} \
    MODEL_HUMOR_2=${MODEL_HUMOR_2} MODEL_FACT_CHECK=${MODEL_FACT_CHECK}

ENTRYPOINT ["python", "-m", "app.main"]
