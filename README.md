# clever_battle_bot
Бот для боев умов в клевере. С консольным интерфейсом и поддержкой безлимитного кол-ва аккаунтов.
# Установка из предсобранных бинарников
0. Скачать бинарник для вашей системы и архитектуры (если нет, см. установка из исходников) [отсюда](https://github.com/TaizoGem/clever_battle_bot/releases/latest)
# Установка из исходников
0. Установить python:
 - [с оф. сайта](https://python.org)
 - из пакетного менеджера:
 ```bash
 # arch/manjaro
 pacman -S python3
 
 # ubuntu/debian
 apt install python
 ```
1. Скачать скрипт:
 - [по прямой ссылке](https://github.com/TaizoGem/clever_battle_bot/archive/master.zip)
 - через git:
 ```bash
 git clone git://github.com/TaizoGem/clever_battle_bot
 ```
 - через wget:
 ```bash
 wget https://github.com/TaizoGem/clever_battle_bot/archive/master.zip -O cbb.zip
 mkdir clever_battle_bot
 cd clever_battle_bot
 unzip ../cbb.zip
 ```
2. Установить зависимости:
 - создать venv и установить зависимости туда:  
   - linux/macos:
   ```bash
   python3 -m venv venv
   . venv/bin/activate
   pip3 install requests PyQt5
   ```
   - windows:
   ```batch
   python -m venv venv
   venv\Scripts\activate
   pip install requests PyQt5
   ```
 - установить зависимости в системный python *(НЕ РЕКОМЕНДУЕТСЯ)*:
   - linux/macos:
   ```bash
   pip3 install requests PyQt5
   ```
   - windows:
   ```batch
   pip install requests PyQt5
   ```
# Использование 
| флаг          | описание                                                        |
|---------------|-----------------------------------------------------------------|
| `--log-file`  | указывает файл логов (по умолчанию `./.battle.log`)             |
| `--token`     | указывает токен/несколько токенов, которые будут использоваться |
| `--once`      | запустить на одну игру (по умолчанию)                           |
| `--times N`   | запустить на N игр                                              |
| `--forever`   | запустить до ручной остановки                                   |
| `--no-log`    | отключает логи                                                  |
| `--telegram`  | включает вывод логов в телеграм.                                |
| `--tgtoken`   | устанавливает токен бота телеграм                               |
| `--tgchannel` | устанавливает канал/чат вывода (@домен или id)                  |
| `--tgproxy`   | устанавливает прокси для телеграма или `disable` для выключения |

Примеры:  
 - запустить с токенами `token1` и `token2` на одну игру с логами в .log:  
 `python clever_battle.py --log-file .log --token token1 --token token2 --once`
 - запустить на 6 игр с токеном `token` с логами только в телеграм:  
 `python clever_battle.py --no-log --telegram --token token --times 6` 
