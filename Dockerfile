# Use official slim Python image for minimal footprint
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install required Python packages
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Expose the port that the application will run on
EXPOSE 8080

# Default command: launch the FastAPI app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]