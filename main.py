"""
Application Dash — Vigilance Canicule par Département
======================================================
Dépendances : pip install dash plotly pandas

Lancement   : python app_canicule.py
puis ouvrir : http://127.0.0.1:8050
"""

import json
from datetime import date, timedelta
import sys
import os
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

# ──────────────────────────────────────────────
# 1. CONFIGURATION — adaptez ces chemins
# ──────────────────────────────────────────────
def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

GEOJSON_PATH = resource_path("departements.geojson")
CSV_PATH     = resource_path(os.path.join("RécuperationDonnées", "historique_canicule.csv"))

DATE_MIN   = date(2023, 1, 1)
DATE_MAX   = date(2025, 12, 31)
TOTAL_DAYS = (DATE_MAX - DATE_MIN).days   # 1094


# ──────────────────────────────────────────────
# 2. CHARGEMENT DES DONNÉES
# ──────────────────────────────────────────────
def load_data():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        geojson = json.load(f)

    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    df["date"]        = pd.to_datetime(df["date"]).dt.date
    df["departement"] = df["departement"].astype(str).str.zfill(2)
    df["niveau"]      = pd.to_numeric(df["niveau"], errors="coerce").fillna(0)

    dept_codes = [feat["properties"]["code"] for feat in geojson["features"]]
    code_to_nom = {
        feat["properties"]["code"]: feat["properties"].get("nom", feat["properties"]["code"])
        for feat in geojson["features"]
    }
    return geojson, df, dept_codes, code_to_nom


try:
    geojson, df_global, dept_codes, code_to_nom = load_data()
    DATA_LOADED = True
except FileNotFoundError as e:
    DATA_LOADED = False
    LOAD_ERROR  = str(e)
    geojson, df_global, dept_codes, code_to_nom = {}, pd.DataFrame(), [], {}


# ──────────────────────────────────────────────
# 3. HELPERS
# ──────────────────────────────────────────────
NIVEAU_COLORS = {
    0: "#d4e6f1",
    1: "#adebb3",
    2: "#f9e79f",
    3: "#f0b27a",
    4: "#e74c3c",
}
NIVEAU_LABELS = {
    0: "Aucune vigilance",
    1: "Vert",
    2: "Jaune",
    3: "Orange",
    4: "Rouge",
}

def days_to_date(n: int) -> date:
    return DATE_MIN + timedelta(days=int(n))

def date_to_days(d: date) -> int:
    return (d - DATE_MIN).days

def get_nom(code: str) -> str:
    return code_to_nom.get(code, code)

def compute_means(d_start: date, d_end: date) -> pd.DataFrame:
    n_days = (d_end - d_start).days + 1
    mask   = (df_global["date"] >= d_start) & (df_global["date"] <= d_end)
    sub    = df_global[mask]

    sums = (sub.groupby("departement")["niveau"]
               .sum()
               .reindex(dept_codes, fill_value=0))

    # Jours par niveau pour chaque département
    def count_level(level):
        return (sub[sub["niveau"] == level]
                .groupby("departement")["niveau"]
                .count()
                .reindex(dept_codes, fill_value=0))

    j2 = count_level(2)
    j3 = count_level(3)
    j4 = count_level(4)

    return pd.DataFrame({
        "code":    dept_codes,
        "moyenne": sums.values / n_days,
        "j_jaune":  j2.values,
        "j_orange": j3.values,
        "j_rouge":  j4.values,
    })


