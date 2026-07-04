FROM csic_backend:latest
COPY agent.py /app/agent.py
COPY file_reference_resolver.py /app/shared/file_reference_resolver.py
COPY _qgis_scene_render_worker.py /app/renderers/_qgis_scene_render_worker.py
