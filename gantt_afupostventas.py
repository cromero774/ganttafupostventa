import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, callback_context
import requests
from datetime import datetime
import time

# --- Función de debug ---
def debug_print(message):
    print(f"DEBUG: {message}")  # Activado para debug

# --- URL de la hoja de Google Sheets ---
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR3rrcWGJWtEbowD_8bJ35lbziZ208DFGdo1JkHKhMvRK9SBjxxlTolXjeoKVMu4v447yfgQn0tUjsT/pub?output=csv"

# --- Función para cargar datos ---
def cargar_datos():
    debug_print(f"Cargando datos a las {datetime.now().strftime('%H:%M:%S')}")
    try:
        response = requests.get(sheet_url, timeout=15)
        response.raise_for_status()
        df = pd.read_csv(sheet_url, encoding='utf-8')
        df.columns = df.columns.str.strip().str.lower()  # ← Normalización de nombres
        df['rn'] = df['rn'].astype(str).str.strip()

        if 'afu asignado' not in df.columns:
            df['afu asignado'] = 'Sin asignar'

        for col in ['inicio', 'fin']:
            try:
                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
            except:
                try:
                    df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='coerce')
                except:
                    try:
                        df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                    except Exception:
                        pass

        df = df.dropna(subset=['inicio', 'fin'])
        df['inicio_str'] = df['inicio'].dt.strftime('%d-%m-%Y')
        df['fin_str'] = df['fin'].dt.strftime('%d-%m-%Y')
        df['duracion'] = (df['fin'] - df['inicio']).dt.days
        df['mes'] = df['fin'].dt.to_period('M').astype(str)
        df['rn_trunc'] = df['rn'].str.lower().apply(lambda x: x if len(x) <= 30 else x[:27] + '...')
        
        return df, True
    
    except Exception as e:
        debug_print(f"Error al cargar datos: {e}")
        sample_dates = pd.date_range(start='2023-01-01', periods=3)
        df = pd.DataFrame({
            'rn': ['Error - Sin datos', 'Ejemplo 2', 'Ejemplo 3'],
            'estado': ['Error', 'Error', 'Error'],
            'afu asignado': ['Sin asignar', 'Sin asignar', 'Sin asignar'],
            'inicio': sample_dates,
            'fin': sample_dates + pd.Timedelta(days=30),
        })
        df['inicio_str'] = df['inicio'].dt.strftime('%d-%m-%Y')
        df['fin_str'] = df['fin'].dt.strftime('%d-%m-%Y')
        df['duracion'] = 30
        df['mes'] = df['fin'].dt.to_period('M').astype(str)
        df['rn_trunc'] = df['rn'].str.lower()
        return df, False

# --- Carga inicial de datos ---
df, carga_exitosa = cargar_datos()

# --- Colores por estado ---
color_estado = {
    'Entregado': '#2ecc71',
    'En desarrollo': '#1abc9c',
    'Backlog': '#f1c40f',
    'Para refinar': '#f5d76e',
    'Escribiendo': '#e67e22',
    'Para escribir': '#e74c3c',
    'En análisis': '#9b59b6',
    'Cancelado': '#95a5a6',
    'Error': '#e74c3c'
}

# --- App Dash ---
app = Dash(__name__)
server = app.server

