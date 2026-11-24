"""
Carte de la mobilité inter-académique Parcoursup (2018-2025)

Ce que mesure le fichier : pour chaque formation (ligne) et chaque année (session),
  - acc_tot       : nb d'admis ayant accepté la proposition
  - acc_aca_orig  : dont nb d'admis issus de la MÊME académie que la formation
=> admis venus d'une autre académie = acc_tot - acc_aca_orig  (entrants)

Dépendances : pip install pandas geopandas matplotlib plotly requests
"""
import io
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import plotly.express as px
import requests

CSV = "parcoursup_2018_2025.csv"
GEOJSON_DEP = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
               "master/departements-version-simplifiee.geojson")

# ----------------------------------------------------------------------
# 1. Chargement et harmonisation des noms d'académies
# ----------------------------------------------------------------------
cols = ["session", "dep", "acad_mies", "acc_tot", "acc_aca_orig"]
df = pd.read_csv(CSV, sep=";", usecols=cols, low_memory=False)

# Les noms changent selon les années : Caen + Rouen -> Normandie (2020),
# "Besancon"/"Besançon", "Réunion"/"La Réunion"
HARMONISATION = {
    "Caen": "Normandie", "Rouen": "Normandie",
    "Besancon": "Besançon",
    "Réunion": "La Réunion",
}
df["academie"] = df["acad_mies"].replace(HARMONISATION)
df["dep"] = df["dep"].astype(str)

# ----------------------------------------------------------------------
# 2. Indicateurs par académie et par année
# ----------------------------------------------------------------------
agg = (df.groupby(["session", "academie"], as_index=False)
         .agg(admis=("acc_tot", "sum"), meme_aca=("acc_aca_orig", "sum")))
agg["entrants"] = agg["admis"] - agg["meme_aca"]          # venus d'ailleurs
agg["part_entrants"] = 100 * agg["entrants"] / agg["admis"]  # en %

print(agg.pivot(index="academie", columns="session", values="part_entrants").round(1))

# ----------------------------------------------------------------------
# 3. Fond de carte : on fusionne les départements en académies
#    (table département -> académie déduite du fichier lui-même)
# ----------------------------------------------------------------------
dep2aca = (df.dropna(subset=["dep"])
             .groupby("dep")["academie"]
             .agg(lambda s: s.mode().iloc[0])
             .to_dict())
dep2aca["20"] = "Corse"   # certains codes anciens

deps = gpd.read_file(io.BytesIO(requests.get(GEOJSON_DEP, timeout=30).content))
deps["academie"] = deps["code"].map(dep2aca)
deps = deps.dropna(subset=["academie"])          # exclut les départements non présents
acad = deps.dissolve(by="academie").reset_index()[["academie", "geometry"]]

# ----------------------------------------------------------------------
# 4a. Carte statique : une carte par année, même échelle de couleurs
# ----------------------------------------------------------------------
annees = sorted(agg["session"].unique())
vmin, vmax = agg["part_entrants"].min(), agg["part_entrants"].max()

fig, axes = plt.subplots(2, 4, figsize=(18, 10))
for ax, an in zip(axes.ravel(), annees):
    d = acad.merge(agg[agg.session == an], on="academie", how="left")
    d.plot(column="part_entrants", cmap="YlOrRd", vmin=vmin, vmax=vmax,
           edgecolor="white", linewidth=0.4, ax=ax,
           missing_kwds={"color": "lightgrey"})
    ax.set_title(str(an), fontsize=14)
    ax.set_axis_off()

sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin, vmax))
fig.colorbar(sm, ax=axes, shrink=0.6, label="% d'admis venus d'une autre académie")
fig.suptitle("Parcoursup : part des admis venant d'une autre académie", fontsize=16)
fig.savefig("mobilite_parcoursup_cartes.png", dpi=150, bbox_inches="tight")

# ----------------------------------------------------------------------
# 4b. Carte interactive animée (curseur sur les années), export HTML
# ----------------------------------------------------------------------
geo = acad.set_index("academie").__geo_interface__
fig2 = px.choropleth(
    agg, geojson=geo, locations="academie", featureidkey="id",
    color="part_entrants", animation_frame="session",
    color_continuous_scale="YlOrRd",
    range_color=(vmin, vmax),
    hover_data={"entrants": ":,", "admis": ":,"},
    labels={"part_entrants": "% venus d'ailleurs"},
)
fig2.update_geos(fitbounds="locations", visible=False)
fig2.write_html("mobilite_parcoursup_animation.html")

# Variante : nombre absolu d'entrants -> color="entrants"