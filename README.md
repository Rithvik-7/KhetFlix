# KhetFlix

KhetFlix is a Flask-based agricultural assistant for Indian farmers. It provides AI-powered crop guidance, voice chat, progressive feedback, video-frame analysis, government-scheme discovery, and an interactive India farm map.

## Features

- Text and voice farming assistant powered by OpenAI
- Crop and video-frame analysis
- Progressive farming feedback and downloadable PDF reports
- Government scheme finder
- India farm map and agricultural data endpoints

## Tech stack

- Python and Flask
- OpenAI API
- HTML, CSS, and JavaScript templates
- ReportLab for PDF generation

## Run locally

1. Install Python 3.10 or newer.
2. Clone the repository and enter the project directory.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Create a `.env` file in the project root:

   ```env
   OPENAI_API_KEY=your_openai_api_key
   ```

6. Start the development server:

   ```bash
   python app.py
   ```

7. Visit `http://localhost:5000`.

## Deploy to Render

This repository includes `render.yaml`, so it can be deployed as a Render Blueprint.

1. Push this repository to GitHub.
2. In Render, select **New +** → **Blueprint** and connect the repository.
3. Render detects `render.yaml` and creates the `khetflix` web service.
4. Add the `OPENAI_API_KEY` environment variable in the Render service settings.
5. Deploy. Render will build with `pip install -r requirements.txt` and start with `gunicorn app:app`.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Enables the OpenAI-powered assistant and analysis features. |

## Security

Never commit `.env` or an API key. The supplied `.gitignore` excludes both local secrets and generated files.

