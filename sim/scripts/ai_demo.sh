#!/usr/bin/env bash
# One full AI pass on a fresh world: build, incident day, learn from promo days, markdown trial, find incidents, score.
# usage: scripts/ai_demo.sh <run-name> on|off [hard-floor] [soft-floor]     (needs PESOWEB_ROOT_PASSWORD, app on :5071)
set -e
run=$1; agent=${2:-on}; hard=${3:-0}; soft=${4:-5}
cd "$(dirname "$0")/.."
python -m simpeso.runner build --seed 21 --profile smoke --run "$run" --policy autonomous --hard-floor "$hard" --soft-floor "$soft" > /dev/null
python -m simpeso.runner day --run "$run" --day 0 > /dev/null
python -m simpeso.ai_hook history --run "$run" > /dev/null
python -m simpeso.ai_hook trial --run "$run" --agent "$agent"
python -m simpeso.ai_hook find --run "$run" --k 4 > /dev/null
python -m simpeso.runner score --run "$run"
