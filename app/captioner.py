"""Fireworks Gemma client: fact sheet -> style writers -> judges -> refine.

Every call: 25s timeout, retries with backoff, model fallback (all Gemma),
and graceful degradation so a single failure never zeroes a clip.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from . import config, prompts

log = logging.getLogger(__name__)

_api_sem: asyncio.Semaphore | None = None
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client, _api_sem
    if _client is None:
        _api_sem = asyncio.Semaphore(config.MAX_CONCURRENT_API)
        _client = httpx.AsyncClient(
            base_url=config.FIREWORKS_BASE_URL,
            headers={"Authorization": f"Bearer {config.FIREWORKS_API_KEY}"},
            timeout=httpx.Timeout(config.API_TIMEOUT, connect=10.0),
        )
    return _client


def _image_parts(frames_b64: list[str], limit: int | None = None) -> list[dict]:
    frames = frames_b64
    if limit is not None and len(frames) > limit:
        # Evenly thin the strip but always keep first and last frame.
        step = (len(frames) - 1) / (limit - 1)
        idx = sorted({round(i * step) for i in range(limit)})
        frames = [frames[i] for i in idx]
    return [
        {"type": "image_url",
         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        for b64 in frames
    ]


async def _chat(messages: list[dict], temperature: float, max_tokens: int = 1200,
                label: str = "", schema: dict | None = None) -> str:
    """One chat completion with retries and Gemma-to-Gemma model fallback.

    When `schema` is given, the server enforces JSON output matching it
    (structured output). Dropped on fallback-model attempts in case the
    fallback deployment rejects it.
    """
    if config.MOCK_API:
        return _mock_response(messages, label)

    client = _get_client()
    last_err: Exception | None = None
    mt = max_tokens
    # Image-bearing calls need a fallback model that can actually see.
    has_images = any(
        isinstance(m.get("content"), list)
        and any(p.get("type") == "image_url" for p in m["content"])
        for m in messages
    )
    fallback = config.MODEL_VISION_FALLBACK if has_images else config.MODEL_FALLBACK
    for attempt in range(config.API_RETRIES + 1):
        model = config.MODEL_PRIMARY if attempt < 2 else fallback
        try:
            body = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": mt,
            }
            if attempt < 2:  # options the fallback model may not support
                if schema is not None:
                    body["response_format"] = {"type": "json_object", "schema": schema}
                if config.REASONING_EFFORT:
                    body["reasoning_effort"] = config.REASONING_EFFORT
            async with _api_sem:
                resp = await client.post("/chat/completions", json=body)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            choice = resp.json()["choices"][0]
            content = choice["message"].get("content") or ""
            # Reasoning models may leak thinking into content when truncated.
            content = re.sub(r"<think>.*?(</think>|$)", "", content, flags=re.DOTALL).strip()
            if choice.get("finish_reason") == "length":
                mt = min(mt * 2, 8192)
                raise RuntimeError("truncated by max_tokens (thinking model) — retrying bigger")
            if not content:
                raise RuntimeError("empty completion")
            return content
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("%s call attempt %d (%s) failed: %s", label, attempt + 1, model, e)
            await asyncio.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"{label} failed after retries: {last_err}")


def _extract_json(text: str):
    """Pull JSON out of a completion that may wrap it in prose/code fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in: {text[:200]}")


# ------------------------------------------------------------------ pipeline

async def fact_sheet(frames_b64: list[str], timestamps: list[float],
                     duration: float) -> str:
    ts = ", ".join(f"{t:.0f}s" for t in timestamps)
    messages = [
        {"role": "system", "content": prompts.FACT_SHEET_SYSTEM},
        {"role": "user", "content": [
            {"type": "text",
             "text": prompts.FACT_SHEET_USER.format(duration=duration, timestamps=ts)},
            *_image_parts(frames_b64),
        ]},
    ]
    return await _chat(messages, temperature=0.2, max_tokens=2500, label="fact_sheet")


