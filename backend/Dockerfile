# backend/Dockerfile

# 1. Use an official Python runtime as a parent image
FROM python:3.10-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Set the working directory in the container
WORKDIR /app

# 4. Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code into the container
COPY . /app/

# 6. Expose the port the app runs on
EXPOSE 8000

# 7. NEW: Add the command to run the application
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "voiceguard_project.asgi:application"]