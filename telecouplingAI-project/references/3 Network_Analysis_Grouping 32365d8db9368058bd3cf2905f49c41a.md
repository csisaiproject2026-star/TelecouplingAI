# 3. Network_Analysis_Grouping

# Description

### Meaning

This function builds a **directed spatial network** from node and link data, automatically detects **community clusters** within the network using graph algorithms, and produces both a **visual PDF output** and a **statistical CSV report**. It is designed to reveal hidden groupings or communities within complex networks — such as trade flows, transport systems, or migration patterns — by analyzing how strongly nodes are connected to each other. The detected clusters are also spatially enriched by merging with an input shapefile using the `ISO_3_CODE` column, and the result is exported as an output shapefile for use in GIS environments.

### Inputs

| Parameter | Type | Description |
| --- | --- | --- |
| `Nodes_Tables` | CSV file path | Table of all nodes (e.g. cities, regions, hubs) with their attributes |
| `Nodes_Join_Attri` | string | The field/column name used to join node data (e.g. `CODE`) |
| `Links_Tables` | CSV file path | Table of directed edges/links between nodes (e.g. flows, connections) |
| `Shapefile_Path` | SHP file path | Input shapefile used as the geographic base layer for spatial output |
| `Layer_Join_Attri` | string | Column name in the shapefile used to join with node data (e.g. `ISO_3_CODE`) |
| `ClusteringAlgorithm` | string | Either `"walktrap"` or `"spin_glass"` — the graph clustering method to use |
| `WeightWithinClusters` | numeric | Distance weight applied to edges **within** the same cluster. Range: 0–100, default: `10` |
| `WeightBetweenClusters` | numeric | Distance weight applied to edges **between** different clusters. Range: 0–100, default: `2` |
| `ColorSet` | string | RColorBrewer palette name. Options: `Set1`, `Set2`, `Set3`, `Accent`, `Dark2`, `Paired`, `Pastel1`, `Pastel2` |
| `NodeSize` | numeric | Scaling factor for node sizes in the visualization. Range: 0–1, default: `0.05` |
| `EdgeWidth` | numeric | Scaling factor for edge/link widths in the visualization. Range: 0–1, default: `0.833333` |
| `LabelSize` | numeric | Font size scaling for node labels. Range: 0–1, default: `0.8` |

### Outputs

| Output | Type | Description |
| --- | --- | --- |
| `output_PDF_path` | PDF file | Visual plot of the clustered network with color-coded communities |
| `output_csv_path` | CSV file | Network statistics per node: **degree**, **closeness**, and **betweenness** centrality |
| `output_shp_path` | Shapefile (.shp) | Input shapefile enriched with cluster assignments, merged via `Layer_Join_Attri` (e.g. `ISO_3_CODE`) |
| `community_df` | Data table | Node-to-cluster assignment table returned to the KNIME workflow |

### Internal Logic

1. **Load data** — Reads the nodes and links CSV files into R data frames.
    1. **Read shapefile** — Loads the input shapefile as an `sf` spatial object.
    2. **Build directed graph** — Converts the data into an `igraph` directed graph object using `graph_from_data_frame()`.
    3. **Detect communities/clusters** — Applies either:
        - **Walktrap**: Detects communities via short random walks on the graph
        - **Spin Glass**: Detects communities using a statistical physics-inspired model
    4. **Merge clusters with shapefile** — Joins `community_df` to the shapefile attribute table using `Layer_Join_Attri` (e.g. `ISO_3_CODE`) as the common key via `left_join()`. Writes the enriched shapefile to `output_shp_path`.
    5. **Assign edge weights** — Edges within the same cluster get `WeightWithinClusters`; edges crossing clusters get `WeightBetweenClusters`. This controls how tightly or loosely clusters are drawn in the layout.
    6. **Compute layout** — Uses the **DrL (Distributed Recursive Layout)** algorithm to position nodes in 2D space based on weighted edges.
    7. **Size nodes** — Node size is calculated from the log-transformed sum of sender and receiver arrival values (`larrivals`), scaled by `NodeSize`.
    8. **Set edge widths** — Edge width is derived from the `larrivals` attribute scaled by `EdgeWidth`.
    9. **Compute network statistics** — Calculates per-node **degree** (number of connections), **closeness centrality** (how close a node is to all others), and **betweenness centrality** (how often a node lies on the shortest path between others). These are exported to CSV.
    10. **Render and export** — Plots the clustered network to a PDF, with cluster-crossing edges colored red (`tomato2`) and within-cluster edges in dark grey.
    
    ---
    
    ### Key Algorithms Used
    
    - **Walktrap community detection** — Good for finding dense, well-separated communities in large networks
    - **Spin Glass community detection** — Better for networks where communities may overlap or have complex boundaries
    - **DrL layout** — A force-directed layout optimized for large graphs, which visually separates clusters based on edge weights
    
    ---
    

