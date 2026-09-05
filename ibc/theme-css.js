// theme-css.js
// Генерация CSS темы читалки (цвета, размеры шрифта) и фильтр рекламных
// секций пиратских сайтов из содержимого книги. Вынесено из reader.html —
// единственные внешние зависимости (themeSettings, log) передаются явно,
// поэтому модуль не завязан на остальное состояние читалки.
//
// ПРИМЕЧАНИЕ: @font-face здесь больше НЕ генерируется. Пользовательские
// шрифты загружаются через FontFace API в fonts.js и регистрируются
// напрямую в document.fonts каждого iframe секции (см.
// window.__registerFontsInDoc в fonts.js и его вызов в reader.html на
// событии view 'load'). Эта CSS-строка лишь ссылается на font-family по
// имени — сам шрифт к этому моменту уже должен быть загружен и
// зарегистрирован в document.fonts текущего iframe.

/**
 * Генерирует CSS темы (цвета, размеры, font-family) на основе объекта
 * настроек темы.
 * @param {object} themeSettings - { bg, text, fontSize, lineHeight, fontFamily }
 */
export function getThemeCSS(themeSettings) {
    return `
        html, body {
            color: ${themeSettings.text} !important;
            background: ${themeSettings.bg} !important;
            margin: 0 !important;
            -webkit-font-smoothing: antialiased !important;
            -moz-osx-font-smoothing: grayscale !important;
            text-rendering: optimizeLegibility !important;
            padding: 0 !important;
        }
        p, li, blockquote, dd, span, a {
            color: ${themeSettings.text} !important;
            font-size: ${themeSettings.fontSize}px;
            line-height: ${themeSettings.lineHeight};
            font-family: '${themeSettings.fontFamily}', Georgia, serif !important;
        }
        h1, h2, h3, h4, h5, h6 {
            color: ${themeSettings.text} !important;
            font-family: '${themeSettings.fontFamily}', Georgia, serif !important;
            text-align: center !important;
            background: transparent !important;
            margin: 1em 0 !important;
            padding: 0 !important;
            border: none !important;
        }
        a { color: inherit !important; }
        * {
            background-color: transparent !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        /* Убираем все рамки */
        * {
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }
        /* Сохраняем фон только у body */
        html, body {
            background: ${themeSettings.bg} !important;
        }
        /* Особые стили для EPUB элементов */
        body > * {
            background: transparent !important;
        }
        img {
            max-width: 100%;
            height: auto;
        }

        /* ── Скрываем рекламные секции пиратских сайтов ─────────────
           Nota bene, «от пирата» и подобные секции определяются по
           заголовку через CSS :has() и attribute selectors.
           Для EPUB: section/div содержащий <h1-h6> с текстом "Nota bene".
           Для FB2 (конвертированного): аналогично.
           Используем display:none чтобы секция не занимала место. */

        /* EPUB: section или div чей первый заголовок = "Nota bene" */
        section:has(> h1:first-child),
        section:has(> h2:first-child),
        section:has(> h3:first-child),
        div:has(> h1:first-child),
        div:has(> h2:first-child) {
            /* Применяется только через JS ниже — здесь заготовка */
        }
    `;
}

/**
 * Вставляет заглушку "Конец книги" вместо скрытой рекламной секции.
 * @param {Document} doc - документ секции (iframe)
 * @param {string} [fontFamily] - шрифт для заглушки (опционально)
 */
export function injectEndOfBookMsg(doc, fontFamily) {
    // Уже вставлено
    if (doc.getElementById('nova-end-of-book')) return;
    const lang = document.documentElement.lang ||
                 navigator.language || 'ru';
    const msg  = lang.startsWith('en') ? 'End of book' : 'Конец книги';
    const div  = doc.createElement('div');
    div.id = 'nova-end-of-book';
    const _fontFamily = fontFamily ? `'${fontFamily}', Georgia, serif` : 'inherit';
    div.style.cssText = [
        'display:flex', 'align-items:center', 'justify-content:center',
        'height:80vh', 'width:100%',
        `font-family:${_fontFamily}`,
        'font-size:1.6em', 'opacity:0.45',
        'font-style:italic', 'letter-spacing:0.05em',
        'color:var(--text-color, inherit)',
        'pointer-events:none', 'user-select:none',
    ].join(';');
    div.textContent = '— ' + msg + ' —';
    // Скрываем весь body и ставим только надпись
    Array.from(doc.body.children).forEach(el => { el.style.display = 'none'; });
    doc.body.appendChild(div);
}

/**
 * Скрывает встроенные "технические" списки оглавления, которые некоторые
 * конвертеры (например, Calibre при FB2 -> EPUB для компиляций из
 * нескольких книг) вставляют прямо в начало книги как обычный читаемый
 * текст — <ul><li><a href="...">Глава N</a></li>...</ul>. По сути это
 * дубликат нормального оглавления читалки, но в виде реального контента:
 * в больших компиляциях список может занимать 300-400+ пунктов, что при
 * листании превращается в десятки "пустых" страниц со сплошными ссылками,
 * а TTS пытается озвучить их все подряд.
 *
 * Определяем эвристически, без привязки к конкретному конвертеру: список,
 * где почти все <li> состоят ИСКЛЮЧИТЕЛЬНО из одной ссылки на другой файл
 * книги. В художественном тексте список из 8+ пунктов, где каждый пункт —
 * только гиперссылка, практически не встречается, поэтому ложные
 * срабатывания маловероятны.
 * @param {Document} doc - документ секции (iframe)
 * @param {(msg: string, type?: string) => void} [log] - логгер (опционально)
 */
