# Sim.PesoWeb + MissionCommerce AI. Default image is CPU; on an AMD Instinct box build with a ROCm PyTorch base:
#   docker build --build-arg BASE=rocm/pytorch:latest -t simpeso .
# PesoWeb itself (the system under test) runs separately; point PESOWEB_URL at it.
ARG BASE=python:3.12-slim
FROM ${BASE}
WORKDIR /app
COPY sim/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && (python -c "import torch" 2>/dev/null || pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu)
COPY sim /app/sim
COPY ai /app/ai
COPY ui /app/ui
COPY results /app/results
ENV PYTHONPATH=/app/sim:/app/ai PESOWEB_URL=http://host.docker.internal:5071
WORKDIR /app/sim
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-t", "."]
