import numpy as np
import os
import re
import datetime
import arxiv
import openai, tenacity
import base64, requests
import argparse
import tiktoken
from get_paper_from_pdf import Paper

from github_issue import make_github_issue

# ------------------------
import sys
from dotenv import load_dotenv

# 仅在本地开发时加载 .env 文件（如果存在一个正确格式的 .env 文件）
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

OPENAI_API_KEYS = os.getenv("OPENAI_API_KEYS")
if not OPENAI_API_KEYS:
    print("❌ 错误：未正确加载 API Key！请检查 GitHub Secrets 或 .env 文件")
    exit(1)
print(f"✅ API Key 加载成功: {OPENAI_API_KEYS[:5]}********")



def split_text_into_chunks(text, max_chunk_size=30000):
    """
    将文本拆分成多个块，每个块长度不超过 max_chunk_size（字符数）
    优先在换行符处拆分，保证内容格式较好。
    """
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        # 计算剩余部分是否已经小于 max_chunk_size
        if text_length - start <= max_chunk_size:
            chunks.append(text[start:])
            break
        # 尝试在 max_chunk_size 范围内找最后一个换行符作为拆分点
        end = text.rfind("\n", start, start + max_chunk_size)
        if end == -1 or end <= start:
            # 如果找不到换行符，则直接强制切分
            end = start + max_chunk_size
        chunks.append(text[start:end])
        start = end
    return chunks
    # return [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]

def create_issues_for_long_text(title, body, labels, max_chunk_size=30000):
    """
    根据 body 内容拆分为多个块，并依次创建 Issue，标题后添加 -1、-2 ...
    """
    chunks = split_text_into_chunks(body, max_chunk_size)
    print(f"DEBUG: Splitting into {len(chunks)} chunks")
    issues = []
    for idx, chunk in enumerate(chunks, start=1):
        issue_title = f"{title}_{idx}"
        # 调用你已有的 make_github_issue 函数创建 Issue
        issue = make_github_issue(title=issue_title, body=chunk, labels=labels)
        issues.append(issue)
        print(f"Successfully created Issue \"{issue_title}\" (chunk length: {len(chunk)})")
    return issues

    # print(f"DEBUG: Total body length: {len(body)}")
    # chunks = split_text_into_chunks(body, max_chunk_size)
    # print(f"DEBUG: Splitting into {len(chunks)} chunks")
    # issues = []
    # for idx, chunk in enumerate(chunks, start=1):
    #     # 如果块内容太短或仅包含空白，则跳过
    #     if not chunk.strip():
    #         print(f"DEBUG: Chunk {idx} is empty or whitespace, skipping")
    #         continue
    #     # 输出前 100 个字符用于调试
    #     print(f"DEBUG: Chunk {idx} preview (length {len(chunk)}): {chunk[:100]!r}")
    #     issue_title = f"{title}-{idx}"
    #     issue = make_github_issue(title=issue_title, body=chunk, labels=labels)
    #     issues.append(issue)
    #     print(f"Successfully created Issue \"{issue_title}\" (chunk length: {len(chunk)})")
    # return issues


# -----------------------

# 本地调试
# os.environ["http_proxy"] = "http://127.0.0.1:8118"
# os.environ["https_proxy"] = "http://127.0.0.1:8118"

from config import OPENAI_API_KEYS, KEYWORD_LIST, LANGUAGE

from datetime import datetime, timedelta
import pytz
now = datetime.now(pytz.utc)

class Reader:
    def __init__(self, filter_keys, filter_times_span=None, key_word=None,
                 query=None, root_path='./',
                 sort=arxiv.SortCriterion.LastUpdatedDate,
                 user_name='default', args=None):

        self.user_name = user_name
        self.key_word = key_word
        self.query = query
        self.sort = sort

        # 设置语言
        if args.language == 'en':
            self.language = 'English'
        elif args.language == 'zh':
            self.language = 'Chinese'
        else:
            self.language = 'Chinese'

        # 处理 filter_times_span 默认值（每次都重新计算 now 和 yesterday）
        if filter_times_span is None:
            now = datetime.now(pytz.utc)
            yesterday = now - timedelta(days=90)
            self.filter_times_span = (yesterday, now)
        else:
            self.filter_times_span = filter_times_span

        self.filter_keys = filter_keys
        self.root_path = root_path

        self.chat_api_list = [OPENAI_API_KEYS] if isinstance(OPENAI_API_KEYS, str) else []
        self.cur_api = 0
        self.file_format = args.file_format
        self.max_token_num = 4096
        self.encoding = tiktoken.get_encoding("gpt2")

        print(f"当前时间范围: {self.filter_times_span[0]} ~ {self.filter_times_span[1]}")



                
    def get_arxiv(self, max_results=999):
        # https://info.arxiv.org/help/api/user-manual.html#query_details
        search = arxiv.Search(query=self.query,
                              max_results=max_results,                              
                              sort_by=self.sort,
                              sort_order=arxiv.SortOrder.Descending,
                              )       
        return search
