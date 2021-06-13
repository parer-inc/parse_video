"""This service allows to prase video info"""
import os
import time
import json
import re
from rq import Worker, Queue, Connection
from methods.connection import get_redis, await_job
from pyyoutube import Api
import requests

YOUTUBE_URL = "https://www.youtube.com/watch?v="
api = Api(api_key=os.environ['YOUTUBE_TOKEN'])
r = get_redis()
request = requests.sessions.Session()
request.headers = {'X-YouTube-Client-Name': '1',
                   'X-YouTube-Client-Version': '2.20201202.06.01',
                   'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.36 Edg/87.0.664.55'}


def get_basic_details(continuation, track_params, token):
    req = request.post(
        f'https://www.youtube.com/comment_service_ajax?action_get_comments=1&pbj=1&ctoken={continuation}&continuation={continuation}&itct={track_params}', data={'session_token': token}).text
    a = json.loads(req)
    count = str(a['response']['continuationContents']['itemSectionContinuation']
                ['header']['commentsHeaderRenderer']['countText']['runs'][0]['text'])
    count = ''.join([s for s in count if s.isdigit()])
    page_len = len(a['response']['continuationContents']
                   ['itemSectionContinuation']['contents'])
    page_count = int(count) // page_len
    return (req, int(count), page_len, page_count)


def get_continuation_data(url):
    html = request.get(url).text
    a, b = re.search(
        r'"continuation":"(.*?)","clickTrackingParams":"(.*?)"', html).groups()
    b = b.replace('=', '%3D')
    token = re.search(r'"XSRF_TOKEN":"(.*?)"',
                      html).groups()[0].replace('\\u003d', '=')
    return (a, b, token)


def parse_video(id, coms=False):
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
            ','.join(data['snippet']['tags']
                     ), data['snippet']['defaultLanguage'],
            data['status']['madeForKids']]
    if coms:
        url = YOUTUBE_URL + id
        continuation, track_params, token = get_continuation_data(url)
        initial_json, count, page_len, end_range = get_basic_details(
            continuation, track_params, token)
        continuation, track_params, token = '', '', ''

        comments = []
        for k in range(1):  # end_range
            if k == 0:
                json_data = initial_json
            else:
                json_data = request.post(
                    f"https://www.youtube.com/comment_service_ajax?action_get_comments=1&pbj=1&ctoken={continuation}&continuation={continuation}&itct={track_params}", data={'session_token': token}).text
            json_data = json.loads(json_data)
            comment_json = json_data['response']['continuationContents']['itemSectionContinuation']['contents']
            token = json_data['xsrf_token']
            continuation = json_data['response']['continuationContents'][
                'itemSectionContinuation']['continuations'][0]["nextContinuationData"]['continuation']
            track_params = json_data['response']['continuationContents']['itemSectionContinuation'][
                'continuations'][0]["nextContinuationData"]["clickTrackingParams"]
            for i in comment_json:
                com_data = i['commentThreadRenderer']['comment']['commentRenderer']
                urnm = com_data['authorText']['simpleText']
                txt = com_data['contentText']['runs'][-1]['text']
                tm = com_data['publishedTimeText']['runs'][-1]['text']
                lks = 0
                rpls = 0
                try:
                    lks = com_data['voteCount']['simpleText']
                    rpls = com_data['replyCount']
                except Exception:
                    pass
                # WRITE INTO COMMENTS
                print(urnm, txt, tm, lks, rpls)
        return True


if __name__ == '__main__':
    q = Queue('parse_video', connection=r)
    with Connection(r):
        worker = Worker([q], connection=r,  name='parse_video')
        worker.work()
