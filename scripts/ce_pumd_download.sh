#!/usr/bin/env bash
# Download and unzip BLS CE PUMD interview files (which carry the NTAXI tax
# files) for the given PUMD years into a directory.
#
#   scripts/ce_pumd_download.sh DEST_DIR 21 22 23
#
# BLS's site rejects requests without browser-style headers (HTTP 403), so
# send them. Files: https://www.bls.gov/cex/pumd_data.htm
set -euo pipefail
dest="$1"; shift
mkdir -p "$dest"
ua="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
for yy in "$@"; do
  zip="$dest/intrvw$yy.zip"
  curl -sSf --http2 --compressed -A "$ua" \
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
    -H "Accept-Language: en-US,en;q=0.9" \
    -H "Referer: https://www.bls.gov/cex/pumd_data.htm" \
    -H "Sec-Fetch-Dest: document" -H "Sec-Fetch-Mode: navigate" \
    -H "Sec-Fetch-Site: same-origin" -H "Upgrade-Insecure-Requests: 1" \
    "https://www.bls.gov/cex/pumd/data/csv/intrvw$yy.zip" -o "$zip"
  unzip -q -o "$zip" "intrvw$yy/ntaxi*" "intrvw$yy/fmli*" -d "$dest"
  echo "intrvw$yy: $(ls "$dest/intrvw$yy"/ntaxi*.csv | wc -l | tr -d ' ') NTAXI files"
done