def build_map(d_start: date, d_end: date, selected_dept=None) -> go.Figure:
    means      = compute_means(d_start, d_end)
    customdata = [[get_nom(c)] for c in means["code"]]

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=means["code"],
        z=means["moyenne"],
        featureidkey="properties.code",
        colorscale=[
            [0.00, NIVEAU_COLORS[0]],
            [0.25, NIVEAU_COLORS[1]],
            [0.50, NIVEAU_COLORS[2]],
            [0.75, NIVEAU_COLORS[3]],
            [1.00, NIVEAU_COLORS[4]],
        ],
        zmin=0, zmax=4,
        marker_line_width=0.6,
        marker_line_color="#6b7a8d",
        marker_opacity=0.20,
        hovertemplate=(
            "<b>%{customdata[0]}</b> (%{location})<br>"
            "Moyenne : <b>%{z:.2f}</b> / 4<br><extra></extra>"
        ),
        customdata=customdata,
        colorbar=dict(
            title=dict(text="Niveau moyen",
                       font=dict(family="DM Sans", size=12, color="#e8eaf0")),
            tickvals=[0, 1, 2, 3, 4],
            ticktext=["0 – Aucune", "1 – Vert", "2 – Jaune", "3 – Orange", "4 – Rouge"],
            tickfont=dict(family="DM Sans", size=11, color="#c8cad6"),
            bgcolor="rgba(18,24,38,0.7)",
            bordercolor="rgba(255,255,255,0.08)",
            borderwidth=1,
            len=0.75, thickness=14, x=1.01,
            y=0,  # ancrage en bas (défaut = 0.5 = centré)
            yanchor="bottom",
        ),
    ))

    if selected_dept:
        print(f"build_map — selected_dept='{selected_dept}', codes sample={means['code'].head().tolist()}")
        sel = means[means["code"] == selected_dept]
        print(f"build_map — sel empty={sel.empty}")
        if not sel.empty:
            fig.add_trace(go.Choroplethmapbox(
                geojson=geojson,
                locations=sel["code"],
                z=sel["moyenne"],
                featureidkey="properties.code",
                colorscale=[[0, "#ffffff"], [1, "#ffffff"]],
                zmin=0, zmax=4,
                marker_line_width=2.5,
                marker_line_color="#f0c040",
                marker_opacity=0.5, #Le problème était ici
                showscale=False,
                hoverinfo="skip",
            ))

    fig.update_layout(
        mapbox=dict(style="carto-darkmatter",
                    center={"lat": 46.5, "lon": 2.5}, zoom=4.8),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        clickmode="event+select",
        uirevision=f"map-{selected_dept or 'none'}",
    )
    return fig


def build_dept_chart(dept_code: str, d_start: date, d_end: date) -> go.Figure:
    dept_nom  = get_nom(dept_code)
    all_dates = pd.date_range(d_start, d_end, freq="D").date
    mask = (
        (df_global["date"] >= d_start) &
        (df_global["date"] <= d_end) &
        (df_global["departement"] == dept_code)
    )
    sub  = df_global[mask].set_index("date")["niveau"]
    nivs = [int(sub.get(d, 0)) for d in all_dates]

    # Comptage par niveau
    j_vert   = nivs.count(1)
    j_jaune  = nivs.count(2)
    j_orange = nivs.count(3)
    j_rouge  = nivs.count(4)

    fig = go.Figure(go.Bar(
        x=list(all_dates), y=nivs,
        marker_color=[NIVEAU_COLORS[n] for n in nivs],
        marker_line_width=0,
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Niveau : %{y}<extra></extra>",
    ))
    mean_val = sum(nivs) / len(nivs) if nivs else 0
    fig.add_hline(
        y=mean_val, line_dash="dash", line_color="#f0c040", line_width=1.5,
        annotation_text=f"Moy. {mean_val:.2f}",
        annotation_font=dict(color="#f0c040", size=11, family="DM Sans"),
        annotation_position="top right",
    )
    fig.update_layout(
        title=dict(
            text=(
                f"<b>{dept_nom}</b> ({dept_code})      "
                f"<span style='font-size:12px; color:{NIVEAU_COLORS[1]}'>🟢 {j_vert}j</span>  "
                f"<span style='font-size:12px; color:{NIVEAU_COLORS[2]}'>🟡 {j_jaune}j</span>  "
                f"<span style='font-size:12px; color:{NIVEAU_COLORS[3]}'>🟠 {j_orange}j</span>  "
                f"<span style='font-size:12px; color:{NIVEAU_COLORS[4]}'>🔴 {j_rouge}j</span>"
            ),
            font=dict(family="DM Serif Display", size=20, color="#e8eaf0"),
            x=0, xanchor="left", pad=dict(l=4, t=4),
        ),
        xaxis=dict(tickformat="%b %Y",
                   tickfont=dict(family="DM Sans", size=14, color="#8892a4"),
                   showgrid=False, linecolor="rgba(255,255,255,0.1)"),
        yaxis=dict(range=[-0.2, 4.3], tickvals=[0, 1, 2, 3, 4],
                   tickfont=dict(family="DM Sans", size=25, color="#8892a4"),
                   gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        bargap=0.15 if (d_end - d_start).days < 90 else 0.05,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=10, t=44, b=30),
        showlegend=False,
    )
    return fig


