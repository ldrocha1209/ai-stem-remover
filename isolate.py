#isolate.py

import os
import torch
import torchaudio
import io
from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import AudioFile
from fastapi import HTTPException
import numpy as np
import soundfile as sf  


def isolate_stem(file_path: str, model, stem: str = "vocals") -> dict:
    """
    Isolates a specific audio stem using the Demucs model and returns it as a BytesIO buffer.

    Parameters:
        file_path (str): Path to the input audio file.
        model: The pre-loaded Demucs model.
        stem (str): Which stem to isolate ('vocals', 'drums', 'bass', 'other').

    Returns:
        dict: In-memory audio buffer and metadata.
    """

    try:
        # ✅ Validate file extension
        ext = os.path.splitext(file_path)[1].lower()
        ALLOWED_EXTENSIONS = [".mp3", ".wav", ".aiff", ".flac", ".m4a"]

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"❌ Unsupported file type: {ext}")

        # ✅ Validate requested stem
        if stem not in model.sources:
            raise HTTPException(
                status_code=400,
                detail=f"❌ Invalid stem: {stem}. Choose from: {model.sources}"
            )

        # ✅ Read and convert audio into a PyTorch tensor
        wav, _ = AudioFile(file_path).read(streams=0, samplerate=model.samplerate)
        wav = torch.tensor(wav, dtype=torch.float32)

        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        if wav.shape[0] == 1:
            wav = wav.repeat(2, 1)

        mix = wav.unsqueeze(0)

        print("🔍 Processing file with Demucs...")
        sources = apply_model(model, mix, split=True, overlap=0.25)[0]

        # ✅ Extract the requested stem
        selected_stem = sources[model.sources.index(stem)].detach().cpu()

        # ✅ Ensure correct shape [channels, samples]
        if selected_stem.ndim == 3:
            selected_stem = selected_stem.squeeze(0)

        # Convert PyTorch tensor to NumPy
        np_audio = selected_stem.detach().cpu().numpy()

        # Save to buffer using soundfile
        buffer = io.BytesIO()
        sf.write(buffer, np_audio.T, samplerate=model.samplerate, format='WAV')
        buffer.seek(0)

        return {
            "status": "success",
            "output_buffer": buffer,
            "stem": stem
        }

    except Exception as e:
        print("❌ Error in isolate_stem():", e)
        raise e  # Let the caller handle this (FastAPI endpoint)

    finally:
        # ✅ Always clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🧹 Deleted uploaded file: {file_path}")


    return {
        "status": "success",
        "output_buffer": buffer,
        "stem": stem
    }
