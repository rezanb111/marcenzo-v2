#!/bin/bash
# Reconstruct full project from base64 bundle parts
set -e
cd "$(dirname "$0")"
if [ ! -f bundle/part_0.b64 ]; then
  echo "bundle parts missing"
  exit 1
fi
cat bundle/part_*.b64 | base64 -d > /tmp/marcenzo-full.zip
unzip -o /tmp/marcenzo-full.zip -d /tmp/marcenzo-extract
if [ -d /tmp/marcenzo-extract/marcenzo-loan-bot ]; then
  cp -a /tmp/marcenzo-extract/marcenzo-loan-bot/. .
  echo "✅ Full project reconstructed into current directory."
else
  echo "Unexpected zip structure"
  ls -la /tmp/marcenzo-extract
  exit 1
fi
echo "Next: cp .env.SERVER_TEMPLATE .env && nano .env && chmod +x deploy.sh && ./deploy.sh"
