from fastapi import FastAPI
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Unique instance ID (replace X with the actual instance number)
INSTANCE_ID = "Instance number 4"

counter = {
    "cluster1": 0,
    "cluster2": 0,
}

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI application!"}

@app.get("/cluster1")
async def cluster1_root():
    global counter  
    counter["cluster1"] += 1  
    message = f"{INSTANCE_ID} (Cluster 1) has received request number {counter['cluster1']}"
    logger.info(message)
    return {"message": message}

@app.get("/cluster2")
async def cluster2_root():
    global counter  
    counter["cluster2"] += 1  
    message = f"{INSTANCE_ID} (Cluster 2) has received request number {counter['cluster2']}"
    logger.info(message)
    return {"message": message}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
