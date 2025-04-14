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
# KEYWORD_LIST = ["blackhole","M87","galaxy","galaxies","machine learning","AGN","ALMA"]
KEYWORD_LIST = ["M87"]

# API???
OPENAI_API_KEYS = os.getenv("OPENAI_API_KEYS")
LANGUAGE = "zh"  # zh | en

# 确保它是一个字符串，而不是字符列表
# if not OPENAI_API_KEYS.startswith("sk-"):
#     print(f"API Key 解析错误: {OPENAI_API_KEYS}")
#     exit(1)
#
# print(f"Loaded OpenAI Key: {OPENAI_API_KEYS[:5]}********")
