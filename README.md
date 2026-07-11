# AMD Hackathon ACT II — Track 2: Video Captioning Agent

An all-Gemma video captioning agent for the AMD Developer Hackathon ACT II
(Track 2). Watches a video clip and writes captions in four styles:
`formal`, `sarcastic`, `humorous_tech`, `humorous_non_tech`.

## Architecture

```
/input/tasks.json
   │  (all clips processed in parallel)
   ▼
1. Download video (streaming, retries)
2. Motion-adaptive frame sampling
   - 1-fps tiny thumbnails -> per-second motion scores (numpy frame diff)
   - frame budget (6-24, scales with duration) spent where motion is;
     calm videos degrade to even spacing; first/last frames always kept
3. Gemma 4 31B (vision): frames -> factual FACT SHEET
4. 4 dedicated style writer nodes in parallel
   (frames + fact sheet + style few-shots, style-tuned temperature,
    each writes 4 candidate captions)
5. 4 dedicated style judges in parallel
   (see frames; score candidates with the official rubric:
    accuracy 0-1 + style 0-1; pick winner + critique)
6. Weak winners (< 0.75) get one refine rewrite using the critique
7. /output/results.json — always valid, every requested style present,
   global watchdog at ~8.3 min, exit 0
```

Models: Gemma 4 31B IT (primary) with Gemma 4 26B A4B IT fallback,
both via Fireworks AI — the pipeline is 100% Gemma.

## Build & push (image MUST be linux/amd64)

```bash
docker buildx build --platform linux/amd64 \
  --build-arg FIREWORKS_API_KEY="fw_..." \
  -t <dockerhub-user>/amd-track2-captioner:latest --push .
```

## Local test

```bash
# mock mode (no API key needed) — verifies plumbing
docker run --rm --platform linux/amd64 --cpus=2 --memory=4g \
  -e MOCK_API=1 \
  -v $PWD/test/input:/input:ro -v $PWD/test/output:/output \
  amd-hackathon-track2:test

# real mode
docker run --rm --platform linux/amd64 --cpus=2 --memory=4g \
  -e FIREWORKS_API_KEY="fw_..." \
  -v $PWD/test/input:/input:ro -v $PWD/test/output:/output \
  amd-hackathon-track2:test
```

## Contract with the judging harness

- reads `/input/tasks.json`: `[{"task_id", "video_url", "styles": [...]}]`
- writes `/output/results.json`: `[{"task_id", "captions": {style: text}}]`
- exit code 0; max runtime 10 min (internal watchdog ~8.3 min);
  every API call capped at 25s (<30s/request rule); English only;
  nothing hardcoded to specific inputs.

## Tunables (env vars)

See `app/config.py` — frame budget, candidate count, refine threshold,
concurrency, timeouts, model IDs.
