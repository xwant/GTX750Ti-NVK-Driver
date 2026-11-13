# GTX 750 Ti / GM107 — NVK driver experiment (v0.1)

Экспериментальная модификация **Mesa NVK** для NVIDIA GeForce GTX 750 Ti (Maxwell GM107), ориентированная на управление кэшем командных буферов. **Не является готовым ускоренным драйвером. Прирост FPS и совместимость Vulkan с GM107 не подтверждены.**

> Основа: Mesa `26.2.6`, commit `8e87a503ebd91408c88596d1b9eeb5f4c0b2088d`.
> Изменения: [`gm107-command-cache.patch`](gm107-command-cache.patch). Полная техническая документация: [`README_RU.md`](README_RU.md).

## Что делает v0.1

Добавляет параметр `NVK_GM107_CMD_CACHE_LIMIT_KIB` (например, `256`): ограничивает кэш **уже освобождённых** LOCAL-capable командных блоков размером 64 KiB в одном Vulkan command pool на чипсете GM107 (`0x117`). Без параметра сохраняется исходная политика. Это **не** глобальный лимит VRAM. Патч может ухудшить производительность, если приведёт к дополнительным выделениям памяти.

## Текущий статус (9 ноября 2026)

| Проверка | Статус |
|---|---|
| Патч исходников Mesa | Готов |
| Сборка NVK в изолированной среде | Успех |
| CPU-тесты Nouveau (архив) | 11/11 PASS |
| Сборка двух вариантов на CachyOS (по выполненным пользователем тестам) | Успех |
| CPU-тесты на CachyOS (по выполненным пользователем тестам) | Base 4/4, patched 11/11 |
| Загрузка ядра Nouveau на GTX 750 Ti | Подтверждена (DRM обнаружил 2048 MiB VRAM) |
| Стабильность KDE Wayland на Nouveau | **Не подтверждена:** чёрное мерцание |
| Аппаратный запуск пользовательского NVK через `vulkaninfo` | **Не проверен** |
| FPS/frametime/эффект ограничения кэша | **Не измерен** |

В журнале Nouveau обнаружены ошибки `gr: DATA_ERROR [INVALID_VALUE]` в канале Discord и сообщения KWin об отсутствии atomic mode-setting; точную причину мерцания пока не установили. См. [`docs/DEVLOG.md`](docs/DEVLOG.md).

## Структура

- `gm107-command-cache.patch` — фактическое изменение исходников NVK (патч к upstream Mesa).
- `build-cachyos.sh` — воспроизводимая локальная сборка исходного и изменённого NVK.
- `bench/` — микротест Vulkan и инструменты анализа frametime.
- `logs/` — журналы из исходного переданного архива.
- `RESULTS.json` — **исторический снимок** результатов до аппаратных загрузок (его поля `hardware_tests` / `cachyos_wsi_build` устарели); актуальное состояние описано здесь и в `docs/DEVLOG.md`.
- `SHA256SUMS` — проверки **исходных файлов** архива; новые файлы `README.md`, `docs/`, `.gitignore` не включены в этот список.

## Сборка

```bash
bash build-cachyos.sh
```

Скрипт собирает изолированные варианты без установки драйвера в систему. **Не меняйте рабочий NVIDIA DKMS или загрузчик ради выполнения скрипта.** Для использования NVK необходим совместимый kernel driver Nouveau и подходящая тестовая загрузка. Отдельный экспериментальный Limine boot entry уже применялся на тестовом ПК; файлы `/boot` и системные конфигурации в этот репозиторий намеренно не включаются.

## Участие и ведение журнала

Каждый воспроизводимый результат фиксируем в [`docs/DEVLOG.md`](docs/DEVLOG.md), отдельные задачи — в GitHub Issues после создания репозитория. Для новых результатов указываем kernel version, используемый ICD, способ воспроизведения, kernel/KWin logs, итоги и откат. Не публикуем приватные токены, домашние пути с персональными данными, произвольные дампы памяти.

Лицензии исходных частей определяются их SPDX/лицензиями; Mesa распространяется по своим лицензиям. Этот репозиторий содержит **патч**, а не копию всего дерева Mesa.

## H3 dataset-v1 (13 November 2026)

Offline dataset/import/validation and bounded tree research: [dataset](docs/H3_DATASET.md), [architecture](docs/H3_ARCHITECTURE.md), [validation](docs/H3_VALIDATION.md), [roadmap](docs/H3_ROADMAP.md), [CachyOS capture](docs/H3_CACHYOS.md). Run `python3 -m unittest discover -s h3/tests -v`. H3 is not integrated into NVK. Synthetic examples are explicitly labelled; no GPU speedup is claimed. Use dataset CLI instead of the permissive Phase-0 prototype for new evidence preparation.

## H3.3 experimental diagnostics and CI

This branch adds opt-in real NIR/NAK compiler telemetry, not H3 runtime policy selection. See [H3_TELEMETRY](docs/H3_TELEMETRY.md), [CPU/compiler validation](docs/H3_VALIDATION.md) and the unified [hardware handoff](docs/HARDWARE_VALIDATION.md). The independent H6 percent simulator lives on `experiment/h6-percent-simulation`; it does not control hardware.
