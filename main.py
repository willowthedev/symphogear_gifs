import os
import sys
import time
import random
import requests
import schedule

from requests_oauthlib import OAuth1

from frames import FRAMES
from tokens import *

MEDIA_ENDPOINT_URL = 'https://upload.twitter.com/1.1/media/upload.json'
POST_TWEET_URL = 'https://api.twitter.com/1.1/statuses/update.json'

oauth = OAuth1(CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=ACCESS_TOKEN,
    resource_owner_secret=ACCESS_TOKEN_SECRET)

class MakeVideo(): 
    def __init__(self, directory, frames_list, copies_folder, output_video): 
        self.directory = directory
        self.frames_list = frames_list
        self.copies_folder = copies_folder
        self.output_video = output_video

    def make_video(self): 
        length = len(self.frames_list)
        index = random.randint(0, length - 120)    

        os.mkdir(self.copies_folder)
        for frame in self.frames_list[index:index + 120]:
            os.system(f"cp {self.directory}/{self.frames_list[index]} {self.copies_folder}/{self.frames_list[index]}")
            index += 1

        for num, frame in enumerate(sorted(os.listdir(self.copies_folder))): 
            os.rename(f"{self.copies_folder}/{frame}", f"{self.copies_folder}/frame{str(num)}.jpg")

        os.system(f"ffmpeg -i {self.copies_folder}/frame%d.jpg -c:a libfdk_aac -c:v libx264 {self.output_video}")

class TweetVideo(object):
    def __init__(self, file_name):
        self.video_filename = file_name
        self.total_bytes = os.path.getsize(self.video_filename)
        self.media_id = None
        self.processing_info = None
    
    def upload_init(self):
        request_data = {
        'command': 'INIT',
        'media_type': 'video/mp4',
        'total_bytes': self.total_bytes,
        'media_category': 'tweet_video'
        }

        req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, auth=oauth)
        media_id = req.json()['media_id']

        self.media_id = media_id

    def upload_append(self):
        segment_id = 0
        bytes_sent = 0
        file = open(self.video_filename, 'rb')

        while bytes_sent < self.total_bytes:
            chunk = file.read(4*1024*1024)        

            request_data = {
                'command': 'APPEND',
                'media_id': self.media_id,
                'segment_index': segment_id
            }

            files = {
                'media':chunk
            }

            req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, files=files, auth=oauth)

            segment_id = segment_id + 1
            bytes_sent = file.tell()

    def upload_finalize(self):
        request_data = {
        'command': 'FINALIZE',
        'media_id': self.media_id
        }

        req = requests.post(url=MEDIA_ENDPOINT_URL, data=request_data, auth=oauth)
        print(req.json())

        self.processing_info = req.json().get('processing_info', None)
        self.check_status()

    def check_status(self):
        if self.processing_info is None:
            return

        state = self.processing_info['state']

        if state == u'succeeded':
            return

        if state == u'failed':
            sys.exit(0)

        check_after_secs = self.processing_info['check_after_secs']
        
        time.sleep(check_after_secs)

        request_params = {
        'command': 'STATUS',
        'media_id': self.media_id
        }

        req = requests.get(url=MEDIA_ENDPOINT_URL, params=request_params, auth=oauth)
        
        self.processing_info = req.json().get('processing_info', None)
        self.check_status()

    def tweet(self):
        request_data = {
        'status': '',
        'media_ids': self.media_id
        }

        req = requests.post(url=POST_TWEET_URL, data=request_data, auth=oauth)
        print(req.json())

class CleanUp(): 
    def __init__(self, folder, video):
        self.folder = folder
        self.video = video 
        
    def clean_up(self): 
        for frame in os.listdir(self.folder): 
            os.remove(f"{self.folder}/{frame}")

        os.rmdir(self.folder)
        os.remove(self.video)

def bot():
    MakeVideo("/Volumes/SYMPHOGEAR", FRAMES, "./frames", "./out.mp4").make_video()
    
    tweet_video = TweetVideo("./out.mp4")
    tweet_video.upload_init()
    tweet_video.upload_append()
    tweet_video.upload_finalize()
    tweet_video.tweet()
    
    CleanUp("./frames", "./out.mp4").clean_up()

def main(): 
    schedule.every().hour.at(":00").do(bot)
    schedule.every().hour.at(":30").do(bot)

    while True: 
        schedule.run_pending()
        time.sleep(1)
    
if __name__ == "__main__": 
    main()