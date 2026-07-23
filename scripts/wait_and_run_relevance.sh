#!/bin/bash
set -e
cd /Users/vaish/Documents/ClaudeCode/Blinkit_ReviewDiscoveryEngine
source .venv/bin/activate
source .env

echo "waiting for Gemini free-tier daily quota to reset..."
while true; do
  status=$(curl -s -o /tmp/quota_check.json -w "%{http_code}" \
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=${GEMINI_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"contents":[{"parts":[{"text":"ping"}]}],"generationConfig":{"responseMimeType":"application/json"},"systemInstruction":{"parts":[{"text":"reply {\"ok\":true}"}]}}')
  echo "$(date): quota check status=$status"
  if [ "$status" = "200" ]; then
    echo "quota available — starting relevance gate"
    break
  fi
  sleep 900
done

python3 -W ignore -m src.relevance --config config.yaml --workers 4
