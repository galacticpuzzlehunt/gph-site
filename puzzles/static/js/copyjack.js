/**
 * **Update Jan 18 2022.**
 * Google Sheets changed how they do images, so the image copying code needs to
 * be redone. If you're fixing this, I recommend tools like InsideClipboard on
 * Windows or Clipboard Viewer on OSX. Then set up a Google Sheet with images in
 * cells, do some copy and pasting, and see what data format Sheets uses to
 * copy images.
 *
 * From a very cursory investigation, it appears to now use `img` tags with a
 * base64 encoded image. This should be possible to replicate and so restore
 * copy-to-clipboard support for images.
 */

/**
 * Helper to implement puzzle copying by setting inline styles on the copied elements.
 *
 * Behaviour:
 *  - Image copying! This tries its best to copy images so that they are
 *    displayed when pasted into spreadsheets. In general, images work when
 *    pasted into Google Sheets, and are replaced with descriptive text plus a
 *    link when pasted into Excel.
 *     - Images are automatically skipped if they (or an ancestor) are marked as
 *       no-copy or as ARIA hidden.
 *     - The descriptive text is used all the time for Excel, and in certain
 *       fallback cases for Sheets. It will be one of:
 *         - A link to the image with text "See original puzzle for image" if the
 *           image has no alt text.
 *         - A link to the image with text "Image: <alt text>" if the image has
 *           alt text.
 *     - Inline images (where multiple images are shown on one row in the puzzle)
 *       are each given their own row in the copied content. This is necessary
 *       for embedding images in Sheets, or making links work.
 *     - If an image is within a `td` or `th`, image embedding/linking will only
 *       work if the image is the only thing within the cell.
 *     - Background images will not be copied.
 *     - If developing locally, the images can't be fetched from localhost, so
 *       we fall back to the Excel behaviour.
 *     - If the image is already within a different link, we don't change that
 *       link.
 *  - It ignores the font-style style if it is the same as the default hunt font,
 *    as it is unlikely the paste target has our hunt font available.
 *  - If a paragraph contains linked text, the whole paragraph will become a link.
 *  - If a table cell contains linked text, the whole paragraph will become a
 *    link. (This needs a hacky workaround for Sheets, so may be brittle.)
 *  - When copying tables, only borders on `th` and `td` elements will have any
 *    effect. Make sure borders are set on those instead of relying on styles for
 *    the `table` or `tr` elements.
 *  - If there is a border on every side, then due to browser weirdness, each
 *    side of the cell must have the same border (at least when copying into
 *    Google Sheets). This makes certain layouts such as having a thicker
 *    outside border challenging.
 *
 * This automatically runs on page load, and finds a button with ID `clipboard-button`.
 * If present, the button becomes a copy puzzle button. The button should contain no
 * content, and be hidden by default so it does not appear if javascript is disabled.
 *   `<button id="clipboard-button"></button>`
 *
 * It uses class names to find puzzle content and control copying.
 *  - `.puzzle` contains the root container for all puzzle content. Everything
 *    within this will be copied by default.
 *  - `.copy-only` contains content that should be included in the clipboard
 *    version only.
 *  - `.no-copy` contains content that should be included in the web version only.
 *
 * Puzzle settings can optionally be added to the clipboard button to control
 * copying globally, or to a DOM node to control copying for that element.
 * As an example, you could use the following to disable adding inline styles
 * globally or for a single element.
 *   `<button id="clipboard-button" data-skip-inline-styles="true"></button>`
 *   `<div src="..." alt="..." data-skip-inline-styles="true">`
 *
 * Available settings are:
 *  - `data-skip-inline-styles`: Don't inject inline styles. Use this is the
 *    styling is mostly decorative, and would be obtrusive in the copied content.
 *  - `data-skip-inline-borders`: Don't inject inline borders. Use this when the
 *    border styling is mostly decorative (say subtle gray borders).
 *  - `data-skip-table-breaks`: Don't inject a br after tables (and hr) elements.
 *  - `data-copy-only-styles`: Style string to inject when copying the element.
 *  - `data-copy-input-value`: Use the value of an input when copying.
 *  - `data-force-rejack`: Force re-run the insertion of copyjack elements (useful
 *  if the page content changes dynamically).
 *
 * The global CSS should have the following styles to support copy-jacking.
 * ```
 * #clipboard-button:not(.shown) {
 *   display: none;
 * }
 *
 * .puzzle .copy-only {
 *   display: none;
 * }
 * ```
 *
 * *Warning*: If the puzzle content changes dynamically, newly added content may
 * be copied differently to original content.
 */

