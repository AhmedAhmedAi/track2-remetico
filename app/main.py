"""Orchestrator. Contract with the judging harness:

  read  /input/tasks.json   [{"task_id", "video_url", "styles": [...]}, ...]
  write /output/results.json [{"task_id", "captions": {style: caption}}, ...]
  exit 0

Guarantees: results.json is ALWAYS written (valid JSON, every requested style
present for every task), inside the global deadline, whatever fails upstream.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

from . import captioner, config, frames, prompts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("main")

# Shared mutable state: task_id -> {"styles": [...], "captions": {...}, "fact": str|None}
STATE: dict[str, dict] = {}


def _requested_styles(task: dict) -> list[str]:
    styles = task.get("styles") or list(config.VALID_STYLES)
    return [s for s in styles if isinstance(s, str)]


async def process_task(task: dict, stagger: float = 0.0) -> None:
    task_id = str(task.get("task_id", ""))
    entry = STATE[task_id]
    if stagger:
        await asyncio.sleep(stagger)  # spread the initial API burst
    t0 = time.monotonic()

    data = await frames.extract_frames(str(task.get("video_url", "")), task_id)
    fb64, ts, dur = data["frames_b64"], data["timestamps"], data["duration"]

    # Lifeline ladder: full fact sheet -> half-frames fact sheet -> no fact
    # sheet at all (writers still caption directly from the frames).
    fact = None
    try:
        fact = await captioner.fact_sheet(fb64, ts, dur)
    except Exception as e:  # noqa: BLE001
        log.warning("task %s: fact sheet failed (%s), retrying with half frames", task_id, e)
        try:
            fact = await captioner.fact_sheet(fb64[::2], ts[::2], dur)
        except Exception as e2:  # noqa: BLE001
            log.error("task %s: half-frame fact sheet also failed (%s) — "
                      "writers will work from frames alone", task_id, e2)
    entry["fact"] = fact
    log.info("task %s: fact sheet %s (%.0fs elapsed)", task_id,
             "ready" if fact else "UNAVAILABLE", time.monotonic() - t0)

    async def one_style(style: str) -> None:
        caption = await captioner.caption_style(style, fb64, ts, fact)
        entry["captions"][style] = caption

    await asyncio.gather(*[one_style(s) for s in entry["styles"]])
    log.info("task %s: done in %.0fs", task_id, time.monotonic() - t0)


async def run_all(tasks: list[dict]) -> None:
    results = await asyncio.gather(
        *[process_task(t, stagger=i * 1.0) for i, t in enumerate(tasks)],
        return_exceptions=True,
    )
    for task, res in zip(tasks, results):
        if isinstance(res, Exception):
            log.error("task %s failed: %s", task.get("task_id"), res)


def build_results() -> list[dict]:
    """Assemble output, filling any hole with a style-appropriate fallback."""
    out = []
    for task_id, entry in STATE.items():
        captions = {}
        for style in entry["styles"]:
            cap = entry["captions"].get(style)
            if not cap or not isinstance(cap, str) or not cap.strip():
                cap = captioner._fallback(style, entry.get("fact"))
                log.warning("task %s style %s: using fallback caption", task_id, style)
            captions[style] = cap.strip()
        out.append({"task_id": task_id, "captions": captions})
    return out


def write_results() -> None:
    path = config.OUTPUT_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = build_results()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    log.info("wrote %s (%d tasks)", path, len(payload))


async def amain() -> int:
    t0 = time.monotonic()
    try:
        with open(config.INPUT_PATH) as f:
            tasks = json.load(f)
        if not isinstance(tasks, list):
            raise ValueError("tasks.json is not a list")
    except Exception as e:  # noqa: BLE001
        log.critical("cannot read input tasks: %s", e)
        # Still write an empty-but-valid results file. Exit 0 per contract.
        STATE.clear()
        write_results()
        return 0

    for task in tasks:
        task_id = str(task.get("task_id", ""))
        STATE[task_id] = {"styles": _requested_styles(task), "captions": {}, "fact": None}

    if not config.FIREWORKS_API_KEY and not config.MOCK_API:
        log.critical("FIREWORKS_API_KEY missing — all captions will be fallbacks")

    try:
        await asyncio.wait_for(run_all(tasks), timeout=config.GLOBAL_DEADLINE)
    except asyncio.TimeoutError:
        log.error("global deadline (%.0fs) hit — writing best-available results",
                  config.GLOBAL_DEADLINE)
    except Exception as e:  # noqa: BLE001
        log.error("unexpected orchestrator error: %s", e)
    finally:
        await captioner.close()

    write_results()
    log.info("total runtime: %.0fs", time.monotonic() - t0)
    return 0


def main() -> None:
    try:
        code = asyncio.run(amain())
    except Exception as e:  # noqa: BLE001 — last-ditch: write whatever we have
        log.critical("fatal: %s", e)
        try:
            write_results()
            code = 0
        except Exception:  # noqa: BLE001
            code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
