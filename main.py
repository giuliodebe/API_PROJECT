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
from pathlib import Path
import win32com.client
import fnmatch
import shutil
from datetime import datetime

# Define path configurations at the top of the file
NETWORK_SHARE = r"\\DESKTOP-1K6DB5A\coherix"  # For images and scan data
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))  # For index.html and local static files
IMAGES_DIR = os.path.join(LOCAL_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)  # Create images directory if it doesn't exist

# Add these debug statements right after your imports and before the FastAPI app initialization
print("\n=== Starting Application ===")
print(f"Current working directory: {os.getcwd()}")
print(f"Attempting to access network share at: {NETWORK_SHARE}")

# Test network share access
try:
    if os.path.exists(NETWORK_SHARE):
        print(f"✅ Successfully accessed network share")
        print("\nListing directory contents:")
        try:
            files = os.listdir(NETWORK_SHARE)
            print(f"Found {len(files)} files/directories")
            print("\nFirst 10 items in directory:")
            for file in files[:10]:
                print(f"- {file}")
        except Exception as e:
            print(f"❌ Error listing directory contents: {str(e)}")
    else:
        print(f"❌ Cannot access network share")
except Exception as e:
    print(f"❌ Error checking network share: {str(e)}")

print("\n=== Network Share Test Complete ===\n")

# Continue with your existing FastAPI app initialization
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

# Add this function at the top of your file
def resolve_shortcut_path(shortcut_path):
    """Resolve the actual path from a Windows shortcut (.lnk) file"""
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        return shortcut.Targetpath
    except Exception as e:
        print(f"Error resolving shortcut: {e}")
        return None

# Update with your actual shortcut path
SHORTCUT_PATH = r"C:\Users\g.debenedetti\Desktop\coherix (DESKTOP-1K6DB5A).lnk"  # Replace this with your actual shortcut path
NETWORK_SHARE_PATH = resolve_shortcut_path(SHORTCUT_PATH) or r"\\DESKTOP-1K6DB5A\coherix"

# Add debug logging
print(f"Network share path resolved to: {NETWORK_SHARE_PATH}")