const PASTED_FONT_FAMILY = 'Arial, sans-serif';
let defaultHuntFontFamily = null;
let defaultHuntFontSize = '1em';

window.addEventListener("load", () => {
  const bodyStyles = window.getComputedStyle(document.body);
  defaultHuntFontFamily = bodyStyles.getPropertyValue("font-family");
  defaultHuntFontSize = bodyStyles.getPropertyValue('font-size');

  const clipboardButton = document.querySelector(".clipboard-button");
  if (clipboardButton) {
    bootstrapClipoardButton(clipboardButton);
  }
});

function bootstrapClipoardButton(clipboardButton) {
  clipboardButton.classList.add('shown');

  const puzzleElement = document.querySelector(".clipboard-container");
  if (!puzzleElement) return;

  // Fill default button contents.
  clipboardButton.textContent = gettext("Copy to clipboard");
  clipboardButton.addEventListener("click", () => {
    // Show copy status within button. Do this before copying, so the copy handler
    // can change the status if needed.
    clipboardButton.textContent = gettext("Copied to clipboard!");

    copyContents(puzzleElement, clipboardButton.dataset);
    setTimeout(() => {
      clipboardButton.textContent = gettext("Copy to clipboard");
    }, 3000);
  });

  // Intercept copies that were due to clicking clipboardButton, and assemble
  // the copied HTML.
  //
  // Note: this is a little awkward to work around an issue in Chrome with
  // Google Sheets.
  //
  // A simpler solution that works in Firefox is to remove this copy handler,
  // and do the following in `copyContents`.
  //   ```
  //   // Toggle .copy-only and .no-copy content.
  //   rootElement.classList.add("copying");
  //   selection.removeAllRanges();
  //
  //   // Select and copy the puzzle.
  //   const range = document.createRange();
  //   range.selectNode(rootElement);
  //   selection.addRange(range);
  //   document.execCommand("copy");
  //
  //   // Restore initial state.
  //   selection.removeAllRanges();
  //   rootElement.classList.remove("copying");
  //   ''`
  //
  // In Chrome, this breaks because execCommand injects default text styles on
  // the `<google-sheets-html-origin>` tag, and then Sheets doesn't show images
  // any more.
  //
  // Instead, we assemble our own versions of the plain text and HTML clipboard
  // data. The main downside is it is more inefficient, and the plain text
  // version is less sophisticated.
  document.addEventListener('copy', event => {
    if (!puzzleElement.dataset.interceptNextCopy) {
      return;
    }
    delete puzzleElement.dataset.interceptNextCopy;

    const cloned = recursiveClone(
      puzzleElement,
      node => {
        if (node.nodeType !== Node.ELEMENT_NODE) return true;
        if (node.tagName.toLowerCase() === 'script') return false;
        if (node.tagName.toLowerCase() === 'style') return false;
        if (node.tagName.toLowerCase() === 'link') return false;
        if (node.tagName.toLowerCase() === 'math') return false;
        return !node.classList.contains('no-copy') && !node.classList.contains('hidden') && !node.classList.contains('errata');
      },
      node => {
        if (node.nodeType !== Node.ELEMENT_NODE) return;


        if (node.dataset.copyOnlyStyles) {
          node.setAttribute(
            "style",
            `${node.style.cssText} ${node.dataset.copyOnlyStyles}`
          );
          delete node.dataset.copyOnlyStyles;
        }
        // Make links absolute.
        if (node.tagName.toLowerCase() === 'a' && node.href) {
          node.href = makeHrefAbsolute(node.href);
        }
        // Set the font family to a websafe default if it matches our default hunt font.
        // In this case, the font family carries no information, and as the paste target
        // probably won't have the font available, use something it can handle.
        if (node.style.fontFamily === defaultHuntFontFamily) {
          node.style.fontFamily = PASTED_FONT_FAMILY;
        }
        // Coerce start -> left as otherwise Sheets treats it as right-aligned sometimes.
        if (node.style.textAlign && node.style.textAlign === 'start') {
          node.style.textAlign = 'left';
        }
        // Copy values out of inputs. Do this lazily on copy as inputs can change.
        if (node.tagName.toLowerCase() === 'input' && node.dataset.copyInputValue) {
          return document.createTextNode(node.value);
        }
      });

    // Allow puzzle-specific copy transformations.
    if (window.puzzleOnCopy) {
      window.puzzleOnCopy(cloned);
    }

    const plainTextVersion = trimPlainText(cloned.innerText);
    if (!plainTextVersion) {
      document.querySelector(".clipboard-button span").innerText = gettext('Nothing was copied');
    }

    event.clipboardData.setData('text/plain', plainTextVersion);
    event.clipboardData.setData('text/html', cloned.innerHTML);
    event.preventDefault();
  });

  // Make sure the button isn't copied.
  clipboardButton.classList.add("no-copy");
}

