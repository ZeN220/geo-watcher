# geo-watcher

Следит за тем, что видят сервисы на нодах Remnawave, и пишет в Telegram, когда
что-то изменилось: Google стал показывать другую страну, Netflix начал
блокировать, Reddit перестал открываться.

Панель умеет запускать [geocheck](https://github.com/remnawave/geocheck) на
ноде — этим и пользуемся. Watcher раз в час обходит ноды, сравнивает отчёт с
прошлым прогоном и присылает только разницу.

![Уведомление в Telegram](assets/notification.png)

## CLI

```
usage: geo-watcher [-h] [--config PATH] [--once] [--version]

options:
  -h, --help     show this help message and exit
  --config PATH  path to the TOML config (default: config.toml)
  --once         run a single pass and exit instead of looping forever
  --version      show program's version number and exit
```

Без флагов команда работает вечным циклом: прогон, пауза `watcher.interval`,
снова прогон. Так её и гоняют в Docker.

```bash
uv run geo-watcher
```

`--once` делает ровно один обход нод и выходит. Это форма для cron и systemd
timer, а ещё для первого запуска, когда хочется просто посмотреть на вывод.

```bash
uv run geo-watcher --once
```

Конфиг ищется как `config.toml` в текущей папке. Другой путь — через `--config`,
им же удобно держать рядом несколько панелей.

```bash
uv run geo-watcher --config /etc/geo-watcher/prod.toml
```
