# DA3408 A4 — Application Monitoring and Observability

A CPU-based AI image-captioning application instrumented with Prometheus and monitored using Grafana and Node Exporter.

## 1. Project Overview

This project implements an image-captioning application and an end-to-end monitoring pipeline. It demonstrates how application performance, system resource utilization, and errors can be monitored in a single dashboard.

The application uses the pretrained `nlpconnect/vit-gpt2-image-captioning` model and runs inference on the CPU.

### Objectives

- Build a Streamlit application for image captioning.
- Support single-image uploads and bulk image processing through ZIP files.
- Instrument the application using the Prometheus Python client.
- Collect application and system-level metrics using Prometheus and Node Exporter.
- Visualize metrics through a Grafana dashboard.
- Configure and test an alert for caption-generation errors.

## 2. Architecture

The monitoring pipeline consists of four main components:

1. **Streamlit application (`app.py`):** Generates captions and exposes custom application metrics.
2. **Node Exporter:** Exposes system-level metrics such as CPU utilization, memory usage, and disk utilization.
3. **Prometheus:** Scrapes and stores application and system metrics.
4. **Grafana:** Visualizes metrics through a dashboard and evaluates alert rules.

### Data flow

- The Streamlit application runs on port `8501`.
- Application metrics are exposed on port `8000`.
- Node Exporter exposes system metrics on port `9100`.
- Prometheus collects metrics from both sources.
- Grafana queries Prometheus to visualize the data and evaluate alerts.

## 3. Features

### Image Captioning

**Single-image mode**
- Upload a JPG, JPEG, or PNG image.
- Generate a caption using the pretrained model.
- Display the generated caption and inference duration.

**Bulk mode**
- Upload a ZIP file containing images.
- Process supported images and display the results.
- View processing status and inference duration for individual images.
- Download the results as a CSV file.

The application limits bulk processing to the first 50 supported images.

### Application Instrumentation

The application uses the `prometheus_client` Python library to expose metrics on port `8000`.

| Metric type | Metric | Purpose |
|---|---|---|
| Counter | `caption_requests_total` | Tracks caption-generation requests by mode. |
| Counter | `caption_images_processed_total` | Counts successfully captioned images by mode. |
| Counter | `caption_errors_total` | Tracks failed caption-generation attempts by mode. |
| Counter | `caption_client_requests_total` | Categorizes requests by mode and client type. |
| Gauge | `caption_active_requests` | Tracks the number of active requests. |
| Histogram | `caption_inference_seconds` | Records inference durations. |
| Histogram | `caption_model_load_seconds` | Records model-loading durations. |
| Summary | `caption_inference_duration_seconds` | Records inference-duration observations, including their sum and count. |

Labels such as `mode="single"`, `mode="bulk"` and `client_type="streamlit_ui"` help categorize the collected metrics.

### Infrastructure Monitoring

Node Exporter exposes machine-level metrics, including:

- CPU utilization
- Memory utilization
- Disk utilization

Prometheus scrapes the Node Exporter endpoint alongside the application's custom metrics. This allows application behavior and system resource utilization to be examined together.

### Grafana Dashboard

The dashboard contains nine panels:

1. Total Caption Requests
2. Successful Images
3. Inference Time
4. Caption Errors
5. Memory Usage
6. CPU Usage
7. Application Health
8. Request Throughput
9. Disk Usage

The dashboard uses a five-second refresh interval and includes descriptive titles, labels, units, legends, and metric descriptions.

### Alerting

A Grafana alert rule named **Caption Generation Errors** monitors increases in the error counter over a five-minute window.

The rule was tested by submitting an invalid image and observing the resulting error metric and alert-state transition.

## 4. Repository Structure

```text
AiOps-Assignment-4/
├── Images/
│   ├── Bulk-mode-output.png
│   ├── Caption_active_requests_query_execution.png
│   ├── Caption_alerts_firing_sign.png
│   ├── Caption_alerts_pending_sign.png
│   ├── Caption_generation_success_bulk.png
│   ├── Caption_generation_success_single.png
│   ├── Caption_inference_seconds_sum_graph.png
│   ├── Caption_model_load_seconds_count_graph.png
│   ├── Error_image.png
│   ├── prometheus_proof_correct_scraping_from_both_sources.png
│   ├── prometheus_query_execution-1.png
│   └── prometheus_query_execution-2.png
├── app.py
├── docker-compose.yml
├── grafana-dashboard.json
├── prometheus.yml
├── README.md
└── AI_DISCLOSURE.md
```

`Images/` contains screenshots documenting application functionality, Prometheus queries, metric collection, and alerting. `AIAppendix` will contain the separate AI-use documentation.

## 5. Prerequisites

Ensure the following are installed:

- Python 3.10 or later, with a version compatible with the installed PyTorch and Transformers dependencies
- pip
- Docker
- Docker Compose v2
- A web browser

The application downloads the pretrained model and its associated processor/tokenizer files from Hugging Face when they are first loaded. An internet connection and sufficient disk space are required for the initial download.

## 6. Setup and Installation

### Step 1: Clone the repository

