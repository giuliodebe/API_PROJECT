from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from PIL import Image
import io
import os
import glob
from typing import List
from pydantic import BaseModel

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for other static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class ScanData(BaseModel):
    percorsoNumber: int
    scanNumber: int
    imagePath: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/scans", response_model=List[ScanData])
async def get_scans():
    """Get all available scans"""
    scans = []
    pattern = "images/FrameResults-OP20-PERCORSO_*-Scan*.jpg"
    
    # Print current working directory and pattern
    print(f"Current working directory: {os.getcwd()}")
    print(f"Looking for files with pattern: {pattern}")
    
    # List all files found
    found_files = glob.glob(pattern)
    print(f"Found files: {found_files}")
    
    if not found_files:
        # Try with absolute path
        abs_pattern = os.path.join(os.getcwd(), pattern)
        found_files = glob.glob(abs_pattern)
        print(f"Found files with absolute path: {found_files}")
    
    for file_path in found_files:
        try:
            filename = os.path.basename(file_path)
            print(f"Processing file: {filename}")
            
            percorso_str = filename.split("PERCORSO_")[1].split("-")[0]
            scan_str = filename.split("Scan")[1].split(".")[0]
            
            # Create URL path for the image
            image_url = f"/api/image/{filename}"
            
            scans.append(ScanData(
                percorsoNumber=int(percorso_str),
                scanNumber=int(scan_str),
                imagePath=image_url
            ))
            print(f"Successfully processed {filename}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            continue
    
    print(f"Total scans found: {len(scans)}")
    return sorted(scans, key=lambda x: (x.percorsoNumber, x.scanNumber))

@app.get("/api/image/{image_name}")
async def get_image(image_name: str):
    """Serve image using PIL"""
    try:
        # Construct the full path
        image_path = os.path.join("images", image_name)
        
        # Open and process the image with PIL
        img = Image.open(image_path)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        return StreamingResponse(img_byte_arr, media_type="image/jpeg")
    
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")

@app.get("/api/background")
async def get_background():
    """Serve background image"""
    try:
        img = Image.open("static/SPALMATURA.jpg")
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        return StreamingResponse(img_byte_arr, media_type="image/jpeg")
    
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Background image not found: {str(e)}")

def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server() 