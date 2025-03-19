# # encoding: utf-8
# from __future__ import absolute_import
# from __future__ import division
# from __future__ import print_function
# from __future__ import unicode_literals

# import json
# import requests
# from config import USERNAME, TOKEN, REPO_OWNER, REPO_NAME

# def make_github_issue(title, body=None, assignee=USERNAME, closed=False, labels=[]):
#     # Create an issue on github.com using the given parameters
#     # Url to create issues via POST
#     url = 'https://api.github.com/repos/%s/%s/import/issues' % (REPO_OWNER, REPO_NAME)

#     # Headers
#     headers = {
#         "Authorization": "token %s" % TOKEN,
#         "Accept": "application/vnd.github.golden-comet-preview+json"
#     }

#     # Create our issue
#     data = {'issue': {'title': title,
#                       'body': body,
#                       'assignee': assignee,
#                       'closed': closed,
#                       'labels': labels}}

#     payload = json.dumps(data)

#     # Add the issue to our repository
#     response = requests.request("POST", url, data=payload, headers=headers)
#     if response.status_code == 202:
#         print ('Successfully created Issue "%s"' % title)
#     else:
#         print ('Could not create Issue "%s"' % title)
#         print ('Response:', response.content)

# if __name__ == '__main__':
#     title = 'Pretty title'
#     body = 'Beautiful body'
#     assignee = USERNAME
#     closed = False
#     labels = [
#         "imagenet", "image retrieval"
#     ]

#     make_github_issue(title, body, assignee, closed, labels)


# --------------------------------------
# fix : bug : 2 keyword no issue
# encoding: utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import requests
from config import USERNAME, TOKEN, REPO_OWNER, REPO_NAME

def make_github_issue(title, body=None, assignee=USERNAME, closed=False, labels=None):
    """
    创建一个 GitHub Issue
    :param title: Issue 标题
    :param body: Issue 正文
    :param assignee: 指定负责人（默认为 USERNAME）
    :param closed: (注：标准 Issue API 不支持直接关闭 issue，可在后续调用 API 关闭)
    :param labels: Issue 标签（列表形式）
    :return: 如果创建成功，返回响应的 JSON，否则返回 None
    """
    if labels is None:
        labels = []
    
    # 使用标准 Issue API endpoint
    url = f'https://api.github.com/repos/lxr-astro/ChatArxiv/issues'

    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # 构造请求 payload
    data = {
        "title": title,
        "body": body,
        "assignee": assignee,
        "labels": labels
    }

    payload = json.dumps(data)

    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 201:
        print('Successfully created Issue "%s"' % title)
        return response.json()
    else:
        print('Could not create Issue "%s"' % title)
        print('Response:', response.status_code, response.text)
        return None

if __name__ == '__main__':
    title = 'Pretty title'
    body = 'Beautiful body'
    assignee = USERNAME
    closed = False
    labels = ["imagenet", "image retrieval"]

    make_github_issue(title, body, assignee, closed, labels)