# --------------------------   
    import tenacity

    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        stop=tenacity.stop_after_attempt(5),
        reraise=True
    ) 


    def filter_arxiv(self, max_results=999):
        search = self.get_arxiv(max_results=max_results)
        print("all search:")
        results = list(search.results())  # 获取所有论文
        for index, result in enumerate(results):
            print(index, result.title, result.updated)
    
        filter_results = []
        filter_keys = self.filter_keys  # 关键词列表，确保它是列表
        print("filter_keys:", filter_keys)
    
        # 只要摘要中出现任意一个关键词，就通过筛选
        for index, result in enumerate(results):
            # 过滤不在时间范围内的论文（DEBUG: 打印时间范围）
            print(f"论文时间: {result.updated}, 允许时间范围: {self.filter_times_span}")
            if result.updated < self.filter_times_span[0] or result.updated > self.filter_times_span[1]:
                continue
    
            abs_text = result.summary.replace('-\n', '-').replace('\n', ' ')  # 处理换行符
            title_text = result.title  # 论文标题
            abs_text = abs_text.lower()  # 摘要小写
            title_text = title_text.lower()  # 标题小写
    
            # DEBUG: 打印摘要和标题，检查是否包含关键词
            print(f"论文标题: {title_text}")
            print(f"论文摘要: {abs_text[:200]}...")  # 只打印前 200 字符，避免过长
    
            # 只要关键词出现在摘要或标题中，就加入筛选结果
            for f_key in filter_keys:
                f_key = f_key.lower()  # 确保关键词小写匹配
                if f_key in abs_text or f_key in title_text:
                    print(f"✅ 关键词 '{f_key}' 命中: {title_text}")  # DEBUG: 记录命中
                    filter_results.append(result)
                    break  # 命中一个关键词即可，不必继续检查
    
        print("筛选后剩下的论文数量：", len(filter_results))
        for index, result in enumerate(filter_results):
            print(index, result.title, result.updated)
    
        return filter_results



        
    # def filter_arxiv(self, max_results=30):
    #     search = self.get_arxiv(max_results=max_results)
    #     print("all search:")
    #     for index, result in enumerate(search.results()):
    #         print(index, result.title, result.updated)
            
    #     filter_results = []   
    #     filter_keys = self.filter_keys
        
    #     print("filter_keys:", self.filter_keys)
    #     # 确保每个关键词都能在摘要中找到，才算是目标论文
    #     for index, result in enumerate(search.results()):
    #         # 过滤不在时间范围内的论文
    #         if result.updated < self.filter_times_span[0] or result.updated > self.filter_times_span[1]:
    #             continue 
    #         abs_text = result.summary.replace('-\n', '-').replace('\n', ' ')
    #         meet_num = 0
    #         for f_key in filter_keys.split(" "):
    #             if f_key.lower() in abs_text.lower():
    #                 meet_num += 1
    #         if meet_num == len(filter_keys.split(" ")):
    #             filter_results.append(result)
    #             # break
    #     print("筛选后剩下的论文数量：")
    #     print("filter_results:", len(filter_results))
    #     print("filter_papers:")
    #     for index, result in enumerate(filter_results):
    #         print(index, result.title, result.updated)
    #     return filter_results
    
    def validateTitle(self, title):
        # 将论文的乱七八糟的路径格式修正
        rstr = r"[\/\\\:\*\?\"\<\>\|]" # '/ \ : * ? " < > |'
        new_title = re.sub(rstr, "_", title) # 替换为下划线
        return new_title

    def download_pdf(self, filter_results):
        # 先创建文件夹
        date_str = str(datetime.now())[:13].replace(' ', '-')        
        key_word = str(self.key_word.replace(':', ' '))        
        path = self.root_path  + 'pdf_files/' + self.query.replace('au: ', '').replace('title: ', '').replace('ti: ', '').replace(':', ' ')[:25] + '-' + date_str
        try:
            os.makedirs(path)
        except:
            pass
        print("All_paper:", len(filter_results))
        # 开始下载：
        paper_list = []
        for r_index, result in enumerate(filter_results):
            try:
                title_str = self.validateTitle(result.title)
                pdf_name = title_str+'.pdf'
                # result.download_pdf(path, filename=pdf_name)
                self.try_download_pdf(result, path, pdf_name)
                paper_path = os.path.join(path, pdf_name)
                print("paper_path:", paper_path)
                paper = Paper(path=paper_path,
                              url=result.entry_id,
                              title=result.title,
                              abs=result.summary.replace('-\n', '-').replace('\n', ' '),
                              authers=[str(aut) for aut in result.authors],
                              )
                # 下载完毕，开始解析：
                paper.parse_pdf()
                paper_list.append(paper)
            except Exception as e:
                print("download_error:", e)
                pass
        return paper_list
    
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    def try_download_pdf(self, result, path, pdf_name):
        result.download_pdf(path, filename=pdf_name)
    
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    def upload_gitee(self, image_path, image_name='', ext='png'):
        """
        上传到码云
        :return:
        """ 
        with open(image_path, 'rb') as f:
            base64_data = base64.b64encode(f.read())
            base64_content = base64_data.decode()
        
        date_str = str(datetime.datetime.now())[:19].replace(':', '-').replace(' ', '-') + '.' + ext
        path = image_name+ '-' +date_str
        
        payload = {
            "access_token": self.gitee_key,
            "owner": self.config.get('Gitee', 'owner'),
            "repo": self.config.get('Gitee', 'repo'),
            "path": self.config.get('Gitee', 'path'),
            "content": base64_content,
            "message": "upload image"
        }
        # 这里需要修改成你的gitee的账户和仓库名，以及文件夹的名字：
        url = f'https://gitee.com/api/v5/repos/'+self.config.get('Gitee', 'owner')+'/'+self.config.get('Gitee', 'repo')+'/contents/'+self.config.get('Gitee', 'path')+'/'+path
        rep = requests.post(url, json=payload).json()
        print("rep:", rep)
        if 'content' in rep.keys():
            image_url = rep['content']['download_url']
        else:
            image_url = r"https://gitee.com/api/v5/repos/"+self.config.get('Gitee', 'owner')+'/'+self.config.get('Gitee', 'repo')+'/contents/'+self.config.get('Gitee', 'path')+'/' + path
            
        return image_url
        
    def summary_with_chat(self, paper_list, htmls=None):
        if htmls is None:
            htmls = []
        for paper_index, paper in enumerate(paper_list):
            # 第一步先用title，abs，和introduction进行总结。
            text = ''
            text += 'Title:' + paper.title
            text += 'Url:' + paper.url
            text += 'Abstrat:' + paper.abs
            text += 'Paper_info:' + paper.section_text_dict['paper_info']
            # intro
            text += list(paper.section_text_dict.values())[0]
            chat_summary_text = ""
            try:
                chat_summary_text = self.chat_summary(text=text)     
            except Exception as e:
                print("summary_error:", e)
                if "maximum context" in str(e):
                    current_tokens_index = str(e).find("your messages resulted in") + len("your messages resulted in")+1
                    offset = int(str(e)[current_tokens_index:current_tokens_index+4])
                    summary_prompt_token = offset+1000+150
                    chat_summary_text = self.chat_summary(text=text, summary_prompt_token=summary_prompt_token)

            # htmls.append('## Paper:' + str(paper_index+1))
            htmls.append(f'## {paper.title}')
            htmls.append(f'- **Url**: {paper.url}')
            htmls.append(f'- **Authors**: {paper.authers}')
            htmls.append(f'- **Abstrat**: {paper.abs}')
            htmls.append('\n')            
            htmls.append(chat_summary_text)
            htmls.append('\n') 
            # 第二步总结方法：
            # TODO，由于有些文章的方法章节名是算法名，所以简单的通过关键词来筛选，很难获取，后面需要用其他的方案去优化。
            # method_key = ''
            # for parse_key in paper.section_text_dict.keys():
            #     if 'method' in parse_key.lower() or 'approach' in parse_key.lower():
            #         method_key = parse_key
            #         break
                
            # if method_key != '':
            #     text = ''
            #     method_text = ''
            #     summary_text = ''
            #     summary_text += "<summary>" + chat_summary_text
            #     # methods                
            #     method_text += paper.section_text_dict[method_key]                   
            #     text = summary_text + "\n\n<Methods>:\n\n" + method_text                 
            #     chat_method_text = ""
            #     try:
            #         chat_method_text = self.chat_method(text=text)                    
            #     except Exception as e:
            #         print("method_error:", e)
            #         if "maximum context" in str(e):
            #             current_tokens_index = str(e).find("your messages resulted in") + len("your messages resulted in")+1
            #             offset = int(str(e)[current_tokens_index:current_tokens_index+4])
            #             method_prompt_token = offset+800+150                        
            #             chat_method_text = self.chat_method(text=text, method_prompt_token=method_prompt_token)           
            #     htmls.append(chat_method_text)
            # else:
            #     chat_method_text = ''
            # htmls.append("\n"*4)
            
            # # 第三步总结全文，并打分：
            # conclusion_key = ''
            # for parse_key in paper.section_text_dict.keys():
            #     if 'conclu' in parse_key.lower():
            #         conclusion_key = parse_key
            #         break
            
            # text = ''
            # conclusion_text = ''
            # summary_text = ''
            # summary_text += "<summary>" + chat_summary_text + "\n <Method summary>:\n" + chat_method_text            
            # if conclusion_key != '':
            #     # conclusion                
            #     conclusion_text += paper.section_text_dict[conclusion_key]                                
            #     text = summary_text + "\n\n<Conclusion>:\n\n" + conclusion_text 
            # else:
            #     text = summary_text            
            # chat_conclusion_text = ""
            # try:
            #     chat_conclusion_text = self.chat_conclusion(text=text)                 
            # except Exception as e:
            #     print("conclusion_error:", e)
            #     if "maximum context" in str(e):
            #         current_tokens_index = str(e).find("your messages resulted in") + len("your messages resulted in")+1
            #         offset = int(str(e)[current_tokens_index:current_tokens_index+4])
            #         conclusion_prompt_token = offset+800+150                                            
            #         chat_conclusion_text = self.chat_conclusion(text=text, conclusion_prompt_token=conclusion_prompt_token)
            # htmls.append(chat_conclusion_text)
            # htmls.append("\n"*4)
            
            # file_name = os.path.join(export_path, date_str+'-'+self.validateTitle(paper.title)+".md")
            # self.export_to_markdown("\n".join(htmls), file_name=file_name, mode=mode)
            # self.save_to_file(htmls)
            # htmls = []

    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    def chat_conclusion(self, text, conclusion_prompt_token = 800):
        openai.api_key = self.chat_api_list[self.cur_api]

