import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- 1. Configuración de la Página ---
st.set_page_config(page_title="Asepeyo Net Zero Map", layout="wide")
st.title("Mapa de Infraestructura y Energía de Centros Asepeyo")

# --- 2. Funciones Auxiliares y de Mapeo de Colores ---
def get_rating_color(rating):
    """Mapea las calificaciones energéticas a colores de marcadores de Folium (espectro Rojo a Verde)"""
    rating = str(rating).strip().upper()
    colors = {
        'A': 'darkgreen', 'B': 'green', 'C': 'lightgreen', 
        'D': 'orange', 'E': 'lightred', 'F': 'red', 'G': 'darkred'
    }
    return colors.get(rating, 'gray')

def get_dist_color(dist):
    """Mapea distribuidoras eléctricas específicas a colores hexadecimales para la capa translúcida"""
    dist = str(dist).lower()
    if 'endesa' in dist: return '#0056b3'    # Azul Oscuro
    if 'iberdrola' in dist: return '#28a745' # Verde Bosque
    if 'naturgy' in dist: return '#fd7e14'   # Naranja
    if 'edp' in dist: return '#dc3545'       # Rojo
    if 'viesgo' in dist: return '#6f42c1'    # Morado
    if 'gaselec' in dist: return '#20c997'   # Turquesa
    return '#adb5bd'                         # Gris por Defecto

def get_gas_distributor(cups_gas):
    """Deduce la Distribuidora de Gas española basándose en el prefijo del CUPS de Gas"""
    if pd.isna(cups_gas) or str(cups_gas).strip() == '':
        return 'Sin Suministro de Gas'
        
    prefix = str(cups_gas).strip().upper()[:6]
    
    nedgia_prefixes = ['ES0203', 'ES0217', 'ES0218', 'ES0219', 'ES0220', 'ES0221', 'ES0222', 'ES0223', 'ES0224', 'ES0226', 'ES0227', 'ES0230', 'ES0237', 'ES0239', 'ES0242']
    redexis_prefixes = ['ES0202', 'ES0204', 'ES0205', 'ES0206', 'ES0208', 'ES0209', 'ES0225', 'ES0228', 'ES0238']
    nortegas_prefixes = ['ES0201', 'ES0211', 'ES0212', 'ES0213', 'ES0214', 'ES0215', 'ES0229']
    mrg_prefixes = ['ES0234', 'ES0236']
    
    if prefix in nedgia_prefixes: return 'Nedgia (Naturgy)'
    if prefix in redexis_prefixes: return 'Redexis Gas'
    if prefix in nortegas_prefixes: return 'Nortegas'
    if prefix in mrg_prefixes: return 'Madrileña Red de Gas'
    if prefix == 'ES0207': return 'Gas Extremadura'
    
    return 'Otra Distribuidora de Gas'

# --- 3. Carga de Datos (Desde GitHub) ---
@st.cache_data
def load_data():
    github_url = "https://raw.githubusercontent.com/hardik5838/Mapa_Asepeyo_Suminitros/refs/heads/main/data.csv"
    
    try:
        df = pd.read_csv(github_url)
        
        # Divide 'Geo-Loaction' en columnas separadas de Latitud y Longitud
        if 'Geo-Loaction' in df.columns:
            coords = df['Geo-Loaction'].astype(str).str.split(',', expand=True)
            if coords.shape[1] >= 2:
                df['Latitude'] = pd.to_numeric(coords[0], errors='coerce')
                df['Longitude'] = pd.to_numeric(coords[1], errors='coerce')
                
        # Genera automáticamente la columna de Distribuidora de Gas basada en el CUPS de Gas
        if 'Cups Gas' in df.columns:
            df['Distribuidora Gas'] = df['Cups Gas'].apply(get_gas_distributor)
                
        return df
        
    except Exception as e:
        st.warning(f"⚠️ No se pudieron cargar los datos desde GitHub. Error: {e}")
        return pd.DataFrame()

df = load_data()

# --- 4. Filtros Principales ---
st.header("Filtrar Centros")
col1, col2, col3, col4 = st.columns(4)

with col1:
    elec_filter = st.multiselect("Distribuidora Eléctrica", df['Distribuidora Eléctrica'].dropna().unique() if 'Distribuidora Eléctrica' in df.columns else [])
with col2:
    if 'Distribuidora Gas' in df.columns:
        gas_options = df['Distribuidora Gas'].unique().tolist()
        gas_filter = st.multiselect("Distribuidora de Gas", gas_options)
    else:
        gas_filter = []
with col3:
    comunidad_filter = st.multiselect("Región (Comunidad Autónoma)", df['Comunidad'].dropna().unique() if 'Comunidad' in df.columns else [])
with col4:
    rating_filter = st.multiselect("Calificación Energética", df['Energy Rating'].dropna().unique() if 'Energy Rating' in df.columns else [])

# Aplicar filtros al dataframe
filtered_df = df.copy()
if elec_filter:
    filtered_df = filtered_df[filtered_df['Distribuidora Eléctrica'].isin(elec_filter)]