function copyContents(rootElement, config) {
  const selection = window.getSelection();
  if (!selection) return;

  // Modify the puzzle content (once), so that it is amenable to copying.
  if (!rootElement.dataset.copyjacked || config.forceRejack) {
    copyJack(rootElement, config);
    rootElement.dataset.copyjacked = 'true';
  }

  // Defer to the copy handler to assemble the copied content. Ideally, we'd
  // select rootElement and let the browser assemble the copied content, but it
  // breaks Sheets interop in Chrome. See the comment for the copy handler for
  // info.
  rootElement.dataset.interceptNextCopy = 'true';

  // Select and copy the puzzle.
  // This is needed for Safari, which won't let us execute 'copy' unless we have
  // selected something.
  selection.removeAllRanges();
  const range = document.createRange();
  range.selectNode(rootElement);
  selection.addRange(range);

  document.execCommand("copy");

  // Restore initial state.
  selection.removeAllRanges();
}

/**
 * One-time processing for puzzle content in `rootElement` to make it amenable to copying.
 */
function copyJack(rootElement, config) {
  const getSetting = (element, setting) =>
    element.dataset[setting] || config[setting];

  // Inject <google-sheets-html-origin> element so Google Sheets interop works.
  const sheetsInteropElement = document.createElement('google-sheets-html-origin');
  rootElement.insertBefore(sheetsInteropElement, rootElement.firstElementChild.nextSibling);

  // Ensure everything with aria-hidden="true" is not copied, unless it's within
  // some copy-only content.
  for (const element of document.querySelectorAll('[aria-hidden="true"]')) {
    if (!element.closest('.copy-only')) {
      element.classList.add('no-copy');
    }
  }

  // Change blank tags to pre, and handle boxed blanks.
  for (const element of rootElement.querySelectorAll(".blanks")) {
    element.classList.add("no-copy");

    const copiedElement = document.createElement("pre");
    copiedElement.classList.add("copy-only");

    for (const child of element.childNodes) {
      copiedElement.appendChild(child.cloneNode(true));
    }

    for (const boxedElement of copiedElement.querySelectorAll(".boxed")) {
      boxedElement.innerHTML = "[" + boxedElement.innerHTML + "]";
    }
    element.parentNode.insertBefore(copiedElement, element.nextSibling);
    copyJackInlineStyles(copiedElement);
  }

  // Change numbered blank tags to pre, change <u>x</u> to _(x), and inject some spaces.
  for (const element of rootElement.querySelectorAll(".numbered-blanks")) {
    element.classList.add("no-copy");

    const copiedElement = document.createElement("pre");
    copiedElement.classList.add("copy-only");

    // Skip text nodes, and only keep element children.
    for (const child of element.children) {
      const isWordBreak = child.nodeType === Node.ELEMENT_NODE && child.classList.contains('word-break');
      copiedElement.appendChild(
        isWordBreak ? document.createTextNode('   ') : child.cloneNode(true));
    }

    for (const underlineElement of copiedElement.querySelectorAll("u")) {
      // Prevent underlines showing up in the copied content, as they won't be
      // spaced out nicely. Also inject a space after the underlined element.
      underlineElement.style.textDecoration = "none";
      underlineElement.innerHTML = underlineElement.innerHTML
        ? "_(" + underlineElement.innerHTML + ") "
        : "_ ";
    }
    element.parentNode.insertBefore(copiedElement, element.nextSibling);
    copyJackInlineStyles(copiedElement);
  }

  // Change .blank-word tags to some underscores.
  for (const element of rootElement.querySelectorAll(".blank-word")) {
    const copiedElement = element.cloneNode(true);
    copiedElement.classList.add("copy-only");
    copiedElement.innerText = '_____';
    element.parentNode.insertBefore(copiedElement, element.nextSibling);

    element.classList.add("no-copy");
  }

  // Replace images with a link to the image, unless it is decorational.
  for (const element of rootElement.querySelectorAll("img")) {
    copyJackImage(element);
  }

  // Insert numbers and letters for ordered lists.
  for (const list of rootElement.querySelectorAll('ol')) {
    if (list.classList.contains('no-bullets')) {
      continue;
    }
    const listStyleType = window.getComputedStyle(list).getPropertyValue('list-style-type');
    let lastIndex = 0;
    for (const item of list.querySelectorAll('li')) {
      const index = item.value ? parseInt(item.value, 10) : lastIndex + 1;
      const displayedIndex = resolveListIndex(index, listStyleType);
      lastIndex = index;

      const span = document.createElement('span');
      span.classList.add('copy-only');
      span.setAttribute('data-skip-inline-styles', 'true');
      span.innerText = displayedIndex;
      item.insertBefore(span, item.firstChild);
    }
  }

  // Wrap .italicized.preserve-on-copy with underscores.
  for (const element of rootElement.querySelectorAll('.italicized.preserve-on-copy')) {
    const prefix = document.createElement('span');
    prefix.classList.add('copy-only');
    prefix.innerText = '_';

    const suffix = prefix.cloneNode(true);
    element.insertBefore(prefix, element.firstChild);
    element.appendChild(suffix);
  }

  // Insert copy-only versions of a caption before the table, as google sheets
  // does not like them.
  for (const element of rootElement.querySelectorAll('caption')) {
    if (element.classList.contains('no-copy')) continue;
    if (element.classList.contains('sr-only')) continue;
    const parentTable = element.closest('table');

    const copyableCaption = document.createElement('div');
    copyableCaption.innerHTML = element.innerHTML;
    copyableCaption.classList.toggle('copy-only', true);
    element.classList.toggle('no-copy', true);

    for (const key in element.dataset) {
      copyableCaption.dataset[key] = element.dataset[key];
    }

    parentTable.parentNode.insertBefore(copyableCaption, parentTable);
  }

  // Add inline styles to content elements and follow them with a reset span.
  for (const tag of ["span", "h1", "h2", "h3", "h4", "h5", "h6", "div", "p", "pre", "code", "ul", "ol", "i", "u", "b", "strong", "em", "sub", "sup", "a"]) {
    for (const element of rootElement.querySelectorAll(tag)) {
      if (element.closest('no-copy')) continue;
      if (getSetting(element, 'skipInlineStyles')) continue;

      copyJackInlineStyles(element);
      maybeAppendResetSpan(element);
    }
  }

  // Add inline styles and borders to table cells.
  for (const tag of ["th", "td"]) {
    for (const element of rootElement.querySelectorAll(tag)) {
      if (!getSetting(element, 'skipInlineBorders')) {
        copyJackInlineBorders(element);
      }
      if (!getSetting(element, 'skipInlineStyles')) {
        copyJackInlineStyles(element);
      }

      // Fix table cells that contain links for Google Sheets.
      copyJackTableLinks(element);
    }
  }

  // Crossword and grid copying.
  // Add a blank line after each child of .prefer-2-col.
  for (const container of rootElement.querySelectorAll('.prefer-2-col')) {
    for (const child of Array.from(container.children)) {
      const br = document.createElement('br');
      br.classList.add("copy-only");
      container.insertBefore(br, child);
    }
  }

  // Move the clues to the bottom in a .clued-item-container.
  for (const container of rootElement.querySelectorAll('.clued-item-container')) {
    for (const clues of container.querySelectorAll('.clues')) {
      if (clues.parentNode !== container) continue;

      const copied = recursiveClone(clues);
      copied.classList.add('copy-only');
      clues.classList.add('no-copy');

      container.appendChild(copied);
    }
  }

  // If a crossword grid contains clues, make two copies.
  for (const crossword of rootElement.querySelectorAll('table.crossword')) {
    if (!crossword.querySelectorAll('.clue').length) continue;

    const copied = recursiveClone(
      crossword,
      node => node.nodeType !== Node.ELEMENT_NODE || !node.classList.contains('clue')
    );
    copied.classList.add('copy-only');
    crossword.parentNode.insertBefore(copied, crossword.nextSibling);
  }

  // Append a . and space to each crossword clue.
  for (const clue of rootElement.querySelectorAll('table.crossword .clue')) {
    const hasOtherText = clue.parentNode.innerText.trim() !== clue.innerText.trim();
    const span = document.createElement('span');
    span.classList.add('copy-only');
    span.innerText = hasOtherText ? '. ' : '';
    clue.appendChild(span);
  }

  // Fix top borders of barred grids. We remove them when copying to allow
  // different border widths when pasting to Sheets.
  for (const barredGrid of rootElement.querySelectorAll('table.barred.grid')) {
    const firstRow = barredGrid.querySelector('tr');
    if (!firstRow) continue;
    const numberOfColumns = firstRow.querySelectorAll('td, th').length;

    const fakeRow = document.createElement('tr');
    fakeRow.classList.add('copy-only');
    for (let i = 0; i < numberOfColumns; i++) {
      const fakeCell = document.createElement('td');
      fakeCell.classList.add('no-border');
      fakeRow.appendChild(fakeCell);
    }
    firstRow.parentNode.insertBefore(fakeRow, firstRow);

    const rows = Array.from(barredGrid.querySelectorAll('tr'));
    let lastRowCells = Array.from(fakeRow.children);
    for (let i = 1; i < rows.length; i++) {
      const rowCells = Array.from(rows[i].querySelectorAll('td, th'));
      if (lastRowCells.length !== rowCells.length) {
        console.warn('Can\'t include top borders for barred grid - col count mismatch');
        break;
      }

      for (let j = 0; j < rowCells.length; j++) {
        const lastCellStyle = window.getComputedStyle(lastRowCells[j]);
        const cellStyle = window.getComputedStyle(rowCells[j]);
        if (lastCellStyle.getPropertyValue('border-bottom-width') === '0px' && cellStyle.getPropertyValue('border-top-width') !== '0px') {
          const width = cellStyle.getPropertyValue('border-top-width');
          const style = cellStyle.getPropertyValue('border-top-style');
          const color = cellStyle.getPropertyValue('border-top-color');

          // Note as of Feb 13 2023:
          // Colored borders work in Google Sheets. Previously, it only handled
          // black and gray borders.
          // Google Sheets only likes 1px and 3px borders, so we coerce border width.
          // Tested in Chrome, Firefox, and Safari.
          const coercedWidth = parseInt(width, 10) < 2 ? '1px' : '3px';
          const injectedStyle = `border-bottom: ${coercedWidth} ${style} ${color};`;
          lastRowCells[j].dataset.copyOnlyStyles = (lastRowCells[j].dataset.copyOnlyStyles || '') + injectedStyle;
        }
      }

      lastRowCells = rowCells;
    }
  }

  // Add breaks after tables and hr elements.
  // Should be done after we duplicate grids with clues.
  for (const tag of ["table", "hr"]) {
    for (const element of rootElement.querySelectorAll(tag)) {
      if (getSetting(element, 'skipTableBreaks')) continue;

      const br = document.createElement('br');
      br.classList.add("copy-only");
      element.parentNode.insertBefore(br, element.nextSibling);
    }
  }
}

