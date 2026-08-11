"""FastAPI proxy for Asset Maintenance Agent."""

import os
import re
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "data", "docs")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI()

_sessions = {}

@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={"parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]},
    )

@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"

    session_id = _sessions.get(user_id)
    cmd = [
        "agents-cli", "run",
        "--mode", "adk",
        message
    ]

    if session_id:
        cmd.extend(["--session-id", session_id])

    env = os.environ.copy()
    env["GOOGLE_CLOUD_PROJECT"] = "qwiklabs-gcp-04-0b387e12c6d8"

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=BASE_DIR,
    )
    output = result.stdout.strip() or result.stderr.strip()

    for line in output.splitlines():
        if "Session:" in line:
            parts = line.split("Session:")
            if len(parts) > 1:
                _sessions[user_id] = parts[1].strip()

    # Check for generated artifact files
    artifact_texts = []
    artifact_matches = re.findall(r"(\.google-agents-cli/artifacts/[a-f0-9]+\.txt)", output)
    for art_path in artifact_matches:
        full_art_path = os.path.join(BASE_DIR, art_path)
        if os.path.exists(full_art_path):
            try:
                with open(full_art_path, "r", encoding="utf-8") as f:
                    artifact_texts.append(f.read().strip())
            except Exception:
                pass

    filtered_lines = []
    skip_artifacts_header = False

    for l in output.splitlines():
        l_str = l.strip()
        if (
            l_str.startswith("Local server started")
            or l_str.startswith("Stop with:")
            or l_str.startswith("Local server stopped")
            or l_str.startswith("Using project root directory:")
            or l_str.startswith("[user]:")
            or l_str.startswith("Querying remote agent:")
            or l_str.startswith("Session:")
            or l_str.startswith("  Resume with:")
            or l_str.startswith("[root_agent]:")
        ):
            continue

        if l_str.startswith("Artifacts:"):
            skip_artifacts_header = True
            continue

        if skip_artifacts_header and l_str.startswith(".google-agents-cli/artifacts/"):
            continue

        filtered_lines.append(l)

    clean_text = "\n".join(filtered_lines).strip()

    if artifact_texts:
        if clean_text:
            clean_text = clean_text + "\n\n" + "\n\n".join(artifact_texts)
        else:
            clean_text = "\n\n".join(artifact_texts)

    if not clean_text:
        clean_text = "Here are the technical document manuals available in the system:\n\n" + \
                     "\n".join([f"• [{f}](/docs/{f})" for f in os.listdir(DOCS_DIR) if not f.startswith(".")])

    return JSONResponse({"parts": [{"kind": "text", "text": clean_text}]})

# Mount /docs for PDF and Markdown document viewing/downloads
if os.path.exists(DOCS_DIR):
    app.mount("/docs", StaticFiles(directory=DOCS_DIR), name="docs")

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8082)))
