import streamlit as st
import zipfile
import time
import csv
from io import BytesIO, StringIO

import torch
from PIL import Image, UnidentifiedImageError
from transformers import (
    VisionEncoderDecoderModel,
    ViTImageProcessor,
    AutoTokenizer,
)
from prometheus_client import (
    start_http_server,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary
)
st.set_page_config(
    page_title="AI Image Captioning",
    page_icon="🖼️",
    layout="wide",
)

st.title("🖼️ AI Image Captioning")
st.write("Generate captions for a single image or a batch of images.")

MODEL_NAME = "nlpconnect/vit-gpt2-image-captioning"
MAX_IMAGES = 50
@st.cache_resource
def setup_metrics():
    registry = CollectorRegistry()

    requests = Counter(
        "caption_requests_total",
        "Total caption-generation attempts",
        ["mode"],
        registry=registry,
    )

    errors = Counter(
        "caption_errors_total",
        "Total failed caption attempts",
        ["mode"],
        registry=registry,
    )
    errors.labels(mode="single").inc(0)
    errors.labels(mode="bulk").inc(0)

    images_processed = Counter(
        "caption_images_processed_total",
        "Images successfully captioned",
        ["mode"],
        registry=registry,
    )

    inference_time = Histogram(
        "caption_inference_seconds",
        "Caption-generation duration in seconds",
        ["mode"],
        registry=registry,
    )

    model_load_time = Histogram(
        "caption_model_load_seconds",
        "Model-loading duration in seconds",
        registry=registry,
    )
    active_requests = Gauge(
        "caption_active_requests",
        "Number of caption requests currently being processed",
        ["mode"],
        registry=registry,
    )

    inference_summary = Summary(
        "caption_inference_duration_seconds",
        "Summary of per-image caption inference duration",
        ["mode"],
        registry=registry,
    )

    client_requests = Counter(
        "caption_client_requests_total",
        "Caption requests categorized by client type and mode",
        ["mode", "client_type"],
        registry=registry,
    )

    # Prometheus scrapes this endpoint on port 8000.
    start_http_server(
        8000,
        addr="0.0.0.0",
        registry=registry,
    )

    return {
        "requests": requests,
        "errors": errors,
        "images_processed": images_processed,
        "inference_time": inference_time,
        "model_load_time": model_load_time,
        "active_requests": active_requests,
        "inference_summary": inference_summary,
        "client_requests": client_requests,
    }

metrics = setup_metrics()