function copyJackInlineStyles(element) {
  const styles = window.getComputedStyle(element);
  // We can't read the styles reliably if it is hidden.
  if (styles.getPropertyValue('display') === 'none') {
    return;
  }

  const isBackgroundColorTransparent = styles.getPropertyValue('background-color') !== 'rgba(0, 0, 0, 0)';
  const jackedStyles = [
    // Only copyjack the background color if it isn't transparent. Otherwise, we
    // could clobber an inherited background color.
    ...(isBackgroundColorTransparent ? ["background-color"] : []),
    "color",
    'font-family',
    "font-weight",
    "font-size",
    "font-style",
    "text-align",
  ].map((prop) => `${prop}: ${styles.getPropertyValue(prop)};`);
  element.setAttribute(
    "style",
    [...jackedStyles, element.style.cssText].join(" ")
  );
}

function maybeAppendResetSpan(element) {
  // Don't break flex/grid containers by adding extra spans into them.
  const parentStyles = window.getComputedStyle(element.parentNode);
  const parentDisplay = parentStyles.getPropertyValue('display');
  if (parentDisplay.endsWith('flex') || parentDisplay.endsWith('grid')) return;

  const display = window.getComputedStyle(element).getPropertyValue('display');
  if (display.startsWith('inline')) {
    let nonInlineParent = element.parentNode;
    while (nonInlineParent && window.getComputedStyle(nonInlineParent).getPropertyValue('display').startsWith('inline')) {
      nonInlineParent = nonInlineParent.parentNode;
    }
    const nonInlineParentDisplay = window.getComputedStyle(nonInlineParent).getPropertyValue('display');
    if (nonInlineParent === element.parentNode && (nonInlineParentDisplay.endsWith('flex') || nonInlineParentDisplay.endsWith('grid'))) return;

    // Keep the inline element styles if it is the only text content.
    if (nonInlineParent.innerText.trim() === element.innerText.trim()) {
      return;
    }
  }

  const reset = document.createElement("span");
  reset.style.backgroundColor = "transparent";
  reset.style.color = "black";
  reset.style.fontFamily = defaultHuntFontFamily;
  reset.style.fontWeight = "normal";
  if (display.startsWith('inline')) {
    reset.style.fontSize = parentStyles.getPropertyValue('font-size');
  } else {
    reset.style.fontSize = parentDisplay.defaultHuntFontSize;
  }
  reset.style.fontStyle = "normal";
  reset.style.textAlign = "left";
  reset.style.textDecoration = "none";

  reset.classList.toggle('copyjack-reset', true);

  element.parentNode.insertBefore(reset, element.nextSibling);
}

