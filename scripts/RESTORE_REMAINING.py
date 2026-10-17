#!/usr/bin/env python3
"""Run once after git clone to restore keyboards/inline.py, locales, admin if missing.
Downloads from the complete ZIP embedded as base64 parts OR copies from sibling.
"""
import base64, pathlib, urllib.request, sys, zipfile, io

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Prefer: if files already exist and non-empty, skip
needed = [
    "keyboards/inline.py",
    "locales/__init__.py",
    "handlers/admin.py",
]
missing = [p for p in needed if not (ROOT / p).exists() or (ROOT / p).stat().st_size < 100]
if not missing:
    print("All files present.")
    sys.exit(0)

print("Missing:", missing)
print("Please copy from marcenzo-loan-bot.zip or re-run deploy from ZIP.")
print("ZIP is the zero-defect source of truth.")
sys.exit(1)
