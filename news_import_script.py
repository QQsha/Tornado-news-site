import datetime as dt
import re
import time
import urllib

import motor
import pytz
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse
from elasticsearch import Elasticsearch

from app import post_func

PATTERN_IMAGE = r'og:image" content="(.*)"'


db = motor.MotorClient().tornado_db
gridfs_coll = motor.MotorGridFS(db)
es = Elasticsearch()

# parsing dailymail rss feed
def parsing_news():
    url = "http://www.dailymail.co.uk/sport/teampages/chelsea.rss"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'xml')
    items = soup.findAll('item')
    info_news = []
    for item in items:
        news = dict()
        news['link'] = item.link.text.strip()
        news['title'] = item.title.text.strip()
        news['description'] = item.description.text.strip()
        news['date'] = parse(item.pubDate.text)
        info_news.append(news)
    return info_news[0]

# get request
def get_url(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content


# return caption text, and image link
def scrapper(url):
    news = {}
    html = get_url(url)
    news['image'] = re.findall(PATTERN_IMAGE, html)[0]
    img_data = requests.get(news['image']).content
    with open('image_name.jpg', 'wb') as handler:
        handler.write(img_data)
        return handler


def main():
    europe_timezone = pytz.timezone('Etc/GMT-1')
    date_baseline = dt.datetime.now(europe_timezone) - dt.timedelta(hours=1)
    while True:
        print("new pivot", dt.datetime.now(europe_timezone))
        news_url = parsing_news()
        last_link = news_url['link']
        last_title = news_url['title']
        last_body = news_url['description']
        if (news_url['date'] > date_baseline):
            last_picture = scrapper(last_link)
            post_func(db, es, gridfs_coll, last_title, last_body, last_picture)
        time.sleep(40)
print("sadasd")

if __name__ == '__main__':
    main()
