import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Дашборд забезпечення засобами РХБ захисту")

# =====================================================
# 1. ШАБЛОН EXCEL
# =====================================================

def generate_template():

    allowed_products = [
        "спеціальна техніка",
        "прилади РР",
        "прилади ХР",
        "протигази",
        "респіратори",
        "захисний одяг"
    ]

    allowed_regions = [
        "Київ","Вінницька область","Волинська область","Дніпропетровська область",
        "Донецька область","Житомирська область","Закарпатська область","Запорізька область",
        "Івано-Франківська область","Київська область","Кіровоградська область","Луганська область",
        "Львівська область","Миколаївська область","Одеська область","Полтавська область",
        "Рівненська область","Сумська область","Тернопільська область","Харківська область",
        "Херсонська область","Хмельницька область","Черкаська область","Чернівецька область",
        "Чернігівська область"
    ]

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        template_df = pd.DataFrame({
            "region_name": [],
            "product_name": [],
            "quantity": [],
            "required_quantity": []
        })

        template_df.to_excel(writer, sheet_name="Дані", index=False)

        max_len = max(len(allowed_regions), len(allowed_products))

        ref_df = pd.DataFrame({
            "Регіони": allowed_regions + [""]*(max_len-len(allowed_regions)),
            "Засоби": allowed_products + [""]*(max_len-len(allowed_products))
        })

        ref_df.to_excel(writer, sheet_name="Довідник", index=False)

        workbook = writer.book
        sheet = workbook["Дані"]

        header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

        for cell in sheet[1]:
            cell.fill = header_fill
            cell.protection = Protection(locked=True)

        dv_region = DataValidation(
            type="list",
            formula1=f"=Довідник!$A$2:$A${len(allowed_regions)+1}"
        )
        dv_region.add("A2:A500")
        sheet.add_data_validation(dv_region)

        dv_product = DataValidation(
            type="list",
            formula1=f"=Довідник!$B$2:$B${len(allowed_products)+1}"
        )
        dv_product.add("B2:B500")
        sheet.add_data_validation(dv_product)

        dv_number = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0"
        )

        dv_number.add("C2:D500")
        sheet.add_data_validation(dv_number)

        sheet.protection.sheet = True

    return output.getvalue()


st.sidebar.header("Excel шаблон")

if st.sidebar.button("📄 Завантажити шаблон Excel"):

    st.sidebar.download_button(
        label="📥 Завантажити",
        data=generate_template(),
        file_name="template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================
# 2. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл")
    st.stop()

df = pd.read_excel(uploaded_file)

df.columns = df.columns.str.strip().str.lower()

for col in ["quantity","required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].unique())
)

selected_product = st.sidebar.selectbox(
    "Засіб",
    ["Всі"] + sorted(df["product_name"].unique())
)

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# =====================================================
# 4. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity","sum"),
        total_required=("required_quantity","sum")
    )
    .reset_index()
)

region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"]/row["total_required"])*100,1)
    if row["total_required"]>0 else 0,
    axis=1
)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).clip(lower=0)

# =====================================================
# 5. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1,col2,col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

percent_total = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("% забезпечення", f"{percent_total}%")

# =====================================================
# 6. ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
"region_name":"Регіон",
"total_quantity":"Наявність",
"total_required":"Потреба"
})

st.subheader("Дані по регіонах")

st.dataframe(display_table, use_container_width=True)

# =====================================================
# 7. ГРАФІК
# =====================================================

st.subheader("Рейтинг регіонів")

st.bar_chart(
    region_summary
    .sort_values("% забезпечення", ascending=False)
    .set_index("region_name")["% забезпечення"]
)

# =====================================================
# 8. КАРТА
# =====================================================
with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
    geojson_data = json.load(f)

region_name_map = {
    "Київ":"Kyiv_city","Вінницька область":"Vinnytska","Волинська область":"Volynska",
    "Дніпропетровська область":"Dnipropetrovska","Донецька область":"Donetska",
    "Житомирська область":"Zhytomyrska","Закарпатська область":"Zakarpatska",
    "Запорізька область":"Zaporizka","Івано-Франківська область":"Ivano-Frankivska",
    "Київська область":"Kyivska","Кіровоградська область":"Kirovohradska","Луганська область":"Luhanska",
    "Львівська область":"Lvivska","Миколаївська область":"Mykolaivska","Одеська область":"Odeska",
    "Полтавська область":"Poltavska","Рівненська область":"Rivnenska","Сумська область":"Sumska",
    "Тернопільська область":"Ternopilska","Харківська область":"Kharkivska","Херсонська область":"Khersonska",
    "Хмельницька область":"Khmelnytska","Черкаська область":"Cherkaska","Чернівецька область":"Chernivetska",
    "Чернігівська область":"Chernihivska"
}

# словник % забезпечення
coverage_dict = {}
for ukr, eng in region_name_map.items():
    row = region_summary[region_summary["region_name"] == ukr]
    coverage_dict[eng] = float(row["% забезпечення"].values[0]) if not row.empty else 0

# кольори за 5 рівнями
def color_by_coverage(c):
    if c >= 100: return "#1a9850"
    elif c >= 86: return "#91cf60"
    elif c >= 71: return "#fee08b"
    elif c >= 51: return "#fc8d59"
    else: return "#d73027"

# карта
m = folium.Map(location=[49,32], zoom_start=6, tiles="cartodbpositron")

# стиль регіону
def style_function(feature):
    name = feature["properties"]["name"]
    coverage = coverage_dict.get(name,0)

    # затемнення неактивних регіонів
    if selected_region != "Всі":
        eng_selected = region_name_map.get(selected_region)
        if name != eng_selected:
            return {"fillColor":"#d9d9d9","color":"black","weight":1,"fillOpacity":0.35}

    return {"fillColor": color_by_coverage(coverage), "color":"black", "weight":1, "fillOpacity":0.75}

# tooltip: назва регіону + % забезпечення
tooltip = folium.GeoJsonTooltip(
    fields=["name"],
    aliases=["Регіон:"],
    labels=True,
    sticky=True,
    localize=True,
    toLocaleString=True,
    style=("background-color: white; color: black; font-weight: bold;"),
    fmt=lambda val, feature: f"{val} – {coverage_dict.get(feature['properties']['name'],0)}%"
)

folium.GeoJson(
    geojson_data,
    style_function=style_function,
    tooltip=tooltip
).add_to(m)

# компактна легенда з кружечками 18px
legend_html = """
<div style="
position: fixed;
bottom: 20px;
left: 20px;
width: 160px;
background-color: white;
border:2px solid grey;
padding:10px;
font-size:12px;
z-index:9999;
">

<b>Рівень забезпечення</b><br><br>
<span style="color:#1a9850;font-size:18px;">●</span> ≥100%<br>
<span style="color:#91cf60;font-size:18px;">●</span> 86–99%<br>
<span style="color:#fee08b;font-size:18px;">●</span> 71–85%<br>
<span style="color:#fc8d59;font-size:18px;">●</span> 51–70%<br>
<span style="color:#d73027;font-size:18px;">●</span> ≤50%

</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st.subheader("Карта стану забезпечення засобами РХБ захисту")
st_folium(m, width=1000, height=650)
# =====================================================
# 9. ЕКСПОРТ
# =====================================================

def convert_to_excel(df):

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()

st.download_button(
    "📥 Завантажити звіт Excel",
    convert_to_excel(display_table),
    "zvit.xlsx"
)
