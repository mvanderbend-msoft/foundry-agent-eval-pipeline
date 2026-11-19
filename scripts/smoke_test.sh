#!/usr/bin/env bash
# Smoke test after each deployment: one real question that needs a tool call.
set -euo pipefail

for attempt in 1 2 3; do
  if out="$(azd ai agent invoke order-agent "Where is my order CP-1001?" --no-prompt 2>&1)"; then
    echo "$out" | tail -n 4
    if echo "$out" | grep -qi "out for delivery"; then
      echo "Smoke test passed."
      exit 0
    fi
  fi
  echo "Attempt $attempt did not return the expected answer, retrying..."
  sleep 20
done

echo "Smoke test failed." >&2
exit 1
