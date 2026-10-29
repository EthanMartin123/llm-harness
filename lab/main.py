import os, json, time, uuid, subprocess
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, Header, HTTPException
from pydantic import BaseModel
import ollama
from lab import rag, tools

MODEL = os.getenv("LAB_MODEL", "qwen2.5:3b")
HARDENED = os.getenv("HARDENED", "0") == "1"
DEBUG = os.getenv("LAB_DEBUG", "1") == "1"
OPTS = {"temperature": 0, "seed": 42, "num_ctx": 8192}
llm = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
SYSTEM = open("lab/system_prompt.txt").read()

app = FastAPI(title="HelpBot Lab")


class ChatIn(BaseModel):
    message: str
    user_id: str | None = None


def git_hash():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "nogit"


def log(trace):
    os.makedirs("results", exist_ok=True)
    with open("results/lab_trace.jsonl", "a") as f:
        f.write(json.dumps(trace) + "\n")


@app.get("/health")
def health():
    return {"model": MODEL, "hardened": HARDENED, "git": git_hash()}


@app.post("/chat")
def chat(req: ChatIn):
    t0 = time.time()
    trace = {"trace_id": str(uuid.uuid4()), "hardened": HARDENED,
             "model": MODEL, "git": git_hash(), "prompt": req.message}
    chunks = rag.retrieve(req.message)
    trace["retrieved"] = [{"id": c["id"], "trust": c["meta"]["trust"], "text": c["text"]} for c in chunks]
    context = "\n\n".join(c["text"] for c in chunks)   # W6: context pasted in with no delimiting
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {req.message}"}]
    resp = llm.chat(model=MODEL, messages=messages, tools=tools.SCHEMAS, options=OPTS)
    trace["tool_calls"] = []
    for _ in range(3):                                 # allow up to 3 tool rounds
        calls = resp.message.tool_calls or []
        if not calls:
            break
        messages.append(resp.message)
        for tc in calls:
            args = dict(tc.function.arguments)
            result = tools.dispatch(tc.function.name, args)   # W2/W3/W5: executed with no gating
            trace["tool_calls"].append({"name": tc.function.name, "args": args, "result": result})
            messages.append({"role": "tool", "content": json.dumps(result)})
        resp = llm.chat(model=MODEL, messages=messages, tools=tools.SCHEMAS, options=OPTS)
    trace["answer"] = resp.message.content             # W7: raw output, no encoding/filtering
    trace["latency_s"] = round(time.time() - t0, 2)
    trace["tokens_out"] = getattr(resp, "eval_count", None)
    log(trace)
    return {"answer": trace["answer"], "trace": trace if DEBUG else None}


@app.post("/upload")
async def upload(file: UploadFile):
    # W8: anyone can upload; documents are trusted like admin content
    os.makedirs("data/uploads", exist_ok=True)
    path = f"data/uploads/{os.path.basename(file.filename)}"
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"ingested": rag.ingest_file(path, trust="upload")}


@app.post("/admin/reset")
def reset(x_admin_token: str = Header(default="")):
    if x_admin_token != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(403)
    for f in os.listdir("data/uploads") if os.path.isdir("data/uploads") else []:
        os.remove(f"data/uploads/{f}")
    for f in ("results/outbox.jsonl", "results/tickets.jsonl"):
        if os.path.exists(f):
            os.remove(f)
    return {"chunks": rag.rebuild()}
