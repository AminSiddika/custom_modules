import os
import requests
import random
import string
import asyncio
import shutil
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from utils.scripts import progress  # Import the progress utility
from utils.misc import modules_help, prefix


# Common headers
headers = {
    'User-Agent': "Ktor client",
    'Connection': "Keep-Alive",
    'Accept': "application/json",
    'Accept-Encoding': "gzip",
    'X-App-Id': "22120300515132",
    'X-App-Token': "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjk3MTk2NzA1MzR9.OXR7o3tomo_e76t1cDRu1xa7lABl8y9-LvKSSzd24Ck",
    'Accept-Charset': "UTF-8",
    'Content-Type': "application/json; charset=utf-8"
}

IMAGE_DIR = "images"
VIDEO_DIR = "videos"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

def get_random_filename(extension):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8)) + extension

def get_temp_dir(base_dir):
    temp_dir = os.path.join(base_dir, ''.join(random.choices(string.ascii_letters + string.digits, k=8)))
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


async def download_file(url, filename, processing_message, block_size=1024*1024):  # Increased block size to 1MB
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0

        with open(filename, 'wb') as file:
            for data in response.iter_content(block_size):
                downloaded_size += len(data)
                file.write(data)
                if total_size > 0:
                    await processing_message.edit(f"Downloading: {filename}\nProgress: {downloaded_size * 100 / total_size:.2f}%", parse_mode=enums.ParseMode.HTML)
        
        await processing_message.edit(f"Download completed: {filename}", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await processing_message.edit(f"Failed to download the media. Please try again later.", parse_mode=enums.ParseMode.HTML)
        raise e


async def download_instagram_media(data, processing_message, temp_dir):
    media_files = []
    media_type = data.get('__type', '')

    if media_type == 'GraphImage':
        items = data.get('items', [])
        best_image = next(
            (img for img in items if img['width'] == 1080 and img['height'] == 1350),
            None
        )
        if not best_image:
            best_image = next(
                (img for img in items if img['width'] == 1080 and img['height'] == 1080),
                None
            )
        if not best_image:
            best_image = max(
                (img for img in items if img['width'] >= 1024 and img['height'] >= 1024),
                key=lambda x: (x['width'], x['height']),
                default=None
            )
        if best_image:
            image_url = best_image['url']
            filename = os.path.join(temp_dir, get_random_filename('.jpg'))
            await download_file(image_url, filename, processing_message)
            media_files.append(filename)
    elif media_type == 'GraphVideo':
        video_url = data['video_url']
        filename = os.path.join(temp_dir, get_random_filename('.mp4'))
        await download_file(video_url, filename, processing_message)
        media_files.append(filename)
    elif media_type == 'GraphSidecar':
        for idx, item in enumerate(data['items']):
            sub_type = item.get('__type', '')
            if sub_type == 'GraphImage':
                best_image = next(
                    (img for img in item['items'] if img['width'] == 1080 and img['height'] == 1350),
                    None
                )
                if not best_image:
                    best_image = next(
                        (img for img in item['items'] if img['width'] == 1080 and img['height'] == 1080),
                        None
                    )
                if not best_image:
                    best_image = max(
                        (img for img in item['items'] if img['width'] >= 1024 and img['height'] >= 1024),
                        key=lambda x: (x['width'], x['height']),
                        default=None
                    )
                if best_image:
                    image_url = best_image['url']
                    filename = os.path.join(temp_dir, f'instagram_image_{idx + 1}.jpg')
                    await download_file(image_url, filename, processing_message)
                    media_files.append(filename)
            elif sub_type == 'GraphVideo':
                video_url = item['video_url']
                filename = os.path.join(temp_dir, f'instagram_video_{idx + 1}.mp4')
                await download_file(video_url, filename, processing_message)
                media_files.append(filename)

    return media_files


async def fetch_and_download(url, message):
    temp_dir = get_temp_dir(VIDEO_DIR if "facebook.com" in url or "tiktok.com" in url or ("instagram.com" in url and "video_url" in url) else IMAGE_DIR)
    
    try:
        processing_message = await message.reply("Processing your request...")

        if "facebook.com" in url:
            api_url = "https://api.snapx.info/v1/fb"
            params = {'url': url}
            platform_name = 'facebook'
        elif "tiktok.com" in url:
            api_url = "https://api.snapx.info/v1/tiktok"
            params = {'url': url, 'is_embed': "true"}
            platform_name = 'tiktok'
        elif "instagram.com" in url:
            api_url = "https://api.snapx.info/v1/instagram"
            params = {'url': url}
            platform_name = 'instagram'
        else:
            await processing_message.edit("Unsupported URL", parse_mode=enums.ParseMode.HTML)
            return

        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        response_json = response.json()

        if platform_name == 'facebook':
            media_url = response_json['data'].get('hd') or response_json['data'].get('sd')
            if not media_url:
                await processing_message.edit("No suitable media available for the provided URL", parse_mode=enums.ParseMode.HTML)
                return
            video_filename = os.path.join(temp_dir, get_random_filename('.mp4'))
            await download_file(media_url, video_filename, processing_message)
            media_files = [video_filename]
        elif platform_name == 'tiktok':
            media_url = response_json['video_link']
            filename = os.path.join(temp_dir, get_random_filename('.mp4'))
            await download_file(media_url, filename, processing_message)
            media_files = [filename]
        elif platform_name == 'instagram':
            media_data = response_json['data']
            if not media_data:
                await processing_message.edit("No media available for the provided URL", parse_mode=enums.ParseMode.HTML)
                return
            media_files = await download_instagram_media(media_data, processing_message, temp_dir)
        
        if not media_files:
            await processing_message.edit("No media could be downloaded.", parse_mode=enums.ParseMode.HTML)
            return

        await upload_files(media_files, processing_message)
    except Exception as e:
        await processing_message.edit("Failed to fetch or process the media. Please try again later.", parse_mode=enums.ParseMode.HTML)
        raise e
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


async def upload_files(files, processing_message):
    try:
        if len(files) > 1:
            # Upload files as an album
            await processing_message._client.send_media_group(
                processing_message.chat.id,
                files,
                progress=progress,  # Use the progress utility
                progress_args=(processing_message, "Uploading album"),
            )
        else:
            # Upload single file
            file = files[0]
            await processing_message._client.send_document(
                processing_message.chat.id,
                file,
                supports_streaming=True,
                progress=progress,  # Use the progress utility
                progress_args=(processing_message, f"Uploading: {file}"),
            )
        
        # Clean up local files after uploading
        for file in files:
            os.remove(file)
        
        await processing_message.delete()
    except Exception as e:
        await processing_message.edit("Failed to upload the media. Please try again later.", parse_mode=enums.ParseMode.HTML)
        raise e


@Client.on_message(filters.command("dlmedia", prefix) & filters.me)
async def dlmedia(client: Client, message: Message):
    urls = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    
    if not urls and message.reply_to_message:
        urls = message.reply_to_message.text
    
    if not urls:
        await message.edit("Please provide one or more media URLs.", parse_mode=enums.ParseMode.HTML)
        return

    url_list = urls.split()
    await message.delete()
    await asyncio.gather(*[fetch_and_download(url, message) for url in url_list])


modules_help["dlmedia"] = {
    "dlmedia [url]": "Download and upload media from Facebook, TikTok, or Instagram by URL. Supports multiple URLs separated by space."
}
