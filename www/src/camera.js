(function () {
  "use strict";

  const CAMERA_COUNT = 4;               // cameras 0..3
  const HLS_JS_URL = "https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.5.13/hls.min.js";
  const RETRY_DELAY_MS = 3000;          // wait before retrying a stream after a fatal error

  function loadHlsJs() {
    return new Promise((resolve, reject) => {
      if (window.Hls) return resolve();
      const script = document.createElement("script");
      script.src = HLS_JS_URL;
      script.onload = resolve;
      script.onerror = () => reject(new Error("Failed to load hls.js"));
      document.head.appendChild(script);
    });
  }

  function createCameraElement(index) {
    const wrap = document.createElement("div");
    wrap.className = "cam";

    const label = document.createElement("div");
    label.className = "cam-label";
    label.textContent = `Camera ${index + 1}`;

    const video = document.createElement("video");
    video.id = `video${index}`;
    video.controls = true;
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;

    wrap.appendChild(label);
    wrap.appendChild(video);
    return { wrap, video };
  }

  function attachStream(video, index) {
    const src = `/hls/${index}.m3u8`;

    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls({ liveSyncDurationCount: 3 });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        console.warn(`Camera ${index}: fatal HLS error (${data.type}), retrying in ${RETRY_DELAY_MS}ms`);
        hls.destroy();
        setTimeout(() => attachStream(video, index), RETRY_DELAY_MS);
      });

      hls.loadSource(src);
      hls.attachMedia(video);
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src; // Safari plays HLS natively, no hls.js needed
    } else {
      console.error(`Camera ${index}: no HLS playback support in this browser`);
    }
  }

  function init() {
    const grid = document.getElementById("grid");
    if (!grid) {
      console.error('No element with id="grid" found to hold the camera feeds.');
      return;
    }

    for (let index = 0; index < CAMERA_COUNT; index++) {
      const { wrap, video } = createCameraElement(index);
      grid.appendChild(wrap);
      attachStream(video, index);
    }
  }

  loadHlsJs()
    .then(init)
    .catch((err) => console.error(err));
})();