def build_ranking_panel(d_start: date, d_end: date) -> list:
    """Retourne les enfants du panneau classement."""
    means = compute_means(d_start, d_end).sort_values("moyenne", ascending=False)

    def badge(count, color, label):
        """Petite pastille 'N j' colorée."""
        return html.Div(
            style={
                "display": "flex", "flexDirection": "column",
                "alignItems": "center", "flexShrink": "0", "width": "28px",
            },
            children=[
                html.Span(str(int(count)), style={
                    "fontSize": "14px", "fontWeight": "500",
                    "color": color if count > 0 else "#3a4255",
                    "fontVariantNumeric": "tabular-nums", "lineHeight": "1.2",
                }),
                html.Span(label, style={
                    "fontSize": "11px", "color": "#3a4255",
                    "letterSpacing": "0.04em", "lineHeight": "1",
                }),
            ],
        )

    rows = []
    for rank, (_, row) in enumerate(means.iterrows(), start=1):
        moy     = row["moyenne"]
        code    = row["code"]
        nom     = get_nom(code)
        niv_col = NIVEAU_COLORS[min(4, round(moy))]
        bar_pct = int(moy / 4 * 100)

        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "gap": "6px",
                "padding": "4px 8px", "borderRadius": "5px",
                "cursor": "pointer", "position": "relative", "overflow": "hidden",
            },
            children=[
                # Barre de fond
                html.Div(style={
                    "position": "absolute", "left": "0", "top": "0",
                    "width": f"{bar_pct}%", "height": "100%",
                    "background": niv_col, "opacity": "0.09", "borderRadius": "5px",
                }),
                # Rang
                html.Span(str(rank), style={
                    "fontSize": "18px", "color": "#4a5568",
                    "width": "20px", "textAlign": "right", "flexShrink": "0",
                    "fontVariantNumeric": "tabular-nums",
                }),
                # Pastille
                html.Div(style={
                    "width": "7px", "height": "7px", "borderRadius": "50%",
                    "backgroundColor": niv_col, "flexShrink": "0",
                }),
                # Nom
                html.Span(nom, style={
                    "fontSize": "18px", "color": "#c8cad6", "flex": "1",
                    "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
                }),
                # Code
                html.Span(f"({code})", style={
                    "fontSize": "18px", "color": "#4a5568", "flexShrink": "0",
                }),
                # Séparateur vertical léger
                html.Div(style={
                    "width": "1px", "height": "20px",
                    "background": "rgba(255,255,255,0.07)", "flexShrink": "0",
                }),
                # Moyenne
                html.Span(f"{moy:.2f}", style={
                    "fontSize": "18px", "fontWeight": "500",
                    "color": niv_col if moy > 0.01 else "#4a5568",
                    "flexShrink": "0", "fontVariantNumeric": "tabular-nums",
                    "width": "32px", "textAlign": "right",
                }),
                # Jours J / O / R
                badge(row["j_jaune"],  NIVEAU_COLORS[2], "jaune"),
                badge(row["j_orange"], NIVEAU_COLORS[3], "org."),
                badge(row["j_rouge"],  NIVEAU_COLORS[4], "rouge"),
            ],
        ))

    # En-tête avec légende des colonnes
    header = html.Div(
        style={
            "display": "flex", "alignItems": "center", "gap": "6px",
            "padding": "0 8px 6px", "flexShrink": "0",
        },
        children=[
            html.Span("CLASSEMENT",
                      style={"fontSize": "9px", "letterSpacing": "0.10em",
                             "color": "#8892a4", "flex": "1"}),
            html.Span("moy.",  style={"fontSize": "9px", "color": "#4a5568",
                                      "width": "32px", "textAlign": "right"}),
            html.Span("🟡",    style={"fontSize": "9px", "width": "28px", "textAlign": "center"}),
            html.Span("🟠",    style={"fontSize": "9px", "width": "28px", "textAlign": "center"}),
            html.Span("🔴",    style={"fontSize": "9px", "width": "28px", "textAlign": "center"}),
        ],
    )

    return [
        header,
        html.Div(
            style={"overflowY": "auto", "flex": "1", "paddingRight": "4px"},
            children=rows,
        ),
    ]


