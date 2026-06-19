from fastapi import Depends, FastAPI, Query, Request, Response, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

app = FastAPI(title="MedTriage Framework Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    # Logique de traitement des messages WhatsApp
    return JSONResponse(
        content={"status": "received"},
        status_code=200
    )

# ... (le reste du fichier reste inchangé)