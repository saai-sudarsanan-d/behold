FROM python:3.8-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=5000
EXPOSE $PORT
CMD ["python", "app.py"]
