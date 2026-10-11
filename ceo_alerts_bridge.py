"""CEO alerts -> Eve Slack bridge (localhost-safe, DRY_RUN default).

Reads scitbd_ceo.db and builds Slack Block Kit payloads compatible with:
 - legacy incoming webhooks (SCITBD_SLACK_*_WEBHOOK)
 - eve Slack channel trigger POST /eve/v1/slack (via Vercel Connect SLACK_CONNECTOR)

Usage:
  python ceo_alerts_bridge.py --mode preblock --dry-run
  python ceo_alerts_bridge.py --mode lead --lead-id 1 --dry-run
  python ceo_alerts_bridge.py --mode lead --lead-id 1 --post http://localhost:8770/eve/v1/slack
  python ceo_alerts_bridge.py --mode health --dry-run
"""
import argparse, json, os, sqlite3, pathlib, datetime, urllib.request, urllib.error

DB_PATH = r"D:/CRM_with_GOOGLE_Sheet/ceo/ceo - Copy/scitbd_ceo.db"
DRY_RUN_DEFAULT = os.environ.get("SCITBD_ALERT_DRYRUN", "1") == "1"

def build_preblock(block_id=2):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM operational_blocks WHERE id=?", (block_id,))
    b = dict(cur.fetchone())
    cur.execute("SELECT id, task_title, priority, status FROM daily_tasks WHERE bst_block_id=? AND status IN ('pending','in_progress') ORDER BY id LIMIT 5", (block_id,))
    tasks = [dict(r) for r in cur.fetchall()]
    con.close()
    text = f":bell: Pre-Block Alert — {b['block_name']}"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Pre-Block: {b['block_name'][:120]}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Focus:* {b['core_execution_focus']}\n*Region:* {b['regional_focus']}\n*Window BST:* {b['bst_start']}-{b['bst_end']}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Open tasks:*\n" + ("\n".join([f"• [{t['id']}] {t['task_title'][:80]} `{t['priority']}/{t['status']}`" for t in tasks]) if tasks else "_none — ready for new intake_")}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "via eve Slack agent - trigger /eve/v1/slack"}]}    ]
    return {"text": text, "blocks": blocks, "metadata": {"mode": "preblock", "block_id": block_id}}

def build_lead(lead_id=None):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    if lead_id:
        cur.execute("SELECT * FROM leads WHERE id=?", (lead_id,))
        row = cur.fetchone()
    else:
        cur.execute("SELECT * FROM leads ORDER BY deal_value DESC LIMIT 1")
        row = cur.fetchone()
    con.close()
    if not row:
        lead = {"id": 0, "client_name": "ACME Demo", "email": "ceo@acme.test", "country": "UAE", "deal_value": 12500, "service_line": "Custom ERP", "status": "new"}
    else:
        lead = dict(row)
    big = lead.get("deal_value", 0) >= 10000
    text = f"{':rotating_light: $10k+ LEAD' if big else ':briefcase: New lead'} — {lead['client_name']} ${lead.get('deal_value',0):,.0f}"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{'$10k+ LEAD — CEO escalation' if big else 'New lead'}: {lead['client_name'][:100]}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Value:*\n${lead.get('deal_value',0):,.0f}"},
            {"type": "mrkdwn", "text": f"*Service:*\n{lead.get('service_line','-')}"},
            {"type": "mrkdwn", "text": f"*Country:*\n{lead.get('country','-')}"},
            {"type": "mrkdwn", "text": f"*Contact:*\n{lead.get('email','-')}"},
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Open CRM"}, "url": os.environ.get("SCITBD_CRM_URL", "https://scit.zya.me/"), "action_id": "open_crm"},
            {"type": "button", "text": {"type": "plain_text", "text": "Approve proposal <2h"}, "action_id": "approve_proposal", "style": "primary", "value": str(lead.get("id",0))},
        ]} if big else [],
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Lead #{lead.get('id',0)} • status {lead.get('status','new')} • SLA: proposal <2h, CEO video if >=$10k"}]}
    ]
    return {"text": text, "blocks": [b for b in blocks if b], "metadata": {"mode": "lead", "lead_id": lead.get("id",0), "big": big}}

def build_health():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        cur.execute("SELECT channel, successes, failures, state, score FROM channel_health")
        rows = cur.fetchall()
    except Exception:
        rows = []
    con.close()
    text = ":heartpulse: CEO channel health"
    lines = "\n".join([f"• `{c}` score {s:.1f} {st} (✔{ok} ✖{fail})" for c, ok, fail, st, s in rows]) if rows else "_no probes yet_"
    return {"text": text, "blocks": [
        {"type": "header", "text": {"type": "plain_text", "text": "Channel health"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": lines}},
    ], "metadata": {"mode": "health"}}

def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()[:2000]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:2000]
    except Exception as e:
        return 0, f"ERR {e} (is mock running? try --dry-run)"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["preblock","lead","health"], default="preblock")
    ap.add_argument("--block-id", type=int, default=2)
    ap.add_argument("--lead-id", type=int, default=None)
    ap.add_argument("--post", default=None, help="URL to POST (e.g. http://localhost:8770/eve/v1/slack)")
    ap.add_argument("--dry-run", action="store_true", default=DRY_RUN_DEFAULT)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    payload = {"preblock": lambda: build_preblock(a.block_id), "lead": lambda: build_lead(a.lead_id), "health": build_health}[a.mode]()
    # Eve trigger envelope: Slack events arrive at /eve/v1/slack, but for localhost test we wrap Block Kit as eve input
    eve_envelope = {"triggerPath": "/eve/v1/slack", "connector": os.environ.get("SLACK_CONNECTOR","slack/my-agent"), "event": {"type": "ceo_alert", "payload": payload}}
    print(json.dumps(payload, indent=2)[:4000])
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps({"payload": payload, "eve_envelope": eve_envelope}, indent=2), encoding="utf-8")
        print(f"Saved {a.out}")
    if a.post and not a.dry_run:
        st, body = post_json(a.post, eve_envelope)
        print(f"POST {a.post} -> {st}\n{body}")
    else:
        print(f"DRY_RUN=1 — no network. Re-run with --post http://localhost:8770/eve/v1/slack --dry-run False to test mock, or set SCITBD_ALERT_DRYRUN=0 for real webhooks.")