# ──────────────────────────────────────────────
# 4. LAYOUT
# ──────────────────────────────────────────────
slider_marks = {}
current = DATE_MIN
while current <= DATE_MAX:
    d = date_to_days(current)
    if current.day <= 7 and current.month in (1, 4, 7, 10):
        slider_marks[d] = {
            "label": current.strftime("%b %Y"),
            "style": {"color": "#8892a4", "fontSize": "10px", "fontFamily": "DM Sans"},
        }
    current += timedelta(weeks=1)
slider_marks[0] = {
    "label": DATE_MIN.strftime("%d/%m/%Y"),
    "style": {"color": "#f0c040", "fontSize": "10px", "fontFamily": "DM Sans"},
}
slider_marks[TOTAL_DAYS] = {
    "label": DATE_MAX.strftime("%d/%m/%Y"),
    "style": {"color": "#f0c040", "fontSize": "10px", "fontFamily": "DM Sans"},
}

search_options = [
    {"label": f"{get_nom(c)}  ({c})", "value": c}
    for c in sorted(dept_codes)
]

app = Dash(__name__, title="Vigilance Canicule", suppress_callback_exceptions=True)

app.layout = html.Div(
    id="root",
    style={
        "display": "flex", "flexDirection": "column", "height": "100vh",
        "background": "#0d1120", "fontFamily": "'DM Sans', sans-serif",
        "color": "#e8eaf0", "overflow": "hidden",
    },
    children=[
        html.Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Serif+Display&display=swap",
        ),

        # ── En-tête ────────────────────────────────────────────
        html.Div(
            style={
                "display": "flex", "alignItems": "center",
                "padding": "10px 24px 8px",
                "borderBottom": "1px solid rgba(255,255,255,0.07)",
                "gap": "16px", "flexShrink": "0",
            },
            children=[
                html.Span("☀", style={"fontSize": "22px"}),
                html.H1("Vigilance Canicule", style={
                    "margin": "0", "fontSize": "18px",
                    "fontFamily": "'DM Serif Display', serif",
                    "letterSpacing": "0.02em", "fontWeight": "400",
                }),
                html.Span("France métropolitaine · 2023–2025",
                          style={"color": "#8892a4", "fontSize": "12px",
                                 "marginLeft": "6px", "flex": "1"}),
            ],
        ),

        # ── Corps ──────────────────────────────────────────────
        html.Div(
            style={"display": "flex", "flex": "1", "overflow": "hidden"},
            children=[

                # ═══ CARTE (gauche) ════════════════════════════
                html.Div(
                    style={"flex": "1.4", "position": "relative", "minWidth": "0"},
                    children=[
                        dcc.Graph(
                            id="map-chart",
                            style={"height": "100%", "width": "100%"},
                            config={"scrollZoom": True, "displayModeBar": False},
                        ),

                        # ── Barre de recherche (haut gauche)
                        html.Div(
                            style={
                                "position": "absolute", "top": "12px", "left": "12px",
                                "width": "270px", "zIndex": "10",
                            },
                            children=[
                                dcc.Dropdown(
                                    id="dept-search",
                                    options=search_options,
                                    placeholder="🔍  Rechercher un département…",
                                    clearable=True,
                                    searchable=True,
                                ),
                            ],
                        ),

                        # Badge sélection
                        html.Div(id="selected-badge", style={"display": "none"}),
                    ],
                ),

                # ═══ PANNEAU DROIT ═════════════════════════════
                html.Div(
                    style={
                        "flex": "1", "display": "flex", "flexDirection": "column",
                        "padding": "16px 20px",
                        "borderLeft": "1px solid rgba(255,255,255,0.07)",
                        "overflow": "hidden", "gap": "14px", "minWidth": "0",
                    },
                    children=[

                        # Période
                        html.Div(style={"flexShrink": "0"}, children=[
                            html.Div("PÉRIODE D'ANALYSE",
                                     style={"fontSize": "9px", "letterSpacing": "0.12em",
                                            "color": "#8892a4", "marginBottom": "8px"}),
                            html.Div(
                                style={"display": "flex", "gap": "8px", "alignItems": "center"},
                                children=[
                                    dcc.DatePickerSingle(
                                        id="date-start-picker", date=DATE_MIN,
                                        min_date_allowed=DATE_MIN, max_date_allowed=DATE_MAX,
                                        display_format="DD/MM/YYYY", style={"flex": "1"},
                                    ),
                                    html.Span("→", style={"color": "#8892a4", "fontSize": "14px"}),
                                    dcc.DatePickerSingle(
                                        id="date-end-picker", date=DATE_MAX,
                                        min_date_allowed=DATE_MIN, max_date_allowed=DATE_MAX,
                                        display_format="DD/MM/YYYY", style={"flex": "1"},
                                    ),
                                ],
                            ),
                        ]),

                        # Slider
                        html.Div(style={"flexShrink": "0"}, children=[
                            html.Div(
                                style={"display": "flex", "justifyContent": "space-between",
                                       "marginBottom": "4px"},
                                children=[
                                    html.Span("AJUSTER LA PÉRIODE",
                                              style={"fontSize": "9px", "letterSpacing": "0.12em",
                                                     "color": "#8892a4"}),
                                    html.Span(id="slider-period-label",
                                              style={"fontSize": "15px", "color": "#f0c040"}),
                                ],
                            ),
                            dcc.RangeSlider(
                                id="week-slider", min=0, max=TOTAL_DAYS,
                                step=7, value=[0, TOTAL_DAYS],
                                marks=slider_marks, allowCross=False,
                                # tooltip={"placement": "bottom", "always_visible": False},
                            ),
                        ]),

                        # Stats
                        html.Div(id="stats-panel",
                                 style={"display": "flex", "gap": "8px", "flexShrink": "0"}),

                        # Légende
                        html.Div(
                            style={"display": "flex", "gap": "6px",
                                   "flexWrap": "wrap", "flexShrink": "0"},
                            children=[
                                html.Div(
                                    style={"display": "flex", "alignItems": "center",
                                           "gap": "4px", "fontSize": "11px", "color": "#8892a4"},
                                    children=[
                                        html.Div(style={
                                            "width": "12px", "height": "12px",
                                            "borderRadius": "2px",
                                            "backgroundColor": NIVEAU_COLORS[n],
                                        }),
                                        html.Span(NIVEAU_LABELS[n]),
                                    ],
                                )
                                for n in range(5)
                            ],
                        ),

                        # Séparateur
                        html.Div(style={
                            "borderTop": "1px solid rgba(255,255,255,0.07)",
                            "flexShrink": "0",
                        }),

                        # Zone principale (graphique / classement / placeholder)
                        html.Div(
                            style={"flex": "1", "minHeight": "0", "position": "relative",
                                   "display": "flex", "flexDirection": "column"},
                            children=[
                                html.Div(
                                    id="chart-placeholder",
                                    style={
                                        "display": "flex", "alignItems": "center",
                                        "justifyContent": "center", "height": "100%",
                                        "color": "#3d4558", "fontSize": "13px",
                                        "textAlign": "center", "lineHeight": "1.6",
                                        "border": "1px dashed rgba(255,255,255,0.06)",
                                        "borderRadius": "8px",
                                    },
                                    children=[html.Div([
                                        html.Div("☝", style={"fontSize": "28px", "marginBottom": "8px"}),
                                        html.Div("Cliquez sur un département"),
                                        html.Div("pour afficher son historique",
                                                 style={"fontSize": "11px", "marginTop": "2px"}),
                                    ])],
                                ),
                                dcc.Graph(
                                    id="dept-chart",
                                    style={"height": "100%", "display": "none"},
                                    config={"displayModeBar": False},
                                ),
                                html.Div(
                                    id="ranking-panel",
                                    style={"display": "none", "height": "100%",
                                           "flexDirection": "column"},
                                ),
                            ],
                        ),

                    ],
                ),
            ],
        ),

        # ── Stores ─────────────────────────────────────────────
        dcc.Store(id="click-source", data=None),  # "map" | "search" | None
        dcc.Store(id="selected-dept", data=None),
        dcc.Store(id="current-dates", data={
            "start": DATE_MIN.isoformat(), "end": DATE_MAX.isoformat(),
        }),
        # "none" | "dept" | "ranking"
        dcc.Store(id="view-mode", data="none"),
        # True si la sélection vient de la barre de recherche (pas de surbrillance carte)
        # dcc.Store(id="search-source", data=False),
    ],
)


