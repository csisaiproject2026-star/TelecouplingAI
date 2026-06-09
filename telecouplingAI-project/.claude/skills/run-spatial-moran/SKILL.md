# Skill: run-spatial-moran

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/spatial_moran.py
Tool name: run_spatial_autocorrelation_moran

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- input_vector: path to a vector file (shapefile .shp, GeoJSON, or GPKG) with geometry and the attribute to analyse
- value_field: name of the numeric attribute column to test for spatial autocorrelation

**Optional parameters**:
- weights_type: spatial weights definition — 'queen' (default) or 'rook' contiguity for polygons, or 'knn' for points / k-nearest neighbours
- k_neighbors: number of neighbours when weights_type='knn', default 8
- permutations: permutations for the pseudo p-value, default 999

**Key notes**:
- Moran's I measures spatial autocorrelation: whether nearby features have similar values.
- Contiguity weights (queen/rook) require POLYGON geometry. For point layers the tool automatically uses KNN.
- A shapefile is several files (.shp/.shx/.dbf/.prj) — make sure all were uploaded; pass the .shp path.
- Trigger words: Moran's I, spatial autocorrelation, spatial clustering, hot spot, cold spot, LISA, spatial outlier, spatial statistics.

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| moran_global.csv | CSV | Global Moran's I, expected I, z-score, normal & permutation p-values, and a plain-language interpretation |
| moran_local_lisa.csv | CSV | Per-feature local Moran's I, z-score, p-value, and cluster label (HH/LL/HL/LH/ns) |
| moran_lisa_summary.csv | CSV | Count of features in each cluster category |
| moran_lisa.geojson | Download | The input features with local_I, lisa_p, and cluster columns — render on a map to see hot/cold spots |

### Suggested next steps
- Read moran_global.csv: I > 0 with p < 0.05 means significant clustering; I < 0 means dispersion; ~0 means random.
- Use moran_lisa_summary.csv to see how many hot spots (HH) and cold spots (LL) were found.
- To visualize the hot/cold spot map, call render_spatial_file on moran_lisa.geojson (only if the user asks to see it).
