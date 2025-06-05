import os
import uuid
import urllib.parse
import traceback

from fastapi import (
    FastAPI, Request, Depends, Form, UploadFile, File,
    status, HTTPException
)
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.config import Config

from sqlalchemy.orm import Session

from demucs.pretrained import get_model
from isolate import isolate_stem

from db import SessionLocal, engine
from models import Base, User
from auth_utils import hash_password, verify_password
from email_validator import validate_email, EmailNotValidError

# At top of main.py, before routes:
for folder in ["temp_uploads", "uploads", "outputs"]:
    os.makedirs(folder, exist_ok=True)


# ────────────────────────────────────────────────────────────────────────────────
# Database setup
# ────────────────────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ────────────────────────────────────────────────────────────────────────────────
# Session middleware configuration
# ────────────────────────────────────────────────────────────────────────────────
config = Config(".env")
SESSION_SECRET_KEY = config("SESSION_SECRET_KEY", cast=str, default="supersecret")

middleware = [
    Middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET_KEY,
        max_age=60 * 60 * 24 * 365,  # 1 year
        https_only=False
    )
]

app = FastAPI(middleware=middleware)

# ────────────────────────────────────────────────────────────────────────────────
# Limit upload size (100 MB)
# ────────────────────────────────────────────────────────────────────────────────
class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        max_size = 100 * 1024 * 1024  # 100 MB
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            return JSONResponse(
                status_code=413,
                content={"status": "error", "message": "File too large. Limit is 100MB."}
            )
        return await call_next(request)

app.mount("/static", StaticFiles(directory="public", html=True), name="static")
app.add_middleware(LimitUploadSizeMiddleware)

# ────────────────────────────────────────────────────────────────────────────────
# Load Demucs model once at startup
# ────────────────────────────────────────────────────────────────────────────────
print("📦 Loading Demucs model...")
demucs_model = get_model(name="htdemucs")
print("✅ Demucs model loaded.")

# ────────────────────────────────────────────────────────────────────────────────
# Signup routes
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/")
    return """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <title>Sign Up – AI Stem Remover</title>
        <link rel="stylesheet" href="/static/style.css?v=1">
        <style>
        input[type="email"], input[type="password"], input[type="text"] {
            background-color: #1a1a1a;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            font-family: var(--font-main);
            font-size: 1rem;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            width: 100%;
            box-sizing: border-box;
            margin: 0.5rem 0 1rem;
        }
        input[type="checkbox"] {
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            margin-right: 0.5rem;
            cursor: pointer;
            background-color: var(--container-bg);
            border: 2px solid var(--primary-color);
            border-radius: 4px;
            position: relative;
        }
        input[type="checkbox"]:checked {
            background-color: var(--primary-color);
        }
        input[type="checkbox"]:checked::after {
            content: "";
            position: absolute;
            top: 50%;
            left: 50%;
            width: 6px;
            height: 10px;
            border: solid var(--text-color);
            border-width: 0 2px 2px 0;
            transform: translate(-50%, -60%) rotate(45deg);
        }
        .checkbox-row {
            display: flex;
            align-items: center;
            margin: 0.5rem 0 1rem;
        }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1 class="gradient-header">🎵 AI Stem Remover</h1>
                <p>Isolate vocals, drums, bass, or instruments from your music using AI – fast &amp; free.</p>
            </header>
            <section class="card">
                <h2>Create Account</h2>
                <form action="/signup" method="post">
                    <div class="form-group">
                        <label for="email">EMAIL ADDRESS</label>
                        <input type="email" id="email" name="email" placeholder="you@example.com" required />
                    </div>
                    <div class="form-group">
                        <label for="password">PASSWORD</label>
                        <input type="password" id="password" name="password" placeholder="Choose a strong password" required />
                    </div>
                    <div class="form-group">
                        <label for="full_name">FULL NAME (OPTIONAL)</label>
                        <input type="text" id="full_name" name="full_name" placeholder="Jane Doe" />
                    </div>
                    <div class="checkbox-row">
                        <input type="checkbox" id="subscribe" name="subscribe" value="yes" />
                        <label for="subscribe">Join our email list</label>
                    </div>
                    <button type="submit">Sign Up</button>
                </form>
                <p style="margin-top: 1rem; color: var(--text-muted);">
                    Already have an account? <a href="/login" style="color: var(--accent-color);">Log In</a>
                </p>
            </section>
            <footer>
                <p>&copy; 2025 AI Stem Remover. All rights reserved.</p>
            </footer>
        </div>
    </body>
    </html>
    """

