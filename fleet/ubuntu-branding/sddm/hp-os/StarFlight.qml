import QtQuick

// Deterministic perspective flight. One small software canvas, no shaders/video.
Canvas {
    id: stars
    property real phase: 0
    property real warp: 0.12
    renderTarget: Canvas.Image
    onPhaseChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        ctx.clearRect(0, 0, width, height);
        var cx = width * 0.5, cy = height * 0.42;
        var span = Math.max(width, height);
        for (var i = 0; i < 100; i++) {
            var angle = i * 2.399963;
            var radius = 0.08 + ((i * 37) % 100) / 100;
            var z = 0.12 + (((i * 0.618034 - phase * 0.16) % 1 + 1) % 1) * 1.8;
            var x = cx + Math.cos(angle) * radius * span * 0.18 / z;
            var y = cy + Math.sin(angle) * radius * span * 0.18 / z;
            var tail = 0.012 + warp * 0.09;
            ctx.beginPath();
            ctx.strokeStyle = "rgba(160,218,255," + Math.min(0.85, 0.35 / z) + ")";
            ctx.lineWidth = Math.max(0.6, 1.3 / z);
            ctx.moveTo(x, y);
            ctx.lineTo(cx + (x-cx) * (1+tail), cy + (y-cy) * (1+tail));
            ctx.stroke();
        }
    }
}
