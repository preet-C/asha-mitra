from fastapi import FastAPI

app = FastAPI(title="ASHA Mitra")

@app.get("/api/health")
def health():
    return {"ok": True}

# WebSocket routes go ABOVE this line (P9, P10).
# Static frontend mount goes at the very END (P11).
