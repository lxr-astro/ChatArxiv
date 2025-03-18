# encoding: utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
# private token
import os
from dotenv import load_dotenv
load_dotenv()

# Authentication for user filing issue (must have read/write access to repository to add issue to)
USERNAME = 'lxr-astro'
TOKEN = os.getenv("TOKEN")

# The repository to add this issue to
REPO_OWNER = 'lxr-astro'
REPO_NAME = 'ChatArxiv'

# Set new submission url of subject
NEW_SUB_URL = 'https://arxiv.org/list/astro-ph.GA/recent'

# Keywords to search
KEYWORD_LIST = ["gravitational lensing","Black hole","Blackhole","Galaxy","software","machine learning"]

# API???
OPENAI_API_KEYS = os.getenv("OPENAI_API_KEYS")
LANGUAGE = "zh"  # zh | en

# 打印检查（调试用，生产环境不要打印密钥）
# print(f"Loaded OpenAI Key: {OPENAI_API_KEYS is not None}")
# print(f"Loaded GitHub Token: {TOKEN is not None}")