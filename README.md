# 📚 NovaReader

**Удобная читалка электронных книг с поддержкой TTS и синхронизацией**

<img width="396" height="253" alt="Снимок экрана_20260514_102704" src="https://github.com/user-attachments/assets/0b874e94-5c18-445d-86b5-eb61b10471e2" />


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
Библиотека

<img width="1348" height="734" alt="2026-07-10_11-07" src="https://github.com/user-attachments/assets/1c15dc1d-0fb7-447f-9a25-cdef2704990a" />


Чтение

<img width="1920" height="1080" alt="2026-07-10_11-08" src="https://github.com/user-attachments/assets/b1953c65-1e64-4c75-91cb-3126b6e6b140" />
<img width="1920" height="1080" alt="2026-07-10_11-13" src="https://github.com/user-attachments/assets/1beb742d-759f-4f35-a377-a53fe6953414" />

Настройки

<img width="724" height="579" alt="2026-07-10_11-16" src="https://github.com/user-attachments/assets/1d0f8f63-290f-4ff3-9861-61bdc720f886" />
<img width="718" height="589" alt="2026-07-10_11-17" src="https://github.com/user-attachments/assets/795b94a4-21cd-4184-ae9c-6e5d60acb68e" />
<img width="713" height="582" alt="2026-07-10_11-17_1" src="https://github.com/user-attachments/assets/77367527-a9ff-46ab-8dd9-63c6adae1b81" />
<img width="722" height="579" alt="2026-07-10_11-17_2" src="https://github.com/user-attachments/assets/31fa778b-8e0f-41af-b22d-5d19b01684b4" />
<img width="703" height="574" alt="2026-07-10_11-17_3" src="https://github.com/user-attachments/assets/fa44f52f-9402-4f79-9194-e0f2ab5c4d69" />
<img width="717" height="590" alt="2026-07-10_11-18" src="https://github.com/user-attachments/assets/7ae6a483-09b4-43c8-af3b-7018a02f7c68" />
<img width="727" height="594" alt="2026-07-10_11-18_1" src="https://github.com/user-attachments/assets/4e400176-c81f-42ca-a02e-5fbd723285af" />
<img width="747" height="617" alt="2026-07-10_11-19" src="https://github.com/user-attachments/assets/c6df5370-0e43-4109-8a72-7618ed51e83f" />






---

## 📥 Скачать

| Платформа | Ссылка | Размер |
|-----------|--------|--------|
| **Windows** | NovaReader.exe | ~450 МБ |
| **Linux** | NovaReader_Linux.tar.gz| ~460 МБ |

---

## 🚀 Установка и запуск

### Windows
1. Скачайте `NovaReader.exe`

### Linux
1. Скачайте `NovaReader_Linux.tar.gz`
2. Распакуйте: `tar -xzf NovaReader_Linux.tar.gz`
3. Запустите: `./NovaReader`

---

### ⚠️ Установка в системные директории (например, /opt)

Если вы переносите программу в папку, требующую прав администратора (root), после копирования выполните команду, сделав исполняемым файл `piper`:

```bash
sudo chmod +x /opt/NovaReader/tts/piper/piper
```

Замените `/opt/NovaReader` на путь к вашей папке с программой, если он отличается. Это нужно из-за особенностей копирования файлов с правами root в некоторых файловых менеджерах — исполняемый бит на бинарнике может теряться. При установке в обычную папку пользователя (например, в домашнюю директорию) этот шаг не требуется.

---

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
## Как Создать и восстановить 
---
- Нажмите создать резервную копию
- Откроется окно
  
  <img width="390" height="296" alt="изображение" src="https://github.com/user-attachments/assets/4a055223-0707-4943-aa4c-2de4b0ae83d0" />
- Выберите нужные пункты
- Сохраните бэкап

  ---
  - Нажмите восстановить резервную копию
  - Откроется окно
   - Выбирайте файл `novareader_backup_*.zip`
    --- 
---

## Как восстановить из облака
1. Загрузите файл `novareader_backup_*.zip` в облачное хранилище:
   - **Яндекс.Диск** — нажмите «Поделиться» → скопируйте ссылку
   - **Google Drive** — нажмите «Получить ссылку» → включите «Общий доступ»
   - **Dropbox** — нажмите «Поделиться» → создайте ссылку

2. Вставьте ссылку в программу → нажмите «Да»
  <img width="522" height="175" alt="2026-07-10_11-32" src="https://github.com/user-attachments/assets/a9baf0ed-2199-4e52-b18b-8e197be20acc" />

4. Программа сама:
   - Определит сервис (Яндекс / Google / Dropbox)
   - Получит прямую ссылку
   - Скачает архив в папку пользователя
   - Откроет диалог восстановления

     <img width="322" height="351" alt="2026-07-10_11-30" src="https://github.com/user-attachments/assets/22c8c232-4bed-4a54-ad4d-d77ef31a7305" />


---

## 📦 Исходный код

Полный исходный код (включая папку `foliate-js`) доступен для скачивания в разделе **Releases**:

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
- [Fb2c](https://github.com/rupor-github/fb2cng) — конвертер FB2 в EPUB
---

## 📧 Контакты

- **Автор:** yuranZO
- **GitHub:** [github.com/yurantest/NovaReader](https://github.com/yurantest/NovaReader)

