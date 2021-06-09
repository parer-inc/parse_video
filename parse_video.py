"""This service allows to prase video info"""
import os
import time
from rq import Worker, Queue, Connection
from methods.connection import get_redis, await_job
from pyyoutube import Api
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

driver = webdriver.Remote(
command_executor='http://chromedriver:4444/wd/hub',
desired_capabilities=DesiredCapabilities.CHROME)

YOUTUBE_URL = "https://www.youtube.com/watch?v="
api = Api(api_key=os.environ['YOUTUBE_TOKEN'])
r = get_redis()

def parse_video(id, coms = False):
    """Parses a video"""
    # GET VIEO DATA USING API
    channel_by_id = api.get_video_by_id(video_id=id)
    data = None
    if channel_by_id.items is not None:
        data = channel_by_id.items[0].to_dict()
    if data is None:
        # log
        return False
    data = [data['id'], data['snippet']['title'],
            data['statistics']['viewCount'], data['statistics']['likeCount'],
            data['statistics']['dislikeCount'], data['statistics']['commentCount'],
            data['snippet']['description'], data['snippet']['channelId'],
            data['contentDetails']['duration'], data['snippet']['publishedAt'],
            ','.join(data['snippet']['tags']), data['snippet']['defaultLanguage'],
            data['status']['madeForKids']]
    if coms:
        driver.get(YOUTUBE_URL + id)
        time.sleep(5)
        height = driver.execute_script("return document.documentElement.scrollHeight")
        print("Parsing comments")
        try:
            for i in range(1):#while True:
                prev_ht = driver.execute_script("return document.documentElement.scrollHeight;")
                driver.execute_script("window.scrollTo(0, " + str(height) + ");")
                time.sleep(5)
                height = driver.execute_script("return document.documentElement.scrollHeight")
                print("done loop")
                if prev_ht == height:
                    break
        except Exception as e:
            print(e)  # LOG
        try:
            comms = driver.find_elements_by_xpath('//*[@id="video-title"]')
            q = Queue('write_comment', connection=r)
            for i in comms:
                print(i)
                # q.enqueue('write_comment.write_comment',)
        except Exception as e:
            print(e)  # LOG
    else:
        return data


if __name__ == '__main__':
    q = Queue('parse_video', connection=r)
    with Connection(r):
        worker = Worker([q], connection=r,  name='parse_video')
        worker.work()
