# backend/Dockerfile

# 1. Use an official Python runtime as a parent image
FROM python:3.10-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Set the working directory in the container
WORKDIR /app

# 4. Install system dependencies if any (we don't have any for now)
# RUN apt-get update && apt-get install -y ...

# 5. Install Python dependencies
# First, copy just the requirements file to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application code into the container
COPY . /app/

# The port the container will listen on (Daphne's default)
EXPOSE 8000