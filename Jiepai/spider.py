#coding=utf-8
import json
from hashlib import md5
from json import JSONDecodeError
import os
import pymongo
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
import requests
from urllib.parse import urlencode
from config import *
from multiprocessing.pool import Pool
import re

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]


def get_page_index(offset,keyword):
    params = {
        'aid': '24',
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '1',
        'from': 'search_tab',
        'pd': 'synthesis'
    }
    base_url = 'https://www.toutiao.com/api/search/content/?'
    url = base_url + urlencode(params)
    try:
        resp = requests.get(url)
        if 200  == resp.status_code:
            return  resp.text
        return None
    except RequestException:
        print('请求索引页出错')
        return None

def parse_page_index(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                if item.get('cell_type') or item.get('article_url')[:25] != 'http://toutiao.com/group/':
                    continue
                # print(item.get('article_url'))
                item_str_list = item.get('article_url').split('group/')
                item_str = 'a'.join(item_str_list)
                yield item_str
    except JSONDecodeError:
        print('解析索引页出错')
        return None


def get_page_detail(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页出错')
        return None


def parse_page_detail(html,url):
    images_pattern = re.compile(r'BASE_DATA.galleryInfo.*?gallery: JSON.parse.*?"(.*?)"\),',re.S)
    result = re.search(images_pattern,html)
    if result != None:
        soup = BeautifulSoup(html, 'lxml')
        title = soup.select('title')[0].get_text()
        data = re.sub('\\\\"' ,'"' , result.group(1))
        data = re.sub(r'\\\\' ,'' , data)
        data = json.loads(data)
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images:
                download_image(image)
            return {
                'title':title,
                'url':url,
                'images':images
            }
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功',result)
        return True
    return False


def download_image(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('请求图片出错',url)
        return None

def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(),md5(content).hexdigest(),'jpg')
    if not os.path.exists(file_path):
        with open(file_path,'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset, KEYWORD)
    # print(html)
    for url in parse_page_index(html):
        # print(url)
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html,url)
            if result:
                save_to_mongo(result)



if __name__ == '__main__':
    # main()
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main,groups)