#----------
        print(f"正在使用 OpenAI API Key: {self.chat_api_list[self.cur_api]}")  # 添加这行
        openai.api_key = self.chat_api_list[self.cur_api]
# ----------

        self.cur_api += 1
        self.cur_api = 0 if self.cur_api >= len(self.chat_api_list)-1 else self.cur_api
        text_token = len(self.encoding.encode(text))
        clip_text_index = int(len(text)*(self.max_token_num-conclusion_prompt_token)/text_token)
        clip_text = text[:clip_text_index]   
        
        messages=[
                {"role": "system", "content": "You are a reviewer in the field of ["+self.key_word+"] and you need to critically review this article"},  # chatgpt 角色
                {"role": "assistant", "content": "This is the <summary> and <conclusion> part of an English literature, where <summary> you have already summarized, but <conclusion> part, I need your help to summarize the following questions:"+clip_text},  # 背景知识，可以参考OpenReview的审稿流程
                {"role": "user", "content": """                 
                 8. Make the following summary.Be sure to use {} answers (proper nouns need to be marked in English).
                    - (1):What is the significance of this piece of work?
                    - (2):Summarize the strengths and weaknesses of this article in three dimensions: innovation point, performance, and workload.                   
                    .......
                 Follow the format of the output later: 
                 8. Conclusion: \n\n
                    - (1):xxx;\n                     
                    - (2):Innovation point: xxx; Performance: xxx; Workload: xxx;\n                      
                 
                 Be sure to use {} answers (proper nouns need to be marked in English), statements as concise and academic as possible, do not repeat the content of the previous <summary>, the value of the use of the original numbers, be sure to strictly follow the format, the corresponding content output to xxx, in accordance with \n line feed, ....... means fill in according to the actual requirements, if not, you can not write.                 
                 """.format(self.language, self.language)},
            ]
        response = openai.ChatCompletion.create(
             jmj="gpt-4o-mini",
            # prompt需要用英语替换，少占用token。
            messages=messages,
        )
        result = ''
        for choice in response.choices:
            result += choice.message.content
        print("conclusion_result:\n", result)
        print("prompt_token_used:", response.usage.prompt_tokens,
              "completion_token_used:", response.usage.completion_tokens,
              "total_token_used:", response.usage.total_tokens)
        print("response_time:", response.response_ms/1000.0, 's')             
        return result            
    
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    def chat_method(self, text, method_prompt_token = 800):
        openai.api_key = self.chat_api_list[self.cur_api]
        self.cur_api += 1
        self.cur_api = 0 if self.cur_api >= len(self.chat_api_list)-1 else self.cur_api
        text_token = len(self.encoding.encode(text))
        clip_text_index = int(len(text)*(self.max_token_num-method_prompt_token)/text_token)
        clip_text = text[:clip_text_index]        
        messages=[
                {"role": "system", "content": "You are a researcher in the field of ["+self.key_word+"] who is good at summarizing papers using concise statements"},  # chatgpt 角色
                {"role": "assistant", "content": "This is the <summary> and <Method> part of an English document, where <summary> you have summarized, but the <Methods> part, I need your help to read and summarize the following questions."+clip_text},  # 背景知识
                {"role": "user", "content": """                 
                 7. Describe in detail the methodological idea of this article. Be sure to use {} answers (proper nouns need to be marked in English). For example, its steps are.
                    - (1):...
                    - (2):...
                    - (3):...
                    - .......
                 Follow the format of the output that follows: 
                 7. Methods: \n\n
                    - (1):xxx;\n 
                    - (2):xxx;\n 
                    - (3):xxx;\n  
                    ....... \n\n     
                 
                 Be sure to use {} answers (proper nouns need to be marked in English), statements as concise and academic as possible, do not repeat the content of the previous <summary>, the value of the use of the original numbers, be sure to strictly follow the format, the corresponding content output to xxx, in accordance with \n line feed, ....... means fill in according to the actual requirements, if not, you can not write.                 
                 """.format(self.language, self.language)},
            ]
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        result = ''
        for choice in response.choices:
            result += choice.message.content
        print("method_result:\n", result)
        print("prompt_token_used:", response.usage.prompt_tokens,
              "completion_token_used:", response.usage.completion_tokens,
              "total_token_used:", response.usage.total_tokens)
        print("response_time:", response.response_ms/1000.0, 's') 
        return result
    
    @tenacity.retry(wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
                    stop=tenacity.stop_after_attempt(5),
                    reraise=True)
    # def chat_summary(self, text, summary_prompt_token = 1100):
    #     openai.api_key = self.chat_api_list[self.cur_api]
    #     self.cur_api += 1
    #     self.cur_api = 0 if self.cur_api >= len(self.chat_api_list)-1 else self.cur_api
    #     text_token = len(self.encoding.encode(text))
    #     clip_text_index = int(len(text)*(self.max_token_num-summary_prompt_token)/text_token)
    #     clip_text = text[:clip_text_index]
    #     messages=[
    #             {"role": "system", "content": "You are a researcher in the field of ["+self.key_word+"] who is good at summarizing papers using concise statements"},
    #             {"role": "assistant", "content": "This is the title, author, link, abstract and introduction of an English document. I need your help to read and summarize the following questions: "+clip_text},
    #             {"role": "user", "content": """                 
    #              summarize according to the following five points.Be sure to use {} answers (proper nouns need to be marked in English)
    #                 - (1):What is the research background of this article?
    #                 - (2):What are the past methods? What are the problems with them? What difference is the proposed approach from existing methods? How does the proposed method address the mentioned problems? Is the proposed approach well-motivated? 
    #                 - (3):What is the contribution of the paper?
    #                 - (4):What is the research methodology proposed in this paper?
    #                 - (5):On what task and what performance is achieved by the methods in this paper? Can the performance support their goals?
    #              Follow the format of the output that follows:                    
    #              **Summary**: \n\n
    #                 - (1):xxx;\n 
    #                 - (2):xxx;\n 
    #                 - (3):xxx;\n 
    #                 - (4):xxx;\n  
    #                 - (5):xxx.\n\n     
                 
    #              Be sure to use {} answers (proper nouns need to be marked in English), statements as concise and academic as possible, do not have too much repetitive information, numerical values using the original numbers, be sure to strictly follow the format, the corresponding content output to xxx, in accordance with \n line feed.                 
    #              """.format(self.language, self.language, self.language)},
    #         ]
                
    #     response = openai.ChatCompletion.create(
    #         model="gpt-4o-mini",
    #         messages=messages,
    #     )
    #     result = ''
    #     for choice in response.choices:
    #         result += choice.message.content
    #     print("summary_result:\n", result)
    #     print("prompt_token_used:", response.usage.prompt_tokens,
    #           "completion_token_used:", response.usage.completion_tokens,
    #           "total_token_used:", response.usage.total_tokens)
    #     print("response_time:", response.response_ms/1000.0, 's')                    
    #     return result      
    
    def chat_summary(self, text, summary_prompt_token=1100):
        openai.api_key = self.chat_api_list[self.cur_api]
        self.cur_api += 1
        self.cur_api = 0 if self.cur_api >= len(self.chat_api_list) - 1 else self.cur_api
        text_token = len(self.encoding.encode(text))
        clip_text_index = int(len(text) * (self.max_token_num - summary_prompt_token) / text_token)
        clip_text = text[:clip_text_index]
        messages = [
            {"role": "system",
             "content": "You are a researcher in the field of [" + self.key_word + "] who is good at summarizing papers using concise statements"},
            {"role": "assistant",
             "content": "This is the title, author, link, abstract and introduction of an English document. I need your help to read and summarize the following questions: " + clip_text},
            {"role": "user", "content": """

                        Translate the title.

                        Translate the abstract.

                        summarize the paper according to the following five points. Be sure to use {0} answers (proper nouns need to be marked in English):
                          - (1): What is the research background of this article?
                          - (2): What are the past methods? What are the problems with them? What difference is the proposed approach from existing methods? How does the proposed method address the mentioned problems? Is the proposed approach well-motivated?
                          - (3): What is the contribution of the paper?
                          - (4): What is the research methodology proposed in this paper?
                          - (5): On what task and what performance is achieved by the methods in this paper? Can the performance support their goals?



                        Follow the format of the output below:

                        **Translated Abstract**: \n\n
                        <Your translated abstract here> \n\n
                        **Summary**:\n\n
                          - (1): xxx;\n
                          - (2): xxx;\n
                          - (3): xxx;\n
                          - (4): xxx;\n
                          - (5): xxx.\n\n

                        Be sure to use {1} answers (proper nouns need to be marked in English) and keep statements concise and academic. Do not repeat content from the previous summary and strictly follow the output format.
                        """.format(self.language, self.language)}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        result = ''
        for choice in response.choices:
            result += choice.message.content
        print("summary_result:\n", result)
        print("prompt_token_used:", response.usage.prompt_tokens,
              "completion_token_used:", response.usage.completion_tokens,
              "total_token_used:", response.usage.total_tokens)
        print("response_time:", response.response_ms/1000.0, 's')
        return result


    # 定义一个方法，打印出读者信息
    def show_info(self):        
        print(f"Key word: {self.key_word}")
        print(f"Query: {self.query}")
        print(f"Sort: {self.sort}")     

def save_to_file(htmls, root_path='./', date_str=None, file_format='md'):
    # # 整合成一个文件，打包保存下来。
    if date_str is None:
        date_str = str(datetime.now())[:13].replace(' ', '-')
    try:
        export_path = os.path.join(root_path, 'export')
        os.makedirs(export_path, exist_ok=True)
    except:
        pass                             
    mode = 'a'
    file_name = os.path.join(export_path, date_str+"."+file_format)
    export_to_markdown("\n".join(htmls), file_name=file_name, mode=mode)

def export_to_markdown(text, file_name, mode='w'):
    # 使用markdown模块的convert方法，将文本转换为html格式
    # html = markdown.markdown(text)
    # 打开一个文件，以写入模式
    with open(file_name, mode, encoding="utf-8") as f:
        # 将html格式的内容写入文件
        f.write(text)

def main(args):       
    # 创建一个Reader对象，并调用show_info方法
    if args.sort == 'Relevance':
        sort = arxiv.SortCriterion.Relevance
    elif args.sort == 'LastUpdatedDate':
        sort = arxiv.SortCriterion.LastUpdatedDate
    else:
        sort = arxiv.SortCriterion.Relevance
    
    if args.pdf_path:
        reader1 = Reader(key_word=args.key_word, 
                         query=args.query, 
                         filter_keys=args.filter_keys,                                    
                         sort=sort, 
                         args=args
                         )
        reader1.show_info()
        # 开始判断是路径还是文件：   
        paper_list = []     
        if args.pdf_path.endswith(".pdf"):
            paper_list.append(Paper(path=args.pdf_path))            
        else:
            for root, dirs, files in os.walk(args.pdf_path):
                print("root:", root, "dirs:", dirs, 'files:', files) #当前目录路径
                for filename in files:
                    # 如果找到PDF文件，则将其复制到目标文件夹中
                    if filename.endswith(".pdf"):
                        paper_list.append(Paper(path=os.path.join(root, filename)))        
        print("------------------paper_num: {}------------------".format(len(paper_list)))        
        [print(paper_index, paper_name.path.split('\\')[-1]) for paper_index, paper_name in enumerate(paper_list)]
        reader1.summary_with_chat(paper_list=paper_list)
    else:
        filter_times_span = (now-timedelta(days=args.filter_times_span), now)
        title = str(now)[:13].replace(' ', '-')
        htmls_body = []
        for filter_key in args.filter_keys:
            # 对于每一个主题做一遍
            # filter_key: remote sensing
            # query: all:remote AND all:sensing
            key_word = filter_key
            query = ''
            for item in filter_key.split(" "):
                if query != '':
                    query += ' AND '
                query += f'all:{item}'
            htmls = []
            htmls.append(f'# {filter_key}')
            reader1 = Reader(key_word=key_word, 
                            query=query, 
                            filter_keys=filter_key,
                            filter_times_span=filter_times_span,                           
                            sort=sort,
                            args=args
                            )
            reader1.show_info()
            filter_results = reader1.filter_arxiv(max_results=args.max_results)
            paper_list = reader1.download_pdf(filter_results)
            reader1.summary_with_chat(paper_list=paper_list, htmls=htmls)
            # htmls.append("#######test#########")
            htmls_body += htmls
        # 在全部模式下，生成 Markdown 文件后：
        save_to_file(htmls_body, date_str=title, root_path='./')
# -----------------------
        # 原先是：make_github_issue(title=title, body="\n".join(htmls_body), labels=args.filter_keys)
        # 替换为拆分创建 Issue：
        full_body = "\n".join(htmls_body)
        chunks = split_text_into_chunks(body, max_chunk_size)
        print(f"DEBUG: Total length = {len(body)}, split into {len(chunks)} chunks")
        create_issues_for_long_text(title=title, body=full_body, labels=args.filter_keys)


# if __name__ == '__main__':    
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--pdf_path", type=str, default='', help="if none, the bot will download from arxiv with query")
#     parser.add_argument("--query", type=str, default='all:remote AND all:sensing', help="the query string, ti: xx, au: xx, all: xx,") 
#     parser.add_argument("--key_word", type=str, default='remote sensing', help="the key word of user research fields")
#     parser.add_argument("--filter_keys", type=list, default=KEYWORD_LIST, help="the filter key words, 摘要中每个单词都得有，才会被筛选为目标论文")
#     parser.add_argument("--filter_times_span", type=int, default=1.1, help='how many days of files to be filtered.')
#     parser.add_argument("--max_results", type=int, default=20, help="the maximum number of results")
#     # arxiv.SortCriterion.Relevance
#     parser.add_argument("--sort", type=str, default="LastUpdatedDate", help="another is LastUpdatedDate | Relevance")
#     parser.add_argument("--file_format", type=str, default='md', help="导出的文件格式，如果存图片的话，最好是md，如果不是的话，txt的不会乱")
#     parser.add_argument("--language", type=str, default=LANGUAGE, help="The other output lauguage is English, is en")
    
#     args = parser.parse_args()
#     import time
#     start_time = time.time()
#     main(args=args)    
#     print("summary time:", time.time() - start_time)



if __name__ == '__main__':    
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf_path", type=str, default='', help="if none, the bot will download from arxiv with query")
    parser.add_argument("--query", type=str, default='all:remote AND all:sensing', help="the query string, ti: xx, au: xx, all: xx,") 
    parser.add_argument("--key_word", type=str, default='remote sensing', help="the key word of user research fields")
    parser.add_argument("--filter_keys", type=str, default=KEYWORD_LIST, help="the filter key words, 摘要中每个单词都得有，才会被筛选为目标论文")
    parser.add_argument("--filter_times_span", type=float, default=90, help='how many days of files to be filtered.')
    parser.add_argument("--max_results", type=int, default=999, help="the maximum number of results")
    parser.add_argument("--sort", type=str, default="LastUpdatedDate", help="another is LastUpdatedDate | Relevance")
    parser.add_argument("--file_format", type=str, default='md', help="导出的文件格式，如果存图片的话，最好是md，如果不是的话，txt的不会乱")
    parser.add_argument("--language", type=str, default=LANGUAGE, help="The other output language is English, is en")
    # 新增 mode 参数：generate, create-issue, 或 all（默认）
    parser.add_argument("--mode", type=str, default="all", choices=["generate", "create-issue", "all"], help="运行模式：generate 仅生成 Markdown, create-issue 仅创建 Issue, all 两者都执行")
    
    args = parser.parse_args()
    import time
    start_time = time.time()

    # 如果选择仅生成 Markdown 文件
    if args.mode == "generate":
        if args.pdf_path:
            # 如果提供 pdf_path，处理 pdf 文件生成摘要
            reader = Reader(key_word=args.key_word, query=args.query, filter_keys=args.filter_keys, sort=arxiv.SortCriterion.LastUpdatedDate, args=args)
            reader.show_info()
            paper_list = []
            if args.pdf_path.endswith(".pdf"):
                paper_list.append(Paper(path=args.pdf_path))
            else:
                for root, dirs, files in os.walk(args.pdf_path):
                    for filename in files:
                        if filename.endswith(".pdf"):
                            paper_list.append(Paper(path=os.path.join(root, filename)))
            reader.summary_with_chat(paper_list=paper_list)
        else:
            filter_times_span = (now - timedelta(days=args.filter_times_span), now)
            title = str(now)[:13].replace(' ', '-')
            htmls_body = []
            for filter_key in args.filter_keys:  # 假设 filter_keys 是以空格分隔的字符串
                query = " AND ".join(f"all:{item}" for item in filter_key.split())
                htmls = [f'# {filter_key}']
                reader = Reader(key_word=filter_key, query=query, filter_keys=filter_key, filter_times_span=filter_times_span, sort=arxiv.SortCriterion.LastUpdatedDate, args=args)
                reader.show_info()
                filter_results = reader.filter_arxiv(max_results=args.max_results)
                paper_list = reader.download_pdf(filter_results)
                reader.summary_with_chat(paper_list=paper_list, htmls=htmls)
                htmls_body += htmls
            save_to_file(htmls_body, date_str=title, root_path='./')
    # 如果选择仅创建 Issue
    elif args.mode == "create-issue":
        # 假设最新的 Markdown 文件在 export/ 目录，以当前日期为文件名
        title = str(now)[:13].replace(' ', '-')
        file_path = os.path.join("export", f"{title}.{args.file_format}")
        if not os.path.exists(file_path):
            print(f"❌ Markdown 文件 {file_path} 不存在，请先运行生成步骤.")
            exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"DEBUG: Read markdown file length: {len(content)}")
        create_issues_for_long_text(title=title, body=content, labels=args.filter_keys)

    # 如果选择全部（默认），生成 Markdown 文件并创建 Issue
    else:
        if args.pdf_path:
            reader = Reader(key_word=args.key_word, query=args.query, filter_keys=args.filter_keys, sort=arxiv.SortCriterion.LastUpdatedDate, args=args)
            reader.show_info()
            paper_list = []
            if args.pdf_path.endswith(".pdf"):
                paper_list.append(Paper(path=args.pdf_path))
            else:
                for root, dirs, files in os.walk(args.pdf_path):
                    for filename in files:
                        if filename.endswith(".pdf"):
                            paper_list.append(Paper(path=os.path.join(root, filename)))
            reader.summary_with_chat(paper_list=paper_list)
        else:
            filter_times_span = (now - timedelta(days=args.filter_times_span), now)
            title = str(now)[:13].replace(' ', '-')
            htmls_body = []
            for filter_key in args.filter_keys:
                query = " AND ".join(f"all:{item}" for item in filter_key.split())
                htmls = [f'# {filter_key}']
                reader = Reader(key_word=filter_key, query=query, filter_keys=filter_key, filter_times_span=filter_times_span, sort=arxiv.SortCriterion.LastUpdatedDate, args=args)
                reader.show_info()
                filter_results = reader.filter_arxiv(max_results=args.max_results)
                paper_list = reader.download_pdf(filter_results)
                reader.summary_with_chat(paper_list=paper_list, htmls=htmls)
                htmls_body += htmls
            save_to_file(htmls_body, date_str=title, root_path='./')
            make_github_issue(title=title, body="\n".join(htmls_body), labels=args.filter_keys)
            
    print("summary time:", time.time() - start_time)

