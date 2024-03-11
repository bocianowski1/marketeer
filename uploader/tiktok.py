from logger import log
import time


@log.logger
def upload(video_path: str):
    """This function will upload the video to tiktok."""
    log.info("Uploading video to tiktok: ", video_path)
    time.sleep(2)
    log.info("Video uploaded")