if gas_filter:
    filtered_df = filtered_df[filtered_df['Distribuidora Gas'].isin(gas_filter)]
if comunidad_filter:
    filtered_df = filtered_df[filtered_df['Comunidad'].isin(comunidad_filter)]
if rating_filter:
    filtered_df = filtered_df[filtered_df['Energy Rating'].isin(rating_filter)]

# --- 5. Configuración del Mapa Interactivo ---
st.header("Mapa Interactivo")
# Centrar el mapa en España
m = folium.Map(location=[40.4637, -3.7492], zoom_start=6, tiles="CartoDB positron")

# Capa 1: Máscaras Regionales de Distribuidoras
mask_layers = {
    'Endesa': folium.FeatureGroup(name="Zona Eléctrica: Endesa", show=True),
    'Iberdrola': folium.FeatureGroup(name="Zona Eléctrica: Iberdrola", show=True),
    'Naturgy': folium.FeatureGroup(name="Zona Eléctrica: Naturgy", show=True),
    'Others': folium.FeatureGroup(name="Zona Eléctrica: Otras", show=True)
}

for idx, row in filtered_df.iterrows():
    if pd.notna(row.get('Latitude')) and pd.notna(row.get('Longitude')):
        dist = str(row.get('Distribuidora Eléctrica', 'Desconocida'))
        dist_lower = dist.lower()
        
        if 'endesa' in dist_lower: layer_group = mask_layers['Endesa']
        elif 'iberdrola' in dist_lower: layer_group = mask_layers['Iberdrola']
        elif 'naturgy' in dist_lower: layer_group = mask_layers['Naturgy']
        else: layer_group = mask_layers['Others']
            
        folium.Circle(
            location=[row['Latitude'], row['Longitude']],
            radius=45000, 
            color=None,
            fill=True,
            fill_color=get_dist_color(dist),
            fill_opacity=0.25,
            tooltip=f"Distribuidora Eléctrica: {dist}"
        ).add_to(layer_group)

for layer in mask_layers.values():
    layer.add_to(m)

# Capa 2: Marcadores de Centros
pins_layer = folium.FeatureGroup(name="📍 Mostrar/Ocultar Puntos", show=True)

for idx, row in filtered_df.iterrows():
    if pd.notna(row.get('Latitude')) and pd.notna(row.get('Longitude')):
        
        rating_val = row.get('Energy Rating', 'Pendiente')
        pin_color = get_rating_color(rating_val)
        gmaps_link = f"https://www.google.com/maps/search/?api=1&query={row['Latitude']},{row['Longitude']}"
        
        # Formateo de Información de Electricidad y Gas
        cups_elec = row.get('CUPs', 'N/A')
        dist_elec = row.get('Distribuidora Eléctrica', 'N/A')
        
        cups_gas = row.get('Cups Gas', 'N/A') if pd.notna(row.get('Cups Gas')) else 'Sin Suministro de Gas'
        dist_gas = row.get('Distribuidora Gas', 'N/A')
        
        # Formato HTML para la ventana emergente (Popup)
        popup_info = f"""
        <div style="font-family: Arial, sans-serif; min-width: 250px;">
            <h4 style="margin-bottom: 5px; color: #004b87;">{row.get('Centre', 'Desconocido')}</h4>
            <hr style="margin: 5px 0;">
            <span style="background-color: {pin_color}; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; float: right;">{rating_val}</span>
            <b>Estado de Auditoría:</b> {row.get('Audit Status', 'N/A')}<br><br>
            
            <b style="color: #d9534f;">⚡ Electricidad</b><br>
            <b>CUPS:</b> {cups_elec}<br>
            <b>Distribuidora:</b> {dist_elec}<br><br>
            
            <b style="color: #5cb85c;">🔥 Gas</b><br>
            <b>CUPS:</b> {cups_gas}<br>
            <b>Distribuidora:</b> {dist_gas}<br><br>
            
            <a href="{gmaps_link}" target="_blank" style="text-decoration: none; color: #0056b3; font-weight: bold;">📍 Abrir en Google Maps</a>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=6,
            color="white",
            weight=1,
            fill=True,
            fill_color=pin_color,
            fill_opacity=1.0,
            popup=folium.Popup(popup_info, max_width=350),
            tooltip=row.get('Centre', 'Centro Asepeyo')
        ).add_to(pins_layer)

pins_layer.add_to(m)

# Control de capas - Expandido y posicionado arriba a la izquierda para no tapar el mapa
folium.LayerControl(position='topleft', collapsed=False).add_to(m)

st_folium(m, width=1200, height=650, returned_objects=[])

# --- 6. Tabla de Datos y Exportación ---
st.header("Datos de los Centros")
display_df = filtered_df.drop(columns=['Latitude', 'Longitude'], errors='ignore')
st.dataframe(display_df, use_container_width=True)

csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Descargar datos filtrados como CSV",
    data=csv,
    file_name='asepeyo_filtered_centers.csv',
    mime='text/csv',
)
