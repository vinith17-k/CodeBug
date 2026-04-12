#!/usr/bin/env python3
import os

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")
HF_TOKEN = os.environ.get("HF_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

print("API Settings:")
print(f"  API_BASE_URL: {API_BASE_URL}")
print(f"  MODEL_NAME: {MODEL_NAME}")
print(f"  HF_TOKEN set: {HF_TOKEN is not None}")
print(f"  OPENAI_API_KEY set: {OPENAI_API_KEY is not None}")