# ──────────────────────────────────────────────
# 5. CALLBACKS
# ──────────────────────────────────────────────

@app.callback(
    Output("date-start-picker", "date"),
    Output("date-end-picker", "date"),
    Input("week-slider", "value"),
    prevent_initial_call=True,
)
def slider_to_dates(v):
    return days_to_date(v[0]).isoformat(), days_to_date(v[1]).isoformat()


@app.callback(
    Output("week-slider", "value"),
    Input("date-start-picker", "date"),
    Input("date-end-picker", "date"),
    prevent_initial_call=True,
)
def dates_to_slider(s, e):
    if not s or not e:
        return no_update
    return [date_to_days(date.fromisoformat(s)), date_to_days(date.fromisoformat(e))]


@app.callback(
    Output("current-dates", "data"),
    Input("date-start-picker", "date"),
    Input("date-end-picker", "date"),
)
def store_dates(s, e):
    d_start = date.fromisoformat(s) if s else DATE_MIN
    d_end   = date.fromisoformat(e) if e else DATE_MAX
    return {"start": d_start.isoformat(), "end": d_end.isoformat()}


@app.callback(
    Output("slider-period-label", "children"),
    Input("current-dates", "data"),
)
def update_period_label(dates):
    d_start = date.fromisoformat(dates["start"])
    d_end   = date.fromisoformat(dates["end"])
    n       = (d_end - d_start).days + 1
    return f"{d_start.strftime('%d/%m/%Y')}  →  {d_end.strftime('%d/%m/%Y')}  ({n} j)"


