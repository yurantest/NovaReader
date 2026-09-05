// fonts.js
// ── Пользовательские шрифты для Immortal Book Core ──────────────────────────
// Загрузка шрифтов ТОЛЬКО через FontFace API (никакого @font-face из Python,
// никакого QFontDatabase для веб-вью).
//
// ВАЖНО про архитектуру foliate-js: каждая секция книги рендерится в
// ОТДЕЛЬНОМ <iframe> (paginator.js, sandbox="allow-same-origin allow-scripts"),
// у которого свой независимый document. document.fonts главной страницы
// НЕ виден внутри iframe — это два разных документа с двумя разными наборами
// шрифтов. Поэтому FontFace, загруженный один раз на главной странице,
// дополнительно регистрируется (add()) в document.fonts КАЖДОГО нового
// iframe при его создании — см. window.__registerFontsInDoc(doc), вызываемую
// из reader.html в обработчике view.addEventListener('load', ...).
// Сам файл шрифта при этом с диска не перечитывается: FontFace — это уже
// загруженный (после face.load()) объект, add() лишь регистрирует один и тот
// же объект в дополнительном документе.
//
// Порядок операций критичен:
//   1. await загрузка ВСЕХ начертаний нужного family (face.load())
//   2. применить font-family к view (themeSettings.fontFamily + applyTheme())
//   3. перепагинация (полный перерендер), с сохранением позиции чтения
// На время шага 3 показывается спиннер «Загрузка...» — переиспользуем
// showReturnOverlay/dismissReturnOverlay из reader.html.

// Кэш загруженных семейств: family → массив уже загруженных FontFace.
// Используется и чтобы не грузить файлы повторно, и чтобы регистрировать
// их в новых iframe без повторного обращения к диску.
const _loadedFaces = new Map(); // family -> FontFace[]

/**
 * Находит family по выбранному display_name пользователя и возвращает
 * все записи fontMap (= settings.font_faces из Python, поле getSettings())
 * с этой же family (Regular/Bold/Italic/BoldItalic...).
 * @param {Array} fontMap - config.get_font_file_map() → приходит в JS как s.font_faces
 * @param {string} selectedDisplayName - reader_font_family из настроек
 * @returns {{family: string, entries: Array} | null}
 */
function _resolveFamily(fontMap, selectedDisplayName) {
    if (!Array.isArray(fontMap) || !fontMap.length) return null;

    // display_name может отличаться от family — сначала ищем точное
    // совпадение display_name, иначе — совпадение по family напрямую.
    const selected =
        fontMap.find(f => f.display_name === selectedDisplayName) ||
        fontMap.find(f => f.family === selectedDisplayName);

    if (!selected) return null;

    const family = selected.family;
    const entries = fontMap.filter(f => f.family === family);
    return { family, entries };
}

/**
 * Загружает все начертания одного family через FontFace API и регистрирует
 * их в document.fonts главной страницы. Возвращает family при успехе хотя бы
 * одного начертания, иначе null.
 */
async function _loadFamily(family, entries, log) {
    const results = await Promise.allSettled(entries.map(async (info) => {
        const weight = info.variable
            ? `${info.wght_min} ${info.wght_max}`
            : String(info.weight ?? 400);
        const style = info.style || 'normal';

        // file_url — абсолютный percent-encoded file:// URL (уже закодирован
        // на Python-стороне, кириллица в пути учтена). fonts_base_url —
        // подстраховка на случай записи без file_url.
        const src = info.file_url || ((window.themeSettings?.fontsBaseUrl || '') + info.file);

        const face = new FontFace(family, `url("${src}")`, { style, weight });
        // FontFace с url() — браузер сам стримит и кэширует декодированный
        // шрифт, ArrayBuffer в JS не держим (память).
        await face.load();
        document.fonts.add(face);
        return face;
    }));

    const loadedFaces = [];
    results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
            loadedFaces.push(r.value);
        } else {
            (log || console.warn)(
                ` Шрифт: не удалось загрузить начертание "${entries[i].file}" ` +
                `семейства "${family}": ${r.reason?.message ?? r.reason}`,
                'warn'
            );
        }
    });

    if (loadedFaces.length === 0) return null; // ни одно начертание не загрузилось
    _loadedFaces.set(family, loadedFaces);
    return family;
}

/**
 * Регистрирует уже загруженные FontFace всех известных семейств в
 * document.fonts переданного document (новый iframe секции). Вызывается
 * из reader.html при каждом view 'load' событии — до пересчёта пагинации,
 * иначе текст в новой секции временно покажется на fallback-шрифте.
 * Файлы с диска повторно не читаются — просто copy-add уже загруженных
 * объектов FontFace в дополнительный документ.
 */
