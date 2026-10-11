"""Mock Eve Slack trigger on localhost: POST /eve/v1/slack -> 200 ack
Run: python mock_eve_slack.py --port 8770
"""
import json, argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._send(200, {"ok": True, "triggerPath": "/eve/v1/slack", "connector": "SLACK_CONNECTOR", "hint": "POST eve envelope here"})
    def do_POST(self):
        n = int(self.headers.get("Content-Length",0))
        raw = self.rfile.read(n) if n else b"{}"
        try: data = json.loads(raw.decode() or "{}")
        except Exception as e: return self._send(400, {"ok": False, "error": str(e)})
        if self.path in ("/eve/v1/slack","/"):
            txt = (data.get("event",{}).get("payload",{}).get("text") or data.get("text") or "")[:120]
            return self._send(200, {"ok": True, "acked": True, "triggerPath": "/eve/v1/slack", "preview": txt, "message": "MOCK ack — no Slack call"})
        return self._send(404, {"ok": False, "path": self.path})
    def log_message(self, f,*a): print(f"[mock-eve] {self.command} {self.path} - {f % a}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port",type=int,default=8770); args = ap.parse_args()
    print(f"Mock Eve Slack at http://localhost:{args.port}/eve/v1/slack")
    HTTPServer(("127.0.0.1",args.port),H).serve_forever()