# ── Département sélectionné : carte OU barre de recherche
@app.callback(
    Output("selected-dept", "data"),
    Output("dept-search", "value"),
    Output("click-source", "data"),
    Input("map-chart", "clickData"),
    Input("dept-search", "value"),
    State("selected-dept", "data"),
    prevent_initial_call=True,
)
def store_selected_dept(click_data, search_value, current_dept):
    triggered = ctx.triggered_id
    print(f"store_selected_dept triggered by {triggered} — search_value={search_value}, current_dept={current_dept}")

    if triggered == "dept-search":
        # print(search_value)
        if search_value:
            # print(search_value)
            return search_value, no_update, "search"
        return None, no_update, None

    if triggered == "map-chart" and click_data:
        try:
            code = click_data["points"][0]["location"]
            if code == current_dept:
                print(code, current_dept)
                # print("ok")
                return None, no_update, None
            # print(code)
            return code, no_update, "map"
        except (KeyError, IndexError):
            pass
    # print("pas ok")
    return current_dept, no_update, no_update


@app.callback(
    Output("view-mode", "data"),
    Input("ranking-trigger", "n_clicks"),
    Input("selected-dept", "data"),
    Input("click-source", "data"),
    State("view-mode", "data"),
    prevent_initial_call=True,
)
def update_view_mode(_ranking_clicks, selected_dept, click_source, current_mode):
    triggered = ctx.triggered_id

    if triggered == "ranking-trigger":
        if not _ranking_clicks:
            return current_mode
        if current_mode == "ranking":
            return "dept" if selected_dept else "none"
        return "ranking"

    if triggered in ("selected-dept", "click-source"):
        if selected_dept:
            return "dept"
        return "none"

    return current_mode


# ── Carte
@app.callback(
    Output("map-chart", "figure"),
    Input("current-dates", "data"),
    Input("selected-dept", "data"),
)
def update_map(dates, selected_dept):
    # print(f"update_map triggered — selected_dept={selected_dept}")
    d_start = date.fromisoformat(dates["start"])
    d_end   = date.fromisoformat(dates["end"])
    return build_map(d_start, d_end, selected_dept)