# --- Layout ---
app.layout = html.Div([
    html.H1("Gantt análisis funcional Postventas", style={'textAlign': 'center'}),
    html.Div([
        html.Div([
            html.Label("Mes de entrega:"),
            dcc.Dropdown(
                id='mes-dropdown',
                options=[{'label': 'Todos', 'value': 'Todos'}] +
                        [{'label': mes, 'value': mes} for mes in sorted(df['mes'].unique())],
                value='Todos',
                clearable=False
            )
        ], style={'width': '24%', 'display': 'inline-block'}),
        html.Div([
            html.Label("Estado:"),
            dcc.Dropdown(
                id='estado-dropdown',
                options=[{'label': 'Todos', 'value': 'Todos'}] +
                        [{'label': estado, 'value': estado} for estado in sorted(df['estado'].unique())],
                value='Todos',
                clearable=False
            )
        ], style={'width': '24%', 'display': 'inline-block', 'marginLeft': '10px'}),
        html.Div([
            html.Label("AFU asignado:"),
            dcc.Dropdown(
                id='afu-dropdown',
                options=[{'label': 'Todos', 'value': 'Todos'}] +
                        [{'label': afu, 'value': afu} for afu in sorted(df['afu asignado'].unique())],
                value='Todos',
                clearable=False
            )
        ], style={'width': '24%', 'display': 'inline-block', 'marginLeft': '10px'}),
        html.Div([
            html.Button('Actualizar datos', id='refresh-button', 
                       style={'marginTop': '20px', 'padding': '8px 16px', 'backgroundColor': '#3498db', 
                              'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer'}),
            html.Div(id='last-update-time', 
                    children=f"Última actualización: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
                    style={'marginTop': '5px', 'fontSize': '12px'})
        ], style={'width': '24%', 'display': 'inline-block', 'marginLeft': '10px', 'textAlign': 'center'})
    ], style={'marginBottom': '20px'}),

    html.Div([
        html.Label("Tema:"),
        dcc.RadioItems(
            id='theme-switch',
            options=[
                {'label': 'Claro', 'value': 'light'},
                {'label': 'Oscuro', 'value': 'dark'}
            ],
            value='light',
            labelStyle={'display': 'inline-block', 'marginRight': '10px'}
        )
    ], style={'marginBottom': '20px'}),

    # Añadir un intervalo para actualizaciones automáticas (cada 60 segundos)
    dcc.Interval(
        id='interval-component',
        interval=60*1000,  # en milisegundos (60 segundos)
        n_intervals=0
    ),
    
    # Almacenar los datos en componente oculto
    dcc.Store(id='stored-data'),
    
    html.Div([
        dcc.Graph(id='gantt-graph', style={'height': '80vh'})
    ])
])