function copyJackInlineBorders(element) {
  // For barred grids, we need some awkward workarounds so they copy correctly.
  // Essentially, if we want borders with different thickness, one of the
  // borders must be missing or it copies wrong.
  //
  // We hack it by removing the top border. And then injecting a row at the top
  // of the table and give it a bottom-border. There's some sophistication to
  // handle cells that have no border though.
  const inBarredGrid = !!element.closest('.barred');
  const styles = window.getComputedStyle(element);
  const borderStyles = ["top", "bottom", "right", "left"].map((dir) => {
    const [width, style, color] = ["width", "style", "color"].map((attribute) =>
      styles.getPropertyValue(`border-${dir}-${attribute}`)
    );
    if (width === "0px") return "";
    // In barred grids, force the top border to 0px. Separately, a top row will
    // be injected at copy time.
    if (inBarredGrid && dir === 'top') return "";
    // Note as of Feb 13 2023:
    // Colored borders work in Google Sheets. Previously, it only handled
    // black and gray borders.
    // Google Sheets only likes 1px and 3px borders, so we coerce border width.
    // Tested in Chrome, Firefox, and Safari.
    const coercedWidth = parseInt(width, 10) < 2 ? '1px' : '3px';
    return `border-${dir}: ${coercedWidth} ${style} ${color};`;
  });
  // Mark as copyOnlyStyles to avoid changing the visual display of the grid.
  const borderStylesText = borderStyles.join(" ").trim();
  if (borderStylesText) {
    element.dataset.copyOnlyStyles = (element.dataset.copyOnlyStyles || '') + borderStylesText;
  }
}