This function is ideal for analyzing **flow networks** (e.g. migration, trade, transport) where understanding which nodes form natural communities or groups is critical to decision-making and planning. The shapefile output further enables results to be visualized and used in any downstream GIS workflow.

---

# Current Code for reference

```r
# Example input:
# Nodes_Tables: ..data\Network Analysis Grouping\nodes.csv
# Links_Tables: ..data\Network Analysis Grouping\links.csv
# Shapefile_Path: ..data\Network Analysis Grouping\world.shp
# Nodes_Join_Attri: CODE
# Layer_Join_Attri: ISO_3_CODE
# ClusteringAlgorithm: walktrap/spin_glass (select one from list)
# ColorSet: Set3/Set2/Set1/Accent/Dark2/Paired/Pastel1/Pastel2 (select one from list)
# WeightWithinClusters: 0-100, default as 10
# WeightBetweenClusters: 0-100, default as 2
# NodeSize: 0-1, default as 0.05
# EdgeWidth: 0-1, default as 0.833333
# LabelSize: 0-1, default as 0.8
# output_PDF_path: output\test.pdf
# output_csv_path: output\test.csv
# output_shp_path: output\test.shp

knime.out <- knime.in

require(igraph)
require(dplyr)
require(sp)
require(RColorBrewer)
require(sf)

in_params <- list()
in_params[[1]] <- knime.flow.in[["Nodes_Tables"]]
in_params[[2]] <- knime.flow.in[["Nodes_Join_Attri"]]
in_params[[3]] <- knime.flow.in[["Links_Tables"]]
in_params[[4]] <- knime.flow.in[["Shapefile_Path"]]
in_params[[5]] <- knime.flow.in[["Layer_Join_Attri"]]
in_params[[6]] <- knime.flow.in[["ClusteringAlgorithm"]]
in_params[[7]] <- knime.flow.in[["WeightWithinClusters"]]
in_params[[8]] <- knime.flow.in[["WeightBetweenClusters"]]
in_params[[9]] <- knime.flow.in[["ColorSet"]]
in_params[[10]] <- knime.flow.in[["NodeSize"]]
in_params[[11]] <- knime.flow.in[["EdgeWidth"]]
in_params[[12]] <- knime.flow.in[["LabelSize"]]

out_params <- list()
out_params[[1]] <- knime.flow.in[["output_PDF_path"]]
out_params[[2]] <- knime.flow.in[["output_shp_path"]]
out_params[[3]] <- knime.flow.in[["output_csv_path"]]

message("Reading Input Parameters...")
nodes_table                <- in_params[[1]]
nodes_table_join           <- in_params[[2]]
link_table                 <- in_params[[3]]
in_shapefile               <- in_params[[4]]
in_telecoupling_layer_join <- in_params[[5]]
clustering_algorithm       <- in_params[[6]]
weight_within              <- as.numeric(in_params[[7]])
weight_between             <- as.numeric(in_params[[8]])
color_set                  <- in_params[[9]]
node_size                  <- as.numeric(in_params[[10]])
edge_width                 <- as.numeric(in_params[[11]])
label_size                 <- as.numeric(in_params[[12]])

### Set output parameters
out_pdf <- out_params[[1]]
out_shp <- out_params[[2]]
out_csv <- out_params[[3]]

# To control thickness/distances between nodes
edge.weights <- function(community, network, weight.within = weight_within, weight.between = weight_between)
{
  bridges <- crossing(communities = community, graph = network)
  weights <- ifelse(test = bridges, yes = weight.between, no = weight.within)
  return(weights)
}

### Load node and link data
nodes_df <- read.csv(file=nodes_table, header=T, stringsAsFactors=FALSE, check.names=FALSE)
links_df <- read.csv(file=link_table, header=T, stringsAsFactors=FALSE, check.names=FALSE)

### Read input shapefile
message("Reading Shapefile...")
shp_layer <- st_read(in_shapefile)

# Change data frame format to igraph format
network_graph <- graph_from_data_frame(d=links_df, vertices=nodes_df, directed=T)

# Create clusters
message("Creating Clusters...")
if (clustering_algorithm == "walktrap")
{
  MyClusters.community <- cluster_walktrap(network_graph)
  community_df <- data.frame(
    V1 = unique(MyClusters.community)[[4]],
    cluster_N = as.numeric(unique(MyClusters.community)[[3]])
  )
  colnames(community_df)[1] <- nodes_table_join
}

if (clustering_algorithm == "spin_glass")
{
  MyClusters.community <- cluster_spinglass(network_graph)
  community_df <- data.frame(
    V1 = unique(MyClusters.community)[[7]],
    cluster_N = as.numeric(unique(MyClusters.community)[[1]])
  )
  colnames(community_df)[1] <- nodes_table_join
}

community_df[ , which(names(community_df) == nodes_table_join)] <- as.character(
  community_df[ , which(names(community_df) == nodes_table_join)]
)

### Merge community_df with shapefile using Layer_Join_Attri variable
message("Merging community clusters with shapefile...")
shp_layer[[in_telecoupling_layer_join]] <- as.character(shp_layer[[in_telecoupling_layer_join]])
community_df[[nodes_table_join]] <- as.character(community_df[[nodes_table_join]])

shp_merged <- shp_layer %>%
  left_join(community_df, by = setNames(nodes_table_join, in_telecoupling_layer_join))

### Write merged shapefile to output
message("Writing output shapefile...")
st_write(shp_merged, out_shp, delete_layer = TRUE)
message(paste("Shapefile written to:", out_shp))

# Assign colors to clusters with minimum 3 colors guard
NumberOfColors <- length(unique(MyClusters.community))
Colors <- brewer.pal(max(3, NumberOfColors), color_set)
MyClusters.col <- Colors[membership(MyClusters.community)]

# Change distances among nodes (within the same clusters & between clusters)
E(network_graph)$weight <- edge.weights(MyClusters.community, network_graph)
test.Layout.drl <- layout_with_drl(network_graph, weights = E(network_graph)$weight)

xmin <- min(test.Layout.drl[,1])
xmax <- max(test.Layout.drl[,1])
ymin <- min(test.Layout.drl[,2])
ymax <- max(test.Layout.drl[,2])

# Compute node degrees (number of links) and use that to set node size
arrivals.sum <- ((exp(V(network_graph)$larrivals.sender)-1) + (exp(V(network_graph)$larrivals.receiver-1)))
V(network_graph)$larrivals.total <- log1p(arrivals.sum)
V(network_graph)$size <- ((V(network_graph)$larrivals.total)^2) * node_size

# Set edge width based on weight
E(network_graph)$width <- E(network_graph)$larrivals * edge_width

V(network_graph)$label.color <- "black"
V(network_graph)$label <- V(network_graph)$name
V(network_graph)$label.cex <- label_size

message("Creating Output CSV file...")
deg_stat  <- degree(network_graph)
clo_stat  <- closeness(network_graph, normalized = TRUE)
betw_stat <- betweenness(network_graph)
inte_csv  <- data.frame(degree = deg_stat, closeness = clo_stat, betweenness = betw_stat)
write.csv(inte_csv, file = out_csv)

result = tryCatch({
  pdf(out_pdf)
  suppressWarnings(plot(
    x = MyClusters.community,
    y = network_graph,
    layout = test.Layout.drl,
    mark.groups = NULL,
    edge.color = c("tomato2", "darkgrey")[crossing(MyClusters.community, network_graph)+1],
    edge.arrow.size = 0,
    rescale = F,
    xlim = c(xmin, xmax),
    ylim = c(ymin, ymax),
    asp = 0,
    col = MyClusters.col
  ))
}, finally = {
  dev.off()
})

knime.out <- community_df
```