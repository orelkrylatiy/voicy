# Voicy

Telegram-бот без Mini App: голосовые и аудиофайлы распознаются через OpenAI, обычные текстовые сообщения получают короткие ответы через [Humanizer Framework](https://github.com/orelkrylatiy/humanizer-framework). Все ответы отправляются обычным текстом, без Markdown/HTML.

## Что делает

- Голосовые, `audio` и аудио-документы: Telegram → OpenAI `gpt-transcribe` → **опциональная** редактура через Humanizer → текст в Telegram.
- Обычный текст: `CommunicationFramework.generate()` → ответ пользователю. Короткая история изолирована по чату и пользователю, хранится только в памяти.
- Подпись к аудио `Имена: Анна, Максим` передаётся как подсказка распознавания и редактору.
- Команды `/start` и `/help`. Никакого Mini App, Nginx, веб-сервера или инлайн-запросов.

## Установка

Требуется Python **3.11+**, `git` и токен Telegram-бота.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполните .env своими значениями; не публикуйте их
python transcribe_bot.py
```

В `.env` обязательно задайте `TELEGRAM_TRANSCRIBE_BOT_TOKEN`, реальные `TELEGRAM_TRANSCRIBE_OWNER_IDS` и `OPENAI_API_KEY` (если распознавание включено). `ZAI_API_KEY` опционален. Когда он есть, режим `HUMANIZER_BACKEND=auto` отдаёт текстовую генерацию нативной цепочке Humanizer; в ином случае используется прямой HTTP-адаптер OpenAI **внутри** `CommunicationFramework`, без OpenCode CLI. Для собственного порядка fallback-провайдеров задайте `HUMANIZER_BACKEND=framework` и настройте провайдеры как в upstream Humanizer.

### Настройки

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `TRANSCRIBE_MODE` | `auto` | `auto`: OpenAI только при аудио; `off`: запретить распознавание (для text-only режима) |
| `TRANSCRIBE_MODEL` | `gpt-transcribe` | Модель OpenAI `/v1/audio/transcriptions` |
| `TRANSCRIBE_EDIT` | `humanizer` | `humanizer`: лёгкая редактура; `raw`: отправлять исходную расшифровку |
| `HUMANIZER_BACKEND` | `auto` | `auto`, `framework` или `openai` |
| `HUMANIZER_OPENAI_MODEL` | `gpt-4.1-mini` | Модель для текстового адаптера при backend=`openai` или автоматическом выборе |
| `TELEGRAM_TRANSCRIBE_OWNER_IDS` | пусто | CSV идентификаторов разрешённых пользователей |
| `TELEGRAM_TRANSCRIBE_ALLOW_PUBLIC` | `false` | Разрешить всем использовать платные вызовы, **только если это намеренно** |
| `TELEGRAM_TRANSCRIBE_TRANSPORT` | `bot_api` | `bot_api` или `mtproto` |

При `TRANSCRIBE_MODE=off` ключ OpenAI необязателен, но для текстовых ответов должен работать выбранный провайдер Humanizer. Если редактор Humanizer недоступен, бот возвращает исходную расшифровку, а текстовые вопросы получают предупреждение. Обработка расшифровок вызывает провайдер, настроенный **в Humanizer**, напрямую: его `chat_reply`-валидатор ограничивает длину ответа несколькими сотнями символов и не подходит для дословных длинных расшифровок. Ответы на текстовые сообщения всегда проходят через `generate()` с политиками и проверками Humanizer.

### Опциональный MTProto

Для существующей конфигурации с Telethon можно оставить режим `mtproto`:

```bash
pip install -r requirements-mtproto.txt
# .env: TELEGRAM_TRANSCRIBE_TRANSPORT=mtproto
# .env: TRANSCRIBE_TG_API_ID=... и TRANSCRIBE_TG_API_HASH=...
python transcribe_bot.py
```

Сессия создаётся локально (`bot-mtproto.session`) и **никогда не должна попадать в Git**. `mtproto` не включает Mini App и не запускает HTTP-сервер. Если выбран `bot_api`, Telegram ограничивает скачивание через `getFile` файлами до 20 МБ. Бот проверяет размер до вызова OpenAI.

## Тесты

```bash
python -m unittest discover -s tests -v
```

Unit-тесты не вызывают Telegram, OpenAI или Humanizer по сети. Сквозную проверку с настоящим ботом и API-ключами проведите самостоятельно в приватном чате: в этой среде реальное аудио и действующие аккаунты не использовались.

## Безопасность

В исходном архиве присутствовали `.env`, `telegram-app.env` и `.session` — их **нет** в этом репозитории. Если архив передавался третьим лицам, замените Telegram Bot Token и OpenAI API Key, а также Telegram API-учётные данные по необходимости; завершите старую MTProto-сессию. Не используйте прежние секреты в публичных настройках или логах. В Git находится только `.env.example` с пустыми значениями. Humanizer подключён зависимостью с фиксированным commit SHA, а не скопированным исходным кодом.
