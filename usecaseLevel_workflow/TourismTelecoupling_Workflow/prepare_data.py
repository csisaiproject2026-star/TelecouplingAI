"""
Prepare the Tourism Telecoupling sample data so it can be fed to the CSIS tools.

Two of the five workflow steps need a small data-prep (the other three consume the
raw sample CSVs directly via configurable field params):

  * CO2 Emissions  -> the raw tourism_Flows.csv has FROM_X/Y, TO_X/Y, Quantity but NO
                      distance column. The co2_emissions tool does not compute distance;
                      it requires a length_km column. We add a geodesic length_km here.
  * FAMD           -> the survey variables live in a shapefile's .dbf
                      (Systems_withSimulatedTourism), not a CSV. We export them to CSV.

Outputs (written next to this script):
  * flows_with_distance.csv   (CO2-ready: original cols + length_km)
  * famd_input.csv            (FAMD-ready: NAME, Role, affin, gdplog, dist, LON, LAT)
"""
import os
import math
import zipfile
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "SampleData_TourismTelecoupling")


def haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in km between two WGS84 points."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def prep_flows_for_co2():
    src = os.path.join(SAMPLE, "Flows", "tourism_Flows.csv")
    df = pd.read_csv(src)
    df["length_km"] = df.apply(
        lambda r: round(haversine_km(r["FROM_X"], r["FROM_Y"], r["TO_X"], r["TO_Y"]), 2),
        axis=1,
    )
    out = os.path.join(HERE, "flows_with_distance.csv")
    df.to_csv(out, index=False)
    print(f"[CO2]  flows_with_distance.csv  ({len(df)} flows)")
    print(f"       length_km: min={df['length_km'].min()}  max={df['length_km'].max()}  "
          f"mean={df['length_km'].mean():.1f}")
    # demo: replicate the tool's math with the paper's Boeing-777 factor (29 kg/km),
    # capacity 1 unit/trip, animal_count = Quantity -> trips = Quantity
    co2 = (df["length_km"] * df["Quantity"] * 29.0).sum()
    print(f"       demo total CO2 @29 kg/km, cap=1: {co2:,.0f} kg")
    return out


def prep_famd():
    import geopandas as gpd
    d = tempfile.mkdtemp()
    zipfile.ZipFile(os.path.join(SAMPLE, "Effect-FAMD", "Systems_withSimulatedTourism.zip")).extractall(d)
    shp = [f for f in os.listdir(d) if f.lower().endswith(".shp")][0]
    g = gpd.read_file(os.path.join(d, shp)).drop(columns="geometry")
    # keep identity + the survey variables (NEAR_DIST duplicates dist, so drop it)
    keep = [c for c in ["NAME", "Role", "affin", "gdplog", "dist", "LON", "LAT"] if c in g.columns]
    g = g[keep]
    out = os.path.join(HERE, "famd_input.csv")
    g.to_csv(out, index=False)
    print(f"[FAMD] famd_input.csv  ({len(g)} systems)  vars: affin, gdplog, dist")
    return out


if __name__ == "__main__":
    prep_flows_for_co2()
    prep_famd()
    print("done.")
