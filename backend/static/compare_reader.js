// SPDX-FileCopyrightText: 2026 Zampher
// SPDX-License-Identifier: MPL-2.0

(function () {
  "use strict";

  const RESIZE_DELAYS_MS = [0, 100, 300, 800, 1500, 3000];
  const MIN_SCALE = 0.5;
  const MAX_SCALE = 3.0;

  let panelScale = 1.0;
  let panState = null;
  let panelLinkedScroll = false;

  function readLinkedScrollParam() {
    const value = readQueryParam("linkedScroll");
    if (value === "1" || value === "true") {
      return true;
    }
    if (value === "0" || value === "false") {
      return false;
    }
    return false;
  }

  function $(id) {
    return document.getElementById(id);
  }

  function readQueryParam(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
  }

  function clampScale(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return 1.0;
    }
    // Accept host values as either ratio (1.25) or percent (125).
    const ratio = parsed > 10 ? parsed / 100 : parsed;
    return Math.max(MIN_SCALE, Math.min(MAX_SCALE, ratio));
  }

  function showError(message) {
    const boot = $("compare-boot-loading");
    if (boot) {
      boot.classList.add("hidden");
    }
    const grid = $("compare-grid");
    if (grid) {
      grid.innerHTML =
        '<div class="compare-error">' + escapeHtml(message) + "</div>";
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function withPreviewQuery(url) {
    try {
      const parsed = new URL(url, window.location.origin);
      parsed.searchParams.set("preview", "1");
      return parsed.toString();
    } catch (error) {
      console.warn("[compare_reader] invalid document URL:", url, error);
      return url;
    }
  }

  function injectBaseHref(html, baseHref) {
    if (!html || html.indexOf("<head") === -1) {
      return html;
    }
    if (html.indexOf("<base ") !== -1) {
      return html;
    }
    return html.replace(/<head(\s[^>]*)?>/i, function (match) {
      return match + '<base href="' + baseHref + '">';
    });
  }

  function measureIframeHeight(iframe) {
    try {
      const win = iframe.contentWindow;
      const doc = win?.document;
      if (!doc) {
        return 0;
      }
      const body = doc.body;
      const root = doc.scrollingElement || doc.documentElement;
      const heights = [
        body?.scrollHeight ?? 0,
        body?.offsetHeight ?? 0,
        root?.scrollHeight ?? 0,
        root?.offsetHeight ?? 0,
      ];
      return Math.max(...heights, 0);
    } catch (error) {
      console.warn("[compare_reader] height measure failed:", error);
      return 0;
    }
  }

  function ensurePanelScrollSize(body) {
    let scrollSize = body.querySelector(".compare-panel-scroll-size");
    if (!scrollSize) {
      scrollSize = document.createElement("div");
      scrollSize.className = "compare-panel-scroll-size";
      body.appendChild(scrollSize);
    }
    return scrollSize;
  }

  function ensurePanelScaler(body) {
    const iframe = body.querySelector("iframe");
    if (!iframe) {
      return null;
    }

    const scrollSize = ensurePanelScrollSize(body);
    let scaler = body.querySelector(".compare-panel-scaler");
    if (!scaler) {
      scaler = document.createElement("div");
      scaler.className = "compare-panel-scaler";
      scrollSize.appendChild(scaler);
      scaler.appendChild(iframe);
      bindPanelPan(body);
    } else if (scaler.parentElement !== scrollSize) {
      scrollSize.appendChild(scaler);
    }
    return scaler;
  }

  function updatePanelLayout(body) {
    const scaler = ensurePanelScaler(body);
    const iframe = body.querySelector("iframe");
    if (!scaler || !iframe) {
      return;
    }

    const scrollSize = ensurePanelScrollSize(body);
    const baseWidth = body.clientWidth || body.offsetWidth || 1;
    const baseHeight = measureIframeHeight(iframe) || iframe.offsetHeight || 120;
    iframe.style.height = baseHeight + "px";

    const visualWidth = Math.ceil(baseWidth * panelScale);
    const visualHeight = Math.ceil(baseHeight * panelScale) + 4;

    scrollSize.style.width = visualWidth + "px";
    scrollSize.style.height = visualHeight + "px";

    scaler.style.width = baseWidth + "px";
    scaler.style.height = baseHeight + "px";
    scaler.style.transform = "scale(" + panelScale + ")";
    scaler.style.transformOrigin = "top left";
    body.style.cursor = panelScale > 1 ? "grab" : "";
  }

  function updateAllPanels() {
    document.querySelectorAll(".compare-panel-body").forEach(updatePanelLayout);
    const shell = $("compare-scroll-shell");
    if (shell) {
      shell.dataset.zoomed = panelScale > 1 ? "1" : "0";
      shell.dataset.linkedScroll = panelLinkedScroll ? "1" : "0";
    }
  }

  function setLinkedScroll(linked) {
    panelLinkedScroll = Boolean(linked);
    updateAllPanels();
  }

  function setPanelScale(scale) {
    panelScale = clampScale(scale);
    updateAllPanels();
  }

  function bindPanelPan(body) {
    if (body.dataset.panBound === "1") {
      return;
    }
    body.dataset.panBound = "1";
    body.addEventListener("mousedown", function (event) {
      if (event.button !== 0 || panelScale <= 1) {
        return;
      }
      panState = {
        body: body,
        startX: event.clientX,
        startY: event.clientY,
        scrollLeft: body.scrollLeft,
        scrollTop: body.scrollTop,
      };
      body.style.cursor = "grabbing";
      event.preventDefault();
    });
  }

  document.addEventListener("mousemove", function (event) {
    if (!panState) {
      return;
    }
    const dx = event.clientX - panState.startX;
    const dy = event.clientY - panState.startY;
    panState.body.scrollLeft = panState.scrollLeft - dx;
    panState.body.scrollTop = panState.scrollTop - dy;
  });

  document.addEventListener("mouseup", function () {
    if (!panState) {
      return;
    }
    if (panelScale > 1) {
      panState.body.style.cursor = "grab";
    }
    panState = null;
  });

  function resizeIframe(iframe) {
    const height = measureIframeHeight(iframe);
    if (height > 0) {
      iframe.style.height = height + "px";
    }
    const body = iframe.closest(".compare-panel-body");
    if (body) {
      updatePanelLayout(body);
    }
  }

  function scheduleIframeHeightUpdates(iframe) {
    RESIZE_DELAYS_MS.forEach(function (delayMs) {
      window.setTimeout(function () {
        resizeIframe(iframe);
      }, delayMs);
    });
  }

  function bindIframeResizeObserver(iframe) {
    try {
      const doc = iframe.contentWindow?.document;
      if (!doc?.body || typeof ResizeObserver === "undefined") {
        return;
      }
      let pending = null;
      const observer = new ResizeObserver(function () {
        if (pending !== null) {
          window.clearTimeout(pending);
        }
        pending = window.setTimeout(function () {
          pending = null;
          resizeIframe(iframe);
        }, 80);
      });
      observer.observe(doc.body);
      if (doc.documentElement) {
        observer.observe(doc.documentElement);
      }
    } catch (error) {
      console.warn("[compare_reader] resize observer failed:", error);
    }
  }

  function bindIframeLoadHandlers(iframe) {
    iframe.setAttribute("scrolling", "no");
    iframe.addEventListener("load", function () {
      resizeIframe(iframe);
      bindIframeResizeObserver(iframe);
      scheduleIframeHeightUpdates(iframe);
    });
  }

  async function loadDocumentIntoIframe(iframe, url) {
    if (!url) {
      throw new Error("Missing document URL for compare panel.");
    }

    bindIframeLoadHandlers(iframe);

    const fetchUrl = withPreviewQuery(url);
    const response = await fetch(fetchUrl, {
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(
        "Failed to load document (" + response.status + "): " + fetchUrl
      );
    }

    const html = await response.text();
    const parsed = new URL(fetchUrl, window.location.origin);
    const baseHref = parsed.origin + "/";
    const htmlWithBase = injectBaseHref(html, baseHref);
    const blob = new Blob([htmlWithBase], { type: "text/html;charset=utf-8" });
    iframe.src = URL.createObjectURL(blob);
  }

  function hideBootLoading() {
    const boot = $("compare-boot-loading");
    if (boot) {
      boot.classList.add("hidden");
    }
  }

  function bindHostMessages() {
    window.addEventListener("message", function (event) {
      const data = event.data;
      if (!data || !data.type) {
        return;
      }
      if (data.type === "owlangs-set-scale") {
        setPanelScale(data.scale);
        return;
      }
      if (data.type === "owlangs-set-linked-scroll") {
        setLinkedScroll(data.linked !== false);
      }
    });
  }

  window.owlangsCompareReader = {
    setScale: setPanelScale,
    getScale: function () {
      return panelScale;
    },
    setLinkedScroll: setLinkedScroll,
    getLinkedScroll: function () {
      return panelLinkedScroll;
    },
    refreshLayout: updateAllPanels,
  };

  async function init() {
    bindHostMessages();

    panelLinkedScroll = readLinkedScrollParam();

    const sourceUrl = readQueryParam("source");
    const targetUrl = readQueryParam("target");
    const sourceLabel = readQueryParam("sourceLabel") || "Source";
    const targetLabel = readQueryParam("targetLabel") || "Target";
    const initialScale = readQueryParam("scale");
    if (initialScale) {
      panelScale = clampScale(parseFloat(initialScale));
    }

    if (!sourceUrl || !targetUrl) {
      showError(
        "Missing required query parameters: source and target document URLs."
      );
      return;
    }

    const sourceLabelEl = $("compare-source-label");
    const targetLabelEl = $("compare-target-label");
    const sourceFrame = $("compare-source-frame");
    const targetFrame = $("compare-target-frame");

    if (!sourceFrame || !targetFrame) {
      showError("Compare reader layout is not initialized.");
      return;
    }

    if (sourceLabelEl) {
      sourceLabelEl.textContent = sourceLabel;
    }
    if (targetLabelEl) {
      targetLabelEl.textContent = targetLabel;
    }

    try {
      await Promise.all([
        loadDocumentIntoIframe(sourceFrame, sourceUrl),
        loadDocumentIntoIframe(targetFrame, targetUrl),
      ]);
      hideBootLoading();
      updateAllPanels();
    } catch (error) {
      console.error("[compare_reader] init failed:", error);
      showError(String(error));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init();
    });
  } else {
    init();
  }
})();