@app.post("/signup")
def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    subscribe: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        valid = validate_email(email)
        email = valid.email
    except EmailNotValidError:
        return HTMLResponse("<h3>Invalid email. <a href='/signup'>Try again</a>.</h3>", status_code=400)

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return HTMLResponse("<h3>Email already registered. <a href='/login'>Log in</a>.</h3>", status_code=400)

    hashed_pw = hash_password(password)
    new_user = User(email=email, hashed_password=hashed_pw, full_name=full_name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if subscribe == "yes":
        pass  # Add to mailing list if desired

    request.session["user_id"] = new_user.id
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

# ────────────────────────────────────────────────────────────────────────────────
# Login routes
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/")
    return """
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <title>Log In – AI Stem Remover</title>
        <link rel="stylesheet" href="/static/style.css?v=1">
        <style>
        input[type="email"], input[type="password"] {
            background-color: #1a1a1a;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            font-family: var(--font-main);
            font-size: 1rem;
            padding: 0.85rem 1rem;
            border-radius: 8px;
            width: 100%;
            box-sizing: border-box;
            margin: 0.5rem 0 1rem;
        }
        input[type="checkbox"] {
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            margin-right: 0.5rem;
            cursor: pointer;
            background-color: var(--container-bg);
            border: 2px solid var(--primary-color);
            border-radius: 4px;
            position: relative;
        }
        input[type="checkbox"]:checked {
            background-color: var(--primary-color);
        }
        input[type="checkbox"]:checked::after {
            content: "";
            position: absolute;
            top: 50%;
            left: 50%;
            width: 6px;
            height: 10px;
            border: solid var(--text-color);
            border-width: 0 2px 2px 0;
            transform: translate(-50%, -60%) rotate(45deg);
        }
        .checkbox-row {
            display: flex;
            align-items: center;
            margin: 0.5rem 0 1rem;
        }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1 class="gradient-header">🎵 AI Stem Remover</h1>
                <p>Log in to access the AI Stem Remover.</p>
            </header>
            <section class="card">
                <h2>Log In</h2>
                <form action="/login" method="post">
                    <div class="form-group">
                        <label for="email">EMAIL ADDRESS</label>
                        <input type="email" id="email" name="email" placeholder="you@example.com" required />
                    </div>
                    <div class="form-group">
                        <label for="password">PASSWORD</label>
                        <input type="password" id="password" name="password" placeholder="Enter your password" required />
                    </div>
                    <div class="checkbox-row">
                        <input type="checkbox" id="remember_me" name="remember_me" value="yes" />
                        <label for="remember_me">Keep me logged in</label>
                    </div>
                    <button type="submit">Log In</button>
                </form>
                <p style="margin-top: 1rem; color: var(--text-muted);">
                    Don’t have an account? <a href="/signup" style="color: var(--accent-color);">Sign Up</a>
                </p>
            </section>
            <footer>
                <p>&copy; 2025 AI Stem Remover. All rights reserved.</p>
            </footer>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return HTMLResponse("<h3>Invalid credentials. <a href='/login'>Try again</a>.</h3>", status_code=400)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

# ────────────────────────────────────────────────────────────────────────────────
# Current user dependency
# ────────────────────────────────────────────────────────────────────────────────
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user

# ────────────────────────────────────────────────────────────────────────────────
# Homepage & isolate endpoints
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_homepage(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login")
    with open("public/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), media_type="text/html")

@app.post("/isolate")
async def isolate_endpoint(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
    stem: str = Form(...)
):
    try:
        unique_id = uuid.uuid4().hex[:8]
        upload_filename = f"{unique_id}_{file.filename}"
        upload_path = os.path.join("temp_uploads", upload_filename)

        with open(upload_path, "wb") as out_f:
            out_f.write(await file.read())

        result = isolate_stem(upload_path, demucs_model, stem)

        base_name = os.path.splitext(upload_filename)[0]
        download_filename = f"{base_name} ({stem} isolated).wav"
        encoded_filename = urllib.parse.quote(download_filename)

        return StreamingResponse(
            result["output_buffer"],
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{download_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
    except Exception as e:
        print("❌ Exception during /isolate:")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "An error occurred during audio processing.", "details": str(e)}
        )
