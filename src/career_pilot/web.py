"""Mount the Gradio interface and career API in the same local process."""

from functools import lru_cache

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from career_pilot.api import app
from career_pilot.ui import build_ui


@lru_cache(maxsize=1)
def create_web_app() -> FastAPI:
    """Share uploaded knowledge between the browser UI and REST endpoints."""

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/ui/")

    return gr.mount_gradio_app(app, build_ui(), path="/ui")
