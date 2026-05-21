(function () {
    "use strict";

    const { chapters, slides } = window.PresData;
    const state = {
        index: 0,
        executionStep: 0,
        executionTimer: null,
        memoryTimer: null,
    };

    const stage = document.getElementById("stage");
    const counter = document.getElementById("slide-counter");
    const progressBar = document.getElementById("progress-bar");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const chapterNav = document.getElementById("chapter-nav");

    function renderChapters() {
        chapterNav.innerHTML = chapters.map((chapter, index) => `
            <button class="chapter-pill" data-jump="${chapter.firstSlide}" data-chapter="${chapter.id}">
                <span>${String(index).padStart(2, "0")}</span>
                ${chapter.label}
            </button>
        `).join("");
        chapterNav.querySelectorAll("[data-jump]").forEach((button) => {
            button.addEventListener("click", () => goTo(Number(button.dataset.jump)));
        });
    }

    function clearTimers() {
        window.clearInterval(state.executionTimer);
        window.clearInterval(state.memoryTimer);
        state.executionTimer = null;
        state.memoryTimer = null;
    }

    function runSlideHook(hookName) {
        if (!hookName) return;
        if (hookName === "bindExecution") {
            window.PresInteractions.bindExecution(state);
            return;
        }
        if (hookName === "bindMemoryFlow") {
            window.PresInteractions.bindMemoryFlow(state);
            return;
        }
        const hook = window.PresInteractions[hookName];
        if (typeof hook === "function") {
            hook();
        }
    }

    function render() {
        clearTimers();
        const slide = slides[state.index];
        stage.innerHTML = slide.render();
        counter.textContent = `${String(state.index + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;
        progressBar.style.width = `${((state.index + 1) / slides.length) * 100}%`;

        stage.querySelectorAll("[data-jump]").forEach((button) => {
            button.addEventListener("click", () => goTo(Number(button.dataset.jump)));
        });

        document.querySelectorAll(".chapter-pill").forEach((pill) => {
            const active = pill.dataset.chapter === slide.chapter;
            pill.classList.toggle("active", active);
            pill.setAttribute("aria-current", active ? "step" : "false");
        });

        prevBtn.disabled = state.index === 0;
        nextBtn.disabled = state.index === slides.length - 1;
        runSlideHook(slide.afterRender);

        const hashIndex = Number(window.location.hash.replace("#/", ""));
        if (hashIndex !== state.index) {
            window.history.replaceState(null, "", `#/${state.index}`);
        }
    }

    function goTo(index) {
        state.index = Math.max(0, Math.min(slides.length - 1, index));
        render();
    }

    function next() {
        goTo(state.index + 1);
    }

    function prev() {
        goTo(state.index - 1);
    }

    prevBtn.addEventListener("click", prev);
    nextBtn.addEventListener("click", next);
    window.addEventListener("keydown", (event) => {
        if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
        if (event.key === "ArrowRight" || event.key === " ") {
            event.preventDefault();
            next();
        }
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            prev();
        }
        if (event.key === "Home") {
            event.preventDefault();
            goTo(0);
        }
        if (event.key === "End") {
            event.preventDefault();
            goTo(slides.length - 1);
        }
    });
    window.addEventListener("hashchange", () => {
        const hashIndex = Number(window.location.hash.replace("#/", ""));
        if (Number.isFinite(hashIndex) && hashIndex !== state.index) {
            goTo(hashIndex);
        }
    });

    renderChapters();
    const initialIndex = Number(window.location.hash.replace("#/", ""));
    if (Number.isFinite(initialIndex)) {
        state.index = Math.max(0, Math.min(slides.length - 1, initialIndex));
    }
    render();
    window.PresBackground.initBackground();
}());
