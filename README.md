# Transcriber
Простой бот телеграм. Принимает голосовые и аудиосообщения, после чего транскрибирует их и выдает текст пользователю. Так же принимает ссылки с ютуба, вытаскивает аудио и транскрибирует его, либо скачивает автоматические субтитры, выдает пользователю текст.
Пока не обрабатывает "кружочки" с телеграма, нет многопоточности. 
Транскрибирует посредством Whisper от OpenAI.
Как установить whisper  https://github.com/openai/whisper
До начала работы с Telethon необходимо получить собственный API ID и Hash. Это можно сделать пройдя по ссылке https://my.telegram.org/auth?to=apps, указав номер телефона привязанный к профилю, и заполнив App title и Short name. Platform - можно выбрать “Other (specify in description)”. Остальные параметры можно оставить пустыми. 
остальные модули через pip install