window.__registerFontsInDoc = function (doc) {
    if (!doc?.fonts) return;
    for (const faces of _loadedFaces.values()) {
        for (const face of faces) {
            try { doc.fonts.add(face); } catch (e) { /* дубликат/недоступно — не критично */ }
        }
    }
};

/**
 * Сохраняет текущую позицию чтения перед перерендером (CFI).
 */
function _capturePosition(view) {
    try {
        return view?.lastLocation?.cfi ?? null;
    } catch (e) {
        return null;
    }
}

/**
 * Восстанавливает позицию чтения после перерендера.
 */
async function _restorePosition(view, cfi) {
    if (!cfi || !view?.goTo) return;
    try {
        await view.goTo(cfi);
    } catch (e) {
        console.warn(' Шрифт: не удалось восстановить позицию после смены шрифта:', e);
    }
}

/**
 * Показывает спиннер «Загрузка...» на время перепагинации.
 */
function _showFontSpinner() {
    if (typeof window.showReturnOverlay === 'function') {
        window.showReturnOverlay('Применяем шрифт…', '');
        return;
    }
    document.getElementById('fontApplySpinnerEl')?.remove();
    const div = document.createElement('div');
    div.id = 'fontApplySpinnerEl';
    div.style.cssText = [
        'position:fixed;inset:0;z-index:5000;',
        'background:var(--bg-color,#f4ecd8);',
        'display:flex;align-items:center;justify-content:center;',
    ].join('');
    div.innerHTML = `
        <div style="width:40px;height:40px;border:3px solid rgba(0,0,0,.12);
             border-top-color:#6c5ce7;border-radius:50%;
             animation:spin 0.8s linear infinite;"></div>`;
    document.getElementById('app')?.appendChild(div);
}

function _hideFontSpinner() {
    if (typeof window.dismissReturnOverlay === 'function') {
        window.dismissReturnOverlay();
        return;
    }
    document.getElementById('fontApplySpinnerEl')?.remove();
}

/**
 * Главная функция: применяет пользовательский шрифт к текущей книге.
 *   1. Определяет family по выбранному display_name.
 *   2. Загружает ВСЕ начертания family через FontFace API (await), регистрирует
 *      их в document.fonts главной страницы И в document.fonts текущего
 *      открытого iframe (чтобы шрифт применился сразу, без ожидания
 *      следующего view 'load').
 *   3. Применяет CSS font-family к view и перепагинирует, сохраняя позицию.
 * Простой трекинг готовности — таймаут 2–3с, сложная логика не нужна.
 *
 * @param {object} view - foliate-js view (window.view в reader.html)
 * @param {Array} fontMap - settings.font_faces из Python
 * @param {string} selectedDisplayName - reader_font_family из настроек
 * @param {function} [applyCssFn] - колбэк, применяющий family к теме
 *        (обновляет themeSettings.fontFamily и вызывает applyTheme()).
 * @param {function} [log]
 */
export async function applyReaderFont(view, fontMap, selectedDisplayName, applyCssFn, log) {
    const resolved = _resolveFamily(fontMap, selectedDisplayName);
    if (!resolved) {
        (log || console.warn)(` Шрифт: запись для "${selectedDisplayName}" не найдена в fontMap`, 'warn');
        return false;
    }
    const { family, entries } = resolved;

    if (!_loadedFaces.has(family)) {
        const loaded = await _loadFamily(family, entries, log);
        if (!loaded) {
            (log || console.warn)(` Шрифт: не удалось загрузить ни одного начертания "${family}", остаёмся на прежнем шрифте`, 'warn');
            return false; // fallback — не ломаем view
        }
    }

    // Регистрируем сразу и в текущем открытом iframe (не только в будущих) —
    // иначе видимая прямо сейчас секция не подхватит шрифт до следующей
    // загрузки секции.
    try {
        const currentDoc = view?.renderer?.getContents?.()?.[0]?.doc;
        if (currentDoc) window.__registerFontsInDoc(currentDoc);
    } catch (e) { /* не критично */ }

    // ── Порядок критичен: шрифт уже в document.fonts, теперь применяем
    //    CSS и перепагинируем. Не применяем шрифт ДО загрузки — иначе
    //    пагинация посчитается по fallback-шрифту и страницы «поползут».
    _showFontSpinner();
    const savedCfi = _capturePosition(view);

    try {
        if (typeof applyCssFn === 'function') {
            applyCssFn(family);
        }
        // Полный перерендер: переходим на сохранённый CFI — paginator.js
        // пересчитает раскладку текущей секции с новым шрифтом.
        if (savedCfi) {
            await _restorePosition(view, savedCfi);
        }
    } finally {
        // Простой таймаут вместо сложного трекинга готовности пагинации.
        setTimeout(_hideFontSpinner, 2200);
    }

    return true;
}
