from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISSUES = ROOT / "docs" / "issues"
PROPOSALS = ROOT / "docs" / "proposals"


def _numbered_markdown(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.md") if re.fullmatch(r"\d{4}-.+\.md", path.name))


def test_issue_files_and_roadmap_are_one_to_one() -> None:
    issue_files = sorted(path for path in ISSUES.glob("*.md") if path.name not in {"index.md", "roadmap.md"})
    by_id: dict[str, Path] = {}
    for path in issue_files:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^id: ([A-Z]+-\d{3})$", text)
        assert match, f"{path.relative_to(ROOT)} has no valid issue id"
        issue_id = match.group(1)
        assert issue_id not in by_id, f"duplicate issue id {issue_id}: {by_id[issue_id]} and {path}"
        by_id[issue_id] = path
        source = re.search(r"(?m)^source: (review|work|adr)$", text)
        assert source, f"{path.relative_to(ROOT)} has no source: review | work | adr"

    roadmap = (ISSUES / "roadmap.md").read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^\| \[([A-Z]+-\d{3})\]\(([^)]+\.md)\) \|", roadmap)
    row_ids = [issue_id for issue_id, _ in rows]
    duplicates = sorted(issue_id for issue_id, count in Counter(row_ids).items() if count > 1)
    assert not duplicates, f"duplicate roadmap rows: {duplicates}"
    assert set(row_ids) == set(by_id), (
        f"roadmap/file mismatch; missing rows={sorted(set(by_id) - set(row_ids))}, "
        f"missing files={sorted(set(row_ids) - set(by_id))}"
    )
    for issue_id, link in rows:
        target = (ISSUES / link).resolve()
        assert target == by_id[issue_id].resolve(), f"roadmap link for {issue_id} points to {link}"


def test_proposal_files_and_index_are_one_to_one() -> None:
    proposal_files = _numbered_markdown(PROPOSALS)
    by_number = {path.name[:4]: path for path in proposal_files}
    assert len(by_number) == len(proposal_files), "duplicate proposal numbers"

    index = (PROPOSALS / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^\| \[(\d{4})\]\(([^)]+\.md)\) \|", index)
    row_numbers = [number for number, _ in rows]
    assert len(row_numbers) == len(set(row_numbers)), "duplicate proposal rows"
    assert set(row_numbers) == set(by_number), (
        f"proposal index/file mismatch; missing rows={sorted(set(by_number) - set(row_numbers))}, "
        f"missing files={sorted(set(row_numbers) - set(by_number))}"
    )
    for number, link in rows:
        assert (PROPOSALS / link).resolve() == by_number[number].resolve()

    forbidden = re.compile(r"(?im)^(status:|#+\s+(status|статус|готовность)\b)")
    for path in proposal_files:
        assert not forbidden.search(path.read_text(encoding="utf-8")), (
            f"{path.relative_to(ROOT)} carries readiness; status belongs only in proposals/README.md"
        )


def test_retired_backlog_locations_are_not_link_targets() -> None:
    ignored_parts = {".git", ".venv", "node_modules", "dist"}
    offenders: list[str] = []
    for path in ROOT.rglob("*.md"):
        if any(part in ignored_parts for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\]\([^)]*(?:\.agent-review|manual-qa-pending)[^)]*\)", text):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"retired backlog locations are still linked: {offenders}"
    assert not (ROOT / "docs" / "manual-qa-pending.md").exists()


def test_relative_markdown_links_resolve() -> None:
    markdown_files = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md"]
    markdown_files.extend((ROOT / "docs").rglob("*.md"))
    broken: list[str] = []
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip("<>").split("#", 1)[0]
            if target in {"", "url"} or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                continue
            if not (path.parent / target).resolve().exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, "broken relative Markdown links:\n" + "\n".join(broken)
