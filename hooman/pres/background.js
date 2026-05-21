(function () {
    "use strict";

    function initBackground() {
        const canvas = document.getElementById("neural-bg");
        const ctx = canvas.getContext("2d");
        let width = 0;
        let height = 0;
        let points = [];

        function resize() {
            width = canvas.width = window.innerWidth * window.devicePixelRatio;
            height = canvas.height = window.innerHeight * window.devicePixelRatio;
            canvas.style.width = `${window.innerWidth}px`;
            canvas.style.height = `${window.innerHeight}px`;
            const count = Math.min(82, Math.max(38, Math.floor(window.innerWidth / 21)));
            points = Array.from({ length: count }, () => ({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.14 * window.devicePixelRatio,
                vy: (Math.random() - 0.5) * 0.14 * window.devicePixelRatio,
            }));
        }

        function tick() {
            ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = "rgba(103, 232, 249, 0.42)";
            ctx.strokeStyle = "rgba(103, 232, 249, 0.1)";
            for (const point of points) {
                point.x += point.vx;
                point.y += point.vy;
                if (point.x < 0 || point.x > width) point.vx *= -1;
                if (point.y < 0 || point.y > height) point.vy *= -1;
                ctx.beginPath();
                ctx.arc(point.x, point.y, 1.15 * window.devicePixelRatio, 0, Math.PI * 2);
                ctx.fill();
            }
            for (let i = 0; i < points.length; i += 1) {
                for (let j = i + 1; j < points.length; j += 1) {
                    const a = points[i];
                    const b = points[j];
                    const dx = a.x - b.x;
                    const dy = a.y - b.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    if (distance < 150 * window.devicePixelRatio) {
                        ctx.globalAlpha = 1 - distance / (150 * window.devicePixelRatio);
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.stroke();
                    }
                }
            }
            ctx.globalAlpha = 1;
            window.requestAnimationFrame(tick);
        }

        resize();
        tick();
        window.addEventListener("resize", resize);
    }

    window.PresBackground = { initBackground };
}());
