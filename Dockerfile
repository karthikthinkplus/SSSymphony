# Multi-stage build for frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# Final runtime image combining Python and Node.js
FROM python:3.11-slim

# Install Node.js, libpq-dev, and gcc (needed for psycopg2)
RUN apt-get update && apt-get install -y curl gnupg libpq-dev gcc \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend app
COPY backend/ ./backend/

# Copy built frontend standalone files
COPY --from=frontend-builder /app/.next/standalone ./frontend/
COPY --from=frontend-builder /app/.next/static ./frontend/.next/static

# Create startup script to launch both services
RUN echo '#!/bin/sh\n\
# Start backend in the background\n\
cd /app/backend\n\
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 &\n\
\n\
# Start frontend in the foreground\n\
cd /app/frontend\n\
PORT=3000 node server.js\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8080 3000

CMD ["/app/entrypoint.sh"]