function copyJackTableLinks(element) {
  if (element.children.length === 1 && element.firstElementChild.tagName.toLowerCase() === 'a') {
    // In Google Sheets, links within table cells won't work. Add special case
    // handling for the case where the table cell directly contains an anchor tag.
    //
    // Note: we use children and firstElementChild to ignore text/comment nodes.
    element.dataset.sheetsValue = '';
    element.dataset.sheetsHyperlink = makeHrefAbsolute(element.firstElementChild.href);
  }
}

function copyJackImage(element) {
  const shouldBeSkipped = (el) => el.classList.contains("no-copy");
  if (findAncestor(element, shouldBeSkipped)) {
    return;
  }

  element.classList.add('no-copy');

  const altText = element.getAttribute("alt");
  const label = altText
    ? `[${gettext('Image:')} ${altText}]`
    : gettext("[See original puzzle for image]");

  const container = document.createElement("div");
  container.className = "copy-only";

  let labelElement = container;

  // Nested links don't work, so don't wrap the image with an anchor tag if
  // there is a parent anchor tag already.
  const ancestorLink = findAncestor(element, el => el.tagName.toLowerCase() === 'a');
  const copiedImageLink = ancestorLink ? ancestorLink.href : element.src;

  // In Google Sheets, we can use special attributes to let images render
  // inline. If the image is inside a `th` or `td` tag already, then these
  // special attributes need to be placed on that element.
  let sheetsImageWrapper;
  const ancestorTableCell = findAncestor(element, el => {
    const parentTagName = el.tagName.toLowerCase();
    return parentTagName === 'td' || parentTagName === 'th';
  });
  if (ancestorTableCell) {
    // If there is other content, placing the special attributes will hide the
    // other content. That's bad, so bail out of embedding our inline images.
    //
    // As an approximation, content can either be images or text. We can use
    // innerText instead of textContent, so that if the text if hidden (say with
    // no-copy), then it doesn't break us.
    const tableCellHasOtherContent =
      ancestorTableCell.innerText.trim() || ancestorTableCell.querySelectorAll('img').length > 1;
    if (!tableCellHasOtherContent) {
      sheetsImageWrapper = ancestorTableCell;
    }
  } else {
    sheetsImageWrapper = document.createElement('div');
    labelElement = sheetsImageWrapper;
    container.appendChild(sheetsImageWrapper);
  }

  if (sheetsImageWrapper) {
    sheetsImageWrapper.dataset.sheetsValue = '';
    if (element.src && !isLocalhostUrl(element.src)) {
      // Local URLs won't load when pasted into Google Sheets, so skip embedding them.
      sheetsImageWrapper.dataset.sheetsFormula = `=image("${element.src}")`;
    } else {
      // Links in table cell elements won't work for Google Sheets, set the
      // hyperlink on the cell directly.
      //
      // This will only have an effect if we haven't already embedded an image
      // in the cell, so check that first.
      sheetsImageWrapper.dataset.sheetsHyperlink = copiedImageLink;
    }
  }

  if (ancestorLink) {
    labelElement.textContent = label;
  } else {
    const imageLink = document.createElement("a");
    imageLink.href = makeHrefAbsolute(copiedImageLink);
    imageLink.textContent = label;
    labelElement.appendChild(imageLink);
  }

  element.parentNode.insertBefore(container, element.nextSibling);
}

