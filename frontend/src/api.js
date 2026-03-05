export async function uploadImages({ firstImage, secondImage, intermediateCount, fps, apiBase }) {
  const form = new FormData();
  form.append("first_image", firstImage);
  form.append("second_image", secondImage);
  form.append("intermediate_count", String(intermediateCount));
  form.append("fps", String(fps));

  const res = await fetch(`${apiBase}/api/interpolate/images`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Image interpolation failed");
  }

  return res.json();
}

export async function uploadVideo({ videoFile, intermediateCount, apiBase }) {
  const form = new FormData();
  form.append("video_file", videoFile);
  form.append("intermediate_count", String(intermediateCount));

  const res = await fetch(`${apiBase}/api/interpolate/video`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Video interpolation failed");
  }

  return res.json();
}
