# backend/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# File Imports
from api.translations import router as translations_router
from model.model import load_model

# ==============================================================================
# 1. CONFIGURE LOGGING & MODEL
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# LIFESPAN EVENT FOR STARTUP
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Code to run before the server starts accepting any requests
    try :
        logger.info("Server starting up: Setting up the translation model...")
        load_model()
        logger.info("model loaded successfully. Server is ready")
    except Exception as e:
        logger.critical(f"FATAL: Failed to load the translation model. Unable to start the application, {e}", exc_info=True)
        raise RuntimeError("Failed to load the translation model.") from e
    
    yield
    logger.info("Shutting down the server")

# ==============================================================================
# FASTAPI APP
# ==============================================================================
app = FastAPI(
    title="Chinese CAD Translation",
    lifespan=lifespan
    )


# ==============================================================================
# CONFIGURING CORS
# ==============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Setting the API routes
# ==============================================================================

@app.get("/health")
async def health_check():
    """A simple endpoint to check if the server is up and running."""
    return {"status": "ready"}

app.include_router(translations_router, prefix="/translate", tags=["translation"])