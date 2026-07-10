/**
 * Floating AI Chatbot Widget — right-side drawer with resize handle
 * Follows the same IIFE pattern as dashboard.js
 */
(function () {
    "use strict";

    var fab, panel, closeBtn, iframe, resizeHandle;
    var iframeLoaded = false;
    var gradioUrl = "http://localhost:7860";

    // ---- Resize state ----
    var isResizing = false;
    var startX = 0;
    var startWidth = 0;
    var currentWidth = 0;   // tracks the panel width in px during resize

    function init() {
        fab = document.getElementById("chatbotFAB");
        panel = document.getElementById("chatbotPanel");
        closeBtn = document.getElementById("chatbotClose");
        iframe = document.getElementById("chatbotIframe");
        resizeHandle = document.getElementById("chatbotResizeHandle");

        if (!fab || !panel) return;

        // Read Gradio URL from data attribute
        if (iframe && iframe.dataset.gradioUrl) {
            gradioUrl = iframe.dataset.gradioUrl;
        }

        // FAB click: show panel
        fab.addEventListener("click", function () {
            openPanel();
        });

        // Close button: hide panel
        if (closeBtn) {
            closeBtn.addEventListener("click", function () {
                closePanel();
            });
        }

        // Escape key: hide panel
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && panel.classList.contains("open")) {
                closePanel();
            }
        });

        // ---- Resize Handle Events ----
        if (resizeHandle) {
            resizeHandle.addEventListener("mousedown", onResizeStart);
        }
        document.addEventListener("mousemove", onResizeMove);
        document.addEventListener("mouseup", onResizeEnd);

        // Touch support for resize
        if (resizeHandle) {
            resizeHandle.addEventListener("touchstart", onResizeStart, { passive: false });
        }
        document.addEventListener("touchmove", onResizeMove, { passive: false });
        document.addEventListener("touchend", onResizeEnd);
    }

    function openPanel() {
        // Restore persisted width if any
        if (currentWidth > 0) {
            panel.style.width = currentWidth + "px";
        }
        panel.classList.add("open");
        fab.style.display = "none";

        // Lazy-load iframe on first open
        if (!iframeLoaded && iframe && !iframe.src) {
            iframe.src = gradioUrl;
            iframeLoaded = true;
        }
    }

    function closePanel() {
        panel.classList.remove("open");
        fab.style.display = "flex";
    }

    // ---- Resize Handlers ----

    function onResizeStart(e) {
        if (!panel.classList.contains("open")) return;
        isResizing = true;
        panel.classList.add("resizing");

        // Get the X position (mouse or touch)
        var clientX = e.touches ? e.touches[0].clientX : e.clientX;
        startX = clientX;
        startWidth = panel.getBoundingClientRect().width;

        if (e.touches) e.preventDefault();
    }

    function onResizeMove(e) {
        if (!isResizing) return;

        var clientX = e.touches ? e.touches[0].clientX : e.clientX;
        // Dragging left = expand panel, right = shrink panel
        var deltaX = startX - clientX;
        var newWidth = startWidth + deltaX;

        // Clamp: min 320px, max 800px
        newWidth = Math.max(320, Math.min(800, newWidth));
        currentWidth = newWidth;
        panel.style.width = newWidth + "px";

        if (e.touches) e.preventDefault();
    }

    function onResizeEnd() {
        if (!isResizing) return;
        isResizing = false;
        panel.classList.remove("resizing");
    }

    // Start on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
