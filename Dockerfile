# Build the web UI, then bake it into the API image.
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY bench ./bench
COPY evals ./evals
COPY agents ./agents
RUN pip install --no-cache-dir -e .
COPY --from=web /web/dist ./web/dist
EXPOSE 8000
CMD ["bench", "serve", "--port", "8000"]
