from logger import log
import time


@log.logger
def upload(video_path: str):
    """This function will upload the video to YouTube Shorts."""
    log.info("Uploading video to YouTube Shorts: ", video_path)
    time.sleep(2)
    log.info("Video uploaded")
