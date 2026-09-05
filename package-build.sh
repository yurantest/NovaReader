#!/bin/bash
# package-build.sh — упаковка NovaReader в AppImage
# Использование: ./package-build.sh

set -e

# ─── Цвета ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  NovaReader — Сборка AppImage${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# ─── Проверка сборки ──────────────────────────────────────────────────────
if [ ! -d "dist/NovaReader" ]; then
    echo -e "${RED}❌ Сборка не найдена!${NC}"
    echo "   Запустите сначала: python build.py --target linux --clean"
    exit 1
fi

# ─── Создание AppDir ──────────────────────────────────────────────────────
echo -e "${YELLOW}📦 1. Создание AppDir...${NC}"

APPDIR="AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/lib/plugins/platforms"
mkdir -p "$APPDIR/usr/lib/plugins/imageformats"
mkdir -p "$APPDIR/usr/lib/plugins/styles"

# Копируем всю сборку в usr/bin/
cp -r dist/NovaReader/* "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/NovaReader"

if [ -f "$APPDIR/usr/bin/python3" ]; then
    chmod +x "$APPDIR/usr/bin/python3"
else
    echo -e "${YELLOW}   ⚠️  python3 не найден в сборке — пропускаю (не критично)${NC}"
fi

if [ -f "$APPDIR/usr/bin/tts/piper/piper" ]; then
    chmod +x "$APPDIR/usr/bin/tts/piper/piper"
    echo "   ✅ tts/piper/piper: chmod +x применён"
else
    echo -e "${YELLOW}   ⚠️  tts/piper/piper не найден — TTS через Piper не будет работать${NC}"
fi

# ─── Автоопределение структуры Qt ──────────────────────────────────────────
echo -e "${YELLOW}📦 2. Определение структуры Qt...${NC}"

QT_RESOURCES_SRC=""
QT_LOCALES_SRC=""
QT_PROCESS_SRC=""

if [ -d "dist/NovaReader/PyQt6/Qt6/resources" ]; then
    QT_RESOURCES_SRC="dist/NovaReader/PyQt6/Qt6/resources"
    echo "   ✅ Ресурсы найдены в dist/NovaReader/PyQt6/Qt6/resources"
fi

if [ -d "dist/NovaReader/PyQt6/Qt6/translations/qtwebengine_locales" ]; then
    QT_LOCALES_SRC="dist/NovaReader/PyQt6/Qt6/translations/qtwebengine_locales"
    echo "   ✅ Локали найдены в dist/NovaReader/PyQt6/Qt6/translations/qtwebengine_locales"
fi

if [ -f "dist/NovaReader/QtWebEngineProcess" ]; then
    QT_PROCESS_SRC="dist/NovaReader/QtWebEngineProcess"
    echo "   ✅ QtWebEngineProcess найден в dist/NovaReader/"
fi

# ─── Копирование библиотек ──────────────────────────────────────────────────
echo -e "${YELLOW}📦 3. Копирование внешних библиотек...${NC}"

copy_lib() {
    local lib="$1"
    local found

    if [ -f "dist/NovaReader/$lib" ]; then
        echo "   ✅ $lib уже есть в сборке"
        return 0
    fi

    local search_dirs=(
        "/usr/lib/x86_64-linux-gnu"
        "/usr/lib"
        "/usr/lib64"
        "/usr/lib/$(uname -m)-linux-gnu"
    )

    for dir in "${search_dirs[@]}"; do
        if [ -d "$dir" ]; then
            found=$(find "$dir" -maxdepth 1 -name "$lib" 2>/dev/null | head -1)
            if [ -n "$found" ]; then
                break
            fi
        fi
    done

    if [ -z "$found" ]; then
        local base_name="${lib%.so*}"
        for dir in "${search_dirs[@]}"; do
            if [ -d "$dir" ]; then
                found=$(find "$dir" -maxdepth 1 -name "${base_name}.so*" 2>/dev/null | head -1)
                if [ -n "$found" ]; then
                    echo "   ⚠️  $lib не найден, использую $(basename "$found")"
                    break
                fi
            fi
        done
    fi

    if [ -n "$found" ] && [ -f "$found" ]; then
        echo "   ✅ $lib → $(basename "$found")"
        cp -v "$found" "$APPDIR/usr/lib/" 2>/dev/null || true
        if [ -L "$found" ]; then
            target=$(readlink -f "$found")
            if [ -f "$target" ]; then
                cp -v "$target" "$APPDIR/usr/lib/" 2>/dev/null || true
            fi
        fi
        return 0
    fi

    echo "   ⚠️  $lib не найден"
    return 1
}

LIBS=(
    "libQt6Core.so.6" "libQt6Gui.so.6" "libQt6Widgets.so.6"
    "libQt6Network.so.6" "libQt6WebEngineCore.so.6" "libQt6WebEngineWidgets.so.6"
    "libQt6WebChannel.so.6" "libQt6EglFsKmsGbmSupport.so.6" "libQt6EglFsKmsSupport.so.6"
    "libxcb-cursor.so.0" "libxcb-icccm.so.4" "libxcb-image.so.0"
    "libxcb-keysyms.so.1" "libxcb-render-util.so.0" "libxcb-xkb.so.1"
    "libxcb-randr.so.0" "libxcb-shm.so.0" "libxcb-xfixes.so.0"
    "libxcb-xinerama.so.0" "libxcb-glx.so.0" "libxkbcommon-x11.so.0"
    "libxkbcommon.so.0"
    "libkrb5.so.3" "libgssapi_krb5.so.2"
    "libk5crypto.so.3" "libcom_err.so.2" "libkrb5support.so.0"
    "libssl.so.3" "libcrypto.so.3" "libtiff.so.6"
    "libjpeg.so.8" "libpng16.so.16" "libfontconfig.so.1"
    "libfreetype.so.6" "libexpat.so.1" "libz.so.1"
    "libbz2.so.1.0" "liblzma.so.5" "libdbus-1.so.3"
    "libGL.so.1" "libEGL.so.1" "libgbm.so.1" "libdrm.so.2"
    "libidn2.so.0" "libbrotlidec.so.1" "libcares.so.2"
    "libnghttp2.so.14" "libpsl.so.5" "libunistring.so.5"
)

for lib in "${LIBS[@]}"; do
    copy_lib "$lib" || true
done

# ─── 3.1 PortAudio: рядом с бинарником (для Piper) ──────────────────────
echo -e "${YELLOW}📦 3.1. Копирование libportaudio (рядом с бинарником)...${NC}"
PORTAUDIO_FOUND=""
for dir in "/usr/lib/x86_64-linux-gnu" "/usr/lib" "/usr/lib64" "/usr/lib/$(uname -m)-linux-gnu"; do
    if [ -d "$dir" ]; then
        found=$(find "$dir" -maxdepth 1 -name "libportaudio.so.2*" 2>/dev/null | head -1)
        if [ -n "$found" ]; then
            PORTAUDIO_FOUND="$found"
            break
        fi
    fi
done

if [ -n "$PORTAUDIO_FOUND" ] && [ -f "$PORTAUDIO_FOUND" ]; then
    cp -v "$PORTAUDIO_FOUND" "$APPDIR/usr/bin/" 2>/dev/null || true
    if [ -L "$PORTAUDIO_FOUND" ]; then
        target=$(readlink -f "$PORTAUDIO_FOUND")
        if [ -f "$target" ]; then
            cp -v "$target" "$APPDIR/usr/bin/" 2>/dev/null || true
        fi
    fi
    echo "   ✅ libportaudio.so.2 → usr/bin/ (для TTS subprocess)"
else
    echo -e "${YELLOW}   ⚠️  libportaudio.so.2 не найден${NC}"
fi

# ─── 3.2 Статический ffmpeg для Edge TTS ──────────────────────────────
echo -e "${YELLOW}📦 3.2. Копирование статического ffmpeg для Edge TTS...${NC}"
FFMPEG_TARGET="$APPDIR/usr/bin/ffmpeg"

if [ -f "$FFMPEG_TARGET" ]; then
    chmod +x "$FFMPEG_TARGET"
    echo -e "   ${GREEN}✅ ffmpeg уже есть в сборке${NC}"
else
    FFMPEG_SOURCE=""
    
    # 1. Проверяем папку ffmpeg/ рядом со скриптом
    if [ -d "ffmpeg" ]; then
        echo "   🔍 Проверяем папку ffmpeg/..."
        # Ищем ffmpeg в папке ffmpeg/bin/ или прямо в ffmpeg/
        if [ -f "ffmpeg/bin/ffmpeg" ]; then
            FFMPEG_SOURCE="ffmpeg/bin/ffmpeg"
            echo "   ✅ Найден ffmpeg в ffmpeg/bin/ffmpeg"
        elif [ -f "ffmpeg/ffmpeg" ]; then
            FFMPEG_SOURCE="ffmpeg/ffmpeg"
            echo "   ✅ Найден ffmpeg в ffmpeg/ffmpeg"
        else
            # Ищем в подпапках
            FOUND_FFMPEG=$(find ffmpeg -name "ffmpeg" -type f 2>/dev/null | head -1)
            if [ -n "$FOUND_FFMPEG" ]; then
                FFMPEG_SOURCE="$FOUND_FFMPEG"
                echo "   ✅ Найден ffmpeg в $FOUND_FFMPEG"
            fi
        fi
    fi
    
    # 2. Проверяем dist/NovaReader/
    if [ -z "$FFMPEG_SOURCE" ] && [ -f "dist/NovaReader/ffmpeg" ]; then
        FFMPEG_SOURCE="dist/NovaReader/ffmpeg"
        echo "   ✅ Найден ffmpeg в dist/NovaReader/ffmpeg"
    fi
    
    # 3. Если нашли - копируем
    if [ -n "$FFMPEG_SOURCE" ] && [ -f "$FFMPEG_SOURCE" ]; then
        echo "   Копирование ffmpeg из $FFMPEG_SOURCE ..."
        cp -v "$FFMPEG_SOURCE" "$FFMPEG_TARGET"
        chmod +x "$FFMPEG_TARGET"
        
        # Проверяем, что это исполняемый файл
        if file "$FFMPEG_TARGET" | grep -q "ELF.*executable"; then
            echo -e "   ${GREEN}✅ ffmpeg скопирован ($(du -h "$FFMPEG_TARGET" | cut -f1))${NC}"
        else
            echo -e "   ${YELLOW}⚠️ Файл не является исполняемым ELF, но попытка будет сделана${NC}"
        fi
    else
        # 4. Если не нашли - пробуем скачать
        echo "   🔍 ffmpeg не найден в ffmpeg/ или dist/NovaReader/, пробуем скачать..."
        
        FFMPEG_DOWNLOADED=false
        
        # Список источников
        SOURCES=(
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
            "https://github.com/acoustid/ffmpeg-build/releases/download/v8.1.2-1/ffmpeg-linux-x86_64-static.tar.xz"
        )
        
        for URL in "${SOURCES[@]}"; do
            echo "   Попытка скачать с $URL ..."
            FFMPEG_TAR="ffmpeg_$(date +%s).tar.xz"
            
            HTTP_CODE=$(curl -L -k -w "%{http_code}" -o "$FFMPEG_TAR" --max-time 60 --retry 3 "$URL" 2>/dev/null)
            if [ "$HTTP_CODE" = "200" ] && [ -f "$FFMPEG_TAR" ]; then
                if file "$FFMPEG_TAR" | grep -q "XZ compressed"; then
                    echo "   ✅ Скачано успешно (XZ архив)"
                    FFMPEG_DOWNLOADED=true
                    break
                else
                    rm -f "$FFMPEG_TAR"
                fi
            else
                rm -f "$FFMPEG_TAR"
            fi
        done
        
        if [ "$FFMPEG_DOWNLOADED" = true ] && [ -f "$FFMPEG_TAR" ]; then
            FILE_SIZE=$(stat -c%s "$FFMPEG_TAR" 2>/dev/null || stat -f%z "$FFMPEG_TAR" 2>/dev/null || echo "0")
            if [ "$FILE_SIZE" -gt 10000000 ]; then
                echo "   Размер файла: $(du -h "$FFMPEG_TAR" | cut -f1)"
                
                # Извлекаем ffmpeg
                EXTRACTED=false
                if tar -xJf "$FFMPEG_TAR" --wildcards --strip-components=2 "*/bin/ffmpeg" -C "$APPDIR/usr/bin/" 2>/dev/null; then
                    EXTRACTED=true
                elif tar -xJf "$FFMPEG_TAR" --wildcards --strip-components=2 "*/bin/ffmpeg" -C "$APPDIR/usr/bin/" 2>/dev/null; then
                    EXTRACTED=true
                elif tar -xJf "$FFMPEG_TAR" -C "$APPDIR/usr/bin/" --wildcards "**/ffmpeg" 2>/dev/null; then
                    find "$APPDIR/usr/bin/" -name "ffmpeg" -type f -exec mv {} "$FFMPEG_TARGET" \; 2>/dev/null || true
                    EXTRACTED=true
                fi
                
                if [ "$EXTRACTED" = true ] && [ -f "$FFMPEG_TARGET" ]; then
                    chmod +x "$FFMPEG_TARGET"
                    if file "$FFMPEG_TARGET" | grep -q "ELF.*executable"; then
                        echo -e "   ${GREEN}✅ статический ffmpeg скопирован ($(du -h "$FFMPEG_TARGET" | cut -f1))${NC}"
                        FFMPEG_DOWNLOADED=true
                    else
                        echo -e "   ${YELLOW}⚠️ Извлечённый файл не является исполняемым ELF${NC}"
                        rm -f "$FFMPEG_TARGET"
                        FFMPEG_DOWNLOADED=false
                    fi
                fi
            fi
            rm -f "$FFMPEG_TAR"
        fi
        
        # 5. Если скачать не удалось - пробуем системный
        if [ "$FFMPEG_DOWNLOADED" != true ]; then
            echo -e "   ${YELLOW}⚠️ Не удалось скачать статический ffmpeg, пробуем системный...${NC}"
            SYSTEM_FFMPEG=$(which ffmpeg 2>/dev/null || true)
            if [ -n "$SYSTEM_FFMPEG" ] && [ -f "$SYSTEM_FFMPEG" ]; then
                echo "   Копирование системного ffmpeg: $SYSTEM_FFMPEG"
                cp -v "$SYSTEM_FFMPEG" "$FFMPEG_TARGET" 2>/dev/null || true
                if [ -f "$FFMPEG_TARGET" ]; then
                    chmod +x "$FFMPEG_TARGET"
                    echo -e "   ${YELLOW}⚠️ Используется системный ffmpeg ($(du -h "$FFMPEG_TARGET" | cut -f1))${NC}"
                    echo -e "   ${YELLOW}⚠️ Может не работать на других дистрибутивах!${NC}"
                fi
            else
                echo -e "   ${RED}❌ ffmpeg не найден! Edge TTS не будет работать.${NC}"
                echo ""
                echo "   Положите статический ffmpeg в одну из папок:"
                echo "   1. ffmpeg/bin/ffmpeg  (рядом со скриптом)"
                echo "   2. ffmpeg/ffmpeg      (рядом со скриптом)"
                echo "   3. dist/NovaReader/ffmpeg"
                echo ""
                echo "   Или установите системный: sudo apt install ffmpeg"
            fi
        fi
    fi
