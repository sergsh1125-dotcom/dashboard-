import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
import os

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Стан забезпечення підрозділів ОРСЦЗ засобами РХБ захисту")

# =====================================================
# 1. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл")
    st.stop()

df = pd.read_excel(uploaded_file)
df.columns = df.columns.str.strip().str.lower()

required_columns = [
    "region_name",
    "category",
    "product_name",
    "quantity",
    "required_quantity"
]

if not all(col in df.columns for col in required_columns):
    st.error("❌ У файлі відсутні необхідні колонки")
    st.write(df.columns.tolist())
    st.stop()

# очистка
df["region_name"] = df["region_name"].astype(str).str.strip()
df["category"] = df["category"].astype(str).str.strip().str.lower()
df["product_name"] = df["product_name"].fillna("").astype(str).str.strip()
df = df[df["product_name"] != ""]

for col in ["quantity", "required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 2. ДОВІДНИКИ
# =====================================================

subunits = [
    "ГМРЦШР",
    'МРЦШР "Суми"',
    'МРЦШР "Одеса"',
    "САЗ ОРС ЦЗ"
]

category_display = {
    "спеціальна техніка": "Спеціальна техніка",
    "прилади рр": "Прилади РР",
    "прилади хр": "Прилади ХР",
    "прилади рр_офіцери_рятувальники": "Прилади РР (офіцери-рятувальники)",
    "прилади хр_офіцери-рятувальники": "Прилади ХР (офіцери-рятувальники)",
    "протигази": "Протигази",
    "респіратори": "Респіратори",
    "захисний одяг": "Захисний одяг"
}

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].dropna().unique())
)

selected_category_display = st.sidebar.selectbox(
    "Категорія",
    ["Всі"] + list(category_display.values())
)

reverse_map = {v: k for k, v in category_display.items()}
selected_category = reverse_map.get(selected_category_display, "Всі")

if selected_category != "Всі":
    product_options = df[df["category"] == selected_category]["product_name"]
else:
    product_options = df["product_name"]

product_options = pd.Series(product_options).dropna().astype(str)

selected_product = st.sidebar.selectbox(
    "Найменування засобу РХБЗ",
    ["Всі"] + sorted(product_options.unique())
)

# =====================================================
# 4. ФІЛЬТРАЦІЯ
# =====================================================

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_category != "Всі":
    filtered_df = filtered_df[filtered_df["category"] == selected_category]

if selected_product != "Всі":
    filtered_df = filtered_df[
        filtered_df["product_name"] == selected_product
    ]

# =====================================================
# 5. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity", "sum"),
        total_required=("required_quantity", "sum")
    )
    .reset_index()
)

region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"] / row["total_required"]) * 100, 1)
    if row["total_required"] > 0 else 0,
    axis=1
)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).clip(lower=0)

# =====================================================
# 6. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1, col2, col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

percent_total = round((total_quantity / total_required) * 100, 1) if total_required > 0 else 0
col3.metric("% забезпечення", f"{percent_total}%")

# =====================================================
# 7. ТАБЛИЦЯ
# =====================================================

region_summary["is_subunit"] = region_summary["region_name"].isin(subunits)

region_summary = region_summary.sort_values(
    by=["is_subunit", "region_name"]
)

display_table = region_summary.rename(columns={
    "region_name": "Регіон",
    "total_quantity": "Наявність",
    "total_required": "Потреба"
}).drop(columns=["is_subunit"])

st.subheader("Дані по регіонах")
st.dataframe(display_table, use_container_width=True)

# =====================================================
# 8. ГРАФІК
# =====================================================

st.subheader("Графік забезпечення (%)")

chart_df = region_summary.sort_values(
    by=["is_subunit", "% забезпечення"],
    ascending=[True, False]
)

st.bar_chart(
    chart_df.set_index("region_name")["% забезпечення"]
)

# =====================================================
# 6. КАРТА З ЛЕГЕНДОЮ
# =====================================================
st.write("---")
st.subheader("🗺️ Карта стану забезпечення засобами РХБЗ в регіонах")

def get_color(c):
    if c >= 100: return "#1a9850"
    if c >= 86:  return "#91cf60"
    if c >= 71:  return "#fee08b"
    if c >= 51:  return "#fc8d59"
    return "#d73027"

