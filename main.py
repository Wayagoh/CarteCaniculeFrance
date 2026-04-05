import json
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px

# ======================
# Chargement des données
# ======================

# CSV attendu : date, departement, niveau (vert, jaune, orange, rouge)
df = pd.read_csv("vigilance.csv")
df["date"] = pd.to_datetime(df["date"])

# Charger GeoJSON des départements
with open("departements.geojson") as f:
    geojson = json.load(f)

# ======================
# Initialisation app Dash
# ======================

app = dash.Dash(__name__)

# Slider basé sur les dates
dates = df["date"].sort_values().unique()

app.layout = html.Div([
    html.H1("Carte Vigilance Canicule"),

    dcc.RangeSlider(
        id="date-slider",
        min=0,
        max=len(dates) - 1,
        value=[0, len(dates) - 1],
        marks={i: str(dates[i].date()) for i in range(0, len(dates), max(1, len(dates)//10))}
    ),

    dcc.Graph(id="map"),

    html.Div(id="stats", style={"marginTop": "20px", "fontSize": "20px"})
])

# ======================
# Callback principal
# ======================

@app.callback(
    Output("map", "figure"),
    Output("stats", "children"),
    Input("date-slider", "value"),
    Input("map", "clickData")
)
def update_map(date_range, clickData):
    start_date = dates[date_range[0]]
    end_date = dates[date_range[1]]

    filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    # Agrégation pour la carte (ex: max niveau sur période)
    agg = filtered.groupby("departement")["niveau"].max().reset_index()

    fig = px.choropleth(
        agg,
        geojson=geojson,
        locations="departement",
        featureidkey="properties.code",
        color="niveau",
        category_orders={"niveau": ["vert", "jaune", "orange", "rouge"]},
    )

    fig.update_geos(fitbounds="locations", visible=False)

    # Stats
    if clickData is None:
        return fig, "Clique sur un département"

    dept = clickData["points"][0]["location"]

    df_dept = filtered[filtered["departement"] == dept]

    rouge = (df_dept["niveau"] == "rouge").sum()
    orange = (df_dept["niveau"] == "orange").sum()

    stats_text = f"Département {dept} → Rouge: {rouge} jours | Orange: {orange} jours"

    return fig, stats_text


# ======================
# Lancement
# ======================

if __name__ == '__main__':
    app.run_server(debug=True)

