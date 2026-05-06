# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm config set strict-ssl false && npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.10
WORKDIR /app

# Install Python requirements (long timeout for large packages)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Overwrite full opencv-python with headless variant (no libGL needed)
RUN pip install --no-cache-dir --force-reinstall --no-deps --trusted-host pypi.org --trusted-host files.pythonhosted.org opencv-python-headless

# Copy all source code
COPY . .

# Copy built frontend into Flask static folder
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Start Flask
EXPOSE 5000
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
