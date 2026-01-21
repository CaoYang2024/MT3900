# Base image
FROM python:3.9-slim

# Working directory
WORKDIR /app

# Install system dependencies
# 🔴 FIX: libgl1-mesa-glx is deprecated, use libgl1 instead
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the driver script
COPY camera_driver.py .

# Run the script
CMD ["python", "-u", "camera_driver.py"]