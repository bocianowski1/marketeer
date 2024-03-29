import os
import sys
from threading import Thread
from dataclasses import dataclass
import time
from dotenv import load_dotenv

from openai import OpenAI
from pytube import YouTube
from moviepy.config import change_settings

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# internal imports
from logger import log

# from uploader import tiktok, yt_shorts

log.emphasize("Starting program...")
load_dotenv()
DEV = os.environ.get("ENV") == "development"

ffmpeg_path = "/usr/local/bin/ffmpeg" if DEV else "/usr/bin/ffmpeg"
change_settings({"FFMPEG_BINARY": ffmpeg_path})

if DEV:
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
else:
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions


@dataclass
class ViralPart:
    start_time: int
    end_time: int
    title: str
    path_to_transcript: str


VIDEO_DIR = "video"
OUT_DIR = "out"
TRANSCRIPT_DIR = "transcripts"
AUDIO_DIR = "audio"

N_VIDEOS = 1

API_KEY = os.environ.get("OPENAI_API_KEY")

if not os.path.exists(VIDEO_DIR):
    log.warn("Creating video directory...")
    os.makedirs(VIDEO_DIR)

if not os.path.exists(OUT_DIR):
    log.warn("Creating output directory...")
    os.makedirs(OUT_DIR)

if not os.path.exists(TRANSCRIPT_DIR):
    log.warn("Creating transcript directory...")
    os.makedirs(TRANSCRIPT_DIR)

if not os.path.exists(AUDIO_DIR):
    log.warn("Creating audio directory...")
    os.makedirs(AUDIO_DIR)

if API_KEY is None:
    log.error("No OpenAI API key found")
    sys.exit(1)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

options = FirefoxOptions()
# if no arguments are passed
# arg can be anything
if len(sys.argv) == 1:
    options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


@log.logger
def download_video(url: str):
    """Uses PyTube to download the video."""
    yt = YouTube(url)
    log.info(f"Downloading video: {yt.title}")

    filename = yt.title.replace(" ", "_").lower()

    if os.path.exists(os.path.join(VIDEO_DIR, filename)):
        log.warn(f"Video already exists: {yt.title}")
        return

    def download_audio_and_find_viral_parts():
        yt.streams.filter(only_audio=True).first().download(
            output_path=AUDIO_DIR, filename=filename + ".mp3"
        )

        log.info(f"Audio downloaded: {yt.title}")
        log.info("Finding viral parts for video:", filename)

        create_viral_clip(filename + ".mp3")

    thread1 = Thread(
        # target=yt.streams.filter(progressive=True, file_extension="mp4", res="720p")
        # .first()
        # .download,
        # args=(VIDEO_DIR, filename + ".mp4"),
        target=print,
        args=("Downloading video...",),
    )

    thread2 = Thread(target=download_audio_and_find_viral_parts)

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    log.info(f"Video downloaded: {yt.title}")


@log.logger
def create_clip_with_subtitles(viral_part: ViralPart):
    """Uses MoviePy to create a video clip with OpenAI generated subtitles."""
    log.info(
        "Creating video clip for viral part:",
        viral_part.title,
        viral_part.start_time,
        viral_part.end_time,
    )
    time.sleep(1)
    log.info("Video clip created")


@log.logger
def create_viral_clip(filename: str):
    """This function will prompt OpenAI to find the viral parts of the video and then create a video clip for each viral part."""
    log.info("Finding viral parts for video:", filename)

    if not filename.endswith(".mp3"):
        log.error("Invalid file type")
        return

    if not os.path.exists(f"{AUDIO_DIR}/{filename}"):
        log.error("Audio file not found")
        return

    transcript_filename = filename.replace(".mp3", ".srt")
    transcript = None
    if os.path.exists(f"{TRANSCRIPT_DIR}/{transcript_filename}"):
        log.warn("Transcript already exists")
        with open(f"{TRANSCRIPT_DIR}/{transcript_filename}", "r") as f:
            transcript = f.read()

    if transcript is None:
        log.warn("Creating transcript for audio file")
        with open(f"{AUDIO_DIR}/{filename}", "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
                prompt="Create a transcript of this video, one word at a time. There should be a new line for each word with the exact time it was spoken.",
            )

            log.info("Transcript created, saving...")

    with open(f"{TRANSCRIPT_DIR}/{filename}.srt", "w") as f:
        f.write(transcript)

    log.info("Finding viral parts from transcript")
    # viral_parts: list[ViralPart] = []

    response = client.completions.create(
        model="gpt-4-turbo-preview",
        prompt="Given this transcript, find the parts of this video that will go viral on tiktok on YouTube Shorts, and create a list of viral parts with a title, the start and end time of each part.\n**Transcript**\n{transcript}",
        max_tokens=100,
        temperature=0.3,
        n=10,
    )

    print(response)

    # viral_parts: list[ViralPart] = [
    #     ViralPart(0, 10, "Title 1", "transcript1.srt"),
    #     ViralPart(10, 20, "Title 2", "transcript2.srt"),
    # ]

    # threads: list[Thread] = []
    # for viral_part in viral_parts:
    #     thread = Thread(target=create_clip_with_subtitles, args=(viral_part,))
    #     threads.append(thread)
    #     thread.start()

    # for thread in threads:
    #     thread.join()