def _category_hint(fact: str | None) -> str:
    """Build a focus hint from the CATEGORY line the fact sheet itself wrote."""
    if not fact:
        return ""
    m = re.search(r"CATEGORY[:\s*]*(.+)", fact, re.IGNORECASE)
    scope = m.group(1) if m else fact[-300:]
    hints = [h for cat, h in prompts.CATEGORY_HINTS.items() if cat in scope.lower()]
    if not hints:
        return ""
    return ("FOCUS for this kind of video: prioritize " + "; ".join(hints[:2]) + ".\n")


async def write_candidates(style: str, frames_b64: list[str],
                           timestamps: list[float], fact: str | None) -> list[str]:
    spec = prompts.STYLE_SPECS[style]
    fact = fact or ("(fact sheet unavailable — analyze the attached frames "
                    "directly and describe only what you can verify in them)")
    ts = ", ".join(f"{t:.0f}s" for t in timestamps)
    messages = [
        {"role": "system",
         "content": prompts._WRITER_COMMON.format(n=config.N_CANDIDATES)},
        {"role": "user", "content": [
            {"type": "text", "text": prompts.WRITER_USER.format(
                fact_sheet=fact, timestamps=ts, n=config.N_CANDIDATES,
                instructions=spec["instructions"], examples=spec["examples"],
                category_hint=_category_hint(fact))},
            *_image_parts(frames_b64, limit=config.WRITER_MAX_FRAMES),
        ]},
    ]
    writer_budget = 1200 if config.N_CANDIDATES <= 1 else 2500
    # No enforced JSON schema here: schema mode triggers M3's hidden thinking
    # (slow under load); the tolerant parser handles free-form JSON output.
    raw = await _chat(messages, temperature=spec["temperature"],
                      max_tokens=writer_budget, label=f"writer:{style}")
    data = _extract_json(raw)
    if isinstance(data, dict):
        data = data.get("captions", [])
    cands = [str(c).strip() for c in data if str(c).strip()] if isinstance(data, list) else []
    if not cands:
        raise ValueError(f"writer:{style} returned no usable candidates")
    return cands[: config.N_CANDIDATES + 2]


async def judge(style: str, frames_b64: list[str], fact: str,
                candidates: list[str]) -> tuple[str, float, str]:
    """Returns (best_caption, best_total_score, critique_of_best)."""
    listing = "\n".join(f"{i}: {c}" for i, c in enumerate(candidates))
    messages = [
        {"role": "system", "content": prompts.JUDGE_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompts.JUDGE_USER.format(
                style=style, style_def=prompts.STYLE_DEFS[style],
                fact_sheet=fact, candidates=listing)},
            *_image_parts(frames_b64, limit=config.WRITER_MAX_FRAMES),
        ]},
    ]
    raw = await _chat(messages, temperature=0.1, max_tokens=2500, label=f"judge:{style}",
                      schema={"type": "object", "properties": {"scores": {
                          "type": "array", "items": {"type": "object", "properties": {
                              "index": {"type": "integer"},
                              "accuracy": {"type": "number"},
                              "style": {"type": "number"},
                              "critique": {"type": "string"}},
                              "required": ["index", "accuracy", "style"]}}},
                          "required": ["scores"]})
    data = _extract_json(raw)
    scores = data.get("scores", []) if isinstance(data, dict) else []

    best_i, best_score, best_crit = 0, -1.0, ""
    for s in scores:
        try:
            i = int(s["index"])
            total = (float(s.get("accuracy", 0)) + float(s.get("style", 0))) / 2
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < len(candidates) and total > best_score:
            best_i, best_score, best_crit = i, total, str(s.get("critique", ""))
    if best_score < 0:
        # Judge output unusable -> keep first candidate, neutral score.
        return candidates[0], 0.5, ""
    return candidates[best_i], best_score, best_crit


