import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import time

from pytube import YouTube
from bs4 import BeautifulSoup
from openai import OpenAI

import re
from dataclasses import dataclass
from dotenv import load_dotenv

import pysrt
from moviepy.editor import (
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    clips_array,
)
from moviepy.config import change_settings
from moviepy.video.fx import resize
import moviepy.video.fx.all as vfx
import textwrap


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

print("--- Initializing Marketeer...")
load_dotenv()
ENGAGEMENT_THRESHOLD = 40
DEV = os.environ.get("ENV") == "development"

ffmpeg_path = "/usr/local/bin/ffmpeg" if DEV else "/usr/bin/ffmpeg"
change_settings({"FFMPEG_BINARY": ffmpeg_path})

if DEV:
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
else:
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions


@dataclass
class Engagement:
    seconds: int
    minutes: int
    engagement: int


class Marketeer:
    options = FirefoxOptions() if DEV else ChromeOptions()
    driver = None

    if DEV:
        options.binary_location = "/usr/bin/chromium-browser"
    # options.add_extension("adblock.crx")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if DEV:
        print("--- Using Firefox (DEV)\n")
        driver = webdriver.Firefox(options=options)
    else:
        print("--- Using Chrome (PROD)\n")
        chrome_driver_path = "/usr/bin/chromedriver"
        service = Service(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=options)

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.driver = self.driver
        self.transcript_folder = "transcripts"
        self.video_folder = "video"
        self.out_folder = "out"

    async def get_video_urls(self, channel_name):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._get_video_urls, channel_name
        )

    def _get_video_urls(self, channel_name):
        print("--- Fetching video URLs")
        self.driver.get(f"https://www.youtube.com/c/{channel_name}/videos")

        try:
            aria_label = "Reject all"

            button = self.driver.find_element(
                By.XPATH, f"//button[@aria-label='{aria_label}']"
            )
            button.click()
            print("--- Clicked button")
            self.driver.implicitly_wait(2)
        except Exception as e:
            print(e)

        print("--- Waited 1/2")
        self.driver.implicitly_wait(2)

        # scroll once to load more videos
        print("--- Scrolling to the bottom of the page")
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        self.driver.implicitly_wait(1)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        if len(soup.find_all("a", {"id": "thumbnail"})) <= 1:
            print("--- Initially, no videos found, scrolling and waiting")
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            self.driver.implicitly_wait(1)
            print("--- Scrolled and done waiting")

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        video_urls = []
        for link in soup.find_all("a", {"id": "thumbnail"}):
            href = link.get("href")
            if href is None:
                continue
            if href.startswith("/watch"):
                video_urls.append(f"https://www.youtube.com{href}")

        if len(video_urls) > 3:
            end = min(10, len(video_urls) - 1)
            video_urls = video_urls[2:end]

        print(len(video_urls), "videos found")
        return video_urls

    async def create_video_clip(self, url, start_time, end_time):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._create_video_clip, url, start_time, end_time
        )

    def _create_video_clip(self, url, start_time, end_time):
        yt = YouTube(url)
        filename = yt.title.replace(" ", "_").lower() + ".mp4"

        full_path = f"{self.video_folder}/{filename}"
        clip_filename = f"clip_{start_time}_{end_time}_{filename}"
        full_clip_path = f"{self.video_folder}/{clip_filename}"

        # if the video is not already downloaded, download it
        if not os.path.exists(full_clip_path):
            if not os.path.exists(full_path):
                print("--- Downloading video", filename)
                try:
                    yt.streams.filter(progressive=True, file_extension="mp4").order_by(
                        "resolution"
                    ).desc().first().download(
                        output_path=self.video_folder, filename=filename
                    )
                    print("--- Download done")
                except Exception as e:
                    print("--- Download failed")
                    print(e)

                    # since the video failed to download, we can't create a clip
                    return None

            print("--- Creating clip")
            try:
                with VideoFileClip(full_path) as video:
                    new = video.subclip(start_time, end_time)
                    new.write_videofile(
                        full_clip_path, codec="libx264", audio_codec="aac"
                    )
                    print("--- Clip done")
            except Exception as e:
                print("--- Clip failed -> aborting process")
                print(e)

                # since the clip failed, we can't transcribe it
                return None

            try:
                os.remove(full_path)
            except Exception as e:
                print(e)

        clip_filename = clip_filename[:-4]
        srt_path = f"{self.transcript_folder}/{clip_filename}.srt"
        title = "NO WAY THIS HAPPENED😱 (watch until the end)"

        if not os.path.exists(srt_path):
            transcript = self._get_video_transcript(full_clip_path)
            try:
                lines = transcript.split("\n")
                for line in lines:
                    if (
                        len(line.strip()) > 0
                        and len(line.strip()) < 25
                        and not line.strip().isdigit()
                    ):
                        title = line.strip()
                        title = title.split(". ")[0][:-1] + "👀"
                        break
            except Exception as e:
                print(e)
            with open(srt_path, "w") as file:
                file.write(transcript)
        else:
            print("--- Transcript already exists")
            with open(srt_path, "r") as file:
                lines = file.readlines()
                for line in lines:
                    if (
                        len(line.strip()) > 0
                        and len(line.strip()) < 25
                        and not line.strip().isdigit()
                    ):
                        title = line.strip()
                        title = title.split(". ")[0][:-1] + "👀"
                        break

        print("--- Creating subtitled video")
        video_path = f"{self.video_folder}/{clip_filename}.mp4"
        output_path = f"{self.out_folder}/{clip_filename}.mp4"

        self.create_video_with_subtitles(video_path, srt_path, output_path)
        print("--- Subtitled video done")

        successful_upload = not DEV

        # post to TikTok
        print(f"\n--- [TIKTOK]\nUploading {title} to TikTok\n({clip_filename})")

        # post to YouTube
        print(
            f"\n--- [YOUTUBE]\nUploading {title} to YouTube Shorts\n({clip_filename})"
        )

        # post to Instagram
        print(
            f"\n--- [INSTAGRAM]\nUploading {title} to Instagram Reels\n({clip_filename})"
        )

        # clean up
        if successful_upload:
            print("--- Removing video and transcript files")
            try:
                os.remove(f"{self.video_folder}/{clip_filename}.mp4")
                os.remove(f"{self.transcript_folder}/{clip_filename}.srt")
                os.remove(f"{self.out_folder}/{clip_filename}.mp4")
            except Exception as e:
                print(e)

        return full_clip_path

    async def get_video_engagement(self, url: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._get_video_engagement, url
        )

    def _get_video_engagement(self, url: str):
        try:
            print("--- Fetching video engagement")
            self.driver.get(url)
            print("--- Title:", self.driver.title)
            self.driver.implicitly_wait(2)
            print("--- Waited 1/2")

            try:
                aria_label = "Reject the use of cookies and other data for the purposes described"

                button = self.driver.find_element(
                    By.XPATH, f"//button[@aria-label='{aria_label}']"
                )
                button.click()
                print("--- Clicked button")
            except Exception as e:
                print(e)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            self.driver.implicitly_wait(2)
            print("--- Waited 2/2")

            duration = soup.find("span", class_="ytp-time-duration").text
            duration = sum(
                int(x) * 60**i for i, x in enumerate(reversed(duration.split(":")))
            )
            print("--- Duration:", duration, "seconds")

            wave = soup.find("path", class_="ytp-heat-map-path")

            if wave is None:
                print("--- No wave found")
                return None

            wave = wave.get("d")

            bezier_pattern = re.compile(
                r"C (\d+\.?\d*),(\d+\.?\d*) (\d+\.?\d*),(\d+\.?\d*) (\d+\.?\d*),(\d+\.?\d*)"
            )
            bezier_segments = bezier_pattern.findall(wave)

            width = 1000
            height = 100

            engagement: list[Engagement] = []

            for segment in bezier_segments:
                x1, y1, x2, y2, x3, y3 = [float(num) for num in segment]

                y1 = int(height - y1)
                y2 = int(height - y2)
                y3 = int(height - y3)

                if (
                    y1 > ENGAGEMENT_THRESHOLD
                    or y2 > ENGAGEMENT_THRESHOLD
                    or y3 > ENGAGEMENT_THRESHOLD
                ):
                    x, y = max([x1, x2, x3]), max([y1, y2, y3])
                    seconds = int(x * duration / width)

                    engagement.append(
                        Engagement(
                            seconds=seconds, minutes=int(seconds / 60), engagement=y
                        )
                    )

            return engagement

        except Exception as e:
            print(e)
            return None
        finally:
            self.driver.quit()

    def _get_video_transcript(self, filepath: str):
        if not os.path.exists(filepath):
            raise Exception(f"(404) Invalid filepath {filepath} does not exist")

        print("--- Transcribing", filepath)
        with open(filepath, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt",
                prompt="Create a transcript of this video, one word at a time. There should be a new line for each word with the exact time it was spoken.",
            )
            return transcript

    async def get_viral_sections(self, transcript: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self._get_viral_sections, transcript
        )

    def _get_viral_sections(self, transcript: str):
        prompt = f"""
            Given this transcript of a YouTube video: 
            How engaging and shareable is the following content? 
            Provide a very concise top 3 list of sections (a few sentences) 
            that could go viral on YouTube shorts and TikTok 
            \n\n'{transcript}'"""

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "assistant",
                    "content": "You are a highly intelligent and helpful assistant. You are a skilled marketer. You create tiktoks and youtube shorts with a high chance of going viral.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=256,
            frequency_penalty=0.0,
        )
        return response.choices[0].message.content

    def create_video_with_subtitles(self, video_path, srt_path, output_path):
        main_video = VideoFileClip(video_path)
        subway_surfers = VideoFileClip("video/subway_surfers.mp4").set_duration(
            main_video.duration
        )
        # subway_surfers = subway_surfers.set_audio(None)

        video = clips_array(
            [[main_video.resize(height=360)], [subway_surfers.resize(height=360)]]
        )

        subtitles = pysrt.open(srt_path)
        subtitle_clips = []
        for sub in subtitles:
            start_time = sub.start.ordinal / 1000
            end_time = sub.end.ordinal / 1000

            wrapped_text = textwrap.fill(sub.text, width=30)
            subtitle_clips.append(
                TextClip(
                    wrapped_text,
                    fontsize=40,
                    color="white",
                    font="Impact",
                    stroke_color="black",
                    stroke_width=2,
                    method="caption",
                    size=(video.w * 0.6, 300),
                )
                .set_position(("center", video.h / 2 - 50))
                .set_duration(end_time - start_time)
                .set_start(start_time)
            )

        video_with_subtitles = CompositeVideoClip([video] + subtitle_clips)

        final_video = video_with_subtitles.fx(resize.resize, height=720)
        final_video = video_with_subtitles.fx(vfx.speedx, 1.1)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
        final_video.close()
        print("--- Sleeping for 2 seconds")
        time.sleep(2)
        print("--- Subtitled video created")

        return output_path


async def main():
    marketeer = Marketeer()

    urls = await marketeer.get_video_urls("BetaSquad")
    if len(urls) == 0:
        print("--- No videos found, returning...")
        return

    urls = urls[:3]

    tasks = []
    for url in urls:
        tasks.append(marketeer.create_video_clip(url, 150, 180))

    await asyncio.gather(*tasks)

    print("--- Done")


if __name__ == "__main__":
    asyncio.run(main())
