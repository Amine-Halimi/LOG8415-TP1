from fastapi import FastAPI
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Unique instance ID (replace X with the actual instance number)
INSTANCE_ID = "Instance number X"

counter = 0

@app.get("/")
async def root():
    global counter  
    counter += 1  
    message = f"{INSTANCE_ID} has received request number {counter}"
    logger.info(message)
    return {"message": message}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
