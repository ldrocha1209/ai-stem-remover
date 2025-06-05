# AI Stem Remover

A web-based FastAPI application that uses Demucs to isolate audio stems (vocals, drums, bass, etc.) from uploaded tracks. Users can sign up, log in, and process audio through a simple UI. Deployed on Render.com with a PostgreSQL backend for persistent user storage.

---

## Table of Contents

1. [Features](#features)  
2. [Demo](#demo)  
3. [Tech Stack](#tech-stack)  
4. [Requirements](#requirements)  

---

## Features

- **User Authentication**  
  - Sign up with email/password (hashed via `passlib[bcrypt]`)  
  - Log in, “keep me logged in” option, and logout  
  - Stores users in PostgreSQL (`users` table)  

- **Audio Stem Isolation**  
  - Upload an audio file (MP3, WAV, FLAC, AIFF, M4A; max 100 MB)  
  - Choose one stem from {`vocals`, `drums`, `bass`, `other`}  
  - Demucs (htdemucs model) processes the file and returns a WAV of the isolated stem  

- **Persistent Backend**  
  - PostgreSQL on Render (persistent across deploys/restarts)  
  - Automatic table creation via SQLAlchemy on startup  

- **UI/UX**  
  - Dark‐themed, responsive HTML/CSS/JS front end under `public/`  
  - Upload form, loader animation, preview + download link for processed stem  
  - Sign-up and login pages styled consistently with the main tool  

- **Security & Data**  
  - Sessions signed with `itsdangerous` and stored in secure cookies  
  - File‐size limit enforced at 100 MB (via custom middleware)  
  - Email validation with `email-validator`  
  - SQLAlchemy ORM prevents SQL injection  
  - Optional nightly backups for `users.db` (if SQLite), but default is PostgreSQL for persistence  

---

## Demo

Once deployed (for example, at `https://ai-stem-remover.onrender.com`):

1. Visit **/signup** to create an account.  
2. After login, you land on the **stem-removal UI**.  
3. Upload a track, select “Vocals” (or “Drums”, “Bass”, “Other”), then click **Isolate Stem**.  
4. After processing, preview and download the isolated WAV file.  
5. Click **Log Out** in the top right to end your session.

---

## Tech Stack

- **Backend**  
  - [FastAPI](https://fastapi.tiangolo.com/) (API framework)  
  - [Uvicorn](https://www.uvicorn.org/) (ASGI server)  
  - [SQLAlchemy](https://www.sqlalchemy.org/) (ORM)  
  - [Pydantic](https://pydantic-docs.helpmanual.io/) (data validation)  
  - [Passlib](https://passlib.readthedocs.io/) + Bcrypt (password hashing)  
  - [Email‐validator](https://pypi.org/project/email-validator/) (validates email formats)  
  - [Starlette SessionMiddleware](https://www.starlette.io/middleware/) + [itsdangerous](https://pypi.org/project/itsdangerous/) (signed cookies)  
  - [Demucs](https://github.com/facebookresearch/demucs) (AI stem‐separation model)  
  - [Torch](https://pytorch.org/) + [torchaudio](https://pytorch.org/audio/) + [numpy](https://numpy.org/) + [soundfile](https://soundfile.readthedocs.io/) (audio I/O & processing)  
  - [PostgreSQL](https://www.postgresql.org/) (persistent user database, managed by Render)  

- **Frontend**  
  - Plain HTML, CSS, and vanilla JavaScript (in `public/`)  
  - Responsive, dark‐themed UI with loader animation, form validation, and download links  

- **Hosting & Deployment**  
  - [Render](https://render.com/) (2 GB RAM instance for Demucs)  
  - Render’s managed PostgreSQL add-on (persistent user storage)  
  - Automatic HTTPS with Let’s Encrypt  

---

## Requirements

Specify these in `requirements.txt`. Any missing dependencies cause build-time errors:

```txt
fastapi==0.115.12
uvicorn==0.34.3
sqlalchemy==2.0.41
pydantic==2.11.5
python-multipart==0.0.20
email-validator==2.2.0
passlib[bcrypt]==1.7.4

# Demucs + audio stack
demucs==4.0.1
torch==2.2.2
torchaudio==2.2.2
soundfile==0.13.1
numpy==1.24.4

itsdangerous==2.2.0      # for SessionMiddleware
psycopg2-binary==2.9.9   # for PostgreSQL support