# ── Badge sur la carte
@app.callback(
    Output("selected-badge", "children"),
    Output("selected-badge", "style"),
    Input("selected-dept", "data"),
)
def update_badge(selected_dept):
    if not selected_dept:
        return "", {"display": "none"}
    return (
        f"📍 {get_nom(selected_dept)} ({selected_dept})",
        {
            "display": "block", "position": "absolute",
            "top": "60px", "left": "12px",
            "background": "rgba(18,24,38,0.88)",
            "border": "1px solid rgba(240,192,64,0.5)",
            "borderRadius": "6px", "padding": "6px 12px",
            "fontSize": "12px", "color": "#f0c040",
            "backdropFilter": "blur(4px)", "zIndex": "9",
        },
    )


# ── Panneau inférieur (graphique / classement / placeholder)
@app.callback(
    Output("dept-chart",        "figure"),
    Output("dept-chart",        "style"),
    Output("chart-placeholder", "style"),
    Output("ranking-panel",     "children"),
    Output("ranking-panel",     "style"),
    Input("view-mode",          "data"),
    Input("selected-dept",      "data"),
    Input("current-dates",      "data"),
)
def update_bottom_panel(view_mode, selected_dept, dates):
    d_start = date.fromisoformat(dates["start"])
    d_end   = date.fromisoformat(dates["end"])

    s_chart  = {"height": "100%", "display": "none"}
    s_rank   = {"display": "none"}
    s_ph     = {
        "display": "flex", "alignItems": "center", "justifyContent": "center",
        "height": "100%", "color": "#3d4558", "fontSize": "13px",
        "textAlign": "center", "lineHeight": "1.6",
        "border": "1px dashed rgba(255,255,255,0.06)", "borderRadius": "8px",
    }

    if view_mode == "ranking":
        children = build_ranking_panel(d_start, d_end)
        return (no_update,
                s_chart,
                {"display": "none"},
                children,
                {"display": "flex", "flexDirection": "column", "height": "100%"})

    if view_mode == "dept" and selected_dept:
        fig = build_dept_chart(selected_dept, d_start, d_end)
        return (fig,
                {"height": "100%", "display": "block"},
                {"display": "none"},
                no_update,
                s_rank)

    return no_update, s_chart, s_ph, no_update, s_rank


# ── Stats (la 3e carte est cliquable pour afficher le classement)
@app.callback(
    Output("stats-panel", "children"),
    Input("current-dates", "data"),
    State("view-mode", "data"),
)
def update_stats(dates, view_mode):
    d_start = date.fromisoformat(dates["start"])
    d_end   = date.fromisoformat(dates["end"])
    means   = compute_means(d_start, d_end)

    n_days   = (d_end - d_start).days + 1
    avg_fr   = means["moyenne"].mean()
    n_alerte = int((means["moyenne"] >= 2).sum())
    dept_max = means.loc[means["moyenne"].idxmax(), "code"] if len(means) else "—"
    max_moy  = means["moyenne"].max()
    is_rank  = (view_mode == "ranking")

    def card(label, value, sub, clickable_id=None):
        style = {
            "flex": "1", "borderRadius": "8px", "padding": "8px 10px",
            "background": "rgba(240,192,64,0.12)" if (clickable_id and is_rank)
                          else "rgba(255,255,255,0.04)",
            "border": "1px solid rgba(240,192,64,0.5)" if (clickable_id and is_rank)
                      else "1px solid rgba(255,255,255,0.07)",
            "cursor": "pointer" if clickable_id else "default",
            "transition": "background 0.2s, border 0.2s",
        }
        inner = [
            html.Div(value, style={"fontSize": "25px",
                                   "fontFamily": "'DM Serif Display', serif",
                                   "color": "#f0c040", "lineHeight": "1.2"}),
            html.Div(label, style={"fontSize": "9px", "color": "#8892a4",
                                   "letterSpacing": "0.08em", "marginTop": "2px"}),
            html.Div(sub,   style={"fontSize": "10px", "color": "#c8cad6",
                                   "marginTop": "2px"}),
        ]
        if clickable_id:
            inner.append(html.Div(
                "▲ fermer" if is_rank else "▼ voir liste",
                style={"fontSize": "9px", "color": "#f0c040",
                       "marginTop": "3px", "letterSpacing": "0.06em"},
            ))
        props = {"style": style, "children": inner}
        if clickable_id:
            props["id"]       = clickable_id
            props["n_clicks"] = 0
        return html.Div(**props)

    return [
        card("MOY. NATIONALE",  f"{avg_fr:.2f}", f"{n_days} jours"),
        card("DEPTS EN ALERTE", str(n_alerte),   "moy. ≥ jaune"),
        card("DEPT LE + CHAUD", f"{max_moy:.2f}", get_nom(dept_max)[:18],
             clickable_id="ranking-trigger"),
    ]


