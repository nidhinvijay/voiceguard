# VoiceGuard: Real-Time AI-Powered Call Monitoring

VoiceGuard is a real-time, AI-powered application designed to monitor phone calls, transcribe them, and analyze them for toxic content. It provides a dashboard to view call history, playback recordings, and manage contacts.

## Features

*   **Real-time Call Transcription:** Transcribes phone calls in real-time using Google Cloud Speech-to-Text.
*   **Toxicity Analysis:** Analyzes transcriptions for toxic content using the Groq API.
*   **Call History:** View a history of all calls made through the application.
*   **Call Playback:** Listen to recordings of past calls.
*   **Contact Management:** Add, and view contacts.
*   **Web-Based Interface:** A user-friendly web interface for making calls and viewing call data.

## Technology Stack

*   **Backend:**
    *   Python / Django
    *   Django Channels for WebSocket communication
    *   Gunicorn and Uvicorn for serving the application
    *   Redis for the Channels layer
*   **Frontend:**
    *   HTML / CSS / JavaScript
    *   Twilio Voice SDK for in-browser calling
*   **Databases:**
    *   SQLite (for development)
*   **APIs & Services:**
    *   **Twilio:** For programmable voice functionalities.
    *   **Google Cloud Speech-to-Text:** For real-time speech recognition.
    *   **Groq:** For language model-based toxicity analysis.
*   **Deployment:**
    *   Docker
    *   Google Cloud Run (via `cloudbuild.yaml`)

## Project Structure

```
voiceguard/
├── core/                # Main Django app
│   ├── migrations/      # Database migrations
│   ├── templates/       # HTML templates
│   ├── admin.py         # Django admin configuration
│   ├── apps.py          # App configuration
│   ├── consumers.py     # WebSocket consumers
│   ├── forms.py         # Django forms
│   ├── models.py        # Database models
│   ├── routing.py       # WebSocket routing
│   ├── tests.py         # Tests
│   ├── urls.py          # URL routing
│   └── views.py         # Django views
├── static/              # Static files (CSS, JS)
├── voiceguard_project/  # Django project configuration
│   ├── asgi.py          # ASGI configuration
│   ├── settings.py      # Django settings
│   ├── urls.py          # Project-level URL routing
│   └── wsgi.py          # WSGI configuration
├── .dockerignore        # Docker ignore file
├── .gitignore           # Git ignore file
├── cloudbuild.yaml      # Google Cloud Build configuration
├── db.sqlite3           # SQLite database
├── Dockerfile           # Docker configuration
├── manage.py            # Django management script
├── README.md            # This file
└── requirements.txt     # Python dependencies
```

## Local Development Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd voiceguard
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the project root and add the following variables:
    ```
    DJANGO_SECRET_KEY='your-secret-key'
    DEBUG=True
    ALLOWED_HOSTS='127.0.0.1 localhost'
    CSRF_TRUSTED_ORIGINS='http://127.0.0.1:8000'
    REDIS_URL='redis://127.0.0.1:6379/0'
    # Add other required environment variables for Twilio, Google Cloud, and Groq
    ```

5.  **Run database migrations:**
    ```bash
    python manage.py migrate
    ```

6.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```
    The application will be available at `http://127.0.0.1:8000`.

## Deployment

This project is configured for deployment to Google Cloud Run using Docker.

1.  **Build the Docker image:**
    ```bash
    docker build -t gcr.io/your-gcp-project-id/voiceguard:latest .
    ```

2.  **Push the image to Google Container Registry:**
    ```bash
    docker push gcr.io/your-gcp-project-id/voiceguard:latest
    ```

3.  **Deploy to Cloud Run:**
    You can use the `gcloud` command-line tool to deploy the container image to Cloud Run.

    Alternatively, you can use the `cloudbuild.yaml` file to automate the build and deployment process with Google Cloud Build.

## How to Run

*   **Making Calls:**
    1.  Navigate to the home page.
    2.  Enter a phone number in the provided input field.
    3.  Click the "Call" button to initiate a call.
*   **Viewing Call History:**
    1.  Click on the "History" link in the navigation bar.
    2.  This will display a list of all past calls, including the contact, duration, and a link to the call details.
*   **Contact Management:**
    1.  Click on the "Directory" link in the navigation bar.
    2.  Here you can view existing contacts and add new ones.