# Callback para actualizar los datos cuando se hace clic en el botón o por el intervalo
@app.callback(
    [Output('stored-data', 'data'),
     Output('mes-dropdown', 'options'),
     Output('estado-dropdown', 'options'),
     Output('afu-dropdown', 'options'),
     Output('last-update-time', 'children')],
    [Input('refresh-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    [State('mes-dropdown', 'value'),
     State('estado-dropdown', 'value'),
     State('afu-dropdown', 'value')]
)
def actualizar_datos(n_clicks, n_intervals, mes_actual, estado_actual, afu_actual):
    # Cargar datos actualizados
    df_actualizado, _ = cargar_datos()
    
    # Actualizar opciones de los dropdowns
    opciones_mes = [{'label': 'Todos', 'value': 'Todos'}] + [
        {'label': mes, 'value': mes} for mes in sorted(df_actualizado['mes'].unique())
    ]
    
    opciones_estado = [{'label': 'Todos', 'value': 'Todos'}] + [
        {'label': estado, 'value': estado} for estado in sorted(df_actualizado['estado'].unique())
    ]
    
    opciones_afu = [{'label': 'Todos', 'value': 'Todos'}] + [
        {'label': afu, 'value': afu} for afu in sorted(df_actualizado['afu asignado'].unique())
    ]
    
    # Actualizar tiempo de la última actualización
    tiempo_actualizacion = f"Última actualización: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
    
    # Convertir DataFrame a diccionario para almacenarlo
    return df_actualizado.to_dict('records'), opciones_mes, opciones_estado, opciones_afu, tiempo_actualizacion

# --- Callback ---
@app.callback(
    Output('gantt-graph', 'figure'),
    [Input('stored-data', 'data'),
     Input('mes-dropdown', 'value'),
     Input('estado-dropdown', 'value'),
     Input('afu-dropdown', 'value'),
     Input('theme-switch', 'value')]
)
def actualizar_grafico(data, mes, estado, afu, theme):
    # Convertir datos almacenados de nuevo a DataFrame
    if not data:
        # Usar datos iniciales si aún no hay datos almacenados
        df_filtrado = df.copy()
    else:
        df_filtrado = pd.DataFrame(data)
        # Convertir columnas de fecha de nuevo a datetime
        for col in ['inicio', 'fin']:
            if col in df_filtrado.columns:
                df_filtrado[col] = pd.to_datetime(df_filtrado[col])

    # Aplicar filtros
    if mes != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['mes'] == mes]
    if estado != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['estado'] == estado]
    if afu != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['afu asignado'] == afu]

    if df_filtrado.empty:
        return px.scatter(title="Sin datos con los filtros seleccionados")

    if theme == 'dark':
        plot_bgcolor = '#23272f'
        paper_bgcolor = '#23272f'
        font_color = '#f0f0f0'
        gridcolor = '#444'
        fecha_actual_color = 'rgba(255, 255, 255, 0.15)'
        fecha_text_color = '#e2e8f0'
    else:
        plot_bgcolor = 'white'
        paper_bgcolor = 'white'
        font_color = '#222'
        gridcolor = '#eee'
        fecha_actual_color = 'rgba(66, 153, 225, 0.15)'
        fecha_text_color = '#3182ce'

    df_filtrado = df_filtrado.sort_values('inicio')
    rn_order = df_filtrado['rn_trunc'].unique().tolist()
    df_filtrado['rn_order'] = df_filtrado['rn_trunc'].map({rn: i for i, rn in enumerate(rn_order)})
    df_filtrado = df_filtrado.sort_values('rn_order')

    try:
        fig = px.timeline(
            df_filtrado,
            x_start="inicio",
            x_end="fin",
            y="rn_trunc",
            color="estado",
            custom_data=["rn", "inicio_str", "fin_str", "duracion", "afu asignado"],
            color_discrete_map=color_estado,
            title=f"Postventas - {estado if estado != 'Todos' else 'Todos los estados'} | {mes if mes != 'Todos' else 'Todos los meses'} | {afu if afu != 'Todos' else 'Todos los AFU'}"
        )

        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Inicio: %{customdata[1]}<br>Fin: %{customdata[2]}<br>Duración: %{customdata[3]} días<br>AFU: %{customdata[4]}",
            marker=dict(line=dict(width=0.3, color='DarkSlateGrey'))
        )

        fecha_actual = datetime.now()
        fecha_actual_str = fecha_actual.strftime('%d-%m-%Y')

        fig.add_shape(
            type="rect",
            x0=fecha_actual,
            x1=fecha_actual + pd.Timedelta(hours=3),
            y0=-0.5,
            y1=len(rn_order),
            xref="x",
            yref="y",
            fillcolor=fecha_actual_color,
            opacity=0.6,
            layer="below",
            line_width=0
        )

        fig.add_annotation(
            x=fecha_actual,
            y=len(rn_order) + 0.5,
            text=f"Hoy: {fecha_actual_str}",
            showarrow=False,
            yshift=5,
            xshift=0,
            xanchor="center",
            yanchor="bottom",
            font=dict(color=fecha_text_color, size=9),
            opacity=0.9
        )

        fig.update_layout(
            xaxis=dict(title="Fecha", tickformat="%d-%m-%Y", gridcolor=gridcolor),
            yaxis=dict(
                autorange="reversed", 
                title="Requerimiento",
                categoryorder='array',
                categoryarray=rn_order,
                tickfont=dict(size=11),
                title_font=dict(size=13)
            ),
            plot_bgcolor=plot_bgcolor,
            paper_bgcolor=paper_bgcolor,
            font=dict(color=font_color),
            legend=dict(title="Estado", x=1.01, y=1),
            margin=dict(l=20, r=250, t=50, b=50),
            height=max(400, 25 * len(df_filtrado))
        )

        return fig

    except Exception as e:
        debug_print(f"Error al generar gráfico: {e}")
        return px.scatter(title=f"Error al generar gráfico: {e}")

# --- Ejecutar ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)


































































