# CSIS Backend — Dockerfile
# Python 3.12 (required by QGIS conda-forge; natcap.invest 3.14.3 compatible)
FROM condaforge/miniforge3:latest

WORKDIR /app

# --- Step 1: conda packages ---
# Python 3.12 chosen for QGIS conda-forge compatibility
# Version pins relaxed on geo libs — let conda solve with QGIS constraints
RUN mamba create -n TeleCouplingAI python=3.12 -y && \
    mamba install -n TeleCouplingAI -c conda-forge -y \
        gdal geos proj \
        geopandas rasterio shapely \
        numpy pandas scikit-learn \
        matplotlib rtree networkx \
        taskgraph \
        fastapi=0.128.0 uvicorn=0.40.0 \
        pydantic=2.10.6 requests python-dotenv \
        pillow pyyaml \
        qgis \
        r-base r-igraph r-factominer r-dplyr r-jsonlite r-sf r-rcolorbrewer \
        gxx_linux-64 gcc_linux-64 && \
    mamba clean -afy

# --- Step 2: activate env by PATH ---
ENV CONDA_DEFAULT_ENV=TeleCouplingAI
ENV PATH=/opt/conda/envs/TeleCouplingAI/bin:$PATH

# Compiler symlinks (needed by pygeoprocessing/natcap.invest build)
RUN ln -sf /opt/conda/envs/TeleCouplingAI/bin/x86_64-conda-linux-gnu-g++ \
           /opt/conda/envs/TeleCouplingAI/bin/g++ && \
    ln -sf /opt/conda/envs/TeleCouplingAI/bin/x86_64-conda-linux-gnu-gcc \
           /opt/conda/envs/TeleCouplingAI/bin/gcc

# --- Step 3: pip packages ---
RUN pip install --no-cache-dir \
        "natcap.invest==3.14.3" \
        "pygeoprocessing==2.4.10" \
        "google-genai>=0.8.0" \
        "python-multipart==0.0.21" \
        "aiofiles>=23.0.0" \
        "pydantic-settings>=2.0.0" \
        "celery[redis]>=5.3.0" \
        "redis>=5.0.0" \
        "aiohttp[speedups]>=3.9.0" \
        "loguru>=0.7.0" \
        "beautifulsoup4>=4.12.0"

# --- Step 4: copy code ---
COPY . .

# --- Step 5: runtime environment variables ---
# QGIS offscreen rendering
ENV QT_QPA_PLATFORM=offscreen
ENV QGIS_PREFIX_PATH=/opt/conda/envs/TeleCouplingAI

# PROJ / GDAL data paths (required by natcap.invest / pygeoprocessing)
ENV PROJ_DATA=/opt/conda/envs/TeleCouplingAI/share/proj
ENV PROJ_LIB=/opt/conda/envs/TeleCouplingAI/share/proj
ENV GDAL_DATA=/opt/conda/envs/TeleCouplingAI/share/gdal

# SSL: fix httpx TLS in conda env (certifi bundle instead of conda's)
ENV SSL_CERT_FILE=/opt/conda/envs/TeleCouplingAI/lib/python3.12/site-packages/certifi/cacert.pem
ENV REQUESTS_CA_BUNDLE=/opt/conda/envs/TeleCouplingAI/lib/python3.12/site-packages/certifi/cacert.pem

# Python path: app code + QGIS Python bindings + QGIS plugins
ENV PYTHONPATH=/app:/opt/conda/envs/TeleCouplingAI/share/qgis/python:/opt/conda/envs/TeleCouplingAI/share/qgis/python/plugins

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
