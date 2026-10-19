FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8001
CMD ["python","-m","uvicorn","career_pilot.web:create_web_app","--factory","--host","0.0.0.0","--port","8001"]
