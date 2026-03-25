FROM node:22-alpine

WORKDIR /app

# Install production deps first (layer cache)
COPY package*.json ./
RUN npm ci --omit=dev

# Copy source
COPY *.mjs ./

# State dir (mount a volume here for persistence)
RUN mkdir -p /data
ENV STATE_DIR=/data

EXPOSE 7340

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD node -e "const http = require('http'); \
    http.get('http://localhost:7340/health', r => { \
      process.exit(r.statusCode === 200 ? 0 : 1); \
    }).on('error', () => process.exit(1));"

CMD ["node", "server.mjs"]