```bash
git clone https://github.com/keerthi-2007/AiOps-Assignment-4.git
cd AiOps-Assignment-4
```

Replace the placeholder with the URL of this GitHub repository.

### Step 2: Create a virtual environment

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install streamlit torch transformers pillow prometheus-client
```

If PyTorch installation fails because of platform or Python-version compatibility, install a supported Python/PyTorch combination for your system.

## 7. Running the Project

Start the application and monitoring stack in separate terminals.

### Terminal 1: Start the Streamlit application

From the repository root, activate the virtual environment and run:

```bash
source .venv/bin/activate
streamlit run app.py
```

Open the application at:

**http://localhost:8501**

Upload an image in single mode or a ZIP file in bulk mode to generate captions.

The application exposes its metrics separately at:

**http://localhost:8000/metrics**

This endpoint displays the raw Prometheus metrics exported by `app.py`.

### Terminal 2: Start the monitoring stack

From the repository root, run:

```bash
docker compose up -d
```

This starts the services defined in `docker-compose.yml`, including the monitoring components configured for this project.

Check the container status:

```bash
docker compose ps
```

View service logs if necessary:

```bash
docker compose logs
```

To inspect a particular service, use its service name from `docker-compose.yml`:

```bash
docker compose logs <service_name>
```

### Access the monitoring interfaces

| Component | URL | Purpose |
|---|---|---|
| Streamlit | http://localhost:8501 | Image-captioning application |
| Application metrics | http://localhost:8000/metrics | Raw custom application metrics |
| Prometheus | http://localhost:9090 | Metric queries and target health |
| Node Exporter | http://localhost:9100/metrics | Raw system-level metrics |
| Grafana | http://localhost:3000 | Dashboard and alerting |

If an endpoint is unavailable, verify that its corresponding process or container is running and that the configured port is accessible.

## 8. Verifying Prometheus and Node Exporter

Open:

http://localhost:9090/targets

Verify that both scrape targets are marked **UP**:

- Application metrics endpoint
- Node Exporter endpoint

The target addresses depend on the configuration in `prometheus.yml` and `docker-compose.yml`. In this project, the application target is configured to be reachable from the Prometheus container through `host.docker.internal:8000`, while Node Exporter is reached through its Docker service endpoint.

### Example PromQL queries

**Application health**

```promql
up{instance="host.docker.internal:8000"}
```

A value of `1` indicates that Prometheus successfully scraped the application target.

**CPU utilization**

```promql
100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))
```

This estimates overall CPU utilization as a percentage, averaged across CPUs over the previous five minutes.

**Total images processed**

```promql
sum(caption_images_processed_total)
```

This sums the successfully processed-image counters across the available modes.

**Average inference duration**

```promql
rate(caption_inference_seconds_sum[5m])
/
rate(caption_inference_seconds_count[5m])
```

This calculates the average observed inference duration over the previous five minutes, provided there are observations in the window.

## 9. Using the Grafana Dashboard

1. Open http://localhost:3000.
2. Sign in using the credentials configured for your Grafana instance.
3. Open the imported dashboard.
4. Set the time range to a recent period, such as the last 15 minutes.
5. Set the refresh interval to five seconds.
6. Generate captions using single mode and bulk mode.
7. Observe changes in request counts, processed images, inference latency, errors, and system resource utilization.

The dashboard combines application metrics with system-level metrics so that workload and resource trends can be compared.

## 10. Testing the Alert

1. Open the Streamlit application.
2. Upload an invalid image that the application cannot process.
3. Verify that the error counter increases.
4. Open Grafana and navigate to **Alerting**.
5. Locate the `Caption Generation Errors` alert rule.
6. Observe the alert transition through its configured states.

The rule evaluates the following PromQL expression:

```promql
sum(increase(caption_errors_total[5m]))
```

The expression calculates the increase in the error counter over a five-minute window and sums the result across label combinations.

The alert's state depends on its evaluation interval and pending period. An alert can move from Pending to Firing when the condition remains true for the configured duration.

## 11. Stopping the Services

To stop the Docker monitoring stack:

```bash
docker compose down
```

To stop the Streamlit application, press `Ctrl+C` in the terminal where it is running.

To deactivate the Python virtual environment:

```bash
deactivate
```

The `docker compose down` command stops and removes the containers created by the Compose configuration. It does not remove the project source files.

## 12. Screenshots and Evidence

The `Images/` directory contains supporting screenshots of:

- Successful single-image caption generation
- Bulk ZIP image processing
- Prometheus metric queries
- Application and Node Exporter scrape status
- Inference and active-request metrics
- Grafana alert states, including Pending and Firing
- Error handling for an invalid image

These screenshots provide evidence of the implemented application and monitoring workflow.

## 13. Technologies Used

- **Python** — application implementation
- **Streamlit** — web interface
- **PyTorch** — CPU-based model inference
- **Hugging Face Transformers** — pretrained image-captioning model
- **Prometheus Python Client** — application instrumentation
- **Prometheus** — metrics collection and storage
- **Node Exporter** — system-level metrics
- **Grafana** — dashboards and alerting
- **Docker Compose** — monitoring-stack deployment