fi
# ─── Копирование Qt плагинов ──────────────────────────────────────────────
echo -e "${YELLOW}📦 4. Копирование Qt плагинов...${NC}"

if [ ! -d "$APPDIR/usr/lib/plugins/platforms" ] || [ -z "$(ls -A $APPDIR/usr/lib/plugins/platforms 2>/dev/null)" ]; then
    for src in "/usr/lib/x86_64-linux-gnu/qt6/plugins/platforms" "/usr/lib/x86_64-linux-gnu/PyQt6/Qt6/plugins/platforms" "/usr/lib/qt6/plugins/platforms" "/usr/lib/PyQt6/Qt6/plugins/platforms"; do
        if [ -d "$src" ]; then
            cp -v "$src"/*.so "$APPDIR/usr/lib/plugins/platforms/" 2>/dev/null || true
            echo "   ✅ Платформы из $src"
            break
        fi
    done
fi

if [ ! -d "$APPDIR/usr/lib/plugins/imageformats" ] || [ -z "$(ls -A $APPDIR/usr/lib/plugins/imageformats 2>/dev/null)" ]; then
    for src in "/usr/lib/x86_64-linux-gnu/qt6/plugins/imageformats" "/usr/lib/x86_64-linux-gnu/PyQt6/Qt6/plugins/imageformats" "/usr/lib/qt6/plugins/imageformats" "/usr/lib/PyQt6/Qt6/plugins/imageformats"; do
        if [ -d "$src" ]; then
            cp -v "$src"/*.so "$APPDIR/usr/lib/plugins/imageformats/" 2>/dev/null || true
            echo "   ✅ Форматы из $src"
            break
        fi
    done
fi

# ─── Удаляем проблемные звуковые библиотеки ──────────────────────────────
echo -e "${YELLOW}   🧹 Удаляем libasound, libpulse, libpipewire, libjack из бандла...${NC}"
find "$APPDIR" -type f \( -name "libasound*" -o -name "libpulse*" -o -name "libpipewire*" -o -name "libjack*" \) -delete 2>/dev/null || true
echo -e "   ${GREEN}✅ Проблемные звуковые библиотеки удалены (libportaudio оставлена)${NC}"

# ─── Создание .desktop ────────────────────────────────────────────────────
echo -e "${YELLOW}📝 5. Создание .desktop...${NC}"

cat > "$APPDIR/com.novareader.NovaReader.desktop" << 'EOF'
[Desktop Entry]
Name=NovaReader
Comment=Книжный ридер с TTS
Exec=NovaReader
Icon=novareader
Terminal=false
Type=Application
Categories=Office;AudioVideo;
EOF

# ─── Копирование иконки ──────────────────────────────────────────────────
if [ -f "icon.png" ]; then
    cp icon.png "$APPDIR/novareader.png"
elif [ -f "NovaReader_Linux.png" ]; then
    cp NovaReader_Linux.png "$APPDIR/novareader.png"
fi

# ─── Создание AppRun ──────────────────────────────────────────────────────
echo -e "${YELLOW}📝 6. Создание AppRun...${NC}"

cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"

# ─── Добавляем usr/bin в PATH (чтобы ffmpeg был доступен по имени) ──────
export PATH="${HERE}/usr/bin:${PATH}"

# ─── Пути к библиотекам ──────────────────────────────────────────────────
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/bin:${LD_LIBRARY_PATH}"

# ─── Qt плагины ──────────────────────────────────────────────────────────
export QT_PLUGIN_PATH="${HERE}/usr/lib/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="${QT_PLUGIN_PATH}/platforms"

# ─── Python ──────────────────────────────────────────────────────────────
export PYTHONHOME="${HERE}/usr/bin"
export PYTHONPATH="${HERE}/usr/bin"

# ─── Qt WebEngine ────────────────────────────────────────────────────────
if [ -d "${HERE}/usr/bin/PyQt6/Qt6/resources" ]; then
    export QTWEBENGINE_RESOURCES_PATH="${HERE}/usr/bin/PyQt6/Qt6/resources"
elif [ -d "${HERE}/usr/lib/PyQt6/Qt6/resources" ]; then
    export QTWEBENGINE_RESOURCES_PATH="${HERE}/usr/lib/PyQt6/Qt6/resources"
fi

if [ -d "${HERE}/usr/bin/PyQt6/Qt6/translations/qtwebengine_locales" ]; then
    export QTWEBENGINE_LOCALES_PATH="${HERE}/usr/bin/PyQt6/Qt6/translations/qtwebengine_locales"
elif [ -d "${HERE}/usr/lib/PyQt6/Qt6/translations/qtwebengine_locales" ]; then
    export QTWEBENGINE_LOCALES_PATH="${HERE}/usr/lib/PyQt6/Qt6/translations/qtwebengine_locales"
fi

if [ -f "${HERE}/usr/bin/QtWebEngineProcess" ]; then
    export QTWEBENGINEPROCESS_PATH="${HERE}/usr/bin/QtWebEngineProcess"
elif [ -f "${HERE}/usr/libexec/QtWebEngineProcess" ]; then
    export QTWEBENGINEPROCESS_PATH="${HERE}/usr/libexec/QtWebEngineProcess"
fi

export QTWEBENGINE_CHROMIUM_FLAGS="--use-gl=egl --disable-gpu-compositing --js-flags=--max-old-space-size=192 --renderer-process-limit=1 --disable-background-networking --disable-dev-shm-usage"

# ─── ЗАПУСК ──────────────────────────────────────────────────────────────
if [[ "$1" == "--reader" && -n "$2" ]]; then
    exec "${HERE}/usr/bin/python3" "${HERE}/usr/bin/main.py" "--reader" "$2"
elif [[ "$1" == "--search" ]]; then
    exec "${HERE}/usr/bin/python3" "${HERE}/usr/bin/main.py" "--search"
else
    exec "${HERE}/usr/bin/NovaReader" "$@"
fi
EOF

chmod +x "$APPDIR/AppRun"

# ─── Скачивание appimagetool ──────────────────────────────────────────────
echo -e "${YELLOW}📦 7. Подготовка appimagetool...${NC}"

if [ ! -f "appimagetool" ]; then
    if ! wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool; then
        echo -e "${RED}   ❌ Не удалось скачать appimagetool${NC}"
        rm -f appimagetool
        exit 1
    fi
    chmod +x appimagetool
fi

# ─── Упаковка в AppImage ──────────────────────────────────────────────────
echo -e "${YELLOW}📦 8. Упаковка в AppImage...${NC}"

VERSION=$(date +%Y%m%d)
APPIMAGE_NAME="NovaReader-${VERSION}.AppImage"

if ./appimagetool --appimage-extract-and-run -n "$APPDIR" "$APPIMAGE_NAME"; then
    APPIMAGE_SIZE=$(du -h "$APPIMAGE_NAME" | cut -f1)
    echo -e "${GREEN}   ✅ AppImage создан: $APPIMAGE_NAME ($APPIMAGE_SIZE)${NC}"
else
    echo -e "${RED}   ❌ Ошибка создания AppImage${NC}"
    exit 1
fi

# ─── Проверка ──────────────────────────────────────────────────────────────
echo -e "${YELLOW}🔍 9. Проверка AppImage...${NC}"

if [ -f "$APPIMAGE_NAME" ]; then
    echo -e "${GREEN}   ✅ Файл создан: $(ls -lh $APPIMAGE_NAME | awk '{print $9 " (" $5 ")"}')${NC}"
    rm -rf squashfs-root 2>/dev/null || true
else
    echo -e "${RED}   ❌ Файл не создан${NC}"
fi

rm -rf "$APPDIR"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ AppImage готов!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📁 Результат:${NC}"
ls -lh "$APPIMAGE_NAME"
echo ""
echo -e "${BLUE}🚀 Запуск:${NC}"
echo "   chmod +x $APPIMAGE_NAME"
echo "   ./$APPIMAGE_NAME"
echo ""
echo -e "${BLUE}📖 Запуск ридера:${NC}"
echo "   ./$APPIMAGE_NAME --reader /path/to/book.epub"