def sync_images_from_network():
    """Synchronize images from network share to local images directory"""
    try:
        print("\n=== Starting Image Sync ===")
        if not os.path.exists(NETWORK_SHARE):
            print("❌ Network share not accessible")
            return False
            
        # Get list of scan files from network share
        network_files = [f for f in os.listdir(NETWORK_SHARE) 
                        if f.startswith("FrameResults-OP20-PERCORSO_") and f.endswith(".jpg")]
        
        # Get list of existing local files
        local_files = os.listdir(IMAGES_DIR) if os.path.exists(IMAGES_DIR) else []
        
        # Copy new files
        new_files = []
        for file in network_files:
            network_path = os.path.join(NETWORK_SHARE, file)
            local_path = os.path.join(IMAGES_DIR, file)
            
            if file not in local_files:
                print(f"Copying new file: {file}")
                shutil.copy2(network_path, local_path)
                new_files.append(file)
        
        print(f"✅ Sync complete. Copied {len(new_files)} new files")
        return True
        
    except Exception as e:
        print(f"❌ Error during sync: {str(e)}")
        return False

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(LOCAL_DIR, "index.html")
    try:
        with open(index_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Index file not found")

@app.get("/api/scans", response_model=List[ScanData])
async def get_scans():
    """Get all available scans"""
    try:
        # Sync images from network share
        sync_success = sync_images_from_network()
        if not sync_success:
            print("Warning: Image sync failed, using existing local images")
        
        # Use local images directory
        print(f"\nSearching for scans in: {IMAGES_DIR}")
        
        if not os.path.exists(IMAGES_DIR):
            print("❌ Local images directory not found")
            raise HTTPException(status_code=500, detail="Images directory not accessible")
        
        # Get files from local directory
        files = os.listdir(IMAGES_DIR)
        found_files = [f for f in files if f.startswith("FrameResults-OP20-PERCORSO_") and f.endswith(".jpg")]
        
        print(f"Found {len(found_files)} matching files")
        
        scans = []
        for filename in found_files:
            try:
                parts = filename.split("-")
                percorso_str = parts[2].replace("PERCORSO_", "")
                scan_str = parts[3].replace("Scan", "").split(".")[0]
                
                scan_data = ScanData(
                    percorsoNumber=int(percorso_str),
                    scanNumber=int(scan_str),
                    imagePath=f"/api/image/{filename}"
                )
                scans.append(scan_data)
                
            except Exception as e:
                print(f"❌ Error processing {filename}: {str(e)}")
                continue

        return sorted(scans, key=lambda x: (x.percorsoNumber, x.scanNumber))

    except Exception as e:
        print(f"❌ Error in get_scans: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/image/{image_name}")
async def get_image(image_name: str):
    """Serve image from local images directory"""
    try:
        image_path = os.path.join(IMAGES_DIR, image_name)
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at: {image_path}")
        
        # Open and process the image with PIL
        img = Image.open(image_path)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGB')
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        return StreamingResponse(
            img_byte_arr, 
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"}
        )
    
    except Exception as e:
        print(f"Error serving image: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Image not found: {str(e)}")

@app.get("/api/background")
async def get_background():
    """Serve background image"""
    try:
        # Look for background image in the local directory first
        background_path = os.path.join(LOCAL_DIR, "SPALMATURA.png")
        print(f"Looking for background image at: {background_path}")
        
        if not os.path.exists(background_path):
            print(f"❌ Background image not found at: {background_path}")
            raise FileNotFoundError("Background image not found")
            
        print(f"✅ Found background image")
        
        # Open and serve the image
        img = Image.open(background_path)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return StreamingResponse(
            img_byte_arr, 
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"}
        )
            
    except Exception as e:
        print(f"Error serving background image: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Background image not found: {str(e)}")

@app.post("/merge_images")
async def merge_images():
    # Get list of all images in static/scans directory
    scan_dir = "static/scans"
    image_files = sorted([f for f in os.listdir(scan_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
    
    if not image_files:
        return {"error": "No images found"}
    
    # Open first image to get dimensions
    images = [Image.open(os.path.join(scan_dir, img)) for img in image_files]
    
    # Calculate total height and max width
    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)
    
    # Create new image with combined dimensions
    merged_image = Image.new('RGB', (max_width, total_height))
    
    # Paste images
    y_offset = 0
    for img in images:
        merged_image.paste(img, (0, y_offset))
        y_offset += img.height
        img.close()
    
    # Save merged image
    output_path = "static/merged_scan.png"
    merged_image.save(output_path)
    
    return {"merged_image_path": "/static/merged_scan.png"}

@app.get("/api/check-image/{percorso}/{scan_num}")
async def check_image_exists(percorso: int, scan_num: int):
    """Check if an image exists for the given percorso and scan number"""
    try:
        # Pad the scan number to 8 digits
        padded_number = str(scan_num).zfill(8)
        filename = f"FrameResults-OP20-PERCORSO_{percorso}-Scan{padded_number}.jpg"
        
        # Use the network share path
        image_path = os.path.join(NETWORK_SHARE, filename)
        
        exists = os.path.exists(image_path)
        
        return {
            "exists": exists,
            "src": f"/api/image/{filename}" if exists else None
        }
    except Exception as e:
        print(f"Error checking image existence: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking image existence: {str(e)}"
        )

@app.get("/api/highest-scan/{percorso}")
async def find_highest_scan(percorso: int):
    """Find the highest scan number for a given percorso using binary search"""
    print(f'Searching for highest scan number in PERCORSO_{percorso}')
    
    async def check_scan_exists(scan_num: int) -> bool:
        padded_number = str(scan_num).zfill(8)
        filename = f"FrameResults-OP20-PERCORSO_{percorso}-Scan{padded_number}.jpg"
        return os.path.exists(os.path.join(NETWORK_SHARE, filename))  # Use NETWORK_SHARE path

    highest_scan = None
    last_found = -1
    step = 10  # Start with larger steps
    
    while step >= 1:
        print(f"Searching with step size: {step}")
        found = False
        
        # Search in current step size
        for scan_num in range(0, 101, step):
            if await check_scan_exists(scan_num):
                last_found = scan_num
                found = True
            elif last_found != -1:
                break
        
        if found:
            # Search precisely around the last found scan
            for scan_num in range(last_found + step - 1, last_found - 1, -1):
                if await check_scan_exists(scan_num):
                    padded_number = str(scan_num).zfill(8)
                    filename = f"FrameResults-OP20-PERCORSO_{percorso}-Scan{padded_number}.jpg"
                    return {
                        "scanNum": scan_num,
                        "src": f"/api/image/{filename}"
                    }
        
        # If nothing found, reduce step size and try again
        step = step // 2
    
    print(f'No scans found for PERCORSO_{percorso}')
    return {"scanNum": None, "src": None}

@app.get("/api/test-network-share")
async def test_network_share():
    """Test network share accessibility"""
    try:
        # Test basic access
        if not os.path.exists(NETWORK_SHARE):
            return {
                "status": "error",
                "message": "Cannot access network share",
                "path": NETWORK_SHARE
            }
            
        # Try to list directory contents
        try:
            files = os.listdir(NETWORK_SHARE)
            return {
                "status": "success",
                "path": NETWORK_SHARE,
                "accessible": True,
                "file_count": len(files),
                "sample_files": files[:5],  # First 5 files for verification
                "current_working_directory": os.getcwd()
            }
        except PermissionError:
            return {
                "status": "error",
                "message": "Permission denied when trying to list directory",
                "path": NETWORK_SHARE
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error listing directory: {str(e)}",
                "path": NETWORK_SHARE
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "path": NETWORK_SHARE
        }

def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run_server() 