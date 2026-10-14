"""Groq (free tier) chat call with a disk cache so CI can replay recorded answers."""
import json, os, hashlib, time, urllib.request
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "llm_cache.json")
MODEL = "openai/gpt-oss-120b"
_c = None
def _cache():
    global _c
    if _c is None:
        _c = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    return _c
def chat(system, user, temperature=0.0, tag=""):
    k = hashlib.sha256(json.dumps([MODEL, system, user, temperature, tag]).encode()).hexdigest()[:20]
    c = _cache()
    if k in c:
        return c[k]
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("no cached answer and no GROQ_API_KEY")
    body = json.dumps({"model": MODEL, "temperature": temperature,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    for i in range(5):
        try:
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", body,
                                         {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ach-agent"})
            out = json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"].strip()
            break
        except Exception as ex:
            if i == 4: raise
            time.sleep(4 * (i + 1))
    c[k] = out
    json.dump(c, open(CACHE, "w"), indent=0, sort_keys=True)
    return out
