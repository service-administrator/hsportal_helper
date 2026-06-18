(() => {
  const MIN_CROP_DISPLAY_SIZE = 36;
  const OUTPUT_TYPE = "image/png";
  const MIN_ZOOM = 1;
  const MAX_ZOOM = 6;
  const ZOOM_STEP = 1.14;

  const modal = document.querySelector("#cropModal");
  const stage = document.querySelector("#cropStage");
  const scroll = document.querySelector("#cropScroll");
  const canvas = document.querySelector("#cropCanvas");
  const image = document.querySelector("#cropImage");
  const selection = document.querySelector("#cropSelection");
  const statusText = document.querySelector("#cropStatus");
  const closeButton = document.querySelector("#closeCropButton");
  const cancelButton = document.querySelector("#cancelCropButton");
  const resetButton = document.querySelector("#resetCropButton");
  const applyButton = document.querySelector("#applyCropButton");
  const useOriginalButton = document.querySelector("#useOriginalButton");

  let activeSession = null;
  let visualBox = { x: 0, y: 0, width: 0, height: 0 };
  let gesture = null;
  let zoom = 1;
  let baseSize = { width: 0, height: 0 };

  window.openImageCropper = function openImageCropper(file) {
    if (!modal || !stage || !scroll || !canvas || !image || !selection) {
      return Promise.resolve({
        file,
        previewUrl: URL.createObjectURL(file),
        crop: null,
      });
    }

    if (activeSession) {
      finishSession(null);
    }

    return new Promise((resolve) => {
      const objectUrl = URL.createObjectURL(file);
      activeSession = {
        file,
        objectUrl,
        resolve,
      };

      modal.hidden = false;
      document.body.classList.add("modal-open");

      image.onload = () => {
        zoom = 1;
        baseSize = getFitSize();
        applyImageZoom({ preserveFocalPoint: false });
        resetCrop("inset");
        setStatus("크롭 박스는 고정됩니다. 휠로 사진만 확대해 세밀하게 맞추세요.", "");
        selection.focus({ preventScroll: true });
      };
      image.src = objectUrl;
    });
  };

  closeButton?.addEventListener("click", () => finishSession(null));
  cancelButton?.addEventListener("click", () => finishSession(null));
  resetButton?.addEventListener("click", () => {
    zoom = 1;
    applyImageZoom({ preserveFocalPoint: false });
    resetCrop("inset");
    setStatus("선택 영역과 확대율을 다시 잡았습니다.", "ok");
  });

  useOriginalButton?.addEventListener("click", () => {
    if (!activeSession) {
      return;
    }

    finishSession({
      file: activeSession.file,
      previewUrl: URL.createObjectURL(activeSession.file),
      crop: null,
    });
  });

  applyButton?.addEventListener("click", async () => {
    if (!activeSession) {
      return;
    }

    applyButton.disabled = true;
    setStatus("선택 영역을 이미지로 만드는 중입니다.", "");

    try {
      const result = await createCroppedFile(activeSession.file);
      finishSession(result);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error), "error");
      applyButton.disabled = false;
    }
  });

  modal?.addEventListener("click", (event) => {
    if (event.target === modal) {
      finishSession(null);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!activeSession || modal.hidden) {
      return;
    }

    if (event.key === "Escape") {
      event.stopImmediatePropagation();
      finishSession(null);
    }
  });

  selection?.addEventListener("keydown", (event) => {
    if (!activeSession) {
      return;
    }

    const step = event.shiftKey ? 12 : 2;

    if (event.key === "ArrowLeft") {
      visualBox.x = clamp(visualBox.x - step, 0, stage.clientWidth - visualBox.width);
    } else if (event.key === "ArrowRight") {
      visualBox.x = clamp(visualBox.x + step, 0, stage.clientWidth - visualBox.width);
    } else if (event.key === "ArrowUp") {
      visualBox.y = clamp(visualBox.y - step, 0, stage.clientHeight - visualBox.height);
    } else if (event.key === "ArrowDown") {
      visualBox.y = clamp(visualBox.y + step, 0, stage.clientHeight - visualBox.height);
    } else {
      return;
    }

    event.preventDefault();
    updateSelection();
  });

  stage?.addEventListener(
    "wheel",
    (event) => {
      if (!activeSession || !image.naturalWidth || !image.naturalHeight) {
        return;
      }

      event.preventDefault();
      const previousZoom = zoom;
      const nextZoom = event.deltaY < 0 ? zoom * ZOOM_STEP : zoom / ZOOM_STEP;
      zoom = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);

      if (zoom === previousZoom) {
        return;
      }

      applyImageZoom({
        preserveFocalPoint: true,
        focalPoint: getSelectionCenter(),
        previousZoom,
      });
      setStatus(`${describeCrop()} · 확대 ${Math.round(zoom * 100)}%`, "");
    },
    { passive: false },
  );

  stage?.addEventListener("pointerdown", (event) => {
    if (!activeSession) {
      return;
    }

    const handle = event.target.dataset?.cropHandle;
    const point = getStagePoint(event);

    if (!point) {
      return;
    }

    event.preventDefault();
    stage.setPointerCapture(event.pointerId);

    if (handle) {
      gesture = {
        mode: "resize",
        handle,
        startPoint: point,
        startBox: { ...visualBox },
      };
      return;
    }

    if (event.target === selection || selection.contains(event.target)) {
      gesture = {
        mode: "move",
        startPoint: point,
        startBox: { ...visualBox },
      };
      return;
    }

    visualBox = {
      x: point.x,
      y: point.y,
      width: MIN_CROP_DISPLAY_SIZE,
      height: MIN_CROP_DISPLAY_SIZE,
    };
    gesture = {
      mode: "draw",
      startPoint: point,
      startBox: { ...visualBox },
    };
    updateSelection();
  });

  stage?.addEventListener("pointermove", (event) => {
    if (!gesture) {
      return;
    }

    const point = getStagePoint(event);
    if (!point) {
      return;
    }

    event.preventDefault();
    const dx = point.x - gesture.startPoint.x;
    const dy = point.y - gesture.startPoint.y;

    if (gesture.mode === "move") {
      visualBox.x = clamp(gesture.startBox.x + dx, 0, stage.clientWidth - gesture.startBox.width);
      visualBox.y = clamp(gesture.startBox.y + dy, 0, stage.clientHeight - gesture.startBox.height);
      visualBox.width = gesture.startBox.width;
      visualBox.height = gesture.startBox.height;
    } else if (gesture.mode === "resize") {
      visualBox = resizeBox(gesture.startBox, dx, dy, gesture.handle);
    } else {
      visualBox = drawBox(gesture.startPoint, point);
    }

    updateSelection();
  });

  stage?.addEventListener("pointerup", (event) => {
    if (!gesture) {
      return;
    }

    stage.releasePointerCapture(event.pointerId);
    gesture = null;
    setStatus(`${describeCrop()} · 확대 ${Math.round(zoom * 100)}%`, "");
  });

  window.addEventListener("resize", () => {
    if (!activeSession || modal.hidden) {
      return;
    }

    const crop = getNaturalCropRect();
    baseSize = getFitSize();
    applyImageZoom({ preserveFocalPoint: false });
    visualBox = naturalRectToVisualBox(crop);
    visualBox = clampVisualBox(visualBox);
    updateSelection();
  });

  function resetCrop(mode) {
    const imageRect = getImageRectInStage();
    const visibleImage = intersectRects(
      imageRect,
      { left: 0, top: 0, right: stage.clientWidth, bottom: stage.clientHeight },
    );
    const insetRatio = mode === "inset" ? 0.06 : 0;
    const insetX = Math.round(visibleImage.width * insetRatio);
    const insetY = Math.round(visibleImage.height * insetRatio);

    visualBox = {
      x: visibleImage.left + insetX,
      y: visibleImage.top + insetY,
      width: Math.max(MIN_CROP_DISPLAY_SIZE, visibleImage.width - insetX * 2),
      height: Math.max(MIN_CROP_DISPLAY_SIZE, visibleImage.height - insetY * 2),
    };
    visualBox = clampVisualBox(visualBox);
    updateSelection();
  }

  function applyImageZoom(options) {
    const focalPoint = options.focalPoint ?? getSelectionCenter();
    const focalNatural = options.preserveFocalPoint
      ? stagePointToNatural(focalPoint)
      : null;
    const width = Math.round(baseSize.width * zoom);
    const height = Math.round(baseSize.height * zoom);

    image.style.width = `${width}px`;
    image.style.height = `${height}px`;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.style.marginLeft = `${Math.max(0, Math.round((scroll.clientWidth - width) / 2))}px`;
    canvas.style.marginTop = `${Math.max(0, Math.round((scroll.clientHeight - height) / 2))}px`;

    if (focalNatural) {
      const marginLeft = parseFloat(canvas.style.marginLeft) || 0;
      const marginTop = parseFloat(canvas.style.marginTop) || 0;
      scroll.scrollLeft = marginLeft + (focalNatural.x / image.naturalWidth) * width - focalPoint.x;
      scroll.scrollTop = marginTop + (focalNatural.y / image.naturalHeight) * height - focalPoint.y;
    } else {
      scroll.scrollLeft = 0;
      scroll.scrollTop = 0;
    }
  }

  function resizeBox(startBox, dx, dy, handle) {
    let next = { ...startBox };

    if (handle.includes("w")) {
      next.x = startBox.x + dx;
      next.width = startBox.width - dx;
    }
    if (handle.includes("e")) {
      next.width = startBox.width + dx;
    }
    if (handle.includes("n")) {
      next.y = startBox.y + dy;
      next.height = startBox.height - dy;
    }
    if (handle.includes("s")) {
      next.height = startBox.height + dy;
    }

    if (next.width < MIN_CROP_DISPLAY_SIZE) {
      if (handle.includes("w")) {
        next.x = startBox.x + startBox.width - MIN_CROP_DISPLAY_SIZE;
      }
      next.width = MIN_CROP_DISPLAY_SIZE;
    }
    if (next.height < MIN_CROP_DISPLAY_SIZE) {
      if (handle.includes("n")) {
        next.y = startBox.y + startBox.height - MIN_CROP_DISPLAY_SIZE;
      }
      next.height = MIN_CROP_DISPLAY_SIZE;
    }

    return clampVisualBox(next);
  }

  function drawBox(startPoint, point) {
    const left = Math.min(startPoint.x, point.x);
    const top = Math.min(startPoint.y, point.y);
    const right = Math.max(startPoint.x, point.x);
    const bottom = Math.max(startPoint.y, point.y);

    return clampVisualBox({
      x: left,
      y: top,
      width: Math.max(MIN_CROP_DISPLAY_SIZE, right - left),
      height: Math.max(MIN_CROP_DISPLAY_SIZE, bottom - top),
    });
  }

  function clampVisualBox(next) {
    const width = Math.min(Math.max(MIN_CROP_DISPLAY_SIZE, next.width), stage.clientWidth);
    const height = Math.min(Math.max(MIN_CROP_DISPLAY_SIZE, next.height), stage.clientHeight);

    return {
      x: clamp(next.x, 0, Math.max(0, stage.clientWidth - width)),
      y: clamp(next.y, 0, Math.max(0, stage.clientHeight - height)),
      width,
      height,
    };
  }

  function updateSelection() {
    selection.style.left = `${visualBox.x}px`;
    selection.style.top = `${visualBox.y}px`;
    selection.style.width = `${visualBox.width}px`;
    selection.style.height = `${visualBox.height}px`;
  }

  function getFitSize() {
    const availableWidth = Math.max(320, scroll.clientWidth);
    const availableHeight = Math.max(280, scroll.clientHeight);
    const imageRatio = image.naturalWidth / image.naturalHeight;
    const stageRatio = availableWidth / availableHeight;

    if (imageRatio > stageRatio) {
      return {
        width: availableWidth,
        height: availableWidth / imageRatio,
      };
    }

    return {
      width: availableHeight * imageRatio,
      height: availableHeight,
    };
  }

  function getStagePoint(event) {
    const stageRect = stage.getBoundingClientRect();

    return {
      x: clamp(event.clientX - stageRect.left, 0, stage.clientWidth),
      y: clamp(event.clientY - stageRect.top, 0, stage.clientHeight),
    };
  }

  function getSelectionCenter() {
    return {
      x: visualBox.x + visualBox.width / 2,
      y: visualBox.y + visualBox.height / 2,
    };
  }

  function getImageRectInStage() {
    const stageRect = stage.getBoundingClientRect();
    const imageRect = image.getBoundingClientRect();

    return {
      left: imageRect.left - stageRect.left,
      top: imageRect.top - stageRect.top,
      right: imageRect.right - stageRect.left,
      bottom: imageRect.bottom - stageRect.top,
      width: imageRect.width,
      height: imageRect.height,
    };
  }

  function stagePointToNatural(point) {
    const imageRect = getImageRectInStage();

    return {
      x: clamp(((point.x - imageRect.left) / imageRect.width) * image.naturalWidth, 0, image.naturalWidth),
      y: clamp(((point.y - imageRect.top) / imageRect.height) * image.naturalHeight, 0, image.naturalHeight),
    };
  }

  function getNaturalCropRect() {
    const topLeft = stagePointToNatural({ x: visualBox.x, y: visualBox.y });
    const bottomRight = stagePointToNatural({
      x: visualBox.x + visualBox.width,
      y: visualBox.y + visualBox.height,
    });
    const x = Math.round(Math.min(topLeft.x, bottomRight.x));
    const y = Math.round(Math.min(topLeft.y, bottomRight.y));
    const width = Math.round(Math.abs(bottomRight.x - topLeft.x));
    const height = Math.round(Math.abs(bottomRight.y - topLeft.y));

    return {
      x,
      y,
      width: Math.max(1, width),
      height: Math.max(1, height),
    };
  }

  function naturalRectToVisualBox(rect) {
    const imageRect = getImageRectInStage();
    const scaleX = imageRect.width / image.naturalWidth;
    const scaleY = imageRect.height / image.naturalHeight;

    return {
      x: imageRect.left + rect.x * scaleX,
      y: imageRect.top + rect.y * scaleY,
      width: rect.width * scaleX,
      height: rect.height * scaleY,
    };
  }

  async function createCroppedFile(originalFile) {
    if (!image.naturalWidth || !image.naturalHeight) {
      throw new Error("이미지를 아직 불러오지 못했습니다.");
    }

    const crop = getNaturalCropRect();
    const canvasElement = document.createElement("canvas");
    canvasElement.width = crop.width;
    canvasElement.height = crop.height;

    const context = canvasElement.getContext("2d");
    context.drawImage(
      image,
      crop.x,
      crop.y,
      crop.width,
      crop.height,
      0,
      0,
      canvasElement.width,
      canvasElement.height,
    );

    const blob = await new Promise((resolve, reject) => {
      canvasElement.toBlob((value) => {
        if (value) {
          resolve(value);
        } else {
          reject(new Error("크롭 이미지를 만들지 못했습니다."));
        }
      }, OUTPUT_TYPE);
    });

    const file = new File([blob], buildCroppedName(originalFile.name), {
      type: OUTPUT_TYPE,
      lastModified: Date.now(),
    });

    return {
      file,
      previewUrl: URL.createObjectURL(file),
      crop: {
        ...crop,
        originalWidth: image.naturalWidth,
        originalHeight: image.naturalHeight,
      },
    };
  }

  function intersectRects(first, second) {
    const left = Math.max(first.left, second.left);
    const top = Math.max(first.top, second.top);
    const right = Math.min(first.right, second.right);
    const bottom = Math.min(first.bottom, second.bottom);

    return {
      left,
      top,
      right,
      bottom,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top),
    };
  }

  function buildCroppedName(name) {
    const baseName = name.replace(/\.[^.]+$/, "");
    return `${baseName || "timetable"}-cropped.png`;
  }

  function describeCrop() {
    const crop = getNaturalCropRect();
    const widthRatio = Math.round((crop.width / image.naturalWidth) * 100);
    const heightRatio = Math.round((crop.height / image.naturalHeight) * 100);
    return `선택 영역: 가로 ${widthRatio}%, 세로 ${heightRatio}%`;
  }

  function finishSession(result) {
    if (!activeSession) {
      return;
    }

    const session = activeSession;
    activeSession = null;
    gesture = null;
    zoom = 1;
    baseSize = { width: 0, height: 0 };
    image.onload = null;
    image.removeAttribute("src");
    image.removeAttribute("style");
    canvas.removeAttribute("style");
    scroll.scrollLeft = 0;
    scroll.scrollTop = 0;
    URL.revokeObjectURL(session.objectUrl);
    applyButton.disabled = false;
    modal.hidden = true;
    syncModalOpenState();
    session.resolve(result);
  }

  function syncModalOpenState() {
    const hasOpenModal = document.querySelector(".modal-backdrop:not([hidden]), .dialog-backdrop:not([hidden])");
    document.body.classList.toggle("modal-open", Boolean(hasOpenModal));
  }

  function setStatus(message, type) {
    statusText.textContent = message;
    statusText.className = type ? `status-text ${type}` : "status-text";
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }
})();