@st.cache_resource
def load_model():
    image_processor = ViTImageProcessor.from_pretrained(MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
    model.eval()
    return model, image_processor, tokenizer
    
def generate_caption(image, model, image_processor, tokenizer):
    inputs = image_processor(
        images=image,
        return_tensors="pt",
    )

    # CPU inference; inference_mode avoids gradient tracking.
    with torch.inference_mode():
        output_ids = model.generate(
            pixel_values=inputs["pixel_values"],
            max_length=16,
            num_beams=4,
        )

    caption = tokenizer.decode(
        output_ids[0],
        skip_special_tokens=True,
    )
    return caption.strip()


mode = st.radio(
    "Choose processing mode",
    ["Single Image", "Bulk ZIP Upload"],
    horizontal=True,
)

if mode == "Single Image":
    image_file = st.file_uploader(
        "Upload an image",
        type=["jpg", "jpeg", "png"],
        key="single_image",
    )

    if image_file is not None:
        try:
            image = Image.open(image_file).convert("RGB")

            st.image(
                image,
                caption="Uploaded Image",
                use_container_width=True,
            )

            if st.button("Generate Caption"):
                mode_name = "single"
                metrics["requests"].labels(mode=mode_name).inc()
                metrics["client_requests"].labels(mode=mode_name, client_type="streamlit_ui").inc()
                metrics["active_requests"].labels(mode=mode_name).inc()
                inference_start = None
                elapsed = None

                try:
                    with st.spinner("Loading model and generating caption..."):
                        load_start = time.perf_counter()
                        model, image_processor, tokenizer = load_model()
                        metrics["model_load_time"].observe(
                            time.perf_counter() - load_start
                        )

                        inference_start = time.perf_counter()
                        caption = generate_caption(
                            image,
                            model,
                            image_processor,
                            tokenizer,
                        )
                        elapsed = time.perf_counter() - inference_start

                        metrics["images_processed"].labels(
                            mode=mode_name
                        ).inc()

                    st.success("Caption generated!")
                    st.subheader("Generated Caption")
                    st.write(caption)
                    st.caption(f"Inference time: {elapsed:.2f} seconds")

                except Exception as error:
                    metrics["errors"].labels(mode=mode_name).inc()
                    st.error(
                        f"Caption generation failed: "
                        f"{type(error).__name__}: {error}"
                    )
                finally:
                    if inference_start is not None:
                        if elapsed is None:
                            elapsed = time.perf_counter() - inference_start

                        metrics["inference_time"].labels(
                            mode=mode_name
                        ).observe(elapsed)

                        metrics["inference_summary"].labels(
                            mode=mode_name
                        ).observe(elapsed)

                    metrics["active_requests"].labels(
                        mode=mode_name
                    ).dec()

        #except (UnidentifiedImageError, OSError) as error:
            #st.error(f"Could not open this image: {error}")
        except (UnidentifiedImageError, OSError) as error:
            metrics["errors"].labels(mode="single").inc()
            st.error(f"Could not open this image: {error}")
else:
    zip_file = st.file_uploader(
        "Upload a ZIP containing images",
        type=["zip"],
        key="bulk_zip",
    )

    if zip_file is not None:
        st.write(f"Uploaded: {zip_file.name}")
        if st.button("Process Images"):
            try:
                with zipfile.ZipFile(zip_file) as archive:
                    image_names = [
                        name
                        for name in archive.namelist()
                        if not name.endswith("/")
                        and name.lower().endswith((".jpg", ".jpeg", ".png"))
                    ]

                    total_found = len(image_names)
                    image_names = image_names[:MAX_IMAGES]

                    if not image_names:
                        st.warning(
                            "No supported JPG or PNG images were found "
                            "in the ZIP file."
                        )
                    else:
                        with st.spinner("Loading pretrained model..."):
                            load_start = time.perf_counter()
                            model, image_processor, tokenizer = load_model()
                            metrics["model_load_time"].observe(
                                time.perf_counter() - load_start
                            )
                        results = []
                        progress = st.progress(0)
                        status = st.empty()
                        for index, name in enumerate(image_names):
                            mode_name = "bulk"
                            metrics["requests"].labels(mode=mode_name).inc()
                            metrics["client_requests"].labels(
                                    mode=mode_name,
                                    client_type="streamlit_ui"
                                ).inc()
                            metrics["active_requests"].labels(
                                    mode=mode_name
                                ).inc()

                            start = time.perf_counter()
                            elapsed = None
                            try:
                                image_bytes = archive.read(name)
                                image = Image.open(
                                    BytesIO(image_bytes)
                                ).convert("RGB")

                                caption = generate_caption(
                                    image,
                                    model,
                                    image_processor,
                                    tokenizer,
                                )
                                elapsed = time.perf_counter() - start
                                metrics["images_processed"].labels(
                                    mode=mode_name
                                ).inc()
                                results.append({
                                    "Filename": name,
                                    "Caption": caption,
                                    "Inference time (s)": round(elapsed, 2),
                                    "Status": "Success",
                                })
                            except Exception as error:
                                elapsed = time.perf_counter() - start
                                metrics["errors"].labels(
                                    mode=mode_name
                                ).inc()

                                results.append({
                                    "Filename": name,
                                    "Caption": (
                                        f"{type(error).__name__}: {error}"
                                    )[:200],
                                    "Inference time (s)": round(elapsed, 2),
                                    "Status": "Failed",
                                })
                            finally:
                                if elapsed is None:
                                    elapsed = time.perf_counter() - start

                                metrics["inference_time"].labels(
                                    mode=mode_name
                                ).observe(elapsed)

                                metrics["inference_summary"].labels(
                                    mode=mode_name
                                ).observe(elapsed)

                                metrics["active_requests"].labels(
                                    mode=mode_name
                                ).dec()
                            progress.progress((index + 1) / len(image_names))
                            status.write(
                                f"Processed {index + 1} of "
                                f"{len(image_names)} images"
                            )
                        st.subheader("Caption Results")
                        st.dataframe(
                            results,
                            use_container_width=True,
                        )
                        csv_buffer = StringIO()
                        writer = csv.DictWriter(
                            csv_buffer,
                            fieldnames=[
                                "Filename",
                                "Caption",
                                "Inference time (s)",
                                "Status",
                            ],
                        )
                        writer.writeheader()
                        writer.writerows(results)
                        st.download_button(
                            "Download Results as CSV",
                            data=csv_buffer.getvalue(),
                            file_name="image_captions.csv",
                            mime="text/csv",
                        )
                        successful = sum(
                            row["Status"] == "Success"
                            for row in results
                        )
                        failed = len(results) - successful

                        st.info(
                            f"Completed: {successful} successful, "
                            f"{failed} failed."
                        )

                        if total_found > MAX_IMAGES:
                            st.warning(
                                f"The ZIP contains {total_found} images. "
                                f"This demo processed only the first "
                                f"{MAX_IMAGES}."
                            )





            except zipfile.BadZipFile:
                st.error("Invalid ZIP file. Please upload a valid archive.")

            except Exception as error:
                st.error(
                    f"Bulk processing failed: "
                    f"{type(error).__name__}: {error}"
                )

st.divider()
st.caption("DA3408 A4 | Application Monitoring")