region_name_map = {
    "Київ": ["Kyiv_city", "Kyiv"], "Вінницька область": ["Vinnytska"], "Волинська область": ["Volynska"],
    "Дніпропетровська область": ["Dnipropetrovska"], "Донецька область": ["Donetska"],
    "Житомирська область": ["Zhytomyrska"], "Закарпатська область": ["Zakarpatska"],
    "Запорізька область": ["Zaporizka"], "Івано-Франківська область": ["Ivano-Frankivska"],
    "Київська область": ["Kyivska"], "Кіровоградська область": ["Kirovohradska"],
    "Луганська область": ["Luhanska"], "Львівська область": ["Lvivska"],
    "Миколаївська область": ["Mykolaivska"], "Одеська область": ["Odeska"],
    "Полтавська область": ["Poltavska"], "Рівненська область": ["Rivnenska"],
    "Сумська область": ["Sumska"], "Тернопільська область": ["Ternopilska"],
    "Харківська область": ["Kharkivska"], "Херсонська область": ["Khersonska"],
    "Хмельницька область": ["Khmelnytska"], "Черкаська область": ["Cherkaska"],
    "Чернівецька область": ["Chernivetska"], "Чернігівська область": ["Chernihivska"]
}

if os.path.exists(GEOJSON_PATH):
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    map_lookup = {row["region_name"]: row for _, row in region_summary.iterrows()}

    for feature in geojson_data["features"]:
        eng_n = feature["properties"]["name"]
        ukr_n = next((k for k, v in region_name_map.items() if eng_n in v), eng_n)
        d = map_lookup.get(ukr_n, {"% забезпечення": 0, "Нестача": 0})
        feature["properties"]["ukr_label"] = ukr_n
        feature["properties"]["coverage"] = f"{d['% забезпечення']}%"
        feature["properties"]["shortage"] = f"{int(d['Нестача'])} од."
        feature["properties"]["val"] = d["% забезпечення"]

    def style_func(feature):
        val = feature["properties"]["val"]
        u_name = feature["properties"]["ukr_label"]
        opac = 0.75
        if selected_region != "Всі" and u_name != selected_region: opac = 0.1
        return {"fillColor": get_color(val), "color": "black", "weight": 1.2, "fillOpacity": opac}

    col_m, col_l = st.columns([8, 2])
    with col_m:
        m = folium.Map(location=[48.3, 31.1], zoom_start=6, tiles="cartodbpositron")
        folium.GeoJson(geojson_data, style_function=style_func,
                       tooltip=folium.GeoJsonTooltip(fields=["ukr_label", "coverage", "shortage"], 
                       aliases=["Регіон:", "Забезп.:", "Нестача:"])).add_to(m)
        
        k_d = map_lookup.get("Київ", {"% забезпечення": 0, "Нестача": 0})
        folium.CircleMarker(location=[50.4501, 30.5234], radius=10, color="black", weight=2, 
                            fill=True, fill_color=get_color(k_d["% забезпечення"]), fill_opacity=0.9,
                            tooltip=f"Місто Київ: {k_d['% забезпечення']}%").add_to(m)
        st_folium(m, width="100%", height=600, key="map_update")

    with col_l:
        st.markdown("""
        <div style="background-color: white; padding: 15px; border: 2px solid #333; border-radius: 10px; color: black;">
            <b style="font-size: 16px;">Легенда (%)</b><br><br>
            <div style="margin-bottom: 8px;"><span style="color: #1a9850; font-size: 20px;">●</span> 100%+</div>
            <div style="margin-bottom: 8px;"><span style="color: #91cf60; font-size: 20px;">●</span> 86% – 99%</div>
            <div style="margin-bottom: 8px;"><span style="color: #fee08b; font-size: 20px;">●</span> 71% – 85%</div>
            <div style="margin-bottom: 8px;"><span style="color: #fc8d59; font-size: 20px;">●</span> 51% – 70%</div>
            <div style="margin-bottom: 8px;"><span style="color: #d73027; font-size: 20px;">●</span> 0% – 50%</div>
        </div>""", unsafe_allow_html=True)
# =====================================================
# 10. ЕКСПОРТ
# =====================================================

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

st.download_button(
    "📥 Завантажити звіт",
    convert_to_excel(display_table),
    "zvit.xlsx"
)
