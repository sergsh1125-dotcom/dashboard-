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
        "Київ","Київська область","Львівська область","Одеська область",
        "Харківська область","Дніпропетровська область","Полтавська область",
        "Сумська область","Вінницька область","Волинська область","Закарпатська область",
        "Запорізька область","Івано-Франківська область","Кіровоградська область",
        "Луганська область","Миколаївська область","Рівненська область",
        "Тернопільська область","Херсонська область","Хмельницька область",
        "Черкаська область","Чернігівська область","Чернівецька область","Житомирська область"
    ]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # === Основний лист ===
        template_df = pd.DataFrame({
            "region_name": [],
            "product_name": [],
            "quantity": [],
            "required_quantity": []
        })
        template_df.to_excel(writer, sheet_name="Дані", index=False)

        # === Лист довідника ===
        max_len = max(len(allowed_regions), len(allowed_products))
        ref_df = pd.DataFrame({
            "Регіони": allowed_regions + [""]*(max_len - len(allowed_regions)),
            "Засоби": allowed_products + [""]*(max_len - len(allowed_products))
        })
        ref_df.to_excel(writer, sheet_name="Довідник", index=False)

        workbook = writer.book
        data_sheet = workbook["Дані"]

        # ---- Підсвітка заголовків
        header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
        for cell in data_sheet[1]:
            cell.fill = header_fill
            cell.protection = Protection(locked=True)

        # ---- Data Validation для регіонів
        dv_region = DataValidation(
            type="list",
            formula1=f"=Довідник!$A$2:$A${len(allowed_regions)+1}",
            allow_blank=True
        )
        dv_region.add("A2:A500")
        data_sheet.add_data_validation(dv_region)

        # ---- Data Validation для продуктів
        dv_product = DataValidation(
            type="list",
            formula1=f"=Довідник!$B$2:$B${len(allowed_products)+1}",
            allow_blank=True
        )
        dv_product.add("B2:B500")
        data_sheet.add_data_validation(dv_product)

        # ---- Data Validation для чисел >=0
        dv_number = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0",
            allow_blank=True
        )
        dv_number.add("C2:D500")
        data_sheet.add_data_validation(dv_number)

        # ---- Захист листа
        data_sheet.protection.sheet = True

    return output.getvalue()

st.sidebar.header("Excel шаблон")
if st.sidebar.button("📄 Завантажити шаблон Excel"):
    template_bytes = generate_template()
    st.sidebar.download_button(
        label="📥 Завантажити шаблон",
        data=template_bytes,
        file_name="template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =====================================================
# 2. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================
uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])
if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл для початку роботи.")
    st.stop()

df = pd.read_excel(uploaded_file)
df.columns = df.columns.str.strip().str.lower()

required_columns = ["region_name","product_name","quantity","required_quantity"]
if not all(col in df.columns for col in required_columns):
    st.error("У файлі відсутні необхідні колонки.")
    st.write("Знайдені колонки:", df.columns.tolist())
    st.stop()

for col in ["quantity","required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================
st.sidebar.header("Фільтри")
selected_region = st.sidebar.selectbox("Регіон", ["Всі"] + sorted(df["region_name"].unique()))
selected_product = st.sidebar.selectbox("Засіб РХБЗ", ["Всі"] + sorted(df["product_name"].unique()))

filtered_df = df.copy()
if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"]==selected_region]
if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"]==selected_product]

# =====================================================
# 4. АГРЕГАЦІЯ
# =====================================================
region_summary = (
    filtered_df.groupby("region_name")
    .agg(total_quantity=("quantity","sum"), total_required=("required_quantity","sum"))
    .reset_index()
)
region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"]/row["total_required"])*100,1)
    if row["total_required"]>0 else 0,
    axis=1
)
region_summary["Нестача"] = (region_summary["total_required"] - region_summary["total_quantity"]).clip(lower=0)
region_summary["Надлишок"] = (region_summary["total_quantity"] - region_summary["total_required"]).clip(lower=0)

# =====================================================
# 5. KPI
# =====================================================
total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())
col1,col2,col3 = st.columns(3)
col1.metric("Наявність", total_quantity)
col2.metric("Штатна потреба", total_required)
overall_percent = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("Загальний % забезпечення", f"{overall_percent}%")

# =====================================================
# 6. ТАБЛИЦЯ
# =====================================================
display_table = region_summary.rename(columns={
    "region_name":"Регіон",
    "total_required":"Штатна потреба",
    "total_quantity":"Наявність"
})[["Регіон","Штатна потреба","Наявність","Нестача","Надлишок","% забезпечення"]]

st.subheader("Інформація по регіонах")
st.dataframe(display_table, use_container_width=True)
if (region_summary["% забезпечення"]<50).any():
    st.warning("⚠ Є регіони з критичним рівнем забезпечення (<50%)")

# =====================================================
# 7. ГРАФІК
# =====================================================
st.subheader("Рейтинг регіонів за % забезпечення")
st.bar_chart(region_summary.sort_values("% забезпечення", ascending=False).set_index("region_name")["% забезпечення"])

# =====================================================
# 8. КАРТА
# =====================================================
with open("data/ukraine_regions.geojson","r",encoding="utf-8") as f:
    geojson_data = json.load(f)

region_name_map = {
    "Київ": "Kyiv_city", "Київська область":"Kyivska", "Львівська область":"Lvivska",
    "Одеська область":"Odeska", "Харківська область":"Kharkivska", "Донецька область;"Donetska" ""Дніпропетровська область":"Dnipropetrovska",
    "Полтавська область":"Poltavska", "Сумська область":"Sumska", "Вінницька область":"Vinnytska",
    "Волинська область":"Volynska","Закарпатська область":"Zakarpatska","Запорізька область":"Zaporizka",
    "Івано-Франківська область":"Ivano-Frankivska","Кіровоградська область":"Kirovohradska","Луганська область":"Luhanska",
    "Миколаївська область":"Mykolaivska","Рівненська область":"Rivnenska","Тернопільська область":"Ternopilska",
    "Херсонська область":"Khersonska","Хмельницька область":"Khmelnytska","Черкаська область":"Cherkaska",
    "Чернігівська область":"Chernihivska","Чернівецька область":"Chernivetska","Житомирська область":"Zhytomyrska"
}

coverage_dict = {eng_name: float(region_summary.loc[region_summary["region_name"]==ukr_name,"% забезпечення"].values[0])
                 if not region_summary.loc[region_summary["region_name"]==ukr_name].empty else 0
                 for ukr_name, eng_name in region_name_map.items()}

def color_by_coverage(c):
    return "#ffffff" if c==0 else "#d73027" if c<50 else "#f46d43" if c<75 else "#fee08b" if c<100 else "#1a9850"

for feature in geojson_data["features"]:
    feature["properties"]["coverage"] = coverage_dict.get(feature["properties"]["name"],0)

m = folium.Map(location=[49,32], zoom_start=6, tiles="cartodbpositron", control_scale=True)
folium.GeoJson(
    geojson_data,
    style_function=lambda f: {"fillColor": color_by_coverage(f["properties"]["coverage"]),
                              "color":"black","weight":1,"fillOpacity":0.75}
).add_to(m)
st.subheader("Карта рівня забезпечення")
st_folium(m,width=1000,height=650)

# =====================================================
# 9. ЕКСПОРТ В EXCEL
# =====================================================
def convert_to_excel(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Звіт", index=False)
    return out.getvalue()

st.download_button(
    label="📥 Завантажити звіт в Excel",
    data=convert_to_excel(display_table),
    file_name="zvit_po_regionakh.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
