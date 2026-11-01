"""Synthetic HTTP process for runtime tests. This is not an LLM backend."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    content = args.content.read_text(encoding="utf-8")
    literal = '{"program":{"loss":{"input":"x"},"gradient":{"const":1}},"explanation":"BackendProbe19"}'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if ((args.mode == "slow_health" and self.path == "/health") or
                    (args.mode == "slow_models" and self.path == "/v1/models")):
                self.send_response(200)
                self.end_headers()
                for _ in range(100):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.05)
                return
            value = {"status": "ok"} if self.path == "/health" else {"data": [{"id": args.alias}]}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(value).encode())

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/apply-template":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"prompt": body["messages"][0]["content"]}).encode())
                return
            if self.path == "/tokenize":
                count = len(body["content"].split()) + 1
                if args.mode == "oversize_context": count = 10000
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"tokens": list(range(count))}).encode())
                return
            control = body["messages"][0]["content"].startswith("Output BROKEN")
            if not control and args.mode == "guard_slow":
                time.sleep(3)
            if not control and args.mode == "slow":
                # Drip bytes often enough to defeat a socket inactivity timeout.
                self.send_response(200)
                self.end_headers()
                for _ in range(100):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.05)
                return
            if not control and args.mode == "source_changed":
                args.model.write_bytes(args.model.read_bytes() + b"changed")
            text = ("BROKEN" if args.mode == "bad_control" else literal) if control else content
            n_prompt = len(body["messages"][0]["content"].split()) + 1
            usage = {"completion_tokens": 10, "prompt_tokens": n_prompt, "total_tokens": n_prompt + 10,
                     "prompt_tokens_details": {"cached_tokens": 0}}
            if args.mode == "bad_usage" and not control: usage["total_tokens"] += 1
            value = {"choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": usage}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"x" * 262145 if args.mode == "oversize" and not control else json.dumps(value).encode())

        def log_message(self, *_):
            pass

    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
