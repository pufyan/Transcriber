from telethon import TelegramClient, events
import logging
import asyncio
import yt_dlp
import whisper
import os
from pydub import AudioSegment
from pydub.silence import detect_silence
import requests
import json

# Подставляем собственные значения из `my.telegram.org`
api_id =
api_hash = '
bot_token =

bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

model = whisper.load_model("base")

async def download_audio(event):
    message = event.message
    user = event.sender
    f_name = f"{user.id}-{message.id}.ogg"
    await asyncio.sleep(2)
    await event.respond("Загрузка больших файлов может занять некоторое время.\n")

    await bot.download_media(message.audio if message.audio else message.voice, f_name)

    await event.respond("Аудиофайл "+f_name+" успешно сохранен.\n"
                                        "Начинаю транскрипцию. \n"
                                        "Ожидайте ответа")

    result = await trnscrb(event, f_name)

async def download_link(event):
    message = event.message
    user = event.sender
    url = event.message.text
    answer = ''

    await event.respond("Начинаю загрузку файла")

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
    video_title = info.get('title', None)

    if info['automatic_captions']['ru']:
     for s_url in info['automatic_captions']['ru']:
        if s_url['ext'] == 'json3':
            response = requests.get(s_url['url'])
            json_data = response.json()
            for i in json_data['events']:
                for j in i:
                    if j == 'segs':
                        for k in i[j]:
                            for l in k:
                                if l == 'utf8':
                                    answer = answer + k['utf8']
            answer = answer.replace("\n", " ")
            await get_answer(event, answer)
    else:
        await event.respond('Эх, не повезло, субтитры отсутствуют!')
        await asyncio.sleep(2)
        await event.respond(f"Загружаю файл {video_title}")

        ydl_opts = {'format': 'worstaudio',
                    'outtmpl': f"{user.id}-{message.id}.mp3"}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await event.reply(f"Файл {user.id}-{message.id}.mp3 сохранен")

        result = await trnscrb(event, f"{user.id}-{message.id}.mp3")



async def get_answer(event, answer):
    if len(answer) > 4096:
        n = int(len(answer) / 4096)
        k = 0
        i = 0
        for x in range(0, n):
            i = i + k
            j = i + 4096
            k = 4096
            while j > i:
                if answer[j] == ' ':
                    break
                j -= 1
                k -= 1

            await event.respond(answer[i:i + k])

        await event.respond(answer[i + k:len(answer)])

    else:
        await event.respond(answer)

#Транскрипция
async def trnscrb(event, audio_file):

    message = event.message
    user = event.sender
    f_name = f"{user.id}-{message.id}"
    t = 10 * 60000
    audio = AudioSegment.from_file(audio_file).set_frame_rate(22050)

#Проверяем длину аудиофайла
    if len(audio) <= t:
        # 10 минут или меньше, сохраняем как есть
        audio.export(f_name+'_tmp.mp3', format="mp3", bitrate="64k")
        result = model.transcribe(f_name+'_tmp.mp3', fp16=False)
        #print(result['text'])
        await get_answer(event, result['text'])
        os.remove(f_name+'_tmp.mp3')
    else:
        part = int(len(audio) / t)
        print(len(audio), 'часть =', part)
        # Разбиваем на части
        start = 0
        chunks = detect_silence(audio, min_silence_len=600, silence_thresh=-25)
        print(len(audio), '\n')
        print(chunks, '\n')
        try:
            for i in range(0, part):
                target_chunk = get_closest_chunk((i + 1) * t, chunks)
                print(target_chunk, '\n')
                end = target_chunk[1]
                segment = audio[start:end]
                segment.export(f_name+'_part{}.mp3'.format(i), format="mp3", bitrate="64k")
                result = model.transcribe(f_name+'_part{}.mp3'.format(i), fp16=False)
                prmp = prmp + ' ' + result['text']
                await get_answer(event, result['text'])
                start = target_chunk[1] - 300 # начало 2й части
                os.remove(f_name+'_part{}.mp3'.format(i))

            segment = audio[start:]
            segment.export(f_name+'_part{}.mp3'.format(part), format="mp3", bitrate="64k")
            result = model.transcribe(f_name + '_part{}.mp3'.format(part), fp16=False)

            await get_answer(event, result['text'])
            os.remove(f_name + '_part{}.mp3'.format(part))
        except:
            await event.respond("Что-то пошло не так")
    os.remove(audio_file)

# Находим чанк максимально близкий к 10 минутам
def get_closest_chunk(time, chunks):
    closest = []
    min_diff = float("inf")

    for start, end in chunks:

        diff = abs(end - time)
        if diff < min_diff:
            min_diff = diff
            closest = [start, end]

    return closest


@bot.on(events.NewMessage)
async def echo_all(event):

    if any(domain in event.message.text for domain in ['youtube.com', 'youtu.be', 'youtube.com/shorts']):
        await download_link(event)

    elif event.message.media:
        await download_audio(event)

bot.run_until_disconnected()