@log.logger
def run_browser_instance(channel_url: str):
    """This function will get videos from the channel and download them."""
    driver = webdriver.Firefox(options=options)
    driver.get(channel_url)

    if driver.current_url.startswith("https://consent"):
        log.info("Consent page found. Submitting the form...")
        try:
            form = driver.find_elements(By.TAG_NAME, "form")[1]
            button = form.find_element(By.TAG_NAME, "button")
            button.click()
        except Exception as e:
            log.error("Error submitting consent form: ", e)
            return

    log.info(f"Getting videos from channel: {channel_url}")
    log.info("Scrolling to the bottom of the page once...")

    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    driver.implicitly_wait(1)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    if len(soup.find_all("a", {"id": "thumbnail"})) <= 1:
        log.warn("Initially, no videos found, scrolling and waiting")
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        driver.implicitly_wait(1)
        log.info("Scrolled and done waiting")

    soup = BeautifulSoup(driver.page_source, "html.parser")

    video_urls = set()
    for link in soup.find_all("a", {"id": "thumbnail"}):
        href = link.get("href")
        if href is None:
            continue
        if href.startswith("/watch"):
            video_urls.add("https://www.youtube.com" + href)

    video_urls = list(video_urls)
    if len(video_urls) == 0:
        log.error("No videos found")
        return

    if len(video_urls) > 3:
        end = min(N_VIDEOS, len(video_urls) - 1)
        video_urls = video_urls[:end]

    log.info(len(video_urls), "videos found")
    driver.quit()
    log.info("Browser instance closed")

    threads: list[Thread] = []
    for url in video_urls:
        thread = Thread(target=download_video, args=(url,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # threads: list[Thread] = []
    # for video_path in os.listdir(VIDEO_DIR):
    #     thread = Thread(target=create_viral_clip, args=(video_path,))
    #     threads.append(thread)
    #     thread.start()

    # for thread in threads:
    #     thread.join()


def main():
    start_time = time.time()
    urls = [
        "https://www.youtube.com/c/BetaSquad/videos",
        "https://www.youtube.com/c/@Sidemen/videos",
        # "https://www.youtube.com/@MrBeast/videos",
    ]

    create_viral_clip("picking_a_date_based_on_their_cooking_(mexican_food).mp3")

    # try:
    #     threads: list[Thread] = []
    #     for url in urls:
    #         thread = Thread(target=run_browser_instance, args=(url,))
    #         threads.append(thread)
    #         thread.start()

    #     for thread in threads:
    #         thread.join()
    # except Exception as e:
    #     print("Error: ", e)
    #     return

    # files_to_upload = os.listdir(OUT_DIR)
    # try:
    #     threads: list[Thread] = []
    #     for file in files_to_upload:
    #         thread = Thread(target=yt_shorts.upload, args=(file,))
    #         threads.append(thread)
    #         thread.start()

    #     for thread in threads:
    #         thread.join()
    # except Exception as e:
    #     print("Error: ", e)
    #     return

    # try:
    #     threads: list[Thread] = []
    #     for file in files_to_upload:
    #         thread = Thread(target=tiktok.upload, args=(file,))
    #         threads.append(thread)
    #         thread.start()

    #     for thread in threads:
    #         thread.join()
    # except Exception as e:
    #     print("Error: ", e)
    #     return

    print()
    log.info(f"Total time: {round(time.time() - start_time, 3)}")
    log.emphasize("Program finished successfully!")


if __name__ == "__main__":
    main()
