#!/usr/bin/env bash
# Records every video named in video/queue.txt into out/video/<name>/ (voice, recording, cards, final video.mp4).
# The demo page must already be running on port 8601. One video failing does not stop the others.
set -uo pipefail
failed=""
for slug in $(grep -v '^#' video/queue.txt | grep -v '^\s*$'); do
  dir="out/video/$slug"
  mkdir -p "$dir/voice"
  ln -sfn "$(pwd)/out/video/voice_model" "$dir/voice_model"
  export SCRIPT="video/series/$slug.json"
  echo "::group::$slug"
  if python video/narrate.py "$dir" \
     && node video/record.js http://127.0.0.1:8601/ "$dir" \
     && python video/cards.py "$dir" \
     && python video/build.py "$dir"; then
    echo "$slug: done"
  else
    echo "::warning::$slug failed"; failed="$failed $slug"
  fi
  rm -rf "$dir/raw" "$dir/raw.webm" "$dir/voice" "$dir/voice_model" "$dir"/_*.mp4 "$dir"/intro.mp4 "$dir"/outro.mp4 "$dir"/main.mp4
  echo "::endgroup::"
done
echo "Failed:${failed:- none}" | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
