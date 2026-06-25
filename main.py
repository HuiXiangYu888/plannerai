import gradio as gr
from fastapi import FastAPI
from app.gradio_app import build_demo

app = FastAPI(title="PlannerAI", version="0.1.0")

@app.get("/api")
async def root():
    return {"message": "PlannerAI API is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

app = gr.mount_gradio_app(app, build_demo(), path="/")
