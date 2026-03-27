# 1. Use Miniforge image, which comes with efficient mamba
FROM condaforge/miniforge3:latest

# 2. Set working directory
WORKDIR /app

# 3. Create environment and install core dependencies
# Merging mamba installations to reduce the number of image layers
RUN mamba create -n TeleCouplingAI python=3.13.11 -y && \
    mamba install -n TeleCouplingAI -c conda-forge -y \
        gdal=3.10.3 geos=3.14.1 proj=9.7.1 \
        geopandas=1.1.2 rasterio=1.4.4 shapely=2.1.2 \
        numpy=2.4.1 pandas=2.3.3 scikit-learn=1.8.0 \
        matplotlib=3.10.8 rtree=1.4.1 networkx=3.6.1 \
        taskgraph=0.11.2 fastapi=0.128.0 uvicorn=0.40.0 \
        pydantic=2.10.6 flask=3.1.2 flask-cors=6.0.2 \
        requests=2.32.5 python-dotenv=1.2.1 pillow=12.1.0 \
        pyyaml=6.0.3 gxx_linux-64 gcc_linux-64 && \
    mamba clean -afy

# 4. Set environment variables to ensure subsequent commands use this environment by default
ENV CONDA_DEFAULT_ENV=TeleCouplingAI
ENV PATH=/opt/conda/envs/TeleCouplingAI/bin:$PATH

# 5. Create compiler symlinks and install Pip dependencies
RUN ln -s /opt/conda/envs/TeleCouplingAI/bin/x86_64-conda-linux-gnu-g++ /opt/conda/envs/TeleCouplingAI/bin/g++ && \
    ln -s /opt/conda/envs/TeleCouplingAI/bin/x86_64-conda-linux-gnu-gcc /opt/conda/envs/TeleCouplingAI/bin/gcc && \
    pip install --no-cache-dir \
        pygeoprocessing==2.4.10 \
        frozenlist==1.8.0 \
        importlib-metadata==8.7.1 \
        propcache==0.4.1 \
        natcap.invest==3.14.3 \
        google-genai==1.63.0 \
        python-multipart==0.0.21 \
        aiofiles==3.13.3





# 3. 将本机的环境清单拷贝到容器里
# COPY local_TelecouplingAI_environment.yml .

# 4. 根据清单创建环境
# --name base 表示我们直接更新 base 环境，或者你可以指定新名字
# 如果你的 yml 里有名字，它会自动创建那个名字的环境
#RUN conda env create -f local_TelecouplingAI_environment.yml

# 5. 确保后续命令在复刻的环境中运行
# 注意：替换下面的 'TeleCouplingAI' 为你 yml 文件第一行显示的名字
#ENV PATH /opt/conda/envs/TeleCouplingAI/bin:$PATH

# 6. 拷贝你的后端代码
#COPY . .

#EXPOSE 8000

# 7. 启动后端
CMD ["tail", "-f", "/dev/null"]
#CMD ["python", "main.py"]