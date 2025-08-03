import os
import uuid
import json
import requests
import time
from typing import Dict, Any
from io import BytesIO

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from PIL import Image

from app.models import CropBox, ImageResponse

app = FastAPI(title="Product Image Processor")

os.makedirs("/app/processed_images")


def process_image_in_background(image_id: str, image_data: bytes, product_data: dict):
    """A background task to process the smart crop."""

    print(f"Starting background processing for image {image_id}")
    ai_response = requests.post(
        "http://127.0.0.1:8000/mock-ai/find-main-object",
        files={"image_file": ("image.jpg", image_data, "image/jpeg")},
        timeout=10
    )
    ai_response.raise_for_status()
    crop_box_data = ai_response.json()["bounding_box"]
    crop_box = CropBox(**crop_box_data)

    image = Image.open(BytesIO(image_data))
    cropped_image = image.crop((
        crop_box.x,
        crop_box.y,
        crop_box.x + crop_box.width,
        crop_box.y + crop_box.height
    ))

    output_path = f"/app/processed_images/{image_id}.jpg"
    cropped_image.save(output_path, "JPEG")
    print(f"Successfully processed and saved image {image_id} to {output_path}")



@app.post("/images/manual-crop")
async def manual_crop(
    source_image: UploadFile = File(...),
    product_info: str = Form(...),
    crop_box: str = Form(...)
):
    product_data = json.loads(product_info)
    crop_data = json.loads(crop_box)

    x = crop_data["x"]
    y = crop_data["y"]
    width = crop_data["width"]
    height = crop_data["height"]

    image_data = await source_image.read()
    image = Image.open(BytesIO(image_data))
    cropped_image = image.crop((x, y, x + width, y + height))

    image_id = str(uuid.uuid4())
    output_path = f"/app/processed_images/{image_id}.jpg"
    cropped_image.save(output_path, "JPEG")

    # TODO: Return a proper JSONResponse as per the spec.


@app.post("/images/smart-crop")
async def smart_crop(
    request: Request,
    background_tasks: BackgroundTasks,
    source_image: UploadFile = File(...),
    product_info: str = Form(...)
):

    product_data = json.loads(product_info)
    image_data = await source_image.read()
    image_id = str(uuid.uuid4())

    background_tasks.add_task(process_image_in_background, image_id, image_data, product_data)

    # TODO: Return a JSONResponse with status 202 as per the spec.


@app.get("/images/{image_path:path}")
async def get_image(image_path: str):
    full_image_path = f"/app/processed_images/{image_path}"

    with open(full_image_path, "r") as f:
        return Response(content=f.read(), media_type="image/jpeg")


# Mock AI endpoint for smart-crop to call
@app.post("/mock-ai/find-main-object")
async def mock_ai_endpoint(image_file: UploadFile = File(...)):
    # Simulate a slow, blocking process
    time.sleep(2)
    _ = image_file.read()
    return {
        "bounding_box": { "x": 50, "y": 50, "width": 150, "height": 150 }
    }
