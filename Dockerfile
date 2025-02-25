# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only the requirements.txt first to leverage caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY Data-ingestion-threading.py .
COPY valve/ valve/

# Set environment variables (if needed, can be overridden later)
ENV DATA_PATH="/app/Data-25"

# Run the script
CMD ["python", "Data-ingestion-threading.py"]