# ──────────────────────────────────────────────
# 6. CSS GLOBAL
# ──────────────────────────────────────────────
app.index_string = """
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d1120; overflow: hidden; }

        /* Slider */
        .rc-slider-rail         { background: rgba(255,255,255,0.1) !important; }
        .rc-slider-track        { background: #f0c040 !important; }
        .rc-slider-handle       { border-color: #f0c040 !important; background: #f0c040 !important; }
        .rc-slider-handle:hover { box-shadow: 0 0 0 4px rgba(240,192,64,0.2) !important; }
        .rc-slider-mark-text    { color: #8892a4 !important; }

        /* DatePicker */
        .SingleDatePickerInput {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 6px !important;
        }
        .DateInput_input {
            background: transparent !important;
            color: #e8eaf0 !important;
            font-family: 'DM Sans', sans-serif !important;
            font-size: 12px !important;
        }
        .DayPicker            { background: #1a2035 !important; }
        .CalendarDay__default { background: #1a2035 !important; color: #e8eaf0 !important; }
        .CalendarDay__selected { background: #f0c040 !important; color: #0d1120 !important; }
        .CalendarDay__hovered_span,
        .CalendarDay__selected_span { background: rgba(240,192,64,0.3) !important; }

        /* Dropdown recherche */
        .Select-control {
            background: rgba(13,17,32,0.92) !important;
            border: 1px solid rgba(255,255,255,0.18) !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 12px rgba(0,0,0,0.4) !important;
        }
        .Select-control:hover { border-color: rgba(240,192,64,0.5) !important; }
        .Select-menu-outer {
            background: #141929 !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5) !important;
            margin-top: 2px !important;
        }
        .VirtualizedSelectOption           { background: #141929 !important; color: #c8cad6 !important; padding: 8px 12px !important; }
        .VirtualizedSelectFocusedOption    { background: rgba(240,192,64,0.12) !important; color: #f0c040 !important; }
        .VirtualizedSelectSelectedOption   { background: rgba(240,192,64,0.08) !important; }
        .Select-value-label                { color: #e8eaf0 !important; }
        .Select-placeholder                { color: #4a5568 !important; font-size: 12px !important; }
        .Select-input > input              { color: #e8eaf0 !important; font-family: 'DM Sans', sans-serif; font-size: 12px !important; }
        .Select-arrow-zone .Select-arrow   { border-top-color: #8892a4 !important; }
        .Select--single .Select-value      { color: #e8eaf0 !important; line-height: 38px !important; }
        .Select-clear-zone                 { color: #8892a4 !important; }
        .Select-clear-zone:hover           { color: #f0c040 !important; }

        /* Classement : hover sur lignes */
        #ranking-panel > div > div > div:hover {
            background: rgba(255,255,255,0.05) !important;
        }

        /* Scrollbar fine */
        ::-webkit-scrollbar       { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
"""


# ──────────────────────────────────────────────
# 7. LANCEMENT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if not DATA_LOADED:
        print(f"\n⚠  Erreur de chargement des données : {LOAD_ERROR}")
        print("   Vérifiez GEOJSON_PATH et CSV_PATH en haut du fichier.\n")
    else:
        print(f"\n✓  {len(df_global)} lignes CSV chargées")
        print(f"✓  {len(dept_codes)} départements dans le GeoJSON")
        print(f"\n→  Ouvrez http://127.0.0.1:8050  (Ctrl+C pour arrêter)\n")
    app.run(debug=False, port=8050)