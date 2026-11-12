#!/bin/bash
# Generate the benchmark reports on this machine.
#
#   evaluation/local/generate_reports.sh [case ID ...]
#
# Downloads the reference files, samples the cases, and builds the reports
# of the cases named, or of every case that has no truth file yet. The
# script starts vLLM with the writing model and stops it afterwards. To use
# a server that is already running, such as a hosted provider, run the
# script with GENTREX_BENCH_BASE_URL and GENTREX_BENCH_API_KEY set, as in
# `uv run --env-file .env evaluation/local/generate_reports.sh`.
#
# VERSION names the benchmark version, v1 by default. PORT is the port of
# the vLLM that the script starts, 8000 by default.
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSION="${VERSION:-v1}"
generate=(uv run python gentrex-bench/generator/generate.py --version "$VERSION")

evaluation/download_reference_files.sh
if [ ! -d "data/gentrex-bench/$VERSION/cases" ]; then
  "${generate[@]}" sample
fi

if [ -n "${GENTREX_BENCH_BASE_URL:-}" ]; then
  exec "${generate[@]}" build "$@"
fi

port="${PORT:-8000}"
model=$(uv run python -c "
import yaml
with open('gentrex-bench/generator/settings.yaml', encoding='utf-8') as fh:
    print(yaml.safe_load(fh)['build']['model'])")
evaluation/local/serve.sh "$model" "$port" &
server=$!
trap 'kill "$server" 2> /dev/null' EXIT

echo "waiting for $model at http://localhost:$port/v1"
until curl -sf "http://localhost:$port/v1/models" > /dev/null; do
  kill -0 "$server" 2> /dev/null || { echo "vLLM stopped; see above"; exit 1; }
  sleep 5
done
GENTREX_BENCH_BASE_URL="http://localhost:$port/v1" "${generate[@]}" build "$@"