function findAncestor(el, predicate) {
  while (el && el !== document.body) {
    if (predicate(el)) {
      return el;
    }
    el = el.parentNode;
  }
  return null;
}

function isLocalhostUrl(url) {
  const parsed = new URL(url);
  return parsed.hostname.toLowerCase() === 'localhost' || parsed.hostname === '127.0.0.1';
}

function recursiveClone(rootNode, filterPredicate = () => true, transformer = () => {}) {
  const result = rootNode.cloneNode();
  const transformedResult = transformer(result) || result;

  for (const child of rootNode.childNodes) {
    if (filterPredicate(child)) {
      transformedResult.appendChild(recursiveClone(child, filterPredicate, transformer));
    }
  }
  return transformedResult;
}

function makeHrefAbsolute(href) {
  return href.startsWith('/') ? location.origin + href : href;
}

function resolveListIndex(index, listStyleType) {
  switch (listStyleType) {
    case 'upper-alpha':
      return String.fromCharCode(64 + Math.max(Math.min(index, 26), 1)) + '. ';

    case 'lower-alpha':
      return String.fromCharCode(96 + Math.max(Math.min(index, 26), 1)) + '. ';

    case 'decimal':
    default:
      return index.toString() + '. ';
  }
}

// TODO(sahil): I'm sure this can be made more efficient.
const LEADING_WHITESPACE_REGEX = /^[^\S\r\n]+/mg;
const MANY_LF_REGEX = /\n{3,}/g;
const MANY_CRLF_REGEX = /(\r\n){3,}/g;
function trimPlainText(rawPlainText) {
  let result = rawPlainText.trim();
  result = result.replaceAll(LEADING_WHITESPACE_REGEX, '');
  result = result.replaceAll(MANY_LF_REGEX, '\n\n');
  result = result.replaceAll(MANY_CRLF_REGEX, '\r\n\r\n');
  return result;
}