async def refine(style: str, frames_b64: list[str], fact: str,
                 caption: str, critique: str) -> str:
    spec = prompts.STYLE_SPECS[style]
    messages = [
        {"role": "system",
         "content": "You are an expert caption editor. English only."},
        {"role": "user", "content": [
            {"type": "text", "text": prompts.REFINE_USER.format(
                fact_sheet=fact, instructions=spec["instructions"],
                caption=caption, critique=critique or "make it sharper and more grounded")},
            *_image_parts(frames_b64, limit=8),
        ]},
    ]
    raw = await _chat(messages, temperature=spec["temperature"],
                      max_tokens=1500, label=f"refine:{style}")
    text = raw.strip().strip('"').strip()
    return text.split("\n")[0].strip() if text else caption


async def _text_only_caption(style: str, fact: str) -> str:
    """Fast image-free fallback: one caption from the fact sheet alone."""
    spec = prompts.STYLE_SPECS[style]
    messages = [
        {"role": "system", "content": "You write video captions. English only."},
        {"role": "user", "content": (
            f"FACT SHEET of a video:\n{fact}\n\n{spec['instructions']}\n\n"
            "Write ONE caption for this video in this style, 1-2 sentences. "
            "Return ONLY the caption text.")},
    ]
    raw = await _chat(messages, temperature=spec["temperature"],
                      max_tokens=800, label=f"textonly:{style}")
    text = raw.strip().strip('"').split("\n")[0].strip()
    if len(text) < 10:
        raise ValueError("text-only caption too short")
    return text


async def caption_style(style: str, frames_b64: list[str],
                        timestamps: list[float], fact: str) -> str:
    """Per-style flow: write N candidates, writer self-ranks, take the best.

    Separate judge/refine calls were removed: blind testing showed they added
    no measurable quality, and the saved time pays for denser frame coverage.
    Never raises.
    """
    try:
        cands = await write_candidates(style, frames_b64, timestamps, fact)
    except Exception as e:  # noqa: BLE001
        log.error("writer:%s failed entirely: %r", style, e)
        try:
            if not fact:
                raise ValueError("no fact sheet for text-only fallback")
            return await _text_only_caption(style, fact)
        except Exception as e2:  # noqa: BLE001
            log.error("textonly:%s also failed: %r", style, e2)
            return _fallback(style, fact)
    return cands[0]  # writer returns candidates ordered best first


def _fallback(style: str, fact: str | None) -> str:
    """Style-appropriate caption built from whatever survived. Never raises."""
    summary = prompts.GENERIC_SUMMARY
    if fact:
        for line in fact.splitlines():
            line = re.sub(r"[*_#`]+", "", line).strip("-•* \t")
            bad = ("style:", "camera", "timeline", "unclear", "notable")
            if len(line) > 30 and ":" not in line[:12] \
                    and not any(b in line.lower() for b in bad):
                summary = line[:160].rstrip(".,;") + "."
                break
    lower = summary[0].lower() + summary[1:] if summary else summary
    tpl = prompts.FALLBACK_TEMPLATES.get(style, "{summary}")
    return tpl.format(summary=summary, summary_lower=lower)


# ----------------------------------------------------------------- mock mode

def _mock_response(messages: list[dict], label: str) -> str:
    if label == "fact_sheet":
        return ("1. SUBJECTS: mock subject\n2. SETTING: mock setting\n"
                "3. ACTION TIMELINE: mock actions over time\n4. NOTABLE DETAILS: mock")
    if label.startswith("writer:"):
        style = label.split(":", 1)[1]
        return json.dumps({"captions": [f"Mock {style} caption {i}"
                                        for i in range(config.N_CANDIDATES)]})
    if label.startswith("judge:"):
        return json.dumps({"scores": [
            {"index": 0, "accuracy": 0.9, "style": 0.9, "critique": "fine"}]})
    if label.startswith("refine:"):
        return "Mock refined caption"
    return "mock"


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
