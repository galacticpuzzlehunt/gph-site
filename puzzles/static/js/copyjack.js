const jackInlineStyles = (e) => {
  const styles = window.getComputedStyle(e);
  const otherStyles = [
    "background-color",
    "color",
    "font-family",
    "font-weight",
    "font-size",
    "font-style",
    "text-align",
  ].map((prop) => `${prop}: ${styles.getPropertyValue(prop)};`);
  e.setAttribute("style", [...otherStyles, e.style.cssText].join(" "));
};

const jackInlineBorders = (e) => {
  const styles = window.getComputedStyle(e);
  const borderStyles = ["top", "bottom", "right", "left"].map((dir) => {
    const f = (x) => styles.getPropertyValue(`border-${dir}-${x}`);
    const [width, style, color] = ["width", "style", "color"].map(f);
    if (width === "0px") return "";
    return `border-${dir}: ${width} ${style} ${
      color === "rgb(0, 0, 0)" ? "black" : "gray"
    };`;
  });
  e.setAttribute("style", [...borderStyles, e.style.cssText].join(" "));
};

const copyJack = (copyable, skips) => {
  const f = (t, x, y) =>
    Array.from(t.querySelectorAll(x)).forEach(
      (e) => Array.from(e.classList).includes("copy-verbatim") || y(e)
    );
  // do not copyjack twice
  if (skips.copyJacked) return;
  skips.copyJacked = true;

  // add reset spans after spans, headings, divs, p
  // and inline styles too
  ["span", "h1", "h2", "h3", "h4", "h5", "h6", "div", "p"].forEach((tag) =>
    f(copyable, tag, (e) => {
      if (!skips.spanreset) {
        const reset = document.createElement("span");
        reset.style.backgroundColor = "transparent";
        reset.style.color = "black";
        reset.style.fontWeight = "normal";
        reset.style.fontStyle = "normal";
        reset.style.fontSize = "1em";
        reset.style.textAlign = "left";
        e.parentNode.insertBefore(reset, e.nextSibling);
      }

      if (!skips.styleinline) jackInlineStyles(e);
    })
  );

  // change blank tags to <pre> tags, change boxed to []
  f(copyable, ".blanks", (e) => {
    if (!skips.blanks) {
      e.classList.add("no-copy");
      const pre = document.createElement("pre");
      pre.classList.add("copy-only");
      pre.innerHTML = e.innerHTML;
      f(pre, ".boxed", (e) => (e.innerHTML = "[" + e.innerHTML + "]"));
      e.parentNode.insertBefore(pre, e.nextSibling);
    }
  });

  // change numbered blank tags to <pre> tags, change <u>x</u> to _(x)
  f(copyable, ".numbered-blanks", (e) => {
    if (!skips.numberedblanks) {
      e.classList.add("no-copy");
      const pre = document.createElement("pre");
      pre.classList.add("copy-only");
      pre.innerHTML = e.innerHTML;
      f(pre, "u", (e) => {
        e.style.textDecoration = "none";
        e.innerHTML = e.innerHTML ? "_(" + e.innerHTML + ")" : "_";
      });
      e.parentNode.insertBefore(pre, e.nextSibling);
    }
  });

  // add [See original puzzle for image] to images
  f(copyable, "img", (e) => {
    if (!skips.imglabel) {
      const label = document.createElement("p");
      label.className = "copy-only";
      label.textContent = gettext("[See original puzzle for image]");
      e.parentNode.insertBefore(label, e.nextSibling);
    }
  });

  // inline th, td borders and styles
  // does NOT work if border color isn't black or gray
  // or if the borders per side are different
  ["th", "td"].forEach((tag) =>
    f(copyable, tag, (e) => {
      if (!skips.borderinline) jackInlineBorders(e);
      if (!skips.styleinline) jackInlineStyles(e);
    })
  );

  f(copyable, "ol > li", (e) => {
    if (!skips.orderedlist) {
      const bullet = document.createElement("span");
      bullet.className = "copy-only";
      bullet.textContent = (e.value ||
          Array.from(e.parentElement.children).indexOf(e) + 1) + ". ";
      e.insertBefore(bullet, e.firstChild);
    }
  });

  f(copyable, "ul > li", (e) => {
    if (!skips.unorderedlist) {
      const bullet = document.createElement("span");
      bullet.className = "copy-only";
      bullet.textContent = "- ";
      e.insertBefore(bullet, e.firstChild);
    }
  });
};

const copyContents = async (btnElt, btnText) => {
  const copyable = btnElt.closest(".clipboard-container");
  if (copyable) {
    copyJack(copyable, btnElt.dataset);
    const f = (x, y) =>
      Array.from(copyable.getElementsByClassName(x)).forEach(y);
    f("copy-only", (e) => (e.style.display = "initial"));
    f("no-copy", (e) => (e.style.display = "none"));
    if (window.getSelection()) window.getSelection().removeAllRanges();
    const range = document.createRange();
    range.selectNode(copyable);
    if (window.getSelection()) window.getSelection().addRange(range);
    if (btnElt) btnElt.style.display = "none";
    document.execCommand("copy");
    if (btnElt) btnElt.style.display = "block";
    f("copy-only", (e) => e.style.removeProperty("display"));
    f("no-copy", (e) => e.style.removeProperty("display"));
  }
  if (window.getSelection()) window.getSelection().removeAllRanges();
  btnText.textContent = gettext("Copied to clipboard!");
  setTimeout(() => {
    btnText.textContent = gettext("Copy to clipboard");
  }, 3000);
};

window.addEventListener("load", () => {
  for (const clipboardButton of document.getElementsByClassName("clipboard-button")) {
    // fill contents
    const btnText = document.createElement("span");
    btnText.textContent = gettext("Copy to clipboard");
    clipboardButton.appendChild(btnText);
    clipboardButton.addEventListener("click", () =>
      copyContents(clipboardButton, btnText)
    );
  }
});
