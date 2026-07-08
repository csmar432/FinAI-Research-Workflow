#!/usr/bin/env bash
# Per-file pytest runner v2
# Usage:
#   bash scripts/run_tests_per_file2.sh --start 1 --end 100   # run files 1..100
#   bash scripts/run_tests_per_file2.sh --start 1               # run from file 1 to end
#   bash scripts/run_tests_per_file2.sh --only a.py,b.py       # run specific files (basename match)
#   bash scripts/run_tests_per_file2.sh --status               # show summary without running
#
# Output:
#   /tmp/perfile2-logs/<basename>.log       # per-file pytest log
#   /tmp/perfile2-summary.txt               # aggregated PASS/FAIL summary
#
# Each line in summary: STATUS DURATION_SEC PATH
# STATUS ∈ {PASS, FAIL(<exitcode>), TIMEOUT, ERROR}

set -u

START=""
END=""
ONLY=""
STATUS_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START="${2:-}"; shift 2 ;;
    --end)   END="${2:-}";   shift 2 ;;
    --only)  ONLY="${2:-}";  shift 2 ;;
    --status) STATUS_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

LOG_DIR=/tmp/perfile2-logs
SUMMARY=/tmp/perfile2-summary.txt
mkdir -p "$LOG_DIR"

# Print summary if asked
if [[ "$STATUS_ONLY" == "1" ]]; then
  if [[ -f "$SUMMARY" ]]; then
    cat "$SUMMARY"
  else
    echo "(no summary yet)" >&2
    exit 1
  fi
  exit 0
fi

# Reset summary
: > "$SUMMARY"

# Build the list of files to run
# Use a portable approach (macOS bash 3.x doesn't have mapfile in some envs)
ALL_FILES_FILE=$(mktemp)
ls -1 tests/test_*.py | sort > "$ALL_FILES_FILE" 2>/dev/null
if [[ ! -s "$ALL_FILES_FILE" ]]; then
  rm -f "$ALL_FILES_FILE"
  echo "Could not find tests/test_*.py in $(pwd)" >&2
  exit 1
fi

SEL_FILE=$(mktemp)
: > "$SEL_FILE"

# If --only, filter by basenames
if [[ -n "$ONLY" ]]; then
  IFS=',' read -ra ONLY_LIST <<< "$ONLY"
  while IFS= read -r f; do
    base=$(basename "$f")
    for o in "${ONLY_LIST[@]}"; do
      o_trim=$(echo "$o" | xargs)
      if [[ "$base" == "$o_trim" || "$base" == "${o_trim}.py" ]]; then
        echo "$f" >> "$SEL_FILE"
        break
      fi
    done
  done < "$ALL_FILES_FILE"
else
  # Slice by 1-based index from ALL_FILES_FILE
  if [[ -z "$START" ]]; then START=1; fi
  total=$(wc -l < "$ALL_FILES_FILE" | tr -d ' ')
  if [[ -z "$END" ]] || [[ "$END" -gt "$total" ]]; then END=$total; fi
  awk -v s="$START" -v e="$END" 'NR>=s && NR<=e {print}' "$ALL_FILES_FILE" > "$SEL_FILE"
fi

if [[ ! -s "$SEL_FILE" ]]; then
  rm -f "$ALL_FILES_FILE" "$SEL_FILE"
  echo "No test files selected" >&2
  exit 1
fi

# Load selection into array
FILES=()
while IFS= read -r f; do
  FILES+=("$f")
done < "$SEL_FILE"
rm -f "$ALL_FILES_FILE" "$SEL_FILE"

echo "[perfile2] running ${#FILES[@]} files (start=$START end=$END) at $(date +%H:%M:%S)"

# Common pytest args — match the original suite ignore list
PYTEST_ARGS=(
  -q --no-header
  -p no:cacheprovider
  --tb=line
  --timeout=30
  -x
)

run_one() {
  local f="$1"
  local base
  base=$(basename "$f" .py)
  local log="$LOG_DIR/${base}.log"
  local start end dur rc status

  start=$(date +%s)
  timeout 90 python -m pytest "$f" "${PYTEST_ARGS[@]}" > "$log" 2>&1
  rc=$?
  end=$(date +%s)
  dur=$((end - start))

  if [[ $rc -eq 0 ]]; then
    if grep -qE " [0-9]+ failed" "$log" 2>/dev/null; then
      status="FAIL($rc)"
    else
      status="PASS"
    fi
  elif [[ $rc -eq 124 ]]; then
    status="TIMEOUT"
  else
    status="FAIL($rc)"
  fi

  printf '%-10s %4ds  %s\n' "$status" "$dur" "$f" >> "$SUMMARY"
  printf '[perfile2] %-10s %4ds  %s\n' "$status" "$dur" "$f"
}

for f in "${FILES[@]}"; do
  run_one "$f"
done

echo "DONE" >> "$SUMMARY"
echo "[perfile2] done at $(date +%H:%M:%S). summary: $SUMMARY"