export function hideFakeTOCLists(doc, log) {
    if (!doc?.body) return;
    const _log = log || (() => {});
    try {
        const lists = doc.querySelectorAll('ul, ol');
        for (const list of lists) {
            if (list.dataset.novaFakeTocChecked) continue;
            list.dataset.novaFakeTocChecked = '1';
            const items = Array.from(list.children).filter(c => c.tagName === 'LI');
            if (items.length < 8) continue; // короткие списки — обычно реальный контент
            let linkOnlyCount = 0;
            for (const li of items) {
                const links = li.querySelectorAll('a[href]');
                const text = (li.textContent || '').trim();
                const linkText = links.length === 1 ? (links[0].textContent || '').trim() : '';
                // Пункт списка — практически только ссылка (плюс, возможно,
                // пара служебных символов вроде номера/точки вокруг неё).
                if (links.length === 1 && text.length > 0 &&
                    text.length <= linkText.length + 6) {
                    linkOnlyCount++;
                }
            }
            if (linkOnlyCount / items.length >= 0.85) {
                list.style.display = 'none';
                _log(`[FakeTOC] Скрыт технический список оглавления (${items.length} пунктов)`, 'info');
                // Список нередко идёт сразу за заголовком вида "Содержание" —
                // прячем и его, если это единственный сосед в контейнере.
                const parent = list.parentElement;
                if (parent && parent.children.length <= 2) {
                    const heading = parent.querySelector('h1, h2, h3, strong');
                    const headingText = (heading?.textContent || '').toLowerCase().trim();
                    if (/содержан|оглавлен|table of contents|^contents:?$/.test(headingText)) {
                        heading.style.display = 'none';
                    }
                }
            }
        }
    } catch (e) {
        _log(`[FakeTOC] Ошибка: ${e.message}`, 'error');
    }
}

/**
 * Скрывает рекламные секции пиратских сайтов в загруженном документе.
 * @param {Document} doc - документ секции (iframe)
 * @param {string} [fontFamily] - шрифт для заглушки "Конец книги" (опционально)
 * @param {(msg: string, type?: string) => void} [log] - логгер (опционально)
 */
export function hideAdSections(doc, fontFamily, log) {
    if (!doc?.body) return;
    const _log = log || (() => {});

    // ── Фильтр по заголовку секции ────────────────────────────────
    const HIDDEN_TITLES = [
        'nota bene', 'note bene', 'notabene',
        'от пирата', 'от пиратов', 'реклама',
    ];

    // ── Фильтр по тексту внутри секции ────────────────────────────
    // Некоторые пиратские книги не имеют заголовка "Nota bene" —
    // реклама идёт просто как обычный текст в последней секции.
    // Определяем по характерным фразам внутри абзацев.
    const HIDDEN_CONTENT = [
        'searchfloor.org',
        'цокольным этажом',
        'цокольный этаж',
        'книга предоставлена',
        'сайт заблокирован в России',
        'наградите автора лайком',
        'telegram-бот',
        'антизапрет',
        'censor tracker',
    ];

    // Скрыть контейнер элемента
    function hideContainer(el, reason) {
        let parent = el.parentElement;
        while (parent && parent !== doc.body) {
            const tag = parent.tagName?.toLowerCase();
            if (tag === 'section' || tag === 'div' || tag === 'article') {
                parent.style.display = 'none';
                _log(`[AdFilter] Скрыта секция по: "${reason}"`, 'info');
                return true;
            }
            parent = parent.parentElement;
        }
        // Нет контейнера — скрываем сам элемент и всё после него
        let sibling = el;
        while (sibling) {
            sibling.style.display = 'none';
            sibling = sibling.nextElementSibling;
        }
        return true;
    }

    // 1. Фильтр по заголовку
    const headings = doc.querySelectorAll('h1,h2,h3,h4,h5,h6,p.title,title');
    let wholeDocHidden = false;
    headings.forEach(h => {
        const text = h.textContent?.trim().toLowerCase() ?? '';
        if (HIDDEN_TITLES.some(s => text === s || text.startsWith(s))) {
            hideContainer(h, h.textContent?.trim());
            wholeDocHidden = true;
        }
    });
    if (wholeDocHidden) { injectEndOfBookMsg(doc, fontFamily); return; }


    // 2. Фильтр по содержимому абзацев
    // Ищем абзацы с характерными фразами пиратских сайтов.
    // Чтобы не скрывать случайные упоминания — требуем совпадения
    // хотя бы 2 фраз в одной секции, или 1 очень специфичной.
    const STRONG_MATCH = ['searchfloor.org', 'цокольным этажом', 'цокольный этаж'];
    const paragraphs = doc.querySelectorAll('p, div');
    paragraphs.forEach(p => {
        if (p.style.display === 'none') return; // уже скрыт
        const text = p.textContent?.toLowerCase() ?? '';
        // Сильное совпадение — скрываем сразу
        if (STRONG_MATCH.some(s => text.includes(s))) {
            hideContainer(p, text.substring(0, 40));
            injectEndOfBookMsg(doc, fontFamily);
            return;
        }
        // Слабые совпадения — считаем сколько фраз нашли
        const matches = HIDDEN_CONTENT.filter(s => text.includes(s));
        if (matches.length >= 2) {
            hideContainer(p, matches.join(', '));
            injectEndOfBookMsg(doc, fontFamily);
        }
    });
}

/**
 * Вычисляет относительную яркость hex-цвета (0 = чёрный, 1 = белый).
 * Использует формулу W3C WCAG 2.0.
 */
export function bgLuminance(hex) {
    try {
        const h = hex.replace('#', '');
        const r = parseInt(h.substring(0, 2), 16) / 255;
        const g = parseInt(h.substring(2, 4), 16) / 255;
        const b = parseInt(h.substring(4, 6), 16) / 255;
        const toLinear = c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
    } catch(e) { return 0.5; }
}
