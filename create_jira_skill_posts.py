"""Create Jira posts for all Eve agent skills in project STT.

Structure: 1 Epic (parent) + 1 Task per skill (child via parent field).

Usage:
  set JIRA_EMAIL=you@company.com
  set JIRA_API_TOKEN=your_token   (create: https://id.atlassian.com/manage-profile/security/api-tokens)
  python create_jira_skill_posts.py [--dry-run]

Auth: Basic (email:token). Token value is never printed or logged.
"""
import argparse, base64, json, os, pathlib, sys, urllib.request, urllib.error

BASE = "https://scitbd.atlassian.net"
PROJECT = "STT"
SKILLS_DIR = pathlib.Path(__file__).parent / "agent" / "skills"

SKILL_ORDER = ["scitbd_ops_plan.md", "scitbd_sales_engine.md", "plan_a_trip.md"]


def adf(text: str) -> dict:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    content = []
    for p in paras[:12]:
        content.append(
            {"type": "paragraph", "content": [{"type": "text", "text": p[:2000]}]}
        )
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph"}]}


def load_skills():
    skills = []
    for fname in SKILL_ORDER:
        p = SKILLS_DIR / fname
        if not p.exists():
            print(f"SKIP missing {fname}")
            continue
        body = p.read_text(encoding="utf-8")
        title = fname.replace(".md", "").replace("_", " ").title()
        skills.append({"file": fname, "title": f"Skill: {title}", "body": body})
    return skills


def api(method, path, auth, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json", **auth}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {"httpError": e.code, "body": e.read().decode()[:1000]}
    except Exception as e:
        return 0, {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not email or not token:
        print("Missing JIRA_EMAIL / JIRA_API_TOKEN env vars.")
        sys.exit(2)
    cred = base64.b64encode(f"{email}:{token}".encode()).decode()
    auth = {"Authorization": "Basic " + cred}

    skills = load_skills()
    print(f"Skills to post: {[s['file'] for s in skills]}")

    epic_body = (
        "Parent epic tracking publication of all Eve agent skills to the team.\n\n"
        "Skills in scope:\n" + "\n".join(f"- {s['title']} ({s['file']})" for s in skills)
        + "\n\nSource repo: scit-eve-slack-agent/agent/skills/"
    )
    epic_payload = {
        "fields": {
            "project": {"key": PROJECT},
            "summary": "Publish Eve agent skills to team workflow",
            "description": adf(epic_body),
            "issuetype": {"name": "Task"},
        }
    }

    if a.dry_run:
        print("--- DRY RUN: epic payload ---")
        print(json.dumps({**epic_payload, "fields": {**epic_payload["fields"]}}, indent=2)[:2000])
        for s in skills:
            print(f"--- DRY RUN: task [{s['title']}] body chars={len(s['body'])} ---")
        print("Dry run OK. Re-run without --dry-run to create.")
        return

    st, epic = api("POST", "/rest/api/3/issue", auth, epic_payload)
    print(f"Epic create -> {st}: {json.dumps(epic)[:500]}")
    if st not in (200, 201) or "key" not in epic:
        print("Epic creation failed, aborting.")
        sys.exit(1)
    epic_key = epic["key"]
    print(f"EPIC: {epic_key}")

    created = [epic_key]
    for s in skills:
        task_payload = {
            "fields": {
                "project": {"key": PROJECT},
                "parent": {"key": epic_key},
                "summary": s["title"],
                "description": adf(f"Source file: agent/skills/{s['file']}\n\n{s['body']}"),
                "issuetype": {"name": "Sub-task"},
            }
        }
        st, resp = api("POST", "/rest/api/3/issue", auth, task_payload)
        print(f"Task [{s['title']}] -> {st}: {json.dumps(resp)[:300]}")
        if "key" in resp:
            created.append(resp["key"])

    print(f"\nDone. Created: {created}")
    print(f"Board: https://scitbd.atlassian.net/jira/core/projects/STT/board")


if __name__ == "__main__":
    main()
