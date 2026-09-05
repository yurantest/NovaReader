#!/bin/bash
# build-flatpak.sh — сборка Flatpak из готовой сборки NovaReader
# Использование: ./build-flatpak.sh

set -e

# ─── Цвета ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  NovaReader — Сборка Flatpak${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# ─── Проверка сборки ──────────────────────────────────────────────────────
if [ ! -d "dist/NovaReader" ]; then
    echo -e "${RED}❌ Сборка не найдена!${NC}"
    echo "   Запустите сначала: python build.py --target linux --clean"
    exit 1
fi

# ─── 1. Копирование отсутствующих библиотек ──────────────────────────────
echo -e "${YELLOW}📦 1. Копирование отсутствующих библиотек...${NC}"

DIST_DIR="dist/NovaReader"

# Список библиотек, которые могут отсутствовать
LIBS=(
    # X11 библиотеки
    "libxcb-cursor.so.0"
    "libxcb-icccm.so.4"
    "libxcb-image.so.0"
    "libxcb-keysyms.so.1"
    "libxcb-render-util.so.0"
    "libxcb-xkb.so.1"
    "libxcb-randr.so.0"
    "libxcb-shm.so.0"
    "libxcb-xfixes.so.0"
    "libxcb-xinerama.so.0"
    "libxcb-glx.so.0"
    "libxkbcommon-x11.so.0"
    "libxkbcommon.so.0"
    
    # Qt библиотеки
    "libQt6EglFsKmsGbmSupport.so.6"
    "libQt6EglFsKmsSupport.so.6"
    
    # Другие библиотеки
    "libtiff.so.5"
    "libscipy_openblas64_-61654e39.so"
    "libgssapi_krb5.so.2"
    "libkrb5.so.3"
    "libk5crypto.so.3"
    "libcom_err.so.2"
    "libkrb5support.so.0"
)

# Копирование каждой библиотеки
for lib in "${LIBS[@]}"; do
    # Ищем библиотеку в системе
    found=$(find /usr/lib/x86_64-linux-gnu -name "$lib*" 2>/dev/null | head -1)
    if [ -z "$found" ]; then
        found=$(find /usr/lib -name "$lib*" 2>/dev/null | head -1)
    fi
    
    if [ -n "$found" ] && [ -f "$found" ]; then
        echo "   ✅ $lib"
        cp -v "$found" "$DIST_DIR/" 2>/dev/null || true
        # Если это симлинк — копируем и реальный файл
        if [ -L "$found" ]; then
            target=$(readlink -f "$found")
            if [ -f "$target" ]; then
                cp -v "$target" "$DIST_DIR/" 2>/dev/null || true
            fi
        fi
    else
        echo "   ⚠️  $lib не найден (пропускаем)"
    fi
done

# ─── 2. Создание правильного манифеста ────────────────────────────────────
echo -e "${YELLOW}📝 2. Создание манифеста...${NC}"

cat > com.novareader.NovaReader.json << 'EOF'
{
    "app-id": "com.novareader.NovaReader",
    "runtime": "org.freedesktop.Platform",
    "runtime-version": "24.08",
    "sdk": "org.freedesktop.Sdk",
    "command": "launcher.sh",
    "finish-args": [
        "--share=ipc",
        "--socket=wayland",
        "--socket=fallback-x11",
        "--share=network",
        "--device=dri",
        "--filesystem=host",
        "--filesystem=home",
        "--socket=pulseaudio",
        "--env=LD_LIBRARY_PATH=/app/bin"
    ],
    "modules": [
        {
            "name": "x11-libs",
            "buildsystem": "simple",
            "build-commands": [
                "mkdir -p /app/bin",
                "cp /usr/lib/x86_64-linux-gnu/libxcb*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libxkbcommon*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libX*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libGL*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libEGL*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libdrm*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libgbm*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libtiff*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libQt6EglFsKms*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libkrb5*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libgssapi*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libk5crypto*.so* /app/bin/ 2>/dev/null || true",
                "cp /usr/lib/x86_64-linux-gnu/libcom_err*.so* /app/bin/ 2>/dev/null || true"
            ],
            "sources": []
        },
        {
            "name": "novareader",
            "buildsystem": "simple",
            "build-commands": [
                "mkdir -p /app/bin",
                "cp -r dist/NovaReader/* /app/bin/",
                "chmod +x /app/bin/NovaReader",
                "chmod +x /app/bin/python3",
                "ln -sf /app/bin/python3 /app/bin/python",
                "cat > /app/bin/launcher.sh << 'LAUNCHER_EOF'\n#!/bin/bash\nexport LD_LIBRARY_PATH=/app/bin:${LD_LIBRARY_PATH}\nexport PYTHONHOME=/app/bin\nexport PYTHONPATH=/app/bin\nexec /app/bin/NovaReader \"$@\"\nLAUNCHER_EOF\n",
                "chmod +x /app/bin/launcher.sh"
            ],
            "sources": [
                {
                    "type": "dir",
                    "path": "."
                }
            ]
        }
    ]
}
EOF

echo -e "${GREEN}   ✅ Манифест создан${NC}"

# ─── 3. Сборка Flatpak ──────────────────────────────────────────────────────
echo -e "${YELLOW}📦 3. Сборка Flatpak...${NC}"

flatpak-builder --force-clean --repo=flatpak-repo --disable-cache flatpak-build com.novareader.NovaReader.json

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка сборки Flatpak${NC}"
    exit 1
fi

# ─── 4. Создание .flatpak файла ────────────────────────────────────────────
echo -e "${YELLOW}📦 4. Создание .flatpak файла...${NC}"

flatpak build-bundle flatpak-repo com.novareader.NovaReader.flatpak com.novareader.NovaReader

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка создания .flatpak файла${NC}"
    exit 1
fi

# ─── 5. Очистка временных файлов ──────────────────────────────────────────
rm -rf flatpak-repo flatpak-build

# ─── 6. Проверка ────────────────────────────────────────────────────────────
echo -e "${YELLOW}🔍 5. Проверка зависимостей...${NC}"

MISSING=$(ldd dist/NovaReader/NovaReader 2>&1 | grep "not found" | wc -l)
if [ "$MISSING" -eq 0 ]; then
    echo -e "${GREEN}   ✅ Все библиотеки найдены!${NC}"
else
    echo -e "${YELLOW}   ⚠️  Осталось отсутствующих библиотек: $MISSING${NC}"
    ldd dist/NovaReader/NovaReader 2>&1 | grep "not found"
fi

# ─── Итог ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Flatpak создан!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}📁 Результат:${NC}"
ls -lh com.novareader.NovaReader.flatpak
echo ""
echo -e "${BLUE}🚀 Установка и запуск:${NC}"
echo "   flatpak install --user com.novareader.NovaReader.flatpak"
echo "   flatpak run com.novareader.NovaReader"
echo ""
echo -e "${BLUE}🔍 Диагностика внутри контейнера:${NC}"
echo "   flatpak run --command=sh com.novareader.NovaReader"
echo "   ldd /app/bin/NovaReader | grep 'not found'"
echo "   exit"
