# geo-watcher

Следит за тем, что видят сервисы на нодах Remnawave, и пишет в Telegram, когда
что-то изменилось: Google стал показывать другую страну, Netflix начал
блокировать, ChatGPT перестал открываться.

Панель умеет запускать [geocheck](https://github.com/remnawave/geocheck) на
ноде — этим и пользуемся. Watcher раз в час обходит ноды, сравнивает отчёт с
прошлым прогоном и присылает только разницу.

```
🌍 🇳🇱 Amsterdam-1: изменились проверки

• Google (services, ipv4): NL → RU
• Google Search captcha (services, ipv4): no → yes
• ChatGPT (web) (stash): available → blocked
```

## Как это работает

1. `GET /api/nodes` — берём ноды, которые подключены и не отключены.
2. `POST /api/connections/geocheck/{nodeUuid}` — ставим задачу geocheck.
   Клиент сам опрашивает её до результата (`wait_geocheck_by_node`).
3. Из отчёта достаём значения проверок: страну по каждому сервису и базе GeoIP,
   доступность (`available` / `restricted` / `blocked`).
4. Сравниваем с прошлым прогоном из `state.json`. Есть разница — летит
   уведомление, нет — тишина.

На старте watcher делает пробный запрос к `/api/nodes`. Если токен просрочен
или у него нет прав на чтение нод, процесс сразу завершится с понятным
сообщением, а не упадёт на первой ноде через час. Права на сам geocheck так не
проверить: панель сообщает о них, только когда задача уже поставлена.

Первый прогон ничего не отправляет: ему не с чем сравнивать, он только
запоминает текущее состояние. Проверки, ответившие ошибкой, пропускаются —
иначе каждый сетевой сбой давал бы «available → error» и обратно.

## Требования

- Python 3.13+
- Remnawave с API-токеном
- бот в Telegram (уведомления можно и не включать — тогда всё пишется в лог)

## Быстрый старт

```bash
git clone <your-repo-url>
cd geo-watcher

uv sync

cp config.example.toml config.toml
# вписать base_url и token от панели, bot_token и chat_id для Telegram

uv run geo-watcher --once   # один прогон, посмотреть что выйдет
uv run geo-watcher          # в цикле, раз в watcher.interval секунд
```

### Docker

`state_file` должен указывать внутрь примонтированной папки, иначе состояние
не переживёт перезапуск контейнера:

```toml
[watcher]
state_file = "data/state.json"
```

```bash
docker compose up -d --build
docker compose logs -f
```

## Конфигурация

Полный пример — в [`config.example.toml`](config.example.toml).

### `[remnawave]`

| Ключ | Что это |
| --- | --- |
| `base_url` | адрес панели |
| `token` | API-токен |

### `[telegram]`

Секции может не быть — тогда уведомления выключены, всё идёт только в лог.

| Ключ | Что это |
| --- | --- |
| `bot_token` | токен бота от @BotFather |
| `chat_id` | id чата, группы или канала (`-100…`), либо `"@channel"` |
| `message_thread_id` | id топика, если группа с темами; необязательный |

### `[watcher]`

| Ключ | По умолчанию | Что это |
| --- | --- | --- |
| `interval` | `3600` | пауза между прогонами, секунд |
| `concurrency` | `3` | сколько нод проверять одновременно |
| `sources` | `["services", "geoip", "stash"]` | что брать из отчёта |
| `state_file` | `"state.json"` | где хранится прошлый прогон |

Значения `sources`:

| Источник | Что даёт | Пример значения |
| --- | --- | --- |
| `services` | страна и доступность у Google, YouTube, Netflix, Steam и прочих | `RU`, `yes` |
| `geoip` | страна по базам GeoIP | `NL` |
| `stash` | доступность сервисов: Netflix, ChatGPT, YouTube Premium | `restricted (US)` |
| `cdn` | локация edge-узла CDN, а не страна IP; по умолчанию выключен | `DE` |

Опечатка в названии источника роняет запуск сразу, с перечислением
допустимых значений.

## Разработка

```bash
uv sync
uv run pre-commit install

uv run pytest
uv run ruff format .
uv run ruff check .
uv run mypy src
```

Линтинг и тесты гоняются в GitHub Actions на каждый push. По тегу вида `0.1.0`
собирается образ и уходит в ghcr.io.

## Структура

```
src/geo_watcher/
├── __main__.py     # CLI, цикл прогонов
├── config.py       # конфиг из TOML
├── remnawave.py    # запуск geocheck на ноде
├── report.py       # схема отчёта geocheck и разбор значений
├── analysis.py     # сравнение с прошлым прогоном
├── state.py        # state.json
├── telegram.py     # отправка уведомлений
└── watcher.py      # обход нод и вывод в лог
```

### Пара решений, которые стоит знать

**Отчёт geocheck типизирован частично.** Панель отдаёт его как есть, схемы у
неё нет. Мы описали только секции `geo` и `stash_checks`, остальные
(`identity`, `reputation`, `connectivity`, …) adaptix пропускает. Неизвестные
значения `kind` и `state` не роняют разбор, а сваливаются в `UNKNOWN`.

**Состояние — плоский словарь** `{node_uuid: {ключ проверки: значение}}`.
Проверка, пропущенная в этом прогоне из-за ошибки, не удаляется из состояния,
иначе следующий удачный ответ выглядел бы как первое появление и изменение
осталось бы незамеченным.

**Таймауты geocheck — константы в `remnawave.py`**, а не в конфиге: опрос раз в
`POLL_INTERVAL` секунд, задача ждётся `JOB_TIMEOUT` секунд. Если ноды медленные
и задачи не успевают, крутить нужно именно их.
