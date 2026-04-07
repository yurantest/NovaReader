# 📚 NovaReader

**Удобная читалка электронных книг с поддержкой TTS и синхронизацией**

[![Version](https://img.shields.io/badge/version-1.0-blue.svg)]()

---

## ✨ Возможности

- 📖 **Поддержка форматов:** FB2, EPUB, PDF, CBZ (комиксы)
- 🎙️ **TTS (чтение вслух):** Голоса Piper (русские), поддержка системных движков
- 🎨 **Настройка интерфейса:** Цвета фона и текста, размер шрифта, режим страниц
- 🔖 **Закладки, заметки, подсветка текста** (4 цвета + подчёркивание/волнистая)
- 📱 **Синхронизация прогресса** между открытыми книгами
- 🚀 **Оптимизировано для больших книг** (сборники до 21 книги)
- 💻 **Кроссплатформенность:** Windows 10/11, Linux (Ubuntu/Fedora/Arch)

---

## 🖼️ Скриншоты

<!-- Вставьте сюда пути к скриншотам -->
![Библиотека](screenshots/library.png)
![Чтение](screenshots/reader.png)
![Настройки TTS](screenshots/tts.png)

---

## 📥 Скачать

| Платформа | Ссылка | Размер |
|-----------|--------|--------|
| **Windows** | [NovaReader_Windows_v1.0.zip](#) | ~450 МБ |
| **Linux** | [NovaReader_Linux_v1.0.tar.gz](#) | ~460 МБ |

---

## 🚀 Установка и запуск
## 📦 Установка зависимостей

Для корректной работы программы необходимы системные библиотеки **PortAudio** (для работы движка TTS) и **XCB** (для отображения графического интерфейса на базе Qt).

Выполните команду, соответствующую вашей операционной системе:

### 🐧 Debian / Ubuntu / Runtu / Linux Mint

sudo apt update && sudo apt install portaudio19-dev libxcb-cursor0

### 🐧 Fedora / RHEL
sudo dnf install portaudio-devel libxcb-cursor

### 🐧 Arch Linux / Garuda / Manjaro
sudo pacman -S portaudio xcb-util-cursor

---

### Windows
1. Скачайте `NovaReader_Windows_v1.0.zip`
2. Распакуйте в любую папку
3. Запустите `NovaReader.exe`

### Linux
1. Скачайте `NovaReader_Linux_v1.0.tar.gz`
2. Распакуйте: `tar -xzf NovaReader_Linux_v1.0.tar.gz`
3. Запустите: `./NovaReader`
---

## 📦 Исходный код

Полный исходный код (включая папку `foliate-js`) доступен для скачивания в разделе **Releases**:

👉 [Скачать исходный код NovaReader_Source.zip](https://github.com/yurantest/NovaReader/releases/tag/NovaReader)

Исходный код прилагается к каждому релизу в виде отдельного архива.
> **Примечание:** Для работы TTS с голосами Piper скачайте голоса через меню настроек.

---

## 🎙️ Настройка TTS (голоса Piper)

1. Откройте книгу → нажмите кнопку **Настройки TTS** (иконка шестерёнки)
2. Выберите вкладку **Piper голоса**
3. Нажмите **Скачать** рядом с нужным голосом (Ирина, Денис, Дмитрий)
4. После установки голос станет доступен

---

## 🛠️ Системные требования

| Компонент | Минимальные | Рекомендуемые |
|-----------|-------------|---------------|
| **ОЗУ** | 4 ГБ | 8+ ГБ |
| **Видеокарта** | Поддержка Vulkan (Linux) / DirectX 11 (Windows) | Любая современная |
| **Место на диске** | 500 МБ | 1 ГБ (для голосов) |

---

## 🐛 Известные проблемы

- **Linux:** На некоторых системах с проприетарными драйверами NVIDIA возможна медленная загрузка первой книги (до 10 секунд)
- **Решение:** Закройте и откройте книгу заново — второй раз откроется быстро

---

## 📄 Лицензия

Этот проект распространяется под лицензией **GNU Lesser General Public License v3.0 (LGPL-3.0)**.

Подробнее: [https://www.gnu.org/licenses/lgpl-3.0.html](https://www.gnu.org/licenses/lgpl-3.0.html)

---

## 🙏 Благодарности

- [Foliate.js](https://github.com/johnfactotum/foliate) — ядро рендеринга книг
- [Piper TTS](https://github.com/rhasspy/piper) — движок синтеза речи
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) — фреймворк интерфейса

---

## 📧 Контакты

- **Автор:** yuranZO
- **Telegram:**
- **GitHub:** [github.com/yurantest/NovaReader](https://github.com/yurantest/NovaReader)

