import logging
import asyncio
import time
import yt_dlp
import whisper
from telegram.ext import Application, MessageHandler, filters
import os
import traceback
from pydub import AudioSegment
from pydub.silence import detect_silence
import requests
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()

bot_token = ''
whisper_model = os.environ.get('WHISPER_MODEL') or 'tiny'
SUB_LANG = os.environ.get('SUB_LANG')




# TODO update code:
async def message_handler(update, context):
    message = update.message
    user = update.message.from_user
    url = message.text
    filename = os.path.join('voices', f"{user.id}-{message.id}.mp3")
    # user = update.message.from_user.username or update.message.from_user.first_name

    if any(domain in message.text for domain in ['youtube.com', 'youtu.be', 'youtube.com/shorts']):
        await download_link(url, filename, update)

    # elif message.media:
    #     await download_audio(update, context)

    else:
        await update.message.reply_text("Я понимаю только ссылки на YouTube видео или аудиосообщения")

async def voice_handler(update, context):
    message = update.message
    user = update.message.from_user
    userid = user.id
    f_name = f"{userid}-{message.id}.ogg"

    audio_file = await save_voice(update, context, f_name)

    await update.message.reply_text((
        f"Аудиофайл {f_name} успешно сохранен.\n"
        "Начинаю транскрипцию. \n"
        "Ожидайте ответа"
    ))

    asyncio.create_task(trnscrb(userid, f_name, audio_file))


async def save_voice(update, context, filename):
    file_id = update.message.voice.file_id
    # Download voice message from Telegram servers:
    file = await context.bot.get_file(file_id)
    os.makedirs('voices', exist_ok=True)
    voice_path = os.path.join(
        'voices',
        filename
    )
    audio_file = await file.download_to_drive(voice_path)
    return audio_file

async def download_audio(update, context):
    # user = update.message.from_user
    # message = update.message

    f_name = f"{user.id}-{message.id}.ogg"
    await asyncio.sleep(2)
    await event.respond("Загрузка больших файлов может занять некоторое время.\n")
    # await context.message.reply_text

    await bot.download_media(message.audio if message.audio else message.voice, f_name)

    await event.respond("Аудиофайл " + f_name + " успешно сохранен.\n"
                                                "Начинаю транскрипцию. \n"
                                                "Ожидайте ответа")

    result = await trnscrb(event, f_name)


async def download_link(url, filename, update):
    answer = ''
    userid = update.message.from_user.id
    # await con.respond("Начинаю загрузку файла")
    await update.message.reply_text("Начинаю загрузку файла")

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
    video_title = info.get('title', None)

    if SUB_LANG and info['automatic_captions'][SUB_LANG]:
        for s_url in info['automatic_captions'][SUB_LANG]:
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
                await get_answer(update, answer)
    else:
        # await event.respond('Эх, не повезло, субтитры отсутствуют!')
        await update.message.reply_text('Эх, не повезло, субтитры отсутствуют!')


        update.message.reply_text(f"Загружаю файл {video_title}")

        ydl_opts = {
            'format': 'worstaudio',
            'outtmpl': filename
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        await update.message.reply_text(f"Файл {filename} сохранен")

        asyncio.create_task(trnscrb(userid, filename, audio_file=None))



# Транскрипция
async def trnscrb(userid, f_name, audio_file):
    Tn = time.time()
    if audio_file is None:
        audio_file = f_name
    t = 10 * 60000
    audio = AudioSegment.from_file(audio_file).set_frame_rate(44100)


    # Проверяем длину аудиофайла
    if len(audio) <= t:
        print("Less than 10 minutes, transcribe with + '_tmp.mp3'out splitting")
        await asyncio.create_task(async_segment_export(audio, f_name + '_tmp.mp3'))
        answ = await asyncio.create_task(async_trans(f_name + '_tmp.mp3'))
        if answ != '':
            await get_answer(userid, answ)

    else:
        print("More than 10 minutes, split and transcribe")
        parts = int(len(audio) / t)
        print('len(audio) =', len(audio), 'parts =', parts)
        # Разбиваем на части
        start = 0
        print('Detecting silence...')
        chunks = detect_silence(audio, min_silence_len=600, silence_thresh=-25, seek_step=100)
        print('Got chunks:', chunks, '\n')
        try:
            tasks = []
            for i in range(parts):
                print('i =', i)
                target_chunk = get_closest_chunk((i + 1) * t, chunks)
                print(target_chunk, '\n')
                end = target_chunk[1]
                segment = audio[start:end]
                task = asyncio.create_task(async_segment_export(segment, f_name + '_part{}.mp3'.format(i)))
                tasks.append(task)
                start = target_chunk[1] - 300  # начало 2й части
            segment = audio[start:]
            tasks.append(asyncio.create_task(async_segment_export(segment, f_name + '_part{}.mp3'.format(parts))))
            await asyncio.gather(*tasks)

            tasks = []
            for i in range(parts + 1):
                print(f'Транскрибирую {i}ю часть')
                task = asyncio.ensure_future(async_trans(f_name + '_part{}.mp3'.format(i)))
                tasks.append(task)

            for i in range(parts + 1):
                answ = await tasks[i]
                if answ != '':
                    await get_answer(userid, answ)



        except Exception as e:
            print(e, traceback.format_exc())


    os.remove(audio_file)
    print(time.time()-Tn)

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

async def get_answer(userid, answer):
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
            await application.bot.send_message(chat_id=userid, text=answer[i:i + k])
        await application.bot.send_message(chat_id=userid, text=answer[i + k:len(answer)])
    else:
        await application.bot.send_message(chat_id=userid, text=answer)

async def load_model():
  loop = asyncio.get_event_loop()
  model = await loop.run_in_executor(None, whisper.load_model, "base")
  return model

async def async_segment_export(segment, f_name):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: segment.export(f_name, format="mp3", bitrate="64k"))

async def async_trans(f_name):
    loop = asyncio.get_event_loop()
    model = await load_model()
    result = await loop.run_in_executor(None, lambda: model.transcribe(f_name, fp16=False)['text'])
    os.remove(f_name)
    return result


if __name__ == '__main__':
     application = Application.builder().token(bot_token).build()
     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
     application.add_handler(MessageHandler(filters.VOICE, voice_handler))
     application.run_polling()