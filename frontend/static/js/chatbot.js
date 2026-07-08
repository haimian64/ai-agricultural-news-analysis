/**
 * Floating AI Chatbot Widget — toggle FAB / panel interactions
 * Follows the same IIFE pattern as dashboard.js
 */
(function () {
    "use strict";

    var fab, panel, closeBtn, iframe;
    var iframeLoaded = false;
    var gradioUrl = "http://localhost:7860";

    function init() {
        fab = document.getElementById("chatbotFAB");
        panel = document.getElementById("chatbotPanel");
        closeBtn = document.getElementById("chatbotClose");
        iframe = document.getElementById("chatbotIframe");

        if (!fab || !panel) return;

        // Read Gradio URL from data attribute (set in HTML)
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
    }

    function openPanel() {
        panel.classList.add("open");
        fab.style.display = "none";

        // Lazy-load iframe on first open (direct to Gradio, not proxy)
        if (!iframeLoaded && iframe && !iframe.src) {
            iframe.src = gradioUrl;
            iframeLoaded = true;
        }
    }

    function closePanel() {
        panel.classList.remove("open");
        fab.style.display = "flex";
    }

    // Start on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
