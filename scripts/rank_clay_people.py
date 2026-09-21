from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_QUERY = (
    'select from people where location_country = "United States" and '
    "experiences.any(is_current = true and "
    '(job_title contains ("founder", "co-founder") or seniority = "Founder") and '
    'company.company_size in ("51-200", "201-500") and '
    'company.industry = "Software Development" and '
    '(company.ai_business_types contains "B2B" or company.ai_business_types is_null))'
)
TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
PROMPT_VERSION = "operating-founder-v2"


class ClayLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    city: str | None = None
    state_or_province: str | None = None


class ClayExperience(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ClayPerson(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clay_profile_id: int | str | None = None
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    linkedin_url: str | None = None
    location: ClayLocation | None = None
    matched_experiences: list[ClayExperience] = Field(default_factory=list)


class ClayPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[ClayPerson] = Field(default_factory=list)
    hasMore: bool = False
    sourceType: str | None = None
    exhaustionReason: str | None = None
    periodQuota: dict[str, Any] | None = None


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run_clay(binary: str, args: list[str]) -> dict[str, Any]:
    resolved = shutil.which(binary)
    if resolved is None:
        raise RuntimeError(
            f"Clay CLI '{binary}' was not found on PATH. Follow the official "
            "clay-run/agent-plugins setup guide."
        )
    process = subprocess.run(
        [resolved, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = process.stdout.strip() or process.stderr.strip()
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Clay CLI returned non-JSON output (exit {process.returncode})."
        ) from exc
    if process.returncode != 0 or "error" in payload:
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise RuntimeError(f"Clay CLI failed: {message or 'unknown error'}")
    return payload


def create_search(binary: str, query: str) -> str:
    payload = run_clay(binary, ["searches", "query-mode", "create", "--query", query])
    search_id = payload.get("searchId")
    if not isinstance(search_id, str) or not search_id:
        raise RuntimeError("Clay CLI did not return a searchId.")
    return search_id


def fetch_page(binary: str, search_id: str, limit: int) -> ClayPage:
    payload = run_clay(
        binary,
        ["searches", "query-mode", "run", search_id, "--limit", str(limit)],
    )
    return ClayPage.model_validate(payload)


def quota_allows_page(period_quota: dict[str, Any] | None, planned: int) -> bool:
    if not period_quota:
        return True
    limit = period_quota.get("limit")
    remaining = period_quota.get("remaining")
    if not isinstance(limit, (int, float)) or not isinstance(remaining, (int, float)):
        return True
    projected = remaining - planned
    return projected >= limit * 0.15


def jev_state(person: ClayPerson) -> dict[str, Any]:
    return {
        "matched_experiences": [
            {
                "title": experience.title,
                "start_date": experience.start_date,
                "end_date": experience.end_date,
            }
            for experience in person.matched_experiences
        ],
        "clay_search_constraints": {
            "current_role": True,
            "target_role": "Founder or Co-Founder",
        },
    }


def jev_payload(person: ClayPerson, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "state": {"candidate": jev_state(person)},
        "questions": {
            "role_type": {
                "type": "choice",
                "instructions": (
                    "Which category best describes the candidate's relationship to the "
                    "company in `candidate.matched_experiences`? Use only the supplied "
                    "titles and dates."
                ),
                "criteria": {
                    "operating_founder": (
                        "Currently founded or co-founded the company and operates or leads "
                        "it. Includes Founder, Co-Founder, Founder and CEO, and Co-Founder "
                        "and CEO."
                    ),
                    "investor_or_board": (
                        "Investor, founding investor, advisor, or board member without a "
                        "current operating founder role."
                    ),
                    "founding_employee": (
                        "Early, founding, or first employee or functional hire who did not "
                        "found the company."
                    ),
                    "founder_support": (
                        "Founder's office, assistant to founder, recruiter, talent, sales, "
                        "or another role supporting a founder."
                    ),
                    "unclear_other": (
                        "The evidence is missing, contradictory, or does not fit the other "
                        "roles."
                    ),
                },
            },
            "current_founder": {
                "type": "noul",
                "instructions": (
                    "Based only on `candidate`, does the person clearly and currently hold "
                    "an operating Founder or Co-Founder role? Evaluate the matched "
                    "experience title and dates."
                ),
                "criteria": {
                    "true": (
                        "A matched experience explicitly shows an operating Founder or "
                        "Co-Founder role and appears current because it has no end date."
                    ),
                    "false": (
                        "The role ended, is ambiguous, or refers only to investing, "
                        "advising, board membership, a founding employee, or founder support."
                    ),
                },
            },
        },
    }


def score_person(
    client: httpx.Client,
    api_key: str,
    person: ClayPerson,
    model: str,
    current_threshold: float,
    operating_threshold: float,
    max_attempts: int = 6,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(max_attempts):
        try:
            response = client.post(
                TYPESAFE_ENDPOINT,
                headers=headers,
                json=jev_payload(person, model),
            )
        except httpx.TransportError:
            if attempt + 1 >= max_attempts:
                raise
            time.sleep(min(30.0, 2**attempt + random.random()))
            continue

        if response.status_code in {429, 529} and attempt + 1 < max_attempts:
            retry_after = response.headers.get("Retry-After")
            delay = (
                float(retry_after)
                if retry_after
                else min(30.0, 2**attempt + random.random())
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        payload = response.json()
        answers = payload.get("answers", {})
        role_answer = answers.get("role_type", {})
        current_answer = answers.get("current_founder", {})
        role_probabilities = role_answer.get("probabilities", {})
        current_probability = current_answer.get("noul")
        operating_probability = role_probabilities.get("operating_founder")
        if not isinstance(current_probability, (int, float)):
            raise RuntimeError("JEV response omitted current_founder.noul.")
        if not isinstance(operating_probability, (int, float)):
            raise RuntimeError(
                "JEV response omitted the operating_founder Choice probability."
            )

        role_type = role_answer.get("choice")
        current = float(current_probability)
        operating = float(operating_probability)
        return {
            "prompt_version": PROMPT_VERSION,
            "score": (0.60 * current) + (0.40 * operating),
            "qualified": (
                role_type == "operating_founder"
                and current >= current_threshold
                and operating >= operating_threshold
            ),
            "role_type": role_type,
            "role_type_confidence": role_answer.get("confidence"),
            "role_probabilities": role_probabilities,
            "current_founder_probability": current,
            "operating_founder_probability": operating,
            "model": payload.get("model", model),
            "usage": payload.get("usage", {}),
        }

    raise RuntimeError("JEV retry limit reached.")


def public_person(person: ClayPerson) -> dict[str, Any]:
    return person.model_dump(mode="json", exclude_none=True)


def rank_page(
    people: list[ClayPerson],
    api_key: str,
    model: str,
    workers: int,
    current_threshold: float,
    operating_threshold: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any] | None] = [None] * len(people)
    limits = httpx.Limits(max_connections=workers, max_keepalive_connections=workers)
    with httpx.Client(timeout=120.0, limits=limits) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    score_person,
                    client,
                    api_key,
                    person,
                    model,
                    current_threshold,
                    operating_threshold,
                ): index
                for index, person in enumerate(people)
            }
            completed = 0
            for future in as_completed(futures):
                index = futures[future]
                results[index] = {
                    "person": public_person(people[index]),
                    "jev": future.result(),
                }
                completed += 1
                if completed % 25 == 0 or completed == len(people):
                    print(f"Ranked {completed}/{len(people)} candidates", flush=True)
    return [result for result in results if result is not None]


def sort_and_rank(results: list[dict[str, Any]]) -> None:
    results.sort(key=lambda item: item["jev"]["score"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank


def preferred_experience(person: dict[str, Any]) -> dict[str, Any]:
    experiences = person.get("matched_experiences") or []
    for experience in experiences:
        title = str(experience.get("title") or "").casefold()
        if "founder" in title and not experience.get("end_date"):
            return experience
    return experiences[0] if experiences else {}


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    columns = [
        "rank",
        "jev_score",
        "current_founder_probability",
        "role_type",
        "operating_founder_probability",
        "name",
        "first_name",
        "last_name",
        "linkedin_url",
        "location",
        "city",
        "state_or_province",
        "company",
        "title",
        "start_date",
        "end_date",
        "clay_profile_id",
        "jev_model",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for item in results:
            person = item["person"]
            location = person.get("location") or {}
            experience = preferred_experience(person)
            writer.writerow(
                {
                    "rank": item["rank"],
                    "jev_score": f'{item["jev"]["score"]:.6f}',
                    "current_founder_probability": (
                        f'{item["jev"]["current_founder_probability"]:.6f}'
                    ),
                    "role_type": item["jev"]["role_type"],
                    "operating_founder_probability": (
                        f'{item["jev"]["operating_founder_probability"]:.6f}'
                    ),
                    "name": person.get("name"),
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "linkedin_url": person.get("linkedin_url"),
                    "location": location.get("name"),
                    "city": location.get("city"),
                    "state_or_province": location.get("state_or_province"),
                    "company": experience.get("company"),
                    "title": experience.get("title"),
                    "start_date": experience.get("start_date"),
                    "end_date": experience.get("end_date"),
                    "clay_profile_id": person.get("clay_profile_id"),
                    "jev_model": item["jev"]["model"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Clay people and rank current operating founders with JEV."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--search-id", help="Reuse an existing Clay Query Mode search.")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--target-qualified", type=int, default=500)
    parser.add_argument("--max-candidates", type=int, default=2000)
    parser.add_argument("--current-founder-threshold", type=float, default=0.90)
    parser.add_argument("--operating-founder-threshold", type=float, default=0.80)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--model", default="jev-latest")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--clay-binary",
        default=os.environ.get("CLAY_BINARY", "clay"),
        help="Clay executable name or path; defaults to CLAY_BINARY or clay.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 1 <= args.page_size <= 500:
        raise RuntimeError("--page-size must be between 1 and 500.")
    if args.target_qualified < 1:
        raise RuntimeError("--target-qualified must be at least 1.")
    if args.max_candidates < args.page_size:
        raise RuntimeError("--max-candidates must be at least --page-size.")
    if args.workers < 1:
        raise RuntimeError("--workers must be at least 1.")
    for name in ("current_founder_threshold", "operating_founder_threshold"):
        value = getattr(args, name)
        if not 0 <= value <= 1:
            raise RuntimeError(f"--{name.replace('_', '-')} must be between 0 and 1.")


def main() -> int:
    started_at = time.perf_counter()
    args = parse_args()
    validate_args(args)
    load_env(args.env_file)
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY is missing from the environment or env file.")

    search_id = args.search_id or create_search(args.clay_binary, args.query)
    all_results: list[dict[str, Any]] = []
    page_size = args.page_size
    page_number = 1
    last_page = ClayPage()
    quota_safeguard_triggered = False

    while len(all_results) < args.max_candidates:
        if page_number > 1 and not quota_allows_page(last_page.periodQuota, page_size):
            quota_safeguard_triggered = True
            print(
                "Quota safeguard stopped before the next Clay page; partial results "
                "will be written.",
                flush=True,
            )
            break
        page = fetch_page(args.clay_binary, search_id, page_size)
        last_page = page
        print(f"Clay page {page_number} returned {len(page.data)} people", flush=True)
        if not page.data:
            break

        all_results.extend(
            rank_page(
                page.data,
                api_key,
                args.model,
                args.workers,
                args.current_founder_threshold,
                args.operating_founder_threshold,
            )
        )
        sort_and_rank(all_results)
        qualified_count = sum(item["jev"]["qualified"] for item in all_results)
        print(
            f"Qualified {qualified_count}/{len(all_results)} candidates",
            flush=True,
        )

        if qualified_count >= args.target_qualified:
            break
        if not page.hasMore or len(all_results) >= args.max_candidates:
            break

        remaining_capacity = args.max_candidates - len(all_results)
        needed = args.target_qualified - qualified_count
        yield_rate = max(qualified_count / len(all_results), 0.10)
        estimated = math.ceil((needed / yield_rate) * 1.15)
        page_size = min(500, remaining_capacity, max(20, estimated))
        page_number += 1

    sort_and_rank(all_results)
    qualified = [item for item in all_results if item["jev"]["qualified"]]
    selected = qualified[: args.target_qualified]
    sort_and_rank(selected)
    if not selected:
        raise RuntimeError("No candidates met the JEV qualification thresholds.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = args.output_dir / f"clay_jev_people_{timestamp}.json"
    csv_path = args.output_dir / f"clay_jev_people_{timestamp}.csv"
    usage = {
        "input_tokens": sum(
            int(item["jev"]["usage"].get("input_tokens") or 0)
            for item in all_results
        ),
        "output_tokens": sum(
            int(item["jev"]["usage"].get("output_tokens") or 0)
            for item in all_results
        ),
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "target_qualified": args.target_qualified,
        "current_founder_threshold": args.current_founder_threshold,
        "operating_founder_threshold": args.operating_founder_threshold,
        "scored_candidate_count": len(all_results),
        "qualified_candidate_count": len(qualified),
        "result_count": len(selected),
        "target_reached": len(selected) >= args.target_qualified,
        "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        "clay_has_more": last_page.hasMore,
        "clay_exhaustion_reason": last_page.exhaustionReason,
        "quota_safeguard_triggered": quota_safeguard_triggered,
        "jev_usage": usage,
        "results": selected,
    }
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_csv(csv_path, selected)

    print(f"Ranked JSON: {json_path}", flush=True)
    print(f"Ranked CSV: {csv_path}", flush=True)
    print(
        f"Selected {len(selected)} qualified people from {len(all_results)} "
        f"Clay candidates; target reached: {report['target_reached']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
