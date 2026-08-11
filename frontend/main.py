"""FastAPI proxy for Asset Maintenance Agent."""

import os
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    output = result.stdout.strip() or result.stderr.strip()

    for line in output.splitlines():
        if "Session:" in line:
            parts = line.split("Session:")
            if len(parts) > 1:
                _sessions[user_id] = parts[1].strip()

    lines = [
        l for l in output.splitlines()
        if not l.startswith("Querying remote agent:")
        and not l.startswith("Session:")
        and not l.startswith("  Resume with:")
        and not l.startswith("Using project root directory:")
        and not l.startswith("[user]:")
    ]
    clean_text = "\n".join(lines).strip() or "No response returned."

    return JSONResponse({"parts": [{"kind": "text", "text": clean_text}]})

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8082)))
