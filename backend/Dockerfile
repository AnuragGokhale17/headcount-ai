# Stage 1: Build the React frontend
# Use the full node image which has build tools pre-installed
FROM node:20 AS frontend-builder
WORKDIR /build

# Set environment to development
ENV NODE_ENV=development

COPY frontend/package*.json ./

# High resilience npm install using HTTP registry to bypass some TLS/SSL filters
RUN npm config set strict-ssl false && \
    npm config set registry http://registry.npmjs.org/ && \
    npm install --include=dev

COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
# Use full python image (not slim) to avoid apt-get install for common build tools
FROM python:3.10
WORKDIR /app

# Ensure pip is up to date and set high resilience
RUN pip install --upgrade pip

# Install Python requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Overwrite with headless variant (this also has fewer dependencies)
RUN pip install --no-cache-dir --force-reinstall --no-deps \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
    opencv-python-headless

RUN pip install --no-cache-dir numpy<2.0 \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org


# Copy all source code
COPY . .

# Copy built frontend into Flask static folder
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Start Flask
EXPOSE 5000
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
